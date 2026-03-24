"""Tests for arbitrage engine — T-timeline and buy/sell point identification."""
from __future__ import annotations

import pytest

from src.analytics.arbitrage_engine import (
    compute_arbitrage_timeline,
    _classify_zone,
    _build_timeline,
    _find_buy_sell_points,
    _build_zones,
    MIN_ARBITRAGE_USD,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _make_fc(prices_and_t: list) -> list:
    """Build a forward curve from [(t, price), ...] pairs.

    Points should be ordered T descending (far future first).
    """
    return [
        {"date": f"2026-05-{i + 1:02d}", "t": t, "predicted_price": price}
        for i, (t, price) in enumerate(prices_and_t)
    ]


def _make_pred(fc_data: list, current_price: float = 200.0, t: int = 60) -> dict:
    """Build a minimal prediction dict."""
    return {
        "detail_id": 12345,
        "hotel_name": "Test Hotel",
        "current_price": current_price,
        "days_to_checkin": t,
        "forward_curve": _make_fc(fc_data),
    }


# ── Empty / minimal cases ─────────────────────────────────────────────

class TestEmptyFC:
    def test_empty_fc_returns_no_arbitrage(self):
        pred = {"detail_id": 1, "hotel_name": "H", "current_price": 100, "days_to_checkin": 30, "forward_curve": []}
        result = compute_arbitrage_timeline(pred)
        assert result["timeline"] == []
        assert result["buy_point"] is None
        assert result["sell_point"] is None
        assert result["arbitrage"]["feasible"] is False

    def test_none_fc_returns_no_arbitrage(self):
        pred = {"detail_id": 1, "hotel_name": "H", "current_price": 100, "days_to_checkin": 30}
        result = compute_arbitrage_timeline(pred)
        assert result["timeline"] == []
        assert result["arbitrage"]["feasible"] is False

    def test_single_point_fc_no_arbitrage(self):
        pred = _make_pred([(10, 200.0)], current_price=200.0)
        result = compute_arbitrage_timeline(pred)
        assert len(result["timeline"]) == 1
        assert result["arbitrage"]["feasible"] is False


# ── Monotonically rising FC ───────────────────────────────────────────

class TestRisingFC:
    def test_rising_fc_buy_at_start_sell_at_end(self):
        """Monotonically rising: buy at T=max (earliest), sell at T=min (latest)."""
        fc = [(60, 180), (50, 200), (40, 220), (30, 240), (20, 260), (10, 280)]
        pred = _make_pred(fc, current_price=180.0, t=60)
        result = compute_arbitrage_timeline(pred)

        assert result["buy_point"]["t_days"] == 60
        assert result["buy_point"]["price"] == 180
        assert result["sell_point"]["t_days"] == 10
        assert result["sell_point"]["price"] == 280
        assert result["arbitrage"]["feasible"] is True
        assert result["arbitrage"]["profit_usd"] == 100.0

    def test_rising_fc_zones_are_green(self):
        fc = [(30, 100), (20, 120), (10, 140)]
        pred = _make_pred(fc, current_price=90.0)
        result = compute_arbitrage_timeline(pred)
        # All rising > 1% so all green
        for pt in result["timeline"]:
            assert pt["zone"] == "green"


# ── Monotonically falling FC ──────────────────────────────────────────

class TestFallingFC:
    def test_falling_fc_no_feasible_arbitrage(self):
        """Monotonically falling: buy at last point, no sell point after."""
        fc = [(60, 300), (50, 280), (40, 260), (30, 240), (20, 220), (10, 200)]
        pred = _make_pred(fc, current_price=310.0, t=60)
        result = compute_arbitrage_timeline(pred)

        # Buy at lowest (T=10, price=200)
        assert result["buy_point"]["t_days"] == 10
        assert result["buy_point"]["price"] == 200
        # No sell point after the last point
        assert result["sell_point"] is None
        assert result["arbitrage"]["feasible"] is False

    def test_falling_fc_zones_are_red(self):
        fc = [(30, 300), (20, 270), (10, 240)]
        pred = _make_pred(fc, current_price=310.0)
        result = compute_arbitrage_timeline(pred)
        for pt in result["timeline"]:
            assert pt["zone"] == "red"


# ── V-shape FC ────────────────────────────────────────────────────────

class TestVShapeFC:
    def test_v_shape_buy_at_bottom_sell_at_peak(self):
        """V-shape: drops then rises. Buy at bottom, sell at peak after."""
        fc = [(50, 250), (40, 220), (30, 185), (20, 210), (10, 270)]
        pred = _make_pred(fc, current_price=260.0, t=50)
        result = compute_arbitrage_timeline(pred)

        assert result["buy_point"]["price"] == 185
        assert result["buy_point"]["t_days"] == 30
        assert result["sell_point"]["price"] == 270
        assert result["sell_point"]["t_days"] == 10
        assert result["arbitrage"]["feasible"] is True
        assert result["arbitrage"]["profit_usd"] == 85.0

    def test_v_shape_profit_pct(self):
        fc = [(40, 200), (30, 100), (20, 150), (10, 200)]
        pred = _make_pred(fc, current_price=200.0, t=40)
        result = compute_arbitrage_timeline(pred)
        assert result["arbitrage"]["profit_pct"] == 100.0  # (200-100)/100 * 100


# ── Inverted V (rise then drop) ───────────────────────────────────────

class TestInvertedV:
    def test_inverted_v_buy_at_start_sell_at_peak(self):
        """Inverted V: rises then falls. Buy at start (lowest), sell at peak."""
        fc = [(50, 200), (40, 240), (30, 280), (20, 250), (10, 210)]
        pred = _make_pred(fc, current_price=190.0, t=50)
        result = compute_arbitrage_timeline(pred)

        assert result["buy_point"]["price"] == 200
        assert result["buy_point"]["t_days"] == 50
        assert result["sell_point"]["price"] == 280
        assert result["sell_point"]["t_days"] == 30
        assert result["arbitrage"]["feasible"] is True
        assert result["arbitrage"]["profit_usd"] == 80.0


# ── Multiple peaks/valleys ────────────────────────────────────────────

class TestMultiplePeaksValleys:
    def test_picks_best_arbitrage_pair(self):
        """Multiple dips and peaks — should find global min and best sell after it."""
        fc = [(60, 220), (50, 190), (40, 250), (30, 170), (20, 260), (10, 230)]
        pred = _make_pred(fc, current_price=220.0, t=60)
        result = compute_arbitrage_timeline(pred)

        # Global min is 170 at T=30
        assert result["buy_point"]["price"] == 170
        assert result["buy_point"]["t_days"] == 30
        # Best sell after T=30 is 260 at T=20
        assert result["sell_point"]["price"] == 260
        assert result["sell_point"]["t_days"] == 20
        assert result["arbitrage"]["profit_usd"] == 90.0
        assert result["arbitrage"]["feasible"] is True


# ── Flat FC ────────────────────────────────────────────────────────────

class TestFlatFC:
    def test_flat_fc_no_significant_arbitrage(self):
        """Flat prices — profit below threshold."""
        fc = [(40, 200.0), (30, 200.2), (20, 200.1), (10, 200.3)]
        pred = _make_pred(fc, current_price=200.0, t=40)
        result = compute_arbitrage_timeline(pred)

        # Profit is tiny (0.3 at most)
        assert result["arbitrage"]["profit_usd"] < MIN_ARBITRAGE_USD or not result["arbitrage"]["feasible"]

    def test_flat_fc_zones_are_gray(self):
        fc = [(30, 200.0), (20, 200.1), (10, 200.0)]
        pred = _make_pred(fc, current_price=200.0)
        result = compute_arbitrage_timeline(pred)
        for pt in result["timeline"]:
            assert pt["zone"] == "gray"


# ── Feasibility ───────────────────────────────────────────────────────

class TestFeasibility:
    def test_buy_must_be_before_sell_in_time(self):
        """buy_t > sell_t means buy happens earlier (more days to checkin)."""
        fc = [(50, 250), (40, 200), (30, 180), (20, 220), (10, 190)]
        pred = _make_pred(fc, current_price=260.0, t=50)
        result = compute_arbitrage_timeline(pred)

        buy_t = result["arbitrage"]["buy_t"]
        sell_t = result["arbitrage"]["sell_t"]
        if result["arbitrage"]["feasible"]:
            assert buy_t > sell_t


# ── Timeline completeness ─────────────────────────────────────────────

class TestTimelineCompleteness:
    def test_timeline_includes_all_fc_points(self):
        fc = [(50, 200), (40, 210), (30, 220), (20, 215), (10, 225)]
        pred = _make_pred(fc, current_price=195.0, t=50)
        result = compute_arbitrage_timeline(pred)
        assert len(result["timeline"]) == len(fc)

    def test_timeline_has_correct_fields(self):
        fc = [(30, 200), (20, 210), (10, 220)]
        pred = _make_pred(fc, current_price=195.0)
        result = compute_arbitrage_timeline(pred)
        for pt in result["timeline"]:
            assert "date" in pt
            assert "t_days" in pt
            assert "predicted_price" in pt
            assert "zone" in pt


# ── Zone building ──────────────────────────────────────────────────────

class TestZones:
    def test_zones_group_consecutive_same_color(self):
        fc = [(50, 200), (40, 220), (30, 240), (20, 210), (10, 180)]
        pred = _make_pred(fc, current_price=190.0)
        result = compute_arbitrage_timeline(pred)
        zones = result["zones"]
        # Should have at least 2 zones (rising then falling)
        assert len(zones) >= 2
        # Each zone has required fields
        for z in zones:
            assert "start_t" in z
            assert "end_t" in z
            assert "signal" in z
            assert z["signal"] in ("CALL", "PUT", "NEUTRAL")
            assert "reason" in z

    def test_single_zone_when_all_same(self):
        fc = [(30, 200), (20, 220), (10, 240)]
        pred = _make_pred(fc, current_price=190.0)
        result = compute_arbitrage_timeline(pred)
        # All rising → single CALL zone
        assert len(result["zones"]) == 1
        assert result["zones"][0]["signal"] == "CALL"


# ── Zone classifier unit tests ────────────────────────────────────────

class TestClassifyZone:
    def test_rising_is_green(self):
        assert _classify_zone(100, 102) == "green"

    def test_falling_is_red(self):
        assert _classify_zone(100, 98) == "red"

    def test_flat_is_gray(self):
        assert _classify_zone(100, 100.5) == "gray"

    def test_zero_prev_price_is_gray(self):
        assert _classify_zone(0, 100) == "gray"


# ── Profit calculation ─────────────────────────────────────────────────

class TestProfitCalculation:
    def test_profit_usd_correct(self):
        fc = [(40, 150), (30, 100), (20, 200), (10, 180)]
        pred = _make_pred(fc, current_price=160.0, t=40)
        result = compute_arbitrage_timeline(pred)
        arb = result["arbitrage"]
        assert arb["profit_usd"] == arb["sell_price"] - arb["buy_price"]

    def test_profit_pct_correct(self):
        fc = [(30, 100), (20, 200), (10, 150)]
        pred = _make_pred(fc, current_price=110.0, t=30)
        result = compute_arbitrage_timeline(pred)
        arb = result["arbitrage"]
        if arb["buy_price"] > 0:
            expected_pct = (arb["sell_price"] - arb["buy_price"]) / arb["buy_price"] * 100
            assert abs(arb["profit_pct"] - expected_pct) < 0.01


# ── Metadata fields ───────────────────────────────────────────────────

class TestMetadata:
    def test_result_includes_hotel_info(self):
        pred = _make_pred([(30, 200), (20, 210), (10, 220)], current_price=195.0, t=30)
        result = compute_arbitrage_timeline(pred)
        assert result["detail_id"] == 12345
        assert result["hotel_name"] == "Test Hotel"
        assert result["current_price"] == 195.0
        assert result["T"] == 30

    def test_zone_avg_and_adr_passed_through(self):
        pred = _make_pred([(30, 200)], current_price=195.0)
        result = compute_arbitrage_timeline(pred, zone_avg=220.5, official_adr=250.0)
        assert result["zone_avg"] == 220.5
        assert result["official_adr"] == 250.0
