"""Term structure engine — compares price-path dynamics by year (2023/2024/2025).

Produces 6 datasets per hotel × category × board combination:
  1. avg_delta    — Avg daily % change by T
  2. cumulative   — Normalized cumulative price path (base=100 at T=90)
  3. volatility   — Realized daily volatility (std dev of daily_pct_change) by T
  4. pct_up       — % of days with positive daily change by T
  5. min_rel_hist — Histogram of min-relative-to-expiry per contract by year
  6. heatmap      — T × year matrix of avg_delta (same data, pivot format)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Reuse same T-bucket definition as yoy_analysis.py
T_BUCKETS = [90, 60, 45, 30, 21, 14, 10, 7, 5, 3, 1]
T_WINDOW = 3

YEARS = ["2023", "2024", "2025"]

# Chart 5 histogram buckets (min_rel ranges)
BUCKET_LABELS = ["<-20%", "-20 to -10%", "-10 to -5%", "-5 to 0%", "0 to +5%", ">+5%"]
BUCKET_EDGES = [-999, -20, -10, -5, 0, 5, 999]

YEAR_COLORS = {"2023": "#6366f1", "2024": "#06b6d4", "2025": "#22c55e"}


def build_all_term_structures(ts: pd.DataFrame, hotel_ids: list[int]) -> dict:
    """Build term-structure chart data for all hotel × category × board combos.

    Args:
        ts: Output of build_scan_timeseries() — must have daily_pct_change, flag, year.
        hotel_ids: List of hotel IDs to process.

    Returns:
        {hotel_id: {"combos": [...], "data": {"category|board": {...}}}}
    """
    result: dict = {}

    if ts.empty or "hotel_id" not in ts.columns:
        return result

    for hid in hotel_ids:
        sub = ts[ts["hotel_id"] == hid]
        if sub.empty:
            continue

        combos_df = sub[["category", "board"]].drop_duplicates().dropna()
        combos: list[str] = []
        data: dict[str, dict] = {}

        for _, row in combos_df.iterrows():
            cat, board = row["category"], row["board"]
            key = f"{cat} | {board}"
            filtered = sub[(sub["category"] == cat) & (sub["board"] == board)]
            combo_data = _compute_one(filtered)
            if combo_data:
                combos.append(key)
                data[key] = combo_data

        if combos:
            result[int(hid)] = {"combos": sorted(combos), "data": data}
            logger.info("Term structure: hotel %s → %d combos", hid, len(combos))

    return result


def _compute_one(sub: pd.DataFrame) -> dict | None:
    """Compute all 6 chart datasets for a single hotel × category × board slice."""
    if sub.empty:
        return None

    # Clean: ok-flag only, years 2023-2025, valid daily_pct_change
    clean = sub[
        (sub["flag"] == "ok")
        & (sub["year"].astype(str).isin(YEARS))
        & sub["daily_pct_change"].notna()
    ].copy()

    if clean.empty:
        return None

    clean["year_str"] = clean["year"].astype(str)

    # ── Charts 1, 3, 4: group by (year_str, T-bucket) ─────────────────────
    avg_delta: dict[str, list] = {yr: [] for yr in YEARS}
    volatility: dict[str, list] = {yr: [] for yr in YEARS}
    pct_up: dict[str, list]     = {yr: [] for yr in YEARS}
    counts: dict[str, list]     = {yr: [] for yr in YEARS}

    for T in T_BUCKETS:
        window = clean[
            (clean["T_days"] >= T - T_WINDOW) & (clean["T_days"] <= T + T_WINDOW)
        ]
        for yr in YEARS:
            vals = window[window["year_str"] == yr]["daily_pct_change"]
            n = len(vals)
            if n >= 3:
                avg_delta[yr].append(round(float(vals.mean()), 4))
                volatility[yr].append(round(float(vals.std()), 4))
                pct_up[yr].append(round(float((vals > 0).mean() * 100), 1))
                counts[yr].append(int(n))
            else:
                avg_delta[yr].append(None)
                volatility[yr].append(None)
                pct_up[yr].append(None)
                counts[yr].append(int(n))

    # ── Chart 2: cumulative normalized path ────────────────────────────────
    # T_BUCKETS is [90, 60, 45, …, 1] = descending T = chronological forward
    cumulative: dict[str, list] = {}
    for yr in YEARS:
        deltas = avg_delta[yr]  # indexed same order as T_BUCKETS (high T → low T)
        path: list[float] = [100.0]
        for d in deltas:
            prev = path[-1]
            path.append(round(prev * (1 + (d if d is not None else 0) / 100), 4))
        cumulative[yr] = path[1:]  # drop the seed 100 to match t_values length

    # ── Chart 5: min_rel histogram ─────────────────────────────────────────
    min_rel_hist = _compute_min_rel_hist(sub)

    # ── Chart 6: heatmap matrix ────────────────────────────────────────────
    heatmap = {
        "t_values": T_BUCKETS,
        "years": YEARS,
        "matrix": {yr: avg_delta[yr] for yr in YEARS},
    }

    return {
        "t_values":   T_BUCKETS,
        "years":      YEARS,
        "avg_delta":  avg_delta,
        "cumulative": cumulative,
        "volatility": volatility,
        "pct_up":     pct_up,
        "counts":     counts,
        "min_rel_hist": min_rel_hist,
        "heatmap":    heatmap,
    }


def _compute_min_rel_hist(sub: pd.DataFrame) -> dict:
    """Compute per-contract min-relative-to-expiry and bucket into histogram by year."""
    CONTRACT_KEY = ["hotel_id", "checkin_date", "category", "board", "year"]

    df = sub.copy()
    df["year_str"] = df["year"].astype(str)

    # Settlement price: price at min(T_days) per contract
    settlement = (
        df.sort_values("T_days")
        .groupby(CONTRACT_KEY, as_index=False)
        .first()[CONTRACT_KEY + ["price"]]
        .rename(columns={"price": "S_exp"})
    )

    merged = df.merge(settlement, on=CONTRACT_KEY, how="inner")
    merged = merged[merged["S_exp"] > 0]

    if merged.empty:
        return {"buckets": BUCKET_LABELS, **{yr: [0] * len(BUCKET_LABELS) for yr in YEARS}}

    merged["rel"] = (merged["price"] - merged["S_exp"]) / merged["S_exp"] * 100.0

    # Min rel per contract
    min_per = (
        merged.groupby(CONTRACT_KEY + ["year_str"])["rel"]
        .min()
        .reset_index()
        .rename(columns={"rel": "min_rel"})
    )

    hist: dict[str, list[int]] = {}
    for yr in YEARS:
        yr_vals = min_per[min_per["year_str"] == yr]["min_rel"].values
        bins = np.histogram(yr_vals, bins=BUCKET_EDGES)[0].tolist() if len(yr_vals) > 0 else [0] * len(BUCKET_LABELS)
        hist[yr] = [int(x) for x in bins]

    return {"buckets": BUCKET_LABELS, **hist}
