"""Position Tracking & PnL — track executed trades and compute profit/loss.

Reads from opportunity_queue.db (CALL) and override_queue.db (PUT) to build
a unified position book. Each "done" queue entry = open position. When the
check-in date passes, the position is closed and scored against actual prices.

Position model:
  - entry_price: what we paid (CALL) or pushed to (PUT)
  - entry_date: when the action was executed
  - current_price: latest scan price from analysis
  - predicted_exit_price: forward curve terminal price
  - unrealized_pnl: current_price - entry_price (CALL) or entry_price - current_price (PUT)
  - realized_pnl: actual outcome after check-in
  - status: OPEN / CLOSED / EXPIRED

This module is READ-ONLY on the queue databases — it only reads, never writes.
PnL computations are stored in a separate positions.db to avoid touching queues.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

MAX_EXPOSURE_PER_HOTEL = 50_000.0  # $ — configurable guardrail
MAX_TOTAL_POSITIONS = 5_000        # safety cap
CONCENTRATION_WARNING_PCT = 30.0   # warn if single hotel > 30% of book

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
POSITIONS_DB_PATH = _DB_DIR / "positions.db"
OPPORTUNITY_DB_PATH = _DB_DIR / "opportunity_queue.db"
OVERRIDE_DB_PATH = _DB_DIR / "override_queue.db"


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class Position:
    """A single tracked position (CALL buy or PUT override)."""
    position_id: int | None = None
    source: str = ""             # "opportunity" or "override"
    source_id: int = 0           # id in the source queue table
    detail_id: int = 0
    hotel_id: int = 0
    hotel_name: str = ""
    category: str = ""
    board: str = ""
    checkin_date: str = ""
    signal: str = ""             # CALL or PUT
    confidence: str = ""

    # Prices
    entry_price: float = 0.0    # buy_price (CALL) or target_price (PUT)
    push_price: float = 0.0     # push price used (CALL only)
    current_price: float = 0.0  # latest observed price
    predicted_exit: float = 0.0 # forward curve prediction at checkin

    # PnL
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    pnl_pct: float = 0.0

    # Timing
    entry_date: str = ""
    close_date: str = ""
    days_held: int = 0
    days_to_checkin: int = 0

    # Status
    status: str = "OPEN"        # OPEN / CLOSED / EXPIRED

    def to_dict(self) -> dict:
        return {k: round(v, 2) if isinstance(v, float) else v
                for k, v in asdict(self).items()}


@dataclass
class PnLSummary:
    """Portfolio-level profit/loss summary."""
    timestamp: str = ""

    # Counts
    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    expired_positions: int = 0

    # PnL
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_pnl: float = 0.0
    avg_pnl_pct: float = 0.0

    # Win/loss
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0   # gross_profit / gross_loss
    best_trade: float = 0.0
    worst_trade: float = 0.0

    # Exposure
    total_exposure: float = 0.0
    call_exposure: float = 0.0
    put_exposure: float = 0.0

    # By type
    call_pnl: float = 0.0
    put_pnl: float = 0.0
    call_count: int = 0
    put_count: int = 0

    # Concentration warnings
    warnings: list[str] = field(default_factory=list)

    # Hotel breakdown
    hotel_pnl: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {k: round(v, 4) if isinstance(v, float) else v
             for k, v in asdict(self).items() if k not in ("hotel_pnl", "warnings")}
        d["warnings"] = self.warnings
        d["hotel_pnl"] = self.hotel_pnl
        return d


# ── Database ─────────────────────────────────────────────────────────

_CREATE_POSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS positions (
    position_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_id       INTEGER NOT NULL,
    detail_id       INTEGER NOT NULL,
    hotel_id        INTEGER NOT NULL,
    hotel_name      TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    board           TEXT DEFAULT '',
    checkin_date    TEXT DEFAULT '',
    signal          TEXT DEFAULT '',
    confidence      TEXT DEFAULT '',
    entry_price     REAL NOT NULL,
    push_price      REAL DEFAULT 0,
    current_price   REAL DEFAULT 0,
    predicted_exit  REAL DEFAULT 0,
    unrealized_pnl  REAL DEFAULT 0,
    realized_pnl    REAL DEFAULT 0,
    pnl_pct         REAL DEFAULT 0,
    entry_date      TEXT NOT NULL,
    close_date      TEXT DEFAULT '',
    days_held       INTEGER DEFAULT 0,
    days_to_checkin INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'OPEN',
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pos_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_pos_hotel ON positions(hotel_id);
CREATE INDEX IF NOT EXISTS idx_pos_detail ON positions(detail_id);
CREATE INDEX IF NOT EXISTS idx_pos_source ON positions(source, source_id);
"""


@contextmanager
def _get_positions_db(db_path: Path | None = None):
    """Thread-safe connection to positions.db."""
    path = db_path or POSITIONS_DB_PATH
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


def init_positions_db(db_path: Path | None = None) -> None:
    """Create positions table if it doesn't exist."""
    with _get_positions_db(db_path) as conn:
        conn.executescript(_CREATE_POSITIONS_TABLE)
    logger.info("positions_db: initialized at %s", db_path or POSITIONS_DB_PATH)


# ── Position Sync ────────────────────────────────────────────────────

def sync_positions_from_queues(
    db_path: Path | None = None,
    opp_db_path: Path | None = None,
    ovr_db_path: Path | None = None,
) -> dict:
    """Sync completed queue entries into the positions table.

    Reads 'done' entries from opportunity_queue.db and override_queue.db,
    creates Position records for any not yet tracked.

    Returns: {new_opportunities: int, new_overrides: int}
    """
    init_positions_db(db_path)
    result = {"new_opportunities": 0, "new_overrides": 0}

    # Sync opportunity queue (CALL positions)
    opp_path = opp_db_path or OPPORTUNITY_DB_PATH
    if opp_path.exists():
        try:
            result["new_opportunities"] = _sync_opportunity_positions(
                db_path=db_path, opp_db_path=opp_path
            )
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Failed to sync opportunity positions: %s", exc)

    # Sync override queue (PUT positions)
    ovr_path = ovr_db_path or OVERRIDE_DB_PATH
    if ovr_path.exists():
        try:
            result["new_overrides"] = _sync_override_positions(
                db_path=db_path, ovr_db_path=ovr_path
            )
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Failed to sync override positions: %s", exc)

    return result


def _sync_opportunity_positions(
    db_path: Path | None = None,
    opp_db_path: Path | None = None,
) -> int:
    """Import done opportunities as CALL positions."""
    opp_path = opp_db_path or OPPORTUNITY_DB_PATH
    count = 0

    # Read done entries from opportunity queue
    opp_conn = sqlite3.connect(str(opp_path), timeout=10)
    opp_conn.row_factory = sqlite3.Row
    try:
        rows = opp_conn.execute(
            "SELECT * FROM opportunity_queue WHERE status = 'done'"
        ).fetchall()
    except sqlite3.OperationalError:
        opp_conn.close()
        return 0
    opp_conn.close()

    if not rows:
        return 0

    now = datetime.utcnow().isoformat() + "Z"

    with _get_positions_db(db_path) as conn:
        for row in rows:
            row_dict = dict(row)
            source_id = row_dict.get("id", 0)

            # Skip if already tracked
            existing = conn.execute(
                "SELECT 1 FROM positions WHERE source='opportunity' AND source_id=?",
                (source_id,)
            ).fetchone()
            if existing:
                continue

            checkin_str = row_dict.get("checkin_date", "")
            entry_date = row_dict.get("completed_at") or row_dict.get("created_at", now)

            conn.execute("""
                INSERT INTO positions (
                    source, source_id, detail_id, hotel_id, hotel_name,
                    category, board, checkin_date, signal, confidence,
                    entry_price, push_price, predicted_exit,
                    entry_date, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """, (
                "opportunity",
                source_id,
                row_dict.get("detail_id", 0),
                row_dict.get("hotel_id", 0),
                row_dict.get("hotel_name", ""),
                row_dict.get("category", ""),
                row_dict.get("board", ""),
                checkin_str,
                row_dict.get("signal", "CALL"),
                row_dict.get("confidence", ""),
                row_dict.get("buy_price", 0.0),
                row_dict.get("push_price", 0.0),
                row_dict.get("predicted_price", 0.0),
                entry_date,
                now,
            ))
            count += 1

    return count


def _sync_override_positions(
    db_path: Path | None = None,
    ovr_db_path: Path | None = None,
) -> int:
    """Import done overrides as PUT positions."""
    ovr_path = ovr_db_path or OVERRIDE_DB_PATH
    count = 0

    ovr_conn = sqlite3.connect(str(ovr_path), timeout=10)
    ovr_conn.row_factory = sqlite3.Row
    try:
        rows = ovr_conn.execute(
            "SELECT * FROM override_requests WHERE status = 'done'"
        ).fetchall()
    except sqlite3.OperationalError:
        ovr_conn.close()
        return 0
    ovr_conn.close()

    if not rows:
        return 0

    now = datetime.utcnow().isoformat() + "Z"

    with _get_positions_db(db_path) as conn:
        for row in rows:
            row_dict = dict(row)
            source_id = row_dict.get("id", 0)

            existing = conn.execute(
                "SELECT 1 FROM positions WHERE source='override' AND source_id=?",
                (source_id,)
            ).fetchone()
            if existing:
                continue

            entry_date = row_dict.get("completed_at") or row_dict.get("created_at", now)

            conn.execute("""
                INSERT INTO positions (
                    source, source_id, detail_id, hotel_id, hotel_name,
                    category, board, checkin_date, signal, confidence,
                    entry_price, predicted_exit,
                    entry_date, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """, (
                "override",
                source_id,
                row_dict.get("detail_id", 0),
                row_dict.get("hotel_id", 0),
                row_dict.get("hotel_name", ""),
                row_dict.get("category", ""),
                row_dict.get("board", ""),
                row_dict.get("checkin_date", ""),
                row_dict.get("signal", "PUT"),
                row_dict.get("confidence", ""),
                row_dict.get("target_price", 0.0),
                row_dict.get("current_price", 0.0),  # predicted_exit = original price
                entry_date,
                now,
            ))
            count += 1

    return count


# ── Price Update & PnL Calculation ───────────────────────────────────

def update_positions_prices(
    analysis: dict,
    db_path: Path | None = None,
) -> int:
    """Update current_price and PnL for all open positions from latest analysis.

    Args:
        analysis: Full analysis dict with predictions keyed by detail_id.
        db_path: Optional positions.db path.

    Returns:
        Number of positions updated.
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        return 0

    # Build lookup: detail_id → current_price
    price_lookup: dict[int, float] = {}
    for did, pred in predictions.items():
        cp = float(pred.get("current_price", 0) or 0)
        if cp > 0:
            price_lookup[int(did)] = cp

    if not price_lookup:
        return 0

    now = datetime.utcnow().isoformat() + "Z"
    today = date.today().isoformat()
    updated = 0

    with _get_positions_db(db_path) as conn:
        rows = conn.execute(
            "SELECT position_id, detail_id, entry_price, signal, source, "
            "entry_date, checkin_date FROM positions WHERE status = 'OPEN'"
        ).fetchall()

        for row in rows:
            row_dict = dict(row)
            detail_id = row_dict["detail_id"]
            entry_price = row_dict["entry_price"]
            signal = row_dict["signal"]

            current_price = price_lookup.get(detail_id)
            if current_price is None:
                continue

            # Compute PnL based on position type
            if signal in ("CALL", "STRONG_CALL"):
                # CALL: profit when price goes UP (we bought low)
                unrealized = current_price - entry_price
            else:
                # PUT: profit when price goes DOWN (we overrode high)
                unrealized = entry_price - current_price

            pnl_pct = (unrealized / entry_price * 100) if entry_price > 0 else 0.0

            # Days held
            try:
                entry_dt = datetime.fromisoformat(
                    row_dict["entry_date"].replace("Z", "+00:00")
                ).date()
                days_held = (date.today() - entry_dt).days
            except (ValueError, TypeError):
                days_held = 0

            # Days to checkin
            try:
                checkin_dt = date.fromisoformat(row_dict["checkin_date"][:10])
                days_to_checkin = (checkin_dt - date.today()).days
            except (ValueError, TypeError):
                days_to_checkin = 0

            # Check if position should be closed (checkin passed)
            status = "OPEN"
            realized = 0.0
            close_date = ""
            if days_to_checkin <= 0:
                status = "CLOSED"
                realized = unrealized  # crystallize PnL
                close_date = today

            conn.execute("""
                UPDATE positions SET
                    current_price = ?, unrealized_pnl = ?, realized_pnl = ?,
                    pnl_pct = ?, days_held = ?, days_to_checkin = ?,
                    status = ?, close_date = ?, updated_at = ?
                WHERE position_id = ?
            """, (
                round(current_price, 2),
                round(unrealized, 2),
                round(realized, 2),
                round(pnl_pct, 2),
                days_held,
                days_to_checkin,
                status,
                close_date,
                now,
                row_dict["position_id"],
            ))
            updated += 1

    return updated


# ── Query Functions ──────────────────────────────────────────────────

def get_positions(
    status: str | None = None,
    hotel_id: int | None = None,
    signal: str | None = None,
    db_path: Path | None = None,
) -> list[Position]:
    """Get positions with optional filters.

    Args:
        status: Filter by OPEN/CLOSED/EXPIRED (None = all)
        hotel_id: Filter by hotel (None = all)
        signal: Filter by CALL/PUT (None = all)
        db_path: Optional positions.db path

    Returns:
        List of Position objects
    """
    init_positions_db(db_path)

    clauses: list[str] = []
    params: list = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if hotel_id is not None:
        clauses.append("hotel_id = ?")
        params.append(hotel_id)
    if signal:
        if signal in ("CALL", "STRONG_CALL"):
            clauses.append("signal IN ('CALL', 'STRONG_CALL')")
        elif signal in ("PUT", "STRONG_PUT"):
            clauses.append("signal IN ('PUT', 'STRONG_PUT')")
        else:
            clauses.append("signal = ?")
            params.append(signal)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f"SELECT * FROM positions{where} ORDER BY entry_date DESC"

    with _get_positions_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_position(dict(r)) for r in rows]


def get_pnl_summary(
    hotel_id: int | None = None,
    db_path: Path | None = None,
) -> PnLSummary:
    """Compute portfolio PnL summary.

    Args:
        hotel_id: Filter to specific hotel (None = all)
        db_path: Optional positions.db path

    Returns:
        PnLSummary with aggregated metrics
    """
    positions = get_positions(hotel_id=hotel_id, db_path=db_path)

    summary = PnLSummary(
        timestamp=datetime.utcnow().isoformat() + "Z",
        total_positions=len(positions),
    )

    if not positions:
        return summary

    # Categorize
    open_pos = [p for p in positions if p.status == "OPEN"]
    closed_pos = [p for p in positions if p.status == "CLOSED"]
    expired_pos = [p for p in positions if p.status == "EXPIRED"]

    summary.open_positions = len(open_pos)
    summary.closed_positions = len(closed_pos)
    summary.expired_positions = len(expired_pos)

    # PnL
    summary.total_unrealized_pnl = sum(p.unrealized_pnl for p in open_pos)
    summary.total_realized_pnl = sum(p.realized_pnl for p in closed_pos)
    summary.total_pnl = summary.total_unrealized_pnl + summary.total_realized_pnl

    all_pnl_pcts = [p.pnl_pct for p in positions if p.entry_price > 0]
    summary.avg_pnl_pct = (sum(all_pnl_pcts) / len(all_pnl_pcts)) if all_pnl_pcts else 0.0

    # Win/loss analysis (on closed positions)
    if closed_pos:
        winners = [p for p in closed_pos if p.realized_pnl > 0]
        losers = [p for p in closed_pos if p.realized_pnl < 0]

        summary.winning_trades = len(winners)
        summary.losing_trades = len(losers)
        summary.win_rate = len(winners) / len(closed_pos) if closed_pos else 0.0

        if winners:
            gross_profit = sum(p.realized_pnl for p in winners)
            summary.avg_win = gross_profit / len(winners)
            summary.best_trade = max(p.realized_pnl for p in winners)
        else:
            gross_profit = 0.0

        if losers:
            gross_loss = abs(sum(p.realized_pnl for p in losers))
            summary.avg_loss = -gross_loss / len(losers)
            summary.worst_trade = min(p.realized_pnl for p in losers)
        else:
            gross_loss = 0.0

        summary.profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
            float("inf") if gross_profit > 0 else 0.0
        )

    # Exposure
    call_positions = [p for p in positions if p.signal in ("CALL", "STRONG_CALL")]
    put_positions = [p for p in positions if p.signal in ("PUT", "STRONG_PUT")]

    summary.call_count = len(call_positions)
    summary.put_count = len(put_positions)
    summary.call_exposure = sum(p.entry_price for p in call_positions if p.status == "OPEN")
    summary.put_exposure = sum(p.entry_price for p in put_positions if p.status == "OPEN")
    summary.total_exposure = summary.call_exposure + summary.put_exposure
    summary.call_pnl = sum(
        (p.unrealized_pnl if p.status == "OPEN" else p.realized_pnl) for p in call_positions
    )
    summary.put_pnl = sum(
        (p.unrealized_pnl if p.status == "OPEN" else p.realized_pnl) for p in put_positions
    )

    # Hotel breakdown
    hotel_map: dict[int, list[Position]] = {}
    for p in positions:
        hotel_map.setdefault(p.hotel_id, []).append(p)

    for hid, hpositions in sorted(hotel_map.items()):
        h_exposure = sum(p.entry_price for p in hpositions if p.status == "OPEN")
        h_pnl = sum(
            (p.unrealized_pnl if p.status == "OPEN" else p.realized_pnl)
            for p in hpositions
        )
        h_name = hpositions[0].hotel_name if hpositions else ""

        summary.hotel_pnl.append({
            "hotel_id": hid,
            "hotel_name": h_name,
            "positions": len(hpositions),
            "open": sum(1 for p in hpositions if p.status == "OPEN"),
            "closed": sum(1 for p in hpositions if p.status == "CLOSED"),
            "exposure": round(h_exposure, 2),
            "pnl": round(h_pnl, 2),
            "exposure_pct": round(
                h_exposure / summary.total_exposure * 100, 1
            ) if summary.total_exposure > 0 else 0.0,
        })

    # Concentration warnings
    for hp in summary.hotel_pnl:
        if hp["exposure_pct"] > CONCENTRATION_WARNING_PCT:
            summary.warnings.append(
                f"{hp['hotel_name']} ({hp['hotel_id']}) concentration: "
                f"{hp['exposure_pct']}% of total exposure"
            )

    if summary.total_exposure > MAX_EXPOSURE_PER_HOTEL * len(hotel_map):
        summary.warnings.append(
            f"Total exposure ${summary.total_exposure:,.0f} exceeds portfolio limit"
        )

    return summary


# ── Helpers ──────────────────────────────────────────────────────────

def _row_to_position(row: dict) -> Position:
    """Convert a SQLite row dict to a Position object."""
    return Position(
        position_id=row.get("position_id"),
        source=row.get("source", ""),
        source_id=row.get("source_id", 0),
        detail_id=row.get("detail_id", 0),
        hotel_id=row.get("hotel_id", 0),
        hotel_name=row.get("hotel_name", ""),
        category=row.get("category", ""),
        board=row.get("board", ""),
        checkin_date=row.get("checkin_date", ""),
        signal=row.get("signal", ""),
        confidence=row.get("confidence", ""),
        entry_price=float(row.get("entry_price", 0) or 0),
        push_price=float(row.get("push_price", 0) or 0),
        current_price=float(row.get("current_price", 0) or 0),
        predicted_exit=float(row.get("predicted_exit", 0) or 0),
        unrealized_pnl=float(row.get("unrealized_pnl", 0) or 0),
        realized_pnl=float(row.get("realized_pnl", 0) or 0),
        pnl_pct=float(row.get("pnl_pct", 0) or 0),
        entry_date=row.get("entry_date", ""),
        close_date=row.get("close_date", ""),
        days_held=int(row.get("days_held", 0) or 0),
        days_to_checkin=int(row.get("days_to_checkin", 0) or 0),
        status=row.get("status", "OPEN"),
    )
