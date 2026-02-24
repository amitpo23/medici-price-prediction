"""Revenue metrics: RevPAR, ADR, and related KPIs."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd
import numpy as np


@dataclass
class RevenueMetrics:
    """Container for computed revenue KPIs."""

    adr: float
    occupancy_rate: float
    revpar: float
    total_revenue: Optional[float] = None
    rooms_available: Optional[int] = None
    rooms_sold: Optional[int] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_revpar(adr: float, occupancy_rate: float) -> float:
    """RevPAR = ADR * Occupancy Rate."""
    return adr * occupancy_rate


def calculate_adr(total_revenue: float, rooms_sold: int) -> float:
    """ADR = Total Revenue / Rooms Sold."""
    if rooms_sold <= 0:
        return 0.0
    return total_revenue / rooms_sold


def compute_revenue_metrics(
    df: pd.DataFrame,
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
    date_col: str = "date",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Compute RevPAR, ADR, and related metrics.

    Args:
        group_cols: Optional grouping (e.g., ['city', 'star_rating']).

    Returns DataFrame with: group columns + adr, avg_occupancy, revpar, revenue_index.
    """
    data = df.copy()
    has_occupancy = occupancy_col in data.columns

    if group_cols:
        groups = data.groupby(group_cols)
    else:
        data["_all"] = "all"
        groups = data.groupby("_all")

    records = []
    overall_revpar_values = []

    for name, group in groups:
        adr = group[price_col].mean()
        occ = group[occupancy_col].mean() if has_occupancy else np.nan
        revpar = adr * occ if has_occupancy and not np.isnan(occ) else np.nan

        rec = {
            "adr": round(adr, 2),
            "avg_occupancy": round(occ, 3) if not np.isnan(occ) else None,
            "revpar": round(revpar, 2) if not np.isnan(revpar) else None,
            "count": len(group),
        }

        if group_cols:
            if isinstance(name, tuple):
                for col, val in zip(group_cols, name):
                    rec[col] = val
            else:
                rec[group_cols[0]] = name

        records.append(rec)
        if not np.isnan(revpar):
            overall_revpar_values.append(revpar)

    result = pd.DataFrame(records)

    # Revenue index: revpar / overall mean revpar
    if overall_revpar_values:
        mean_revpar = np.mean(overall_revpar_values)
        if mean_revpar > 0:
            result["revenue_index"] = result["revpar"].apply(
                lambda x: round(x / mean_revpar, 3) if x is not None else None
            )

    if "_all" in result.columns:
        result = result.drop(columns=["_all"])

    return result


def revenue_time_series(
    df: pd.DataFrame,
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
    date_col: str = "date",
    freq: str = "W",
) -> pd.DataFrame:
    """Aggregate revenue metrics into a time series at given frequency.

    Args:
        freq: 'D' (daily), 'W' (weekly), 'M' (monthly), 'Q' (quarterly).

    Returns DataFrame indexed by period: adr, avg_occupancy, revpar.
    """
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.set_index(date_col).sort_index()

    has_occupancy = occupancy_col in data.columns

    resampled = data.resample(freq)
    result = pd.DataFrame({
        "adr": resampled[price_col].mean(),
    })

    if has_occupancy:
        result["avg_occupancy"] = resampled[occupancy_col].mean()
        result["revpar"] = result["adr"] * result["avg_occupancy"]
    else:
        result["avg_occupancy"] = np.nan
        result["revpar"] = np.nan

    result = result.dropna(subset=["adr"]).round(2)
    result.index.name = "period"
    return result.reset_index()


def forecast_revpar(
    price_forecast_df: pd.DataFrame,
    occupancy_forecast_df: pd.DataFrame | None = None,
    date_col: str = "date",
) -> pd.DataFrame:
    """Combine price and occupancy forecasts to produce RevPAR forecast.

    Returns DataFrame with: date, predicted_price, predicted_occupancy,
    predicted_revpar. Includes bounds if available in inputs.
    """
    result = price_forecast_df[[date_col, "predicted_price"]].copy()

    if occupancy_forecast_df is not None and "predicted_occupancy" in occupancy_forecast_df.columns:
        occ = occupancy_forecast_df[[date_col, "predicted_occupancy"]].copy()
        result = result.merge(occ, on=date_col, how="left")
        result["predicted_occupancy"] = result["predicted_occupancy"].fillna(0.65)
    else:
        result["predicted_occupancy"] = 0.65  # reasonable Israeli hotel default

    result["predicted_revpar"] = (
        result["predicted_price"] * result["predicted_occupancy"]
    ).round(2)

    # Propagate confidence intervals if present
    for level in [80, 95]:
        lower_p = f"lower_{level}"
        upper_p = f"upper_{level}"
        lower_o = f"occupancy_lower_{level}"
        upper_o = f"occupancy_upper_{level}"

        if lower_p in price_forecast_df.columns:
            result[lower_p] = price_forecast_df[lower_p].values

            occ_lower = (
                occupancy_forecast_df[lower_o].values
                if occupancy_forecast_df is not None and lower_o in occupancy_forecast_df.columns
                else result["predicted_occupancy"].values
            )
            result[f"revpar_lower_{level}"] = (result[lower_p] * occ_lower).round(2)

        if upper_p in price_forecast_df.columns:
            result[upper_p] = price_forecast_df[upper_p].values

            occ_upper = (
                occupancy_forecast_df[upper_o].values
                if occupancy_forecast_df is not None and upper_o in occupancy_forecast_df.columns
                else result["predicted_occupancy"].values
            )
            result[f"revpar_upper_{level}"] = (result[upper_p] * occ_upper).round(2)

    return result
