"""Unit tests for group_actions.py — bulk CALL/PUT execution with filtering."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from src.analytics.group_actions import (
    GroupFilter,
    GroupActionResult,
    filter_signals,
    preview_group_action,
    execute_group_override,
    execute_group_opportunity,
    MAX_GROUP_SIZE,
    MIN_T_DAYS,
    _expand_signal,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_signal(
    detail_id=1001,
    hotel_id=100,
    hotel_name="Test Hotel",
    category="standard",
    board="ro",
    recommendation="CALL",
    confidence="High",
    T=15,
    S_t=800.0,
    predicted_price=850.0,
    checkin_date="2026-05-01",
    path_min_price=None,
):
    """Create a synthetic signal dict matching compute_next_day_signals output."""
    return {
        "detail_id": detail_id,
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "category": category,
        "board": board,
        "recommendation": recommendation,
        "confidence": confidence,
        "T": T,
        "S_t": S_t,
        "predicted_price": predicted_price,
        "checkin_date": checkin_date,
        "path_min_price": path_min_price,
    }


def _make_analysis(detail_ids=None):
    """Build a minimal analysis dict."""
    if detail_ids is None:
        detail_ids = [1001]
    return {
        "predictions": {
            str(did): {"detail_id": did, "predicted_checkin_price": 850}
            for did in detail_ids
        }
    }


def _make_signals_batch(n=10, hotel_id=100, recommendation="CALL", T=15):
    """Generate a batch of signals."""
    return [
        _make_signal(
            detail_id=1000 + i,
            hotel_id=hotel_id,
            recommendation=recommendation,
            T=T,
        )
        for i in range(n)
    ]


# ── GroupFilter tests ────────────────────────────────────────────────

class TestGroupFilter:
    def test_default_filter(self):
        gf = GroupFilter()
        assert gf.signal is None
        assert gf.hotel_id is None
        assert gf.describe() == "all"

    def test_describe_signal(self):
        gf = GroupFilter(signal="CALL")
        assert "signal=CALL" in gf.describe()

    def test_describe_hotel(self):
        gf = GroupFilter(hotel_id=100)
        assert "hotel=100" in gf.describe()

    def test_describe_multiple_hotels(self):
        gf = GroupFilter(hotel_ids=[100, 200])
        desc = gf.describe()
        assert "hotels=" in desc

    def test_describe_category(self):
        gf = GroupFilter(category="deluxe")
        assert "category=deluxe" in gf.describe()

    def test_describe_board(self):
        gf = GroupFilter(board="bb")
        assert "board=bb" in gf.describe()

    def test_describe_confidence(self):
        gf = GroupFilter(confidence="High")
        assert "confidence=High" in gf.describe()

    def test_describe_T_range(self):
        gf = GroupFilter(min_T=5, max_T=30)
        assert "T=[5..30]" in gf.describe()

    def test_describe_price_range(self):
        gf = GroupFilter(min_price=100, max_price=500)
        assert "price=[$100.." in gf.describe()

    def test_describe_combined(self):
        gf = GroupFilter(signal="PUT", hotel_id=200, confidence="Med")
        desc = gf.describe()
        assert "signal=PUT" in desc
        assert "hotel=200" in desc
        assert "confidence=Med" in desc


# ── _expand_signal tests ─────────────────────────────────────────────

class TestExpandSignal:
    def test_call(self):
        assert _expand_signal("CALL") == {"CALL", "STRONG_CALL"}

    def test_put(self):
        assert _expand_signal("PUT") == {"PUT", "STRONG_PUT"}

    def test_none(self):
        assert _expand_signal("NONE") == {"NONE"}

    def test_case_insensitive(self):
        assert _expand_signal("call") == {"CALL", "STRONG_CALL"}
        assert _expand_signal("put") == {"PUT", "STRONG_PUT"}

    def test_unknown(self):
        assert _expand_signal("HOLD") == {"HOLD"}


# ── filter_signals tests ─────────────────────────────────────────────

class TestFilterSignals:
    def test_no_filter_returns_all(self):
        signals = [
            _make_signal(detail_id=1, recommendation="CALL", T=10),
            _make_signal(detail_id=2, recommendation="PUT", T=10),
        ]
        gf = GroupFilter()
        result = filter_signals(signals, _make_analysis([1, 2]), gf)
        assert len(result) == 2

    def test_filter_by_signal_call(self):
        signals = [
            _make_signal(detail_id=1, recommendation="CALL"),
            _make_signal(detail_id=2, recommendation="PUT"),
            _make_signal(detail_id=3, recommendation="STRONG_CALL"),
        ]
        gf = GroupFilter(signal="CALL")
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 2
        recs = {s["recommendation"] for s in result}
        assert recs == {"CALL", "STRONG_CALL"}

    def test_filter_by_signal_put(self):
        signals = [
            _make_signal(detail_id=1, recommendation="CALL"),
            _make_signal(detail_id=2, recommendation="PUT"),
            _make_signal(detail_id=3, recommendation="STRONG_PUT"),
        ]
        gf = GroupFilter(signal="PUT")
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 2

    def test_filter_by_hotel_id(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100),
            _make_signal(detail_id=2, hotel_id=200),
            _make_signal(detail_id=3, hotel_id=100),
        ]
        gf = GroupFilter(hotel_id=100)
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 2
        assert all(s["hotel_id"] == 100 for s in result)

    def test_filter_by_hotel_ids(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100),
            _make_signal(detail_id=2, hotel_id=200),
            _make_signal(detail_id=3, hotel_id=300),
        ]
        gf = GroupFilter(hotel_ids=[100, 300])
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 2
        ids = {s["hotel_id"] for s in result}
        assert ids == {100, 300}

    def test_filter_by_category(self):
        signals = [
            _make_signal(detail_id=1, category="standard"),
            _make_signal(detail_id=2, category="deluxe"),
            _make_signal(detail_id=3, category="suite"),
        ]
        gf = GroupFilter(category="deluxe")
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 1
        assert result[0]["category"] == "deluxe"

    def test_filter_by_board(self):
        signals = [
            _make_signal(detail_id=1, board="ro"),
            _make_signal(detail_id=2, board="bb"),
        ]
        gf = GroupFilter(board="bb")
        result = filter_signals(signals, _make_analysis([1, 2]), gf)
        assert len(result) == 1
        assert result[0]["board"] == "bb"

    def test_filter_by_confidence(self):
        signals = [
            _make_signal(detail_id=1, confidence="High"),
            _make_signal(detail_id=2, confidence="Med"),
            _make_signal(detail_id=3, confidence="Low"),
        ]
        gf = GroupFilter(confidence="High")
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 1

    def test_filter_by_T_range(self):
        signals = [
            _make_signal(detail_id=1, T=5),
            _make_signal(detail_id=2, T=15),
            _make_signal(detail_id=3, T=30),
            _make_signal(detail_id=4, T=45),
        ]
        gf = GroupFilter(min_T=10, max_T=35)
        result = filter_signals(signals, _make_analysis([1, 2, 3, 4]), gf)
        assert len(result) == 2
        T_values = {s["T"] for s in result}
        assert T_values == {15, 30}

    def test_filter_by_price_range(self):
        signals = [
            _make_signal(detail_id=1, S_t=100),
            _make_signal(detail_id=2, S_t=500),
            _make_signal(detail_id=3, S_t=1000),
        ]
        gf = GroupFilter(min_price=200, max_price=800)
        result = filter_signals(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result) == 1
        assert result[0]["S_t"] == 500

    def test_min_T_safety_filter(self):
        """Rooms with T < MIN_T_DAYS should always be excluded."""
        signals = [_make_signal(detail_id=1, T=0)]
        gf = GroupFilter()
        result = filter_signals(signals, _make_analysis([1]), gf)
        assert len(result) == 0

    def test_combined_filters(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, recommendation="CALL", confidence="High", T=10),
            _make_signal(detail_id=2, hotel_id=100, recommendation="CALL", confidence="Med", T=10),
            _make_signal(detail_id=3, hotel_id=200, recommendation="CALL", confidence="High", T=10),
            _make_signal(detail_id=4, hotel_id=100, recommendation="PUT", confidence="High", T=10),
        ]
        gf = GroupFilter(signal="CALL", hotel_id=100, confidence="High")
        result = filter_signals(signals, _make_analysis([1, 2, 3, 4]), gf)
        assert len(result) == 1
        assert result[0]["detail_id"] == 1

    def test_empty_signals(self):
        gf = GroupFilter(signal="CALL")
        result = filter_signals([], {}, gf)
        assert result == []

    def test_category_case_insensitive(self):
        signals = [_make_signal(detail_id=1, category="Deluxe")]
        gf = GroupFilter(category="deluxe")
        result = filter_signals(signals, _make_analysis([1]), gf)
        assert len(result) == 1

    def test_confidence_case_insensitive(self):
        signals = [_make_signal(detail_id=1, confidence="high")]
        gf = GroupFilter(confidence="High")
        result = filter_signals(signals, _make_analysis([1]), gf)
        assert len(result) == 1


# ── preview_group_action tests ───────────────────────────────────────

class TestPreviewGroupAction:
    def test_basic_preview(self):
        signals = _make_signals_batch(5, recommendation="CALL")
        gf = GroupFilter(signal="CALL")
        result = preview_group_action(signals, _make_analysis(range(1000, 1005)), gf)
        assert result["total_matched"] == 5
        assert result["exceeds_limit"] is False
        assert len(result["hotel_breakdown"]) >= 1

    def test_preview_empty(self):
        signals = _make_signals_batch(5, recommendation="CALL")
        gf = GroupFilter(signal="PUT")
        result = preview_group_action(signals, _make_analysis(range(1000, 1005)), gf)
        assert result["total_matched"] == 0
        assert result["hotel_breakdown"] == []

    def test_preview_exceeds_limit(self):
        signals = _make_signals_batch(MAX_GROUP_SIZE + 10, recommendation="CALL")
        gf = GroupFilter(signal="CALL")
        analysis = _make_analysis(range(1000, 1000 + MAX_GROUP_SIZE + 10))
        result = preview_group_action(signals, analysis, gf)
        assert result["exceeds_limit"] is True

    def test_preview_hotel_breakdown(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, hotel_name="Hotel A"),
            _make_signal(detail_id=2, hotel_id=100, hotel_name="Hotel A"),
            _make_signal(detail_id=3, hotel_id=200, hotel_name="Hotel B"),
        ]
        gf = GroupFilter()
        result = preview_group_action(signals, _make_analysis([1, 2, 3]), gf)
        assert len(result["hotel_breakdown"]) == 2
        # Sorted by total descending
        assert result["hotel_breakdown"][0]["hotel_name"] == "Hotel A"
        assert result["hotel_breakdown"][0]["total"] == 2

    def test_preview_matched_details_capped(self):
        """Preview should cap matched_details at 50."""
        signals = _make_signals_batch(100, recommendation="CALL")
        gf = GroupFilter(signal="CALL")
        analysis = _make_analysis(range(1000, 1100))
        result = preview_group_action(signals, analysis, gf)
        assert len(result["matched_details"]) <= 50

    def test_preview_total_value(self):
        signals = [
            _make_signal(detail_id=1, S_t=500),
            _make_signal(detail_id=2, S_t=300),
        ]
        gf = GroupFilter()
        result = preview_group_action(signals, _make_analysis([1, 2]), gf)
        assert result["total_value_usd"] == 800.0

    def test_preview_call_put_counts(self):
        signals = [
            _make_signal(detail_id=1, recommendation="CALL"),
            _make_signal(detail_id=2, recommendation="STRONG_CALL"),
            _make_signal(detail_id=3, recommendation="PUT"),
        ]
        gf = GroupFilter()
        result = preview_group_action(signals, _make_analysis([1, 2, 3]), gf)
        hotel = result["hotel_breakdown"][0]
        assert hotel["calls"] == 2
        assert hotel["puts"] == 1


# ── execute_group_override tests ─────────────────────────────────────

class TestExecuteGroupOverride:
    @patch("src.analytics.override_queue.enqueue_override")
    def test_basic_override(self, mock_enqueue):
        """Should queue all PUT signals."""
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, recommendation="PUT"),
            _make_signal(detail_id=2, recommendation="PUT"),
            _make_signal(detail_id=3, recommendation="CALL"),
        ]
        gf = GroupFilter()
        result = execute_group_override(signals, _make_analysis([1, 2, 3]), gf)
        assert result.action == "override"
        assert result.total_queued == 2
        assert result.total_skipped == 0
        assert result.batch_id.startswith("GRP-OVR-")
        assert mock_enqueue.call_count == 2

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_forces_put_filter(self, mock_enqueue):
        """execute_group_override should force signal=PUT regardless of input."""
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, recommendation="CALL"),
            _make_signal(detail_id=2, recommendation="PUT"),
        ]
        gf = GroupFilter(signal="CALL")  # User passed CALL, but override forces PUT
        result = execute_group_override(signals, _make_analysis([1, 2]), gf)
        assert result.total_queued == 1  # Only the PUT signal

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_with_hotel_filter(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, hotel_id=100, recommendation="PUT"),
            _make_signal(detail_id=2, hotel_id=200, recommendation="PUT"),
        ]
        gf = GroupFilter(hotel_id=100)
        result = execute_group_override(signals, _make_analysis([1, 2]), gf)
        assert result.total_queued == 1

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_validation_error_skips(self, mock_enqueue):
        """Rooms that fail validation should be skipped, not crash."""
        from src.analytics.override_queue import OverrideValidationError
        mock_enqueue.side_effect = OverrideValidationError("Price too low")
        signals = [_make_signal(detail_id=1, recommendation="PUT")]
        gf = GroupFilter()
        result = execute_group_override(signals, _make_analysis([1]), gf)
        assert result.total_queued == 0
        assert result.total_skipped == 1
        assert len(result.skipped_reasons) == 1
        assert "Price too low" in result.skipped_reasons[0]

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_exceeds_group_size(self, mock_enqueue):
        """Should reject if matched rooms exceed MAX_GROUP_SIZE."""
        signals = [
            _make_signal(detail_id=i, recommendation="PUT")
            for i in range(MAX_GROUP_SIZE + 10)
        ]
        gf = GroupFilter()
        analysis = _make_analysis(range(MAX_GROUP_SIZE + 10))
        result = execute_group_override(signals, analysis, gf)
        assert result.total_queued == 0
        assert result.batch_id == ""
        assert "exceeds limit" in result.skipped_reasons[0]
        mock_enqueue.assert_not_called()

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_hotel_breakdown(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, hotel_id=100, hotel_name="Hotel A", recommendation="PUT"),
            _make_signal(detail_id=2, hotel_id=100, hotel_name="Hotel A", recommendation="PUT"),
            _make_signal(detail_id=3, hotel_id=200, hotel_name="Hotel B", recommendation="PUT"),
        ]
        gf = GroupFilter()
        result = execute_group_override(signals, _make_analysis([1, 2, 3]), gf)
        assert result.total_queued == 3
        assert len(result.hotel_breakdown) == 2
        # Hotel A has 2 rooms, should be first
        assert result.hotel_breakdown[0]["hotel_name"] == "Hotel A"
        assert result.hotel_breakdown[0]["queued"] == 2

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_discount_passed(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [_make_signal(detail_id=1, recommendation="PUT")]
        gf = GroupFilter()
        execute_group_override(signals, _make_analysis([1]), gf, discount_usd=5.0)
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args
        assert call_kwargs.kwargs.get("discount_usd") == 5.0 or call_kwargs[1].get("discount_usd") == 5.0

    @patch("src.analytics.override_queue.enqueue_override")
    def test_override_batch_id_and_trigger(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [_make_signal(detail_id=1, recommendation="PUT")]
        gf = GroupFilter()
        result = execute_group_override(signals, _make_analysis([1]), gf)
        call_kwargs = mock_enqueue.call_args
        assert call_kwargs.kwargs.get("trigger_type") == "group_override" or call_kwargs[1].get("trigger_type") == "group_override"
        assert call_kwargs.kwargs.get("batch_id", "").startswith("GRP-OVR-") or call_kwargs[1].get("batch_id", "").startswith("GRP-OVR-")


# ── execute_group_opportunity tests ──────────────────────────────────

class TestExecuteGroupOpportunity:
    @patch("src.analytics.opportunity_queue.enqueue_opportunity")
    def test_basic_opportunity(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, recommendation="CALL"),
            _make_signal(detail_id=2, recommendation="CALL"),
            _make_signal(detail_id=3, recommendation="PUT"),
        ]
        gf = GroupFilter()
        result = execute_group_opportunity(signals, _make_analysis([1, 2, 3]), gf)
        assert result.action == "opportunity"
        assert result.total_queued == 2
        assert result.batch_id.startswith("GRP-OPP-")

    @patch("src.analytics.opportunity_queue.enqueue_opportunity")
    def test_opportunity_forces_call_filter(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, recommendation="PUT"),
            _make_signal(detail_id=2, recommendation="CALL"),
        ]
        gf = GroupFilter(signal="PUT")  # User passed PUT but opportunity forces CALL
        result = execute_group_opportunity(signals, _make_analysis([1, 2]), gf)
        assert result.total_queued == 1

    @patch("src.analytics.opportunity_queue.enqueue_opportunity")
    def test_opportunity_validation_error_skips(self, mock_enqueue):
        from src.analytics.opportunity_queue import OpportunityValidationError
        mock_enqueue.side_effect = OpportunityValidationError("Profit too low")
        signals = [_make_signal(detail_id=1, recommendation="CALL")]
        gf = GroupFilter()
        result = execute_group_opportunity(signals, _make_analysis([1]), gf)
        assert result.total_queued == 0
        assert result.total_skipped == 1

    @patch("src.analytics.opportunity_queue.enqueue_opportunity")
    def test_opportunity_exceeds_group_size(self, mock_enqueue):
        signals = [
            _make_signal(detail_id=i, recommendation="CALL")
            for i in range(MAX_GROUP_SIZE + 10)
        ]
        gf = GroupFilter()
        analysis = _make_analysis(range(MAX_GROUP_SIZE + 10))
        result = execute_group_opportunity(signals, analysis, gf)
        assert result.total_queued == 0
        assert result.batch_id == ""
        mock_enqueue.assert_not_called()

    @patch("src.analytics.opportunity_queue.enqueue_opportunity")
    def test_opportunity_max_rooms_passed(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [_make_signal(detail_id=1, recommendation="CALL")]
        gf = GroupFilter()
        execute_group_opportunity(signals, _make_analysis([1]), gf, max_rooms=3)
        call_kwargs = mock_enqueue.call_args
        assert call_kwargs.kwargs.get("max_rooms") == 3 or call_kwargs[1].get("max_rooms") == 3

    @patch("src.analytics.opportunity_queue.enqueue_opportunity")
    def test_opportunity_includes_strong_call(self, mock_enqueue):
        mock_enqueue.return_value = None
        signals = [
            _make_signal(detail_id=1, recommendation="STRONG_CALL"),
            _make_signal(detail_id=2, recommendation="CALL"),
        ]
        gf = GroupFilter()
        result = execute_group_opportunity(signals, _make_analysis([1, 2]), gf)
        assert result.total_queued == 2


# ── GroupActionResult tests ──────────────────────────────────────────

class TestGroupActionResult:
    def test_to_dict(self):
        result = GroupActionResult(
            batch_id="GRP-OVR-test",
            action="override",
            filter_description="signal=PUT",
            total_matched=5,
            total_queued=4,
            total_skipped=1,
            skipped_reasons=["detail=999: Price too low"],
            hotel_breakdown=[{"hotel_id": 100, "queued": 4}],
            timestamp="2026-03-20T12:00:00Z",
        )
        d = result.to_dict()
        assert d["batch_id"] == "GRP-OVR-test"
        assert d["total_queued"] == 4
        assert isinstance(d["skipped_reasons"], list)
        assert isinstance(d["hotel_breakdown"], list)


# ── Edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_filter_with_missing_fields(self):
        """Signal dicts with missing fields should not crash."""
        signals = [{"detail_id": 1, "T": 10}]  # Missing most fields
        gf = GroupFilter()
        result = filter_signals(signals, {}, gf)
        assert len(result) == 1

    def test_filter_with_none_values(self):
        signals = [_make_signal(detail_id=1, recommendation=None, T=10)]
        gf = GroupFilter(signal="CALL")
        result = filter_signals(signals, _make_analysis([1]), gf)
        assert len(result) == 0

    def test_filter_T_exactly_at_min(self):
        """T exactly at MIN_T_DAYS should be included."""
        signals = [_make_signal(detail_id=1, T=MIN_T_DAYS)]
        gf = GroupFilter()
        result = filter_signals(signals, _make_analysis([1]), gf)
        assert len(result) == 1

    def test_filter_T_below_min(self):
        """T below MIN_T_DAYS should be excluded."""
        signals = [_make_signal(detail_id=1, T=MIN_T_DAYS - 1)]
        gf = GroupFilter()
        result = filter_signals(signals, _make_analysis([1]), gf)
        assert len(result) == 0

    @patch("src.analytics.override_queue.enqueue_override")
    def test_skip_reasons_capped_at_10(self, mock_enqueue):
        from src.analytics.override_queue import OverrideValidationError
        mock_enqueue.side_effect = OverrideValidationError("bad")
        signals = [
            _make_signal(detail_id=i, recommendation="PUT")
            for i in range(20)
        ]
        gf = GroupFilter()
        result = execute_group_override(signals, _make_analysis(range(20)), gf)
        assert result.total_skipped == 20
        assert len(result.skipped_reasons) == 10  # Capped
