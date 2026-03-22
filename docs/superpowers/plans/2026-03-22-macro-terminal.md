# Macro Terminal — 3-Level Portfolio Navigation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Trading Terminal with 3 drill-down levels (Portfolio → Hotel → Option Detail) following the Bloomberg/IB Risk Navigator pattern, without breaking the current single-hotel flow.

**Architecture:** L1 (Portfolio View) is a new HTML page served at `/dashboard/terminal` that replaces the current single-hotel terminal as the entry point. It shows a summary header bar, heat map grid, filter bar, and virtualized options table. Clicking a hotel row navigates to L2 (Hotel Drill-down) which is the current terminal enhanced with T-Decay Distribution and Source Agreement charts. Clicking a row in L2 opens L3 (Option Detail) which is the existing detail panel enhanced with a Historical T chart. All data comes from 3 new JSON API endpoints that aggregate existing cached data — no new prediction logic needed.

**Tech Stack:** FastAPI, Jinja2 templates, Chart.js, vanilla JS (matching existing terminal pattern), SQLite (price_snapshots read-only), Azure SQL (medici-db read-only via `trading_db.py`)

**Data Sources:** Beyond cached signals and price_snapshots, this plan leverages the full Azure SQL trading database through existing `trading_db.py` functions — active bookings (real exposure), price velocity, cancellation history, competitor data, and App Service logs. This transforms the Terminal from a signal-only view into a real trading desk with live position data.

---

## File Structure

```
src/
  analytics/
    portfolio_aggregator.py      → NEW: Portfolio-level aggregation logic (signals + live DB data)
  api/
    routers/
      analytics_router.py        → MODIFY: Add 5 new JSON endpoints (3 core + 2 live-data)
      dashboard_router.py        → MODIFY: Add 1 new HTML route
  templates/
    macro_terminal.html          → NEW: L1 Portfolio View + L2 Hotel Drill-down (single-page app)
    terminal.html                → MODIFY: Add Historical T chart to L3 detail panel
tests/
  unit/
    test_portfolio_aggregator.py → NEW: Unit tests for aggregation logic
  integration/
    test_macro_terminal_api.py   → NEW: Integration tests for new endpoints
```

---

## Task 1: Portfolio Aggregator — Core Logic

**Files:**
- Create: `src/analytics/portfolio_aggregator.py`
- Test: `tests/unit/test_portfolio_aggregator.py`

This module reads cached signals (already computed by `options_engine.compute_next_day_signals`) and aggregates them into portfolio-level and hotel-level summaries. No new prediction logic — pure aggregation of existing data.

### Step 1.1: Write failing tests for `build_portfolio_summary()`

- [ ] **Step 1.1.1: Create test file with portfolio summary tests**

```python
# tests/unit/test_portfolio_aggregator.py
"""Tests for portfolio-level aggregation logic."""
from __future__ import annotations

import pytest

from src.analytics.portfolio_aggregator import (
    build_portfolio_summary,
    build_hotel_heatmap,
    build_hotel_drilldown,
    PortfolioSummary,
    HotelHeatmapRow,
    HotelDrilldown,
)


# ── Fixtures ──────────────────────────────────────────────────────

def _make_signal(
    detail_id: int = 1,
    hotel_id: int = 100,
    hotel_name: str = "Test Hotel",
    signal: str = "CALL",
    confidence: str = "High",
    T: int = 30,
    S_t: float = 200.0,
    category: str = "standard",
    board: str = "ro",
    expected_return_1d: float = 0.5,
    P_up: float = 75.0,
    P_down: float = 20.0,
    regime: str = "NORMAL",
    quality: str = "high",
    momentum_signal: str = "UP",
    source: str = "ensemble",
    **overrides,
) -> dict:
    """Create a single signal dict matching options_engine output."""
    sig = {
        "detail_id": str(detail_id),
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "recommendation": signal,
        "confidence": confidence,
        "T": T,
        "S_t": S_t,
        "category": category,
        "board": board,
        "expected_return_1d": expected_return_1d,
        "P_up": P_up,
        "P_down": P_down,
        "regime": regime,
        "quality": quality,
        "momentum_signal": momentum_signal,
        "checkin_date": "2026-05-01",
        "sigma_1d": 1.2,
        "velocity_24h": 0.3,
        "acceleration": 0.1,
    }
    sig.update(overrides)
    return sig


def _make_signals_mixed() -> list[dict]:
    """Portfolio with 3 hotels, mixed signals."""
    return [
        # Hotel A: 2 CALLs, 1 PUT
        _make_signal(detail_id=1, hotel_id=100, hotel_name="Hotel A", signal="CALL", confidence="High", T=5),
        _make_signal(detail_id=2, hotel_id=100, hotel_name="Hotel A", signal="CALL", confidence="Med", T=20),
        _make_signal(detail_id=3, hotel_id=100, hotel_name="Hotel A", signal="PUT", confidence="High", T=45),
        # Hotel B: 1 CALL, 2 NEUTRAL
        _make_signal(detail_id=4, hotel_id=200, hotel_name="Hotel B", signal="CALL", confidence="Low", T=10),
        _make_signal(detail_id=5, hotel_id=200, hotel_name="Hotel B", signal="NONE", confidence="Low", T=35),
        _make_signal(detail_id=6, hotel_id=200, hotel_name="Hotel B", signal="NONE", confidence="Low", T=70),
        # Hotel C: 2 PUTs
        _make_signal(detail_id=7, hotel_id=300, hotel_name="Hotel C", signal="PUT", confidence="Med", T=15),
        _make_signal(detail_id=8, hotel_id=300, hotel_name="Hotel C", signal="PUT", confidence="High", T=50),
    ]


# ── Portfolio Summary Tests ───────────────────────────────────────

class TestBuildPortfolioSummary:
    def test_counts_signals_correctly(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals)
        assert summary.total_options == 8
        assert summary.calls == 3
        assert summary.puts == 3
        assert summary.neutrals == 2

    def test_counts_hotels(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals)
        assert summary.total_hotels == 3

    def test_average_confidence_mapping(self):
        # All High confidence → should be "High"
        signals = [
            _make_signal(detail_id=i, confidence="High")
            for i in range(5)
        ]
        summary = build_portfolio_summary(signals)
        assert summary.avg_confidence == "High"

    def test_empty_signals(self):
        summary = build_portfolio_summary([])
        assert summary.total_options == 0
        assert summary.total_hotels == 0
        assert summary.calls == 0

    def test_theta_aggregate_included(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals, greeks={"total_theta": -2300.0})
        assert summary.theta_daily == -2300.0

    def test_theta_none_when_no_greeks(self):
        signals = _make_signals_mixed()
        summary = build_portfolio_summary(signals)
        assert summary.theta_daily is None
```

- [ ] **Step 1.1.2: Run tests — verify they fail**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/unit/test_portfolio_aggregator.py -v --no-header 2>&1 | head -30`
Expected: ImportError — module `portfolio_aggregator` does not exist yet.

### Step 1.2: Implement `PortfolioSummary` and `build_portfolio_summary()`

- [ ] **Step 1.2.1: Create portfolio_aggregator.py with dataclasses and summary function**

```python
# src/analytics/portfolio_aggregator.py
"""Portfolio-level aggregation for the Macro Terminal.

Reads cached signals from options_engine and aggregates them into:
  - PortfolioSummary: top-level header bar data
  - HotelHeatmapRow: one row per hotel in the heat map grid
  - HotelDrilldown: per-hotel detail with T-distribution and source agreement

This module is READ-ONLY — it never computes predictions, only aggregates.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)

# T-bucket boundaries (inclusive on both sides, non-overlapping)
T_BUCKETS = [
    ("0-7", 0, 7),       # This week
    ("8-30", 8, 30),      # This month
    ("31-60", 31, 60),    # Next month
    ("61+", 61, 9999),    # Beyond 2 months
]

CONFIDENCE_SCORES = {"High": 3, "Med": 2, "Low": 1}


@dataclass
class PortfolioSummary:
    """Summary header bar data for L1."""
    total_options: int = 0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0
    total_hotels: int = 0
    avg_confidence: str = "Low"
    theta_daily: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TBucketCell:
    """Single cell in the heat map grid (hotel × T-bucket)."""
    bucket: str
    count: int = 0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0
    dominant_signal: str = "NONE"
    avg_confidence_score: float = 0.0  # 1-3 scale for color intensity

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HotelHeatmapRow:
    """One row in the heat map — one hotel across T-buckets."""
    hotel_id: int
    hotel_name: str
    total_options: int = 0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0
    dominant_signal: str = "NONE"
    avg_price: float = 0.0
    buckets: list[TBucketCell] = field(default_factory=list)
    agreement_score: float = 0.0  # 0-100% source agreement

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class TDistributionBar:
    """One bar in the T-Decay Distribution histogram (L2)."""
    bucket: str
    count: int = 0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceAgreementRow:
    """Per-source agreement summary for a hotel (L2)."""
    source: str
    label: str
    total_signals: int = 0
    agrees_with_ensemble: int = 0
    agreement_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HotelDrilldown:
    """Full hotel detail for L2 drill-down."""
    hotel_id: int
    hotel_name: str
    total_options: int = 0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0
    t_distribution: list[TDistributionBar] = field(default_factory=list)
    source_agreement: list[SourceAgreementRow] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)  # Full option rows for table

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── Builder Functions ────────────────────────────────────────────────

def _classify_signal(rec: str) -> str:
    """Normalize signal name: CALL, PUT, or NONE."""
    rec = (rec or "").upper().strip()
    if rec == "CALL":
        return "CALL"
    if rec == "PUT":
        return "PUT"
    return "NONE"


def _t_bucket(t: int) -> str:
    """Map T value to bucket label."""
    for label, lo, hi in T_BUCKETS:
        if lo <= t <= hi:
            return label
    return "61+"


def _avg_confidence_label(signals: list[dict]) -> str:
    """Compute average confidence as a label."""
    if not signals:
        return "Low"
    total = sum(CONFIDENCE_SCORES.get(s.get("confidence", "Low"), 1) for s in signals)
    avg = total / len(signals)
    if avg >= 2.5:
        return "High"
    if avg >= 1.5:
        return "Med"
    return "Low"


def build_portfolio_summary(
    signals: list[dict],
    greeks: dict[str, Any] | None = None,
) -> PortfolioSummary:
    """Build L1 summary header bar from cached signals.

    Args:
        signals: List of signal dicts from options_engine.compute_next_day_signals().
        greeks: Optional portfolio greeks dict with 'portfolio_theta' key.

    Returns:
        PortfolioSummary with counts, hotel count, avg confidence, theta.
    """
    if not signals:
        return PortfolioSummary()

    calls = puts = neutrals = 0
    hotel_ids: set[int] = set()

    for sig in signals:
        cls = _classify_signal(sig.get("recommendation", ""))
        if cls == "CALL":
            calls += 1
        elif cls == "PUT":
            puts += 1
        else:
            neutrals += 1
        hotel_ids.add(sig.get("hotel_id", 0))

    theta = None
    if greeks and "total_theta" in greeks:
        theta = greeks["total_theta"]

    return PortfolioSummary(
        total_options=len(signals),
        calls=calls,
        puts=puts,
        neutrals=neutrals,
        total_hotels=len(hotel_ids),
        avg_confidence=_avg_confidence_label(signals),
        theta_daily=theta,
    )


def build_hotel_heatmap(
    signals: list[dict],
    source_agreement: dict[int, float] | None = None,
) -> list[HotelHeatmapRow]:
    """Build L1 heat map grid — one row per hotel, cells per T-bucket.

    Args:
        signals: List of signal dicts from options_engine.
        source_agreement: Optional dict of hotel_id → agreement % (0-100).

    Returns:
        List of HotelHeatmapRow sorted by hotel name.
    """
    if not signals:
        return []

    # Group by hotel
    by_hotel: dict[int, list[dict]] = defaultdict(list)
    hotel_names: dict[int, str] = {}
    for sig in signals:
        hid = sig.get("hotel_id", 0)
        by_hotel[hid].append(sig)
        hotel_names[hid] = sig.get("hotel_name", f"Hotel {hid}")

    rows: list[HotelHeatmapRow] = []
    for hid, hotel_signals in by_hotel.items():
        # Build T-bucket cells
        bucket_map: dict[str, list[dict]] = defaultdict(list)
        for sig in hotel_signals:
            t = sig.get("T", 0)
            bucket_map[_t_bucket(t)].append(sig)

        cells: list[TBucketCell] = []
        for label, _, _ in T_BUCKETS:
            sigs_in_bucket = bucket_map.get(label, [])
            c = p = n = 0
            conf_sum = 0.0
            for s in sigs_in_bucket:
                cls = _classify_signal(s.get("recommendation", ""))
                if cls == "CALL":
                    c += 1
                elif cls == "PUT":
                    p += 1
                else:
                    n += 1
                conf_sum += CONFIDENCE_SCORES.get(s.get("confidence", "Low"), 1)

            dominant = "NONE"
            if c >= p and c >= n and c > 0:
                dominant = "CALL"
            elif p >= c and p >= n and p > 0:
                dominant = "PUT"

            avg_conf = conf_sum / len(sigs_in_bucket) if sigs_in_bucket else 0.0

            cells.append(TBucketCell(
                bucket=label,
                count=len(sigs_in_bucket),
                calls=c, puts=p, neutrals=n,
                dominant_signal=dominant,
                avg_confidence_score=avg_conf,
            ))

        # Hotel-level totals
        total_c = sum(cell.calls for cell in cells)
        total_p = sum(cell.puts for cell in cells)
        total_n = sum(cell.neutrals for cell in cells)
        dominant = "NONE"
        if total_c >= total_p and total_c >= total_n and total_c > 0:
            dominant = "CALL"
        elif total_p >= total_c and total_p >= total_n and total_p > 0:
            dominant = "PUT"

        prices = [s.get("S_t", 0) for s in hotel_signals if s.get("S_t")]
        avg_price = sum(prices) / len(prices) if prices else 0.0

        agree = 0.0
        if source_agreement and hid in source_agreement:
            agree = source_agreement[hid]

        rows.append(HotelHeatmapRow(
            hotel_id=hid,
            hotel_name=hotel_names[hid],
            total_options=len(hotel_signals),
            calls=total_c, puts=total_p, neutrals=total_n,
            dominant_signal=dominant,
            avg_price=avg_price,
            buckets=cells,
            agreement_score=agree,
        ))

    rows.sort(key=lambda r: r.hotel_name)
    return rows


def build_hotel_drilldown(
    signals: list[dict],
    hotel_id: int,
    predictions: dict[str, dict] | None = None,
) -> HotelDrilldown | None:
    """Build L2 hotel drill-down: T-distribution + source agreement + options list.

    Args:
        signals: All portfolio signals.
        hotel_id: Hotel to drill into.
        predictions: Optional analysis['predictions'] dict for source-level data.

    Returns:
        HotelDrilldown or None if hotel not found.
    """
    hotel_signals = [s for s in signals if s.get("hotel_id") == hotel_id]
    if not hotel_signals:
        return None

    hotel_name = hotel_signals[0].get("hotel_name", f"Hotel {hotel_id}")

    # Signal counts
    calls = puts = neutrals = 0
    for sig in hotel_signals:
        cls = _classify_signal(sig.get("recommendation", ""))
        if cls == "CALL":
            calls += 1
        elif cls == "PUT":
            puts += 1
        else:
            neutrals += 1

    # T-Distribution histogram
    bucket_counts: dict[str, list[dict]] = defaultdict(list)
    for sig in hotel_signals:
        bucket_counts[_t_bucket(sig.get("T", 0))].append(sig)

    t_dist: list[TDistributionBar] = []
    for label, _, _ in T_BUCKETS:
        sigs = bucket_counts.get(label, [])
        c = sum(1 for s in sigs if _classify_signal(s.get("recommendation", "")) == "CALL")
        p = sum(1 for s in sigs if _classify_signal(s.get("recommendation", "")) == "PUT")
        n = len(sigs) - c - p
        t_dist.append(TDistributionBar(bucket=label, count=len(sigs), calls=c, puts=p, neutrals=n))

    # Source agreement — requires predictions dict with fc_price, hist_price, ml_price
    source_rows: list[SourceAgreementRow] = []
    if predictions:
        source_defs = [
            ("forward_curve", "Forward Curve", "fc_price"),
            ("historical", "Historical", "hist_price"),
            ("ml", "ML Model", "ml_price"),
        ]
        for src_key, src_label, price_key in source_defs:
            total = agrees = 0
            for sig in hotel_signals:
                did = str(sig.get("detail_id", ""))
                pred = predictions.get(did)
                if not pred:
                    continue
                src_price = pred.get(price_key)
                ensemble_price = pred.get("predicted_checkin_price")
                current = pred.get("current_price") or sig.get("S_t")
                if src_price is None or ensemble_price is None or not current:
                    continue
                total += 1
                # Agree = same direction (both above or both below current price)
                src_dir = 1 if src_price > current else (-1 if src_price < current else 0)
                ens_dir = 1 if ensemble_price > current else (-1 if ensemble_price < current else 0)
                if src_dir == ens_dir:
                    agrees += 1
            source_rows.append(SourceAgreementRow(
                source=src_key,
                label=src_label,
                total_signals=total,
                agrees_with_ensemble=agrees,
                agreement_pct=round(agrees / total * 100, 1) if total > 0 else 0.0,
            ))

    # Build options list for the table (reuse signal dicts, add enrichment data)
    options: list[dict] = []
    for sig in hotel_signals:
        row = {
            "detail_id": sig.get("detail_id"),
            "category": sig.get("category", ""),
            "board": sig.get("board", ""),
            "checkin_date": sig.get("checkin_date", ""),
            "T": sig.get("T", 0),
            "S_t": sig.get("S_t", 0),
            "signal": _classify_signal(sig.get("recommendation", "")),
            "confidence": sig.get("confidence", "Low"),
            "expected_return_1d": sig.get("expected_return_1d", 0),
            "regime": sig.get("regime", ""),
            "quality": sig.get("quality", ""),
            "momentum_signal": sig.get("momentum_signal", ""),
            "P_up": sig.get("P_up", 0),
            "P_down": sig.get("P_down", 0),
        }
        # Add source disagreement count from predictions
        did = str(sig.get("detail_id", ""))
        pred = predictions.get(did) if predictions else None
        if pred:
            row["predicted_price"] = pred.get("predicted_checkin_price")
            row["min_price"] = pred.get("min_price", pred.get("current_price", 0) * 0.9)
            row["max_price"] = pred.get("max_price", pred.get("current_price", 0) * 1.1)
        options.append(row)

    # Sort: PUTs first (highest urgency), then by T ascending
    signal_order = {"PUT": 0, "CALL": 1, "NONE": 2}
    options.sort(key=lambda o: (signal_order.get(o.get("signal", "NONE"), 2), o.get("T", 0)))

    return HotelDrilldown(
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        total_options=len(hotel_signals),
        calls=calls, puts=puts, neutrals=neutrals,
        t_distribution=t_dist,
        source_agreement=source_rows,
        options=options,
    )
```

- [ ] **Step 1.2.2: Run tests — verify they pass**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/unit/test_portfolio_aggregator.py -v --no-header 2>&1 | tail -20`
Expected: All 6 tests PASS.

### Step 1.3: Write and pass tests for `build_hotel_heatmap()`

- [ ] **Step 1.3.1: Add heatmap tests to test file**

Append to `tests/unit/test_portfolio_aggregator.py`:

```python
class TestBuildHotelHeatmap:
    def test_returns_one_row_per_hotel(self):
        signals = _make_signals_mixed()
        rows = build_hotel_heatmap(signals)
        assert len(rows) == 3  # Hotels A, B, C

    def test_rows_sorted_by_name(self):
        signals = _make_signals_mixed()
        rows = build_hotel_heatmap(signals)
        names = [r.hotel_name for r in rows]
        assert names == sorted(names)

    def test_each_row_has_4_t_buckets(self):
        signals = _make_signals_mixed()
        rows = build_hotel_heatmap(signals)
        for row in rows:
            assert len(row.buckets) == 4
            assert [b.bucket for b in row.buckets] == ["0-7", "8-30", "31-60", "61+"]

    def test_t_bucket_assignment(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, T=3),   # 0-7 bucket
            _make_signal(detail_id=2, hotel_id=100, T=15),  # 7-30 bucket
            _make_signal(detail_id=3, hotel_id=100, T=45),  # 30-60 bucket
            _make_signal(detail_id=4, hotel_id=100, T=90),  # 60+ bucket
        ]
        rows = build_hotel_heatmap(signals)
        assert len(rows) == 1
        buckets = rows[0].buckets
        assert buckets[0].count == 1  # 0-7
        assert buckets[1].count == 1  # 7-30
        assert buckets[2].count == 1  # 30-60
        assert buckets[3].count == 1  # 60+

    def test_dominant_signal_in_bucket(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, signal="CALL", T=5),
            _make_signal(detail_id=2, hotel_id=100, signal="CALL", T=6),
            _make_signal(detail_id=3, hotel_id=100, signal="PUT", T=7),
        ]
        rows = build_hotel_heatmap(signals)
        # 0-7 bucket: 2 CALL, 1 PUT → dominant = CALL
        assert rows[0].buckets[0].dominant_signal == "CALL"

    def test_agreement_score_from_external_dict(self):
        signals = [_make_signal(detail_id=1, hotel_id=100)]
        agreement = {100: 85.5}
        rows = build_hotel_heatmap(signals, source_agreement=agreement)
        assert rows[0].agreement_score == 85.5

    def test_empty_signals(self):
        rows = build_hotel_heatmap([])
        assert rows == []

    def test_avg_price_computed(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, S_t=200.0),
            _make_signal(detail_id=2, hotel_id=100, S_t=300.0),
        ]
        rows = build_hotel_heatmap(signals)
        assert rows[0].avg_price == 250.0
```

- [ ] **Step 1.3.2: Run tests — verify they pass**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/unit/test_portfolio_aggregator.py -v --no-header 2>&1 | tail -25`
Expected: All 14+ tests PASS.

### Step 1.4: Write and pass tests for `build_hotel_drilldown()`

- [ ] **Step 1.4.1: Add drilldown tests**

Append to `tests/unit/test_portfolio_aggregator.py`:

```python
class TestBuildHotelDrilldown:
    def test_returns_none_for_unknown_hotel(self):
        signals = _make_signals_mixed()
        result = build_hotel_drilldown(signals, hotel_id=999)
        assert result is None

    def test_correct_signal_counts(self):
        signals = _make_signals_mixed()
        dd = build_hotel_drilldown(signals, hotel_id=100)
        assert dd is not None
        assert dd.calls == 2
        assert dd.puts == 1
        assert dd.neutrals == 0

    def test_t_distribution_has_4_bars(self):
        signals = _make_signals_mixed()
        dd = build_hotel_drilldown(signals, hotel_id=100)
        assert len(dd.t_distribution) == 4

    def test_options_list_matches_hotel_signals(self):
        signals = _make_signals_mixed()
        dd = build_hotel_drilldown(signals, hotel_id=100)
        assert len(dd.options) == 3  # Hotel A has 3 signals

    def test_options_sorted_puts_first(self):
        signals = _make_signals_mixed()
        dd = build_hotel_drilldown(signals, hotel_id=100)
        signal_types = [o["signal"] for o in dd.options]
        # PUT should come before CALL
        assert signal_types.index("PUT") < signal_types.index("CALL")

    def test_source_agreement_with_predictions(self):
        signals = [
            _make_signal(detail_id=1, hotel_id=100, S_t=200.0),
        ]
        predictions = {
            "1": {
                "fc_price": 210.0,
                "hist_price": 210.0,
                "ml_price": 190.0,
                "predicted_checkin_price": 207.0,
                "current_price": 200.0,
            },
        }
        dd = build_hotel_drilldown(signals, hotel_id=100, predictions=predictions)
        assert len(dd.source_agreement) == 3
        # FC and Hist agree with ensemble (both up), ML disagrees (down vs up)
        fc_row = next(r for r in dd.source_agreement if r.source == "forward_curve")
        ml_row = next(r for r in dd.source_agreement if r.source == "ml")
        assert fc_row.agreement_pct == 100.0
        assert ml_row.agreement_pct == 0.0

    def test_source_agreement_empty_without_predictions(self):
        signals = [_make_signal(detail_id=1, hotel_id=100)]
        dd = build_hotel_drilldown(signals, hotel_id=100)
        # source_agreement should still be populated but with 0 totals
        assert len(dd.source_agreement) == 0  # No predictions → no source rows
```

- [ ] **Step 1.4.2: Run all tests**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/unit/test_portfolio_aggregator.py -v --no-header 2>&1 | tail -30`
Expected: All 21+ tests PASS.

- [ ] **Step 1.4.3: Compile check**

Run: `python3 -m py_compile src/analytics/portfolio_aggregator.py && echo "OK"`
Expected: OK

- [ ] **Step 1.4.4: Commit**

```bash
git add src/analytics/portfolio_aggregator.py tests/unit/test_portfolio_aggregator.py
git commit -m "feat: add portfolio_aggregator.py — L1/L2 aggregation logic with 21 tests"
```

---

## Task 2: API Endpoints — 3 New JSON Routes

**Files:**
- Modify: `src/api/routers/analytics_router.py` (append at end, ~lines 2100+)
- Test: `tests/unit/test_portfolio_aggregator.py` (add endpoint-level test)
- Test: `tests/integration/test_macro_terminal_api.py`

Three new endpoints that power the Macro Terminal UI. All read from the existing cached signals — no new computation.

### Step 2.1: Add `/macro/summary` endpoint

- [ ] **Step 2.1.1: Write integration test**

```python
# tests/integration/test_macro_terminal_api.py
"""Integration tests for Macro Terminal API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked analysis cache."""
    from unittest.mock import patch, MagicMock
    from src.api.main import app

    # Mock signals data
    mock_signals = [
        {
            "detail_id": "1", "hotel_id": 100, "hotel_name": "Test Hotel A",
            "recommendation": "CALL", "confidence": "High", "T": 15,
            "S_t": 200.0, "category": "standard", "board": "ro",
            "expected_return_1d": 0.5, "P_up": 75.0, "P_down": 20.0,
            "regime": "NORMAL", "quality": "high", "momentum_signal": "UP",
            "checkin_date": "2026-05-01", "sigma_1d": 1.2,
            "velocity_24h": 0.3, "acceleration": 0.1,
        },
        {
            "detail_id": "2", "hotel_id": 200, "hotel_name": "Test Hotel B",
            "recommendation": "PUT", "confidence": "Med", "T": 30,
            "S_t": 300.0, "category": "deluxe", "board": "bb",
            "expected_return_1d": -0.3, "P_up": 30.0, "P_down": 65.0,
            "regime": "NORMAL", "quality": "medium", "momentum_signal": "DOWN",
            "checkin_date": "2026-06-01", "sigma_1d": 1.5,
            "velocity_24h": -0.2, "acceleration": -0.1,
        },
    ]
    mock_analysis = {
        "predictions": {},
        "statistics": {"total_rooms": 2, "total_hotels": 2},
    }

    with patch("src.api.routers.analytics_router._get_cached_signals", return_value=mock_signals), \
         patch("src.api.routers.analytics_router._get_cached_analysis", return_value=mock_analysis):
        yield TestClient(app)


class TestMacroSummary:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/salesoffice/macro/summary")
        assert resp.status_code == 200

    def test_summary_structure(self, client):
        data = client.get("/api/v1/salesoffice/macro/summary").json()
        assert "summary" in data
        assert "heatmap" in data
        s = data["summary"]
        assert "total_options" in s
        assert "calls" in s
        assert "puts" in s

    def test_heatmap_has_hotels(self, client):
        data = client.get("/api/v1/salesoffice/macro/summary").json()
        assert len(data["heatmap"]) == 2


class TestMacroHotelDrilldown:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/salesoffice/macro/hotel/100")
        assert resp.status_code == 200

    def test_returns_404_unknown_hotel(self, client):
        resp = client.get("/api/v1/salesoffice/macro/hotel/999")
        assert resp.status_code == 404

    def test_drilldown_structure(self, client):
        data = client.get("/api/v1/salesoffice/macro/hotel/100").json()
        assert "hotel_id" in data
        assert "t_distribution" in data
        assert "options" in data


class TestMacroHistoricalT:
    def test_returns_404_no_history(self, client):
        """No price_snapshots for this detail_id → 404."""
        resp = client.get("/api/v1/salesoffice/macro/historical-t/9999")
        assert resp.status_code == 404

    def test_returns_200_with_history(self, client_with_history):
        """When price history exists → 200 with actual points."""
        resp = client_with_history.get("/api/v1/salesoffice/macro/historical-t/1")
        assert resp.status_code == 200
        data = resp.json()
        assert "actual" in data
        assert "predicted" in data
        assert "checkin_date" in data
        assert len(data["actual"]) > 0

    def test_actual_points_sorted_high_t_first(self, client_with_history):
        """Actual points should be sorted by T descending (high T on left)."""
        data = client_with_history.get("/api/v1/salesoffice/macro/historical-t/1").json()
        t_values = [p["t"] for p in data["actual"]]
        assert t_values == sorted(t_values, reverse=True)
```

Note: `client_with_history` fixture needs a mock of `price_store.load_price_history()` returning a DataFrame with snapshot_ts and room_price columns, plus mock signals containing the matching detail_id with a checkin_date. Example fixture:

```python
@pytest.fixture
def client_with_history():
    from unittest.mock import patch
    import pandas as pd
    from src.api.main import app

    mock_signals = [
        {
            "detail_id": "1", "hotel_id": 100, "hotel_name": "Test Hotel A",
            "recommendation": "CALL", "confidence": "High", "T": 15,
            "S_t": 200.0, "category": "standard", "board": "ro",
            "checkin_date": "2026-05-01", "expected_return_1d": 0.5,
            "P_up": 75.0, "P_down": 20.0, "regime": "NORMAL",
            "quality": "high", "momentum_signal": "UP",
            "sigma_1d": 1.2, "velocity_24h": 0.3, "acceleration": 0.1,
        },
    ]
    mock_history = pd.DataFrame({
        "snapshot_ts": ["2026-04-15 09:00:00", "2026-04-16 09:00:00", "2026-04-17 09:00:00"],
        "room_price": [195.0, 198.0, 200.0],
    })

    with patch("src.api.routers.analytics_router._get_cached_signals", return_value=mock_signals), \
         patch("src.api.routers.analytics_router._get_cached_analysis", return_value={"predictions": {}}), \
         patch("src.analytics.price_store.load_price_history", return_value=mock_history):
        yield TestClient(app)
```

- [ ] **Step 2.1.2: Add 3 endpoints to analytics_router.py**

Append to `src/api/routers/analytics_router.py`:

```python
# ── Macro Terminal endpoints ──────────────────────────────────────────

@analytics_router.get("/macro/summary")
def macro_portfolio_summary(request: Request, _key=Depends(_optional_api_key)):
    """L1 Portfolio View — summary header + hotel heat map."""
    signals = _get_cached_signals()
    if not signals:
        raise HTTPException(503, "Signals not ready — cache warming up")

    analysis = _get_cached_analysis()

    from src.analytics.portfolio_aggregator import (
        build_portfolio_summary,
        build_hotel_heatmap,
    )

    # Try to get portfolio theta from greeks
    greeks = None
    try:
        from src.analytics.portfolio_greeks import compute_portfolio_greeks
        if analysis:
            pg = compute_portfolio_greeks(analysis)
            greeks = {"total_theta": pg.portfolio_theta}
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        logger.debug("Greeks unavailable for macro summary: %s", exc)

    summary = build_portfolio_summary(signals, greeks=greeks)
    heatmap = build_hotel_heatmap(signals)

    return {
        "summary": summary.to_dict(),
        "heatmap": [r.to_dict() for r in heatmap],
    }


@analytics_router.get("/macro/hotel/{hotel_id}")
def macro_hotel_drilldown(hotel_id: int, request: Request, _key=Depends(_optional_api_key)):
    """L2 Hotel Drill-down — T-distribution, source agreement, options list."""
    signals = _get_cached_signals()
    if not signals:
        raise HTTPException(503, "Signals not ready — cache warming up")

    analysis = _get_cached_analysis()
    predictions = analysis.get("predictions", {}) if analysis else {}

    from src.analytics.portfolio_aggregator import build_hotel_drilldown

    drilldown = build_hotel_drilldown(signals, hotel_id, predictions=predictions)
    if drilldown is None:
        raise HTTPException(404, f"Hotel {hotel_id} not found in signals")

    return drilldown.to_dict()


@analytics_router.get("/macro/historical-t/{detail_id}")
def macro_historical_t(detail_id: int, request: Request, _key=Depends(_optional_api_key)):
    """L3 Historical T chart — actual vs predicted price indexed by T.

    Returns two series:
      - actual: [{t, price, date}] — observed price at each scan
      - predicted: [{t, price, date}] — forward curve prediction made at that scan's T

    X axis = T (high to low, left to right = time moving forward)
    Y axis = price in USD
    """
    from src.analytics.price_store import load_price_history

    history = load_price_history(detail_id)
    if history.empty:
        raise HTTPException(404, f"No price history for detail_id={detail_id}")

    # Get check-in date from analysis cache
    analysis = _get_cached_analysis()
    checkin_date = None
    if analysis and "predictions" in analysis:
        pred = analysis["predictions"].get(str(detail_id))
        if pred:
            checkin_date = pred.get("date_from")

    if not checkin_date:
        # Try to get from signals
        signals = _get_cached_signals()
        if signals:
            match = next((s for s in signals if str(s.get("detail_id")) == str(detail_id)), None)
            if match:
                checkin_date = match.get("checkin_date")

    if not checkin_date:
        raise HTTPException(404, f"Cannot determine check-in date for detail_id={detail_id}")

    import pandas as pd
    from datetime import datetime

    checkin_dt = pd.to_datetime(checkin_date)
    actual_points = []
    for _, row in history.iterrows():
        scan_dt = pd.to_datetime(row["snapshot_ts"])
        t = (checkin_dt - scan_dt).days
        if t < 0:
            continue  # Skip post-checkin scans
        actual_points.append({
            "t": t,
            "price": round(float(row["room_price"]), 2),
            "date": scan_dt.strftime("%Y-%m-%d %H:%M"),
        })

    # Build predicted series from forward curve if available
    predicted_points = []
    if analysis and "predictions" in analysis:
        pred = analysis["predictions"].get(str(detail_id))
        if pred and "forward_curve" in pred:
            for pt in pred["forward_curve"]:
                predicted_points.append({
                    "t": pt.get("t", 0),
                    "price": round(float(pt.get("predicted_price", 0)), 2),
                    "date": pt.get("date", ""),
                })

    return {
        "detail_id": detail_id,
        "checkin_date": checkin_date,
        "actual": sorted(actual_points, key=lambda p: -p["t"]),  # High T first
        "predicted": sorted(predicted_points, key=lambda p: -p["t"]),
    }
```

- [ ] **Step 2.1.3: Run integration tests**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/integration/test_macro_terminal_api.py -v --no-header 2>&1 | tail -20`
Expected: All 5 integration tests PASS.

- [ ] **Step 2.1.4: Compile check**

Run: `python3 -m py_compile src/api/routers/analytics_router.py && echo "OK"`
Expected: OK

- [ ] **Step 2.1.5: Commit**

```bash
git add src/api/routers/analytics_router.py tests/integration/test_macro_terminal_api.py
git commit -m "feat: add 3 macro terminal API endpoints — /macro/summary, /macro/hotel, /macro/historical-t"
```

---

## Task 3: L1 Portfolio View — HTML Template

**Files:**
- Create: `src/templates/macro_terminal.html`
- Modify: `src/api/routers/dashboard_router.py` (add route)

This is the largest task. The template is a self-contained HTML page (following the existing terminal.html pattern) with:
1. Summary Header Bar (sticky top)
2. Heat Map Grid (hotels × T-buckets)
3. Filter Bar (signal, hotel, confidence, T-range)
4. Virtualized Options Table (all portfolio options)
5. L2 Hotel Drill-down panel (slides in when hotel clicked)

### Step 3.1: Add HTML route to dashboard_router.py

- [ ] **Step 3.1.1: Add the route**

Add to `src/api/routers/dashboard_router.py` after the existing terminal route (line ~377):

```python
@dashboard_router.get("/dashboard/macro", response_class=HTMLResponse)
async def dashboard_macro_terminal():
    """Macro Trading Terminal — portfolio-level 3-level drill-down view."""
    from src.utils.template_engine import render_template
    return HTMLResponse(content=render_template("macro_terminal.html"))
```

- [ ] **Step 3.1.2: Compile check**

Run: `python3 -m py_compile src/api/routers/dashboard_router.py && echo "OK"`
Expected: OK

- [ ] **Step 3.1.3: Commit**

```bash
git add src/api/routers/dashboard_router.py
git commit -m "feat: add /dashboard/macro route for macro terminal"
```

### Step 3.2: Create macro_terminal.html — Structure and Styles

- [ ] **Step 3.2.1: Create template file**

Create `src/templates/macro_terminal.html` with the full L1 + L2 single-page application. This is a large file — build it section by section.

**Section 1: Head, CSS variables (reuse terminal.html design tokens), Summary Bar HTML structure.**

Key CSS requirements:
- Reuse `--bg`, `--surface`, `--panel`, `--border`, `--call`, `--put`, `--none` from terminal.html
- Summary bar: `position: sticky; top: 0; z-index: 100; background: var(--panel)`
- Heat map cells: CSS Grid with `grid-template-columns: 200px repeat(4, 1fr)`
- Cell colors: `.cell-call { background: rgba(0,200,83, var(--intensity)) }`, same for PUT/NONE
- Intensity mapped from confidence_score: High=0.6, Med=0.35, Low=0.15
- Filter bar: `display: flex; gap: 8px; flex-wrap: wrap`
- L2 panel: `position: fixed; right: 0; top: 0; width: 50vw; height: 100vh; transform: translateX(100%); transition: transform 0.3s`

**Section 2: JavaScript — API calls, state management, rendering.**

Key JS architecture:
```javascript
const STATE = {
    signals: [],          // Raw signals from /macro/summary
    summary: null,        // PortfolioSummary
    heatmap: [],          // HotelHeatmapRow[]
    filters: {signal: null, hotel: null, confidence: null, minT: 0, maxT: 999},
    activeHotel: null,    // Hotel ID for L2 panel
    activeDetail: null,   // Detail ID for L3 (redirect to terminal)
};

async function loadPortfolio() { ... }      // GET /macro/summary
async function loadHotelDrilldown(id) { ... }  // GET /macro/hotel/{id}
function renderSummaryBar() { ... }
function renderHeatmap() { ... }
function renderFilteredTable() { ... }
function renderL2Panel(data) { ... }
function applyFilters() { ... }
```

**Section 3: Heat map rendering.**

Each cell rendered as:
```html
<div class="hm-cell cell-{signal}" style="--intensity:{confidence}"
     data-hotel="{hotel_id}" data-bucket="{bucket}">
  <span class="cell-count">{count}</span>
</div>
```

Hover tooltip shows: `{calls}C / {puts}P / {neutrals}N | Avg conf: {score}`

**Section 4: Filter bar rendering.**

Dropdowns populated dynamically from loaded signals:
- Signal: ALL / CALL / PUT / NEUTRAL
- Hotel: ALL / [hotel names from heatmap]
- Source: Ensemble (default — defer source-only filtering to phase 2)
- Confidence: ALL / High / Med / Low
- T range: two `<input type="range">` elements for min/max

Filtering operates client-side on `STATE.signals` array.

**Section 5: Virtualized options table.**

For 500+ rows without React, use a simple windowing approach:
```javascript
// Render only visible rows + buffer
const ROW_HEIGHT = 32;
const BUFFER = 20;
const container = document.getElementById('opts-scroll');
container.addEventListener('scroll', () => {
    const scrollTop = container.scrollTop;
    const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - BUFFER);
    const endIdx = Math.min(filteredRows.length, startIdx + visibleCount + BUFFER * 2);
    renderTableSlice(startIdx, endIdx);
});
```

Table columns: Hotel | Category | Board | Check-in | T | Price | Signal | Confidence | Trade% | Actions

**Section 6: L2 Hotel Drill-down panel.**

Slides in from right when hotel row clicked in heatmap. Contains:
- Hotel header with signal breakdown
- T-Decay Distribution chart (Chart.js horizontal stacked bar)
- Source Agreement chart (Chart.js horizontal bar, 3 bars: FC, Historical, ML)
- Options table filtered to that hotel

Click on an option row → navigate to existing terminal with `?hotel={id}&option={detail_id}` query params.

**Section 7: L2→L3 handoff.**

When an option row is clicked in L2, redirect to existing terminal:
```javascript
function openOptionDetail(hotelId, detailId) {
    window.location.href = `/api/v1/salesoffice/dashboard/terminal?hotel=${hotelId}&detail=${detailId}`;
}
```

This requires a small modification to `terminal.html` (Task 4) to read query params and auto-select.

- [ ] **Step 3.2.2: Verify template renders**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python3 -c "from src.utils.template_engine import render_template; html = render_template('macro_terminal.html'); print(f'OK — {len(html)} chars')" 2>&1`
Expected: `OK — XXXXX chars`

- [ ] **Step 3.2.3: Commit**

```bash
git add src/templates/macro_terminal.html
git commit -m "feat: add macro_terminal.html — L1 portfolio view with heatmap, filters, virtualized table"
```

---

## Task 4: L3 Enhancement — Historical T Chart + Query Param Auto-Select

**Files:**
- Modify: `src/templates/terminal.html`

### Step 4.1: Add query param handling to terminal.html

- [ ] **Step 4.1.1: Add URL param reader to terminal.html init()**

In `src/templates/terminal.html`, after the `init()` function (around line 238), add query param handling:

```javascript
// Inside init(), after hotels are populated in dropdown:
const params = new URLSearchParams(window.location.search);
const presetHotel = params.get('hotel');
const presetDetail = params.get('detail');
if (presetHotel) {
    el('sel-hotel').value = presetHotel;
    onHotelChange();  // This populates the options dropdown synchronously from S.options
    if (presetDetail) {
        // onHotelChange() populates sel-option synchronously from the already-loaded
        // S.options array, so no timeout needed — just set the value directly.
        el('sel-option').value = presetDetail;
        onOptionChange();
    }
}
```

- [ ] **Step 4.1.2: Add "← Back to Portfolio" link in terminal header**

In terminal.html header section (~line 123), add a back link:

```html
<a href="/api/v1/salesoffice/dashboard/macro" style="font-size:12px">&larr; Portfolio</a>
```

### Step 4.2: Add Historical T chart to terminal.html

- [ ] **Step 4.2.1: Add chart container after the Enrichment Decomposition chart**

After the enrichment chart box (~line 138 in terminal.html), add:

```html
<div class="chart-box" id="hist-t-box" style="height:220px;display:none">
  <div class="chart-title">Historical T — Actual vs Predicted</div>
  <canvas id="hist-t-chart"></canvas>
</div>
```

- [ ] **Step 4.2.2: Add Historical T chart rendering function**

Add to the `<script>` section in terminal.html:

```javascript
let histTChart = null;

async function loadHistoricalT(detailId) {
    const box = el('hist-t-box');
    const data = await api(`/macro/historical-t/${detailId}`);
    if (!data || !data.actual || data.actual.length < 2) {
        box.style.display = 'none';
        return;
    }
    box.style.display = 'block';

    const actualPts = data.actual.map(p => ({x: p.t, y: p.price}));
    const predictedPts = data.predicted.map(p => ({x: p.t, y: p.price}));

    if (histTChart) histTChart.destroy();
    histTChart = new Chart(el('hist-t-chart'), {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Actual Price',
                    data: actualPts,
                    borderColor: '#42a5f5',
                    backgroundColor: 'rgba(66,165,245,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    borderWidth: 2,
                },
                {
                    label: 'Predicted (FC)',
                    data: predictedPts,
                    borderColor: '#ffa726',
                    borderDash: [5, 5],
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 1.5,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    reverse: true,  // High T on left, low T on right
                    title: {display: true, text: 'T (days to check-in)', color: '#8899aa'},
                    ticks: {color: '#8899aa'},
                    grid: {color: 'rgba(255,255,255,0.05)'},
                },
                y: {
                    title: {display: true, text: 'Price ($)', color: '#8899aa'},
                    ticks: {color: '#8899aa', callback: v => '$' + v},
                    grid: {color: 'rgba(255,255,255,0.05)'},
                },
            },
            plugins: {
                legend: {labels: {color: '#eee'}},
                tooltip: {
                    callbacks: {
                        title: ctx => `T = ${ctx[0].parsed.x} days`,
                        label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y}`,
                    },
                },
            },
        },
    });
}
```

- [ ] **Step 4.2.3: Call `loadHistoricalT()` from `onOptionChange()`**

In the `onOptionChange()` function in terminal.html, after the existing detail load call, add:

```javascript
loadHistoricalT(S.detailId);
```

- [ ] **Step 4.2.4: Verify terminal.html is valid HTML**

Run: `python3 -c "from src.utils.template_engine import render_template; html = render_template('terminal.html'); print(f'OK — {len(html)} chars')" 2>&1`
Expected: `OK — XXXXX chars`

- [ ] **Step 4.2.5: Commit**

```bash
git add src/templates/terminal.html
git commit -m "feat: add Historical T chart + query param auto-select + back-to-portfolio link to terminal"
```

---

## Task 5: Landing Page Integration

**Files:**
- Modify: `src/analytics/landing_page.py` (add Macro Terminal link)

### Step 5.1: Add link to landing page

- [ ] **Step 5.1.1: Find the page links section in landing_page.py and add Macro Terminal**

Read `src/analytics/landing_page.py`, find where page links are defined (likely a list of dicts or HTML block with links to `/dashboard/*`), and add a new entry:

```python
{
    "title": "Macro Terminal",
    "url": "/api/v1/salesoffice/dashboard/macro",
    "description": "Portfolio-level trading view — heat map, drill-down, all hotels at once",
    "icon": "📊",
}
```

Position it before or next to the existing "Trading Terminal" link.

- [ ] **Step 5.1.2: Compile check**

Run: `python3 -m py_compile src/analytics/landing_page.py && echo "OK"`
Expected: OK

- [ ] **Step 5.1.3: Commit**

```bash
git add src/analytics/landing_page.py
git commit -m "feat: add Macro Terminal link to landing page"
```

---

## Task 6: Full Integration Verification

### Step 6.1: Run all existing tests

- [ ] **Step 6.1.1: Run full test suite**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/ -v --no-header --tb=short 2>&1 | tail -40`
Expected: All 237+ existing tests PASS, plus ~26 new tests PASS.

- [ ] **Step 6.1.2: Compile-check all modified files**

Run: `python3 -m py_compile src/analytics/portfolio_aggregator.py && python3 -m py_compile src/api/routers/analytics_router.py && python3 -m py_compile src/api/routers/dashboard_router.py && echo "ALL OK"`
Expected: ALL OK

### Step 6.2: Manual smoke test endpoints

- [ ] **Step 6.2.1: Start server and test endpoints**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && timeout 10 python3 -c "
from fastapi.testclient import TestClient
from src.api.main import app
c = TestClient(app)

# Verify new routes exist (will return 503 without warm cache — that's OK)
for path in ['/api/v1/salesoffice/macro/summary', '/api/v1/salesoffice/dashboard/macro']:
    r = c.get(path)
    print(f'{path} → {r.status_code}')
print('Smoke test passed')
" 2>&1`
Expected: Status codes 200 or 503 (503 is acceptable — means cache not warm but route exists).

- [ ] **Step 6.2.2: Final commit**

```bash
git add -A
git commit -m "feat: Macro Terminal v1 — complete 3-level portfolio navigation"
```

---

## Task 7: Live Trading Data Layer (Azure SQL Integration)

**Files:**
- Modify: `src/analytics/portfolio_aggregator.py` (add live data functions)
- Modify: `src/api/routers/analytics_router.py` (add 2 new endpoints)
- Modify: `src/templates/macro_terminal.html` (add Position Panel and Velocity indicators)
- Test: `tests/unit/test_portfolio_aggregator.py` (add live data tests)

This task connects the Macro Terminal to the real trading database via the existing `trading_db.py` read-only functions. This transforms the Terminal from a signal-only view into a real trading desk with live position data, PnL, and price velocity.

### Step 7.1: Add `build_portfolio_positions()` to portfolio_aggregator.py

- [ ] **Step 7.1.1: Write failing tests for position aggregation**

Append to `tests/unit/test_portfolio_aggregator.py`:

```python
from src.analytics.portfolio_aggregator import (
    build_portfolio_positions,
    build_hotel_velocity,
    PortfolioPositions,
    HotelVelocity,
)


class TestBuildPortfolioPositions:
    def test_basic_aggregation(self, mock_bookings):
        """Active bookings → position summary per hotel."""
        positions = build_portfolio_positions(mock_bookings)
        assert positions.total_active > 0
        assert positions.total_exposure_buy > 0
        assert positions.total_exposure_sell >= positions.total_exposure_buy

    def test_hotel_breakdown(self, mock_bookings):
        """Each hotel has a position entry with buy/sell exposure."""
        positions = build_portfolio_positions(mock_bookings)
        assert len(positions.hotels) > 0
        for h in positions.hotels:
            assert "hotel_id" in h
            assert "active_count" in h
            assert "buy_exposure" in h
            assert "sell_exposure" in h
            assert "unrealized_pnl" in h

    def test_empty_bookings(self):
        import pandas as pd
        positions = build_portfolio_positions(pd.DataFrame())
        assert positions.total_active == 0

    def test_pnl_calculation(self, mock_bookings):
        """Unrealized PnL = sum(PushPrice - BuyPrice) per booking."""
        positions = build_portfolio_positions(mock_bookings)
        assert isinstance(positions.total_unrealized_pnl, float)


class TestBuildHotelVelocity:
    def test_velocity_per_hotel(self, mock_velocity_data):
        """Price velocity indicators per hotel from update log."""
        velocity = build_hotel_velocity(mock_velocity_data)
        assert len(velocity) > 0
        for v in velocity:
            assert "hotel_id" in v
            assert "updates_24h" in v
            assert "avg_change_pct" in v
            assert "direction" in v  # "up", "down", "flat"
```

Fixtures needed:

```python
@pytest.fixture
def mock_bookings():
    import pandas as pd
    return pd.DataFrame({
        "Id": [1, 2, 3, 4],
        "HotelId": [100, 100, 200, 200],
        "HotelName": ["Hotel A", "Hotel A", "Hotel B", "Hotel B"],
        "BuyPrice": [150.0, 180.0, 200.0, 250.0],
        "PushPrice": [170.0, 195.0, 220.0, 260.0],
        "IsActive": [1, 1, 1, 1],
        "IsSold": [0, 0, 0, 0],
        "DateFrom": pd.to_datetime(["2026-05-01", "2026-05-15", "2026-06-01", "2026-06-15"]),
        "DateTo": pd.to_datetime(["2026-05-02", "2026-05-16", "2026-06-02", "2026-06-16"]),
    })

@pytest.fixture
def mock_velocity_data():
    import pandas as pd
    return pd.DataFrame({
        "HotelId": [100, 100, 200],
        "updates_24h": [12, 12, 5],
        "avg_change_abs": [3.50, 3.50, 1.20],
        "avg_change_pct": [1.8, 1.8, 0.5],
        "max_change_pct": [4.2, 4.2, 1.1],
    })
```

- [ ] **Step 7.1.2: Implement position and velocity aggregation**

Add to `src/analytics/portfolio_aggregator.py`:

```python
import pandas as pd


@dataclass
class PortfolioPositions:
    """Live position data from Azure SQL trading database."""
    total_active: int = 0
    total_sold: int = 0
    total_exposure_buy: float = 0.0    # Sum of BuyPrice (cost basis)
    total_exposure_sell: float = 0.0   # Sum of PushPrice (intended sell)
    total_unrealized_pnl: float = 0.0  # Sum of (PushPrice - BuyPrice)
    hotels: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_portfolio_positions(bookings_df: pd.DataFrame) -> PortfolioPositions:
    """Aggregate active bookings into portfolio-level position summary.

    Args:
        bookings_df: DataFrame from trading_db.load_active_bookings().
            Expected columns: Id, HotelId, HotelName, BuyPrice, PushPrice, IsActive, IsSold.

    Returns:
        PortfolioPositions with per-hotel breakdown.
    """
    if bookings_df.empty:
        return PortfolioPositions()

    active = bookings_df[bookings_df.get("IsActive", pd.Series(dtype=int)) == 1].copy()
    if active.empty:
        return PortfolioPositions()

    # Per-hotel aggregation
    hotels = []
    for hotel_id, group in active.groupby("HotelId"):
        buy_total = float(group["BuyPrice"].sum())
        sell_total = float(group["PushPrice"].fillna(group["BuyPrice"]).sum())
        pnl = sell_total - buy_total
        hotels.append({
            "hotel_id": int(hotel_id),
            "hotel_name": group["HotelName"].iloc[0] if "HotelName" in group.columns else f"Hotel {hotel_id}",
            "active_count": len(group),
            "buy_exposure": round(buy_total, 2),
            "sell_exposure": round(sell_total, 2),
            "unrealized_pnl": round(pnl, 2),
            "avg_buy_price": round(buy_total / len(group), 2),
            "avg_sell_price": round(sell_total / len(group), 2),
            "margin_pct": round(pnl / buy_total * 100, 1) if buy_total > 0 else 0.0,
        })

    hotels.sort(key=lambda h: h["unrealized_pnl"], reverse=True)

    return PortfolioPositions(
        total_active=len(active),
        total_sold=len(bookings_df[bookings_df.get("IsSold", pd.Series(dtype=int)) == 1]),
        total_exposure_buy=round(sum(h["buy_exposure"] for h in hotels), 2),
        total_exposure_sell=round(sum(h["sell_exposure"] for h in hotels), 2),
        total_unrealized_pnl=round(sum(h["unrealized_pnl"] for h in hotels), 2),
        hotels=hotels,
    )


def build_hotel_velocity(velocity_df: pd.DataFrame) -> list[dict]:
    """Build price velocity indicators per hotel.

    Args:
        velocity_df: DataFrame from trading_db.load_price_update_velocity().
            Expected columns: HotelId, updates_24h, avg_change_pct, max_change_pct.

    Returns:
        List of dicts with velocity indicators per hotel.
    """
    if velocity_df.empty:
        return []

    result = []
    for _, row in velocity_df.drop_duplicates("HotelId").iterrows():
        avg_pct = float(row.get("avg_change_pct", 0))
        direction = "up" if avg_pct > 0.1 else ("down" if avg_pct < -0.1 else "flat")
        result.append({
            "hotel_id": int(row["HotelId"]),
            "updates_24h": int(row.get("updates_24h", 0)),
            "avg_change_pct": round(avg_pct, 2),
            "max_change_pct": round(float(row.get("max_change_pct", 0)), 2),
            "direction": direction,
        })

    return result
```

- [ ] **Step 7.1.3: Run tests — verify they pass**

Run: `cd /sessions/cool-lucid-cray/mnt/medici-price-prediction && python -m pytest tests/unit/test_portfolio_aggregator.py::TestBuildPortfolioPositions tests/unit/test_portfolio_aggregator.py::TestBuildHotelVelocity -v --no-header 2>&1 | tail -15`
Expected: All position and velocity tests PASS.

### Step 7.2: Add 2 live-data API endpoints

- [ ] **Step 7.2.1: Add `/macro/positions` and `/macro/velocity` endpoints**

Append to `src/api/routers/analytics_router.py`:

```python
@analytics_router.get("/macro/positions")
def macro_portfolio_positions(request: Request, _key=Depends(_optional_api_key)):
    """Live portfolio positions from Azure SQL — active bookings, PnL, exposure.

    Data source: trading_db.load_active_bookings() → portfolio_aggregator.build_portfolio_positions()
    """
    try:
        from src.data.trading_db import load_active_bookings
        from src.analytics.portfolio_aggregator import build_portfolio_positions
        bookings = load_active_bookings()
        positions = build_portfolio_positions(bookings)
        return positions.to_dict()
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("Positions unavailable: %s", exc)
        raise HTTPException(503, f"Trading database unavailable: {exc}")


@analytics_router.get("/macro/velocity")
def macro_price_velocity(request: Request, _key=Depends(_optional_api_key)):
    """Live price velocity from Azure SQL — how fast prices are changing per hotel.

    Data source: trading_db.load_price_update_velocity() → portfolio_aggregator.build_hotel_velocity()
    """
    try:
        from src.data.trading_db import load_price_update_velocity
        from src.analytics.portfolio_aggregator import build_hotel_velocity
        velocity_df = load_price_update_velocity()
        velocity = build_hotel_velocity(velocity_df)
        return {"hotels": velocity}
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("Velocity unavailable: %s", exc)
        raise HTTPException(503, f"Trading database unavailable: {exc}")
```

- [ ] **Step 7.2.2: Compile check**

Run: `python3 -m py_compile src/api/routers/analytics_router.py && echo "OK"`
Expected: OK

- [ ] **Step 7.2.3: Commit**

```bash
git add src/analytics/portfolio_aggregator.py src/api/routers/analytics_router.py tests/unit/test_portfolio_aggregator.py
git commit -m "feat: add live trading positions + price velocity endpoints from Azure SQL"
```

### Step 7.3: Integrate live data into macro_terminal.html

- [ ] **Step 7.3.1: Add Position Panel to L1 Summary Bar**

In `macro_terminal.html`, extend the summary header bar to show live position data:

```html
<!-- Position Panel — loaded async from /macro/positions -->
<div class="position-bar" id="position-bar">
  <span class="pos-item">Exposure: <span id="pos-exposure">--</span></span>
  <span class="pos-item">PnL: <span id="pos-pnl" class="val">--</span></span>
  <span class="pos-item">Active: <span id="pos-active">--</span></span>
  <span class="pos-item">Sold: <span id="pos-sold">--</span></span>
</div>
```

CSS for position bar:
```css
.position-bar{display:flex;gap:16px;padding:6px 12px;background:rgba(0,0,0,0.3);border-radius:4px;font-size:11px}
.pos-item{color:var(--muted)}.pos-item .val.up{color:var(--call)}.pos-item .val.down{color:var(--put)}
```

JS to load positions:
```javascript
async function loadPositions() {
    const data = await api('/macro/positions');
    if (!data) return;
    el('pos-exposure').textContent = '$' + data.total_exposure_sell.toLocaleString();
    const pnlEl = el('pos-pnl');
    pnlEl.textContent = (data.total_unrealized_pnl >= 0 ? '+$' : '-$') +
        Math.abs(data.total_unrealized_pnl).toLocaleString();
    pnlEl.className = 'val ' + (data.total_unrealized_pnl >= 0 ? 'up' : 'down');
    el('pos-active').textContent = data.total_active;
    el('pos-sold').textContent = data.total_sold;

    // Store hotel positions for heatmap enrichment
    STATE.positions = {};
    (data.hotels || []).forEach(h => { STATE.positions[h.hotel_id] = h; });
    renderHeatmap();  // Re-render with position data
}
```

- [ ] **Step 7.3.2: Add Velocity Indicators to Heat Map rows**

In the heatmap rendering, after hotel name, add a velocity arrow indicator:

```javascript
async function loadVelocity() {
    const data = await api('/macro/velocity');
    if (!data || !data.hotels) return;
    STATE.velocity = {};
    data.hotels.forEach(v => { STATE.velocity[v.hotel_id] = v; });
    renderHeatmap();  // Re-render with velocity arrows
}

// In renderHeatmapRow(), after hotel name:
function velocityIndicator(hotelId) {
    const v = STATE.velocity[hotelId];
    if (!v) return '';
    const arrow = v.direction === 'up' ? '▲' : v.direction === 'down' ? '▼' : '–';
    const cls = v.direction === 'up' ? 'call' : v.direction === 'down' ? 'put' : 'muted';
    const title = `${v.updates_24h} updates/24h, avg ${v.avg_change_pct}%`;
    return `<span class="velocity ${cls}" title="${title}">${arrow} ${v.updates_24h}</span>`;
}
```

- [ ] **Step 7.3.3: Add Per-Hotel PnL to L2 Drill-down Panel**

When L2 panel opens for a hotel, show position data from `STATE.positions[hotelId]`:

```javascript
function renderL2PositionPanel(hotelId) {
    const pos = STATE.positions[hotelId];
    if (!pos) return '<div class="empty">No active positions</div>';
    return `
        <div class="panel-title">Live Positions</div>
        <div class="sig-row"><span class="lbl">Active Bookings</span><span class="val">${pos.active_count}</span></div>
        <div class="sig-row"><span class="lbl">Buy Exposure</span><span class="val">$${pos.buy_exposure.toLocaleString()}</span></div>
        <div class="sig-row"><span class="lbl">Sell Exposure</span><span class="val">$${pos.sell_exposure.toLocaleString()}</span></div>
        <div class="sig-row"><span class="lbl">Unrealized PnL</span><span class="val ${pos.unrealized_pnl >= 0 ? 'up' : 'down'}">${pos.unrealized_pnl >= 0 ? '+' : ''}$${pos.unrealized_pnl.toLocaleString()}</span></div>
        <div class="sig-row"><span class="lbl">Margin</span><span class="val">${pos.margin_pct}%</span></div>
    `;
}
```

- [ ] **Step 7.3.4: Load live data on page init**

In `macro_terminal.html`, after `loadPortfolio()` completes:

```javascript
async function init() {
    await loadPortfolio();       // Signals + heatmap (from cache)
    loadPositions();             // Live positions (from Azure SQL) — async, non-blocking
    loadVelocity();              // Live velocity (from Azure SQL) — async, non-blocking
}
```

Note: Positions and velocity load in parallel, non-blocking. If Azure SQL is down, the Terminal still works with cached signals — the position bar just shows "--".

- [ ] **Step 7.3.5: Commit**

```bash
git add src/templates/macro_terminal.html
git commit -m "feat: integrate live positions + velocity into macro terminal UI"
```

---

## Task 8: Extended Live Data — Cancellations, Competitors, App Logs

**Files:**
- Modify: `src/analytics/portfolio_aggregator.py` (add cancellation risk + competitor functions)
- Modify: `src/api/routers/analytics_router.py` (add endpoints)
- Modify: `src/templates/macro_terminal.html` (add risk indicators to L2)

This task extends the live data layer with three more data sources from Azure SQL.

### Step 8.1: Cancellation Risk Per Hotel

- [ ] **Step 8.1.1: Add `build_cancellation_risk()` function**

```python
def build_cancellation_risk(cancellations_df: pd.DataFrame) -> list[dict]:
    """Compute cancellation risk indicators per hotel.

    Args:
        cancellations_df: DataFrame from trading_db.load_cancellations().
            Expected: HotelId, CancellationDate, CancellationReason, etc.

    Returns:
        List of {hotel_id, cancel_rate_30d, cancel_count_30d, top_reason}.
    """
    if cancellations_df.empty:
        return []

    result = []
    for hotel_id, group in cancellations_df.groupby("HotelId"):
        count = len(group)
        top_reason = group["CancellationReason"].mode().iloc[0] if "CancellationReason" in group.columns and not group["CancellationReason"].mode().empty else "unknown"
        result.append({
            "hotel_id": int(hotel_id),
            "cancel_count_30d": count,
            "top_reason": str(top_reason),
        })
    return result
```

- [ ] **Step 8.1.2: Add `/macro/risk` endpoint**

```python
@analytics_router.get("/macro/risk")
def macro_risk_indicators(request: Request, _key=Depends(_optional_api_key)):
    """Live risk indicators — cancellation rates, competitor pressure."""
    try:
        from src.data.trading_db import load_cancellations
        from src.analytics.portfolio_aggregator import build_cancellation_risk
        cancellations = load_cancellations(days_back=30)
        risk = build_cancellation_risk(cancellations)
        return {"cancellation_risk": risk}
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("Risk data unavailable: %s", exc)
        raise HTTPException(503, f"Trading database unavailable: {exc}")
```

### Step 8.2: Competitor Context Per Hotel (L2)

- [ ] **Step 8.2.1: Add competitor data loader for L2 drill-down**

When a hotel is selected in L2, load competitor data:

```python
@analytics_router.get("/macro/hotel/{hotel_id}/competitors")
def macro_hotel_competitors(hotel_id: int, request: Request, _key=Depends(_optional_api_key)):
    """Competitor hotels within 5km radius with pricing comparison."""
    try:
        from src.data.trading_db import load_competitor_hotels
        competitors = load_competitor_hotels(hotel_id, radius_km=5.0)
        if competitors.empty:
            return {"competitors": []}
        return {
            "competitors": competitors.head(10).to_dict("records"),
            "count": len(competitors),
        }
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("Competitor data unavailable: %s", exc)
        raise HTTPException(503, f"Trading database unavailable: {exc}")
```

### Step 8.3: App Service Prediction Logs (L3 accuracy context)

- [ ] **Step 8.3.1: Add prediction log endpoint for L3 context**

```python
@analytics_router.get("/macro/hotel/{hotel_id}/prediction-log")
def macro_hotel_prediction_log(
    hotel_id: int,
    days_back: int = Query(default=30, ge=1, le=365),
    request: Request = None,
    _key=Depends(_optional_api_key),
):
    """Recent prediction events from App Service logs for this hotel."""
    try:
        from src.data.trading_db import load_appservice_prediction_logs
        logs = load_appservice_prediction_logs(days_back=days_back)
        if logs.empty:
            return {"logs": [], "count": 0}
        hotel_logs = logs[logs.get("HotelId", logs.get("hotel_id", pd.Series())) == hotel_id]
        return {
            "logs": hotel_logs.head(50).to_dict("records"),
            "count": len(hotel_logs),
        }
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("Prediction logs unavailable: %s", exc)
        raise HTTPException(503, f"App Service logs unavailable: {exc}")
```

- [ ] **Step 8.3.2: Commit**

```bash
git add src/analytics/portfolio_aggregator.py src/api/routers/analytics_router.py
git commit -m "feat: add cancellation risk, competitor data, and prediction log endpoints"
```

### Step 8.4: Integrate into UI

- [ ] **Step 8.4.1: Add risk badges to L1 heatmap rows**

In the heatmap, show a small cancellation risk badge next to hotels with high cancel rates:

```javascript
function riskBadge(hotelId) {
    const r = STATE.risk[hotelId];
    if (!r || r.cancel_count_30d < 3) return '';
    return `<span class="risk-badge" title="${r.cancel_count_30d} cancellations (30d), top reason: ${r.top_reason}">⚠ ${r.cancel_count_30d}</span>`;
}
```

- [ ] **Step 8.4.2: Add competitor panel to L2 drill-down**

When L2 opens, async-load competitors:

```javascript
async function loadCompetitors(hotelId) {
    const data = await api(`/macro/hotel/${hotelId}/competitors`);
    if (!data || !data.competitors.length) return;
    // Render a small comparison table: Name, Stars, AvgPrice, Distance
    const html = data.competitors.map(c =>
        `<div class="src-row">
            <span class="src-name">${c.name || c.HotelName}</span>
            <span class="src-conf">${c.stars || '-'}★</span>
            <span class="src-price">${c.avg_price ? '$'+Math.round(c.avg_price) : '-'}</span>
        </div>`
    ).join('');
    el('l2-competitors').innerHTML = `<div class="panel-title">Competitors (${data.count})</div>` + html;
}
```

- [ ] **Step 8.4.3: Commit**

```bash
git add src/templates/macro_terminal.html
git commit -m "feat: add risk badges, competitor panel, and prediction logs to macro terminal"
```

---

## Available Azure SQL Data Sources Reference

For implementers: these are the `trading_db.py` functions available for querying the Azure SQL database. All are read-only. Use them to enrich the Macro Terminal with live data:

| Function | Returns | Use Case |
|----------|---------|----------|
| `load_active_bookings()` | Active bookings: BuyPrice, PushPrice, HotelId, DateFrom/To | **L1**: Portfolio exposure, PnL |
| `load_all_bookings(days_back)` | All bookings incl. sold/cancelled | **L1**: Historical PnL, sell-through rate |
| `load_opportunities(days_back)` | MED_Opportunities pipeline | **L2**: Pending deals per hotel |
| `load_hotels()` | Hotel metadata: name, city, stars | **L1**: Heatmap enrichment |
| `load_price_updates(days_back)` | Every price change event | **L1**: Velocity indicator |
| `load_price_update_velocity()` | Aggregated velocity per hotel | **L1**: Heatmap velocity arrows |
| `load_cancellations(days_back)` | Cancellation history + reasons | **L1/L2**: Risk badges |
| `load_search_results()` | Search results with net/gross | **L2**: Provider comparison |
| `load_ai_search_data()` | AI search pricing | **L2**: Market benchmark |
| `load_competitor_hotels(hotel_id)` | Competitors within radius | **L2**: Competitor panel |
| `load_salesoffice_log()` | SalesOffice action log | **L3**: Audit trail |
| `load_prebooks()` | Pre-booking data with providers | **L2**: Supply pipeline |
| `load_appservice_prediction_logs()` | Prediction events from App Service | **L3**: Accuracy context |
| `load_appservice_price_logs()` | Price observation events | **L3**: Price trail |
| `load_appservice_price_change_logs()` | Price change events | **L1**: Real-time velocity |
| `load_reservations(days_back)` | Guest reservations | **L2**: Occupancy context |
| `load_historical_prices()` | Monthly pricing from tprice | **L2**: Historical baseline |
| `load_market_benchmark(hotel_ids)` | Avg price of same-star competitors | **L2**: Market positioning |
| `run_trading_query(sql)` | Raw SQL → DataFrame | **Any**: Custom queries |

**Key principle:** All live data endpoints gracefully degrade. If Azure SQL is unavailable, the Macro Terminal still works with cached signals — live data panels just show "--" or a "Data unavailable" message. This follows the existing project pattern where collectors fail independently.

---

## Summary: What Gets Built

| Component | Type | Lines (est.) | Tests |
|-----------|------|-------------|-------|
| `portfolio_aggregator.py` | New Python | ~400 | 27 unit |
| 5+3 API endpoints | Added to analytics_router | ~180 | 8 integration |
| `macro_terminal.html` | New template | ~800 | Manual |
| `terminal.html` changes | Modified | ~80 | Manual |
| `dashboard_router.py` | 1 new route | ~5 | Covered by integration |
| `landing_page.py` | 1 link added | ~5 | N/A |

**Total new code:** ~1,470 lines
**Total new tests:** ~35 automated
**New endpoints:** 9 (7 JSON + 1 HTML + 1 existing /greeks reused)
**Data sources tapped:** Cached signals + SQLite price_snapshots + Azure SQL (bookings, velocity, cancellations, competitors, logs)
**Existing code broken:** None — L2/L3 is the current terminal, untouched except additive changes

## Architecture Decisions

1. **Single-page L1+L2, redirect to L3:** L1 and L2 live in `macro_terminal.html` as a single-page app with a slide-in panel. L3 redirects to the existing `terminal.html` with query params. This avoids duplicating the complex L3 detail rendering.

2. **Client-side filtering:** With ~500 options, all filtering happens in JS on the already-loaded data. No server roundtrips for filter changes. The `/macro/summary` endpoint returns everything in one call.

3. **Virtualized table without React:** Simple scroll-based windowing (render visible rows + buffer). For 500 rows at 32px each = 16,000px total height. DOM only holds ~50 rows at any time.

4. **Historical T chart uses existing data:** `price_snapshots` table already stores every 3h scan. The `/macro/historical-t/{detail_id}` endpoint just computes T = checkin_date - scan_date for each snapshot. Forward curve predictions come from the analysis cache.

5. **No new caching layer:** All aggregation is fast (iterate 500 signals, group by hotel) and runs on every request. If performance becomes an issue, we can add a `"macro"` cache region later — but premature optimization isn't needed for <1ms aggregation.

6. **Graceful degradation for live data:** All Azure SQL endpoints are wrapped in try/except and return 503 if the database is unavailable. The frontend loads live data async and non-blocking — the Terminal works with cached signals even without DB access. This follows the existing collector pattern where each data source fails independently.

7. **Full Azure SQL utilization:** The `trading_db.py` module exposes 20+ read-only functions covering bookings, pricing, competitors, cancellations, and logs. Tasks 7-8 tap the highest-value ones (positions, velocity, risk, competitors). The reference table above documents all available sources for future sprints.
