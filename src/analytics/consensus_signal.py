"""Consensus Signal Engine — aggregates 11 independent voter signals into a single consensus."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SourceVote:
    """A single source's directional vote."""
    source: str       # e.g. "forward_curve"
    vote: str         # "CALL", "PUT", "NEUTRAL"
    category: str     # "Leading", "Coincident", "Lagging"
    reason: str = ""  # Human-readable explanation


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

def calculate_consensus(votes: List[SourceVote]) -> dict:
    """Aggregate votes into a consensus signal.

    Rules:
    - NEUTRAL votes are excluded from the voting count.
    - probability = agreeing / voting * 100
    - >= 66% agreement -> that signal; otherwise NEUTRAL
    """
    if not votes:
        return {
            "signal": "NEUTRAL",
            "probability": 0.0,
            "sources_voting": 0,
            "sources_neutral": 0,
            "sources_agree": 0,
            "sources_disagree": 0,
            "call_pct": 0.0,
            "put_pct": 0.0,
            "votes": [],
            "by_category": {},
        }

    call_votes = [v for v in votes if v.vote == "CALL"]
    put_votes = [v for v in votes if v.vote == "PUT"]
    neutral_votes = [v for v in votes if v.vote == "NEUTRAL"]

    n_call = len(call_votes)
    n_put = len(put_votes)
    n_neutral = len(neutral_votes)
    n_voting = n_call + n_put  # neutrals excluded

    if n_voting == 0:
        call_pct = 0.0
        put_pct = 0.0
        signal = "NEUTRAL"
        probability = 0.0
        agreeing = 0
    else:
        call_pct = round(n_call / n_voting * 100, 1)
        put_pct = round(n_put / n_voting * 100, 1)

        if n_call >= n_put:
            majority_signal = "CALL"
            agreeing = n_call
        else:
            majority_signal = "PUT"
            agreeing = n_put

        probability = round(agreeing / n_voting * 100, 1)

        MIN_VOTING_SOURCES = 4  # Need at least 4 non-neutral voters for a signal
        if n_voting < MIN_VOTING_SOURCES:
            signal = "NEUTRAL"  # Too few voters = insufficient data
        elif probability >= 66.0:
            signal = majority_signal
        else:
            signal = "NEUTRAL"

    sources_agree = agreeing if n_voting > 0 else 0
    sources_disagree = n_voting - sources_agree if n_voting > 0 else 0

    # Category breakdown
    by_category: Dict[str, dict] = {}
    for cat in ("Leading", "Coincident", "Lagging"):
        cat_votes = [v for v in votes if v.category == cat]
        if cat_votes:
            by_category[cat] = {
                "call": sum(1 for v in cat_votes if v.vote == "CALL"),
                "put": sum(1 for v in cat_votes if v.vote == "PUT"),
                "neutral": sum(1 for v in cat_votes if v.vote == "NEUTRAL"),
                "total": len(cat_votes),
            }

    return {
        "signal": signal,
        "probability": probability,
        "sources_voting": n_voting,
        "sources_neutral": n_neutral,
        "sources_agree": sources_agree,
        "sources_disagree": sources_disagree,
        "call_pct": call_pct,
        "put_pct": put_pct,
        "votes": [
            {"source": v.source, "vote": v.vote, "category": v.category, "reason": v.reason}
            for v in votes
        ],
        "by_category": by_category,
    }


# ---------------------------------------------------------------------------
# Helper to safely read FC enrichment fields
# ---------------------------------------------------------------------------

def _fc_field(pred: dict, field_name: str, default: float = 0.0) -> float:
    """Read an enrichment field from the first forward_curve entry."""
    fc = pred.get("forward_curve")
    if not fc or not isinstance(fc, list) or len(fc) == 0:
        return default
    entry = fc[0]
    if not isinstance(entry, dict):
        return default
    val = entry.get(field_name, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 11 Voters
# ---------------------------------------------------------------------------

def vote_forward_curve(pred: dict) -> SourceVote:
    """Lagging — FC prices: drop >= 5% -> PUT, rise >= 15% -> CALL."""
    fc = pred.get("forward_curve")
    if not fc or not isinstance(fc, list) or len(fc) == 0:
        return SourceVote("forward_curve", "NEUTRAL", "Lagging", "No FC data")

    entry = fc[0]
    if not isinstance(entry, dict):
        return SourceVote("forward_curve", "NEUTRAL", "Lagging", "Invalid FC entry")

    change_pct = entry.get("change_pct", 0.0)
    try:
        change_pct = float(change_pct)
    except (TypeError, ValueError):
        return SourceVote("forward_curve", "NEUTRAL", "Lagging", "Invalid change_pct")

    if change_pct <= -5.0:
        return SourceVote("forward_curve", "PUT", "Lagging", f"FC drop {change_pct:.1f}%")
    elif change_pct >= 15.0:
        return SourceVote("forward_curve", "CALL", "Lagging", f"FC rise {change_pct:.1f}%")
    return SourceVote("forward_curve", "NEUTRAL", "Lagging", f"FC change {change_pct:.1f}% within range")


def vote_scan_velocity(pred: dict) -> SourceVote:
    """Coincident — momentum velocity_24h: > 3% -> CALL, < -3% -> PUT."""
    mom = pred.get("momentum")
    if not mom or not isinstance(mom, dict):
        return SourceVote("scan_velocity", "NEUTRAL", "Coincident", "No momentum data")

    vel = mom.get("velocity_24h", 0.0)
    try:
        vel = float(vel)
    except (TypeError, ValueError):
        return SourceVote("scan_velocity", "NEUTRAL", "Coincident", "Invalid velocity")

    # velocity_24h is a fraction, e.g. 0.05 = 5%
    vel_pct = vel * 100

    if vel_pct > 3.0:
        return SourceVote("scan_velocity", "CALL", "Coincident", f"Velocity +{vel_pct:.1f}%")
    elif vel_pct < -3.0:
        return SourceVote("scan_velocity", "PUT", "Coincident", f"Velocity {vel_pct:.1f}%")
    return SourceVote("scan_velocity", "NEUTRAL", "Coincident", f"Velocity {vel_pct:.1f}% within range")


def vote_competitors(pred: dict, zone_avg: float = 0.0) -> SourceVote:
    """Coincident — price vs zone avg: <= -15% -> CALL (underpriced), >= +10% -> PUT (overpriced)."""
    if zone_avg <= 0:
        return SourceVote("competitors", "NEUTRAL", "Coincident", "No zone average")

    price = pred.get("current_price", 0)
    try:
        price = float(price)
    except (TypeError, ValueError):
        return SourceVote("competitors", "NEUTRAL", "Coincident", "Invalid price")

    if price <= 0:
        return SourceVote("competitors", "NEUTRAL", "Coincident", "No current price")

    diff_pct = ((price - zone_avg) / zone_avg) * 100

    if diff_pct <= -15.0:
        return SourceVote("competitors", "CALL", "Coincident", f"Price {diff_pct:.1f}% below zone avg")
    elif diff_pct >= 10.0:
        return SourceVote("competitors", "PUT", "Coincident", f"Price {diff_pct:.1f}% above zone avg")
    return SourceVote("competitors", "NEUTRAL", "Coincident", f"Price {diff_pct:.1f}% vs zone avg")


def vote_events(pred: dict, events: Optional[List[dict]] = None) -> SourceVote:
    """Leading — major event in T window -> CALL, post-event -> PUT."""
    if not events:
        return SourceVote("events", "NEUTRAL", "Leading", "No event data")

    for ev in events:
        if not isinstance(ev, dict):
            continue
        status = ev.get("status", "")
        if status == "upcoming":
            name = ev.get("name", "event")
            return SourceVote("events", "CALL", "Leading", f"Upcoming event: {name}")
        elif status == "past":
            name = ev.get("name", "event")
            return SourceVote("events", "PUT", "Leading", f"Post-event drop: {name}")

    return SourceVote("events", "NEUTRAL", "Leading", "No impactful events")


def vote_seasonality(pred: dict) -> SourceVote:
    """Leading — season_adj_pct from FC enrichments: > 5% -> CALL, < -5% -> PUT."""
    adj = _fc_field(pred, "season_adj_pct", 0.0)
    adj_pct = adj * 100

    if adj_pct > 5.0:
        return SourceVote("seasonality", "CALL", "Leading", f"Season boost +{adj_pct:.1f}%")
    elif adj_pct < -5.0:
        return SourceVote("seasonality", "PUT", "Leading", f"Season drag {adj_pct:.1f}%")
    return SourceVote("seasonality", "NEUTRAL", "Leading", f"Season adj {adj_pct:.1f}%")


def vote_flight_demand(pred: dict) -> SourceVote:
    """Leading — demand_adj_pct from FC: > 3% -> CALL, < -3% -> PUT."""
    adj = _fc_field(pred, "demand_adj_pct", 0.0)
    adj_pct = adj * 100

    if adj_pct > 3.0:
        return SourceVote("flight_demand", "CALL", "Leading", f"Flight demand +{adj_pct:.1f}%")
    elif adj_pct < -3.0:
        return SourceVote("flight_demand", "PUT", "Leading", f"Flight demand {adj_pct:.1f}%")
    return SourceVote("flight_demand", "NEUTRAL", "Leading", f"Flight demand {adj_pct:.1f}%")


def vote_weather(pred: dict) -> SourceVote:
    """Leading — weather_adj_pct from FC: < -5% -> PUT, > 3% -> CALL."""
    adj = _fc_field(pred, "weather_adj_pct", 0.0)
    adj_pct = adj * 100

    if adj_pct < -5.0:
        return SourceVote("weather", "PUT", "Leading", f"Weather drag {adj_pct:.1f}%")
    elif adj_pct > 3.0:
        return SourceVote("weather", "CALL", "Leading", f"Weather boost +{adj_pct:.1f}%")
    return SourceVote("weather", "NEUTRAL", "Leading", f"Weather adj {adj_pct:.1f}%")


def vote_peers(pred: dict, peer_prices: Optional[List[dict]] = None) -> SourceVote:
    """Coincident — >= 66% peers rising -> CALL, >= 66% falling -> PUT."""
    if not peer_prices or len(peer_prices) == 0:
        return SourceVote("peers", "NEUTRAL", "Coincident", "No peer data")

    rising = sum(1 for p in peer_prices if isinstance(p, dict) and p.get("direction") == "up")
    falling = sum(1 for p in peer_prices if isinstance(p, dict) and p.get("direction") == "down")
    total = len(peer_prices)

    if total == 0:
        return SourceVote("peers", "NEUTRAL", "Coincident", "No valid peers")

    rising_pct = rising / total
    falling_pct = falling / total

    if rising_pct >= 0.66:
        return SourceVote("peers", "CALL", "Coincident", f"{rising}/{total} peers rising")
    elif falling_pct >= 0.66:
        return SourceVote("peers", "PUT", "Coincident", f"{falling}/{total} peers falling")
    return SourceVote("peers", "NEUTRAL", "Coincident", f"Peers split: {rising} up, {falling} down")


def vote_booking_momentum(pred: dict) -> SourceVote:
    """Lagging — cancellation_adj_pct from FC: < -2% -> PUT."""
    adj = _fc_field(pred, "cancellation_adj_pct", 0.0)
    adj_pct = adj * 100

    if adj_pct < -2.0:
        return SourceVote("booking_momentum", "PUT", "Lagging", f"Cancellation drag {adj_pct:.1f}%")
    return SourceVote("booking_momentum", "NEUTRAL", "Lagging", f"Cancellations {adj_pct:.1f}%")


def vote_historical(pred: dict) -> SourceVote:
    """Lagging — probability up/down from prediction: >= 65% -> signal."""
    prob = pred.get("probability")
    if not prob or not isinstance(prob, dict):
        return SourceVote("historical", "NEUTRAL", "Lagging", "No probability data")

    prob_up = prob.get("up", 0)
    prob_down = prob.get("down", 0)
    try:
        prob_up = float(prob_up)
        prob_down = float(prob_down)
    except (TypeError, ValueError):
        return SourceVote("historical", "NEUTRAL", "Lagging", "Invalid probability values")

    if prob_up >= 65.0:
        return SourceVote("historical", "CALL", "Lagging", f"Historical {prob_up:.0f}% up")
    elif prob_down >= 65.0:
        return SourceVote("historical", "PUT", "Lagging", f"Historical {prob_down:.0f}% down")
    return SourceVote("historical", "NEUTRAL", "Lagging", f"Historical split: {prob_up:.0f}% up / {prob_down:.0f}% down")


def vote_scan_drop_risk(pred: dict) -> SourceVote:
    """Coincident — scan history drop patterns: high drop frequency + streak -> PUT.

    Uses real scan data from SalesOffice.Details historical scans:
    - drop_frequency (% of scans with price drops)
    - consecutive trend (scan_trend = "down")
    - max single drop magnitude
    - scan_actual_drops vs scan_actual_rises ratio
    """
    scan = pred.get("scan_history")
    if not scan or not isinstance(scan, dict):
        return SourceVote("scan_drop_risk", "NEUTRAL", "Coincident", "No scan history")

    snapshots = int(scan.get("scan_snapshots", 0) or 0)
    if snapshots < 3:
        return SourceVote("scan_drop_risk", "NEUTRAL", "Coincident", f"Only {snapshots} scans")

    drops = int(scan.get("scan_actual_drops", 0) or 0)
    rises = int(scan.get("scan_actual_rises", 0) or 0)
    total_moves = drops + rises
    trend = scan.get("scan_trend", "no_data")

    # Score the drop risk (simplified from next-scan-drop skill)
    score = 0.0

    # Drop frequency
    if total_moves > 0:
        drop_freq = drops / total_moves
        if drop_freq > 0.6:
            score += 30
        elif drop_freq > 0.4:
            score += 15

    # Trend direction
    if trend == "down":
        score += 25
    elif trend == "up":
        score -= 15  # Reduces risk

    # Max single drop magnitude
    max_drop = abs(float(scan.get("scan_max_single_drop", 0) or 0))
    if max_drop > 20:
        score += 20
    elif max_drop > 10:
        score += 10

    # Ratio of drops to rises
    if drops > 0 and rises == 0:
        score += 15  # All drops, no rises
    elif drops > rises * 2:
        score += 10

    if score >= 50:
        return SourceVote("scan_drop_risk", "PUT", "Coincident",
                          f"Drop risk score {score:.0f}: {drops} drops/{rises} rises, trend={trend}")
    elif score <= -10:
        return SourceVote("scan_drop_risk", "CALL", "Coincident",
                          f"Low drop risk score {score:.0f}: trend={trend}")
    return SourceVote("scan_drop_risk", "NEUTRAL", "Coincident",
                      f"Drop risk score {score:.0f}")


def vote_provider_spread(pred: dict) -> SourceVote:
    """Coincident — provider pressure from SearchResultsPollLog (8.3M rows, 129 providers).

    provider_pressure is pre-computed in the enrichment cycle from search results:
    - Negative = providers offering lower prices -> PUT pressure
    - Positive = providers offering higher prices -> CALL opportunity
    Range: -1.0 to +1.0
    """
    source_inputs = pred.get("source_inputs")
    if not source_inputs or not isinstance(source_inputs, dict):
        return SourceVote("provider_spread", "NEUTRAL", "Coincident", "No source inputs")

    pressure = source_inputs.get("provider_pressure", 0.0)
    try:
        pressure = float(pressure)
    except (TypeError, ValueError):
        return SourceVote("provider_spread", "NEUTRAL", "Coincident", "Invalid provider pressure")

    if abs(pressure) < 0.01:
        return SourceVote("provider_spread", "NEUTRAL", "Coincident", "No provider data")

    # Strong negative pressure = providers undercut us = PUT
    if pressure <= -0.3:
        return SourceVote("provider_spread", "PUT", "Coincident",
                          f"Provider pressure {pressure:.2f} — OTAs undercutting")
    elif pressure <= -0.1:
        return SourceVote("provider_spread", "PUT", "Coincident",
                          f"Provider pressure {pressure:.2f} — mild undercut")
    elif pressure >= 0.3:
        return SourceVote("provider_spread", "CALL", "Coincident",
                          f"Provider pressure {pressure:.2f} — we're priced low")
    elif pressure >= 0.1:
        return SourceVote("provider_spread", "CALL", "Coincident",
                          f"Provider pressure {pressure:.2f} — slight advantage")
    return SourceVote("provider_spread", "NEUTRAL", "Coincident",
                      f"Provider pressure {pressure:.2f}")


def vote_margin_erosion(pred: dict, med_book_buy_price: float = 0.0) -> SourceVote:
    """Lagging — if we bought this room (MED_Book), compare buy price vs current market.

    If current market price dropped below our buy price -> strong PUT signal
    (margin eroding, may need to cut losses or rebuy cheaper).
    If market price is above buy price with good margin -> CALL (profitable position).
    """
    if med_book_buy_price <= 0:
        return SourceVote("margin_erosion", "NEUTRAL", "Lagging", "No MED_Book buy price")

    current_price = pred.get("current_price", 0)
    try:
        current_price = float(current_price)
    except (TypeError, ValueError):
        return SourceVote("margin_erosion", "NEUTRAL", "Lagging", "Invalid current price")

    if current_price <= 0:
        return SourceVote("margin_erosion", "NEUTRAL", "Lagging", "No current price")

    margin_pct = ((current_price - med_book_buy_price) / med_book_buy_price) * 100

    if margin_pct <= -10.0:
        return SourceVote("margin_erosion", "PUT", "Lagging",
                          f"Margin erosion {margin_pct:.1f}% — market below buy price")
    elif margin_pct <= -3.0:
        return SourceVote("margin_erosion", "PUT", "Lagging",
                          f"Margin pressure {margin_pct:.1f}%")
    elif margin_pct >= 30.0:
        return SourceVote("margin_erosion", "CALL", "Lagging",
                          f"Strong margin +{margin_pct:.1f}% — profitable position")
    elif margin_pct >= 15.0:
        return SourceVote("margin_erosion", "CALL", "Lagging",
                          f"Good margin +{margin_pct:.1f}%")
    return SourceVote("margin_erosion", "NEUTRAL", "Lagging",
                      f"Margin {margin_pct:.1f}%")


def vote_official_benchmark(pred: dict, official_adr: float = 0.0) -> SourceVote:
    """Lagging — price vs official ADR: <= -20% -> CALL, >= +15% -> PUT."""
    if official_adr <= 0:
        return SourceVote("official_benchmark", "NEUTRAL", "Lagging", "No official ADR")

    price = pred.get("current_price", 0)
    try:
        price = float(price)
    except (TypeError, ValueError):
        return SourceVote("official_benchmark", "NEUTRAL", "Lagging", "Invalid price")

    if price <= 0:
        return SourceVote("official_benchmark", "NEUTRAL", "Lagging", "No current price")

    diff_pct = ((price - official_adr) / official_adr) * 100

    if diff_pct <= -20.0:
        return SourceVote("official_benchmark", "CALL", "Lagging", f"Price {diff_pct:.1f}% below ADR")
    elif diff_pct >= 15.0:
        return SourceVote("official_benchmark", "PUT", "Lagging", f"Price {diff_pct:.1f}% above ADR")
    return SourceVote("official_benchmark", "NEUTRAL", "Lagging", f"Price {diff_pct:.1f}% vs ADR")


# ---------------------------------------------------------------------------
# Master function
# ---------------------------------------------------------------------------

def compute_consensus_signal(
    pred: dict,
    zone_avg: float = 0.0,
    official_adr: float = 0.0,
    events: Optional[List[dict]] = None,
    peer_prices: Optional[List[dict]] = None,
    med_book_buy_price: float = 0.0,
) -> dict:
    """Run all 14 voters and return a consensus signal with full metadata."""
    votes = [
        vote_forward_curve(pred),
        vote_scan_velocity(pred),
        vote_competitors(pred, zone_avg),
        vote_events(pred, events),
        vote_seasonality(pred),
        vote_flight_demand(pred),
        vote_weather(pred),
        vote_peers(pred, peer_prices),
        vote_booking_momentum(pred),
        vote_historical(pred),
        vote_official_benchmark(pred, official_adr),
        # v2.6.0: 3 new data-driven voters
        vote_scan_drop_risk(pred),
        vote_provider_spread(pred),
        vote_margin_erosion(pred, med_book_buy_price),
    ]

    result = calculate_consensus(votes)

    # Attach prediction metadata
    result["current_price"] = pred.get("current_price", 0)
    result["hotel_name"] = pred.get("hotel_name", "")
    result["detail_id"] = pred.get("detail_id", 0)
    result["T"] = pred.get("T", 0)

    return result
