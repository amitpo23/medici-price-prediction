"""Seasonality decomposition and seasonal pattern analysis."""
from __future__ import annotations

import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import STL


def decompose_series(
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "price",
    period: int = 7,
    seasonal_window: int = 13,
) -> pd.DataFrame:
    """Run STL decomposition on a time series.

    Returns DataFrame with: date, observed, trend, seasonal, residual.
    Requires at least 2*period data points.
    """
    data = df[[date_col, value_col]].copy()
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(date_col).dropna(subset=[value_col])

    if len(data) < 2 * period:
        data["trend"] = np.nan
        data["seasonal"] = np.nan
        data["residual"] = np.nan
        data = data.rename(columns={value_col: "observed"})
        return data

    series = data.set_index(date_col)[value_col]
    series = series.interpolate(method="linear").bfill().ffill()

    stl = STL(series, period=period, seasonal=seasonal_window, robust=True)
    result = stl.fit()

    out = pd.DataFrame({
        "date": series.index,
        "observed": series.values,
        "trend": result.trend.values,
        "seasonal": result.seasonal.values,
        "residual": result.resid.values,
    })
    return out


def seasonal_strength_index(
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "price",
    period: int = 7,
) -> float:
    """Calculate seasonal strength index (0-1).

    Fs = max(0, 1 - Var(residual) / Var(seasonal + residual))
    Values close to 1 mean strong seasonality.
    """
    decomposed = decompose_series(df, date_col, value_col, period)

    if decomposed["seasonal"].isna().all():
        return 0.0

    seasonal = decomposed["seasonal"].values
    residual = decomposed["residual"].values

    var_resid = np.nanvar(residual)
    var_seasonal_resid = np.nanvar(seasonal + residual)

    if var_seasonal_resid == 0:
        return 0.0

    return float(max(0.0, 1.0 - var_resid / var_seasonal_resid))


def identify_peak_periods(
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "price",
    period: int = 7,
    threshold_percentile: float = 75.0,
) -> list[dict]:
    """Identify peak and off-peak periods from seasonal decomposition.

    Returns list of dicts: {start_date, end_date, period_type, avg_seasonal_effect, duration_days}.
    """
    decomposed = decompose_series(df, date_col, value_col, period)

    if decomposed["seasonal"].isna().all():
        return []

    seasonal = decomposed["seasonal"].values
    dates = decomposed["date"].values

    threshold = np.nanpercentile(seasonal, threshold_percentile)
    low_threshold = np.nanpercentile(seasonal, 100 - threshold_percentile)

    periods = []
    current_type = None
    start_idx = 0

    for i, val in enumerate(seasonal):
        if np.isnan(val):
            continue

        if val >= threshold:
            ptype = "peak"
        elif val <= low_threshold:
            ptype = "off_peak"
        else:
            ptype = "shoulder"

        if ptype != current_type:
            if current_type is not None and current_type != "shoulder":
                periods.append({
                    "start_date": str(pd.Timestamp(dates[start_idx]).date()),
                    "end_date": str(pd.Timestamp(dates[i - 1]).date()),
                    "period_type": current_type,
                    "avg_seasonal_effect": float(np.nanmean(seasonal[start_idx:i])),
                    "duration_days": i - start_idx,
                })
            current_type = ptype
            start_idx = i

    # Close last period
    if current_type is not None and current_type != "shoulder":
        periods.append({
            "start_date": str(pd.Timestamp(dates[start_idx]).date()),
            "end_date": str(pd.Timestamp(dates[-1]).date()),
            "period_type": current_type,
            "avg_seasonal_effect": float(np.nanmean(seasonal[start_idx:])),
            "duration_days": len(seasonal) - start_idx,
        })

    return periods


def city_seasonal_profile(
    df: pd.DataFrame,
    city_col: str = "city",
    date_col: str = "date",
    value_col: str = "price",
) -> pd.DataFrame:
    """Generate seasonal profiles per city.

    Returns DataFrame: city, month, avg_price, seasonal_index, period_type.
    Seasonal index = city_month_avg / city_overall_avg.
    """
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col])
    data["month"] = data[date_col].dt.month

    if city_col not in data.columns:
        data[city_col] = "all"

    # Monthly averages per city
    monthly = data.groupby([city_col, "month"])[value_col].mean().reset_index()
    monthly.columns = [city_col, "month", "avg_price"]

    # Overall averages per city
    overall = data.groupby(city_col)[value_col].mean().reset_index()
    overall.columns = [city_col, "city_avg_price"]

    monthly = monthly.merge(overall, on=city_col)
    monthly["seasonal_index"] = monthly["avg_price"] / monthly["city_avg_price"].replace(0, np.nan)
    monthly["seasonal_index"] = monthly["seasonal_index"].fillna(1.0)

    # Classify months
    monthly["period_type"] = "shoulder"
    monthly.loc[monthly["seasonal_index"] >= 1.15, "period_type"] = "peak"
    monthly.loc[monthly["seasonal_index"] <= 0.85, "period_type"] = "off_peak"

    return monthly.drop(columns=["city_avg_price"])
