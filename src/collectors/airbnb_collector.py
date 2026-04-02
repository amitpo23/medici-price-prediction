"""Airbnb Collector — Inside Airbnb Miami Beach pricing data.

Downloads monthly listings CSV from Inside Airbnb (public, no API key).
Extracts average nightly prices for Miami Beach area as a competitive benchmark.

Source: http://insideairbnb.com/get-the-data/ (Miami)
"""
from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Inside Airbnb data URL for Miami
AIRBNB_LISTINGS_URL = os.getenv(
    "AIRBNB_LISTINGS_URL",
    "http://data.insideairbnb.com/united-states/fl/miami/2025-12-29/visualisations/listings.csv"
)

SQLITE_PATH = Path(os.getenv("AIRBNB_DB_PATH", "data/airbnb_prices.db"))
TABLE_NAME = "airbnb_listings"


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER NOT NULL,
            name TEXT,
            neighbourhood TEXT,
            room_type TEXT,
            price REAL,
            minimum_nights INTEGER,
            availability_365 INTEGER,
            snapshot_date TEXT NOT NULL,
            fetched_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (id, snapshot_date)
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS airbnb_zone_avg (
            snapshot_date TEXT NOT NULL,
            neighbourhood TEXT NOT NULL,
            avg_price REAL,
            median_price REAL,
            listing_count INTEGER,
            PRIMARY KEY (snapshot_date, neighbourhood)
        )
    """)
    conn.commit()


class AirbnbCollector(BaseCollector):
    """Collects Airbnb pricing data from Inside Airbnb (Miami)."""

    name = "airbnb"

    def __init__(self, cache=None, url: str | None = None):
        super().__init__(cache)
        self.url = url or AIRBNB_LISTINGS_URL
        self.db_path = SQLITE_PATH

    def is_available(self) -> bool:
        try:
            resp = requests.head(self.url, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def collect(self, **kwargs) -> pd.DataFrame:
        """Download listings CSV, parse, cache in SQLite."""
        try:
            logger.info("Airbnb: downloading listings from %s", self.url)
            resp = requests.get(self.url, timeout=60)
            if resp.status_code != 200:
                logger.warning("Airbnb download failed: HTTP %d", resp.status_code)
                return pd.DataFrame()

            df = pd.read_csv(io.StringIO(resp.text))
            if df.empty:
                logger.warning("Airbnb: empty CSV")
                return pd.DataFrame()

            # Normalize price column (remove $ and commas if present)
            if "price" in df.columns:
                df["price"] = pd.to_numeric(
                    df["price"].astype(str).str.replace(r"[$,]", "", regex=True),
                    errors="coerce"
                )

            # Filter to relevant listings (entire home/apt, price > 0)
            df = df[df["price"] > 0].copy()
            snapshot_date = datetime.utcnow().strftime("%Y-%m-%d")
            df["snapshot_date"] = snapshot_date

            self._save_to_sqlite(df, snapshot_date)
            logger.info("Airbnb: %d listings fetched, avg price $%.2f",
                        len(df), df["price"].mean())
            return df

        except Exception as exc:
            logger.warning("Airbnb collect failed: %s", exc)
            return pd.DataFrame()

    def _save_to_sqlite(self, df: pd.DataFrame, snapshot_date: str) -> None:
        """Save listings and zone averages to SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)

            # Save individual listings
            for _, row in df.iterrows():
                conn.execute(f"""
                    INSERT OR REPLACE INTO {TABLE_NAME}
                        (id, name, neighbourhood, room_type, price,
                         minimum_nights, availability_365, snapshot_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(row.get("id", 0)),
                    str(row.get("name", ""))[:200],
                    str(row.get("neighbourhood", "")),
                    str(row.get("room_type", "")),
                    float(row.get("price", 0)),
                    int(row.get("minimum_nights", 0)),
                    int(row.get("availability_365", 0)),
                    snapshot_date,
                ))

            # Compute and save zone averages
            zone_stats = df.groupby("neighbourhood")["price"].agg(
                avg_price="mean", median_price="median", listing_count="count"
            ).reset_index()

            for _, row in zone_stats.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO airbnb_zone_avg
                        (snapshot_date, neighbourhood, avg_price, median_price, listing_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (snapshot_date, row["neighbourhood"],
                      round(row["avg_price"], 2), round(row["median_price"], 2),
                      int(row["listing_count"])))

            conn.commit()
            logger.info("Airbnb: saved %d listings + %d zone averages to SQLite",
                        len(df), len(zone_stats))
        finally:
            conn.close()

    def get_miami_beach_avg(self) -> float | None:
        """Get latest average Airbnb price for Miami Beach."""
        if not self.db_path.exists():
            return None
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            row = conn.execute("""
                SELECT avg_price FROM airbnb_zone_avg
                WHERE neighbourhood LIKE '%Miami Beach%'
                ORDER BY snapshot_date DESC LIMIT 1
            """).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def get_indicator_series(self, neighbourhood: str = "Miami Beach",
                             days_back: int = 365) -> list[dict]:
        """Get historical avg price series for a neighbourhood. Returns [{t, v}]."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            rows = conn.execute("""
                SELECT snapshot_date, avg_price FROM airbnb_zone_avg
                WHERE neighbourhood LIKE ?
                ORDER BY snapshot_date
            """, (f"%{neighbourhood}%",)).fetchall()
            return [{"t": r[0], "v": r[1]} for r in rows]
        finally:
            conn.close()
