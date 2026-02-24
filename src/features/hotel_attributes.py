"""Hotel classification and attribute features."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_star_rating_features(df: pd.DataFrame, star_col: str = "star_rating") -> pd.DataFrame:
    """Add star-rating derived features."""
    df = df.copy()

    if star_col not in df.columns:
        return df

    stars = pd.to_numeric(df[star_col], errors="coerce")

    # Star bucket
    df["star_bucket"] = pd.cut(
        stars,
        bins=[0, 2, 3, 4, 5],
        labels=["budget", "midrange", "upscale", "luxury"],
        right=True,
    )

    # Expected price multiplier based on star rating
    # Budget (1-2): 0.6x, Midrange (3): 1.0x, Upscale (4): 1.5x, Luxury (5): 2.2x
    star_multiplier = {1.0: 0.5, 2.0: 0.7, 3.0: 1.0, 4.0: 1.5, 5.0: 2.2}
    df["star_price_multiplier"] = stars.round().map(star_multiplier).fillna(1.0)

    return df


def add_hotel_type_features(df: pd.DataFrame, type_col: str = "hotel_type") -> pd.DataFrame:
    """Add hotel type classification features."""
    df = df.copy()

    if type_col not in df.columns:
        return df

    hotel_type = df[type_col].str.lower().fillna("")

    df["is_resort"] = hotel_type.str.contains("resort|spa").astype(int)
    df["is_business"] = hotel_type.str.contains("business|conference|convention").astype(int)
    df["is_boutique"] = hotel_type.str.contains("boutique").astype(int)
    df["is_hostel"] = hotel_type.str.contains("hostel|budget").astype(int)

    return df


def add_market_position(
    df: pd.DataFrame,
    price_col: str = "price",
    city_col: str = "city",
    star_col: str = "star_rating",
) -> pd.DataFrame:
    """Calculate hotel's market position relative to similar hotels."""
    df = df.copy()

    if city_col not in df.columns or star_col not in df.columns:
        return df

    # Average price by city + star group
    group_cols = [city_col, star_col]
    valid = df.dropna(subset=[price_col, city_col, star_col])

    if valid.empty:
        return df

    avg_prices = valid.groupby(group_cols)[price_col].mean().reset_index()
    avg_prices.columns = [city_col, star_col, "segment_avg_price"]

    df = df.merge(avg_prices, on=group_cols, how="left")
    df["price_vs_segment"] = df[price_col] / df["segment_avg_price"].replace(0, np.nan)
    df["price_vs_segment"] = df["price_vs_segment"].fillna(1.0)

    return df
