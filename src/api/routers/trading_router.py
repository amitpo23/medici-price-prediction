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
  /trading/daily-summary   — Morning brief with signal transitions
  /trading/pnl-today       — Today's executed overrides + opportunities P&L

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
    _get_cached_signals,
)

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/trading", tags=["trading-layer"])

# Module-level store for signal transition tracking between cycles
_previous_signals: dict[int, str] = {}  # detail_id → signal (CALL/PUT/NEUTRAL)


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


# ── Daily Trading Summary ───────────────────────────────────────────


@trading_router.get("/daily-summary")
async def get_daily_trading_summary(
    request=None,
    top_n: int = Query(5, ge=1, le=20, description="Number of top CALL/PUT items"),
    _key: str = Depends(_optional_api_key),
):
    """Morning brief: signal distribution, top movers, rules status, accuracy snapshot.

    Aggregates from cached signals and analysis — no new DB queries.
    """
    from datetime import date

    signals = _get_cached_signals()
    if not signals:
        return JSONResponse(
            {"error": "Signals not available yet — cache warming up"},
            status_code=503,
        )

    today = date.today().isoformat()

    # --- Signal distribution ---
    dist: dict[str, int] = {"CALL": 0, "PUT": 0, "NEUTRAL": 0}
    hotels_seen: set[int] = set()
    confidences: list[float] = []
    t_values: list[int] = []
    prices: list[float] = []
    calls: list[dict] = []
    puts: list[dict] = []

    for sig in signals:
        rec = sig.get("recommendation", "NONE")
        # Map NONE to NEUTRAL for the summary
        mapped = "NEUTRAL" if rec == "NONE" else rec
        dist[mapped] = dist.get(mapped, 0) + 1

        hotel_id = sig.get("hotel_id")
        if hotel_id is not None:
            hotels_seen.add(int(hotel_id))

        conf_pct = float(sig.get("consensus_probability", 0) or 0)
        confidences.append(conf_pct)

        t_val = sig.get("T")
        if t_val is not None:
            t_values.append(int(t_val))

        price = float(sig.get("S_t", 0) or 0)
        if price > 0:
            prices.append(price)

        exp_return = float(sig.get("expected_return_1d", 0) or 0)
        item = {
            "hotel": sig.get("hotel_name", ""),
            "category": sig.get("category", ""),
            "price": round(price, 2),
            "predicted": round(price * (1 + exp_return / 100), 2) if price > 0 else 0,
            "change_pct": round(exp_return, 1),
        }

        if rec == "CALL":
            calls.append(item)
        elif rec == "PUT":
            puts.append(item)

    # Sort by magnitude of expected change
    calls.sort(key=lambda x: x["change_pct"], reverse=True)
    puts.sort(key=lambda x: x["change_pct"])  # most negative first

    # --- Rules status ---
    override_rules_active = 0
    opportunity_rules_active = 0
    recent_overrides = 0
    recent_opportunities = 0

    try:
        from src.analytics.override_rules import get_rules
        rules = get_rules(active_only=True)
        override_rules_active = len(rules)
    except (ImportError, OSError, Exception):
        pass

    try:
        from src.analytics.opportunity_rules import get_opp_rules
        opp_rules = get_opp_rules(active_only=True)
        opportunity_rules_active = len(opp_rules)
    except (ImportError, OSError, Exception):
        pass

    try:
        from src.analytics.override_rules import get_execution_log
        override_log = get_execution_log(limit=100)
        recent_overrides = sum(
            1 for entry in override_log
            if str(entry.get("executed_at", "")).startswith(today)
        )
    except (ImportError, OSError, Exception):
        pass

    try:
        from src.analytics.opportunity_rules import get_opp_execution_log
        opp_log = get_opp_execution_log(limit=100)
        recent_opportunities = sum(
            1 for entry in opp_log
            if str(entry.get("executed_at", "")).startswith(today)
        )
    except (ImportError, OSError, Exception):
        pass

    # --- Aggregates ---
    total_options = len(signals)
    avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else 0
    avg_t = round(sum(t_values) / len(t_values)) if t_values else 0

    price_range = {
        "min": round(min(prices), 2) if prices else 0,
        "max": round(max(prices), 2) if prices else 0,
        "avg": round(sum(prices) / len(prices), 2) if prices else 0,
    }

    # --- Signal transitions ---
    global _previous_signals
    current_signals: dict[int, dict] = {}
    for sig in signals:
        did = sig.get("detail_id")
        rec = sig.get("recommendation", "NONE")
        mapped = "NEUTRAL" if rec == "NONE" else rec
        if did is not None:
            current_signals[int(did)] = {
                "signal": mapped,
                "hotel": sig.get("hotel_name", ""),
                "price": round(float(sig.get("S_t", 0) or 0), 2),
            }

    signal_transitions: list[dict] = []
    if _previous_signals:
        for did, info in current_signals.items():
            prev = _previous_signals.get(did)
            if prev and prev != info["signal"]:
                signal_transitions.append({
                    "detail_id": did,
                    "hotel": info["hotel"],
                    "from": prev,
                    "to": info["signal"],
                    "price": info["price"],
                })

    # Update the store for the next cycle
    _previous_signals = {did: info["signal"] for did, info in current_signals.items()}

    return {
        "date": today,
        "signal_distribution": dist,
        "total_options": total_options,
        "hotels_count": len(hotels_seen),
        "top_calls": calls[:top_n],
        "top_puts": puts[:top_n],
        "override_rules_active": override_rules_active,
        "opportunity_rules_active": opportunity_rules_active,
        "recent_executions": {
            "overrides": recent_overrides,
            "opportunities": recent_opportunities,
        },
        "avg_confidence_pct": avg_conf,
        "avg_t_days": avg_t,
        "price_range": price_range,
        "signal_transitions": signal_transitions,
        "transition_count": len(signal_transitions),
    }


# ── Daily P&L ──────────────────────────────────────────────────────


@trading_router.get("/pnl-today")
async def get_pnl_today(
    request=None,
    _key: str = Depends(_optional_api_key),
):
    """Today's executed overrides + opportunities with P&L calculations.

    Queries the local execution logs (SQLite) for today's activity.
    No Azure SQL queries — uses cached rule execution data only.
    """
    from datetime import date

    today = date.today().isoformat()

    overrides_executed = 0
    overrides_total_discount = 0.0
    opportunities_submitted = 0
    opportunities_total_profit = 0.0
    opportunities_filled = 0

    # --- Override execution log ---
    try:
        from src.analytics.override_rules import get_execution_log
        override_log = get_execution_log(limit=500)
        for entry in override_log:
            executed_at = str(entry.get("executed_at", ""))
            if executed_at.startswith(today):
                overrides_executed += 1
                overrides_total_discount += float(entry.get("discount_usd", 0) or 0)
    except (ImportError, OSError, Exception) as exc:
        logger.debug("Could not load override execution log: %s", exc)

    # --- Opportunity execution log ---
    try:
        from src.analytics.opportunity_rules import get_opp_execution_log
        opp_log = get_opp_execution_log(limit=500)
        for entry in opp_log:
            executed_at = str(entry.get("executed_at", ""))
            if executed_at.startswith(today):
                opportunities_submitted += 1
                opportunities_total_profit += float(entry.get("profit_usd", 0) or entry.get("expected_profit", 0) or 0)
                if entry.get("status") == "filled":
                    opportunities_filled += 1
    except (ImportError, OSError, Exception) as exc:
        logger.debug("Could not load opportunity execution log: %s", exc)

    # --- Net position summary ---
    parts = []
    if overrides_executed:
        parts.append(f"{overrides_executed} PUT overrides active")
    if opportunities_submitted:
        parts.append(f"{opportunities_submitted} CALL opportunities pending")
    net_position = ", ".join(parts) if parts else "No executions today"

    return {
        "date": today,
        "overrides_executed": overrides_executed,
        "overrides_total_discount": round(overrides_total_discount, 2),
        "opportunities_submitted": opportunities_submitted,
        "opportunities_total_profit_expected": round(opportunities_total_profit, 2),
        "opportunities_filled": opportunities_filled,
        "net_position": net_position,
    }
