"""AI endpoints — Claude analyst, AI insights, metadata enrichment."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from src.api.middleware import limiter, RATE_LIMIT_AI
from src.api.models.pagination import pagination_params, paginate

from src.api.routers._shared_state import _get_or_run_analysis

logger = logging.getLogger(__name__)

ai_router = APIRouter()


@ai_router.get("/options/ai-insights")
@limiter.limit(RATE_LIMIT_AI)
async def salesoffice_ai_insights(
    request: Request,
    t_days: Optional[int] = None,
    hotel_name: Optional[str] = None,
):
    """AI-powered market intelligence — aggregate + per-room analysis."""
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


@ai_router.get("/ai/ask")
@limiter.limit(RATE_LIMIT_AI)
async def salesoffice_ai_ask(
    request: Request,
    q: str,
    detail_id: Optional[int] = None,
    deep: bool = False,
):
    """Ask Claude a question about the portfolio data."""
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


@ai_router.get("/ai/brief")
@limiter.limit(RATE_LIMIT_AI)
async def salesoffice_ai_brief(
    request: Request,
    lang: str = "en",
):
    """AI-generated executive market brief for the trading team."""
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


@ai_router.get("/ai/explain/{detail_id}")
@limiter.limit(RATE_LIMIT_AI)
async def salesoffice_ai_explain(request: Request, detail_id: int):
    """Deep AI explanation of a specific room's prediction."""
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


@ai_router.get("/ai/metadata")
@limiter.limit(RATE_LIMIT_AI)
async def salesoffice_ai_metadata(
    request: Request,
    detail_id: Optional[int] = None,
    page: dict = Depends(pagination_params),
):
    """AI-generated smart tags and metadata for room options."""
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

    # Enrich all, then paginate the results
    enrich_limit = page["limit"] if not page["all"] else len(predictions)
    results = batch_enrich_metadata(predictions, limit=max(enrich_limit + page["offset"], 100))

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

    paged = paginate(enriched_rooms, page["limit"], page["offset"], page["all"])
    response = JSONResponse(content={
        "total": paged["total"],
        "limit": paged["limit"],
        "offset": paged["offset"],
        "has_more": paged["has_more"],
        "rooms": paged["items"],
    })
    if paged.get("_all"):
        response.headers["X-Pagination-Warning"] = "All items returned; consider using pagination"
    return response
