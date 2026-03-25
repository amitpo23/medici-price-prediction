"""Unit tests for attribution.py — Factor Attribution Analysis."""
from __future__ import annotations

import pytest

from src.analytics.attribution import (
    compute_attribution,
    compute_hotel_attribution,
    compute_signal_attribution,
    AttributionResult,
    FactorAttribution,
    ENRICHMENT_FACTORS,
    _extract_avg_adjustments,
    _build_factor_list,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_fc_points(n=5, event=0.1, season=0.05, demand=0.02,
                    weather=-0.01, competitor=0.03, momentum=0.04,
                    dz=0.02, rebuy=0.01, sv=0.005):
    """Create N forward curve points with given enrichment values."""
    return [
        {
            "predicted_price": 200 + i,
            "volatility_at_t": 1.5,
            "event_adj_pct": event,
            "season_adj_pct": season,
            "demand_adj_pct": demand,
            "weather_adj_pct": weather,
            "competitor_adj_pct": competitor,
            "momentum_adj_pct": momentum,
            "demand_zone_adj_pct": dz,
            "rebuy_signal_adj_pct": rebuy,
            "search_volume_adj_pct": sv,
        }
        for i in range(n)
    ]


def _make_analysis(n_rooms=10, hotel_ids=None, signals=None):
    """Create a fake analysis dict with predictions."""
    if hotel_ids is None:
        hotel_ids = [1] * n_rooms
    if signals is None:
        signals = ["CALL"] * (n_rooms // 2) + ["PUT"] * (n_rooms - n_rooms // 2)

    predictions = {}
    for i in range(n_rooms):
        detail_id = str(100 + i)
        predictions[detail_id] = {
            "hotel_id": hotel_ids[i] if i < len(hotel_ids) else 1,
            "current_price": 200.0,
            "option_signal": signals[i] if i < len(signals) else "NONE",
            "forward_curve": _make_fc_points(),
        }
    return {"predictions": predictions}


# ── Test Core Attribution ────────────────────────────────────────────

class TestComputeAttribution:
    def test_basic(self):
        analysis = _make_analysis(5)
        result = compute_attribution(analysis)
        assert isinstance(result, AttributionResult)
        assert result.n_rooms == 5
        assert len(result.factors) == len(ENRICHMENT_FACTORS)
        assert result.timestamp

    def test_empty_analysis(self):
        result = compute_attribution({})
        assert result.n_rooms == 0
        assert result.factors == []

    def test_empty_predictions(self):
        result = compute_attribution({"predictions": {}})
        assert result.n_rooms == 0

    def test_dominant_factor(self):
        analysis = _make_analysis(5)
        result = compute_attribution(analysis)
        assert result.dominant_factor  # not empty
        # Event has the highest adj (0.1), so should be dominant
        assert result.dominant_factor == "event"
        assert result.dominant_contribution_pct > 0

    def test_total_enrichment_impact(self):
        analysis = _make_analysis(5)
        result = compute_attribution(analysis)
        # Sum of all avg contributions
        expected = sum(f.avg_contribution_pct for f in result.factors)
        assert abs(result.total_enrichment_impact_pct - expected) < 0.001

    def test_factor_samples(self):
        analysis = _make_analysis(10)
        result = compute_attribution(analysis)
        for f in result.factors:
            assert f.samples == 10

    def test_call_put_split(self):
        analysis = _make_analysis(10, signals=["CALL"] * 6 + ["PUT"] * 4)
        result = compute_attribution(analysis)
        # Should have both call and put attribution
        assert len(result.call_attribution) > 0
        assert len(result.put_attribution) > 0

    def test_filter_by_hotel(self):
        analysis = _make_analysis(10, hotel_ids=[1]*5 + [2]*5)
        result = compute_attribution(analysis, hotel_id=1)
        assert result.n_rooms == 5

    def test_skips_zero_price(self):
        analysis = {"predictions": {
            "100": {"hotel_id": 1, "current_price": 0, "forward_curve": _make_fc_points()},
            "101": {"hotel_id": 1, "current_price": 200, "forward_curve": _make_fc_points()},
        }}
        result = compute_attribution(analysis)
        assert result.n_rooms == 1

    def test_skips_no_fc(self):
        analysis = {"predictions": {
            "100": {"hotel_id": 1, "current_price": 200, "forward_curve": []},
        }}
        result = compute_attribution(analysis)
        assert result.n_rooms == 0


class TestHotelAttribution:
    def test_hotel_filter(self):
        analysis = _make_analysis(10, hotel_ids=[1]*5 + [2]*5)
        result = compute_hotel_attribution(analysis, hotel_id=2)
        assert result.n_rooms == 5


class TestSignalAttribution:
    def test_comparison(self):
        analysis = _make_analysis(10, signals=["CALL"]*5 + ["PUT"]*5)
        result = compute_signal_attribution(analysis)
        assert "comparison" in result
        assert len(result["comparison"]) == len(ENRICHMENT_FACTORS)
        for comp in result["comparison"]:
            assert "factor" in comp
            assert "favors" in comp
            assert comp["favors"] in ("CALL", "PUT", "neutral")


# ── Test Internal Helpers ────────────────────────────────────────────

class TestExtractAdjustments:
    def test_basic(self):
        fc = _make_fc_points(3, event=0.3, season=0.0)
        adj = _extract_avg_adjustments(fc)
        assert abs(adj["event"] - 0.3) < 0.001
        assert adj["seasonality"] == 0.0

    def test_empty(self):
        assert _extract_avg_adjustments([]) == {}

    def test_averaging(self):
        fc = [
            {"event_adj_pct": 0.1, "season_adj_pct": 0.2},
            {"event_adj_pct": 0.3, "season_adj_pct": 0.0},
        ]
        adj = _extract_avg_adjustments(fc)
        assert abs(adj["event"] - 0.2) < 0.001
        assert abs(adj["seasonality"] - 0.1) < 0.001


class TestBuildFactorList:
    def test_basic(self):
        data = {"event": [0.1, 0.2, 0.3], "weather": [-0.05, -0.1]}
        factors = _build_factor_list(data)
        assert len(factors) == 2
        # Sorted by abs contribution
        assert factors[0].factor == "event"  # higher avg

    def test_empty_values(self):
        data = {"event": []}
        factors = _build_factor_list(data)
        assert factors[0].samples == 0

    def test_direction_bullish(self):
        data = {"event": [0.1, 0.2, 0.3, 0.4]}  # all positive
        factors = _build_factor_list(data)
        assert factors[0].direction == "bullish"

    def test_direction_bearish(self):
        data = {"weather": [-0.1, -0.2, -0.3, -0.4]}  # all negative
        factors = _build_factor_list(data)
        assert factors[0].direction == "bearish"


class TestToDict:
    def test_attribution_result_to_dict(self):
        result = compute_attribution(_make_analysis(5))
        d = result.to_dict()
        assert "factors" in d
        assert "dominant_factor" in d
        assert isinstance(d["factors"], list)

    def test_factor_to_dict(self):
        f = FactorAttribution(factor="event", avg_contribution_pct=0.123456)
        d = f.to_dict()
        assert d["factor"] == "event"
        assert isinstance(d["avg_contribution_pct"], float)
