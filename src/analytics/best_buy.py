"""Best Buy Opportunity Analyzer — ranks rooms by purchase attractiveness.

Composite score: ADR gap (25%) + Zone avg gap (25%) + Signal strength (20%)
                 + Velocity (15%) + Consensus (15%)

Returns Top N opportunities sorted by score with Strong Buy / Buy / Watch / Avoid labels.
"""
from __future__ import annotations

import logging
from typing import Optional

from config.hotel_segments import HOTEL_SEGMENTS, ZONES, get_hotel_segment

logger = logging.getLogger(__name__)

# Official GMCVB ADR benchmarks per zone (USD)
ZONE_ADR = {
    "south_beach": 380,
    "mid_beach": 420,
    "downtown": 280,
    "brickell": 280,
    "airport": 150,
    "sunny_isles": 300,
}

# Score thresholds
STRONG_BUY_THRESHOLD = 0.45
BUY_THRESHOLD = 0.30
WATCH_THRESHOLD = 0.20


def compute_best_buy(analysis: dict, top_n: int = 20) -> list[dict]:
    """Compute best-buy opportunities from a precomputed analysis result.

    Args:
        analysis: The result from _get_or_run_analysis() containing 'rooms'.
        top_n: Number of top opportunities to return.

    Returns:
        List of opportunity dicts sorted by composite score descending.
    """
    rooms = analysis.get("rooms") or []
    if not rooms:
        return []

    # Build zone averages
    zone_prices: dict[str, list[float]] = {}
    for room in rooms:
        price = room.get("room_price") or room.get("price")
        hotel_id = room.get("hotel_id")
        if not price or not hotel_id or price <= 0:
            continue
        seg = HOTEL_SEGMENTS.get(hotel_id)
        if seg:
            zone = seg["zone"]
            zone_prices.setdefault(zone, []).append(price)

    zone_avg = {z: sum(ps) / len(ps) for z, ps in zone_prices.items() if ps}

    opportunities = []

    for room in rooms:
        price = room.get("room_price") or room.get("price")
        hotel_id = room.get("hotel_id")
        detail_id = room.get("detail_id") or room.get("id")
        if not price or price <= 0 or not hotel_id:
            continue

        seg = HOTEL_SEGMENTS.get(hotel_id)
        if not seg:
            continue

        zone = seg["zone"]
        tier = seg["tier"]
        hotel_name = seg.get("name", f"Hotel {hotel_id}")

        # Signal
        signal = room.get("signal", "NEUTRAL")
        confidence = room.get("confidence", 0) or 0

        # Velocity (daily change %)
        velocity = room.get("daily_change_pct", 0) or 0

        # Consensus
        consensus_prob = room.get("consensus_probability", 0) or 0

        # ADR gap
        adr = ZONE_ADR.get(zone, 300)
        adr_gap = max(0, (adr - price) / adr) if adr > 0 else 0

        # Zone avg gap
        z_avg = zone_avg.get(zone, price)
        zone_gap = max(0, (z_avg - price) / z_avg) if z_avg > 0 else 0

        # Signal score (CALL=1.0, NEUTRAL=0.3, PUT=0.0)
        if signal == "CALL":
            signal_score = min(1.0, confidence)
        elif signal == "NEUTRAL":
            signal_score = 0.3
        else:
            signal_score = 0.0

        # Velocity score (positive velocity = good, capped at ±100%)
        vel_score = max(0, min(1.0, (velocity + 50) / 100)) if velocity > -50 else 0.0

        # Consensus score
        consensus_score = min(1.0, consensus_prob / 100) if consensus_prob else 0.15

        # Composite
        composite = (
            adr_gap * 0.25
            + zone_gap * 0.25
            + signal_score * 0.20
            + vel_score * 0.15
            + consensus_score * 0.15
        )

        # Label
        if composite >= STRONG_BUY_THRESHOLD:
            label = "STRONG BUY"
        elif composite >= BUY_THRESHOLD:
            label = "BUY"
        elif composite >= WATCH_THRESHOLD:
            label = "WATCH"
        else:
            label = "AVOID"

        # Skip PUT signals
        if signal == "PUT" and confidence > 0.5:
            label = "AVOID"

        category = room.get("category", "")
        board = room.get("board", "")
        t_value = room.get("t_value") or room.get("T")

        opportunities.append({
            "detail_id": detail_id,
            "hotel_id": hotel_id,
            "hotel_name": hotel_name,
            "zone": ZONES.get(zone, {}).get("name", zone),
            "tier": tier.title(),
            "category": category,
            "board": board,
            "price": round(price, 2),
            "adr_benchmark": adr,
            "adr_gap_pct": round(adr_gap * 100, 1),
            "zone_avg": round(z_avg, 2),
            "zone_gap_pct": round(zone_gap * 100, 1),
            "signal": signal,
            "confidence": round(confidence, 2),
            "velocity_pct": round(velocity, 1),
            "consensus_pct": round(consensus_prob, 1),
            "composite_score": round(composite, 3),
            "label": label,
            "t_value": t_value,
        })

    # Sort by composite score descending
    opportunities.sort(key=lambda x: x["composite_score"], reverse=True)

    return opportunities[:top_n]
