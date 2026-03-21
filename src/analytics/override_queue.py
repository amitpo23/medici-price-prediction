"""Price Override Queue — SQLite-based job queue for price push execution.

The prediction system is READ-ONLY — it never writes to SalesOffice/Zenith.
Instead, when an operator wants to override a price (undercut competitors by $X),
a request is saved to a local SQLite queue. The external price-override skill
reads this same SQLite file, executes the push, and updates the status.

Architecture:
    Prediction System (this code) → writes to override_queue.db
    Price Override Skill (external) → reads override_queue.db, pushes to Zenith,
                                      updates status to done/failed

Queue states: pending → picked → done / failed
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration / Guardrails ───────────────────────────────────────

MAX_DISCOUNT_USD = 10.0          # Max $10 discount per room
MIN_TARGET_PRICE_USD = 50.0      # Floor — never push below $50
MAX_BULK_SIZE = 100              # Max overrides in one batch
ALLOWED_SIGNALS = ("PUT", "STRONG_PUT")
DEFAULT_DISCOUNT_USD = 1.0

# SQLite DB path — same directory as price_store.db so the skill can find it
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DB_DIR / "override_queue.db"


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class OverrideRequest:
    """One price override request in the queue."""
    id: int | None = None
    detail_id: int = 0
    hotel_id: int = 0
    hotel_name: str = ""
    category: str = ""
    board: str = ""
    checkin_date: str = ""
    current_price: float = 0.0
    discount_usd: float = DEFAULT_DISCOUNT_USD
    target_price: float = 0.0
    signal: str = "PUT"
    confidence: str = ""
    path_min_price: float | None = None
    status: str = "pending"
    created_at: str = ""
    picked_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    trigger_type: str = "manual"
    batch_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Database Setup ───────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS override_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id       INTEGER NOT NULL,
    hotel_id        INTEGER NOT NULL,
    hotel_name      TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    board           TEXT DEFAULT '',
    checkin_date    TEXT DEFAULT '',
    current_price   REAL NOT NULL,
    discount_usd    REAL NOT NULL DEFAULT 1.0,
    target_price    REAL NOT NULL,
    signal          TEXT DEFAULT 'PUT',
    confidence      TEXT DEFAULT '',
    path_min_price  REAL,
    status          TEXT DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    picked_at       TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    trigger_type    TEXT DEFAULT 'manual',
    batch_id        TEXT
);

CREATE INDEX IF NOT EXISTS idx_override_status ON override_requests(status);
CREATE INDEX IF NOT EXISTS idx_override_batch ON override_requests(batch_id);
CREATE INDEX IF NOT EXISTS idx_override_detail ON override_requests(detail_id);
"""


@contextmanager
def _get_db():
    """Thread-safe SQLite connection with WAL mode for concurrent reads."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
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


def init_db() -> None:
    """Create the queue table if it doesn't exist."""
    with _get_db() as conn:
        conn.executescript(_CREATE_TABLE)
    logger.info("override_queue: initialized at %s", DB_PATH)


# ── Validation ───────────────────────────────────────────────────────

class OverrideValidationError(ValueError):
    """Raised when an override request fails guardrails."""
    pass


def validate_request(
    current_price: float,
    discount_usd: float,
    signal: str = "PUT",
) -> float:
    """Validate and compute target price. Returns target_price.

    Raises OverrideValidationError on guardrail violation.
    """
    if discount_usd <= 0:
        raise OverrideValidationError("Discount must be positive")

    if discount_usd > MAX_DISCOUNT_USD:
        raise OverrideValidationError(
            f"Discount ${discount_usd} exceeds maximum ${MAX_DISCOUNT_USD}"
        )

    if current_price <= 0:
        raise OverrideValidationError("Current price must be positive")

    target_price = round(current_price - discount_usd, 2)

    if target_price < MIN_TARGET_PRICE_USD:
        raise OverrideValidationError(
            f"Target price ${target_price} below minimum ${MIN_TARGET_PRICE_USD}"
        )

    if signal not in ALLOWED_SIGNALS:
        raise OverrideValidationError(
            f"Signal '{signal}' not in allowed: {ALLOWED_SIGNALS}"
        )

    return target_price


# ── Queue Operations ─────────────────────────────────────────────────

def enqueue_override(
    detail_id: int,
    hotel_id: int,
    current_price: float,
    discount_usd: float = DEFAULT_DISCOUNT_USD,
    signal: str = "PUT",
    confidence: str = "",
    hotel_name: str = "",
    category: str = "",
    board: str = "",
    checkin_date: str = "",
    path_min_price: float | None = None,
    trigger_type: str = "manual",
    batch_id: str | None = None,
) -> OverrideRequest:
    """Add a single override request to the queue.

    Validates guardrails, computes target_price, saves to SQLite.
    Returns the created OverrideRequest with its ID.
    """
    target_price = validate_request(current_price, discount_usd, signal)
    now = datetime.utcnow().isoformat(timespec="seconds")

    init_db()  # ensure table exists

    with _get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO override_requests
               (detail_id, hotel_id, hotel_name, category, board, checkin_date,
                current_price, discount_usd, target_price,
                signal, confidence, path_min_price,
                status, created_at, trigger_type, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (
                detail_id, hotel_id, hotel_name, category, board, checkin_date,
                current_price, discount_usd, target_price,
                signal, confidence, path_min_price,
                now, trigger_type, batch_id,
            ),
        )
        request_id = cursor.lastrowid

    logger.info(
        "override_queue: enqueued #%d detail=%d price=$%.2f→$%.2f (-%s$) [%s]",
        request_id, detail_id, current_price, target_price, discount_usd, trigger_type,
    )

    return OverrideRequest(
        id=request_id,
        detail_id=detail_id,
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        category=category,
        board=board,
        checkin_date=checkin_date,
        current_price=current_price,
        discount_usd=discount_usd,
        target_price=target_price,
        signal=signal,
        confidence=confidence,
        path_min_price=path_min_price,
        status="pending",
        created_at=now,
        trigger_type=trigger_type,
        batch_id=batch_id,
    )


def enqueue_bulk_puts(
    analysis: dict,
    signals: list[dict],
    discount_usd: float = DEFAULT_DISCOUNT_USD,
    hotel_id_filter: int | None = None,
) -> tuple[str, list[OverrideRequest]]:
    """Queue overrides for ALL active PUT signals.

    Args:
        analysis: Full analysis dict with predictions.
        signals: Pre-computed signals from compute_next_day_signals.
        discount_usd: Dollar discount to apply.
        hotel_id_filter: Optional — only override for this hotel.

    Returns:
        (batch_id, list of created requests)
    """
    # Filter to PUT signals only
    put_signals = [
        s for s in signals
        if s.get("recommendation") in ALLOWED_SIGNALS
    ]

    if hotel_id_filter is not None:
        put_signals = [
            s for s in put_signals
            if s.get("hotel_id") == hotel_id_filter
        ]

    if not put_signals:
        return "", []

    if len(put_signals) > MAX_BULK_SIZE:
        raise OverrideValidationError(
            f"Bulk size {len(put_signals)} exceeds maximum {MAX_BULK_SIZE}. "
            f"Filter by hotel or reduce scope."
        )

    batch_id = f"bulk-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    results: list[OverrideRequest] = []
    predictions = analysis.get("predictions", {})

    for sig in put_signals:
        detail_id = sig.get("detail_id")
        pred = predictions.get(str(detail_id)) or predictions.get(detail_id) or {}
        current_price = float(sig.get("S_t", 0) or pred.get("current_price", 0) or 0)

        if current_price <= 0:
            continue

        try:
            req = enqueue_override(
                detail_id=int(detail_id),
                hotel_id=int(sig.get("hotel_id", 0)),
                current_price=current_price,
                discount_usd=discount_usd,
                signal=str(sig.get("recommendation", "PUT")),
                confidence=str(sig.get("confidence", "")),
                hotel_name=str(sig.get("hotel_name", "")),
                category=str(sig.get("category", "")),
                board=str(sig.get("board", "")),
                checkin_date=str(sig.get("checkin_date", "")),
                path_min_price=sig.get("path_min_price"),
                trigger_type="bulk_put",
                batch_id=batch_id,
            )
            results.append(req)
        except OverrideValidationError as exc:
            logger.debug("bulk override skipped detail %s: %s", detail_id, exc)
            continue

    logger.info(
        "override_queue: bulk enqueued %d/%d PUTs, batch=%s, discount=$%.2f",
        len(results), len(put_signals), batch_id, discount_usd,
    )

    return batch_id, results


# ── Query Operations ─────────────────────────────────────────────────

def _row_to_request(row: sqlite3.Row) -> OverrideRequest:
    """Convert a SQLite row to OverrideRequest."""
    return OverrideRequest(**dict(row))


def get_queue(
    status: str | None = None,
    batch_id: str | None = None,
    hotel_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OverrideRequest], int]:
    """Query the override queue with filters.

    Returns (requests, total_count).
    """
    init_db()

    where_clauses: list[str] = []
    params: list = []

    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if batch_id:
        where_clauses.append("batch_id = ?")
        params.append(batch_id)
    if hotel_id is not None:
        where_clauses.append("hotel_id = ?")
        params.append(hotel_id)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    with _get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM override_requests WHERE {where_sql}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT * FROM override_requests
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

    return [_row_to_request(r) for r in rows], total


def get_request(request_id: int) -> OverrideRequest | None:
    """Get a single override request by ID."""
    init_db()
    with _get_db() as conn:
        row = conn.execute(
            "SELECT * FROM override_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    return _row_to_request(row) if row else None


def get_queue_stats() -> dict:
    """Get queue statistics."""
    init_db()
    with _get_db() as conn:
        stats = {}
        for status in ("pending", "picked", "done", "failed"):
            count = conn.execute(
                "SELECT COUNT(*) FROM override_requests WHERE status = ?",
                (status,),
            ).fetchone()[0]
            stats[status] = count
        stats["total"] = sum(stats.values())
    return stats


# ── Status Updates (called by external skill via SQLite) ─────────────

def mark_picked(request_id: int) -> bool:
    """Mark a request as picked up by the execution skill."""
    init_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE override_requests SET status = 'picked', picked_at = ? WHERE id = ? AND status = 'pending'",
            (now, request_id),
        )
    return cursor.rowcount > 0


def mark_completed(request_id: int, success: bool, error_message: str = "") -> bool:
    """Mark a request as done or failed."""
    init_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    status = "done" if success else "failed"
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE override_requests SET status = ?, completed_at = ?, error_message = ? WHERE id = ?",
            (status, now, error_message or None, request_id),
        )
    return cursor.rowcount > 0


def get_pending_requests(limit: int = 50) -> list[OverrideRequest]:
    """Get all pending requests — used by the external skill to pick up work."""
    init_db()
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM override_requests WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_request(r) for r in rows]


# ── History / Audit ──────────────────────────────────────────────────

def get_history(
    days: int = 30,
    hotel_id: int | None = None,
) -> dict:
    """Get override execution history for analysis.

    Returns summary stats: total overrides, success rate, avg discount,
    breakdown by hotel.
    """
    init_db()
    from_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
    from_date = from_date.replace(day=max(1, from_date.day - days))

    with _get_db() as conn:
        where = "created_at >= ?"
        params: list = [from_date.isoformat()]

        if hotel_id is not None:
            where += " AND hotel_id = ?"
            params.append(hotel_id)

        rows = conn.execute(
            f"SELECT * FROM override_requests WHERE {where} ORDER BY created_at DESC",
            params,
        ).fetchall()

    if not rows:
        return {"total": 0, "done": 0, "failed": 0, "pending": 0, "avg_discount": 0}

    requests = [dict(r) for r in rows]
    done = [r for r in requests if r["status"] == "done"]
    failed = [r for r in requests if r["status"] == "failed"]
    pending = [r for r in requests if r["status"] == "pending"]

    avg_discount = sum(r["discount_usd"] for r in requests) / len(requests) if requests else 0
    total_discount_volume = sum(r["discount_usd"] for r in done)

    # Per-hotel breakdown
    hotels: dict[int, dict] = {}
    for r in requests:
        hid = r["hotel_id"]
        if hid not in hotels:
            hotels[hid] = {"hotel_id": hid, "hotel_name": r["hotel_name"], "total": 0, "done": 0, "failed": 0}
        hotels[hid]["total"] += 1
        if r["status"] == "done":
            hotels[hid]["done"] += 1
        elif r["status"] == "failed":
            hotels[hid]["failed"] += 1

    return {
        "total": len(requests),
        "done": len(done),
        "failed": len(failed),
        "pending": len(pending),
        "success_rate_pct": round(len(done) / len(requests) * 100, 1) if requests else 0,
        "avg_discount_usd": round(avg_discount, 2),
        "total_discount_volume_usd": round(total_discount_volume, 2),
        "by_hotel": sorted(hotels.values(), key=lambda h: h["total"], reverse=True),
        "days": days,
    }
