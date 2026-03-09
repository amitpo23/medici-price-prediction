"""Xotelo competitor rate fetcher — free, no API key required.

Fetches multi-OTA hotel rates (Booking.com, Expedia, Hotels.com, etc.) for our 4 Miami
hotels and stores them in a local SQLite table.

Competitor pressure signal:
  get_competitor_pressure(hotel_id, our_adr) → float -1.0 to +1.0
  Positive = market charges more than us → opportunity to raise prices
  Negative = market charges less than us → risk of being overpriced

Note on Xotelo hotel keys: these are Tripadvisor location IDs.
The XOTELO_KEYS mapping below uses placeholder values. To get the correct keys,
visit https://data.xotelo.com and search for each hotel — the key is the `hotel_key`
parameter shown in the URL / API docs for that property.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "competitor_rates.sqlite"

# Xotelo hotel keys (Tripadvisor location IDs) for our 4 Miami hotels.
# These need to be verified — update if Xotelo returns 404 for a key.
XOTELO_KEYS: dict[int, str] = {
    66814: "g78307620",    # Breakwater South Beach (Hotel Breakwater South Beach)
    854881: "g78307621",   # citizenM Miami Brickell
    20702: "g147808",      # Embassy Suites Miami Airport
    24982: "g147809",      # Hilton Miami Downtown
}

XOTELO_RATE_URL = "https://data.xotelo.com/api/rates"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS competitor_rates (
            hotel_id       INTEGER NOT NULL,
            checkin_date   TEXT    NOT NULL,
            checkout_date  TEXT    NOT NULL,
            min_rate       REAL,
            median_rate    REAL,
            provider_count INTEGER,
            collected_ts   TEXT,
            PRIMARY KEY (hotel_id, checkin_date)
        )
    """)
    conn.commit()


def fetch_rates(hotel_id: int, days_ahead: int = 60) -> int:
    """Fetch Xotelo rates for the next N days (weekly sampling).

    Returns number of rows upserted. Returns 0 if hotel key not found or API fails.
    Samples every 7 days to stay within Xotelo's undocumented rate limits.
    """
    key = XOTELO_KEYS.get(hotel_id)
    if not key:
        return 0

    count = 0
    with _get_conn() as conn:
        _ensure_table(conn)
        for offset in range(0, days_ahead, 7):
            checkin = (date.today() + timedelta(days=offset)).isoformat()
            checkout = (date.today() + timedelta(days=offset + 1)).isoformat()
            try:
                r = requests.get(
                    XOTELO_RATE_URL,
                    params={"hotel_key": key, "chk_in": checkin, "chk_out": checkout},
                    timeout=10,
                )
                r.raise_for_status()
                payload = r.json()
                if not isinstance(payload, dict):
                    logger.debug("Xotelo returned non-dict payload for hotel %d on %s", hotel_id, checkin)
                    continue

                result = payload.get("result") or {}
                if not isinstance(result, dict):
                    logger.debug("Xotelo returned malformed result for hotel %d on %s", hotel_id, checkin)
                    continue

                rate_list = result.get("rates", [])
                rates = [
                    float(item["rate"])
                    for item in rate_list
                    if isinstance(item, dict) and item.get("rate") is not None
                ]
                if not rates:
                    continue

                sorted_rates = sorted(rates)
                median = sorted_rates[len(sorted_rates) // 2]
                ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                conn.execute(
                    "INSERT OR REPLACE INTO competitor_rates "
                    "(hotel_id, checkin_date, checkout_date, min_rate, median_rate, provider_count, collected_ts) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (hotel_id, checkin, checkout, min(rates), median, len(rates), ts),
                )
                count += 1
            except (
                ConnectionError,
                TimeoutError,
                requests.RequestException,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                logger.debug("Xotelo fetch failed for hotel %d on %s: %s", hotel_id, checkin, exc)
                continue

        conn.commit()

    return count


def get_competitor_pressure(hotel_id: int, our_adr: float) -> float:
    """Return competitor pressure scalar: -1.0 to +1.0.

    Positive means the market median is above our ADR → opportunity to raise prices.
    Negative means the market median is below our ADR → risk of being overpriced.
    Returns 0.0 if no data is available or our_adr is 0.
    """
    if our_adr <= 0:
        return 0.0

    try:
        with _get_conn() as conn:
            _ensure_table(conn)
            rows = conn.execute(
                "SELECT median_rate FROM competitor_rates "
                "WHERE hotel_id = ? AND checkin_date >= date('now') "
                "ORDER BY checkin_date LIMIT 10",
                (hotel_id,),
            ).fetchall()

        if not rows:
            return 0.0

        market_median = sum(r[0] for r in rows if r[0]) / len(rows)
        if market_median <= 0:
            return 0.0

        # Positive = market charges more than us (we can raise)
        ratio = (market_median - our_adr) / market_median
        return max(-1.0, min(1.0, ratio))

    except (OSError, ValueError, TypeError, ZeroDivisionError) as exc:
        logger.debug("Competitor pressure calc failed for hotel %d: %s", hotel_id, exc)
        return 0.0


def get_rates_summary(hotel_id: int) -> dict:
    """Return a summary of stored competitor rates for display."""
    try:
        with _get_conn() as conn:
            _ensure_table(conn)
            rows = conn.execute(
                "SELECT checkin_date, min_rate, median_rate, provider_count, collected_ts "
                "FROM competitor_rates "
                "WHERE hotel_id = ? AND checkin_date >= date('now') "
                "ORDER BY checkin_date LIMIT 10",
                (hotel_id,),
            ).fetchall()

        if not rows:
            return {"hotel_id": hotel_id, "rates": [], "status": "no_data"}

        return {
            "hotel_id": hotel_id,
            "status": "ok",
            "rates": [
                {
                    "checkin_date": r[0],
                    "min_rate": r[1],
                    "median_rate": r[2],
                    "provider_count": r[3],
                    "collected_ts": r[4],
                }
                for r in rows
            ],
        }
    except (OSError, ValueError, TypeError) as exc:
        return {"hotel_id": hotel_id, "status": "error", "error": str(exc)}
