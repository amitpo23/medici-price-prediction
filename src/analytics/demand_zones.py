"""Demand Zone Detection — Support/Resistance levels from price history.

A Demand Zone is a price level where a room has reversed direction
at least twice within a lookback window. Analogous to ICT/SMC concepts:
  - SUPPORT: Price bounced UP from this level (buy zone)
  - RESISTANCE: Price bounced DOWN from this level (sell zone)

Also detects Break of Structure (BOS) and Change of Character (CHOCH).

Consumes data from price_store.py (local SQLite snapshots).
Does NOT modify any existing file.

Safety: This is a NEW file.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

# Lookback window for zone detection
LOOKBACK_DAYS = 90

# Minimum reversals to form a valid zone
MIN_TOUCHES = 2

# Price clustering tolerance (% range for grouping reversals)
ZONE_TOLERANCE_PCT = 3.0

# Recency decay half-life (days) — recent touches weighted higher
RECENCY_HALF_LIFE = 14

# Minimum price change (%) to qualify as a reversal
MIN_REVERSAL_PCT = 1.0

# BOS: price must break previous high/low by this %
BOS_BREAK_THRESHOLD_PCT = 0.5


def detect_demand_zones(
    price_history: pd.DataFrame,
    hotel_id: int,
    category: str = "",
) -> list[dict]:
    """Detect demand zones from historical price snapshots.

    Args:
        price_history: DataFrame with columns: snapshot_ts, room_price, date_from
            Sorted by snapshot_ts ascending.
        hotel_id: Hotel ID
        category: Room category filter

    Returns:
        List of demand zone dicts ready for AnalyticalCache.save_demand_zones()
    """
    if price_history.empty or len(price_history) < 10:
        logger.debug("Insufficient price history for hotel_id=%s (rows=%d)", hotel_id, len(price_history))
        return []

    prices = price_history["room_price"].values
    timestamps = price_history["snapshot_ts"].values

    # Step 1: Find reversal points (local minima and maxima)
    reversals = _find_reversals(prices, timestamps)
    if len(reversals) < MIN_TOUCHES:
        return []

    # Step 2: Cluster reversals into zones
    zones = _cluster_into_zones(reversals, hotel_id, category)

    # Step 3: Calculate zone strength with recency weighting
    for zone in zones:
        zone["strength"] = _calculate_zone_strength(zone)

    # Filter: only zones with enough touches
    valid_zones = [z for z in zones if z["touch_count"] >= MIN_TOUCHES]

    logger.info(
        "Detected %d demand zones for hotel_id=%s category=%s (%d support, %d resistance)",
        len(valid_zones), hotel_id, category,
        sum(1 for z in valid_zones if z["zone_type"] == "SUPPORT"),
        sum(1 for z in valid_zones if z["zone_type"] == "RESISTANCE"),
    )
    return valid_zones


def _find_reversals(prices: np.ndarray, timestamps: np.ndarray) -> list[dict]:
    """Find local minima (support) and maxima (resistance) in price series."""
    reversals = []
    n = len(prices)
    if n < 3:
        return reversals

    for i in range(1, n - 1):
        prev_price = prices[i - 1]
        curr_price = prices[i]
        next_price = prices[i + 1]

        if prev_price == 0 or curr_price == 0:
            continue

        change_before = (curr_price - prev_price) / prev_price * 100
        change_after = (next_price - curr_price) / curr_price * 100

        # Local minimum: price was falling, then starts rising
        if change_before <= -MIN_REVERSAL_PCT and change_after >= MIN_REVERSAL_PCT:
            reversals.append({
                "price": float(curr_price),
                "type": "SUPPORT",
                "timestamp": str(timestamps[i]),
                "idx": i,
            })

        # Local maximum: price was rising, then starts falling
        elif change_before >= MIN_REVERSAL_PCT and change_after <= -MIN_REVERSAL_PCT:
            reversals.append({
                "price": float(curr_price),
                "type": "RESISTANCE",
                "timestamp": str(timestamps[i]),
                "idx": i,
            })

    return reversals


def _cluster_into_zones(reversals: list[dict], hotel_id: int, category: str) -> list[dict]:
    """Cluster nearby reversals into demand zones.

    Reversals within ZONE_TOLERANCE_PCT of each other get grouped.
    """
    if not reversals:
        return []

    # Sort by price
    sorted_revs = sorted(reversals, key=lambda r: r["price"])

    zones = []
    used = set()

    for i, rev in enumerate(sorted_revs):
        if i in used:
            continue

        # Start a new cluster with this reversal
        cluster = [rev]
        used.add(i)

        # Find all reversals within tolerance
        for j in range(i + 1, len(sorted_revs)):
            if j in used:
                continue
            other = sorted_revs[j]
            price_diff_pct = abs(other["price"] - rev["price"]) / rev["price"] * 100
            if price_diff_pct <= ZONE_TOLERANCE_PCT and other["type"] == rev["type"]:
                cluster.append(other)
                used.add(j)

        if len(cluster) >= MIN_TOUCHES:
            cluster_prices = [r["price"] for r in cluster]
            timestamps = [r["timestamp"] for r in cluster]

            zone_id = _make_zone_id(hotel_id, category, rev["type"], min(cluster_prices))

            zones.append({
                "zone_id": zone_id,
                "hotel_id": hotel_id,
                "category": category,
                "zone_type": rev["type"],
                "price_lower": round(min(cluster_prices), 2),
                "price_upper": round(max(cluster_prices), 2),
                "touch_count": len(cluster),
                "first_touch": min(timestamps),
                "last_touch": max(timestamps),
                "is_broken": False,
                "touches": cluster,  # For strength calculation
            })

    return zones


def _calculate_zone_strength(zone: dict) -> float:
    """Calculate zone strength with recency-weighted touch count.

    Strength = sum of recency weights for each touch, normalized to 0-1.
    """
    touches = zone.get("touches", [])
    if not touches:
        return 0.0

    now = datetime.utcnow()
    total_weight = 0.0

    for touch in touches:
        try:
            ts = datetime.fromisoformat(str(touch["timestamp"]).replace("Z", "+00:00").split("+")[0])
            days_ago = (now - ts).days
        except (ValueError, TypeError):
            days_ago = LOOKBACK_DAYS  # Default to old

        # Exponential decay: recent touches count more
        weight = 2 ** (-days_ago / RECENCY_HALF_LIFE)
        total_weight += weight

    # Normalize: 2 touches at half-life = 0.5 strength
    # 4+ recent touches = ~1.0 strength
    strength = min(1.0, total_weight / 3.0)
    return round(strength, 3)


def _make_zone_id(hotel_id: int, category: str, zone_type: str, price: float) -> str:
    """Generate a stable zone ID from its key properties."""
    raw = f"{hotel_id}_{category}_{zone_type}_{price:.0f}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ── Break of Structure Detection ─────────────────────────────────────

def detect_structure_breaks(
    price_history: pd.DataFrame,
    hotel_id: int,
    category: str = "",
    demand_zones: Optional[list[dict]] = None,
) -> list[dict]:
    """Detect Break of Structure (BOS) and Change of Character (CHOCH).

    BOS: Price breaks above previous resistance (bullish) or below support (bearish).
    CHOCH: A series of higher-highs reverses to a lower-low, or vice versa.

    Args:
        price_history: DataFrame with room_price, snapshot_ts columns
        hotel_id: Hotel ID
        category: Room category
        demand_zones: Optional pre-computed demand zones

    Returns:
        List of structure break dicts
    """
    if price_history.empty or len(price_history) < 10:
        return []

    prices = price_history["room_price"].values
    timestamps = price_history["snapshot_ts"].values
    breaks = []

    # Find swing highs and lows (simplified)
    swing_highs = []
    swing_lows = []

    window = 5  # Look at 5-scan windows for swing detection
    for i in range(window, len(prices) - window):
        local_max = max(prices[i - window:i + window + 1])
        local_min = min(prices[i - window:i + window + 1])

        if prices[i] == local_max and prices[i] > 0:
            swing_highs.append({"price": float(prices[i]), "idx": i, "ts": str(timestamps[i])})
        elif prices[i] == local_min and prices[i] > 0:
            swing_lows.append({"price": float(prices[i]), "idx": i, "ts": str(timestamps[i])})

    # Detect BOS: current price breaks above previous swing high
    if len(swing_highs) >= 2:
        latest_price = float(prices[-1])
        prev_high = swing_highs[-2]["price"]  # Second-to-last swing high

        if latest_price > prev_high * (1 + BOS_BREAK_THRESHOLD_PCT / 100):
            break_id = _make_zone_id(hotel_id, category, "BOS_BULL", latest_price)
            breaks.append({
                "break_id": break_id,
                "hotel_id": hotel_id,
                "category": category,
                "break_type": "BOS",
                "break_date": str(timestamps[-1]).split(" ")[0] if " " in str(timestamps[-1]) else str(timestamps[-1])[:10],
                "break_price": latest_price,
                "previous_level": prev_high,
                "direction": "BULLISH",
                "significance": min(1.0, (latest_price - prev_high) / prev_high * 10),
            })

    if len(swing_lows) >= 2:
        latest_price = float(prices[-1])
        prev_low = swing_lows[-2]["price"]

        if latest_price < prev_low * (1 - BOS_BREAK_THRESHOLD_PCT / 100):
            break_id = _make_zone_id(hotel_id, category, "BOS_BEAR", latest_price)
            breaks.append({
                "break_id": break_id,
                "hotel_id": hotel_id,
                "category": category,
                "break_type": "BOS",
                "break_date": str(timestamps[-1]).split(" ")[0] if " " in str(timestamps[-1]) else str(timestamps[-1])[:10],
                "break_price": latest_price,
                "previous_level": prev_low,
                "direction": "BEARISH",
                "significance": min(1.0, (prev_low - latest_price) / prev_low * 10),
            })

    # Detect CHOCH: change of character (series of HH→LL or LL→HH)
    if len(swing_highs) >= 3 and len(swing_lows) >= 3:
        choch = _detect_choch(swing_highs, swing_lows, hotel_id, category, timestamps)
        breaks.extend(choch)

    # Mark broken demand zones
    if demand_zones and breaks:
        for brk in breaks:
            for zone in demand_zones:
                if brk["direction"] == "BULLISH" and zone["zone_type"] == "RESISTANCE":
                    if brk["break_price"] > zone["price_upper"]:
                        zone["is_broken"] = True
                elif brk["direction"] == "BEARISH" and zone["zone_type"] == "SUPPORT":
                    if brk["break_price"] < zone["price_lower"]:
                        zone["is_broken"] = True

    logger.info(
        "Detected %d structure breaks for hotel_id=%s (%d BOS, %d CHOCH)",
        len(breaks), hotel_id,
        sum(1 for b in breaks if b["break_type"] == "BOS"),
        sum(1 for b in breaks if b["break_type"] == "CHOCH"),
    )
    return breaks


def _detect_choch(
    swing_highs: list[dict],
    swing_lows: list[dict],
    hotel_id: int,
    category: str,
    timestamps: np.ndarray,
) -> list[dict]:
    """Detect Change of Character (CHOCH).

    CHOCH occurs when:
    - After a series of higher highs, a lower high appears (bearish CHOCH)
    - After a series of lower lows, a higher low appears (bullish CHOCH)
    """
    choch_breaks = []

    # Check for bearish CHOCH: HH → LH
    if len(swing_highs) >= 3:
        h1, h2, h3 = swing_highs[-3]["price"], swing_highs[-2]["price"], swing_highs[-1]["price"]
        if h1 < h2 and h3 < h2:  # Was making HH, now made LH
            break_id = _make_zone_id(hotel_id, category, "CHOCH_BEAR", h3)
            choch_breaks.append({
                "break_id": break_id,
                "hotel_id": hotel_id,
                "category": category,
                "break_type": "CHOCH",
                "break_date": swing_highs[-1]["ts"].split(" ")[0] if " " in swing_highs[-1]["ts"] else swing_highs[-1]["ts"][:10],
                "break_price": h3,
                "previous_level": h2,
                "direction": "BEARISH",
                "significance": min(1.0, abs(h2 - h3) / h2 * 10),
            })

    # Check for bullish CHOCH: LL → HL
    if len(swing_lows) >= 3:
        l1, l2, l3 = swing_lows[-3]["price"], swing_lows[-2]["price"], swing_lows[-1]["price"]
        if l1 > l2 and l3 > l2:  # Was making LL, now made HL
            break_id = _make_zone_id(hotel_id, category, "CHOCH_BULL", l3)
            choch_breaks.append({
                "break_id": break_id,
                "hotel_id": hotel_id,
                "category": category,
                "break_type": "CHOCH",
                "break_date": swing_lows[-1]["ts"].split(" ")[0] if " " in swing_lows[-1]["ts"] else swing_lows[-1]["ts"][:10],
                "break_price": l3,
                "previous_level": l2,
                "direction": "BULLISH",
                "significance": min(1.0, abs(l3 - l2) / l2 * 10),
            })

    return choch_breaks
