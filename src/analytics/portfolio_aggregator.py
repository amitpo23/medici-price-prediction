"""Portfolio-level aggregation for the Macro Terminal.

Reads cached signals from options_engine and aggregates them into:
  - PortfolioSummary: top-level header bar data
  - HotelHeatmapRow: one row per hotel in the heat map grid
  - HotelDrilldown: per-hotel detail with T-distribution and source agreement
  - Next-scan risk scoring (from next-scan-drop skill logic)
  - Drop history aggregation (from price_snapshots)

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
    ("0-14", 0, 14),
    ("15-30", 15, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("91+", 91, 9999),
]

CONFIDENCE_SCORES = {"High": 3, "Med": 2, "Low": 1}


# ── Dataclasses ──────────────────────────────────────────────────────

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
    """Single cell in the heat map grid (hotel x T-bucket)."""
    bucket: str
    count: int = 0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0
    dominant_signal: str = "NONE"
    avg_confidence_score: float = 0.0

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
    agreement_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


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
class DropHistorySummary:
    """Price drop history for a hotel (L2)."""
    total_drops_7d: int = 0
    avg_drop_pct: float = 0.0
    max_drop_pct: float = 0.0
    rooms_with_drops: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NextScanRisk:
    """Next-scan drop risk for a single option."""
    score: int = 0
    label: str = "NEUTRAL"  # STRONG_PUT / PUT / WATCH / NEUTRAL

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
    drop_history: DropHistorySummary = field(default_factory=DropHistorySummary)
    options: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Helper Functions ─────────────────────────────────────────────────

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
    return "91+"


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


def _dominant_signal(calls: int, puts: int, neutrals: int) -> str:
    """Return the dominant signal from counts."""
    if calls >= puts and calls >= neutrals and calls > 0:
        return "CALL"
    if puts >= calls and puts >= neutrals and puts > 0:
        return "PUT"
    return "NONE"


# ── Next-Scan Risk Scoring ───────────────────────────────────────────

def compute_next_scan_risk(sig: dict) -> NextScanRisk:
    """Score next-scan drop risk using the next-scan-drop skill logic.

    Scoring (out of 100):
      - velocity_24h < -3%:     +30
      - acceleration < 0:       +15
      - momentum DOWN:          +15
      - regime VOLATILE/STALE:  +10
      - P_down > 60%:           +20
      - category Suite/Deluxe:  +10

    Labels:
      > 70 = STRONG_PUT, > 50 = PUT, > 30 = WATCH, else NEUTRAL
    """
    score = 0

    velocity = sig.get("velocity_24h", 0) or 0
    if velocity < -3.0:
        score += 30
    elif velocity < -1.0:
        score += 15

    accel = sig.get("acceleration", 0) or 0
    if accel < 0:
        score += 15

    momentum = (sig.get("momentum_signal") or "").upper()
    if momentum in ("DOWN", "ACCELERATING_DOWN", "DECELERATING_DOWN"):
        score += 15

    regime = (sig.get("regime") or "").upper()
    if regime in ("VOLATILE", "STALE"):
        score += 10

    p_down = sig.get("P_down", 0) or 0
    if p_down > 60:
        score += 20
    elif p_down > 40:
        score += 10

    category = (sig.get("category") or "").lower()
    if category in ("suite", "deluxe"):
        score += 10

    if score > 70:
        label = "STRONG_PUT"
    elif score > 50:
        label = "PUT"
    elif score > 30:
        label = "WATCH"
    else:
        label = "NEUTRAL"

    return NextScanRisk(score=score, label=label)


# ── Builder Functions ────────────────────────────────────────────────

def build_portfolio_summary(
    signals: list[dict],
    greeks: dict[str, Any] | None = None,
) -> PortfolioSummary:
    """Build L1 summary header bar from cached signals."""
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
    """Build L1 heat map grid — one row per hotel, cells per T-bucket."""
    if not signals:
        return []

    by_hotel: dict[int, list[dict]] = defaultdict(list)
    hotel_names: dict[int, str] = {}
    for sig in signals:
        hid = sig.get("hotel_id", 0)
        by_hotel[hid].append(sig)
        hotel_names[hid] = sig.get("hotel_name", f"Hotel {hid}")

    rows: list[HotelHeatmapRow] = []
    for hid, hotel_signals in by_hotel.items():
        bucket_map: dict[str, list[dict]] = defaultdict(list)
        for sig in hotel_signals:
            bucket_map[_t_bucket(sig.get("T", 0))].append(sig)

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

            avg_conf = conf_sum / len(sigs_in_bucket) if sigs_in_bucket else 0.0

            cells.append(TBucketCell(
                bucket=label,
                count=len(sigs_in_bucket),
                calls=c, puts=p, neutrals=n,
                dominant_signal=_dominant_signal(c, p, n),
                avg_confidence_score=avg_conf,
            ))

        total_c = sum(cell.calls for cell in cells)
        total_p = sum(cell.puts for cell in cells)
        total_n = sum(cell.neutrals for cell in cells)

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
            dominant_signal=_dominant_signal(total_c, total_p, total_n),
            avg_price=round(avg_price, 2),
            buckets=cells,
            agreement_score=agree,
        ))

    rows.sort(key=lambda r: r.hotel_name)
    return rows


def build_hotel_drilldown(
    signals: list[dict],
    hotel_id: int,
    predictions: dict[str, dict] | None = None,
    drop_history: DropHistorySummary | None = None,
) -> HotelDrilldown | None:
    """Build L2 hotel drill-down: T-distribution + source agreement + options list."""
    hotel_signals = [s for s in signals if s.get("hotel_id") == hotel_id]
    if not hotel_signals:
        return None

    hotel_name = hotel_signals[0].get("hotel_name", f"Hotel {hotel_id}")

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

    # Source agreement
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

    # Options list with next-scan risk
    options: list[dict] = []
    for sig in hotel_signals:
        risk = compute_next_scan_risk(sig)
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
            "next_scan_risk": risk.to_dict(),
        }
        did = str(sig.get("detail_id", ""))
        pred = predictions.get(did) if predictions else None
        if pred:
            row["predicted_price"] = pred.get("predicted_checkin_price")
            row["min_price"] = pred.get("min_price")
            row["max_price"] = pred.get("max_price")
        options.append(row)

    signal_order = {"PUT": 0, "CALL": 1, "NONE": 2}
    options.sort(key=lambda o: (signal_order.get(o.get("signal", "NONE"), 2), o.get("T", 0)))

    return HotelDrilldown(
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        total_options=len(hotel_signals),
        calls=calls, puts=puts, neutrals=neutrals,
        t_distribution=t_dist,
        source_agreement=source_rows,
        drop_history=drop_history or DropHistorySummary(),
        options=options,
    )


def filter_signals_by_source(
    signals: list[dict],
    predictions: dict[str, dict],
    source: str,
) -> list[dict]:
    """Filter signals to show only what a specific source would recommend.

    Re-derives signal direction from per-source price vs current price.
    Valid sources: 'forward_curve', 'historical', 'ml', 'ensemble'.
    """
    if source == "ensemble":
        return signals

    price_key_map = {
        "forward_curve": "fc_price",
        "historical": "hist_price",
        "ml": "ml_price",
    }
    price_key = price_key_map.get(source)
    if not price_key:
        return signals

    filtered = []
    for sig in signals:
        did = str(sig.get("detail_id", ""))
        pred = predictions.get(did)
        if not pred:
            continue
        src_price = pred.get(price_key)
        current = pred.get("current_price") or sig.get("S_t")
        if src_price is None or not current:
            continue

        # Derive signal from source price vs current
        if src_price > current * 1.02:
            derived_signal = "CALL"
        elif src_price < current * 0.98:
            derived_signal = "PUT"
        else:
            derived_signal = "NONE"

        row = dict(sig)
        row["recommendation"] = derived_signal
        row["source_filter"] = source
        row["source_price"] = src_price
        filtered.append(row)

    return filtered


def compute_drop_history(
    snapshots_df,
    hotel_id: int,
    days: int = 7,
    drop_threshold_pct: float = -1.0,
) -> DropHistorySummary:
    """Compute price drop history for a hotel from price_snapshots.

    Args:
        snapshots_df: DataFrame with columns [hotel_id, detail_id, snapshot_ts, room_price]
        hotel_id: Hotel to analyze
        days: Lookback window in days
        drop_threshold_pct: Minimum % change to count as a drop (negative number)
    """
    import pandas as pd

    if snapshots_df is None or snapshots_df.empty:
        return DropHistorySummary()

    hotel_df = snapshots_df[snapshots_df["hotel_id"] == hotel_id].copy()
    if hotel_df.empty:
        return DropHistorySummary()

    hotel_df["snapshot_ts"] = pd.to_datetime(hotel_df["snapshot_ts"])
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    hotel_df = hotel_df[hotel_df["snapshot_ts"] >= cutoff]

    if hotel_df.empty:
        return DropHistorySummary()

    # Compute per-detail price changes between consecutive scans
    hotel_df = hotel_df.sort_values(["detail_id", "snapshot_ts"])
    hotel_df["prev_price"] = hotel_df.groupby("detail_id")["room_price"].shift(1)
    hotel_df["pct_change"] = (
        (hotel_df["room_price"] - hotel_df["prev_price"]) / hotel_df["prev_price"] * 100
    )
    hotel_df = hotel_df.dropna(subset=["pct_change"])

    drops = hotel_df[hotel_df["pct_change"] <= drop_threshold_pct]

    if drops.empty:
        return DropHistorySummary()

    return DropHistorySummary(
        total_drops_7d=len(drops),
        avg_drop_pct=round(float(drops["pct_change"].mean()), 2),
        max_drop_pct=round(float(drops["pct_change"].min()), 2),
        rooms_with_drops=int(drops["detail_id"].nunique()),
    )
