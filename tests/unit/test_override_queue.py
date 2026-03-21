"""Tests for the price override queue — SQLite-based job queue."""
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from src.analytics.override_queue import (
    OverrideRequest,
    OverrideValidationError,
    validate_request,
    enqueue_override,
    enqueue_bulk_puts,
    get_queue,
    get_request,
    get_queue_stats,
    get_pending_requests,
    mark_picked,
    mark_completed,
    get_history,
    init_db,
    MAX_DISCOUNT_USD,
    MIN_TARGET_PRICE_USD,
    MAX_BULK_SIZE,
    ALLOWED_SIGNALS,
    DEFAULT_DISCOUNT_USD,
    DB_PATH,
)


# ── Test with temp DB ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Redirect override queue to a temp database for each test."""
    temp_db = tmp_path / "test_override_queue.db"
    with patch("src.analytics.override_queue.DB_PATH", temp_db):
        yield temp_db


# ── Validation ───────────────────────────────────────────────────────

class TestValidation:
    def test_valid_request(self):
        target = validate_request(current_price=250.0, discount_usd=1.0)
        assert target == 249.0

    def test_valid_large_discount(self):
        target = validate_request(current_price=250.0, discount_usd=10.0)
        assert target == 240.0

    def test_reject_negative_discount(self):
        with pytest.raises(OverrideValidationError, match="positive"):
            validate_request(current_price=250.0, discount_usd=-1.0)

    def test_reject_zero_discount(self):
        with pytest.raises(OverrideValidationError, match="positive"):
            validate_request(current_price=250.0, discount_usd=0)

    def test_reject_over_max_discount(self):
        with pytest.raises(OverrideValidationError, match="maximum"):
            validate_request(current_price=250.0, discount_usd=15.0)

    def test_reject_zero_price(self):
        with pytest.raises(OverrideValidationError, match="positive"):
            validate_request(current_price=0, discount_usd=1.0)

    def test_reject_below_floor(self):
        with pytest.raises(OverrideValidationError, match="minimum"):
            validate_request(current_price=55.0, discount_usd=10.0)

    def test_reject_invalid_signal(self):
        with pytest.raises(OverrideValidationError, match="Signal"):
            validate_request(current_price=250.0, discount_usd=1.0, signal="CALL")

    def test_accept_strong_put(self):
        target = validate_request(current_price=250.0, discount_usd=1.0, signal="STRONG_PUT")
        assert target == 249.0


# ── Enqueue Single ───────────────────────────────────────────────────

class TestEnqueueSingle:
    def test_enqueue_basic(self):
        req = enqueue_override(
            detail_id=12345,
            hotel_id=66814,
            current_price=250.0,
            discount_usd=1.0,
        )
        assert req.id is not None
        assert req.id > 0
        assert req.detail_id == 12345
        assert req.current_price == 250.0
        assert req.discount_usd == 1.0
        assert req.target_price == 249.0
        assert req.status == "pending"
        assert req.trigger_type == "manual"

    def test_enqueue_with_metadata(self):
        req = enqueue_override(
            detail_id=99999,
            hotel_id=854881,
            current_price=300.0,
            discount_usd=3.0,
            signal="STRONG_PUT",
            confidence="High",
            hotel_name="Sunrise Miami",
            category="deluxe",
            board="bb",
            checkin_date="2026-05-20",
            path_min_price=280.0,
        )
        assert req.target_price == 297.0
        assert req.hotel_name == "Sunrise Miami"
        assert req.signal == "STRONG_PUT"
        assert req.path_min_price == 280.0

    def test_enqueue_guardrail_blocks(self):
        with pytest.raises(OverrideValidationError):
            enqueue_override(
                detail_id=1,
                hotel_id=1,
                current_price=250.0,
                discount_usd=20.0,  # Over max
            )

    def test_enqueue_creates_unique_ids(self):
        r1 = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        r2 = enqueue_override(detail_id=2, hotel_id=1, current_price=200.0)
        assert r1.id != r2.id

    def test_to_dict(self):
        req = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        d = req.to_dict()
        assert isinstance(d, dict)
        assert d["detail_id"] == 1
        assert d["target_price"] == 199.0
        assert d["status"] == "pending"


# ── Enqueue Bulk ─────────────────────────────────────────────────────

class TestEnqueueBulk:
    def _make_analysis_and_signals(self, n_puts: int = 3, n_calls: int = 2) -> tuple:
        predictions = {}
        signals = []
        for i in range(n_puts):
            did = 1000 + i
            predictions[str(did)] = {
                "hotel_id": 66814,
                "hotel_name": "Test Hotel",
                "category": "standard",
                "board": "bb",
                "date_from": "2026-05-20",
                "current_price": 200.0 + i * 10,
            }
            signals.append({
                "detail_id": did,
                "hotel_id": 66814,
                "hotel_name": "Test Hotel",
                "category": "standard",
                "board": "bb",
                "checkin_date": "2026-05-20",
                "S_t": 200.0 + i * 10,
                "recommendation": "PUT",
                "confidence": "High",
            })
        for i in range(n_calls):
            did = 2000 + i
            signals.append({
                "detail_id": did,
                "hotel_id": 66814,
                "recommendation": "CALL",
                "S_t": 300.0,
            })
        return {"predictions": predictions}, signals

    def test_bulk_creates_only_puts(self):
        analysis, signals = self._make_analysis_and_signals(n_puts=3, n_calls=2)
        batch_id, requests = enqueue_bulk_puts(analysis, signals, discount_usd=2.0)

        assert batch_id.startswith("bulk-")
        assert len(requests) == 3
        for r in requests:
            assert r.signal == "PUT"
            assert r.discount_usd == 2.0
            assert r.trigger_type == "bulk_put"
            assert r.batch_id == batch_id

    def test_bulk_hotel_filter(self):
        analysis, signals = self._make_analysis_and_signals(n_puts=3)
        # Add a PUT for a different hotel
        signals.append({
            "detail_id": 9999,
            "hotel_id": 11111,
            "recommendation": "PUT",
            "S_t": 150.0,
        })
        analysis["predictions"]["9999"] = {"hotel_id": 11111, "current_price": 150.0}

        batch_id, requests = enqueue_bulk_puts(
            analysis, signals, discount_usd=1.0, hotel_id_filter=66814,
        )
        assert len(requests) == 3  # Only hotel 66814

    def test_bulk_empty_when_no_puts(self):
        analysis = {"predictions": {}}
        signals = [{"detail_id": 1, "recommendation": "CALL", "S_t": 200}]
        batch_id, requests = enqueue_bulk_puts(analysis, signals)
        assert batch_id == ""
        assert len(requests) == 0

    def test_bulk_max_size_guard(self):
        analysis, signals = self._make_analysis_and_signals(n_puts=MAX_BULK_SIZE + 10)
        with pytest.raises(OverrideValidationError, match="Bulk size"):
            enqueue_bulk_puts(analysis, signals)


# ── Queue Query ──────────────────────────────────────────────────────

class TestQueueQuery:
    def test_get_queue_empty(self):
        requests, total = get_queue()
        assert total == 0
        assert requests == []

    def test_get_queue_with_data(self):
        enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        enqueue_override(detail_id=2, hotel_id=1, current_price=300.0)

        requests, total = get_queue()
        assert total == 2
        assert len(requests) == 2

    def test_get_queue_filter_status(self):
        enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        requests, total = get_queue(status="pending")
        assert total == 1

        requests, total = get_queue(status="done")
        assert total == 0

    def test_get_request_by_id(self):
        req = enqueue_override(detail_id=42, hotel_id=1, current_price=200.0)
        fetched = get_request(req.id)
        assert fetched is not None
        assert fetched.detail_id == 42
        assert fetched.target_price == 199.0

    def test_get_request_not_found(self):
        assert get_request(99999) is None

    def test_queue_stats(self):
        enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        enqueue_override(detail_id=2, hotel_id=1, current_price=200.0)

        stats = get_queue_stats()
        assert stats["pending"] == 2
        assert stats["done"] == 0
        assert stats["total"] == 2

    def test_pagination(self):
        for i in range(10):
            enqueue_override(detail_id=i, hotel_id=1, current_price=200.0)

        page1, total = get_queue(limit=3, offset=0)
        assert total == 10
        assert len(page1) == 3

        page2, _ = get_queue(limit=3, offset=3)
        assert len(page2) == 3


# ── Status Transitions ───────────────────────────────────────────────

class TestStatusTransitions:
    def test_mark_picked(self):
        req = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        success = mark_picked(req.id)
        assert success

        fetched = get_request(req.id)
        assert fetched.status == "picked"
        assert fetched.picked_at is not None

    def test_mark_picked_only_pending(self):
        req = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        mark_picked(req.id)
        # Try picking again — should fail
        success = mark_picked(req.id)
        assert not success

    def test_mark_done(self):
        req = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        success = mark_completed(req.id, success=True)
        assert success

        fetched = get_request(req.id)
        assert fetched.status == "done"
        assert fetched.completed_at is not None
        assert fetched.error_message is None

    def test_mark_failed(self):
        req = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        success = mark_completed(req.id, success=False, error_message="Connection timeout")
        assert success

        fetched = get_request(req.id)
        assert fetched.status == "failed"
        assert fetched.error_message == "Connection timeout"

    def test_complete_nonexistent(self):
        success = mark_completed(99999, success=True)
        assert not success


# ── Pending Requests (for external skill) ────────────────────────────

class TestPendingRequests:
    def test_get_pending_empty(self):
        pending = get_pending_requests()
        assert pending == []

    def test_get_pending_only_pending(self):
        r1 = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        r2 = enqueue_override(detail_id=2, hotel_id=1, current_price=200.0)
        mark_completed(r2.id, success=True)

        pending = get_pending_requests()
        assert len(pending) == 1
        assert pending[0].detail_id == 1

    def test_pending_fifo_order(self):
        r1 = enqueue_override(detail_id=1, hotel_id=1, current_price=200.0)
        r2 = enqueue_override(detail_id=2, hotel_id=1, current_price=200.0)
        r3 = enqueue_override(detail_id=3, hotel_id=1, current_price=200.0)

        pending = get_pending_requests()
        assert len(pending) == 3
        assert pending[0].detail_id == 1  # FIFO


# ── History ──────────────────────────────────────────────────────────

class TestHistory:
    def test_empty_history(self):
        h = get_history()
        assert h["total"] == 0
        assert h["done"] == 0

    def test_history_with_data(self):
        r1 = enqueue_override(detail_id=1, hotel_id=66814, current_price=200.0, discount_usd=2.0)
        r2 = enqueue_override(detail_id=2, hotel_id=66814, current_price=300.0, discount_usd=3.0)
        mark_completed(r1.id, success=True)
        mark_completed(r2.id, success=False, error_message="timeout")

        h = get_history()
        assert h["total"] == 2
        assert h["done"] == 1
        assert h["failed"] == 1
        assert h["success_rate_pct"] == 50.0
        assert h["avg_discount_usd"] == 2.5

    def test_history_hotel_filter(self):
        enqueue_override(detail_id=1, hotel_id=66814, current_price=200.0)
        enqueue_override(detail_id=2, hotel_id=11111, current_price=200.0)

        h = get_history(hotel_id=66814)
        assert h["total"] == 1

    def test_history_by_hotel_breakdown(self):
        enqueue_override(detail_id=1, hotel_id=66814, current_price=200.0, hotel_name="Hotel A")
        enqueue_override(detail_id=2, hotel_id=66814, current_price=200.0, hotel_name="Hotel A")
        enqueue_override(detail_id=3, hotel_id=11111, current_price=200.0, hotel_name="Hotel B")

        h = get_history()
        assert len(h["by_hotel"]) == 2
        # Sorted by total descending
        assert h["by_hotel"][0]["hotel_id"] == 66814
        assert h["by_hotel"][0]["total"] == 2


# ── Constants ────────────────────────────────────────────────────────

class TestConstants:
    def test_guardrail_values(self):
        assert MAX_DISCOUNT_USD == 10.0
        assert MIN_TARGET_PRICE_USD == 50.0
        assert MAX_BULK_SIZE == 100
        assert DEFAULT_DISCOUNT_USD == 1.0
        assert "PUT" in ALLOWED_SIGNALS
        assert "STRONG_PUT" in ALLOWED_SIGNALS
        assert "CALL" not in ALLOWED_SIGNALS
