"""Audit Trail & Compliance — complete decision trail for every signal and action.

Logged events:
  - Every CALL/PUT signal generated (with all inputs)
  - Every queue insertion (opportunity + override)
  - Every rule application and result
  - Every parameter change
  - Every manual override

Storage: SQLite audit_trail.db
Retention: 365 days
API: GET /api/v1/salesoffice/audit?from=&to=&hotel_id=

This module is append-only — it never modifies or deletes records.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

RETENTION_DAYS = 365
MAX_EVENTS_PER_QUERY = 1000
MAX_PAYLOAD_SIZE = 10_000  # max chars for event payload JSON

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
AUDIT_DB_PATH = _DB_DIR / "audit_trail.db"

# Event types
EVENT_SIGNAL_GENERATED = "signal_generated"
EVENT_QUEUE_INSERT = "queue_insert"
EVENT_QUEUE_EXECUTE = "queue_execute"
EVENT_QUEUE_FAIL = "queue_fail"
EVENT_RULE_APPLIED = "rule_applied"
EVENT_OVERRIDE = "manual_override"
EVENT_PARAM_CHANGE = "param_change"
EVENT_SYSTEM = "system"


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class AuditEvent:
    """A single audit trail event."""
    event_id: int | None = None
    event_type: str = ""
    timestamp: str = ""
    detail_id: int = 0
    hotel_id: int = 0
    hotel_name: str = ""
    signal: str = ""
    action: str = ""            # what happened
    actor: str = "system"       # system / operator / rule_engine
    payload: dict = field(default_factory=dict)  # event-specific data
    correlation_id: str = ""    # link related events

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditSummary:
    """Summary of audit events over a time period."""
    from_date: str = ""
    to_date: str = ""
    total_events: int = 0
    by_type: dict = field(default_factory=dict)
    by_hotel: dict = field(default_factory=dict)
    recent_events: list[AuditEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "from_date": self.from_date,
            "to_date": self.to_date,
            "total_events": self.total_events,
            "by_type": self.by_type,
            "by_hotel": self.by_hotel,
            "recent_events": [e.to_dict() for e in self.recent_events],
        }


# ── Database ─────────────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    detail_id       INTEGER DEFAULT 0,
    hotel_id        INTEGER DEFAULT 0,
    hotel_name      TEXT DEFAULT '',
    signal          TEXT DEFAULT '',
    action          TEXT DEFAULT '',
    actor           TEXT DEFAULT 'system',
    payload_json    TEXT DEFAULT '{}',
    correlation_id  TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_hotel ON audit_events(hotel_id);
CREATE INDEX IF NOT EXISTS idx_audit_detail ON audit_events(detail_id);
CREATE INDEX IF NOT EXISTS idx_audit_corr ON audit_events(correlation_id);
"""


@contextmanager
def _get_audit_db(db_path: Path | None = None):
    """Thread-safe connection to audit_trail.db."""
    path = db_path or AUDIT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_audit_db(db_path: Path | None = None) -> None:
    """Create audit tables if needed."""
    with _get_audit_db(db_path) as conn:
        conn.executescript(_CREATE_TABLES)


# ── Event Logging ────────────────────────────────────────────────────

def log_event(
    event_type: str,
    action: str,
    detail_id: int = 0,
    hotel_id: int = 0,
    hotel_name: str = "",
    signal: str = "",
    actor: str = "system",
    payload: dict | None = None,
    correlation_id: str = "",
    db_path: Path | None = None,
) -> int:
    """Log a single audit event.

    Args:
        event_type: One of EVENT_* constants.
        action: Human-readable description of what happened.
        detail_id: Room detail ID (0 for system events).
        hotel_id: Hotel ID.
        hotel_name: Hotel name.
        signal: CALL/PUT/NONE signal.
        actor: Who triggered this (system/operator/rule_engine).
        payload: Additional event data.
        correlation_id: Link related events.
        db_path: Optional DB path.

    Returns:
        event_id of the inserted record.
    """
    init_audit_db(db_path)
    now = datetime.utcnow().isoformat() + "Z"

    payload_json = "{}"
    if payload:
        try:
            payload_json = json.dumps(payload, default=str)
            if len(payload_json) > MAX_PAYLOAD_SIZE:
                payload_json = json.dumps({"truncated": True, "keys": list(payload.keys())})
        except (TypeError, ValueError):
            payload_json = "{}"

    with _get_audit_db(db_path) as conn:
        cursor = conn.execute("""
            INSERT INTO audit_events
            (event_type, timestamp, detail_id, hotel_id, hotel_name,
             signal, action, actor, payload_json, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_type, now, detail_id, hotel_id, hotel_name,
            signal, action, actor, payload_json, correlation_id,
        ))
        return cursor.lastrowid or 0


def log_signal_batch(
    signals: list[dict],
    correlation_id: str = "",
    db_path: Path | None = None,
) -> int:
    """Log a batch of signal generation events.

    Args:
        signals: List of signal dicts from options_engine.
        correlation_id: Shared ID for this analysis run.
        db_path: Optional DB path.

    Returns:
        Number of events logged.
    """
    init_audit_db(db_path)
    now = datetime.utcnow().isoformat() + "Z"
    count = 0

    with _get_audit_db(db_path) as conn:
        for sig in signals:
            try:
                detail_id = int(sig.get("detail_id", 0) or 0)
                hotel_id = int(sig.get("hotel_id", 0) or 0)
                signal = sig.get("signal", "NONE") or "NONE"
                confidence = sig.get("confidence", "")

                payload = {
                    "P_up": sig.get("P_up", 0),
                    "P_down": sig.get("P_down", 0),
                    "sigma_1d": sig.get("sigma_1d", 0),
                    "T": sig.get("T", 0),
                    "confidence": confidence,
                    "regime": sig.get("regime", ""),
                }

                conn.execute("""
                    INSERT INTO audit_events
                    (event_type, timestamp, detail_id, hotel_id, hotel_name,
                     signal, action, actor, payload_json, correlation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    EVENT_SIGNAL_GENERATED, now, detail_id, hotel_id,
                    sig.get("hotel_name", ""),
                    signal,
                    f"Signal {signal} ({confidence}) generated",
                    "system",
                    json.dumps(payload, default=str),
                    correlation_id,
                ))
                count += 1
            except (ValueError, TypeError, sqlite3.Error) as exc:
                logger.debug("Audit log skip signal: %s", exc)
                continue

    return count


# ── Query Functions ──────────────────────────────────────────────────

def get_audit_events(
    from_date: str | None = None,
    to_date: str | None = None,
    hotel_id: int | None = None,
    event_type: str | None = None,
    detail_id: int | None = None,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[AuditEvent]:
    """Query audit events with filters.

    Args:
        from_date: ISO date string (inclusive).
        to_date: ISO date string (inclusive).
        hotel_id: Filter by hotel.
        event_type: Filter by event type.
        detail_id: Filter by detail ID.
        limit: Max results.
        db_path: Optional DB path.

    Returns:
        List of AuditEvent sorted by timestamp desc.
    """
    init_audit_db(db_path)

    clauses: list[str] = []
    params: list = []

    if from_date:
        clauses.append("timestamp >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("timestamp <= ?")
        params.append(to_date + "T23:59:59Z")
    if hotel_id is not None:
        clauses.append("hotel_id = ?")
        params.append(hotel_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if detail_id is not None:
        clauses.append("detail_id = ?")
        params.append(detail_id)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    limit = min(limit, MAX_EVENTS_PER_QUERY)
    sql = f"SELECT * FROM audit_events{where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _get_audit_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_event(dict(r)) for r in rows]


def get_audit_summary(
    days_back: int = 7,
    db_path: Path | None = None,
) -> AuditSummary:
    """Get summary of audit events over a time period.

    Args:
        days_back: Number of days to summarize.
        db_path: Optional DB path.

    Returns:
        AuditSummary with counts and recent events.
    """
    now = datetime.utcnow()
    from_dt = now - timedelta(days=days_back)
    from_str = from_dt.isoformat() + "Z"
    to_str = now.isoformat() + "Z"

    events = get_audit_events(from_date=from_str, to_date=to_str, limit=200, db_path=db_path)

    summary = AuditSummary(
        from_date=from_str,
        to_date=to_str,
        total_events=len(events),
    )

    for e in events:
        summary.by_type[e.event_type] = summary.by_type.get(e.event_type, 0) + 1
        if e.hotel_id > 0:
            key = f"{e.hotel_id}:{e.hotel_name}"
            summary.by_hotel[key] = summary.by_hotel.get(key, 0) + 1

    summary.recent_events = events[:20]
    return summary


def cleanup_old_events(
    retention_days: int = RETENTION_DAYS,
    db_path: Path | None = None,
) -> int:
    """Remove audit events older than retention period.

    Args:
        retention_days: Keep events newer than this.
        db_path: Optional DB path.

    Returns:
        Number of events deleted.
    """
    init_audit_db(db_path)
    cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat() + "Z"

    with _get_audit_db(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM audit_events WHERE timestamp < ?", (cutoff,)
        )
        return cursor.rowcount


# ── Helpers ──────────────────────────────────────────────────────────

def _row_to_event(row: dict) -> AuditEvent:
    """Convert DB row to AuditEvent."""
    payload = {}
    try:
        payload = json.loads(row.get("payload_json", "{}") or "{}")
    except (json.JSONDecodeError, TypeError):
        pass

    return AuditEvent(
        event_id=row.get("event_id"),
        event_type=row.get("event_type", ""),
        timestamp=row.get("timestamp", ""),
        detail_id=int(row.get("detail_id", 0) or 0),
        hotel_id=int(row.get("hotel_id", 0) or 0),
        hotel_name=row.get("hotel_name", ""),
        signal=row.get("signal", ""),
        action=row.get("action", ""),
        actor=row.get("actor", "system"),
        payload=payload,
        correlation_id=row.get("correlation_id", ""),
    )
