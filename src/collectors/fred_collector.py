"""FRED Collector — Federal Reserve hotel price indices for market context."""
from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES = {
    "hotel_ppi": "PCU721110721110",
    "luxury_hotel_ppi": "PCU721110721110103",
}


def fetch_fred_series(series_id: str, months_back: int = 12) -> list:
    """Fetch FRED series observations. Returns list of {date, value}."""
    if not FRED_API_KEY:
        logger.debug("FRED_API_KEY not set — skipping")
        return []

    import requests
    start = (datetime.utcnow() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(FRED_BASE_URL, params={
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": start,
            "sort_order": "desc",
        }, timeout=10)
        if resp.status_code != 200:
            logger.warning("FRED API error: %d", resp.status_code)
            return []
        data = resp.json()
        return [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in data.get("observations", [])
            if obs.get("value") != "."
        ]
    except Exception as exc:
        logger.warning("FRED fetch failed: %s", exc)
        return []


def get_hotel_ppi_trend() -> dict:
    """Get hotel PPI trend — is the national hotel market rising or falling?

    Returns: {"direction": "up"/"down"/"flat", "change_pct": float, "latest": float}
    """
    obs = fetch_fred_series(SERIES["hotel_ppi"], months_back=6)
    if len(obs) < 2:
        return {"direction": "flat", "change_pct": 0, "latest": 0}

    latest = obs[0]["value"]
    prev = obs[1]["value"]
    change_pct = ((latest - prev) / prev) * 100 if prev else 0

    if change_pct > 1:
        direction = "up"
    elif change_pct < -1:
        direction = "down"
    else:
        direction = "flat"

    return {"direction": direction, "change_pct": round(change_pct, 2), "latest": latest, "previous": prev}


# ---------------------------------------------------------------------------
# BaseCollector subclass for registry / scheduled collection
# ---------------------------------------------------------------------------

import sqlite3

import pandas as pd

from config.settings import DATA_DIR
from src.collectors.base import BaseCollector

FRED_DB_PATH = DATA_DIR / "fred_data.db"

DISPLAY_SERIES = {
    "hotel_employment": "IPUTN721110W200000000",
    "lodging_cpi": "CUSR0000SEHB",
    "fl_hospitality_jobs": "FLLEIH",
}


class FREDCollector(BaseCollector):
    """Collector for FRED economic indicators relevant to hotel pricing."""

    name = "fred"

    def is_available(self) -> bool:
        return bool(FRED_API_KEY)

    def collect(self, **kwargs) -> pd.DataFrame:
        """Fetch all FRED series and persist to SQLite."""
        if not self.is_available():
            logger.info("FRED collector skipped — no API key")
            return pd.DataFrame()

        all_series = {**SERIES, **DISPLAY_SERIES}
        rows = []
        for name, series_id in all_series.items():
            obs = fetch_fred_series(series_id, months_back=13)
            for o in obs:
                rows.append({
                    "series_name": name,
                    "series_id": series_id,
                    "date": o["date"],
                    "value": o["value"],
                    "fetched_at": datetime.utcnow().isoformat(),
                })

        df = pd.DataFrame(rows)
        if not df.empty:
            self._persist(df)
        return df

    def _persist(self, df: pd.DataFrame) -> None:
        """Write observations to SQLite for freshness tracking."""
        try:
            conn = sqlite3.connect(str(FRED_DB_PATH))
            conn.execute("""CREATE TABLE IF NOT EXISTS fred_observations (
                series_name TEXT, series_id TEXT, date TEXT, value REAL, fetched_at TEXT,
                PRIMARY KEY (series_id, date)
            )""")
            df.to_sql("fred_observations", conn, if_exists="replace", index=False)
            conn.commit()
            conn.close()
            logger.info("FRED: persisted %d observations to %s", len(df), FRED_DB_PATH)
        except Exception as exc:
            logger.warning("FRED persist failed: %s", exc)
