"""SalesOffice Analytics Dashboard — live endpoints for price analysis.

Endpoints:
  GET /api/v1/salesoffice/dashboard  — Interactive HTML dashboard (Plotly)
  GET /api/v1/salesoffice/info       — System information & documentation (HTML)
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
    analysis = _get_or_run_analysis()
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
    return analysis


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


def _generate_html(analysis: dict) -> str:
    """Generate the HTML dashboard from analysis results."""
    from src.analytics.report import generate_report
    from config.settings import DATA_DIR

    report_path = generate_report(analysis)

    # Read and return the HTML
    return report_path.read_text(encoding="utf-8")
