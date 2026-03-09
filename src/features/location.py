"""Geolocation features for hotels."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
from geopy.distance import geodesic

from config.settings import ISRAEL_CITIES


# Key Israeli landmarks that drive hotel demand
LANDMARKS = {
    "Western Wall":       (31.7767, 35.2345),
    "Tel Aviv Beach":     (32.0853, 34.7700),
    "Ben Gurion Airport": (32.0055, 34.8854),
    "Eilat Coral Beach":  (29.5050, 34.9178),
    "Dead Sea Ein Bokek": (31.2000, 35.3600),
    "Sea of Galilee":     (32.8300, 35.5900),
    "Old City Jerusalem": (31.7781, 35.2360),
}

REGIONS = {
    "Central": ["Tel Aviv", "Herzliya", "Netanya"],
    "Jerusalem": ["Jerusalem"],
    "South": ["Eilat", "Dead Sea"],
    "North": ["Haifa", "Tiberias"],
}

# Coastal cities
COASTAL_CITIES = {"Tel Aviv", "Herzliya", "Netanya", "Haifa", "Eilat"}
DESERT_CITIES = {"Eilat", "Dead Sea"}


def add_location_features(
    df: pd.DataFrame,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    city_col: str = "city",
) -> pd.DataFrame:
    """Add distance-to-landmark and region classification features."""
    df = df.copy()

    # If we have lat/lon, compute distances
    if lat_col in df.columns and lon_col in df.columns:
        for name, (lat, lon) in LANDMARKS.items():
            col_name = f"dist_to_{name.lower().replace(' ', '_')}_km"
            df[col_name] = df.apply(
                lambda row: _safe_distance(row[lat_col], row[lon_col], lat, lon),
                axis=1,
            )

        # Nearest landmark
        dist_cols = [c for c in df.columns if c.startswith("dist_to_")]
        if dist_cols:
            df["min_landmark_distance_km"] = df[dist_cols].min(axis=1)

    # City-based features
    if city_col in df.columns:
        df["region"] = df[city_col].apply(_classify_region)
        df["is_coastal"] = df[city_col].isin(COASTAL_CITIES).astype(int)
        df["is_desert"] = df[city_col].isin(DESERT_CITIES).astype(int)

        # Fill lat/lon from known cities if missing
        if lat_col not in df.columns:
            df[lat_col] = df[city_col].map(lambda c: ISRAEL_CITIES.get(c, (None, None))[0])
            df[lon_col] = df[city_col].map(lambda c: ISRAEL_CITIES.get(c, (None, None))[1])

    return df


def _safe_distance(lat1, lon1, lat2, lon2) -> float:
    """Calculate geodesic distance, return NaN on error."""
    try:
        if pd.isna(lat1) or pd.isna(lon1):
            return np.nan
        return geodesic((lat1, lon1), (lat2, lon2)).km
    except (ValueError, TypeError) as e:
        logger.warning("Distance calculation failed: %s", e)
        return np.nan


def _classify_region(city: str) -> str:
    """Classify a city into a region."""
    for region, cities in REGIONS.items():
        if city in cities:
            return region
    return "Other"
