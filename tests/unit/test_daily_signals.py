"""Unit tests for daily_signals.py — per-day CALL/PUT/NEUTRAL generation.

Uses real objects with constructed data — NO mocks.
"""
from __future__ import annotations

import pytest

from src.analytics.daily_signals import (
    generate_daily_signals,
    summarize_signals,
    _classify_daily_signal,
    _extract_enrichments,
    _compute_daily_confidence,
    DAILY_CALL_THRESHOLD,
    DAILY_PUT_THRESHOLD,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_fc_points(n=10, base_price=200.0, daily_change=0.8):
    """Build forward curve points for testing."""
    points = []
    price = base_price
    for i in range(n):
        pct = daily_change if i % 3 != 2 else -daily_change
        price *= (1 + pct / 100)
        points.append({
            "date": f"2026-04-{i+1:02d}",
            "t": 30 - i,
            "predicted_price": round(price, 2),
            "daily_change_pct": pct,
            "event_adj_pct": 0.02 if i == 0 else 0.0,
            "season_adj_pct": 0.05,
        })
    return points


# ── Signal Classification ────────────────────────────────────────────


class TestClassifyDailySignal:
    """Tests for _classify_daily_signal()."""

    def test_call_above_threshold(self):
        assert _classify_daily_signal(0.5) == "CALL"
        assert _classify_daily_signal(1.5) == "CALL"
        assert _classify_daily_signal(5.0) == "CALL"

    def test_put_below_threshold(self):
        assert _classify_daily_signal(-0.5) == "PUT"
        assert _classify_daily_signal(-2.0) == "PUT"

    def test_neutral_in_between(self):
        assert _classify_daily_signal(0.0) == "NEUTRAL"
        assert _classify_daily_signal(0.3) == "NEUTRAL"
        assert _classify_daily_signal(-0.3) == "NEUTRAL"
        assert _classify_daily_signal(0.49) == "NEUTRAL"
        assert _classify_daily_signal(-0.49) == "NEUTRAL"

    def test_exact_thresholds(self):
        assert _classify_daily_signal(DAILY_CALL_THRESHOLD) == "CALL"
        assert _classify_daily_signal(DAILY_PUT_THRESHOLD) == "PUT"


# ── Enrichment Extraction ────────────────────────────────────────────


class TestExtractEnrichments:
    """Tests for _extract_enrichments()."""

    def test_extracts_nonzero_keys(self):
        point = {"event_adj_pct": 0.03, "season_adj_pct": 0.0, "demand_adj_pct": -0.1}
        result = _extract_enrichments(point)
        assert "event_adj_pct" in result
        assert "demand_adj_pct" in result
        assert "season_adj_pct" not in result  # Zero excluded

    def test_empty_point(self):
        assert _extract_enrichments({}) == {}

    def test_overrides(self):
        point = {"event_adj_pct": 0.03}
        overrides = {"event_adj_pct": 0.10}
        result = _extract_enrichments(point, overrides)
        assert result["event_adj_pct"] == 0.10

    def test_override_adds_new_key(self):
        point = {}
        overrides = {"weather_adj_pct": -0.05}
        result = _extract_enrichments(point, overrides)
        assert result["weather_adj_pct"] == -0.05


# ── Confidence Computation ───────────────────────────────────────────


class TestComputeDailyConfidence:
    """Tests for _compute_daily_confidence()."""

    def test_high_magnitude_high_confidence(self):
        conf = _compute_daily_confidence(3.0, {"event_adj_pct": 0.05}, t_value=5)
        assert conf >= 0.85

    def test_low_magnitude_low_confidence(self):
        conf = _compute_daily_confidence(0.2, {}, t_value=60)
        assert conf <= 0.50

    def test_t_proximity_boost(self):
        far = _compute_daily_confidence(1.0, {}, t_value=60)
        close = _compute_daily_confidence(1.0, {}, t_value=5)
        assert close > far

    def test_enrichment_agreement_boost(self):
        no_enrich = _compute_daily_confidence(1.0, {}, t_value=14)
        agree_enrich = _compute_daily_confidence(
            1.0, {"event_adj_pct": 0.05, "season_adj_pct": 0.03, "demand_adj_pct": 0.02}, t_value=14
        )
        assert agree_enrich > no_enrich

    def test_enrichment_disagreement(self):
        # Positive daily change but negative enrichments
        disagree = _compute_daily_confidence(
            1.0, {"event_adj_pct": -0.05, "season_adj_pct": -0.03}, t_value=14
        )
        agree = _compute_daily_confidence(
            1.0, {"event_adj_pct": 0.05, "season_adj_pct": 0.03}, t_value=14
        )
        assert agree > disagree

    def test_confidence_capped_at_095(self):
        conf = _compute_daily_confidence(5.0, {"a": 0.1, "b": 0.1, "c": 0.1}, t_value=1)
        assert conf <= 0.95

    def test_neutral_range_low_confidence(self):
        conf = _compute_daily_confidence(0.1, {}, t_value=30)
        assert conf < 0.50


# ── Signal Generation ────────────────────────────────────────────────


class TestGenerateDailySignals:
    """Tests for generate_daily_signals() — main entry point."""

    def test_basic_generation(self):
        points = _make_fc_points(n=5)
        signals = generate_daily_signals(points, detail_id=100, hotel_id=1)
        assert len(signals) == 5
        for s in signals:
            assert s["signal"] in ("CALL", "PUT", "NEUTRAL")
            assert 0 <= s["confidence"] <= 1
            assert s["detail_id"] == 100
            assert s["hotel_id"] == 1

    def test_empty_input(self):
        assert generate_daily_signals([], detail_id=1, hotel_id=1) == []

    def test_skips_invalid_prices(self):
        points = [
            {"date": "2026-04-01", "t": 10, "predicted_price": 0, "daily_change_pct": 1.0},
            {"date": "2026-04-02", "t": 9, "predicted_price": 200.0, "daily_change_pct": 0.8},
        ]
        signals = generate_daily_signals(points, detail_id=1, hotel_id=1)
        assert len(signals) == 1  # First one skipped

    def test_skips_missing_date(self):
        points = [
            {"date": "", "t": 10, "predicted_price": 200.0, "daily_change_pct": 1.0},
        ]
        signals = generate_daily_signals(points, detail_id=1, hotel_id=1)
        assert len(signals) == 0

    def test_enrichments_passed_through(self):
        points = [{"date": "2026-04-01", "t": 10, "predicted_price": 200.0,
                    "daily_change_pct": 1.0, "event_adj_pct": 0.05}]
        signals = generate_daily_signals(points, detail_id=1, hotel_id=1)
        assert "event_adj_pct" in signals[0]["enrichments"]

    def test_enrichment_overrides(self):
        points = [{"date": "2026-04-01", "t": 10, "predicted_price": 200.0,
                    "daily_change_pct": 1.0, "event_adj_pct": 0.02}]
        overrides = {"event_adj_pct": 0.50}
        signals = generate_daily_signals(points, detail_id=1, hotel_id=1, enrichments=overrides)
        assert signals[0]["enrichments"]["event_adj_pct"] == 0.50

    def test_signal_dates_preserved(self):
        points = _make_fc_points(n=3)
        signals = generate_daily_signals(points, detail_id=1, hotel_id=1)
        dates = [s["signal_date"] for s in signals]
        assert dates == ["2026-04-01", "2026-04-02", "2026-04-03"]


# ── Signal Summary ───────────────────────────────────────────────────


class TestSummarizeSignals:
    """Tests for summarize_signals()."""

    def test_empty(self):
        result = summarize_signals([])
        assert result["total"] == 0
        assert result["trend"] == "NEUTRAL"

    def test_bullish_trend(self):
        signals = [
            {"signal": "CALL", "signal_date": f"2026-04-{i:02d}", "daily_change_pct": 1.0}
            for i in range(1, 8)
        ]
        result = summarize_signals(signals)
        assert result["calls"] == 7
        assert result["trend"] == "BULLISH"

    def test_bearish_trend(self):
        signals = [
            {"signal": "PUT", "signal_date": f"2026-04-{i:02d}", "daily_change_pct": -1.0}
            for i in range(1, 8)
        ]
        result = summarize_signals(signals)
        assert result["puts"] == 7
        assert result["trend"] == "BEARISH"

    def test_neutral_trend(self):
        signals = [
            {"signal": "CALL", "signal_date": "2026-04-01", "daily_change_pct": 1.0},
            {"signal": "PUT", "signal_date": "2026-04-02", "daily_change_pct": -1.0},
            {"signal": "NEUTRAL", "signal_date": "2026-04-03", "daily_change_pct": 0.0},
        ]
        result = summarize_signals(signals)
        assert result["trend"] == "NEUTRAL"

    def test_mildly_bullish(self):
        signals = [
            {"signal": "CALL", "signal_date": "2026-04-01", "daily_change_pct": 1.0},
            {"signal": "CALL", "signal_date": "2026-04-02", "daily_change_pct": 0.8},
            {"signal": "PUT", "signal_date": "2026-04-03", "daily_change_pct": -1.0},
            {"signal": "NEUTRAL", "signal_date": "2026-04-04", "daily_change_pct": 0.0},
        ]
        result = summarize_signals(signals)
        assert result["trend"] == "MILDLY_BULLISH"

    def test_next_7_days(self):
        signals = [
            {"signal": "CALL", "signal_date": f"2026-04-{i:02d}", "daily_change_pct": 1.0}
            for i in range(1, 11)
        ]
        result = summarize_signals(signals)
        assert len(result["next_7_days"]["signals"]) == 7
        assert result["next_7_days"]["calls"] == 7
