"""Opportunity Queue — SQLite-based job queue for insert-opportunity execution.

When the prediction system identifies a CALL signal (good price to buy),
an operator can queue an "insert opportunity" request. The external
insert-opp skill reads the queue, creates BackOfficeOPT + MED_Opportunities
records, and updates the status.

Queue states: pending → picked → done / failed
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration / Guardrails ───────────────────────────────────────

MIN_BUY_PRICE = 1.0
MAX_BUY_PRICE = 10000.0
MIN_MARGIN_PCT = 3              # push_price >= 103% of buy_price
MAX_ROOMS = 30
MAX_BULK_SIZE = 50
ALLOWED_SIGNALS = ("CALL", "STRONG_CALL")
DEFAULT_MARGIN_PCT = 15         # default markup: buy * 1.15

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DB_DIR / "opportunity_queue.db"


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
    current_price: float = 0.0
    buy_price: float = 0.0
    push_price: float = 0.0
    margin_pct: float = 0.0
    max_rooms: int = 1
    signal: str = "CALL"
    confidence: str = ""
    status: str = "pending"
    created_at: str = ""
    picked_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    trigger_type: str = "manual"
    batch_id: str | None = None
    board_id: int = 1
    category_id: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


class OpportunityValidationError(Exception):
    pass


# ── Database ─────────────────────────────────────────────────────────

@contextmanager
def _get_db():
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_opportunity_db() -> None:
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detail_id INTEGER NOT NULL,
                hotel_id INTEGER NOT NULL,
                hotel_name TEXT DEFAULT '',
                category TEXT DEFAULT '',
                board TEXT DEFAULT '',
                checkin_date TEXT DEFAULT '',
                current_price REAL DEFAULT 0,
                buy_price REAL NOT NULL,
                push_price REAL NOT NULL,
                margin_pct REAL DEFAULT 0,
                max_rooms INTEGER DEFAULT 1,
                signal TEXT DEFAULT 'CALL',
                confidence TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                picked_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                trigger_type TEXT DEFAULT 'manual',
                batch_id TEXT,
                board_id INTEGER DEFAULT 1,
                category_id INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunity_queue(status)
        """)
        conn.commit()


# ── Board/Category mapping ───────────────────────────────────────────

BOARD_MAP = {"ro": 1, "bb": 2}
CATEGORY_MAP = {"standard": 1, "superior": 2, "deluxe": 4, "suite": 12}


def _resolve_board_id(board: str) -> int:
    return BOARD_MAP.get(board.strip().lower(), 1)


def _resolve_category_id(category: str) -> int:
    return CATEGORY_MAP.get(category.strip().lower(), 1)


# ── Enqueue ──────────────────────────────────────────────────────────

def enqueue_opportunity(
    *,
    detail_id: int,
    hotel_id: int,
    current_price: float,
    buy_price: float | None = None,
    push_price: float | None = None,
    margin_pct: float | None = None,
    max_rooms: int = 1,
    signal: str = "CALL",
    confidence: str = "",
    hotel_name: str = "",
    category: str = "",
    board: str = "",
    checkin_date: str = "",
    trigger_type: str = "manual",
    batch_id: str | None = None,
) -> OpportunityRequest:
    """Queue a single insert-opportunity request."""
    init_opportunity_db()

    if signal.upper() not in ALLOWED_SIGNALS:
        raise OpportunityValidationError(
            f"Signal must be {ALLOWED_SIGNALS}, got '{signal}'"
        )

    # Default buy_price = current_price (buy at market)
    if buy_price is None:
        buy_price = current_price

    # Default margin
    if margin_pct is None:
        margin_pct = DEFAULT_MARGIN_PCT

    # Compute push_price if not given
    if push_price is None:
        push_price = round(buy_price * (1 + margin_pct / 100.0), 2)

    # Validate
    if buy_price < MIN_BUY_PRICE or buy_price > MAX_BUY_PRICE:
        raise OpportunityValidationError(
            f"Buy price ${buy_price} out of range [${MIN_BUY_PRICE}, ${MAX_BUY_PRICE}]"
        )
    min_push = buy_price * (1 + MIN_MARGIN_PCT / 100.0)
    if push_price < min_push:
        raise OpportunityValidationError(
            f"Push price ${push_price:.2f} too low — minimum ${min_push:.2f} ({MIN_MARGIN_PCT}% margin)"
        )
    if max_rooms < 1 or max_rooms > MAX_ROOMS:
        raise OpportunityValidationError(
            f"Max rooms {max_rooms} out of range [1, {MAX_ROOMS}]"
        )

    actual_margin = round((push_price / buy_price - 1) * 100, 2) if buy_price > 0 else 0

    board_id = _resolve_board_id(board)
    category_id = _resolve_category_id(category)

    req = OpportunityRequest(
        detail_id=detail_id,
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        category=category,
        board=board,
        checkin_date=checkin_date,
        current_price=round(current_price, 2),
        buy_price=round(buy_price, 2),
        push_price=round(push_price, 2),
        margin_pct=actual_margin,
        max_rooms=max_rooms,
        signal=signal.upper(),
        confidence=confidence,
        status="pending",
        created_at=datetime.utcnow().isoformat(),
        trigger_type=trigger_type,
        batch_id=batch_id,
        board_id=board_id,
        category_id=category_id,
    )

    with _get_db() as conn:
        cur = conn.execute("""
            INSERT INTO opportunity_queue
            (detail_id, hotel_id, hotel_name, category, board, checkin_date,
             current_price, buy_price, push_price, margin_pct, max_rooms,
             signal, confidence, status, created_at, trigger_type, batch_id,
             board_id, category_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            req.detail_id, req.hotel_id, req.hotel_name, req.category, req.board,
            req.checkin_date, req.current_price, req.buy_price, req.push_price,
            req.margin_pct, req.max_rooms, req.signal, req.confidence, req.status,
            req.created_at, req.trigger_type, req.batch_id, req.board_id, req.category_id,
        ))
        conn.commit()
        req.id = cur.lastrowid

    logger.info(
        "Queued opportunity #%d: detail=%d buy=$%.2f push=$%.2f margin=%.1f%%",
        req.id, detail_id, buy_price, push_price, actual_margin,
    )
    return req


def enqueue_bulk_calls(
    *,
    analysis: dict,
    signals: list[dict],
    margin_pct: float = DEFAULT_MARGIN_PCT,
    max_rooms: int = 1,
    hotel_id_filter: int | None = None,
) -> tuple[str, list[OpportunityRequest]]:
    """Queue opportunities for all CALL signals in one batch."""
    predictions = analysis.get("predictions", {})
    batch_id = f"OPP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    call_signals = [
        s for s in signals
        if s.get("recommendation", "").upper() in ALLOWED_SIGNALS
    ]

    if hotel_id_filter:
        call_signals = [
            s for s in call_signals
            if int(s.get("hotel_id", 0)) == hotel_id_filter
        ]

    if len(call_signals) > MAX_BULK_SIZE:
        call_signals = call_signals[:MAX_BULK_SIZE]

    results: list[OpportunityRequest] = []
    for sig in call_signals:
        detail_id = sig.get("detail_id")
        pred = predictions.get(str(detail_id)) or predictions.get(detail_id) or {}
        current_price = float(pred.get("current_price", 0) or 0)
        if current_price <= 0:
            continue

        try:
            req = enqueue_opportunity(
                detail_id=int(detail_id),
                hotel_id=int(pred.get("hotel_id", 0)),
                current_price=current_price,
                margin_pct=margin_pct,
                max_rooms=max_rooms,
                signal=str(sig.get("recommendation", "CALL")),
                confidence=str(sig.get("confidence", "")),
                hotel_name=str(pred.get("hotel_name", "")),
                category=str(pred.get("category", "")),
                board=str(pred.get("board", "")),
                checkin_date=str(pred.get("date_from", "")),
                trigger_type="bulk",
                batch_id=batch_id,
            )
            results.append(req)
        except OpportunityValidationError as exc:
            logger.debug("Skipped opp for detail %s: %s", detail_id, exc)
            continue

    logger.info("Bulk opp batch %s: queued %d opportunities", batch_id, len(results))
    return batch_id, results


# ── Query ────────────────────────────────────────────────────────────

def get_opp_queue(
    *,
    status: str | None = None,
    hotel_id: int | None = None,
    batch_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OpportunityRequest], int]:
    init_opportunity_db()
    conditions = []
    params: list = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if hotel_id:
        conditions.append("hotel_id = ?")
        params.append(hotel_id)
    if batch_id:
        conditions.append("batch_id = ?")
        params.append(batch_id)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with _get_db() as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM opportunity_queue{where}", params).fetchone()
        total = row[0] if row else 0

        rows = conn.execute(
            f"SELECT * FROM opportunity_queue{where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return [_row_to_request(r) for r in rows], total


def get_opp_queue_stats() -> dict:
    init_opportunity_db()
    with _get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status='picked' THEN 1 ELSE 0 END) as picked,
                SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                AVG(margin_pct) as avg_margin,
                SUM(buy_price * max_rooms) as total_buy_volume
            FROM opportunity_queue
        """).fetchone()
    return {
        "total": row[0] or 0, "pending": row[1] or 0, "picked": row[2] or 0,
        "done": row[3] or 0, "failed": row[4] or 0,
        "avg_margin": round(row[5] or 0, 2),
        "total_buy_volume": round(row[6] or 0, 2),
    }


def get_opp_request(request_id: int) -> OpportunityRequest | None:
    init_opportunity_db()
    with _get_db() as conn:
        row = conn.execute(
            "SELECT * FROM opportunity_queue WHERE id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row) if row else None


def get_pending_opps(limit: int = 50) -> list[OpportunityRequest]:
    init_opportunity_db()
    with _get_db() as conn:
        conn.execute(
            "UPDATE opportunity_queue SET status='picked', picked_at=? WHERE status='pending'",
            (datetime.utcnow().isoformat(),),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM opportunity_queue WHERE status='picked' ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_request(r) for r in rows]


def mark_opp_completed(request_id: int, *, success: bool, error_message: str = "") -> bool:
    init_opportunity_db()
    new_status = "done" if success else "failed"
    with _get_db() as conn:
        cur = conn.execute(
            "UPDATE opportunity_queue SET status=?, completed_at=?, error_message=? WHERE id=? AND status IN ('pending','picked')",
            (new_status, datetime.utcnow().isoformat(), error_message or None, request_id),
        )
        conn.commit()
    return cur.rowcount > 0


def get_opp_history(days: int = 30, hotel_id: int | None = None) -> dict:
    init_opportunity_db()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    params: list = [since]
    hotel_filter = ""
    if hotel_id:
        hotel_filter = " AND hotel_id = ?"
        params.append(hotel_id)

    with _get_db() as conn:
        row = conn.execute(f"""
            SELECT COUNT(*), SUM(CASE WHEN status='done' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END),
                   AVG(margin_pct), SUM(buy_price * max_rooms)
            FROM opportunity_queue WHERE created_at >= ?{hotel_filter}
        """, params).fetchone()

        hotels = conn.execute(f"""
            SELECT hotel_id, hotel_name, COUNT(*) as total,
                   SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
            FROM opportunity_queue WHERE created_at >= ?{hotel_filter}
            GROUP BY hotel_id, hotel_name ORDER BY total DESC
        """, params).fetchall()

    return {
        "total_opportunities": row[0] or 0,
        "done": row[1] or 0, "failed": row[2] or 0,
        "avg_margin": round(row[3] or 0, 2),
        "total_buy_volume": round(row[4] or 0, 2),
        "by_hotel": [
            {"hotel_id": h[0], "hotel_name": h[1], "total": h[2], "done": h[3], "failed": h[4] or 0}
            for h in hotels
        ],
    }


def _row_to_request(row) -> OpportunityRequest:
    return OpportunityRequest(**{k: row[k] for k in row.keys()})
