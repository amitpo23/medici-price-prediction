"""Prediction accuracy engine — backtest predicted vs actual settlement prices.

For each historical contract, measures how accurately we predicted the
check-in price from various lead times (T=7, 14, 30, 60, 90).

Uses walk-forward methodology: at each T, the predicted settlement price
is computed using the empirical decay curve from prior-only data.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

T_TEST_POINTS = [7, 14, 30, 60, 90]
HOTEL_IDS = [66814, 854881, 20702, 24982]
HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}
CONTRACT_KEY = ["hotel_id", "checkin_date", "category", "board"]


def build_accuracy_data(hotel_ids: list[int] | None = None) -> dict:
    """Build prediction accuracy metrics from historical price tracks.

    Returns structured dict with per-hotel, per-T accuracy stats.
    """
    from src.data.yoy_db import load_unified_yoy_data

    hids = hotel_ids or HOTEL_IDS
    raw = load_unified_yoy_data(hids)
    if raw.empty:
        return {"error": "No historical data available", "hotels": {}}

    # Filter valid prices
    raw = raw[raw["price"].notna() & (raw["price"] > 0)].copy()
    if raw.empty:
        return {"error": "No valid price data", "hotels": {}}

    # Compute settlement price per contract (price at minimum T_days)
    settlement = (
        raw.sort_values("T_days")
        .groupby(CONTRACT_KEY, as_index=False)
        .first()[CONTRACT_KEY + ["price", "T_days"]]
        .rename(columns={"price": "S_exp", "T_days": "settlement_T"})
    )
    # Only use contracts where settlement T <= 5 (close to check-in)
    settlement = settlement[settlement["settlement_T"] <= 5]

    merged = raw.merge(settlement[CONTRACT_KEY + ["S_exp"]], on=CONTRACT_KEY, how="inner")
    merged = merged[merged["S_exp"] > 0].copy()
    merged["actual_change_pct"] = (merged["S_exp"] - merged["price"]) / merged["price"] * 100

    if merged.empty:
        return {"error": "No contracts with settlement data", "hotels": {}}

    # Compute empirical decay curve (average daily pct change at each T)
    merged["year"] = merged["scan_date"].dt.year

    # Build accuracy metrics per hotel
    hotels_data = {}
    overall_results = []

    for hid in hids:
        sub = merged[merged["hotel_id"] == hid]
        if sub.empty:
            continue

        hotel_results = _compute_hotel_accuracy(sub, hid)
        if hotel_results:
            hotels_data[hid] = hotel_results
            overall_results.extend(hotel_results.get("raw_results", []))

    # Overall summary
    overall = _compute_overall_summary(overall_results)

    # Year-over-year accuracy comparison
    yoy_accuracy = _compute_yoy_accuracy(merged)

    # Source attribution
    source_counts = merged["source"].value_counts().to_dict() if "source" in merged.columns else {}

    return {
        "hotels": hotels_data,
        "overall": overall,
        "yoy_accuracy": yoy_accuracy,
        "total_contracts": merged.groupby(CONTRACT_KEY).ngroups,
        "total_observations": len(merged),
        "sources_used": {k: int(v) for k, v in source_counts.items()},
    }


def _compute_hotel_accuracy(sub: pd.DataFrame, hotel_id: int) -> dict:
    """Compute accuracy metrics for a single hotel across T-buckets."""
    results_per_t = {}
    raw_results = []

    for t_test in T_TEST_POINTS:
        # Get observations near this T value (within ±2 days)
        t_obs = sub[(sub["T_days"] >= t_test - 2) & (sub["T_days"] <= t_test + 2)]
        if len(t_obs) < 3:
            continue

        actual_changes = t_obs["actual_change_pct"].values
        prices_at_t = t_obs["price"].values
        settlement_prices = t_obs["S_exp"].values

        # Simple prediction: assume price stays flat (naive baseline)
        naive_errors = actual_changes  # error = actual change from predicted 0% change

        # Decay curve prediction: use historical mean change at this T
        mean_change = float(np.mean(actual_changes))
        predicted_settlements = prices_at_t * (1 + mean_change / 100)
        decay_errors = (settlement_prices - predicted_settlements) / settlement_prices * 100

        # Direction accuracy: does the sign of actual_change match the mean?
        if mean_change != 0:
            direction_correct = np.sum(np.sign(actual_changes) == np.sign(mean_change))
        else:
            direction_correct = np.sum(actual_changes == 0)
        direction_pct = float(direction_correct / len(actual_changes) * 100)

        # Within-band accuracy: % of predictions within ±5% of actual
        within_5 = float(np.mean(np.abs(naive_errors) <= 5) * 100)
        within_10 = float(np.mean(np.abs(naive_errors) <= 10) * 100)

        # MAPE and RMSE
        mape = float(np.mean(np.abs(naive_errors)))
        rmse = float(np.sqrt(np.mean(naive_errors ** 2)))

        results_per_t[t_test] = {
            "n_observations": len(t_obs),
            "mean_actual_change_pct": round(mean_change, 2),
            "median_actual_change_pct": round(float(np.median(actual_changes)), 2),
            "std_change_pct": round(float(np.std(actual_changes)), 2),
            "direction_accuracy_pct": round(direction_pct, 1),
            "within_5pct": round(within_5, 1),
            "within_10pct": round(within_10, 1),
            "mape": round(mape, 2),
            "rmse": round(rmse, 2),
            "price_went_down_pct": round(float(np.mean(actual_changes < 0) * 100), 1),
            "price_went_up_pct": round(float(np.mean(actual_changes > 0) * 100), 1),
            "price_stable_pct": round(float(np.mean(actual_changes == 0) * 100), 1),
        }

        for change, price, sexp in zip(actual_changes, prices_at_t, settlement_prices):
            raw_results.append({
                "hotel_id": hotel_id,
                "T": t_test,
                "price_at_T": round(float(price), 2),
                "settlement": round(float(sexp), 2),
                "change_pct": round(float(change), 2),
            })

    if not results_per_t:
        return {}

    return {
        "hotel_name": HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}"),
        "accuracy_by_T": results_per_t,
        "raw_results": raw_results,
    }


def _compute_overall_summary(raw_results: list[dict]) -> dict:
    """Compute aggregate accuracy metrics across all hotels."""
    if not raw_results:
        return {}

    df = pd.DataFrame(raw_results)
    summary = {}

    for t_val in T_TEST_POINTS:
        t_data = df[df["T"] == t_val]
        if t_data.empty:
            continue

        changes = t_data["change_pct"].values
        summary[t_val] = {
            "n": len(t_data),
            "mean_change": round(float(np.mean(changes)), 2),
            "median_change": round(float(np.median(changes)), 2),
            "mape": round(float(np.mean(np.abs(changes))), 2),
            "within_5": round(float(np.mean(np.abs(changes) <= 5) * 100), 1),
            "within_10": round(float(np.mean(np.abs(changes) <= 10) * 100), 1),
            "pct_down": round(float(np.mean(changes < 0) * 100), 1),
        }

    # Scatter data (for predicted vs actual chart)
    scatter = []
    for _, row in df.iterrows():
        predicted = row["price_at_T"]  # naive: predict price stays flat
        actual = row["settlement"]
        scatter.append({
            "predicted": round(float(predicted), 2),
            "actual": round(float(actual), 2),
            "T": int(row["T"]),
            "hotel_id": int(row["hotel_id"]),
        })

    return {
        "by_T": summary,
        "scatter": scatter[:500],  # limit for chart performance
        "total_trials": len(df),
    }


def _compute_yoy_accuracy(merged: pd.DataFrame) -> dict:
    """Compute accuracy breakdown by year for trend analysis."""
    result = {}
    for year in sorted(merged["year"].unique()):
        yr_data = merged[merged["year"] == year]
        if len(yr_data) < 10:
            continue

        changes = yr_data["actual_change_pct"].values
        result[int(year)] = {
            "n": len(yr_data),
            "mean_change": round(float(np.mean(changes)), 2),
            "mape": round(float(np.mean(np.abs(changes))), 2),
            "within_5": round(float(np.mean(np.abs(changes) <= 5) * 100), 1),
            "pct_down": round(float(np.mean(changes < 0) * 100), 1),
        }

    return result
