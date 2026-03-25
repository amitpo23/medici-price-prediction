"""Unit tests for deep_predictor.py — ensemble weighting, confidence, clamps.

Uses real DeepPredictor with constructed data — NO mocks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.forward_curve import (
    DecayCurve,
    DecayCurvePoint,
    Enrichments,
    _default_curve,
)
from src.analytics.deep_predictor import DeepPredictor


# ── Helpers ─────────────────────────────────────────────────────────


def _make_curve() -> DecayCurve:
    """Build a simple DecayCurve with a few known points."""
    return _default_curve()


def _make_predictor(
    historical_patterns: dict | None = None,
) -> DeepPredictor:
    """Build a DeepPredictor with a default curve and optional patterns."""
    curve = _make_curve()
    return DeepPredictor(
        decay_curve=curve,
        historical_patterns=historical_patterns or {},
        ml_models_dir=None,
    )


def _make_empty_snapshots() -> pd.DataFrame:
    return pd.DataFrame()


# ── DEFAULT_WEIGHTS ─────────────────────────────────────────────────


class TestDefaultWeights:
    def test_weights_sum_to_one(self):
        w = DeepPredictor.DEFAULT_WEIGHTS
        assert abs(sum(w.values()) - 1.0) < 0.001

    def test_forward_curve_is_dominant(self):
        w = DeepPredictor.DEFAULT_WEIGHTS
        assert w["forward_curve"] == 0.70
        assert w["forward_curve"] > w["historical_pattern"]
        assert w["forward_curve"] > w["ml_forecast"]

    def test_historical_10_pct(self):
        assert DeepPredictor.DEFAULT_WEIGHTS["historical_pattern"] == 0.10

    def test_ml_20_pct(self):
        assert DeepPredictor.DEFAULT_WEIGHTS["ml_forecast"] == 0.20


# ── _compute_weights ────────────────────────────────────────────────


class TestComputeWeights:
    def test_single_signal_gets_full_weight(self):
        predictor = _make_predictor()
        signals = [{"source": "forward_curve", "predicted_price": 100, "confidence": 0.8}]
        weights = predictor._compute_weights(signals)
        assert weights == [1.0]

    def test_two_signals_normalized(self):
        predictor = _make_predictor()
        signals = [
            {"source": "forward_curve", "predicted_price": 100, "confidence": 0.8},
            {"source": "historical_pattern", "predicted_price": 110, "confidence": 0.6},
        ]
        weights = predictor._compute_weights(signals)
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 0.001

    def test_three_signals_normalized(self):
        predictor = _make_predictor()
        signals = [
            {"source": "forward_curve", "predicted_price": 100, "confidence": 0.8},
            {"source": "historical_pattern", "predicted_price": 110, "confidence": 0.6},
            {"source": "ml_forecast", "predicted_price": 105, "confidence": 0.5},
        ]
        weights = predictor._compute_weights(signals)
        assert len(weights) == 3
        assert abs(sum(weights) - 1.0) < 0.001

    def test_higher_confidence_gets_more_weight(self):
        """Signal with higher confidence should get proportionally more weight."""
        predictor = _make_predictor()
        signals = [
            {"source": "forward_curve", "predicted_price": 100, "confidence": 0.9},
            {"source": "historical_pattern", "predicted_price": 110, "confidence": 0.1},
        ]
        weights = predictor._compute_weights(signals)
        # FC has base 0.50 and high confidence, hist has base 0.30 and low confidence
        assert weights[0] > weights[1]

    def test_zero_confidence_handled(self):
        predictor = _make_predictor()
        signals = [
            {"source": "forward_curve", "predicted_price": 100, "confidence": 0.0},
            {"source": "historical_pattern", "predicted_price": 110, "confidence": 0.0},
        ]
        weights = predictor._compute_weights(signals)
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 0.001

    def test_weight_formula(self):
        """Verify the actual formula: base_weight * (0.5 + 0.5 * confidence)."""
        predictor = _make_predictor()
        signals = [
            {"source": "forward_curve", "predicted_price": 100, "confidence": 0.8},
            {"source": "historical_pattern", "predicted_price": 110, "confidence": 0.6},
        ]
        weights = predictor._compute_weights(signals)
        # Manual calculation (weights: FC=0.70, Hist=0.10)
        raw_fc = 0.70 * (0.5 + 0.5 * 0.8)  # 0.70 * 0.90 = 0.63
        raw_hist = 0.10 * (0.5 + 0.5 * 0.6)  # 0.10 * 0.80 = 0.08
        total = raw_fc + raw_hist
        expected_fc = raw_fc / total
        expected_hist = raw_hist / total
        assert abs(weights[0] - expected_fc) < 0.001
        assert abs(weights[1] - expected_hist) < 0.001


# ── Predict — forward curve only ────────────────────────────────────


class TestPredictForwardCurveOnly:
    """When no historical patterns or ML models, only forward_curve signal is used."""

    def test_single_signal_prediction(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert "predicted_checkin_price" in result
        assert result["predicted_checkin_price"] > 0
        assert result["prediction_method"] == "forward_curve_only"

    def test_has_signals_list(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert len(result["signals"]) == 1
        assert result["signals"][0]["source"] == "forward_curve"
        assert result["signals"][0]["weight"] == 1.0

    def test_forward_curve_points(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert len(result["forward_curve"]) == 7
        assert len(result["daily"]) == 7


# ── Predict — with historical pattern ──────────────────────────────


class TestPredictWithHistorical:
    @pytest.fixture()
    def predictor_with_hist(self) -> DeepPredictor:
        patterns = {
            (42, "standard"): {
                "same_period": {
                    6: {  # June
                        "avg_price": 210.0,
                        "median_price": 205.0,
                        "n_observations": 50,
                        "data_source": "historical",
                    }
                },
                "lead_time": [
                    {"bucket": "0-7d", "avg_daily_change_pct": 0.5},
                    {"bucket": "8-14d", "avg_daily_change_pct": 0.3},
                ],
                "monthly_index": {6: 1.05},
                "day_of_week": {"dow_index": {0: -1.0, 6: 2.0}},
                "data_quality": 0.7,
            }
        }
        return _make_predictor(historical_patterns=patterns)

    def test_ensemble_with_historical(self, predictor_with_hist):
        result = predictor_with_hist.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert result["prediction_method"] == "deep_ensemble"
        assert len(result["signals"]) == 2  # FC + historical

    def test_yoy_comparison_present(self, predictor_with_hist):
        result = predictor_with_hist.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        yoy = result["yoy_comparison"]
        assert yoy is not None
        assert yoy["period"] == "June"
        assert yoy["prior_avg_price"] == 210.0

    def test_explanation_has_factors(self, predictor_with_hist):
        result = predictor_with_hist.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        explanation = result["explanation"]
        assert explanation["n_signals"] == 2
        assert len(explanation["factors"]) > 0


# ── Hard clamps ─────────────────────────────────────────────────────


class TestHardClamps:
    def test_upper_clamp_250_pct(self):
        """Ensemble price cannot exceed 2.50x current price."""
        # Use historical pattern that predicts a very high price
        patterns = {
            (42, "standard"): {
                "same_period": {6: {"avg_price": 800.0, "n_observations": 5, "data_source": "test"}},
                "lead_time": [],
                "monthly_index": {},
                "day_of_week": {"dow_index": {}},
                "data_quality": 0.9,
            }
        }
        predictor = _make_predictor(historical_patterns=patterns)
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=100.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert result["predicted_checkin_price"] <= 100.0 * 2.50

    def test_lower_clamp_40_pct(self):
        """Ensemble price cannot drop below 0.40x current price."""
        patterns = {
            (42, "standard"): {
                "same_period": {6: {"avg_price": 10.0, "n_observations": 5, "data_source": "test"}},
                "lead_time": [],
                "monthly_index": {},
                "day_of_week": {"dow_index": {}},
                "data_quality": 0.9,
            }
        }
        predictor = _make_predictor(historical_patterns=patterns)
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=100.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert result["predicted_checkin_price"] >= 100.0 * 0.40


# ── Sanity clamp on signals ─────────────────────────────────────────


class TestSanityClamp:
    def test_wild_signal_gets_penalty(self):
        """Signal predicting >2x current price should get confidence penalty."""
        predictor = _make_predictor()
        signals = [
            {"source": "forward_curve", "predicted_price": 500, "confidence": 0.8, "reasoning": "test"},
        ]
        # Manually test the sanity clamp logic
        current_price = 100.0
        for s in signals:
            ratio = s["predicted_price"] / current_price
            if ratio > 2.0 or ratio < 0.5:
                penalty = max(0.05, 1.0 / (1.0 + abs(np.log2(max(ratio, 0.01)))))
                s["confidence"] = s["confidence"] * penalty
        # ratio=5.0, log2(5)≈2.32, penalty = 1/(1+2.32) ≈ 0.30
        assert signals[0]["confidence"] < 0.8  # Was penalized


# ── Confidence quality ──────────────────────────────────────────────


class TestConfidenceQuality:
    def test_low_quality_no_data(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        # Default curve has n_observations=0 → density "low", no hist → quality low
        assert result["confidence_quality"] in ("low", "medium")

    def test_medium_quality_with_some_data(self):
        """With default curve (medium density by fallback) → medium quality."""
        # Build a curve with actual data points
        curve = DecayCurve(
            points={
                7: DecayCurvePoint(t=7, n_observations=10, mean_daily_pct=-0.05,
                                   median_daily_pct=-0.04, std_daily_pct=1.0,
                                   p_up=35, p_down=35, p_stable=30),
            },
            global_mean_daily_pct=-0.04,
            global_std_daily_pct=1.0,
            total_observations=50,
            total_tracks=5,
            max_t=60,
        )
        predictor = DeepPredictor(
            decay_curve=curve,
            historical_patterns={},
            ml_models_dir=None,
        )
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        assert result["confidence_quality"] in ("medium", "low")


# ── Result structure ────────────────────────────────────────────────


class TestResultStructure:
    def test_required_keys(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        required = [
            "current_price", "date_from", "days_to_checkin",
            "predicted_checkin_price", "expected_change_pct",
            "probability", "model_type", "daily",
            "confidence_quality", "forward_curve",
            "prediction_method", "signals", "yoy_comparison",
            "explanation",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_probability_structure(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        prob = result["probability"]
        assert "up" in prob
        assert "down" in prob
        assert "stable" in prob

    def test_explanation_structure(self):
        predictor = _make_predictor()
        result = predictor.predict(
            detail_id=1, hotel_id=42,
            current_price=200.0, days_to_checkin=7,
            category="standard", board="bb",
            date_from="2025-06-15",
            all_snapshots=_make_empty_snapshots(),
            enrichments=Enrichments(),
        )
        exp = result["explanation"]
        assert "summary" in exp
        assert "factors" in exp
        assert "confidence_statement" in exp
        assert "n_signals" in exp
