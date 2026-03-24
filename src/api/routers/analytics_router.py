"""Core analytics endpoints — JSON APIs for data, options, forward curve, backtest."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

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


class OverrideRequestBody(BaseModel):
    detail_id: int = Field(gt=0)
    discount_usd: float = Field(default=1.0)
    signal: str = "PUT"
    confidence: str = ""
    path_min_price: float | None = None


class OverrideBulkRequestBody(BaseModel):
    discount_usd: float = Field(default=1.0)
    hotel_id: int | None = None


class QueueCompletionBody(BaseModel):
    status: Literal["done", "failed"] = "done"
    error_message: str = ""


class OpportunityRequestBody(BaseModel):
    detail_id: int = Field(gt=0)
    max_rooms: int = Field(default=1)
    signal: str = "CALL"
    confidence: str = ""


class OpportunityBulkRequestBody(BaseModel):
    max_rooms: int = Field(default=1)
    hotel_id: int | None = None


class OpportunityCompletionBody(QueueCompletionBody):
    opp_id: int | None = None


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

        # Segment enrichment — zone + tier
        from config.hotel_segments import get_hotel_segment
        _hotel_id = pred_view.get("hotel_id")
        _seg = get_hotel_segment(int(_hotel_id)) if _hotel_id else None

        row = {
            "detail_id": int(detail_id),
            "hotel_id": _hotel_id,
            "hotel_name": pred_view.get("hotel_name"),
            "zone": _seg["zone_name"] if _seg else "",
            "tier": _seg["tier_name"] if _seg else "",
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
    if not signals:
        return JSONResponse(content={
            "filter": str(gf.describe()),
            "total_matched": 0,
            "total_value_usd": 0,
            "hotel_breakdown": [],
            "signals_warming": True,
            "message": "Signals are computing in background. Retry in 30 seconds.",
        })
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
    payload: OverrideRequestBody,
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

    detail_id = payload.detail_id
    discount_usd = payload.discount_usd

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
            signal=payload.signal,
            confidence=payload.confidence,
            hotel_name=str(pred.get("hotel_name", "")),
            category=str(pred.get("category", "")),
            board=str(pred.get("board", "")),
            checkin_date=str(pred.get("date_from", "")),
            path_min_price=payload.path_min_price,
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
    payload: OverrideBulkRequestBody,
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
    discount_usd = payload.discount_usd
    hotel_id_filter = payload.hotel_id

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
    payload: QueueCompletionBody,
    _api_key: str = Depends(_optional_api_key),
):
    """Report execution result — called by the external skill after push.

    Body JSON:
        status: "done" or "failed"
        error_message: string (optional, for failures)
    """
    from src.analytics.override_queue import mark_completed

    success = mark_completed(
        request_id,
        success=(payload.status == "done"),
        error_message=payload.error_message,
    )
    if not success:
        raise HTTPException(404, f"Override request {request_id} not found or already completed")

    return {"request_id": request_id, "status": payload.status}


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


# ── Override Execute (Direct Push to Zenith) ────────────────────────────

@analytics_router.post("/override/execute")
@limiter.limit("10/minute")
async def override_execute_direct(
    request: Request,
    payload: OverrideRequestBody,
    _api_key: str = Depends(_optional_api_key),
):
    """Execute a single price override directly — write to DB + push to Zenith.

    This is the live execution endpoint. It:
    1. Looks up the detail in Azure SQL (mapping, current price)
    2. Writes to SalesOffice.PriceOverride
    3. Pushes the new price to Zenith via SOAP
    4. Returns the result

    Use /override/request for queue-based (async) flow instead.
    """
    import pyodbc
    import os

    detail_id = payload.detail_id
    discount_usd = payload.discount_usd

    # Get current prediction data
    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data — run warmup first")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found")

    # Guardrail: only PUT signals can be overridden
    pred_signal = pred.get("option_signal", "")
    if pred_signal not in ("PUT", "STRONG_PUT"):
        raise HTTPException(400, f"Detail {detail_id} signal is {pred_signal}, not PUT — override rejected")

    current_price = float(pred.get("current_price", 0) or 0)
    if current_price <= 0:
        raise HTTPException(400, f"Detail {detail_id}: no valid price")

    target_price = round(current_price - discount_usd, 2)
    if target_price < 50:
        raise HTTPException(400, f"Target ${target_price} below $50 minimum")
    if discount_usd <= 0 or discount_usd > 10:
        raise HTTPException(400, f"Discount must be $0.01-$10.00")

    # Connect to Azure SQL
    db_url = os.getenv("MEDICI_DB_URL", "")
    if not db_url:
        raise HTTPException(503, "MEDICI_DB_URL not configured")

    # Convert SQLAlchemy URL to pyodbc connection string
    # mssql+pyodbc://user:pass@server/db?driver=... → DRIVER=...;Server=...;...
    try:
        from urllib.parse import urlparse, parse_qs, unquote
        parsed = urlparse(db_url)
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        server = parsed.hostname or ""
        database = parsed.path.lstrip("/")
        qs = parse_qs(parsed.query)
        driver = qs.get("driver", ["ODBC Driver 18 for SQL Server"])[0]

        conn_str = (
            f"DRIVER={{{driver}}};Server={server};Database={database};"
            f"Uid={user};Pwd={password};Encrypt=yes;TrustServerCertificate=no;"
            f"Connection Timeout=15"
        )
        conn = pyodbc.connect(conn_str, timeout=15)
    except Exception as exc:
        logger.error("Override execute: DB connect failed: %s", exc)
        raise HTTPException(503, f"DB connection failed: {str(exc)[:100]}")

    try:
        cursor = conn.cursor()

        # Debug: check which user we're connected as
        cursor.execute("SELECT CURRENT_USER AS cu, SYSTEM_USER AS su")
        _dbuser = cursor.fetchone()
        db_user_info = {"current_user": _dbuser[0], "system_user": _dbuser[1]}

        # Step 1: Get detail with Zenith mapping
        cursor.execute("""
            SELECT d.Id, d.HotelId, d.RoomCategory, d.RoomBoard, d.RoomPrice,
                   d.IsDeleted, d.SalesOfficeOrderId,
                   o.DateFrom, o.DateTo,
                   h.Innstant_ZenithId, h.[Name] as HotelName,
                   r.RatePlanCode, r.InvTypeCode
            FROM [SalesOffice.Details] d
            JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
            LEFT JOIN Med_Hotels h ON h.HotelId = d.HotelId
            LEFT JOIN MED_Board brd ON brd.BoardCode = d.RoomBoard
            LEFT JOIN MED_RoomCategory cat ON LOWER(cat.[Name]) = LOWER(d.RoomCategory)
            LEFT JOIN Med_Hotels_ratebycat r
                ON r.HotelId = d.HotelId AND r.BoardId = brd.BoardId AND r.CategoryId = cat.CategoryId
            WHERE d.Id = ?
        """, detail_id)
        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, f"Detail {detail_id} not found in DB")

        cols = [desc[0] for desc in cursor.description]
        detail = dict(zip(cols, row))

        if detail.get("IsDeleted"):
            raise HTTPException(400, f"Detail {detail_id} is deleted")

        if not detail.get("RatePlanCode") or not detail.get("InvTypeCode"):
            raise HTTPException(400, f"Detail {detail_id}: no Zenith mapping (RPC/ITC missing)")

        original_price = float(detail["RoomPrice"])
        zenith_id = str(detail["Innstant_ZenithId"])
        rpc = detail["RatePlanCode"]
        itc = detail["InvTypeCode"]
        date_from = detail["DateFrom"].strftime("%Y-%m-%d")
        hotel_name = detail.get("HotelName", "")

        # Deviation check
        if original_price > 0:
            deviation = abs(target_price - original_price) / original_price * 100
            if deviation > 50:
                raise HTTPException(400, f"Target ${target_price} deviates {deviation:.0f}% from DB price ${original_price} (max 50%)")

        # Step 2: Write to SalesOffice.PriceOverride
        try:
            cursor.execute("""
                UPDATE [SalesOffice.PriceOverride]
                SET IsActive = 0
                WHERE DetailId = ? AND IsActive = 1
            """, detail_id)

            cursor.execute("""
                INSERT INTO [SalesOffice.PriceOverride]
                (DetailId, OriginalPrice, OverridePrice, CreatedBy, IsActive)
                VALUES (?, ?, ?, 'PricePredictor', 1)
            """, detail_id, original_price, target_price)
            conn.commit()
            db_write = "success"
        except Exception as exc:
            db_write = f"failed: {str(exc)[:300]}"
            logger.error("Override DB write failed: %s", exc)

        # Step 3: Push to Zenith
        import requests as req_lib
        from datetime import datetime as dt

        soap = f'''<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Header>
    <wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <wsse:UsernameToken>
        <wsse:Username>APIMedici:Medici Live</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">12345</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" TimeStamp="{dt.now().strftime("%Y-%m-%dT%H:%M:%S")}" Version="1.0" EchoToken="override-test">
      <RateAmountMessages HotelCode="{zenith_id}">
        <RateAmountMessage>
          <StatusApplicationControl InvTypeCode="{itc}" RatePlanCode="{rpc}" Start="{date_from}" End="{date_from}"/>
          <Rates>
            <Rate>
              <BaseByGuestAmts>
                <BaseByGuestAmt AgeQualifyingCode="10" AmountAfterTax="{target_price}"/>
                <BaseByGuestAmt AgeQualifyingCode="8" AmountAfterTax="{target_price}"/>
              </BaseByGuestAmts>
            </Rate>
          </Rates>
        </RateAmountMessage>
      </RateAmountMessages>
    </OTA_HotelRateAmountNotifRQ>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>'''

        zenith_result = {"status": "not_pushed", "detail": "Waiting for confirmation"}
        # *** SAFETY: Only push if explicitly enabled ***
        push_enabled = os.getenv("OVERRIDE_PUSH_ENABLED", "false").lower() == "true"
        if push_enabled:
            try:
                resp = req_lib.post(
                    "https://hotel.tools/service/Medici%20new",
                    data=soap,
                    headers={"Content-Type": "text/xml"},
                    timeout=10,
                )
                zenith_success = resp.status_code == 200 and "Error" not in resp.text
                zenith_result = {
                    "status": "success" if zenith_success else "error",
                    "http_code": resp.status_code,
                    "response_preview": resp.text[:200],
                }
            except Exception as exc:
                zenith_result = {"status": "error", "detail": str(exc)[:200]}
        else:
            zenith_result = {
                "status": "dry_run",
                "detail": "OVERRIDE_PUSH_ENABLED=false — Zenith push skipped. Set to true to enable.",
                "soap_preview": soap[:300] + "...",
            }

        return {
            "action": "override_execute",
            "detail_id": detail_id,
            "hotel_name": hotel_name,
            "original_price": original_price,
            "discount_usd": discount_usd,
            "target_price": target_price,
            "db_write": db_write,
            "zenith_push": zenith_result,
            "zenith_mapping": {"hotel_code": zenith_id, "rpc": rpc, "itc": itc, "date": date_from},
            "db_user": db_user_info,
        }

    finally:
        conn.close()


# ── Override Audit Log (from Azure SQL PriceOverride table) ─────────────

@analytics_router.get("/override/audit")
@limiter.limit(RATE_LIMIT_DATA)
async def override_audit_log(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    hotel_id: int | None = Query(None),
    detail_id: int | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
):
    """Override audit log from Azure SQL — shows all PriceOverride records.

    Returns which options were overridden, when, by whom, original vs override price.
    Use this to track execution history across scan cycles.
    """
    import pyodbc
    import os
    from urllib.parse import urlparse, parse_qs, unquote

    db_url = os.getenv("MEDICI_DB_URL", "")
    if not db_url:
        raise HTTPException(503, "MEDICI_DB_URL not configured")

    try:
        parsed = urlparse(db_url)
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        server = parsed.hostname or ""
        database = parsed.path.lstrip("/")
        qs_params = parse_qs(parsed.query)
        driver = qs_params.get("driver", ["ODBC Driver 18 for SQL Server"])[0]
        conn_str = (
            f"DRIVER={{{driver}}};Server={server};Database={database};"
            f"Uid={user};Pwd={password};Encrypt=yes;TrustServerCertificate=no;"
            f"Connection Timeout=15"
        )
        conn = pyodbc.connect(conn_str, timeout=15)
    except Exception as exc:
        raise HTTPException(503, f"DB connection failed: {str(exc)[:100]}")

    try:
        cursor = conn.cursor()
        sql = """
            SELECT TOP (?) po.Id, po.DetailId, po.OriginalPrice, po.OverridePrice,
                   po.CreatedBy, po.IsActive, po.PushStatus, po.PushedAt, po.CreatedAt,
                   d.HotelId, h.[Name] as HotelName, d.RoomCategory, d.RoomBoard,
                   o.DateFrom
            FROM [SalesOffice.PriceOverride] po
            LEFT JOIN [SalesOffice.Details] d ON d.Id = po.DetailId
            LEFT JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
            LEFT JOIN Med_Hotels h ON h.HotelId = d.HotelId
            WHERE 1=1
        """
        params = [limit]
        if hotel_id:
            sql += " AND d.HotelId = ?"
            params.append(hotel_id)
        if detail_id:
            sql += " AND po.DetailId = ?"
            params.append(detail_id)
        if active_only:
            sql += " AND po.IsActive = 1"
        sql += " ORDER BY po.CreatedAt DESC"

        cursor.execute(sql, params)
        cols = [desc[0] for desc in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

        # Summary stats
        active_count = sum(1 for r in rows if r.get("IsActive"))
        total_discount = sum(float(r.get("OriginalPrice", 0) or 0) - float(r.get("OverridePrice", 0) or 0) for r in rows)

        # Detail IDs with active overrides (for Command Center marking)
        active_detail_ids = [r["DetailId"] for r in rows if r.get("IsActive")]

        # Serialize datetime fields
        for r in rows:
            for k in ("PushedAt", "CreatedAt", "DateFrom"):
                if r.get(k) and hasattr(r[k], "isoformat"):
                    r[k] = r[k].isoformat()

        return {
            "total": len(rows),
            "active_overrides": active_count,
            "total_discount_usd": round(total_discount, 2),
            "active_detail_ids": active_detail_ids,
            "records": rows,
        }
    finally:
        conn.close()


# ── Override Rules (Persistent Trading Strategies) ──────────────────────


class OverrideRuleCreate(BaseModel):
    """Request body for creating an override rule."""
    name: str = ""
    signal: str = "PUT"
    discount_usd: float = 1.0
    hotel_id: int | None = None
    category: str | None = None
    board: str | None = None
    min_T: int = 7
    max_T: int = 120


@analytics_router.post("/override/rules")
@limiter.limit("10/minute")
async def create_override_rule(
    request: Request,
    body: OverrideRuleCreate,
    _api_key: str = Depends(_optional_api_key),
):
    """Create a persistent override rule."""
    from src.analytics.override_rules import init_rules_db, create_rule, RuleValidationError

    try:
        init_rules_db()
        rule = create_rule(
            signal=body.signal,
            discount_usd=body.discount_usd,
            name=body.name,
            hotel_id=body.hotel_id,
            category=body.category,
            board=body.board,
            min_T=body.min_T,
            max_T=body.max_T,
        )
        return {"status": "created", "rule": rule.to_dict()}
    except RuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@analytics_router.get("/override/rules")
@limiter.limit(RATE_LIMIT_DATA)
async def list_override_rules(
    request: Request,
    active_only: bool = Query(False, description="Only return active rules"),
    _api_key: str = Depends(_optional_api_key),
):
    """List all override rules."""
    from src.analytics.override_rules import get_rules

    rules = get_rules(active_only=active_only)
    rule_dicts = [r.to_dict() for r in rules]
    active_count = sum(1 for r in rules if r.is_active)
    return {"rules": rule_dicts, "total": len(rule_dicts), "active": active_count}


@analytics_router.get("/override/rules/{rule_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def get_override_rule(
    request: Request,
    rule_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Get a single override rule with its execution log."""
    from src.analytics.override_rules import get_rule, get_execution_log

    rule = get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    executions = get_execution_log(rule_id=rule_id, limit=50)
    return {"rule": rule.to_dict(), "executions": executions}


@analytics_router.put("/override/rules/{rule_id}")
@limiter.limit("10/minute")
async def update_override_rule(
    request: Request,
    rule_id: int,
    action: str = Query(..., description="'pause' or 'resume'"),
    _api_key: str = Depends(_optional_api_key),
):
    """Pause or resume an override rule."""
    from src.analytics.override_rules import pause_rule, resume_rule, get_rule

    if action not in ("pause", "resume"):
        raise HTTPException(status_code=400, detail="action must be 'pause' or 'resume'")

    rule = get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    if action == "pause":
        changed = pause_rule(rule_id)
    else:
        changed = resume_rule(rule_id)

    return {"status": action + "d", "rule_id": rule_id, "changed": changed}


@analytics_router.delete("/override/rules/{rule_id}")
@limiter.limit("10/minute")
async def delete_override_rule(
    request: Request,
    rule_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Delete an override rule permanently."""
    from src.analytics.override_rules import delete_rule

    deleted = delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "deleted", "rule_id": rule_id}


@analytics_router.post("/override/rules/trigger")
@limiter.limit("10/minute")
async def trigger_override_rules(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Manually trigger all active rules — match, write to DB, push to Zenith."""
    from src.analytics.override_rules import match_rules, execute_matched_overrides

    analysis = _get_cached_analysis()
    if not analysis:
        raise HTTPException(status_code=503, detail="No cached analysis available — run a collection cycle first")

    base = _get_or_build_options_base_payload(
        analysis, t_days=None, include_chart=False, profile="lite", source=None, source_only=False,
    )
    options = base.get("rows", []) if isinstance(base, dict) else []

    matches = match_rules(options)

    # Cap at 50 per trigger to avoid gateway timeout (121 * 200ms = 24s + DB = too slow)
    MAX_TRIGGER = 50
    total_matched = len(matches)
    capped = matches[:MAX_TRIGGER]

    # Execute in background thread to avoid timeout
    import threading
    results_holder = {"success": 0, "failed": 0, "skipped": 0, "total": 0}

    if capped:
        # Run synchronously for small batches, async for large
        if len(capped) <= 20:
            results_holder = execute_matched_overrides(capped)
        else:
            # Fire and forget — results logged to override_rule_log
            def _bg():
                try:
                    execute_matched_overrides(capped)
                except Exception as exc:
                    logger.error("Trigger background execution failed: %s", exc)
            threading.Thread(target=_bg, daemon=True).start()
            results_holder = {"status": "executing_in_background", "queued": len(capped)}

    return {
        "status": "triggered",
        "options_scanned": len(options),
        "matched": total_matched,
        "executing": len(capped),
        "capped_at": MAX_TRIGGER if total_matched > MAX_TRIGGER else None,
        "results": results_holder,
    }


# ── Opportunity Rules (Persistent CALL Strategies) ──────────────────────


class OpportunityRuleCreate(BaseModel):
    """Request body for creating an opportunity rule."""
    name: str = ""
    signal: str = "CALL"
    hotel_id: int | None = None
    category: str | None = None
    board: str | None = None
    min_T: int = 7
    max_T: int = 120
    push_markup_pct: float = 30.0


@analytics_router.post("/opportunity/rules")
@limiter.limit("10/minute")
async def create_opportunity_rule(
    request: Request,
    body: OpportunityRuleCreate,
    _api_key: str = Depends(_optional_api_key),
):
    """Create a persistent opportunity (CALL) rule."""
    from src.analytics.opportunity_rules import init_opp_rules_db, create_opp_rule, OppRuleValidationError

    try:
        init_opp_rules_db()
        rule = create_opp_rule(
            signal=body.signal,
            push_markup_pct=body.push_markup_pct,
            name=body.name,
            hotel_id=body.hotel_id,
            category=body.category,
            board=body.board,
            min_T=body.min_T,
            max_T=body.max_T,
        )
        return {"status": "created", "rule": rule.to_dict()}
    except OppRuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@analytics_router.get("/opportunity/rules")
@limiter.limit(RATE_LIMIT_DATA)
async def list_opportunity_rules(
    request: Request,
    active_only: bool = Query(False, description="Only return active rules"),
    _api_key: str = Depends(_optional_api_key),
):
    """List all opportunity rules."""
    from src.analytics.opportunity_rules import get_opp_rules

    rules = get_opp_rules(active_only=active_only)
    rule_dicts = [r.to_dict() for r in rules]
    active_count = sum(1 for r in rules if r.is_active)
    return {"rules": rule_dicts, "total": len(rule_dicts), "active": active_count}


@analytics_router.get("/opportunity/rules/{rule_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def get_opportunity_rule(
    request: Request,
    rule_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Get a single opportunity rule with its execution log."""
    from src.analytics.opportunity_rules import get_opp_rule, get_opp_execution_log

    rule = get_opp_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    executions = get_opp_execution_log(rule_id=rule_id, limit=50)
    return {"rule": rule.to_dict(), "executions": executions}


@analytics_router.put("/opportunity/rules/{rule_id}")
@limiter.limit("10/minute")
async def update_opportunity_rule(
    request: Request,
    rule_id: int,
    action: str = Query(..., description="'pause' or 'resume'"),
    _api_key: str = Depends(_optional_api_key),
):
    """Pause or resume an opportunity rule."""
    from src.analytics.opportunity_rules import pause_opp_rule, resume_opp_rule, get_opp_rule

    if action not in ("pause", "resume"):
        raise HTTPException(status_code=400, detail="action must be 'pause' or 'resume'")

    rule = get_opp_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    if action == "pause":
        changed = pause_opp_rule(rule_id)
    else:
        changed = resume_opp_rule(rule_id)

    return {"status": action + "d", "rule_id": rule_id, "changed": changed}


@analytics_router.delete("/opportunity/rules/{rule_id}")
@limiter.limit("10/minute")
async def delete_opportunity_rule(
    request: Request,
    rule_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Delete an opportunity rule permanently."""
    from src.analytics.opportunity_rules import delete_opp_rule

    deleted = delete_opp_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "deleted", "rule_id": rule_id}


@analytics_router.post("/opportunity/rules/trigger")
@limiter.limit("10/minute")
async def trigger_opportunity_rules(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
):
    """Manually trigger all active CALL rules — match, write to BackOfficeOPT + MED_Opportunities."""
    from src.analytics.opportunity_rules import match_opp_rules, execute_matched_opportunities

    analysis = _get_cached_analysis()
    if not analysis:
        raise HTTPException(status_code=503, detail="No cached analysis available — run a collection cycle first")

    base = _get_or_build_options_base_payload(
        analysis, t_days=None, include_chart=False, profile="lite", source=None, source_only=False,
    )
    options = base.get("rows", []) if isinstance(base, dict) else []

    matches = match_opp_rules(options)

    # Cap at 20 per trigger — budget conscious
    MAX_TRIGGER = 20
    total_matched = len(matches)
    capped = matches[:MAX_TRIGGER]

    import threading
    results_holder: dict = {"success": 0, "failed": 0, "skipped": 0, "total": 0}

    if capped:
        if len(capped) <= 10:
            results_holder = execute_matched_opportunities(capped)
        else:
            def _bg():
                try:
                    execute_matched_opportunities(capped)
                except Exception as exc:
                    logger.error("Opportunity trigger background execution failed: %s", exc)
            threading.Thread(target=_bg, daemon=True).start()
            results_holder = {"status": "executing_in_background", "queued": len(capped)}

    return {
        "status": "triggered",
        "options_scanned": len(options),
        "matched": total_matched,
        "executing": len(capped),
        "capped_at": MAX_TRIGGER if total_matched > MAX_TRIGGER else None,
        "results": results_holder,
    }


class OpportunitySingleExecute(BaseModel):
    """Request body for single opportunity execution."""
    detail_id: int = Field(gt=0)


@analytics_router.post("/opportunity/execute")
@limiter.limit("10/minute")
async def opportunity_execute_single(
    request: Request,
    body: OpportunitySingleExecute,
    _api_key: str = Depends(_optional_api_key),
):
    """Execute a single CALL opportunity — buy 1 room, write to BackOfficeOPT + MED_Opportunities.

    Auto-computes buy_price from current option price and push_price with 30% markup.
    """
    from src.analytics.opportunity_rules import execute_matched_opportunities

    # Look up the option to get current price
    analysis = _get_cached_analysis()
    if not analysis:
        raise HTTPException(status_code=503, detail="No cached analysis — run a collection cycle first")

    base = _get_or_build_options_base_payload(
        analysis, t_days=None, include_chart=False, profile="lite", source=None, source_only=False,
    )
    options = base.get("rows", []) if isinstance(base, dict) else []

    target = None
    for opt in options:
        if opt.get("detail_id") == body.detail_id:
            target = opt
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Option detail_id={body.detail_id} not found in current scan")

    # Guardrail: only CALL signals can create opportunities
    opt_signal = target.get("option_signal", "")
    if opt_signal not in ("CALL", "STRONG_CALL"):
        raise HTTPException(status_code=400, detail=f"Detail {body.detail_id} signal is {opt_signal}, not CALL — buy rejected")

    buy_price = float(target.get("current_price", 0))
    if buy_price <= 0:
        raise HTTPException(status_code=400, detail="Option has zero or negative price")

    push_price = round(buy_price * 1.30, 2)
    profit_usd = round(push_price - buy_price, 2)

    match_entry = {
        "detail_id": body.detail_id,
        "hotel_id": target.get("hotel_id", 0),
        "hotel_name": target.get("hotel_name", ""),
        "buy_price": buy_price,
        "push_price": push_price,
        "profit_usd": profit_usd,
        "rule_id": 0,  # manual execution, no rule
        "rule_name": "Manual",
    }

    result = execute_matched_opportunities([match_entry])
    return {
        "status": "executed",
        "detail_id": body.detail_id,
        "buy_price": buy_price,
        "push_price": push_price,
        "profit_usd": profit_usd,
        "result": result,
    }


# ── Override Execute Bulk (Direct Push to Zenith) ───────────────────────

@analytics_router.post("/override/execute-bulk")
@limiter.limit("5/minute")
async def override_execute_bulk(
    request: Request,
    _api_key: str = Depends(_optional_api_key),
    signal: str = Query("PUT", description="PUT only — override is for price reductions"),
    hotel_id: int | None = Query(None, description="Specific hotel or null=all"),
    category: str | None = Query(None, description="standard, deluxe, suite, superior"),
    board: str | None = Query(None, description="ro, bb"),
    min_T: int = Query(7, description="Min days to check-in"),
    max_T: int = Query(120, description="Max days to check-in"),
    discount_usd: float = Query(1.0, ge=0.01, le=10.0),
    max_items: int = Query(50, ge=1, le=200, description="Max overrides to execute"),
):
    """Execute price overrides in bulk — filter, write to DB, push to Zenith.

    Flow: filter PUT signals → write PriceOverride rows → push each to Zenith.
    Safety: OVERRIDE_PUSH_ENABLED env var must be true. 200ms delay between pushes.
    """
    import pyodbc
    import os
    import time as _time
    import requests as req_lib
    from datetime import datetime as dt
    from urllib.parse import urlparse, parse_qs, unquote

    push_enabled = os.getenv("OVERRIDE_PUSH_ENABLED", "false").lower() == "true"

    # Guardrail: override only works for PUT signals
    if signal not in ("PUT", "STRONG_PUT"):
        raise HTTPException(400, f"Override only supports PUT/STRONG_PUT signals, got: {signal}")

    # Step 1: Build options list from analysis (same logic as /options endpoint)
    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data — cache warming up")

    base = _get_or_build_options_base_payload(
        analysis, t_days=None, include_chart=False, profile="lite",
        source=None, source_only=False,
    )
    signals = base.get("rows", []) if isinstance(base, dict) else []

    candidates = []
    for pred in signals:
        sig = pred.get("option_signal", "") or pred.get("signal", "")
        if signal and sig not in (signal, f"STRONG_{signal}"):
            continue
        hid = int(pred.get("hotel_id", 0) or 0)
        if hotel_id and hid != hotel_id:
            continue
        if category and (pred.get("category", "") or "").lower() != category.lower():
            continue
        if board and (pred.get("board", "") or "").lower() != board.lower():
            continue
        t = int(pred.get("days_to_checkin", 0) or 0)
        if t < min_T or t > max_T:
            continue
        cp = float(pred.get("current_price", 0) or 0)
        if cp <= 0:
            continue
        target = round(cp - discount_usd, 2)
        if target < 50:
            continue
        candidates.append({
            "detail_id": int(pred.get("detail_id", 0)),
            "hotel_id": hid,
            "hotel_name": str(pred.get("hotel_name", "")),
            "category": str(pred.get("category", "")),
            "board": str(pred.get("board", "")),
            "current_price": cp,
            "target_price": target,
            "date_from": str(pred.get("date_from", "")),
            "signal": sig,
            "T": t,
        })

    # Cap to max_items
    candidates = candidates[:max_items]

    if not candidates:
        return {
            "action": "override_execute_bulk",
            "filter": {"signal": signal, "hotel_id": hotel_id, "category": category, "board": board, "min_T": min_T, "max_T": max_T},
            "total_matched": 0,
            "message": "No matching PUT signals found",
        }

    # Step 2: Connect to DB
    db_url = os.getenv("MEDICI_DB_URL", "")
    if not db_url:
        raise HTTPException(503, "MEDICI_DB_URL not configured")

    try:
        parsed = urlparse(db_url)
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        server = parsed.hostname or ""
        database = parsed.path.lstrip("/")
        qs_params = parse_qs(parsed.query)
        driver = qs_params.get("driver", ["ODBC Driver 18 for SQL Server"])[0]

        conn_str = (
            f"DRIVER={{{driver}}};Server={server};Database={database};"
            f"Uid={user};Pwd={password};Encrypt=yes;TrustServerCertificate=no;"
            f"Connection Timeout=15"
        )
        conn = pyodbc.connect(conn_str, timeout=15)
    except Exception as exc:
        logger.error("Override bulk: DB connect failed: %s", exc)
        raise HTTPException(503, f"DB connection failed: {str(exc)[:100]}")

    results = {"success": 0, "db_only": 0, "failed": 0, "skipped": 0, "errors": [], "details": []}

    try:
        cursor = conn.cursor()

        for item in candidates:
            detail_id = item["detail_id"]
            target_price = item["target_price"]

            # Get Zenith mapping
            cursor.execute("""
                SELECT d.Id, d.HotelId, d.RoomPrice, d.IsDeleted,
                       o.DateFrom,
                       h.Innstant_ZenithId,
                       r.RatePlanCode, r.InvTypeCode
                FROM [SalesOffice.Details] d
                JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
                LEFT JOIN Med_Hotels h ON h.HotelId = d.HotelId
                LEFT JOIN MED_Board brd ON brd.BoardCode = d.RoomBoard
                LEFT JOIN MED_RoomCategory cat ON LOWER(cat.[Name]) = LOWER(d.RoomCategory)
                LEFT JOIN Med_Hotels_ratebycat r
                    ON r.HotelId = d.HotelId AND r.BoardId = brd.BoardId AND r.CategoryId = cat.CategoryId
                WHERE d.Id = ?
            """, detail_id)
            row = cursor.fetchone()

            if not row:
                results["skipped"] += 1
                results["errors"].append(f"{detail_id}: not found in DB")
                continue

            cols = [desc[0] for desc in cursor.description]
            detail = dict(zip(cols, row))

            if detail.get("IsDeleted") or not detail.get("RatePlanCode") or not detail.get("InvTypeCode"):
                results["skipped"] += 1
                continue

            zenith_id = str(detail["Innstant_ZenithId"])
            rpc = detail["RatePlanCode"]
            itc = detail["InvTypeCode"]
            date_from = detail["DateFrom"].strftime("%Y-%m-%d")
            original_price = float(detail["RoomPrice"])

            # Deviation check
            if original_price > 0:
                deviation = abs(target_price - original_price) / original_price * 100
                if deviation > 50:
                    results["skipped"] += 1
                    results["errors"].append(f"{detail_id}: deviation {deviation:.0f}% > 50%")
                    continue

            # Write to PriceOverride
            try:
                cursor.execute("""
                    UPDATE [SalesOffice.PriceOverride]
                    SET IsActive = 0
                    WHERE DetailId = ? AND IsActive = 1
                """, detail_id)
                cursor.execute("""
                    INSERT INTO [SalesOffice.PriceOverride]
                    (DetailId, OriginalPrice, OverridePrice, CreatedBy, IsActive)
                    VALUES (?, ?, ?, 'PricePredictor', 1)
                """, detail_id, original_price, target_price)
                conn.commit()
            except Exception as exc:
                results["failed"] += 1
                results["errors"].append(f"{detail_id}: DB write failed - {str(exc)[:80]}")
                continue

            # Push to Zenith
            if push_enabled:
                soap = f'''<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Header><wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <wsse:UsernameToken><wsse:Username>APIMedici:Medici Live</wsse:Username>
      <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">12345</wsse:Password>
    </wsse:UsernameToken></wsse:Security></SOAP-ENV:Header>
  <SOAP-ENV:Body><OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" TimeStamp="{dt.now().strftime("%Y-%m-%dT%H:%M:%S")}" Version="1.0" EchoToken="bulk-override">
    <RateAmountMessages HotelCode="{zenith_id}"><RateAmountMessage>
      <StatusApplicationControl InvTypeCode="{itc}" RatePlanCode="{rpc}" Start="{date_from}" End="{date_from}"/>
      <Rates><Rate><BaseByGuestAmts>
        <BaseByGuestAmt AgeQualifyingCode="10" AmountAfterTax="{target_price}"/>
        <BaseByGuestAmt AgeQualifyingCode="8" AmountAfterTax="{target_price}"/>
      </BaseByGuestAmts></Rate></Rates>
    </RateAmountMessage></RateAmountMessages>
  </OTA_HotelRateAmountNotifRQ></SOAP-ENV:Body></SOAP-ENV:Envelope>'''

                try:
                    _time.sleep(0.2)  # 200ms delay between pushes
                    resp = req_lib.post(
                        "https://hotel.tools/service/Medici%20new",
                        data=soap, headers={"Content-Type": "text/xml"}, timeout=10,
                    )
                    if resp.status_code == 200 and "Error" not in resp.text:
                        results["success"] += 1
                        results["details"].append({
                            "detail_id": detail_id, "hotel": item["hotel_name"],
                            "price": f"${original_price} → ${target_price}",
                            "zenith": "pushed",
                        })
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"{detail_id}: Zenith error {resp.status_code}")
                except Exception as exc:
                    results["failed"] += 1
                    results["errors"].append(f"{detail_id}: push error - {str(exc)[:80]}")
            else:
                results["db_only"] += 1
                results["details"].append({
                    "detail_id": detail_id, "hotel": item["hotel_name"],
                    "price": f"${original_price} → ${target_price}",
                    "zenith": "dry_run",
                })

    finally:
        conn.close()

    return {
        "action": "override_execute_bulk",
        "filter": {"signal": signal, "hotel_id": hotel_id, "category": category, "board": board, "min_T": min_T, "max_T": max_T, "discount_usd": discount_usd},
        "total_matched": len(candidates),
        "push_enabled": push_enabled,
        "results": results,
    }


# ── Insert Opportunity Endpoints ─────────────────────────────────────

@analytics_router.post("/opportunity/request")
@limiter.limit(RATE_LIMIT_DATA)
async def opportunity_request_single(
    request: Request,
    payload: OpportunityRequestBody,
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

    detail_id = payload.detail_id

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
            max_rooms=payload.max_rooms,
            signal=payload.signal,
            confidence=payload.confidence,
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
    payload: OpportunityBulkRequestBody,
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
    max_rooms = payload.max_rooms
    hotel_id_filter = payload.hotel_id

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
    payload: OpportunityCompletionBody,
    _api_key: str = Depends(_optional_api_key),
):
    """Report execution result — called by external insert-opp skill."""
    from src.analytics.opportunity_queue import mark_completed

    success = mark_completed(
        request_id,
        success=(payload.status == "done"),
        opp_id=payload.opp_id,
        error_message=payload.error_message,
    )
    if not success:
        raise HTTPException(404, f"Opportunity request {request_id} not found or already completed")
    return {"request_id": request_id, "status": payload.status}


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


# ── Macro Terminal helpers ────────────────────────────────────────────


def _get_signals_or_compute() -> list[dict]:
    """Get cached signals, or compute on-demand from analysis cache."""
    signals = _get_cached_signals()
    if signals:
        return signals
    analysis = _get_cached_analysis()
    if analysis and analysis.get("predictions"):
        try:
            from src.analytics.options_engine import compute_next_day_signals
            signals = compute_next_day_signals(analysis)
            _cm.set_data("signals", signals)
            logger.info("Macro: computed %d signals on-demand", len(signals))
            return signals
        except (ImportError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Macro: on-demand signal compute failed: %s", exc)
    return []


# ── Macro Terminal endpoints ──────────────────────────────────────────


@analytics_router.get("/macro/summary")
@limiter.limit(RATE_LIMIT_DATA)
async def macro_portfolio_summary(request: Request, _key=Depends(_optional_api_key)):
    """L1 Portfolio View — summary header + hotel heat map."""
    signals = _get_signals_or_compute()
    if not signals:
        raise HTTPException(503, "Signals not ready — cache warming up")

    from src.analytics.portfolio_aggregator import (
        build_portfolio_summary,
        build_hotel_heatmap,
    )

    greeks = None
    try:
        from src.analytics.portfolio_greeks import compute_portfolio_greeks
        analysis = _get_cached_analysis()
        if analysis:
            pg = compute_portfolio_greeks(analysis)
            greeks = {"total_theta": getattr(pg, "portfolio_theta", None)}
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        logger.debug("Greeks unavailable for macro summary: %s", exc)

    summary = build_portfolio_summary(signals, greeks=greeks)
    heatmap = build_hotel_heatmap(signals)

    return {
        "summary": summary.to_dict(),
        "heatmap": [r.to_dict() for r in heatmap],
    }


@analytics_router.get("/macro/hotel/{hotel_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def macro_hotel_drilldown(hotel_id: int, request: Request, _key=Depends(_optional_api_key)):
    """L2 Hotel Drill-down — T-distribution, source agreement, drop history, options list."""
    signals = _get_signals_or_compute()
    if not signals:
        raise HTTPException(503, "Signals not ready — cache warming up")

    analysis = _get_cached_analysis()
    predictions = analysis.get("predictions", {}) if analysis else {}

    from src.analytics.portfolio_aggregator import build_hotel_drilldown, compute_drop_history

    # Compute drop history from price snapshots
    drop_history = None
    try:
        from src.analytics.price_store import load_snapshots_for_hotel
        snapshots = load_snapshots_for_hotel(hotel_id)
        if not snapshots.empty:
            drop_history = compute_drop_history(snapshots, hotel_id)
    except (ImportError, OSError, ValueError) as exc:
        logger.debug("Drop history unavailable for hotel %d: %s", hotel_id, exc)

    drilldown = build_hotel_drilldown(signals, hotel_id, predictions=predictions, drop_history=drop_history)
    if drilldown is None:
        raise HTTPException(404, f"Hotel {hotel_id} not found in signals")

    return drilldown.to_dict()


@analytics_router.get("/macro/historical-t/{detail_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def macro_historical_t(detail_id: int, request: Request, _key=Depends(_optional_api_key)):
    """L3 Historical T chart — actual vs predicted price indexed by T."""
    import pandas as pd
    from src.analytics.price_store import load_price_history

    history = load_price_history(detail_id)
    if history.empty:
        raise HTTPException(404, f"No price history for detail_id={detail_id}")

    # Get check-in date from signals or analysis
    checkin_date = None
    signals = _get_signals_or_compute()
    if signals:
        match = next((s for s in signals if str(s.get("detail_id")) == str(detail_id)), None)
        if match:
            checkin_date = match.get("checkin_date")

    if not checkin_date:
        analysis = _get_cached_analysis()
        if analysis and "predictions" in analysis:
            pred = analysis["predictions"].get(str(detail_id))
            if pred:
                checkin_date = pred.get("date_from")

    if not checkin_date:
        raise HTTPException(404, f"Cannot determine check-in date for detail_id={detail_id}")

    checkin_dt = pd.to_datetime(checkin_date)
    actual_points = []
    for _, row in history.iterrows():
        scan_dt = pd.to_datetime(row["snapshot_ts"])
        t = (checkin_dt - scan_dt).days
        if t < 0:
            continue
        actual_points.append({
            "t": t,
            "price": round(float(row["room_price"]), 2),
            "date": scan_dt.strftime("%Y-%m-%d %H:%M"),
        })

    # Predicted series from forward curve
    predicted_points = []
    analysis = _get_cached_analysis()
    if analysis and "predictions" in analysis:
        pred = analysis["predictions"].get(str(detail_id))
        if pred and "forward_curve" in pred:
            for pt in pred["forward_curve"]:
                predicted_points.append({
                    "t": pt.get("t", 0),
                    "price": round(float(pt.get("predicted_price", 0)), 2),
                    "date": pt.get("date", ""),
                })

    return {
        "detail_id": detail_id,
        "checkin_date": checkin_date,
        "actual": sorted(actual_points, key=lambda p: -p["t"]),
        "predicted": sorted(predicted_points, key=lambda p: -p["t"]),
    }


@analytics_router.get("/macro/sources/{source}")
@limiter.limit(RATE_LIMIT_DATA)
async def macro_filtered_by_source(
    source: str, request: Request, _key=Depends(_optional_api_key),
):
    """Portfolio signals filtered by a specific source (forward_curve, historical, ml, ensemble)."""
    signals = _get_signals_or_compute()
    if not signals:
        raise HTTPException(503, "Signals not ready — cache warming up")

    analysis = _get_cached_analysis()
    predictions = analysis.get("predictions", {}) if analysis else {}

    from src.analytics.portfolio_aggregator import (
        filter_signals_by_source,
        build_portfolio_summary,
        build_hotel_heatmap,
    )

    filtered = filter_signals_by_source(signals, predictions, source)
    summary = build_portfolio_summary(filtered)
    heatmap = build_hotel_heatmap(filtered)

    return {
        "source": source,
        "summary": summary.to_dict(),
        "heatmap": [r.to_dict() for r in heatmap],
    }


@analytics_router.get("/macro/drop-history/{hotel_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def macro_drop_history(
    hotel_id: int,
    days: int = Query(7, ge=1, le=30),
    request: Request = None,
    _key=Depends(_optional_api_key),
):
    """Price drop history for a hotel from price snapshots."""
    from src.analytics.portfolio_aggregator import compute_drop_history
    from src.analytics.price_store import load_snapshots_for_hotel

    snapshots = load_snapshots_for_hotel(hotel_id)
    if snapshots.empty:
        raise HTTPException(404, f"No price snapshots for hotel {hotel_id}")

    result = compute_drop_history(snapshots, hotel_id, days=days)
    return result.to_dict()


# ──────────────────────────────────────────────────────────────────
#  Hotel Segments & Peer Comparison
# ──────────────────────────────────────────────────────────────────


@analytics_router.get("/signal/consensus/{detail_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def signal_consensus_detail(
    request: Request,
    detail_id: int,
    _api_key: str = Depends(_optional_api_key),
):
    """Full consensus signal breakdown — all 11 source votes for one option."""
    from src.analytics.consensus_signal import compute_consensus_signal
    from config.hotel_segments import get_hotel_segment, HOTEL_SEGMENTS

    analysis = _get_cached_analysis()
    if not analysis or not analysis.get("predictions"):
        raise HTTPException(503, "No analysis data")

    pred = analysis["predictions"].get(str(detail_id)) or analysis["predictions"].get(detail_id)
    if not pred:
        raise HTTPException(404, f"Detail {detail_id} not found")

    # Compute zone average
    zone_avg = 0.0
    hotel_id = int(pred.get("hotel_id", 0) or 0)
    seg = get_hotel_segment(hotel_id)
    if seg:
        zone = seg["zone"]
        zone_prices = []
        for _, other_pred in analysis["predictions"].items():
            other_hid = int(other_pred.get("hotel_id", 0) or 0)
            other_seg = HOTEL_SEGMENTS.get(other_hid, {})
            if other_seg.get("zone") == zone:
                cp = float(other_pred.get("current_price", 0) or 0)
                if cp > 0:
                    zone_prices.append(cp)
        if zone_prices:
            zone_avg = sum(zone_prices) / len(zone_prices)

    result = compute_consensus_signal(pred, zone_avg=zone_avg)
    result["segment"] = seg
    return result


@analytics_router.get("/hotel-segments")
@limiter.limit(RATE_LIMIT_DATA)
async def hotel_segments(
    request: Request,
    _key=Depends(_optional_api_key),
):
    """Return all hotel segment mappings (zone + tier)."""
    from config.hotel_segments import HOTEL_SEGMENTS, ZONES, TIERS
    return {"segments": HOTEL_SEGMENTS, "zones": ZONES, "tiers": TIERS}


@analytics_router.get("/hotel-peers/{hotel_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def hotel_peers(
    request: Request,
    hotel_id: int,
    _key=Depends(_optional_api_key),
):
    """Peer comparison for a hotel — same-zone peers with price stats."""
    from config.hotel_segments import get_hotel_segment, get_peer_hotels, HOTEL_SEGMENTS

    seg = get_hotel_segment(hotel_id)
    if not seg:
        return {"hotel_id": hotel_id, "segment": None, "peers": []}

    peer_ids = get_peer_hotels(hotel_id, same_zone=True, same_tier=False)

    # Get current prices for peers from cached analysis
    analysis = _get_cached_analysis()
    peer_data = []
    if analysis and analysis.get("predictions"):
        preds = analysis["predictions"]
        for pid in peer_ids:
            peer_prices = []
            for _key_id, pred in preds.items():
                if int(pred.get("hotel_id", 0)) == pid:
                    cp = float(pred.get("current_price", 0) or 0)
                    if cp > 0:
                        peer_prices.append(cp)
            if peer_prices:
                peer_data.append({
                    "hotel_id": pid,
                    "hotel_name": HOTEL_SEGMENTS.get(pid, {}).get("name", ""),
                    "tier": HOTEL_SEGMENTS.get(pid, {}).get("tier", ""),
                    "avg_price": round(sum(peer_prices) / len(peer_prices), 2),
                    "min_price": min(peer_prices),
                    "max_price": max(peer_prices),
                    "options_count": len(peer_prices),
                })

    zone_avg = round(sum(p["avg_price"] for p in peer_data) / len(peer_data), 2) if peer_data else None

    return {
        "hotel_id": hotel_id,
        "segment": seg,
        "peers": peer_data,
        "zone_avg": zone_avg,
    }
