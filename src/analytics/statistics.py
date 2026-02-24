"""Market statistics, competitive analysis, and KPI aggregation."""
from __future__ import annotations

import pandas as pd
import numpy as np

from src.analytics.revenue import calculate_revpar


def market_overview(
    df: pd.DataFrame,
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
    city_col: str = "city",
    star_col: str = "star_rating",
) -> dict:
    """Generate high-level market overview KPIs.

    Returns dict with: total_hotels, avg_price, median_price, avg_occupancy,
    avg_revpar, price_range, by_city, by_star_bucket.
    """
    valid = df.dropna(subset=[price_col])
    has_occ = occupancy_col in valid.columns

    avg_occ = float(valid[occupancy_col].mean()) if has_occ else None
    avg_price = float(valid[price_col].mean())
    avg_revpar = calculate_revpar(avg_price, avg_occ) if avg_occ is not None else None

    result = {
        "total_hotels": int(valid["hotel_id"].nunique()) if "hotel_id" in valid.columns else len(valid),
        "total_records": len(valid),
        "avg_price": round(avg_price, 2),
        "median_price": round(float(valid[price_col].median()), 2),
        "avg_occupancy": round(avg_occ, 3) if avg_occ is not None else None,
        "avg_revpar": round(avg_revpar, 2) if avg_revpar is not None else None,
        "price_range": {
            "min": round(float(valid[price_col].min()), 2),
            "max": round(float(valid[price_col].max()), 2),
        },
    }

    # By city
    if city_col in valid.columns:
        by_city = {}
        for city, group in valid.groupby(city_col):
            city_avg = float(group[price_col].mean())
            city_occ = float(group[occupancy_col].mean()) if has_occ else None
            by_city[str(city)] = {
                "avg_price": round(city_avg, 2),
                "median_price": round(float(group[price_col].median()), 2),
                "avg_occupancy": round(city_occ, 3) if city_occ is not None else None,
                "revpar": round(calculate_revpar(city_avg, city_occ), 2) if city_occ else None,
                "count": len(group),
            }
        result["by_city"] = by_city

    # By star bucket
    if star_col in valid.columns:
        stars = pd.to_numeric(valid[star_col], errors="coerce")
        buckets = pd.cut(stars, bins=[0, 2, 3, 4, 5], labels=["budget", "midrange", "upscale", "luxury"])
        by_star = {}
        for bucket, group in valid.groupby(buckets, observed=True):
            b_avg = float(group[price_col].mean())
            b_occ = float(group[occupancy_col].mean()) if has_occ else None
            by_star[str(bucket)] = {
                "avg_price": round(b_avg, 2),
                "avg_occupancy": round(b_occ, 3) if b_occ is not None else None,
                "revpar": round(calculate_revpar(b_avg, b_occ), 2) if b_occ else None,
                "count": len(group),
            }
        result["by_star_bucket"] = by_star

    return result


def city_statistics(
    df: pd.DataFrame,
    city: str,
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
    star_col: str = "star_rating",
    city_col: str = "city",
) -> dict:
    """Compute detailed statistics for a single city."""
    city_data = df[df[city_col] == city] if city_col in df.columns else df
    valid = city_data.dropna(subset=[price_col])

    if valid.empty:
        return {"city": city, "error": "No data found"}

    has_occ = occupancy_col in valid.columns
    prices = valid[price_col]

    avg_price = float(prices.mean())
    avg_occ = float(valid[occupancy_col].mean()) if has_occ else None

    result = {
        "city": city,
        "hotel_count": int(valid["hotel_id"].nunique()) if "hotel_id" in valid.columns else len(valid),
        "record_count": len(valid),
        "avg_price": round(avg_price, 2),
        "median_price": round(float(prices.median()), 2),
        "price_std": round(float(prices.std()), 2),
        "avg_occupancy": round(avg_occ, 3) if avg_occ is not None else None,
        "revpar": round(calculate_revpar(avg_price, avg_occ), 2) if avg_occ else None,
        "price_distribution": {
            "p10": round(float(prices.quantile(0.10)), 2),
            "p25": round(float(prices.quantile(0.25)), 2),
            "p50": round(float(prices.quantile(0.50)), 2),
            "p75": round(float(prices.quantile(0.75)), 2),
            "p90": round(float(prices.quantile(0.90)), 2),
        },
    }

    # By star rating
    if star_col in valid.columns:
        by_star = {}
        for star, group in valid.groupby(star_col):
            s_avg = float(group[price_col].mean())
            s_occ = float(group[occupancy_col].mean()) if has_occ else None
            by_star[str(star)] = {
                "avg_price": round(s_avg, 2),
                "avg_occupancy": round(s_occ, 3) if s_occ is not None else None,
                "revpar": round(calculate_revpar(s_avg, s_occ), 2) if s_occ else None,
                "count": len(group),
            }
        result["by_star_rating"] = by_star

    return result


def competitive_position(
    hotel_price: float,
    hotel_star_rating: float,
    market_df: pd.DataFrame,
    city: str | None = None,
    price_col: str = "price",
    star_col: str = "star_rating",
    city_col: str = "city",
) -> dict:
    """Analyze a hotel's competitive position within its segment."""
    segment = market_df.copy()

    if city and city_col in segment.columns:
        segment = segment[segment[city_col] == city]

    if star_col in segment.columns:
        star = pd.to_numeric(segment[star_col], errors="coerce")
        segment = segment[(star >= hotel_star_rating - 0.5) & (star <= hotel_star_rating + 0.5)]

    segment = segment.dropna(subset=[price_col])

    if segment.empty:
        return {
            "percentile_rank": 50,
            "segment_avg": hotel_price,
            "segment_median": hotel_price,
            "price_index": 1.0,
            "position": "no_data",
            "nearby_competitors": 0,
        }

    prices = segment[price_col].values
    seg_avg = float(np.mean(prices))
    seg_median = float(np.median(prices))

    # Percentile rank
    rank = float(np.mean(prices <= hotel_price) * 100)

    # Price index
    price_index = hotel_price / seg_avg if seg_avg > 0 else 1.0

    # Position label
    if price_index < 0.90:
        position = "below_market"
    elif price_index > 1.10:
        position = "above_market"
    else:
        position = "at_market"

    # Competitors within +/- 10% price range
    low = hotel_price * 0.90
    high = hotel_price * 1.10
    nearby = int(np.sum((prices >= low) & (prices <= high)))

    return {
        "percentile_rank": round(rank, 1),
        "segment_avg": round(seg_avg, 2),
        "segment_median": round(seg_median, 2),
        "price_index": round(price_index, 3),
        "position": position,
        "nearby_competitors": nearby,
        "segment_size": len(prices),
    }


def segment_comparison(
    df: pd.DataFrame,
    segment_col: str = "star_bucket",
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
) -> pd.DataFrame:
    """Compare KPIs across market segments.

    Returns DataFrame: segment, hotel_count, avg_price, avg_occupancy, revpar, price_range.
    """
    if segment_col not in df.columns:
        return pd.DataFrame()

    has_occ = occupancy_col in df.columns
    records = []

    for segment, group in df.groupby(segment_col, observed=True):
        valid = group.dropna(subset=[price_col])
        if valid.empty:
            continue

        avg_p = float(valid[price_col].mean())
        avg_o = float(valid[occupancy_col].mean()) if has_occ else None

        records.append({
            "segment": str(segment),
            "hotel_count": int(valid["hotel_id"].nunique()) if "hotel_id" in valid.columns else len(valid),
            "avg_price": round(avg_p, 2),
            "avg_occupancy": round(avg_o, 3) if avg_o is not None else None,
            "revpar": round(calculate_revpar(avg_p, avg_o), 2) if avg_o else None,
            "price_min": round(float(valid[price_col].min()), 2),
            "price_max": round(float(valid[price_col].max()), 2),
        })

    return pd.DataFrame(records)
