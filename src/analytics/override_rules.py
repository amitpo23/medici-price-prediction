"""Override Rules Engine — persistent rules that auto-match options after each scan.

Unlike the one-time override_queue, rules are persistent filters that match against
current options on every scan cycle. When an option matches a rule, it generates
an override action (price reduction). Rules can be paused/resumed and track execution stats.

Architecture:
    Prediction System → runs match_rules() after each scan
    → matched options are queued via override_queue or executed directly
    → execution results logged to override_rule_log
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration / Guardrails ───────────────────────────────────────

ALLOWED_SIGNALS = ("PUT", "STRONG_PUT")
MAX_DISCOUNT_USD = 10.0
MIN_TARGET_PRICE_USD = 50.0
MAX_RULES = 50

# SQLite DB path — same directory as other data stores
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DB_DIR / "override_rules.db"


# ── Exceptions ───────────────────────────────────────────────────────

class RuleValidationError(ValueError):
    """Raised when a rule fails validation guardrails."""
    pass


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class OverrideRule:
    """A persistent override rule definition."""
    id: int | None = None
    name: str = ""
    signal: str = "PUT"
    hotel_id: int | None = None
    category: str | None = None
    board: str | None = None
    min_T: int = 7
    max_T: int = 120
    discount_usd: float = 1.0
    is_active: bool = True
    created_at: str = ""
    last_run_at: str | None = None
    total_executions: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Database Setup ───────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS override_rules (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL DEFAULT '',
    signal            TEXT NOT NULL DEFAULT 'PUT',
    hotel_id          INTEGER,
    category          TEXT,
    board             TEXT,
    min_T             INTEGER NOT NULL DEFAULT 7,
    max_T             INTEGER NOT NULL DEFAULT 120,
    discount_usd      REAL NOT NULL DEFAULT 1.0,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL,
    last_run_at       TEXT,
    total_executions  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS override_rule_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id           INTEGER NOT NULL,
    rule_name         TEXT NOT NULL DEFAULT '',
    detail_id         INTEGER NOT NULL,
    hotel_id          INTEGER NOT NULL,
    hotel_name        TEXT NOT NULL DEFAULT '',
    original_price    REAL NOT NULL,
    target_price      REAL NOT NULL,
    discount_usd      REAL NOT NULL,
    db_write          INTEGER NOT NULL DEFAULT 0,
    zenith_push       INTEGER NOT NULL DEFAULT 0,
    executed_at       TEXT NOT NULL,
    FOREIGN KEY (rule_id) REFERENCES override_rules(id)
);

CREATE INDEX IF NOT EXISTS idx_rule_log_rule ON override_rule_log(rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_log_detail ON override_rule_log(detail_id);
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


def init_rules_db() -> None:
    """Create the rules and log tables if they don't exist."""
    with _get_db() as conn:
        conn.executescript(_CREATE_TABLES)
    logger.info("override_rules: initialized at %s", DB_PATH)


# ── Helpers ──────────────────────────────────────────────────────────

def _row_to_rule(row: sqlite3.Row) -> OverrideRule:
    """Convert a SQLite row to OverrideRule."""
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    return OverrideRule(**d)


# ── CRUD Operations ──────────────────────────────────────────────────

def create_rule(
    signal: str,
    discount_usd: float,
    name: str = "",
    hotel_id: int | None = None,
    category: str | None = None,
    board: str | None = None,
    min_T: int = 7,
    max_T: int = 120,
) -> OverrideRule:
    """Create a new override rule with validation.

    Raises RuleValidationError on guardrail violation.
    """
    # Validate signal
    if signal not in ALLOWED_SIGNALS:
        raise RuleValidationError(
            f"Signal '{signal}' not in allowed: {ALLOWED_SIGNALS}"
        )

    # Validate discount
    if discount_usd <= 0:
        raise RuleValidationError("Discount must be positive")

    if discount_usd > MAX_DISCOUNT_USD:
        raise RuleValidationError(
            f"Discount ${discount_usd} exceeds maximum ${MAX_DISCOUNT_USD}"
        )

    # Validate T range
    if min_T < 0 or max_T < 0:
        raise RuleValidationError("T range values must be non-negative")

    if min_T > max_T:
        raise RuleValidationError(
            f"min_T ({min_T}) must be <= max_T ({max_T})"
        )

    init_rules_db()

    # Check rule count limit
    with _get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM override_rules").fetchone()[0]
        if count >= MAX_RULES:
            raise RuleValidationError(
                f"Maximum {MAX_RULES} rules reached. Delete unused rules first."
            )

        now = datetime.utcnow().isoformat(timespec="seconds")
        cursor = conn.execute(
            """INSERT INTO override_rules
               (name, signal, hotel_id, category, board, min_T, max_T,
                discount_usd, is_active, created_at, total_executions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0)""",
            (name, signal, hotel_id, category, board, min_T, max_T,
             discount_usd, now),
        )
        rule_id = cursor.lastrowid

    logger.info(
        "override_rules: created rule #%d name='%s' signal=%s discount=$%.2f",
        rule_id, name, signal, discount_usd,
    )

    return OverrideRule(
        id=rule_id,
        name=name,
        signal=signal,
        hotel_id=hotel_id,
        category=category,
        board=board,
        min_T=min_T,
        max_T=max_T,
        discount_usd=discount_usd,
        is_active=True,
        created_at=now,
        total_executions=0,
    )


def get_rules(active_only: bool = False) -> list[OverrideRule]:
    """List all rules, optionally filtering to active only."""
    init_rules_db()
    with _get_db() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM override_rules WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM override_rules ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_rule(r) for r in rows]


def get_rule(rule_id: int) -> OverrideRule | None:
    """Get a single rule by ID, or None if not found."""
    init_rules_db()
    with _get_db() as conn:
        row = conn.execute(
            "SELECT * FROM override_rules WHERE id = ?",
            (rule_id,),
        ).fetchone()
    return _row_to_rule(row) if row else None


def pause_rule(rule_id: int) -> bool:
    """Deactivate a rule. Returns True if updated."""
    init_rules_db()
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE override_rules SET is_active = 0 WHERE id = ? AND is_active = 1",
            (rule_id,),
        )
    if cursor.rowcount > 0:
        logger.info("override_rules: paused rule #%d", rule_id)
    return cursor.rowcount > 0


def resume_rule(rule_id: int) -> bool:
    """Reactivate a rule. Returns True if updated."""
    init_rules_db()
    with _get_db() as conn:
        cursor = conn.execute(
            "UPDATE override_rules SET is_active = 1 WHERE id = ? AND is_active = 0",
            (rule_id,),
        )
    if cursor.rowcount > 0:
        logger.info("override_rules: resumed rule #%d", rule_id)
    return cursor.rowcount > 0


def delete_rule(rule_id: int) -> bool:
    """Delete a rule permanently. Returns True if deleted."""
    init_rules_db()
    with _get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM override_rules WHERE id = ?",
            (rule_id,),
        )
    if cursor.rowcount > 0:
        logger.info("override_rules: deleted rule #%d", rule_id)
    return cursor.rowcount > 0


# ── Matching Engine ──────────────────────────────────────────────────

def match_rules(options: list[dict]) -> list[dict]:
    """Match active rules against a list of options.

    Each option dict should have:
        detail_id, option_signal, hotel_id, current_price,
        days_to_checkin, category, board, hotel_name (optional)

    Multiple rules can match the same option — highest discount wins.

    Returns list of match dicts:
        detail_id, hotel_id, hotel_name, current_price, target_price,
        discount_usd, rule_id, rule_name
    """
    rules = get_rules(active_only=True)
    if not rules:
        return []

    # For each option, find the best matching rule (highest discount)
    best_matches: dict[int, dict] = {}  # detail_id → best match

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

            # Compute target price
            target_price = round(opt_price - rule.discount_usd, 2)

            # Skip if target below floor
            if target_price < MIN_TARGET_PRICE_USD:
                continue

            # Keep best match (highest discount)
            existing = best_matches.get(detail_id)
            if existing is None or rule.discount_usd > existing["discount_usd"]:
                best_matches[detail_id] = {
                    "detail_id": detail_id,
                    "hotel_id": opt_hotel_id,
                    "hotel_name": opt_hotel_name,
                    "current_price": opt_price,
                    "target_price": target_price,
                    "discount_usd": rule.discount_usd,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                }

    matches = list(best_matches.values())
    logger.info(
        "override_rules: matched %d options against %d active rules",
        len(matches), len(rules),
    )
    return matches


# ── Execution Logging ────────────────────────────────────────────────

def log_execution(
    rule_id: int,
    rule_name: str,
    detail_id: int,
    hotel_id: int,
    hotel_name: str,
    original_price: float,
    target_price: float,
    discount_usd: float,
    db_write: bool = False,
    zenith_push: bool = False,
) -> int:
    """Log a rule execution to the audit trail.

    Returns the log entry ID.
    """
    init_rules_db()
    now = datetime.utcnow().isoformat(timespec="seconds")

    with _get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO override_rule_log
               (rule_id, rule_name, detail_id, hotel_id, hotel_name,
                original_price, target_price, discount_usd,
                db_write, zenith_push, executed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, rule_name, detail_id, hotel_id, hotel_name,
             original_price, target_price, discount_usd,
             int(db_write), int(zenith_push), now),
        )
        log_id = cursor.lastrowid

        # Update rule stats
        conn.execute(
            """UPDATE override_rules
               SET total_executions = total_executions + 1, last_run_at = ?
               WHERE id = ?""",
            (now, rule_id),
        )

    logger.info(
        "override_rules: logged execution rule=#%d detail=%d price=$%.2f→$%.2f",
        rule_id, detail_id, original_price, target_price,
    )
    return log_id


def get_execution_log(
    rule_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Read execution log entries, optionally filtered by rule_id."""
    init_rules_db()
    with _get_db() as conn:
        if rule_id is not None:
            rows = conn.execute(
                """SELECT * FROM override_rule_log
                   WHERE rule_id = ?
                   ORDER BY executed_at DESC LIMIT ?""",
                (rule_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM override_rule_log
                   ORDER BY executed_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()

    return [dict(r) for r in rows]
