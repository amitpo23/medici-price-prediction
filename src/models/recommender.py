"""Trading recommendation engine — the decision brain.

Analyzes buy opportunities, existing bookings, and the full portfolio
using ML predictions, market context, and trading metrics.
Returns advisory recommendations only (BUY/PASS/HOLD/REPRICE/CONSIDER_CANCEL/ALERT).
Never executes actions.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

import numpy as np
import pandas as pd

from src.data.trading_schema import Recommendation
from src.features.trading import compute_booking_analysis


# ── Configurable thresholds ──────────────────────────────────────────
MIN_MARGIN_BUY = 0.15          # Minimum margin to recommend a BUY
MIN_SELL_PROBABILITY = 0.40    # Minimum estimated sell probability
REPRICE_THRESHOLD = 0.10       # Market-vs-push gap to trigger REPRICE
CANCEL_RISK_DAYS = 5           # Days before cancel deadline → high urgency
LOW_MARGIN_ALERT = 0.05        # Below this margin → alert
HIGH_INVENTORY_THRESHOLD = 10  # More than this → oversupply warning
MAX_DAYS_UNSOLD = 60           # Alert after this many days without sale


class TradingRecommender:
    """Analyze trading data and produce advisory recommendations.

    This class is the decision engine. It:
      - Evaluates buy opportunities → BUY or PASS
      - Evaluates existing bookings → HOLD, REPRICE, or CONSIDER_CANCEL
      - Analyzes the full portfolio → summary + attention items
    """

    def __init__(
        self,
        min_margin: float = MIN_MARGIN_BUY,
        min_sell_prob: float = MIN_SELL_PROBABILITY,
        reprice_threshold: float = REPRICE_THRESHOLD,
    ):
        self.min_margin = min_margin
        self.min_sell_prob = min_sell_prob
        self.reprice_threshold = reprice_threshold

    # ── Opportunity Analysis ─────────────────────────────────────────

    def analyze_opportunity(
        self,
        opportunity: dict,
        predicted_price: float,
        confidence_interval: tuple[float, float] | None = None,
        occupancy_forecast: float | None = None,
        competitor_price: float | None = None,
        seasonal_context: dict | None = None,
        hotel_metrics: dict | None = None,
    ) -> dict:
        """Analyze a buy opportunity and recommend BUY or PASS.

        Args:
            opportunity: Dict with hotel_id, buy_price, date_from, date_to, etc.
            predicted_price: ML-predicted market price for the dates.
            confidence_interval: (lower, upper) of prediction CI.
            occupancy_forecast: Predicted occupancy rate (0-1).
            competitor_price: Average competitor price.
            seasonal_context: Dict with season, is_holiday, is_weekend, etc.
            hotel_metrics: Trading metrics for this hotel from compute_trading_metrics.

        Returns:
            Full analysis dict with recommendation, reasoning, price data, risk.
        """
        buy_price = float(opportunity.get("buy_price", 0))
        push_price = opportunity.get("push_price")
        hotel_id = opportunity.get("hotel_id", 0)

        if buy_price <= 0:
            return self._build_result(
                "PASS", 0.95, ["Buy price is zero or negative"], hotel_id,
                opportunity_reference=opportunity.get("opportunity_id"),
            )

        # Price analysis
        price_analysis = self._analyze_price(
            buy_price, predicted_price, confidence_interval, competitor_price, push_price,
        )

        # Sell probability estimate
        sell_prob = self._estimate_sell_probability(
            price_analysis, occupancy_forecast, seasonal_context, hotel_metrics,
        )

        # Risk assessment
        risk = self._assess_risk(
            price_analysis, sell_prob, occupancy_forecast, hotel_metrics,
        )

        # Decision
        rec_type, confidence, reasoning = self._decide_opportunity(
            price_analysis, sell_prob, risk, seasonal_context,
        )

        # Suggested push price
        suggested_push = self._calculate_push_price(
            buy_price, predicted_price, competitor_price, sell_prob,
        )

        # Impact factors
        impact_factors = self._compute_impact_factors(
            occupancy_forecast, seasonal_context, hotel_metrics, competitor_price,
        )

        result = self._build_result(
            rec_type, confidence, reasoning, hotel_id,
            opportunity_reference=opportunity.get("opportunity_id"),
            price_data={
                "buy_price": buy_price,
                "predicted_market_price": round(predicted_price, 2),
                "suggested_push_price": round(suggested_push, 2),
                "competitor_price": round(competitor_price, 2) if competitor_price else None,
                "margin_pct": round(price_analysis["margin_pct"], 1),
                "sell_probability": round(sell_prob, 3),
                "confidence_interval": {
                    "lower": round(confidence_interval[0], 2),
                    "upper": round(confidence_interval[1], 2),
                } if confidence_interval else None,
            },
            risk_data=risk,
            market_context={
                "occupancy_forecast": round(occupancy_forecast, 3) if occupancy_forecast else None,
                "season": (seasonal_context or {}).get("season"),
                "is_holiday": (seasonal_context or {}).get("is_holiday", False),
                "is_weekend": (seasonal_context or {}).get("is_weekend", False),
            },
            impact_factors=impact_factors,
        )

        return result

    def _decide_opportunity(
        self,
        price_analysis: dict,
        sell_prob: float,
        risk: dict,
        seasonal_context: dict | None,
    ) -> tuple[str, float, list[str]]:
        """Core decision logic for opportunities."""
        reasoning = []
        margin = price_analysis["margin_pct"] / 100
        market_upside = price_analysis["market_upside_pct"] / 100

        # Strong BUY signals
        strong_buy = (
            margin >= self.min_margin * 1.5
            and sell_prob >= 0.65
            and market_upside >= 0.10
        )

        # Basic BUY criteria
        basic_buy = (
            margin >= self.min_margin
            and sell_prob >= self.min_sell_prob
        )

        if strong_buy:
            reasoning.append(f"Strong margin ({margin:.0%}) with high sell probability ({sell_prob:.0%})")
            if market_upside > 0.15:
                reasoning.append(f"Significant market upside ({market_upside:.0%})")
            if seasonal_context and seasonal_context.get("is_holiday"):
                reasoning.append("Holiday period boosts demand")
            return "BUY", min(0.70 + sell_prob * 0.25, 0.95), reasoning

        if basic_buy:
            reasoning.append(f"Margin ({margin:.0%}) meets minimum threshold")
            reasoning.append(f"Sell probability: {sell_prob:.0%}")
            if risk.get("risk_level") == "high":
                reasoning.append(f"Elevated risk: {risk.get('primary_risk', 'various factors')}")
            return "BUY", min(0.50 + sell_prob * 0.30, 0.85), reasoning

        # PASS reasons
        if margin < self.min_margin:
            reasoning.append(f"Margin ({margin:.0%}) below minimum ({self.min_margin:.0%})")
        if sell_prob < self.min_sell_prob:
            reasoning.append(f"Sell probability ({sell_prob:.0%}) too low")
        if market_upside < 0:
            reasoning.append(f"Market price below buy price (downside: {market_upside:.0%})")
        if risk.get("risk_level") == "high" and not basic_buy:
            reasoning.append(f"High risk: {risk.get('primary_risk', 'multiple factors')}")

        return "PASS", min(0.50 + (1 - sell_prob) * 0.30, 0.90), reasoning

    # ── Booking Analysis ─────────────────────────────────────────────

    def analyze_booking(
        self,
        booking_row: pd.Series,
        predicted_price: float,
        confidence_interval: tuple[float, float] | None = None,
        occupancy_forecast: float | None = None,
        competitor_price: float | None = None,
    ) -> dict:
        """Analyze an existing booking → HOLD, REPRICE, or CONSIDER_CANCEL.

        Args:
            booking_row: Series from active bookings DataFrame.
            predicted_price: Current ML market price prediction.
            confidence_interval: (lower, upper) bounds.
            occupancy_forecast: Current occupancy forecast.
            competitor_price: Current competitor average.
        """
        analysis = compute_booking_analysis(booking_row, predicted_price)
        hotel_id = int(booking_row.get("HotelId", 0))
        pre_book_id = booking_row.get("PreBookId")

        buy_price = analysis["buy_price"]
        push_price = analysis["push_price"]
        market_price = analysis["market_price"]
        margin_pct = analysis["margin_pct"]
        market_vs_push = analysis["market_vs_push_pct"]
        days_to_checkin = analysis["days_to_checkin"]
        days_to_cancel = analysis["days_to_cancel_deadline"]

        reasoning = []
        rec_type = "HOLD"
        confidence = 0.60

        # Check if repricing is warranted
        if market_vs_push > self.reprice_threshold * 100:
            # Market is significantly above our push price → reprice up
            rec_type = "REPRICE"
            reasoning.append(
                f"Market ({market_price:.0f}) is {market_vs_push:.1f}% above push price ({push_price:.0f})"
            )
            confidence = min(0.60 + abs(market_vs_push) / 200, 0.90)

        elif market_vs_push < -self.reprice_threshold * 100:
            # Market dropped significantly below push price
            if margin_pct > LOW_MARGIN_ALERT * 100:
                rec_type = "REPRICE"
                reasoning.append(
                    f"Market dropped {abs(market_vs_push):.1f}% below push price — consider lowering"
                )
                confidence = min(0.55 + abs(market_vs_push) / 200, 0.85)
            else:
                rec_type = "CONSIDER_CANCEL"
                reasoning.append(
                    f"Market well below push price and margin thin ({margin_pct:.1f}%)"
                )
                confidence = 0.65

        # Cancel deadline pressure
        if days_to_cancel is not None and days_to_cancel <= CANCEL_RISK_DAYS:
            if not analysis["is_profitable_at_market"]:
                rec_type = "CONSIDER_CANCEL"
                reasoning.append(
                    f"Cancel deadline in {days_to_cancel} days, unprofitable at market price"
                )
                confidence = max(confidence, 0.75)
            elif margin_pct < LOW_MARGIN_ALERT * 100:
                rec_type = "ALERT"
                reasoning.append(
                    f"Cancel deadline in {days_to_cancel} days with thin margin ({margin_pct:.1f}%)"
                )
                confidence = max(confidence, 0.70)

        # Long unsold check
        if days_to_checkin is not None and days_to_checkin > MAX_DAYS_UNSOLD:
            pass  # Far out, no urgency
        elif days_to_checkin is not None and days_to_checkin < 7:
            if not analysis["is_profitable_at_market"]:
                reasoning.append(f"Check-in in {days_to_checkin} days — urgent attention needed")
                if rec_type == "HOLD":
                    rec_type = "ALERT"
                    confidence = 0.80

        # Default HOLD reasoning
        if rec_type == "HOLD" and not reasoning:
            reasoning.append(f"Position healthy — margin {margin_pct:.1f}%, market aligned")
            if days_to_checkin is not None:
                reasoning.append(f"{days_to_checkin} days to check-in")

        # Suggested new push price for REPRICE
        suggested_push = None
        if rec_type == "REPRICE":
            suggested_push = self._calculate_push_price(
                buy_price, predicted_price, competitor_price, 0.6,
            )

        return self._build_result(
            rec_type, confidence, reasoning, hotel_id,
            booking_reference=pre_book_id,
            price_data={
                "buy_price": buy_price,
                "current_push_price": push_price,
                "predicted_market_price": round(predicted_price, 2),
                "suggested_push_price": round(suggested_push, 2) if suggested_push else None,
                "margin_pct": round(margin_pct, 1),
                "market_vs_push_pct": round(market_vs_push, 1),
                "days_to_checkin": days_to_checkin,
                "days_to_cancel_deadline": days_to_cancel,
                "is_profitable_at_market": analysis["is_profitable_at_market"],
            },
        )

    # ── Portfolio Analysis ───────────────────────────────────────────

    def analyze_portfolio(
        self,
        bookings_df: pd.DataFrame,
        predictions: dict[int, float] | None = None,
        occupancy_forecasts: dict[int, float] | None = None,
    ) -> dict:
        """Analyze the full active booking portfolio.

        Args:
            bookings_df: Active bookings from trading DB.
            predictions: Dict of hotel_id → predicted market price.
            occupancy_forecasts: Dict of hotel_id → forecasted occupancy.

        Returns:
            Portfolio summary with attention items and statistics.
        """
        if bookings_df.empty:
            return {
                "total_bookings": 0,
                "summary": "No active bookings in portfolio",
                "attention_items": [],
                "statistics": {},
            }

        predictions = predictions or {}
        occupancy_forecasts = occupancy_forecasts or {}

        attention_items = []
        all_recommendations = []
        total_buy_value = 0.0
        total_push_value = 0.0
        hotels_in_portfolio = set()

        for _, row in bookings_df.iterrows():
            hotel_id = int(row.get("HotelId", 0))
            hotels_in_portfolio.add(hotel_id)

            buy_price = float(row.get("BuyPrice", 0) or 0)
            push_price = float(row.get("PushPrice", 0) or 0)
            total_buy_value += buy_price
            total_push_value += push_price

            predicted = predictions.get(hotel_id)
            if predicted is None:
                continue

            occupancy = occupancy_forecasts.get(hotel_id)
            rec = self.analyze_booking(row, predicted, occupancy_forecast=occupancy)
            all_recommendations.append(rec)

            if rec["type"] in ("REPRICE", "CONSIDER_CANCEL", "ALERT"):
                attention_items.append({
                    "pre_book_id": row.get("PreBookId"),
                    "hotel_id": hotel_id,
                    "hotel_name": row.get("HotelName", row.get("hotel_name", "")),
                    "recommendation": rec["type"],
                    "confidence": rec["confidence"],
                    "reasoning": rec["reasoning"],
                    "price_data": rec.get("price_data"),
                })

        # Compute statistics
        rec_counts = {}
        for rec in all_recommendations:
            t = rec["type"]
            rec_counts[t] = rec_counts.get(t, 0) + 1

        portfolio_margin = (
            (total_push_value - total_buy_value) / total_buy_value * 100
            if total_buy_value > 0 else 0.0
        )

        # Sort attention items by urgency
        urgency_order = {"CONSIDER_CANCEL": 0, "ALERT": 1, "REPRICE": 2}
        attention_items.sort(key=lambda x: urgency_order.get(x["recommendation"], 99))

        return {
            "total_bookings": len(bookings_df),
            "analyzed": len(all_recommendations),
            "hotels_in_portfolio": len(hotels_in_portfolio),
            "attention_items": attention_items,
            "attention_count": len(attention_items),
            "recommendation_breakdown": rec_counts,
            "statistics": {
                "total_buy_value": round(total_buy_value, 2),
                "total_push_value": round(total_push_value, 2),
                "portfolio_margin_pct": round(portfolio_margin, 1),
                "avg_margin_pct": round(portfolio_margin, 1),
            },
            "summary": self._generate_portfolio_summary(
                len(bookings_df), rec_counts, len(attention_items), portfolio_margin,
            ),
        }

    def _generate_portfolio_summary(
        self,
        total: int,
        rec_counts: dict,
        attention_count: int,
        margin_pct: float,
    ) -> str:
        """Generate a human-readable portfolio summary."""
        parts = [f"{total} active bookings"]
        parts.append(f"portfolio margin: {margin_pct:.1f}%")

        if attention_count > 0:
            parts.append(f"{attention_count} items need attention")
            if rec_counts.get("CONSIDER_CANCEL", 0) > 0:
                parts.append(
                    f"{rec_counts['CONSIDER_CANCEL']} cancel candidates"
                )
            if rec_counts.get("REPRICE", 0) > 0:
                parts.append(f"{rec_counts['REPRICE']} reprice suggestions")
        else:
            parts.append("all positions healthy")

        return " | ".join(parts)

    # ── Private Helpers ──────────────────────────────────────────────

    def _analyze_price(
        self,
        buy_price: float,
        predicted_price: float,
        ci: tuple[float, float] | None,
        competitor_price: float | None,
        push_price: float | None,
    ) -> dict:
        """Compute price analysis metrics."""
        margin_pct = (predicted_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
        market_upside_pct = (predicted_price - buy_price) / buy_price * 100 if buy_price > 0 else 0

        result = {
            "buy_price": buy_price,
            "predicted_price": predicted_price,
            "margin_pct": margin_pct,
            "market_upside_pct": market_upside_pct,
        }

        if ci:
            result["ci_lower"] = ci[0]
            result["ci_upper"] = ci[1]
            # Worst-case margin (lower CI bound)
            result["worst_case_margin_pct"] = (
                (ci[0] - buy_price) / buy_price * 100 if buy_price > 0 else 0
            )

        if competitor_price and competitor_price > 0:
            result["vs_competitor_pct"] = (
                (predicted_price - competitor_price) / competitor_price * 100
            )

        if push_price and push_price > 0:
            result["push_margin_pct"] = (
                (push_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
            )

        return result

    def _estimate_sell_probability(
        self,
        price_analysis: dict,
        occupancy: float | None,
        seasonal: dict | None,
        hotel_metrics: dict | None,
    ) -> float:
        """Estimate probability of selling the room at push price.

        Combines multiple signals into a 0-1 probability.
        """
        # Start with base probability from margin
        margin = price_analysis["margin_pct"] / 100
        if margin < 0:
            base = 0.15
        elif margin < 0.10:
            base = 0.35
        elif margin < 0.20:
            base = 0.55
        elif margin < 0.35:
            base = 0.65
        else:
            base = 0.50  # Very high margin may mean overpriced

        # Adjust for occupancy
        if occupancy is not None:
            if occupancy > 0.85:
                base += 0.15  # High demand
            elif occupancy > 0.65:
                base += 0.05
            elif occupancy < 0.40:
                base -= 0.10  # Low demand

        # Adjust for seasonal context
        if seasonal:
            if seasonal.get("is_holiday"):
                base += 0.10
            if seasonal.get("is_weekend"):
                base += 0.05

        # Adjust for hotel historical performance
        if hotel_metrics:
            sell_rate = hotel_metrics.get("sell_through_rate", 0)
            if sell_rate > 0.7:
                base += 0.10
            elif sell_rate > 0.4:
                base += 0.05
            elif sell_rate < 0.2:
                base -= 0.10

        # Adjust for competitor positioning
        vs_comp = price_analysis.get("vs_competitor_pct")
        if vs_comp is not None:
            if vs_comp < -10:
                base += 0.10  # Cheaper than competitors
            elif vs_comp > 10:
                base -= 0.10  # More expensive

        # Adjust for CI uncertainty
        if "worst_case_margin_pct" in price_analysis:
            if price_analysis["worst_case_margin_pct"] < 0:
                base -= 0.10  # Risk of loss at lower CI

        return float(np.clip(base, 0.05, 0.95))

    def _calculate_push_price(
        self,
        buy_price: float,
        predicted_price: float,
        competitor_price: float | None,
        sell_prob: float,
    ) -> float:
        """Calculate suggested push price balancing margin and sell probability."""
        if buy_price <= 0:
            return predicted_price

        # Target margin based on sell probability
        if sell_prob >= 0.70:
            target_margin = 0.25  # Can afford higher margin
        elif sell_prob >= 0.50:
            target_margin = 0.18
        else:
            target_margin = 0.12  # Price competitively

        # Start from buy price + target margin
        push_from_margin = buy_price * (1 + target_margin)

        # Consider market price (don't go too far above or below)
        push_from_market = predicted_price * 0.97  # Slightly under market

        # Blend: weight market price more when sell probability is lower
        market_weight = 1.0 - sell_prob * 0.5
        push = push_from_margin * (1 - market_weight) + push_from_market * market_weight

        # Don't go below buy price + minimum margin
        min_push = buy_price * (1 + LOW_MARGIN_ALERT)
        push = max(push, min_push)

        # Don't go significantly above competitor
        if competitor_price and competitor_price > 0:
            max_above_comp = competitor_price * 1.05
            if push > max_above_comp and sell_prob < 0.60:
                push = max_above_comp

        return round(push, 2)

    def _assess_risk(
        self,
        price_analysis: dict,
        sell_prob: float,
        occupancy: float | None,
        hotel_metrics: dict | None,
    ) -> dict:
        """Assess the risk level of a position or opportunity."""
        risk_factors = []

        # Margin risk
        margin = price_analysis["margin_pct"] / 100
        if margin < LOW_MARGIN_ALERT:
            risk_factors.append("very_thin_margin")
        elif margin < self.min_margin:
            risk_factors.append("below_target_margin")

        # CI risk
        if price_analysis.get("worst_case_margin_pct", 100) < 0:
            risk_factors.append("potential_loss_at_lower_ci")

        # Sell probability risk
        if sell_prob < 0.30:
            risk_factors.append("low_sell_probability")

        # Occupancy risk
        if occupancy is not None and occupancy < 0.35:
            risk_factors.append("low_occupancy_forecast")

        # Inventory concentration
        if hotel_metrics and hotel_metrics.get("inventory_depth", 0) > HIGH_INVENTORY_THRESHOLD:
            risk_factors.append("high_inventory_concentration")

        # Determine overall risk level
        if len(risk_factors) >= 3 or "potential_loss_at_lower_ci" in risk_factors:
            level = "high"
        elif len(risk_factors) >= 1:
            level = "medium"
        else:
            level = "low"

        return {
            "risk_level": level,
            "risk_factors": risk_factors,
            "primary_risk": risk_factors[0] if risk_factors else None,
        }

    def _compute_impact_factors(
        self,
        occupancy: float | None,
        seasonal: dict | None,
        hotel_metrics: dict | None,
        competitor_price: float | None,
    ) -> list[dict]:
        """Compute impact factors explaining what influenced the recommendation."""
        factors = []

        if occupancy is not None:
            direction = "positive" if occupancy > 0.65 else "negative" if occupancy < 0.40 else "neutral"
            factors.append({
                "factor": "occupancy_forecast",
                "value": round(occupancy, 3),
                "direction": direction,
                "weight": 0.25,
            })

        if seasonal:
            if seasonal.get("is_holiday"):
                factors.append({
                    "factor": "holiday_period",
                    "value": True,
                    "direction": "positive",
                    "weight": 0.20,
                })
            if seasonal.get("season"):
                high_seasons = ("summer",)
                direction = "positive" if seasonal["season"] in high_seasons else "neutral"
                factors.append({
                    "factor": "season",
                    "value": seasonal["season"],
                    "direction": direction,
                    "weight": 0.10,
                })

        if hotel_metrics:
            sell_rate = hotel_metrics.get("sell_through_rate", 0)
            direction = "positive" if sell_rate > 0.5 else "negative" if sell_rate < 0.2 else "neutral"
            factors.append({
                "factor": "hotel_sell_through_rate",
                "value": round(sell_rate, 3),
                "direction": direction,
                "weight": 0.20,
            })

        if competitor_price is not None:
            factors.append({
                "factor": "competitor_price",
                "value": round(competitor_price, 2),
                "direction": "neutral",
                "weight": 0.15,
            })

        return factors

    def _build_result(
        self,
        rec_type: str,
        confidence: float,
        reasoning: list[str],
        hotel_id: int,
        booking_reference: int | None = None,
        opportunity_reference: str | None = None,
        price_data: dict | None = None,
        risk_data: dict | None = None,
        market_context: dict | None = None,
        impact_factors: list[dict] | None = None,
    ) -> dict:
        """Build a standardized recommendation result dict."""
        rec = Recommendation(
            type=rec_type,
            confidence=round(confidence, 3),
            reasoning=reasoning,
            hotel_id=hotel_id,
            booking_reference=booking_reference,
            opportunity_reference=opportunity_reference,
            price_data=price_data,
            risk_data=risk_data,
            market_context=market_context,
            impact_factors=impact_factors or [],
        )
        return asdict(rec)
