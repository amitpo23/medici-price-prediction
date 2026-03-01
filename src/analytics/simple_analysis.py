"""Simplified analysis output — human-readable wrapper over raw analysis.

Transforms the deeply nested analysis dict from run_analysis() into
a clear, flat, jargon-free format with 4 sections:
  1. Executive Summary — one-paragraph overview
  2. Predictions — per-room simplified predictions
  3. Attention Items — rooms that need action
  4. Market Overview — portfolio-level statistics
"""
from __future__ import annotations


def simplify_analysis(analysis: dict) -> dict:
    """Transform raw analysis output into a simplified, readable format.

    Args:
        analysis: The dict returned by run_analysis().

    Returns:
        Dict with 4 sections: summary, predictions, attention, market.
    """
    if "error" in analysis:
        return {"summary": analysis["error"], "predictions": [], "attention": [], "market": {}}

    predictions_raw = analysis.get("predictions", {})
    statistics = analysis.get("statistics", {})
    model_info = analysis.get("model_info", {})

    # Build simplified predictions
    predictions = []
    for detail_id, pred in predictions_raw.items():
        predictions.append(format_prediction_summary(detail_id, pred))

    # Sort: attention-worthy items first, then by expected change magnitude
    predictions.sort(key=lambda p: (
        0 if p["status"] != "NORMAL" else 1,
        -abs(p["expected_change_pct"]),
    ))

    # Extract attention items
    attention = format_attention_items(predictions_raw)

    return {
        "summary": get_executive_summary(analysis),
        "predictions": predictions,
        "attention": attention,
        "market": _format_market_overview(statistics),
        "run_ts": analysis.get("run_ts", ""),
    }


def format_prediction_summary(detail_id, prediction: dict) -> dict:
    """Simplify a single room prediction into plain language.

    Translates trading jargon into simple labels:
      - momentum signal → price trend (RISING/FALLING/STABLE)
      - regime → status (NORMAL/WATCH/WARNING)
      - confidence_quality → confidence (HIGH/MEDIUM/LOW)
    """
    current_price = prediction.get("current_price", 0)
    predicted_price = prediction.get("predicted_checkin_price", current_price)
    change_pct = prediction.get("expected_change_pct", 0)
    days = prediction.get("days_to_checkin", 0)

    # Translate momentum signal to price trend
    momentum = prediction.get("momentum", {})
    mom_signal = momentum.get("signal", "NORMAL")
    trend = _translate_trend(mom_signal, change_pct)

    # Translate regime to status
    regime = prediction.get("regime", {})
    regime_name = regime.get("regime", "NORMAL")
    status = _translate_status(regime_name, regime.get("alert_level", "none"))

    # Translate confidence quality
    confidence = prediction.get("confidence_quality", "medium").upper()

    # Price direction description
    price_diff = predicted_price - current_price
    if abs(change_pct) < 1:
        direction_text = "Price expected to remain stable"
    elif change_pct > 0:
        direction_text = f"Price expected to increase ~${abs(price_diff):.0f} by check-in"
    else:
        direction_text = f"Price expected to decrease ~${abs(price_diff):.0f} by check-in"

    # Probability info
    probability = prediction.get("probability", {})

    return {
        "detail_id": int(detail_id),
        "hotel_name": prediction.get("hotel_name", ""),
        "hotel_id": prediction.get("hotel_id"),
        "category": prediction.get("category", ""),
        "board": prediction.get("board", ""),
        "current_price": round(current_price, 2),
        "predicted_price": round(predicted_price, 2),
        "expected_change_pct": round(change_pct, 1),
        "price_change_dollar": round(price_diff, 2),
        "date_from": prediction.get("date_from", ""),
        "days_to_checkin": days,
        "trend": trend,
        "status": status,
        "confidence": confidence,
        "direction": direction_text,
        "prob_up": probability.get("up"),
        "prob_down": probability.get("down"),
        "prob_stable": probability.get("stable"),
        "cancel_probability": prediction.get("cancel_probability"),
        # Deep predictor enrichments
        "prediction_method": prediction.get("prediction_method", "forward_curve_only"),
        "yoy_comparison": _format_yoy(prediction.get("yoy_comparison")),
        "explanation": _format_explanation(prediction.get("explanation")),
        "signals": prediction.get("signals", []),
    }


def format_attention_items(predictions: dict) -> list[dict]:
    """Extract rooms that need attention with clear action items.

    Flags rooms where:
      - Price is dropping significantly (>5% expected decrease)
      - Regime is VOLATILE, TRENDING_DOWN, or STALE
      - Momentum is ACCELERATING_DOWN
      - Check-in is very close (<7 days) with large expected change
    """
    items = []

    for detail_id, pred in predictions.items():
        change_pct = pred.get("expected_change_pct", 0)
        regime = pred.get("regime", {}).get("regime", "NORMAL")
        momentum_signal = pred.get("momentum", {}).get("signal", "NORMAL")
        days = pred.get("days_to_checkin", 999)
        current_price = pred.get("current_price", 0)
        predicted_price = pred.get("predicted_checkin_price", current_price)

        reason = None
        action = None
        urgency = "low"

        # Significant price drop expected
        if change_pct < -5:
            reason = f"Price DROPPING: ${current_price:.0f} -> ${predicted_price:.0f} ({change_pct:+.1f}%)"
            action = "Consider repricing or cancellation before price drops further"
            urgency = "high" if change_pct < -10 else "medium"

        # Volatile behavior
        elif regime == "VOLATILE":
            reason = "Price UNSTABLE: large swings between scans"
            action = "Monitor closely — price may jump up or down unexpectedly"
            urgency = "medium"

        # Trending down significantly
        elif regime == "TRENDING_DOWN":
            z = pred.get("regime", {}).get("z_score", 0)
            reason = f"Price trending below expected pattern"
            action = "Review pricing — room is underperforming expectations"
            urgency = "medium" if abs(z) > 3 else "low"

        # Stale prices
        elif regime == "STALE":
            reason = "Price STALE: no movement detected across many scans"
            action = "Verify data feed — price may not be updating correctly"
            urgency = "low"

        # Accelerating down
        elif momentum_signal == "ACCELERATING_DOWN":
            reason = "Price dropping FASTER than normal"
            action = "Price is accelerating downward — act quickly if selling"
            urgency = "medium"

        # Close check-in with significant change
        elif days < 7 and abs(change_pct) > 3:
            direction = "up" if change_pct > 0 else "down"
            reason = f"Check-in in {days} days, price moving {direction}"
            action = "Imminent check-in with price movement — review now"
            urgency = "high"

        if reason:
            items.append({
                "detail_id": int(detail_id),
                "hotel_name": pred.get("hotel_name", ""),
                "category": pred.get("category", ""),
                "board": pred.get("board", ""),
                "current_price": round(current_price, 2),
                "predicted_price": round(predicted_price, 2),
                "days_to_checkin": days,
                "reason": reason,
                "action": action,
                "urgency": urgency,
            })

    # Sort by urgency: high first, then medium, then low
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: urgency_order.get(x["urgency"], 99))

    return items


def get_executive_summary(analysis: dict) -> str:
    """Generate a one-paragraph executive summary in plain language."""
    stats = analysis.get("statistics", {})
    predictions = analysis.get("predictions", {})
    model_info = analysis.get("model_info", {})

    total_rooms = stats.get("total_rooms", 0)
    total_hotels = stats.get("total_hotels", 0)
    avg_price = stats.get("price_mean", 0)
    n_predictions = len(predictions)

    # Count attention items
    n_attention = 0
    for pred in predictions.values():
        regime = pred.get("regime", {}).get("regime", "NORMAL")
        change = pred.get("expected_change_pct", 0)
        if regime in ("VOLATILE", "TRENDING_DOWN", "STALE") or change < -5:
            n_attention += 1

    # Model source
    data_source = model_info.get("data_source", "default")
    total_tracks = model_info.get("total_tracks", 0)
    hist_summary = analysis.get("historical_patterns_summary", {})
    n_combos = hist_summary.get("n_combos", 0)

    if n_combos > 0 and total_tracks > 0:
        model_desc = (
            f"Deep prediction using {total_tracks} price tracks + "
            f"{n_combos} historical patterns (YoY, lead-time, events)"
        )
    elif data_source == "forward_curve" and total_tracks > 0:
        model_desc = f"Predictions based on {total_tracks} historical price tracks"
    else:
        model_desc = "Using default prediction model (no historical data yet)"

    # Build summary
    parts = [
        f"You have {total_rooms} rooms across {total_hotels} hotels.",
        f"Average price: ${avg_price:.0f}.",
    ]

    if n_predictions > 0:
        parts.append(f"{n_predictions} rooms have price predictions.")
    else:
        parts.append("No predictions available yet (need more data snapshots).")

    if n_attention > 0:
        parts.append(f"{n_attention} room{'s' if n_attention > 1 else ''} need{'s' if n_attention == 1 else ''} attention.")
    else:
        parts.append("All rooms are tracking normally.")

    parts.append(model_desc + ".")

    return " ".join(parts)


def simplify_to_text(analysis: dict) -> str:
    """Convert raw analysis to a plain text report.

    Suitable for quick reading in terminal, email, or chat.
    """
    simplified = simplify_analysis(analysis)

    lines = []
    lines.append("=" * 60)
    lines.append("MEDICI PRICE ANALYSIS REPORT")
    lines.append(f"Generated: {simplified.get('run_ts', 'N/A')}")
    lines.append("=" * 60)

    # Executive Summary
    lines.append("")
    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(simplified["summary"])

    # Attention Items (if any)
    attention = simplified.get("attention", [])
    if attention:
        lines.append("")
        lines.append(f"ATTENTION NEEDED ({len(attention)} items)")
        lines.append("-" * 40)
        for i, item in enumerate(attention, 1):
            lines.append(
                f"{i}. Room #{item['detail_id']} | {item['hotel_name']} | "
                f"{item['category']} | {item['board']}"
            )
            lines.append(f"   {item['reason']}")
            lines.append(f"   Current: ${item['current_price']:.0f} | "
                         f"Predicted: ${item['predicted_price']:.0f} | "
                         f"{item['days_to_checkin']} days to check-in")
            lines.append(f"   Action: {item['action']}")
            lines.append(f"   Urgency: {item['urgency'].upper()}")
            lines.append("")

    # Predictions
    predictions = simplified.get("predictions", [])
    if predictions:
        lines.append("")
        lines.append(f"PRICE PREDICTIONS ({len(predictions)} rooms)")
        lines.append("-" * 40)
        for pred in predictions:
            trend_icon = {"RISING": "+", "FALLING": "-", "STABLE": "="}
            icon = trend_icon.get(pred["trend"], "?")
            lines.append(
                f"[{icon}] Room #{pred['detail_id']} | {pred['hotel_name']} | "
                f"{pred['category']} | {pred['board']}"
            )
            lines.append(
                f"    Price: ${pred['current_price']:.0f} -> "
                f"${pred['predicted_price']:.0f} ({pred['expected_change_pct']:+.1f}%) | "
                f"Check-in: {pred['date_from']} ({pred['days_to_checkin']}d)"
            )
            lines.append(
                f"    Trend: {pred['trend']} | "
                f"Status: {pred['status']} | "
                f"Confidence: {pred['confidence']}"
            )
            lines.append(f"    {pred['direction']}")
            # YoY comparison
            yoy = pred.get("yoy_comparison")
            if yoy and yoy.get("text"):
                lines.append(f"    YoY: {yoy['text']}")
            # Explanation factors
            explanation = pred.get("explanation")
            if explanation and explanation.get("factors"):
                lines.append(f"    Why: {'; '.join(explanation['factors'][:3])}")
            lines.append("")

    # Market Overview
    market = simplified.get("market", {})
    if market:
        lines.append("")
        lines.append("MARKET OVERVIEW")
        lines.append("-" * 40)
        lines.append(
            f"Hotels: {market.get('total_hotels', 0)} | "
            f"Rooms: {market.get('total_rooms', 0)} | "
            f"Avg Price: ${market.get('avg_price', 0):.0f}"
        )
        lines.append(
            f"Price Range: ${market.get('price_min', 0):.0f} - "
            f"${market.get('price_max', 0):.0f} | "
            f"Avg Days to Check-in: {market.get('avg_days_to_checkin', 0):.0f}"
        )

        by_category = market.get("by_category", {})
        if by_category:
            lines.append("")
            lines.append("By Category:")
            for cat, info in by_category.items():
                lines.append(f"  {cat}: {info['count']} rooms, avg ${info['avg_price']:.0f}")

        by_board = market.get("by_board", {})
        if by_board:
            lines.append("")
            lines.append("By Board:")
            for board, info in by_board.items():
                lines.append(f"  {board}: {info['count']} rooms, avg ${info['avg_price']:.0f}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("END OF REPORT")
    lines.append("=" * 60)

    return "\n".join(lines)


# ── Private helpers ──────────────────────────────────────────────────

def _translate_trend(momentum_signal: str, change_pct: float) -> str:
    """Translate momentum signal to simple trend label."""
    if momentum_signal == "ACCELERATING_UP":
        return "RISING"
    if momentum_signal == "ACCELERATING_DOWN":
        return "FALLING"
    if momentum_signal in ("ACCELERATING",):
        return "RISING" if change_pct > 0 else "FALLING"
    if momentum_signal == "DECELERATING":
        return "STABLE"

    # Fall back to expected change direction
    if change_pct > 2:
        return "RISING"
    if change_pct < -2:
        return "FALLING"
    return "STABLE"


def _translate_status(regime: str, alert_level: str) -> str:
    """Translate regime to simple status label."""
    if regime in ("VOLATILE", "STALE"):
        return "WARNING"
    if regime in ("TRENDING_DOWN",):
        return "WATCH" if alert_level == "watch" else "WARNING"
    if regime in ("TRENDING_UP",):
        return "WATCH" if alert_level == "watch" else "NORMAL"
    return "NORMAL"


def _format_yoy(yoy: dict | None) -> dict | None:
    """Format YoY comparison into simple text."""
    if not yoy:
        return None
    return {
        "period": yoy.get("period", ""),
        "prior_avg_price": yoy.get("prior_avg_price"),
        "current_price": yoy.get("current_price"),
        "change_pct": yoy.get("yoy_change_pct"),
        "text": (
            f"Last {yoy.get('period', 'year')}: avg ${yoy.get('prior_avg_price', 0):.0f} "
            f"({yoy.get('yoy_change_pct', 0):+.1f}% YoY)"
            if yoy.get("prior_avg_price") else None
        ),
    }


def _format_explanation(explanation: dict | None) -> dict | None:
    """Format explanation into simple text."""
    if not explanation:
        return None
    factors = explanation.get("factors", [])
    if not factors:
        return None
    return {
        "summary": explanation.get("summary", ""),
        "confidence": explanation.get("confidence_statement", ""),
        "factors": [
            f"{f['factor']}: {f['effect']}" + (f" — {f['detail']}" if f.get("detail") else "")
            for f in factors[:5]  # Top 5 factors
        ],
    }


def _format_market_overview(statistics: dict) -> dict:
    """Format market statistics into a clean flat dict."""
    return {
        "total_rooms": statistics.get("total_rooms", 0),
        "total_hotels": statistics.get("total_hotels", 0),
        "avg_price": statistics.get("price_mean", 0),
        "median_price": statistics.get("price_median", 0),
        "price_min": statistics.get("price_min", 0),
        "price_max": statistics.get("price_max", 0),
        "avg_days_to_checkin": statistics.get("avg_days_to_checkin", 0),
        "nearest_checkin": statistics.get("nearest_checkin", ""),
        "farthest_checkin": statistics.get("farthest_checkin", ""),
        "total_inventory_value": statistics.get("total_inventory_value", 0),
        "by_category": statistics.get("by_category", {}),
        "by_board": statistics.get("by_board", {}),
    }
