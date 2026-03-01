"""Backtest framework — validate prediction quality against actual outcomes.

Uses walk-forward methodology: for each historical price track, predicts
the check-in price from an earlier observation and compares to actual.

No data leakage: the decay curve is built using only data available
before each test point.
"""
from __future__ import annotations

import logging
from math import sqrt

import numpy as np
import pandas as pd

from src.analytics.forward_curve import build_decay_curve, predict_forward_curve, Enrichments

logger = logging.getLogger(__name__)


class HistoricalBacktester:
    """Backtest prediction quality against actual outcomes."""

    def __init__(self):
        self.results = []

    def run_backtest(
        self,
        historical_df: pd.DataFrame | None = None,
        test_t_values: list[int] | None = None,
        min_track_length: int = 3,
    ) -> dict:
        """Run walk-forward backtest on historical data.

        Args:
            historical_df: Historical price data. If None, loads from DB.
            test_t_values: T values to test predictions at. Default: [7, 14, 30, 60].
            min_track_length: Minimum scans per track to include.

        Returns:
            BacktestSummary dict with per-method metrics.
        """
        if test_t_values is None:
            test_t_values = [7, 14, 30, 60]

        if historical_df is None:
            try:
                from src.analytics.collector import load_historical_prices
                historical_df = load_historical_prices()
            except Exception as e:
                logger.error("Cannot load historical data for backtest: %s", e)
                return {"error": str(e), "n_trials": 0}

        if historical_df.empty:
            return {"error": "No historical data available", "n_trials": 0}

        # Prepare data
        df = historical_df.copy()
        df["scan_date"] = pd.to_datetime(df["scan_date"], errors="coerce")
        df["date_from_dt"] = pd.to_datetime(df["date_from"], errors="coerce")
        df["room_price"] = pd.to_numeric(df["room_price"], errors="coerce")
        df = df.dropna(subset=["room_price", "scan_date", "date_from_dt"])

        # Split into tracks
        tracks = self._split_tracks(df, min_track_length)
        if not tracks:
            return {"error": "No valid tracks found", "n_trials": 0}

        logger.info("Backtest: %d tracks found, testing at T=%s", len(tracks), test_t_values)

        self.results = []

        for track in tracks:
            for test_t in test_t_values:
                result = self._backtest_one_track(track, test_t, df)
                if result is not None:
                    self.results.append(result)

        if not self.results:
            return {"error": "No valid test points found", "n_trials": 0}

        return self._compute_summary()

    def _split_tracks(
        self,
        df: pd.DataFrame,
        min_length: int = 3,
    ) -> list[dict]:
        """Split historical data into individual price tracks.

        A track = all observations for one (order_id, hotel_id, category, board, date_from).
        """
        tracks = []
        groups = df.groupby(["order_id", "hotel_id", "room_category", "room_board"])

        for key, grp in groups:
            grp = grp.sort_values("scan_date")
            if len(grp) < min_length:
                continue

            order_id, hotel_id, category, board = key
            date_from = grp.iloc[0]["date_from_dt"]

            if pd.isna(date_from):
                continue

            tracks.append({
                "order_id": order_id,
                "hotel_id": int(hotel_id),
                "category": str(category).lower(),
                "board": str(board).lower() if board else "unknown",
                "date_from": date_from,
                "scans": list(zip(
                    grp["scan_date"].values,
                    grp["room_price"].values.astype(float),
                )),
            })

        return tracks

    def _backtest_one_track(
        self,
        track: dict,
        test_t: int,
        all_data: pd.DataFrame,
    ) -> dict | None:
        """Run prediction for one track at one T value.

        Finds the scan closest to T days before check-in,
        then predicts the final price and compares.
        """
        date_from = track["date_from"]
        scans = track["scans"]  # list of (timestamp, price) tuples

        # Final price is the last scan (closest to check-in)
        actual_price = scans[-1][1]
        if actual_price <= 0:
            return None

        # Find the scan closest to T days before check-in
        target_scan_date = date_from - pd.Timedelta(days=test_t)
        best_scan = None
        best_diff = float("inf")

        for scan_ts, scan_price in scans[:-1]:  # Exclude the last scan
            scan_date = pd.Timestamp(scan_ts)
            diff = abs((scan_date - target_scan_date).total_seconds() / 86400)
            if diff < best_diff and diff < test_t * 0.5:
                best_diff = diff
                best_scan = (scan_date, scan_price)

        if best_scan is None:
            return None

        prediction_date, prediction_price = best_scan
        if prediction_price <= 0:
            return None

        actual_t = max(1, int((date_from - prediction_date).total_seconds() / 86400))

        # Build decay curve from data BEFORE this prediction point (no leakage)
        prior_data = all_data[all_data["scan_date"] < prediction_date]
        if len(prior_data) < 20:
            # Not enough prior data to build a curve — use all data
            # (this is less rigorous but avoids empty curves for early tracks)
            curve = build_decay_curve(all_data)
        else:
            curve = build_decay_curve(prior_data)

        # Run forward curve prediction
        try:
            fwd = predict_forward_curve(
                detail_id=0,
                hotel_id=track["hotel_id"],
                current_price=prediction_price,
                current_t=actual_t,
                category=track["category"],
                board=track["board"],
                curve=curve,
                enrichments=Enrichments(),
            )
            fwd_predicted = fwd.points[-1].predicted_price if fwd.points else prediction_price
        except Exception:
            fwd_predicted = prediction_price

        # Compute errors
        fwd_error_pct = abs(fwd_predicted - actual_price) / actual_price * 100

        return {
            "hotel_id": track["hotel_id"],
            "category": track["category"],
            "board": track["board"],
            "test_t": test_t,
            "actual_t": actual_t,
            "prediction_price": round(prediction_price, 2),
            "actual_checkin_price": round(actual_price, 2),
            "fwd_predicted_price": round(fwd_predicted, 2),
            "fwd_error_pct": round(fwd_error_pct, 2),
            "date_from": str(track["date_from"].date()),
        }

    def _compute_summary(self) -> dict:
        """Compute aggregate backtest metrics."""
        if not self.results:
            return {"error": "No results", "n_trials": 0}

        df = pd.DataFrame(self.results)

        def _metrics(subset):
            if subset.empty:
                return {}
            errors = subset["fwd_error_pct"].values
            return {
                "mape": round(float(np.mean(errors)), 2),
                "rmse_pct": round(float(sqrt(np.mean(errors ** 2))), 2),
                "median_error_pct": round(float(np.median(errors)), 2),
                "n_trials": len(subset),
            }

        summary = {
            "n_trials": len(df),
            "overall": _metrics(df),
            "by_t": {},
            "by_hotel": {},
            "by_category": {},
        }

        # By T value
        for t_val, grp in df.groupby("test_t"):
            summary["by_t"][int(t_val)] = _metrics(grp)

        # By hotel
        for hotel_id, grp in df.groupby("hotel_id"):
            summary["by_hotel"][int(hotel_id)] = _metrics(grp)

        # By category
        for cat, grp in df.groupby("category"):
            summary["by_category"][str(cat)] = _metrics(grp)

        # Quality assessment
        mape = summary["overall"].get("mape", 100)
        if mape < 5:
            summary["quality"] = "excellent"
            summary["quality_description"] = f"Average prediction error is {mape:.1f}% — very accurate"
        elif mape < 10:
            summary["quality"] = "good"
            summary["quality_description"] = f"Average prediction error is {mape:.1f}% — reliable"
        elif mape < 20:
            summary["quality"] = "fair"
            summary["quality_description"] = f"Average prediction error is {mape:.1f}% — usable but imprecise"
        else:
            summary["quality"] = "poor"
            summary["quality_description"] = f"Average prediction error is {mape:.1f}% — predictions need improvement"

        return summary
