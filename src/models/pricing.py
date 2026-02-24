"""Dynamic pricing logic — revenue management layer on top of forecasts."""
from __future__ import annotations

import pandas as pd
import numpy as np


class DynamicPricer:
    """Calculate recommended prices based on forecasts, demand, and competition."""

    def __init__(
        self,
        min_price: float = 200.0,
        max_price: float = 2000.0,
        base_margin: float = 0.15,
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.base_margin = base_margin

    def calculate_recommended_price(
        self,
        predicted_price: float,
        occupancy_rate: float | None = None,
        competitor_price: float | None = None,
        is_weekend: bool = False,
        is_holiday: bool = False,
        event_impact_score: float | None = None,
        beach_weather_score: float | None = None,
        star_rating: float | None = None,
    ) -> dict:
        """Calculate a recommended price with all available signals.

        Returns a dict with recommended price and breakdown of adjustments.
        """
        base = predicted_price
        adjustments = {}

        # Star rating premium (non-linear curve)
        if star_rating is not None and star_rating > 0:
            star_multipliers = {1: 0.7, 2: 0.85, 3: 1.0, 4: 1.3, 5: 1.8}
            nearest = min(star_multipliers.keys(), key=lambda k: abs(k - star_rating))
            factor = star_multipliers[nearest]
            if factor != 1.0:
                adjustments["star_rating"] = factor
                base *= factor

        # Demand-based adjustment (occupancy)
        if occupancy_rate is not None:
            if occupancy_rate > 0.85:
                factor = 1.0 + (occupancy_rate - 0.85) * 2
                adjustments["high_demand"] = factor
                base *= factor
            elif occupancy_rate < 0.4:
                factor = 0.85 + occupancy_rate * 0.375
                adjustments["low_demand"] = factor
                base *= factor

        # Weekend premium
        if is_weekend:
            adjustments["weekend"] = 1.10
            base *= 1.10

        # Holiday premium
        if is_holiday:
            adjustments["holiday"] = 1.20
            base *= 1.20

        # Event impact (conferences, festivals)
        if event_impact_score is not None and event_impact_score > 0:
            factor = 1.0 + min(event_impact_score * 0.03, 0.15)  # Up to +15%
            adjustments["events"] = round(factor, 3)
            base *= factor

        # Beach weather score (good weather → higher coastal demand)
        if beach_weather_score is not None and beach_weather_score > 0.7:
            factor = 1.0 + (beach_weather_score - 0.7) * 0.1  # Up to +3%
            adjustments["good_weather"] = round(factor, 3)
            base *= factor

        # Competitive positioning
        if competitor_price is not None and competitor_price > 0:
            ratio = base / competitor_price
            if ratio > 1.15:
                factor = 0.95
                adjustments["competitor_high"] = factor
                base *= factor
            elif ratio < 0.85:
                factor = 1.05
                adjustments["competitor_low"] = factor
                base *= factor

        # Enforce bounds
        recommended = np.clip(base, self.min_price, self.max_price)

        return {
            "predicted_price": round(predicted_price, 2),
            "recommended_price": round(recommended, 2),
            "adjustments": adjustments,
            "margin_vs_predicted": round((recommended - predicted_price) / predicted_price * 100, 1),
        }

    def generate_pricing_table(
        self,
        predictions_df: pd.DataFrame,
        occupancy_df: pd.DataFrame | None = None,
        competitor_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Generate a full pricing recommendation table from predictions.

        Args:
            predictions_df: DataFrame with 'date' and 'predicted_price' columns.
            occupancy_df: Optional DataFrame with 'date' and 'occupancy_rate'.
            competitor_df: Optional DataFrame with 'date' and 'competitor_avg_price'.
        """
        df = predictions_df.copy()

        if occupancy_df is not None:
            df = df.merge(occupancy_df[["date", "occupancy_rate"]], on="date", how="left")
        if competitor_df is not None:
            df = df.merge(competitor_df[["date", "competitor_avg_price"]], on="date", how="left")

        results = []
        for _, row in df.iterrows():
            rec = self.calculate_recommended_price(
                predicted_price=row["predicted_price"],
                occupancy_rate=row.get("occupancy_rate"),
                competitor_price=row.get("competitor_avg_price"),
                is_weekend=pd.Timestamp(row["date"]).dayofweek in (4, 5),
            )
            rec["date"] = row["date"]
            results.append(rec)

        return pd.DataFrame(results)
