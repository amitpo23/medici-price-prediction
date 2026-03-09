"""Core analytics endpoints — JSON APIs for data, options, forward curve, backtest."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.api.middleware import limiter, RATE_LIMIT_DATA
from src.api.models.pagination import pagination_params, paginate

from src.api.routers._shared_state import (
    _analysis_warming,
    _scheduler_thread,
    _optional_api_key,
    _get_or_run_analysis,
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
    COLLECTION_INTERVAL,
)
from src.utils.cache_manager import cache as _cm

logger = logging.getLogger(__name__)

analytics_router = APIRouter()


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
def salesoffice_option_detail(detail_id: int):
    """Return compact detail data for the inline trading chart panel."""
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


@analytics_router.get("/forward-curve/{detail_id}")
def salesoffice_forward_curve(detail_id: int):
    """Full forward curve prediction for a specific room."""
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


@analytics_router.get("/options")
@limiter.limit(RATE_LIMIT_DATA)
async def salesoffice_options(
    request: Request,
    t_days: int | None = None,
    include_chart: bool = True,
    profile: str = "full",
    include_system_context: bool = True,
    _key: str = Depends(_optional_api_key),
    page: dict = Depends(pagination_params),
):
    """Options-style row output with min/max path stats and source transparency."""
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

    paged = paginate(rows, page["limit"], page["offset"], page["all"])

    response_payload = {
        "run_ts": analysis.get("run_ts"),
        "total_rows": paged["total"],
        "limit": paged["limit"],
        "offset": paged["offset"],
        "has_more": paged["has_more"],
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
        "rows": paged["items"],
    }

    if include_system_context:
        response_payload["system_capabilities"] = _build_system_capabilities(analysis, total_rows=paged["total"])

    response = JSONResponse(content=response_payload)
    if paged.get("_all"):
        response.headers["X-Pagination-Warning"] = "All items returned; consider using pagination"
    return response


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

    init_db()
    snapshot_count = get_snapshot_count()
    latest = load_latest_snapshot()

    return {
        "status": "ok",
        "snapshots_collected": snapshot_count,
        "total_rooms": len(latest) if not latest.empty else 0,
        "total_hotels": latest["hotel_id"].nunique() if not latest.empty else 0,
        "last_analysis": (_cm.get_data("analytics") or {}).get("run_ts"),
        "cache_ready": _cm.has_data("analytics"),
        "analysis_warming": _analysis_warming.is_set(),
        "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "collection_interval_seconds": COLLECTION_INTERVAL,
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
