"""Unit tests for trade_setup.py — stop-loss, take-profit, sizing, RR.

Uses real objects with constructed data — NO mocks.
"""
from __future__ import annotations

import pytest

from src.analytics.trade_setup import (
    TradeSetup,
    compute_trade_setup,
    batch_compute_setups,
    _compute_stop_loss,
    _compute_take_profit,
    _compute_position_size,
    _assess_quality,
    _kelly_position_size,
    _zone_based_stop,
    _zone_based_target,
    MIN_RISK_REWARD,
    MIN_STOP_DISTANCE_PCT,
    MAX_STOP_DISTANCE_PCT,
    STOP_VOL_MULTIPLIER,
    KELLY_FRACTION,
)


# ── TradeSetup Dataclass ─────────────────────────────────────────────


class TestTradeSetupDataclass:
    """Tests for TradeSetup properties and serialization."""

    def test_defaults(self):
        ts = TradeSetup(detail_id=1, hotel_id=1)
        assert ts.signal == "NEUTRAL"
        assert ts.reasons == {}
        assert ts.position_size == 1

    def test_to_dict(self):
        ts = TradeSetup(detail_id=1, hotel_id=1, entry_price=200.0, signal="CALL")
        d = ts.to_dict()
        assert d["detail_id"] == 1
        assert d["entry_price"] == 200.0
        assert isinstance(d, dict)

    def test_is_valid_call(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, entry_price=200.0, signal="CALL",
            risk_reward_ratio=1.5, stop_distance_pct=3.0,
        )
        assert ts.is_valid is True

    def test_is_valid_put(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, entry_price=200.0, signal="PUT",
            risk_reward_ratio=1.5, stop_distance_pct=3.0,
        )
        assert ts.is_valid is True

    def test_invalid_neutral_signal(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, entry_price=200.0, signal="NEUTRAL",
            risk_reward_ratio=2.0, stop_distance_pct=3.0,
        )
        assert ts.is_valid is False

    def test_invalid_low_rr(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, entry_price=200.0, signal="CALL",
            risk_reward_ratio=0.5, stop_distance_pct=3.0,
        )
        assert ts.is_valid is False

    def test_invalid_tight_stop(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, entry_price=200.0, signal="CALL",
            risk_reward_ratio=2.0, stop_distance_pct=0.5,
        )
        assert ts.is_valid is False

    def test_invalid_zero_price(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, entry_price=0, signal="CALL",
            risk_reward_ratio=2.0, stop_distance_pct=3.0,
        )
        assert ts.is_valid is False


# ── Stop-Loss Computation ────────────────────────────────────────────


class TestStopLoss:
    """Tests for _compute_stop_loss()."""

    def test_volatility_stop_call(self):
        stop, method = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=10)
        assert method == "volatility"
        assert stop < 200.0  # CALL stop is below entry

    def test_volatility_stop_put(self):
        stop, method = _compute_stop_loss(200.0, "PUT", sigma_1d=2.0, t_value=10)
        assert method == "volatility"
        assert stop > 200.0  # PUT stop is above entry

    def test_stop_respects_min_distance(self):
        # Very low vol should still have MIN_STOP_DISTANCE_PCT
        stop, _ = _compute_stop_loss(200.0, "CALL", sigma_1d=0.01, t_value=1)
        distance_pct = (200.0 - stop) / 200.0 * 100
        assert distance_pct >= MIN_STOP_DISTANCE_PCT

    def test_stop_respects_max_distance(self):
        # Very high vol should be capped
        stop, _ = _compute_stop_loss(200.0, "CALL", sigma_1d=50.0, t_value=14)
        distance_pct = (200.0 - stop) / 200.0 * 100
        assert distance_pct <= MAX_STOP_DISTANCE_PCT

    def test_zone_based_stop_call(self):
        zones = [
            {"zone_type": "SUPPORT", "price_lower": 185.0, "price_upper": 190.0, "is_broken": False},
        ]
        stop, method = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=10, demand_zones=zones)
        assert method == "demand_zone"
        assert stop < 190.0  # Below zone lower with buffer

    def test_zone_based_stop_put(self):
        zones = [
            {"zone_type": "RESISTANCE", "price_lower": 210.0, "price_upper": 215.0, "is_broken": False},
        ]
        stop, method = _compute_stop_loss(200.0, "PUT", sigma_1d=2.0, t_value=10, demand_zones=zones)
        assert method == "demand_zone"
        assert stop > 215.0  # Above zone upper with buffer

    def test_broken_zone_ignored(self):
        zones = [
            {"zone_type": "SUPPORT", "price_lower": 185.0, "price_upper": 190.0, "is_broken": True},
        ]
        stop, method = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=10, demand_zones=zones)
        assert method == "volatility"  # Zone was broken, fallback to vol

    def test_zone_too_far_falls_back(self):
        # Zone so far away it exceeds MAX_STOP_DISTANCE_PCT
        zones = [
            {"zone_type": "SUPPORT", "price_lower": 50.0, "price_upper": 55.0, "is_broken": False},
        ]
        stop, method = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=10, demand_zones=zones)
        assert method == "volatility"  # Too far, fallback

    def test_turning_point_stop(self):
        turning_points = [
            {"type": "MIN", "price": 190.0},
        ]
        stop, method = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=10,
                                           turning_points=turning_points)
        assert method == "turning_point"
        assert stop < 190.0

    def test_holding_days_capped_at_14(self):
        # t_value=100 should use holding_days=14
        stop_long, _ = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=100)
        stop_14, _ = _compute_stop_loss(200.0, "CALL", sigma_1d=2.0, t_value=14)
        assert stop_long == stop_14


# ── Take-Profit Computation ──────────────────────────────────────────


class TestTakeProfit:
    """Tests for _compute_take_profit()."""

    def test_rr_based_target_call(self):
        target, method = _compute_take_profit(200.0, "CALL", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0)
        assert method == "rr_based"
        assert target > 200.0

    def test_rr_based_target_put(self):
        target, method = _compute_take_profit(200.0, "PUT", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0)
        assert method == "rr_based"
        assert target < 200.0

    def test_path_forecast_target_call(self):
        pf = {"best_sell_price": 220.0}
        target, method = _compute_take_profit(200.0, "CALL", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0, path_forecast=pf)
        assert method == "path_forecast"
        assert target == 220.0

    def test_path_forecast_target_put(self):
        pf = {"best_buy_price": 180.0}
        target, method = _compute_take_profit(200.0, "PUT", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0, path_forecast=pf)
        assert method == "path_forecast"
        assert target == 180.0

    def test_path_forecast_too_close_falls_back(self):
        # Target only 0.5% above entry — should fallback
        pf = {"best_sell_price": 201.0}
        target, method = _compute_take_profit(200.0, "CALL", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0, path_forecast=pf)
        assert method != "path_forecast"

    def test_zone_based_target_call(self):
        zones = [
            {"zone_type": "RESISTANCE", "price_lower": 215.0, "price_upper": 220.0, "is_broken": False},
        ]
        target, method = _compute_take_profit(200.0, "CALL", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0, demand_zones=zones)
        assert method == "demand_zone"
        assert target == 215.0  # Sell at zone lower bound

    def test_zone_based_target_put(self):
        zones = [
            {"zone_type": "SUPPORT", "price_lower": 175.0, "price_upper": 180.0, "is_broken": False},
        ]
        target, method = _compute_take_profit(200.0, "PUT", sigma_1d=2.0, t_value=10,
                                               stop_distance_pct=5.0, demand_zones=zones)
        assert method == "demand_zone"
        assert target == 180.0  # Buy at zone upper bound


# ── Position Sizing ──────────────────────────────────────────────────


class TestPositionSizing:
    """Tests for _compute_position_size() and Kelly criterion."""

    def test_simple_risk_based(self):
        # $200 price, 5% stop = $10 risk per contract
        # $100 max risk → 10 contracts
        size = _compute_position_size(200.0, 5.0, max_risk_usd=100.0)
        assert size == 10

    def test_minimum_one_contract(self):
        # Very expensive with tight max risk
        size = _compute_position_size(1000.0, 5.0, max_risk_usd=10.0)
        assert size >= 1

    def test_capped_at_50(self):
        size = _compute_position_size(10.0, 0.1, max_risk_usd=10000.0)
        assert size <= 50

    def test_zero_price(self):
        size = _compute_position_size(0, 5.0, max_risk_usd=100.0)
        assert size == 1

    def test_zero_stop(self):
        size = _compute_position_size(200.0, 0, max_risk_usd=100.0)
        assert size == 1

    def test_kelly_sizing(self):
        size = _compute_position_size(
            200.0, 5.0, max_risk_usd=100.0,
            win_rate=0.60, avg_win_pct=3.0, avg_loss_pct=2.0,
        )
        assert size >= 1

    def test_kelly_low_winrate_ignored(self):
        # Win rate below MIN_WIN_RATE_FOR_KELLY → fallback to simple sizing
        size = _compute_position_size(
            200.0, 5.0, max_risk_usd=100.0,
            win_rate=0.30, avg_win_pct=3.0, avg_loss_pct=2.0,
        )
        # Should be simple: 100 / (200*0.05) = 10
        assert size == 10


class TestKellyCriterion:
    """Tests for _kelly_position_size() directly."""

    def test_positive_kelly(self):
        size = _kelly_position_size(200.0, 10.0, 100.0,
                                     win_rate=0.60, avg_win_pct=3.0, avg_loss_pct=2.0)
        assert size >= 1

    def test_negative_kelly_returns_zero(self):
        # Very low win rate, bad payoff → Kelly says don't bet
        size = _kelly_position_size(200.0, 10.0, 100.0,
                                     win_rate=0.20, avg_win_pct=1.0, avg_loss_pct=5.0)
        assert size == 0

    def test_zero_avg_loss(self):
        size = _kelly_position_size(200.0, 10.0, 100.0,
                                     win_rate=0.60, avg_win_pct=3.0, avg_loss_pct=0)
        assert size == 0

    def test_half_kelly(self):
        # Verify half-Kelly is more conservative than full Kelly
        # We test that the result is bounded
        size = _kelly_position_size(200.0, 10.0, 100.0,
                                     win_rate=0.55, avg_win_pct=2.0, avg_loss_pct=1.5)
        assert 1 <= size <= 50


# ── Quality Assessment ───────────────────────────────────────────────


class TestAssessQuality:
    """Tests for _assess_quality()."""

    def test_high_quality(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, risk_reward_ratio=2.5,
            confidence=0.80, stop_method="demand_zone",
        )
        assert _assess_quality(ts) == "high"

    def test_high_quality_vol_stop_needs_higher_rr(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, risk_reward_ratio=2.0,
            confidence=0.75, stop_method="volatility",
        )
        # RR=2.0, conf=0.75, volatility stop → medium (needs RR>=2.5 for high w/ vol)
        assert _assess_quality(ts) == "medium"

    def test_medium_quality(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, risk_reward_ratio=1.5,
            confidence=0.55,
        )
        assert _assess_quality(ts) == "medium"

    def test_low_quality(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, risk_reward_ratio=1.1,
            confidence=0.40,
        )
        assert _assess_quality(ts) == "low"

    def test_skip_quality(self):
        ts = TradeSetup(
            detail_id=1, hotel_id=1, risk_reward_ratio=0.5,
            confidence=0.80,
        )
        assert _assess_quality(ts) == "skip"


# ── Full Trade Setup Computation ─────────────────────────────────────


class TestComputeTradeSetup:
    """Integration tests for compute_trade_setup()."""

    def test_call_setup(self):
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=200.0,
            signal="CALL", confidence=0.75, sigma_1d=2.0, t_value=14,
        )
        assert setup.signal == "CALL"
        assert setup.entry_price == 200.0
        assert setup.stop_loss < 200.0
        assert setup.take_profit > 200.0
        assert setup.risk_reward_ratio > 0
        assert setup.stop_distance_pct > 0
        assert setup.target_distance_pct > 0

    def test_put_setup(self):
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=200.0,
            signal="PUT", confidence=0.70, sigma_1d=2.0, t_value=14,
        )
        assert setup.signal == "PUT"
        assert setup.stop_loss > 200.0
        assert setup.take_profit < 200.0

    def test_neutral_returns_skip(self):
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=200.0,
            signal="NEUTRAL", confidence=0.50, sigma_1d=2.0, t_value=14,
        )
        assert setup.setup_quality == "skip"

    def test_zero_price_returns_skip(self):
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=0,
            signal="CALL", confidence=0.75, sigma_1d=2.0, t_value=14,
        )
        assert setup.setup_quality == "skip"

    def test_with_demand_zones(self):
        zones = [
            {"zone_type": "SUPPORT", "price_lower": 185.0, "price_upper": 190.0, "is_broken": False},
            {"zone_type": "RESISTANCE", "price_lower": 215.0, "price_upper": 220.0, "is_broken": False},
        ]
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=200.0,
            signal="CALL", confidence=0.75, sigma_1d=2.0, t_value=14,
            demand_zones=zones,
        )
        assert setup.stop_method == "demand_zone"
        assert setup.target_method == "demand_zone"

    def test_with_path_forecast(self):
        pf = {"best_sell_price": 230.0, "best_buy_price": 170.0}
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=200.0,
            signal="CALL", confidence=0.75, sigma_1d=2.0, t_value=14,
            path_forecast=pf,
        )
        assert setup.target_method == "path_forecast"
        assert setup.take_profit == 230.0

    def test_reasons_populated(self):
        setup = compute_trade_setup(
            detail_id=100, hotel_id=1, current_price=200.0,
            signal="CALL", confidence=0.75, sigma_1d=2.0, t_value=14,
        )
        assert "stop" in setup.reasons
        assert "target" in setup.reasons
        assert "rr" in setup.reasons
        assert "size" in setup.reasons


# ── Batch Compute ────────────────────────────────────────────────────


class TestBatchCompute:
    """Tests for batch_compute_setups()."""

    def test_batch_basic(self):
        options = [
            {"detail_id": 100, "hotel_id": 1, "S_t": 200.0,
             "recommendation": "CALL", "confidence_score": 75,
             "sigma_1d": 2.0, "days_to_checkin": 14},
            {"detail_id": 101, "hotel_id": 1, "S_t": 180.0,
             "recommendation": "PUT", "confidence_score": 65,
             "sigma_1d": 1.5, "days_to_checkin": 7},
        ]
        setups = batch_compute_setups(options)
        assert len(setups) == 2
        assert setups[0].signal == "CALL"
        assert setups[1].signal == "PUT"

    def test_batch_skips_neutral(self):
        options = [
            {"detail_id": 100, "hotel_id": 1, "S_t": 200.0,
             "recommendation": "NEUTRAL", "confidence_score": 50,
             "sigma_1d": 2.0, "days_to_checkin": 14},
        ]
        setups = batch_compute_setups(options)
        assert len(setups) == 0

    def test_batch_with_trade_stats(self):
        options = [
            {"detail_id": 100, "hotel_id": 1, "S_t": 200.0,
             "recommendation": "CALL", "confidence_score": 75,
             "sigma_1d": 2.0, "days_to_checkin": 14},
        ]
        stats = {
            "total_trades": 50, "win_rate": 60.0,
            "avg_win_pct": 3.0, "avg_loss_pct": -2.0,
        }
        setups = batch_compute_setups(options, trade_stats=stats)
        assert len(setups) == 1

    def test_batch_empty_options(self):
        assert batch_compute_setups([]) == []

    def test_batch_with_zones(self):
        options = [
            {"detail_id": 100, "hotel_id": 1, "S_t": 200.0,
             "recommendation": "CALL", "confidence_score": 75,
             "sigma_1d": 2.0, "days_to_checkin": 14},
        ]
        zones = {
            1: [{"zone_type": "SUPPORT", "price_lower": 185.0, "price_upper": 190.0, "is_broken": False}],
        }
        setups = batch_compute_setups(options, demand_zones_by_hotel=zones)
        assert setups[0].stop_method == "demand_zone"
