"""BTS Flights Collector — Bureau of Transportation Statistics airport passenger data.

Downloads monthly passenger counts for Miami International Airport (MIA).
Used as a leading demand indicator — more passengers = more hotel demand.

Source: BTS T-100 Domestic/International Segment Data
API: https://data.transportation.gov/
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# BTS Socrata API for T-100 segment data (MIA airport)
BTS_API_URL = os.getenv(
    "BTS_API_URL",
    "https://data.transportation.gov/resource/xgub-n9bw.json"
)

MIA_AIRPORT_CODE = "MIA"
SQLITE_PATH = Path(os.getenv("BTS_DB_PATH", "data/bts_flights.db"))
TABLE_NAME = "bts_monthly_passengers"


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            passengers INTEGER,
            departures INTEGER,
            carrier_count INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (year, month)
        )
    """)
    conn.commit()


class BTSCollector(BaseCollector):
    """Collects MIA airport passenger data from Bureau of Transportation Statistics."""

    name = "bts"

    def __init__(self, cache=None):
        super().__init__(cache)
        self.db_path = SQLITE_PATH

    def is_available(self) -> bool:
        try:
            resp = requests.head(BTS_API_URL, timeout=10)
            return resp.status_code in (200, 301, 302)
        except Exception:
            return False

    def collect(self, months_back: int = 24, **kwargs) -> pd.DataFrame:
        """Fetch monthly passenger data for MIA airport."""
        try:
            # Query BTS Socrata API for MIA departures
            year_cutoff = (datetime.utcnow() - timedelta(days=months_back * 30)).year
            params = {
                "$where": f"origin = '{MIA_AIRPORT_CODE}' AND year >= {year_cutoff}",
                "$select": "year, month, sum(passengers) as total_passengers, "
                           "sum(departures_performed) as total_departures, "
                           "count(distinct unique_carrier) as carrier_count",
                "$group": "year, month",
                "$order": "year, month",
                "$limit": 5000,
            }

            logger.info("BTS: fetching MIA airport data from %d onwards", year_cutoff)
            resp = requests.get(BTS_API_URL, params=params, timeout=30)

            if resp.status_code != 200:
                logger.warning("BTS API error: HTTP %d", resp.status_code)
                return self._fallback_from_cache()

            data = resp.json()
            if not data:
                logger.warning("BTS: no data returned")
                return self._fallback_from_cache()

            rows = []
            for item in data:
                rows.append({
                    "year": int(item.get("year", 0)),
                    "month": int(item.get("month", 0)),
                    "passengers": int(float(item.get("total_passengers", 0))),
                    "departures": int(float(item.get("total_departures", 0))),
                    "carrier_count": int(float(item.get("carrier_count", 0))),
                })

            df = pd.DataFrame(rows)
            self._save_to_sqlite(df)
            logger.info("BTS: %d monthly records fetched for MIA", len(df))
            return df

        except Exception as exc:
            logger.warning("BTS collect failed: %s", exc)
            return self._fallback_from_cache()

    def _fallback_from_cache(self) -> pd.DataFrame:
        """Return cached data if API fails."""
        if not self.db_path.exists():
            return pd.DataFrame()
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME} ORDER BY year, month", conn)
            if not df.empty:
                logger.info("BTS: using %d cached records", len(df))
            return df
        finally:
            conn.close()

    def _save_to_sqlite(self, df: pd.DataFrame) -> None:
        """Upsert monthly records to SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            for _, row in df.iterrows():
                conn.execute(f"""
                    INSERT OR REPLACE INTO {TABLE_NAME}
                        (year, month, passengers, departures, carrier_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (row["year"], row["month"], row["passengers"],
                      row["departures"], row["carrier_count"]))
            conn.commit()
            logger.info("BTS: saved %d monthly records to SQLite", len(df))
        finally:
            conn.close()

    def get_indicator_series(self, days_back: int = 730) -> list[dict]:
        """Get monthly passenger series. Returns [{t, v}] with t as YYYY-MM-01."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            rows = conn.execute(f"""
                SELECT year, month, passengers FROM {TABLE_NAME}
                ORDER BY year, month
            """).fetchall()
            return [
                {"t": f"{r[0]}-{r[1]:02d}-01", "v": r[2]}
                for r in rows if r[2] and r[2] > 0
            ]
        finally:
            conn.close()

    def get_mom_trend(self) -> str:
        """Get month-over-month trend: 'rising', 'falling', or 'flat'."""
        series = self.get_indicator_series()
        if len(series) < 2:
            return "flat"
        last = series[-1]["v"]
        prev = series[-2]["v"]
        if prev == 0:
            return "flat"
        change_pct = (last - prev) / prev * 100
        if change_pct > 3.0:
            return "rising"
        elif change_pct < -3.0:
            return "falling"
        return "flat"
