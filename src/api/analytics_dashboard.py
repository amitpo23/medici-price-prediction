"""SalesOffice Analytics Dashboard — thin shell that assembles all sub-routers.

All endpoint handlers live in src/api/routers/. This module keeps the
router = APIRouter(prefix="/api/v1/salesoffice") for backward compatibility
with main.py and includes all sub-routers.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from src.api.routers._shared_state import (
    start_salesoffice_scheduler,
    stop_salesoffice_scheduler,
)
from src.api.routers.export_router import export_router
from src.api.routers.ai_router import ai_router
from src.api.routers.market_router import market_router
from src.api.routers.dashboard_router import dashboard_router
from src.api.routers.analytics_router import analytics_router
from src.api.routers.monitor_router import monitor_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/salesoffice", tags=["salesoffice-analytics"])

# Include all sub-routers (no prefix — the prefix stays on this parent router)
router.include_router(analytics_router)
router.include_router(dashboard_router)
router.include_router(export_router)
router.include_router(ai_router)
router.include_router(market_router)
router.include_router(monitor_router)
