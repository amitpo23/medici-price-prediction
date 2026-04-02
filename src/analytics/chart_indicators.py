"""Chart Indicators Aggregator — Assembles 20 indicators for the Trading Chart.

Collects time series from DB, SQLite, collectors, and enrichments.
Applies correlation grouping, T-aware filtering, and type weights.
Computes BUY/SELL consensus signals.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Indicator Definitions ────────────────────────────────────────────────

INDICATOR_DEFS = {
    # Group A: Price
    "price_scan":      {"label": "Price Scan",       "group": "price",  "color": "#FFFFFF", "style": "solid",  "unit": "$",           "type": "coincident"},
    "forward_curve":   {"label": "Forward Curve",    "group": "price",  "color": "#00E5FF", "style": "dashed", "unit": "$",           "type": "leading"},
    "historical_t":    {"label": "Historical T",     "group": "price",  "color": "#FFD600", "style": "dotted", "unit": "$",           "type": "lagging"},
    "yoy_price":       {"label": "YoY Price",        "group": "price",  "color": "#9E9E9E", "style": "dotted", "unit": "$",           "type": "lagging"},
    "prophet":         {"label": "Prophet Forecast",  "group": "price",  "color": "#E040FB", "style": "dashed", "unit": "$",           "type": "leading"},
    # Group B: Demand
    "booking_velocity": {"label": "Booking Velocity", "group": "demand", "color": "#4CAF50", "style": "solid", "unit": "bookings/day", "type": "leading"},
    "cancel_rate":     {"label": "Cancellation Rate", "group": "demand", "color": "#F44336", "style": "solid",  "unit": "%",           "type": "lagging"},
    "price_velocity":  {"label": "Price Velocity",    "group": "demand", "color": "#FF9800", "style": "solid",  "unit": "changes/day", "type": "coincident"},
    "bts_flights":     {"label": "BTS Flights (MIA)", "group": "demand", "color": "#9C27B0", "style": "dashed", "unit": "pax/mo",      "type": "leading"},
    # Group C: Supply
    "provider_count":  {"label": "Provider Count",    "group": "supply", "color": "#2196F3", "style": "solid",  "unit": "count",       "type": "coincident"},
    "competitor_avg":  {"label": "Competitor Avg",     "group": "supply", "color": "#FF5722", "style": "solid",  "unit": "$",           "type": "coincident"},
    "browser_rank":    {"label": "Browser Rank",       "group": "supply", "color": "#CDDC39", "style": "solid",  "unit": "rank",        "type": "coincident"},
    "airbnb_avg":      {"label": "Airbnb Avg",         "group": "supply", "color": "#FF6D00", "style": "dashed", "unit": "$",           "type": "coincident"},
    # Group D: Macro
    "jets_etf":        {"label": "JETS ETF",          "group": "macro",  "color": "#4CAF50", "style": "solid",  "unit": "$",           "type": "leading"},
    "vix":             {"label": "VIX Index",         "group": "macro",  "color": "#F44336", "style": "solid",  "unit": "index",       "type": "leading"},
    "hotel_reits":     {"label": "Hotel REITs Avg",   "group": "macro",  "color": "#2196F3", "style": "solid",  "unit": "$",           "type": "leading"},
    "hotel_ppi":       {"label": "Hotel PPI",         "group": "macro",  "color": "#9E9E9E", "style": "dashed", "unit": "index",       "type": "lagging"},
    # Group E: Environment
    "events":          {"label": "Events Impact",     "group": "env",    "color": "#E91E63", "style": "solid",  "unit": "%",           "type": "leading"},
    "seasonality":     {"label": "Seasonality",       "group": "env",    "color": "#00BCD4", "style": "solid",  "unit": "multiplier",  "type": "leading"},
    # Group F: Profitability
    "margin":          {"label": "Margin %",          "group": "profit", "color": "#76FF03", "style": "solid",  "unit": "%",           "type": "coincident"},
}

# Correlation groups — indicators that share ONE vote
CORRELATION_GROUPS = {
    "travel_demand_macro": ["jets_etf", "hotel_reits"],
    "demand_volume":       ["booking_velocity", "bts_flights"],
    "price_prediction":    ["forward_curve", "prophet"],
}

# Type weights
TYPE_WEIGHTS = {
    "leading": 1.5,
    "coincident": 1.0,
    "lagging": 0.5,
}

# T-aware: which indicators are active at each T range
T_ACTIVE_RANGES = {
    # indicator: minimum T (days) to be active
    "bts_flights": 30,
    "airbnb_avg": 30,
    "jets_etf": 14,
    "vix": 14,
    "hotel_reits": 14,
    "hotel_ppi": 14,
    "events": 0,
    "seasonality": 0,
    "price_scan": 0,
    "forward_curve": 0,
    "prophet": 0,
    "historical_t": 0,
    "yoy_price": 7,
    "booking_velocity": 0,
    "cancel_rate": 0,
    "price_velocity": 0,
    "provider_count": 0,
    "competitor_avg": 0,
    "browser_rank": 0,
    "margin": 0,
}


@dataclass
class IndicatorSeries:
    """A single indicator's time series + metadata."""
    key: str
    label: str
    group: str
    color: str
    style: str
    unit: str
    indicator_type: str
    weight: float
    active_at_T: bool
    correlation_group: str | None
    vote: str  # "BUY", "SELL", or "NEUTRAL"
    data: list[dict] = field(default_factory=list)  # [{t, v}]


@dataclass
class ConsensusResult:
    """BUY/SELL consensus from all indicators."""
    votes_buy: int
    votes_sell: int
    total_votes: int
    score: float  # 0.0 (all SELL) to 1.0 (all BUY)
    signal: str   # "BUY", "SELL", "NEUTRAL"
    breakdown: dict = field(default_factory=dict)


def get_active_indicators(T: int) -> list[str]:
    """Return indicator keys active at given T (days to check-in)."""
    return [key for key, min_t in T_ACTIVE_RANGES.items() if T >= min_t]


def compute_vote(key: str, series: list[dict], current_price: float,
                 fc_price: float | None = None) -> str:
    """Determine BUY/SELL/NEUTRAL vote for a single indicator."""
    if not series or len(series) < 2:
        return "NEUTRAL"

    last_val = series[-1]["v"]
    prev_val = series[-2]["v"] if len(series) >= 2 else last_val

    if key == "price_scan":
        return "BUY" if last_val < (fc_price or current_price) else "SELL"

    if key in ("forward_curve", "prophet"):
        return "BUY" if last_val > current_price else "SELL"

    if key == "historical_t":
        return "BUY" if last_val > current_price else "SELL"

    if key == "yoy_price":
        return "BUY" if last_val > current_price else "SELL"

    if key == "booking_velocity":
        return "BUY" if last_val > prev_val else "SELL" if last_val < prev_val else "NEUTRAL"

    if key == "cancel_rate":
        return "SELL" if last_val > prev_val else "BUY" if last_val < prev_val else "NEUTRAL"

    if key == "price_velocity":
        return "SELL" if last_val > prev_val else "BUY" if last_val < prev_val else "NEUTRAL"

    if key == "provider_count":
        return "SELL" if last_val > prev_val else "BUY" if last_val < prev_val else "NEUTRAL"

    if key == "competitor_avg":
        return "BUY" if last_val > current_price else "SELL"

    if key == "browser_rank":
        return "BUY" if last_val <= 3 else "SELL" if last_val > 10 or last_val == 0 else "NEUTRAL"

    if key == "airbnb_avg":
        return "BUY" if last_val > current_price else "SELL"

    if key in ("jets_etf", "hotel_reits"):
        return "BUY" if last_val > prev_val else "SELL" if last_val < prev_val else "NEUTRAL"

    if key == "vix":
        return "SELL" if last_val > prev_val else "BUY" if last_val < prev_val else "NEUTRAL"

    if key == "hotel_ppi":
        return "BUY" if last_val > prev_val else "SELL" if last_val < prev_val else "NEUTRAL"

    if key == "bts_flights":
        return "BUY" if last_val > prev_val else "SELL" if last_val < prev_val else "NEUTRAL"

    if key == "events":
        return "BUY" if last_val > 0.05 else "NEUTRAL"

    if key == "seasonality":
        return "BUY" if last_val > 1.0 else "SELL" if last_val < 1.0 else "NEUTRAL"

    if key == "margin":
        return "SELL" if last_val > 40 else "BUY" if last_val < 15 else "NEUTRAL"

    return "NEUTRAL"


def compute_consensus(indicators: dict[str, IndicatorSeries], T: int) -> ConsensusResult:
    """Compute weighted consensus from all active indicators."""
    active_keys = get_active_indicators(T)

    # Build correlation group votes (average direction within group)
    group_votes: dict[str, list[str]] = {}
    independent_votes: list[tuple[str, float]] = []  # (vote, weight)

    for key, ind in indicators.items():
        if key not in active_keys:
            continue
        if ind.vote == "NEUTRAL":
            continue

        # Check if this indicator is in a correlation group
        in_group = False
        for group_name, members in CORRELATION_GROUPS.items():
            if key in members:
                group_votes.setdefault(group_name, []).append(ind.vote)
                in_group = True
                break

        if not in_group:
            independent_votes.append((ind.vote, ind.weight))

    # Resolve correlation groups to single votes
    for group_name, votes in group_votes.items():
        buy_count = sum(1 for v in votes if v == "BUY")
        sell_count = sum(1 for v in votes if v == "SELL")
        group_vote = "BUY" if buy_count > sell_count else "SELL" if sell_count > buy_count else "NEUTRAL"
        if group_vote != "NEUTRAL":
            # Use leading weight for group (since groups typically contain leading indicators)
            independent_votes.append((group_vote, TYPE_WEIGHTS["leading"]))

    if not independent_votes:
        return ConsensusResult(0, 0, 0, 0.5, "NEUTRAL", {})

    total_weight = sum(w for _, w in independent_votes)
    buy_weight = sum(w for v, w in independent_votes if v == "BUY")
    sell_weight = sum(w for v, w in independent_votes if v == "SELL")

    score = buy_weight / total_weight if total_weight > 0 else 0.5
    votes_buy = sum(1 for v, _ in independent_votes if v == "BUY")
    votes_sell = sum(1 for v, _ in independent_votes if v == "SELL")

    if score >= 0.66:
        signal = "BUY"
    elif score <= 0.34:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    # Breakdown by type
    breakdown = {"leading": {"buy": 0, "sell": 0, "total": 0},
                 "coincident": {"buy": 0, "sell": 0, "total": 0},
                 "lagging": {"buy": 0, "sell": 0, "total": 0}}

    for key, ind in indicators.items():
        if key not in active_keys or ind.vote == "NEUTRAL":
            continue
        itype = ind.indicator_type
        if itype in breakdown:
            breakdown[itype]["total"] += 1
            if ind.vote == "BUY":
                breakdown[itype]["buy"] += 1
            else:
                breakdown[itype]["sell"] += 1

    return ConsensusResult(
        votes_buy=votes_buy,
        votes_sell=votes_sell,
        total_votes=len(independent_votes),
        score=round(score, 3),
        signal=signal,
        breakdown=breakdown,
    )


def build_indicator(key: str, data: list[dict], T: int,
                    current_price: float, fc_price: float | None = None) -> IndicatorSeries:
    """Build a single IndicatorSeries with vote computed."""
    defn = INDICATOR_DEFS.get(key, {})
    active = T >= T_ACTIVE_RANGES.get(key, 0)

    # Find correlation group
    corr_group = None
    for group_name, members in CORRELATION_GROUPS.items():
        if key in members:
            corr_group = group_name
            break

    vote = compute_vote(key, data, current_price, fc_price) if active and data else "NEUTRAL"
    weight = TYPE_WEIGHTS.get(defn.get("type", "coincident"), 1.0)

    return IndicatorSeries(
        key=key,
        label=defn.get("label", key),
        group=defn.get("group", "other"),
        color=defn.get("color", "#FFFFFF"),
        style=defn.get("style", "solid"),
        unit=defn.get("unit", ""),
        indicator_type=defn.get("type", "coincident"),
        weight=weight,
        active_at_T=active,
        correlation_group=corr_group,
        vote=vote,
        data=data,
    )


def indicator_to_dict(ind: IndicatorSeries) -> dict:
    """Serialize IndicatorSeries to JSON-friendly dict."""
    return {
        "label": ind.label,
        "group": ind.group,
        "color": ind.color,
        "style": ind.style,
        "unit": ind.unit,
        "type": ind.indicator_type,
        "weight": ind.weight,
        "active_at_T": ind.active_at_T,
        "correlation_group": ind.correlation_group,
        "vote": ind.vote,
        "data": ind.data,
    }


def consensus_to_dict(c: ConsensusResult) -> dict:
    """Serialize ConsensusResult to JSON-friendly dict."""
    return {
        "votes_buy": c.votes_buy,
        "votes_sell": c.votes_sell,
        "total_votes": c.total_votes,
        "score": c.score,
        "signal": c.signal,
        "breakdown": c.breakdown,
    }
