"""Data freshness monitor — check last update times for all data sources.

Queries each data source's last-updated timestamp and computes
staleness levels (green/yellow/red) based on expected update frequency.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Expected max age in hours for each source type
FRESHNESS_THRESHOLDS = {
    "realtime": {"green": 4, "yellow": 24},       # expect updates every few hours
    "hourly": {"green": 6, "yellow": 24},          # expect hourly scans
    "daily": {"green": 48, "yellow": 168},         # expect daily updates
    "weekly": {"green": 192, "yellow": 720},       # expect weekly updates
    "static": {"green": 99999, "yellow": 99999},   # never stale
}


def build_freshness_data() -> dict:
    """Check freshness of all data sources.

    Returns list of source status dicts with last_updated, age, status color.
    """
    sources = []
    now = datetime.now(timezone.utc)

    # 1. SalesOffice.Details (hourly scans)
    sources.append(_check_source(
        "SalesOffice.Details",
        "SELECT MAX(DateInsert) AS last_update FROM [SalesOffice.Details]",
        "hourly", "Internal room price scans", now,
    ))

    # 2. SalesOffice.Orders
    sources.append(_check_source(
        "SalesOffice.Orders",
        "SELECT MAX(DateInsert) AS last_update FROM [SalesOffice.Orders]",
        "hourly", "Scan orders", now,
    ))

    # 3. AI_Search_HotelData (real-time)
    sources.append(_check_source(
        "AI_Search_HotelData",
        "SELECT MAX(UpdatedAt) AS last_update FROM AI_Search_HotelData",
        "realtime", "8.5M market pricing records", now,
    ))

    # 4. SearchResultsSessionPollLog (real-time)
    sources.append(_check_source(
        "SearchResultsSessionPollLog",
        "SELECT MAX(DateInsert) AS last_update FROM SearchResultsSessionPollLog",
        "realtime", "8.3M provider search results", now,
    ))

    # 5. MED_SearchHotels (static archive)
    sources.append(_check_source(
        "MED_SearchHotels",
        "SELECT MAX(RequestTime) AS last_update FROM MED_SearchHotels",
        "static", "7M historical search (2020-2023)", now,
    ))

    # 6. RoomPriceUpdateLog
    sources.append(_check_source(
        "RoomPriceUpdateLog",
        "SELECT MAX(DateInsert) AS last_update FROM RoomPriceUpdateLog",
        "daily", "82K price change events", now,
    ))

    # 7. MED_Book (bookings)
    sources.append(_check_source(
        "MED_Book",
        "SELECT MAX(DateInsert) AS last_update FROM MED_Book",
        "daily", "Active bookings", now,
    ))

    # 8. MED_PreBook
    sources.append(_check_source(
        "MED_PreBook",
        "SELECT MAX(DateInsert) AS last_update FROM MED_PreBook",
        "daily", "Pre-booking data", now,
    ))

    # 9. SalesOffice.Log
    sources.append(_check_source(
        "SalesOffice.Log",
        "SELECT MAX(DateCreated) AS last_update FROM [SalesOffice.Log]",
        "hourly", "1.2M action logs", now,
    ))

    # 10. External sources (check local SQLite DBs)
    sources.append(_check_external("Events DB", "events", "daily", now))
    sources.append(_check_external("Weather Cache", "weather", "daily", now))
    sources.append(_check_external("Flights DB", "flights", "daily", now))
    sources.append(_check_external("Xotelo Rates", "xotelo", "daily", now))
    sources.append(_check_external("FRED Indicators", "fred", "weekly", now))

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


def _check_source(
    name: str, query: str, freq: str, description: str, now: datetime,
) -> dict:
    """Check a single SQL data source."""
    try:
        from src.data.trading_db import run_trading_query
        df = run_trading_query(query)
        if df.empty or df.iloc[0]["last_update"] is None:
            return {
                "name": name, "description": description,
                "last_updated": None, "age_hours": None,
                "status": "unknown", "frequency": freq,
            }

        last_update = df.iloc[0]["last_update"]
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
    except Exception as e:
        logger.warning("Freshness check failed for %s: %s", name, e)
        return {
            "name": name, "description": description,
            "last_updated": None, "age_hours": None,
            "status": "unknown", "frequency": freq,
            "error": str(e),
        }


def _check_external(name: str, source_type: str, freq: str, now: datetime) -> dict | None:
    """Check an external data source (local SQLite)."""
    description = {
        "events": "SeatGeek + Ticketmaster events",
        "weather": "Open-Meteo weather forecasts",
        "flights": "Kiwi.com flight demand data",
        "xotelo": "Competitor OTA rates",
        "fred": "FRED economic indicators",
    }.get(source_type, source_type)

    try:
        import sqlite3
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
                "status": "unknown", "frequency": freq,
            }

        # Check file modification time as proxy
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
    except Exception as e:
        logger.debug("External freshness check failed for %s: %s", name, e)
        return {
            "name": name, "description": description,
            "last_updated": None, "age_hours": None,
            "status": "unknown", "frequency": freq,
        }


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
