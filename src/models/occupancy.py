"""Occupancy rate prediction model."""
from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config.settings import MODELS_DIR


# Features the model looks for (uses whichever are available)
_CANDIDATE_FEATURES = [
    "month", "day_of_week", "is_weekend", "is_holiday",
    "is_high_impact_holiday", "is_summer_vacation",
    "events_active_count", "event_impact_score",
    "temperature_max", "beach_weather_score",
    "star_rating", "is_coastal", "is_desert",
    "season_encoded",
]


class OccupancyPredictor:
    """Predict hotel occupancy rates (0-1) using gradient boosting.

    Falls back to CBS baseline averages when model is not trained.
    """

    def __init__(self):
        self.model: GradientBoostingRegressor | None = None
        self.feature_cols: list[str] = []
        self.cbs_baselines: dict | None = None

    def set_cbs_baselines(self, cbs_df: pd.DataFrame) -> None:
        """Ingest CBS fallback occupancy data as baseline priors.

        Expected columns: city (or region), season, avg_occupancy_rate.
        """
        if cbs_df.empty:
            return

        baselines = {}
        group_col = "city" if "city" in cbs_df.columns else "region"
        for _, row in cbs_df.iterrows():
            key = (row.get(group_col, "all"), row.get("season", "all"))
            baselines[key] = row.get("avg_occupancy_rate", row.get("occupancy_rate", 0.6))
        self.cbs_baselines = baselines

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "occupancy_rate",
    ) -> dict:
        """Train the occupancy prediction model.

        Returns dict with mae, rmse, r2 metrics.
        """
        data = df.dropna(subset=[target_col]).copy()

        if len(data) < 20:
            return {"error": "Not enough data with occupancy rates", "rows": len(data)}

        # Encode season if present
        if "season" in data.columns:
            season_map = {"winter": 0, "spring": 1, "summer": 2, "autumn": 3}
            data["season_encoded"] = data["season"].map(season_map).fillna(0).astype(int)

        # Select available features
        self.feature_cols = [c for c in _CANDIDATE_FEATURES if c in data.columns]

        if not self.feature_cols:
            return {"error": "No usable features found"}

        X = data[self.feature_cols].fillna(0).values
        y = data[target_col].clip(0, 1).values

        # Time series split
        tscv = TimeSeriesSplit(n_splits=3)
        all_mae, all_rmse = [], []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
            )
            model.fit(X_train, y_train)

            preds = np.clip(model.predict(X_val), 0, 1)
            all_mae.append(mean_absolute_error(y_val, preds))
            all_rmse.append(np.sqrt(mean_squared_error(y_val, preds)))

        # Final model on all data
        self.model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        self.model.fit(X, y)

        full_preds = np.clip(self.model.predict(X), 0, 1)

        return {
            "mae": round(float(np.mean(all_mae)), 4),
            "rmse": round(float(np.mean(all_rmse)), 4),
            "r2": round(float(r2_score(y, full_preds)), 4),
            "features_used": self.feature_cols,
            "training_rows": len(data),
        }

    def predict(
        self,
        df: pd.DataFrame,
        city: str | None = None,
        star_rating: float | None = None,
    ) -> pd.DataFrame:
        """Predict occupancy rates.

        Falls back to CBS baselines if model not trained.
        """
        result = df[["date"]].copy() if "date" in df.columns else df.iloc[:, :0].copy()

        if self.model is not None and self.feature_cols:
            data = df.copy()
            if "season" in data.columns:
                season_map = {"winter": 0, "spring": 1, "summer": 2, "autumn": 3}
                data["season_encoded"] = data["season"].map(season_map).fillna(0).astype(int)

            available = [c for c in self.feature_cols if c in data.columns]
            if available:
                X = data[available].fillna(0).values
                # Pad missing features with zeros
                if len(available) < len(self.feature_cols):
                    full_X = np.zeros((len(X), len(self.feature_cols)))
                    idx_map = [self.feature_cols.index(c) for c in available]
                    for i, idx in enumerate(idx_map):
                        full_X[:, idx] = X[:, i]
                    X = full_X

                result["predicted_occupancy"] = np.clip(self.model.predict(X), 0, 1)
                return result

        # Fallback to CBS baselines
        result["predicted_occupancy"] = self._cbs_fallback(df, city)
        return result

    def predict_with_intervals(
        self,
        df: pd.DataFrame,
        confidence: float = 0.80,
    ) -> pd.DataFrame:
        """Predict occupancy with confidence intervals via residual scaling."""
        result = self.predict(df)

        # Approximate intervals using model uncertainty
        pred = result["predicted_occupancy"].values
        # Scale uncertainty based on distance from 0.5 (more uncertain at extremes)
        half_width = (1 - confidence) * 0.5 + 0.05
        uncertainty = half_width * (1 - np.abs(pred - 0.5) * 2)

        pct = int(confidence * 100)
        result[f"occupancy_lower_{pct}"] = np.clip(pred - uncertainty, 0, 1).round(3)
        result[f"occupancy_upper_{pct}"] = np.clip(pred + uncertainty, 0, 1).round(3)

        return result

    def _cbs_fallback(self, df: pd.DataFrame, city: str | None = None) -> np.ndarray:
        """Generate occupancy estimates from CBS baselines."""
        n = len(df)

        if not self.cbs_baselines:
            return np.full(n, 0.60)  # Israeli hotel average

        results = []
        for i in range(n):
            row = df.iloc[i]
            c = city or row.get("city", "all")
            month = pd.to_datetime(row.get("date", pd.NaT)).month if "date" in df.columns else 6

            # Determine season from month
            if month in (12, 1, 2):
                season = "winter"
            elif month in (3, 4, 5):
                season = "spring"
            elif month in (6, 7, 8):
                season = "summer"
            else:
                season = "autumn"

            # Look up baseline
            occ = self.cbs_baselines.get((c, season))
            if occ is None:
                occ = self.cbs_baselines.get((c, "all"))
            if occ is None:
                occ = self.cbs_baselines.get(("all", season))
            if occ is None:
                occ = 0.60

            results.append(float(occ))

        return np.array(results)

    def save(self, name: str = "occupancy_model") -> Path:
        """Save model to disk."""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        path = MODELS_DIR / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "feature_cols": self.feature_cols,
                "cbs_baselines": self.cbs_baselines,
            }, f)
        return path

    @classmethod
    def load(cls, path: str | Path) -> OccupancyPredictor:
        """Load a saved model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        predictor = cls()
        predictor.model = data["model"]
        predictor.feature_cols = data["feature_cols"]
        predictor.cbs_baselines = data.get("cbs_baselines")
        return predictor
