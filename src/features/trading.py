"""Trading-derived features for enhanced price prediction.

Computes features from Medici Hotels trading data:
buy/sell spreads, inventory depth, sell-through rates,
booking velocity, cancellation pressure, and more.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


TRADING_FEATURE_COLUMNS = [
    "buy_sell_spread",
    "inventory_depth",
    "sell_through_rate",
    "avg_days_to_sell",
    "cancellation_pressure",
    "booking_velocity",
    "price_revision_count",
    "supplier_price_gap",
    "opportunity_conversion",
]


def add_trading_features(
    df: pd.DataFrame,
    bookings_df: pd.DataFrame,
    date_col: str = "date",
    hotel_col: str = "hotel_id",
) -> pd.DataFrame:
    """Add all trading-derived features to the pricing DataFrame.

    Args:
        df: Main pricing DataFrame (from existing pipeline).
        bookings_df: Trading bookings from MED_Book (all history).
        date_col: Date column name in df.
        hotel_col: Hotel ID column name in df.
    """
    df = df.copy()

    if bookings_df.empty:
        for col in TRADING_FEATURE_COLUMNS:
            df[col] = 0.0
        return df

    metrics = compute_trading_metrics(bookings_df)

    if hotel_col in df.columns and "HotelId" in metrics.columns:
        df = df.merge(
            metrics.rename(columns={"HotelId": hotel_col}),
            on=hotel_col,
            how="left",
        )

    for col in TRADING_FEATURE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)
        else:
            df[col] = 0.0

    return df


def compute_trading_metrics(bookings_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-hotel trading metrics from booking history.

    Returns DataFrame with one row per HotelId and all 9 trading features.
    """
    df = bookings_df.copy()
    today = pd.Timestamp(date.today())

    results = []
    for hotel_id, group in df.groupby("HotelId"):
        active = group[group["IsActive"] == True]
        sold = group[group["IsSold"] == True]

        # 1. buy_sell_spread: average (PushPrice - BuyPrice) / BuyPrice
        valid_prices = group.dropna(subset=["PushPrice", "BuyPrice"])
        valid_prices = valid_prices[valid_prices["BuyPrice"] > 0]
        if not valid_prices.empty:
            spread = (
                (valid_prices["PushPrice"] - valid_prices["BuyPrice"])
                / valid_prices["BuyPrice"]
            ).mean()
        else:
            spread = 0.0

        # 2. inventory_depth: count of active rooms
        inv_depth = len(active)

        # 3. sell_through_rate: sold / (sold + active)
        total = len(sold) + len(active)
        sell_rate = len(sold) / total if total > 0 else 0.0

        # 4. avg_days_to_sell: average days from Created to DateFrom as proxy
        if not sold.empty and "Created" in sold.columns:
            sold_with_dates = sold.dropna(subset=["Created", "DateFrom"])
            if not sold_with_dates.empty:
                days_to_sell = (
                    sold_with_dates["DateFrom"] - sold_with_dates["Created"]
                ).dt.days.mean()
            else:
                days_to_sell = 30.0
        else:
            days_to_sell = 30.0

        # 5. cancellation_pressure: rooms with cancel deadline < 7 days / total
        if not active.empty and "CancellationTo" in active.columns:
            approaching = active[
                (active["CancellationTo"].notna())
                & (active["CancellationTo"] <= today + timedelta(days=7))
            ]
            cancel_pressure = len(approaching) / len(active)
        else:
            cancel_pressure = 0.0

        # 6. booking_velocity: new bookings per day (last 30 days)
        recent = group[group["Created"] >= today - timedelta(days=30)]
        if not recent.empty and "Created" in recent.columns:
            date_range = (recent["Created"].max() - recent["Created"].min()).days
            velocity = len(recent) / max(date_range, 1)
        else:
            velocity = 0.0

        # 7. price_revision_count: rooms where Price != LastPrice
        if "LastPrice" in group.columns:
            revised = group[
                (group["LastPrice"].notna())
                & (group["PushPrice"] != group["LastPrice"])
            ]
            revision_count = len(revised)
        else:
            revision_count = 0

        # 8. supplier_price_gap: avg price diff between sources
        if "Source" in group.columns:
            by_source = group.groupby("Source")["BuyPrice"].mean()
            if len(by_source) >= 2:
                price_gap = float(by_source.max() - by_source.min())
            else:
                price_gap = 0.0
        else:
            price_gap = 0.0

        # 9. opportunity_conversion: sold / total for this hotel
        total_all = len(group)
        opp_conversion = len(sold) / total_all if total_all > 0 else 0.0

        results.append({
            "HotelId": hotel_id,
            "buy_sell_spread": round(float(spread), 4),
            "inventory_depth": int(inv_depth),
            "sell_through_rate": round(float(sell_rate), 4),
            "avg_days_to_sell": round(float(days_to_sell), 1),
            "cancellation_pressure": round(float(cancel_pressure), 4),
            "booking_velocity": round(float(velocity), 3),
            "price_revision_count": int(revision_count),
            "supplier_price_gap": round(float(price_gap), 2),
            "opportunity_conversion": round(float(opp_conversion), 4),
        })

    if not results:
        return pd.DataFrame(columns=["HotelId"] + TRADING_FEATURE_COLUMNS)

    return pd.DataFrame(results)


def compute_booking_analysis(booking_row: pd.Series, market_price: float) -> dict:
    """Compute analysis metrics for a single booking.

    Used by the recommender for per-booking analysis.
    """
    buy_price = float(booking_row.get("BuyPrice", 0) or 0)
    push_price = float(booking_row.get("PushPrice", 0) or 0)
    today = date.today()

    cancel_to = booking_row.get("CancellationTo")
    days_to_cancel = None
    if pd.notna(cancel_to):
        cancel_date = cancel_to.date() if hasattr(cancel_to, "date") else cancel_to
        days_to_cancel = max(0, (cancel_date - today).days)

    date_from = booking_row.get("DateFrom")
    days_to_checkin = None
    if pd.notna(date_from):
        checkin_date = date_from.date() if hasattr(date_from, "date") else date_from
        days_to_checkin = max(0, (checkin_date - today).days)

    margin_pct = (
        (push_price - buy_price) / buy_price * 100 if buy_price > 0 else 0.0
    )

    market_vs_push = (
        (market_price - push_price) / push_price * 100 if push_price > 0 else 0.0
    )

    return {
        "buy_price": buy_price,
        "push_price": push_price,
        "market_price": market_price,
        "margin_pct": round(margin_pct, 1),
        "market_vs_push_pct": round(market_vs_push, 1),
        "days_to_checkin": days_to_checkin,
        "days_to_cancel_deadline": days_to_cancel,
        "is_profitable_at_market": market_price > buy_price,
    }
