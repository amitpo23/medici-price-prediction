"""Prophet Voter — Time series forecasting voter for consensus engine.

Uses Facebook Prophet to forecast hotel room prices based on historical
scan data. Returns CALL/PUT/NEUTRAL vote like all other consensus voters.

This is voter #12 — additive to existing 11 voters, does not replace anything.
Falls back to NEUTRAL if insufficient data (<30 points) or if Prophet unavailable.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

PRICE_SCANS_DB = Path("data/price_scans.db")
MIN_DATA_POINTS = 30
FORECAST_HORIZON_DAYS = 14


def _load_price_history(venue_id: int, category: str = None,
                        db_path: Path = PRICE_SCANS_DB) -> list[dict]:
    """Load price scan history from SQLite. Returns [{ds, y}] for Prophet."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        # Try common table structures
        for table in ["price_scans", "scan_history", "prices"]:
            try:
                query = f"SELECT scan_date, price FROM {table} WHERE venue_id = ?"
                params = [venue_id]
                if category:
                    query += " AND category = ?"
                    params.append(category)
                query += " ORDER BY scan_date"

                rows = conn.execute(query, params).fetchall()
                if rows:
                    return [{"ds": r[0], "y": float(r[1])} for r in rows if r[1]]
            except sqlite3.OperationalError:
                continue
        return []
    finally:
        conn.close()


def prophet_forecast(venue_id: int, category: str = None,
                     horizon_days: int = FORECAST_HORIZON_DAYS) -> dict:
    """Run Prophet forecast for a hotel room.

    Returns:
        {
            "forecast": [{ds, yhat, yhat_lower, yhat_upper}],
            "current_trend": "rising" | "falling" | "flat",
            "predicted_price": float,
            "confidence": float (0-1),
        }
    """
    try:
        from prophet import Prophet
        import pandas as pd
    except ImportError:
        logger.debug("Prophet not installed — returning empty forecast")
        return {"forecast": [], "current_trend": "flat", "predicted_price": None, "confidence": 0}

    history = _load_price_history(venue_id, category)
    if len(history) < MIN_DATA_POINTS:
        logger.debug("Prophet: insufficient data for venue %d (%d points)", venue_id, len(history))
        return {"forecast": [], "current_trend": "flat", "predicted_price": None, "confidence": 0}

    try:
        df = pd.DataFrame(history)
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.dropna(subset=["y"])
        df = df[df["y"] > 0]

        if len(df) < MIN_DATA_POINTS:
            return {"forecast": [], "current_trend": "flat", "predicted_price": None, "confidence": 0}

        # Fit Prophet model
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
            seasonality_mode="multiplicative",
        )
        model.fit(df)

        # Forecast
        future = model.make_future_dataframe(periods=horizon_days)
        forecast = model.predict(future)

        # Extract future predictions only
        future_mask = forecast["ds"] > df["ds"].max()
        future_fc = forecast[future_mask][["ds", "yhat", "yhat_lower", "yhat_upper"]]

        fc_list = [
            {
                "ds": row["ds"].strftime("%Y-%m-%d"),
                "yhat": round(row["yhat"], 2),
                "yhat_lower": round(row["yhat_lower"], 2),
                "yhat_upper": round(row["yhat_upper"], 2),
            }
            for _, row in future_fc.iterrows()
        ]

        # Determine trend from last 7 days of forecast
        if len(fc_list) >= 2:
            first_price = fc_list[0]["yhat"]
            last_price = fc_list[-1]["yhat"]
            change_pct = (last_price - first_price) / first_price * 100 if first_price else 0
            trend = "rising" if change_pct > 1.5 else "falling" if change_pct < -1.5 else "flat"
        else:
            trend = "flat"

        predicted_price = fc_list[-1]["yhat"] if fc_list else None

        # Confidence based on data density and forecast interval width
        current_price = df["y"].iloc[-1]
        if predicted_price and current_price:
            interval_width = (fc_list[-1]["yhat_upper"] - fc_list[-1]["yhat_lower"]) / current_price
            confidence = max(0.2, min(0.9, 1.0 - interval_width))
        else:
            confidence = 0.3

        return {
            "forecast": fc_list,
            "current_trend": trend,
            "predicted_price": predicted_price,
            "confidence": round(confidence, 2),
        }

    except Exception as exc:
        logger.warning("Prophet forecast failed for venue %d: %s", venue_id, exc)
        return {"forecast": [], "current_trend": "flat", "predicted_price": None, "confidence": 0}


def prophet_vote(venue_id: int, current_price: float,
                 category: str = None) -> dict:
    """Generate CALL/PUT/NEUTRAL vote from Prophet forecast.

    Returns:
        {
            "vote": "CALL" | "PUT" | "NEUTRAL",
            "confidence": float,
            "predicted_price": float | None,
            "trend": str,
            "voter_name": "prophet",
        }
    """
    result = prophet_forecast(venue_id, category)

    if not result["predicted_price"] or not current_price:
        return {
            "vote": "NEUTRAL",
            "confidence": 0,
            "predicted_price": None,
            "trend": "flat",
            "voter_name": "prophet",
        }

    predicted = result["predicted_price"]
    change_pct = (predicted - current_price) / current_price * 100

    # CALL if Prophet predicts >2% rise, PUT if >2% drop
    if change_pct > 2.0:
        vote = "CALL"
    elif change_pct < -2.0:
        vote = "PUT"
    else:
        vote = "NEUTRAL"

    return {
        "vote": vote,
        "confidence": result["confidence"],
        "predicted_price": predicted,
        "trend": result["current_trend"],
        "voter_name": "prophet",
    }


def get_prophet_chart_series(venue_id: int, category: str = None) -> list[dict]:
    """Get Prophet forecast as chart series [{t, v}] for trading chart."""
    result = prophet_forecast(venue_id, category)
    return [{"t": p["ds"], "v": p["yhat"]} for p in result.get("forecast", [])]
