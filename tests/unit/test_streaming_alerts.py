"""Unit tests for streaming_alerts.py — Real-Time Streaming Alerts."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.streaming_alerts import (
    StreamingAlert,
    AlertSummary,
    generate_alerts,
    get_recent_alerts,
    init_alerts_db,
    _check_band_breach,
    _check_signal_flip,
    _make_alert_id,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "streaming_alerts.db"
    init_alerts_db(path)
    return path


def _make_analysis(predictions: dict, data_quality: dict | None = None) -> dict:
    result = {"predictions": predictions}
    if data_quality:
        result["data_quality"] = data_quality
    return result


def _make_pred(
    hotel_id, hotel_name, current_price, signal="CALL",
    fc_lower=None, fc_upper=None, regime="NORMAL",
    momentum_signal="", category="standard",
):
    fc = []
    if fc_lower is not None and fc_upper is not None:
        fc = [{"lower_bound": fc_lower, "upper_bound": fc_upper, "predicted_price": current_price}]
    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "category": category,
        "current_price": current_price,
        "option_signal": signal,
        "regime": {"regime": regime},
        "momentum": {"signal": momentum_signal},
        "forward_curve": fc,
    }


# ── Test Band Breach ────────────────────────────────────────────────

class TestBandBreach:
    def test_within_band(self):
        alert = _check_band_breach(
            1001, 1, "Hotel A", "standard",
            current_price=150, fc=[{"lower_bound": 140, "upper_bound": 160}],
            now_str="2026-03-26T12:00:00Z",
        )
        assert alert is None

    def test_below_lower_band(self):
        alert = _check_band_breach(
            1001, 1, "Hotel A", "standard",
            current_price=100, fc=[{"lower_bound": 140, "upper_bound": 160}],
            now_str="2026-03-26T12:00:00Z",
        )
        assert alert is not None
        assert alert.alert_type == "BAND_BREACH"
        assert alert.severity == SEVERITY_CRITICAL

    def test_above_upper_band(self):
        alert = _check_band_breach(
            1001, 1, "Hotel A", "standard",
            current_price=200, fc=[{"lower_bound": 140, "upper_bound": 160}],
            now_str="2026-03-26T12:00:00Z",
        )
        assert alert is not None
        assert alert.alert_type == "BAND_BREACH"
        assert alert.severity == SEVERITY_WARNING

    def test_empty_fc(self):
        alert = _check_band_breach(
            1001, 1, "Hotel A", "standard",
            current_price=150, fc=[],
            now_str="2026-03-26T12:00:00Z",
        )
        assert alert is None

    def test_zero_bounds(self):
        alert = _check_band_breach(
            1001, 1, "Hotel A", "standard",
            current_price=150, fc=[{"lower_bound": 0, "upper_bound": 0}],
            now_str="2026-03-26T12:00:00Z",
        )
        assert alert is None


# ── Test Signal Flip ─────────────────────────────────────────────────

class TestSignalFlip:
    def test_call_to_put(self):
        alert = _check_signal_flip(
            1001, 1, "Hotel A", "standard",
            "CALL", "PUT", "2026-03-26T12:00:00Z",
        )
        assert alert is not None
        assert alert.alert_type == "SIGNAL_FLIP"
        assert alert.severity == SEVERITY_CRITICAL

    def test_put_to_call(self):
        alert = _check_signal_flip(
            1001, 1, "Hotel A", "standard",
            "STRONG_PUT", "STRONG_CALL", "2026-03-26T12:00:00Z",
        )
        assert alert is not None
        assert alert.alert_type == "SIGNAL_FLIP"

    def test_no_flip_same_direction(self):
        alert = _check_signal_flip(
            1001, 1, "Hotel A", "standard",
            "CALL", "STRONG_CALL", "2026-03-26T12:00:00Z",
        )
        assert alert is None

    def test_no_flip_from_none(self):
        alert = _check_signal_flip(
            1001, 1, "Hotel A", "standard",
            "NONE", "CALL", "2026-03-26T12:00:00Z",
        )
        assert alert is None


# ── Test Alert ID / Dedup ────────────────────────────────────────────

class TestAlertId:
    def test_same_inputs_same_id(self):
        a1 = StreamingAlert(
            alert_type="BAND_BREACH", detail_id=100, hotel_id=1,
            created_at="2026-03-26T12:00:00Z",
        )
        a2 = StreamingAlert(
            alert_type="BAND_BREACH", detail_id=100, hotel_id=1,
            created_at="2026-03-26T12:30:00Z",  # same hour bucket
        )
        assert _make_alert_id(a1) == _make_alert_id(a2)

    def test_different_hour_different_id(self):
        a1 = StreamingAlert(
            alert_type="BAND_BREACH", detail_id=100, hotel_id=1,
            created_at="2026-03-26T12:00:00Z",
        )
        a2 = StreamingAlert(
            alert_type="BAND_BREACH", detail_id=100, hotel_id=1,
            created_at="2026-03-26T13:00:00Z",  # different hour
        )
        assert _make_alert_id(a1) != _make_alert_id(a2)

    def test_different_type_different_id(self):
        a1 = StreamingAlert(
            alert_type="BAND_BREACH", detail_id=100, hotel_id=1,
            created_at="2026-03-26T12:00:00Z",
        )
        a2 = StreamingAlert(
            alert_type="SIGNAL_FLIP", detail_id=100, hotel_id=1,
            created_at="2026-03-26T12:00:00Z",
        )
        assert _make_alert_id(a1) != _make_alert_id(a2)


# ── Test Generate Alerts ─────────────────────────────────────────────

class TestGenerateAlerts:
    def test_no_predictions(self, db_path):
        summary = generate_alerts({}, db_path=db_path)
        assert isinstance(summary, AlertSummary)
        assert summary.total_generated == 0

    def test_band_breach_alert(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 100, fc_lower=140, fc_upper=160),
        })
        summary = generate_alerts(analysis, db_path=db_path)
        assert summary.total_generated >= 1
        types = [a.alert_type for a in summary.alerts]
        assert "BAND_BREACH" in types

    def test_regime_change_alert(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 150, regime="VOLATILE"),
        })
        summary = generate_alerts(analysis, db_path=db_path)
        types = [a.alert_type for a in summary.alerts]
        assert "REGIME_CHANGE" in types

    def test_signal_flip_alert(self, db_path):
        prev = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 150, signal="CALL"),
        })
        curr = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 150, signal="PUT"),
        })
        summary = generate_alerts(curr, previous_analysis=prev, db_path=db_path)
        types = [a.alert_type for a in summary.alerts]
        assert "SIGNAL_FLIP" in types

    def test_stale_data_alert(self, db_path):
        analysis = _make_analysis(
            predictions={},
            data_quality={"source_a": {"freshness_hours": 12.0}},
        )
        summary = generate_alerts(analysis, db_path=db_path)
        types = [a.alert_type for a in summary.alerts]
        assert "STALE_DATA" in types

    def test_momentum_shift_alert(self, db_path):
        prev = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 150, momentum_signal="ACCELERATING_DOWN"),
        })
        curr = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 150, momentum_signal="ACCELERATING_UP"),
        })
        summary = generate_alerts(curr, previous_analysis=prev, db_path=db_path)
        types = [a.alert_type for a in summary.alerts]
        assert "MOMENTUM_SHIFT" in types

    def test_deduplication(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 100, fc_lower=140, fc_upper=160),
        })
        s1 = generate_alerts(analysis, db_path=db_path)
        s2 = generate_alerts(analysis, db_path=db_path)
        # Second run should suppress the same alert
        assert s2.total_suppressed >= s1.total_new

    def test_summary_counts(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 100, fc_lower=140, fc_upper=160, regime="VOLATILE"),
        })
        summary = generate_alerts(analysis, db_path=db_path)
        assert summary.total_generated == summary.total_new + summary.total_suppressed
        assert summary.total_generated == sum(summary.by_type.values()) + summary.total_suppressed

    def test_zero_price_skipped(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 0),
        })
        summary = generate_alerts(analysis, db_path=db_path)
        assert summary.total_generated == 0


# ── Test Get Recent Alerts ───────────────────────────────────────────

class TestGetRecentAlerts:
    def test_empty_db(self, db_path):
        alerts = get_recent_alerts(db_path=db_path)
        assert alerts == []

    def test_after_generate(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 100, fc_lower=140, fc_upper=160),
        })
        generate_alerts(analysis, db_path=db_path)
        alerts = get_recent_alerts(db_path=db_path)
        assert len(alerts) >= 1

    def test_filter_by_type(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 100, fc_lower=140, fc_upper=160, regime="VOLATILE"),
        })
        generate_alerts(analysis, db_path=db_path)
        alerts = get_recent_alerts(alert_type="BAND_BREACH", db_path=db_path)
        assert all(a.alert_type == "BAND_BREACH" for a in alerts)

    def test_filter_by_severity(self, db_path):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", 100, fc_lower=140, fc_upper=160),
        })
        generate_alerts(analysis, db_path=db_path)
        alerts = get_recent_alerts(severity="critical", db_path=db_path)
        assert all(a.severity == "critical" for a in alerts)


# ── Test Data Classes ────────────────────────────────────────────────

class TestDataClasses:
    def test_alert_to_dict(self):
        alert = StreamingAlert(
            alert_id="abc123", alert_type="BAND_BREACH",
            severity="critical", detail_id=100, hotel_id=1,
            hotel_name="Hotel A", message="test",
        )
        d = alert.to_dict()
        assert d["alert_id"] == "abc123"
        assert d["severity"] == "critical"

    def test_summary_to_dict(self):
        summary = AlertSummary(
            timestamp="2026-03-26T12:00:00Z",
            total_generated=5, total_suppressed=2, total_new=3,
        )
        d = summary.to_dict()
        assert d["total_generated"] == 5
        assert d["total_new"] == 3
