"""SQLite storage for flight demand data (Kiwi.com).

Stores flight search results as demand indicators for hotel price predictions.
Flight data is collected via Kiwi MCP tool and stored here for the analyzer.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from config.settings import DATA_DIR

DB_PATH = DATA_DIR / "salesoffice_prices.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_flights_db() -> None:
    """Create flight_demand table if it doesn't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS flight_demand (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_ts    TEXT    NOT NULL,
            origin          TEXT    NOT NULL,
            destination     TEXT    NOT NULL,
            flight_date     TEXT    NOT NULL,
            num_flights     INTEGER NOT NULL,
            min_price       REAL,
            avg_price       REAL,
            max_price       REAL,
            currency        TEXT    DEFAULT 'USD',
            UNIQUE(collected_ts, origin, flight_date)
        );

        CREATE INDEX IF NOT EXISTS idx_flight_demand_date
            ON flight_demand(destination, flight_date);

        CREATE INDEX IF NOT EXISTS idx_flight_demand_collected
            ON flight_demand(collected_ts);
    """)
    conn.close()


def save_flight_results(
    origin: str,
    destination: str,
    flight_date: str,
    num_flights: int,
    min_price: float | None,
    avg_price: float | None,
    max_price: float | None,
    currency: str = "USD",
    collected_ts: datetime | None = None,
) -> None:
    """Save a single flight search result."""
    ts = (collected_ts or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO flight_demand "
        "(collected_ts, origin, destination, flight_date, num_flights, "
        "min_price, avg_price, max_price, currency) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, origin, destination, flight_date, num_flights,
         min_price, avg_price, max_price, currency),
    )
    conn.commit()
    conn.close()


def save_flight_batch(records: list[dict]) -> int:
    """Save multiple flight search results at once.

    Each record should have: origin, destination, flight_date,
    num_flights, min_price, avg_price, max_price, currency.
    """
    if not records:
        return 0

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    inserted = 0
    for rec in records:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO flight_demand "
                "(collected_ts, origin, destination, flight_date, num_flights, "
                "min_price, avg_price, max_price, currency) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts,
                    rec["origin"],
                    rec.get("destination", "Miami"),
                    rec["flight_date"],
                    rec["num_flights"],
                    rec.get("min_price"),
                    rec.get("avg_price"),
                    rec.get("max_price"),
                    rec.get("currency", "USD"),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def load_demand_for_dates(
    destination: str = "Miami",
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Load flight demand data for a destination and date range."""
    conn = _get_conn()
    query = "SELECT * FROM flight_demand WHERE destination = ?"
    params: list = [destination]

    if date_from:
        query += " AND flight_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND flight_date <= ?"
        params.append(date_to)

    query += " ORDER BY flight_date, origin"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_demand_summary(destination: str = "Miami") -> dict:
    """Get latest demand summary for a destination.

    Returns dict with:
    - indicator: HIGH / MEDIUM / LOW
    - avg_price: average flight price across all origins
    - total_flights: total flights available
    - origins_checked: number of origin cities
    - by_origin: per-origin breakdown
    - last_collected: timestamp of latest collection
    """
    conn = _get_conn()

    # Get the latest collection timestamp
    row = conn.execute(
        "SELECT MAX(collected_ts) FROM flight_demand WHERE destination = ?",
        (destination,),
    ).fetchone()

    if not row or not row[0]:
        conn.close()
        return {"indicator": "NO_DATA", "detail": "No flight data collected yet"}

    latest_ts = row[0]

    # Get all records from latest collection
    df = pd.read_sql_query(
        "SELECT * FROM flight_demand WHERE destination = ? AND collected_ts = ?",
        conn, params=(destination, latest_ts),
    )
    conn.close()

    if df.empty:
        return {"indicator": "NO_DATA", "detail": "No flight data for latest collection"}

    total_flights = int(df["num_flights"].sum())
    overall_avg = float(df["avg_price"].mean()) if not df["avg_price"].isna().all() else 0
    overall_min = float(df["min_price"].min()) if not df["min_price"].isna().all() else 0

    # Demand indicator logic
    if overall_avg > 250 or total_flights < 20:
        indicator = "HIGH"
    elif overall_avg > 150:
        indicator = "MEDIUM"
    else:
        indicator = "LOW"

    by_origin = []
    for _, row_data in df.iterrows():
        by_origin.append({
            "origin": row_data["origin"],
            "flight_date": row_data["flight_date"],
            "num_flights": int(row_data["num_flights"]),
            "min_price": round(float(row_data["min_price"]), 2) if pd.notna(row_data["min_price"]) else None,
            "avg_price": round(float(row_data["avg_price"]), 2) if pd.notna(row_data["avg_price"]) else None,
        })

    return {
        "indicator": indicator,
        "avg_flight_price": round(overall_avg, 2),
        "min_flight_price": round(overall_min, 2),
        "total_flights": total_flights,
        "origins_checked": int(df["origin"].nunique()),
        "dates_checked": int(df["flight_date"].nunique()),
        "last_collected": latest_ts,
        "by_origin": by_origin,
    }


def get_demand_for_date(destination: str, flight_date: str) -> dict | None:
    """Get demand indicator for a specific date."""
    conn = _get_conn()

    # Get latest data for this date
    df = pd.read_sql_query(
        "SELECT * FROM flight_demand "
        "WHERE destination = ? AND flight_date = ? "
        "ORDER BY collected_ts DESC",
        conn, params=(destination, flight_date),
    )
    conn.close()

    if df.empty:
        return None

    # Use only the latest collection
    latest_ts = df["collected_ts"].iloc[0]
    df = df[df["collected_ts"] == latest_ts]

    avg_price = float(df["avg_price"].mean()) if not df["avg_price"].isna().all() else 0
    total = int(df["num_flights"].sum())

    if avg_price > 250 or total < 5:
        indicator = "HIGH"
    elif avg_price > 150:
        indicator = "MEDIUM"
    else:
        indicator = "LOW"

    return {
        "indicator": indicator,
        "avg_price": round(avg_price, 2),
        "total_flights": total,
    }
