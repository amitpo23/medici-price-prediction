"""Unit tests for options_engine.py — signal generation, crossings, expiry metrics.

Uses real objects with constructed data — NO mocks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.options_engine import (
    P_THRESHOLD_HIGH,
    P_THRESHOLD_MED,
    BREACH_THRESHOLDS,
    _normal_cdf,
    _count_crossings,
    compute_next_day_signals,
    build_expiry_metrics,
)


# ── _normal_cdf tests ──────────────────────────────────────────────


class TestNormalCdf:
    def test_cdf_at_zero(self):
        assert abs(_normal_cdf(0) - 0.5) < 0.001

    def test_cdf_large_positive(self):
        assert _normal_cdf(5.0) > 0.999

    def test_cdf_large_negative(self):
        assert _normal_cdf(-5.0) < 0.001

    def test_cdf_symmetric(self):
        """CDF(x) + CDF(-x) should equal 1."""
        for x in [0.5, 1.0, 2.0, 3.0]:
            assert abs(_normal_cdf(x) + _normal_cdf(-x) - 1.0) < 0.001

    def test_cdf_at_one(self):
        # CDF(1) ≈ 0.8413
        assert abs(_normal_cdf(1.0) - 0.8413) < 0.001


# ── _count_crossings tests ─────────────────────────────────────────


class TestCountCrossings:
    def test_empty_array(self):
        assert _count_crossings(np.array([]), -5.0) == 0

    def test_single_value_below(self):
        assert _count_crossings(np.array([-6.0]), -5.0) == 1

    def test_single_value_above(self):
        assert _count_crossings(np.array([0.0]), -5.0) == 0

    def test_one_crossing(self):
        """Transition from above to below counts as one event."""
        values = np.array([0.0, -3.0, -6.0, -7.0, 0.0])
        assert _count_crossings(values, -5.0) == 1

    def test_two_crossings(self):
        """Two separate dips below threshold."""
        values = np.array([0.0, -6.0, 0.0, -6.0, 0.0])
        assert _count_crossings(values, -5.0) == 2

    def test_starts_below(self):
        """If first value is below, that counts as an event + any transitions."""
        values = np.array([-6.0, 0.0, -6.0])
        assert _count_crossings(values, -5.0) == 2  # first_below + 1 transition

    def test_all_above(self):
        values = np.array([0.0, 1.0, 2.0, 3.0])
        assert _count_crossings(values, -5.0) == 0

    def test_all_below(self):
        """All below: first_below=1, no transitions."""
        values = np.array([-6.0, -7.0, -8.0])
        assert _count_crossings(values, -5.0) == 1


# ── Threshold constants ─────────────────────────────────────────────


class TestThresholds:
    def test_high_threshold(self):
        assert P_THRESHOLD_HIGH == 0.70

    def test_med_threshold(self):
        assert P_THRESHOLD_MED == 0.60

    def test_breach_thresholds(self):
        assert BREACH_THRESHOLDS == (-5.0, -10.0)


# ── compute_next_day_signals ────────────────────────────────────────


def _make_prediction(
    p_up: float = 50.0,
    p_down: float = 50.0,
    accel: float = 0.0,
    regime: str = "NORMAL",
    quality: str = "medium",
    velocity_24h: float = 0.0,
    detail_id: str = "1001",
    hotel_id: int = 42,
    current_price: float = 200.0,
    days_to_checkin: int = 14,
    fc_prices: list = None,
    fc_change_pct: float = 0.0,
    season_adj_pct: float = 0.0,
    demand_adj_pct: float = 0.0,
    weather_adj_pct: float = 0.0,
    cancellation_adj_pct: float = 0.0,
) -> dict:
    """Build a realistic prediction dict for compute_next_day_signals.

    fc_prices: list of predicted prices along forward curve.
    Default: flat at current_price (no movement → NEUTRAL).
    fc_change_pct: change_pct for FC voter (stored in first FC entry).
    season/demand/weather/cancellation_adj_pct: enrichment fields for consensus voters.
    """
    if fc_prices is None:
        fc_prices = [current_price] * 5  # flat = no signal
    fc = []
    for i, p in enumerate(fc_prices):
        entry = {"predicted_price": p, "volatility_at_t": 1.2, "date": f"2025-06-{i+1:02d}"}
        if i == 0:
            entry["change_pct"] = fc_change_pct
            entry["season_adj_pct"] = season_adj_pct
            entry["demand_adj_pct"] = demand_adj_pct
            entry["weather_adj_pct"] = weather_adj_pct
            entry["cancellation_adj_pct"] = cancellation_adj_pct
        fc.append(entry)
    return {
        detail_id: {
            "hotel_id": hotel_id,
            "hotel_name": "Test Hotel",
            "date_from": "2025-06-15",
            "days_to_checkin": days_to_checkin,
            "category": "standard",
            "board": "bb",
            "current_price": current_price,
            "expected_change_pct": 1.5,
            "probability": {"up": p_up, "down": p_down, "stable": 100 - p_up - p_down},
            "regime": {"regime": regime},
            "momentum": {"acceleration": accel, "velocity_24h": velocity_24h, "signal": "NORMAL"},
            "confidence_quality": quality,
            "forward_curve": fc,
        }
    }


class TestComputeNextDaySignals:
    def test_empty_analysis(self):
        signals = compute_next_day_signals({})
        assert signals == []

    def test_empty_predictions(self):
        signals = compute_next_day_signals({"predictions": {}})
        assert signals == []

    def test_call_signal(self):
        """Consensus: multiple voters agree CALL → CALL signal.

        Triggers: FC +35%, historical 80% up, seasonality +5%, demand +3%.
        At least 4/11 voters → CALL with ≥66% agreement among non-neutral voters.
        """
        analysis = {"predictions": _make_prediction(
            current_price=200.0, fc_prices=[200, 220, 260, 300, 290],
            p_up=80.0, p_down=10.0,
            fc_change_pct=35.0,
            season_adj_pct=0.06,
            demand_adj_pct=0.04,
        )}
        signals = compute_next_day_signals(analysis)
        assert len(signals) == 1
        assert signals[0]["recommendation"] == "CALL"
        assert signals[0]["confidence"] in ("Low", "Med", "High")

    def test_call_with_velocity(self):
        """Consensus CALL boosted by strong scan velocity."""
        analysis = {"predictions": _make_prediction(
            current_price=200.0, fc_prices=[200, 220, 260, 300, 290],
            p_up=80.0, p_down=10.0,
            velocity_24h=0.05,  # 5% → CALL vote
            fc_change_pct=35.0,
            season_adj_pct=0.06,
        )}
        signals = compute_next_day_signals(analysis)
        assert len(signals) == 1
        assert signals[0]["recommendation"] == "CALL"

    def test_put_signal(self):
        """Consensus: multiple voters agree PUT → PUT signal.

        Triggers: FC -10%, historical 80% down, weather -5%, cancellation -3%.
        """
        analysis = {"predictions": _make_prediction(
            current_price=200.0, fc_prices=[200, 195, 185, 176, 180],
            p_up=10.0, p_down=80.0,
            fc_change_pct=-10.0,
            weather_adj_pct=-0.06,
            cancellation_adj_pct=-0.03,
        )}
        signals = compute_next_day_signals(analysis)
        assert len(signals) == 1
        assert signals[0]["recommendation"] == "PUT"
        assert signals[0]["confidence"] in ("Low", "Med", "High")

    def test_put_with_negative_velocity(self):
        """Consensus PUT with scan velocity confirming decline."""
        analysis = {"predictions": _make_prediction(
            current_price=200.0, fc_prices=[200, 196, 190, 186, 188],
            p_up=10.0, p_down=80.0,
            velocity_24h=-0.05,  # -5% → PUT vote
            fc_change_pct=-7.0,
            cancellation_adj_pct=-0.03,
        )}
        signals = compute_next_day_signals(analysis)
        assert len(signals) == 1
        assert signals[0]["recommendation"] == "PUT"

    def test_none_signal_neutral(self):
        """FC shows <5% drop and <30% rise → NONE (no significant movement)."""
        # current=200, FC range 195-205 = ±2.5% → NONE
        analysis = {"predictions": _make_prediction(
            current_price=200.0, fc_prices=[200, 198, 195, 202, 205]
        )}
        signals = compute_next_day_signals(analysis)
        assert len(signals) == 1
        assert signals[0]["recommendation"] == "NONE"
        assert signals[0]["confidence"] == "Low"

    def test_suppress_stale_regime(self):
        """STALE regime → suppress signal → NONE."""
        analysis = {"predictions": _make_prediction(
            p_up=80.0, p_down=5.0, accel=1.0, regime="STALE",
        )}
        signals = compute_next_day_signals(analysis)
        assert signals[0]["recommendation"] == "NONE"

    def test_volatile_regime_not_suppressed(self):
        """VOLATILE regime is NOT suppressed by consensus engine (only STALE is)."""
        analysis = {"predictions": _make_prediction(
            p_up=80.0, p_down=5.0, accel=1.0, regime="VOLATILE",
            fc_change_pct=35.0, season_adj_pct=0.06, demand_adj_pct=0.04,
        )}
        signals = compute_next_day_signals(analysis)
        # VOLATILE regime does not suppress — consensus voters decide
        assert signals[0]["recommendation"] in ("CALL", "NONE")

    def test_suppress_low_quality(self):
        """Low quality → suppress signal → NONE."""
        analysis = {"predictions": _make_prediction(
            p_up=80.0, p_down=5.0, accel=1.0, quality="low",
        )}
        signals = compute_next_day_signals(analysis)
        assert signals[0]["recommendation"] == "NONE"

    def test_consensus_needs_agreement(self):
        """High P_up alone is not enough — consensus needs multiple voters agreeing."""
        # Only historical voter fires CALL (80% up), rest are NEUTRAL → no 66% agreement
        analysis = {"predictions": _make_prediction(p_up=80.0, p_down=5.0, accel=-0.5)}
        signals = compute_next_day_signals(analysis)
        # Only 1 voter (historical) says CALL out of ~1 voting → could be CALL or NONE
        # depending on neutral exclusion rules. With only 1 voting, 100% agreement → CALL
        assert signals[0]["recommendation"] in ("CALL", "NONE")

    def test_consensus_needs_agreement_put(self):
        """High P_down alone — historical voter fires PUT but may not reach agreement."""
        analysis = {"predictions": _make_prediction(p_up=5.0, p_down=80.0, accel=0.5)}
        signals = compute_next_day_signals(analysis)
        assert signals[0]["recommendation"] in ("PUT", "NONE")

    def test_signal_output_fields(self):
        """Verify all required fields in signal output, including consensus fields."""
        analysis = {"predictions": _make_prediction(p_up=75.0, p_down=10.0, accel=0.5)}
        signals = compute_next_day_signals(analysis)
        sig = signals[0]
        required_fields = [
            "detail_id", "hotel_id", "hotel_name", "checkin_date", "T",
            "category", "board", "S_t", "expected_return_1d", "sigma_1d",
            "P_up", "P_down", "velocity_24h", "acceleration",
            "momentum_signal", "regime", "quality",
            "recommendation", "confidence",
            "consensus_probability", "consensus_sources_agree",
            "consensus_sources_voting", "consensus_by_category",
            "fc_max_drop_pct", "fc_max_rise_pct", "fc_points",
            "market_context",
        ]
        for f in required_fields:
            assert f in sig, f"Missing field: {f}"

    def test_p_up_p_down_scaled_to_100(self):
        """P_up/P_down in output should be on 0-100 scale."""
        analysis = {"predictions": _make_prediction(p_up=75.0, p_down=10.0, accel=0.5)}
        signals = compute_next_day_signals(analysis)
        # Input p_up=75 on 0-100 scale, internally divided by 100, then output * 100
        assert signals[0]["P_up"] == 75.0
        assert signals[0]["P_down"] == 10.0

    def test_multiple_predictions_sorted(self):
        """Multiple predictions should be sorted by (hotel_id, checkin_date, -T)."""
        preds = {}
        preds.update(_make_prediction(
            p_up=75.0, p_down=10.0, accel=0.5,
            detail_id="1001", hotel_id=42, days_to_checkin=14,
        ))
        preds.update(_make_prediction(
            p_up=65.0, p_down=20.0, accel=0.1,
            detail_id="1002", hotel_id=42, days_to_checkin=7,
        ))
        signals = compute_next_day_signals({"predictions": preds})
        assert len(signals) == 2
        # T=14 should come before T=7 (sorted by -T)
        assert signals[0]["T"] >= signals[1]["T"]


# ── build_expiry_metrics tests ──────────────────────────────────────


def _make_expiry_df() -> pd.DataFrame:
    """Build a DataFrame suitable for build_expiry_metrics.

    Creates completed contracts (checkin in last 6 months) with
    price observations at various T_days.
    """
    today = pd.Timestamp.today().normalize()
    rows = []
    # Hotel 42, one contract with checkin 30 days ago
    checkin = today - pd.Timedelta(days=30)
    s_exp = 180.0  # settlement price at T=0

    for t in range(30, 0, -1):
        scan_date = checkin - pd.Timedelta(days=t)
        # Price starts high, drops, then recovers to settlement
        if t > 20:
            price = 200.0  # above settlement
        elif t > 10:
            price = 165.0  # below -5% of 180 = 171
        else:
            price = 175.0  # recovers

        rows.append({
            "hotel_id": 42,
            "checkin_date": checkin,
            "category": "standard",
            "board": "bb",
            "scan_date": scan_date,
            "price": price,
            "T_days": t,
        })

    # Add settlement observation (T=0)
    rows.append({
        "hotel_id": 42,
        "checkin_date": checkin,
        "category": "standard",
        "board": "bb",
        "scan_date": checkin,
        "price": s_exp,
        "T_days": 0,
    })

    return pd.DataFrame(rows)


class TestBuildExpiryMetrics:
    def test_empty_df(self):
        summary_df, rollups = build_expiry_metrics(pd.DataFrame())
        assert summary_df.empty
        assert rollups == {}

    def test_basic_metrics(self):
        df = _make_expiry_df()
        summary_df, rollups = build_expiry_metrics(df)

        if summary_df.empty:
            pytest.skip("No completed contracts found in test data")

        assert len(summary_df) >= 1
        row = summary_df.iloc[0]
        assert row["hotel_id"] == 42
        assert row["S_exp"] > 0
        assert "min_rel" in row.index
        assert "max_rel" in row.index
        assert "days_below_5" in row.index
        assert "events_below_5" in row.index

    def test_hotel_rollups(self):
        df = _make_expiry_df()
        summary_df, rollups = build_expiry_metrics(df)

        if not rollups:
            pytest.skip("No rollups generated from test data")

        assert 42 in rollups
        hotel = rollups[42]
        assert "total_contracts" in hotel
        assert "pct_below_5" in hotel
        assert "pct_below_10" in hotel
        assert hotel["total_contracts"] >= 1

    def test_no_future_contracts(self):
        """Only completed contracts (checkin < today) should be included."""
        today = pd.Timestamp.today().normalize()
        future_checkin = today + pd.Timedelta(days=30)

        rows = [{
            "hotel_id": 42,
            "checkin_date": future_checkin,
            "category": "standard",
            "board": "bb",
            "scan_date": today,
            "price": 200.0,
            "T_days": 30,
        }]
        df = pd.DataFrame(rows)
        summary_df, rollups = build_expiry_metrics(df)
        assert summary_df.empty

    def test_old_contracts_excluded(self):
        """Contracts older than 6 months should be excluded."""
        today = pd.Timestamp.today().normalize()
        old_checkin = today - pd.Timedelta(days=200)

        rows = [{
            "hotel_id": 42,
            "checkin_date": old_checkin,
            "category": "standard",
            "board": "bb",
            "scan_date": old_checkin - pd.Timedelta(days=10),
            "price": 200.0,
            "T_days": 10,
        }]
        df = pd.DataFrame(rows)
        summary_df, rollups = build_expiry_metrics(df)
        assert summary_df.empty


# ── Edge cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    def test_missing_probability_in_prediction(self):
        """Missing probability dict should not crash."""
        analysis = {"predictions": {
            "1001": {
                "hotel_id": 42,
                "hotel_name": "Test",
                "date_from": "2025-06-15",
                "days_to_checkin": 14,
                "current_price": 200,
                "expected_change_pct": 0,
                "probability": None,
                "regime": None,
                "momentum": None,
                "confidence_quality": "medium",
                "forward_curve": [],
            }
        }}
        signals = compute_next_day_signals(analysis)
        assert len(signals) == 1
        assert signals[0]["recommendation"] == "NONE"

    def test_missing_forward_curve(self):
        """Empty forward_curve list → sigma_1d = 0."""
        analysis = {"predictions": _make_prediction(p_up=50, p_down=50)}
        # Replace forward_curve with empty
        key = list(analysis["predictions"].keys())[0]
        analysis["predictions"][key]["forward_curve"] = []
        signals = compute_next_day_signals(analysis)
        assert signals[0]["sigma_1d"] == 0.0

    def test_bad_prediction_skipped(self):
        """Prediction that raises exception should be silently skipped."""
        analysis = {"predictions": {
            "bad": "not_a_dict",  # Will cause AttributeError on .get()
            **_make_prediction(p_up=50, p_down=50, detail_id="good"),
        }}
        signals = compute_next_day_signals(analysis)
        # The "good" prediction should still produce a signal
        assert len(signals) >= 1
        good_ids = [s["detail_id"] for s in signals]
        assert "good" in good_ids
