"""Unit tests for audit_trail.py — Audit Trail & Compliance."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.audit_trail import (
    AuditEvent,
    AuditSummary,
    log_event,
    log_signal_batch,
    get_audit_events,
    get_audit_summary,
    cleanup_old_events,
    init_audit_db,
    EVENT_SIGNAL_GENERATED,
    EVENT_QUEUE_INSERT,
    EVENT_QUEUE_EXECUTE,
    EVENT_RULE_APPLIED,
    EVENT_OVERRIDE,
    EVENT_PARAM_CHANGE,
    EVENT_SYSTEM,
    RETENTION_DAYS,
    MAX_EVENTS_PER_QUERY,
    MAX_PAYLOAD_SIZE,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "audit_trail.db"
    init_audit_db(path)
    return path


# ── Test Log Event ───────────────────────────────────────────────────

class TestLogEvent:
    def test_basic_log(self, db_path):
        event_id = log_event(
            event_type=EVENT_SIGNAL_GENERATED,
            action="CALL signal generated",
            detail_id=1001,
            hotel_id=1,
            hotel_name="Hotel A",
            signal="CALL",
            db_path=db_path,
        )
        assert event_id > 0

    def test_with_payload(self, db_path):
        event_id = log_event(
            event_type=EVENT_QUEUE_INSERT,
            action="Opportunity queued",
            detail_id=1001,
            hotel_id=1,
            payload={"profit_usd": 50, "rooms": 3},
            db_path=db_path,
        )
        assert event_id > 0
        # Verify payload stored
        events = get_audit_events(detail_id=1001, db_path=db_path)
        assert len(events) == 1
        assert events[0].payload["profit_usd"] == 50

    def test_with_correlation_id(self, db_path):
        corr_id = "batch-20260326-001"
        log_event(
            event_type=EVENT_SYSTEM,
            action="Analysis started",
            correlation_id=corr_id,
            db_path=db_path,
        )
        events = get_audit_events(db_path=db_path)
        assert events[0].correlation_id == corr_id

    def test_large_payload_truncated(self, db_path):
        huge_payload = {f"key_{i}": "x" * 100 for i in range(200)}
        event_id = log_event(
            event_type=EVENT_SYSTEM,
            action="Big payload test",
            payload=huge_payload,
            db_path=db_path,
        )
        assert event_id > 0
        events = get_audit_events(db_path=db_path)
        assert events[0].payload.get("truncated") is True

    def test_all_event_types(self, db_path):
        types = [
            EVENT_SIGNAL_GENERATED, EVENT_QUEUE_INSERT, EVENT_QUEUE_EXECUTE,
            EVENT_RULE_APPLIED, EVENT_OVERRIDE, EVENT_PARAM_CHANGE, EVENT_SYSTEM,
        ]
        for et in types:
            log_event(event_type=et, action=f"Test {et}", db_path=db_path)
        events = get_audit_events(limit=100, db_path=db_path)
        assert len(events) == len(types)

    def test_actor_default(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="test", db_path=db_path)
        events = get_audit_events(db_path=db_path)
        assert events[0].actor == "system"

    def test_custom_actor(self, db_path):
        log_event(
            event_type=EVENT_OVERRIDE,
            action="Manual override",
            actor="operator",
            db_path=db_path,
        )
        events = get_audit_events(db_path=db_path)
        assert events[0].actor == "operator"


# ── Test Log Signal Batch ────────────────────────────────────────────

class TestLogSignalBatch:
    def test_batch_log(self, db_path):
        signals = [
            {"detail_id": 1001, "hotel_id": 1, "hotel_name": "H1",
             "signal": "CALL", "confidence": "HIGH",
             "P_up": 0.72, "P_down": 0.28, "sigma_1d": 0.015, "T": 14},
            {"detail_id": 2001, "hotel_id": 2, "hotel_name": "H2",
             "signal": "PUT", "confidence": "MEDIUM",
             "P_up": 0.35, "P_down": 0.65, "sigma_1d": 0.02, "T": 7},
        ]
        count = log_signal_batch(signals, correlation_id="batch-001", db_path=db_path)
        assert count == 2

    def test_batch_empty(self, db_path):
        count = log_signal_batch([], db_path=db_path)
        assert count == 0

    def test_batch_with_bad_entry(self, db_path):
        signals = [
            {"detail_id": 1001, "hotel_id": 1, "signal": "CALL"},
            {"bad": "entry"},  # missing required fields but should not crash
        ]
        count = log_signal_batch(signals, db_path=db_path)
        assert count >= 1  # at least the good one logged

    def test_batch_correlation_id(self, db_path):
        signals = [
            {"detail_id": 1001, "hotel_id": 1, "signal": "CALL", "hotel_name": "H1"},
        ]
        log_signal_batch(signals, correlation_id="run-123", db_path=db_path)
        events = get_audit_events(db_path=db_path)
        assert events[0].correlation_id == "run-123"


# ── Test Query Functions ─────────────────────────────────────────────

class TestGetAuditEvents:
    def test_empty_db(self, db_path):
        events = get_audit_events(db_path=db_path)
        assert events == []

    def test_filter_by_hotel(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="h1", hotel_id=1, db_path=db_path)
        log_event(event_type=EVENT_SYSTEM, action="h2", hotel_id=2, db_path=db_path)
        events = get_audit_events(hotel_id=1, db_path=db_path)
        assert len(events) == 1
        assert events[0].hotel_id == 1

    def test_filter_by_event_type(self, db_path):
        log_event(event_type=EVENT_SIGNAL_GENERATED, action="sig", db_path=db_path)
        log_event(event_type=EVENT_OVERRIDE, action="ovr", db_path=db_path)
        events = get_audit_events(event_type=EVENT_OVERRIDE, db_path=db_path)
        assert len(events) == 1
        assert events[0].event_type == EVENT_OVERRIDE

    def test_filter_by_detail_id(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="d1", detail_id=100, db_path=db_path)
        log_event(event_type=EVENT_SYSTEM, action="d2", detail_id=200, db_path=db_path)
        events = get_audit_events(detail_id=100, db_path=db_path)
        assert len(events) == 1

    def test_limit(self, db_path):
        for i in range(10):
            log_event(event_type=EVENT_SYSTEM, action=f"e{i}", db_path=db_path)
        events = get_audit_events(limit=3, db_path=db_path)
        assert len(events) == 3

    def test_limit_cap(self, db_path):
        # Limit should be capped at MAX_EVENTS_PER_QUERY
        events = get_audit_events(limit=99999, db_path=db_path)
        assert isinstance(events, list)

    def test_order_desc(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="first", db_path=db_path)
        log_event(event_type=EVENT_SYSTEM, action="second", db_path=db_path)
        events = get_audit_events(db_path=db_path)
        # Most recent first
        assert events[0].action == "second"


# ── Test Audit Summary ───────────────────────────────────────────────

class TestGetAuditSummary:
    def test_empty(self, db_path):
        summary = get_audit_summary(db_path=db_path)
        assert isinstance(summary, AuditSummary)
        assert summary.total_events == 0

    def test_with_events(self, db_path):
        log_event(event_type=EVENT_SIGNAL_GENERATED, action="s1", hotel_id=1, hotel_name="H1", db_path=db_path)
        log_event(event_type=EVENT_SIGNAL_GENERATED, action="s2", hotel_id=1, hotel_name="H1", db_path=db_path)
        log_event(event_type=EVENT_OVERRIDE, action="o1", hotel_id=2, hotel_name="H2", db_path=db_path)
        summary = get_audit_summary(days_back=1, db_path=db_path)
        assert summary.total_events == 3
        assert summary.by_type[EVENT_SIGNAL_GENERATED] == 2
        assert summary.by_type[EVENT_OVERRIDE] == 1
        assert "1:H1" in summary.by_hotel
        assert "2:H2" in summary.by_hotel

    def test_recent_events_limited(self, db_path):
        for i in range(30):
            log_event(event_type=EVENT_SYSTEM, action=f"e{i}", db_path=db_path)
        summary = get_audit_summary(days_back=1, db_path=db_path)
        assert len(summary.recent_events) <= 20

    def test_to_dict(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="test", db_path=db_path)
        summary = get_audit_summary(db_path=db_path)
        d = summary.to_dict()
        assert "total_events" in d
        assert "by_type" in d
        assert "recent_events" in d


# ── Test Cleanup ─────────────────────────────────────────────────────

class TestCleanup:
    def test_cleanup_no_old(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="recent", db_path=db_path)
        deleted = cleanup_old_events(retention_days=RETENTION_DAYS, db_path=db_path)
        assert deleted == 0

    def test_cleanup_with_zero_retention(self, db_path):
        log_event(event_type=EVENT_SYSTEM, action="old", db_path=db_path)
        # retention_days=0 means delete everything
        deleted = cleanup_old_events(retention_days=0, db_path=db_path)
        assert deleted >= 1


# ── Test Data Classes ────────────────────────────────────────────────

class TestDataClasses:
    def test_audit_event_to_dict(self):
        event = AuditEvent(
            event_id=1, event_type=EVENT_SYSTEM,
            timestamp="2026-03-26T12:00:00Z",
            action="test", actor="system",
        )
        d = event.to_dict()
        assert d["event_id"] == 1
        assert d["event_type"] == EVENT_SYSTEM

    def test_constants(self):
        assert RETENTION_DAYS == 365
        assert MAX_EVENTS_PER_QUERY == 1000
        assert MAX_PAYLOAD_SIZE == 10_000
