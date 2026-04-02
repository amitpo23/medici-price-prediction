"""Monitor endpoints — health alerting, confidence adjustments, unified status.

Provides API access to the MonitorBridge service:
- /monitor/check — Run health check and dispatch alerts
- /monitor/ingest — Ingest external monitor results (from system_monitor.py)
- /monitor/adjustments — View active confidence adjustments
- /monitor/adjustments/{hotel_id} — View adjustments for a specific hotel
- /monitor/status — Unified health status (prediction + booking engine)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.middleware import limiter, RATE_LIMIT_DATA
from src.api.routers._shared_state import _optional_api_key

logger = logging.getLogger(__name__)

monitor_router = APIRouter()


@monitor_router.get("/monitor/check")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_check(request: Request, _key: str = Depends(_optional_api_key)):
    """Run health check and dispatch alerts for any degradation.

    This endpoint polls prediction engine health (freshness, cache age)
    and dispatches alerts through configured channels if issues are detected.
    Call every 30 minutes via scheduled task or external cron.
    """
    try:
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.check_health_and_alert()
        return JSONResponse(content=result)
    except (ImportError, OSError) as e:
        logger.error("Monitor check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Monitor check failed: {e}")


@monitor_router.post("/monitor/ingest")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_ingest(request: Request, _key: str = Depends(_optional_api_key)):
    """Ingest results from the external system_monitor.py.

    Expects JSON body with "results" and "alerts" keys matching
    SystemMonitor output format. Forwards alerts to dispatcher and
    applies confidence adjustments to affected hotels.

    Example body:
        {
            "results": { "webjob": {...}, "mapping": {...}, ... },
            "alerts": [ {"severity": "CRITICAL", "component": "WebJob", ...} ]
        }
    """
    try:
        body = await request.json()
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    if "results" not in body and "alerts" not in body:
        raise HTTPException(
            status_code=400,
            detail="Body must contain 'results' and/or 'alerts' keys",
        )

    try:
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_monitor_results(body)
        return JSONResponse(content=result)
    except (ImportError, OSError) as e:
        logger.error("Monitor ingest failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Monitor ingest failed: {e}")


@monitor_router.get("/monitor/adjustments")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_adjustments(request: Request, _key: str = Depends(_optional_api_key)):
    """Get all active confidence adjustments from monitor findings.

    Returns list of adjustments that are currently reducing prediction
    confidence due to system issues (WebJob stale, mapping gaps, etc.).
    Adjustments expire after 1 hour and must be renewed by the next check.
    """
    try:
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        adjustments = bridge.get_active_adjustments()
        modifier = bridge.get_confidence_modifier()
        return JSONResponse(content={
            "active_adjustments": len(adjustments),
            "global_confidence_modifier": modifier,
            "adjustments": adjustments,
        })
    except (ImportError, OSError) as e:
        logger.error("Monitor adjustments query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Monitor query failed — check server logs")


@monitor_router.get("/monitor/adjustments/{hotel_id}")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_adjustments_hotel(
    hotel_id: str,
    request: Request,
    _key: str = Depends(_optional_api_key),
):
    """Get confidence adjustments for a specific hotel.

    Returns both hotel-specific and global adjustments that affect
    this hotel's prediction confidence.
    """
    try:
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        adjustments = bridge.get_active_adjustments(hotel_id=hotel_id)
        modifier = bridge.get_confidence_modifier(hotel_id=hotel_id)
        return JSONResponse(content={
            "hotel_id": hotel_id,
            "active_adjustments": len(adjustments),
            "confidence_modifier": modifier,
            "adjustments": adjustments,
        })
    except (ImportError, OSError) as e:
        logger.error("Monitor adjustments query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Monitor query failed — check server logs")


@monitor_router.get("/monitor/status")
@limiter.limit(RATE_LIMIT_DATA)
async def monitor_status(request: Request, _key: str = Depends(_optional_api_key)):
    """Unified health status — prediction engine + booking engine.

    Combines internal health check data with monitor history to provide
    a single view of system health, including trend analysis and
    active confidence adjustments.
    """
    try:
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        status = bridge.get_unified_status()
        return JSONResponse(content=status)
    except (ImportError, OSError) as e:
        logger.error("Monitor status query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Monitor query failed — check server logs")
