"""SalesOffice Analytics Dashboard — live endpoints for price analysis.

Endpoints:
  GET /api/v1/salesoffice/dashboard  — Interactive HTML dashboard (Plotly)
  GET /api/v1/salesoffice/data       — Raw analysis JSON
  GET /api/v1/salesoffice/status     — Quick status check

Background:
  Hourly price collection from medici-db [SalesOffice.Details]
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

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

    # Strip daily predictions (too verbose for JSON) — keep summaries
    predictions = analysis.get("predictions", {})
    summary_predictions = {}
    for detail_id, pred in predictions.items():
        summary_predictions[detail_id] = {
            k: v for k, v in pred.items() if k != "daily"
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
