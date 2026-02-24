"""Price forecasting using Darts time series library."""

import pickle
from pathlib import Path

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

    def prepare_series(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        target_col: str = "price",
        covariate_cols: list[str] | None = None,
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
        self.target_series = self.scaler.fit_transform(self.target_series)

        # Covariate series
        self.covariate_series = None
        if covariate_cols:
            valid_cols = [c for c in covariate_cols if c in df.columns]
            if valid_cols:
                self.covariate_series = TimeSeries.from_dataframe(
                    df, time_col=date_col, value_cols=valid_cols, fill_missing_dates=True
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

    def predict(self, n_days: int | None = None) -> pd.DataFrame:
        """Generate price predictions for the next n_days."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        horizon = n_days or self.horizon
        pred = self.model.predict(horizon)
        pred_rescaled = self.scaler.inverse_transform(pred)

        result = pred_rescaled.pd_dataframe().reset_index()
        result.columns = ["date", "predicted_price"]
        return result

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
        except Exception as e:
            results.append({"model": model_name, "error": str(e)})

    return pd.DataFrame(results)
