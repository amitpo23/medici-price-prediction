"""Unit tests for meta_learner.py — Adaptive Signal Weighting."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.meta_learner import (
    WeightAdjustment,
    ConsensusScore,
    MetaLearnerReport,
    compute_consensus,
    compute_meta_learner_report,
    get_weight_for_context,
    MAX_WEIGHT_DEVIATION,
    MIN_SAMPLES_FOR_ADJUSTMENT,
    T_RANGES,
    _signal_direction,
    _get_t_range,
    _clamp_weight,
    _make_adjustment,
    init_meta_db,
)
from config.constants import (
    ENSEMBLE_WEIGHT_FORWARD_CURVE,
    ENSEMBLE_WEIGHT_HISTORICAL,
    ENSEMBLE_WEIGHT_ML,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "meta_learner.db"
    init_meta_db(path)
    return path


@pytest.fixture
def sample_analysis():
    return {
        "predictions": {
            "1001": {
                "hotel_id": 1, "hotel_name": "Hotel A",
                "category": "standard", "current_price": 150,
                "option_signal": "CALL", "confidence": "HIGH",
                "probability": {"up": 72, "down": 28},
                "T": 14, "days_to_checkin": 14,
                "date_from": "2026-06-15",
                "forward_curve": [
                    {"t": 1, "predicted_price": 155, "daily_change_pct": 0.5},
                ],
                "momentum": {"signal": "ACCELERATING_UP"},
                "regime": {"regime": "NORMAL"},
            },
            "2001": {
                "hotel_id": 2, "hotel_name": "Hotel B",
                "category": "deluxe", "current_price": 250,
                "option_signal": "PUT", "confidence": "MEDIUM",
                "probability": {"up": 35, "down": 65},
                "T": 5, "days_to_checkin": 5,
                "date_from": "2026-01-20",
                "forward_curve": [
                    {"t": 1, "predicted_price": 245, "daily_change_pct": -0.3},
                ],
                "momentum": {"signal": "DECELERATING"},
                "regime": {"regime": "NORMAL"},
            },
        }
    }


# ── Test T-Range Classification ──────────────────────────────────────

class TestTRangeClassify:
    def test_short(self):
        assert _get_t_range(3) == "short"

    def test_medium(self):
        assert _get_t_range(14) == "medium"

    def test_long(self):
        assert _get_t_range(30) == "long"

    def test_very_long(self):
        assert _get_t_range(90) == "very_long"

    def test_boundary_short_medium(self):
        assert _get_t_range(7) == "short"
        assert _get_t_range(8) == "medium"

    def test_boundary_medium_long(self):
        assert _get_t_range(21) == "medium"
        assert _get_t_range(22) == "long"

    def test_boundary_long_very_long(self):
        assert _get_t_range(60) == "long"
        assert _get_t_range(61) == "very_long"


# ── Test Signal Direction ────────────────────────────────────────────

class TestSignalDirection:
    def test_call(self):
        assert _signal_direction("CALL") == "UP"

    def test_strong_call(self):
        assert _signal_direction("STRONG_CALL") == "UP"

    def test_put(self):
        assert _signal_direction("PUT") == "DOWN"

    def test_strong_put(self):
        assert _signal_direction("STRONG_PUT") == "DOWN"

    def test_none(self):
        assert _signal_direction("NONE") == "FLAT"

    def test_empty(self):
        assert _signal_direction("") == "FLAT"


# ── Test Clamp Weight ────────────────────────────────────────────────

class TestClampWeight:
    def test_within_range(self):
        result = _clamp_weight(0.50, 0.50)
        assert result == 0.50

    def test_above_max(self):
        result = _clamp_weight(0.90, 0.50)
        assert result == 0.50 + MAX_WEIGHT_DEVIATION

    def test_below_min(self):
        result = _clamp_weight(0.10, 0.50)
        assert result == 0.50 - MAX_WEIGHT_DEVIATION

    def test_small_base(self):
        result = _clamp_weight(0.0, 0.10)
        # Should not go below 0.01
        assert result >= 0.01


# ── Test Consensus Score ─────────────────────────────────────────────

class TestConsensusScore:
    def test_basic_consensus(self, sample_analysis):
        scores = compute_consensus(sample_analysis)
        assert len(scores) == 2
        assert all(isinstance(s, ConsensusScore) for s in scores)

    def test_consensus_fields(self, sample_analysis):
        scores = compute_consensus(sample_analysis)
        for s in scores:
            assert s.ensemble_signal in ("CALL", "PUT", "NONE", "STRONG_CALL", "STRONG_PUT")
            assert 0 <= s.agreement_pct <= 1.0
            assert 0 <= s.agreement_count <= 3

    def test_empty_analysis(self):
        scores = compute_consensus({})
        assert scores == []

    def test_no_predictions(self):
        scores = compute_consensus({"predictions": {}})
        assert scores == []

    def test_to_dict(self, sample_analysis):
        scores = compute_consensus(sample_analysis)
        d = scores[0].to_dict()
        assert "agreement_pct" in d
        assert "fc_signal" in d
        assert "ensemble_signal" in d

    def test_unanimous(self):
        """All sources agree → unanimous=True."""
        analysis = {"predictions": {
            "100": {
                "option_signal": "CALL",
                "source_signals": {
                    "forward_curve": "CALL",
                    "historical": "CALL",
                    "ml": "CALL",
                },
            },
        }}
        scores = compute_consensus(analysis)
        assert scores[0].unanimous is True
        assert scores[0].agreement_count == 3


# ── Test Meta-Learner Report ─────────────────────────────────────────

class TestMetaLearnerReport:
    def test_basic_report(self, sample_analysis, db_path):
        report = compute_meta_learner_report(sample_analysis, db_path=db_path)
        assert isinstance(report, MetaLearnerReport)
        assert report.timestamp.endswith("Z")

    def test_base_weights(self, sample_analysis, db_path):
        report = compute_meta_learner_report(sample_analysis, db_path=db_path)
        assert report.base_weights["forward_curve"] == ENSEMBLE_WEIGHT_FORWARD_CURVE
        assert report.base_weights["historical"] == ENSEMBLE_WEIGHT_HISTORICAL
        assert report.base_weights["ml"] == ENSEMBLE_WEIGHT_ML

    def test_report_to_dict(self, sample_analysis, db_path):
        report = compute_meta_learner_report(sample_analysis, db_path=db_path)
        d = report.to_dict()
        assert "base_weights" in d
        assert "by_regime" in d
        assert "by_t_range" in d
        assert "by_season" in d
        assert "avg_consensus" in d
        assert "recommendations" in d

    def test_empty_report(self, db_path):
        report = compute_meta_learner_report({}, db_path=db_path)
        assert report.avg_consensus == 0.0

    def test_consensus_distribution(self, sample_analysis, db_path):
        report = compute_meta_learner_report(sample_analysis, db_path=db_path)
        assert isinstance(report.consensus_distribution, dict)


# ── Test Weight For Context ──────────────────────────────────────────

class TestWeightForContext:
    def test_default_weights(self, db_path):
        """No history → returns base weights."""
        w = get_weight_for_context(regime="NORMAL", t_value=14, db_path=db_path)
        assert isinstance(w, WeightAdjustment)
        assert w.fc_weight == ENSEMBLE_WEIGHT_FORWARD_CURVE
        assert w.hist_weight == ENSEMBLE_WEIGHT_HISTORICAL
        assert w.ml_weight == ENSEMBLE_WEIGHT_ML
        assert w.adjustment_reason == "insufficient_data"

    def test_weights_sum_to_one(self, db_path):
        w = get_weight_for_context(regime="NORMAL", t_value=14, db_path=db_path)
        total = w.fc_weight + w.hist_weight + w.ml_weight
        assert total == pytest.approx(1.0, abs=0.01)

    def test_different_contexts(self, db_path):
        w1 = get_weight_for_context(regime="NORMAL", t_value=3, db_path=db_path)
        w2 = get_weight_for_context(regime="VOLATILE", t_value=60, db_path=db_path)
        # Both should have base weights (no history)
        assert w1.fc_weight == w2.fc_weight

    def test_context_string(self, db_path):
        w = get_weight_for_context(regime="NORMAL", t_value=14, season="summer", db_path=db_path)
        assert "regime=NORMAL" in w.context
        assert "season=summer" in w.context


# ── Test Make Adjustment ─────────────────────────────────────────────

class TestMakeAdjustment:
    def test_insufficient_samples(self):
        stats = {"total": 5, "call": 3, "put": 2, "none": 0}
        adj = _make_adjustment("test_context", stats)
        assert adj.adjustment_reason == "base_weights"
        assert adj.fc_weight == ENSEMBLE_WEIGHT_FORWARD_CURVE

    def test_directional_bias(self):
        stats = {"total": 50, "call": 40, "put": 5, "none": 5}
        adj = _make_adjustment("test_context", stats)
        assert adj.adjustment_reason == "directional_bias"
        assert adj.fc_weight > ENSEMBLE_WEIGHT_FORWARD_CURVE

    def test_balanced_signals(self):
        stats = {"total": 50, "call": 25, "put": 25, "none": 0}
        adj = _make_adjustment("test_context", stats)
        assert adj.adjustment_reason == "base_weights"


# ── Test Data Classes ────────────────────────────────────────────────

class TestDataClasses:
    def test_weight_adjustment_to_dict(self):
        wa = WeightAdjustment(
            context="test", fc_weight=0.55, hist_weight=0.27, ml_weight=0.18,
            adjustment_reason="test", samples=100, confidence=0.8,
        )
        d = wa.to_dict()
        assert d["context"] == "test"
        assert d["samples"] == 100

    def test_constants(self):
        base_sum = ENSEMBLE_WEIGHT_FORWARD_CURVE + ENSEMBLE_WEIGHT_HISTORICAL + ENSEMBLE_WEIGHT_ML
        assert base_sum == pytest.approx(1.0)
        assert MAX_WEIGHT_DEVIATION > 0
        assert MAX_WEIGHT_DEVIATION <= 0.5
        assert len(T_RANGES) >= 3
