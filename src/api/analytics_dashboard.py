"""SalesOffice Analytics Dashboard — live endpoints for price analysis.

Endpoints:
  GET /api/v1/salesoffice/home       — Consolidated landing page (HTML)
  GET /api/v1/salesoffice/dashboard  — Interactive HTML dashboard (Plotly)
  GET /api/v1/salesoffice/info       — System information & documentation (HTML)
  GET /api/v1/salesoffice/insights   — Price insights: up/down, below/above today (HTML)
  GET /api/v1/salesoffice/yoy        — Year-over-Year comparison: decay curve, calendar spread (HTML)
  GET /api/v1/salesoffice/options    — Options trading: CALL/PUT signals + expiry analytics (HTML)
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

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/salesoffice", tags=["salesoffice-analytics"])

# Cache for latest analysis (avoid recomputing on every request)
_cache: dict = {}
_cache_lock = threading.Lock()
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()

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
async def salesoffice_data(
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
async def salesoffice_simple():
    """Simplified analysis — human-readable JSON with 4 clear sections.

    Returns: summary (text), predictions (per-room), attention (action items), market (stats).
    Easy to read, no trading jargon.
    """
    from src.analytics.simple_analysis import simplify_analysis

    analysis = _get_or_run_analysis()
    simplified = simplify_analysis(analysis)
    return JSONResponse(content=simplified)


@router.get("/simple/text", response_class=PlainTextResponse)
async def salesoffice_simple_text():
    """Plain text analysis report — for quick reading in terminal or email."""
    from src.analytics.simple_analysis import simplify_to_text

    analysis = _get_or_run_analysis()
    text = simplify_to_text(analysis)
    return PlainTextResponse(content=text)


@router.get("/debug")
async def salesoffice_debug():
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
async def salesoffice_forward_curve(detail_id: int):
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


@router.get("/backtest")
async def salesoffice_backtest(
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
async def salesoffice_decay_curve():
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
async def salesoffice_info():
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
async def salesoffice_charts_contract_data(
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
async def salesoffice_export_contracts():
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
async def salesoffice_export_providers():
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
async def salesoffice_export_summary(format: str = "json"):
    """Weekly summary digest — JSON or plain text."""
    from src.analytics.export_engine import generate_weekly_summary, generate_summary_text

    try:
        summary = generate_weekly_summary()
        if format == "text":
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
        "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "collection_interval_seconds": COLLECTION_INTERVAL,
    }


# ── Market Data endpoints (new mega-tables) ──────────────────────────

@router.get("/market/search-data")
async def market_search_data(hotel_id: int | None = None, days_back: int = 30):
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
async def market_search_summary(hotel_id: int | None = None):
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
async def market_search_results(hotel_id: int | None = None, days_back: int = 7):
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
async def market_price_updates(days_back: int = 30):
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
async def market_price_velocity(hotel_id: int | None = None):
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
async def market_competitors(hotel_id: int, radius_km: float = 5.0,
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
async def market_prebooks(hotel_id: int | None = None, days_back: int = 90):
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
async def market_cancellations(days_back: int = 365):
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
async def market_hotels_geo():
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
async def market_db_overview():
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
            try:
                _run_collection_cycle()
            except Exception as e:
                logger.error("SalesOffice collection cycle failed: %s", e, exc_info=True)
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
    """Return cached analysis or run a fresh one."""
    with _cache_lock:
        if _cache:
            return dict(_cache)

    # No cache — run now
    try:
        result = _run_collection_cycle()
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Analysis failed: {e}")
    if result is None:
        raise HTTPException(status_code=503, detail="No SalesOffice data available. Check DB connection.")
    return result


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
