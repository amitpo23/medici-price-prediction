"""Best Sell Analyzer — ranks rooms by overpricing / sell urgency.

Identifies rooms priced ABOVE market value that should be overridden down.
Mirror of best_buy.py — same composite approach, inverted logic.

Labels: STRONG SELL / SELL / OVERPRICED / FAIR PRICE
"""
from __future__ import annotations

import logging

from config.hotel_segments import HOTEL_SEGMENTS, ZONES

logger = logging.getLogger(__name__)

ZONE_ADR = {
    "south_beach": 380,
    "mid_beach": 420,
    "downtown": 280,
    "brickell": 280,
    "airport": 150,
    "sunny_isles": 300,
}

STRONG_SELL_THRESHOLD = 0.45
SELL_THRESHOLD = 0.30
OVERPRICED_THRESHOLD = 0.20


def compute_best_sell(analysis: dict, top_n: int = 20) -> list[dict]:
    """Compute overpriced rooms from analysis result.

    Returns list sorted by overpricing score descending.
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
            zone_prices.setdefault(seg["zone"], []).append(price)

    zone_avg = {z: sum(ps) / len(ps) for z, ps in zone_prices.items() if ps}

    results = []

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

        signal = room.get("signal", "NEUTRAL")
        confidence = room.get("confidence", 0) or 0
        velocity = room.get("daily_change_pct", 0) or 0
        consensus_prob = room.get("consensus_probability", 0) or 0

        adr = ZONE_ADR.get(zone, 300)
        z_avg = zone_avg.get(zone, price)

        # Overpricing gaps (positive = overpriced)
        adr_over = max(0, (price - adr) / adr) if adr > 0 else 0
        zone_over = max(0, (price - z_avg) / z_avg) if z_avg > 0 else 0

        # PUT signal score (PUT=1.0, NEUTRAL=0.3, CALL=0.0)
        if signal == "PUT":
            signal_score = min(1.0, confidence)
        elif signal == "NEUTRAL":
            signal_score = 0.3
        else:
            signal_score = 0.0

        # Negative velocity score (more negative = higher sell urgency)
        vel_score = max(0, min(1.0, (-velocity) / 50)) if velocity < 0 else 0.0

        # Consensus score (for PUT)
        consensus_score = min(1.0, consensus_prob / 100) if consensus_prob else 0.15

        # Composite overpricing score
        composite = (
            adr_over * 0.25
            + zone_over * 0.25
            + signal_score * 0.20
            + vel_score * 0.15
            + consensus_score * 0.15
        )

        # Only include if there's some overpricing signal
        if composite < 0.05:
            continue

        # Label
        if composite >= STRONG_SELL_THRESHOLD:
            label = "STRONG SELL"
        elif composite >= SELL_THRESHOLD:
            label = "SELL"
        elif composite >= OVERPRICED_THRESHOLD:
            label = "OVERPRICED"
        else:
            label = "FAIR PRICE"

        # Boost PUT signals
        if signal == "PUT" and confidence > 0.5:
            if label == "OVERPRICED":
                label = "SELL"

        # Fair market price estimate (zone avg)
        fair_price = round(z_avg, 2)
        overpricing_usd = round(price - z_avg, 2) if price > z_avg else 0

        category = room.get("category", "")
        board = room.get("board", "")
        t_value = room.get("t_value") or room.get("T")

        results.append({
            "detail_id": detail_id,
            "hotel_id": hotel_id,
            "hotel_name": hotel_name,
            "zone": ZONES.get(zone, {}).get("name", zone),
            "tier": tier.title(),
            "category": category,
            "board": board,
            "price": round(price, 2),
            "fair_price": fair_price,
            "overpricing_usd": overpricing_usd,
            "adr_benchmark": adr,
            "adr_over_pct": round(adr_over * 100, 1),
            "zone_avg": round(z_avg, 2),
            "zone_over_pct": round(zone_over * 100, 1),
            "signal": signal,
            "confidence": round(confidence, 2),
            "velocity_pct": round(velocity, 1),
            "consensus_pct": round(consensus_prob, 1),
            "composite_score": round(composite, 3),
            "label": label,
            "t_value": t_value,
        })

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results[:top_n]
