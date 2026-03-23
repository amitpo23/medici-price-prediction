# Override Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build persistent override rules that auto-execute after every scan cycle — replacing one-time overrides with always-on trading strategies.

**Architecture:** SQLite `override_rules` table stores active rules (signal, hotel, category, board, T-range, discount). After each collection cycle (`_run_collection_cycle`), the system matches rules against current PUT signals and executes overrides (DB write + Zenith push). Rules can be created, paused, and deleted via API. Command Center shows active rules and their execution history.

**Tech Stack:** SQLite, FastAPI, existing Zenith SOAP push logic, existing `_run_collection_cycle` hook.

---

## File Structure

### New Files
- `src/analytics/override_rules.py` — Rule engine: CRUD, matching, execution
- `tests/unit/test_override_rules.py` — Unit tests

### Modified Files
- `src/api/routers/analytics_router.py` — 4 new endpoints (CRUD + trigger)
- `src/api/routers/_shared_state.py:202-250` — Hook into collection cycle
- `src/templates/command_center.html` — Rules panel in right column

---

## Task 1: Override Rules SQLite Engine

**Files:**
- Create: `src/analytics/override_rules.py`
- Test: `tests/unit/test_override_rules.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/test_override_rules.py
"""Tests for override rules engine."""
import os
import tempfile
import pytest
from src.analytics.override_rules import (
    OverrideRule, init_rules_db, create_rule, get_rules,
    get_rule, pause_rule, resume_rule, delete_rule,
    match_rules, RuleValidationError,
)

@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "test_rules.db"
    monkeypatch.setattr("src.analytics.override_rules.DB_PATH", db)
    init_rules_db()
    yield db

class TestRuleCRUD:
    def test_create_rule_minimal(self):
        rule = create_rule(signal="PUT", discount_usd=1.0, name="Test PUT rule")
        assert rule.id is not None
        assert rule.signal == "PUT"
        assert rule.discount_usd == 1.0
        assert rule.is_active is True

    def test_create_rule_with_hotel(self):
        rule = create_rule(signal="PUT", discount_usd=2.0, name="Breakwater PUTs", hotel_id=66814)
        assert rule.hotel_id == 66814

    def test_create_rule_full_filters(self):
        rule = create_rule(
            signal="PUT", discount_usd=1.5, name="Targeted rule",
            hotel_id=66814, category="standard", board="ro",
            min_T=14, max_T=90,
        )
        assert rule.category == "standard"
        assert rule.board == "ro"
        assert rule.min_T == 14
        assert rule.max_T == 90

    def test_create_rule_invalid_signal(self):
        with pytest.raises(RuleValidationError, match="signal"):
            create_rule(signal="CALL", discount_usd=1.0, name="Bad")

    def test_create_rule_invalid_discount(self):
        with pytest.raises(RuleValidationError, match="discount"):
            create_rule(signal="PUT", discount_usd=15.0, name="Bad")

    def test_create_rule_zero_discount(self):
        with pytest.raises(RuleValidationError, match="discount"):
            create_rule(signal="PUT", discount_usd=0, name="Bad")

    def test_get_rules(self):
        create_rule(signal="PUT", discount_usd=1.0, name="Rule A")
        create_rule(signal="PUT", discount_usd=2.0, name="Rule B")
        rules = get_rules()
        assert len(rules) == 2

    def test_get_rules_active_only(self):
        r = create_rule(signal="PUT", discount_usd=1.0, name="Rule A")
        create_rule(signal="PUT", discount_usd=2.0, name="Rule B")
        pause_rule(r.id)
        active = get_rules(active_only=True)
        assert len(active) == 1

    def test_get_single_rule(self):
        r = create_rule(signal="PUT", discount_usd=1.0, name="Rule A")
        fetched = get_rule(r.id)
        assert fetched.name == "Rule A"

    def test_pause_resume(self):
        r = create_rule(signal="PUT", discount_usd=1.0, name="Rule A")
        pause_rule(r.id)
        assert get_rule(r.id).is_active is False
        resume_rule(r.id)
        assert get_rule(r.id).is_active is True

    def test_delete_rule(self):
        r = create_rule(signal="PUT", discount_usd=1.0, name="Rule A")
        delete_rule(r.id)
        assert get_rule(r.id) is None

class TestRuleMatching:
    def test_match_all_puts(self):
        create_rule(signal="PUT", discount_usd=1.0, name="All PUTs")
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
            {"detail_id": 2, "option_signal": "CALL", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
            {"detail_id": 3, "option_signal": "PUT", "hotel_id": 200, "current_price": 150, "days_to_checkin": 60, "category": "deluxe", "board": "bb"},
        ]
        matches = match_rules(options)
        assert len(matches) == 2
        assert all(m["detail_id"] in (1, 3) for m in matches)

    def test_match_hotel_filter(self):
        create_rule(signal="PUT", discount_usd=1.0, name="Hotel 100 only", hotel_id=100)
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
            {"detail_id": 2, "option_signal": "PUT", "hotel_id": 200, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 1

    def test_match_category_board(self):
        create_rule(signal="PUT", discount_usd=1.0, name="Std RO", category="standard", board="ro")
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
            {"detail_id": 2, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "deluxe", "board": "ro"},
            {"detail_id": 3, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "bb"},
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 1

    def test_match_t_range(self):
        create_rule(signal="PUT", discount_usd=1.0, name="T 30-90", min_T=30, max_T=90)
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 10, "category": "standard", "board": "ro"},
            {"detail_id": 2, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 45, "category": "standard", "board": "ro"},
            {"detail_id": 3, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 120, "category": "standard", "board": "ro"},
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 2

    def test_match_target_below_50_skipped(self):
        create_rule(signal="PUT", discount_usd=5.0, name="Big discount")
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 52, "days_to_checkin": 30, "category": "standard", "board": "ro"},
            {"detail_id": 2, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
        ]
        matches = match_rules(options)
        # detail 1: $52 - $5 = $47 < $50 → skipped
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 2

    def test_match_multiple_rules_best_discount(self):
        create_rule(signal="PUT", discount_usd=1.0, name="All PUTs -$1")
        create_rule(signal="PUT", discount_usd=3.0, name="Breakwater -$3", hotel_id=100)
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
        ]
        matches = match_rules(options)
        # Should use the higher discount ($3) when multiple rules match
        assert len(matches) == 1
        assert matches[0]["discount_usd"] == 3.0

    def test_no_match_paused_rule(self):
        r = create_rule(signal="PUT", discount_usd=1.0, name="Paused")
        pause_rule(r.id)
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
        ]
        matches = match_rules(options)
        assert len(matches) == 0

    def test_execution_log(self):
        create_rule(signal="PUT", discount_usd=1.0, name="Test")
        options = [
            {"detail_id": 1, "option_signal": "PUT", "hotel_id": 100, "current_price": 200, "days_to_checkin": 30, "category": "standard", "board": "ro"},
        ]
        matches = match_rules(options)
        assert matches[0]["rule_id"] is not None
        assert matches[0]["rule_name"] == "Test"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/unit/test_override_rules.py -v`
Expected: ImportError — module not found

- [ ] **Step 3: Implement override_rules.py**

```python
# src/analytics/override_rules.py
"""Override Rules Engine — persistent trading rules that auto-execute after scans.

Instead of one-time overrides, operators define rules like:
  "All PUT signals at Breakwater → override -$1"
  "All PUT signals, Standard RO, T=30-90 → override -$2"

Rules are checked after every collection cycle. Matching options get
overridden automatically (DB write + Zenith push).

Architecture:
    SQLite override_rules.db — stores rules + execution log
    _run_collection_cycle() → calls apply_override_rules()
    apply_override_rules() → matches rules → executes overrides
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Guardrails ──────────────────────────────────────────────────────────
MAX_DISCOUNT_USD = 10.0
MIN_TARGET_PRICE_USD = 50.0
ALLOWED_SIGNALS = ("PUT", "STRONG_PUT")
MAX_RULES = 50  # Max active rules at once

# ── DB Path ─────────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DB_DIR / "override_rules.db"


class RuleValidationError(Exception):
    pass


@dataclass
class OverrideRule:
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


@contextmanager
def _db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_rules_db():
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS override_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                signal TEXT NOT NULL DEFAULT 'PUT',
                hotel_id INTEGER,
                category TEXT,
                board TEXT,
                min_T INTEGER DEFAULT 7,
                max_T INTEGER DEFAULT 120,
                discount_usd REAL NOT NULL DEFAULT 1.0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_run_at TEXT,
                total_executions INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS override_rule_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                rule_name TEXT,
                detail_id INTEGER NOT NULL,
                hotel_id INTEGER,
                hotel_name TEXT,
                original_price REAL,
                target_price REAL,
                discount_usd REAL,
                db_write TEXT,
                zenith_push TEXT,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (rule_id) REFERENCES override_rules(id)
            )
        """)


def _validate_rule(signal: str, discount_usd: float):
    if signal not in ALLOWED_SIGNALS:
        raise RuleValidationError(f"signal must be PUT or STRONG_PUT, got: {signal}")
    if discount_usd <= 0 or discount_usd > MAX_DISCOUNT_USD:
        raise RuleValidationError(f"discount must be $0.01-${MAX_DISCOUNT_USD}, got: ${discount_usd}")


def create_rule(
    signal: str, discount_usd: float, name: str,
    hotel_id: int | None = None, category: str | None = None,
    board: str | None = None, min_T: int = 7, max_T: int = 120,
) -> OverrideRule:
    _validate_rule(signal, discount_usd)
    now = datetime.utcnow().isoformat()

    with _db() as conn:
        # Check max rules
        count = conn.execute("SELECT COUNT(*) FROM override_rules WHERE is_active=1").fetchone()[0]
        if count >= MAX_RULES:
            raise RuleValidationError(f"Max {MAX_RULES} active rules reached")

        cur = conn.execute("""
            INSERT INTO override_rules (name, signal, hotel_id, category, board, min_T, max_T, discount_usd, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (name, signal, hotel_id, category, board, min_T, max_T, discount_usd, now))

        return OverrideRule(
            id=cur.lastrowid, name=name, signal=signal, hotel_id=hotel_id,
            category=category, board=board, min_T=min_T, max_T=max_T,
            discount_usd=discount_usd, is_active=True, created_at=now,
        )


def get_rules(active_only: bool = False) -> list[OverrideRule]:
    with _db() as conn:
        sql = "SELECT * FROM override_rules"
        if active_only:
            sql += " WHERE is_active=1"
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql).fetchall()
        return [OverrideRule(**{k: row[k] for k in row.keys()}) for row in rows]


def get_rule(rule_id: int) -> OverrideRule | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM override_rules WHERE id=?", (rule_id,)).fetchone()
        if not row:
            return None
        return OverrideRule(**{k: row[k] for k in row.keys()})


def pause_rule(rule_id: int):
    with _db() as conn:
        conn.execute("UPDATE override_rules SET is_active=0 WHERE id=?", (rule_id,))


def resume_rule(rule_id: int):
    with _db() as conn:
        conn.execute("UPDATE override_rules SET is_active=1 WHERE id=?", (rule_id,))


def delete_rule(rule_id: int):
    with _db() as conn:
        conn.execute("DELETE FROM override_rules WHERE id=?", (rule_id,))


def match_rules(options: list[dict]) -> list[dict]:
    """Match active rules against current options. Returns list of overrides to execute.

    Each option can match multiple rules — the highest discount wins.
    """
    rules = get_rules(active_only=True)
    if not rules:
        return []

    matched = {}  # detail_id → best match

    for opt in options:
        sig = opt.get("option_signal", "")
        hid = int(opt.get("hotel_id", 0) or 0)
        cat = (opt.get("category", "") or "").lower()
        brd = (opt.get("board", "") or "").lower()
        t = int(opt.get("days_to_checkin", 0) or 0)
        cp = float(opt.get("current_price", 0) or 0)
        did = int(opt.get("detail_id", 0))

        for rule in rules:
            # Signal match
            if sig not in (rule.signal, f"STRONG_{rule.signal}"):
                continue
            # Hotel filter
            if rule.hotel_id and hid != rule.hotel_id:
                continue
            # Category filter
            if rule.category and cat != rule.category.lower():
                continue
            # Board filter
            if rule.board and brd != rule.board.lower():
                continue
            # T range
            if t < rule.min_T or t > rule.max_T:
                continue
            # Target price check
            target = round(cp - rule.discount_usd, 2)
            if target < MIN_TARGET_PRICE_USD:
                continue

            # Best discount wins
            if did not in matched or rule.discount_usd > matched[did]["discount_usd"]:
                matched[did] = {
                    "detail_id": did,
                    "hotel_id": hid,
                    "hotel_name": opt.get("hotel_name", ""),
                    "current_price": cp,
                    "target_price": target,
                    "discount_usd": rule.discount_usd,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                }

    return list(matched.values())


def log_execution(rule_id: int, rule_name: str, detail_id: int,
                  hotel_id: int, hotel_name: str,
                  original_price: float, target_price: float,
                  discount_usd: float, db_write: str, zenith_push: str):
    with _db() as conn:
        conn.execute("""
            INSERT INTO override_rule_log
            (rule_id, rule_name, detail_id, hotel_id, hotel_name,
             original_price, target_price, discount_usd, db_write, zenith_push, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, rule_name, detail_id, hotel_id, hotel_name,
              original_price, target_price, discount_usd, db_write, zenith_push,
              datetime.utcnow().isoformat()))

        conn.execute("""
            UPDATE override_rules
            SET last_run_at=?, total_executions=total_executions+1
            WHERE id=?
        """, (datetime.utcnow().isoformat(), rule_id))


def get_execution_log(rule_id: int | None = None, limit: int = 50) -> list[dict]:
    with _db() as conn:
        if rule_id:
            rows = conn.execute(
                "SELECT * FROM override_rule_log WHERE rule_id=? ORDER BY executed_at DESC LIMIT ?",
                (rule_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM override_rule_log ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/unit/test_override_rules.py -v`
Expected: All 14 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/analytics/override_rules.py tests/unit/test_override_rules.py
git commit -m "feat: override rules engine with SQLite storage, matching, and execution log"
```

---

## Task 2: API Endpoints for Rules CRUD

**Files:**
- Modify: `src/api/routers/analytics_router.py`

- [ ] **Step 1: Add 6 endpoints**

After the `/override/audit` endpoint, add:

```
POST   /override/rules          — Create a new rule
GET    /override/rules          — List all rules
GET    /override/rules/{id}     — Get single rule + execution log
PUT    /override/rules/{id}     — Pause/resume rule
DELETE /override/rules/{id}     — Delete rule
POST   /override/rules/trigger  — Manual trigger: run all active rules now
```

Each endpoint calls the corresponding function from `override_rules.py`.

- [ ] **Step 2: Verify syntax**

Run: `python3 -m py_compile src/api/routers/analytics_router.py`

- [ ] **Step 3: Commit**

```bash
git add src/api/routers/analytics_router.py
git commit -m "feat: API endpoints for override rules CRUD + manual trigger"
```

---

## Task 3: Hook into Collection Cycle

**Files:**
- Modify: `src/api/routers/_shared_state.py:243`

- [ ] **Step 1: Add auto-execution after scan**

After `_persist_salesoffice_state()` (line 243), add:

```python
    # Auto-execute override rules after fresh scan
    try:
        from src.analytics.override_rules import init_rules_db, get_rules, match_rules
        init_rules_db()
        active_rules = get_rules(active_only=True)
        if active_rules:
            # Get fresh options
            options_payload = _get_or_build_options_base_payload(
                analysis, t_days=None, include_chart=False, profile="lite",
                source=None, source_only=False,
            )
            options = options_payload.get("rows", []) if isinstance(options_payload, dict) else []
            if options:
                matches = match_rules(options)
                if matches:
                    from src.analytics.override_rules import _execute_matched_overrides
                    result = _execute_matched_overrides(matches)
                    logger.info(
                        "Override rules: %d rules, %d matches, %d pushed, %d failed",
                        len(active_rules), len(matches),
                        result.get("success", 0), result.get("failed", 0),
                    )
    except Exception as exc:
        logger.warning("Override rules auto-execution failed: %s", exc)
```

- [ ] **Step 2: Add `_execute_matched_overrides` function to override_rules.py**

This function takes the matched overrides, connects to Azure SQL, writes PriceOverride, and pushes to Zenith. Same logic as `/override/execute-bulk` but called internally.

- [ ] **Step 3: Commit**

```bash
git add src/api/routers/_shared_state.py src/analytics/override_rules.py
git commit -m "feat: auto-execute override rules after each collection cycle"
```

---

## Task 4: Command Center — Rules Panel

**Files:**
- Modify: `src/templates/command_center.html`

- [ ] **Step 1: Add Rules section in right column**

Between Override History and Queue Sidebar, add:

```html
<!-- Override Rules -->
<div class="section" id="panel-rules">
  <div class="section-title">Override Rules</div>
  <div id="rules-body" class="empty">No active rules</div>
  <div style="margin-top:4px">
    <button class="btn btn-put btn-sm" id="btn-add-rule" onclick="showAddRule()">+ Add Rule</button>
    <button class="btn btn-sm" style="background:var(--muted)" id="btn-trigger-rules" onclick="triggerRules()">Run Now</button>
  </div>
</div>
```

- [ ] **Step 2: Add JS functions for rules management**

Functions: `loadRules()`, `showAddRule()`, `createRule()`, `toggleRule()`, `deleteRule()`, `triggerRules()`.

- [ ] **Step 3: Commit**

```bash
git add src/templates/command_center.html
git commit -m "feat: override rules panel in Command Center"
```

---

## Task 5: Integration Test + Deploy

- [ ] **Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v --tb=short --ignore=tests/unit/test_collectors.py`
Expected: All pass

- [ ] **Step 2: Deploy**

Run: `python3 build_deploy.py --deploy`

- [ ] **Step 3: Verify**

```bash
# Create a rule
curl -X POST ".../override/rules" -H "Content-Type: application/json" \
  -d '{"name":"Breakwater PUTs -$1","signal":"PUT","hotel_id":66814,"discount_usd":1.0}'

# List rules
curl ".../override/rules"

# Trigger manually
curl -X POST ".../override/rules/trigger"

# Check execution log
curl ".../override/rules/1"
```

- [ ] **Step 4: Commit any fixes**

---

## Verification Checklist

- [ ] Rules persist across restarts (SQLite)
- [ ] Rules auto-execute after collection cycle
- [ ] Only PUT/STRONG_PUT signals match
- [ ] Hotel/category/board/T filters work correctly
- [ ] Target price < $50 is skipped
- [ ] Discount > $10 is rejected
- [ ] Max 50 active rules
- [ ] `OVERRIDE_PUSH_ENABLED` still controls Zenith push
- [ ] Paused rules don't match
- [ ] Deleted rules don't match
- [ ] Execution log tracks every override with rule_id
- [ ] Command Center shows active rules
- [ ] Multiple rules → highest discount wins
