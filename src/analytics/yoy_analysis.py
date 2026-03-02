"""Year-over-Year price change analysis.

Takes the unified scan history DataFrame and produces:
- T × Year pivot (avg daily % change at each T per year)
- YoY comparison table (current year vs prior years, with z-score)
- Calendar spread (price path across years for each check-in month)
"""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

# T buckets: target days-to-checkin, ±3 day window around each
T_BUCKETS = [90, 60, 45, 30, 21, 14, 10, 7, 5, 3, 1]
T_WINDOW = 3  # ±days around each T bucket

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def build_scan_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """Compute consecutive price changes and daily % change per contract.

    Contract key: (hotel_id, checkin_date, category, board)
    Adds columns: prev_price, days_gap, delta_pct, daily_pct_change, flag
    """
    if df.empty:
        return df

    df = df.copy()
    df = df.sort_values(["hotel_id", "checkin_date", "category", "board", "scan_date"])

    group_cols = ["hotel_id", "checkin_date", "category", "board"]

    df["prev_price"] = df.groupby(group_cols)["price"].shift(1)
    df["prev_scan_date"] = df.groupby(group_cols)["scan_date"].shift(1)

    # Days gap between consecutive scans
    df["days_gap"] = (df["scan_date"] - df["prev_scan_date"]).dt.days.clip(lower=1)

    # Daily % change: price change per day between scans
    df["delta_pct"] = (df["price"] - df["prev_price"]) / df["prev_price"] * 100
    df["daily_pct_change"] = df["delta_pct"] / df["days_gap"]

    # Data quality flags
    df["flag"] = "ok"

    # STALE: price unchanged for 3+ consecutive scans
    price_unchanged = df["price"] == df["prev_price"]
    stale_count = price_unchanged.groupby(
        [df["hotel_id"], df["checkin_date"], df["category"], df["board"]]
    ).transform("sum")
    df.loc[stale_count >= 3, "flag"] = "STALE"

    # VOLATILE: |daily_pct_change| > 10%
    df.loc[df["daily_pct_change"].abs() > 10, "flag"] = "VOLATILE"

    # Drop first scan per contract (no prev_price)
    df = df[df["prev_price"].notna()].copy()

    # Remove outliers: daily change > ±20% is likely a data error
    df = df[df["daily_pct_change"].abs() <= 20].copy()

    return df


def build_t_year_pivot(df: pd.DataFrame, hotel_id: int) -> dict:
    """Build the T × Year pivot showing avg daily % change.

    Returns:
        {
            "years": [2022, 2023, 2024, 2025],
            "rows": [
                {"T": 60, "label": "60d", "years": {2024: {"avg": -0.05, "n": 42}, ...}},
                ...
            ]
        }
    """
    sub = df[df["hotel_id"] == hotel_id].copy()
    if sub.empty:
        return {"years": [], "rows": []}

    years = sorted(sub["year"].unique().tolist())
    rows = []

    for T in T_BUCKETS:
        # ±T_WINDOW day window around each T bucket
        window = sub[
            (sub["T_days"] >= T - T_WINDOW) & (sub["T_days"] <= T + T_WINDOW)
            & (sub["flag"] == "ok")
        ]

        year_data: dict[int, dict] = {}
        for yr in years:
            yr_data = window[window["year"] == yr]["daily_pct_change"]
            n = len(yr_data)
            if n < 2:
                year_data[yr] = None
            else:
                year_data[yr] = {"avg": round(yr_data.mean(), 4), "n": n}

        # Delta vs last year
        delta_vs_ly = None
        current_yr = max(years)
        prev_yr = current_yr - 1
        if year_data.get(current_yr) and year_data.get(prev_yr):
            delta_vs_ly = round(
                year_data[current_yr]["avg"] - year_data[prev_yr]["avg"], 4
            )

        rows.append({
            "T": T,
            "label": f"{T}d",
            "years": year_data,
            "delta_vs_ly": delta_vs_ly,
        })

    return {"years": years, "rows": rows}


def build_yoy_comparison(df: pd.DataFrame, hotel_id: int) -> list[dict]:
    """Build YoY comparison: current year vs prior years at same T and check-in month.

    Returns list of rows with: category, checkin_month, T_bucket,
    current avg_price, last_year avg_price, yoy_pct, zscore, flag.
    """
    sub = df[df["hotel_id"] == hotel_id].copy()
    if sub.empty:
        return []

    current_year = sub["year"].max()
    prior_years = sorted([y for y in sub["year"].unique() if y < current_year])

    if not prior_years:
        return []

    sub["checkin_month"] = sub["checkin_date"].dt.month

    results = []
    categories = sub["category"].unique()

    for cat in categories:
        cat_df = sub[sub["category"] == cat]
        for T in T_BUCKETS:
            window = cat_df[
                (cat_df["T_days"] >= T - T_WINDOW) & (cat_df["T_days"] <= T + T_WINDOW)
            ]
            for month in range(1, 13):
                month_window = window[window["checkin_month"] == month]
                if month_window.empty:
                    continue

                current = month_window[month_window["year"] == current_year]
                if current.empty:
                    continue

                last_yr = prior_years[-1]
                last_year_data = month_window[month_window["year"] == last_yr]

                current_avg = current["price"].mean()
                last_avg = last_year_data["price"].mean() if not last_year_data.empty else None

                # Historical mean and std across all prior years
                hist = month_window[month_window["year"].isin(prior_years)]["price"]
                hist_mean = hist.mean() if len(hist) >= 3 else None
                hist_std = hist.std() if len(hist) >= 3 else None

                yoy_pct = None
                if last_avg and last_avg > 0:
                    yoy_pct = round((current_avg - last_avg) / last_avg * 100, 2)

                zscore = None
                if hist_mean and hist_std and hist_std > 0:
                    zscore = round((current_avg - hist_mean) / hist_std, 2)

                alert = "normal"
                if zscore is not None:
                    if abs(zscore) > 2.5:
                        alert = "warning"
                    elif abs(zscore) > 1.5:
                        alert = "watch"

                results.append({
                    "category": cat,
                    "checkin_month": month,
                    "checkin_month_name": MONTH_NAMES[month],
                    "T_bucket": T,
                    "current_year": current_year,
                    "current_avg_price": round(current_avg, 2),
                    "current_n": len(current),
                    "last_year": last_yr,
                    "last_year_avg_price": round(last_avg, 2) if last_avg else None,
                    "last_year_n": len(last_year_data),
                    "hist_mean": round(hist_mean, 2) if hist_mean else None,
                    "yoy_pct": yoy_pct,
                    "zscore": zscore,
                    "alert": alert,
                })

    return results


def build_calendar_spread(df: pd.DataFrame, hotel_id: int) -> dict:
    """Build calendar spread: for each check-in month × T, show avg price per year.

    Returns:
        {
            "years": [2022, 2023, 2024, 2025],
            "months": {
                "Mar": {
                    "rows": [
                        {"T": 60, "years": {2023: 210.5, 2024: 228.3, 2025: 252.1}},
                        ...
                    ]
                }
            }
        }
    """
    sub = df[df["hotel_id"] == hotel_id].copy()
    if sub.empty:
        return {"years": [], "months": {}}

    years = sorted(sub["year"].unique().tolist())
    sub["checkin_month"] = sub["checkin_date"].dt.month

    result_months: dict[str, dict] = {}

    for month in range(1, 13):
        month_df = sub[sub["checkin_month"] == month]
        if month_df.empty:
            continue

        month_name = MONTH_NAMES[month]
        rows = []

        for T in T_BUCKETS:
            window = month_df[
                (month_df["T_days"] >= T - T_WINDOW) & (month_df["T_days"] <= T + T_WINDOW)
            ]
            if window.empty:
                continue

            yr_prices: dict[int, float | None] = {}
            for yr in years:
                yr_data = window[window["year"] == yr]["price"]
                yr_prices[yr] = round(yr_data.mean(), 2) if len(yr_data) >= 2 else None

            # Only include rows where at least 2 years have data
            if sum(1 for v in yr_prices.values() if v is not None) >= 2:
                rows.append({"T": T, "label": f"{T}d", "years": yr_prices})

        if rows:
            result_months[month_name] = {"month_num": month, "rows": rows}

    return {"years": years, "months": result_months}


def _safe_color(value: float | None, scale: float = 0.5) -> str:
    """Return a CSS background color for a daily % change value.

    Negative → green (price falling = good for late buyer)
    Positive → red (price rising)
    None/zero → transparent
    """
    if value is None or not math.isfinite(value):
        return "transparent"
    clamped = max(-scale, min(scale, value))
    ratio = clamped / scale  # -1 to +1
    if ratio < 0:
        # Green: more negative = more green
        intensity = int(abs(ratio) * 120)
        return f"rgba(34,197,94,{abs(ratio) * 0.6:.2f})"
    if ratio > 0:
        # Red: more positive = more red
        return f"rgba(239,68,68,{ratio * 0.6:.2f})"
    return "transparent"


def _safe_price_color(value: float | None, ref: float | None) -> str:
    """Color a price cell relative to a reference price."""
    if value is None or ref is None:
        return "transparent"
    pct = (value - ref) / ref
    if pct > 0.05:
        return f"rgba(239,68,68,{min(pct * 3, 0.5):.2f})"
    if pct < -0.05:
        return f"rgba(34,197,94,{min(abs(pct) * 3, 0.5):.2f})"
    return "transparent"
