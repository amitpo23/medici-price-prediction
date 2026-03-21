"""Tests for the opportunity queue — SQLite-based job queue for CALL signals."""
from unittest.mock import patch

import pytest

from src.analytics.opportunity_queue import (
    OpportunityRequest,
    OpportunityValidationError,
    validate_request,
    enqueue_opportunity,
    enqueue_bulk_calls,
    get_queue,
    get_request,
    get_queue_stats,
    get_pending_requests,
    mark_picked,
    mark_completed,
    get_history,
    init_db,
    FIXED_MARKUP_USD,
    MIN_PROFIT_USD,
    MIN_BUY_PRICE,
    MAX_BUY_PRICE,
    MAX_ROOMS,
    MAX_BULK_SIZE,
    ALLOWED_SIGNALS,
    DB_PATH,
)


# ── Test with temp DB ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Redirect opportunity queue to a temp database for each test."""
    temp_db = tmp_path / "test_opportunity_queue.db"
    with patch("src.analytics.opportunity_queue.DB_PATH", temp_db):
        yield temp_db


# ── Validation ───────────────────────────────────────────────────────

class TestValidation:
    def test_valid_request(self):
        push, profit = validate_request(200.0, 260.0, "CALL")
        assert push == 250.0  # 200 + 50
        assert profit == 60.0  # 260 - 200

    def test_push_price_always_buy_plus_50(self):
        push, _ = validate_request(100.0, 180.0, "CALL")
        assert push == 150.0

    def test_profit_must_be_at_least_50(self):
        with pytest.raises(OpportunityValidationError, match="Predicted profit"):
            validate_request(200.0, 230.0, "CALL")  # profit = 30 < 50

    def test_profit_exactly_50_ok(self):
        push, profit = validate_request(200.0, 250.0, "CALL")
        assert profit == 50.0

    def test_reject_put_signal(self):
        with pytest.raises(OpportunityValidationError, match="not in allowed"):
            validate_request(200.0, 260.0, "PUT")

    def test_accept_strong_call(self):
        push, profit = validate_request(200.0, 260.0, "STRONG_CALL")
        assert push == 250.0

    def test_reject_buy_below_min(self):
        with pytest.raises(OpportunityValidationError, match="below minimum"):
            validate_request(0.5, 100.0, "CALL")

    def test_reject_buy_above_max(self):
        with pytest.raises(OpportunityValidationError, match="exceeds maximum"):
            validate_request(6000.0, 6100.0, "CALL")

    def test_reject_rooms_too_many(self):
        with pytest.raises(OpportunityValidationError, match="Max rooms"):
            validate_request(200.0, 260.0, "CALL", max_rooms=31)

    def test_reject_rooms_zero(self):
        with pytest.raises(OpportunityValidationError, match="Max rooms"):
            validate_request(200.0, 260.0, "CALL", max_rooms=0)


# ── Enqueue Single ───────────────────────────────────────────────────

class TestEnqueueSingle:
    def test_enqueue_basic(self):
        req = enqueue_opportunity(
            detail_id=100, hotel_id=66814,
            buy_price=200.0, predicted_price=260.0,
        )
        assert req.id is not None
        assert req.buy_price == 200.0
        assert req.push_price == 250.0  # 200 + 50
        assert req.predicted_price == 260.0
        assert req.profit_usd == 60.0
        assert req.status == "pending"
        assert req.signal == "CALL"

    def test_enqueue_with_metadata(self):
        req = enqueue_opportunity(
            detail_id=101, hotel_id=66814,
            buy_price=300.0, predicted_price=380.0,
            hotel_name="Sunrise Miami", category="deluxe", board="bb",
            checkin_date="2026-05-20", max_rooms=3,
        )
        assert req.hotel_name == "Sunrise Miami"
        assert req.category == "deluxe"
        assert req.board_id == 2  # bb -> 2
        assert req.category_id == 4  # deluxe -> 4
        assert req.max_rooms == 3
        assert req.push_price == 350.0  # 300 + 50

    def test_enqueue_rejected_low_profit(self):
        with pytest.raises(OpportunityValidationError, match="Predicted profit"):
            enqueue_opportunity(
                detail_id=102, hotel_id=66814,
                buy_price=200.0, predicted_price=220.0,  # only $20 profit
            )

    def test_enqueue_creates_unique_ids(self):
        r1 = enqueue_opportunity(detail_id=200, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        r2 = enqueue_opportunity(detail_id=201, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        assert r1.id != r2.id

    def test_to_dict(self):
        req = enqueue_opportunity(detail_id=300, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        d = req.to_dict()
        assert d["detail_id"] == 300
        assert d["push_price"] == 150.0
        assert d["profit_usd"] == 60.0
        assert "status" in d


# ── Enqueue Bulk ─────────────────────────────────────────────────────

class TestEnqueueBulk:
    def _make_signals(self, n=3, signal="CALL", price=200.0, predicted=260.0):
        return [
            {
                "detail_id": 1000 + i,
                "hotel_id": 66814,
                "recommendation": signal,
                "S_t": price,
                "predicted_price": predicted,
                "confidence": "High",
                "hotel_name": "Test Hotel",
                "category": "standard",
                "board": "ro",
            }
            for i in range(n)
        ]

    def test_bulk_creates_only_calls(self):
        signals = self._make_signals(2, "CALL") + self._make_signals(1, "PUT")
        batch_id, reqs = enqueue_bulk_calls(
            analysis={"predictions": {}}, signals=signals,
        )
        assert len(reqs) == 2  # only CALLs
        assert batch_id.startswith("OPP-")

    def test_bulk_hotel_filter(self):
        sigs = self._make_signals(3)
        sigs[2]["hotel_id"] = 99999  # different hotel
        batch_id, reqs = enqueue_bulk_calls(
            analysis={"predictions": {}}, signals=sigs, hotel_id_filter=66814,
        )
        assert len(reqs) == 2

    def test_bulk_skips_low_profit(self):
        sigs = self._make_signals(2, predicted=220.0)  # only $20 profit
        batch_id, reqs = enqueue_bulk_calls(
            analysis={"predictions": {}}, signals=sigs,
        )
        assert len(reqs) == 0  # all skipped

    def test_bulk_max_size_guard(self):
        sigs = self._make_signals(MAX_BULK_SIZE + 10)
        with pytest.raises(OpportunityValidationError, match="Bulk size"):
            enqueue_bulk_calls(analysis={"predictions": {}}, signals=sigs)

    def test_bulk_empty_when_no_calls(self):
        sigs = self._make_signals(3, signal="PUT")
        batch_id, reqs = enqueue_bulk_calls(
            analysis={"predictions": {}}, signals=sigs,
        )
        assert batch_id == ""
        assert reqs == []


# ── Queue Query ──────────────────────────────────────────────────────

class TestQueueQuery:
    def test_get_queue_empty(self):
        reqs, total = get_queue()
        assert total == 0
        assert reqs == []

    def test_get_queue_with_data(self):
        enqueue_opportunity(detail_id=500, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        enqueue_opportunity(detail_id=501, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        reqs, total = get_queue()
        assert total == 2

    def test_get_queue_filter_status(self):
        enqueue_opportunity(detail_id=600, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        reqs, total = get_queue(status="pending")
        assert total == 1
        reqs, total = get_queue(status="done")
        assert total == 0

    def test_get_request_by_id(self):
        req = enqueue_opportunity(detail_id=700, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        found = get_request(req.id)
        assert found is not None
        assert found.detail_id == 700

    def test_get_request_not_found(self):
        assert get_request(99999) is None

    def test_queue_stats(self):
        enqueue_opportunity(detail_id=800, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        stats = get_queue_stats()
        assert stats["pending"] == 1
        assert stats["total"] == 1

    def test_pagination(self):
        for i in range(5):
            enqueue_opportunity(detail_id=900 + i, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        reqs, total = get_queue(limit=2, offset=0)
        assert total == 5
        assert len(reqs) == 2


# ── Status Transitions ───────────────────────────────────────────────

class TestStatusTransitions:
    def test_mark_picked(self):
        req = enqueue_opportunity(detail_id=1100, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        assert mark_picked(req.id)
        found = get_request(req.id)
        assert found.status == "picked"
        assert found.picked_at is not None

    def test_mark_picked_only_pending(self):
        req = enqueue_opportunity(detail_id=1101, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        mark_picked(req.id)
        assert not mark_picked(req.id)  # already picked

    def test_mark_done_with_opp_id(self):
        req = enqueue_opportunity(detail_id=1102, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        assert mark_completed(req.id, success=True, opp_id=3866)
        found = get_request(req.id)
        assert found.status == "done"
        assert found.opp_id == 3866

    def test_mark_failed(self):
        req = enqueue_opportunity(detail_id=1103, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        assert mark_completed(req.id, success=False, error_message="No ratebycat")
        found = get_request(req.id)
        assert found.status == "failed"
        assert "ratebycat" in found.error_message

    def test_complete_nonexistent(self):
        assert not mark_completed(99999, success=True)


# ── Pending Requests ─────────────────────────────────────────────────

class TestPendingRequests:
    def test_get_pending_empty(self):
        assert get_pending_requests() == []

    def test_get_pending_only_pending(self):
        r1 = enqueue_opportunity(detail_id=1200, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        r2 = enqueue_opportunity(detail_id=1201, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        mark_picked(r1.id)
        pending = get_pending_requests()
        assert len(pending) == 1
        assert pending[0].detail_id == 1201

    def test_pending_fifo_order(self):
        r1 = enqueue_opportunity(detail_id=1300, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        r2 = enqueue_opportunity(detail_id=1301, hotel_id=1, buy_price=100.0, predicted_price=160.0)
        pending = get_pending_requests()
        assert pending[0].id < pending[1].id  # FIFO


# ── History ──────────────────────────────────────────────────────────

class TestHistory:
    def test_empty_history(self):
        h = get_history()
        assert h["total"] == 0

    def test_history_with_data(self):
        r1 = enqueue_opportunity(detail_id=1400, hotel_id=1, buy_price=100.0, predicted_price=170.0)
        mark_completed(r1.id, success=True, opp_id=100)
        h = get_history()
        assert h["done"] == 1
        assert h["total_profit_usd"] == 70.0  # 170 - 100

    def test_history_hotel_filter(self):
        enqueue_opportunity(detail_id=1500, hotel_id=111, buy_price=100.0, predicted_price=160.0)
        enqueue_opportunity(detail_id=1501, hotel_id=222, buy_price=100.0, predicted_price=160.0)
        h = get_history(hotel_id=111)
        assert h["total"] == 1

    def test_history_by_hotel_breakdown(self):
        enqueue_opportunity(detail_id=1600, hotel_id=111, buy_price=100.0, predicted_price=160.0, hotel_name="Hotel A")
        enqueue_opportunity(detail_id=1601, hotel_id=222, buy_price=100.0, predicted_price=160.0, hotel_name="Hotel B")
        h = get_history()
        assert len(h["by_hotel"]) == 2


# ── Constants ────────────────────────────────────────────────────────

class TestConstants:
    def test_guardrail_values(self):
        assert FIXED_MARKUP_USD == 50.0
        assert MIN_PROFIT_USD == 50.0
        assert MIN_BUY_PRICE == 1.0
        assert MAX_BUY_PRICE == 5000.0
        assert MAX_ROOMS == 30
        assert MAX_BULK_SIZE == 50
        assert "CALL" in ALLOWED_SIGNALS
        assert "STRONG_CALL" in ALLOWED_SIGNALS
        assert "PUT" not in ALLOWED_SIGNALS
