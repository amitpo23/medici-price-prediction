"""Opportunity Queue — SQLite-based job queue for CALL signal execution.

The prediction system is READ-ONLY — it never writes to SalesOffice/Azure SQL.
Instead, when the system identifies a CALL signal with $50+ predicted profit,
a purchase opportunity request is queued to a local SQLite DB.
The external insert-opp skill reads this queue, creates BackOfficeOPT +
MED_Opportunities records in Azure SQL, and the BuyRoom WebJob executes
the actual purchase.

Architecture:
    Prediction System (this code) → writes to opportunity_queue.db
    Insert Opp Skill (external)   → reads opportunity_queue.db,
                                     creates records in Azure SQL,
                                     updates status to done/failed

Queue states: pending → picked → done / failed

Push price rule:  push_price = buy_price + FIXED_MARKUP_USD ($50)
Eligibility rule: predicted_price - buy_price >= MIN_PROFIT_USD ($50)
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration / Guardrails ───────────────────────────────────────

FIXED_MARKUP_USD = 50.0             # push_price = buy_price + $50
MIN_PROFIT_USD = 50.0               # Only CALL with predicted profit >= $50
MIN_BUY_PRICE = 1.0
MAX_BUY_PRICE = 5000.0
MAX_ROOMS = 30
MAX_BULK_SIZE = 50                  # Conservative — real money at stake
ALLOWED_SIGNALS = ("CALL", "STRONG_CALL")

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DB_DIR / "opportunity_queue.db"


# ── Board/Category Mapping ──────────────────────────────────────────

BOARD_MAP = {"ro": 1, "bb": 2}
CATEGORY_MAP = {"standard": 1, "superior": 2, "deluxe": 4, "suite": 12}


def _resolve_board_id(board: str) -> int:
    return BOARD_MAP.get(board.strip().lower(), 1)


def _resolve_category_id(category: str) -> int:
    return CATEGORY_MAP.get(category.strip().lower(), 1)


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class OpportunityRequest:
    """One insert-opportunity request in the queue."""
    id: int | None = None
    detail_id: int = 0
    hotel_id: int = 0
    hotel_name: str = ""
    category: str = ""
    board: str = ""
    checkin_date: str = ""
    buy_price: float = 0.0
    push_price: float = 0.0
    predicted_price: float = 0.0
    profit_usd: float = 0.0
    max_rooms: int = 1
    signal: str = "CALL"
    confidence: str = ""
    status: str = "pending"
    created_at: str = ""
    picked_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    opp_id: int | None = None          # BackOfficeOPT.id after skill executes
    trigger_type: str = "manual"
    batch_id: str | None = None
    board_id: int = 1
    category_id: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


class OpportunityValidationError(ValueError):
    """Raised when an opportunity request fails guardrails."""
    pass


# ── Database ─────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS opportunity_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id       INTEGER NOT NULL,
    hotel_id        INTEGER NOT NULL,
    hotel_name      TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    board           TEXT DEFAULT '',
    checkin_date    TEXT DEFAULT '',
    buy_price       REAL NOT NULL,
    push_price      REAL NOT NULL,
    predicted_price REAL DEFAULT 0,
    profit_usd      REAL DEFAULT 0,
    max_rooms       INTEGER DEFAULT 1,
    signal          TEXT DEFAULT 'CALL',
    confidence      TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    picked_at       TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    opp_id          INTEGER,
    trigger_type    TEXT DEFAULT 'manual',
    batch_id        TEXT,
    board_id        INTEGER DEFAULT 1,
    category_id     INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunity_queue(status);
CREATE INDEX IF NOT EXISTS idx_opp_batch ON opportunity_queue(batch_id);
CREATE INDEX IF NOT EXISTS idx_opp_detail ON opportunity_queue(detail_id);
CREATE INDEX IF NOT EXISTS idx_opp_hotel ON opportunity_queue(hotel_id);
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
    logger.info("opportunity_queue: initialized at %s", DB_PATH)


# ── Validation ───────────────────────────────────────────────────────

def validate_request(
    buy_price: float,
    predicted_price: float,
    signal: str = "CALL",
    max_rooms: int = 1,
) -> tuple[float, float]:
    """Validate and compute push_price and profit.

    Returns (push_price, profit_usd).
    Raises OpportunityValidationError on guardrail violation.
    """
    if signal.upper() not in ALLOWED_SIGNALS:
        raise OpportunityValidationError(
            f"Signal '{signal}' not in allowed: {ALLOWED_SIGNALS}"
        )

    if buy_price < MIN_BUY_PRICE:
        raise OpportunityValidationError(
            f"Buy price ${buy_price} below minimum ${MIN_BUY_PRICE}"
        )

    if buy_price > MAX_BUY_PRICE:
        raise OpportunityValidationError(
            f"Buy price ${buy_price} exceeds maximum ${MAX_BUY_PRICE}"
        )

    # Push price = buy + fixed $50 markup
    push_price = round(buy_price + FIXED_MARKUP_USD, 2)

    # Profit check: predicted must be >= buy + $50
    profit_usd = round(predicted_price - buy_price, 2)
    if profit_usd < MIN_PROFIT_USD:
        raise OpportunityValidationError(
            f"Predicted profit ${profit_usd} below minimum ${MIN_PROFIT_USD} "
            f"(buy=${buy_price}, predicted=${predicted_price})"
        )

    if max_rooms < 1 or max_rooms > MAX_ROOMS:
        raise OpportunityValidationError(
            f"Max rooms {max_rooms} out of range [1, {MAX_ROOMS}]"
        )

    return push_price, profit_usd


# ── Enqueue ──────────────────────────────────────────────────────────

def enqueue_opportunity(
    *,
    detail_id: int,
    hotel_id: int,
    buy_price: float,
    predicted_price: float,
    signal: str = "CALL",
    confidence: str = "",
    max_rooms: int = 1,
    hotel_name: str = "",
    category: str = "",
    board: str = "",
    checkin_date: str = "",
    trigger_type: str = "manual",
    batch_id: str | None = None,
) -> OpportunityRequest:
    """Queue a single insert-opportunity request.

    push_price is computed automatically: buy_price + $50.
    Only accepted if predicted_price - buy_price >= $50.
    """
    push_price, profit_usd = validate_request(
        buy_price, predicted_price, signal, max_rooms
    )
    now = datetime.utcnow().isoformat(timespec="seconds")

    board_id = _resolve_board_id(board)
    category_id = _resolve_category_id(category)

    init_db()

    with _get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO opportunity_queue
               (detail_id, hotel_id, hotel_name, category, board, checkin_date,
                buy_price, push_price, predicted_price, profit_usd,
                max_rooms, signal, confidence,
                status, created_at, trigger_type, batch_id,
                board_id, category_id)
               VALUES (?,?,?,?,?,?, ?,?,?,?, ?,?,?, 'pending',?,?,?, ?,?)""",
            (
                detail_id, hotel_id, hotel_name, category, board, checkin_date,
                round(buy_price, 2), push_price, round(predicted_price, 2), profit_usd,
                max_rooms, signal.upper(), confidence,
                now, trigger_type, batch_id,
                board_id, category_id,
            ),
        )
        request_id = cursor.lastrowid

    logger.info(
        "opportunity_queue: enqueued #%d detail=%d buy=$%.2f push=$%.2f "
        "predicted=$%.2f profit=$%.2f rooms=%d [%s]",
        request_id, detail_id, buy_price, push_price,
        predicted_price, profit_usd, max_rooms, trigger_type,
    )

    return OpportunityRequest(
        id=request_id,
        detail_id=detail_id,
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        category=category,
        board=board,
        checkin_date=checkin_date,
        buy_price=round(buy_price, 2),
        push_price=push_price,
        predicted_price=round(predicted_price, 2),
        profit_usd=profit_usd,
        max_rooms=max_rooms,
        signal=signal.upper(),
        confidence=confidence,
        status="pending",
        created_at=now,
        trigger_type=trigger_type,
        batch_id=batch_id,
        board_id=board_id,
        category_id=category_id,
    )


def enqueue_bulk_calls(
    *,
    analysis: dict,
    signals: list[dict],
    max_rooms: int = 1,
    hotel_id_filter: int | None = None,
) -> tuple[str, list[OpportunityRequest]]:
    """Queue opportunities for all CALL signals with $50+ predicted profit.

    push_price is always buy_price + $50.
    Only signals where predicted_price - current_price >= $50 are queued.
    """
    predictions = analysis.get("predictions", {})
    batch_id = f"OPP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    call_signals = [
        s for s in signals
        if s.get("recommendation", "").upper() in ALLOWED_SIGNALS
    ]

    if hotel_id_filter is not None:
        call_signals = [
            s for s in call_signals
            if int(s.get("hotel_id", 0)) == hotel_id_filter
        ]

    if not call_signals:
        return "", []

    if len(call_signals) > MAX_BULK_SIZE:
        raise OpportunityValidationError(
            f"Bulk size {len(call_signals)} exceeds maximum {MAX_BULK_SIZE}. "
            f"Filter by hotel or reduce scope."
        )

    results: list[OpportunityRequest] = []
    for sig in call_signals:
        detail_id = sig.get("detail_id")
        pred = predictions.get(str(detail_id)) or predictions.get(detail_id) or {}

        buy_price = float(
            sig.get("S_t", 0) or pred.get("current_price", 0) or 0
        )
        predicted_price = float(
            sig.get("predicted_price", 0)
            or pred.get("predicted_price", 0)
            or 0
        )

        if buy_price <= 0 or predicted_price <= 0:
            continue

        try:
            req = enqueue_opportunity(
                detail_id=int(detail_id),
                hotel_id=int(sig.get("hotel_id", 0) or pred.get("hotel_id", 0)),
                buy_price=buy_price,
                predicted_price=predicted_price,
                signal=str(sig.get("recommendation", "CALL")),
                confidence=str(sig.get("confidence", "")),
                max_rooms=max_rooms,
                hotel_name=str(sig.get("hotel_name", "") or pred.get("hotel_name", "")),
                category=str(sig.get("category", "") or pred.get("category", "")),
                board=str(sig.get("board", "") or pred.get("board", "")),
                checkin_date=str(sig.get("checkin_date", "") or pred.get("date_from", "")),
                trigger_type="bulk_call",
                batch_id=batch_id,
            )
            results.append(req)
        except OpportunityValidationError as exc:
            logger.debug("bulk opportunity skipped detail %s: %s", detail_id, exc)
            continue

    logger.info(
        "opportunity_queue: bulk enqueued %d/%d CALLs, batch=%s",
        len(results), len(call_signals), batch_id,
    )

    return batch_id, results


# ── Query ────────────────────────────────────────────────────────────

def _row_to_request(row: sqlite3.Row) -> OpportunityRequest:
    """Convert a SQLite row to OpportunityRequest."""
    return OpportunityRequest(**{k: row[k] for k in row.keys()})


def get_queue(
    *,
    status: str | None = None,
    hotel_id: int | None = None,
    batch_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OpportunityRequest], int]:
    """Query the opportunity queue with filters.

    Returns (requests, total_count).
    """
    init_db()

    where_clauses: list[str] = []
    params: list = []

    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if hotel_id is not None:
        where_clauses.append("hotel_id = ?")
        params.append(hotel_id)
    if batch_id:
        where_clauses.append("batch_id = ?")
        params.append(batch_id)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    with _get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM opportunity_queue WHERE {where_sql}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT * FROM opportunity_queue
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

    return [_row_to_request(r) for r in rows], total


def get_queue_stats() -> dict:
    """Get queue statistics."""
    init_db()
    with _get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status='picked' THEN 1 ELSE 0 END) as picked,
                SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                AVG(profit_usd) as avg_profit,
                SUM(CASE WHEN status='done' THEN profit_usd * max_rooms ELSE 0 END) as total_profit
            FROM opportunity_queue
        """).fetchone()
    return {
        "total": row[0] or 0,
        "pending": row[1] or 0,
        "picked": row[2] or 0,
        "done": row[3] or 0,
        "failed": row[4] or 0,
        "avg_profit_usd": round(row[5] or 0, 2),
        "total_profit_usd": round(row[6] or 0, 2),
    }


def get_request(request_id: int) -> OpportunityRequest | None:
    """Get a single opportunity request by ID."""
    init_db()
    with _get_db() as conn:
        row = conn.execute(
            "SELECT * FROM opportunity_queue WHERE id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row) if row else None


# ── Status Updates (called by external insert-opp skill) ─────────────

def mark_picked(request_id: int) -> bool:
    """Mark a request as picked up by the insert-opp skill."""
    init_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE opportunity_queue SET status = 'picked', picked_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, request_id),
        )
    return cursor.rowcount > 0


def mark_completed(
    request_id: int,
    *,
    success: bool,
    opp_id: int | None = None,
    error_message: str = "",
) -> bool:
    """Mark a request as done or failed.

    Args:
        request_id: Queue request ID.
        success: True=done, False=failed.
        opp_id: BackOfficeOPT.id created by skill (on success).
        error_message: Error details (on failure).
    """
    init_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    new_status = "done" if success else "failed"
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE opportunity_queue SET status = ?, completed_at = ?, "
            "opp_id = ?, error_message = ? WHERE id = ?",
            (new_status, now, opp_id, error_message or None, request_id),
        )
    return cursor.rowcount > 0


def get_pending_requests(limit: int = 50) -> list[OpportunityRequest]:
    """Get all pending requests — used by the external insert-opp skill."""
    init_db()
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM opportunity_queue WHERE status = 'pending' "
            "ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_request(r) for r in rows]


# ── History / Audit ──────────────────────────────────────────────────

def get_history(days: int = 30, hotel_id: int | None = None) -> dict:
    """Get opportunity execution history for analysis."""
    init_db()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    params: list = [since]
    hotel_filter = ""
    if hotel_id is not None:
        hotel_filter = " AND hotel_id = ?"
        params.append(hotel_id)

    with _get_db() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                AVG(profit_usd) as avg_profit,
                SUM(CASE WHEN status='done' THEN profit_usd * max_rooms ELSE 0 END) as total_profit
            FROM opportunity_queue WHERE created_at >= ?{hotel_filter}
        """, params).fetchone()

        hotels = conn.execute(f"""
            SELECT hotel_id, hotel_name, COUNT(*) as total,
                   SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                   SUM(CASE WHEN status='done' THEN profit_usd * max_rooms ELSE 0 END) as hotel_profit
            FROM opportunity_queue WHERE created_at >= ?{hotel_filter}
            GROUP BY hotel_id, hotel_name ORDER BY total DESC
        """, params).fetchall()

    total = row[0] or 0
    done = row[1] or 0

    return {
        "total": total,
        "done": done,
        "failed": row[2] or 0,
        "pending": row[3] or 0,
        "success_rate_pct": round(done / total * 100, 1) if total else 0,
        "avg_profit_usd": round(row[4] or 0, 2),
        "total_profit_usd": round(row[5] or 0, 2),
        "by_hotel": [
            {
                "hotel_id": h[0], "hotel_name": h[1], "total": h[2],
                "done": h[3], "failed": h[4] or 0,
                "total_profit_usd": round(h[5] or 0, 2),
            }
            for h in hotels
        ],
        "days": days,
    }
