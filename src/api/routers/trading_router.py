"""Trading Layer API — signals, demand zones, trade setups, search intelligence.

Endpoints for the Phase 1 analytical cache data:
  /trading/signals         — Daily CALL/PUT/NEUTRAL signals per detail_id
  /trading/zones           — Demand (support/resistance) zones per hotel
  /trading/setups          — Trade setups with entry/stop/target/RR/sizing
  /trading/breaks          — Structure breaks (BOS/CHOCH) per hotel
  /trading/search-intel    — Search results intelligence (3 price points)
  /trading/rebuy           — Rebuy signals from cancellation book
  /trading/overrides       — Human price override history
  /trading/cache/freshness — Cache layer freshness + row counts
  /trading/cache/refresh   — Trigger manual cache refresh

Safety: This is a NEW file — does not modify any existing file.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.middleware import limiter, RATE_LIMIT_DATA
from src.api.routers._shared_state import (
    _get_analytical_cache,
    _get_cache_aggregator,
    _optional_api_key,
    _refresh_analytical_cache_daily,
    _refresh_analytical_cache_signals,
    _get_cached_analysis,
)

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/trading", tags=["trading-layer"])


# ── Daily Signals ────────────────────────────────────────────────────


@trading_router.get("/signals")
async def get_signals(
    request=None,
    detail_id: int = Query(..., description="SalesOffice detail ID"),
    days_forward: int = Query(30, ge=1, le=365),
    _key: str = Depends(_optional_api_key),
):
    """Get daily CALL/PUT/NEUTRAL signals for a specific detail_id.

    Each signal includes: date, signal (CALL/PUT/NEUTRAL),
    confidence (0-1), expected_change_pct, and enrichment factors.
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    signals = cache.get_daily_signals(detail_id, days_forward=days_forward)
    return {
        "detail_id": detail_id,
        "count": len(signals),
        "signals": signals,
    }


@trading_router.get("/signals/summary")
async def get_signals_summary(
    request=None,
    detail_id: int = Query(..., description="SalesOffice detail ID"),
    days_forward: int = Query(30, ge=1, le=365),
    _key: str = Depends(_optional_api_key),
):
    """Get summary of daily signals — counts by signal type + avg confidence."""
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    signals = cache.get_daily_signals(detail_id, days_forward=days_forward)

    # Summarize
    summary = {"CALL": 0, "PUT": 0, "NEUTRAL": 0, "total": len(signals)}
    confidences = {"CALL": [], "PUT": [], "NEUTRAL": []}
    for s in signals:
        sig = s.get("signal", "NEUTRAL")
        summary[sig] = summary.get(sig, 0) + 1
        confidences.setdefault(sig, []).append(s.get("confidence", 0))

    avg_conf = {}
    for sig, vals in confidences.items():
        avg_conf[sig] = round(sum(vals) / len(vals), 3) if vals else 0

    return {
        "detail_id": detail_id,
        "days_forward": days_forward,
        "summary": summary,
        "avg_confidence": avg_conf,
        "dominant_signal": max(summary, key=lambda k: summary[k] if k != "total" else -1),
    }


# ── Demand Zones ─────────────────────────────────────────────────────


@trading_router.get("/zones")
async def get_demand_zones(
    request=None,
    hotel_id: int = Query(..., description="Hotel ID"),
    category: Optional[str] = Query(None, description="Room category filter"),
    active_only: bool = Query(True, description="Only active zones"),
    _key: str = Depends(_optional_api_key),
):
    """Get demand (support/resistance) zones for a hotel.

    Zones are detected from price history reversals.
    Strength is based on touch count and recency.
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    zones = cache.get_demand_zones(hotel_id, category=category, active_only=active_only)
    return {
        "hotel_id": hotel_id,
        "count": len(zones),
        "zones": zones,
    }


# ── Structure Breaks ─────────────────────────────────────────────────


@trading_router.get("/breaks")
async def get_structure_breaks(
    request=None,
    hotel_id: int = Query(..., description="Hotel ID"),
    days_back: int = Query(30, ge=1, le=365),
    _key: str = Depends(_optional_api_key),
):
    """Get structure breaks (BOS/CHOCH) for a hotel.

    BOS = Break of Structure (trend continuation)
    CHOCH = Change of Character (trend reversal)
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    breaks = cache.get_structure_breaks(hotel_id, days_back=days_back)
    return {
        "hotel_id": hotel_id,
        "count": len(breaks),
        "breaks": breaks,
    }


# ── Trade Setups ─────────────────────────────────────────────────────


@trading_router.get("/setups")
async def get_trade_setups(
    request=None,
    hotel_id: Optional[int] = Query(None, description="Filter by hotel ID"),
    signal: Optional[str] = Query(None, description="Filter by signal: CALL/PUT"),
    min_rr: float = Query(0, ge=0, description="Minimum risk/reward ratio"),
    limit: int = Query(50, ge=1, le=200),
    _key: str = Depends(_optional_api_key),
):
    """Get trade setups with entry/stop-loss/take-profit/RR/sizing.

    Stop-loss priority: demand_zone → turning_point → volatility (2σ√days)
    Take-profit priority: path_forecast → demand_zone → RR-based (1.5× stop)
    Position sizing: Half-Kelly criterion
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    setups = cache.get_trade_setups(
        hotel_id=hotel_id,
        signal=signal,
        min_rr=min_rr,
        limit=limit,
    )
    return {
        "count": len(setups),
        "filters": {"hotel_id": hotel_id, "signal": signal, "min_rr": min_rr},
        "setups": setups,
    }


# ── Search Intelligence ──────────────────────────────────────────────


@trading_router.get("/search-intel")
async def get_search_intelligence(
    request=None,
    hotel_id: int = Query(..., description="Hotel ID"),
    days_back: int = Query(30, ge=1, le=365),
    _key: str = Depends(_optional_api_key),
):
    """Get search results intelligence — 3 price points per day.

    From SearchResultsSessionPollLog (8.4M rows, pre-aggregated):
    - PriceAmount (sell), NetPriceAmount (wholesale), BarRateAmount (rack rate)
    - Margin spread, search volume, provider count
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    search_data = cache.get_search_daily(hotel_id, days_back=days_back)
    return {
        "hotel_id": hotel_id,
        "count": len(search_data),
        "data": search_data,
    }


# ── Rebuy Signals ────────────────────────────────────────────────────


@trading_router.get("/rebuy")
async def get_rebuy_signals(
    request=None,
    hotel_id: int = Query(0, description="Hotel ID (0 = all hotels)"),
    _key: str = Depends(_optional_api_key),
):
    """Get rebuy signals from cancellation book.

    'Cancelled By Last Price Update Job' = price dropped >10%, rebuy triggered.
    This is a strong CALL signal: someone cancelled to rebuy at a lower price.
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    rebuy = cache.get_rebuy_activity(hotel_id=hotel_id)
    return {
        "hotel_id": hotel_id if hotel_id else "all",
        "count": len(rebuy),
        "signals": rebuy,
    }


# ── Price Overrides ──────────────────────────────────────────────────


@trading_router.get("/overrides")
async def get_price_overrides(
    request=None,
    hotel_id: int = Query(..., description="Hotel ID"),
    _key: str = Depends(_optional_api_key),
):
    """Get human price override history — expert intelligence signals.

    When humans override prices:
    - Increase → human sees upside (confirms CALL)
    - Decrease → human sees pressure (confirms PUT)
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    overrides = cache.get_price_override_signals(hotel_id)
    return {
        "hotel_id": hotel_id,
        "count": len(overrides),
        "overrides": overrides,
    }


# ── Cache Management ─────────────────────────────────────────────────


@trading_router.get("/cache/freshness")
async def get_cache_freshness(
    request=None,
    _key: str = Depends(_optional_api_key),
):
    """Get freshness status for all analytical cache layers.

    Shows row count, latest timestamp, and layer classification
    for each of the 13 tables.
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    return cache.get_freshness()


@trading_router.post("/cache/refresh")
async def trigger_cache_refresh(
    request=None,
    layer: str = Query("all", description="Layer to refresh: all, daily, signals"),
    _key: str = Depends(_optional_api_key),
):
    """Manually trigger a cache refresh.

    - all: Full refresh (Layer 1 + 2 + 3)
    - daily: Layer 1 + 2 only (reference + market)
    - signals: Layer 3 only (demand zones + signals)
    """
    result = {}

    if layer in ("all", "daily"):
        result["daily"] = _refresh_analytical_cache_daily()

    if layer in ("all", "signals"):
        analysis = _get_cached_analysis()
        result["signals"] = _refresh_analytical_cache_signals(analysis)

    return {
        "layer": layer,
        "result": result,
    }


# ── Hotel Overview (combined) ────────────────────────────────────────


@trading_router.get("/hotel/{hotel_id}")
async def get_hotel_trading_overview(
    hotel_id: int,
    request=None,
    _key: str = Depends(_optional_api_key),
):
    """Get complete trading overview for a hotel.

    Combines: demand zones, structure breaks, rebuy signals,
    price overrides, and search intelligence into one response.
    """
    cache = _get_analytical_cache()
    if cache is None:
        return JSONResponse({"error": "Analytical cache not available"}, status_code=503)

    zones = cache.get_demand_zones(hotel_id)
    breaks = cache.get_structure_breaks(hotel_id, days_back=30)
    rebuy = cache.get_rebuy_activity(hotel_id=hotel_id)
    overrides = cache.get_price_override_signals(hotel_id)
    search = cache.get_search_daily(hotel_id, days_back=7)

    # Derive overall sentiment
    bullish_signals = len(rebuy) + sum(1 for o in overrides if o.get("change_amount", 0) > 0)
    bearish_signals = sum(1 for o in overrides if o.get("change_amount", 0) < 0)
    support_zones = [z for z in zones if z.get("zone_type") == "SUPPORT"]
    resistance_zones = [z for z in zones if z.get("zone_type") == "RESISTANCE"]

    return {
        "hotel_id": hotel_id,
        "zones": {"count": len(zones), "support": len(support_zones), "resistance": len(resistance_zones), "data": zones},
        "breaks": {"count": len(breaks), "data": breaks},
        "rebuy_signals": {"count": len(rebuy), "data": rebuy},
        "overrides": {"count": len(overrides), "data": overrides},
        "search_intel": {"count": len(search), "recent_days": 7, "data": search},
        "sentiment": {
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "bias": "BULLISH" if bullish_signals > bearish_signals else "BEARISH" if bearish_signals > bullish_signals else "NEUTRAL",
        },
    }
