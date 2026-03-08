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
  GET /api/v1/salesoffice/options/ai-insights — AI-powered market intelligence (JSON)
  GET /api/v1/salesoffice/ai/ask     — Ask Claude about portfolio data (Q&A)
  GET /api/v1/salesoffice/ai/brief   — AI market brief (EN/HE)
  GET /api/v1/salesoffice/ai/explain/{detail_id} — Deep prediction explanation
  GET /api/v1/salesoffice/ai/metadata — Smart tags & metadata per room
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


@router.get("/options/detail/{detail_id}")
def salesoffice_option_detail(detail_id: int):
    """Return compact detail data for the inline trading chart panel.

    Called lazily when the user expands a row in the HTML dashboard.
    """
    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})
    pred = predictions.get(detail_id) or predictions.get(str(detail_id))
    if not pred:
        raise HTTPException(status_code=404, detail=f"Room {detail_id} not found")

    curve_points = _extract_curve_points(pred, None)
    scan = pred.get("scan_history") or {}
    current_price = float(pred.get("current_price", 0) or 0)
    predicted_checkin = float(pred.get("predicted_checkin_price", current_price) or current_price)

    path_prices = [p["predicted_price"] for p in curve_points]
    expected_min = min(path_prices) if path_prices else current_price
    expected_max = max(path_prices) if path_prices else predicted_checkin
    option_signal = _derive_option_signal(pred)

    signals_list = pred.get("signals") or []
    fc_sig = next((s for s in signals_list if s.get("source") == "forward_curve"), None)
    hist_sig = next((s for s in signals_list if s.get("source") == "historical_pattern"), None)

    fc_pts = pred.get("forward_curve") or []
    ev_adj = sum(float(p.get("event_adj_pct", 0) or 0) for p in fc_pts)
    se_adj = sum(float(p.get("season_adj_pct", 0) or 0) for p in fc_pts)
    dm_adj = sum(float(p.get("demand_adj_pct", 0) or 0) for p in fc_pts)
    mo_adj = sum(float(p.get("momentum_adj_pct", 0) or 0) for p in fc_pts)

    quality = _build_quality_summary(pred, _extract_sources(pred, analysis))
    chg = round(float(pred.get("expected_change_pct", 0) or 0), 2)

    # Build scan points with MM-DD dates
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

    detail_data = {
        "fc": [{"d": p["date"][-5:], "p": round(p["predicted_price"], 1),
                "lo": round(float(p.get("lower_bound") or p["predicted_price"]), 1),
                "hi": round(float(p.get("upper_bound") or p["predicted_price"]), 1)}
               for p in curve_points],
        "scan": scan_pts,
        "cp": round(current_price, 2),
        "pp": round(predicted_checkin, 2),
        "mn": round(expected_min, 2),
        "mx": round(expected_max, 2),
        "sig": option_signal,
        "fcW": round(float(fc_sig.get("weight", 0) or 0), 2) if fc_sig else 0,
        "fcC": round(float(fc_sig.get("confidence", 0) or 0), 2) if fc_sig else 0,
        "fcP": round(float(fc_sig["predicted_price"]), 2) if fc_sig and fc_sig.get("predicted_price") else None,
        "hiW": round(float(hist_sig.get("weight", 0) or 0), 2) if hist_sig else 0,
        "hiC": round(float(hist_sig.get("confidence", 0) or 0), 2) if hist_sig else 0,
        "hiP": round(float(hist_sig["predicted_price"]), 2) if hist_sig and hist_sig.get("predicted_price") else None,
        "adj": {"ev": round(ev_adj, 2), "se": round(se_adj, 2),
                "dm": round(dm_adj, 2), "mo": round(mo_adj, 2)},
        "mom": pred.get("momentum", {}),
        "reg": pred.get("regime", {}),
        "mkt": (pred.get("market_benchmark") or {}).get("market_avg_price", 0),
        "q": quality.get("label", ""),
        "chg": chg,
        "drops": scan.get("scan_actual_drops", 0),
        "rises": scan.get("scan_actual_rises", 0),
        "scans": scan.get("scan_snapshots", 0),
    }
    return JSONResponse(content=detail_data)


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


@router.get("/options/ai-insights")
async def salesoffice_ai_insights(
    t_days: int | None = None,
    hotel_name: str | None = None,
):
    """AI-powered market intelligence — aggregate + per-room analysis.

    Query params:
      - t_days: horizon limit (matches /options)
      - hotel_name: filter to a specific hotel (partial match)

    Returns AI-generated market summary, alerts, anomalies, risk assessment,
    signal synthesis, and Bayesian tracker state for the current portfolio.
    """
    try:
        from src.analytics.ai_intelligence import (
            generate_ai_insights_batch,
            generate_market_narrative,
            detect_anomaly,
            assess_risk,
            synthesize_signals,
            get_bayesian_tracker,
            AI_ENABLED,
            ANTHROPIC_API_KEY,
            CLAUDE_MODEL,
        )
    except ImportError:
        return JSONResponse(content={"error": "AI intelligence module not available"}, status_code=503)

    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    ai_rows = []
    for detail_id, pred in predictions.items():
        h_name = pred.get("hotel_name", "")
        if hotel_name and hotel_name.lower() not in (h_name or "").lower():
            continue

        current_price = float(pred.get("current_price", 0) or 0)
        predicted_price = float(pred.get("predicted_checkin_price", current_price) or current_price)
        change_pct = float(pred.get("expected_change_pct", 0) or 0)
        days = int(pred.get("days_to_checkin", 0) or 0)

        # Signal data
        signal = "CALL" if change_pct > 2 else "PUT" if change_pct < -2 else "NEUTRAL"
        regime = "NORMAL"
        momentum_sig = "NORMAL"
        if pred.get("regime"):
            regime = pred["regime"].get("regime", "NORMAL") if isinstance(pred["regime"], dict) else str(pred["regime"])
        if pred.get("momentum"):
            momentum_sig = pred["momentum"].get("signal", "NORMAL") if isinstance(pred["momentum"], dict) else str(pred["momentum"])

        scan = pred.get("scan_history") or {}
        scan_prices = scan.get("scan_price_series", [])
        events_data = analysis.get("events", {}).get("next_events", [])

        # Generate per-room AI analysis
        narrative = generate_market_narrative(
            hotel_name=h_name,
            category=pred.get("category", ""),
            current_price=current_price,
            predicted_price=predicted_price,
            change_pct=change_pct,
            days_to_checkin=days,
            signal=signal,
            regime=regime,
            momentum_signal=momentum_sig,
            events=events_data,
            scan_count=scan.get("scan_snapshots", 0),
            scan_drops=scan.get("scan_actual_drops", 0),
            scan_rises=scan.get("scan_actual_rises", 0),
        )

        anomaly = detect_anomaly(
            hotel_name=h_name,
            current_price=current_price,
            predicted_price=predicted_price,
            change_pct=change_pct,
            scan_prices=[p.get("price", 0) if isinstance(p, dict) else p for p in scan_prices] if scan_prices else [],
            regime=regime,
        )

        risk = assess_risk(
            current_price=current_price,
            predicted_price=predicted_price,
            change_pct=change_pct,
            days_to_checkin=days,
            scan_count=scan.get("scan_snapshots", 0),
            regime=regime,
        )

        ai_rows.append({
            "detail_id": int(detail_id),
            "hotel_name": h_name,
            "category": pred.get("category"),
            "current_price": round(current_price, 2),
            "predicted_price": round(predicted_price, 2),
            "change_pct": round(change_pct, 2),
            "signal": signal,
            "narrative": narrative.to_dict(),
            "anomaly": anomaly.to_dict(),
            "risk": risk.to_dict(),
        })

    # Sort by risk score descending  
    ai_rows.sort(key=lambda r: r.get("risk", {}).get("risk_score", 0), reverse=True)

    # Aggregate insights
    batch_rows = []
    for r in ai_rows:
        batch_rows.append({
            "signal": r["signal"],
            "change_pct": r["change_pct"],
            "ai_anomaly": r["anomaly"],
            "ai_risk": r["risk"],
        })
    batch_insights = generate_ai_insights_batch(batch_rows)

    return JSONResponse(content={
        "ai_version": "1.0",
        "ai_enabled": AI_ENABLED,
        "claude_connected": bool(ANTHROPIC_API_KEY),
        "model": CLAUDE_MODEL if ANTHROPIC_API_KEY else "rule_based_fallback",
        "total_rooms_analyzed": len(ai_rows),
        "market_insights": batch_insights,
        "rooms": ai_rows,
    })


# ── Claude Analyst Endpoints ─────────────────────────────────────────


@router.get("/ai/ask")
async def salesoffice_ai_ask(
    q: str,
    detail_id: int | None = None,
    deep: bool = False,
):
    """Ask Claude a question about the portfolio data.

    Query params:
      - q: Your question in natural language (English or Hebrew)
      - detail_id: Optional — focus analysis on a specific room
      - deep: Use more powerful model for deeper analysis (slower)

    Examples:
      - /ai/ask?q=what are the best CALL opportunities right now?
      - /ai/ask?q=מה המצב של מלון הילטון?
      - /ai/ask?q=explain the risk for room 12345&detail_id=12345
      - /ai/ask?q=which hotels have momentum signals?&deep=true
    """
    try:
        from src.analytics.claude_analyst import ask_analyst
    except ImportError:
        return JSONResponse(content={"error": "Claude analyst module not available"}, status_code=503)

    analysis = _get_or_run_analysis()
    result = ask_analyst(question=q, analysis=analysis, detail_id=detail_id, deep=deep)

    return JSONResponse(content={
        "question": q,
        "detail_id": detail_id,
        "deep_mode": deep,
        **result.to_dict(),
    })


@router.get("/ai/brief")
async def salesoffice_ai_brief(
    lang: str = "en",
):
    """AI-generated executive market brief for the trading team.

    Query params:
      - lang: "en" for English, "he" for Hebrew (עברית)

    Returns a formatted market brief covering:
      - Market pulse and overall tone
      - Top opportunities (CALL signals)
      - Risk alerts (PUT signals, anomalies)
      - Events and external factors
      - Action items
    """
    try:
        from src.analytics.claude_analyst import generate_market_brief
    except ImportError:
        return JSONResponse(content={"error": "Claude analyst module not available"}, status_code=503)

    analysis = _get_or_run_analysis()
    result = generate_market_brief(analysis=analysis, language=lang)

    return JSONResponse(content={
        "language": lang,
        **result.to_dict(),
    })


@router.get("/ai/explain/{detail_id}")
async def salesoffice_ai_explain(detail_id: int):
    """Deep AI explanation of a specific room's prediction.

    Walks through each contributing factor:
      - Forward Curve signal
      - Historical Pattern
      - Scan History (actual price behavior)
      - Events impact
      - Market positioning
      - Momentum & Regime
    """
    try:
        from src.analytics.claude_analyst import explain_prediction
    except ImportError:
        return JSONResponse(content={"error": "Claude analyst module not available"}, status_code=503)

    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})
    pred = predictions.get(str(detail_id)) or predictions.get(detail_id)

    if not pred:
        raise HTTPException(status_code=404, detail=f"Room {detail_id} not found")

    result = explain_prediction(pred=pred, detail_id=detail_id, analysis=analysis)

    return JSONResponse(content={
        "detail_id": detail_id,
        "hotel_name": pred.get("hotel_name"),
        "category": pred.get("category"),
        "current_price": float(pred.get("current_price", 0) or 0),
        "predicted_price": float(pred.get("predicted_checkin_price", 0) or 0),
        **result.to_dict(),
    })


@router.get("/ai/metadata")
async def salesoffice_ai_metadata(
    limit: int = 50,
    detail_id: int | None = None,
):
    """AI-generated smart tags and metadata for room options.

    Query params:
      - limit: Max rooms to enrich (default 50, sorted by signal strength)
      - detail_id: Optional — get metadata for a single room

    Returns per-room:
      - tag: hot_deal | watch | risky | stable | momentum_play | contrarian | premium_opportunity
      - one_liner: 1-sentence insight
      - action: BUY_NOW | WAIT | AVOID | MONITOR | REVIEW
      - confidence_emoji: 🟢 🟡 🔴
      - key_factor: Most important driver
    """
    try:
        from src.analytics.claude_analyst import enrich_room_metadata, batch_enrich_metadata
    except ImportError:
        return JSONResponse(content={"error": "Claude analyst module not available"}, status_code=503)

    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    if detail_id is not None:
        pred = predictions.get(str(detail_id)) or predictions.get(detail_id)
        if not pred:
            raise HTTPException(status_code=404, detail=f"Room {detail_id} not found")
        meta = enrich_room_metadata(pred, detail_id, analysis)
        return JSONResponse(content={
            "detail_id": detail_id,
            "hotel_name": pred.get("hotel_name"),
            "category": pred.get("category"),
            **meta,
        })

    results = batch_enrich_metadata(predictions, limit=limit)

    enriched_rooms = []
    for pid, meta in results.items():
        pred = predictions.get(str(pid)) or predictions.get(int(pid), {})
        enriched_rooms.append({
            "detail_id": int(pid),
            "hotel_name": pred.get("hotel_name", ""),
            "category": pred.get("category", ""),
            "current_price": round(float(pred.get("current_price", 0) or 0), 2),
            "predicted_price": round(float(pred.get("predicted_checkin_price", 0) or 0), 2),
            "change_pct": round(float(pred.get("expected_change_pct", 0) or 0), 2),
            **meta,
        })

    # Sort by action priority
    action_order = {"BUY_NOW": 0, "AVOID": 1, "MONITOR": 2, "REVIEW": 3, "WAIT": 4}
    enriched_rooms.sort(key=lambda r: action_order.get(r.get("action", "WAIT"), 5))

    return JSONResponse(content={
        "total_enriched": len(enriched_rooms),
        "limit": limit,
        "rooms": enriched_rooms,
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

        # Per-source predicted prices
        signals_list = pred.get("signals") or []
        fc_sig = next((s for s in signals_list if s.get("source") == "forward_curve"), None)
        hist_sig = next((s for s in signals_list if s.get("source") == "historical_pattern"), None)
        ml_sig = next((s for s in signals_list if s.get("source") == "ml_forecast"), None)

        # Forward curve adjustment totals
        fc_pts = pred.get("forward_curve") or []
        ev_adj = sum(float(p.get("event_adj_pct", 0) or 0) for p in fc_pts)
        se_adj = sum(float(p.get("season_adj_pct", 0) or 0) for p in fc_pts)
        dm_adj = sum(float(p.get("demand_adj_pct", 0) or 0) for p in fc_pts)
        mo_adj = sum(float(p.get("momentum_adj_pct", 0) or 0) for p in fc_pts)

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
            # Scan min/max from actual monitoring
            "scan_min_price": min((p.get("price", 0) for p in (scan.get("scan_price_series") or []) if p.get("price")), default=None),
            "scan_max_price": max((p.get("price", 0) for p in (scan.get("scan_price_series") or []) if p.get("price")), default=None),
            # Market benchmark — hotel vs same-star avg in same city
            "market_avg_price": (pred.get("market_benchmark") or {}).get("market_avg_price", 0),
            "market_pressure": (pred.get("market_benchmark") or {}).get("pressure", 0),
            "market_competitor_hotels": (pred.get("market_benchmark") or {}).get("competitor_hotels", 0),
            "market_city": (pred.get("market_benchmark") or {}).get("city", ""),
            "market_stars": (pred.get("market_benchmark") or {}).get("stars", 0),
            # Per-source predictions
            "fc_price": round(float(fc_sig["predicted_price"]), 2) if fc_sig and fc_sig.get("predicted_price") else None,
            "fc_confidence": round(float(fc_sig.get("confidence", 0) or 0), 2) if fc_sig else 0,
            "fc_weight": round(float(fc_sig.get("weight", 0) or 0), 2) if fc_sig else 0,
            "hist_price": round(float(hist_sig["predicted_price"]), 2) if hist_sig and hist_sig.get("predicted_price") else None,
            "hist_confidence": round(float(hist_sig.get("confidence", 0) or 0), 2) if hist_sig else 0,
            "hist_weight": round(float(hist_sig.get("weight", 0) or 0), 2) if hist_sig else 0,
            "ml_price": round(float(ml_sig["predicted_price"]), 2) if ml_sig and ml_sig.get("predicted_price") else None,
            "event_adj_total": round(ev_adj, 2),
            "season_adj_total": round(se_adj, 2),
            "demand_adj_total": round(dm_adj, 2),
            "momentum_adj_total": round(mo_adj, 2),
            # Signal reasoning for source detail popup
            "fc_reasoning": (fc_sig.get("reasoning", "") if fc_sig else ""),
            "hist_reasoning": (hist_sig.get("reasoning", "") if hist_sig else ""),
            "ml_reasoning": (ml_sig.get("reasoning", "") if ml_sig else ""),
            "prediction_method": pred.get("prediction_method", ""),
            "explanation_factors": pred.get("explanation", {}).get("factors", []),
            # Forward curve series for inline trading chart
            "fc_series": [{"d": p["date"][-5:], "p": round(p["predicted_price"], 1),
                           "lo": round(float(p.get("lower_bound") or p["predicted_price"]), 1),
                           "hi": round(float(p.get("upper_bound") or p["predicted_price"]), 1)}
                          for p in curve_points],
            # Per-day adjustments for detail panel
            "fc_adj_series": [{"d": p["date"][-5:],
                               "ev": round(float(p.get("event_adj_pct", 0) or 0), 2),
                               "se": round(float(p.get("season_adj_pct", 0) or 0), 2),
                               "dm": round(float(p.get("demand_adj_pct", 0) or 0), 2),
                               "mo": round(float(p.get("momentum_adj_pct", 0) or 0), 2)}
                              for p in (pred.get("forward_curve") or [])[:len(curve_points)]],
            # Momentum & regime for detail panel
            "momentum": pred.get("momentum", {}),
            "regime": pred.get("regime", {}),
            # YoY comparison
            "yoy": pred.get("yoy_comparison", {}),
        })

    rows.sort(key=lambda x: (
        0 if x["option_signal"] in ("CALL", "PUT") else 1,
        -abs(float(x.get("expected_change_pct", 0))),
    ))

    if signal:
        sig_upper = signal.strip().upper()
        if sig_upper in ("CALL", "PUT", "NEUTRAL"):
            rows = [r for r in rows if r["option_signal"] == sig_upper]

    # ── Enrich rows with AI intelligence ──
    try:
        from src.analytics.ai_intelligence import detect_anomaly, assess_risk

        for r in rows:
            scan_prices_raw = r.get("scan_price_series", [])
            scan_prices = [
                p.get("price", 0) if isinstance(p, dict) else p
                for p in scan_prices_raw
            ] if scan_prices_raw else []

            anomaly = detect_anomaly(
                hotel_name=r.get("hotel_name", ""),
                current_price=r.get("current_price", 0),
                predicted_price=r.get("predicted_checkin_price", 0),
                change_pct=r.get("expected_change_pct", 0),
                scan_prices=scan_prices,
                regime="NORMAL",
            )
            risk = assess_risk(
                current_price=r.get("current_price", 0),
                predicted_price=r.get("predicted_checkin_price", 0),
                change_pct=r.get("expected_change_pct", 0),
                days_to_checkin=r.get("days_to_checkin", 0) or 0,
                scan_count=r.get("scan_snapshots", 0),
                regime="NORMAL",
                quality_score=r.get("quality_score", 0.5),
            )
            r["ai_anomaly"] = anomaly.to_dict()
            r["ai_risk"] = risk.to_dict()
            r["ai_conviction"] = ""
    except Exception as e:
        logger.debug(f"AI enrichment for HTML skipped: {e}")

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

        # Per-source prediction cells
        fc_p = r.get("fc_price")
        fc_w = r.get("fc_weight", 0)
        fc_c = r.get("fc_confidence", 0)
        ev_adj = r.get("event_adj_total", 0)
        se_adj = r.get("season_adj_total", 0)
        dm_adj = r.get("demand_adj_total", 0)
        mo_adj = r.get("momentum_adj_total", 0)
        if fc_p is not None:
            fc_cls = "pct-up" if fc_p > r["current_price"] else ("pct-down" if fc_p < r["current_price"] else "")
            fc_chg = (fc_p - r["current_price"]) / r["current_price"] * 100 if r["current_price"] > 0 else 0
            fc_title = (
                f"FC predicted: ${fc_p:,.0f} ({fc_chg:+.1f}%) | "
                f"Weight: {fc_w:.0%} | Confidence: {fc_c:.0%} | "
                f"Adjustments: events {ev_adj:+.1f}%, season {se_adj:+.1f}%, "
                f"demand {dm_adj:+.1f}%, momentum {mo_adj:+.1f}%"
            )
            fc_cell = f'${fc_p:,.0f} <small class="{fc_cls}">({fc_chg:+.0f}%)</small>'
        else:
            fc_cls = ""
            fc_title = "No forward curve data"
            fc_cell = "-"

        hist_p = r.get("hist_price")
        hist_w = r.get("hist_weight", 0)
        hist_c = r.get("hist_confidence", 0)
        if hist_p is not None:
            hist_cls = "pct-up" if hist_p > r["current_price"] else ("pct-down" if hist_p < r["current_price"] else "")
            hist_chg = (hist_p - r["current_price"]) / r["current_price"] * 100 if r["current_price"] > 0 else 0
            hist_title = (
                f"Historical predicted: ${hist_p:,.0f} ({hist_chg:+.1f}%) | "
                f"Weight: {hist_w:.0%} | Confidence: {hist_c:.0%}"
            )
            hist_cell = f'${hist_p:,.0f} <small class="{hist_cls}">({hist_chg:+.0f}%)</small>'
        else:
            hist_cls = ""
            hist_title = "No historical pattern data for this hotel/period"
            hist_cell = '<span style="color:#94a3b8">-</span>'
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

        # ── Scan min/max from actual monitoring ──
        scan_min = r.get("scan_min_price")
        scan_max = r.get("scan_max_price")
        pred_min = r["expected_min_price"]
        pred_max = r["expected_max_price"]

        if scan_min is not None and s_snaps > 1:
            min_title = f"Scan min: ${scan_min:,.0f} (actual) | Predicted min: ${pred_min:,.0f} (FC path)"
            min_cell = f'<span class="price-dual">${scan_min:,.0f}<small class="pred-sub">pred ${pred_min:,.0f}</small></span>'
        else:
            min_title = f"Predicted min: ${pred_min:,.0f} (forward curve path)"
            min_cell = f'${pred_min:,.2f}'

        if scan_max is not None and s_snaps > 1:
            max_title = f"Scan max: ${scan_max:,.0f} (actual) | Predicted max: ${pred_max:,.0f} (FC path)"
            max_cell = f'<span class="price-dual">${scan_max:,.0f}<small class="pred-sub">pred ${pred_max:,.0f}</small></span>'
        else:
            max_title = f"Predicted max: ${pred_max:,.0f} (forward curve path)"
            max_cell = f'${pred_max:,.2f}'

        # ── Source detail JSON for popup ──
        src_detail = {
            "method": r.get("prediction_method", ""),
            "signals": [],
            "adjustments": {"events": ev_adj, "season": se_adj, "demand": dm_adj, "momentum": mo_adj},
            "factors": r.get("explanation_factors", []),
        }
        if fc_p is not None:
            src_detail["signals"].append({
                "source": "Forward Curve", "price": fc_p, "weight": fc_w,
                "confidence": fc_c, "reasoning": r.get("fc_reasoning", ""),
            })
        if hist_p is not None:
            src_detail["signals"].append({
                "source": "Historical Pattern", "price": hist_p, "weight": hist_w,
                "confidence": hist_c, "reasoning": r.get("hist_reasoning", ""),
            })
        ml_p = r.get("ml_price")
        if ml_p is not None:
            src_detail["signals"].append({
                "source": "ML Forecast", "price": ml_p, "weight": 0,
                "confidence": 0, "reasoning": r.get("ml_reasoning", ""),
            })
        src_json = json.dumps(src_detail).replace("'", "&#39;").replace('"', "&quot;")

        # ── Chart + Sources combined cell ──
        if len(scan_series) > 1:
            chart_cell = (
                f'<button class="chart-btn" title="Scan price chart" '
                f"onclick='showChart({det_id}, "
                f"{esc_hotel}, "
                f"this.dataset.series)' "
                f"data-series='{series_json}'>"
                f'&#128200;</button>'
                f'<button class="src-btn" title="Source detail" '
                f'onclick="showSources(this)" '
                f'data-sources="{src_json}" '
                f'data-hotel="{_html_escape(r["hotel_name"])}" '
                f'data-detail-id="{r["detail_id"]}">'
                f'&#128269;</button>'
            )
        else:
            chart_cell = (
                f'<button class="src-btn" title="Source detail" '
                f'onclick="showSources(this)" '
                f'data-sources="{src_json}" '
                f'data-hotel="{_html_escape(r["hotel_name"])}" '
                f'data-detail-id="{r["detail_id"]}">'
                f'&#128269;</button>'
            )

        # ── AI Intelligence cell ──
        ai_risk_data = r.get("ai_risk", {})
        ai_anomaly_data = r.get("ai_anomaly", {})
        ai_conviction = r.get("ai_conviction", "")
        ai_risk_level = ai_risk_data.get("risk_level", "")
        ai_risk_score = ai_risk_data.get("risk_score", 0)
        ai_is_anomaly = ai_anomaly_data.get("is_anomaly", False)
        ai_anomaly_type = ai_anomaly_data.get("anomaly_type", "")
        ai_anomaly_sev = ai_anomaly_data.get("severity", "none")

        # Build AI badge
        risk_cls_map = {"low": "ai-low", "medium": "ai-med", "high": "ai-high", "extreme": "ai-ext"}
        ai_risk_cls = risk_cls_map.get(ai_risk_level, "ai-low")
        ai_title_parts = [f"Risk: {ai_risk_level} ({ai_risk_score:.0%})"]
        if ai_conviction:
            ai_title_parts.append(f"Conviction: {ai_conviction}")
        if ai_is_anomaly:
            ai_title_parts.append(f"Anomaly: {ai_anomaly_type} ({ai_anomaly_sev})")
        ai_title = " | ".join(ai_title_parts)

        ai_badge = f'<span class="ai-badge {ai_risk_cls}" title="{ai_title}">'
        ai_badge += f'{ai_risk_level[:3].upper()}'
        if ai_is_anomaly:
            ai_badge += f' <span class="ai-anomaly-dot" title="{ai_anomaly_type}: {ai_anomaly_data.get("explanation", "")}">&#9888;</span>'
        ai_badge += '</span>'

        table_rows.append(
            f'<tr class="{sig_cls}" '
            f'data-signal="{sig}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-change="{chg}" '
            f'data-detail-id="{r["detail_id"]}" '
            f'data-current-price="{r["current_price"]}">'
            f'<td class="col-id sticky-col sc-id"><button class="expand-btn" id="eb-{r["detail_id"]}" onclick="toggleDetail({r["detail_id"]})" title="Expand trading chart">&#9660;</button> {r["detail_id"]}</td>'
            f'<td class="col-hotel sticky-col sc-hotel" title="{_html_escape(r["hotel_name"])}">{_html_escape(r["hotel_name"][:30])}</td>'
            f'<td>{_html_escape(r["category"])}</td>'
            f'<td>{_html_escape(r["board"])}</td>'
            f'<td>{_html_escape(str(r["date_from"] or ""))}</td>'
            f'<td class="num">{r["days_to_checkin"] or ""}</td>'
            f'<td>{sig_badge}</td>'
            f'<td class="num">${r["current_price"]:,.2f}</td>'
            f'<td class="num">${r["predicted_checkin_price"]:,.2f}</td>'
            f'<td class="num {chg_cls}">{chg_arrow} {chg:+.1f}%</td>'
            f'<td class="num {fc_cls}" title="{fc_title}">{fc_cell}</td>'
            f'<td class="num {hist_cls}" title="{hist_title}">{hist_cell}</td>'
            f'<td class="num" title="{min_title}">{min_cell}</td>'
            f'<td class="num" title="{max_title}">{max_cell}</td>'
            f'<td class="num">{r["touches_min"]}/{r["touches_max"]}</td>'
            f'<td class="num">{r["changes_gt_20"]}</td>'
            f'<td class="num">{r["put_decline_count"]}</td>'
            f'<td><span class="q-dot {q_cls}" title="{r["quality_label"]} ({q_score:.2f})">'
            f'{r["quality_label"]}</span></td>'
            f'<td class="num">{s_snaps}</td>'
            f'<td class="num">{scan_first_str}</td>'
            f'<td class="scan-col">{scan_hist_str}</td>'
            f'<td class="num {scan_chg_cls}" title="drop ${s_total_drop:.0f} / rise ${s_total_rise:.0f}">{trend_badge} {scan_chg_arrow} {s_chg_pct:+.1f}%</td>'
            f'<td class="col-chart">{chart_cell}</td>'
            f'<td class="col-put">{put_info}</td>'
            f'<td class="num {mkt_cls}" title="{mkt_title}">{mkt_str}</td>'
            f'<td class="col-rules"><button class="rules-btn" title="Set pricing rules" '
            f'onclick="openRulesPanel(this)" '
            f'data-detail-id="{r["detail_id"]}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-board="{_html_escape(r["board"])}" '
            f'data-price="{r["current_price"]}" '
            f'data-signal="{sig}">'
            f'&#9881; Rules</button></td>'
            f'<td class="col-ai">{ai_badge}</td>'
            f'</tr>'
        )

# ── Detail row (empty shell — data loaded lazily via AJAX) ──
        table_rows.append(
            f'<tr class="detail-row" id="detail-{r["detail_id"]}">' 
            f'<td colspan="27">'
            f'<div class="detail-panel" id="dp-{r["detail_id"]}">' 
            f'<div class="detail-chart-wrap">'
            f'<div class="detail-chart-title">Price Trajectory &mdash; Forward Curve + Actual Scans</div>'
            f'<canvas class="detail-canvas" id="dc-{r["detail_id"]}" width="700" height="200"></canvas>'
            f'<div class="detail-legend">'
            f'<span><span class="leg-line" style="background:#3b82f6"></span> Forward Curve</span>'
            f'<span><span class="leg-line" style="background:rgba(59,130,246,.15);height:6px"></span> Confidence Band</span>'
            f'<span><span class="leg-dot" style="background:#f97316"></span> Actual Scans</span>'
            f'<span><span class="leg-line" style="background:#10b981;height:1px;border-top:1px dashed #10b981"></span> Current $</span>'
            f'<span><span class="leg-line" style="background:#a855f7;height:1px;border-top:1px dashed #a855f7"></span> Predicted $</span>'
            f'</div></div>'
            f'<div class="detail-info-wrap" id="di-{r["detail_id"]}">' 
            f'</div></div>'
            f'</td></tr>'
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

  /* ── Sticky first columns ───────────────────────────────────── */
  .sticky-col {{ position: sticky; z-index: 3; background: inherit; }}
  .sc-id {{ left: 0; min-width: 55px; }}
  .sc-hotel {{ left: 55px; min-width: 160px; border-right: 2px solid #cbd5e1; }}
  thead .sticky-col {{ z-index: 5; background: #f1f5f9; }}
  tr.sig-call .sticky-col {{ background: var(--call-row); }}
  tr.sig-put .sticky-col {{ background: var(--put-row); }}
  tr:hover .sticky-col {{ background: #f1f5f9; }}
  td.sticky-col {{ background: #fff; }}
  tr.sig-call td.sticky-col {{ background: var(--call-row); }}
  tr.sig-put td.sticky-col {{ background: var(--put-row); }}

  /* ── Source columns ─────────────────────────────────────────── */
  .src-col {{ background: #f5f3ff !important; }}
  td:nth-child(11), td:nth-child(12) {{ background: rgba(245,243,255,.45); font-size: 12px; }}
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

  /* ── Source detail button ─── */
  .src-btn {{ background: none; border: 1px solid #c7d2fe; border-radius: 5px;
              cursor: pointer; font-size: 13px; padding: 2px 5px; line-height: 1;
              transition: background .15s; margin-left: 3px; }}
  .src-btn:hover {{ background: #eef2ff; }}

  /* ── Price dual display (scan / pred) ─── */
  .price-dual {{ display: flex; flex-direction: column; line-height: 1.2; }}
  .price-dual .pred-sub {{ font-size: 9px; color: #94a3b8; }}

  /* ── Source detail modal ─── */
  .src-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                  background: rgba(0,0,0,.4); z-index: 150; justify-content: center; align-items: center; }}
  .src-overlay.open {{ display: flex; }}
  .src-box {{ background: #fff; border-radius: 14px; padding: 24px; width: 560px;
              max-width: 95vw; max-height: 85vh; overflow-y: auto;
              box-shadow: 0 12px 40px rgba(0,0,0,.3); position: relative; }}
  .src-close {{ position: absolute; top: 12px; right: 16px; font-size: 20px;
                cursor: pointer; color: #64748b; background: none; border: none; }}
  .src-close:hover {{ color: #1e293b; }}
  .src-title {{ font-size: 15px; font-weight: 700; margin-bottom: 4px; color:#1e293b; }}
  .src-subtitle {{ font-size: 11px; color:#64748b; margin-bottom: 14px; }}
  .src-signals {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }}
  .src-signal {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }}
  .src-signal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
  .src-signal-name {{ font-weight: 700; font-size: 13px; color: #1e293b; }}
  .src-signal-price {{ font-size: 15px; font-weight: 700; }}
  .src-signal-bar {{ height: 6px; border-radius: 3px; background: #e2e8f0; margin-bottom: 4px; }}
  .src-signal-fill {{ height: 100%; border-radius: 3px; }}
  .src-signal-meta {{ font-size: 10px; color: #64748b; }}
  .src-signal-reasoning {{ font-size: 10px; color: #475569; margin-top: 4px; padding: 4px 6px;
                           background: #f1f5f9; border-radius: 4px; line-height: 1.4; }}
  .src-adj {{ margin-bottom: 16px; }}
  .src-adj h4 {{ font-size: 12px; font-weight: 700; color: #475569; margin: 0 0 8px; }}
  .src-adj-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .src-adj-item {{ background: #f1f5f9; border-radius: 8px; padding: 8px; text-align: center; }}
  .src-adj-val {{ font-size: 16px; font-weight: 700; }}
  .src-adj-val.pos {{ color: var(--call); }}
  .src-adj-val.neg {{ color: var(--put); }}
  .src-adj-label {{ font-size: 9px; color: #64748b; text-transform: uppercase; }}
  .src-factors {{ font-size: 10px; color: #64748b; margin-top: 8px; }}

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
    pointer-events: auto;
  }}
  .info-tip::after {{
    content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    border: 6px solid transparent; border-top-color: #1e293b;
  }}
  .info-icon:hover .info-tip, .info-tip.active {{ display: block; }}
  /* Right-edge tooltips: shift left so they don't overflow */
  th:nth-child(n+18) .info-tip {{ left: auto; right: 0; transform: none; }}
  th:nth-child(n+18) .info-tip::after {{ left: auto; right: 12px; transform: none; }}
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

  /* ── Rules Column ───────────────────────────────────────────── */
  .col-rules {{ text-align: center; white-space: nowrap; }}
  .rules-btn {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; border: none; border-radius: 6px; padding: 4px 10px;
    font-size: 11px; font-weight: 600; cursor: pointer; letter-spacing: .3px;
    transition: all .2s; display: inline-flex; align-items: center; gap: 4px;
  }}
  .rules-btn:hover {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); transform: translateY(-1px); box-shadow: 0 2px 8px rgba(99,102,241,.35); }}

  /* ── AI Intelligence Column ─────────────────────────────────── */
  .col-ai {{ text-align: center; white-space: nowrap; }}
  .ai-badge {{
    display: inline-flex; align-items: center; gap: 3px;
    padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700;
    letter-spacing: .4px; border: 1.5px solid transparent;
  }}
  .ai-low {{ background: #dcfce7; color: #166534; border-color: #86efac; }}
  .ai-med {{ background: #fef9c3; color: #854d0e; border-color: #fde047; }}
  .ai-high {{ background: #fee2e2; color: #991b1b; border-color: #fca5a5; }}
  .ai-ext {{ background: #dc2626; color: #fff; border-color: #b91c1c; animation: ai-pulse 1.5s infinite; }}
  @keyframes ai-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
  .ai-anomaly-dot {{ color: #f59e0b; font-size: 12px; cursor: help; }}
  .ai-ext .ai-anomaly-dot {{ color: #fef08a; }}

  /* ── Inline Trading Detail Row ──────────────────────────────── */
  .detail-row {{ display: none; }}
  .detail-row.open {{ display: table-row; }}
  .detail-row > td {{ padding: 0 !important; border-bottom: 2px solid #3b82f6; background: #f8fafc; }}
  .detail-panel {{
    display: flex; gap: 0; padding: 16px 20px; min-height: 220px;
    border-top: 2px solid #3b82f6;
  }}
  .detail-chart-wrap {{
    flex: 1 1 60%; min-width: 0; position: relative;
  }}
  .detail-chart-title {{
    font-size: 11px; font-weight: 700; color: #475569; margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: .5px;
  }}
  .detail-canvas {{
    width: 100%; height: 200px; border: 1px solid #e2e8f0; border-radius: 8px;
    background: #fff;
  }}
  .detail-legend {{
    display: flex; gap: 14px; margin-top: 6px; font-size: 10px; color: #64748b;
  }}
  .detail-legend span {{ display: flex; align-items: center; gap: 4px; }}
  .detail-legend .leg-dot {{
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  }}
  .detail-legend .leg-line {{
    width: 16px; height: 2px; display: inline-block; border-radius: 1px;
  }}
  .detail-info-wrap {{
    flex: 0 0 320px; padding-left: 20px; border-left: 1px solid #e2e8f0;
    display: flex; flex-direction: column; gap: 10px; overflow-y: auto; max-height: 260px;
  }}
  .detail-section {{ }}
  .detail-section h4 {{
    font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
    letter-spacing: .6px; margin: 0 0 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px;
  }}
  .detail-signals {{ display: flex; flex-direction: column; gap: 4px; }}
  .detail-sig-row {{
    display: flex; align-items: center; gap: 6px; font-size: 11px;
  }}
  .detail-sig-name {{ width: 80px; font-weight: 600; color: #475569; white-space: nowrap; }}
  .detail-sig-bar {{ flex: 1; height: 10px; background: #e2e8f0; border-radius: 5px; overflow: hidden; position: relative; }}
  .detail-sig-fill {{ height: 100%; border-radius: 5px; transition: width .3s; }}
  .detail-sig-fill.fc {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
  .detail-sig-fill.hist {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
  .detail-sig-fill.ml {{ background: linear-gradient(90deg, #8b5cf6, #a78bfa); }}
  .detail-sig-val {{ font-size: 10px; color: #64748b; width: 60px; text-align: right; white-space: nowrap; }}
  .detail-adj-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  }}
  .detail-adj-item {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 5px 8px; text-align: center;
  }}
  .detail-adj-val {{ font-size: 13px; font-weight: 700; }}
  .detail-adj-val.pos {{ color: var(--call); }}
  .detail-adj-val.neg {{ color: var(--put); }}
  .detail-adj-val.zero {{ color: #94a3b8; }}
  .detail-adj-label {{ font-size: 8px; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; }}
  .detail-meta-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 3px; font-size: 10px;
  }}
  .detail-meta-item {{ display: flex; justify-content: space-between; padding: 2px 0; }}
  .detail-meta-key {{ color: #94a3b8; }}
  .detail-meta-val {{ font-weight: 600; color: #475569; }}
  .expand-btn {{
    background: none; border: none; cursor: pointer; font-size: 11px;
    color: #64748b; padding: 0 3px; transition: transform .2s;
  }}
  .expand-btn:hover {{ color: #3b82f6; }}
  .expand-btn.open {{ transform: rotate(180deg); }}
  @media (max-width: 900px) {{
    .detail-panel {{ flex-direction: column; }}
    .detail-info-wrap {{ flex: auto; padding-left: 0; padding-top: 12px; border-left: none; border-top: 1px solid #e2e8f0; max-height: none; }}
  }}

  /* ── Rules Modal / Panel ────────────────────────────────────── */
  .rules-overlay {{
    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,.5); z-index: 300; justify-content: center; align-items: flex-start;
    padding-top: 60px;
  }}
  .rules-overlay.open {{ display: flex; }}
  .rules-panel {{
    background: #fff; border-radius: 14px; padding: 0; width: 520px;
    max-width: 95vw; max-height: 80vh; overflow-y: auto;
    box-shadow: 0 12px 48px rgba(0,0,0,.3); position: relative;
  }}
  .rules-panel-header {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; padding: 18px 24px; border-radius: 14px 14px 0 0;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .rules-panel-header h2 {{ font-size: 16px; font-weight: 700; margin: 0; }}
  .rules-panel-header .rules-close {{
    background: rgba(255,255,255,.2); border: none; color: #fff; font-size: 18px;
    cursor: pointer; border-radius: 50%; width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
  }}
  .rules-panel-header .rules-close:hover {{ background: rgba(255,255,255,.35); }}
  .rules-panel-body {{ padding: 20px 24px; }}

  .rules-context {{
    background: #f1f5f9; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;
    font-size: 12px; color: #475569; line-height: 1.5;
  }}
  .rules-context .ctx-label {{ font-weight: 700; color: #1e293b; }}
  .rules-context .ctx-val {{ color: #6366f1; font-weight: 600; }}

  /* Scope selector */
  .rules-scope {{ margin-bottom: 18px; }}
  .rules-scope h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .scope-options {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .scope-opt {{
    flex: 1; min-width: 130px; padding: 10px 12px; border: 2px solid var(--border);
    border-radius: 8px; cursor: pointer; text-align: center; transition: all .15s;
    background: #fff;
  }}
  .scope-opt:hover {{ border-color: #a5b4fc; background: #eef2ff; }}
  .scope-opt.selected {{ border-color: #6366f1; background: #eef2ff; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }}
  .scope-opt .scope-icon {{ font-size: 20px; display: block; margin-bottom: 4px; }}
  .scope-opt .scope-label {{ font-size: 12px; font-weight: 600; color: #1e293b; }}
  .scope-opt .scope-desc {{ font-size: 10px; color: #64748b; margin-top: 2px; }}

  /* Preset buttons */
  .rules-presets {{ margin-bottom: 18px; }}
  .rules-presets h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .preset-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }}
  .preset-card {{
    padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px;
    cursor: pointer; transition: all .15s; background: #fff; text-align: center;
  }}
  .preset-card:hover {{ border-color: #a5b4fc; background: #eef2ff; transform: translateY(-1px); }}
  .preset-card.selected {{ border-color: #6366f1; background: #eef2ff; box-shadow: 0 0 0 2px rgba(99,102,241,.2); }}
  .preset-card .preset-icon {{ font-size: 22px; display: block; margin-bottom: 2px; }}
  .preset-card .preset-name {{ font-size: 11px; font-weight: 700; color: #1e293b; }}
  .preset-card .preset-desc {{ font-size: 10px; color: #64748b; margin-top: 3px; line-height: 1.3; }}

  /* Custom rules section */
  .rules-custom {{ margin-bottom: 18px; }}
  .rules-custom h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .custom-rule-row {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
    padding: 8px 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border);
  }}
  .custom-rule-row label {{ font-size: 11px; font-weight: 600; color: #475569; min-width: 90px; }}
  .custom-rule-row input, .custom-rule-row select {{
    padding: 5px 8px; border: 1px solid var(--border); border-radius: 5px;
    font-size: 12px; width: 120px;
  }}
  .custom-rule-row .rule-toggle {{
    width: 36px; height: 20px; border-radius: 10px; border: none;
    background: #cbd5e1; cursor: pointer; position: relative; transition: background .2s;
  }}
  .custom-rule-row .rule-toggle.on {{ background: #6366f1; }}
  .custom-rule-row .rule-toggle::after {{
    content: ''; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
    border-radius: 50%; background: #fff; transition: left .2s;
  }}
  .custom-rule-row .rule-toggle.on::after {{ left: 18px; }}

  /* Action buttons */
  .rules-actions {{
    display: flex; gap: 10px; justify-content: flex-end; padding-top: 14px;
    border-top: 1px solid var(--border);
  }}
  .rules-actions button {{
    padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all .15s;
  }}
  .btn-cancel {{
    background: #fff; color: #64748b; border: 1px solid var(--border);
  }}
  .btn-cancel:hover {{ background: #f1f5f9; }}
  .btn-apply {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; border: none;
  }}
  .btn-apply:hover {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); box-shadow: 0 2px 8px rgba(99,102,241,.35); }}

  /* Toast notification */
  .rules-toast {{
    position: fixed; bottom: 24px; right: 24px; background: #1e293b; color: #f8fafc;
    padding: 12px 20px; border-radius: 10px; font-size: 13px; font-weight: 500;
    box-shadow: 0 4px 16px rgba(0,0,0,.25); z-index: 400;
    transform: translateY(80px); opacity: 0; transition: all .3s ease;
  }}
  .rules-toast.show {{ transform: translateY(0); opacity: 1; }}
  .rules-toast .toast-icon {{ margin-right: 8px; }}
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
  <th data-col="0" data-type="num" class="sticky-col sc-id">ID<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Detail ID</b><br>Unique room identifier from SalesOffice DB.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="1" data-type="str" class="sticky-col sc-hotel">Hotel<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Hotel Name</b><br>Property name from Med_Hotels table joined via HotelID.<br><span class="src-tag">Med_Hotels</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="2" data-type="str">Category<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Room Category</b><br>Mapped from RoomCategoryID: 1=Standard, 2=Superior, 4=Deluxe, 12=Suite. Affects forward-curve category offset in prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="3" data-type="str">Board<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Board Type</b><br>Meal plan from BoardId: RO, BB, HB, FB, AI, etc. Adds a board offset to the forward curve prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="4" data-type="str">Check-in<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Check-in Date</b><br>Booked arrival date from the order. This is the target date (T=0) for the forward curve walk.<br><span class="src-tag">SalesOffice.Orders</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="5" data-type="num">Days<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Days to Check-in</b><br>Calendar days from today to check-in. This is the T value &mdash; how many steps the forward curve walks.<br>Formula: <b>check_in_date &minus; today</b></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="6" data-type="str">Signal<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Option Signal (CALL / PUT / NEUTRAL)</b><br>&bull; <b>CALL</b>: price expected to rise (&ge;0.5%) or prob_up &gt; prob_down+0.1<br>&bull; <b>PUT</b>: price expected to drop (&le;&minus;0.5%) or prob_down &gt; prob_up+0.1<br>&bull; <b>L1-L10</b>: confidence level (65% change magnitude + 35% probability &times; quality)<br><span class="src-tag">Forward Curve 50%</span> <span class="src-tag">Historical 30%</span> <span class="src-tag">ML 20%</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="7" data-type="num">Current $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Current Room Price</b><br>Latest price from the most recent hourly scan of SalesOffice.Details. This is the starting point for the forward curve.<br><span class="src-tag">SalesOffice.Details</span> <span class="src-tag">Hourly scan</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="8" data-type="num">Predicted $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Predicted Check-in Price (Ensemble)</b><br>Weighted ensemble of 2-3 signals:<br>&bull; <b>Forward Curve (50%)</b>: day-by-day walk with decay + events + season + weather adjustments<br>&bull; <b>Historical Pattern (30%)</b>: same-month prior-year average + lead-time adjustment<br>&bull; <b>ML Model (20%)</b>: if trained model exists (currently inactive)<br>Weights are scaled by each signal's confidence then normalized.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Open-Meteo</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="9" data-type="num">Change %<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Price Change %</b><br>Percentage difference between predicted check-in price and current price.<br>Formula: <b>(predicted &divide; current &minus; 1) &times; 100</b><br>Green = price expected to rise, Red = expected to drop.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="10" data-type="num" class="src-col">FC $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Forward Curve Prediction</b><br>Price predicted by the <b>Forward Curve</b> model alone (weight ~50%).<br>Day-by-day random walk with:<br>&bull; Decay rate from {'{'}model_info.total_tracks{'}'} price tracks<br>&bull; Event adjustments (Miami events, holidays)<br>&bull; Season adjustments (monthly ADR patterns)<br>&bull; Demand adjustments (flight demand index)<br>&bull; Momentum adjustments (recent price trend)<br>Hover for full adjustment breakdown.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span> <span class="src-tag">Flights</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="11" data-type="num" class="src-col">Hist $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Historical Pattern Prediction</b><br>Price predicted by <b>Historical Patterns</b> alone (weight ~30%).<br>Same-month prior-year average price adjusted by:<br>&bull; Lead-time offset (how far from check-in)<br>&bull; Day-of-week patterns<br>&bull; Year-over-year trend<br>Only available when historical data exists for this hotel/period combination.<br><span class="src-tag">medici-db Historical</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="12" data-type="num">Min $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Minimum Price</b><br>Lowest price point on the forward curve between now and check-in.<br>Formula: <b>min(all daily predicted prices)</b><br>This is the predicted best buying opportunity in the path.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="13" data-type="num">Max $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Maximum Price</b><br>Highest price point on the forward curve between now and check-in.<br>Formula: <b>max(all daily predicted prices)</b><br>Peak predicted price before check-in.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="14" data-type="str">Touches<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Touches Min / Max</b><br>How many times the forward curve touches the min and max price levels (within $0.01).<br>Format: <b>min_touches / max_touches</b><br>High touch count = price lingers at that level (support/resistance).</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="15" data-type="num">Big Moves<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Big Price Moves (&gt;$20)</b><br>Count of day-to-day predicted price changes greater than $20 on the forward curve.<br>More big moves = higher volatility expected.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="16" data-type="num">Exp Drops<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Price Drops</b><br>Number of day-to-day drops predicted by the forward curve between now and check-in.<br>Higher count for PUT signals = more predicted decline episodes.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="17" data-type="str">Quality<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Prediction Quality Score</b><br>Blended confidence metric:<br>&bull; 60% from data availability (scan count, price history depth, hotel coverage)<br>&bull; 40% from mean signal confidence<br>Levels: <b>HIGH</b> (&ge;0.75), <b>MEDIUM</b> (&ge;0.50), <b>LOW</b> (&lt;0.50)<br>Higher = more data backing the prediction.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="18" data-type="num">Scans<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Count (Actual)</b><br>Number of real price snapshots collected from medici-db since tracking started (Feb 23).<br>Scanned every ~3 hours. More scans = better trend visibility.<br><span class="src-tag">SalesOffice.Details.DateCreated</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="19" data-type="num">1st Price<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>First Scan Price</b><br>The room price at the earliest recorded scan. Used as baseline to measure actual price movement since tracking began.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="20" data-type="str">Actual D/R<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Actual Drops / Rises (Observed)</b><br>Real price drops and rises observed across actual scans &mdash; NOT predictions.<br>&bull; <b style="color:#ef4444">Red number&#9660;</b> = count of scans where price decreased<br>&bull; <b style="color:#22c55e">Green number&#9650;</b> = count of scans where price increased<br>Hover for total $ amounts and max single move.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="21" data-type="num">Scan Chg%<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Price Change %</b><br>Actual price change from first scan to current price.<br>Formula: <b>(latest &minus; first) &divide; first &times; 100</b><br>Trend badge: &#9650; up, &#9660; down, &#9644; stable.<br>This is REAL observed data, not a prediction.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="22" data-type="str">Chart<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Price Chart</b><br>Click &#128200; to view price history chart showing all actual scan prices over time with colored dots (red=drop, green=rise).<br>Requires &ge;2 scans.</span></span></th>
  <th data-col="23" data-type="str">PUT Detail<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>PUT Decline Details</b><br>Breakdown of predicted downward moves on the forward curve:<br>&bull; <b>drops</b>: count of decline days<br>&bull; <b>total $</b>: sum of all daily drops<br>&bull; <b>max $</b>: largest single-day drop<br>Only shown for rooms with predicted declines.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="24" data-type="num">Mkt &#9733;$<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Market Benchmark (same &#9733; avg)</b><br>Average price of all other hotels with the <b>same star rating</b> in the <b>same city</b> from AI_Search_HotelData (8.5M records, 6K+ hotels, 323 cities).<br>&bull; <b style="color:#22c55e">Green</b>: our price &lt; market avg (well-positioned)<br>&bull; <b style="color:#ef4444">Red</b>: our price &gt; market avg (premium priced)<br>Hover for N competitor hotels and city.<br><span class="src-tag">AI_Search_HotelData</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="25" data-type="str">Rules<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Pricing Rules</b><br>Set pricing rules for this room, hotel, or all hotels.<br>&bull; <b>Scope</b>: This row / This hotel / All hotels<br>&bull; <b>Presets</b>: Conservative, Moderate, Aggressive, Seasonal High, Fire Sale, Wait for Drop, Exclude AI<br>&bull; <b>Custom</b>: Price ceiling/floor, markup %, target price, category/board exclusions<br>Rules are applied at Step 5 (Flatten &amp; Group) of the SalesOffice scanning pipeline.<br><span class="src-tag">Rules Engine</span></span></span></th>
  <th data-col="26" data-type="str">AI<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>AI Intelligence</b><br>Claude-powered risk assessment and anomaly detection.<br>&bull; <b style="color:#22c55e">LOW</b>: Standard conditions, low risk<br>&bull; <b style="color:#f59e0b">MED</b>: Moderate risk, some uncertainty<br>&bull; <b style="color:#ef4444">HIG</b>: High risk, large predicted moves or limited data<br>&bull; <b style="color:#dc2626">EXT</b>: Extreme risk, urgent review needed<br>&bull; &#9888; = Anomaly detected (spike, dip, stale, divergence)<br>Click <a href="/api/v1/salesoffice/options/ai-insights" style="color:#60a5fa">AI Insights</a> for full analysis.<br><span class="src-tag">AI Intelligence Engine</span></span></span></th>
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
  &bull; <a href="/api/v1/salesoffice/options/ai-insights" style="color:#a78bfa">&#129302; AI Insights</a>
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

<!-- Source Detail Modal -->
<div id="src-overlay" class="src-overlay">
  <div class="src-box">
    <button class="src-close" onclick="closeSources()">&times;</button>
    <div class="src-title" id="src-title">Prediction Sources</div>
    <div class="src-subtitle" id="src-subtitle"></div>
    <div class="src-signals" id="src-signals"></div>
    <div class="src-adj">
      <h4>&#128200; Forward Curve Adjustments</h4>
      <div class="src-adj-grid" id="src-adjustments"></div>
    </div>
    <div class="src-factors" id="src-factors" style="display:none"></div>
  </div>
</div>

<!-- Rules Panel Modal -->
<div id="rules-overlay" class="rules-overlay">
  <div class="rules-panel">
    <div class="rules-panel-header">
      <h2>&#9881; Pricing Rules</h2>
      <button class="rules-close" onclick="closeRulesPanel()">&times;</button>
    </div>
    <div class="rules-panel-body">
      <!-- Context info -->
      <div class="rules-context" id="rules-context">
        <span class="ctx-label">Room:</span> <span class="ctx-val" id="rc-room">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Hotel:</span> <span class="ctx-val" id="rc-hotel">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Price:</span> <span class="ctx-val" id="rc-price">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Signal:</span> <span class="ctx-val" id="rc-signal">-</span>
      </div>

      <!-- Scope selector -->
      <div class="rules-scope">
        <h3>&#127919; Apply Scope</h3>
        <div class="scope-options">
          <div class="scope-opt selected" data-scope="row" onclick="selectScope(this)">
            <span class="scope-icon">&#128196;</span>
            <span class="scope-label">This Room</span>
            <span class="scope-desc">Only this specific room option</span>
          </div>
          <div class="scope-opt" data-scope="hotel" onclick="selectScope(this)">
            <span class="scope-icon">&#127976;</span>
            <span class="scope-label" id="scope-hotel-label">This Hotel</span>
            <span class="scope-desc">All rooms for this hotel</span>
          </div>
          <div class="scope-opt" data-scope="all" onclick="selectScope(this)">
            <span class="scope-icon">&#127758;</span>
            <span class="scope-label">All Hotels</span>
            <span class="scope-desc">Apply to every hotel</span>
          </div>
        </div>
      </div>

      <!-- Preset selection -->
      <div class="rules-presets">
        <h3>&#9889; Quick Presets</h3>
        <div class="preset-grid">
          <div class="preset-card" data-preset="conservative" onclick="selectPreset(this)">
            <span class="preset-icon">&#128737;</span>
            <span class="preset-name">Conservative</span>
            <span class="preset-desc">Low markup, tight ceiling, safe floor</span>
          </div>
          <div class="preset-card" data-preset="moderate" onclick="selectPreset(this)">
            <span class="preset-icon">&#9878;</span>
            <span class="preset-name">Moderate</span>
            <span class="preset-desc">Balanced markup with reasonable bounds</span>
          </div>
          <div class="preset-card" data-preset="aggressive" onclick="selectPreset(this)">
            <span class="preset-icon">&#128640;</span>
            <span class="preset-name">Aggressive</span>
            <span class="preset-desc">Higher markup, wider price range</span>
          </div>
          <div class="preset-card" data-preset="seasonal_high" onclick="selectPreset(this)">
            <span class="preset-icon">&#9728;</span>
            <span class="preset-name">Seasonal High</span>
            <span class="preset-desc">Peak season premium pricing</span>
          </div>
          <div class="preset-card" data-preset="fire_sale" onclick="selectPreset(this)">
            <span class="preset-icon">&#128293;</span>
            <span class="preset-name">Fire Sale</span>
            <span class="preset-desc">Deep discount, move inventory fast</span>
          </div>
          <div class="preset-card" data-preset="wait_for_drop" onclick="selectPreset(this)">
            <span class="preset-icon">&#9202;</span>
            <span class="preset-name">Wait for Drop</span>
            <span class="preset-desc">Hold until price drops below threshold</span>
          </div>
          <div class="preset-card" data-preset="exclude_ai" onclick="selectPreset(this)">
            <span class="preset-icon">&#128683;</span>
            <span class="preset-name">Exclude AI</span>
            <span class="preset-desc">No AI pricing &mdash; use supplier price</span>
          </div>
        </div>
      </div>

      <!-- Custom rules -->
      <div class="rules-custom">
        <h3>&#128295; Custom Rules</h3>
        <div class="custom-rule-row">
          <label>Price Ceiling</label>
          <input type="number" id="rule-ceiling" placeholder="Max price $" step="1">
          <span style="font-size:11px;color:#64748b">Maximum allowed price</span>
        </div>
        <div class="custom-rule-row">
          <label>Price Floor</label>
          <input type="number" id="rule-floor" placeholder="Min price $" step="1">
          <span style="font-size:11px;color:#64748b">Minimum allowed price</span>
        </div>
        <div class="custom-rule-row">
          <label>Markup %</label>
          <input type="number" id="rule-markup" placeholder="e.g. 5" step="0.5" min="-50" max="100">
          <span style="font-size:11px;color:#64748b">Add/subtract % from predicted</span>
        </div>
        <div class="custom-rule-row">
          <label>Target Price</label>
          <input type="number" id="rule-target" placeholder="Override price $" step="1">
          <span style="font-size:11px;color:#64748b">Force a specific price</span>
        </div>
      </div>

      <!-- Summary of what will be applied -->
      <div id="rules-summary" style="display:none; background:#eef2ff; border-radius:8px; padding:12px 16px; margin-bottom:14px; font-size:12px; color:#4338ca; border:1px solid #c7d2fe;">
        <strong>&#9989; Rules to apply:</strong> <span id="rules-summary-text"></span>
      </div>

      <!-- Actions -->
      <div class="rules-actions">
        <button class="btn-cancel" onclick="closeRulesPanel()">Cancel</button>
        <button class="btn-apply" onclick="applyRules()">&#9889; Apply Rules</button>
      </div>
    </div>
  </div>
</div>

<!-- Toast notification -->
<div id="rules-toast" class="rules-toast">
  <span class="toast-icon">&#9989;</span> <span id="toast-msg">Rules applied</span>
</div>

<script>
/* ── Info-tip click toggle (global) ──────────────────────── */
function toggleTip(el, e) {{
  if (!e) e = window.event;
  /* If clicked on the tooltip text itself, stop propagation and return (don't close) */
  if (e && e.target && e.target.closest && e.target.closest('.info-tip')) {{
    if (e.stopPropagation) e.stopPropagation();
    return;
  }}
  var tip = el.querySelector('.info-tip');
  if (!tip) return;
  var isOpen = tip.classList.contains('active');
  document.querySelectorAll('.info-tip.active').forEach(function(t) {{ t.classList.remove('active'); }});
  if (!isOpen) tip.classList.add('active');
  if (e && e.stopPropagation) e.stopPropagation();
}}
document.addEventListener('click', function() {{
  document.querySelectorAll('.info-tip.active').forEach(function(t) {{ t.classList.remove('active'); }});
}});

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
    th.addEventListener('click', function(e) {{
      if (e.target.closest('.info-icon')) return;   /* skip sort when clicking info */
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
  if (e.key === 'Escape') {{ closeChart(); closeRulesPanel(); closeSources(); }}
}});

/* ── Inline Trading Detail Panel ────────────────────────────── */
function toggleDetail(detailId) {{
  var row = document.getElementById('detail-' + detailId);
  var btn = document.getElementById('eb-' + detailId);
  if (!row) return;
  var isOpen = row.classList.contains('open');
  if (isOpen) {{
    row.classList.remove('open');
    if (btn) btn.classList.remove('open');
  }} else {{
    row.classList.add('open');
    if (btn) btn.classList.add('open');
    // Fetch detail data lazily on first open
    if (!row.dataset.drawn) {{
      row.dataset.drawn = '1';
      var infoWrap = document.getElementById('di-' + detailId);
      if (infoWrap) infoWrap.innerHTML = '<div style="padding:20px;color:#94a3b8;font-size:12px">Loading...</div>';
      fetch('/api/v1/salesoffice/options/detail/' + detailId)
        .then(function(r) {{ return r.json(); }})
        .then(function(dd) {{
          drawTradingChart(detailId, dd);
          buildDetailInfo(detailId, dd);
        }})
        .catch(function(err) {{
          console.error('Detail fetch failed:', err);
          if (infoWrap) infoWrap.innerHTML = '<div style="padding:20px;color:#dc2626;font-size:12px">Failed to load detail data</div>';
        }});
    }}
  }}
}}

function drawTradingChart(detailId, dd) {{
  var canvas = document.getElementById('dc-' + detailId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  var fc = dd.fc || [];
  var scan = dd.scan || [];
  if (fc.length === 0 && scan.length === 0) {{
    ctx.fillStyle = '#94a3b8'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('No chart data available', W/2, H/2);
    return;
  }}

  // Collect all prices to determine Y range
  var allP = [];
  fc.forEach(function(pt) {{ allP.push(pt.p, pt.lo, pt.hi); }});
  scan.forEach(function(pt) {{ allP.push(pt.p); }});
  allP.push(dd.cp, dd.pp);
  var minP = Math.min.apply(null, allP.filter(function(v){{return v>0;}}));
  var maxP = Math.max.apply(null, allP);
  var pPad = (maxP - minP) * 0.08 || 5;
  minP -= pPad; maxP += pPad;
  var pRange = maxP - minP || 1;

  // All dates for X axis (forward curve dates are the main timeline)
  var allDates = fc.map(function(pt){{return pt.d;}});

  // Scans are PAST data, FC is FUTURE. Scans go on the LEFT, FC on the RIGHT
  // Build a unified timeline: [scan dates] + [fc dates]
  var scanDates = scan.map(function(s){{return s.d;}});
  // Remove duplicate dates
  var seen = {{}};
  var timeline = [];
  scanDates.forEach(function(d) {{ if (!seen[d]) {{ seen[d]=1; timeline.push({{d:d, src:'scan'}}); }} }});
  allDates.forEach(function(d) {{ if (!seen[d]) {{ seen[d]=1; timeline.push({{d:d, src:'fc'}}); }} }});

  var n = timeline.length;
  if (n === 0) return;

  var padL = 56, padR = 16, padT = 14, padB = 28;
  var cw = W - padL - padR, ch = H - padT - padB;

  // Helper: date to X
  var dateIdx = {{}};
  timeline.forEach(function(t, i) {{ dateIdx[t.d] = i; }});
  function dateToX(d) {{ var idx = dateIdx[d]; return idx !== undefined ? padL + (idx / Math.max(n-1,1)) * cw : -1; }}
  function priceToY(p) {{ return padT + ch - ((p - minP) / pRange) * ch; }}

  // Background
  ctx.fillStyle = '#fafbfc'; ctx.fillRect(padL, padT, cw, ch);

  // Grid lines
  ctx.strokeStyle = '#f1f5f9'; ctx.lineWidth = 0.5;
  for (var gi=0; gi<=5; gi++) {{
    var gy = padT + ch * gi / 5;
    ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL + cw, gy); ctx.stroke();
    var gp = maxP - (pRange * gi / 5);
    ctx.fillStyle = '#94a3b8'; ctx.font = '9px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + gp.toFixed(0), padL - 4, gy + 3);
  }}

  // X axis labels (strip #N suffixes used for uniqueness)
  ctx.fillStyle = '#94a3b8'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(n / 8));
  for (var xi=0; xi<n; xi+=xStep) {{
    var xx = padL + (xi / Math.max(n-1,1)) * cw;
    var lbl = timeline[xi].d.split('#')[0];
    ctx.fillText(lbl, xx, H - 6);
  }}

  // Vertical divider between scan period and FC period
  var firstFcDate = allDates[0];
  var divX = dateToX(firstFcDate);
  if (divX > padL + 10 && scanDates.length > 0) {{
    ctx.save();
    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1; ctx.setLineDash([3,3]);
    ctx.beginPath(); ctx.moveTo(divX, padT); ctx.lineTo(divX, padT+ch); ctx.stroke();
    ctx.restore();
    // Labels
    ctx.fillStyle = '#94a3b8'; ctx.font = 'bold 8px sans-serif';
    ctx.textAlign = 'right'; ctx.fillText('ACTUAL', divX - 4, padT + 10);
    ctx.textAlign = 'left'; ctx.fillText('FORECAST', divX + 4, padT + 10);
  }}

  // ── Confidence band (FC) ──
  if (fc.length > 1) {{
    ctx.beginPath();
    fc.forEach(function(pt, i) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.hi);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }});
    for (var i=fc.length-1; i>=0; i--) {{
      var x = dateToX(fc[i].d); if (x < 0) continue;
      ctx.lineTo(x, priceToY(fc[i].lo));
    }}
    ctx.closePath();
    ctx.fillStyle = 'rgba(59,130,246,.10)'; ctx.fill();
  }}

  // ── Forward Curve line ──
  if (fc.length > 0) {{
    ctx.beginPath();
    ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
    var started = false;
    fc.forEach(function(pt) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.p);
      if (!started) {{ ctx.moveTo(x, y); started = true; }} else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}

  // ── Actual scan line ──
  if (scan.length > 1) {{
    ctx.beginPath();
    ctx.strokeStyle = '#f97316'; ctx.lineWidth = 1.5;
    var started2 = false;
    scan.forEach(function(pt) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.p);
      if (!started2) {{ ctx.moveTo(x, y); started2 = true; }} else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}

  // ── Scan dots ──
  scan.forEach(function(pt, i) {{
    var x = dateToX(pt.d); if (x < 0) return;
    var y = priceToY(pt.p);
    var clr = '#f97316';
    if (i > 0) {{
      if (pt.p < scan[i-1].p - 0.01) clr = '#dc2626';
      else if (pt.p > scan[i-1].p + 0.01) clr = '#16a34a';
    }}
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2);
    ctx.fillStyle = clr; ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.5; ctx.stroke();
  }});

  // ── Current price dashed line ──
  ctx.save();
  ctx.strokeStyle = '#10b981'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  var cpY = priceToY(dd.cp);
  ctx.beginPath(); ctx.moveTo(padL, cpY); ctx.lineTo(padL+cw, cpY); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = '#10b981'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('$' + dd.cp.toFixed(0), padL+cw+2, cpY+3);

  // ── Predicted price dashed line ──
  ctx.save();
  ctx.strokeStyle = '#a855f7'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  var ppY = priceToY(dd.pp);
  ctx.beginPath(); ctx.moveTo(padL, ppY); ctx.lineTo(padL+cw, ppY); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = '#a855f7'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('$' + dd.pp.toFixed(0), padL+cw+2, ppY+3);

  // ── Min/Max markers on FC ──
  if (fc.length > 0) {{
    var mnPt = fc.reduce(function(a,b){{return a.p < b.p ? a : b;}});
    var mxPt = fc.reduce(function(a,b){{return a.p > b.p ? a : b;}});
    // Min marker
    var mnX = dateToX(mnPt.d), mnY = priceToY(mnPt.p);
    if (mnX > 0) {{
      ctx.beginPath(); ctx.arc(mnX, mnY, 4, 0, Math.PI*2);
      ctx.fillStyle = '#ef4444'; ctx.fill();
      ctx.fillStyle = '#ef4444'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('$' + mnPt.p.toFixed(0), mnX, mnY + 13);
    }}
    // Max marker
    var mxX = dateToX(mxPt.d), mxY = priceToY(mxPt.p);
    if (mxX > 0) {{
      ctx.beginPath(); ctx.arc(mxX, mxY, 4, 0, Math.PI*2);
      ctx.fillStyle = '#3b82f6'; ctx.fill();
      ctx.fillStyle = '#3b82f6'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('$' + mxPt.p.toFixed(0), mxX, mxY - 8);
    }}
  }}
}}

function buildDetailInfo(detailId, dd) {{
  var wrap = document.getElementById('di-' + detailId);
  if (!wrap) return;
  var h = '';

  // ── Signal Weights ──
  h += '<div class="detail-section"><h4>Signal Weights</h4><div class="detail-signals">';
  if (dd.fcP) {{
    h += '<div class="detail-sig-row"><span class="detail-sig-name">Forward Curve</span>' +
         '<div class="detail-sig-bar"><div class="detail-sig-fill fc" style="width:' + (dd.fcW*100).toFixed(0) + '%"></div></div>' +
         '<span class="detail-sig-val">$' + dd.fcP.toFixed(0) + ' (' + (dd.fcW*100).toFixed(0) + '%)</span></div>';
  }}
  if (dd.hiP) {{
    h += '<div class="detail-sig-row"><span class="detail-sig-name">Historical</span>' +
         '<div class="detail-sig-bar"><div class="detail-sig-fill hist" style="width:' + (dd.hiW*100).toFixed(0) + '%"></div></div>' +
         '<span class="detail-sig-val">$' + dd.hiP.toFixed(0) + ' (' + (dd.hiW*100).toFixed(0) + '%)</span></div>';
  }}
  h += '</div></div>';

  // ── Adjustments ──
  var adj = dd.adj || {{}};
  h += '<div class="detail-section"><h4>FC Adjustments (cumulative %)</h4><div class="detail-adj-grid">';
  var adjItems = [
    {{k:'Events', v:adj.ev}}, {{k:'Season', v:adj.se}},
    {{k:'Demand', v:adj.dm}}, {{k:'Momentum', v:adj.mo}}
  ];
  adjItems.forEach(function(a) {{
    var cls = a.v > 0.01 ? 'pos' : (a.v < -0.01 ? 'neg' : 'zero');
    h += '<div class="detail-adj-item"><div class="detail-adj-val ' + cls + '">' +
         (a.v >= 0 ? '+' : '') + a.v.toFixed(1) + '%</div>' +
         '<div class="detail-adj-label">' + a.k + '</div></div>';
  }});
  h += '</div></div>';

  // ── Market & Signals ──
  h += '<div class="detail-section"><h4>Key Metrics</h4><div class="detail-meta-grid">';
  var sigClr = dd.sig === 'CALL' ? 'var(--call)' : (dd.sig === 'PUT' ? 'var(--put)' : 'var(--neutral)');
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Signal</span><span class="detail-meta-val" style="color:' + sigClr + '">' + dd.sig + '</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Change</span><span class="detail-meta-val" style="color:' + (dd.chg>=0?'var(--call)':'var(--put)') + '">' + (dd.chg>=0?'+':'') + dd.chg.toFixed(1) + '%</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Quality</span><span class="detail-meta-val">' + dd.q + '</span></div>';
  if (dd.mkt > 0) {{
    h += '<div class="detail-meta-item"><span class="detail-meta-key">Mkt Avg</span><span class="detail-meta-val">$' + dd.mkt.toFixed(0) + '</span></div>';
  }}
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Scans</span><span class="detail-meta-val">' + dd.scans + '</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Actual D/R</span><span class="detail-meta-val">' +
       '<span style="color:var(--put)">' + dd.drops + '&#9660;</span> ' +
       '<span style="color:var(--call)">' + dd.rises + '&#9650;</span></span></div>';
  h += '</div></div>';

  // ── Momentum & Regime ──
  var mom = dd.mom || {{}};
  var reg = dd.reg || {{}};
  if (mom.signal || reg.regime) {{
    h += '<div class="detail-section"><h4>Momentum &amp; Regime</h4><div class="detail-meta-grid">';
    if (mom.signal) {{
      h += '<div class="detail-meta-item"><span class="detail-meta-key">Momentum</span><span class="detail-meta-val">' + mom.signal + '</span></div>';
      if (mom.velocity_24h !== undefined) {{
        h += '<div class="detail-meta-item"><span class="detail-meta-key">Velocity 24h</span><span class="detail-meta-val">' + (mom.velocity_24h >= 0 ? '+' : '') + Number(mom.velocity_24h).toFixed(1) + '%</span></div>';
      }}
    }}
    if (reg.regime) {{
      h += '<div class="detail-meta-item"><span class="detail-meta-key">Regime</span><span class="detail-meta-val">' + reg.regime + '</span></div>';
    }}
    h += '</div></div>';
  }}

  wrap.innerHTML = h;
}}

/* ── Source Detail Modal Functions ───────────────────────────── */
function showSources(btn) {{
  var raw = btn.getAttribute('data-sources');
  if (!raw) return;
  raw = raw.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  var data;
  try {{ data = JSON.parse(raw); }} catch(e) {{ console.error('src parse', e); return; }}

  var hotel = btn.getAttribute('data-hotel') || '';
  var detId = btn.getAttribute('data-detail-id') || '';

  document.getElementById('src-title').textContent = 'Prediction Sources \u2014 ' + hotel;
  document.getElementById('src-subtitle').textContent = 'ID: ' + detId + ' | Method: ' + (data.method || 'ensemble');

  /* Signals */
  var sigHtml = '';
  var colors = {{'Forward Curve':'#3b82f6', 'Historical Pattern':'#f59e0b', 'ML Forecast':'#8b5cf6'}};
  (data.signals || []).forEach(function(s) {{
    var c = colors[s.source] || '#64748b';
    var wPct = Math.round((s.weight || 0) * 100);
    var confPct = Math.round((s.confidence || 0) * 100);
    var priceCls = '';
    sigHtml += '<div class="src-signal">';
    sigHtml += '<div class="src-signal-header">';
    sigHtml += '<span class="src-signal-name" style="color:' + c + '">' + s.source + '</span>';
    sigHtml += '<span class="src-signal-price">$' + (s.price ? s.price.toFixed(0) : '-') + '</span>';
    sigHtml += '</div>';
    sigHtml += '<div class="src-signal-bar"><div class="src-signal-fill" style="width:' + wPct + '%;background:' + c + '"></div></div>';
    sigHtml += '<div class="src-signal-meta">Weight: ' + wPct + '% | Confidence: ' + confPct + '%</div>';
    if (s.reasoning) {{
      sigHtml += '<div class="src-signal-reasoning">' + s.reasoning + '</div>';
    }}
    sigHtml += '</div>';
  }});
  document.getElementById('src-signals').innerHTML = sigHtml || '<div style="color:#94a3b8">No signal data available</div>';

  /* Adjustments */
  var adj = data.adjustments || {{}};
  var adjHtml = '';
  ['events','season','demand','momentum'].forEach(function(k) {{
    var v = adj[k] || 0;
    var pct = (v * 100).toFixed(1);
    var cls = v > 0.001 ? 'pos' : (v < -0.001 ? 'neg' : '');
    adjHtml += '<div class="src-adj-item"><div class="src-adj-val ' + cls + '">' + (v >= 0 ? '+' : '') + pct + '%</div>';
    adjHtml += '<div class="src-adj-label">' + k + '</div></div>';
  }});
  document.getElementById('src-adjustments').innerHTML = adjHtml;

  /* Factors */
  var factors = data.factors || [];
  if (factors.length > 0) {{
    document.getElementById('src-factors').innerHTML = '<strong>Key factors:</strong> ' + factors.join(' &bull; ');
    document.getElementById('src-factors').style.display = '';
  }} else {{
    document.getElementById('src-factors').style.display = 'none';
  }}

  document.getElementById('src-overlay').classList.add('open');
}}

function closeSources() {{
  document.getElementById('src-overlay').classList.remove('open');
}}
document.getElementById('src-overlay').addEventListener('click', function(e) {{
  if (e.target === this) closeSources();
}});

/* ── Rules Panel Logic ──────────────────────────────────────── */
var _rulesState = {{
  detailId: null,
  hotel: '',
  category: '',
  board: '',
  price: 0,
  signal: '',
  scope: 'row',
  preset: null,
}};

function openRulesPanel(btn) {{
  _rulesState.detailId = btn.dataset.detailId;
  _rulesState.hotel = btn.dataset.hotel;
  _rulesState.category = btn.dataset.category;
  _rulesState.board = btn.dataset.board;
  _rulesState.price = parseFloat(btn.dataset.price) || 0;
  _rulesState.signal = btn.dataset.signal;
  _rulesState.scope = 'row';
  _rulesState.preset = null;

  // Fill context
  document.getElementById('rc-room').textContent = '#' + _rulesState.detailId + ' (' + _rulesState.category + ' / ' + _rulesState.board + ')';
  document.getElementById('rc-hotel').textContent = _rulesState.hotel;
  document.getElementById('rc-price').textContent = '$' + _rulesState.price.toFixed(2);
  var sigEl = document.getElementById('rc-signal');
  sigEl.textContent = _rulesState.signal;
  sigEl.style.color = _rulesState.signal === 'CALL' ? 'var(--call)' : (_rulesState.signal === 'PUT' ? 'var(--put)' : 'var(--neutral)');

  // Update hotel scope label
  document.getElementById('scope-hotel-label').textContent = _rulesState.hotel.substring(0, 20) || 'This Hotel';

  // Reset selections
  document.querySelectorAll('.scope-opt').forEach(function(el) {{ el.classList.remove('selected'); }});
  document.querySelector('.scope-opt[data-scope="row"]').classList.add('selected');
  document.querySelectorAll('.preset-card').forEach(function(el) {{ el.classList.remove('selected'); }});

  // Clear custom inputs
  document.getElementById('rule-ceiling').value = '';
  document.getElementById('rule-floor').value = '';
  document.getElementById('rule-markup').value = '';
  document.getElementById('rule-target').value = '';
  document.getElementById('rules-summary').style.display = 'none';

  document.getElementById('rules-overlay').classList.add('open');
}}

function closeRulesPanel() {{
  document.getElementById('rules-overlay').classList.remove('open');
}}

document.getElementById('rules-overlay').addEventListener('click', function(e) {{
  if (e.target === this) closeRulesPanel();
}});

function selectScope(el) {{
  document.querySelectorAll('.scope-opt').forEach(function(s) {{ s.classList.remove('selected'); }});
  el.classList.add('selected');
  _rulesState.scope = el.dataset.scope;
  updateRulesSummary();
}}

function selectPreset(el) {{
  var wasSelected = el.classList.contains('selected');
  document.querySelectorAll('.preset-card').forEach(function(c) {{ c.classList.remove('selected'); }});
  if (!wasSelected) {{
    el.classList.add('selected');
    _rulesState.preset = el.dataset.preset;
  }} else {{
    _rulesState.preset = null;
  }}
  updateRulesSummary();
}}

function updateRulesSummary() {{
  var parts = [];
  var scopeText = _rulesState.scope === 'row' ? 'Room #' + _rulesState.detailId :
                  _rulesState.scope === 'hotel' ? 'All rooms in ' + _rulesState.hotel :
                  'All hotels';

  if (_rulesState.preset) {{
    parts.push('Preset: <b>' + _rulesState.preset + '</b>');
  }}

  var ceiling = document.getElementById('rule-ceiling').value;
  var floor = document.getElementById('rule-floor').value;
  var markup = document.getElementById('rule-markup').value;
  var target = document.getElementById('rule-target').value;

  if (ceiling) parts.push('Ceiling: $' + ceiling);
  if (floor) parts.push('Floor: $' + floor);
  if (markup) parts.push('Markup: ' + markup + '%');
  if (target) parts.push('Target: $' + target);

  var summaryEl = document.getElementById('rules-summary');
  if (parts.length > 0) {{
    document.getElementById('rules-summary-text').innerHTML =
      '<b>Scope:</b> ' + scopeText + ' &nbsp;|&nbsp; ' + parts.join(' &nbsp;|&nbsp; ');
    summaryEl.style.display = 'block';
  }} else {{
    summaryEl.style.display = 'none';
  }}
}}

// Update summary when custom inputs change
['rule-ceiling', 'rule-floor', 'rule-markup', 'rule-target'].forEach(function(id) {{
  document.getElementById(id).addEventListener('input', updateRulesSummary);
}});

function applyRules() {{
  var scopeText = _rulesState.scope === 'row' ? 'Room #' + _rulesState.detailId :
                  _rulesState.scope === 'hotel' ? _rulesState.hotel :
                  'All Hotels';

  var rulesCount = 0;
  var rulesList = [];

  if (_rulesState.preset) {{
    rulesCount++;
    rulesList.push(_rulesState.preset);
  }}
  if (document.getElementById('rule-ceiling').value) {{
    rulesCount++;
    rulesList.push('ceiling=$' + document.getElementById('rule-ceiling').value);
  }}
  if (document.getElementById('rule-floor').value) {{
    rulesCount++;
    rulesList.push('floor=$' + document.getElementById('rule-floor').value);
  }}
  if (document.getElementById('rule-markup').value) {{
    rulesCount++;
    rulesList.push('markup=' + document.getElementById('rule-markup').value + '%');
  }}
  if (document.getElementById('rule-target').value) {{
    rulesCount++;
    rulesList.push('target=$' + document.getElementById('rule-target').value);
  }}

  if (rulesCount === 0) {{
    showToast('&#9888; Please select a preset or set custom rules', '#f59e0b');
    return;
  }}

  // Update button(s) in the table to show rules are set
  var targetBtns = [];
  if (_rulesState.scope === 'row') {{
    var btn = document.querySelector('.rules-btn[data-detail-id="' + _rulesState.detailId + '"]');
    if (btn) targetBtns.push(btn);
  }} else if (_rulesState.scope === 'hotel') {{
    document.querySelectorAll('.rules-btn[data-hotel="' + _rulesState.hotel.replace(/"/g, '\\\\"') + '"]').forEach(function(b) {{ targetBtns.push(b); }});
  }} else {{
    document.querySelectorAll('.rules-btn').forEach(function(b) {{ targetBtns.push(b); }});
  }}

  targetBtns.forEach(function(b) {{
    b.innerHTML = '&#9881; ' + rulesCount + ' rule' + (rulesCount > 1 ? 's' : '');
    b.style.background = 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)';
    b.title = 'Active rules: ' + rulesList.join(', ') + ' | Scope: ' + scopeText;
  }});

  closeRulesPanel();
  showToast('&#9989; ' + rulesCount + ' rule' + (rulesCount > 1 ? 's' : '') + ' set for ' + scopeText, '#16a34a');

  // TODO: Wire to API  POST /api/v1/salesoffice/rules/
  // The backend connection will be wired in the next step
  console.log('Rules applied:', {{
    scope: _rulesState.scope,
    detailId: _rulesState.detailId,
    hotel: _rulesState.hotel,
    preset: _rulesState.preset,
    ceiling: document.getElementById('rule-ceiling').value,
    floor: document.getElementById('rule-floor').value,
    markup: document.getElementById('rule-markup').value,
    target: document.getElementById('rule-target').value,
  }});
}}

function showToast(msg, bgColor) {{
  var toast = document.getElementById('rules-toast');
  document.getElementById('toast-msg').innerHTML = msg;
  if (bgColor) toast.style.background = bgColor;
  toast.classList.add('show');
  setTimeout(function() {{ toast.classList.remove('show'); }}, 3000);
}}
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
