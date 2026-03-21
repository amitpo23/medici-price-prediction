"""Core analytics endpoints — JSON APIs for data, options, forward curve, backtest."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from config.constants import CANCELLATION_IMPACT_MAX, COMPETITOR_IMPACT_MAX, PROVIDER_IMPACT_MAX
from config.settings import SALESOFFICE_PRECOMPUTE_DETAIL_LIMIT, SALESOFFICE_PRECOMPUTE_T_DAYS
from src.api.middleware import limiter, RATE_LIMIT_DATA
from src.api.models.pagination import pagination_params, paginate

from src.api.routers._shared_state import (
    _analysis_warming,
    _optional_api_key,
    _get_cached_analysis,
    _get_or_run_analysis,
    _kickoff_analysis_warmup,
    _is_scheduler_running,
    _run_collection_cycle,
    _extract_curve_points,
    _derive_option_signal,
    _extract_sources,
    _build_quality_summary,
    _build_option_levels,
    _build_info_badge,
    _build_row_chart,
    _build_put_path_insights,
    _build_source_validation,
    _build_sources_audit,
    _build_system_capabilities,
    _get_cached_signals,
    COLLECTION_INTERVAL,
)
from src.utils.cache_manager import cache as _cm

logger = logging.getLogger(__name__)

analytics_router = APIRouter()

DIRECT_SIGNAL_SOURCES = {"forward_curve", "historical_pattern", "ml_forecast"}

SOURCE_ALIAS_TO_METHOD = {
    "salesoffice": "forward_curve",
    "med_search_hotels": "historical_pattern",
    "room_price_update_log": "momentum",
    "hotel_booking_dataset": "seasonality",
    "cancellation_data": "cancellation",
    "kiwi_flights": "demand",
    "open_meteo": "weather",
    "miami_events_hardcoded": "events",
    "seatgeek": "events",
    "predicthq": "events",
    "ai_search_hotel_data": "market_benchmark",
    "tbo_hotels": "market_benchmark",
    "ota_brightdata_exports": "market_benchmark",
    "destinations_geo": "market_benchmark",
    "xotelo": "market_benchmark",
    "serpapi_hotels": "market_benchmark",
    "trivago_statista": "market_benchmark",
    "search_results_poll_log": "provider_pressure",
    "med_prebook": "provider_pressure",
    "salesoffice_log": "price_velocity",
}

SUPPORTED_ANALYSIS_SOURCES = DIRECT_SIGNAL_SOURCES | set(SOURCE_ALIAS_TO_METHOD)
OPTIONS_CACHE_REGION = "salesoffice_options"
DETAIL_CACHE_REGION = "salesoffice_detail"
PRECOMPUTE_SOURCE_ONLY_SOURCES = ("forward_curve", "historical_pattern", "ml_forecast")


def _normalize_source_key(source: str | None) -> str | None:
    if not source:
        return None
    value = source.strip().lower()
    return value if value in SUPPORTED_ANALYSIS_SOURCES else None


def _build_linear_curve_from_target(
    pred: dict,
    target_price: float,
    t_days: int | None,
) -> list[dict]:
    synthetic_signal = {"predicted_price": target_price}
    return _build_source_only_forward_curve(pred, "synthetic", synthetic_signal, t_days)


def _build_adjustment_only_curve(
    pred: dict,
    adjustment_key: str,
    t_days: int | None,
) -> list[dict]:
    base_curve = list(pred.get("forward_curve") or [])
    if isinstance(t_days, int) and t_days > 0:
        base_curve = base_curve[:t_days]

    current_price = float(pred.get("current_price", 0) or 0)
    days_to_checkin = max(int(pred.get("days_to_checkin", 0) or 0), 1)
    curve = [{
        "date": "today",
        "t": days_to_checkin,
        "predicted_price": round(current_price, 2),
        "daily_change_pct": 0.0,
        "cumulative_change_pct": 0.0,
        "lower_bound": round(current_price, 2),
        "upper_bound": round(current_price, 2),
        "volatility_at_t": 0.0,
        "event_adj_pct": 0.0,
        "season_adj_pct": 0.0,
        "demand_adj_pct": 0.0,
        "momentum_adj_pct": 0.0,
        "weather_adj_pct": 0.0,
    }]
    if not base_curve:
        return curve

    price = current_price
    for idx, point in enumerate(base_curve, start=1):
        daily_adj = float(point.get(adjustment_key, 0) or 0)
        price *= (1.0 + (daily_adj / 100.0))
        cumulative = ((price / current_price - 1.0) * 100.0) if current_price > 0 else 0.0
        curve.append({
            "date": point.get("date") or f"T+{idx}",
            "t": point.get("t", max(days_to_checkin - idx, 0)),
            "predicted_price": round(price, 2),
            "daily_change_pct": round(daily_adj, 4),
            "cumulative_change_pct": round(cumulative, 4),
            "lower_bound": round(price, 2),
            "upper_bound": round(price, 2),
            "volatility_at_t": 0.0,
            "event_adj_pct": round(float(point.get("event_adj_pct", 0) or 0), 4),
            "season_adj_pct": round(float(point.get("season_adj_pct", 0) or 0), 4),
            "demand_adj_pct": round(float(point.get("demand_adj_pct", 0) or 0), 4),
            "momentum_adj_pct": round(float(point.get("momentum_adj_pct", 0) or 0), 4),
            "weather_adj_pct": round(float(point.get("weather_adj_pct", 0) or 0), 4),
        })
    return curve


def _curve_confidence(curve: list[dict], default: float = 0.45) -> float:
    if len(curve) <= 1:
        return default
    adjustments = [
        abs(float(point.get("daily_change_pct", 0) or 0))
        for point in curve[1:]
    ]
    if not adjustments:
        return default
    non_zero = sum(1 for value in adjustments if value > 0.0001)
    return min(0.85, max(default, 0.35 + (non_zero / max(len(adjustments), 1)) * 0.4))


def _serialize_source_prediction(prediction: dict) -> dict:
    return {
        "source": prediction.get("source"),
        "predicted_price": prediction.get("predicted_price"),
        "confidence": prediction.get("confidence"),
        "weight": prediction.get("weight", 1.0),
        "reasoning": prediction.get("reasoning", ""),
        "basis": prediction.get("basis"),
        "reliability": prediction.get("reliability"),
    }


def _serialize_compact_source_prediction(prediction: dict) -> dict:
    return {
        "predicted_price": prediction.get("predicted_price"),
        "confidence": prediction.get("confidence"),
        "basis": prediction.get("basis"),
        "reliability": prediction.get("reliability"),
    }


def _build_source_prediction_summary_catalog(pred: dict) -> dict[str, dict]:
    current_price = float(pred.get("current_price", 0) or 0)
    market = pred.get("market_benchmark") or {}
    source_inputs = pred.get("source_inputs") or {}
    catalog: dict[str, dict] = {}

    for signal in (pred.get("signals") or []):
        signal_source = str(signal.get("source", "")).strip().lower()
        if not signal_source:
            continue
        catalog[signal_source] = {
            "source": signal_source,
            "predicted_price": round(float(signal.get("predicted_price", current_price) or current_price), 2),
            "confidence": round(float(signal.get("confidence", 0) or 0), 2),
            "weight": round(float(signal.get("weight", 1.0) or 1.0), 3),
            "reasoning": signal.get("reasoning", ""),
            "basis": "native_signal",
            "reliability": _confidence_quality_from_value(signal.get("confidence")),
        }

    alias_signal_map = {
        "salesoffice": "forward_curve",
        "med_search_hotels": "historical_pattern",
    }
    for alias_key, native_key in alias_signal_map.items():
        native = catalog.get(native_key)
        if native:
            catalog[alias_key] = {
                "source": alias_key,
                "predicted_price": native["predicted_price"],
                "confidence": native.get("confidence"),
                "weight": 1.0,
                "reasoning": native.get("reasoning", "") or f"Standalone view mapped from {native_key}",
                "basis": native_key,
                "reliability": native.get("reliability"),
            }

    adjustment_sources = {
        "room_price_update_log": ("momentum_adj_pct", "Momentum-only path from Room Price Update Log velocity and recent directional pressure."),
        "kiwi_flights": ("demand_adj_pct", "Demand-only path from Kiwi flight demand indicator for Miami."),
        "open_meteo": ("weather_adj_pct", "Weather-only path from Open-Meteo forecast adjustments."),
        "miami_events_hardcoded": ("event_adj_pct", "Event-only path from Miami Major Events calendar."),
        "seatgeek": ("event_adj_pct", "Event-only path from SeatGeek-driven event enrichment."),
        "predicthq": ("event_adj_pct", "Event-only path from PredictHQ event enrichment when available."),
        "hotel_booking_dataset": ("season_adj_pct", "Seasonality-only path from Hotel Booking Demand benchmark dataset."),
    }
    for source_key, (adj_key, reasoning) in adjustment_sources.items():
        curve = _build_adjustment_only_curve(pred, adj_key, None)
        catalog[source_key] = {
            "source": source_key,
            "predicted_price": round(float(curve[-1].get("predicted_price", current_price) or current_price), 2),
            "confidence": round(_curve_confidence(curve), 2),
            "weight": 1.0,
            "reasoning": reasoning,
            "basis": adj_key,
            "reliability": _confidence_quality_from_value(_curve_confidence(curve)),
        }

    market_avg_price = float(market.get("market_avg_price", 0) or 0)
    market_confidence = 0.65 if market_avg_price > 0 else 0.25
    market_target = market_avg_price if market_avg_price > 0 else current_price
    market_reasoning = (
        f"Market benchmark view from same-star city competitors: avg=${market_avg_price:.2f}, "
        f"pressure={float(market.get('pressure', 0) or 0):+.2f}, competitors={int(market.get('competitor_hotels', 0) or 0)}"
    )
    for source_key in ("ai_search_hotel_data", "tbo_hotels", "ota_brightdata_exports", "destinations_geo", "xotelo", "serpapi_hotels", "trivago_statista"):
        catalog[source_key] = {
            "source": source_key,
            "predicted_price": round(market_target, 2),
            "confidence": round(market_confidence, 2),
            "weight": 1.0,
            "reasoning": market_reasoning,
            "basis": "market_benchmark",
            "reliability": _confidence_quality_from_value(market_confidence),
        }

    days_to_checkin = max(int(pred.get("days_to_checkin", 0) or 0), 1)
    cancel_prob = float(pred.get("cancel_probability", source_inputs.get("cancellation_risk", 0)) or 0)
    cancel_daily_adj = -(cancel_prob * CANCELLATION_IMPACT_MAX)
    cancel_target = current_price * ((1.0 + (cancel_daily_adj / 100.0)) ** days_to_checkin)
    catalog["cancellation_data"] = {
        "source": "cancellation_data",
        "predicted_price": round(cancel_target, 2),
        "confidence": round(min(0.75, 0.35 + cancel_prob), 2),
        "weight": 1.0,
        "reasoning": f"Cancellation-risk-only path using cancel probability {cancel_prob:.3f} with daily cap {CANCELLATION_IMPACT_MAX:.2f}%.",
        "basis": "cancellation_risk",
        "reliability": _confidence_quality_from_value(min(0.75, 0.35 + cancel_prob)),
    }

    provider_pressure = float(source_inputs.get("provider_pressure", 0) or 0)
    provider_daily_adj = provider_pressure * PROVIDER_IMPACT_MAX
    provider_target = current_price * ((1.0 + (provider_daily_adj / 100.0)) ** days_to_checkin)
    provider_conf = min(0.7, 0.35 + abs(provider_pressure) * 0.35)
    for source_key in ("search_results_poll_log", "med_prebook"):
        catalog[source_key] = {
            "source": source_key,
            "predicted_price": round(provider_target, 2),
            "confidence": round(provider_conf, 2),
            "weight": 1.0,
            "reasoning": f"Provider-pressure-only path from search and prebook data (pressure={provider_pressure:+.3f}, daily_adj={provider_daily_adj:+.3f}%).",
            "basis": "provider_pressure",
            "reliability": _confidence_quality_from_value(provider_conf),
        }

    velocity = float(source_inputs.get("price_velocity", 0) or 0)
    catalog["salesoffice_log"] = {
        "source": "salesoffice_log",
        "predicted_price": round(current_price, 2),
        "confidence": round(min(0.55, 0.25 + velocity * 0.3), 2),
        "weight": 1.0,
        "reasoning": f"Operational scan-log view: velocity={velocity:.3f}. This source affects volatility and reliability more than direction.",
        "basis": "price_velocity",
        "reliability": _confidence_quality_from_value(min(0.55, 0.25 + velocity * 0.3)),
    }

    return catalog


def _get_source_prediction_summary_catalog(pred: dict) -> dict[str, dict]:
    cached_catalog = pred.get("_source_prediction_summary_catalog")
    if isinstance(cached_catalog, dict) and cached_catalog:
        return cached_catalog

    catalog = _build_source_prediction_summary_catalog(pred)
    pred["_source_prediction_summary_catalog"] = catalog
    return catalog


def _build_source_prediction_curve(
    pred: dict,
    source_key: str,
    source_prediction: dict,
    t_days: int | None,
) -> list[dict]:
    basis = source_prediction.get("basis")
    if source_key == "forward_curve" or basis == "native_signal":
        return _build_source_only_forward_curve(pred, source_key, source_prediction, t_days)
    if basis in {"forward_curve", "historical_pattern"}:
        return _build_linear_curve_from_target(pred, float(source_prediction.get("predicted_price", 0) or 0), t_days)
    if basis in {"momentum_adj_pct", "demand_adj_pct", "weather_adj_pct", "event_adj_pct", "season_adj_pct"}:
        return _build_adjustment_only_curve(pred, str(basis), t_days)
    return _build_linear_curve_from_target(pred, float(source_prediction.get("predicted_price", 0) or 0), t_days)


def _confidence_quality_from_value(confidence: float | None) -> str:
    value = float(confidence or 0)
    if value >= 0.75:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def _build_source_only_forward_curve(
    pred: dict,
    source_key: str,
    source_signal: dict,
    t_days: int | None,
) -> list[dict]:
    if source_key == "forward_curve":
        return list(pred.get("forward_curve") or [])

    current_price = float(pred.get("current_price", 0) or 0)
    target_price = float(source_signal.get("predicted_price", current_price) or current_price)
    days_to_checkin = max(int(pred.get("days_to_checkin", 0) or 0), 1)
    horizon_days = days_to_checkin
    if isinstance(t_days, int) and t_days > 0:
        horizon_days = max(1, min(days_to_checkin, t_days))

    ratio = min(1.0, horizon_days / max(days_to_checkin, 1))
    horizon_price = current_price + ((target_price - current_price) * ratio)
    horizon_label = str(pred.get("date_from") or "checkin") if ratio >= 1.0 else f"T+{horizon_days}"
    cumulative_change_pct = ((horizon_price / current_price - 1.0) * 100.0) if current_price > 0 else 0.0

    return [
        {
            "date": "today",
            "t": horizon_days,
            "predicted_price": round(current_price, 2),
            "daily_change_pct": 0.0,
            "cumulative_change_pct": 0.0,
            "lower_bound": round(current_price, 2),
            "upper_bound": round(current_price, 2),
            "volatility_at_t": 0.0,
            "event_adj_pct": 0.0,
            "season_adj_pct": 0.0,
            "demand_adj_pct": 0.0,
            "momentum_adj_pct": 0.0,
        },
        {
            "date": horizon_label,
            "t": max(days_to_checkin - horizon_days, 0),
            "predicted_price": round(horizon_price, 2),
            "daily_change_pct": round(cumulative_change_pct, 2),
            "cumulative_change_pct": round(cumulative_change_pct, 2),
            "lower_bound": round(horizon_price, 2),
            "upper_bound": round(horizon_price, 2),
            "volatility_at_t": 0.0,
            "event_adj_pct": 0.0,
            "season_adj_pct": 0.0,
            "demand_adj_pct": 0.0,
            "momentum_adj_pct": 0.0,
        },
    ]


def _build_prediction_view(
    pred: dict,
    source_key: str | None,
    source_only: bool,
    t_days: int | None = None,
) -> dict:
    normalized_source = _normalize_source_key(source_key)
    source_catalog = _get_source_prediction_summary_catalog(pred)
    if not source_only or not normalized_source:
        pred_view = dict(pred)
        pred_view["source_predictions"] = {
            key: _serialize_source_prediction(value)
            for key, value in source_catalog.items()
        }
        return pred_view

    source_signal = source_catalog.get(normalized_source)
    if source_signal is None:
        pred_view = dict(pred)
        pred_view["source_predictions"] = {
            key: _serialize_source_prediction(value)
            for key, value in source_catalog.items()
        }
        return pred_view

    current_price = float(pred.get("current_price", 0) or 0)
    forward_curve = list(_build_source_prediction_curve(pred, normalized_source, source_signal, t_days))
    predicted_price = float(forward_curve[-1].get("predicted_price", current_price) or current_price)
    expected_change_pct = ((predicted_price / current_price - 1.0) * 100.0) if current_price > 0 else 0.0
    confidence = float(source_signal.get("confidence", 0) or 0)
    if source_signal.get("basis") in {"momentum_adj_pct", "demand_adj_pct", "weather_adj_pct", "event_adj_pct", "season_adj_pct"}:
        confidence = float(_curve_confidence(forward_curve, default=confidence or 0.45) or 0)

    pred_view = dict(pred)
    pred_view["predicted_checkin_price"] = round(predicted_price, 2)
    pred_view["expected_change_pct"] = round(expected_change_pct, 2)
    pred_view["confidence_quality"] = _confidence_quality_from_value(confidence)
    pred_view["model_type"] = f"source_only:{normalized_source}"
    pred_view["prediction_method"] = f"source_only:{normalized_source}"
    pred_view["signals"] = [{
        "source": normalized_source,
        "predicted_price": round(predicted_price, 2),
        "confidence": round(confidence, 2),
        "weight": 1.0,
        "reasoning": source_signal.get("reasoning", ""),
    }]
    pred_view["source_predictions"] = {
        key: _serialize_source_prediction(value)
        for key, value in source_catalog.items()
    }
    pred_view["source_predictions"][normalized_source] = _serialize_source_prediction({
        **source_signal,
        "predicted_price": round(predicted_price, 2),
        "confidence": round(confidence, 2),
        "reliability": _confidence_quality_from_value(confidence),
    })
    pred_view["source_analysis"] = {
        "mode": "source_only",
        "selected_source": normalized_source,
        "native_curve": normalized_source == "forward_curve",
        "available_sources": list(source_catalog.keys()),
    }

    if normalized_source != "forward_curve":
        pred_view["probability"] = {}

    pred_view["forward_curve"] = forward_curve
    pred_view["daily"] = [
        {
            "date": point.get("date"),
            "days_remaining": point.get("t"),
            "predicted_price": point.get("predicted_price"),
            "lower_bound": point.get("lower_bound"),
            "upper_bound": point.get("upper_bound"),
            "dow": None,
        }
        for point in forward_curve
    ]
    return pred_view


def _build_row_scan_history(scan: dict, include_series: bool = True) -> dict:
    row_scan_history = {
        "scan_snapshots": scan.get("scan_snapshots", 0),
        "first_scan_date": scan.get("first_scan_date"),
        "first_scan_price": scan.get("first_scan_price"),
        "latest_scan_date": scan.get("latest_scan_date"),
        "latest_scan_price": scan.get("latest_scan_price"),
        "scan_price_change": scan.get("scan_price_change", 0),
        "scan_price_change_pct": scan.get("scan_price_change_pct", 0),
        "scan_actual_drops": scan.get("scan_actual_drops", 0),
        "scan_actual_rises": scan.get("scan_actual_rises", 0),
        "scan_total_drop_amount": scan.get("scan_total_drop_amount", 0),
        "scan_total_rise_amount": scan.get("scan_total_rise_amount", 0),
        "scan_max_single_drop": scan.get("scan_max_single_drop", 0),
        "scan_max_single_rise": scan.get("scan_max_single_rise", 0),
        "scan_trend": scan.get("scan_trend", "no_data"),
    }
    if include_series:
        row_scan_history["scan_price_series"] = scan.get("scan_price_series", [])
    return row_scan_history


def _options_base_cache_key(
    analysis: dict,
    t_days: int | None,
    include_chart: bool,
    profile: str,
    source: str | None,
    source_only: bool,
) -> str:
    normalized_source = _normalize_source_key(source) if source_only else None
    run_ts = str(analysis.get("run_ts") or "no-run-ts")
    return "|".join([
        f"run={run_ts}",
        f"profile={profile}",
        f"chart={1 if include_chart else 0}",
        f"t_days={t_days or 0}",
        f"source={normalized_source or 'ensemble'}",
        f"source_only={1 if source_only and normalized_source else 0}",
    ])


def _detail_cache_key(analysis: dict, detail_id: int, source: str | None, source_only: bool) -> str:
    normalized_source = _normalize_source_key(source) if source_only else None
    run_ts = str(analysis.get("run_ts") or "no-run-ts")
    return "|".join([
        f"run={run_ts}",
        f"detail_id={detail_id}",
        f"source={normalized_source or 'ensemble'}",
        f"source_only={1 if source_only and normalized_source else 0}",
    ])


def _build_path_and_source_summary(
    pred_view: dict,
    curve_points: list[dict],
    current_price: float,
    detail_id: int,
) -> dict:
    """Compute path forecast summary + source consensus for one option row.

    Returns dict with: path_min_price, path_min_t, path_max_price, path_max_t,
    path_num_reversals, path_best_trade_pct, source_consensus, source_disagreement.
    """
    result: dict = {
        "path_min_price": None,
        "path_min_t": None,
        "path_max_price": None,
        "path_max_t": None,
        "path_num_reversals": 0,
        "path_best_trade_pct": 0.0,
        "source_consensus": "NEUTRAL",
        "source_disagreement": False,
    }

    # ── Path forecast summary ────────────────────────────────────────
    if curve_points and current_price > 0:
        try:
            from src.analytics.path_forecast import analyze_path
            pf = analyze_path(
                forward_curve_points=curve_points,
                detail_id=detail_id,
                hotel_id=int(pred_view.get("hotel_id", 0) or 0),
                hotel_name=str(pred_view.get("hotel_name", "")),
                category=str(pred_view.get("category", "")),
                board=str(pred_view.get("board", "")),
                checkin_date=str(pred_view.get("date_from", "")),
                current_price=current_price,
                current_t=int(pred_view.get("days_to_checkin", 0) or 0),
            )
            result["path_min_price"] = pf.predicted_min_price
            result["path_min_t"] = pf.predicted_min_t
            result["path_max_price"] = pf.predicted_max_price
            result["path_max_t"] = pf.predicted_max_t
            result["path_num_reversals"] = pf.num_up_segments + pf.num_down_segments - 1 if (pf.num_up_segments + pf.num_down_segments) > 1 else 0
            result["path_best_trade_pct"] = pf.max_trade_profit_pct
        except Exception as exc:
            logger.debug("path summary skipped for %d: %s", detail_id, exc)

    # ── Source consensus ─────────────────────────────────────────────
    try:
        from src.analytics.raw_source_analyzer import compare_sources
        comp = compare_sources(pred_view)
        result["source_consensus"] = comp.consensus_direction
        result["source_disagreement"] = comp.disagreement_flag
    except Exception as exc:
        logger.debug("source consensus skipped for %d: %s", detail_id, exc)

    return result


def _build_options_rows(
    analysis: dict,
    t_days: int | None,
    include_chart: bool,
    profile: str,
    source: str | None,
    source_only: bool,
) -> dict:
    predictions = analysis.get("predictions", {})
    normalized_source = _normalize_source_key(source)
    profile_applied = (profile or "full").strip().lower()
    if profile_applied not in {"full", "lite"}:
        profile_applied = "full"

    effective_include_chart = include_chart
    if profile_applied == "lite":
        effective_include_chart = False
    is_lite_profile = profile_applied == "lite"

    rows: list[dict] = []
    for detail_id, pred in predictions.items():
        pred_view = _build_prediction_view(pred, normalized_source, source_only, t_days=t_days)
        source_predictions = pred_view.get("source_predictions") or {}
        row_source_predictions = (
            {
                key: _serialize_compact_source_prediction(value)
                for key, value in source_predictions.items()
            }
            if is_lite_profile
            else source_predictions
        )
        curve_points = _extract_curve_points(pred_view, t_days)
        path_prices = [p["predicted_price"] for p in curve_points]

        current_price = float(pred_view.get("current_price", 0) or 0)
        predicted_checkin = float(pred_view.get("predicted_checkin_price", current_price) or current_price)

        if path_prices:
            expected_min_price = min(path_prices)
            expected_max_price = max(path_prices)
            price_range = max(expected_max_price - expected_min_price, 1.0)
            touch_band = max(price_range * 0.10, 1.0)
            touches_min = sum(1 for px in path_prices if abs(px - expected_min_price) <= touch_band)
            touches_max = sum(1 for px in path_prices if abs(px - expected_max_price) <= touch_band)

            changes_gt_20 = 0
            changes_lte_20 = 0
            for i in range(1, len(path_prices)):
                prev_px = path_prices[i - 1]
                if prev_px > 0:
                    delta = path_prices[i] - prev_px
                    if delta < -0.001:
                        changes_gt_20 += 1
                    else:
                        changes_lte_20 += 1
        else:
            expected_min_price = predicted_checkin
            expected_max_price = predicted_checkin
            touches_min = 1
            touches_max = 1
            changes_gt_20 = 0
            changes_lte_20 = 0

        option_signal = _derive_option_signal(pred_view)
        sources = _extract_sources(pred_view, analysis)
        quality = _build_quality_summary(pred_view, sources)
        option_levels = _build_option_levels(pred_view, option_signal, quality)
        info = _build_info_badge(option_signal, quality, sources)
        put_path_insights = _build_put_path_insights(
            curve_points=curve_points,
            current_price=current_price,
            predicted_checkin=predicted_checkin,
            probability=pred_view.get("probability"),
            include_decline_events=not is_lite_profile,
        )

        row = {
            "detail_id": int(detail_id),
            "hotel_id": pred_view.get("hotel_id"),
            "hotel_name": pred_view.get("hotel_name"),
            "category": pred_view.get("category"),
            "board": pred_view.get("board"),
            "date_from": pred_view.get("date_from"),
            "days_to_checkin": pred_view.get("days_to_checkin"),
            "t_horizon_days": len(path_prices),
            "option_signal": option_signal,
            "analysis_mode": "source_only" if source_only and normalized_source else "ensemble",
            "analysis_source": normalized_source if source_only and normalized_source else None,
            "current_price": round(current_price, 2),
            "predicted_checkin_price": round(predicted_checkin, 2),
            "source_predictions": row_source_predictions,
            "expected_change_pct": round(float(pred_view.get("expected_change_pct", 0) or 0), 2),
            "expected_min_price": round(float(expected_min_price), 2),
            "expected_max_price": round(float(expected_max_price), 2),
            "expected_min_delta_from_now": round(float(expected_min_price - current_price), 2),
            "expected_max_delta_from_now": round(float(expected_max_price - current_price), 2),
            "touches_expected_min": touches_min,
            "touches_expected_max": touches_max,
            "count_price_changes_gt_20": changes_gt_20,
            "count_price_changes_lte_20": changes_lte_20,
            "sources": sources,
            "quality": quality,
            "option_levels": option_levels,
            "info": info,
            "forward_curve_url": f"/api/v1/salesoffice/forward-curve/{int(detail_id)}",
        }

        if effective_include_chart:
            row["chart"] = _build_row_chart(curve_points)

        row.update(put_path_insights)

        # Path forecast summary + source consensus enrichment
        row.update(_build_path_and_source_summary(
            pred_view, curve_points, current_price, int(detail_id),
        ))

        scan = pred_view.get("scan_history") or {}
        row["scan_history"] = _build_row_scan_history(scan, include_series=not is_lite_profile)

        if not is_lite_profile:
            row["market_benchmark"] = pred_view.get("market_benchmark") or {}

        rows.append(row)

    rows.sort(
        key=lambda x: (
            0 if x["option_signal"] in ("CALL", "PUT") else 1,
            -abs(float(x.get("expected_change_pct", 0))),
        )
    )

    return {
        "run_ts": analysis.get("run_ts"),
        "t_days_requested": t_days,
        "profile_applied": profile_applied,
        "analysis_mode": "source_only" if source_only and normalized_source else "ensemble",
        "selected_source": normalized_source if source_only and normalized_source else None,
        "include_chart": effective_include_chart,
        "rows": rows,
    }


def _filter_options_rows(rows: list[dict], signal: str | None, source: str | None) -> list[dict]:
    filtered_rows = rows
    normalized_source = _normalize_source_key(source)

    if signal:
        signal_upper = signal.strip().upper()
        if signal_upper in {"CALL", "PUT", "NEUTRAL"}:
            filtered_rows = [row for row in filtered_rows if row.get("option_signal") == signal_upper]

    if normalized_source:
        filtered_rows = [
            row for row in filtered_rows
            if (
                normalized_source in (row.get("source_predictions") or {})
                or any(
                    str((item or {}).get("source", "")).strip().lower() == normalized_source
                    for item in (row.get("sources") or [])
                )
            )
        ]

    return filtered_rows


def _build_options_response_payload(
    analysis: dict,
    base_payload: dict,
    signal: str | None,
    source: str | None,
    include_metadata: bool,
    include_system_context: bool,
    page: dict,
) -> JSONResponse:
    rows = _filter_options_rows(base_payload.get("rows") or [], signal, source)
    paged = paginate(rows, page["limit"], page["offset"], page["all"])

    response_payload = {
        "run_ts": base_payload.get("run_ts"),
        "total_rows": paged["total"],
        "limit": paged["limit"],
        "offset": paged["offset"],
        "has_more": paged["has_more"],
        "t_days_requested": base_payload.get("t_days_requested"),
        "profile_applied": base_payload.get("profile_applied"),
        "analysis_mode": base_payload.get("analysis_mode"),
        "selected_source": base_payload.get("selected_source"),
        "rows": paged["items"],
    }

    if include_metadata:
        response_payload.update({
            "source_validation": _build_source_validation(analysis),
            "sources_audit_summary": _build_sources_audit(analysis, summary_only=True),
            "data_sources": {
                "model_info": analysis.get("model_info", {}),
                "flight_demand": analysis.get("flight_demand", {}),
                "events": {
                    "upcoming_events": analysis.get("events", {}).get("upcoming_events", 0),
                    "next_events": analysis.get("events", {}).get("next_events", []),
                },
                "benchmarks_status": analysis.get("benchmarks", {}).get("status"),
                "historical_patterns": analysis.get("historical_patterns_summary", {}),
            },
        })

    if include_system_context:
        response_payload["system_capabilities"] = _build_system_capabilities(
            analysis,
            total_rows=paged["total"],
        )

    response = JSONResponse(content=response_payload)
    if paged.get("_all"):
        response.headers["X-Pagination-Warning"] = "All items returned; consider using pagination"
    return response


def _build_option_detail_payload(
    analysis: dict,
    detail_id: int,
    source: str | None,
    source_only: bool,
) -> dict:
    predictions = analysis.get("predictions", {})
    pred = predictions.get(detail_id) or predictions.get(str(detail_id))
    if not pred:
        raise HTTPException(status_code=404, detail=f"Room {detail_id} not found")

    pred_view = _build_prediction_view(pred, source, source_only)
    selected_source = _normalize_source_key(source) if source_only else None
    source_predictions = pred_view.get("source_predictions") or {}

    curve_points = _extract_curve_points(pred_view, None)
    scan = pred_view.get("scan_history") or {}
    current_price = float(pred_view.get("current_price", 0) or 0)
    predicted_checkin = float(pred_view.get("predicted_checkin_price", current_price) or current_price)

    path_prices = [p["predicted_price"] for p in curve_points]
    expected_min = min(path_prices) if path_prices else current_price
    expected_max = max(path_prices) if path_prices else predicted_checkin
    option_signal = _derive_option_signal(pred_view)

    signals_list = pred_view.get("signals") or []
    fc_sig = next((s for s in signals_list if s.get("source") == "forward_curve"), None)
    hist_sig = next((s for s in signals_list if s.get("source") == "historical_pattern"), None)
    sel_sig = source_predictions.get(selected_source) if selected_source else None

    fc_pts = pred_view.get("forward_curve") or []
    ev_adj = sum(float(p.get("event_adj_pct", 0) or 0) for p in fc_pts)
    se_adj = sum(float(p.get("season_adj_pct", 0) or 0) for p in fc_pts)
    dm_adj = sum(float(p.get("demand_adj_pct", 0) or 0) for p in fc_pts)
    mo_adj = sum(float(p.get("momentum_adj_pct", 0) or 0) for p in fc_pts)
    we_adj = sum(float(p.get("weather_adj_pct", 0) or 0) for p in fc_pts)

    quality = _build_quality_summary(pred_view, _extract_sources(pred_view, analysis))
    chg = round(float(pred_view.get("expected_change_pct", 0) or 0), 2)

    scan_raw = scan.get("scan_price_series", [])
    scan_d_counts: dict[str, int] = {}
    scan_pts: list[dict] = []
    for s in scan_raw:
        sd = s["date"][5:10] if len(s.get("date", "")) >= 10 else s.get("date", "")[-5:]
        scan_d_counts[sd] = scan_d_counts.get(sd, 0) + 1
        scan_pts.append({"d": sd, "p": round(s["price"], 1)})
    dup_dates = {d for d, c in scan_d_counts.items() if c > 1}
    if dup_dates:
        cnt: dict[str, int] = {}
        for pt in scan_pts:
            if pt["d"] in dup_dates:
                cnt[pt["d"]] = cnt.get(pt["d"], 0) + 1
                pt["d"] = f'{pt["d"]}#{cnt[pt["d"]]}'

    return {
        "fc": [{
            "d": p["date"][-5:],
            "p": round(p["predicted_price"], 1),
            "lo": round(float(p.get("lower_bound") or p["predicted_price"]), 1),
            "hi": round(float(p.get("upper_bound") or p["predicted_price"]), 1),
        } for p in curve_points],
        "scan": scan_pts,
        "cp": round(current_price, 2),
        "pp": round(predicted_checkin, 2),
        "mn": round(expected_min, 2),
        "mx": round(expected_max, 2),
        "sig": option_signal,
        "analysis_mode": "source_only" if selected_source else "ensemble",
        "selected_source": selected_source,
        "available_sources": list(source_predictions.keys()),
        "selected_source_price": round(float(sel_sig.get("predicted_price", 0) or 0), 2) if sel_sig else None,
        "selected_source_confidence": round(float(sel_sig.get("confidence", 0) or 0), 2) if sel_sig else None,
        "selected_source_reasoning": sel_sig.get("reasoning") if sel_sig else None,
        "source_predictions": source_predictions,
        "fcW": round(float(fc_sig.get("weight", 0) or 0), 2) if fc_sig else 0,
        "fcC": round(float(fc_sig.get("confidence", 0) or 0), 2) if fc_sig else 0,
        "fcP": round(float(fc_sig["predicted_price"]), 2) if fc_sig and fc_sig.get("predicted_price") else None,
        "hiW": round(float(hist_sig.get("weight", 0) or 0), 2) if hist_sig else 0,
        "hiC": round(float(hist_sig.get("confidence", 0) or 0), 2) if hist_sig else 0,
        "hiP": round(float(hist_sig["predicted_price"]), 2) if hist_sig and hist_sig.get("predicted_price") else None,
        "adj": {"ev": round(ev_adj, 2), "se": round(se_adj, 2), "dm": round(dm_adj, 2), "mo": round(mo_adj, 2), "we": round(we_adj, 2)},
        "mom": pred_view.get("momentum", {}),
        "reg": pred_view.get("regime", {}),
        "mkt": (pred_view.get("market_benchmark") or {}).get("market_avg_price", 0),
        "q": quality.get("label", ""),
        "chg": chg,
        "drops": scan.get("scan_actual_drops", 0),
        "rises": scan.get("scan_actual_rises", 0),
        "scans": scan.get("scan_snapshots", 0),
    }


def _get_or_build_options_base_payload(
    analysis: dict,
    t_days: int | None,
    include_chart: bool,
    profile: str,
    source: str | None,
    source_only: bool,
) -> dict:
    cache_key = _options_base_cache_key(analysis, t_days, include_chart, profile, source, source_only)
    cached_payload = _cm.get(OPTIONS_CACHE_REGION, cache_key)
    if isinstance(cached_payload, dict) and cached_payload.get("rows") is not None:
        return cached_payload

    payload = _build_options_rows(analysis, t_days, include_chart, profile, source, source_only)
    _cm.set(OPTIONS_CACHE_REGION, cache_key, payload)
    return payload


def _get_or_build_detail_payload(analysis: dict, detail_id: int, source: str | None, source_only: bool) -> dict:
    cache_key = _detail_cache_key(analysis, detail_id, source, source_only)
    cached_payload = _cm.get(DETAIL_CACHE_REGION, cache_key)
    if isinstance(cached_payload, dict) and cached_payload:
        return cached_payload

    payload = _build_option_detail_payload(analysis, detail_id, source, source_only)
    _cm.set(DETAIL_CACHE_REGION, cache_key, payload)
    return payload


def _prime_salesoffice_route_caches(analysis: dict) -> dict[str, int]:
    cached_options = 0
    cached_details = 0

    precompute_configs = [
        {
            "t_days": SALESOFFICE_PRECOMPUTE_T_DAYS,
            "include_chart": False,
            "profile": "lite",
            "source": None,
            "source_only": False,
        },
        {
            "t_days": SALESOFFICE_PRECOMPUTE_T_DAYS,
            "include_chart": False,
            "profile": "full",
            "source": None,
            "source_only": False,
        },
    ]
    precompute_configs.extend({
        "t_days": SALESOFFICE_PRECOMPUTE_T_DAYS,
        "include_chart": False,
        "profile": "lite",
        "source": source_key,
        "source_only": True,
    } for source_key in PRECOMPUTE_SOURCE_ONLY_SOURCES)

    detail_ids: list[int] = []
    for config in precompute_configs:
        payload = _get_or_build_options_base_payload(analysis, **config)
        cached_options += 1
        if not detail_ids and config["profile"] == "lite" and not config["source_only"]:
            detail_ids = [
                int(row["detail_id"])
                for row in (payload.get("rows") or [])[:SALESOFFICE_PRECOMPUTE_DETAIL_LIMIT]
                if row.get("detail_id") is not None
            ]

    for detail_id in detail_ids:
        _get_or_build_detail_payload(analysis, detail_id, None, False)
        cached_details += 1
        for source_key in PRECOMPUTE_SOURCE_ONLY_SOURCES:
            _get_or_build_detail_payload(analysis, detail_id, source_key, True)
            cached_details += 1

    return {
        "options": cached_options,
        "details": cached_details,
    }


@analytics_router.get("/data")
@limiter.limit(RATE_LIMIT_DATA)
def salesoffice_data(
    request: Request,
    _key: str = Depends(_optional_api_key),
    page: dict = Depends(pagination_params),
):
    """Raw analysis data as JSON — for programmatic access."""
    analysis = _get_or_run_analysis()

    # Strip daily/forward_curve arrays (too verbose) — keep summaries + trading signals
    predictions = analysis.get("predictions", {})
    summary_list = []
    for detail_id, pred in predictions.items():
        item = {k: v for k, v in pred.items() if k not in ("daily", "forward_curve")}
        item["detail_id"] = detail_id
        summary_list.append(item)

    paged = paginate(summary_list, page["limit"], page["offset"], page["all"])
    response = JSONResponse(content={
        "run_ts": analysis.get("run_ts"),
        "total_snapshots": analysis.get("total_snapshots"),
        "model_info": analysis.get("model_info"),
        "statistics": analysis.get("statistics"),
        "hotels": analysis.get("hotels"),
        "predictions_summary": paged["items"],
        "total": paged["total"],
        "limit": paged["limit"],
        "offset": paged["offset"],
        "has_more": paged["has_more"],
        "booking_window": analysis.get("booking_window"),
        "price_changes": analysis.get("price_changes"),
    })
    if paged.get("_all"):
        response.headers["X-Pagination-Warning"] = "All items returned; consider using pagination"
    return response


@analytics_router.get("/simple")
@limiter.limit(RATE_LIMIT_DATA)
def salesoffice_simple(
    request: Request,
    page: dict = Depends(pagination_params),
):
    """Simplified analysis — human-readable JSON with 4 clear sections."""
    from src.analytics.simple_analysis import simplify_analysis

    analysis = _get_or_run_analysis()
    simplified = simplify_analysis(analysis)

    all_predictions = simplified.get("predictions", [])
    paged = paginate(all_predictions, page["limit"], page["offset"], page["all"])
    simplified["predictions"] = paged["items"]
    simplified["total"] = paged["total"]
    simplified["limit"] = paged["limit"]
    simplified["offset"] = paged["offset"]
    simplified["has_more"] = paged["has_more"]

    response = JSONResponse(content=simplified)
    if paged.get("_all"):
        response.headers["X-Pagination-Warning"] = "All items returned; consider using pagination"
    return response


@analytics_router.get("/simple/text", response_class=PlainTextResponse)
def salesoffice_simple_text():
    """Plain text analysis report — for quick reading in terminal or email."""
    from src.analytics.simple_analysis import simplify_to_text

    analysis = _get_or_run_analysis()
    text = simplify_to_text(analysis)
    return PlainTextResponse(content=text)


@analytics_router.get("/debug")
def salesoffice_debug():
    """Debug endpoint — runs analysis and returns error details if any."""
    import traceback
    try:
        result = _run_collection_cycle()
        if result is None:
            return {"status": "no_data", "detail": "No data collected"}
        return {
            "status": "ok",
            "rooms": result.get("statistics", {}).get("total_rooms", 0),
            "model_info": result.get("model_info"),
        }
    except (ValueError, TypeError, KeyError, OSError) as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@analytics_router.get("/options/detail/{detail_id}")
def salesoffice_option_detail(
    detail_id: int,
    source: str | None = None,
    source_only: bool = False,
):
    """Return compact detail data for the inline trading chart panel."""
    analysis = _get_or_run_analysis()
    return JSONResponse(content=_get_or_build_detail_payload(analysis, detail_id, source, source_only))


@analytics_router.get("/forward-curve/{detail_id}")
def salesoffice_forward_curve(detail_id: int, raw: bool = False):
    """Full forward curve prediction for a specific room.

    When raw=true, returns the pure decay-curve walk with all enrichment
    adjustments stripped (events, seasonality, demand, weather, competitor,
    momentum).  The enriched curve is still included for comparison.
    """
    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    # detail_id might be int or str key
    pred = predictions.get(detail_id) or predictions.get(str(detail_id))
    if not pred:
        raise HTTPException(status_code=404, detail=f"Room {detail_id} not found in predictions")

    fc_points = pred.get("forward_curve", [])
    current_price = float(pred.get("current_price", 0) or 0)

    payload: dict = {
        "detail_id": detail_id,
        "hotel_name": pred.get("hotel_name"),
        "hotel_id": pred.get("hotel_id"),
        "category": pred.get("category"),
        "board": pred.get("board"),
        "current_price": pred.get("current_price"),
        "date_from": pred.get("date_from"),
        "days_to_checkin": pred.get("days_to_checkin"),
        "predicted_checkin_price": pred.get("predicted_checkin_price"),
        "expected_change_pct": pred.get("expected_change_pct"),
        "probability": pred.get("probability"),
        "cancel_probability": pred.get("cancel_probability"),
        "model_type": pred.get("model_type"),
        "confidence_quality": pred.get("confidence_quality"),
        "momentum": pred.get("momentum"),
        "regime": pred.get("regime"),
        "forward_curve": fc_points,
        # Deep predictor enrichments
        "prediction_method": pred.get("prediction_method"),
        "signals": pred.get("signals"),
        "yoy_comparison": pred.get("yoy_comparison"),
        "explanation": pred.get("explanation"),
        "raw_mode": raw,
    }

    if raw and fc_points and current_price > 0:
        from src.analytics.raw_source_analyzer import _strip_enrichments_from_curve
        raw_prices = _strip_enrichments_from_curve(fc_points, current_price)
        raw_curve = []
        for i, pt in enumerate(fc_points):
            raw_curve.append({
                "date": pt.get("date"),
                "t": pt.get("t"),
                "predicted_price": round(raw_prices[i], 2) if i < len(raw_prices) else pt.get("predicted_price"),
                "enriched_price": round(float(pt.get("predicted_price", 0)), 2),
                "enrichment_delta": round(
                    float(pt.get("predicted_price", 0)) - (raw_prices[i] if i < len(raw_prices) else float(pt.get("predicted_price", 0))),
                    2,
                ),
                "event_adj_pct": pt.get("event_adj_pct", 0),
                "season_adj_pct": pt.get("season_adj_pct", 0),
                "demand_adj_pct": pt.get("demand_adj_pct", 0),
                "momentum_adj_pct": pt.get("momentum_adj_pct", 0),
                "weather_adj_pct": pt.get("weather_adj_pct", 0),
                "competitor_adj_pct": pt.get("competitor_adj_pct", 0),
            })
        payload["raw_forward_curve"] = raw_curve
        payload["raw_final_price"] = round(raw_prices[-1], 2) if raw_prices else current_price
        payload["enrichment_total_impact"] = round(
            float(fc_points[-1].get("predicted_price", 0)) - (raw_prices[-1] if raw_prices else current_price),
            2,
        ) if fc_points else 0.0

    return JSONResponse(content=payload)


@analytics_router.get("/options")
@limiter.limit(RATE_LIMIT_DATA)
async def salesoffice_options(
    request: Request,
    t_days: int | None = None,
    include_chart: bool = True,
    profile: str = "full",
    include_system_context: bool = True,
    include_metadata: bool = True,
    signal: str | None = None,
    source: str | None = None,
    source_only: bool = False,
    _key: str = Depends(_optional_api_key),
    page: dict = Depends(pagination_params),
):
    """Options-style row output with min/max path stats and source transparency."""
    analysis = _get_or_run_analysis()
    normalized_source = _normalize_source_key(source)

    profile_applied = (profile or "full").strip().lower()
    if profile_applied not in {"full", "lite"}:
        profile_applied = "full"

    effective_include_chart = include_chart
    if profile_applied == "lite":
        effective_include_chart = False
    base_payload = _get_or_build_options_base_payload(
        analysis,
        t_days=t_days,
        include_chart=effective_include_chart,
        profile=profile_applied,
        source=normalized_source,
        source_only=source_only,
    )
    return _build_options_response_payload(
        analysis,
        base_payload,
        signal=signal,
        source=normalized_source,
        include_metadata=include_metadata,
        include_system_context=include_system_context,
        page=page,
    )


@analytics_router.get("/options/legend")
async def salesoffice_options_legend():
    """UI legend for options info icon and source-quality semantics."""
    level_bands = [
        {"range": "1-3", "meaning": "weak conviction"},
        {"range": "4-6", "meaning": "moderate conviction"},
        {"range": "7-8", "meaning": "strong conviction"},
        {"range": "9-10", "meaning": "very strong conviction"},
    ]

    call_levels = [
        {"level": i, "label": f"CALL_L{i}", "direction": "CALL"}
        for i in range(1, 11)
    ]
    put_levels = [
        {"level": i, "label": f"PUT_L{i}", "direction": "PUT"}
        for i in range(1, 11)
    ]

    return JSONResponse(content={
        "legend_version": "2.0",
        "info_icon_rules": {
            "info_icon": "i",
            "question_icon": "?",
            "thresholds": {
                "question_mark_if_quality_below": 0.5,
                "info_if_quality_at_or_above": 0.5,
            },
            "meaning": {
                "i": "Prediction is based on available sources with acceptable confidence.",
                "?": "Prediction exists, but confidence/signal quality is weak and should be reviewed.",
            },
        },
        "quality_score_bands": [
            {"label": "HIGH", "min": 0.75, "max": 1.0},
            {"label": "MEDIUM", "min": 0.5, "max": 0.749},
            {"label": "LOW", "min": 0.0, "max": 0.499},
        ],
        "scale": {
            "min": 1,
            "max": 10,
            "neutral": 0,
            "description": "Higher level means stronger conviction while keeping original method unchanged.",
        },
        "levels": {
            "call": [f"CALL_L{i}" for i in range(1, 11)],
            "put": [f"PUT_L{i}" for i in range(1, 11)],
        },
        "call_levels": call_levels,
        "put_levels": put_levels,
        "option_levels": {
            "scale": "1-10",
            "description": "Higher level means stronger CALL/PUT conviction while keeping original method unchanged.",
            "neutral": "Level 0",
            "bands": level_bands,
        },
        "source_fields": [
            {"field": "source", "description": "Model source name (forward_curve / historical_pattern / ml_forecast)."},
            {"field": "weight", "description": "Relative contribution of this signal in the final prediction."},
            {"field": "confidence", "description": "Confidence score for this signal (when available)."},
            {"field": "reasoning", "description": "Human-readable explanation of how this source contributed."},
        ],
    })


@analytics_router.post("/options/warmup")
async def salesoffice_options_warmup(
    _key: str = Depends(_optional_api_key),
):
    """Start options analysis warmup in background without blocking the request path."""
    return JSONResponse(content=_kickoff_analysis_warmup())


@analytics_router.get("/sources/audit")
async def salesoffice_sources_audit(
    _key: str = Depends(_optional_api_key),
):
    """Full runtime audit for all configured data sources."""
    analysis = _get_or_run_analysis()
    return JSONResponse(content=_build_sources_audit(analysis, summary_only=False))


@analytics_router.get("/backtest")
def salesoffice_backtest(
    _key: str = Depends(_optional_api_key),
):
    """Run walk-forward backtest on historical price data."""
    from src.analytics.backtest import HistoricalBacktester

    try:
        backtester = HistoricalBacktester()
        results = backtester.run_backtest()
        return JSONResponse(content=results)
    except (ValueError, TypeError, KeyError, OSError) as e:
        logger.error("Backtest failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "n_trials": 0},
        )


@analytics_router.get("/decay-curve")
def salesoffice_decay_curve():
    """The empirical decay curve term structure."""
    analysis = _get_or_run_analysis()
    model_info = analysis.get("model_info", {})
    return JSONResponse(content={
        "data_source": model_info.get("data_source", "N/A"),
        "total_tracks": model_info.get("total_tracks", 0),
        "total_observations": model_info.get("total_observations", 0),
        "global_mean_daily_pct": model_info.get("global_mean_daily_pct", 0),
        "category_offsets": model_info.get("category_offsets", {}),
        "curve_snapshot": model_info.get("curve_snapshot", []),
    })


@analytics_router.get("/charts/contract-data")
def salesoffice_charts_contract_data(
    hotel_id: int,
    checkin_date: str,
    category: str,
    board: str,
    radius_km: float = 5.0,
    stars: int | None = None,
):
    """Contract path data for Charts 1-4 (Tab 1). Called via AJAX."""
    from src.analytics.charts_engine import build_contract_path

    try:
        data = build_contract_path(
            hotel_id=hotel_id,
            checkin_date=checkin_date,
            category=category,
            board=board,
            market_radius_km=radius_km,
            market_stars=stars,
        )
        return JSONResponse(content=data)
    except (OSError, ConnectionError, ValueError) as e:
        logger.error("Contract path failed: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Contract data query failed: {e}")


@analytics_router.get("/status")
async def salesoffice_status():
    """Quick status — snapshot count, last run, rooms, hotels."""
    from src.analytics.price_store import get_snapshot_count, load_latest_snapshot, init_db
    from src.analytics.collector import get_collection_runtime_status

    init_db()
    snapshot_count = get_snapshot_count()
    latest = load_latest_snapshot()

    cached_analysis = _get_cached_analysis() or {}
    collection_runtime = get_collection_runtime_status()

    return {
        "status": "ok",
        "data_source": "cache",
        "snapshots_collected": snapshot_count,
        "total_rooms": len(latest) if not latest.empty else 0,
        "total_hotels": latest["hotel_id"].nunique() if not latest.empty else 0,
        "last_analysis": cached_analysis.get("run_ts"),
        "cache_ready": bool(cached_analysis),
        "analysis_warming": _analysis_warming.is_set(),
        "scheduler_running": _is_scheduler_running(),
        "collection_interval_seconds": COLLECTION_INTERVAL,
        "last_successful_db_query_ts": collection_runtime.get("last_successful_db_query_ts"),
        "collection_runtime": collection_runtime,
    }


# ── Prediction Accuracy Feedback Loop ────────────────────────────────


@analytics_router.get("/accuracy/summary")
def accuracy_summary(days: int = 30):
    """MAE, MAPE, directional accuracy for scored predictions."""
    from src.analytics.accuracy_tracker import get_accuracy_summary, init_tracker_db
    init_tracker_db()
    return JSONResponse(content=get_accuracy_summary(days=days))


@analytics_router.get("/accuracy/by-signal")
def accuracy_by_signal():
    """Precision/recall per CALL/PUT/NEUTRAL."""
    from src.analytics.accuracy_tracker import get_accuracy_by_signal, init_tracker_db
    init_tracker_db()
    return JSONResponse(content=get_accuracy_by_signal())


@analytics_router.get("/accuracy/by-t-bucket")
def accuracy_by_t_bucket():
    """Accuracy for T ranges: 1-7, 8-14, 15-30, 31-60, 61+."""
    from src.analytics.accuracy_tracker import get_accuracy_by_t_bucket, init_tracker_db
    init_tracker_db()
    return JSONResponse(content=get_accuracy_by_t_bucket())


@analytics_router.get("/accuracy/by-hotel")
def accuracy_by_hotel():
    """Per-hotel accuracy metrics."""
    from src.analytics.accuracy_tracker import get_accuracy_by_hotel, init_tracker_db
    init_tracker_db()
    return JSONResponse(content=get_accuracy_by_hotel())


@analytics_router.get("/accuracy/trend")
def accuracy_trend():
    """Rolling 7/30-day accuracy trend."""
    from src.analytics.accuracy_tracker import get_accuracy_trend, init_tracker_db
    init_tracker_db()
    return JSONResponse(content=get_accuracy_trend())


# ── Alert endpoints ───────────────────────────────────────────────────


@analytics_router.get("/alerts/history")
def alerts_history(days: int = Query(default=7, ge=1, le=90)):
    """Alert log for the past N days."""
    from src.services.alert_dispatcher import get_alert_history
    return JSONResponse(content={"alerts": get_alert_history(days=days)})


@analytics_router.post("/alerts/test")
def alerts_test(_key: str = Depends(_optional_api_key)):
    """Fire a test alert to all configured channels."""
    from src.services.alert_dispatcher import AlertDispatcher
    dispatcher = AlertDispatcher()
    result = dispatcher.test_alert()
    return JSONResponse(content=result)


@analytics_router.get("/alerts/stats")
def alerts_stats():
    """Alert volume, top rules, channel distribution."""
    from src.services.alert_dispatcher import get_alert_stats
    return JSONResponse(content=get_alert_stats())


# ── Data quality endpoints ────────────────────────────────────────────


@analytics_router.get("/data-quality/status")
def data_quality_status():
    """All sources with freshness, reliability, and anomaly scores."""
    from src.analytics.data_quality import get_quality_status
    return JSONResponse(content=get_quality_status())


@analytics_router.get("/data-quality/history")
def data_quality_history(
    source: str = Query(..., description="Source ID (e.g. open_meteo)"),
    days: int = Query(default=30, ge=1, le=90),
):
    """Quality history for a specific source."""
    from src.analytics.data_quality import get_quality_history
    return JSONResponse(content=get_quality_history(source_id=source, days=days))


# ── Scenario analysis endpoints ───────────────────────────────────────


@analytics_router.post("/scenario/run")
async def scenario_run(request: Request):
    """Run a what-if scenario with override parameters.

    Body: {"event_impact": 0, "demand_multiplier": 0.7, ...}
    """
    try:
        body = await request.json()
    except (ValueError, RuntimeError):
        body = {}

    from src.analytics.scenario_engine import run_scenario_from_cache
    return JSONResponse(content=run_scenario_from_cache(body))


@analytics_router.get("/scenario/presets")
def scenario_presets():
    """List available preset scenarios."""
    from src.analytics.scenario_engine import get_presets
    return JSONResponse(content={"presets": get_presets()})


@analytics_router.post("/scenario/compare")
async def scenario_compare(request: Request):
    """Compare multiple scenarios side by side.

    Body: {"scenarios": [{"name": "...", "overrides": {...}}, ...]}
    """
    try:
        body = await request.json()
    except (ValueError, RuntimeError):
        body = {}

    scenarios = body.get("scenarios", [])
    from src.analytics.scenario_engine import compare_scenarios_from_cache
    return JSONResponse(content=compare_scenarios_from_cache(scenarios))


# ── Portfolio Greeks endpoints ────────────────────────────────────────


@analytics_router.get("/greeks")
def portfolio_greeks_summary(request: Request, _key=Depends(_optional_api_key)):
    """Portfolio-level Greeks summary: Theta, Delta, Vega, VaR, CVaR."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.portfolio_greeks import compute_portfolio_greeks
    result = compute_portfolio_greeks(analysis)
    return JSONResponse(content=result.to_dict())


@analytics_router.get("/greeks/{hotel_id}")
def hotel_greeks(hotel_id: int, request: Request, _key=Depends(_optional_api_key)):
    """Per-hotel Greeks breakdown with per-room detail."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.portfolio_greeks import compute_hotel_greeks
    result = compute_hotel_greeks(analysis, hotel_id)
    return JSONResponse(content=result)


@analytics_router.get("/greeks/var")
def portfolio_var(request: Request, _key=Depends(_optional_api_key)):
    """Dedicated VaR/CVaR endpoint with per-hotel breakdown."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.portfolio_greeks import compute_portfolio_greeks
    pg = compute_portfolio_greeks(analysis)
    return JSONResponse(content={
        "timestamp": pg.timestamp,
        "portfolio_var_95": pg.portfolio_var_95,
        "portfolio_cvar_95": pg.portfolio_cvar_95,
        "total_exposure": pg.total_exposure,
        "n_contracts": pg.n_contracts,
        "max_hotel_exposure_pct": pg.max_hotel_exposure_pct,
        "max_hotel_name": pg.max_hotel_name,
        "hotel_var": [
            {"hotel_id": h["hotel_id"], "hotel_name": h["hotel_name"],
             "var_95": h["var_95"], "exposure": h["exposure"],
             "exposure_pct": h["exposure_pct"]}
            for h in pg.hotel_greeks
        ],
    })


# ── Source Attribution ────────────────────────────────────────────────


@analytics_router.get("/attribution")
def source_attribution_report(request: Request, _key=Depends(_optional_api_key)):
    """Full source attribution — 4 isolated tracks + enrichment breakdown + agreement."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.source_attribution import build_attribution_report
    report = build_attribution_report(analysis)
    return JSONResponse(content=report.to_dict())


@analytics_router.get("/attribution/sources")
def source_tracks_only(request: Request, _key=Depends(_optional_api_key)):
    """Isolated source comparison — FC vs Historical vs ML vs Ensemble."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.source_attribution import (
        extract_source_predictions, build_source_track,
    )
    predictions = analysis.get("predictions", {})
    total_rooms = len(predictions)
    tracks = extract_source_predictions(analysis)

    result = {
        "total_rooms": total_rooms,
        "sources": {
            "forward_curve": build_source_track(
                "forward_curve", "Forward Curve (100%)", 100,
                tracks["forward_curve"], total_rooms,
            ).to_dict(),
            "historical": build_source_track(
                "historical", "Historical Patterns (100%)", 100,
                tracks["historical"], total_rooms,
            ).to_dict(),
            "ml": build_source_track(
                "ml", "ML Model (100%)", 100,
                tracks["ml"], total_rooms,
            ).to_dict(),
            "ensemble": build_source_track(
                "ensemble", "Ensemble (50/30/20)", -1,
                tracks["ensemble"], total_rooms,
            ).to_dict(),
        },
    }
    return JSONResponse(content=result)


@analytics_router.get("/attribution/enrichments")
def enrichment_attribution(request: Request, _key=Depends(_optional_api_key)):
    """Per-enrichment contribution — events, seasonality, demand, weather, etc."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.source_attribution import compute_enrichment_attribution
    enrichments = compute_enrichment_attribution(analysis)
    return JSONResponse(content=[e.to_dict() for e in enrichments])


@analytics_router.get("/attribution/agreement")
def source_agreement(request: Request, _key=Depends(_optional_api_key)):
    """Cross-source agreement — where FC, Historical, ML agree or diverge."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.source_attribution import (
        extract_source_predictions, compute_agreement,
    )
    tracks = extract_source_predictions(analysis)
    agreement_rate, divergences = compute_agreement(tracks)
    return JSONResponse(content={
        "agreement_rate_pct": agreement_rate,
        "divergence_count": len(divergences),
        "divergence_rooms": divergences,
    })


@analytics_router.get("/attribution/hotel/{hotel_id}")
def hotel_source_attribution(
    hotel_id: int, request: Request, _key=Depends(_optional_api_key),
):
    """Per-hotel source attribution — compare all sources for one hotel."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")

    from src.analytics.source_attribution import extract_source_predictions
    tracks = extract_source_predictions(analysis)

    result = {}
    for source_name, preds in tracks.items():
        hotel_preds = [p for p in preds if int(p.get("hotel_id", 0)) == hotel_id]
        if not hotel_preds:
            result[source_name] = {"rooms": 0, "predictions": []}
            continue

        prices = [p["predicted_price"] for p in hotel_preds]
        calls = sum(1 for p in hotel_preds if (p.get("signal") or "").upper() in ("CALL", "STRONG_CALL"))
        puts = sum(1 for p in hotel_preds if (p.get("signal") or "").upper() in ("PUT", "STRONG_PUT"))

        result[source_name] = {
            "rooms": len(hotel_preds),
            "avg_predicted_price": round(sum(prices) / len(prices), 2),
            "avg_change_pct": round(sum(p.get("change_pct", 0) for p in hotel_preds) / len(hotel_preds), 2),
            "calls": calls,
            "puts": puts,
            "neutrals": len(hotel_preds) - calls - puts,
            "predictions": hotel_preds[:30],
        }

    return JSONResponse(content={"hotel_id": hotel_id, "sources": result})


# ── Group Actions (Bulk CALL/PUT) ────────────────────────────────────


@analytics_router.post("/group/preview")
def group_action_preview(
    request: Request,
    signal: str | None = Query(None, description="CALL, PUT, or None for all"),
    hotel_id: int | None = Query(None),
    hotel_ids: str | None = Query(None, description="Comma-separated hotel IDs"),
    category: str | None = Query(None, description="standard, deluxe, suite"),
    board: str | None = Query(None, description="ro, bb"),
    confidence: str | None = Query(None, description="High, Med, Low"),
    min_T: int | None = Query(None, description="Min days to check-in"),
    max_T: int | None = Query(None, description="Max days to check-in"),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    _key=Depends(_optional_api_key),
):
    """Preview a group action — dry run showing what would be affected."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")


    from src.analytics.group_actions import GroupFilter, preview_group_action

    parsed_hotel_ids = [int(x.strip()) for x in hotel_ids.split(",")] if hotel_ids else None
    gf = GroupFilter(
        signal=signal, hotel_id=hotel_id, hotel_ids=parsed_hotel_ids,
        category=category, board=board, confidence=confidence,
        min_T=min_T, max_T=max_T, min_price=min_price, max_price=max_price,
    )
    signals = _get_cached_signals()
    result = preview_group_action(signals, analysis, gf)
    return JSONResponse(content=result)


@analytics_router.post("/group/override")
def group_override(
    request: Request,
    signal: str | None = Query(None),
    hotel_id: int | None = Query(None),
    hotel_ids: str | None = Query(None, description="Comma-separated hotel IDs"),
    category: str | None = Query(None),
    board: str | None = Query(None),
    confidence: str | None = Query(None),
    min_T: int | None = Query(None),
    max_T: int | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    discount_usd: float = Query(1.0, description="Override discount in USD"),
    _key=Depends(_optional_api_key),
):
    """Execute bulk PUT overrides for rooms matching the filter."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")


    from src.analytics.group_actions import GroupFilter, execute_group_override

    parsed_hotel_ids = [int(x.strip()) for x in hotel_ids.split(",")] if hotel_ids else None
    gf = GroupFilter(
        signal=signal, hotel_id=hotel_id, hotel_ids=parsed_hotel_ids,
        category=category, board=board, confidence=confidence,
        min_T=min_T, max_T=max_T, min_price=min_price, max_price=max_price,
    )
    signals = _get_cached_signals()
    result = execute_group_override(signals, analysis, gf, discount_usd=discount_usd)

    logger.info(
        "group_override: batch=%s queued=%d skipped=%d",
        result.batch_id, result.total_queued, result.total_skipped,
    )
    return JSONResponse(content=result.to_dict())


@analytics_router.post("/group/opportunity")
def group_opportunity(
    request: Request,
    signal: str | None = Query(None),
    hotel_id: int | None = Query(None),
    hotel_ids: str | None = Query(None, description="Comma-separated hotel IDs"),
    category: str | None = Query(None),
    board: str | None = Query(None),
    confidence: str | None = Query(None),
    min_T: int | None = Query(None),
    max_T: int | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    max_rooms: int = Query(1, description="Max rooms to buy per opportunity"),
    _key=Depends(_optional_api_key),
):
    """Execute bulk CALL opportunities for rooms matching the filter."""
    analysis = _get_cached_analysis()
    if analysis is None:
        raise HTTPException(503, "Analysis cache not ready")


    from src.analytics.group_actions import GroupFilter, execute_group_opportunity

    parsed_hotel_ids = [int(x.strip()) for x in hotel_ids.split(",")] if hotel_ids else None
    gf = GroupFilter(
        signal=signal, hotel_id=hotel_id, hotel_ids=parsed_hotel_ids,
        category=category, board=board, confidence=confidence,
        min_T=min_T, max_T=max_T, min_price=min_price, max_price=max_price,
    )
    signals = _get_cached_signals()
    result = execute_group_opportunity(signals, analysis, gf, max_rooms=max_rooms)

    logger.info(
        "group_opportunity: batch=%s queued=%d skipped=%d",
        result.batch_id, result.total_queued, result.total_skipped,
    )
    return JSONResponse(content=result.to_dict())


# ── Hotel Readiness Diagnostic ───────────────────────────────────────

TARGET_HOTELS = {
    173508: "Cadet Hotel",
    67387: "Holiday Inn Express",
    855711: "Albion Hotel",
    383277: "Iberostar Berkeley Shore",
    87197: "Catalina Hotel",
    117491: "Fairwind Hotel",
    64390: "Crystal Beach Suites",
    6654: "Dorchester Hotel",
    241025: "Dream South Beach",
    19977: "Fontainebleau",
    701659: "Generator Miami",
    301640: "Hilton Garden Inn Miami SB",
    414146: "Hotel Belleza",
    31226: "Kimpton Angler's",
    6663: "Marseilles Hotel",
    21842: "Miami Intl Airport Hotel",
    237547: "Notebook Miami Beach",
    64309: "Savoy Hotel",
    852120: "SLS LUX Brickell",
    6805: "Pullman Miami Airport",
    66814: "Breakwater South Beach",
    333502: "Eurostars Langford Hotel",
    20702: "Embassy Suites Miami Intl Airport",
}


@analytics_router.get("/hotel-readiness")
async def hotel_readiness():
    """Check all 4 mapping layers for 19 target Miami hotels.

    Layers checked:
    1. Med_Hotels — exists with Innstant_ZenithId > 0 and isActive = 1
    2. Med_Hotels_ratebycat — at least 1 row with RatePlanCode
    3. SalesOffice.Orders — active order with successful mapping
    4. SalesOffice.Details — recent scan data exists
    """
    from src.data.trading_db import run_trading_query

    results = []
    try:
        hotel_ids = list(TARGET_HOTELS.keys())
        ids_str = ",".join(str(h) for h in hotel_ids)

        # Layer 1: Med_Hotels
        layer1 = run_trading_query(f"""
            SELECT HotelId, Name, Innstant_ZenithId, isActive
            FROM Med_Hotels WHERE HotelId IN ({ids_str})
        """)
        med_hotels = {int(r["HotelId"]): r for _, r in layer1.iterrows()} if not layer1.empty else {}

        # Layer 2: Med_Hotels_ratebycat
        layer2 = run_trading_query(f"""
            SELECT HotelId, COUNT(*) AS ratebycat_rows
            FROM Med_Hotels_ratebycat WHERE HotelId IN ({ids_str})
            GROUP BY HotelId
        """)
        ratebycat = {int(r["HotelId"]): int(r["ratebycat_rows"]) for _, r in layer2.iterrows()} if not layer2.empty else {}

        # Layer 3: SalesOffice.Orders (uses DestinationId, not HotelId)
        layer3 = run_trading_query(f"""
            SELECT o.DestinationId AS HotelId, COUNT(*) AS active_orders,
                   MAX(o.WebJobStatus) AS last_status
            FROM [SalesOffice.Orders] o
            WHERE o.IsActive = 1
              AND o.DestinationId IN ({ids_str})
            GROUP BY o.DestinationId
        """)
        layer3b = layer3  # single query covers both
        orders = {}
        for df in [layer3, layer3b]:
            if not df.empty:
                for _, r in df.iterrows():
                    hid = int(r["HotelId"])
                    if hid not in orders:
                        orders[hid] = {"active_orders": int(r["active_orders"]), "last_status": str(r.get("last_status", ""))}

        # Layer 4: SalesOffice.Details (recent data)
        layer4 = run_trading_query(f"""
            SELECT d.HotelId, COUNT(*) AS detail_rows,
                   MAX(d.DateCreated) AS last_scan
            FROM [SalesOffice.Details] d
            JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
            WHERE d.HotelId IN ({ids_str}) AND o.IsActive = 1
            GROUP BY d.HotelId
        """)
        details = {int(r["HotelId"]): {"rows": int(r["detail_rows"]), "last_scan": str(r.get("last_scan", ""))} for _, r in layer4.iterrows()} if not layer4.empty else {}

        # Build results
        ready_count = 0
        for hid, name in TARGET_HOTELS.items():
            mh = med_hotels.get(hid)
            rc = ratebycat.get(hid, 0)
            od = orders.get(hid)
            dt = details.get(hid)

            l1_ok = mh is not None and int(mh.get("Innstant_ZenithId", 0) or 0) > 0 and int(mh.get("isActive", 0) or 0) == 1
            l2_ok = rc > 0
            l3_ok = od is not None and od["active_orders"] > 0
            l3_mapped = l3_ok and "Mapping: 0" not in (od.get("last_status") or "")
            l4_ok = dt is not None and dt["rows"] > 0
            all_ok = l1_ok and l2_ok and l3_mapped and l4_ok
            if all_ok:
                ready_count += 1

            results.append({
                "hotel_id": hid,
                "hotel_name": name,
                "ready": all_ok,
                "layer1_med_hotels": {
                    "ok": l1_ok,
                    "exists": mh is not None,
                    "zenith_id": int(mh["Innstant_ZenithId"]) if mh is not None and mh.get("Innstant_ZenithId") else None,
                    "is_active": int(mh["isActive"]) if mh is not None and mh.get("isActive") is not None else None,
                },
                "layer2_ratebycat": {"ok": l2_ok, "rows": rc},
                "layer3_orders": {
                    "ok": l3_mapped,
                    "active_orders": od["active_orders"] if od else 0,
                    "last_status": od.get("last_status") if od else None,
                },
                "layer4_details": {
                    "ok": l4_ok,
                    "rows": dt["rows"] if dt else 0,
                    "last_scan": dt.get("last_scan") if dt else None,
                },
            })

        return {
            "total_target": len(TARGET_HOTELS),
            "ready": ready_count,
            "not_ready": len(TARGET_HOTELS) - ready_count,
            "hotels": sorted(results, key=lambda x: (x["ready"], x["hotel_name"])),
        }

    except (OSError, ConnectionError, ValueError) as exc:
        logger.error("hotel-readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"error": str(exc), "hint": "medici-db may be unreachable"},
        )


# ── Path Forecast Endpoints ─────────────────────────────────────────────

@analytics_router.get("/path-forecast")
@limiter.limit(RATE_LIMIT_DATA)
async def path_forecast_all(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    hotel_id: int | None = Query(None, description="Filter by hotel ID"),
    min_profit: float = Query(0.0, description="Min trade profit % to include"),
):
    """Full path forecast for all active options.

    Returns the complete predicted price path from now to check-in,
    with turning points, segments, min/max prices, and optimal
    buy/sell opportunities.

    Unlike /options which gives a single CALL/PUT signal, this shows
    the FULL LIFECYCLE of each option — ups, downs, best entry/exit.
    """
    from src.analytics.path_forecast import analyze_portfolio_paths

    analysis = _get_cached_analysis()
    if not analysis:
        analysis = await _get_or_run_analysis()
    if not analysis or not analysis.get("predictions"):
        return {"paths": [], "total": 0, "message": "No analysis data available"}

    all_paths = analyze_portfolio_paths(analysis, source="ensemble")

    # Filter by hotel
    if hotel_id is not None:
        all_paths = [p for p in all_paths if p.get("hotel_id") == hotel_id]

    # Filter by minimum profit opportunity
    if min_profit > 0:
        all_paths = [p for p in all_paths if p.get("max_trade_profit_pct", 0) >= min_profit]

    total = len(all_paths)
    page = all_paths[offset: offset + limit]

    return {
        "paths": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "source": "ensemble",
    }


@analytics_router.get("/path-forecast/{detail_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def path_forecast_detail(
    request: Request,
    detail_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Full path forecast for a single option/room.

    Shows the complete price lifecycle with all turning points,
    segments, and trading opportunities.
    """
    from src.analytics.path_forecast import analyze_path

    analysis = _get_cached_analysis()
    if not analysis:
        analysis = await _get_or_run_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(404, "No analysis data available")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found")

    fc_points = pred.get("forward_curve") or []
    current_price = float(pred.get("current_price", 0) or 0)

    if not fc_points or current_price <= 0:
        raise HTTPException(404, f"No forward curve data for detail {detail_id}")

    path = analyze_path(
        forward_curve_points=fc_points,
        detail_id=detail_id,
        hotel_id=int(pred.get("hotel_id", 0)),
        hotel_name=str(pred.get("hotel_name", "")),
        category=str(pred.get("category", "")),
        board=str(pred.get("board", "")),
        checkin_date=str(pred.get("date_from", "")),
        current_price=current_price,
        current_t=int(pred.get("days_to_checkin", 0)),
        source="ensemble",
        enrichments_applied=True,
        data_quality=str(pred.get("confidence_quality", "medium")),
    )

    return path.to_dict()


# ── Raw Source Analysis Endpoints ────────────────────────────────────────

@analytics_router.get("/sources/compare")
@limiter.limit(RATE_LIMIT_DATA)
async def sources_compare_all(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    hotel_id: int | None = Query(None, description="Filter by hotel ID"),
    disagreements_only: bool = Query(False, description="Only show where sources disagree"),
):
    """Compare all data sources independently — no ensemble, no enrichments.

    For each active option, shows what each source says on its own:
    statistical profile, independent prediction, and consensus analysis.

    Use this to see where sources agree vs. disagree, and how the
    ensemble compares to the raw consensus.
    """
    from src.analytics.raw_source_analyzer import compare_all_sources


    analysis = _get_cached_analysis()
    if not analysis:
        analysis = await _get_or_run_analysis()
    if not analysis or not analysis.get("predictions"):
        return {"comparisons": [], "total": 0, "message": "No analysis data available"}

    signals = _get_cached_signals()
    all_comps = compare_all_sources(analysis, signals)

    # Filter by hotel
    if hotel_id is not None:
        all_comps = [c for c in all_comps if c.get("hotel_id") == hotel_id]

    # Filter disagreements only
    if disagreements_only:
        all_comps = [c for c in all_comps if c.get("disagreement_flag")]

    total = len(all_comps)
    page = all_comps[offset: offset + limit]

    return {
        "comparisons": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "disagreements_in_total": sum(1 for c in all_comps if c.get("disagreement_flag")),
    }


@analytics_router.get("/sources/compare/{detail_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def sources_compare_detail(
    request: Request,
    detail_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Compare all sources for a single option — raw data, no blending.

    Shows per-source statistics, independent predictions, and
    consensus analysis for one specific room/option.
    """
    from src.analytics.raw_source_analyzer import compare_sources

    analysis = _get_cached_analysis()
    if not analysis:
        analysis = await _get_or_run_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(404, "No analysis data available")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found")

    # Build ensemble signal from prediction data directly (avoid slow compute_next_day_signals)
    ensemble_signal = {
        "recommendation": _derive_option_signal(pred),
        "predicted_price": pred.get("predicted_checkin_price", pred.get("predicted_price", 0)),
    }

    try:
        comparison = compare_sources(pred, ensemble_signal)
        return comparison.to_dict()
    except Exception as exc:
        logger.error("sources/compare/%s failed: %s", detail_id, exc, exc_info=True)
        raise HTTPException(500, f"Source comparison failed: {exc}")


@analytics_router.get("/sources/raw/{source_name}/{detail_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def source_raw_detail(
    request: Request,
    source_name: str,
    detail_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Raw statistical analysis from a single source for one option.

    Returns the pure statistical view and prediction from one source
    with ZERO enrichments and ZERO blending — just the data.

    Valid sources: forward_curve, historical_pattern, ml_forecast,
    salesoffice, ai_search_hotel_data, search_results_poll_log
    """
    from src.analytics.raw_source_analyzer import (
        analyze_source_statistics,
        build_source_prediction,
        PREDICTIVE_SOURCES,
        ENRICHMENT_ONLY_SOURCES,
    )

    valid_sources = PREDICTIVE_SOURCES | ENRICHMENT_ONLY_SOURCES
    if source_name not in valid_sources:
        raise HTTPException(400, f"Unknown source: {source_name}. Valid: {sorted(valid_sources)}")

    analysis = _get_cached_analysis()
    if not analysis:
        analysis = await _get_or_run_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(404, "No analysis data available")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found")

    stats = analyze_source_statistics(pred, source_name)
    prediction = build_source_prediction(pred, source_name, stats)

    return {
        "detail_id": detail_id,
        "source": source_name,
        "current_price": float(pred.get("current_price", 0) or 0),
        "days_to_checkin": int(pred.get("days_to_checkin", 0) or 0),
        "statistics": stats.to_dict(),
        "prediction": {
            "predicted_price": prediction.predicted_price,
            "predicted_change_pct": prediction.predicted_change_pct,
            "direction": prediction.direction,
            "confidence": prediction.confidence,
            "basis": prediction.basis,
            "n_supporting_cases": prediction.n_supporting_cases,
            "n_total_cases": prediction.n_total_cases,
        },
    }


# ── Price Override Queue Endpoints ───────────────────────────────────────

@analytics_router.post("/override/request")
@limiter.limit(RATE_LIMIT_DATA)
async def override_request_single(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Queue a single price override — undercut competitors by $X.

    Body JSON:
        detail_id: int — room detail ID
        discount_usd: float — dollars to subtract (default 1.0)

    The system computes target_price = current_price - discount_usd,
    validates guardrails, and saves to the local queue.
    The external price-override skill picks it up and executes.
    """
    from src.analytics.override_queue import (
        enqueue_override,
        OverrideValidationError,
    )

    body = await request.json()
    detail_id = int(body.get("detail_id", 0))
    discount_usd = float(body.get("discount_usd", 1.0))

    if not detail_id:
        raise HTTPException(400, "detail_id is required")

    # Get current prediction data for context
    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data available — run warmup first")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found in predictions")

    current_price = float(pred.get("current_price", 0) or 0)
    if current_price <= 0:
        raise HTTPException(400, f"Detail {detail_id} has no valid current price")

    try:
        req = enqueue_override(
            detail_id=detail_id,
            hotel_id=int(pred.get("hotel_id", 0)),
            current_price=current_price,
            discount_usd=discount_usd,
            signal=str(body.get("signal", "PUT")),
            confidence=str(body.get("confidence", "")),
            hotel_name=str(pred.get("hotel_name", "")),
            category=str(pred.get("category", "")),
            board=str(pred.get("board", "")),
            checkin_date=str(pred.get("date_from", "")),
            path_min_price=body.get("path_min_price"),
            trigger_type="manual",
        )
    except OverrideValidationError as exc:
        raise HTTPException(400, str(exc))

    return {
        "request_id": req.id,
        "detail_id": req.detail_id,
        "current_price": req.current_price,
        "discount_usd": req.discount_usd,
        "target_price": req.target_price,
        "status": req.status,
    }


@analytics_router.post("/override/bulk")
@limiter.limit("10/minute")
async def override_bulk_puts(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Queue overrides for ALL active PUT signals in one batch.

    Body JSON:
        discount_usd: float — dollars to subtract (default 1.0)
        hotel_id: int|null — optional hotel filter
        signal_filter: str — "PUT" or "STRONG_PUT" (default: both)

    Creates a batch of override requests. The external skill
    picks them all up and executes sequentially.
    """
    from src.analytics.override_queue import (
        enqueue_bulk_puts,
        OverrideValidationError,
    )


    body = await request.json()
    discount_usd = float(body.get("discount_usd", 1.0))
    hotel_id_filter = body.get("hotel_id")
    if hotel_id_filter is not None:
        hotel_id_filter = int(hotel_id_filter)

    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data available — run warmup first")

    signals = _get_cached_signals()

    try:
        batch_id, requests = enqueue_bulk_puts(
            analysis=analysis,
            signals=signals,
            discount_usd=discount_usd,
            hotel_id_filter=hotel_id_filter,
        )
    except OverrideValidationError as exc:
        raise HTTPException(400, str(exc))

    return {
        "batch_id": batch_id,
        "count": len(requests),
        "discount_usd": discount_usd,
        "requests": [
            {
                "request_id": r.id,
                "detail_id": r.detail_id,
                "hotel_name": r.hotel_name,
                "current_price": r.current_price,
                "target_price": r.target_price,
            }
            for r in requests
        ],
    }


@analytics_router.get("/override/queue")
@limiter.limit(RATE_LIMIT_DATA)
async def override_queue_list(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    status: str | None = Query(None, description="Filter: pending, picked, done, failed"),
    batch_id: str | None = Query(None),
    hotel_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """View the override queue — pending, in-progress, completed, failed."""
    from src.analytics.override_queue import get_queue, get_queue_stats

    requests, total = get_queue(
        status=status, batch_id=batch_id, hotel_id=hotel_id,
        limit=limit, offset=offset,
    )
    stats = get_queue_stats()

    return {
        "requests": [r.to_dict() for r in requests],
        "total": total,
        "offset": offset,
        "limit": limit,
        "stats": stats,
    }


@analytics_router.get("/override/queue/{request_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def override_queue_detail(
    request: Request,
    request_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Get status of a single override request."""
    from src.analytics.override_queue import get_request

    req = get_request(request_id)
    if not req:
        raise HTTPException(404, f"Override request {request_id} not found")

    return req.to_dict()


@analytics_router.get("/override/pending")
@limiter.limit(RATE_LIMIT_DATA)
async def override_pending(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    limit: int = Query(50, ge=1, le=200),
):
    """Get all pending override requests — consumed by the external skill.

    The price-override skill polls this endpoint (or reads SQLite directly)
    to pick up work.
    """
    from src.analytics.override_queue import get_pending_requests

    pending = get_pending_requests(limit=limit)
    return {
        "pending": [r.to_dict() for r in pending],
        "count": len(pending),
    }


@analytics_router.post("/override/{request_id}/complete")
@limiter.limit(RATE_LIMIT_DATA)
async def override_complete(
    request: Request,
    request_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Report execution result — called by the external skill after push.

    Body JSON:
        status: "done" or "failed"
        error_message: string (optional, for failures)
    """
    from src.analytics.override_queue import mark_completed, mark_picked

    body = await request.json()
    status = body.get("status", "done")
    error_message = body.get("error_message", "")

    if status not in ("done", "failed"):
        raise HTTPException(400, "status must be 'done' or 'failed'")

    success = mark_completed(request_id, success=(status == "done"), error_message=error_message)
    if not success:
        raise HTTPException(404, f"Override request {request_id} not found or already completed")

    return {"request_id": request_id, "status": status}


@analytics_router.get("/override/history")
@limiter.limit(RATE_LIMIT_DATA)
async def override_history(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    days: int = Query(30, ge=1, le=365),
    hotel_id: int | None = Query(None),
):
    """Override execution history — for post-trade analysis.

    Shows: total overrides, success rate, avg discount, breakdown by hotel.
    """
    from src.analytics.override_queue import get_history

    return get_history(days=days, hotel_id=hotel_id)


# ── Insert Opportunity Endpoints ─────────────────────────────────────

@analytics_router.post("/opportunity/request")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_request_single(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Queue a single insert-opportunity — buy at current price, push at buy+$50.

    Only accepted if predicted_price - buy_price >= $50.

    Body JSON:
        detail_id: int
        max_rooms: int (default 1)
    """
    from src.analytics.opportunity_queue import (
        enqueue_opportunity,
        OpportunityValidationError,
    )

    body = await request.json()
    detail_id = int(body.get("detail_id", 0))
    if not detail_id:
        raise HTTPException(400, "detail_id is required")

    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data available — run warmup first")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found in predictions")

    buy_price = float(pred.get("current_price", 0) or 0)
    if buy_price <= 0:
        raise HTTPException(400, f"Detail {detail_id} has no valid current price")

    predicted_price = float(
        pred.get("predicted_checkin_price", 0)
        or pred.get("predicted_price", 0)
        or 0
    )
    if predicted_price <= 0:
        raise HTTPException(400, f"Detail {detail_id} has no predicted price")

    try:
        req = enqueue_opportunity(
            detail_id=detail_id,
            hotel_id=int(pred.get("hotel_id", 0)),
            buy_price=buy_price,
            predicted_price=predicted_price,
            max_rooms=int(body.get("max_rooms", 1)),
            signal=str(body.get("signal", "CALL")),
            confidence=str(body.get("confidence", "")),
            hotel_name=str(pred.get("hotel_name", "")),
            category=str(pred.get("category", "")),
            board=str(pred.get("board", "")),
            checkin_date=str(pred.get("date_from", "")),
            trigger_type="manual",
        )
    except OpportunityValidationError as exc:
        raise HTTPException(400, str(exc))

    return {
        "request_id": req.id,
        "detail_id": req.detail_id,
        "buy_price": req.buy_price,
        "push_price": req.push_price,
        "predicted_price": req.predicted_price,
        "profit_usd": req.profit_usd,
        "max_rooms": req.max_rooms,
        "status": req.status,
    }


@analytics_router.post("/opportunity/bulk")
@limiter.limit("10/minute")
async def opportunity_bulk_calls(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Queue opportunities for ALL active CALL signals with $50+ predicted profit.

    push_price = buy_price + $50. Only options where predicted - buy >= $50.

    Body JSON:
        max_rooms: int (default 1)
        hotel_id: int|null (optional filter)
    """
    from src.analytics.opportunity_queue import (
        enqueue_bulk_calls,
        OpportunityValidationError,
    )


    body = await request.json()
    max_rooms = int(body.get("max_rooms", 1))
    hotel_id_filter = body.get("hotel_id")
    if hotel_id_filter is not None:
        hotel_id_filter = int(hotel_id_filter)

    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data available — run warmup first")

    signals = _get_cached_signals()

    try:
        batch_id, requests = enqueue_bulk_calls(
            analysis=analysis,
            signals=signals,
            max_rooms=max_rooms,
            hotel_id_filter=hotel_id_filter,
        )
    except OpportunityValidationError as exc:
        raise HTTPException(400, str(exc))

    return {
        "batch_id": batch_id,
        "count": len(requests),
        "markup_usd": 50.0,
        "requests": [
            {"request_id": r.id, "detail_id": r.detail_id, "hotel_name": r.hotel_name,
             "buy_price": r.buy_price, "push_price": r.push_price,
             "predicted_price": r.predicted_price, "profit_usd": r.profit_usd}
            for r in requests
        ],
    }


@analytics_router.get("/opportunity/queue")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_queue_list(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    status: str | None = Query(None),
    hotel_id: int | None = Query(None),
    batch_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """View the opportunity queue."""
    from src.analytics.opportunity_queue import get_queue, get_queue_stats

    requests, total = get_queue(
        status=status, hotel_id=hotel_id, batch_id=batch_id,
        limit=limit, offset=offset,
    )
    stats = get_queue_stats()

    return {
        "requests": [r.to_dict() for r in requests],
        "total": total, "offset": offset, "limit": limit, "stats": stats,
    }


@analytics_router.get("/opportunity/queue/{request_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_queue_detail(
    request: Request,
    request_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Get status of a single opportunity request."""
    from src.analytics.opportunity_queue import get_request

    req = get_request(request_id)
    if not req:
        raise HTTPException(404, f"Opportunity request {request_id} not found")
    return req.to_dict()


@analytics_router.get("/opportunity/pending")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_pending(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    limit: int = Query(50, ge=1, le=200),
):
    """Get pending opportunities — consumed by the external insert-opp skill."""
    from src.analytics.opportunity_queue import get_pending_requests

    pending = get_pending_requests(limit=limit)
    return {"pending": [r.to_dict() for r in pending], "count": len(pending)}


@analytics_router.post("/opportunity/{request_id}/complete")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_complete(
    request: Request,
    request_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Report execution result — called by external insert-opp skill."""
    from src.analytics.opportunity_queue import mark_completed

    body = await request.json()
    status = body.get("status", "done")
    error_message = body.get("error_message", "")
    opp_id = body.get("opp_id")  # BackOfficeOPT.id from skill
    if status not in ("done", "failed"):
        raise HTTPException(400, "status must be 'done' or 'failed'")

    success = mark_completed(
        request_id, success=(status == "done"),
        opp_id=opp_id, error_message=error_message,
    )
    if not success:
        raise HTTPException(404, f"Opportunity request {request_id} not found or already completed")
    return {"request_id": request_id, "status": status}


@analytics_router.get("/opportunity/history")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_history(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    days: int = Query(30, ge=1, le=365),
    hotel_id: int | None = Query(None),
):
    """Opportunity execution history."""
    from src.analytics.opportunity_queue import get_history
    return get_history(days=days, hotel_id=hotel_id)


# ── Monitor Bridge Endpoints ─────────────────────────────────────────


@analytics_router.get("/monitor/status")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_booking_engine_status(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Booking engine health status from monitor bridge."""
    from src.analytics.monitor_bridge import get_booking_engine_status
    return get_booking_engine_status()


@analytics_router.get("/monitor/trend")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_trend(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    hours: int = Query(24, ge=1, le=168),
):
    """Booking engine health trend over time."""
    from src.analytics.monitor_bridge import get_monitor_trend
    return get_monitor_trend(hours=hours)


@analytics_router.get("/monitor/degraded-hotels")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_degraded_hotels(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Hotels with ORDER≠DETAIL gaps above degradation threshold."""
    from src.analytics.monitor_bridge import MonitorBridge
    bridge = MonitorBridge()
    return {"degraded_hotels": bridge.get_degraded_hotels()}


@analytics_router.post("/monitor/ingest")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_ingest_report(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    report_path: str = Query(..., description="Path to monitor JSON report"),
):
    """Ingest a monitor report into the prediction system."""
    from src.analytics.monitor_bridge import MonitorBridge
    bridge = MonitorBridge()
    return bridge.ingest_report(report_path)
