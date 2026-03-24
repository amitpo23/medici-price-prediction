"""Arbitrage Engine — identifies buy/sell points along the T timeline.

For each option, scans the forward curve to find:
- Buy Point: lowest predicted price (best time to buy)
- Sell Point: highest predicted price after the buy point
- Arbitrage Profit: sell - buy
- Zone coloring: green (rising), red (falling), gray (flat)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Zone thresholds — price change > 1% triggers color
ZONE_THRESHOLD_PCT = 1.0
# Minimum arbitrage profit to be considered significant
MIN_ARBITRAGE_USD = 1.0


def _classify_zone(prev_price: float, curr_price: float) -> str:
    """Classify a point as green/red/gray based on price change from previous."""
    if prev_price <= 0:
        return "gray"
    change_pct = ((curr_price - prev_price) / prev_price) * 100.0
    if change_pct > ZONE_THRESHOLD_PCT:
        return "green"
    elif change_pct < -ZONE_THRESHOLD_PCT:
        return "red"
    return "gray"


def _build_timeline(fc_points: List[dict], current_price: float) -> List[dict]:
    """Build timeline with zone coloring for each FC point.

    FC points are ordered from T=high (far future) to T=low (near checkin).
    """
    timeline = []  # type: List[dict]
    prev_price = current_price

    for pt in fc_points:
        price = float(pt.get("predicted_price", 0) or 0)
        t_days = int(pt.get("t", 0) or 0)
        date = pt.get("date", "")

        zone = _classify_zone(prev_price, price)
        timeline.append({
            "date": date,
            "t_days": t_days,
            "predicted_price": round(price, 2),
            "zone": zone,
        })
        prev_price = price

    return timeline


def _find_buy_sell_points(
    timeline: List[dict],
) -> tuple:
    """Find optimal buy and sell points.

    Buy = lowest price point in the timeline.
    Sell = highest price point AFTER buy in time (sell_t < buy_t).

    Returns (buy_point, sell_point) or (None, None) if not feasible.
    """
    if not timeline:
        return None, None

    # Find the lowest price point (buy candidate)
    buy_idx = 0
    buy_price = timeline[0]["predicted_price"]
    for i, pt in enumerate(timeline):
        if pt["predicted_price"] < buy_price:
            buy_price = pt["predicted_price"]
            buy_idx = i

    buy_point = {
        "date": timeline[buy_idx]["date"],
        "t_days": timeline[buy_idx]["t_days"],
        "price": timeline[buy_idx]["predicted_price"],
        "reason": "lowest predicted price on forward curve",
    }

    # Find highest price AFTER buy in time (lower t_days = later in time)
    # Points after buy_idx in the list have lower t values (closer to checkin)
    sell_point = None
    sell_price = -1.0
    for i in range(buy_idx + 1, len(timeline)):
        pt = timeline[i]
        if pt["predicted_price"] > sell_price:
            sell_price = pt["predicted_price"]
            sell_point = {
                "date": pt["date"],
                "t_days": pt["t_days"],
                "price": pt["predicted_price"],
                "reason": "highest predicted price after buy point",
            }

    # If no point after buy, check if buy is last point — no sell possible
    if sell_point is None:
        # Fall back: sell at the last point if it's different from buy
        if len(timeline) > 1 and buy_idx < len(timeline) - 1:
            last = timeline[-1]
            sell_point = {
                "date": last["date"],
                "t_days": last["t_days"],
                "price": last["predicted_price"],
                "reason": "last point on forward curve (no better option)",
            }

    return buy_point, sell_point


def _build_zones(timeline: List[dict]) -> List[dict]:
    """Group consecutive same-zone points into signal zones.

    Each zone has start_t, end_t, signal (CALL/PUT/NEUTRAL), and reason.
    """
    if not timeline:
        return []

    zone_map = {"green": "CALL", "red": "PUT", "gray": "NEUTRAL"}
    reason_map = {
        "green": "price rising",
        "red": "price declining",
        "gray": "price stable / transition",
    }

    zones = []  # type: List[dict]
    current_zone = timeline[0]["zone"]
    start_t = timeline[0]["t_days"]

    for i in range(1, len(timeline)):
        pt = timeline[i]
        if pt["zone"] != current_zone:
            # Close current zone
            zones.append({
                "start_t": start_t,
                "end_t": timeline[i - 1]["t_days"],
                "signal": zone_map.get(current_zone, "NEUTRAL"),
                "reason": reason_map.get(current_zone, ""),
            })
            current_zone = pt["zone"]
            start_t = pt["t_days"]

    # Close last zone
    zones.append({
        "start_t": start_t,
        "end_t": timeline[-1]["t_days"],
        "signal": zone_map.get(current_zone, "NEUTRAL"),
        "reason": reason_map.get(current_zone, ""),
    })

    return zones


def compute_arbitrage_timeline(
    pred: dict,
    zone_avg: float = 0,
    official_adr: float = 0,
) -> dict:
    """Compute T-timeline with per-period signals and arbitrage opportunities.

    Args:
        pred: Prediction dict with forward_curve, current_price, hotel_name, etc.
        zone_avg: Average price in the competitive zone (for context).
        official_adr: Official ADR for the hotel (for context).

    Returns:
        Dict with timeline, buy_point, sell_point, arbitrage, and zones.
    """
    detail_id = pred.get("detail_id", 0)
    hotel_name = pred.get("hotel_name", "")
    current_price = float(pred.get("current_price", 0) or 0)
    t_days = int(pred.get("days_to_checkin", 0) or 0)

    fc = pred.get("forward_curve") or []

    # Normalize FC points to dicts (may be dataclass objects)
    fc_points = []  # type: List[dict]
    for pt in fc:
        if isinstance(pt, dict):
            fc_points.append(pt)
        elif hasattr(pt, "__dict__"):
            fc_points.append(pt.__dict__)
        else:
            continue

    result = {
        "detail_id": detail_id,
        "hotel_name": hotel_name,
        "current_price": current_price,
        "T": t_days,
        "zone_avg": round(zone_avg, 2),
        "official_adr": round(official_adr, 2),
        "timeline": [],
        "buy_point": None,
        "sell_point": None,
        "arbitrage": {
            "profit_usd": 0.0,
            "profit_pct": 0.0,
            "buy_price": 0.0,
            "sell_price": 0.0,
            "buy_date": "",
            "sell_date": "",
            "buy_t": 0,
            "sell_t": 0,
            "feasible": False,
        },
        "zones": [],
    }

    if not fc_points:
        logger.debug("No forward curve for detail_id=%s", detail_id)
        return result

    # Build timeline with zone coloring
    timeline = _build_timeline(fc_points, current_price)
    result["timeline"] = timeline

    # Find buy/sell points
    buy_point, sell_point = _find_buy_sell_points(timeline)
    result["buy_point"] = buy_point
    result["sell_point"] = sell_point

    # Compute arbitrage
    if buy_point and sell_point:
        buy_price = buy_point["price"]
        sell_price = sell_point["price"]
        profit_usd = sell_price - buy_price
        profit_pct = (profit_usd / buy_price * 100.0) if buy_price > 0 else 0.0
        # Feasible if buy happens before sell in time (buy_t > sell_t)
        feasible = buy_point["t_days"] > sell_point["t_days"] and profit_usd >= MIN_ARBITRAGE_USD

        result["arbitrage"] = {
            "profit_usd": round(profit_usd, 2),
            "profit_pct": round(profit_pct, 2),
            "buy_price": round(buy_price, 2),
            "sell_price": round(sell_price, 2),
            "buy_date": buy_point["date"],
            "sell_date": sell_point["date"],
            "buy_t": buy_point["t_days"],
            "sell_t": sell_point["t_days"],
            "feasible": feasible,
        }

    # Build zone segments
    result["zones"] = _build_zones(timeline)

    return result
