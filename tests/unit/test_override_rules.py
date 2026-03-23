"""Tests for the override rules engine — persistent rules that auto-match options."""
from unittest.mock import patch

import pytest

from src.analytics.override_rules import (
    OverrideRule,
    RuleValidationError,
    create_rule,
    get_rules,
    get_rule,
    pause_rule,
    resume_rule,
    delete_rule,
    match_rules,
    log_execution,
    get_execution_log,
    init_rules_db,
    ALLOWED_SIGNALS,
    MAX_DISCOUNT_USD,
    MIN_TARGET_PRICE_USD,
    MAX_RULES,
    DB_PATH,
)


# ── Test with temp DB ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Redirect override rules to a temp database for each test."""
    temp_db = tmp_path / "test_override_rules.db"
    with patch("src.analytics.override_rules.DB_PATH", temp_db):
        yield temp_db


# ── Helpers ──────────────────────────────────────────────────────────

def _make_option(
    detail_id: int = 1001,
    option_signal: str = "PUT",
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
        rule = create_rule(signal="PUT", discount_usd=2.0)
        assert rule.id is not None
        assert rule.signal == "PUT"
        assert rule.discount_usd == 2.0
        assert rule.is_active is True
        assert rule.hotel_id is None
        assert rule.min_T == 7
        assert rule.max_T == 120
        assert rule.total_executions == 0

    def test_create_with_hotel(self):
        """Create rule scoped to a specific hotel."""
        rule = create_rule(signal="PUT", discount_usd=3.0, hotel_id=42, name="Hotel 42 PUT")
        assert rule.hotel_id == 42
        assert rule.name == "Hotel 42 PUT"

    def test_create_full_filters(self):
        """Create rule with all filter fields."""
        rule = create_rule(
            signal="STRONG_PUT",
            discount_usd=5.0,
            name="Full filter rule",
            hotel_id=10,
            category="Deluxe",
            board="HB",
            min_T=14,
            max_T=60,
        )
        assert rule.signal == "STRONG_PUT"
        assert rule.category == "Deluxe"
        assert rule.board == "HB"
        assert rule.min_T == 14
        assert rule.max_T == 60

    def test_reject_invalid_signal(self):
        """CALL signal is not allowed for override rules."""
        with pytest.raises(RuleValidationError, match="Signal"):
            create_rule(signal="CALL", discount_usd=1.0)

    def test_reject_invalid_discount(self):
        """Discount exceeding MAX_DISCOUNT_USD is rejected."""
        with pytest.raises(RuleValidationError, match="maximum"):
            create_rule(signal="PUT", discount_usd=15.0)

    def test_reject_zero_discount(self):
        """Zero discount is rejected."""
        with pytest.raises(RuleValidationError, match="positive"):
            create_rule(signal="PUT", discount_usd=0)


class TestGetRules:
    def test_get_rules_returns_all(self):
        """get_rules() returns all rules including paused ones."""
        create_rule(signal="PUT", discount_usd=1.0, name="r1")
        r2 = create_rule(signal="PUT", discount_usd=2.0, name="r2")
        pause_rule(r2.id)

        rules = get_rules(active_only=False)
        assert len(rules) == 2

    def test_get_rules_active_only(self):
        """get_rules(active_only=True) excludes paused rules."""
        create_rule(signal="PUT", discount_usd=1.0, name="active")
        r2 = create_rule(signal="PUT", discount_usd=2.0, name="paused")
        pause_rule(r2.id)

        rules = get_rules(active_only=True)
        assert len(rules) == 1
        assert rules[0].name == "active"

    def test_get_single_rule(self):
        """get_rule() returns a single rule by ID."""
        created = create_rule(signal="PUT", discount_usd=4.0, name="lookup")
        fetched = get_rule(created.id)
        assert fetched is not None
        assert fetched.name == "lookup"
        assert fetched.discount_usd == 4.0

    def test_get_nonexistent_rule(self):
        """get_rule() returns None for missing ID."""
        assert get_rule(9999) is None


class TestPauseResumeDelete:
    def test_pause_and_resume(self):
        """Pausing deactivates, resuming reactivates."""
        rule = create_rule(signal="PUT", discount_usd=1.0)
        assert pause_rule(rule.id) is True

        fetched = get_rule(rule.id)
        assert fetched.is_active is False

        assert resume_rule(rule.id) is True
        fetched = get_rule(rule.id)
        assert fetched.is_active is True

    def test_delete_rule(self):
        """Deleted rule is gone."""
        rule = create_rule(signal="PUT", discount_usd=1.0)
        assert delete_rule(rule.id) is True
        assert get_rule(rule.id) is None


# ── Matching Tests ───────────────────────────────────────────────────

class TestMatchRules:
    def test_match_all_puts(self):
        """Rule matching PUT signal matches PUT options."""
        create_rule(signal="PUT", discount_usd=3.0, name="all PUTs")
        options = [
            _make_option(detail_id=1, option_signal="PUT"),
            _make_option(detail_id=2, option_signal="CALL"),  # should not match
            _make_option(detail_id=3, option_signal="PUT"),
        ]
        matches = match_rules(options)
        assert len(matches) == 2
        matched_ids = {m["detail_id"] for m in matches}
        assert matched_ids == {1, 3}

    def test_match_hotel_filter(self):
        """Rule with hotel_id only matches that hotel."""
        create_rule(signal="PUT", discount_usd=2.0, hotel_id=10)
        options = [
            _make_option(detail_id=1, hotel_id=10, option_signal="PUT"),
            _make_option(detail_id=2, hotel_id=20, option_signal="PUT"),
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["hotel_id"] == 10

    def test_match_category_and_board(self):
        """Rule with category+board filters correctly."""
        create_rule(signal="PUT", discount_usd=2.0, category="Deluxe", board="HB")
        options = [
            _make_option(detail_id=1, category="Deluxe", board="HB", option_signal="PUT"),
            _make_option(detail_id=2, category="Standard", board="HB", option_signal="PUT"),
            _make_option(detail_id=3, category="Deluxe", board="BB", option_signal="PUT"),
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 1

    def test_match_T_range(self):
        """Rule T range filters correctly."""
        create_rule(signal="PUT", discount_usd=2.0, min_T=10, max_T=30)
        options = [
            _make_option(detail_id=1, days_to_checkin=5, option_signal="PUT"),   # too soon
            _make_option(detail_id=2, days_to_checkin=15, option_signal="PUT"),  # in range
            _make_option(detail_id=3, days_to_checkin=60, option_signal="PUT"),  # too far
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 2

    def test_skip_target_below_floor(self):
        """Options where target_price < $50 are skipped."""
        create_rule(signal="PUT", discount_usd=5.0)
        options = [
            _make_option(detail_id=1, current_price=52.0, option_signal="PUT"),  # 52-5=47 < 50
            _make_option(detail_id=2, current_price=200.0, option_signal="PUT"),  # 200-5=195 OK
        ]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["detail_id"] == 2
        assert matches[0]["target_price"] == 195.0

    def test_multiple_rules_best_discount_wins(self):
        """When multiple rules match, highest discount wins."""
        create_rule(signal="PUT", discount_usd=2.0, name="small")
        create_rule(signal="PUT", discount_usd=5.0, name="big")
        options = [_make_option(detail_id=1, option_signal="PUT")]
        matches = match_rules(options)
        assert len(matches) == 1
        assert matches[0]["discount_usd"] == 5.0
        assert matches[0]["rule_name"] == "big"

    def test_paused_rule_no_match(self):
        """Paused rules do not match any options."""
        rule = create_rule(signal="PUT", discount_usd=3.0)
        pause_rule(rule.id)
        options = [_make_option(detail_id=1, option_signal="PUT")]
        matches = match_rules(options)
        assert len(matches) == 0


# ── Execution Log Tests ──────────────────────────────────────────────

class TestExecutionLog:
    def test_log_execution_has_rule_id(self):
        """Execution log entries reference the rule and contain all fields."""
        rule = create_rule(signal="PUT", discount_usd=3.0, name="test rule")
        log_id = log_execution(
            rule_id=rule.id,
            rule_name=rule.name,
            detail_id=1001,
            hotel_id=10,
            hotel_name="Test Hotel",
            original_price=200.0,
            target_price=197.0,
            discount_usd=3.0,
            db_write=True,
            zenith_push=True,
        )
        assert log_id is not None

        logs = get_execution_log(rule_id=rule.id)
        assert len(logs) == 1
        entry = logs[0]
        assert entry["rule_id"] == rule.id
        assert entry["rule_name"] == "test rule"
        assert entry["detail_id"] == 1001
        assert entry["original_price"] == 200.0
        assert entry["target_price"] == 197.0
        assert entry["db_write"] == 1
        assert entry["zenith_push"] == 1

        # Rule stats should be updated
        updated_rule = get_rule(rule.id)
        assert updated_rule.total_executions == 1
        assert updated_rule.last_run_at is not None
