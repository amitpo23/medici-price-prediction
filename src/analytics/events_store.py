"""Events and conferences store for Miami hotel demand signals.

Hardcoded major events + dynamic events from APIs (SeatGeek, PredictHQ).
Events are stored in SQLite and used by the analyzer to adjust predictions.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, date

import pandas as pd

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "salesoffice_prices.db"

# ── Major recurring Miami events (hardcoded, high confidence) ──────────
MIAMI_MAJOR_EVENTS = [
    {
        "name": "Miami International Boat Show",
        "start": "2026-02-11",
        "end": "2026-02-15",
        "category": "expos",
        "expected_attendance": 100_000,
        "hotel_impact": "very_high",
        "source": "hardcoded",
    },
    {
        "name": "South Beach Wine & Food Festival",
        "start": "2026-02-19",
        "end": "2026-02-22",
        "category": "festivals",
        "expected_attendance": 65_000,
        "hotel_impact": "high",
        "source": "hardcoded",
    },
    {
        "name": "Miami Open Tennis",
        "start": "2026-03-15",
        "end": "2026-03-29",
        "category": "sports",
        "expected_attendance": 300_000,
        "hotel_impact": "very_high",
        "source": "hardcoded",
    },
    {
        "name": "Ultra Music Festival",
        "start": "2026-03-27",
        "end": "2026-03-29",
        "category": "festivals",
        "expected_attendance": 170_000,
        "hotel_impact": "very_high",
        "source": "hardcoded",
    },
    {
        "name": "F1 Miami Grand Prix",
        "start": "2026-05-01",
        "end": "2026-05-03",
        "category": "sports",
        "expected_attendance": 250_000,
        "hotel_impact": "extreme",
        "source": "hardcoded",
    },
    {
        "name": "Miami Swim Week",
        "start": "2026-05-27",
        "end": "2026-05-31",
        "category": "expos",
        "expected_attendance": 20_000,
        "hotel_impact": "moderate",
        "source": "hardcoded",
    },
    {
        "name": "Florida SuperCon",
        "start": "2026-07-10",
        "end": "2026-07-12",
        "category": "expos",
        "expected_attendance": 50_000,
        "hotel_impact": "moderate",
        "source": "hardcoded",
    },
    {
        "name": "Art Basel Miami Beach",
        "start": "2026-12-04",
        "end": "2026-12-06",
        "category": "expos",
        "expected_attendance": 83_000,
        "hotel_impact": "extreme",
        "source": "hardcoded",
    },
]

# Impact multipliers for prediction adjustment
IMPACT_MULTIPLIERS = {
    "extreme": 0.40,    # +40% upward pressure on prices
    "very_high": 0.25,  # +25%
    "high": 0.15,       # +15%
    "moderate": 0.08,   # +8%
    "low": 0.03,        # +3%
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_events_db() -> None:
    """Create events table if it doesn't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS miami_events (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            start_date          TEXT    NOT NULL,
            end_date            TEXT    NOT NULL,
            category            TEXT,
            expected_attendance INTEGER,
            hotel_impact        TEXT,
            source              TEXT    DEFAULT 'hardcoded',
            collected_ts        TEXT,
            UNIQUE(name, start_date)
        );

        CREATE INDEX IF NOT EXISTS idx_events_dates
            ON miami_events(start_date, end_date);
    """)
    conn.close()


def seed_major_events() -> int:
    """Insert hardcoded major events (skip if already exist)."""
    conn = _get_conn()
    inserted = 0
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for ev in MIAMI_MAJOR_EVENTS:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO miami_events "
                "(name, start_date, end_date, category, expected_attendance, "
                "hotel_impact, source, collected_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ev["name"], ev["start"], ev["end"], ev["category"],
                 ev["expected_attendance"], ev["hotel_impact"], ev["source"], ts),
            )
            inserted += conn.total_changes
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def save_events(events: list[dict]) -> int:
    """Save dynamic events from API sources."""
    if not events:
        return 0

    conn = _get_conn()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for ev in events:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO miami_events "
                "(name, start_date, end_date, category, expected_attendance, "
                "hotel_impact, source, collected_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ev["name"],
                    ev["start_date"],
                    ev.get("end_date", ev["start_date"]),
                    ev.get("category", "other"),
                    ev.get("expected_attendance", 0),
                    ev.get("hotel_impact", "low"),
                    ev.get("source", "api"),
                    ts,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def load_events_for_dates(date_from: str, date_to: str) -> pd.DataFrame:
    """Load events that overlap with a date range."""
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM miami_events "
        "WHERE start_date <= ? AND end_date >= ? "
        "ORDER BY start_date",
        conn, params=(date_to, date_from),
    )
    conn.close()
    return df


def get_events_for_date(check_date: str) -> list[dict]:
    """Get all events active on a specific date."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT name, start_date, end_date, category, expected_attendance, "
        "hotel_impact, source FROM miami_events "
        "WHERE start_date <= ? AND end_date >= ? "
        "ORDER BY expected_attendance DESC",
        (check_date, check_date),
    ).fetchall()
    conn.close()

    return [
        {
            "name": r[0], "start_date": r[1], "end_date": r[2],
            "category": r[3], "expected_attendance": r[4],
            "hotel_impact": r[5], "source": r[6],
        }
        for r in rows
    ]


def get_impact_for_date(check_date: str) -> dict:
    """Calculate combined hotel impact for a specific date.

    Returns dict with impact_level, multiplier, events list.
    """
    events = get_events_for_date(check_date)
    if not events:
        return {"impact_level": "none", "multiplier": 0, "events": []}

    # Use the highest-impact event's multiplier
    max_impact = "low"
    max_multiplier = 0
    for ev in events:
        impact = ev.get("hotel_impact", "low")
        mult = IMPACT_MULTIPLIERS.get(impact, 0)
        if mult > max_multiplier:
            max_multiplier = mult
            max_impact = impact

    return {
        "impact_level": max_impact,
        "multiplier": max_multiplier,
        "events": events,
        "event_count": len(events),
    }


def get_events_summary() -> dict:
    """Get summary of all stored events."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM miami_events").fetchone()[0]
    upcoming = conn.execute(
        "SELECT COUNT(*) FROM miami_events WHERE start_date >= ?",
        (date.today().isoformat(),),
    ).fetchone()[0]

    # Next 3 upcoming events
    next_events = conn.execute(
        "SELECT name, start_date, end_date, category, expected_attendance, hotel_impact "
        "FROM miami_events WHERE start_date >= ? "
        "ORDER BY start_date LIMIT 5",
        (date.today().isoformat(),),
    ).fetchall()
    conn.close()

    return {
        "total_events": total,
        "upcoming_events": upcoming,
        "next_events": [
            {
                "name": r[0], "start_date": r[1], "end_date": r[2],
                "category": r[3], "expected_attendance": r[4],
                "hotel_impact": r[5],
            }
            for r in next_events
        ],
    }
