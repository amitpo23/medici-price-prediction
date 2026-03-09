"""Feature engineering for hotel price prediction."""
from __future__ import annotations

import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


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


def add_seasonality_features(
    df: pd.DataFrame,
    value_col: str = "price",
    date_col: str = "date",
) -> pd.DataFrame:
    """Add STL seasonality decomposition features."""
    df = df.copy()

    if value_col not in df.columns or len(df) < 14:
        return df

    try:
        from statsmodels.tsa.seasonal import STL

        series = df.set_index(pd.to_datetime(df[date_col]))[value_col]
        series = series.interpolate(method="linear").bfill().ffill()

        if len(series) >= 14:
            stl = STL(series, period=7, seasonal=13, robust=True)
            result = stl.fit()
            df["price_trend"] = result.trend.values
            df["price_seasonal"] = result.seasonal.values
            df["price_residual"] = result.resid.values
    except (ImportError, ValueError, TypeError) as e:
        logger.warning("STL decomposition failed, skipping: %s", e)

    return df


def prepare_features(
    df: pd.DataFrame,
    date_col: str = "date",
    price_col: str = "price",
    events_df: pd.DataFrame | None = None,
    weather_df: pd.DataFrame | None = None,
    trading_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Run the full feature engineering pipeline with all available data."""
    from src.features.holidays import add_hebrew_holiday_features, add_school_vacation_features
    from src.features.events import add_event_features
    from src.features.weather import add_weather_features
    from src.features.hotel_attributes import add_star_rating_features, add_hotel_type_features
    from src.features.location import add_location_features

    # Core time-series features
    df = add_calendar_features(df, date_col)
    df = add_lag_features(df, price_col)
    df = add_rolling_features(df, price_col)
    df = add_seasonality_features(df, price_col, date_col)
    df = add_occupancy_features(df)
    df = add_competitor_features(df, price_col)

    # Hebrew calendar holidays (replaces old approximation)
    df = add_hebrew_holiday_features(df, date_col)
    df = add_school_vacation_features(df, date_col)

    # Hotel attributes (if columns exist)
    df = add_star_rating_features(df)
    df = add_hotel_type_features(df)

    # Location features (if columns exist)
    df = add_location_features(df)

    # Event features (if events data provided)
    if events_df is not None and not events_df.empty:
        df = add_event_features(df, events_df, date_col)

    # Weather features (if weather data provided)
    if weather_df is not None and not weather_df.empty:
        df = add_weather_features(df, weather_df, date_col)

    # Trading features (if trading data provided)
    if trading_df is not None and not trading_df.empty:
        from src.features.trading import add_trading_features
        df = add_trading_features(df, trading_df, date_col)

    return df
