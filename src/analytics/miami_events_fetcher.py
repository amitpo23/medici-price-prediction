"""Fetch Miami events from Ticketmaster + SeatGeek into the miami_events table.

Both APIs are free tier (no cost). Events inserted here flow automatically into
Enrichments.events on the next analysis run — zero pipeline changes required.

APIs:
  Ticketmaster Discovery v2: 5,000 calls/day free (developer.ticketmaster.com)
  SeatGeek: free with client_id (seatgeek.com/account/develop)

Usage:
  refresh_api_events(days_ahead=90) → {"ticketmaster": N, "seatgeek": M, "total": N+M}
  Called daily from the scheduler in analytics_dashboard.py.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

from src.analytics.events_store import save_events
from config.settings import TICKETMASTER_API_KEY, SEATGEEK_CLIENT_ID

logger = logging.getLogger(__name__)

MIAMI_LAT = 25.7617
MIAMI_LON = -80.1918
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
SEATGEEK_URL = "https://api.seatgeek.com/2/events"

# Map Ticketmaster segment names to our category keys
_TM_SEGMENT_MAP: dict[str, str] = {
    "Music": "festivals",
    "Sports": "sports",
    "Arts & Theatre": "expos",
    "Film": "other",
    "Miscellaneous": "other",
}


def fetch_ticketmaster_events(days_ahead: int = 90) -> int:
    """Fetch Miami events from Ticketmaster Discovery API.

    Returns count of events upserted to the miami_events table.
    Returns 0 if API key not configured or request fails.
    """
    if not TICKETMASTER_API_KEY:
        logger.debug("TICKETMASTER_API_KEY not set — skipping")
        return 0

    start = date.today().isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()

    try:
        r = requests.get(
            TICKETMASTER_URL,
            params={
                "apikey": TICKETMASTER_API_KEY,
                "latlong": f"{MIAMI_LAT},{MIAMI_LON}",
                "radius": "25",
                "unit": "miles",
                "startDateTime": f"{start}T00:00:00Z",
                "endDateTime": f"{end}T23:59:59Z",
                "size": 200,
                "sort": "date,asc",
            },
            timeout=15,
        )
        r.raise_for_status()
        raw_events = r.json().get("_embedded", {}).get("events", [])
    except (ConnectionError, TimeoutError, requests.RequestException, KeyError, ValueError) as exc:
        logger.warning("Ticketmaster API error: %s", exc)
        return 0

    events = []
    for ev in raw_events:
        start_date = ev.get("dates", {}).get("start", {}).get("localDate", "")
        if not start_date:
            continue

        segment = (
            ev.get("classifications", [{}])[0]
            .get("segment", {})
            .get("name", "other")
        )
        category = _TM_SEGMENT_MAP.get(segment, "other")

        # Estimate attendance from venue capacity if available
        venues = ev.get("_embedded", {}).get("venues", [{}])
        capacity_str = venues[0].get("capacity", "") if venues else ""
        try:
            capacity = int(capacity_str) if capacity_str else None
        except (ValueError, TypeError):
            capacity = None

        events.append({
            "name": ev.get("name", "")[:200],
            "start_date": start_date,
            "end_date": start_date,
            "category": category,
            "expected_attendance": capacity,
            "hotel_impact": "low",
            "source": "ticketmaster",
        })

    if not events:
        return 0

    count = save_events(events)
    logger.info("Ticketmaster: upserted %d events", count)
    return count


def fetch_seatgeek_events(days_ahead: int = 90) -> int:
    """Fetch Miami events from SeatGeek API.

    Returns count of events upserted to the miami_events table.
    Returns 0 if client_id not configured or request fails.
    """
    if not SEATGEEK_CLIENT_ID:
        logger.debug("SEATGEEK_CLIENT_ID not set — skipping")
        return 0

    start = date.today().isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()

    try:
        r = requests.get(
            SEATGEEK_URL,
            params={
                "client_id": SEATGEEK_CLIENT_ID,
                "lat": MIAMI_LAT,
                "lon": MIAMI_LON,
                "range": "25mi",
                "datetime_utc.gte": f"{start}T00:00:00",
                "datetime_utc.lte": f"{end}T23:59:59",
                "per_page": 200,
                "sort": "datetime_utc.asc",
            },
            timeout=15,
        )
        r.raise_for_status()
        raw_events = r.json().get("events", [])
    except (ConnectionError, TimeoutError, requests.RequestException, KeyError, ValueError) as exc:
        logger.warning("SeatGeek API error: %s", exc)
        return 0

    events = []
    for ev in raw_events:
        dt_utc = ev.get("datetime_utc", "")
        start_date = dt_utc[:10] if len(dt_utc) >= 10 else ""
        if not start_date:
            continue

        sg_type = ev.get("type", "other")
        category_map = {
            "concert": "festivals",
            "sports": "sports",
            "theater": "expos",
            "comedy": "other",
        }
        category = category_map.get(sg_type, "other")

        events.append({
            "name": ev.get("title", "")[:200],
            "start_date": start_date,
            "end_date": start_date,
            "category": category,
            "expected_attendance": None,
            "hotel_impact": "low",
            "source": "seatgeek",
        })

    if not events:
        return 0

    count = save_events(events)
    logger.info("SeatGeek: upserted %d events", count)
    return count


def refresh_api_events(days_ahead: int = 90) -> dict:
    """Refresh miami_events from all API sources.

    Called daily from the scheduler. Returns summary dict.
    """
    tm = fetch_ticketmaster_events(days_ahead)
    sg = fetch_seatgeek_events(days_ahead)
    total = tm + sg
    logger.info("API event refresh complete: ticketmaster=%d seatgeek=%d total=%d", tm, sg, total)
    return {"ticketmaster": tm, "seatgeek": sg, "total": total}
