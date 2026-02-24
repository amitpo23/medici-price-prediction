"""Weather-derived demand features."""
from __future__ import annotations

import pandas as pd
import numpy as np


def add_weather_features(
    df: pd.DataFrame,
    weather_df: pd.DataFrame,
    date_col: str = "date",
    city_col: str = "city",
) -> pd.DataFrame:
    """Merge weather data and create demand-relevant features."""
    df = df.copy()

    if weather_df.empty:
        return df

    weather = weather_df.copy()
    weather["date"] = pd.to_datetime(weather["date"])

    # Merge on date (and city if available)
    merge_cols = [date_col]
    if city_col in df.columns and "city" in weather.columns:
        merge_cols.append(city_col)

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.merge(
        weather.rename(columns={"city": city_col} if city_col != "city" else {}),
        on=merge_cols,
        how="left",
    )

    # Weather-derived features
    if "temperature_max" in df.columns:
        df["is_hot"] = (df["temperature_max"] > 35).astype(int)
        df["is_pleasant"] = (
            (df["temperature_max"] >= 20) & (df["temperature_max"] <= 30)
        ).astype(int)

    if "precipitation_mm" in df.columns:
        df["is_rainy"] = (df["precipitation_mm"] > 1.0).astype(int)

    # Beach weather score (good for coastal hotels)
    if "temperature_max" in df.columns and "precipitation_mm" in df.columns:
        temp_score = np.clip((df["temperature_max"] - 20) / 15, 0, 1)
        rain_penalty = np.clip(df["precipitation_mm"] / 10, 0, 1)
        df["beach_weather_score"] = (temp_score * (1 - rain_penalty)).round(2)

    return df
