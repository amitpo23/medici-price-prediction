"""Pricing Rules API — FastAPI router for SalesOffice Step 5 integration.

Two audiences:
  1. WebJob (C# / Step 5)  — calls /apply and /apply-batch
  2. Human operators / dashboard — calls CRUD, presets, auto-generate

All endpoints under /api/v1/salesoffice/rules/
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from src.rules.engine import RulesEngine
from src.rules.models import (
    PricingRuleCreate,
    PricingRuleResponse,
    PricingRuleUpdate,
    RuleAction,
    RuleApplyRequest,
    RuleApplyResult,
    RuleBatchRequest,
    RuleBatchResponse,
    RuleStatsResponse,
)
from src.rules.store import RulesStore

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/salesoffice/rules",
    tags=["pricing-rules"],
)

# Singletons
_store = RulesStore()
_engine = RulesEngine(store=_store)


# ── Auth ─────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(default="")) -> str:
    """Validate API key if one is configured."""
    from src.api.middleware import verify_api_key as _check
    if not _check(x_api_key):
        logger.warning("Failed auth attempt with key prefix: %s...", x_api_key[:8] if x_api_key else "(empty)")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


# ═══════════════════════════════════════════════════════════════════════
#  STEP 5 ENDPOINTS — called by the WebJob
# ═══════════════════════════════════════════════════════════════════════

@router.get("/apply/{hotel_id}", response_model=RuleApplyResult)
def apply_rules(
    hotel_id: int,
    price: float = Query(..., description="Cheapest price found (MinBy result)"),
    category: str = Query("", description="Room category (standard, deluxe, etc.)"),
    board: str = Query("", description="Board type (RO, BB, HB, AI, etc.)"),
):
    """Apply pricing rules to a room — the core Step 5 endpoint.

    Called by the WebJob after MinBy price selection.
    Returns ACCEPT/REJECT/MODIFY with the adjusted price to push to Zenith.

    No API key required for this endpoint — the WebJob needs fast,
    unrestricted access. Security is via network isolation.
    """
    try:
        result = _engine.apply(
            hotel_id=hotel_id,
            price=price,
            category=category,
            board=board,
        )
        return result
    except (ValueError, TypeError, KeyError, OSError) as e:
        logger.error("Rules apply error for hotel %d: %s", hotel_id, e, exc_info=True)
        # Graceful degradation: if rules engine fails, accept with default markup
        return RuleApplyResult(
            hotel_id=hotel_id,
            original_price=price,
            action=RuleAction.ACCEPT,
            adjusted_price=round(price + 0.01, 2),
            markup_applied=0.01,
            rules_applied=[],
            reason=f"Rules engine error — fallback to $0.01 markup: {e}",
        )


@router.post("/apply-batch", response_model=RuleBatchResponse)
def apply_rules_batch(
    request: RuleBatchRequest,
):
    """Apply rules to multiple rooms at once — batch endpoint for Step 5.

    More efficient than individual calls when scanning many hotels.
    """
    results = []
    accepted = rejected = modified = 0

    for room in request.rooms:
        try:
            result = _engine.apply(
                hotel_id=room.hotel_id,
                price=room.price,
                category=room.category,
                board=room.board,
            )
        except (ValueError, TypeError, KeyError, OSError) as e:
            result = RuleApplyResult(
                hotel_id=room.hotel_id,
                original_price=room.price,
                action=RuleAction.ACCEPT,
                adjusted_price=round(room.price + 0.01, 2),
                markup_applied=0.01,
                reason=f"Error — fallback: {e}",
            )

        results.append(result)
        if result.action == RuleAction.ACCEPT:
            accepted += 1
        elif result.action == RuleAction.REJECT:
            rejected += 1
        elif result.action in (RuleAction.MODIFY, RuleAction.HOLD):
            modified += 1

    return RuleBatchResponse(
        results=results,
        total=len(results),
        accepted=accepted,
        rejected=rejected,
        modified=modified,
    )


# ═══════════════════════════════════════════════════════════════════════
#  CRUD ENDPOINTS — manage rules
# ═══════════════════════════════════════════════════════════════════════

@router.get("", response_model=list[PricingRuleResponse])
def list_all_rules(
    _key: str = Depends(verify_api_key),
):
    """Get all active pricing rules across all hotels."""
    return _store.get_all_active_rules()


@router.get("/hotel/{hotel_id}", response_model=list[PricingRuleResponse])
def list_hotel_rules(
    hotel_id: int,
    active_only: bool = Query(True),
    _key: str = Depends(verify_api_key),
):
    """Get all rules for a specific hotel."""
    return _store.get_rules_for_hotel(hotel_id, active_only=active_only)


@router.get("/rule/{rule_id}", response_model=PricingRuleResponse)
def get_rule(
    rule_id: int,
    _key: str = Depends(verify_api_key),
):
    """Get a single rule by ID."""
    rule = _store.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule


@router.post("", response_model=PricingRuleResponse, status_code=201)
def create_rule(
    data: PricingRuleCreate,
    _key: str = Depends(verify_api_key),
):
    """Create a new pricing rule."""
    return _store.create_rule(data)


@router.post("/batch", response_model=list[PricingRuleResponse], status_code=201)
def create_rules_batch(
    rules: list[PricingRuleCreate],
    _key: str = Depends(verify_api_key),
):
    """Create multiple pricing rules at once."""
    return _store.create_rules_batch(rules)


@router.put("/rule/{rule_id}", response_model=PricingRuleResponse)
def update_rule(
    rule_id: int,
    data: PricingRuleUpdate,
    _key: str = Depends(verify_api_key),
):
    """Update an existing pricing rule."""
    result = _store.update_rule(rule_id, data)
    if not result:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return result


@router.delete("/rule/{rule_id}")
def delete_rule(
    rule_id: int,
    _key: str = Depends(verify_api_key),
):
    """Deactivate (soft-delete) a pricing rule."""
    success = _store.deactivate_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "deactivated", "rule_id": rule_id}


@router.delete("/hotel/{hotel_id}")
def delete_hotel_rules(
    hotel_id: int,
    rule_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    _key: str = Depends(verify_api_key),
):
    """Deactivate all rules for a hotel (optionally filtered by type/source)."""
    count = _store.deactivate_hotel_rules(hotel_id, rule_type=rule_type, source=source)
    return {"status": "deactivated", "hotel_id": hotel_id, "count": count}


# ═══════════════════════════════════════════════════════════════════════
#  AUTO-GENERATE — predictor creates rules from Forward Curve
# ═══════════════════════════════════════════════════════════════════════

@router.post("/auto-generate/{hotel_id}")
def auto_generate_hotel_rules(
    hotel_id: int,
    _key: str = Depends(verify_api_key),
):
    """Auto-generate pricing rules for a specific hotel from Forward Curve.

    Uses the latest FC prediction to create smart rules.
    """
    from src.rules.auto_generator import RulesAutoGenerator

    # Get forward curve data for this hotel
    fc_data = _get_forward_curve_data(hotel_id)
    if not fc_data:
        raise HTTPException(
            status_code=404,
            detail=f"No forward curve data for hotel {hotel_id}",
        )

    generator = RulesAutoGenerator(store=_store)
    created = generator.generate_from_forward_curve(
        hotel_id=hotel_id,
        current_price=fc_data["current_price"],
        forward_points=fc_data["points"],
    )

    return {
        "hotel_id": hotel_id,
        "rules_created": len(created),
        "rules": created,
        "current_price": fc_data["current_price"],
    }


@router.post("/auto-generate")
def auto_generate_all_rules(
    _key: str = Depends(verify_api_key),
):
    """Auto-generate pricing rules for ALL hotels from Forward Curves.

    Runs across the entire active portfolio.
    """
    from src.rules.auto_generator import RulesAutoGenerator

    analyses = _get_all_forward_curves()
    if not analyses:
        return {
            "status": "no_data",
            "message": "No forward curve data available",
            "total_rules": 0,
        }

    generator = RulesAutoGenerator(store=_store)
    summary = generator.generate_for_all_hotels(analyses)

    return {
        "status": "ok",
        "total_hotels": summary["total_hotels"],
        "total_rules": summary["total_rules"],
        "by_hotel": summary["by_hotel"],
    }


# ═══════════════════════════════════════════════════════════════════════
#  PRESETS — templates for common strategies
# ═══════════════════════════════════════════════════════════════════════

@router.get("/presets")
def list_presets(
    _key: str = Depends(verify_api_key),
):
    """List all available preset templates."""
    from src.rules.presets import BUILTIN_PRESETS

    presets = _store.get_presets()
    builtin_names = list(BUILTIN_PRESETS.keys())

    return {
        "presets": presets,
        "builtin_available": builtin_names,
    }


@router.post("/presets/install")
def install_presets(
    _key: str = Depends(verify_api_key),
):
    """Install/update all built-in presets in the database."""
    from src.rules.presets import install_builtin_presets

    results = install_builtin_presets(store=_store)
    return {"status": "ok", "installed": results}


@router.post("/presets/{preset_name}/apply/{hotel_id}")
def apply_preset(
    preset_name: str,
    hotel_id: int,
    current_price: float = Query(0.0, description="Current price for ceiling calculations"),
    _key: str = Depends(verify_api_key),
):
    """Apply a named preset to a hotel."""
    from src.rules.presets import BUILTIN_PRESETS, apply_preset_to_hotel

    if preset_name not in BUILTIN_PRESETS:
        raise HTTPException(
            status_code=404,
            detail=f"Preset '{preset_name}' not found. Available: {list(BUILTIN_PRESETS.keys())}",
        )

    created = apply_preset_to_hotel(
        preset_name=preset_name,
        hotel_id=hotel_id,
        current_price=current_price,
        store=_store,
    )

    return {
        "hotel_id": hotel_id,
        "preset": preset_name,
        "rules_created": len(created),
        "rules": created,
    }


# ═══════════════════════════════════════════════════════════════════════
#  PREVIEW & STATS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/preview/{hotel_id}")
def preview_rules(
    hotel_id: int,
    _key: str = Depends(verify_api_key),
):
    """Preview what rules would do with recent scan data.

    Fetches latest prices from trading DB and simulates rule application.
    """
    prices = _get_recent_prices(hotel_id)
    if not prices:
        # Still show what rules exist
        rules = _store.get_rules_for_hotel(hotel_id)
        return {
            "hotel_id": hotel_id,
            "rules_count": len(rules),
            "rules": [r.model_dump() for r in rules],
            "preview": [],
            "note": "No recent scan data — showing rules only",
        }

    results = _engine.preview(hotel_id, prices)
    rules = _store.get_rules_for_hotel(hotel_id)

    # Calculate impact summary
    total_markup = sum(r.markup_applied for r in results)
    rejected_count = sum(1 for r in results if r.action == RuleAction.REJECT)
    modified_count = sum(1 for r in results if r.action in (RuleAction.MODIFY, RuleAction.ACCEPT))

    return {
        "hotel_id": hotel_id,
        "rules_count": len(rules),
        "rules": [r.model_dump() for r in rules],
        "preview": [r.model_dump() for r in results],
        "impact": {
            "rooms_analyzed": len(results),
            "rooms_rejected": rejected_count,
            "rooms_modified": modified_count,
            "total_extra_markup": round(total_markup, 2),
            "avg_markup_per_room": round(total_markup / len(results), 2) if results else 0,
        },
    }


@router.get("/stats", response_model=RuleStatsResponse)
def get_stats(
    _key: str = Depends(verify_api_key),
):
    """Get aggregate statistics about pricing rules."""
    return _store.get_stats()


@router.get("/logs")
def get_logs(
    hotel_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    _key: str = Depends(verify_api_key),
):
    """Get recent rule application logs."""
    logs = _store.get_recent_logs(hotel_id=hotel_id, limit=limit)
    return {"logs": logs, "count": len(logs)}


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS — data fetching
# ═══════════════════════════════════════════════════════════════════════

def _get_forward_curve_data(hotel_id: int) -> Optional[dict]:
    """Get forward curve prediction data for a hotel.

    Runs the full analysis pipeline to get FC points.
    """
    try:
        from src.analytics.runner import run_full_analysis
        analysis = run_full_analysis()
        if not analysis:
            return None

        # Find rows for this hotel
        rows = analysis.get("rows", [])
        for row in rows:
            if row.get("hotel_id") == hotel_id:
                fc = row.get("forward_curve", {})
                points = fc.get("points", [])
                current_price = row.get("current_price") or row.get("buy_price", 0)
                if points and current_price:
                    return {
                        "current_price": current_price,
                        "points": points,
                    }

        return None
    except (ValueError, TypeError, KeyError, OSError) as e:
        logger.error("Failed to get FC for hotel %d: %s", hotel_id, e, exc_info=True)
        return None


def _get_all_forward_curves() -> list[dict]:
    """Get forward curves for all active hotels."""
    try:
        from src.analytics.runner import run_full_analysis
        analysis = run_full_analysis()
        if not analysis:
            return []

        results = []
        for row in analysis.get("rows", []):
            fc = row.get("forward_curve", {})
            points = fc.get("points", [])
            hotel_id = row.get("hotel_id")
            current_price = row.get("current_price") or row.get("buy_price", 0)

            if hotel_id and points and current_price:
                results.append({
                    "hotel_id": hotel_id,
                    "current_price": current_price,
                    "forward_points": points,
                })

        return results
    except (ValueError, TypeError, KeyError, OSError) as e:
        logger.error("Failed to get all FCs: %s", e, exc_info=True)
        return []


def _get_recent_prices(hotel_id: int) -> list[dict]:
    """Get recent scan prices from trading DB for preview."""
    try:
        from src.data.trading_db import load_scan_history, check_connection
        if not check_connection():
            return []

        history = load_scan_history(hotel_id)
        if history.empty:
            return []

        # Get latest scan's prices
        prices = []
        for _, row in history.tail(20).iterrows():
            prices.append({
                "price": float(row.get("room_price", 0)),
                "category": str(row.get("room_category", "")),
                "board": str(row.get("room_board", "")),
            })

        return prices
    except (OSError, ConnectionError, ValueError) as e:
        logger.debug("Could not load recent prices for hotel %d: %s", hotel_id, e)
        return []
