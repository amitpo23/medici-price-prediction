"""SalesOffice Analytics Dashboard — live endpoints for price analysis.

Endpoints:
  GET /api/v1/salesoffice/home       — Consolidated landing page (HTML)
  GET /api/v1/salesoffice/dashboard  — Interactive HTML dashboard (Plotly)
  GET /api/v1/salesoffice/info       — System information & documentation (HTML)
  GET /api/v1/salesoffice/insights   — Price insights: up/down, below/above today (HTML)
  GET /api/v1/salesoffice/yoy        — Year-over-Year comparison: decay curve, calendar spread (HTML)
  GET /api/v1/salesoffice/options    — Options JSON API
  GET /api/v1/salesoffice/options/view   — Options HTML dashboard (browser) + interactive charts
  GET /api/v1/salesoffice/options/legend — Legend/semantics
  GET /api/v1/salesoffice/charts     — Chart Pack: contract path, term structure, opportunity stats (HTML)
  GET /api/v1/salesoffice/charts/contract-data — Contract path data (JSON, AJAX)
  GET /api/v1/salesoffice/accuracy   — Prediction accuracy tracker (HTML)
  GET /api/v1/salesoffice/providers  — Provider price comparison (HTML)
  GET /api/v1/salesoffice/alerts     — Price alert system (HTML)
  GET /api/v1/salesoffice/freshness  — Data freshness monitor (HTML)
  GET /api/v1/salesoffice/export/csv/contracts  — CSV export: contract prices
  GET /api/v1/salesoffice/export/csv/providers  — CSV export: provider data
  GET /api/v1/salesoffice/export/summary        — Weekly summary JSON/text
  GET /api/v1/salesoffice/data       — Raw analysis JSON
  GET /api/v1/salesoffice/simple     — Simplified human-readable JSON
  GET /api/v1/salesoffice/simple/text — Plain text report
  GET /api/v1/salesoffice/backtest   — Backtest prediction quality
  GET /api/v1/salesoffice/status     — Quick status check

Background:
  Hourly price collection from medici-db [SalesOffice.Details]
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/salesoffice", tags=["salesoffice-analytics"])

# Cache for latest analysis (avoid recomputing on every request)
_cache: dict = {}
_cache_lock = threading.Lock()
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_analysis_warming = threading.Event()  # set while background analysis is running

COLLECTION_INTERVAL = 3600  # 1 hour
_last_event_refresh_date: list[str] = [""]  # tracks date of last API event refresh

# YoY cache (separate — loaded on first /yoy request, 6-hour TTL)
_yoy_cache: dict = {}
_yoy_cache_ts: list[float] = [0.0]   # mutable container so inner function can update it
_yoy_loading: list[bool] = [False]   # guard against duplicate background loads
_YOY_CACHE_TTL = 6 * 3600           # 6 hours

# Options expiry cache (separate — 6-hour TTL)
_options_expiry_cache: dict = {}
_options_expiry_ts: list[float] = [0.0]
_options_loading: list[bool] = [False]
_OPTIONS_CACHE_TTL = 6 * 3600

# Charts cache (separate — 6-hour TTL)
_charts_cache: dict = {}
_charts_cache_ts: list[float] = [0.0]
_charts_loading: list[bool] = [False]
_CHARTS_CACHE_TTL = 6 * 3600

# Accuracy cache (separate — 6-hour TTL)
_accuracy_cache: dict = {}
_accuracy_cache_ts: list[float] = [0.0]
_accuracy_loading: list[bool] = [False]
_ACCURACY_CACHE_TTL = 6 * 3600

# Provider cache (separate — 6-hour TTL)
_provider_cache: dict = {}
_provider_cache_ts: list[float] = [0.0]
_provider_loading: list[bool] = [False]
_PROVIDER_CACHE_TTL = 6 * 3600


# ── Auth (reuse from integration) ────────────────────────────────────

def _optional_api_key(x_api_key: str = Header(default="")) -> str:
    from config.settings import PREDICTION_API_KEY
    if PREDICTION_API_KEY and x_api_key != PREDICTION_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def salesoffice_dashboard():
    """Full interactive HTML dashboard with Plotly charts.

    Open in browser for the visual report.
    """
    analysis = _get_cached_analysis()
    if analysis is None:
        return HTMLResponse(content=_loading_page(
            "Analytics Dashboard", "/api/v1/salesoffice/dashboard"
        ))
    html = _generate_html(analysis)
    return HTMLResponse(content=html)


@router.get("/data")
def salesoffice_data(
    _key: str = Depends(_optional_api_key),
):
    """Raw analysis data as JSON — for programmatic access."""
    analysis = _get_or_run_analysis()

    # Strip daily/forward_curve arrays (too verbose) — keep summaries + trading signals
    predictions = analysis.get("predictions", {})
    summary_predictions = {}
    for detail_id, pred in predictions.items():
        summary_predictions[detail_id] = {
            k: v for k, v in pred.items() if k not in ("daily", "forward_curve")
        }

    return JSONResponse(content={
        "run_ts": analysis.get("run_ts"),
        "total_snapshots": analysis.get("total_snapshots"),
        "model_info": analysis.get("model_info"),
        "statistics": analysis.get("statistics"),
        "hotels": analysis.get("hotels"),
        "predictions_summary": summary_predictions,
        "booking_window": analysis.get("booking_window"),
        "price_changes": analysis.get("price_changes"),
    })


@router.get("/simple")
def salesoffice_simple():
    """Simplified analysis — human-readable JSON with 4 clear sections.

    Returns: summary (text), predictions (per-room), attention (action items), market (stats).
    Easy to read, no trading jargon.
    """
    from src.analytics.simple_analysis import simplify_analysis

    analysis = _get_or_run_analysis()
    simplified = simplify_analysis(analysis)
    return JSONResponse(content=simplified)


@router.get("/simple/text", response_class=PlainTextResponse)
def salesoffice_simple_text():
    """Plain text analysis report — for quick reading in terminal or email."""
    from src.analytics.simple_analysis import simplify_to_text

    analysis = _get_or_run_analysis()
    text = simplify_to_text(analysis)
    return PlainTextResponse(content=text)


@router.get("/debug")
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
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@router.get("/flights/demand")
async def salesoffice_flights_demand():
    """Flight demand indicator for Miami — based on Kiwi.com data."""
    from src.analytics.flights_store import get_demand_summary, init_flights_db

    init_flights_db()
    summary = get_demand_summary("Miami")
    return JSONResponse(content=summary)


@router.get("/events")
async def salesoffice_events():
    """Events and conferences in Miami — demand indicators."""
    from src.analytics.events_store import init_events_db, seed_major_events, get_events_summary

    init_events_db()
    seed_major_events()
    summary = get_events_summary()
    return JSONResponse(content=summary)


@router.get("/data-sources")
async def salesoffice_data_sources():
    """Registry of all data sources (active + planned)."""
    from src.analytics.data_sources import get_sources_summary

    return JSONResponse(content=get_sources_summary())


@router.get("/benchmarks")
async def salesoffice_benchmarks():
    """Booking behavior benchmarks — seasonality, lead time, cancellation models."""
    from src.analytics.booking_benchmarks import get_benchmarks_summary

    return JSONResponse(content=get_benchmarks_summary())


@router.get("/forward-curve/{detail_id}")
def salesoffice_forward_curve(detail_id: int):
    """Full forward curve prediction for a specific room.

    Returns the decay curve walk with momentum, regime, and enrichments.
    """
    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    # detail_id might be int or str key
    pred = predictions.get(detail_id) or predictions.get(str(detail_id))
    if not pred:
        raise HTTPException(status_code=404, detail=f"Room {detail_id} not found in predictions")

    return JSONResponse(content={
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
        "forward_curve": pred.get("forward_curve", []),
        # Deep predictor enrichments
        "prediction_method": pred.get("prediction_method"),
        "signals": pred.get("signals"),
        "yoy_comparison": pred.get("yoy_comparison"),
        "explanation": pred.get("explanation"),
    })


@router.get("/options")
async def salesoffice_options(
    t_days: int | None = None,
    include_chart: bool = True,
    profile: str = "full",
    include_system_context: bool = True,
    _key: str = Depends(_optional_api_key),
):
    """Options-style row output with min/max path stats and source transparency.

    Query params:
      - t_days: optional horizon limit (analyze first T forecast days only)
      - include_chart: include embedded chart payload per row
            - profile: full (default) / lite
            - include_system_context: include top-level capability snapshot
    """
    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    profile_applied = (profile or "full").strip().lower()
    if profile_applied not in {"full", "lite"}:
        profile_applied = "full"

    effective_include_chart = include_chart
    if profile_applied == "lite":
        effective_include_chart = False

    rows: list[dict] = []
    for detail_id, pred in predictions.items():
        curve_points = _extract_curve_points(pred, t_days)
        path_prices = [p["predicted_price"] for p in curve_points]

        current_price = float(pred.get("current_price", 0) or 0)
        predicted_checkin = float(pred.get("predicted_checkin_price", current_price) or current_price)

        if path_prices:
            expected_min_price = min(path_prices)
            expected_max_price = max(path_prices)

            # Touches: count days price is within 2% of min/max band
            price_range = max(expected_max_price - expected_min_price, 1.0)
            touch_band = max(price_range * 0.10, 1.0)  # 10% of range, min $1
            touches_min = sum(1 for px in path_prices if abs(px - expected_min_price) <= touch_band)
            touches_max = sum(1 for px in path_prices if abs(px - expected_max_price) <= touch_band)

            # Count daily price drops vs rises in the forward curve path
            # gt_20: days with price DECLINE (negative daily change)
            # lte_20: days with price RISE or flat (positive daily change)
            changes_gt_20 = 0  # decline days
            changes_lte_20 = 0  # rise/flat days
            for i in range(1, len(path_prices)):
                prev_px = path_prices[i - 1]
                if prev_px > 0:
                    delta = path_prices[i] - prev_px
                    if delta < -0.001:  # price dropped
                        changes_gt_20 += 1
                    else:  # price rose or flat
                        changes_lte_20 += 1
        else:
            expected_min_price = predicted_checkin
            expected_max_price = predicted_checkin
            touches_min = 1
            touches_max = 1
            changes_gt_20 = 0
            changes_lte_20 = 0

        option_signal = _derive_option_signal(pred)
        sources = _extract_sources(pred, analysis)
        quality = _build_quality_summary(pred, sources)
        option_levels = _build_option_levels(pred, option_signal, quality)
        info = _build_info_badge(option_signal, quality, sources)
        put_path_insights = _build_put_path_insights(
            curve_points=curve_points,
            current_price=current_price,
            predicted_checkin=predicted_checkin,
            probability=pred.get("probability"),
        )

        row = {
            "detail_id": int(detail_id),
            "hotel_id": pred.get("hotel_id"),
            "hotel_name": pred.get("hotel_name"),
            "category": pred.get("category"),
            "board": pred.get("board"),
            "date_from": pred.get("date_from"),
            "days_to_checkin": pred.get("days_to_checkin"),
            "t_horizon_days": len(path_prices),
            "option_signal": option_signal,
            "current_price": round(current_price, 2),
            "predicted_checkin_price": round(predicted_checkin, 2),
            "expected_change_pct": round(float(pred.get("expected_change_pct", 0) or 0), 2),
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

        # Scan history — actual observed price behavior since tracking started
        scan = pred.get("scan_history") or {}
        row["scan_history"] = {
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
            "scan_price_series": scan.get("scan_price_series", []),
        }

        # Market benchmark — hotel vs same-star avg in same city
        bench = pred.get("market_benchmark") or {}
        row["market_benchmark"] = bench

        rows.append(row)

    rows.sort(
        key=lambda x: (
            0 if x["option_signal"] in ("CALL", "PUT") else 1,
            -abs(float(x.get("expected_change_pct", 0))),
        )
    )

    response_payload = {
        "run_ts": analysis.get("run_ts"),
        "total_rows": len(rows),
        "t_days_requested": t_days,
        "profile_applied": profile_applied,
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
        "rows": rows,
    }

    if include_system_context:
        response_payload["system_capabilities"] = _build_system_capabilities(analysis, total_rows=len(rows))

    return JSONResponse(content=response_payload)


@router.get("/options/legend")
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


@router.get("/options/view", response_class=HTMLResponse)
async def salesoffice_options_view(
    t_days: int | None = None,
    signal: str | None = None,
):
    """Interactive HTML dashboard for Call/Put options.

    Query params:
      - t_days: optional horizon limit
      - signal: filter by CALL / PUT / NEUTRAL (optional)

    Open in browser for the visual options board.
    """
    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    rows: list[dict] = []
    for detail_id, pred in predictions.items():
        curve_points = _extract_curve_points(pred, t_days)
        path_prices = [p["predicted_price"] for p in curve_points]

        current_price = float(pred.get("current_price", 0) or 0)
        predicted_checkin = float(pred.get("predicted_checkin_price", current_price) or current_price)

        if path_prices:
            expected_min_price = min(path_prices)
            expected_max_price = max(path_prices)

            # Touches: count days price is within 10% of min/max band
            price_range = max(expected_max_price - expected_min_price, 1.0)
            touch_band = max(price_range * 0.10, 1.0)
            touches_min = sum(1 for px in path_prices if abs(px - expected_min_price) <= touch_band)
            touches_max = sum(1 for px in path_prices if abs(px - expected_max_price) <= touch_band)

            # Count daily price drops vs rises in the forward curve path
            changes_gt_20 = 0  # decline days
            changes_lte_20 = 0  # rise/flat days
            for i in range(1, len(path_prices)):
                prev_px = path_prices[i - 1]
                if prev_px > 0:
                    delta = path_prices[i] - prev_px
                    if delta < -0.001:  # price dropped
                        changes_gt_20 += 1
                    else:  # price rose or flat
                        changes_lte_20 += 1
        else:
            expected_min_price = predicted_checkin
            expected_max_price = predicted_checkin
            touches_min = 1
            touches_max = 1
            changes_gt_20 = 0

        option_signal = _derive_option_signal(pred)
        sources = _extract_sources(pred, analysis)
        quality = _build_quality_summary(pred, sources)
        option_levels = _build_option_levels(pred, option_signal, quality)
        put_insights = _build_put_path_insights(
            curve_points, current_price, predicted_checkin,
            probability=pred.get("probability"),
        )
        scan = pred.get("scan_history") or {}

        rows.append({
            "detail_id": int(detail_id),
            "hotel_name": pred.get("hotel_name", ""),
            "category": pred.get("category", ""),
            "board": pred.get("board", ""),
            "date_from": pred.get("date_from", ""),
            "days_to_checkin": pred.get("days_to_checkin"),
            "option_signal": option_signal,
            "current_price": round(current_price, 2),
            "predicted_checkin_price": round(predicted_checkin, 2),
            "expected_change_pct": round(float(pred.get("expected_change_pct", 0) or 0), 2),
            "expected_min_price": round(float(expected_min_price), 2),
            "expected_max_price": round(float(expected_max_price), 2),
            "touches_min": touches_min,
            "touches_max": touches_max,
            "changes_gt_20": changes_gt_20,
            "quality_label": quality.get("label", ""),
            "quality_score": quality.get("score", 0),
            "level": option_levels.get("level_10", 0),
            "level_label": option_levels.get("label", ""),
            "sources_count": len(sources),
            "put_decline_count": put_insights.get("put_decline_count", 0),
            "put_total_decline": put_insights.get("put_total_decline_amount", 0),
            "put_largest_decline": put_insights.get("put_largest_single_decline", 0),
            "expected_future_drops": put_insights.get("expected_future_drops", 0),
            "expected_future_rises": put_insights.get("expected_future_rises", 0),
            "t_min_price": put_insights.get("t_min_price", 0),
            "t_max_price": put_insights.get("t_max_price", 0),
            "t_min_price_date": put_insights.get("t_min_price_date", ""),
            "t_max_price_date": put_insights.get("t_max_price_date", ""),
            # Scan history — actual
            "scan_snapshots": scan.get("scan_snapshots", 0),
            "first_scan_price": scan.get("first_scan_price"),
            "scan_price_change": scan.get("scan_price_change", 0),
            "scan_price_change_pct": scan.get("scan_price_change_pct", 0),
            "scan_actual_drops": scan.get("scan_actual_drops", 0),
            "scan_actual_rises": scan.get("scan_actual_rises", 0),
            "scan_total_drop_amount": scan.get("scan_total_drop_amount", 0),
            "scan_total_rise_amount": scan.get("scan_total_rise_amount", 0),
            "scan_trend": scan.get("scan_trend", "no_data"),
            "scan_price_series": scan.get("scan_price_series", []),
            "scan_max_single_drop": scan.get("scan_max_single_drop", 0),
            "scan_max_single_rise": scan.get("scan_max_single_rise", 0),
            "first_scan_date": scan.get("first_scan_date"),
            "latest_scan_date": scan.get("latest_scan_date"),
            "latest_scan_price": scan.get("latest_scan_price"),
            # Market benchmark — hotel vs same-star avg in same city
            "market_avg_price": (pred.get("market_benchmark") or {}).get("market_avg_price", 0),
            "market_pressure": (pred.get("market_benchmark") or {}).get("pressure", 0),
            "market_competitor_hotels": (pred.get("market_benchmark") or {}).get("competitor_hotels", 0),
            "market_city": (pred.get("market_benchmark") or {}).get("city", ""),
            "market_stars": (pred.get("market_benchmark") or {}).get("stars", 0),
        })

    rows.sort(key=lambda x: (
        0 if x["option_signal"] in ("CALL", "PUT") else 1,
        -abs(float(x.get("expected_change_pct", 0))),
    ))

    if signal:
        sig_upper = signal.strip().upper()
        if sig_upper in ("CALL", "PUT", "NEUTRAL"):
            rows = [r for r in rows if r["option_signal"] == sig_upper]

    html = _generate_options_html(rows, analysis, t_days)
    return HTMLResponse(content=html)


@router.get("/sources/audit")
async def salesoffice_sources_audit(
    _key: str = Depends(_optional_api_key),
):
    """Full runtime audit for all configured data sources."""
    analysis = _get_or_run_analysis()
    return JSONResponse(content=_build_sources_audit(analysis, summary_only=False))


@router.get("/backtest")
def salesoffice_backtest(
    _key: str = Depends(_optional_api_key),
):
    """Run walk-forward backtest on historical price data.

    Validates prediction quality by comparing forward curve predictions
    against actual outcomes. No data leakage — decay curve is rebuilt
    from prior-only data for each test point.

    Returns MAPE, RMSE per method, per hotel, per lead-time bucket.
    """
    from src.analytics.backtest import HistoricalBacktester

    try:
        backtester = HistoricalBacktester()
        results = backtester.run_backtest()
        return JSONResponse(content=results)
    except Exception as e:
        logger.error("Backtest failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "n_trials": 0},
        )


@router.get("/decay-curve")
def salesoffice_decay_curve():
    """The empirical decay curve term structure.

    Shows expected daily price change at each T (days to check-in),
    volatility surface, and category offsets.
    """
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


@router.get("/knowledge")
async def salesoffice_knowledge():
    """Hotel knowledge base — competitive landscape from TBO dataset."""
    from src.analytics.hotel_knowledge import get_knowledge_summary

    return JSONResponse(content=get_knowledge_summary())


@router.get("/knowledge/{hotel_id}")
async def salesoffice_hotel_profile(hotel_id: int):
    """Detailed profile for a specific SalesOffice hotel."""
    from src.analytics.hotel_knowledge import get_hotel_profile

    profile = get_hotel_profile(hotel_id)
    if "error" in profile:
        raise HTTPException(status_code=404, detail=profile["error"])
    return JSONResponse(content=profile)


@router.get("/info", response_class=HTMLResponse)
def salesoffice_info():
    """System information & documentation — how everything works."""
    from src.analytics.info_page import generate_info_html
    from src.analytics.data_sources import DATA_SOURCES

    # Try to get DB stats for the KPI section
    db_stats = None
    try:
        from src.data.trading_db import run_trading_query
        df = run_trading_query("""
            SELECT t.name AS table_name, p.rows AS row_count,
                   SUM(a.total_pages) * 8 / 1024 AS size_mb
            FROM sys.tables t
            INNER JOIN sys.indexes i ON t.object_id = i.object_id
            INNER JOIN sys.partitions p ON i.object_id = p.object_id
                AND i.index_id = p.index_id
            INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE i.index_id <= 1
            GROUP BY t.name, p.rows
        """)
        db_stats = {
            "total_tables": len(df),
            "total_rows": int(df["row_count"].sum()),
            "total_size_mb": int(df["size_mb"].sum()),
        }
    except Exception:
        pass

    html = generate_info_html(DATA_SOURCES, db_stats)
    return HTMLResponse(content=html)


@router.get("/insights", response_class=HTMLResponse)
async def salesoffice_insights():
    """Price insights — when prices go up/down, days below/above today."""
    from src.analytics.insights_page import generate_insights_html

    analysis = _get_cached_analysis()
    if analysis is None:
        return HTMLResponse(content=_loading_page(
            "Price Insights", "/api/v1/salesoffice/insights"
        ))
    html = generate_insights_html(analysis)
    return HTMLResponse(content=html)


@router.get("/yoy", response_class=HTMLResponse)
async def salesoffice_yoy():
    """Year-over-Year price comparison — decay curve by year, calendar spread, benchmarks."""
    import time
    from src.analytics.yoy_page import generate_yoy_html

    # Separate 6-hour cache for YoY data (heavy multi-year query)
    if _yoy_cache and (time.time() - _yoy_cache_ts[0]) < _YOY_CACHE_TTL:
        return HTMLResponse(content=generate_yoy_html(_yoy_cache))

    if _yoy_loading[0]:
        return HTMLResponse(content=_loading_page(
            "Year-over-Year Price Comparison", "/api/v1/salesoffice/yoy"
        ))

    # Trigger background load
    def _run_yoy():
        import time as _time
        from src.data.yoy_db import load_unified_yoy_data
        from src.analytics.yoy_analysis import (
            build_scan_timeseries,
            build_t_year_pivot,
            build_yoy_comparison,
            build_calendar_spread,
        )
        from src.analytics.term_structure_engine import build_all_term_structures
        _yoy_loading[0] = True
        try:
            HOTEL_IDS = [66814, 854881, 20702, 24982]
            raw = load_unified_yoy_data(HOTEL_IDS)
            if raw.empty:
                logger.warning("YoY: no data returned from DB")
                return
            ts = build_scan_timeseries(raw)
            ts_structures = build_all_term_structures(ts, HOTEL_IDS)
            result: dict = {}
            for hid in HOTEL_IDS:
                result[hid] = {
                    "pivot": build_t_year_pivot(ts, hid),
                    "comparison": build_yoy_comparison(ts, hid),
                    "spread": build_calendar_spread(ts, hid),
                    "term_structure": ts_structures.get(int(hid), {}),
                }
            _yoy_cache.update(result)
            _yoy_cache_ts[0] = _time.time()
            logger.info("YoY cache populated for %d hotels", len(result))
        except Exception as exc:
            logger.error("YoY background load failed: %s", exc, exc_info=True)
        finally:
            _yoy_loading[0] = False

    t = threading.Thread(target=_run_yoy, daemon=True)
    t.start()
    return HTMLResponse(content=_loading_page(
        "Year-over-Year Price Comparison", "/api/v1/salesoffice/yoy"
    ))


@router.get("/options", response_class=HTMLResponse)
async def salesoffice_options():
    """Options trading signals + 6-month expiry-relative analytics."""
    import time
    from src.analytics.options_page import generate_options_html

    # Section A needs existing analysis cache (non-blocking)
    analysis = _get_cached_analysis()
    if analysis is None:
        return HTMLResponse(content=_loading_page(
            "Options Trading Signals", "/api/v1/salesoffice/options"
        ))

    # Section B: separate 6h cache for historical expiry data
    expiry_data: dict = {}
    if _options_expiry_cache and (time.time() - _options_expiry_ts[0]) < _OPTIONS_CACHE_TTL:
        expiry_data = dict(_options_expiry_cache)
    elif not _options_loading[0]:
        def _run_options_expiry():
            import time as _t
            from src.data.yoy_db import load_unified_yoy_data
            from src.analytics.options_engine import build_expiry_metrics
            _options_loading[0] = True
            try:
                HOTEL_IDS = [66814, 854881, 20702, 24982]
                df = load_unified_yoy_data(HOTEL_IDS)
                if not df.empty:
                    summaries, rollups = build_expiry_metrics(df)
                    _options_expiry_cache.clear()
                    _options_expiry_cache.update({
                        "summaries": summaries.to_dict("records") if not summaries.empty else [],
                        "rollups": rollups,
                    })
                    _options_expiry_ts[0] = _t.time()
                    logger.info("Options expiry cache populated")
            except Exception as exc:
                logger.error("Options expiry load failed: %s", exc, exc_info=True)
            finally:
                _options_loading[0] = False

        threading.Thread(target=_run_options_expiry, daemon=True).start()

    html = generate_options_html(analysis, expiry_data)
    return HTMLResponse(content=html)


@router.get("/charts", response_class=HTMLResponse)
async def salesoffice_charts():
    """Chart Pack — 3-tab visual analysis: contract path, term structure, opportunity stats."""
    import time
    from src.analytics.charts_page import generate_charts_html

    # Separate 6-hour cache (same pattern as /yoy)
    if _charts_cache and (time.time() - _charts_cache_ts[0]) < _CHARTS_CACHE_TTL:
        return HTMLResponse(content=generate_charts_html(_charts_cache))

    if _charts_loading[0]:
        return HTMLResponse(content=_loading_page(
            "Chart Pack", "/api/v1/salesoffice/charts"
        ))

    # Trigger background load
    def _run_charts():
        import time as _time
        from src.analytics.charts_engine import build_charts_cache
        _charts_loading[0] = True
        try:
            HOTEL_IDS = [66814, 854881, 20702, 24982]
            result = build_charts_cache(HOTEL_IDS)
            if result:
                _charts_cache.update(result)
                _charts_cache_ts[0] = _time.time()
                logger.info("Charts cache populated")
        except Exception as exc:
            logger.error("Charts background load failed: %s", exc, exc_info=True)
        finally:
            _charts_loading[0] = False

    t = threading.Thread(target=_run_charts, daemon=True)
    t.start()
    return HTMLResponse(content=_loading_page(
        "Chart Pack", "/api/v1/salesoffice/charts"
    ))


@router.get("/charts/contract-data")
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
    except Exception as e:
        logger.error("Contract path failed: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Contract data query failed: {e}")


@router.get("/home", response_class=HTMLResponse)
async def salesoffice_home():
    """Consolidated landing page — hub linking to all analytics pages."""
    from src.analytics.landing_page import generate_landing_html

    status_data = None
    try:
        from src.analytics.price_store import get_snapshot_count, load_latest_snapshot, init_db
        init_db()
        latest = load_latest_snapshot()
        status_data = {
            "total_rooms": len(latest) if not latest.empty else 0,
            "total_hotels": latest["hotel_id"].nunique() if not latest.empty else 0,
            "snapshots_collected": get_snapshot_count(),
            "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        }
    except Exception:
        pass

    html = generate_landing_html(status_data)
    return HTMLResponse(content=html)


@router.get("/accuracy", response_class=HTMLResponse)
async def salesoffice_accuracy():
    """Prediction Accuracy Tracker — backtest predicted vs actual settlement prices."""
    import time
    from src.analytics.accuracy_page import generate_accuracy_html

    # Separate 6-hour cache
    if _accuracy_cache and (time.time() - _accuracy_cache_ts[0]) < _ACCURACY_CACHE_TTL:
        return HTMLResponse(content=generate_accuracy_html(_accuracy_cache))

    if _accuracy_loading[0]:
        return HTMLResponse(content=_loading_page(
            "Prediction Accuracy Tracker", "/api/v1/salesoffice/accuracy"
        ))

    def _run_accuracy():
        import time as _time
        from src.analytics.accuracy_engine import build_accuracy_data
        _accuracy_loading[0] = True
        try:
            result = build_accuracy_data()
            if result:
                _accuracy_cache.update(result)
                _accuracy_cache_ts[0] = _time.time()
                logger.info("Accuracy cache populated")
        except Exception as exc:
            logger.error("Accuracy background load failed: %s", exc, exc_info=True)
        finally:
            _accuracy_loading[0] = False

    threading.Thread(target=_run_accuracy, daemon=True).start()
    return HTMLResponse(content=_loading_page(
        "Prediction Accuracy Tracker", "/api/v1/salesoffice/accuracy"
    ))


@router.get("/providers", response_class=HTMLResponse)
async def salesoffice_providers():
    """Provider Price Comparison — 129 providers from 8.3M search results."""
    import time
    from src.analytics.provider_page import generate_provider_html

    # Separate 6-hour cache
    if _provider_cache and (time.time() - _provider_cache_ts[0]) < _PROVIDER_CACHE_TTL:
        return HTMLResponse(content=generate_provider_html(_provider_cache))

    if _provider_loading[0]:
        return HTMLResponse(content=_loading_page(
            "Provider Price Comparison", "/api/v1/salesoffice/providers"
        ))

    def _run_providers():
        import time as _time
        from src.analytics.provider_engine import build_provider_data
        _provider_loading[0] = True
        try:
            result = build_provider_data(days_back=90)
            if result:
                _provider_cache.update(result)
                _provider_cache_ts[0] = _time.time()
                logger.info("Provider cache populated")
        except Exception as exc:
            logger.error("Provider background load failed: %s", exc, exc_info=True)
        finally:
            _provider_loading[0] = False

    threading.Thread(target=_run_providers, daemon=True).start()
    return HTMLResponse(content=_loading_page(
        "Provider Price Comparison", "/api/v1/salesoffice/providers"
    ))


@router.get("/alerts", response_class=HTMLResponse)
async def salesoffice_alerts():
    """Price Alert System — breach threshold monitoring."""
    import time
    from src.analytics.alerts_page import generate_alerts_html

    # Alerts use the charts cache (Tab 3 data)
    if _charts_cache and (time.time() - _charts_cache_ts[0]) < _CHARTS_CACHE_TTL:
        return HTMLResponse(content=generate_alerts_html(_charts_cache))

    if _charts_loading[0]:
        return HTMLResponse(content=_loading_page(
            "Price Alert System", "/api/v1/salesoffice/alerts"
        ))

    # Trigger charts cache load if needed
    def _run_charts_for_alerts():
        import time as _time
        from src.analytics.charts_engine import build_charts_cache
        _charts_loading[0] = True
        try:
            HOTEL_IDS = [66814, 854881, 20702, 24982]
            result = build_charts_cache(HOTEL_IDS)
            if result:
                _charts_cache.update(result)
                _charts_cache_ts[0] = _time.time()
                logger.info("Charts cache populated (for alerts)")
        except Exception as exc:
            logger.error("Charts load for alerts failed: %s", exc, exc_info=True)
        finally:
            _charts_loading[0] = False

    threading.Thread(target=_run_charts_for_alerts, daemon=True).start()
    return HTMLResponse(content=_loading_page(
        "Price Alert System", "/api/v1/salesoffice/alerts"
    ))


@router.get("/freshness", response_class=HTMLResponse)
async def salesoffice_freshness():
    """Data Freshness Monitor — check all data source update times."""
    from src.analytics.freshness_engine import build_freshness_data
    from src.analytics.freshness_page import generate_freshness_html

    try:
        data = build_freshness_data()
        return HTMLResponse(content=generate_freshness_html(data))
    except Exception as e:
        logger.error("Freshness monitor failed: %s", e, exc_info=True)
        return HTMLResponse(content=_loading_page(
            "Data Freshness Monitor", "/api/v1/salesoffice/freshness"
        ))


@router.get("/export/csv/contracts")
def salesoffice_export_contracts():
    """CSV export of contract price history."""
    from src.analytics.export_engine import export_contracts_csv

    try:
        csv_data = export_contracts_csv()
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=medici_contracts.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Export failed: {e}")


@router.get("/export/csv/providers")
def salesoffice_export_providers():
    """CSV export of provider pricing data."""
    from src.analytics.export_engine import export_providers_csv

    try:
        csv_data = export_providers_csv()
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=medici_providers.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Export failed: {e}")


@router.get("/export/summary")
def salesoffice_export_summary(fmt: str = "json"):
    """Weekly summary digest — JSON or plain text. Use ?fmt=text for plain text."""
    from src.analytics.export_engine import generate_weekly_summary, generate_summary_text

    try:
        summary = generate_weekly_summary()
        if fmt == "text":
            text = generate_summary_text(summary)
            return PlainTextResponse(content=text)
        return JSONResponse(content=summary)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Summary generation failed: {e}")


@router.get("/status")
async def salesoffice_status():
    """Quick status — snapshot count, last run, rooms, hotels."""
    from src.analytics.price_store import get_snapshot_count, load_latest_snapshot, init_db

    init_db()
    snapshot_count = get_snapshot_count()
    latest = load_latest_snapshot()

    return {
        "status": "ok",
        "snapshots_collected": snapshot_count,
        "total_rooms": len(latest) if not latest.empty else 0,
        "total_hotels": latest["hotel_id"].nunique() if not latest.empty else 0,
        "last_analysis": _cache.get("run_ts"),
        "cache_ready": bool(_cache),
        "analysis_warming": _analysis_warming.is_set(),
        "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "collection_interval_seconds": COLLECTION_INTERVAL,
    }


# ── Market Data endpoints (new mega-tables) ──────────────────────────

@router.get("/market/search-data")
def market_search_data(hotel_id: int | None = None, days_back: int = 30):
    """AI Search Hotel Data — price history from 8.5M search records."""
    try:
        from src.data.trading_db import load_ai_search_data
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_ai_search_data(hotel_ids=hotel_ids, days_back=days_back)
        return {
            "source": "AI_Search_HotelData",
            "total_records": len(df),
            "hotels": df["HotelId"].nunique() if not df.empty else 0,
            "date_range": {
                "from": str(df["UpdatedAt"].min()) if not df.empty else None,
                "to": str(df["UpdatedAt"].max()) if not df.empty else None,
            },
            "records": df.to_dict(orient="records")[:500],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Market data query failed: {e}")


@router.get("/market/search-summary")
def market_search_summary(hotel_id: int | None = None):
    """Aggregated market pricing stats per hotel from AI search data."""
    try:
        from src.data.trading_db import load_ai_search_summary
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_ai_search_summary(hotel_ids=hotel_ids)
        return {
            "source": "AI_Search_HotelData",
            "total_hotels": len(df),
            "hotels": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Summary query failed: {e}")


@router.get("/market/search-results")
def market_search_results(hotel_id: int | None = None, days_back: int = 7):
    """Search Results Poll Log — net/gross prices, providers, room details."""
    try:
        from src.data.trading_db import load_search_results_summary
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_search_results_summary(hotel_ids=hotel_ids)
        return {
            "source": "SearchResultsSessionPollLog",
            "total_hotels": len(df),
            "hotels": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Search results query failed: {e}")


@router.get("/market/price-updates")
def market_price_updates(days_back: int = 30):
    """Room price change events — every price update tracked."""
    try:
        from src.data.trading_db import load_price_updates
        df = load_price_updates(days_back=days_back)
        return {
            "source": "RoomPriceUpdateLog",
            "total_updates": len(df),
            "unique_rooms": df["PreBookId"].nunique() if not df.empty else 0,
            "updates": df.to_dict(orient="records")[:500],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Price updates query failed: {e}")


@router.get("/market/price-velocity")
def market_price_velocity(hotel_id: int | None = None):
    """Price change velocity per hotel — how fast prices move."""
    try:
        from src.data.trading_db import load_price_update_velocity
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_price_update_velocity(hotel_ids=hotel_ids)
        # Replace NaN/NaT with None for JSON serialization
        df = df.where(df.notna(), None)
        records = df.to_dict(orient="records")
        # Convert datetime objects to strings
        for rec in records:
            for k, v in rec.items():
                if hasattr(v, "isoformat"):
                    rec[k] = v.isoformat()
        return {
            "source": "RoomPriceUpdateLog",
            "hotels": records,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Velocity query failed: {e}")


@router.get("/market/competitors/{hotel_id}")
def market_competitors(hotel_id: int, radius_km: float = 5.0,
                              stars: int | None = None):
    """Find competitor hotels within radius using geo coordinates."""
    try:
        from src.data.trading_db import load_competitor_hotels
        df = load_competitor_hotels(hotel_id, radius_km=radius_km, stars=stars)
        return {
            "hotel_id": hotel_id,
            "radius_km": radius_km,
            "total_competitors": len(df),
            "competitors": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Competitor query failed: {e}")


@router.get("/market/prebooks")
def market_prebooks(hotel_id: int | None = None, days_back: int = 90):
    """Pre-booking data with provider pricing and cancellation policies."""
    try:
        from src.data.trading_db import load_prebooks
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_prebooks(hotel_ids=hotel_ids, days_back=days_back)
        return {
            "source": "MED_PreBook",
            "total_prebooks": len(df),
            "prebooks": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Prebook query failed: {e}")


@router.get("/market/cancellations")
def market_cancellations(days_back: int = 365):
    """Booking cancellation history with reasons."""
    try:
        from src.data.trading_db import load_cancellations
        df = load_cancellations(days_back=days_back)
        return {
            "source": "MED_CancelBook",
            "total_cancellations": len(df),
            "cancellations": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cancellation query failed: {e}")


@router.get("/market/hotels-geo")
def market_hotels_geo():
    """Hotel metadata with lat/long, stars, country."""
    try:
        from src.data.trading_db import load_hotels_with_geo
        df = load_hotels_with_geo()
        return {
            "source": "Med_Hotels + Med_Hotels_instant",
            "total_hotels": len(df),
            "hotels": df.to_dict(orient="records")[:200],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Geo query failed: {e}")


@router.get("/market/weather")
async def market_weather():
    """Miami weather forecast + hurricane proximity status."""
    from src.analytics.miami_weather import get_weather_forecast, _check_hurricane_proximity
    return {
        "adjustments": get_weather_forecast(days=14),
        "hurricane_adj": _check_hurricane_proximity(),
    }


@router.get("/market/xotelo")
async def market_xotelo():
    """Competitor rates from Xotelo for all 4 Miami hotels."""
    from src.analytics.xotelo_store import get_rates_summary
    hotel_ids = [66814, 854881, 20702, 24982]
    return {str(hid): get_rates_summary(hid) for hid in hotel_ids}


@router.get("/market/fred")
async def market_fred():
    """FRED economic indicators for Miami hotel market context."""
    from src.analytics.fred_store import get_fred_indicators
    return get_fred_indicators()


@router.get("/market/kaggle-bookings")
async def market_kaggle_bookings():
    """Lead-time price curves + DOW premiums from Kaggle Hotel Booking Demand dataset (119K bookings)."""
    from src.analytics.kaggle_bookings import get_summary
    return get_summary()


@router.get("/market/makcorps")
async def market_makcorps():
    """Makcorps historical OTA price data for our 4 Miami hotels."""
    from src.analytics.makcorps_store import get_summary
    return get_summary()



@router.get("/market/db-overview")
def market_db_overview():
    """Full database overview — all tables with row counts."""
    try:
        from src.data.trading_db import run_trading_query
        df = run_trading_query("""
            SELECT t.name AS table_name, p.rows AS row_count,
                   SUM(a.total_pages) * 8 / 1024 AS size_mb
            FROM sys.tables t
            INNER JOIN sys.indexes i ON t.object_id = i.object_id
            INNER JOIN sys.partitions p ON i.object_id = p.object_id
                AND i.index_id = p.index_id
            INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE i.index_id <= 1
            GROUP BY t.name, p.rows
            ORDER BY p.rows DESC
        """)
        return {
            "total_tables": len(df),
            "total_rows": int(df["row_count"].sum()),
            "total_size_mb": int(df["size_mb"].sum()),
            "tables": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB overview failed: {e}")


# ── Background scheduler ─────────────────────────────────────────────

def start_salesoffice_scheduler() -> None:
    """Start hourly price collection in background thread."""
    global _scheduler_thread

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.info("SalesOffice scheduler already running")
        return

    _scheduler_stop.clear()

    def _loop():
        logger.info("SalesOffice price collector started (every %ds)", COLLECTION_INTERVAL)
        while not _scheduler_stop.is_set():
            _analysis_warming.set()
            try:
                _run_collection_cycle()
            except Exception as e:
                logger.error("SalesOffice collection cycle failed: %s", e, exc_info=True)
            finally:
                _analysis_warming.clear()
            _scheduler_stop.wait(COLLECTION_INTERVAL)
        logger.info("SalesOffice price collector stopped")

    _scheduler_thread = threading.Thread(target=_loop, daemon=True, name="salesoffice-collector")
    _scheduler_thread.start()


def stop_salesoffice_scheduler() -> None:
    """Stop the background scheduler."""
    _scheduler_stop.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=5)


# ── Internal helpers ──────────────────────────────────────────────────

def _run_collection_cycle() -> dict | None:
    """Collect prices and run analysis. Cache the result."""
    from src.analytics.collector import collect_prices
    from src.analytics.analyzer import run_analysis
    from src.analytics.price_store import init_db

    init_db()

    logger.info("SalesOffice: collecting prices...")
    df = collect_prices()
    if df.empty:
        logger.warning("SalesOffice: no data collected")
        return None

    logger.info("SalesOffice: collected %d rooms, running analysis...", len(df))
    analysis = run_analysis()

    with _cache_lock:
        _cache.update(analysis)

    logger.info(
        "SalesOffice: analysis complete — %d rooms, %d hotels",
        analysis.get("statistics", {}).get("total_rooms", 0),
        analysis.get("statistics", {}).get("total_hotels", 0),
    )

    # Daily refreshes — run once per calendar day (not every hour)
    from datetime import date as _date
    today_str = _date.today().isoformat()
    if _last_event_refresh_date[0] != today_str:
        _last_event_refresh_date[0] = today_str

        # Ticketmaster + SeatGeek events
        try:
            from src.analytics.miami_events_fetcher import refresh_api_events
            event_result = refresh_api_events(days_ahead=90)
            logger.info("API events refreshed: %s", event_result)
        except Exception as exc:
            logger.warning("Event API refresh failed: %s", exc)

        # Xotelo competitor rates (free, no key)
        try:
            from src.analytics.xotelo_store import fetch_rates
            hotel_ids = [66814, 854881, 20702, 24982]
            xotelo_total = sum(fetch_rates(hid, days_ahead=60) for hid in hotel_ids)
            logger.info("Xotelo competitor rates refreshed: %d records", xotelo_total)
        except Exception as exc:
            logger.warning("Xotelo refresh failed: %s", exc)

        # Makcorps historical prices (needs API key)
        try:
            from src.analytics.makcorps_store import fetch_historical_prices
            from config.settings import MAKCORPS_API_KEY
            if MAKCORPS_API_KEY:
                hotel_ids = [66814, 854881, 20702, 24982]
                mc_total = sum(fetch_historical_prices(hid) for hid in hotel_ids)
                logger.info("Makcorps historical prices refreshed: %d records", mc_total)
        except Exception as exc:
            logger.warning("Makcorps refresh failed: %s", exc)

    return analysis


def _get_cached_analysis() -> dict | None:
    """Return cached analysis or None — never blocks."""
    with _cache_lock:
        return dict(_cache) if _cache else None


def _get_or_run_analysis() -> dict:
    """Return cached analysis or signal that warmup is in progress.

    NEVER runs a synchronous collection cycle in the request path.
    The background scheduler (started at app boot) fills the cache.
    If the cache is still empty, return 503 so Azure gateway doesn't
    hit the 230-second timeout.
    """
    with _cache_lock:
        if _cache:
            return dict(_cache)

    # Cache is empty — check if background warmup is already running
    if _analysis_warming.is_set():
        raise HTTPException(
            status_code=503,
            detail="Analysis is warming up in background. Retry in 30-60 seconds.",
            headers={"Retry-After": "30"},
        )

    # Nobody is warming yet — kick off a background thread and return 503
    def _background_warm():
        _analysis_warming.set()
        try:
            _run_collection_cycle()
        except Exception as exc:
            logger.error("Background warmup failed: %s", exc, exc_info=True)
        finally:
            _analysis_warming.clear()

    threading.Thread(target=_background_warm, daemon=True, name="analysis-warmup").start()
    raise HTTPException(
        status_code=503,
        detail="Analysis cache is cold. Warmup started — retry in 60 seconds.",
        headers={"Retry-After": "60"},
    )


def _loading_page(title: str, redirect_url: str) -> str:
    """Return a self-refreshing loading page while analysis warms up."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="12;url={redirect_url}">
<title>{title} — Loading</title>
<style>
body{{background:#0f1117;color:#e4e7ec;font-family:'Inter',-apple-system,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}}
.box{{text-align:center;max-width:480px;padding:40px;}}
h1{{font-size:1.6em;background:linear-gradient(135deg,#c7d2fe,#818cf8);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px;}}
p{{color:#8b90a0;margin:8px 0;font-size:0.95em;}}
.spinner{{width:48px;height:48px;border:4px solid #2d3140;border-top-color:#818cf8;
border-radius:50%;animation:spin 1s linear infinite;margin:24px auto;}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}
.bar{{height:4px;background:#2d3140;border-radius:2px;margin:24px 0;overflow:hidden;}}
.bar-fill{{height:100%;width:40%;background:linear-gradient(90deg,#6366f1,#818cf8);
border-radius:2px;animation:slide 1.5s ease-in-out infinite;}}
@keyframes slide{{0%{{margin-left:-40%;}}100%{{margin-left:100%;}}}}
small{{color:#4b5563;font-size:0.8em;}}
</style>
</head>
<body>
<div class="box">
    <div class="spinner"></div>
    <h1>{title}</h1>
    <div class="bar"><div class="bar-fill"></div></div>
    <p>The analysis engine is running in the background.</p>
    <p>This page will refresh automatically in a few seconds.</p>
    <small>First run after deployment takes ~2 minutes to collect and analyze all room prices.</small>
</div>
<script>
// Also try to refresh every 12 seconds via JS
setTimeout(() => window.location.reload(), 12000);
</script>
</body>
</html>"""


def _generate_html(analysis: dict) -> str:
    """Generate the HTML dashboard from analysis results."""
    from src.analytics.report import generate_report
    from config.settings import DATA_DIR

    report_path = generate_report(analysis)

    # Read and return the HTML
    return report_path.read_text(encoding="utf-8")


def _generate_options_html(rows: list[dict], analysis: dict, t_days: int | None) -> str:
    """Generate a self-contained interactive HTML dashboard for options."""
    total = len(rows)
    calls = sum(1 for r in rows if r["option_signal"] == "CALL")
    puts = sum(1 for r in rows if r["option_signal"] == "PUT")
    neutrals = total - calls - puts
    run_ts = analysis.get("run_ts", "")

    # Build table rows HTML
    table_rows = []
    for r in rows:
        sig = r["option_signal"]
        chg = r["expected_change_pct"]
        lvl = r["level"]

        if sig == "CALL":
            sig_cls = "sig-call"
            sig_badge = f'<span class="badge badge-call">CALL L{lvl}</span>'
        elif sig == "PUT":
            sig_cls = "sig-put"
            sig_badge = f'<span class="badge badge-put">PUT L{lvl}</span>'
        else:
            sig_cls = "sig-neutral"
            sig_badge = '<span class="badge badge-neutral">NEUTRAL</span>'

        chg_cls = "pct-up" if chg > 0 else ("pct-down" if chg < 0 else "")
        chg_arrow = "&#9650;" if chg > 0 else ("&#9660;" if chg < 0 else "")

        q_score = r["quality_score"]
        q_cls = "q-high" if q_score >= 0.75 else ("q-med" if q_score >= 0.5 else "q-low")

        put_info = ""
        exp_drops = r.get("expected_future_drops", 0)
        if r["put_decline_count"] > 0:
            put_info = (
                f'{r["put_decline_count"]} drops, '
                f'total ${r["put_total_decline"]:.0f}, '
                f'max ${r["put_largest_decline"]:.0f}'
            )
        elif exp_drops > 0:
            put_info = f'~{exp_drops:.0f} expected drops (prob-based)'

        # Scan history cells
        s_snaps = r.get("scan_snapshots", 0)
        s_drops = r.get("scan_actual_drops", 0)
        s_rises = r.get("scan_actual_rises", 0)
        s_chg = r.get("scan_price_change", 0)
        s_chg_pct = r.get("scan_price_change_pct", 0)
        s_first = r.get("first_scan_price")
        s_latest = r.get("latest_scan_price")
        s_trend = r.get("scan_trend", "no_data")
        s_total_drop = r.get("scan_total_drop_amount", 0)
        s_total_rise = r.get("scan_total_rise_amount", 0)
        s_max_drop = r.get("scan_max_single_drop", 0)
        s_max_rise = r.get("scan_max_single_rise", 0)
        s_first_date = r.get("first_scan_date") or ""
        s_latest_date = r.get("latest_scan_date") or ""

        scan_chg_cls = "pct-up" if s_chg > 0 else ("pct-down" if s_chg < 0 else "")
        scan_chg_arrow = "&#9650;" if s_chg > 0.5 else ("&#9660;" if s_chg < -0.5 else "")
        scan_first_str = f"${s_first:,.0f}" if s_first else "-"

        # Rich Actual D/R: colored pill with drop/rise counts
        if s_snaps > 1:
            dr_title = (
                f"Since {s_first_date[:10]}: "
                f"{s_drops} drops (total ${s_total_drop:.0f}, max ${s_max_drop:.0f}) | "
                f"{s_rises} rises (total ${s_total_rise:.0f}, max ${s_max_rise:.0f})"
            )
            drop_part = f'<span class="scan-drop">{s_drops}&#9660;</span>' if s_drops else '<span class="scan-zero">0&#9660;</span>'
            rise_part = f'<span class="scan-rise">{s_rises}&#9650;</span>' if s_rises else '<span class="scan-zero">0&#9650;</span>'
            scan_hist_str = f'<span class="scan-dr" title="{dr_title}">{drop_part} {rise_part}</span>'
        else:
            scan_hist_str = '<span class="scan-nodata">-</span>'

        # Scan trend badge
        if s_trend == "down":
            trend_badge = '<span class="trend-badge trend-down">&#9660;</span>'
        elif s_trend == "up":
            trend_badge = '<span class="trend-badge trend-up">&#9650;</span>'
        elif s_trend == "stable":
            trend_badge = '<span class="trend-badge trend-stable">&#9644;</span>'
        else:
            trend_badge = ''

        # Chart icon — only show if we have >1 scan
        scan_series = r.get("scan_price_series", [])
        if len(scan_series) > 1:
            series_json = json.dumps(scan_series).replace("'", "&#39;")
            esc_hotel = _html_escape(json.dumps(r["hotel_name"]))
            det_id = r["detail_id"]
            chart_icon = (
                f'<button class="chart-btn" title="View scan price chart" '
                f"onclick='showChart({det_id}, "
                f"{esc_hotel}, "
                f"this.dataset.series)' "
                f"data-series='{series_json}'>"
                f'&#128200;</button>'
            )
        else:
            chart_icon = '<span class="chart-btn-empty" title="Not enough scan data">-</span>'

        # Market benchmark cell (hotel vs same-star avg in same city)
        mkt_avg = r.get("market_avg_price", 0)
        mkt_pressure = r.get("market_pressure", 0)
        mkt_hotels = r.get("market_competitor_hotels", 0)
        mkt_city = r.get("market_city", "")
        mkt_stars = r.get("market_stars", 0)
        if mkt_avg and mkt_avg > 0:
            mkt_cls = "pct-up" if r["current_price"] < mkt_avg else ("pct-down" if r["current_price"] > mkt_avg else "")
            mkt_pct = (r["current_price"] - mkt_avg) / mkt_avg * 100
            mkt_arrow = "&#9660;" if mkt_pct < -1 else ("&#9650;" if mkt_pct > 1 else "")
            mkt_title = (
                f"{mkt_city} {mkt_stars}★ avg: ${mkt_avg:,.0f} | "
                f"{mkt_hotels} competitor hotels | "
                f"You are {mkt_pct:+.1f}% vs market"
            )
            mkt_str = f'{mkt_arrow} ${mkt_avg:,.0f} <small>({mkt_pct:+.0f}%)</small>'
        else:
            mkt_cls = ""
            mkt_title = "No market data for this hotel's city/star combo"
            mkt_str = "-"

        table_rows.append(
            f'<tr class="{sig_cls}" '
            f'data-signal="{sig}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-change="{chg}">'
            f'<td class="col-id">{r["detail_id"]}</td>'
            f'<td class="col-hotel" title="{_html_escape(r["hotel_name"])}">{_html_escape(r["hotel_name"][:30])}</td>'
            f'<td>{_html_escape(r["category"])}</td>'
            f'<td>{_html_escape(r["board"])}</td>'
            f'<td>{_html_escape(str(r["date_from"] or ""))}</td>'
            f'<td class="num">{r["days_to_checkin"] or ""}</td>'
            f'<td>{sig_badge}</td>'
            f'<td class="num">${r["current_price"]:,.2f}</td>'
            f'<td class="num">${r["predicted_checkin_price"]:,.2f}</td>'
            f'<td class="num {chg_cls}">{chg_arrow} {chg:+.1f}%</td>'
            f'<td class="num">${r["expected_min_price"]:,.2f}</td>'
            f'<td class="num">${r["expected_max_price"]:,.2f}</td>'
            f'<td class="num">{r["touches_min"]}/{r["touches_max"]}</td>'
            f'<td class="num">{r["changes_gt_20"]}</td>'
            f'<td class="num">{r["put_decline_count"]}</td>'
            f'<td><span class="q-dot {q_cls}" title="{r["quality_label"]} ({q_score:.2f})">' 
            f'{r["quality_label"]}</span></td>'
            f'<td class="num">{s_snaps}</td>'
            f'<td class="num">{scan_first_str}</td>'
            f'<td class="scan-col">{scan_hist_str}</td>'
            f'<td class="num {scan_chg_cls}" title="drop ${s_total_drop:.0f} / rise ${s_total_rise:.0f}">{trend_badge} {scan_chg_arrow} {s_chg_pct:+.1f}%</td>'
            f'<td class="col-chart">{chart_icon}</td>'
            f'<td class="col-put">{put_info}</td>'
            f'<td class="num {mkt_cls}" title="{mkt_title}">{mkt_str}</td>'
            f'</tr>'
        )

    rows_html = "\n".join(table_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SalesOffice Options Dashboard</title>
<style>
  :root {{
    --call: #16a34a; --call-bg: #dcfce7; --call-row: #f0fdf4;
    --put: #dc2626; --put-bg: #fee2e2; --put-row: #fef2f2;
    --neutral: #6b7280; --neutral-bg: #f3f4f6;
    --border: #e5e7eb; --header-bg: #1e293b; --header-fg: #f8fafc;
    --bg: #f8fafc; --card-bg: #fff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: #1e293b; font-size: 13px; }}

  .top-bar {{ background: var(--header-bg); color: var(--header-fg);
              padding: 14px 24px; display: flex; justify-content: space-between;
              align-items: center; }}
  .top-bar h1 {{ font-size: 18px; font-weight: 600; }}
  .top-bar .ts {{ font-size: 11px; opacity: 0.7; }}

  .cards {{ display: flex; gap: 14px; padding: 18px 24px; flex-wrap: wrap; }}
  .card {{ background: var(--card-bg); border-radius: 10px; padding: 16px 22px;
           min-width: 140px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
           border-left: 4px solid var(--border); }}
  .card.c-total {{ border-left-color: #3b82f6; }}
  .card.c-call  {{ border-left-color: var(--call); }}
  .card.c-put   {{ border-left-color: var(--put); }}
  .card.c-neut  {{ border-left-color: var(--neutral); }}
  .card .num-big {{ font-size: 28px; font-weight: 700; }}
  .card .label {{ font-size: 11px; text-transform: uppercase; color: #64748b;
                  margin-top: 2px; letter-spacing: 0.5px; }}

  .controls {{ padding: 8px 24px 12px; display: flex; gap: 10px; flex-wrap: wrap;
               align-items: center; }}
  .controls input, .controls select {{ padding: 7px 12px; border: 1px solid var(--border);
    border-radius: 6px; font-size: 13px; background: #fff; }}
  .controls input {{ width: 260px; }}
  .controls select {{ min-width: 110px; }}
  .controls label {{ font-size: 12px; color: #64748b; margin-right: 2px; }}

  .table-wrap {{ overflow-x: auto; padding: 0 24px 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  thead {{ background: #f1f5f9; position: sticky; top: 0; z-index: 2; }}
  th {{ padding: 10px 10px; text-align: left; font-weight: 600; font-size: 11px;
       text-transform: uppercase; letter-spacing: .4px; color: #475569;
       border-bottom: 2px solid var(--border); cursor: pointer; white-space: nowrap;
       user-select: none; }}
  th:hover {{ background: #e2e8f0; }}
  th .arrow {{ font-size: 10px; margin-left: 3px; opacity: .4; }}
  th.sorted .arrow {{ opacity: 1; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  tr:hover {{ background: #f1f5f9; }}
  tr.sig-call {{ background: var(--call-row); }}
  tr.sig-put  {{ background: var(--put-row); }}

  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}

  .badge {{ display: inline-block; padding: 3px 9px; border-radius: 12px;
            font-size: 11px; font-weight: 600; letter-spacing: .3px; }}
  .badge-call    {{ background: var(--call-bg); color: var(--call); }}
  .badge-put     {{ background: var(--put-bg);  color: var(--put); }}
  .badge-neutral {{ background: var(--neutral-bg); color: var(--neutral); }}

  .pct-up   {{ color: var(--call); font-weight: 600; }}
  .pct-down {{ color: var(--put);  font-weight: 600; }}

  .q-dot {{ padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 600; }}
  .q-high {{ background: #dcfce7; color: #15803d; }}
  .q-med  {{ background: #fef9c3; color: #a16207; }}
  .q-low  {{ background: #fee2e2; color: #b91c1c; }}

  .col-hotel {{ max-width: 180px; overflow: hidden; text-overflow: ellipsis; }}
  .col-put {{ font-size: 11px; color: #64748b; max-width: 200px;
              overflow: hidden; text-overflow: ellipsis; }}
  .col-id {{ color: #94a3b8; font-size: 11px; }}
  .scan-col {{ font-size: 11px; }}

  .scan-dr {{ display: inline-flex; gap: 6px; align-items: center; }}
  .scan-drop {{ color: var(--put); font-weight: 700; font-size: 12px; }}
  .scan-rise {{ color: var(--call); font-weight: 700; font-size: 12px; }}
  .scan-zero {{ color: #94a3b8; font-size: 12px; }}
  .scan-nodata {{ color: #cbd5e1; }}

  .trend-badge {{ display: inline-block; font-size: 10px; margin-right: 2px; }}
  .trend-down {{ color: var(--put); }}
  .trend-up {{ color: var(--call); }}
  .trend-stable {{ color: #94a3b8; }}

  .chart-btn {{ background: none; border: 1px solid var(--border); border-radius: 5px;
                cursor: pointer; font-size: 14px; padding: 2px 6px; line-height: 1;
                transition: background .15s; }}
  .chart-btn:hover {{ background: #e2e8f0; }}
  .chart-btn-empty {{ color: #cbd5e1; font-size: 12px; }}
  .col-chart {{ text-align: center; }}

  /* Modal overlay */
  .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,.45); z-index: 100; justify-content: center;
                    align-items: center; }}
  .modal-overlay.open {{ display: flex; }}
  .modal-box {{ background: #fff; border-radius: 12px; padding: 24px; width: 680px;
                max-width: 95vw; max-height: 90vh; overflow-y: auto;
                box-shadow: 0 8px 32px rgba(0,0,0,.25); position: relative; }}
  .modal-close {{ position: absolute; top: 12px; right: 16px; font-size: 20px;
                  cursor: pointer; color: #64748b; background: none; border: none; }}
  .modal-close:hover {{ color: #1e293b; }}
  .modal-title {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; color: #1e293b; }}
  .modal-subtitle {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
  .modal-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
  .modal-stat {{ background: #f1f5f9; border-radius: 8px; padding: 10px 14px; min-width: 90px; }}
  .modal-stat .val {{ font-size: 20px; font-weight: 700; }}
  .modal-stat .lbl {{ font-size: 10px; text-transform: uppercase; color: #64748b; }}
  .modal-stat.drop .val {{ color: var(--put); }}
  .modal-stat.rise .val {{ color: var(--call); }}

  .footer {{ text-align: center; padding: 18px; font-size: 11px; color: #94a3b8; }}

  /* ── Info-icon tooltips ─────────────────────────────────────── */
  .info-icon {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 14px; height: 14px; border-radius: 50%; background: #94a3b8;
    color: #fff; font-size: 9px; font-weight: 700; font-style: normal;
    margin-left: 4px; cursor: help; position: relative; vertical-align: middle;
    flex-shrink: 0; line-height: 1;
  }}
  .info-icon:hover {{ background: #3b82f6; }}
  .info-tip {{
    display: none; position: absolute; bottom: calc(100% + 8px); left: 50%;
    transform: translateX(-50%); width: 290px; padding: 10px 12px;
    background: #1e293b; color: #f1f5f9; font-size: 11px; font-weight: 400;
    line-height: 1.45; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.3);
    z-index: 200; text-transform: none; letter-spacing: 0; white-space: normal;
    pointer-events: none;
  }}
  .info-tip::after {{
    content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    border: 6px solid transparent; border-top-color: #1e293b;
  }}
  .info-icon:hover .info-tip {{ display: block; }}
  /* Right-edge tooltips: shift left so they don't overflow */
  th:nth-child(n+16) .info-tip {{ left: auto; right: 0; transform: none; }}
  th:nth-child(n+16) .info-tip::after {{ left: auto; right: 12px; transform: none; }}
  .info-tip b {{ color: #93c5fd; }}
  .info-tip .src-tag {{ display: inline-block; background: #334155; padding: 1px 5px;
    border-radius: 3px; font-size: 10px; margin: 2px 2px 0 0; }}

  @media (max-width: 900px) {{
    .cards {{ padding: 12px; gap: 8px; }}
    .controls {{ padding: 8px 12px; }}
    .table-wrap {{ padding: 0 8px 16px; }}
    .controls input {{ width: 100%; }}
    .info-tip {{ width: 220px; }}
  }}
</style>
</head>
<body>

<div class="top-bar">
  <h1>SalesOffice &mdash; Options Board</h1>
  <span class="ts">Last run: {_html_escape(str(run_ts))}</span>
</div>

<div class="cards">
  <div class="card c-total"><div class="num-big">{total}</div><div class="label">Total Options</div></div>
  <div class="card c-call"><div class="num-big">{calls}</div><div class="label">CALL</div></div>
  <div class="card c-put"><div class="num-big">{puts}</div><div class="label">PUT</div></div>
  <div class="card c-neut"><div class="num-big">{neutrals}</div><div class="label">Neutral</div></div>
</div>

<div class="controls">
  <label for="search">Search:</label>
  <input id="search" type="text" placeholder="Filter by hotel name, category...">
  <label for="sig-filter">Signal:</label>
  <select id="sig-filter">
    <option value="">All</option>
    <option value="CALL">CALL</option>
    <option value="PUT">PUT</option>
    <option value="NEUTRAL">NEUTRAL</option>
  </select>
  <label for="q-filter">Quality:</label>
  <select id="q-filter">
    <option value="">All</option>
    <option value="HIGH">HIGH</option>
    <option value="MEDIUM">MEDIUM</option>
    <option value="LOW">LOW</option>
  </select>
</div>

<div class="table-wrap">
<table id="opts-table">
<thead><tr>
  <th data-col="0" data-type="num">ID<span class="info-icon">i<span class="info-tip"><b>Detail ID</b><br>Unique room identifier from SalesOffice DB.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="1" data-type="str">Hotel<span class="info-icon">i<span class="info-tip"><b>Hotel Name</b><br>Property name from Med_Hotels table joined via HotelID.<br><span class="src-tag">Med_Hotels</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="2" data-type="str">Category<span class="info-icon">i<span class="info-tip"><b>Room Category</b><br>Mapped from RoomCategoryID: 1=Standard, 2=Superior, 4=Deluxe, 12=Suite. Affects forward-curve category offset in prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="3" data-type="str">Board<span class="info-icon">i<span class="info-tip"><b>Board Type</b><br>Meal plan from BoardId: RO, BB, HB, FB, AI, etc. Adds a board offset to the forward curve prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="4" data-type="str">Check-in<span class="info-icon">i<span class="info-tip"><b>Check-in Date</b><br>Booked arrival date from the order. This is the target date (T=0) for the forward curve walk.<br><span class="src-tag">SalesOffice.Orders</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="5" data-type="num">Days<span class="info-icon">i<span class="info-tip"><b>Days to Check-in</b><br>Calendar days from today to check-in. This is the T value &mdash; how many steps the forward curve walks.<br>Formula: <b>check_in_date &minus; today</b></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="6" data-type="str">Signal<span class="info-icon">i<span class="info-tip"><b>Option Signal (CALL / PUT / NEUTRAL)</b><br>&bull; <b>CALL</b>: price expected to rise (&ge;0.5%) or prob_up &gt; prob_down+0.1<br>&bull; <b>PUT</b>: price expected to drop (&le;&minus;0.5%) or prob_down &gt; prob_up+0.1<br>&bull; <b>L1-L10</b>: confidence level (65% change magnitude + 35% probability &times; quality)<br><span class="src-tag">Forward Curve 50%</span> <span class="src-tag">Historical 30%</span> <span class="src-tag">ML 20%</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="7" data-type="num">Current $<span class="info-icon">i<span class="info-tip"><b>Current Room Price</b><br>Latest price from the most recent hourly scan of SalesOffice.Details. This is the starting point for the forward curve.<br><span class="src-tag">SalesOffice.Details</span> <span class="src-tag">Hourly scan</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="8" data-type="num">Predicted $<span class="info-icon">i<span class="info-tip"><b>Predicted Check-in Price</b><br>Weighted ensemble of 2-3 signals:<br>&bull; <b>Forward Curve (50%)</b>: day-by-day walk with decay + events + season + weather adjustments<br>&bull; <b>Historical Pattern (30%)</b>: same-month prior-year average + lead-time adjustment<br>&bull; <b>ML Model (20%)</b>: if trained model exists (currently inactive)<br>Weights are scaled by each signal's confidence then normalized.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Open-Meteo</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="9" data-type="num">Change %<span class="info-icon">i<span class="info-tip"><b>Expected Price Change %</b><br>Percentage difference between predicted check-in price and current price.<br>Formula: <b>(predicted &divide; current &minus; 1) &times; 100</b><br>Green = price expected to rise, Red = expected to drop.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="10" data-type="num">Min $<span class="info-icon">i<span class="info-tip"><b>Expected Minimum Price</b><br>Lowest price point on the forward curve between now and check-in.<br>Formula: <b>min(all daily predicted prices)</b><br>This is the predicted best buying opportunity in the path.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="11" data-type="num">Max $<span class="info-icon">i<span class="info-tip"><b>Expected Maximum Price</b><br>Highest price point on the forward curve between now and check-in.<br>Formula: <b>max(all daily predicted prices)</b><br>Peak predicted price before check-in.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="12" data-type="str">Touches<span class="info-icon">i<span class="info-tip"><b>Touches Min / Max</b><br>How many times the forward curve touches the min and max price levels (within $0.01).<br>Format: <b>min_touches / max_touches</b><br>High touch count = price lingers at that level (support/resistance).</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="13" data-type="num">Big Moves<span class="info-icon">i<span class="info-tip"><b>Big Price Moves (&gt;$20)</b><br>Count of day-to-day predicted price changes greater than $20 on the forward curve.<br>More big moves = higher volatility expected.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="14" data-type="num">Exp Drops<span class="info-icon">i<span class="info-tip"><b>Expected Price Drops</b><br>Number of day-to-day drops predicted by the forward curve between now and check-in.<br>Higher count for PUT signals = more predicted decline episodes.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="15" data-type="str">Quality<span class="info-icon">i<span class="info-tip"><b>Prediction Quality Score</b><br>Blended confidence metric:<br>&bull; 60% from data availability (scan count, price history depth, hotel coverage)<br>&bull; 40% from mean signal confidence<br>Levels: <b>HIGH</b> (&ge;0.75), <b>MEDIUM</b> (&ge;0.50), <b>LOW</b> (&lt;0.50)<br>Higher = more data backing the prediction.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="16" data-type="num">Scans<span class="info-icon">i<span class="info-tip"><b>Scan Count (Actual)</b><br>Number of real price snapshots collected from medici-db since tracking started (Feb 23).<br>Scanned every ~3 hours. More scans = better trend visibility.<br><span class="src-tag">SalesOffice.Details.DateCreated</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="17" data-type="num">1st Price<span class="info-icon">i<span class="info-tip"><b>First Scan Price</b><br>The room price at the earliest recorded scan. Used as baseline to measure actual price movement since tracking began.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="18" data-type="str">Actual D/R<span class="info-icon">i<span class="info-tip"><b>Actual Drops / Rises (Observed)</b><br>Real price drops and rises observed across actual scans &mdash; NOT predictions.<br>&bull; <b style="color:#ef4444">Red number&#9660;</b> = count of scans where price decreased<br>&bull; <b style="color:#22c55e">Green number&#9650;</b> = count of scans where price increased<br>Hover for total $ amounts and max single move.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="19" data-type="num">Scan Chg%<span class="info-icon">i<span class="info-tip"><b>Scan Price Change %</b><br>Actual price change from first scan to current price.<br>Formula: <b>(latest &minus; first) &divide; first &times; 100</b><br>Trend badge: &#9650; up, &#9660; down, &#9644; stable.<br>This is REAL observed data, not a prediction.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="20" data-type="str">Chart<span class="info-icon">i<span class="info-tip"><b>Scan Price Chart</b><br>Click &#128200; to view price history chart showing all actual scan prices over time with colored dots (red=drop, green=rise).<br>Requires &ge;2 scans.</span></span></th>
  <th data-col="21" data-type="str">PUT Detail<span class="info-icon">i<span class="info-tip"><b>PUT Decline Details</b><br>Breakdown of predicted downward moves on the forward curve:<br>&bull; <b>drops</b>: count of decline days<br>&bull; <b>total $</b>: sum of all daily drops<br>&bull; <b>max $</b>: largest single-day drop<br>Only shown for rooms with predicted declines.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="22" data-type="num">Mkt &#9733;$<span class="info-icon">i<span class="info-tip"><b>Market Benchmark (same &#9733; avg)</b><br>Average price of all other hotels with the <b>same star rating</b> in the <b>same city</b> from AI_Search_HotelData (8.5M records, 6K+ hotels, 323 cities).<br>&bull; <b style="color:#22c55e">Green</b>: our price &lt; market avg (well-positioned)<br>&bull; <b style="color:#ef4444">Red</b>: our price &gt; market avg (premium priced)<br>Hover for N competitor hotels and city.<br><span class="src-tag">AI_Search_HotelData</span></span></span> <span class="arrow">&#9650;</span></th>
</tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="footer">
  Medici Price Prediction &mdash; Options Dashboard
  &bull; {total} rows
  &bull; T={t_days or "all"} days
  &bull; <a href="/api/v1/salesoffice/options?profile=lite" style="color:#3b82f6">JSON API</a>
  &bull; <a href="/api/v1/salesoffice/options/legend" style="color:#3b82f6">Legend</a>
</div>

<!-- Scan Chart Modal -->
<div id="chart-modal" class="modal-overlay">
  <div class="modal-box">
    <button class="modal-close" onclick="closeChart()">&times;</button>
    <div class="modal-title" id="chart-title"></div>
    <div class="modal-subtitle" id="chart-subtitle"></div>
    <div class="modal-stats" id="chart-stats"></div>
    <canvas id="chart-canvas" width="620" height="260" style="width:100%;border:1px solid #e5e7eb;border-radius:8px"></canvas>
  </div>
</div>

<script>
(function() {{
  const table = document.getElementById('opts-table');
  const tbody = table.querySelector('tbody');
  const headers = table.querySelectorAll('th');
  const searchBox = document.getElementById('search');
  const sigFilter = document.getElementById('sig-filter');
  const qFilter = document.getElementById('q-filter');

  // Sort
  let sortCol = -1, sortAsc = true;
  headers.forEach(th => {{
    th.addEventListener('click', function() {{
      const col = parseInt(this.dataset.col);
      const type = this.dataset.type;
      if (sortCol === col) {{ sortAsc = !sortAsc; }} else {{ sortCol = col; sortAsc = true; }}
      headers.forEach(h => h.classList.remove('sorted'));
      this.classList.add('sorted');
      const arrow = this.querySelector('.arrow');
      if (arrow) arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';

      const rowsArr = Array.from(tbody.querySelectorAll('tr'));
      rowsArr.sort((a, b) => {{
        let av = a.children[col].textContent.trim();
        let bv = b.children[col].textContent.trim();
        if (type === 'num') {{
          av = parseFloat(av.replace(/[$,%,\\s,\\u25B2,\\u25BC,\\u2594]/g, '')) || 0;
          bv = parseFloat(bv.replace(/[$,%,\\s,\\u25B2,\\u25BC,\\u2594]/g, '')) || 0;
          return sortAsc ? av - bv : bv - av;
        }}
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
      rowsArr.forEach(r => tbody.appendChild(r));
    }});
  }});

  // Filter
  function applyFilters() {{
    const q = searchBox.value.toLowerCase();
    const sig = sigFilter.value;
    const qual = qFilter.value;
    const allRows = tbody.querySelectorAll('tr');
    allRows.forEach(r => {{
      const text = r.textContent.toLowerCase();
      const rSig = r.dataset.signal || '';
      const rQual = r.querySelector('.q-dot') ? r.querySelector('.q-dot').textContent.trim() : '';
      const matchQ = !q || text.includes(q);
      const matchSig = !sig || rSig === sig;
      const matchQual = !qual || rQual === qual;
      r.style.display = (matchQ && matchSig && matchQual) ? '' : 'none';
    }});
  }}
  searchBox.addEventListener('input', applyFilters);
  sigFilter.addEventListener('change', applyFilters);
  qFilter.addEventListener('change', applyFilters);
}})();

/* ── Chart Modal Functions ──────────────────────────────────────── */
function showChart(detailId, hotelName, seriesJson) {{
  let series;
  try {{ series = JSON.parse(seriesJson); }} catch(e) {{ return; }}
  if (!series || series.length < 2) return;

  const modal = document.getElementById('chart-modal');
  const canvas = document.getElementById('chart-canvas');
  const ctx = canvas.getContext('2d');

  // Title
  document.getElementById('chart-title').textContent =
    'Scan Price History — ' + hotelName + ' (ID: ' + detailId + ')';
  document.getElementById('chart-subtitle').textContent =
    series.length + ' scans from ' + series[0].date.substring(0,10) +
    ' to ' + series[series.length-1].date.substring(0,10);

  // Stats
  const prices = series.map(s => s.price);
  const firstP = prices[0], lastP = prices[prices.length-1];
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  let drops=0, rises=0;
  for (let i=1; i<prices.length; i++) {{
    if (prices[i] < prices[i-1] - 0.01) drops++;
    else if (prices[i] > prices[i-1] + 0.01) rises++;
  }}
  const chg = lastP - firstP;
  const chgPct = firstP > 0 ? (chg / firstP * 100) : 0;

  document.getElementById('chart-stats').innerHTML =
    '<div class="modal-stat"><div class="val">$' + firstP.toFixed(0) + '</div><div class="lbl">First Scan</div></div>' +
    '<div class="modal-stat"><div class="val">$' + lastP.toFixed(0) + '</div><div class="lbl">Latest</div></div>' +
    '<div class="modal-stat drop"><div class="val">' + drops + '</div><div class="lbl">Drops &#9660;</div></div>' +
    '<div class="modal-stat rise"><div class="val">' + rises + '</div><div class="lbl">Rises &#9650;</div></div>' +
    '<div class="modal-stat"><div class="val">$' + minP.toFixed(0) + '</div><div class="lbl">Min</div></div>' +
    '<div class="modal-stat"><div class="val">$' + maxP.toFixed(0) + '</div><div class="lbl">Max</div></div>' +
    '<div class="modal-stat ' + (chg < 0 ? 'drop' : 'rise') + '">' +
    '<div class="val">' + (chg >= 0 ? '+' : '') + chgPct.toFixed(1) + '%</div>' +
    '<div class="lbl">Total Change</div></div>';

  // Draw chart on canvas
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const padL = 60, padR = 20, padT = 20, padB = 40;
  const cw = W - padL - padR, ch = H - padT - padB;
  const pRange = maxP - minP || 1;
  const n = prices.length;

  // Grid
  ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 0.5;
  for (let i=0; i<=4; i++) {{
    const y = padT + ch * i / 4;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + cw, y); ctx.stroke();
    const pLabel = maxP - (pRange * i / 4);
    ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + pLabel.toFixed(0), padL - 6, y + 4);
  }}

  // X axis labels
  ctx.fillStyle = '#94a3b8'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(n / 6));
  for (let i=0; i<n; i+=step) {{
    const x = padL + (i / (n-1)) * cw;
    ctx.fillText(series[i].date.substring(5,10), x, H - 8);
  }}

  // Price line
  ctx.beginPath();
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
  for (let i=0; i<n; i++) {{
    const x = padL + (i / (n-1)) * cw;
    const y = padT + ch - ((prices[i] - minP) / pRange) * ch;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  // Fill under
  const lastX = padL + cw;
  ctx.lineTo(lastX, padT + ch); ctx.lineTo(padL, padT + ch); ctx.closePath();
  ctx.fillStyle = 'rgba(59,130,246,.08)'; ctx.fill();

  // Dots on price changes
  for (let i=0; i<n; i++) {{
    const x = padL + (i / (n-1)) * cw;
    const y = padT + ch - ((prices[i] - minP) / pRange) * ch;
    let color = '#3b82f6';
    if (i > 0 && prices[i] < prices[i-1] - 0.01) color = '#dc2626';
    else if (i > 0 && prices[i] > prices[i-1] + 0.01) color = '#16a34a';
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
  }}

  modal.classList.add('open');
}}

function closeChart() {{
  document.getElementById('chart-modal').classList.remove('open');
}}
document.getElementById('chart-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeChart();
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') closeChart();
}});
</script>
</body>
</html>"""


def _html_escape(s: str) -> str:
    """Minimal HTML escaping for user-provided strings."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _extract_curve_points(pred: dict, t_days: int | None) -> list[dict]:
    points = pred.get("forward_curve") or []
    if not points:
        points = pred.get("daily") or []

    normalized = []
    for p in points:
        date = p.get("date")
        price = p.get("predicted_price")
        if date is None or price is None:
            continue
        normalized.append({
            "date": date,
            "predicted_price": float(price),
            "lower_bound": p.get("lower_bound"),
            "upper_bound": p.get("upper_bound"),
            "t": p.get("t", p.get("days_remaining")),
        })

    if t_days is not None and t_days > 0:
        return normalized[:t_days]
    return normalized


def _derive_option_signal(pred: dict) -> str:
    change_pct = float(pred.get("expected_change_pct", 0) or 0)
    probability = pred.get("probability", {}) or {}
    up = float(probability.get("up", 0) or 0)
    down = float(probability.get("down", 0) or 0)

    if change_pct >= 0.5 or up > down + 0.1:
        return "CALL"
    if change_pct <= -0.5 or down > up + 0.1:
        return "PUT"
    return "NEUTRAL"


def _extract_sources(pred: dict, analysis: dict) -> list[dict]:
    signals = pred.get("signals") or []
    if signals:
        return [
            {
                "source": s.get("source"),
                "weight": s.get("weight"),
                "confidence": s.get("confidence"),
                "reasoning": s.get("reasoning"),
            }
            for s in signals
        ]

    model_info = analysis.get("model_info", {})
    return [
        {
            "source": "forward_curve",
            "weight": 1.0,
            "confidence": None,
            "reasoning": (
                f"Empirical decay curve from {model_info.get('total_tracks', 0)} tracks "
                f"and {model_info.get('total_observations', 0)} observations"
            ),
        }
    ]


def _build_quality_summary(pred: dict, sources: list[dict]) -> dict:
    quality = str(pred.get("confidence_quality", "medium") or "medium").lower()
    base_score_map = {"high": 0.85, "medium": 0.65, "low": 0.4}
    base_score = base_score_map.get(quality, 0.6)

    signal_conf_values = []
    for src in sources:
        conf = src.get("confidence")
        if isinstance(conf, (int, float)):
            signal_conf_values.append(float(conf))

    signal_confidence_mean = round(mean(signal_conf_values), 3) if signal_conf_values else None
    if signal_confidence_mean is not None:
        score = round((base_score * 0.6) + (signal_confidence_mean * 0.4), 3)
    else:
        score = round(base_score, 3)

    return {
        "label": quality.upper(),
        "score": score,
        "signals_count": len(sources),
        "signal_confidence_mean": signal_confidence_mean,
    }


def _build_option_levels(pred: dict, option_signal: str, quality: dict) -> dict:
    change_pct = float(pred.get("expected_change_pct", 0) or 0)
    probability = pred.get("probability", {}) or {}
    up = float(probability.get("up", 0) or 0)
    down = float(probability.get("down", 0) or 0)
    quality_score = float(quality.get("score", 0.6) or 0.6)

    prob_bias = up - down
    change_component = max(-1.0, min(1.0, change_pct / 12.0))
    probability_component = max(-1.0, min(1.0, prob_bias))

    base_score = (change_component * 0.65) + (probability_component * 0.35)
    weighted_score = base_score * max(0.2, min(1.0, quality_score))
    weighted_score = max(-1.0, min(1.0, weighted_score))

    abs_strength = abs(weighted_score)
    level_10 = int(round(abs_strength * 10))
    if level_10 == 0 and option_signal in ("CALL", "PUT"):
        level_10 = 1

    if option_signal == "CALL":
        direction = "CALL"
    elif option_signal == "PUT":
        direction = "PUT"
    else:
        direction = "NEUTRAL"
        level_10 = 0

    call_level = level_10 if direction == "CALL" else 0
    put_level = level_10 if direction == "PUT" else 0
    label = f"{direction}_L{level_10}" if direction != "NEUTRAL" else "NEUTRAL_L0"

    return {
        "direction": direction,
        "level_10": level_10,
        "label": label,
        "call_strength_level_10": call_level,
        "put_strength_level_10": put_level,
        "score": round(weighted_score, 4),
    }


def _build_row_chart(curve_points: list[dict]) -> dict:
    labels = [p["date"] for p in curve_points]
    predicted = [round(float(p["predicted_price"]), 2) for p in curve_points]
    lower = [round(float(p["lower_bound"]), 2) if p.get("lower_bound") is not None else None for p in curve_points]
    upper = [round(float(p["upper_bound"]), 2) if p.get("upper_bound") is not None else None for p in curve_points]
    return {
        "labels": labels,
        "series": {
            "predicted_price": predicted,
            "lower_bound": lower,
            "upper_bound": upper,
        },
    }


def _build_put_path_insights(
    curve_points: list[dict],
    current_price: float,
    predicted_checkin: float,
    probability: dict | None = None,
) -> dict:
    """Build put-side path insights: dips, declines, expected drops.

    Combines actual curve path analysis with probability-based expected drops.
    """
    horizon = len(curve_points) if curve_points else 0
    prob = probability or {}
    p_down = float(prob.get("down", 30.0) or 30.0) / 100.0
    p_up = float(prob.get("up", 30.0) or 30.0) / 100.0

    # Probability-based expected drops/rises over the horizon
    expected_future_drops = round(p_down * horizon, 1) if horizon > 0 else 0.0
    expected_future_rises = round(p_up * horizon, 1) if horizon > 0 else 0.0

    if not curve_points:
        base_price = round(float(predicted_checkin), 2)
        return {
            "t_min_price": base_price,
            "t_max_price": base_price,
            "t_min_price_date": None,
            "t_max_price_date": None,
            "put_decline_count": 0,
            "put_total_decline_amount": 0.0,
            "put_largest_single_decline": 0.0,
            "put_first_decline_date": None,
            "put_largest_decline_date": None,
            "put_downside_from_now_to_t_min": round(max(0.0, float(current_price) - base_price), 2),
            "put_rebound_from_t_min_to_checkin": 0.0,
            "put_decline_events": [],
            "expected_future_drops": expected_future_drops,
            "expected_future_rises": expected_future_rises,
        }

    prices = [float(p.get("predicted_price", predicted_checkin) or predicted_checkin) for p in curve_points]
    min_idx = min(range(len(prices)), key=lambda i: prices[i])
    max_idx = max(range(len(prices)), key=lambda i: prices[i])

    t_min_price = prices[min_idx]
    t_max_price = prices[max_idx]
    t_min_price_date = curve_points[min_idx].get("date")
    t_max_price_date = curve_points[max_idx].get("date")

    decline_events: list[dict] = []
    for i in range(1, len(prices)):
        prev_price = prices[i - 1]
        next_price = prices[i]
        drop_amount = prev_price - next_price

        if drop_amount > 0:
            drop_pct = round(drop_amount / prev_price * 100.0, 2) if prev_price > 0 else 0.0
            decline_events.append({
                "from_date": curve_points[i - 1].get("date"),
                "to_date": curve_points[i].get("date"),
                "from_price": round(prev_price, 2),
                "to_price": round(next_price, 2),
                "drop_amount": round(drop_amount, 2),
                "drop_pct": drop_pct,
            })

    total_decline = round(sum(float(e["drop_amount"]) for e in decline_events), 2)
    largest_decline_event = max(decline_events, key=lambda e: e["drop_amount"], default=None)

    # Use actual path dips if found; otherwise use probability-based estimate
    actual_decline_count = len(decline_events)
    effective_decline_count = max(actual_decline_count, round(expected_future_drops))

    return {
        "t_min_price": round(t_min_price, 2),
        "t_max_price": round(t_max_price, 2),
        "t_min_price_date": t_min_price_date,
        "t_max_price_date": t_max_price_date,
        "put_decline_count": effective_decline_count,
        "put_total_decline_amount": total_decline,
        "put_largest_single_decline": round(float(largest_decline_event["drop_amount"]), 2) if largest_decline_event else 0.0,
        "put_first_decline_date": decline_events[0]["to_date"] if decline_events else None,
        "put_largest_decline_date": largest_decline_event["to_date"] if largest_decline_event else None,
        "put_downside_from_now_to_t_min": round(max(0.0, float(current_price) - t_min_price), 2),
        "put_rebound_from_t_min_to_checkin": round(max(0.0, float(predicted_checkin) - t_min_price), 2),
        "put_decline_events": decline_events,
        "expected_future_drops": expected_future_drops,
        "expected_future_rises": expected_future_rises,
    }


def _build_info_badge(option_signal: str, quality: dict, sources: list[dict]) -> dict:
    score = float(quality.get("score", 0) or 0)
    icon = "i"
    if score < 0.5:
        icon = "?"

    quality_label = quality.get("label", "UNKNOWN")
    sources_text = _build_sources_tooltip(sources)
    tooltip = (
        f"Signal: {option_signal} | Quality: {quality_label} ({score:.2f})"
        f" | Sources: {sources_text}"
    )

    return {
        "icon": icon,
        "label": "information",
        "tooltip": tooltip,
        "show_sources_on_click": True,
    }


def _build_sources_tooltip(sources: list[dict]) -> str:
    parts: list[str] = []
    for src in sources[:4]:
        name = src.get("source") or "unknown"
        weight = src.get("weight")
        confidence = src.get("confidence")

        text = f"{name}"
        if isinstance(weight, (int, float)):
            text += f" w={float(weight):.2f}"
        if isinstance(confidence, (int, float)):
            text += f" c={float(confidence):.2f}"
        parts.append(text)

    if len(sources) > 4:
        parts.append(f"+{len(sources) - 4} more")
    return "; ".join(parts) if parts else "none"


def _build_source_validation(analysis: dict) -> dict:
    model_info = analysis.get("model_info", {}) or {}
    hist = analysis.get("historical_patterns_summary", {}) or {}
    events = analysis.get("events", {}) or {}
    flights = analysis.get("flight_demand", {}) or {}
    benchmarks = analysis.get("benchmarks", {}) or {}

    checks = {
        "forward_curve_tracks": int(model_info.get("total_tracks", 0) or 0) > 0,
        "forward_curve_observations": int(model_info.get("total_observations", 0) or 0) > 0,
        "historical_patterns_loaded": bool(hist.get("loaded", False)),
        "events_loaded": int(events.get("upcoming_events", 0) or 0) >= 0,
        "flight_demand_loaded": bool(flights),
        "benchmarks_available": benchmarks.get("status") in ("ok", "partial", "no_data"),
    }

    return {
        "checked_at": analysis.get("run_ts"),
        "checks": checks,
        "passed_checks": sum(1 for v in checks.values() if v),
        "total_checks": len(checks),
    }


def _build_system_capabilities(analysis: dict, total_rows: int) -> dict:
    model_info = analysis.get("model_info", {}) or {}
    events = analysis.get("events", {}) or {}
    flight = analysis.get("flight_demand", {}) or {}
    benchmarks = analysis.get("benchmarks", {}) or {}
    patterns = analysis.get("historical_patterns_summary", {}) or {}

    core_modules = {
        "forward_curve": bool(model_info.get("total_tracks", 0)),
        "historical_patterns": bool(patterns.get("loaded", False)),
        "events_enrichment": bool(events.get("total_events", 0) or events.get("upcoming_events", 0)),
        "flight_demand": flight.get("indicator", "NO_DATA") != "NO_DATA",
        "benchmarks": benchmarks.get("status") == "ok",
        "options_signal_engine": total_rows > 0,
        "option_levels_1_to_10": True,
        "source_transparency": True,
        "chart_payload": True,
    }

    return {
        "as_of": analysis.get("run_ts"),
        "trading_stack": {
            "signals": ["CALL", "PUT", "NEUTRAL"],
            "option_levels": "L1-L10",
            "row_metrics": [
                "expected_min_price",
                "expected_max_price",
                "touches_expected_min",
                "touches_expected_max",
                "count_price_changes_gt_20",
                "count_price_changes_lte_20",
            ],
            "explainability": ["sources", "quality", "info", "source_validation", "sources_audit_summary"],
        },
        "data_coverage": {
            "total_prediction_rows": total_rows,
            "tracks": int(model_info.get("total_tracks", 0) or 0),
            "observations": int(model_info.get("total_observations", 0) or 0),
            "events_upcoming": int(events.get("upcoming_events", 0) or 0),
            "flight_indicator": flight.get("indicator", "NO_DATA"),
            "benchmarks_status": benchmarks.get("status", "no_data"),
            "historical_combos": int(patterns.get("n_combos", 0) or 0),
        },
        "core_modules": core_modules,
        "active_modules": sum(1 for v in core_modules.values() if v),
        "total_modules": len(core_modules),
    }


def _build_sources_audit(analysis: dict, summary_only: bool = False) -> dict:
    from src.analytics.data_sources import get_sources_summary

    registry = get_sources_summary()
    sources = registry.get("sources", [])

    model_info = analysis.get("model_info", {}) or {}
    flight_demand = analysis.get("flight_demand", {}) or {}
    events = analysis.get("events", {}) or {}
    knowledge = analysis.get("knowledge", {}) or {}
    benchmarks = analysis.get("benchmarks", {}) or {}
    hist = analysis.get("historical_patterns_summary", {}) or {}

    audited = []
    for src in sources:
        sid = src.get("id")
        runtime_status = "not_checked"
        evidence = "No runtime probe configured"

        if sid == "salesoffice":
            tracks = int(model_info.get("total_tracks", 0) or 0)
            runtime_status = "active" if tracks > 0 else "degraded"
            evidence = f"forward_curve_tracks={tracks}"
        elif sid == "kiwi_flights":
            indicator = flight_demand.get("indicator", "NO_DATA")
            runtime_status = "active" if indicator != "NO_DATA" else "degraded"
            evidence = f"indicator={indicator}"
        elif sid == "miami_events_hardcoded":
            total_events = int(events.get("total_events", 0) or 0)
            runtime_status = "active" if total_events > 0 else "degraded"
            evidence = f"total_events={total_events}"
        elif sid == "tbo_hotels":
            market = knowledge.get("market", {}) or {}
            total_hotels = int(market.get("total_hotels", 0) or 0)
            runtime_status = "active" if total_hotels > 0 else "degraded"
            evidence = f"market_hotels={total_hotels}"
        elif sid == "hotel_booking_dataset":
            status = benchmarks.get("status", "no_data")
            runtime_status = "active" if status == "ok" else "degraded"
            evidence = f"benchmarks_status={status}"
        elif sid == "trivago_statista":
            statista_info = _detect_statista_benchmark_file()
            runtime_status = "active" if statista_info["exists"] else "degraded"
            if statista_info["exists"]:
                evidence = (
                    f"file={statista_info['path']}, "
                    f"months={statista_info['months_count']}, "
                    f"source={statista_info['source_name']}"
                )
            else:
                evidence = f"file_missing={statista_info['path']}"
        elif sid == "brightdata_mcp":
            brightdata_info = _detect_brightdata_mcp()
            runtime_status = "active" if brightdata_info["configured"] else "degraded"
            if brightdata_info["configured"]:
                evidence = (
                    f"mcp_config={brightdata_info['path']}, "
                    f"has_server_key={brightdata_info['has_server_key']}"
                )
            else:
                evidence = f"mcp_not_configured={brightdata_info['path']}"
        elif sid == "ota_brightdata_exports":
            ota_info = _detect_brightdata_ota_outputs()
            runtime_status = "active" if ota_info["exists"] and ota_info["rows"] > 0 else "degraded"
            if ota_info["exists"]:
                evidence = (
                    f"file={ota_info['path']}, rows={ota_info['rows']}, "
                    f"platforms={','.join(ota_info['platforms']) or 'none'}"
                )
            else:
                evidence = f"file_missing={ota_info['path']}"
        elif src.get("status") == "planned":
            runtime_status = "planned"
            evidence = "Source is configured as planned"

        audited.append({
            "id": sid,
            "name": src.get("name"),
            "category": src.get("category"),
            "configured_status": src.get("status"),
            "runtime_status": runtime_status,
            "evidence": evidence,
            "update_freq": src.get("update_freq"),
            "url": src.get("url"),
        })

    active_runtime = sum(1 for s in audited if s["runtime_status"] == "active")
    degraded_runtime = sum(1 for s in audited if s["runtime_status"] == "degraded")
    planned_runtime = sum(1 for s in audited if s["runtime_status"] == "planned")

    summary = {
        "checked_at": analysis.get("run_ts"),
        "total_sources": len(audited),
        "runtime_active": active_runtime,
        "runtime_degraded": degraded_runtime,
        "runtime_planned": planned_runtime,
        "historical_patterns_loaded": bool(hist.get("loaded", False)),
    }

    status = "ok" if degraded_runtime == 0 else "degraded"
    checks = {
        "has_sources": len(audited) > 0,
        "has_active_runtime_source": active_runtime > 0,
        "historical_patterns_loaded": bool(hist.get("loaded", False)),
    }

    if summary_only:
        return summary

    return {
        "status": status,
        "summary": summary,
        "checks": checks,
        "source_validation": _build_source_validation(analysis),
        "sources": audited,
    }


def _detect_statista_benchmark_file() -> dict:
    workspace_root = Path(__file__).resolve().parents[2]
    benchmark_path = workspace_root / "data" / "miami_benchmarks.json"

    result = {
        "path": str(benchmark_path),
        "exists": benchmark_path.exists(),
        "months_count": 0,
        "source_name": None,
    }
    if not benchmark_path.exists():
        return result

    try:
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
        months_data = payload.get("monthly_adr") or payload.get("adr_by_month") or []
        if isinstance(months_data, dict):
            months_count = len(months_data)
        elif isinstance(months_data, list):
            months_count = len(months_data)
        else:
            months_count = 0

        result["months_count"] = months_count
        result["source_name"] = payload.get("source") or payload.get("data_source")
        return result
    except Exception:
        return result


def _detect_brightdata_mcp() -> dict:
    workspace_root = Path(__file__).resolve().parents[2]
    mcp_path = workspace_root / ".mcp.json"
    result = {
        "path": str(mcp_path),
        "configured": False,
        "has_server_key": False,
    }
    if not mcp_path.exists():
        return result

    try:
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        servers = payload.get("mcpServers", {}) if isinstance(payload, dict) else {}
        has_server = "brightdata" in servers
        result["configured"] = has_server
        result["has_server_key"] = has_server
        return result
    except Exception:
        return result


def _detect_brightdata_ota_outputs() -> dict:
    workspace_root = Path(__file__).resolve().parents[2]
    summary_path = workspace_root / "data" / "processed" / "brightdata_ota_summary.json"
    result = {
        "path": str(summary_path),
        "exists": summary_path.exists(),
        "rows": 0,
        "platforms": [],
    }
    if not summary_path.exists():
        return result

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        result["rows"] = int(payload.get("rows", 0) or 0)
        platforms = payload.get("platforms", {})
        if isinstance(platforms, dict):
            result["platforms"] = sorted([str(k) for k in platforms.keys()])
        return result
    except Exception:
        return result
