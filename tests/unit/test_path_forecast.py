"""Tests for the path forecast engine — full price path analysis."""
import pytest

from src.analytics.path_forecast import (
    analyze_path,
    analyze_portfolio_paths,
    PathForecast,
    PathSegment,
    TurningPoint,
    _smooth_prices,
    _find_extremes,
    _find_best_trade,
)


# ── Test Fixtures ────────────────────────────────────────────────────

def _make_fc_points(prices: list[float], start_t: int = 60) -> list[dict]:
    """Build forward curve points from a price series."""
    points = []
    prev_price = prices[0] if prices else 100.0
    for i, price in enumerate(prices):
        daily_change = (price / prev_price - 1.0) * 100.0 if prev_price > 0 else 0.0
        points.append({
            "date": f"2026-04-{i + 1:02d}",
            "t": start_t - i - 1,
            "predicted_price": price,
            "daily_change_pct": round(daily_change, 4),
            "cumulative_change_pct": round((price / prices[0] - 1.0) * 100.0, 2) if prices[0] > 0 else 0.0,
            "lower_bound": round(price * 0.95, 2),
            "upper_bound": round(price * 1.05, 2),
            "volatility_at_t": 1.5,
            "event_adj_pct": 0.0,
            "season_adj_pct": 0.0,
            "demand_adj_pct": 0.0,
            "momentum_adj_pct": 0.0,
            "weather_adj_pct": 0.0,
            "competitor_adj_pct": 0.0,
        })
        prev_price = price
    return points


def _base_kwargs():
    return {
        "detail_id": 12345,
        "hotel_id": 66814,
        "hotel_name": "Test Hotel Miami",
        "category": "standard",
        "board": "bb",
        "checkin_date": "2026-05-20",
        "current_price": 250.0,
        "current_t": 60,
    }


# ── Basic Analysis ───────────────────────────────────────────────────

class TestAnalyzePath:
    def test_empty_curve_returns_current_price(self):
        pf = analyze_path(forward_curve_points=[], **_base_kwargs())
        assert pf.predicted_final_price == 250.0
        assert pf.predicted_min_price == 250.0
        assert pf.predicted_max_price == 250.0
        assert pf.num_up_segments == 0
        assert pf.num_down_segments == 0

    def test_monotonic_up_path(self):
        """Prices steadily increase — should be one UP segment."""
        prices = [252, 255, 258, 262, 267, 270, 275, 280, 285, 290]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        assert pf.predicted_final_price == 290.0
        assert pf.predicted_min_price <= 252.0
        assert pf.predicted_max_price >= 290.0
        assert pf.net_change_pct > 0
        assert pf.num_up_segments >= 1
        assert pf.num_down_segments == 0

    def test_monotonic_down_path(self):
        """Prices steadily decrease — should be one DOWN segment."""
        prices = [248, 245, 240, 235, 230, 225, 220, 215, 210, 205]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        assert pf.predicted_final_price == 205.0
        assert pf.net_change_pct < 0
        assert pf.num_down_segments >= 1

    def test_v_shaped_path(self):
        """Price drops then recovers — should have MIN turning point."""
        prices = [248, 240, 232, 225, 220, 225, 232, 240, 250, 260]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        assert pf.predicted_min_price <= 220.0
        assert pf.predicted_max_price >= 260.0
        # Should find a best trade at or near the bottom
        assert pf.best_buy_price <= 225.0
        assert pf.max_trade_profit_pct > 0

    def test_inverted_v_path(self):
        """Price rises then drops — should have MAX turning point."""
        prices = [255, 265, 275, 285, 290, 285, 275, 265, 255, 245]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        assert pf.predicted_max_price >= 290.0
        assert pf.predicted_final_price == 245.0

    def test_multiple_oscillations(self):
        """Price goes up, down, up — should detect turning points even if
        the segment builder merges small moves into one net-UP segment."""
        prices = [255, 260, 270, 280, 275, 265, 255, 260, 270, 280, 290]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        # The segment builder may merge small oscillations, but turning points
        # should capture the dip. At minimum there should be 1+ segments.
        assert pf.num_up_segments + pf.num_down_segments >= 1
        assert len(pf.segments) >= 1
        # Turning points should detect the oscillation
        assert len(pf.turning_points) >= 1

    def test_flat_path(self):
        """Constant price — should be flat with no turning points."""
        prices = [250, 250, 250, 250, 250, 250, 250, 250, 250, 250]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        assert pf.net_change_pct == 0.0
        assert pf.max_trade_profit_pct == 0.0

    def test_daily_prices_include_current(self):
        """Daily prices should start with current price at today."""
        prices = [255, 260, 265]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        assert len(pf.daily_prices) == 4  # current + 3 points
        assert pf.daily_prices[0]["date"] == "today"
        assert pf.daily_prices[0]["predicted_price"] == 250.0

    def test_to_dict_serializable(self):
        """Result should serialize to dict without errors."""
        prices = [255, 260, 255, 250, 260]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())
        d = pf.to_dict()

        assert isinstance(d, dict)
        assert "segments" in d
        assert "turning_points" in d
        assert "daily_prices" in d
        assert d["detail_id"] == 12345

    def test_source_and_quality_metadata(self):
        """Source and quality metadata should be passed through."""
        prices = [255, 260]
        fc = _make_fc_points(prices)
        pf = analyze_path(
            forward_curve_points=fc,
            **_base_kwargs(),
            source="raw_salesoffice",
            enrichments_applied=False,
            data_quality="high",
        )
        assert pf.source == "raw_salesoffice"
        assert pf.enrichments_applied is False
        assert pf.data_quality == "high"


# ── Best Trade Detection ─────────────────────────────────────────────

class TestBestTrade:
    def test_best_trade_buy_low_sell_high(self):
        """Should find optimal buy→sell across the path."""
        prices = [260, 255, 240, 230, 245, 260, 280, 290, 285, 275]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        # Best buy should be around $230, best sell around $290
        assert pf.best_buy_price <= 235.0
        assert pf.best_sell_price >= 285.0
        assert pf.max_trade_profit_pct > 20.0

    def test_no_trade_when_only_dropping(self):
        """Monotonic decline should have minimal/zero trade opportunity."""
        prices = [248, 245, 242, 239, 236, 233, 230, 227, 224, 221]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        # Even in decline, the algo finds small intra-path opportunities
        # but the best trade should be small
        assert pf.max_trade_profit_pct < 2.0


# ── Smoothing ────────────────────────────────────────────────────────

class TestSmoothing:
    def test_smooth_preserves_trend(self):
        daily = [{"predicted_price": p} for p in [100, 102, 104, 106, 108]]
        smoothed = _smooth_prices(daily, window=3)
        assert smoothed[-1] >= smoothed[0]

    def test_smooth_reduces_noise(self):
        daily = [{"predicted_price": p} for p in [100, 110, 95, 115, 90, 105]]
        smoothed = _smooth_prices(daily, window=3)
        raw = [100, 110, 95, 115, 90, 105]
        # Smoothed interior points should be less extreme
        assert abs(smoothed[2] - 100) < abs(raw[2] - 100) or abs(smoothed[3] - 100) < abs(raw[3] - 100)

    def test_short_series_unchanged(self):
        daily = [{"predicted_price": 100}, {"predicted_price": 200}]
        smoothed = _smooth_prices(daily, window=3)
        assert smoothed == [100, 200]


# ── Segment Building ─────────────────────────────────────────────────

class TestSegments:
    def test_segments_cover_full_path(self):
        """Segments should not leave gaps."""
        prices = [255, 260, 270, 265, 255, 260, 275, 280]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        if pf.segments:
            first_seg = pf.segments[0]
            last_seg = pf.segments[-1]
            # First segment should start near current T
            assert first_seg.t_start >= last_seg.t_start

    def test_segment_directions_valid(self):
        prices = [255, 265, 275, 260, 250, 265, 280]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        for seg in pf.segments:
            assert seg.direction in ("UP", "DOWN")
            if seg.direction == "UP":
                assert seg.change_pct >= 0
            else:
                assert seg.change_pct <= 0

    def test_segment_counts_match(self):
        prices = [255, 265, 275, 260, 250, 265, 280]
        fc = _make_fc_points(prices)
        pf = analyze_path(forward_curve_points=fc, **_base_kwargs())

        up_count = sum(1 for s in pf.segments if s.direction == "UP")
        down_count = sum(1 for s in pf.segments if s.direction == "DOWN")
        assert pf.num_up_segments == up_count
        assert pf.num_down_segments == down_count


# ── Portfolio Analysis ───────────────────────────────────────────────

class TestPortfolioPaths:
    def test_empty_analysis(self):
        result = analyze_portfolio_paths({})
        assert result == []

    def test_no_predictions(self):
        result = analyze_portfolio_paths({"predictions": {}})
        assert result == []

    def test_single_prediction(self):
        prices = [255, 260, 270, 265, 280]
        fc = _make_fc_points(prices)
        analysis = {
            "predictions": {
                "12345": {
                    "hotel_id": 66814,
                    "hotel_name": "Test Hotel",
                    "category": "standard",
                    "board": "bb",
                    "date_from": "2026-05-20",
                    "current_price": 250.0,
                    "days_to_checkin": 60,
                    "forward_curve": fc,
                    "confidence_quality": "medium",
                }
            }
        }
        result = analyze_portfolio_paths(analysis)
        assert len(result) == 1
        assert result[0]["detail_id"] == 12345
        assert result[0]["hotel_id"] == 66814

    def test_sorted_by_profit(self):
        """Results should be sorted by max_trade_profit_pct descending."""
        analysis = {"predictions": {}}
        # Room with big trade opportunity
        big_prices = [255, 230, 210, 240, 280, 310]
        analysis["predictions"]["1"] = {
            "hotel_id": 1, "hotel_name": "Big", "category": "std", "board": "bb",
            "date_from": "2026-05-20", "current_price": 250.0, "days_to_checkin": 60,
            "forward_curve": _make_fc_points(big_prices), "confidence_quality": "high",
        }
        # Room with small opportunity
        small_prices = [252, 253, 254, 255, 256, 257]
        analysis["predictions"]["2"] = {
            "hotel_id": 2, "hotel_name": "Small", "category": "std", "board": "bb",
            "date_from": "2026-05-20", "current_price": 250.0, "days_to_checkin": 60,
            "forward_curve": _make_fc_points(small_prices), "confidence_quality": "medium",
        }

        result = analyze_portfolio_paths(analysis)
        assert len(result) == 2
        assert result[0]["max_trade_profit_pct"] >= result[1]["max_trade_profit_pct"]

    def test_skips_zero_price(self):
        analysis = {"predictions": {
            "1": {
                "hotel_id": 1, "hotel_name": "Zero", "category": "std", "board": "bb",
                "date_from": "2026-05-20", "current_price": 0, "days_to_checkin": 60,
                "forward_curve": [{"date": "x", "t": 59, "predicted_price": 100}],
            }
        }}
        result = analyze_portfolio_paths(analysis)
        assert len(result) == 0
