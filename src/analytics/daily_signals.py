"""Daily Signal Generator — per-day CALL/PUT/NEUTRAL from forward curve.

Instead of one signal per room, generates a signal for EACH DAY on the
forward curve path. This allows traders to see: "CALL today, PUT tomorrow,
CALL the day after."

Consumes forward curve points (from forward_curve.py) — does NOT modify them.
Stores results in analytical_cache.db via AnalyticalCache.

Safety: This is a NEW file. Does not modify any existing file.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Signal Thresholds ────────────────────────────────────────────────
# These are for daily signals, different from the main consensus thresholds.
# Daily signal looks at day-over-day predicted change from forward curve.

DAILY_CALL_THRESHOLD = 0.5     # ≥ +0.5% day-over-day → CALL
DAILY_PUT_THRESHOLD = -0.5     # ≤ -0.5% day-over-day → PUT
# Between -0.5% and +0.5% → NEUTRAL

# Confidence scaling based on enrichment strength
CONFIDENCE_BASE = 0.5
CONFIDENCE_ENRICHMENT_BOOST = 0.3  # Max boost from enrichments


def generate_daily_signals(
    forward_curve_points: list[dict],
    detail_id: int,
    hotel_id: int,
    enrichments: Optional[dict] = None,
) -> list[dict]:
    """Generate per-day CALL/PUT/NEUTRAL signals from forward curve.

    Args:
        forward_curve_points: List of dicts with at minimum:
            - date (str), t (int), predicted_price (float), daily_change_pct (float)
            Optional: event_adj_pct, season_adj_pct, demand_adj_pct, etc.
        detail_id: Room detail ID
        hotel_id: Hotel ID
        enrichments: Optional dict of enrichment overrides

    Returns:
        List of daily signal dicts ready for AnalyticalCache.save_daily_signals()
    """
    if not forward_curve_points:
        return []

    signals = []
    for point in forward_curve_points:
        daily_pct = point.get("daily_change_pct", 0.0)
        predicted_price = point.get("predicted_price", 0.0)
        t_value = point.get("t", 0)
        signal_date = point.get("date", "")

        if not signal_date or predicted_price <= 0:
            continue

        # Determine signal direction
        signal = _classify_daily_signal(daily_pct)

        # Calculate confidence from enrichment alignment
        enrichment_data = _extract_enrichments(point, enrichments)
        confidence = _compute_daily_confidence(daily_pct, enrichment_data, t_value)

        signals.append({
            "detail_id": detail_id,
            "hotel_id": hotel_id,
            "signal_date": signal_date,
            "t_value": t_value,
            "predicted_price": round(predicted_price, 2),
            "daily_change_pct": round(daily_pct, 4),
            "signal": signal,
            "confidence": round(confidence, 3),
            "enrichments": enrichment_data,
        })

    logger.debug(
        "Generated %d daily signals for detail_id=%s (CALL=%d, PUT=%d, NEUTRAL=%d)",
        len(signals), detail_id,
        sum(1 for s in signals if s["signal"] == "CALL"),
        sum(1 for s in signals if s["signal"] == "PUT"),
        sum(1 for s in signals if s["signal"] == "NEUTRAL"),
    )
    return signals


def _classify_daily_signal(daily_change_pct: float) -> str:
    """Classify a daily price change into CALL/PUT/NEUTRAL."""
    if daily_change_pct >= DAILY_CALL_THRESHOLD:
        return "CALL"
    elif daily_change_pct <= DAILY_PUT_THRESHOLD:
        return "PUT"
    return "NEUTRAL"


def _extract_enrichments(point: dict, overrides: Optional[dict] = None) -> dict:
    """Extract enrichment values from a forward curve point."""
    enrichment_keys = [
        "event_adj_pct", "season_adj_pct", "demand_adj_pct",
        "momentum_adj_pct", "weather_adj_pct", "competitor_adj_pct",
        "cancellation_adj_pct", "provider_adj_pct",
    ]
    data = {}
    for key in enrichment_keys:
        val = point.get(key, 0.0)
        if overrides and key in overrides:
            val = overrides[key]
        if val != 0.0:
            data[key] = round(val, 4)
    return data


def _compute_daily_confidence(daily_pct: float, enrichments: dict, t_value: int) -> float:
    """Compute confidence for a daily signal.

    Higher confidence when:
    - The daily change is large (strong directional move)
    - Multiple enrichments agree on the direction
    - T is low (closer to check-in, more data available)
    """
    # Base confidence from magnitude of change
    magnitude = abs(daily_pct)
    if magnitude >= 2.0:
        base = 0.85
    elif magnitude >= 1.0:
        base = 0.70
    elif magnitude >= 0.5:
        base = 0.55
    else:
        base = 0.40  # NEUTRAL range — low confidence

    # Enrichment agreement boost
    # Count how many enrichments agree with the signal direction
    positive_enrichments = sum(1 for v in enrichments.values() if v > 0)
    negative_enrichments = sum(1 for v in enrichments.values() if v < 0)
    total_enrichments = len(enrichments)

    if total_enrichments > 0:
        if daily_pct > 0:
            agreement = positive_enrichments / total_enrichments
        elif daily_pct < 0:
            agreement = negative_enrichments / total_enrichments
        else:
            agreement = 0.5
        enrichment_boost = agreement * CONFIDENCE_ENRICHMENT_BOOST
    else:
        enrichment_boost = 0.0

    # T-proximity boost: closer to check-in = more reliable
    t_boost = 0.0
    if t_value <= 7:
        t_boost = 0.10  # Very close — high confidence
    elif t_value <= 14:
        t_boost = 0.05
    elif t_value <= 30:
        t_boost = 0.02

    confidence = min(0.95, base + enrichment_boost + t_boost)
    return confidence


def summarize_signals(signals: list[dict]) -> dict:
    """Create a summary of daily signals for display.

    Returns signal counts, dominant trend, and next-7-day outlook.
    """
    if not signals:
        return {"total": 0, "calls": 0, "puts": 0, "neutrals": 0, "trend": "NEUTRAL"}

    calls = sum(1 for s in signals if s["signal"] == "CALL")
    puts = sum(1 for s in signals if s["signal"] == "PUT")
    neutrals = sum(1 for s in signals if s["signal"] == "NEUTRAL")

    # Dominant trend
    if calls > puts + neutrals:
        trend = "BULLISH"
    elif puts > calls + neutrals:
        trend = "BEARISH"
    elif calls > puts:
        trend = "MILDLY_BULLISH"
    elif puts > calls:
        trend = "MILDLY_BEARISH"
    else:
        trend = "NEUTRAL"

    # Next 7 days
    next_7 = signals[:7] if len(signals) >= 7 else signals
    next_7_calls = sum(1 for s in next_7 if s["signal"] == "CALL")
    next_7_puts = sum(1 for s in next_7 if s["signal"] == "PUT")

    return {
        "total": len(signals),
        "calls": calls,
        "puts": puts,
        "neutrals": neutrals,
        "trend": trend,
        "next_7_days": {
            "calls": next_7_calls,
            "puts": next_7_puts,
            "neutrals": len(next_7) - next_7_calls - next_7_puts,
            "signals": [{"date": s["signal_date"], "signal": s["signal"],
                         "change": s["daily_change_pct"]} for s in next_7],
        },
    }
