"""Opportunity Rules Engine — persistent rules that auto-match CALL options after each scan.

Unlike the one-time opportunity_queue, rules are persistent filters that match against
current options on every scan cycle. When an option matches a rule, it generates
a buy opportunity (INSERT into BackOfficeOPT + MED_Opportunities). Rules can be
paused/resumed and track execution stats.

Architecture:
    Prediction System -> runs match_opp_rules() after each scan
    -> matched options are executed via execute_matched_opportunities()
    -> execution results logged to opportunity_rule_log

NOTE: The Azure SQL user (prediction_reader) needs INSERT permission on:
    - BackOfficeOPT
    - MED_Opportunities
Grant these separately; this module does NOT attempt to GRANT.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration / Guardrails ───────────────────────────────────────

ALLOWED_SIGNALS = ("CALL", "STRONG_CALL")
MIN_MARGIN_PCT = 30          # push_price >= buy_price * 1.30
MAX_ROOMS_PER_OPP = 1
MAX_RULES = 50
DAILY_BUDGET_DEFAULT = 2000.0

# SQLite DB path — same directory as other data stores
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DB_DIR / "opportunity_rules.db"


# ── Exceptions ───────────────────────────────────────────────────────

class OppRuleValidationError(ValueError):
    """Raised when an opportunity rule fails validation guardrails."""
    pass


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class OpportunityRule:
    """A persistent opportunity (CALL) rule definition."""
    id: int | None = None
    name: str = ""
    signal: str = "CALL"
    hotel_id: int | None = None
    category: str | None = None
    board: str | None = None
    min_T: int = 7
    max_T: int = 120
    push_markup_pct: float = 30.0
    is_active: bool = True
    created_at: str = ""
    last_run_at: str | None = None
    total_executions: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Database Setup ───────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS opportunity_rules (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL DEFAULT '',
    signal            TEXT NOT NULL DEFAULT 'CALL',
    hotel_id          INTEGER,
    category          TEXT,
    board             TEXT,
    min_T             INTEGER NOT NULL DEFAULT 7,
    max_T             INTEGER NOT NULL DEFAULT 120,
    push_markup_pct   REAL NOT NULL DEFAULT 30.0,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL,
    last_run_at       TEXT,
    total_executions  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS opportunity_rule_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id           INTEGER NOT NULL,
    rule_name         TEXT NOT NULL DEFAULT '',
    detail_id         INTEGER NOT NULL,
    hotel_id          INTEGER NOT NULL,
    hotel_name        TEXT NOT NULL DEFAULT '',
    buy_price         REAL NOT NULL,
    push_price        REAL NOT NULL,
    profit_usd        REAL NOT NULL DEFAULT 0.0,
    opp_id            INTEGER,
    db_write          INTEGER NOT NULL DEFAULT 0,
    executed_at       TEXT NOT NULL,
    FOREIGN KEY (rule_id) REFERENCES opportunity_rules(id)
);

CREATE INDEX IF NOT EXISTS idx_opp_log_rule ON opportunity_rule_log(rule_id);
CREATE INDEX IF NOT EXISTS idx_opp_log_detail ON opportunity_rule_log(detail_id);
CREATE INDEX IF NOT EXISTS idx_opp_log_date ON opportunity_rule_log(executed_at);
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


def init_opp_rules_db() -> None:
    """Create the opportunity rules and log tables if they don't exist."""
    with _get_db() as conn:
        conn.executescript(_CREATE_TABLES)
    logger.info("opportunity_rules: initialized at %s", DB_PATH)


# ── Helpers ──────────────────────────────────────────────────────────

def _row_to_rule(row: sqlite3.Row) -> OpportunityRule:
    """Convert a SQLite row to OpportunityRule."""
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    return OpportunityRule(**d)


# ── CRUD Operations ──────────────────────────────────────────────────

def create_opp_rule(
    signal: str,
    push_markup_pct: float = 30.0,
    name: str = "",
    hotel_id: int | None = None,
    category: str | None = None,
    board: str | None = None,
    min_T: int = 7,
    max_T: int = 120,
) -> OpportunityRule:
    """Create a new opportunity rule with validation.

    Raises OppRuleValidationError on guardrail violation.
    """
    # Validate signal
    if signal not in ALLOWED_SIGNALS:
        raise OppRuleValidationError(
            f"Signal '{signal}' not in allowed: {ALLOWED_SIGNALS}"
        )

    # Validate margin
    if push_markup_pct < MIN_MARGIN_PCT:
        raise OppRuleValidationError(
            f"Markup {push_markup_pct}% below minimum {MIN_MARGIN_PCT}%"
        )

    if push_markup_pct <= 0:
        raise OppRuleValidationError("Markup must be positive")

    # Validate T range
    if min_T < 0 or max_T < 0:
        raise OppRuleValidationError("T range values must be non-negative")

    if min_T > max_T:
        raise OppRuleValidationError(
            f"min_T ({min_T}) must be <= max_T ({max_T})"
        )

    init_opp_rules_db()

    # Check rule count limit
    with _get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM opportunity_rules").fetchone()[0]
        if count >= MAX_RULES:
            raise OppRuleValidationError(
                f"Maximum {MAX_RULES} rules reached. Delete unused rules first."
            )

        now = datetime.utcnow().isoformat(timespec="seconds")
        cursor = conn.execute(
            """INSERT INTO opportunity_rules
               (name, signal, hotel_id, category, board, min_T, max_T,
                push_markup_pct, is_active, created_at, total_executions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0)""",
            (name, signal, hotel_id, category, board, min_T, max_T,
             push_markup_pct, now),
        )
        rule_id = cursor.lastrowid

    logger.info(
        "opportunity_rules: created rule #%d name='%s' signal=%s markup=%.0f%%",
        rule_id, name, signal, push_markup_pct,
    )

    return OpportunityRule(
        id=rule_id,
        name=name,
        signal=signal,
        hotel_id=hotel_id,
        category=category,
        board=board,
        min_T=min_T,
        max_T=max_T,
        push_markup_pct=push_markup_pct,
        is_active=True,
        created_at=now,
        total_executions=0,
    )


def get_opp_rules(active_only: bool = False) -> list[OpportunityRule]:
    """List all opportunity rules, optionally filtering to active only."""
    init_opp_rules_db()
    with _get_db() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM opportunity_rules WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM opportunity_rules ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_rule(r) for r in rows]


def get_opp_rule(rule_id: int) -> OpportunityRule | None:
    """Get a single opportunity rule by ID, or None if not found."""
    init_opp_rules_db()
    with _get_db() as conn:
        row = conn.execute(
            "SELECT * FROM opportunity_rules WHERE id = ?",
            (rule_id,),
        ).fetchone()
    return _row_to_rule(row) if row else None


def pause_opp_rule(rule_id: int) -> bool:
    """Deactivate a rule. Returns True if updated."""
    init_opp_rules_db()
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE opportunity_rules SET is_active = 0 WHERE id = ? AND is_active = 1",
            (rule_id,),
        )
    if cursor.rowcount > 0:
        logger.info("opportunity_rules: paused rule #%d", rule_id)
    return cursor.rowcount > 0


def resume_opp_rule(rule_id: int) -> bool:
    """Reactivate a rule. Returns True if updated."""
    init_opp_rules_db()
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE opportunity_rules SET is_active = 1 WHERE id = ? AND is_active = 0",
            (rule_id,),
        )
    if cursor.rowcount > 0:
        logger.info("opportunity_rules: resumed rule #%d", rule_id)
    return cursor.rowcount > 0


def delete_opp_rule(rule_id: int) -> bool:
    """Delete a rule permanently. Returns True if deleted."""
    init_opp_rules_db()
    with _get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM opportunity_rules WHERE id = ?",
            (rule_id,),
        )
    if cursor.rowcount > 0:
        logger.info("opportunity_rules: deleted rule #%d", rule_id)
    return cursor.rowcount > 0


# ── Matching Engine ──────────────────────────────────────────────────

def match_opp_rules(options: list[dict]) -> list[dict]:
    """Match active CALL rules against a list of options.

    Each option dict should have:
        detail_id, option_signal, hotel_id, current_price,
        days_to_checkin, category, board, hotel_name (optional)

    Multiple rules can match the same option — highest margin wins.

    Returns list of match dicts:
        detail_id, hotel_id, hotel_name, buy_price, push_price,
        profit_usd, rule_id, rule_name
    """
    rules = get_opp_rules(active_only=True)
    if not rules:
        return []

    # For each option, find the best matching rule (highest markup/profit)
    best_matches: dict[int, dict] = {}  # detail_id -> best match

    for option in options:
        detail_id = option.get("detail_id")
        opt_signal = option.get("option_signal", "")
        opt_hotel_id = option.get("hotel_id")
        opt_price = float(option.get("current_price", 0))
        opt_T = int(option.get("days_to_checkin", 0))
        opt_category = option.get("category", "")
        opt_board = option.get("board", "")
        opt_hotel_name = option.get("hotel_name", "")

        if opt_price <= 0:
            continue

        for rule in rules:
            # Signal filter
            if rule.signal != opt_signal:
                continue

            # Hotel filter
            if rule.hotel_id is not None and rule.hotel_id != opt_hotel_id:
                continue

            # Category filter
            if rule.category is not None and rule.category != opt_category:
                continue

            # Board filter
            if rule.board is not None and rule.board != opt_board:
                continue

            # T range filter
            if opt_T < rule.min_T or opt_T > rule.max_T:
                continue

            # Compute push price with markup
            push_price = round(opt_price * (1.0 + rule.push_markup_pct / 100.0), 2)
            profit_usd = round(push_price - opt_price, 2)

            # Keep best match (highest profit)
            existing = best_matches.get(detail_id)
            if existing is None or profit_usd > existing["profit_usd"]:
                best_matches[detail_id] = {
                    "detail_id": detail_id,
                    "hotel_id": opt_hotel_id,
                    "hotel_name": opt_hotel_name,
                    "buy_price": opt_price,
                    "push_price": push_price,
                    "profit_usd": profit_usd,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                }

    matches = list(best_matches.values())
    logger.info(
        "opportunity_rules: matched %d options against %d active rules",
        len(matches), len(rules),
    )
    return matches


# ── Daily Budget ─────────────────────────────────────────────────────

def get_daily_spend() -> float:
    """Read today's log to calculate total spend (buy_price) so far."""
    init_opp_rules_db()
    today_prefix = date.today().isoformat()
    with _get_db() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(buy_price), 0) as total
               FROM opportunity_rule_log
               WHERE executed_at LIKE ? AND db_write = 1""",
            (today_prefix + "%",),
        ).fetchone()
    return float(row["total"]) if row else 0.0


def _get_daily_budget() -> float:
    """Read daily budget from env var, default to DAILY_BUDGET_DEFAULT."""
    try:
        return float(os.getenv("OPPORTUNITY_DAILY_BUDGET", str(DAILY_BUDGET_DEFAULT)))
    except (ValueError, TypeError):
        return DAILY_BUDGET_DEFAULT


# ── Execution ────────────────────────────────────────────────────────

def execute_matched_opportunities(matches: list[dict]) -> dict:
    """Execute matched opportunities: write to Azure SQL BackOfficeOPT + MED_Opportunities.

    For each match dict (from match_opp_rules()):
        1. Check daily budget
        2. Check OPPORTUNITY_EXECUTE_ENABLED env var
        3. Duplicate check (existing active opp in BackOfficeOPT)
        4. Get hotel info + ratebycat mapping
        5. INSERT into BackOfficeOPT
        6. Get new opp_id (SCOPE_IDENTITY)
        7. INSERT into MED_Opportunities (one row per night)
        8. Log execution

    Returns summary: {"success": N, "failed": N, "skipped": N, "total": N}
    """
    summary = {"success": 0, "failed": 0, "skipped": 0, "total": len(matches)}

    if not matches:
        return summary

    # Check execution enabled
    execute_enabled = os.getenv("OPPORTUNITY_EXECUTE_ENABLED", "false").lower() == "true"
    if not execute_enabled:
        logger.warning("opportunity_rules execute: OPPORTUNITY_EXECUTE_ENABLED=false — skipping all")
        summary["skipped"] = len(matches)
        return summary

    # Connect to Azure SQL
    db_url = os.getenv("MEDICI_DB_URL", "")
    if not db_url:
        logger.warning("opportunity_rules execute: MEDICI_DB_URL not configured — skipping all")
        summary["skipped"] = len(matches)
        return summary

    try:
        import pyodbc
    except ImportError:
        logger.warning("opportunity_rules execute: pyodbc not installed — skipping all")
        summary["skipped"] = len(matches)
        return summary

    try:
        from urllib.parse import urlparse, parse_qs, unquote

        parsed = urlparse(db_url)
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        server = parsed.hostname or ""
        database = parsed.path.lstrip("/")
        qs_params = parse_qs(parsed.query)
        driver = qs_params.get("driver", ["ODBC Driver 18 for SQL Server"])[0]
        conn_str = (
            f"DRIVER={{{driver}}};Server={server};Database={database};"
            f"Uid={user};Pwd={password};Encrypt=yes;TrustServerCertificate=no;"
            f"Connection Timeout=15"
        )
        conn = pyodbc.connect(conn_str, timeout=15)
    except (pyodbc.Error, OSError, ValueError) as exc:
        logger.error("opportunity_rules execute: DB connect failed: %s", exc)
        summary["failed"] = len(matches)
        return summary

    daily_budget = _get_daily_budget()

    try:
        cursor = conn.cursor()

        for match in matches:
            detail_id = match["detail_id"]
            buy_price = match["buy_price"]
            push_price = match["push_price"]
            profit_usd = match["profit_usd"]
            rule_id = match["rule_id"]
            rule_name = match.get("rule_name", "")
            hotel_id = match.get("hotel_id", 0)
            hotel_name = match.get("hotel_name", "")

            # Step 1: Daily budget check
            current_spend = get_daily_spend()
            if current_spend + buy_price > daily_budget:
                logger.warning(
                    "opportunity_rules: budget exceeded — spend=$%.2f + buy=$%.2f > budget=$%.2f",
                    current_spend, buy_price, daily_budget,
                )
                summary["skipped"] += 1
                summary.setdefault("skip_reasons", []).append(f"{detail_id}: budget")
                continue

            # Step 2: Duplicate check — existing active opp
            try:
                cursor.execute("""
                    SELECT TOP 1 Id, StartDate, BuyPrice, Status FROM BackOfficeOPT
                    WHERE HotelID = ? AND Status IN (0, 1)
                    AND StartDate = (
                        SELECT TOP 1 o.DateFrom
                        FROM [SalesOffice.Details] d
                        JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
                        WHERE d.Id = ?
                    )
                """, hotel_id, detail_id)
                existing = cursor.fetchone()
                if existing:
                    dup_id = existing[0]
                    dup_date = existing[1]
                    logger.info(
                        "opportunity_rules: duplicate opp #%s date=%s for hotel=%d detail=%d — skipping",
                        dup_id, dup_date, hotel_id, detail_id,
                    )
                    summary["skipped"] += 1
                    summary.setdefault("skip_reasons", []).append(f"{detail_id}: duplicate opp #{dup_id}")
                    continue
            except (pyodbc.Error, OSError) as exc:
                logger.warning(
                    "opportunity_rules: duplicate check failed detail=%d: %s",
                    detail_id, exc,
                )
                # Continue anyway — better to attempt than skip

            # Step 3: Get hotel info + ratebycat mapping
            try:
                cursor.execute("""
                    SELECT d.Id, d.HotelId, d.RoomBoard, d.RoomCategory,
                           o.DateFrom, o.DateTo,
                           brd.BoardId, cat.CategoryId,
                           r.RatePlanCode, r.InvTypeCode
                    FROM [SalesOffice.Details] d
                    JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
                    LEFT JOIN MED_Board brd ON LOWER(brd.BoardCode) = LOWER(d.RoomBoard)
                    LEFT JOIN MED_RoomCategory cat ON LOWER(cat.[Name]) = LOWER(d.RoomCategory)
                    LEFT JOIN Med_Hotels_ratebycat r
                        ON r.HotelId = d.HotelId AND r.BoardId = brd.BoardId
                        AND r.CategoryId = cat.CategoryId
                    WHERE d.Id = ?
                """, detail_id)
                row = cursor.fetchone()
                if not row:
                    logger.warning(
                        "opportunity_rules: detail=%d not found in SalesOffice.Details",
                        detail_id,
                    )
                    summary["failed"] += 1
                    summary.setdefault("errors", []).append(f"detail {detail_id}: not found in DB")
                    log_opp_execution(
                        rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                        hotel_id=hotel_id, hotel_name=hotel_name,
                        buy_price=buy_price, push_price=push_price,
                        profit_usd=profit_usd, opp_id=None, db_write=False,
                    )
                    continue

                cols = [desc[0] for desc in cursor.description]
                detail = dict(zip(cols, row))
            except (pyodbc.Error, OSError) as exc:
                logger.error(
                    "opportunity_rules: detail lookup failed detail=%d: %s",
                    detail_id, exc,
                )
                summary["failed"] += 1
                log_opp_execution(
                    rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                    hotel_id=hotel_id, hotel_name=hotel_name,
                    buy_price=buy_price, push_price=push_price,
                    profit_usd=profit_usd, opp_id=None, db_write=False,
                )
                continue

            board_id = detail.get("BoardId")
            category_id = detail.get("CategoryId")
            rate_plan_code = detail.get("RatePlanCode") or ""
            inv_type_code = detail.get("InvTypeCode") or ""
            date_from = detail.get("DateFrom")
            date_to = detail.get("DateTo")

            if not board_id or not category_id or not date_from:
                logger.warning(
                    "opportunity_rules: missing mapping for detail=%d (board=%s, cat=%s, date=%s)",
                    detail_id, board_id, category_id, date_from,
                )
                summary["failed"] += 1
                summary.setdefault("errors", []).append(f"{detail_id}: missing mapping board={board_id} cat={category_id} date={date_from}")
                log_opp_execution(
                    rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                    hotel_id=hotel_id, hotel_name=hotel_name,
                    buy_price=buy_price, push_price=push_price,
                    profit_usd=profit_usd, opp_id=None, db_write=False,
                )
                continue

            # StartDate = checkin, EndDate = checkout (next day)
            start_date = date_from
            if hasattr(date_from, "strftime"):
                from datetime import timedelta
                end_date = date_from + timedelta(days=1)
            else:
                end_date = date_from  # fallback

            # Step 4: INSERT into BackOfficeOPT (matching C# BaseEF.cs pattern)
            opp_id = None
            try:
                cursor.execute(
                    """INSERT INTO BackOfficeOPT
                       (HotelID, StartDate, EndDate, BordID, CatrgoryID,
                        BuyPrice, PushPrice, MaxRooms, Status, DateInsert,
                        invTypeCode, ratePlanCode, CountryId, ReservationFirstName)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, GETDATE(),
                        ?, ?, 1, 'PricePredictor')""",
                    hotel_id, start_date, end_date, board_id, category_id,
                    buy_price, push_price, inv_type_code, rate_plan_code,
                )
                # Get the new opp_id
                cursor.execute("SELECT SCOPE_IDENTITY()")
                identity_row = cursor.fetchone()
                opp_id = int(identity_row[0]) if identity_row and identity_row[0] else None
                conn.commit()
            except (pyodbc.Error, OSError) as exc:
                logger.error(
                    "opportunity_rules: BackOfficeOPT insert failed detail=%d: %s",
                    detail_id, exc,
                )
                summary["failed"] += 1
                summary.setdefault("errors", []).append(f"BackOfficeOPT {detail_id}: {str(exc)[:200]}")
                log_opp_execution(
                    rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                    hotel_id=hotel_id, hotel_name=hotel_name,
                    buy_price=buy_price, push_price=push_price,
                    profit_usd=profit_usd, opp_id=None, db_write=False,
                )
                continue

            if not opp_id:
                # Try @@IDENTITY as fallback
                try:
                    cursor.execute("SELECT @@IDENTITY")
                    alt_row = cursor.fetchone()
                    opp_id = int(alt_row[0]) if alt_row and alt_row[0] else None
                except Exception:
                    pass

            if not opp_id:
                logger.error(
                    "opportunity_rules: SCOPE_IDENTITY returned None for detail=%d",
                    detail_id,
                )
                summary["failed"] += 1
                summary.setdefault("errors", []).append(f"{detail_id}: SCOPE_IDENTITY=None (INSERT may have succeeded)")
                log_opp_execution(
                    rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                    hotel_id=hotel_id, hotel_name=hotel_name,
                    buy_price=buy_price, push_price=push_price,
                    profit_usd=profit_usd, opp_id=None, db_write=False,
                )
                continue

            # Step 5: INSERT into MED_Opportunities (matching C# BaseEF.cs pattern)
            # Table name has hidden Unicode chars — must read actual name from sys.tables
            try:
                # Table name has hidden Unicode chars — find the real MED_ table
                cursor.execute("SELECT name FROM sys.tables WHERE name LIKE 'MED%pportunities' AND name NOT LIKE 'BAK%'")
                tbl_row = cursor.fetchone()
                med_opp_table = tbl_row[0] if tbl_row else "MED_Opportunities"
                logger.info("opportunity_rules: resolved MED_Opportunities table name: [%s]", med_opp_table)

                cursor.execute(
                    f"""INSERT INTO [{med_opp_table}]
                       (OpportunityMlId, DateForm, DateTo,
                        DestinationsType, DestinationsId,
                        PushHotelCode, PushBookingLimit,
                        PushInvTypeCode, PushRatePlanCode,
                        PushPrice, IsActive, IsPush, IsSale)
                       VALUES (?, ?, ?,
                        'hotel', ?,
                        ?, 1,
                        ?, ?,
                        ?, 1, 0, 0)""",
                    opp_id, start_date, end_date,
                    hotel_id,
                    hotel_id,
                    inv_type_code, rate_plan_code,
                    push_price,
                )
                conn.commit()
            except (pyodbc.Error, OSError, Exception) as exc:
                logger.error(
                    "opportunity_rules: MED_Opportunities insert failed opp=%d table=[%s]: %s",
                    opp_id, med_opp_table, exc,
                )
                summary.setdefault("errors", []).append(f"MED_Opp {detail_id}: {str(exc)[:200]}")
                # BackOfficeOPT was already inserted — log partial success
                log_opp_execution(
                    rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                    hotel_id=hotel_id, hotel_name=hotel_name,
                    buy_price=buy_price, push_price=push_price,
                    profit_usd=profit_usd, opp_id=opp_id, db_write=True,
                )
                summary["success"] += 1
                continue

            # Step 6: Log execution
            log_opp_execution(
                rule_id=rule_id, rule_name=rule_name, detail_id=detail_id,
                hotel_id=hotel_id, hotel_name=hotel_name,
                buy_price=buy_price, push_price=push_price,
                profit_usd=profit_usd, opp_id=opp_id, db_write=True,
            )
            summary["success"] += 1

    except (pyodbc.Error, OSError, ValueError) as exc:
        logger.error("opportunity_rules execute: unexpected error: %s", exc)
    finally:
        conn.close()

    logger.info(
        "opportunity_rules execute: total=%d success=%d failed=%d skipped=%d",
        summary["total"], summary["success"], summary["failed"], summary["skipped"],
    )
    return summary


# ── Execution Logging ────────────────────────────────────────────────

def log_opp_execution(
    rule_id: int,
    rule_name: str,
    detail_id: int,
    hotel_id: int,
    hotel_name: str,
    buy_price: float,
    push_price: float,
    profit_usd: float,
    opp_id: int | None = None,
    db_write: bool = False,
) -> int:
    """Log an opportunity rule execution to the audit trail.

    Returns the log entry ID.
    """
    init_opp_rules_db()
    now = datetime.utcnow().isoformat(timespec="seconds")

    with _get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO opportunity_rule_log
               (rule_id, rule_name, detail_id, hotel_id, hotel_name,
                buy_price, push_price, profit_usd, opp_id,
                db_write, executed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, rule_name, detail_id, hotel_id, hotel_name,
             buy_price, push_price, profit_usd, opp_id,
             int(db_write), now),
        )
        log_id = cursor.lastrowid

        # Update rule stats
        conn.execute(
            """UPDATE opportunity_rules
               SET total_executions = total_executions + 1, last_run_at = ?
               WHERE id = ?""",
            (now, rule_id),
        )

    logger.info(
        "opportunity_rules: logged execution rule=#%d detail=%d buy=$%.2f push=$%.2f opp_id=%s",
        rule_id, detail_id, buy_price, push_price, opp_id,
    )
    return log_id


def get_opp_execution_log(
    rule_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Read execution log entries, optionally filtered by rule_id."""
    init_opp_rules_db()
    with _get_db() as conn:
        if rule_id is not None:
            rows = conn.execute(
                """SELECT * FROM opportunity_rule_log
                   WHERE rule_id = ?
                   ORDER BY executed_at DESC LIMIT ?""",
                (rule_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM opportunity_rule_log
                   ORDER BY executed_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()

    return [dict(r) for r in rows]
