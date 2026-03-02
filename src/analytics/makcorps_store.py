"""Makcorps Historical Hotel Price API integration.

Makcorps provides historical OTA rates (Booking.com, Expedia, Hotels.com, etc.)
going back to 2010 for 200+ OTAs. Free tier: 5,000 calls/month.

Sign up: https://makcorps.com (email registration, instant free key)
Once you have a key, set it via:
  az webapp config appsettings set --name medici-prediction-api \\
    --resource-group medici-prediction-rg --settings MAKCORPS_API_KEY="<key>"

API structure:
  1. Hotel mapping: /mapping?hotel_name=...&city=...&api_key=...  → find hotel_id
  2. Historical rates: /hotel?hotelid=...&checkin=...&checkout=...&api_key=... → prices

We store found hotel_id mappings and cached historical prices in SQLite.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from config.settings import DATA_DIR

try:
    from config.settings import MAKCORPS_API_KEY
except ImportError:
    MAKCORPS_API_KEY = ""

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "makcorps_prices.sqlite"
BASE_URL = "https://api.makcorps.com"

# Our 4 Miami hotels — hotel_id will be filled in after mapping call
OUR_HOTELS: dict[int, dict] = {
    66814:  {"name": "Breakwater South Beach",    "city": "Miami Beach", "makcorps_id": None},
    854881: {"name": "citizenM Miami Brickell",   "city": "Miami",       "makcorps_id": None},
    20702:  {"name": "Embassy Suites Miami Airport", "city": "Miami",    "makcorps_id": None},
    24982:  {"name": "Hilton Miami Downtown",     "city": "Miami",       "makcorps_id": None},
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS hotel_mappings (
            our_hotel_id  INTEGER PRIMARY KEY,
            hotel_name    TEXT,
            makcorps_id   TEXT,
            mapped_ts     TEXT
        );
        CREATE TABLE IF NOT EXISTS historical_prices (
            our_hotel_id  INTEGER NOT NULL,
            checkin_date  TEXT    NOT NULL,
            checkout_date TEXT    NOT NULL,
            min_price     REAL,
            median_price  REAL,
            prices_json   TEXT,
            fetched_ts    TEXT,
            PRIMARY KEY (our_hotel_id, checkin_date)
        );
    """)
    conn.commit()


def find_hotel_id(hotel_id: int) -> str | None:
    """Find Makcorps hotel ID for one of our hotels using name search.

    Caches result in SQLite. Returns makcorps_id string or None.
    """
    if not MAKCORPS_API_KEY:
        return None

    hotel = OUR_HOTELS.get(hotel_id)
    if not hotel:
        return None

    # Check cache first
    with _get_conn() as conn:
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT makcorps_id FROM hotel_mappings WHERE our_hotel_id = ?",
            (hotel_id,),
        ).fetchone()
        if row and row[0]:
            return row[0]

    # Search Makcorps
    try:
        r = requests.get(
            f"{BASE_URL}/mapping",
            params={
                "hotel_name": hotel["name"],
                "city": hotel["city"],
                "api_key": MAKCORPS_API_KEY,
            },
            timeout=15,
        )
        r.raise_for_status()
        results = r.json()

        # Makcorps returns a list of matches; take the first one
        makcorps_id = None
        if isinstance(results, list) and results:
            makcorps_id = str(results[0].get("hotel_id") or results[0].get("id", ""))
        elif isinstance(results, dict):
            makcorps_id = str(results.get("hotel_id") or results.get("id", ""))

        if makcorps_id:
            with _get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO hotel_mappings VALUES (?, ?, ?, datetime('now'))",
                    (hotel_id, hotel["name"], makcorps_id),
                )
                conn.commit()
            logger.info("Makcorps mapping: hotel_id=%d → makcorps_id=%s", hotel_id, makcorps_id)
            return makcorps_id

    except Exception as exc:
        logger.warning("Makcorps mapping failed for hotel %d: %s", hotel_id, exc)
    return None


def fetch_historical_prices(
    hotel_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    """Fetch historical prices for a hotel across a date range.

    Queries each check-in date individually (1-night stay).
    Returns number of rows stored. Uses ~1 API call per check-in date.

    With 5,000 free calls/month and 4 hotels:
      5000 / 4 = 1,250 check-in dates per hotel per month ≈ 3.5 years of data
    """
    if not MAKCORPS_API_KEY:
        logger.debug("MAKCORPS_API_KEY not set")
        return 0

    makcorps_id = find_hotel_id(hotel_id)
    if not makcorps_id:
        logger.warning("No Makcorps ID found for hotel %d — run find_hotel_id() first", hotel_id)
        return 0

    # Default: last 180 days of history
    if start_date is None:
        start_date = (date.today() - timedelta(days=180)).isoformat()
    if end_date is None:
        end_date = (date.today() - timedelta(days=1)).isoformat()  # yesterday

    start_dt = date.fromisoformat(start_date)
    end_dt = date.fromisoformat(end_date)
    count = 0

    with _get_conn() as conn:
        _ensure_tables(conn)

        current = start_dt
        while current <= end_dt:
            checkin = current.isoformat()
            checkout = (current + timedelta(days=1)).isoformat()

            # Skip if already cached
            existing = conn.execute(
                "SELECT 1 FROM historical_prices WHERE our_hotel_id=? AND checkin_date=?",
                (hotel_id, checkin),
            ).fetchone()
            if existing:
                current += timedelta(days=7)  # skip 7 days at a time
                continue

            try:
                r = requests.get(
                    f"{BASE_URL}/hotel",
                    params={
                        "hotelid": makcorps_id,
                        "checkin": checkin,
                        "checkout": checkout,
                        "api_key": MAKCORPS_API_KEY,
                    },
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()

                # Extract prices from response
                prices = []
                if isinstance(data, list):
                    prices = [float(p["price"]) for p in data if p.get("price")]
                elif isinstance(data, dict):
                    raw = data.get("rates", data.get("prices", []))
                    prices = [float(p) for p in raw if p]

                if prices:
                    import json
                    sorted_p = sorted(prices)
                    conn.execute(
                        "INSERT OR REPLACE INTO historical_prices VALUES (?,?,?,?,?,?,datetime('now'))",
                        (
                            hotel_id, checkin, checkout,
                            min(prices),
                            sorted_p[len(sorted_p) // 2],
                            json.dumps(sorted_p[:10]),
                        ),
                    )
                    count += 1

            except Exception as exc:
                logger.debug("Makcorps price fetch failed %s: %s", checkin, exc)

            current += timedelta(days=7)  # weekly sampling to preserve API quota

        conn.commit()

    logger.info("Makcorps: stored %d historical price records for hotel %d", count, hotel_id)
    return count


def get_price_history(hotel_id: int, days: int = 365) -> list[dict]:
    """Return stored historical prices for a hotel (most recent N days)."""
    try:
        with _get_conn() as conn:
            _ensure_tables(conn)
            rows = conn.execute(
                "SELECT checkin_date, min_price, median_price, fetched_ts "
                "FROM historical_prices "
                "WHERE our_hotel_id = ? AND checkin_date >= date('now', ?) "
                "ORDER BY checkin_date",
                (hotel_id, f"-{days} days"),
            ).fetchall()
        return [
            {"checkin_date": r[0], "min_price": r[1], "median_price": r[2], "fetched_ts": r[3]}
            for r in rows
        ]
    except Exception:
        return []


def get_summary() -> dict:
    """Return summary of stored Makcorps data for API/dashboard."""
    has_key = bool(MAKCORPS_API_KEY)
    try:
        with _get_conn() as conn:
            _ensure_tables(conn)
            total_prices = conn.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
            mappings = conn.execute("SELECT our_hotel_id, hotel_name, makcorps_id FROM hotel_mappings").fetchall()
            by_hotel = {}
            for hotel_id, in conn.execute("SELECT DISTINCT our_hotel_id FROM historical_prices").fetchall():
                cnt = conn.execute("SELECT COUNT(*) FROM historical_prices WHERE our_hotel_id=?", (hotel_id,)).fetchone()[0]
                by_hotel[str(hotel_id)] = cnt
    except Exception:
        total_prices = 0
        mappings = []
        by_hotel = {}

    return {
        "status": "active" if has_key else "needs_api_key",
        "api_key_set": has_key,
        "sign_up_url": "https://makcorps.com",
        "free_calls_per_month": 5000,
        "total_stored_prices": total_prices,
        "hotel_mappings": [
            {"our_hotel_id": m[0], "hotel_name": m[1], "makcorps_id": m[2]}
            for m in mappings
        ],
        "prices_by_hotel": by_hotel,
    }
