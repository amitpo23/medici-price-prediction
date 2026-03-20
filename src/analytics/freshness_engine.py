"""Data freshness monitor — check last update times for all data sources.

Uses a single UNION ALL query to check all SQL sources at once (avoids
sequential MAX() on huge tables which times out). External sources
checked via file modification time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Expected max age in hours for each source type
FRESHNESS_THRESHOLDS = {
    "realtime": {"green": 4, "yellow": 24},
    "hourly": {"green": 6, "yellow": 24},
    "daily": {"green": 48, "yellow": 168},
    "weekly": {"green": 192, "yellow": 720},
    "static": {"green": 99999, "yellow": 99999},
}

# SQL source definitions: (name, query_fragment, frequency, description)
# Use TOP 1 ORDER BY DESC instead of MAX() — much faster on unindexed columns
SQL_SOURCES = [
    ("SalesOffice.Details", "SELECT TOP 1 DateUpdated AS lu FROM [SalesOffice.Details] ORDER BY DateUpdated DESC", "hourly", "Internal room price scans"),
    ("SalesOffice.Orders", "SELECT TOP 1 DateInsert AS lu FROM [SalesOffice.Orders] ORDER BY DateInsert DESC", "hourly", "Scan orders"),
    ("AI_Search_HotelData", "SELECT TOP 1 UpdatedAt AS lu FROM AI_Search_HotelData ORDER BY Id DESC", "realtime", "8.5M market pricing records"),
    ("SearchResultsSessionPollLog", "SELECT TOP 1 DateInsert AS lu FROM SearchResultsSessionPollLog ORDER BY Id DESC", "realtime", "8.3M provider search results"),
    ("RoomPriceUpdateLog", "SELECT TOP 1 DateInsert AS lu FROM RoomPriceUpdateLog ORDER BY Id DESC", "daily", "82K price change events"),
    ("MED_Book", "SELECT TOP 1 DateInsert AS lu FROM MED_Book ORDER BY id DESC", "daily", "Active bookings"),
    ("MED_PreBook", "SELECT TOP 1 DateInsert AS lu FROM MED_PreBook ORDER BY PreBookId DESC", "daily", "Pre-booking data"),
    ("SalesOffice.Log", "SELECT TOP 1 DateCreated AS lu FROM [SalesOffice.Log] ORDER BY Id DESC", "hourly", "1.2M action logs"),
]

# Static/archive sources — just check if they exist, don't query MAX
STATIC_SOURCES = [
    ("MED_SearchHotels", "static", "7M historical search (2020-2023)"),
]


def build_freshness_data() -> dict:
    """Check freshness of all data sources."""
    sources = []
    now = datetime.now(timezone.utc)

    # Check SQL sources — each query individually with error handling
    for name, query, freq, description in SQL_SOURCES:
        sources.append(_check_sql_source(name, query, freq, description, now))

    # Static sources — just mark as archive
    for name, freq, description in STATIC_SOURCES:
        sources.append({
            "name": name,
            "description": description,
            "last_updated": "Static archive",
            "age_hours": 0,
            "age_display": "archive",
            "status": "green",
            "frequency": freq,
        })

    # External sources (check local SQLite DBs via file mtime)
    sources.append(_check_external("Events DB", "events", "daily", now))
    sources.append(_check_external("Weather Cache", "weather", "daily", now))
    sources.append(_check_external("Flights DB", "flights", "daily", now))
    sources.append(_check_external("Xotelo Rates", "xotelo", "daily", now))
    sources.append(_check_external("FRED Indicators", "fred", "weekly", now))

    # Add booking engine status from monitor bridge (if available)
    booking_status = _check_booking_engine(now)
    if booking_status:
        sources.append(booking_status)

    # Filter out None entries
    sources = [s for s in sources if s is not None]

    # Summary stats
    statuses = [s["status"] for s in sources]
    n_green = statuses.count("green")
    n_yellow = statuses.count("yellow")
    n_red = statuses.count("red")
    n_unknown = statuses.count("unknown")

    overall = "green"
    if n_red > 0:
        overall = "red"
    elif n_yellow > 0:
        overall = "yellow"

    return {
        "sources": sources,
        "summary": {
            "total": len(sources),
            "green": n_green,
            "yellow": n_yellow,
            "red": n_red,
            "unknown": n_unknown,
            "overall_status": overall,
        },
        "checked_at": now.strftime("%Y-%m-%d %H:%M UTC"),
    }


def _check_sql_source(
    name: str, query: str, freq: str, description: str, now: datetime,
) -> dict:
    """Check a single SQL data source using TOP 1 ORDER BY DESC (fast)."""
    try:
        from src.data.trading_db import run_trading_query
        df = run_trading_query(query)
        if df.empty or df.iloc[0]["lu"] is None:
            return {
                "name": name, "description": description,
                "last_updated": None, "age_hours": None,
                "age_display": "N/A",
                "status": "unknown", "frequency": freq,
            }

        last_update = df.iloc[0]["lu"]
        if hasattr(last_update, "to_pydatetime"):
            last_update = last_update.to_pydatetime()
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        age_hours = (now - last_update).total_seconds() / 3600
        status = _compute_status(age_hours, freq)

        return {
            "name": name,
            "description": description,
            "last_updated": last_update.strftime("%Y-%m-%d %H:%M UTC"),
            "age_hours": round(age_hours, 1),
            "age_display": _format_age(age_hours),
            "status": status,
            "frequency": freq,
        }
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.warning("Freshness check failed for %s: %s", name, e)
        return {
            "name": name, "description": description,
            "last_updated": None, "age_hours": None,
            "age_display": "error",
            "status": "unknown", "frequency": freq,
            "error": str(e)[:100],
        }


def _check_external(name: str, source_type: str, freq: str, now: datetime) -> dict | None:
    """Check an external data source (local SQLite) via file mtime."""
    description = {
        "events": "SeatGeek + Ticketmaster events",
        "weather": "Open-Meteo weather forecasts",
        "flights": "Kiwi.com flight demand data",
        "xotelo": "Competitor OTA rates",
        "fred": "FRED economic indicators",
    }.get(source_type, source_type)

    try:
        from pathlib import Path
        data_dir = Path(__file__).parent.parent.parent / "data"

        db_map = {
            "events": "events.db",
            "weather": "weather_cache.db",
            "flights": "flights.db",
            "xotelo": "xotelo_rates.db",
            "fred": "fred_data.db",
        }

        db_file = data_dir / db_map.get(source_type, f"{source_type}.db")
        if not db_file.exists():
            return {
                "name": name, "description": description,
                "last_updated": None, "age_hours": None,
                "age_display": "N/A",
                "status": "unknown", "frequency": freq,
            }

        mtime = datetime.fromtimestamp(db_file.stat().st_mtime, tz=timezone.utc)
        age_hours = (now - mtime).total_seconds() / 3600
        status = _compute_status(age_hours, freq)

        return {
            "name": name,
            "description": description,
            "last_updated": mtime.strftime("%Y-%m-%d %H:%M UTC"),
            "age_hours": round(age_hours, 1),
            "age_display": _format_age(age_hours),
            "status": status,
            "frequency": freq,
        }
    except (FileNotFoundError, OSError, ValueError) as e:
        logger.debug("External freshness check failed for %s: %s", name, e)
        return {
            "name": name, "description": description,
            "last_updated": None, "age_hours": None,
            "age_display": "N/A",
            "status": "unknown", "frequency": freq,
        }


def _check_booking_engine(now: datetime) -> dict | None:
    """Check booking engine health from monitor bridge data.

    Returns a freshness entry for the booking engine WebJob,
    or None if no monitor data is available.
    """
    try:
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        status = bridge.get_booking_engine_status()

        if status.get("status") == "no_data":
            return None

        # Map monitor status to freshness status
        monitor_status = status.get("status", "unknown")
        status_map = {"green": "green", "yellow": "yellow", "red": "red"}
        freshness_status = status_map.get(monitor_status, "unknown")

        return {
            "name": "Booking Engine (WebJob)",
            "description": "SalesOffice WebJob scan process health",
            "last_updated": status.get("last_check", "Unknown"),
            "age_hours": None,
            "age_display": "via monitor",
            "status": freshness_status,
            "frequency": "realtime",
            "monitor_details": {
                "webjob_stale": status.get("webjob_stale", False),
                "zenith_ok": status.get("zenith_ok", True),
                "mapping_gaps": status.get("mapping_gaps", 0),
                "critical_alerts": status.get("critical", 0),
            },
        }
    except (ImportError, Exception) as e:
        logger.debug("Booking engine check unavailable: %s", e)
        return None


def _compute_status(age_hours: float, freq: str) -> str:
    """Compute green/yellow/red status based on age and expected frequency."""
    thresholds = FRESHNESS_THRESHOLDS.get(freq, FRESHNESS_THRESHOLDS["daily"])
    if age_hours <= thresholds["green"]:
        return "green"
    if age_hours <= thresholds["yellow"]:
        return "yellow"
    return "red"


def _format_age(hours: float) -> str:
    """Format age in human-readable string."""
    if hours < 1:
        return f"{int(hours * 60)}m ago"
    if hours < 24:
        return f"{hours:.0f}h ago"
    days = hours / 24
    if days < 7:
        return f"{days:.0f}d ago"
    return f"{days / 7:.0f}w ago"
