"""Price forecasting using Darts time series library."""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np
from darts import TimeSeries
from darts.models import (
    ExponentialSmoothing,
    XGBModel,
    LightGBMModel,
    NBEATSModel,
)
from darts.metrics import mape, rmse, mae
from darts.dataprocessing.transformers import Scaler
from sklearn.model_selection import TimeSeriesSplit

from config.settings import MODELS_DIR, FORECAST_HORIZON


class HotelPriceForecaster:
    """Multi-model hotel price forecaster using Darts."""

    AVAILABLE_MODELS = {
        "exponential_smoothing": ExponentialSmoothing,
        "xgboost": XGBModel,
        "lightgbm": LightGBMModel,
        "nbeats": NBEATSModel,
    }

    def __init__(self, model_name: str = "lightgbm", horizon: int = FORECAST_HORIZON):
        self.model_name = model_name
        self.horizon = horizon
        self.model = None
        self.scaler = Scaler()
        self.target_series = None
        self.covariate_series = None

    # Recommended covariate columns for hotel forecasting
    DEFAULT_COVARIATES = [
        "day_of_week", "month", "is_weekend", "is_holiday",
        "is_high_impact_holiday", "is_summer_vacation",
        "events_active_count", "event_impact_score",
        "temperature_max", "beach_weather_score",
        "star_price_multiplier", "is_coastal",
        "price_trend", "price_seasonal",
    ]

    def prepare_series(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        target_col: str = "price",
        covariate_cols: list[str] | None = None,
        future_covariate_cols: list[str] | None = None,
    ) -> tuple[TimeSeries, TimeSeries | None]:
        """Convert DataFrame to Darts TimeSeries objects.

        Args:
            df: DataFrame with date and price columns.
            date_col: Name of the date column.
            target_col: Name of the target (price) column.
            covariate_cols: Optional list of feature columns to use as covariates.

        Returns:
            Tuple of (target_series, covariate_series).
        """
        df = df.sort_values(date_col).reset_index(drop=True)

        # Target series
        self.target_series = TimeSeries.from_dataframe(
            df, time_col=date_col, value_cols=target_col, fill_missing_dates=True
        )
        # Fit scaler on training portion only to prevent data leakage
        train_portion = self.target_series[:len(self.target_series) - self.horizon]
        self.scaler.fit(train_portion)
        self.target_series = self.scaler.transform(self.target_series)

        # Past covariate series (known only historically)
        self.covariate_series = None
        if covariate_cols:
            valid_cols = [c for c in covariate_cols if c in df.columns]
            if valid_cols:
                cov_df = df[[date_col] + valid_cols].copy()
                cov_df[valid_cols] = cov_df[valid_cols].fillna(0)
                self.covariate_series = TimeSeries.from_dataframe(
                    cov_df, time_col=date_col, value_cols=valid_cols, fill_missing_dates=True
                )

        # Future covariate series (known ahead of time: holidays, events, weather forecasts)
        self.future_covariate_series = None
        if future_covariate_cols:
            valid_future = [c for c in future_covariate_cols if c in df.columns]
            if valid_future:
                fut_df = df[[date_col] + valid_future].copy()
                fut_df[valid_future] = fut_df[valid_future].fillna(0)
                self.future_covariate_series = TimeSeries.from_dataframe(
                    fut_df, time_col=date_col, value_cols=valid_future, fill_missing_dates=True
                )

        return self.target_series, self.covariate_series

    def train(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        target_col: str = "price",
        covariate_cols: list[str] | None = None,
        **model_kwargs,
    ) -> dict:
        """Train the forecasting model.

        Returns:
            Dict with training metrics.
        """
        target, covariates = self.prepare_series(df, date_col, target_col, covariate_cols)

        # Split: use last `horizon` days as validation
        train, val = target[:-self.horizon], target[-self.horizon:]

        # Build model
        model_class = self.AVAILABLE_MODELS[self.model_name]

        if self.model_name in ("xgboost", "lightgbm"):
            defaults = {
                "lags": 30,
                "lags_past_covariates": 14 if covariates else None,
                "output_chunk_length": self.horizon,
            }
            defaults.update(model_kwargs)
            self.model = model_class(**defaults)
        elif self.model_name == "nbeats":
            defaults = {
                "input_chunk_length": 30,
                "output_chunk_length": self.horizon,
                "n_epochs": 50,
            }
            defaults.update(model_kwargs)
            self.model = model_class(**defaults)
        else:
            self.model = model_class(**model_kwargs)

        # Train
        fit_kwargs = {}
        if covariates and self.model_name in ("xgboost", "lightgbm"):
            fit_kwargs["past_covariates"] = covariates
        self.model.fit(train, **fit_kwargs)

        # Validate
        pred = self.model.predict(self.horizon)
        pred_rescaled = self.scaler.inverse_transform(pred)
        val_rescaled = self.scaler.inverse_transform(val)

        metrics = {
            "mape": float(mape(val_rescaled, pred_rescaled)),
            "rmse": float(rmse(val_rescaled, pred_rescaled)),
            "mae": float(mae(val_rescaled, pred_rescaled)),
        }

        return metrics

    def train_auto(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        target_col: str = "price",
        **model_kwargs,
    ) -> dict:
        """Train with automatic covariate detection from available columns."""
        available = [c for c in self.DEFAULT_COVARIATES if c in df.columns]
        return self.train(df, date_col, target_col, covariate_cols=available or None, **model_kwargs)

    def train_multi_hotel(
        self,
        df: pd.DataFrame,
        hotel_col: str = "hotel_id",
        date_col: str = "date",
        target_col: str = "price",
    ) -> dict[str, dict]:
        """Train separate models per hotel. Returns metrics per hotel."""
        results = {}
        hotels = df[hotel_col].unique()

        for hotel_id in hotels:
            hotel_df = df[df[hotel_col] == hotel_id].copy()
            if len(hotel_df) < self.horizon * 2:
                results[str(hotel_id)] = {"error": "Not enough data"}
                continue

            try:
                metrics = self.train_auto(hotel_df, date_col, target_col)
                self.save(name=f"price_model_{hotel_id}")
                metrics["hotel_id"] = str(hotel_id)
                results[str(hotel_id)] = metrics
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Training failed for hotel %s: %s", hotel_id, e)
                results[str(hotel_id)] = {"error": str(e)}

        return results

    def predict(
        self,
        n_days: int | None = None,
        include_intervals: bool = False,
        confidence_levels: list[float] | None = None,
    ) -> pd.DataFrame:
        """Generate price predictions for the next n_days.

        Args:
            include_intervals: If True, include confidence interval columns.
            confidence_levels: Confidence levels (default [0.80, 0.95]).
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        if include_intervals:
            return self.predict_with_intervals(n_days, confidence_levels)

        horizon = n_days or self.horizon
        pred = self.model.predict(horizon)
        pred_rescaled = self.scaler.inverse_transform(pred)

        result = pred_rescaled.pd_dataframe().reset_index()
        result.columns = ["date", "predicted_price"]
        return result

    def predict_with_intervals(
        self,
        n_days: int | None = None,
        confidence_levels: list[float] | None = None,
    ) -> pd.DataFrame:
        """Generate predictions with confidence intervals (80%, 95%).

        Uses probabilistic forecasting for Darts models that support it,
        or residual bootstrap for tree-based models.
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        horizon = n_days or self.horizon
        confidence_levels = confidence_levels or [0.80, 0.95]

        # Point prediction
        pred = self.model.predict(horizon)
        pred_rescaled = self.scaler.inverse_transform(pred)
        result = pred_rescaled.pd_dataframe().reset_index()
        result.columns = ["date", "predicted_price"]

        for level in confidence_levels:
            lower_q = (1 - level) / 2
            upper_q = 1 - lower_q
            pct = int(level * 100)

            try:
                lower, upper = self._compute_intervals(
                    horizon, lower_q, upper_q
                )
                result[f"lower_{pct}"] = lower
                result[f"upper_{pct}"] = upper
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Interval computation failed for level %s: %s", level, e)
                # Fallback: percentage-based intervals
                width = (1 - level) * 0.5
                result[f"lower_{pct}"] = result["predicted_price"] * (1 - width)
                result[f"upper_{pct}"] = result["predicted_price"] * (1 + width)

        return result

    def _compute_intervals(
        self,
        horizon: int,
        lower_quantile: float,
        upper_quantile: float,
        n_samples: int = 200,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute prediction intervals using the best available method."""
        if self.model_name in ("exponential_smoothing", "nbeats"):
            # Darts probabilistic: use num_samples
            pred = self.model.predict(horizon, num_samples=n_samples)
            pred_rescaled = self.scaler.inverse_transform(pred)
            lower = pred_rescaled.quantile_df(lower_quantile).values.flatten()
            upper = pred_rescaled.quantile_df(upper_quantile).values.flatten()
            return lower, upper
        else:
            # Residual bootstrap for tree-based models
            return self._bootstrap_intervals(horizon, lower_quantile, upper_quantile, n_samples)

    def _bootstrap_intervals(
        self,
        horizon: int,
        lower_quantile: float,
        upper_quantile: float,
        n_bootstrap: int = 200,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Bootstrap prediction intervals for XGBoost/LightGBM.

        Resamples training residuals and adds them to point predictions.
        """
        # Point prediction
        pred = self.model.predict(horizon)
        point_vals = self.scaler.inverse_transform(pred).values().flatten()

        # Compute in-sample residuals
        if self.target_series is not None and len(self.target_series) > horizon + 30:
            try:
                historical = self.model.historical_forecasts(
                    self.target_series,
                    start=max(30, len(self.target_series) - 100),
                    forecast_horizon=1,
                    stride=1,
                    retrain=False,
                    verbose=False,
                )
                hist_rescaled = self.scaler.inverse_transform(historical)
                actual_slice = self.scaler.inverse_transform(
                    self.target_series[-len(hist_rescaled):]
                )
                residuals = (
                    actual_slice.values().flatten()
                    - hist_rescaled.values().flatten()
                )
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Historical forecast failed, using fallback residuals: %s", e)
                # Fallback: estimate residuals as 10% of price std
                residuals = point_vals.mean() * 0.10 * np.random.randn(100)
        else:
            residuals = point_vals.mean() * 0.10 * np.random.randn(100)

        # Bootstrap
        bootstrap_preds = np.zeros((n_bootstrap, horizon))
        for i in range(n_bootstrap):
            sampled = np.random.choice(residuals, size=horizon, replace=True)
            bootstrap_preds[i] = point_vals + sampled

        lower = np.quantile(bootstrap_preds, lower_quantile, axis=0)
        upper = np.quantile(bootstrap_preds, upper_quantile, axis=0)
        return lower, upper

    def backtest(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        target_col: str = "price",
        n_splits: int = 3,
    ) -> list[dict]:
        """Run time-series cross-validation."""
        target, _ = self.prepare_series(df, date_col, target_col)

        tscv = TimeSeriesSplit(n_splits=n_splits)
        series_values = target.values().flatten()
        results = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(series_values)):
            train_series = target[:len(train_idx)]
            val_series = target[len(train_idx):len(train_idx) + len(val_idx)]

            model_class = self.AVAILABLE_MODELS[self.model_name]
            if self.model_name in ("xgboost", "lightgbm"):
                model = model_class(lags=30, output_chunk_length=min(len(val_idx), self.horizon))
            else:
                model = model_class()

            model.fit(train_series)
            pred = model.predict(len(val_idx))

            pred_r = self.scaler.inverse_transform(pred)
            val_r = self.scaler.inverse_transform(val_series)

            results.append({
                "fold": fold,
                "mape": float(mape(val_r, pred_r)),
                "rmse": float(rmse(val_r, pred_r)),
                "mae": float(mae(val_r, pred_r)),
            })

        return results

    def save(self, name: str = "price_model") -> Path:
        """Save the trained model to disk."""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        path = MODELS_DIR / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "scaler": self.scaler,
                "model_name": self.model_name,
                "horizon": self.horizon,
            }, f)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "HotelPriceForecaster":
        """Load a saved model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        forecaster = cls(model_name=data["model_name"], horizon=data["horizon"])
        forecaster.model = data["model"]
        forecaster.scaler = data["scaler"]
        return forecaster


def compare_models(
    df: pd.DataFrame,
    date_col: str = "date",
    target_col: str = "price",
    models: list[str] | None = None,
) -> pd.DataFrame:
    """Train and compare multiple models, returning metrics for each."""
    if models is None:
        models = ["exponential_smoothing", "xgboost", "lightgbm"]

    results = []
    for model_name in models:
        forecaster = HotelPriceForecaster(model_name=model_name)
        try:
            metrics = forecaster.train(df, date_col, target_col)
            metrics["model"] = model_name
            results.append(metrics)
        except (ValueError, TypeError, RuntimeError) as e:
            logger.warning("Model comparison failed for %s: %s", model_name, e)
            results.append({"model": model_name, "error": str(e)})

    return pd.DataFrame(results)
