"""Feature engineering for hotel price prediction."""

import pandas as pd
import numpy as np


def add_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add time-based features from a date column."""
    df = df.copy()
    dt = df[date_col]

    df["day_of_week"] = dt.dt.dayofweek  # 0=Monday
    df["day_of_month"] = dt.dt.day
    df["month"] = dt.dt.month
    df["quarter"] = dt.dt.quarter
    df["week_of_year"] = dt.dt.isocalendar().week.astype(int)
    df["year"] = dt.dt.year

    # Weekend flag (Friday=4, Saturday=5)
    df["is_weekend"] = dt.dt.dayofweek.isin([4, 5]).astype(int)

    # Season (Northern Hemisphere — adjust for Israel if needed)
    df["season"] = dt.dt.month.map({
        12: "winter", 1: "winter", 2: "winter",
        3: "spring", 4: "spring", 5: "spring",
        6: "summer", 7: "summer", 8: "summer",
        9: "autumn", 10: "autumn", 11: "autumn",
    })

    return df


def add_lag_features(
    df: pd.DataFrame,
    value_col: str = "price",
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """Add lagged price values as features."""
    df = df.copy()
    if lags is None:
        lags = [1, 7, 14, 28]  # yesterday, week ago, 2 weeks, month

    for lag in lags:
        df[f"{value_col}_lag_{lag}"] = df[value_col].shift(lag)

    return df


def add_rolling_features(
    df: pd.DataFrame,
    value_col: str = "price",
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """Add rolling statistics as features."""
    df = df.copy()
    if windows is None:
        windows = [7, 14, 30]

    for w in windows:
        df[f"{value_col}_rolling_mean_{w}"] = df[value_col].rolling(w).mean()
        df[f"{value_col}_rolling_std_{w}"] = df[value_col].rolling(w).std()
        df[f"{value_col}_rolling_min_{w}"] = df[value_col].rolling(w).min()
        df[f"{value_col}_rolling_max_{w}"] = df[value_col].rolling(w).max()

    return df


def add_occupancy_features(
    df: pd.DataFrame,
    occupancy_col: str = "occupancy_rate",
) -> pd.DataFrame:
    """Add occupancy-derived features."""
    df = df.copy()
    if occupancy_col not in df.columns:
        return df

    df["occupancy_bucket"] = pd.cut(
        df[occupancy_col],
        bins=[0, 0.3, 0.6, 0.85, 1.0],
        labels=["low", "medium", "high", "full"],
    )

    # Trend: is occupancy increasing or decreasing?
    df["occupancy_trend_7d"] = (
        df[occupancy_col].rolling(7).mean() - df[occupancy_col].rolling(14).mean()
    )

    return df


def add_competitor_features(
    df: pd.DataFrame,
    our_price_col: str = "price",
    competitor_price_col: str = "competitor_avg_price",
) -> pd.DataFrame:
    """Add competitive positioning features."""
    df = df.copy()
    if competitor_price_col not in df.columns:
        return df

    df["price_vs_competitor"] = df[our_price_col] - df[competitor_price_col]
    df["price_ratio_competitor"] = df[our_price_col] / df[competitor_price_col].replace(0, np.nan)

    return df


def add_israeli_holidays(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Flag Israeli holidays and events that affect hotel pricing.

    Major dates that impact hotel demand in Israel:
    - Rosh Hashana, Yom Kippur, Sukkot (Sep-Oct)
    - Passover (Mar-Apr)
    - Summer vacation (Jul-Aug)
    - Christmas/New Year (for tourism)
    """
    df = df.copy()

    # Static approximate windows — for production, use a proper Hebrew calendar library
    holiday_windows = {
        "passover": [(3, 15), (3, 16), (3, 17), (3, 18), (3, 19), (3, 20), (3, 21), (3, 22),
                      (4, 15), (4, 16), (4, 17), (4, 18), (4, 19), (4, 20), (4, 21), (4, 22)],
        "sukkot": [(9, 20), (9, 21), (9, 22), (9, 23), (9, 24), (9, 25), (9, 26), (9, 27),
                   (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7)],
    }

    # Summer high season
    df["is_summer_season"] = df[date_col].dt.month.isin([7, 8]).astype(int)

    # Approximate holiday flag (month, day tuples)
    df["is_holiday_approx"] = 0
    for holiday, dates in holiday_windows.items():
        for month, day in dates:
            mask = (df[date_col].dt.month == month) & (df[date_col].dt.day == day)
            df.loc[mask, "is_holiday_approx"] = 1

    return df


def prepare_features(
    df: pd.DataFrame,
    date_col: str = "date",
    price_col: str = "price",
) -> pd.DataFrame:
    """Run the full feature engineering pipeline."""
    df = add_calendar_features(df, date_col)
    df = add_lag_features(df, price_col)
    df = add_rolling_features(df, price_col)
    df = add_occupancy_features(df)
    df = add_competitor_features(df, price_col)
    df = add_israeli_holidays(df, date_col)
    return df
