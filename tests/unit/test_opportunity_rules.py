"""Tests for the opportunity rules engine — persistent CALL rules that auto-match options."""
from unittest.mock import patch

import pytest

from src.analytics.opportunity_rules import (
    OpportunityRule,
    OppRuleValidationError,
    create_opp_rule,
    get_opp_rules,
    get_opp_rule,
    pause_opp_rule,
    resume_opp_rule,
    delete_opp_rule,
    match_opp_rules,
    log_opp_execution,
    get_opp_execution_log,
    get_daily_spend,
    init_opp_rules_db,
    ALLOWED_SIGNALS,
    MIN_MARGIN_PCT,
    MAX_RULES,
    DB_PATH,
)


# ── Test with temp DB ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Redirect opportunity rules to a temp database for each test."""
    temp_db = tmp_path / "test_opportunity_rules.db"
    with patch("src.analytics.opportunity_rules.DB_PATH", temp_db):
        yield temp_db


# ── Helpers ──────────────────────────────────────────────────────────

def _make_option(
    detail_id: int = 1001,
    option_signal: str = "CALL",
    hotel_id: int = 10,
    hotel_name: str = "Test Hotel",
    current_price: float = 200.0,
    days_to_checkin: int = 30,
    category: str = "Standard",
    board: str = "BB",
) -> dict:
    return {
        "detail_id": detail_id,
        "option_signal": option_signal,
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "current_price": current_price,
        "days_to_checkin": days_to_checkin,
        "category": category,
        "board": board,
    }


# ── CRUD Tests ───────────────────────────────────────────────────────

class TestCreateRule:
    def test_create_minimal(self):
        """Create rule with only required fields."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0)
        assert rule.id is not None
        assert rule.signal == "CALL"
        assert rule.push_markup_pct == 30.0
        assert rule.is_active is True
        assert rule.hotel_id is None
        assert rule.min_T == 7
        assert rule.max_T == 120
        assert rule.total_executions == 0

    def test_create_with_hotel(self):
        """Create rule scoped to a specific hotel."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=40.0, hotel_id=42, name="Hotel 42 CALL")
        assert rule.hotel_id == 42
        assert rule.name == "Hotel 42 CALL"

    def test_create_full_filters(self):
        """Create rule with all filter fields."""
        rule = create_opp_rule(
            signal="STRONG_CALL",
            push_markup_pct=50.0,
            name="Full filter rule",
            hotel_id=10,
            category="Deluxe",
            board="HB",
            min_T=14,
            max_T=60,
        )
        assert rule.signal == "STRONG_CALL"
        assert rule.category == "Deluxe"
        assert rule.board == "HB"
        assert rule.min_T == 14
        assert rule.max_T == 60

    def test_reject_put_signal(self):
        """PUT signal is not allowed for opportunity rules."""
        with pytest.raises(OppRuleValidationError, match="Signal"):
            create_opp_rule(signal="PUT", push_markup_pct=30.0)

    def test_reject_strong_put_signal(self):
        """STRONG_PUT signal is not allowed for opportunity rules."""
        with pytest.raises(OppRuleValidationError, match="Signal"):
            create_opp_rule(signal="STRONG_PUT", push_markup_pct=30.0)

    def test_reject_margin_below_minimum(self):
        """Markup below MIN_MARGIN_PCT (30%) is rejected."""
        with pytest.raises(OppRuleValidationError, match="minimum"):
            create_opp_rule(signal="CALL", push_markup_pct=20.0)

    def test_reject_zero_margin(self):
        """Zero markup is rejected (both below minimum and non-positive)."""
        with pytest.raises(OppRuleValidationError):
            create_opp_rule(signal="CALL", push_markup_pct=0)

    def test_accept_strong_call(self):
        """STRONG_CALL is an accepted signal."""
        rule = create_opp_rule(signal="STRONG_CALL", push_markup_pct=35.0)
        assert rule.signal == "STRONG_CALL"


class TestGetRules:
    def test_get_rules_returns_all(self):
        """get_opp_rules() returns all rules including paused ones."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, name="r1")
        r2 = create_opp_rule(signal="CALL", push_markup_pct=40.0, name="r2")
        pause_opp_rule(r2.id)

        rules = get_opp_rules(active_only=False)
        assert len(rules) == 2

    def test_get_rules_active_only(self):
        """get_opp_rules(active_only=True) excludes paused rules."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, name="active")
        r2 = create_opp_rule(signal="CALL", push_markup_pct=40.0, name="paused")
        pause_opp_rule(r2.id)

        rules = get_opp_rules(active_only=True)
        assert len(rules) == 1
        assert rules[0].name == "active"

    def test_get_single_rule(self):
        """get_opp_rule() returns a single rule by ID."""
        created = create_opp_rule(signal="CALL", push_markup_pct=45.0, name="lookup")
        fetched = get_opp_rule(created.id)
        assert fetched is not None
        assert fetched.name == "lookup"
        assert fetched.push_markup_pct == 45.0

    def test_get_nonexistent_rule(self):
        """get_opp_rule() returns None for missing ID."""
        assert get_opp_rule(9999) is None


class TestPauseResumeDelete:
    def test_pause_and_resume(self):
        """Pausing deactivates, resuming reactivates."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0)
        assert pause_opp_rule(rule.id) is True

        fetched = get_opp_rule(rule.id)
        assert fetched.is_active is False

        assert resume_opp_rule(rule.id) is True
        fetched = get_opp_rule(rule.id)
        assert fetched.is_active is True

    def test_delete_rule(self):
        """Deleted rule is gone."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0)
        assert delete_opp_rule(rule.id) is True
        assert get_opp_rule(rule.id) is None


# ── Matching Tests ───────────────────────────────────────────────────

class TestMatchRules:
    def test_match_all_calls(self):
        """Rule matching CALL signal matches CALL options."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, name="all CALLs")
        options = [
            _make_option(detail_id=1, option_signal="CALL"),
            _make_option(detail_id=2, option_signal="PUT"),     # should not match
            _make_option(detail_id=3, option_signal="CALL"),
        ]
        matches = match_opp_rules(options)
        assert len(matches) == 2
        matched_ids = {m["detail_id"] for m in matches}
        assert matched_ids == {1, 3}

    def test_match_hotel_filter(self):
        """Rule with hotel_id only matches that hotel."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, hotel_id=10)
        options = [
            _make_option(detail_id=1, hotel_id=10, option_signal="CALL"),
            _make_option(detail_id=2, hotel_id=20, option_signal="CALL"),
        ]
        matches = match_opp_rules(options)
        assert len(matches) == 1
        assert matches[0]["hotel_id"] == 10

    def test_match_category_and_board(self):
        """Rule with category+board filters correctly."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, category="Deluxe", board="HB")
        options = [
            _make_option(detail_id=1, category="Deluxe", board="HB", option_signal="CALL"),
            _make_option(detail_id=2, category="Standard", board="HB", option_signal="CALL"),
            _make_option(detail_id=3, category="Deluxe", board="BB", option_signal="CALL"),
        ]
        matches = match_opp_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 1

    def test_match_T_range(self):
        """Rule T range filters correctly."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, min_T=10, max_T=30)
        options = [
            _make_option(detail_id=1, days_to_checkin=5, option_signal="CALL"),   # too soon
            _make_option(detail_id=2, days_to_checkin=15, option_signal="CALL"),  # in range
            _make_option(detail_id=3, days_to_checkin=60, option_signal="CALL"),  # too far
        ]
        matches = match_opp_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 2

    def test_paused_rule_no_match(self):
        """Paused rules do not match any options."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0)
        pause_opp_rule(rule.id)
        options = [_make_option(detail_id=1, option_signal="CALL")]
        matches = match_opp_rules(options)
        assert len(matches) == 0

    def test_push_price_calculation(self):
        """Push price = buy_price * (1 + markup/100)."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, name="30% markup")
        options = [_make_option(detail_id=1, current_price=100.0, option_signal="CALL")]
        matches = match_opp_rules(options)
        assert len(matches) == 1
        assert matches[0]["buy_price"] == 100.0
        assert matches[0]["push_price"] == 130.0
        assert matches[0]["profit_usd"] == 30.0

    def test_multiple_rules_highest_margin_wins(self):
        """When multiple rules match, highest profit wins."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0, name="small")
        create_opp_rule(signal="CALL", push_markup_pct=50.0, name="big")
        options = [_make_option(detail_id=1, current_price=100.0, option_signal="CALL")]
        matches = match_opp_rules(options)
        assert len(matches) == 1
        assert matches[0]["push_price"] == 150.0
        assert matches[0]["rule_name"] == "big"

    def test_zero_price_option_skipped(self):
        """Options with zero or negative price are skipped."""
        create_opp_rule(signal="CALL", push_markup_pct=30.0)
        options = [
            _make_option(detail_id=1, current_price=0, option_signal="CALL"),
            _make_option(detail_id=2, current_price=-10, option_signal="CALL"),
        ]
        matches = match_opp_rules(options)
        assert len(matches) == 0


# ── Daily Budget Tests ───────────────────────────────────────────────

class TestDailySpend:
    def test_initial_spend_is_zero(self):
        """No log entries means daily spend is 0."""
        assert get_daily_spend() == 0.0

    def test_spend_tracks_logged_executions(self):
        """Spend accumulates from logged executions with db_write=True."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0, name="budget test")
        log_opp_execution(
            rule_id=rule.id, rule_name=rule.name, detail_id=1001,
            hotel_id=10, hotel_name="Test", buy_price=100.0, push_price=130.0,
            profit_usd=30.0, opp_id=1, db_write=True,
        )
        log_opp_execution(
            rule_id=rule.id, rule_name=rule.name, detail_id=1002,
            hotel_id=10, hotel_name="Test", buy_price=200.0, push_price=260.0,
            profit_usd=60.0, opp_id=2, db_write=True,
        )
        assert get_daily_spend() == 300.0


# ── Execution Log Tests ──────────────────────────────────────────────

class TestExecutionLog:
    def test_log_execution_has_rule_id(self):
        """Execution log entries reference the rule and contain all fields."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0, name="test rule")
        log_id = log_opp_execution(
            rule_id=rule.id,
            rule_name=rule.name,
            detail_id=1001,
            hotel_id=10,
            hotel_name="Test Hotel",
            buy_price=200.0,
            push_price=260.0,
            profit_usd=60.0,
            opp_id=42,
            db_write=True,
        )
        assert log_id is not None

        logs = get_opp_execution_log(rule_id=rule.id)
        assert len(logs) == 1
        entry = logs[0]
        assert entry["rule_id"] == rule.id
        assert entry["rule_name"] == "test rule"
        assert entry["detail_id"] == 1001
        assert entry["buy_price"] == 200.0
        assert entry["push_price"] == 260.0
        assert entry["profit_usd"] == 60.0
        assert entry["opp_id"] == 42
        assert entry["db_write"] == 1

        # Rule stats should be updated
        updated_rule = get_opp_rule(rule.id)
        assert updated_rule.total_executions == 1
        assert updated_rule.last_run_at is not None

    def test_log_without_db_write(self):
        """Failed execution (db_write=False) is also logged."""
        rule = create_opp_rule(signal="CALL", push_markup_pct=30.0, name="fail test")
        log_opp_execution(
            rule_id=rule.id, rule_name=rule.name, detail_id=2001,
            hotel_id=20, hotel_name="Hotel B", buy_price=150.0,
            push_price=195.0, profit_usd=45.0, opp_id=None, db_write=False,
        )
        logs = get_opp_execution_log(rule_id=rule.id)
        assert len(logs) == 1
        assert logs[0]["db_write"] == 0
        assert logs[0]["opp_id"] is None
