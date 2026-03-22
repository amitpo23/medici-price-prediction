"""Tests for portfolio-level aggregation logic."""
from __future__ import annotations

import pandas as pd
import pytest

from src.analytics.portfolio_aggregator import (
    build_portfolio_summary,
    build_hotel_heatmap,
    build_hotel_drilldown,
    filter_signals_by_source,
    compute_next_scan_risk,
    compute_drop_history,
    PortfolioSummary,
    HotelHeatmapRow,
    HotelDrilldown,
    DropHistorySummary,
    NextScanRisk,
    T_BUCKETS,
)


# ── Fixtures ──────────────────────────────────────────────────────

def _make_signal(
    detail_id: int = 1,
    hotel_id: int = 100,
    hotel_name: str = "Test Hotel",
    signal: str = "CALL",
    confidence: str = "High",
    T: int = 30,
    S_t: float = 200.0,
    category: str = "standard",
    board: str = "ro",
    velocity_24h: float = 0.3,
    acceleration: float = 0.1,
    P_up: float = 75.0,
    P_down: float = 20.0,
    regime: str = "NORMAL",
    quality: str = "high",
    momentum_signal: str = "UP",
    **overrides,
) -> dict:
    sig = {
        "detail_id": str(detail_id),
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "recommendation": signal,
        "confidence": confidence,
        "T": T,
        "S_t": S_t,
        "category": category,
        "board": board,
        "expected_return_1d": 0.5,
        "P_up": P_up,
        "P_down": P_down,
        "regime": regime,
        "quality": quality,
        "momentum_signal": momentum_signal,
        "checkin_date": "2026-05-01",
        "sigma_1d": 1.2,
        "velocity_24h": velocity_24h,
        "acceleration": acceleration,
    }
    sig.update(overrides)
    return sig


def _make_signals_mixed() -> list[dict]:
    return [
        # Hotel A: 2 CALLs, 1 PUT
        _make_signal(detail_id=1, hotel_id=100, hotel_name="Hotel A", signal="CALL", confidence="High", T=5),
        _make_signal(detail_id=2, hotel_id=100, hotel_name="Hotel A", signal="CALL", confidence="Med", T=20),
        _make_signal(detail_id=3, hotel_id=100, hotel_name="Hotel A", signal="PUT", confidence="High", T=45),
        # Hotel B: 1 CALL, 2 NEUTRAL
        _make_signal(detail_id=4, hotel_id=200, hotel_name="Hotel B", signal="CALL", confidence="Low", T=10),
        _make_signal(detail_id=5, hotel_id=200, hotel_name="Hotel B", signal="NONE", confidence="Low", T=35),
        _make_signal(detail_id=6, hotel_id=200, hotel_name="Hotel B", signal="NONE", confidence="Low", T=70),
        # Hotel C: 2 PUTs
        _make_signal(detail_id=7, hotel_id=300, hotel_name="Hotel C", signal="PUT", confidence="Med", T=15),
        _make_signal(detail_id=8, hotel_id=300, hotel_name="Hotel C", signal="PUT", confidence="High", T=50),
    ]


# ── Portfolio Summary Tests ───────────────────────────────────────

class TestBuildPortfolioSummary:
    def test_counts_signals_correctly(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals)
        assert summary.total_options == 8
        assert summary.calls == 3
        assert summary.puts == 3
        assert summary.neutrals == 2

    def test_counts_hotels(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals)
        assert summary.total_hotels == 3

    def test_average_confidence_high(self):
        signals = [_make_signal(detail_id=i, confidence="High") for i in range(5)]
        summary = build_portfolio_summary(signals)
        assert summary.avg_confidence == "High"

    def test_average_confidence_med(self):
        signals = [
            _make_signal(detail_id=1, confidence="High"),
            _make_signal(detail_id=2, confidence="Med"),
            _make_signal(detail_id=3, confidence="Low"),
        ]
        summary = build_portfolio_summary(signals)
        assert summary.avg_confidence == "Med"

    def test_empty_signals(self):
        summary = build_portfolio_summary([])
        assert summary.total_options == 0
        assert summary.total_hotels == 0
        assert summary.calls == 0

    def test_theta_from_greeks(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals, greeks={"total_theta": -2300.0})
        assert summary.theta_daily == -2300.0

    def test_theta_none_without_greeks(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals)
        assert summary.theta_daily is None

    def test_to_dict(self):
        summary = build_portfolio_summary([_make_signal()])
        d = summary.to_dict()
        assert isinstance(d, dict)
        assert "total_options" in d
        assert "calls" in d


# ── Hotel Heatmap Tests ──────────────────────────────────────────

class TestBuildHotelHeatmap:
    def test_returns_one_row_per_hotel(self):
        signals = _make_signals_mixed()
        rows = build_hotel_heatmap(signals)
        assert len(rows) == 3

    def test_rows_sorted_by_name(self):
        signals = _make_signals_mixed()
        rows = build_hotel_heatmap(signals)
        names = [r.hotel_name for r in rows]
        assert names == sorted(names)

    def test_each_row_has_5_t_buckets(self):
        signals = _make_signals_mixed()
        rows = build_hotel_heatmap(signals)
        for row in rows:
            assert len(row.buckets) == 5
            assert [b.bucket for b in row.buckets] == ["0-14", "15-30", "31-60", "61-90", "91+"]

    def test_t_bucket_assignment(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, T=3),
            _make_signal(detail_id=2, hotel_id=100, T=20),
            _make_signal(detail_id=3, hotel_id=100, T=45),
            _make_signal(detail_id=4, hotel_id=100, T=75),
            _make_signal(detail_id=5, hotel_id=100, T=95),
        ]
        rows = build_hotel_heatmap(signals)
        assert len(rows) == 1
        buckets = rows[0].buckets
        assert buckets[0].count == 1  # 0-14
        assert buckets[1].count == 1  # 15-30
        assert buckets[2].count == 1  # 31-60
        assert buckets[3].count == 1  # 61-90
        assert buckets[4].count == 1  # 91+

    def test_dominant_signal_in_bucket(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, signal="CALL", T=5),
            _make_signal(detail_id=2, hotel_id=100, signal="CALL", T=6),
            _make_signal(detail_id=3, hotel_id=100, signal="PUT", T=7),
        ]
        rows = build_hotel_heatmap(signals)
        assert rows[0].buckets[0].dominant_signal == "CALL"

    def test_agreement_score_from_external(self):
        signals = [_make_signal(detail_id=1, hotel_id=100)]
        rows = build_hotel_heatmap(signals, source_agreement={100: 85.5})
        assert rows[0].agreement_score == 85.5

    def test_empty_signals(self):
        assert build_hotel_heatmap([]) == []

    def test_avg_price_computed(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, S_t=200.0),
            _make_signal(detail_id=2, hotel_id=100, S_t=300.0),
        ]
        rows = build_hotel_heatmap(signals)
        assert rows[0].avg_price == 250.0

    def test_hotel_dominant_signal(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, signal="PUT"),
            _make_signal(detail_id=2, hotel_id=100, signal="PUT"),
            _make_signal(detail_id=3, hotel_id=100, signal="CALL"),
        ]
        rows = build_hotel_heatmap(signals)
        assert rows[0].dominant_signal == "PUT"


# ── Hotel Drilldown Tests ────────────────────────────────────────

class TestBuildHotelDrilldown:
    def test_returns_none_for_unknown_hotel(self):
        result = build_hotel_drilldown(_make_signals_mixed(), hotel_id=999)
        assert result is None

    def test_correct_signal_counts(self):
        dd = build_hotel_drilldown(_make_signals_mixed(), hotel_id=100)
        assert dd is not None
        assert dd.calls == 2
        assert dd.puts == 1
        assert dd.neutrals == 0

    def test_t_distribution_has_5_bars(self):
        dd = build_hotel_drilldown(_make_signals_mixed(), hotel_id=100)
        assert len(dd.t_distribution) == 5

    def test_options_list_matches_hotel(self):
        dd = build_hotel_drilldown(_make_signals_mixed(), hotel_id=100)
        assert len(dd.options) == 3

    def test_options_sorted_puts_first(self):
        dd = build_hotel_drilldown(_make_signals_mixed(), hotel_id=100)
        signal_types = [o["signal"] for o in dd.options]
        assert signal_types.index("PUT") < signal_types.index("CALL")

    def test_options_have_next_scan_risk(self):
        dd = build_hotel_drilldown(_make_signals_mixed(), hotel_id=100)
        for opt in dd.options:
            assert "next_scan_risk" in opt
            assert "score" in opt["next_scan_risk"]
            assert "label" in opt["next_scan_risk"]

    def test_source_agreement_with_predictions(self):
        signals = [_make_signal(detail_id=1, hotel_id=100, S_t=200.0)]
        predictions = {
            "1": {
                "fc_price": 210.0,
                "hist_price": 210.0,
                "ml_price": 190.0,
                "predicted_checkin_price": 207.0,
                "current_price": 200.0,
            },
        }
        dd = build_hotel_drilldown(signals, hotel_id=100, predictions=predictions)
        assert len(dd.source_agreement) == 3
        fc_row = next(r for r in dd.source_agreement if r.source == "forward_curve")
        ml_row = next(r for r in dd.source_agreement if r.source == "ml")
        assert fc_row.agreement_pct == 100.0
        assert ml_row.agreement_pct == 0.0

    def test_source_agreement_empty_without_predictions(self):
        dd = build_hotel_drilldown([_make_signal(hotel_id=100)], hotel_id=100)
        assert len(dd.source_agreement) == 0

    def test_drop_history_passed_through(self):
        drop = DropHistorySummary(total_drops_7d=5, avg_drop_pct=-3.2)
        dd = build_hotel_drilldown(
            [_make_signal(hotel_id=100)], hotel_id=100, drop_history=drop,
        )
        assert dd.drop_history.total_drops_7d == 5
        assert dd.drop_history.avg_drop_pct == -3.2

    def test_to_dict(self):
        dd = build_hotel_drilldown(_make_signals_mixed(), hotel_id=100)
        d = dd.to_dict()
        assert isinstance(d, dict)
        assert "t_distribution" in d
        assert "options" in d


# ── Next-Scan Risk Tests ─────────────────────────────────────────

class TestComputeNextScanRisk:
    def test_neutral_for_calm_signal(self):
        sig = _make_signal(velocity_24h=0.1, acceleration=0.05, P_down=15, regime="NORMAL", momentum_signal="UP")
        risk = compute_next_scan_risk(sig)
        assert risk.label == "NEUTRAL"
        assert risk.score < 30

    def test_watch_for_moderate_risk(self):
        sig = _make_signal(velocity_24h=-0.5, acceleration=-0.1, P_down=42, regime="NORMAL", momentum_signal="DOWN")
        risk = compute_next_scan_risk(sig)
        assert risk.label == "WATCH"

    def test_put_for_high_risk(self):
        sig = _make_signal(velocity_24h=-3.5, acceleration=-0.5, P_down=65, regime="NORMAL", momentum_signal="DOWN", category="deluxe")
        risk = compute_next_scan_risk(sig)
        assert risk.label in ("PUT", "STRONG_PUT")
        assert risk.score > 50

    def test_strong_put_for_extreme(self):
        sig = _make_signal(velocity_24h=-5.0, acceleration=-1.0, P_down=80, regime="VOLATILE", momentum_signal="ACCELERATING_DOWN", category="suite")
        risk = compute_next_scan_risk(sig)
        assert risk.label == "STRONG_PUT"
        assert risk.score > 70

    def test_volatile_regime_adds_score(self):
        calm = _make_signal(regime="NORMAL")
        volatile = _make_signal(regime="VOLATILE")
        assert compute_next_scan_risk(volatile).score > compute_next_scan_risk(calm).score


# ── Source Filtering Tests ────────────────────────────────────────

class TestFilterSignalsBySource:
    def test_ensemble_returns_original(self):
        signals = _make_signals_mixed()
        result = filter_signals_by_source(signals, {}, "ensemble")
        assert result is signals

    def test_fc_filter_derives_signal(self):
        signals = [_make_signal(detail_id=1, hotel_id=100, S_t=200.0)]
        predictions = {
            "1": {"fc_price": 250.0, "current_price": 200.0, "predicted_checkin_price": 220.0},
        }
        result = filter_signals_by_source(signals, predictions, "forward_curve")
        assert len(result) == 1
        assert result[0]["recommendation"] == "CALL"
        assert result[0]["source_filter"] == "forward_curve"

    def test_ml_filter_put_signal(self):
        signals = [_make_signal(detail_id=1, hotel_id=100, S_t=200.0)]
        predictions = {
            "1": {"ml_price": 150.0, "current_price": 200.0, "predicted_checkin_price": 220.0},
        }
        result = filter_signals_by_source(signals, predictions, "ml")
        assert result[0]["recommendation"] == "PUT"

    def test_unknown_source_returns_original(self):
        signals = _make_signals_mixed()
        result = filter_signals_by_source(signals, {}, "unknown")
        assert result is signals

    def test_skips_signals_without_prediction(self):
        signals = [_make_signal(detail_id=1), _make_signal(detail_id=2)]
        predictions = {"1": {"fc_price": 250.0, "current_price": 200.0, "predicted_checkin_price": 220.0}}
        result = filter_signals_by_source(signals, predictions, "forward_curve")
        assert len(result) == 1


# ── Drop History Tests ────────────────────────────────────────────

class TestComputeDropHistory:
    def test_empty_dataframe(self):
        result = compute_drop_history(pd.DataFrame(), hotel_id=100)
        assert result.total_drops_7d == 0

    def test_none_dataframe(self):
        result = compute_drop_history(None, hotel_id=100)
        assert result.total_drops_7d == 0

    def test_counts_drops(self):
        now = pd.Timestamp.now()
        df = pd.DataFrame({
            "hotel_id": [100, 100, 100, 100],
            "detail_id": [1, 1, 1, 1],
            "snapshot_ts": [
                now - pd.Timedelta(hours=9),
                now - pd.Timedelta(hours=6),
                now - pd.Timedelta(hours=3),
                now,
            ],
            "room_price": [200.0, 195.0, 190.0, 188.0],
        })
        result = compute_drop_history(df, hotel_id=100)
        assert result.total_drops_7d == 3
        assert result.avg_drop_pct < 0
        assert result.rooms_with_drops == 1

    def test_ignores_other_hotels(self):
        now = pd.Timestamp.now()
        df = pd.DataFrame({
            "hotel_id": [100, 200],
            "detail_id": [1, 2],
            "snapshot_ts": [now - pd.Timedelta(hours=3), now],
            "room_price": [200.0, 150.0],
        })
        result = compute_drop_history(df, hotel_id=100)
        # Only one row for hotel 100 → no consecutive pair → no drops
        assert result.total_drops_7d == 0

    def test_ignores_old_data(self):
        now = pd.Timestamp.now()
        df = pd.DataFrame({
            "hotel_id": [100, 100],
            "detail_id": [1, 1],
            "snapshot_ts": [now - pd.Timedelta(days=10), now - pd.Timedelta(days=9)],
            "room_price": [200.0, 180.0],
        })
        result = compute_drop_history(df, hotel_id=100, days=7)
        assert result.total_drops_7d == 0
