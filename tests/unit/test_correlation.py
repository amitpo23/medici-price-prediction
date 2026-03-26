"""Unit tests for correlation.py — Cross-Hotel Correlation Matrix."""
from __future__ import annotations

import pytest

from src.analytics.correlation import (
    CorrelationPair,
    CorrelationMatrix,
    compute_correlation_matrix,
    _pearson_correlation,
    _classify_correlation,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_analysis(predictions: dict) -> dict:
    return {"predictions": predictions}


def _make_pred(hotel_id, hotel_name, fc_changes):
    """Build a minimal prediction with forward_curve daily_change_pct."""
    fc = [{"daily_change_pct": c} for c in fc_changes]
    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "category": "standard",
        "forward_curve": fc,
    }


@pytest.fixture
def two_hotel_analysis():
    """Two hotels with perfectly correlated price changes."""
    return _make_analysis({
        "1001": _make_pred(1, "Hotel A", [0.5, 1.0, -0.5, 0.8, -0.2, 0.3, 1.1, -0.7, 0.4, 0.6]),
        "1002": _make_pred(1, "Hotel A", [0.6, 1.1, -0.4, 0.9, -0.1, 0.4, 1.2, -0.6, 0.5, 0.7]),  # same hotel, diff room
        "2001": _make_pred(2, "Hotel B", [0.5, 1.0, -0.5, 0.8, -0.2, 0.3, 1.1, -0.7, 0.4, 0.6]),
    })


@pytest.fixture
def three_hotel_analysis():
    """Three hotels: A≈B (correlated), C (inverse)."""
    return _make_analysis({
        "1001": _make_pred(1, "Hotel A", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        "2001": _make_pred(2, "Hotel B", [1.1, 2.2, 3.1, 4.3, 5.0, 6.2, 7.1, 8.3, 9.0, 10.1]),
        "3001": _make_pred(3, "Hotel C", [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]),
    })


# ── Test Pearson Correlation ─────────────────────────────────────────

class TestPearsonCorrelation:
    def test_perfect_positive(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        corr, n = _pearson_correlation(x, y)
        assert corr == pytest.approx(1.0, abs=0.001)
        assert n == 5

    def test_perfect_negative(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [-1.0, -2.0, -3.0, -4.0, -5.0]
        corr, n = _pearson_correlation(x, y)
        assert corr == pytest.approx(-1.0, abs=0.001)

    def test_no_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 5.0, 5.0, 5.0, 5.0]  # constant → zero variance
        corr, n = _pearson_correlation(x, y)
        assert corr == 0.0

    def test_insufficient_data(self):
        x = [1.0, 2.0]
        y = [3.0, 4.0]
        corr, n = _pearson_correlation(x, y)
        assert corr == 0.0
        assert n == 0

    def test_different_lengths(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        corr, n = _pearson_correlation(x, y)
        assert corr == pytest.approx(1.0, abs=0.001)
        assert n == 5


# ── Test Classify Correlation ────────────────────────────────────────

class TestClassifyCorrelation:
    def test_strong_positive(self):
        assert _classify_correlation(0.85) == "strong_positive"

    def test_strong_negative(self):
        assert _classify_correlation(-0.75) == "strong_negative"

    def test_moderate_positive(self):
        assert _classify_correlation(0.55) == "moderate_positive"

    def test_moderate_negative(self):
        assert _classify_correlation(-0.5) == "moderate_negative"

    def test_weak_positive(self):
        assert _classify_correlation(0.25) == "weak_positive"

    def test_weak_negative(self):
        assert _classify_correlation(-0.3) == "weak_negative"

    def test_negligible(self):
        assert _classify_correlation(0.05) == "negligible"
        assert _classify_correlation(-0.1) == "negligible"


# ── Test Correlation Matrix ──────────────────────────────────────────

class TestCorrelationMatrix:
    def test_empty_analysis(self):
        result = compute_correlation_matrix({})
        assert isinstance(result, CorrelationMatrix)
        assert result.n_hotels == 0
        assert result.matrix == []

    def test_single_hotel(self):
        analysis = _make_analysis({
            "1001": _make_pred(1, "Hotel A", [1, 2, 3, 4, 5]),
        })
        result = compute_correlation_matrix(analysis)
        assert result.n_hotels == 0  # need at least 2

    def test_two_hotels(self, two_hotel_analysis):
        result = compute_correlation_matrix(two_hotel_analysis, window_days=10)
        assert result.n_hotels == 2  # hotel 1 and 2
        assert len(result.matrix) == 2
        assert len(result.matrix[0]) == 2
        # Diagonal = 1.0
        assert result.matrix[0][0] == 1.0
        assert result.matrix[1][1] == 1.0
        # Symmetric
        assert result.matrix[0][1] == result.matrix[1][0]

    def test_three_hotels_ranking(self, three_hotel_analysis):
        result = compute_correlation_matrix(three_hotel_analysis, window_days=10)
        assert result.n_hotels == 3
        assert len(result.strongest_positive) > 0
        assert len(result.strongest_negative) > 0
        # A-B should be strong positive, A-C and B-C strong negative
        top_pos = result.strongest_positive[0]
        assert top_pos.correlation > 0.9
        top_neg = result.strongest_negative[0]
        assert top_neg.correlation < -0.9

    def test_hotel_names(self, three_hotel_analysis):
        result = compute_correlation_matrix(three_hotel_analysis, window_days=10)
        assert "Hotel A" in result.hotel_names
        assert "Hotel B" in result.hotel_names
        assert "Hotel C" in result.hotel_names

    def test_timestamp(self, two_hotel_analysis):
        result = compute_correlation_matrix(two_hotel_analysis, window_days=10)
        assert result.timestamp.endswith("Z")

    def test_category_matrix(self, two_hotel_analysis):
        result = compute_correlation_matrix(two_hotel_analysis, window_days=10)
        # All rooms are "standard" so only 1 category → empty
        assert result.category_matrix == {} or len(result.category_matrix) <= 1

    def test_multi_category(self):
        analysis = _make_analysis({
            "1001": {
                "hotel_id": 1, "hotel_name": "H1", "category": "standard",
                "forward_curve": [{"daily_change_pct": c} for c in [1, 2, 3, 4, 5, 6, 7]],
            },
            "2001": {
                "hotel_id": 2, "hotel_name": "H2", "category": "deluxe",
                "forward_curve": [{"daily_change_pct": c} for c in [1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1]],
            },
        })
        result = compute_correlation_matrix(analysis, window_days=7)
        assert "standard" in result.category_matrix or "deluxe" in result.category_matrix

    def test_to_dict(self, three_hotel_analysis):
        result = compute_correlation_matrix(three_hotel_analysis, window_days=10)
        d = result.to_dict()
        assert "matrix" in d
        assert "strongest_positive" in d
        assert "strongest_negative" in d
        assert "hotel_ids" in d
        assert "n_hotels" in d

    def test_pair_to_dict(self):
        pair = CorrelationPair(
            hotel_a_id=1, hotel_a_name="A",
            hotel_b_id=2, hotel_b_name="B",
            correlation=0.8567, samples=10,
            relationship="strong_positive",
        )
        d = pair.to_dict()
        assert d["correlation"] == 0.8567
        assert d["samples"] == 10

    def test_no_fc_data(self):
        analysis = _make_analysis({
            "1001": {"hotel_id": 1, "hotel_name": "H1", "forward_curve": []},
            "2001": {"hotel_id": 2, "hotel_name": "H2", "forward_curve": []},
        })
        result = compute_correlation_matrix(analysis)
        # Empty FC → no series data → fewer than 2 hotels with data
        assert isinstance(result, CorrelationMatrix)
