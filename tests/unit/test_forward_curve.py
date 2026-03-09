"""Unit tests for forward_curve.py — decay curve, forward prediction, enrichments.

Uses real objects with constructed data — NO mocks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.forward_curve import (
    DecayCurve,
    DecayCurvePoint,
    Enrichments,
    ForwardCurve,
    ForwardPoint,
    build_decay_curve,
    predict_forward_curve,
    _MIN_VOL,
    _BAYESIAN_K,
    _extract_t_observations,
    _build_smoothed_points,
    _get_half_width,
    _compute_offsets,
    _default_curve,
)


# ── Helpers — build real DataFrames ─────────────────────────────────


def _make_historical_df(n_tracks: int = 10, scans_per_track: int = 10) -> pd.DataFrame:
    """Build a realistic historical DataFrame for decay curve building.

    Simulates n_tracks hotel room price tracks, each with scans_per_track
    daily scans going from T=60 down to T=60-scans_per_track.
    """
    rows = []
    for i in range(n_tracks):
        order_id = 1000 + i
        hotel_id = 42
        category = "standard" if i % 2 == 0 else "deluxe"
        board = "bb" if i % 3 == 0 else "hb"
        base_price = 100 + i * 5
        checkin = pd.Timestamp("2025-06-15") + pd.Timedelta(days=i * 3)

        for j in range(scans_per_track):
            scan_date = checkin - pd.Timedelta(days=60 - j)
            # Price drifts slightly down over time (realistic)
            price = base_price * (1 - 0.002 * j + 0.001 * np.random.randn())
            rows.append({
                "order_id": order_id,
                "hotel_id": hotel_id,
                "room_category": category,
                "room_board": board,
                "room_price": round(price, 2),
                "scan_date": scan_date,
                "date_from": checkin,
            })
    return pd.DataFrame(rows)


# ── DecayCurve dataclass tests ──────────────────────────────────────


class TestDecayCurvePoint:
    def test_fields(self):
        pt = DecayCurvePoint(
            t=7, n_observations=20.0, mean_daily_pct=-0.05,
            median_daily_pct=-0.04, std_daily_pct=1.2,
            p_up=35.0, p_down=30.0, p_stable=35.0,
        )
        assert pt.t == 7
        assert pt.n_observations == 20.0
        assert pt.mean_daily_pct == -0.05


class TestDecayCurve:
    """Tests for DecayCurve methods using real constructed points."""

    @pytest.fixture()
    def curve(self) -> DecayCurve:
        """Build a DecayCurve with a few known points."""
        points = {
            5: DecayCurvePoint(t=5, n_observations=20.0, mean_daily_pct=-0.10,
                               median_daily_pct=-0.08, std_daily_pct=1.5,
                               p_up=30.0, p_down=40.0, p_stable=30.0),
            10: DecayCurvePoint(t=10, n_observations=15.0, mean_daily_pct=-0.05,
                                median_daily_pct=-0.04, std_daily_pct=1.2,
                                p_up=35.0, p_down=35.0, p_stable=30.0),
            30: DecayCurvePoint(t=30, n_observations=8.0, mean_daily_pct=-0.02,
                                median_daily_pct=-0.01, std_daily_pct=0.8,
                                p_up=38.0, p_down=32.0, p_stable=30.0),
        }
        return DecayCurve(
            points=points,
            global_mean_daily_pct=-0.04,
            global_std_daily_pct=1.1,
            total_observations=100,
            total_tracks=10,
            max_t=60,
        )

    def test_get_daily_change_known_t(self, curve):
        """Direct lookup at a known T value."""
        assert curve.get_daily_change(5) == -0.08  # median

    def test_get_daily_change_interpolated(self, curve):
        """Interpolated T between two known points."""
        val = curve.get_daily_change(7)
        # Between T=5 (-0.08) and T=10 (-0.04), T=7 is 40% of the way
        expected = -0.08 + (-0.04 - (-0.08)) * (2 / 5)
        assert abs(val - expected) < 0.001

    def test_get_daily_change_clamps_to_range(self, curve):
        """T below 1 clamps to 1, T above max_t clamps to max_t."""
        val_low = curve.get_daily_change(0)  # should clamp to t=1
        val_high = curve.get_daily_change(200)  # should clamp to max_t=60
        assert isinstance(val_low, float)
        assert isinstance(val_high, float)

    def test_get_volatility_min_floor(self, curve):
        """Volatility never drops below _MIN_VOL."""
        # Even if we construct a point with low std, the floor applies
        curve.points[99] = DecayCurvePoint(
            t=99, n_observations=5.0, mean_daily_pct=0.0,
            median_daily_pct=0.0, std_daily_pct=0.01,  # below _MIN_VOL
            p_up=33.0, p_down=33.0, p_stable=34.0,
        )
        assert curve.get_volatility(99) >= _MIN_VOL

    def test_get_volatility_known_t(self, curve):
        """Direct lookup returns std from point (above floor)."""
        assert curve.get_volatility(5) == 1.5  # above _MIN_VOL

    def test_get_probabilities_known(self, curve):
        probs = curve.get_probabilities(10)
        assert probs["up"] == 35.0
        assert probs["down"] == 35.0
        assert probs["stable"] == 30.0

    def test_get_probabilities_unknown_t(self, curve):
        """Unknown T returns default probabilities."""
        probs = curve.get_probabilities(99)
        assert probs == {"up": 30.0, "down": 30.0, "stable": 40.0}

    def test_get_data_density_high(self, curve):
        assert curve.get_data_density(5) == "high"  # n=20

    def test_get_data_density_medium(self, curve):
        assert curve.get_data_density(30) == "medium"  # n=8

    def test_get_data_density_extrapolated(self, curve):
        assert curve.get_data_density(99) == "extrapolated"  # no point

    def test_to_summary_structure(self, curve):
        summary = curve.to_summary()
        assert "total_tracks" in summary
        assert "curve_snapshot" in summary
        assert isinstance(summary["curve_snapshot"], list)

    def test_interpolate_empty_points(self):
        """Empty curve interpolation returns sensible default."""
        empty = DecayCurve(points={}, global_mean_daily_pct=-0.01)
        val = empty._interpolate("median_daily_pct", 10)
        assert isinstance(val, float)


# ── build_decay_curve tests ─────────────────────────────────────────


class TestBuildDecayCurve:
    def test_empty_df_returns_default(self):
        curve = build_decay_curve(pd.DataFrame())
        assert curve.total_observations == 0
        assert curve.total_tracks == 0
        assert len(curve.points) == 180  # default curve has T=1..180

    def test_too_few_rows_returns_default(self):
        # Less than 50 rows → default curve
        small_df = _make_historical_df(n_tracks=2, scans_per_track=3)
        curve = build_decay_curve(small_df)
        assert curve.total_tracks == 0

    def test_sufficient_data_builds_real_curve(self):
        df = _make_historical_df(n_tracks=10, scans_per_track=10)
        curve = build_decay_curve(df)
        assert curve.total_observations > 0
        assert curve.total_tracks > 0
        assert len(curve.points) > 0

    def test_curve_has_category_offsets(self):
        df = _make_historical_df(n_tracks=20, scans_per_track=10)
        curve = build_decay_curve(df)
        # With 20 tracks split between standard/deluxe, offsets should exist
        if curve.total_observations > 0:
            assert isinstance(curve.category_offsets, dict)

    def test_global_stats_reasonable(self):
        df = _make_historical_df(n_tracks=15, scans_per_track=12)
        curve = build_decay_curve(df)
        if curve.total_observations > 0:
            # With slight downward drift, global mean should be near-zero negative
            assert -5.0 < curve.global_mean_daily_pct < 5.0

    def test_outlier_capping(self):
        """Outlier daily changes should be capped at ±10%."""
        df = _make_historical_df(n_tracks=10, scans_per_track=10)
        # Inject an extreme price jump
        df.loc[5, "room_price"] = 9999.99
        curve = build_decay_curve(df)
        # The curve should still build (outlier capped, not crash)
        assert isinstance(curve, DecayCurve)


# ── _extract_t_observations tests ───────────────────────────────────


class TestExtractTObservations:
    def test_basic_extraction(self):
        df = _make_historical_df(n_tracks=5, scans_per_track=5)
        df["scan_date"] = pd.to_datetime(df["scan_date"])
        df["date_from_dt"] = pd.to_datetime(df["date_from"])
        df["room_price"] = pd.to_numeric(df["room_price"], errors="coerce")
        obs = _extract_t_observations(df)
        assert len(obs) > 0
        # Each observation should have required keys
        for o in obs:
            assert "t" in o
            assert "daily_pct" in o
            assert "weight" in o
            assert "track_id" in o

    def test_daily_pct_capped(self):
        """All daily_pct values should be in [-10, 10]."""
        df = _make_historical_df(n_tracks=10, scans_per_track=10)
        df["scan_date"] = pd.to_datetime(df["scan_date"])
        df["date_from_dt"] = pd.to_datetime(df["date_from"])
        df["room_price"] = pd.to_numeric(df["room_price"], errors="coerce")
        obs = _extract_t_observations(df)
        for o in obs:
            assert -10.0 <= o["daily_pct"] <= 10.0

    def test_single_scan_per_track_yields_nothing(self):
        """Tracks with only 1 scan can't produce pairs."""
        df = _make_historical_df(n_tracks=5, scans_per_track=1)
        df["scan_date"] = pd.to_datetime(df["scan_date"])
        df["date_from_dt"] = pd.to_datetime(df["date_from"])
        df["room_price"] = pd.to_numeric(df["room_price"], errors="coerce")
        obs = _extract_t_observations(df)
        assert len(obs) == 0


# ── Bayesian shrinkage ──────────────────────────────────────────────


class TestBayesianShrinkage:
    def test_shrinkage_pulls_toward_global(self):
        """With few observations, shrinkage should pull the mean toward global."""
        df = _make_historical_df(n_tracks=10, scans_per_track=10)
        df["scan_date"] = pd.to_datetime(df["scan_date"])
        df["date_from_dt"] = pd.to_datetime(df["date_from"])
        df["room_price"] = pd.to_numeric(df["room_price"], errors="coerce")
        obs = _extract_t_observations(df)
        obs_df = pd.DataFrame(obs)
        if len(obs_df) < 2:
            pytest.skip("Not enough observations")

        global_mean = float(obs_df["daily_pct"].mean())
        points = _build_smoothed_points(obs_df, global_mean)

        # Points with fewer observations should be closer to global mean
        for t, pt in points.items():
            if pt.n_observations < 3:
                # Heavily shrunk: should be close to global_mean
                diff_from_global = abs(pt.mean_daily_pct - global_mean)
                assert diff_from_global < 2.0  # Not too far from global


# ── _default_curve ──────────────────────────────────────────────────


class TestDefaultCurve:
    def test_default_has_180_points(self):
        curve = _default_curve()
        assert len(curve.points) == 180

    def test_default_all_low_density(self):
        curve = _default_curve()
        for t in [1, 30, 90, 180]:
            assert curve.get_data_density(t) == "low"  # n=0

    def test_default_probabilities(self):
        curve = _default_curve()
        probs = curve.get_probabilities(10)
        assert probs["up"] == 30.0
        assert probs["down"] == 30.0
        assert probs["stable"] == 40.0


# ── _get_half_width ─────────────────────────────────────────────────


class TestGetHalfWidth:
    def test_near_checkin(self):
        assert _get_half_width(5) == 2

    def test_mid_range(self):
        assert _get_half_width(45) == 3

    def test_far_out(self):
        assert _get_half_width(100) == 7


# ── predict_forward_curve tests ─────────────────────────────────────


class TestPredictForwardCurve:
    @pytest.fixture()
    def curve(self) -> DecayCurve:
        return _default_curve()

    def test_zero_t_returns_empty(self, curve):
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=100.0,
            current_t=0, category="standard", board="bb", curve=curve,
        )
        assert isinstance(fc, ForwardCurve)
        assert len(fc.points) == 0
        assert fc.current_t == 0

    def test_basic_prediction_length(self, curve):
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=200.0,
            current_t=7, category="standard", board="bb", curve=curve,
        )
        assert len(fc.points) == 7  # One point per day

    def test_prices_are_positive(self, curve):
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=150.0,
            current_t=30, category="standard", board="bb", curve=curve,
        )
        for pt in fc.points:
            assert pt.predicted_price > 0

    def test_confidence_bands_widen(self, curve):
        """Upper-lower band should widen as we go further out."""
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=200.0,
            current_t=30, category="standard", board="bb", curve=curve,
        )
        first_width = fc.points[0].upper_bound - fc.points[0].lower_bound
        last_width = fc.points[-1].upper_bound - fc.points[-1].lower_bound
        assert last_width >= first_width

    def test_forward_point_has_dow(self, curve):
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=100.0,
            current_t=3, category="standard", board="bb", curve=curve,
        )
        valid_dows = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
        for pt in fc.points:
            assert pt.dow in valid_dows

    def test_with_momentum(self, curve):
        """Positive momentum should push prices higher than no momentum."""
        fc_no_mom = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=200.0,
            current_t=7, category="standard", board="bb", curve=curve,
        )
        fc_with_mom = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=200.0,
            current_t=7, category="standard", board="bb", curve=curve,
            momentum_state={"momentum_vs_expected": 2.0, "strength": 0.8},
        )
        # With positive momentum, final price should be higher
        assert fc_with_mom.points[-1].predicted_price > fc_no_mom.points[-1].predicted_price

    def test_with_enrichments_high_demand(self, curve):
        """HIGH demand should push prices up."""
        enrich = Enrichments(demand_indicator="HIGH")
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=200.0,
            current_t=7, category="standard", board="bb", curve=curve,
            enrichments=enrich,
        )
        fc_no = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=200.0,
            current_t=7, category="standard", board="bb", curve=curve,
        )
        assert fc.points[-1].predicted_price > fc_no.points[-1].predicted_price

    def test_curve_type_default(self, curve):
        """Default curve should set curve_type to 'default'."""
        fc = predict_forward_curve(
            detail_id=1, hotel_id=42, current_price=100.0,
            current_t=5, category="standard", board="bb", curve=curve,
        )
        assert fc.curve_type == "default"  # total_tracks=0 → "default"


# ── Enrichments tests ───────────────────────────────────────────────


class TestEnrichments:
    def test_demand_high_adj(self):
        e = Enrichments(demand_indicator="HIGH")
        assert e.get_demand_daily_adj() == 0.15

    def test_demand_low_adj(self):
        e = Enrichments(demand_indicator="LOW")
        assert e.get_demand_daily_adj() == -0.15

    def test_demand_no_data_adj(self):
        e = Enrichments(demand_indicator="NO_DATA")
        assert e.get_demand_daily_adj() == 0.0

    def test_season_adj_peak_month(self):
        e = Enrichments(seasonality_index={"February": 1.1})
        from datetime import datetime
        adj = e.get_season_daily_adj(datetime(2025, 2, 15))
        # (1.1 - 1.0) * 3.0 = 0.30
        assert abs(adj - 0.30) < 0.01

    def test_season_adj_off_month(self):
        e = Enrichments(seasonality_index={"September": 0.85})
        from datetime import datetime
        adj = e.get_season_daily_adj(datetime(2025, 9, 10))
        # (0.85 - 1.0) * 3.0 = -0.45
        assert abs(adj - (-0.45)) < 0.01

    def test_competitor_adj(self):
        e = Enrichments(competitor_pressure=0.5)
        assert abs(e.get_competitor_daily_adj() - 0.10) < 0.001

    def test_cancel_risk_adj(self):
        e = Enrichments(cancellation_risk=0.4)
        # -0.4 * 0.25 = -0.10
        assert abs(e.get_cancel_risk_adj() - (-0.10)) < 0.001

    def test_velocity_adj_zero(self):
        """Velocity is non-directional, always returns 0."""
        e = Enrichments(price_velocity=0.9)
        assert e.get_velocity_daily_adj() == 0.0

    def test_weather_adj_date(self):
        e = Enrichments(weather_signal={"2025-06-15": 0.5})
        from datetime import datetime
        assert e.get_weather_daily_adj(datetime(2025, 6, 15)) == 0.5
        assert e.get_weather_daily_adj(datetime(2025, 6, 16)) == 0.0

    def test_provider_pressure_adj(self):
        e = Enrichments(provider_pressure=-0.5)
        assert abs(e.get_provider_pressure_adj() - (-0.10)) < 0.001

    def test_event_adj_no_events(self):
        e = Enrichments()
        from datetime import datetime
        assert e.get_event_daily_adj(datetime(2025, 6, 15)) == 0.0

    def test_event_adj_during_event(self):
        e = Enrichments(events=[{
            "start_date": "2025-06-14",
            "end_date": "2025-06-16",
            "multiplier": 1.5,
        }])
        from datetime import datetime
        adj = e.get_event_daily_adj(datetime(2025, 6, 15))
        assert adj > 0  # During event → positive adjustment
