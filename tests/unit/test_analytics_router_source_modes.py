"""Regression tests for source-specific option prediction views."""
from __future__ import annotations

from src.api.routers.analytics_router import _build_prediction_view


def _sample_prediction() -> dict:
    return {
        "current_price": 100.0,
        "predicted_checkin_price": 112.0,
        "expected_change_pct": 12.0,
        "days_to_checkin": 4,
        "date_from": "2026-04-01",
        "cancel_probability": 0.4,
        "market_benchmark": {
            "market_avg_price": 118.0,
            "pressure": 0.12,
            "competitor_hotels": 6,
        },
        "source_inputs": {
            "provider_pressure": 0.25,
            "price_velocity": 0.2,
            "cancellation_risk": 0.4,
        },
        "signals": [
            {
                "source": "forward_curve",
                "predicted_price": 112.0,
                "confidence": 0.81,
                "weight": 0.5,
                "reasoning": "Forward curve baseline.",
            },
            {
                "source": "historical_pattern",
                "predicted_price": 106.0,
                "confidence": 0.68,
                "weight": 0.3,
                "reasoning": "Historical pattern signal.",
            },
            {
                "source": "ml_forecast",
                "predicted_price": 109.0,
                "confidence": 0.61,
                "weight": 0.2,
                "reasoning": "ML forecast signal.",
            },
        ],
        "forward_curve": [
            {
                "date": "2026-03-28",
                "t": 4,
                "predicted_price": 100.0,
                "daily_change_pct": 0.0,
                "cumulative_change_pct": 0.0,
                "lower_bound": 100.0,
                "upper_bound": 100.0,
                "volatility_at_t": 0.0,
                "event_adj_pct": 0.0,
                "season_adj_pct": 0.0,
                "demand_adj_pct": 0.0,
                "momentum_adj_pct": 0.0,
                "weather_adj_pct": 0.0,
            },
            {
                "date": "2026-03-29",
                "t": 3,
                "predicted_price": 102.0,
                "daily_change_pct": 2.0,
                "cumulative_change_pct": 2.0,
                "lower_bound": 102.0,
                "upper_bound": 102.0,
                "volatility_at_t": 0.0,
                "event_adj_pct": 0.1,
                "season_adj_pct": 0.2,
                "demand_adj_pct": 0.0,
                "momentum_adj_pct": 0.0,
                "weather_adj_pct": -0.3,
            },
            {
                "date": "2026-03-30",
                "t": 2,
                "predicted_price": 105.0,
                "daily_change_pct": 2.94,
                "cumulative_change_pct": 5.0,
                "lower_bound": 105.0,
                "upper_bound": 105.0,
                "volatility_at_t": 0.0,
                "event_adj_pct": 0.0,
                "season_adj_pct": 0.15,
                "demand_adj_pct": 0.25,
                "momentum_adj_pct": 0.0,
                "weather_adj_pct": 0.0,
            },
            {
                "date": "2026-03-31",
                "t": 1,
                "predicted_price": 108.0,
                "daily_change_pct": 2.86,
                "cumulative_change_pct": 8.0,
                "lower_bound": 108.0,
                "upper_bound": 108.0,
                "volatility_at_t": 0.0,
                "event_adj_pct": 0.0,
                "season_adj_pct": 0.1,
                "demand_adj_pct": 0.0,
                "momentum_adj_pct": 0.5,
                "weather_adj_pct": 0.0,
            },
            {
                "date": "2026-04-01",
                "t": 0,
                "predicted_price": 112.0,
                "daily_change_pct": 3.7,
                "cumulative_change_pct": 12.0,
                "lower_bound": 112.0,
                "upper_bound": 112.0,
                "volatility_at_t": 0.0,
                "event_adj_pct": 0.0,
                "season_adj_pct": 0.0,
                "demand_adj_pct": 0.2,
                "momentum_adj_pct": 0.0,
                "weather_adj_pct": 0.0,
            },
        ],
    }


def test_source_only_prediction_changes_with_selected_source() -> None:
    pred = _sample_prediction()

    forward_curve_view = _build_prediction_view(pred, "forward_curve", True)
    historical_view = _build_prediction_view(pred, "historical_pattern", True)
    cancellation_view = _build_prediction_view(pred, "cancellation_data", True)
    weather_view = _build_prediction_view(pred, "open_meteo", True)

    assert forward_curve_view["predicted_checkin_price"] == 112.0
    assert historical_view["predicted_checkin_price"] == 106.0
    assert cancellation_view["predicted_checkin_price"] < forward_curve_view["predicted_checkin_price"]
    assert weather_view["predicted_checkin_price"] != forward_curve_view["predicted_checkin_price"]

    assert historical_view["source_analysis"]["selected_source"] == "historical_pattern"
    assert cancellation_view["source_analysis"]["selected_source"] == "cancellation_data"
    assert weather_view["source_analysis"]["selected_source"] == "open_meteo"
    assert weather_view["signals"][0]["source"] == "open_meteo"


def test_ensemble_view_exposes_source_prediction_catalog() -> None:
    pred = _sample_prediction()

    ensemble_view = _build_prediction_view(pred, None, False)
    source_predictions = ensemble_view["source_predictions"]

    assert source_predictions["forward_curve"]["predicted_price"] == 112.0
    assert source_predictions["historical_pattern"]["predicted_price"] == 106.0
    assert source_predictions["salesoffice"]["basis"] == "forward_curve"
    assert source_predictions["cancellation_data"]["basis"] == "cancellation_risk"
    assert source_predictions["open_meteo"]["basis"] == "weather_adj_pct"
    assert source_predictions["search_results_poll_log"]["basis"] == "provider_pressure"
    assert "_source_prediction_summary_catalog" in pred


def test_source_only_horizon_updates_selected_source_entry() -> None:
    pred = _sample_prediction()

    view = _build_prediction_view(pred, "historical_pattern", True, t_days=2)

    assert view["predicted_checkin_price"] == view["source_predictions"]["historical_pattern"]["predicted_price"]
    assert view["predicted_checkin_price"] == 103.0
