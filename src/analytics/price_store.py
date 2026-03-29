"""Local SQLite store for SalesOffice price history.

Stores hourly snapshots of room prices so we can track changes over time
and build price trajectories for each room until check-in.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "salesoffice_prices.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Recreates DB if corrupted."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = _get_conn()
    except sqlite3.DatabaseError:
        logger.warning("SQLite DB corrupted at %s — recreating", DB_PATH)
        for p in (DB_PATH, Path(str(DB_PATH) + "-wal"), Path(str(DB_PATH) + "-shm")):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_ts TEXT    NOT NULL,
            detail_id   INTEGER NOT NULL,
            order_id    INTEGER NOT NULL,
            hotel_id    INTEGER NOT NULL,
            hotel_name  TEXT,
            room_category INTEGER,
            room_board  INTEGER,
            room_price  REAL    NOT NULL,
            room_code   TEXT,
            date_from   TEXT    NOT NULL,
            date_to     TEXT    NOT NULL,
            destination_id INTEGER,
            is_processed INTEGER,
            UNIQUE(snapshot_ts, detail_id)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_detail
            ON price_snapshots(detail_id, snapshot_ts);

        CREATE INDEX IF NOT EXISTS idx_snapshots_hotel_date
            ON price_snapshots(hotel_id, date_from, snapshot_ts);

        CREATE TABLE IF NOT EXISTS analysis_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_ts      TEXT NOT NULL,
            total_rooms INTEGER,
            hotels      INTEGER,
            avg_price   REAL,
            summary     TEXT
        );
    """)
    conn.close()


def save_snapshot(df: pd.DataFrame, snapshot_ts: datetime | None = None) -> int:
    """Save a price snapshot. Returns number of new rows inserted."""
    if df.empty:
        return 0

    ts = (snapshot_ts or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")
    df = df.copy()
    df["snapshot_ts"] = ts

    cols = [
        "snapshot_ts", "detail_id", "order_id", "hotel_id", "hotel_name",
        "room_category", "room_board", "room_price", "room_code",
        "date_from", "date_to", "destination_id", "is_processed",
    ]

    conn = _get_conn()
    inserted = 0
    for _, row in df.iterrows():
        try:
            conn.execute(
                f"INSERT OR IGNORE INTO price_snapshots ({', '.join(cols)}) "
                f"VALUES ({', '.join(['?'] * len(cols))})",
                [row.get(c) for c in cols],
            )
            inserted += conn.total_changes
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    actual = conn.execute(
        "SELECT COUNT(*) FROM price_snapshots WHERE snapshot_ts = ?", (ts,)
    ).fetchone()[0]
    conn.close()
    return actual


def load_all_snapshots() -> pd.DataFrame:
    """Load all price snapshots."""
    conn = _get_conn()
    df = pd.read_sql_query("SELECT * FROM price_snapshots ORDER BY snapshot_ts, detail_id", conn)
    conn.close()
    return df


def load_snapshots_for_hotel(hotel_id: int) -> pd.DataFrame:
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM price_snapshots WHERE hotel_id = ? ORDER BY snapshot_ts",
        conn, params=(hotel_id,),
    )
    conn.close()
    return df


def load_latest_snapshot() -> pd.DataFrame:
    """Load the most recent snapshot."""
    conn = _get_conn()
    latest_ts = conn.execute(
        "SELECT MAX(snapshot_ts) FROM price_snapshots"
    ).fetchone()[0]
    if not latest_ts:
        conn.close()
        return pd.DataFrame()
    df = pd.read_sql_query(
        "SELECT * FROM price_snapshots WHERE snapshot_ts = ?",
        conn, params=(latest_ts,),
    )
    conn.close()
    return df


def load_price_history(detail_id: int) -> pd.DataFrame:
    """Load price history for a specific room detail."""
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT snapshot_ts, room_price FROM price_snapshots "
        "WHERE detail_id = ? ORDER BY snapshot_ts",
        conn, params=(detail_id,),
    )
    conn.close()
    return df


def get_snapshot_count() -> int:
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(DISTINCT snapshot_ts) FROM price_snapshots").fetchone()[0]
    conn.close()
    return count


def save_analysis_run(total_rooms: int, hotels: int, avg_price: float, summary: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO analysis_runs (run_ts, total_rooms, hotels, avg_price, summary) "
        "VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), total_rooms, hotels, avg_price, summary),
    )
    conn.commit()
    conn.close()
