"""Deep prediction engine — weighted ensemble of multiple signals.

Combines three prediction signals:
  Signal 1: Forward curve (existing decay curve walk)
  Signal 2: Historical patterns (same-period, lead-time, DOW)
  Signal 3: ML forecast (Darts XGBoost/LightGBM, if trained)

Produces enriched predictions with:
  - Per-signal breakdown and weights
  - Year-over-year comparison
  - Human-readable "why" explanation
  - All existing prediction fields (backward-compatible)
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.forward_curve import (
    DecayCurve,
    Enrichments,
    predict_forward_curve,
)

logger = logging.getLogger(__name__)


class DeepPredictor:
    """Unified prediction engine combining all available signals."""

    DEFAULT_WEIGHTS = {
        "forward_curve": 0.50,
        "historical_pattern": 0.30,
        "ml_forecast": 0.20,
    }

    def __init__(
        self,
        decay_curve: DecayCurve,
        historical_patterns: dict,
        ml_models_dir: Path | None = None,
    ):
        self.decay_curve = decay_curve
        self.historical_patterns = historical_patterns
        self.ml_models_dir = ml_models_dir

    def predict(
        self,
        detail_id: int,
        hotel_id: int,
        current_price: float,
        days_to_checkin: int,
        category: str,
        board: str,
        date_from,
        all_snapshots: pd.DataFrame,
        enrichments: Enrichments,
        momentum_state: dict | None = None,
        regime_state: dict | None = None,
    ) -> dict:
        """Generate a deep prediction combining all available signals.

        Args:
            momentum_state: Pre-computed momentum dict (from compute_momentum().to_dict()).
            regime_state: Pre-computed regime dict (from detect_regime().to_dict()).

        Returns a dict that is a backward-compatible superset of the
        existing prediction format from analyzer._predict_prices().
        """
        if momentum_state is None:
            momentum_state = {"signal": "INSUFFICIENT_DATA", "strength": 0}
        if regime_state is None:
            regime_state = {"regime": "NORMAL", "z_score": 0, "divergence_pct": 0, "alert_level": "none", "description": ""}

        # Signal 1: Forward curve
        fwd_signal = self._get_forward_curve_signal(
            detail_id, hotel_id, current_price, days_to_checkin,
            category, board, momentum_state, enrichments,
        )

        # Signal 2: Historical patterns
        hist_signal = self._get_historical_signal(
            hotel_id, category, current_price, date_from, days_to_checkin,
        )

        # Signal 3: ML forecast (optional)
        ml_signal = self._get_ml_signal(
            hotel_id, days_to_checkin,
            current_price=current_price,
            date_from=date_from,
            enrichments=enrichments,
        )

        # Collect available signals
        signals = [fwd_signal]
        if hist_signal is not None:
            signals.append(hist_signal)
        if ml_signal is not None:
            signals.append(ml_signal)

        # Compute dynamic weights
        weights = self._compute_weights(signals)

        # Ensemble prediction
        ensemble_price = sum(
            s["predicted_price"] * w for s, w in zip(signals, weights)
        )
        ensemble_change_pct = (ensemble_price / current_price - 1) * 100

        # Use forward curve bounds, widened if signals disagree
        fwd_lower = fwd_signal.get("lower_bound", ensemble_price * 0.90)
        fwd_upper = fwd_signal.get("upper_bound", ensemble_price * 1.10)
        signal_spread = max(s["predicted_price"] for s in signals) - min(s["predicted_price"] for s in signals)
        if signal_spread > 0:
            fwd_lower -= signal_spread * 0.3
            fwd_upper += signal_spread * 0.3

        # YoY comparison
        yoy = self._build_yoy_comparison(hotel_id, category, current_price, date_from)

        # Explanation
        explanation = self._build_explanation(
            signals, weights, yoy,
            self._get_context(hotel_id, category),
            momentum_state, regime_state, enrichments, date_from,
        )

        # Probability info
        prob_info = self.decay_curve.get_probabilities(days_to_checkin)

        # Cancel probability
        cancel_prob = None
        try:
            from src.analytics.booking_benchmarks import get_cancel_probability
            cancel_prob = get_cancel_probability(days_to_checkin)
        except Exception:
            pass

        # Forward curve daily points (for compatibility)
        fwd_curve = fwd_signal.get("forward_curve_obj")
        daily_predictions = []
        forward_curve_points = []
        if fwd_curve and fwd_curve.points:
            for pt in fwd_curve.points:
                daily_predictions.append({
                    "date": pt.date,
                    "days_remaining": pt.t,
                    "predicted_price": pt.predicted_price,
                    "lower_bound": pt.lower_bound,
                    "upper_bound": pt.upper_bound,
                    "dow": pt.dow,
                })
                forward_curve_points.append({
                    "date": pt.date, "t": pt.t,
                    "predicted_price": pt.predicted_price,
                    "daily_change_pct": pt.daily_change_pct,
                    "cumulative_change_pct": pt.cumulative_change_pct,
                    "lower_bound": pt.lower_bound,
                    "upper_bound": pt.upper_bound,
                    "volatility_at_t": pt.volatility_at_t,
                    "event_adj_pct": pt.event_adj_pct,
                    "season_adj_pct": pt.season_adj_pct,
                    "demand_adj_pct": pt.demand_adj_pct,
                    "momentum_adj_pct": pt.momentum_adj_pct,
                })

        # Determine confidence quality
        density = self.decay_curve.get_data_density(days_to_checkin)
        hist_quality = 0.0
        ctx = self._get_context(hotel_id, category)
        if ctx:
            hist_quality = ctx.get("data_quality", 0)

        if density in ("high",) and hist_quality > 0.5:
            confidence_quality = "high"
        elif density in ("high", "medium") or hist_quality > 0.3:
            confidence_quality = "medium"
        else:
            confidence_quality = "low"

        # Build result — backward-compatible superset
        # Note: momentum, regime, hotel_name, category, board labels
        # are added by analyzer.py after this call.
        result = {
            "current_price": current_price,
            "date_from": str(date_from),
            "days_to_checkin": days_to_checkin,
            "predicted_checkin_price": round(ensemble_price, 2),
            "expected_change_pct": round(ensemble_change_pct, 2),
            "probability": prob_info,
            "cancel_probability": round(cancel_prob, 3) if cancel_prob is not None else None,
            "model_type": "deep_ensemble" if len(signals) > 1 else "forward_curve",
            "daily": daily_predictions,
            "confidence_quality": confidence_quality,
            "forward_curve": forward_curve_points,

            # New keys
            "prediction_method": "deep_ensemble" if len(signals) > 1 else "forward_curve_only",
            "signals": [
                {
                    "source": s["source"],
                    "predicted_price": round(s["predicted_price"], 2),
                    "confidence": round(s["confidence"], 2),
                    "weight": round(w, 3),
                    "reasoning": s.get("reasoning", ""),
                }
                for s, w in zip(signals, weights)
            ],
            "yoy_comparison": yoy,
            "explanation": explanation,
        }

        return result

    # ── Signal generators ────────────────────────────────────────────

    def _get_forward_curve_signal(
        self,
        detail_id: int,
        hotel_id: int,
        current_price: float,
        days_to_checkin: int,
        category: str,
        board: str,
        momentum_state: dict,
        enrichments: Enrichments,
    ) -> dict:
        """Signal 1: Existing forward curve prediction."""
        fwd = predict_forward_curve(
            detail_id=detail_id,
            hotel_id=hotel_id,
            current_price=current_price,
            current_t=days_to_checkin,
            category=category,
            board=board,
            curve=self.decay_curve,
            momentum_state=momentum_state,
            enrichments=enrichments,
        )

        final_price = fwd.points[-1].predicted_price if fwd.points else current_price
        lower = fwd.points[-1].lower_bound if fwd.points else current_price * 0.90
        upper = fwd.points[-1].upper_bound if fwd.points else current_price * 1.10

        density = self.decay_curve.get_data_density(days_to_checkin)
        confidence_map = {"high": 0.8, "medium": 0.6, "low": 0.4, "extrapolated": 0.2}
        confidence = confidence_map.get(density, 0.3)

        return {
            "source": "forward_curve",
            "predicted_price": final_price,
            "confidence": confidence,
            "lower_bound": lower,
            "upper_bound": upper,
            "reasoning": f"Decay curve walk ({density} data density at T={days_to_checkin})",
            "forward_curve_obj": fwd,
        }

    def _get_historical_signal(
        self,
        hotel_id: int,
        category: str,
        current_price: float,
        date_from: str,
        days_to_checkin: int,
    ) -> dict | None:
        """Signal 2: Historical pattern-based prediction."""
        ctx = self._get_context(hotel_id, category)
        if not ctx:
            return None

        try:
            target_date = pd.Timestamp(date_from)
            target_month = target_date.month
        except Exception:
            return None

        # Start with same-period average price
        same_period = ctx.get("same_period", {}).get(target_month, {})
        base_price = same_period.get("avg_price")
        reasoning_parts = []

        if base_price is not None:
            reasoning_parts.append(
                f"Same-period avg price: ${base_price:.0f} "
                f"({same_period.get('data_source', 'historical')}, "
                f"n={same_period.get('n_observations', 0)})"
            )
        else:
            # Fall back to current price adjusted by monthly index
            monthly_index = ctx.get("monthly_index", {})
            month_idx = monthly_index.get(target_month, 1.0)
            base_price = current_price * month_idx
            if month_idx != 1.0:
                reasoning_parts.append(
                    f"No same-period data; adjusted by monthly index ({month_idx:.2f}x)"
                )
            else:
                return None  # No useful historical signal

        # Adjust by lead-time pattern
        lead_time = ctx.get("lead_time", [])
        lead_adj = 0.0
        for lt in lead_time:
            bucket = lt["bucket"]
            if bucket == "0-7d" and days_to_checkin <= 7:
                lead_adj = lt["avg_daily_change_pct"] * days_to_checkin
                reasoning_parts.append(f"Lead-time ({bucket}): {lead_adj:+.1f}% typical")
                break
            elif bucket == "8-14d" and 8 <= days_to_checkin <= 14:
                lead_adj = lt["avg_daily_change_pct"] * days_to_checkin
                reasoning_parts.append(f"Lead-time ({bucket}): {lead_adj:+.1f}% typical")
                break
            elif bucket == "15-30d" and 15 <= days_to_checkin <= 30:
                lead_adj = lt["avg_daily_change_pct"] * days_to_checkin
                reasoning_parts.append(f"Lead-time ({bucket}): {lead_adj:+.1f}% typical")
                break
            elif bucket == "31-60d" and 31 <= days_to_checkin <= 60:
                lead_adj = lt["avg_daily_change_pct"] * days_to_checkin
                reasoning_parts.append(f"Lead-time ({bucket}): {lead_adj:+.1f}% typical")
                break
            elif bucket == "60+d" and days_to_checkin > 60:
                lead_adj = lt["avg_daily_change_pct"] * min(days_to_checkin, 90)
                reasoning_parts.append(f"Lead-time ({bucket}): {lead_adj:+.1f}% typical")
                break

        predicted = base_price * (1 + lead_adj / 100)

        # Adjust by DOW pattern
        dow_data = ctx.get("day_of_week", {})
        dow_index = dow_data.get("dow_index", {})
        try:
            target_dow = pd.Timestamp(date_from).dayofweek
            dow_adj = dow_index.get(target_dow, 0)
            if abs(dow_adj) > 0.5:
                predicted *= (1 + dow_adj / 100)
                reasoning_parts.append(f"DOW pattern: {dow_adj:+.1f}% for day {target_dow}")
        except Exception:
            pass

        data_quality = ctx.get("data_quality", 0)
        confidence = min(data_quality, 0.8)

        return {
            "source": "historical_pattern",
            "predicted_price": round(predicted, 2),
            "confidence": confidence,
            "reasoning": "; ".join(reasoning_parts) if reasoning_parts else "Historical pattern",
        }

    def _get_ml_signal(
        self,
        hotel_id: int,
        days_to_checkin: int,
        current_price: float = 0,
        date_from=None,
        enrichments: Enrichments | None = None,
    ) -> dict | None:
        """Signal 3: ML forecast from trained LightGBM model.

        Supports both lightweight direct-LightGBM models (type=lightgbm_direct)
        and legacy Darts models.
        """
        if self.ml_models_dir is None:
            return None

        model_path = self.ml_models_dir / f"price_model_{hotel_id}.pkl"
        if not model_path.exists():
            return None

        try:
            import pickle
            with open(model_path, "rb") as f:
                model_data = pickle.load(f)

            # ── Lightweight LightGBM model ──
            if isinstance(model_data, dict) and model_data.get("type") == "lightgbm_direct":
                model = model_data["model"]
                feature_cols = model_data["feature_cols"]
                price_mean = model_data.get("price_mean", current_price)

                # Build feature vector from what's available at prediction time
                import numpy as np
                from datetime import datetime as dt

                features = {}

                # Calendar features from checkin date
                if date_from:
                    try:
                        checkin = pd.to_datetime(date_from)
                        features["day_of_week"] = checkin.dayofweek
                        features["month"] = checkin.month
                        features["is_weekend"] = 1 if checkin.dayofweek >= 5 else 0
                    except Exception:
                        pass

                # Price-based features
                if current_price > 0:
                    features["price_lag_1"] = current_price
                    features["price_lag_3"] = current_price
                    features["price_lag_7"] = current_price
                    features["price_lag_14"] = current_price
                    features["price_lag_28"] = current_price
                    features["price_rolling_mean_7"] = current_price
                    features["price_rolling_std_7"] = 0
                    features["price_rolling_mean_14"] = current_price
                    features["price_rolling_std_14"] = 0
                    features["price_rolling_mean_28"] = current_price
                    features["price_rolling_std_28"] = 0
                    features["price_min"] = current_price
                    features["price_max"] = current_price
                    features["price_std"] = 0
                    if price_mean > 0:
                        features["price_vs_market"] = current_price / price_mean

                # Enrichment features
                if enrichments:
                    features["price_update_velocity"] = enrichments.price_velocity
                    features["cancellation_rate"] = enrichments.cancellation_risk
                    features["star_rating"] = enrichments.competitor_pressure  # proxy

                # Build feature array in correct order
                feature_arr = np.array([[features.get(c, 0) for c in feature_cols]])
                predicted_price = float(model.predict(feature_arr)[0])

                # Sanity check: clamp to reasonable range
                if current_price > 0:
                    predicted_price = max(predicted_price, current_price * 0.5)
                    predicted_price = min(predicted_price, current_price * 2.0)

                return {
                    "source": "ml_forecast",
                    "predicted_price": round(predicted_price, 2),
                    "confidence": 0.5,
                    "reasoning": f"LightGBM model ({len(feature_cols)} features) for hotel {hotel_id}",
                }

            # ── Legacy Darts model (requires darts library) ──
            else:
                from src.models.forecaster import HotelPriceForecaster
                forecaster = HotelPriceForecaster.load(model_path)
                pred_df = forecaster.predict(n_days=days_to_checkin)

                if pred_df.empty:
                    return None

                predicted_price = float(pred_df.iloc[-1]["predicted_price"])
                return {
                    "source": "ml_forecast",
                    "predicted_price": predicted_price,
                    "confidence": 0.5,
                    "reasoning": f"Darts {forecaster.model_name} model for hotel {hotel_id}",
                }

        except Exception as e:
            logger.debug("ML signal unavailable for hotel %d: %s", hotel_id, e)
            return None

    # ── Weight computation ───────────────────────────────────────────

    def _compute_weights(self, signals: list[dict]) -> list[float]:
        """Dynamically compute signal weights based on availability and confidence."""
        if len(signals) == 1:
            return [1.0]

        raw_weights = []
        for s in signals:
            source = s["source"]
            base_w = self.DEFAULT_WEIGHTS.get(source, 0.1)
            # Scale by confidence
            w = base_w * (0.5 + 0.5 * s["confidence"])
            raw_weights.append(w)

        # Normalize to sum to 1.0
        total = sum(raw_weights)
        if total <= 0:
            return [1.0 / len(signals)] * len(signals)

        return [w / total for w in raw_weights]

    # ── YoY comparison ───────────────────────────────────────────────

    def _build_yoy_comparison(
        self,
        hotel_id: int,
        category: str,
        current_price: float,
        date_from: str,
    ) -> dict | None:
        """Compare current price to same period last year."""
        try:
            target_date = pd.Timestamp(date_from)
            target_month = target_date.month
        except Exception:
            return None

        ctx = self._get_context(hotel_id, category)
        if not ctx:
            return None

        same_period = ctx.get("same_period", {}).get(target_month, {})
        prior_avg = same_period.get("avg_price")

        if prior_avg is None or prior_avg <= 0:
            return None

        yoy_change = (current_price - prior_avg) / prior_avg * 100

        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

        return {
            "period": month_names[target_month],
            "prior_avg_price": round(prior_avg, 2),
            "prior_median_price": same_period.get("median_price"),
            "current_price": round(current_price, 2),
            "yoy_change_pct": round(yoy_change, 1),
            "data_source": same_period.get("data_source", "unknown"),
            "n_observations": same_period.get("n_observations", 0),
        }

    # ── Explanation builder ──────────────────────────────────────────

    def _build_explanation(
        self,
        signals: list[dict],
        weights: list[float],
        yoy: dict | None,
        context: dict | None,
        momentum: dict,
        regime: dict,
        enrichments: Enrichments,
        date_from: str,
    ) -> dict:
        """Build human-readable explanation of the prediction."""
        factors = []

        # Main prediction driver
        primary = max(zip(signals, weights), key=lambda x: x[1])
        primary_signal, primary_weight = primary

        # Signal-based factors
        for signal, weight in zip(signals, weights):
            if weight < 0.05:
                continue
            factors.append({
                "factor": signal["source"].replace("_", " ").title(),
                "effect": f"${signal['predicted_price']:.0f} (weight: {weight:.0%})",
                "detail": signal.get("reasoning", ""),
            })

        # YoY factor
        if yoy and yoy.get("yoy_change_pct") is not None:
            direction = "higher" if yoy["yoy_change_pct"] > 0 else "lower"
            factors.append({
                "factor": "Year-over-year",
                "effect": f"{yoy['yoy_change_pct']:+.1f}%",
                "detail": f"Current price is {abs(yoy['yoy_change_pct']):.1f}% {direction} "
                          f"than same period average (${yoy['prior_avg_price']:.0f})",
            })

        # Event factor
        try:
            target_date = pd.Timestamp(date_from)
            event_adj = enrichments.get_event_daily_adj(target_date)
            if abs(event_adj) > 0.01:
                factors.append({
                    "factor": "Events",
                    "effect": f"{event_adj:+.2f}%/day",
                    "detail": "Active event near check-in date affecting prices",
                })
        except Exception:
            pass

        # Momentum factor
        mom_signal = momentum.get("signal", "NORMAL")
        if mom_signal not in ("NORMAL", "INSUFFICIENT_DATA"):
            direction = "upward" if "UP" in mom_signal else "downward"
            factors.append({
                "factor": "Momentum",
                "effect": direction,
                "detail": f"Price moving {direction} faster than expected "
                          f"(strength: {momentum.get('strength', 0):.0%})",
            })

        # Regime factor
        regime_name = regime.get("regime", "NORMAL")
        if regime_name != "NORMAL":
            factors.append({
                "factor": "Price behavior",
                "effect": regime_name.replace("_", " ").title(),
                "detail": regime.get("description", ""),
            })

        # Lead-time factor
        if context:
            lead_time = context.get("lead_time", [])
            for lt in lead_time:
                avg_change = lt["avg_daily_change_pct"]
                if abs(avg_change) > 0.05:
                    direction = "rise" if avg_change > 0 else "fall"
                    factors.append({
                        "factor": "Lead-time pattern",
                        "effect": f"{avg_change:+.2f}%/day in {lt['bucket']}",
                        "detail": f"Prices typically {direction} {abs(avg_change):.2f}%/day "
                                  f"in the {lt['bucket']} window before check-in",
                    })
                    break  # Only show the most relevant bucket

        # Monthly seasonality
        if context:
            monthly_idx = context.get("monthly_index", {})
            try:
                month_num = pd.Timestamp(date_from).month
                idx = monthly_idx.get(month_num, 1.0)
                if abs(idx - 1.0) > 0.05:
                    direction = "above" if idx > 1.0 else "below"
                    factors.append({
                        "factor": "Monthly seasonality",
                        "effect": f"{idx:.2f}x average",
                        "detail": f"This month's prices are typically "
                                  f"{abs(idx - 1) * 100:.0f}% {direction} annual average",
                    })
            except Exception:
                pass

        # Build summary
        ensemble_price = sum(s["predicted_price"] * w for s, w in zip(signals, weights))
        direction = "rise" if ensemble_price > signals[0].get("predicted_price", 0) * 0.5 else "fall"
        change_pct = (ensemble_price / max(signals[0].get("predicted_price", 1), 1) - 1) * 100

        # Confidence statement
        avg_confidence = sum(s["confidence"] * w for s, w in zip(signals, weights))
        if avg_confidence > 0.6:
            confidence_stmt = "High confidence — backed by strong historical data and curve density"
        elif avg_confidence > 0.3:
            confidence_stmt = "Medium confidence — some historical data available"
        else:
            confidence_stmt = "Low confidence — limited historical data, prediction is approximate"

        summary = f"Prediction based on {len(signals)} signal{'s' if len(signals) > 1 else ''}"
        if yoy and yoy.get("yoy_change_pct") is not None:
            summary += f", {abs(yoy['yoy_change_pct']):.0f}% {'above' if yoy['yoy_change_pct'] > 0 else 'below'} last year"

        return {
            "summary": summary,
            "factors": factors,
            "confidence_statement": confidence_stmt,
            "n_signals": len(signals),
        }

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_context(self, hotel_id: int, category: str) -> dict | None:
        """Get historical context for a hotel+category combo."""
        key = (hotel_id, str(category).lower())
        return self.historical_patterns.get(key)

    def _empty_prediction(
        self,
        current_price: float,
        date_from,
        days_to_checkin: int,
    ) -> dict:
        """Return a minimal prediction for rooms with T<=0."""
        return {
            "current_price": current_price,
            "date_from": str(date_from),
            "days_to_checkin": days_to_checkin,
            "predicted_checkin_price": current_price,
            "expected_change_pct": 0,
            "probability": {"up": 30, "down": 30, "stable": 40},
            "cancel_probability": None,
            "model_type": "none",
            "daily": [],
            "confidence_quality": "low",
            "forward_curve": [],
            "prediction_method": "none",
            "signals": [],
            "yoy_comparison": None,
            "explanation": {"summary": "Check-in is today or past", "factors": [], "confidence_statement": "", "n_signals": 0},
        }
