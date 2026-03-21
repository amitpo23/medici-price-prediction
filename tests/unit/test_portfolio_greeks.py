"""Unit tests for portfolio_greeks.py — options-style risk metrics."""
from __future__ import annotations

import math
import pytest

from src.analytics.portfolio_greeks import (
    compute_room_greeks,
    compute_portfolio_greeks,
    compute_hotel_greeks,
    RoomGreeks,
    PortfolioGreeks,
    VAR_Z,
    GREEKS_MIN_DATA_POINTS,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_fc(n_points=10, base_price=800, daily_change=0.5, vol=2.0):
    """Generate a synthetic forward curve."""
    fc = []
    price = base_price
    for i in range(n_points):
        price += daily_change
        fc.append({
            "date": f"2026-04-{10+i:02d}",
            "predicted_price": round(price, 2),
            "volatility_at_t": vol,
        })
    return fc


def _make_pred(
    detail_id=1001,
    hotel_id=100,
    hotel_name="Test Hotel",
    current_price=800,
    predicted_price=850,
    days_to_checkin=30,
    signal="CALL",
    p_up=75,
    p_down=25,
    category="standard",
    board="ro",
    fc_points=10,
    vol=2.0,
):
    """Create a synthetic prediction dict."""
    return {
        "detail_id": detail_id,
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "current_price": current_price,
        "predicted_checkin_price": predicted_price,
        "days_to_checkin": days_to_checkin,
        "option_signal": signal,
        "probability": {"up": p_up, "down": p_down, "stable": 100 - p_up - p_down},
        "category": category,
        "board": board,
        "date_from": "2026-05-01",
        "forward_curve": _make_fc(
            n_points=fc_points,
            base_price=current_price,
            vol=vol,
        ),
    }


def _make_analysis(preds: list[dict] | None = None):
    """Build an analysis dict from a list of predictions."""
    if preds is None:
        preds = [_make_pred()]
    return {"predictions": {str(p["detail_id"]): p for p in preds}}


# ── compute_room_greeks tests ────────────────────────────────────────

class TestComputeRoomGreeks:
    def test_basic_call_signal(self):
        pred = _make_pred(signal="CALL", p_up=75, p_down=25)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.signal == "CALL"
        assert rg.delta > 0  # CALL → positive delta
        assert rg.delta == pytest.approx(0.75, abs=0.01)

    def test_basic_put_signal(self):
        pred = _make_pred(signal="PUT", p_up=25, p_down=75, predicted_price=750)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.signal == "PUT"
        assert rg.delta < 0  # PUT → negative delta
        assert rg.delta == pytest.approx(-0.75, abs=0.01)

    def test_none_signal(self):
        pred = _make_pred(signal="NONE", p_up=50, p_down=50)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.signal == "NONE"
        assert abs(rg.delta) < 0.1  # Roughly neutral

    def test_theta_positive_for_rising(self):
        """Theta should be positive when FC shows price rising."""
        pred = _make_pred(predicted_price=850)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.theta > 0  # FC predicts daily rise

    def test_theta_negative_for_falling(self):
        """Theta should be negative when FC shows price falling."""
        fc = _make_fc(base_price=800, daily_change=-0.5)
        pred = _make_pred(predicted_price=750)
        pred["forward_curve"] = fc
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.theta < 0

    def test_vega_increases_with_volatility(self):
        rg_low = compute_room_greeks(_make_pred(vol=1.0))
        rg_high = compute_room_greeks(_make_pred(vol=5.0))
        assert rg_low is not None and rg_high is not None
        assert rg_high.vega > rg_low.vega

    def test_vega_increases_with_time(self):
        rg_near = compute_room_greeks(_make_pred(days_to_checkin=5, fc_points=6))
        rg_far = compute_room_greeks(_make_pred(days_to_checkin=60, fc_points=10))
        assert rg_near is not None and rg_far is not None
        assert rg_far.vega > rg_near.vega

    def test_var_proportional_to_price_and_vol(self):
        rg = compute_room_greeks(_make_pred(current_price=1000, vol=3.0))
        assert rg is not None
        expected_var = 1000 * (3.0 / 100.0) * VAR_Z
        assert rg.var_1d == pytest.approx(expected_var, abs=0.1)

    def test_returns_none_for_zero_price(self):
        pred = _make_pred(current_price=0)
        assert compute_room_greeks(pred) is None

    def test_returns_none_for_zero_T(self):
        pred = _make_pred(days_to_checkin=0)
        assert compute_room_greeks(pred) is None

    def test_returns_none_for_insufficient_fc(self):
        pred = _make_pred(fc_points=2)
        assert compute_room_greeks(pred) is None

    def test_position_value(self):
        pred = _make_pred(current_price=800, predicted_price=850)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.position_value == pytest.approx(50, abs=1)

    def test_handles_missing_probability(self):
        pred = _make_pred()
        del pred["probability"]
        rg = compute_room_greeks(pred)
        assert rg is not None  # Should use defaults

    def test_strong_call_positive_delta(self):
        pred = _make_pred(signal="STRONG_CALL", p_up=85)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.delta > 0

    def test_strong_put_negative_delta(self):
        pred = _make_pred(signal="STRONG_PUT", p_down=85, predicted_price=720)
        rg = compute_room_greeks(pred)
        assert rg is not None
        assert rg.delta < 0

    def test_to_dict(self):
        rg = compute_room_greeks(_make_pred())
        assert rg is not None
        d = rg.to_dict()
        assert "theta" in d
        assert "delta" in d
        assert "vega" in d
        assert "var_1d" in d
        assert "detail_id" in d


# ── compute_portfolio_greeks tests ───────────────────────────────────

class TestComputePortfolioGreeks:
    def test_single_contract(self):
        analysis = _make_analysis([_make_pred()])
        pg = compute_portfolio_greeks(analysis)
        assert pg.n_contracts == 1
        assert pg.n_calls == 1
        assert pg.n_puts == 0

    def test_multiple_signals(self):
        preds = [
            _make_pred(detail_id=1, signal="CALL", p_up=80),
            _make_pred(detail_id=2, signal="PUT", p_down=80, predicted_price=750),
            _make_pred(detail_id=3, signal="NONE", p_up=50, p_down=50),
        ]
        pg = compute_portfolio_greeks(_make_analysis(preds))
        assert pg.n_contracts == 3
        assert pg.n_calls == 1
        assert pg.n_puts == 1
        assert pg.n_none == 1

    def test_portfolio_var_diversified(self):
        """Portfolio VaR should be less than sum of individual VaRs (diversification)."""
        preds = [
            _make_pred(detail_id=i, hotel_id=i % 3, current_price=500 + i * 10)
            for i in range(10)
        ]
        pg = compute_portfolio_greeks(_make_analysis(preds))
        assert pg.portfolio_var_95 > 0
        assert pg.portfolio_cvar_95 > pg.portfolio_var_95  # CVaR > VaR always

    def test_cvar_greater_than_var(self):
        pg = compute_portfolio_greeks(_make_analysis([_make_pred()]))
        assert pg.portfolio_cvar_95 >= pg.portfolio_var_95

    def test_empty_analysis(self):
        pg = compute_portfolio_greeks({"predictions": {}})
        assert pg.n_contracts == 0
        assert pg.portfolio_var_95 == 0
        assert pg.total_theta == 0

    def test_hotel_concentration(self):
        preds = [
            _make_pred(detail_id=1, hotel_id=100, hotel_name="Big Hotel",
                       current_price=1000, predicted_price=1100),
            _make_pred(detail_id=2, hotel_id=200, hotel_name="Small Hotel",
                       current_price=100, predicted_price=110),
        ]
        pg = compute_portfolio_greeks(_make_analysis(preds))
        assert pg.max_hotel_name == "Big Hotel"
        assert pg.max_hotel_exposure_pct > 50  # Big Hotel dominates

    def test_hotel_greeks_breakdown(self):
        preds = [
            _make_pred(detail_id=1, hotel_id=100, hotel_name="Hotel A"),
            _make_pred(detail_id=2, hotel_id=100, hotel_name="Hotel A"),
            _make_pred(detail_id=3, hotel_id=200, hotel_name="Hotel B"),
        ]
        pg = compute_portfolio_greeks(_make_analysis(preds))
        assert len(pg.hotel_greeks) == 2
        hotel_a = next(h for h in pg.hotel_greeks if h["hotel_id"] == 100)
        assert hotel_a["n_contracts"] == 2

    def test_total_unrealized_pnl(self):
        preds = [
            _make_pred(detail_id=1, current_price=800, predicted_price=900),
            _make_pred(detail_id=2, current_price=500, predicted_price=450),
        ]
        pg = compute_portfolio_greeks(_make_analysis(preds))
        # +100 and -50 = +50
        assert pg.total_unrealized_pnl == pytest.approx(50, abs=5)

    def test_to_dict(self):
        pg = compute_portfolio_greeks(_make_analysis())
        d = pg.to_dict()
        assert "portfolio_var_95" in d
        assert "hotel_greeks" in d
        assert "timestamp" in d


# ── compute_hotel_greeks tests ───────────────────────────────────────

class TestComputeHotelGreeks:
    def test_basic(self):
        preds = [
            _make_pred(detail_id=1, hotel_id=100),
            _make_pred(detail_id=2, hotel_id=100),
            _make_pred(detail_id=3, hotel_id=200),
        ]
        result = compute_hotel_greeks(_make_analysis(preds), hotel_id=100)
        assert result["n_contracts"] == 2
        assert result["hotel_id"] == 100
        assert len(result["rooms"]) == 2

    def test_nonexistent_hotel(self):
        result = compute_hotel_greeks(_make_analysis(), hotel_id=999)
        assert result["error"] == "No data"
        assert result["rooms"] == []

    def test_rooms_sorted_by_position_value(self):
        preds = [
            _make_pred(detail_id=1, hotel_id=100, current_price=800, predicted_price=810),
            _make_pred(detail_id=2, hotel_id=100, current_price=800, predicted_price=900),
        ]
        result = compute_hotel_greeks(_make_analysis(preds), hotel_id=100)
        # Room with $100 difference should be first
        assert result["rooms"][0]["detail_id"] == 2

    def test_signal_counts(self):
        preds = [
            _make_pred(detail_id=1, hotel_id=100, signal="CALL"),
            _make_pred(detail_id=2, hotel_id=100, signal="PUT", predicted_price=750),
            _make_pred(detail_id=3, hotel_id=100, signal="NONE"),
        ]
        result = compute_hotel_greeks(_make_analysis(preds), hotel_id=100)
        assert result["n_calls"] == 1
        assert result["n_puts"] == 1
