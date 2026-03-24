# Consensus Signal Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an 11-source consensus voting engine that replaces the current probability-based signal with independent source votes, probability calculation, and arbitrage scoring.

**Architecture:** New `src/analytics/consensus_signal.py` with 11 voter functions, each returning CALL/PUT/NEUTRAL independently. A coordinator collects all votes, calculates probability (agreeing/voting × 100%), and determines signal (≥66% = signal, <66% = NEUTRAL). Sources categorized as Leading/Coincident/Lagging. Output includes buy/sell points along T and arbitrage profit estimate.

**Tech Stack:** Python 3.12, existing analysis cache, existing data sources (FC, velocity, AI_Search, events, weather, flights, segments).

**Spec:** `docs/ARBITRAGE_SIGNAL_MODEL.md`

---

## File Structure

### New Files
- `src/analytics/consensus_signal.py` — Main engine: 11 voter functions + coordinator + arbitrage scorer
- `tests/unit/test_consensus_signal.py` — Unit tests for each voter + coordinator

### Modified Files
- `src/analytics/options_engine.py` — Replace `compute_next_day_signals()` to call consensus engine
- `src/api/routers/analytics_router.py` — Add `/signal/consensus/{detail_id}` endpoint

---

## Task 1: Consensus Engine Core — Coordinator + Vote Structure

**Files:**
- Create: `src/analytics/consensus_signal.py`
- Test: `tests/unit/test_consensus_signal.py`

- [ ] **Step 1: Write tests for coordinator**

```python
# tests/unit/test_consensus_signal.py
import pytest
from src.analytics.consensus_signal import (
    SourceVote, calculate_consensus, SIGNAL_THRESHOLD,
)

class TestCalculateConsensus:
    def test_unanimous_call(self):
        votes = [
            SourceVote("fc", "CALL", "Leading", "FC predicts +35%"),
            SourceVote("velocity", "CALL", "Coincident", "3 scans up"),
            SourceVote("competitors", "CALL", "Coincident", "zone avg up"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == 100.0
        assert result["sources_agree"] == 3
        assert result["sources_voting"] == 3

    def test_unanimous_put(self):
        votes = [
            SourceVote("fc", "PUT", "Leading", "FC predicts -8%"),
            SourceVote("velocity", "PUT", "Coincident", "3 scans down"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "PUT"
        assert result["probability"] == 100.0

    def test_majority_call_above_threshold(self):
        votes = [
            SourceVote("fc", "CALL", "Leading", ""),
            SourceVote("velocity", "CALL", "Coincident", ""),
            SourceVote("competitors", "PUT", "Coincident", ""),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == pytest.approx(66.7, abs=0.1)

    def test_split_vote_neutral(self):
        votes = [
            SourceVote("fc", "CALL", "Leading", ""),
            SourceVote("velocity", "PUT", "Coincident", ""),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "NEUTRAL"
        assert result["probability"] == 0

    def test_neutral_votes_excluded(self):
        votes = [
            SourceVote("fc", "CALL", "Leading", ""),
            SourceVote("velocity", "CALL", "Coincident", ""),
            SourceVote("weather", "NEUTRAL", "Leading", "no impact"),
            SourceVote("peers", "NEUTRAL", "Coincident", "mixed"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == 100.0
        assert result["sources_voting"] == 2
        assert result["sources_neutral"] == 2

    def test_all_neutral(self):
        votes = [
            SourceVote("fc", "NEUTRAL", "Leading", ""),
            SourceVote("velocity", "NEUTRAL", "Coincident", ""),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "NEUTRAL"
        assert result["probability"] == 0

    def test_empty_votes(self):
        result = calculate_consensus([])
        assert result["signal"] == "NEUTRAL"

    def test_category_breakdown(self):
        votes = [
            SourceVote("events", "CALL", "Leading", ""),
            SourceVote("flights", "CALL", "Leading", ""),
            SourceVote("seasonality", "CALL", "Leading", ""),
            SourceVote("velocity", "PUT", "Coincident", ""),
            SourceVote("competitors", "CALL", "Coincident", ""),
            SourceVote("historical", "CALL", "Lagging", ""),
        ]
        result = calculate_consensus(votes)
        cats = result["by_category"]
        assert cats["Leading"]["call"] == 3
        assert cats["Coincident"]["call"] == 1
        assert cats["Coincident"]["put"] == 1
        assert cats["Lagging"]["call"] == 1

    def test_below_threshold_neutral(self):
        # 3 CALL, 2 PUT = 60% < 66% threshold
        votes = [
            SourceVote("a", "CALL", "Leading", ""),
            SourceVote("b", "CALL", "Coincident", ""),
            SourceVote("c", "CALL", "Lagging", ""),
            SourceVote("d", "PUT", "Coincident", ""),
            SourceVote("e", "PUT", "Lagging", ""),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "NEUTRAL"
```

- [ ] **Step 2: Implement coordinator**

```python
# src/analytics/consensus_signal.py
"""Consensus Signal Engine — 11-source independent voting for arbitrage signals.

Each data source votes CALL/PUT/NEUTRAL independently (equal weight).
Signal = direction with ≥66% agreement among voting sources.
NEUTRAL sources don't count in the vote.

Sources are categorized:
  Leading:    predict future (events, flights, seasonality, weather)
  Coincident: happening now (scan velocity, competitors, peers)
  Lagging:    confirm past (historical pattern, official benchmark, booking momentum, FC)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

SIGNAL_THRESHOLD = 66.0  # Minimum % agreement for signal


@dataclass
class SourceVote:
    """One source's vote."""
    source: str          # e.g. "forward_curve"
    vote: str            # "CALL", "PUT", "NEUTRAL"
    category: str        # "Leading", "Coincident", "Lagging"
    reason: str = ""     # Human-readable explanation


def calculate_consensus(votes: list[SourceVote]) -> dict:
    """Calculate consensus signal from independent source votes."""
    if not votes:
        return {"signal": "NEUTRAL", "probability": 0, "sources_voting": 0,
                "sources_neutral": 0, "sources_agree": 0, "sources_disagree": 0,
                "votes": [], "by_category": {}}

    call_votes = [v for v in votes if v.vote == "CALL"]
    put_votes = [v for v in votes if v.vote == "PUT"]
    neutral_votes = [v for v in votes if v.vote == "NEUTRAL"]

    voting_count = len(call_votes) + len(put_votes)

    if voting_count == 0:
        return {"signal": "NEUTRAL", "probability": 0, "sources_voting": 0,
                "sources_neutral": len(neutral_votes), "sources_agree": 0,
                "sources_disagree": 0, "votes": [asdict(v) for v in votes],
                "by_category": _category_breakdown(votes)}

    call_pct = len(call_votes) / voting_count * 100
    put_pct = len(put_votes) / voting_count * 100

    if call_pct >= SIGNAL_THRESHOLD:
        signal = "CALL"
        probability = round(call_pct, 1)
        agree = len(call_votes)
        disagree = len(put_votes)
    elif put_pct >= SIGNAL_THRESHOLD:
        signal = "PUT"
        probability = round(put_pct, 1)
        agree = len(put_votes)
        disagree = len(call_votes)
    else:
        signal = "NEUTRAL"
        probability = 0
        agree = max(len(call_votes), len(put_votes))
        disagree = min(len(call_votes), len(put_votes))

    return {
        "signal": signal,
        "probability": probability,
        "sources_voting": voting_count,
        "sources_neutral": len(neutral_votes),
        "sources_agree": agree,
        "sources_disagree": disagree,
        "call_pct": round(call_pct, 1),
        "put_pct": round(put_pct, 1),
        "votes": [asdict(v) for v in votes],
        "by_category": _category_breakdown(votes),
    }


def _category_breakdown(votes: list[SourceVote]) -> dict:
    """Group votes by category (Leading/Coincident/Lagging)."""
    cats = {}
    for v in votes:
        if v.category not in cats:
            cats[v.category] = {"call": 0, "put": 0, "neutral": 0}
        cats[v.category][v.vote.lower()] += 1
    return cats
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/unit/test_consensus_signal.py -v`
Expected: All 10 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/analytics/consensus_signal.py tests/unit/test_consensus_signal.py
git commit -m "feat: consensus signal engine core — coordinator with 11-source voting"
```

---

## Task 2: Implement 11 Voter Functions

**Files:**
- Modify: `src/analytics/consensus_signal.py`
- Test: `tests/unit/test_consensus_signal.py`

Each voter takes `(prediction: dict, analysis: dict, context: dict)` and returns `SourceVote`.

- [ ] **Step 1: Implement all 11 voters**

```python
# Add to consensus_signal.py after calculate_consensus

# ── Voter 1: Forward Curve ─────────────────────────────
def vote_forward_curve(pred: dict) -> SourceVote:
    """FC predicts ≥5% drop → PUT, ≥30% rise → CALL."""
    fc = pred.get("forward_curve") or []
    cp = float(pred.get("current_price", 0) or 0)
    if not fc or cp <= 0:
        return SourceVote("forward_curve", "NEUTRAL", "Lagging", "no FC data")
    prices = [float(p.get("predicted_price", 0)) for p in fc if p.get("predicted_price")]
    if len(prices) < 3:
        return SourceVote("forward_curve", "NEUTRAL", "Lagging", "insufficient FC points")
    max_drop = (cp - min(prices)) / cp * 100
    max_rise = (max(prices) - cp) / cp * 100
    if max_rise >= 30:
        return SourceVote("forward_curve", "CALL", "Lagging", f"FC predicts +{max_rise:.0f}%")
    if max_drop >= 5:
        return SourceVote("forward_curve", "PUT", "Lagging", f"FC predicts -{max_drop:.0f}%")
    return SourceVote("forward_curve", "NEUTRAL", "Lagging", f"FC range: -{max_drop:.1f}% to +{max_rise:.1f}%")


# ── Voter 2: Scan Velocity ─────────────────────────────
def vote_scan_velocity(pred: dict) -> SourceVote:
    """Last scans trending up/down ≥3% → signal."""
    momentum = pred.get("momentum") or {}
    vel = float(momentum.get("velocity_24h", 0) or 0)
    accel = float(momentum.get("acceleration", 0) or 0)
    if vel > 0.03 and accel >= 0:
        return SourceVote("scan_velocity", "CALL", "Coincident", f"velocity +{vel*100:.1f}%")
    if vel < -0.03 and accel <= 0:
        return SourceVote("scan_velocity", "PUT", "Coincident", f"velocity {vel*100:.1f}%")
    return SourceVote("scan_velocity", "NEUTRAL", "Coincident", f"velocity {vel*100:.1f}%, flat")


# ── Voter 3: Competitor Prices ─────────────────────────
def vote_competitors(pred: dict, zone_avg: float = 0) -> SourceVote:
    """Current price vs zone average → signal."""
    cp = float(pred.get("current_price", 0) or 0)
    if cp <= 0 or zone_avg <= 0:
        return SourceVote("competitors", "NEUTRAL", "Coincident", "no zone data")
    deviation = (cp - zone_avg) / zone_avg * 100
    if deviation <= -15:
        return SourceVote("competitors", "CALL", "Coincident", f"price {deviation:.0f}% below zone avg ${zone_avg:.0f}")
    if deviation >= 10:
        return SourceVote("competitors", "PUT", "Coincident", f"price {deviation:.0f}% above zone avg ${zone_avg:.0f}")
    return SourceVote("competitors", "NEUTRAL", "Coincident", f"price {deviation:+.0f}% vs zone avg")


# ── Voter 4: Events Calendar ──────────────────────────
def vote_events(pred: dict, events: list = None) -> SourceVote:
    """Upcoming events in T window → CALL, post-event → PUT."""
    if not events:
        return SourceVote("events", "NEUTRAL", "Leading", "no events data")
    t = int(pred.get("days_to_checkin", 0) or 0)
    # Check if any major event falls within T window
    for ev in events:
        ev_t = ev.get("days_until", 999)
        impact = ev.get("impact", "low")
        if 0 < ev_t <= t and impact in ("high", "medium"):
            return SourceVote("events", "CALL", "Leading", f"event '{ev.get('name','')}' in {ev_t}d")
    return SourceVote("events", "NEUTRAL", "Leading", "no major events in T window")


# ── Voter 5: Seasonality Index ─────────────────────────
def vote_seasonality(pred: dict) -> SourceVote:
    """Historical monthly pattern → signal."""
    enrichments = {}
    fc = pred.get("forward_curve") or []
    if fc:
        enrichments = {k: float(v) for k, v in fc[0].items() if k.endswith("_adj_pct")}
    season_adj = enrichments.get("season_adj_pct", 0)
    if season_adj > 0.02:
        return SourceVote("seasonality", "CALL", "Leading", f"seasonal boost +{season_adj*100:.1f}%")
    if season_adj < -0.02:
        return SourceVote("seasonality", "PUT", "Leading", f"seasonal drag {season_adj*100:.1f}%")
    return SourceVote("seasonality", "NEUTRAL", "Leading", "no seasonal effect")


# ── Voter 6: Flight Demand ─────────────────────────────
def vote_flight_demand(pred: dict) -> SourceVote:
    """Flight demand indicator → signal."""
    enrichments = {}
    fc = pred.get("forward_curve") or []
    if fc:
        enrichments = {k: float(v) for k, v in fc[0].items() if k.endswith("_adj_pct")}
    demand_adj = enrichments.get("demand_adj_pct", 0)
    if demand_adj > 0.01:
        return SourceVote("flight_demand", "CALL", "Leading", f"high flight demand +{demand_adj*100:.1f}%")
    if demand_adj < -0.01:
        return SourceVote("flight_demand", "PUT", "Leading", f"low flight demand {demand_adj*100:.1f}%")
    return SourceVote("flight_demand", "NEUTRAL", "Leading", "normal demand")


# ── Voter 7: Weather Forecast ──────────────────────────
def vote_weather(pred: dict) -> SourceVote:
    """Weather impact → signal."""
    enrichments = {}
    fc = pred.get("forward_curve") or []
    if fc:
        enrichments = {k: float(v) for k, v in fc[0].items() if k.endswith("_adj_pct")}
    weather_adj = enrichments.get("weather_adj_pct", 0)
    if weather_adj < -0.03:
        return SourceVote("weather", "PUT", "Leading", f"bad weather impact {weather_adj*100:.1f}%")
    if weather_adj > 0.01:
        return SourceVote("weather", "CALL", "Leading", f"good weather boost +{weather_adj*100:.1f}%")
    return SourceVote("weather", "NEUTRAL", "Leading", "normal weather")


# ── Voter 8: Peer Hotel Behavior ───────────────────────
def vote_peers(pred: dict, peer_prices: list = None) -> SourceVote:
    """Majority of peers rising/falling → signal."""
    if not peer_prices or len(peer_prices) < 2:
        return SourceVote("peers", "NEUTRAL", "Coincident", "insufficient peer data")
    rising = sum(1 for p in peer_prices if p.get("trend", 0) > 0)
    falling = sum(1 for p in peer_prices if p.get("trend", 0) < 0)
    total = rising + falling
    if total == 0:
        return SourceVote("peers", "NEUTRAL", "Coincident", "peers flat")
    if rising / total >= 0.66:
        return SourceVote("peers", "CALL", "Coincident", f"{rising}/{total} peers rising")
    if falling / total >= 0.66:
        return SourceVote("peers", "PUT", "Coincident", f"{falling}/{total} peers falling")
    return SourceVote("peers", "NEUTRAL", "Coincident", f"peers mixed: {rising}↑ {falling}↓")


# ── Voter 9: Booking Momentum ──────────────────────────
def vote_booking_momentum(pred: dict) -> SourceVote:
    """Net bookings vs cancellations → signal."""
    # Uses cancellation enrichment from FC
    enrichments = {}
    fc = pred.get("forward_curve") or []
    if fc:
        enrichments = {k: float(v) for k, v in fc[0].items() if k.endswith("_adj_pct")}
    cancel_adj = enrichments.get("cancellation_adj_pct", 0)
    if cancel_adj < -0.02:
        return SourceVote("booking_momentum", "PUT", "Lagging", f"high cancellations {cancel_adj*100:.1f}%")
    if cancel_adj >= 0:
        return SourceVote("booking_momentum", "CALL", "Lagging", "low cancellation risk")
    return SourceVote("booking_momentum", "NEUTRAL", "Lagging", "normal booking pace")


# ── Voter 10: Historical Pattern ───────────────────────
def vote_historical(pred: dict) -> SourceVote:
    """Same period last year pattern → signal."""
    prob = pred.get("probability") or {}
    p_up = float(prob.get("up", 0))
    p_down = float(prob.get("down", 0))
    if p_up >= 65:
        return SourceVote("historical", "CALL", "Lagging", f"historically {p_up:.0f}% up")
    if p_down >= 65:
        return SourceVote("historical", "PUT", "Lagging", f"historically {p_down:.0f}% down")
    return SourceVote("historical", "NEUTRAL", "Lagging", f"historical: {p_up:.0f}% up / {p_down:.0f}% down")


# ── Voter 11: Official Market Benchmark ────────────────
def vote_official_benchmark(pred: dict, official_adr: float = 0) -> SourceVote:
    """Current price vs official zone ADR benchmark → signal."""
    cp = float(pred.get("current_price", 0) or 0)
    if cp <= 0 or official_adr <= 0:
        return SourceVote("official_benchmark", "NEUTRAL", "Lagging", "no benchmark data")
    deviation = (cp - official_adr) / official_adr * 100
    if deviation <= -20:
        return SourceVote("official_benchmark", "CALL", "Lagging", f"price {deviation:.0f}% below official ADR ${official_adr:.0f}")
    if deviation >= 15:
        return SourceVote("official_benchmark", "PUT", "Lagging", f"price {deviation:.0f}% above official ADR ${official_adr:.0f}")
    return SourceVote("official_benchmark", "NEUTRAL", "Lagging", f"price {deviation:+.0f}% vs official ADR")


# ── Master: Collect All Votes ──────────────────────────
def compute_consensus_signal(pred: dict, zone_avg: float = 0,
                              official_adr: float = 0, events: list = None,
                              peer_prices: list = None) -> dict:
    """Run all 11 voters and compute consensus signal."""
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
    ]
    result = calculate_consensus(votes)
    result["current_price"] = float(pred.get("current_price", 0) or 0)
    result["hotel_name"] = pred.get("hotel_name", "")
    result["detail_id"] = pred.get("detail_id", "")
    result["T"] = pred.get("days_to_checkin", 0)
    return result
```

- [ ] **Step 2: Add voter tests**

Add tests for key voters: FC, velocity, competitors, events, seasonality, official benchmark.

- [ ] **Step 3: Run all tests**

Run: `python3 -m pytest tests/unit/test_consensus_signal.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/analytics/consensus_signal.py tests/unit/test_consensus_signal.py
git commit -m "feat: 11 voter functions for consensus signal engine"
```

---

## Task 3: Replace compute_next_day_signals

**Files:**
- Modify: `src/analytics/options_engine.py`

- [ ] **Step 1: Update compute_next_day_signals to use consensus**

Replace the decision rules block with a call to `compute_consensus_signal()`. Keep all existing output fields, add new ones (probability, sources_agree, by_category).

- [ ] **Step 2: Run existing tests**

Run: `python3 -m pytest tests/unit/test_options_engine.py -v`

- [ ] **Step 3: Commit**

```bash
git add src/analytics/options_engine.py
git commit -m "feat: replace probability-based signals with 11-source consensus voting"
```

---

## Task 4: API Endpoint for Consensus Detail

**Files:**
- Modify: `src/api/routers/analytics_router.py`

- [ ] **Step 1: Add endpoint**

```python
@analytics_router.get("/signal/consensus/{detail_id}")
async def signal_consensus_detail(request: Request, detail_id: int):
    """Full consensus signal breakdown for a single option."""
    # Returns: all 11 votes, probability, by_category, arbitrage points
```

- [ ] **Step 2: Commit**

```bash
git add src/api/routers/analytics_router.py
git commit -m "feat: add /signal/consensus/{detail_id} endpoint"
```

---

## Task 5: Deploy + Verify

- [ ] **Step 1: Run full test suite**
- [ ] **Step 2: Deploy**
- [ ] **Step 3: Verify signal distribution**
- [ ] **Step 4: Tag version**

---

## Verification Checklist

- [ ] 11 voters each return SourceVote independently
- [ ] calculate_consensus returns correct probability
- [ ] ≥66% agreement → signal, <66% → NEUTRAL
- [ ] NEUTRAL votes excluded from count
- [ ] Category breakdown (Leading/Coincident/Lagging) included
- [ ] compute_consensus_signal integrates all voters
- [ ] /signal/consensus/{detail_id} returns full breakdown
- [ ] Existing tests still pass
- [ ] Signal distribution is realistic (not 100% CALL)
