"""Train ML price models using all available historical data.

This script loads data from all medici-db sources, builds features using
the existing feature engineering pipeline, and trains per-hotel LightGBM
models that power Signal 3 in the DeepPredictor ensemble.

Data sources used:
  1. SalesOffice scan history — main price time-series (scan pairs)
  2. AI_Search_HotelData (8.5M) — market benchmark prices
  3. RoomPriceUpdateLog (82K) — real price change events → velocity signal
  4. MED_CancelBook (4.7K) — cancellation rates by hotel/lead-time
  5. SearchResultsSessionPollLog (8.3M) — provider pricing pressure
  6. tprice — monthly historical pricing
  7. MED_Book — booking/trading history

Output:
  data/models/price_model_{hotel_id}.pkl — per-hotel Darts LightGBM model
  data/models/training_report.json — metrics for every trained model

Usage:
  python -m scripts.train_models                 # Train all hotels
  python -m scripts.train_models --hotel 66814   # Train single hotel
  python -m scripts.train_models --dry-run       # Show data stats only
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from config.settings import MODELS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("train_models")


# ─── Data Loading ────────────────────────────────────────────────────

def load_training_data(lite: bool = False) -> dict:
    """Load all data sources needed for training.

    Args:
        lite: If True, only load fast essential sources (scans, tprice, velocity,
              cancellations). Skips heavy multi-million-row DB queries.
    """
    from src.data.trading_db import (
        load_historical_prices as load_tprice,
        load_all_bookings,
        load_price_updates,
        load_price_update_velocity,
        load_cancellations,
        load_ai_search_data,
        load_search_results_summary,
        load_market_benchmark,
        load_hotels_with_geo,
        load_appservice_prediction_logs,
        load_appservice_price_logs,
        load_appservice_price_change_logs,
    )
    from src.analytics.collector import load_historical_prices

    data = {}

    # 1. SalesOffice scan history (primary time-series) — load FIRST to get hotel IDs
    logger.info("Loading SalesOffice scan history...")
    try:
        scan_df = load_historical_prices()
        if scan_df is not None and not scan_df.empty:
            scan_df["scan_date"] = pd.to_datetime(scan_df["scan_date"], errors="coerce")
            scan_df["date_from"] = pd.to_datetime(scan_df["date_from"], errors="coerce")
            scan_df["room_price"] = pd.to_numeric(scan_df["room_price"], errors="coerce")
            scan_df = scan_df.dropna(subset=["room_price", "scan_date"])
            data["scans"] = scan_df
            logger.info("  → %d scan records, %d hotels", len(scan_df), scan_df["hotel_id"].nunique())
        else:
            data["scans"] = pd.DataFrame()
            logger.warning("  → No scan data")
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["scans"] = pd.DataFrame()

    # Extract hotel IDs to filter heavy queries
    tracked_hotel_ids = []
    if not data["scans"].empty and "hotel_id" in data["scans"].columns:
        tracked_hotel_ids = data["scans"]["hotel_id"].unique().tolist()
    logger.info("Tracked hotels: %s", tracked_hotel_ids)

    # 2. tprice monthly historical
    logger.info("Loading tprice monthly prices...")
    try:
        tprice = load_tprice()
        data["tprice"] = tprice
        logger.info("  → %d records", len(tprice))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["tprice"] = pd.DataFrame()

    # 3. Price update velocity per hotel (lightweight aggregate)
    logger.info("Loading price update velocity...")
    try:
        velocity = load_price_update_velocity()
        data["velocity"] = velocity
        logger.info("  → %d hotels with velocity data", len(velocity))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["velocity"] = pd.DataFrame()

    # 4. Cancellations (4.7K rows — fast)
    logger.info("Loading cancellation history...")
    try:
        cancels = load_cancellations(days_back=730)
        data["cancellations"] = cancels
        logger.info("  → %d cancellation records", len(cancels))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["cancellations"] = pd.DataFrame()

    # ── Heavy sources (skipped in lite mode) ──
    if lite:
        logger.info("LITE mode — skipping heavy DB sources (price_updates, bookings, ai_search, etc.)")
        for key in ("price_updates", "bookings", "ai_search", "hotels_geo",
                     "search_summary", "prediction_logs", "price_logs", "price_change_logs"):
            data[key] = pd.DataFrame()
        return data

    # 5. Price change events (82K with JOIN)
    logger.info("Loading price update events...")
    try:
        updates = load_price_updates(days_back=365)
        data["price_updates"] = updates
        logger.info("  → %d price change events", len(updates))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["price_updates"] = pd.DataFrame()

    # 6. Booking history
    logger.info("Loading booking history...")
    try:
        bookings = load_all_bookings(days_back=365)
        data["bookings"] = bookings
        logger.info("  → %d booking records", len(bookings))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["bookings"] = pd.DataFrame()

    # 7. AI Search market data — filter to tracked hotels (8.5M rows total)
    logger.info("Loading AI search market data (hotel-filtered)...")
    try:
        ai_search = load_ai_search_data(hotel_ids=tracked_hotel_ids or None, days_back=90)
        data["ai_search"] = ai_search
        logger.info("  → %d market price records", len(ai_search))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["ai_search"] = pd.DataFrame()

    # 8. Hotel geo/metadata
    logger.info("Loading hotel metadata...")
    try:
        hotels_geo = load_hotels_with_geo()
        data["hotels_geo"] = hotels_geo
        logger.info("  → %d hotels with geo", len(hotels_geo))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["hotels_geo"] = pd.DataFrame()

    # 9. Search results summary — filter to tracked hotels (8.3M rows total)
    logger.info("Loading search results summary (hotel-filtered)...")
    try:
        search_summary = load_search_results_summary(hotel_ids=tracked_hotel_ids or None)
        data["search_summary"] = search_summary
        logger.info("  → %d hotels with search results", len(search_summary))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["search_summary"] = pd.DataFrame()

    # 10. App Service prediction logs (structured JSONL)
    logger.info("Loading App Service prediction logs...")
    try:
        pred_logs = load_appservice_prediction_logs(days_back=180)
        data["prediction_logs"] = pred_logs
        logger.info("  → %d prediction log events", len(pred_logs))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["prediction_logs"] = pd.DataFrame()

    # 11. App Service price observation logs (structured JSONL)
    logger.info("Loading App Service price logs...")
    try:
        price_logs = load_appservice_price_logs(days_back=180)
        data["price_logs"] = price_logs
        logger.info("  → %d price log events", len(price_logs))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["price_logs"] = pd.DataFrame()

    # 12. App Service price change logs (structured JSONL)
    logger.info("Loading App Service price change logs...")
    try:
        change_logs = load_appservice_price_change_logs(days_back=180)
        data["price_change_logs"] = change_logs
        logger.info("  → %d price change events", len(change_logs))
    except Exception as e:
        logger.error("  → Failed: %s", e)
        data["price_change_logs"] = pd.DataFrame()

    return data


# ─── Feature Building ────────────────────────────────────────────────

def build_hotel_daily_series(hotel_id: int, data: dict) -> pd.DataFrame:
    """Build a daily price time-series for a hotel with all features.

    Combines scan history + tprice + market benchmark + price velocity +
    calendar + holiday + seasonal features into a single DataFrame
    indexed by date with 'price' as target.
    """
    from src.features.engineering import (
        add_calendar_features,
        add_lag_features,
        add_rolling_features,
    )
    from src.features.holidays import (
        add_hebrew_holiday_features,
        add_school_vacation_features,
    )

    scans = data.get("scans", pd.DataFrame())
    tprice_df = data.get("tprice", pd.DataFrame())
    velocity_df = data.get("velocity", pd.DataFrame())
    cancels_df = data.get("cancellations", pd.DataFrame())
    bookings_df = data.get("bookings", pd.DataFrame())
    ai_search_df = data.get("ai_search", pd.DataFrame())
    hotels_geo = data.get("hotels_geo", pd.DataFrame())

    # ── Primary: daily avg price from scan history ──
    records = []

    # Source 1: Scans — group by (hotel_id, scan_date) → daily avg price
    if not scans.empty:
        hotel_scans = scans[scans["hotel_id"] == hotel_id].copy()
        if not hotel_scans.empty:
            hotel_scans["date"] = hotel_scans["scan_date"].dt.date
            daily = (
                hotel_scans
                .groupby("date")
                .agg(
                    price=("room_price", "median"),
                    room_count=("room_price", "count"),
                    price_std=("room_price", "std"),
                    price_min=("room_price", "min"),
                    price_max=("room_price", "max"),
                )
                .reset_index()
            )
            daily["date"] = pd.to_datetime(daily["date"])
            daily["source"] = "scan"
            records.append(daily)

    # Source 2: tprice monthly — expand to daily
    if not tprice_df.empty:
        hotel_tprice = tprice_df[tprice_df["HotelId"] == hotel_id].copy()
        if not hotel_tprice.empty:
            tp_rows = []
            for _, row in hotel_tprice.iterrows():
                try:
                    month_dt = pd.to_datetime(row["Month"])
                    price = float(row["Price"])
                    if price > 0:
                        # Create daily entries for the whole month
                        days_in_month = pd.Period(month_dt, freq="M").days_in_month
                        for d in range(days_in_month):
                            tp_rows.append({
                                "date": month_dt + timedelta(days=d),
                                "price": price,
                                "room_count": 1,
                                "price_std": 0,
                                "price_min": price,
                                "price_max": price,
                                "source": "tprice",
                            })
                except Exception:
                    continue
            if tp_rows:
                records.append(pd.DataFrame(tp_rows))

    # Source 3: AI Search market data for this hotel
    if not ai_search_df.empty:
        hotel_ai = ai_search_df[ai_search_df["HotelId"] == hotel_id].copy()
        if not hotel_ai.empty and "UpdatedAt" in hotel_ai.columns:
            hotel_ai["date"] = pd.to_datetime(hotel_ai["UpdatedAt"]).dt.normalize()
            ai_daily = (
                hotel_ai
                .groupby("date")
                .agg(
                    price=("PriceAmount", "median"),
                    room_count=("PriceAmount", "count"),
                    price_std=("PriceAmount", "std"),
                    price_min=("PriceAmount", "min"),
                    price_max=("PriceAmount", "max"),
                )
                .reset_index()
            )
            ai_daily["source"] = "ai_search"
            records.append(ai_daily)

    if not records:
        return pd.DataFrame()

    # Merge all sources — prefer scan > ai_search > tprice
    df = pd.concat(records, ignore_index=True)
    source_priority = {"scan": 0, "ai_search": 1, "tprice": 2}
    df["priority"] = df["source"].map(source_priority).fillna(3)
    df = df.sort_values(["date", "priority"]).drop_duplicates(subset=["date"], keep="first")
    df = df.sort_values("date").reset_index(drop=True)

    if len(df) < 30:
        logger.debug("Hotel %d: only %d days of data, skipping", hotel_id, len(df))
        return pd.DataFrame()

    # Fill gaps (max 3-day interpolation)
    full_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    df = df.set_index("date").reindex(full_dates).rename_axis("date").reset_index()
    df["price"] = df["price"].interpolate(method="linear", limit=3)
    df = df.dropna(subset=["price"])
    df["room_count"] = df["room_count"].fillna(0).astype(int)
    df["price_std"] = df["price_std"].fillna(0)
    df["price_min"] = df["price_min"].fillna(df["price"])
    df["price_max"] = df["price_max"].fillna(df["price"])

    # ── Calendar features ──
    df = add_calendar_features(df, "date")

    # ── Hebrew holiday features ──
    try:
        df = add_hebrew_holiday_features(df, "date")
    except Exception:
        df["is_holiday"] = 0
        df["is_high_impact_holiday"] = 0
        df["is_medium_impact_holiday"] = 0
        df["is_holiday_eve"] = 0
        df["days_to_next_holiday"] = 30

    try:
        df = add_school_vacation_features(df, "date")
    except Exception:
        df["is_summer_vacation"] = 0
        df["is_chanuka_break"] = 0

    # ── Lag and rolling features ──
    df = add_lag_features(df, "price")
    df = add_rolling_features(df, "price")

    # ── Price velocity from RoomPriceUpdateLog ──
    if not velocity_df.empty:
        hotel_vel = velocity_df[velocity_df["HotelId"] == hotel_id]
        if not hotel_vel.empty:
            row = hotel_vel.iloc[0]
            df["price_update_velocity"] = float(row.get("total_updates", 0))
            df["price_revision_intensity"] = float(row.get("unique_rooms", 0))
            df["price_stdev_market"] = float(row.get("price_stdev", 0))
        else:
            df["price_update_velocity"] = 0
            df["price_revision_intensity"] = 0
            df["price_stdev_market"] = 0
    else:
        df["price_update_velocity"] = 0
        df["price_revision_intensity"] = 0
        df["price_stdev_market"] = 0

    # ── Cancellation rate per hotel ──
    cancel_rate = 0.0
    if not cancels_df.empty and not bookings_df.empty:
        hotel_cancels = cancels_df[cancels_df["HotelId"] == hotel_id]
        hotel_bookings = bookings_df[bookings_df["HotelId"] == hotel_id]
        if len(hotel_bookings) > 0:
            cancel_rate = len(hotel_cancels) / len(hotel_bookings)
    df["cancellation_rate"] = min(cancel_rate, 1.0)

    # ── Hotel star/geo features ──
    if not hotels_geo.empty:
        hotel_meta = hotels_geo[hotels_geo["HotelId"] == hotel_id]
        if not hotel_meta.empty:
            meta = hotel_meta.iloc[0]
            stars = float(meta.get("Stars", 0) or 0)
            df["star_rating"] = stars
            star_mult = {0: 0.7, 1: 0.5, 2: 0.7, 3: 1.0, 4: 1.5, 5: 2.2}
            df["star_price_multiplier"] = star_mult.get(int(stars), 1.0)
            df["latitude"] = float(meta.get("Latitude", 0) or 0)
            df["longitude"] = float(meta.get("Longitude", 0) or 0)
        else:
            df["star_rating"] = 0
            df["star_price_multiplier"] = 1.0
            df["latitude"] = 0
            df["longitude"] = 0
    else:
        df["star_rating"] = 0
        df["star_price_multiplier"] = 1.0
        df["latitude"] = 0
        df["longitude"] = 0

    # ── Market comparison from AI Search ──
    if not ai_search_df.empty:
        hotel_ai = ai_search_df[ai_search_df["HotelId"] == hotel_id]
        if not hotel_ai.empty:
            market_avg = ai_search_df["PriceAmount"].median()
            hotel_avg = hotel_ai["PriceAmount"].median()
            df["price_vs_market"] = hotel_avg / market_avg if market_avg > 0 else 1.0
        else:
            df["price_vs_market"] = 1.0
    else:
        df["price_vs_market"] = 1.0

    # ── App Service price change history (from structured logs) ──
    price_change_logs = data.get("price_change_logs", pd.DataFrame())
    if not price_change_logs.empty and "hotel_id" in price_change_logs.columns:
        hotel_changes = price_change_logs[price_change_logs["hotel_id"] == hotel_id]
        if not hotel_changes.empty:
            df["log_price_changes_count"] = len(hotel_changes)
            df["log_avg_change_pct"] = float(hotel_changes["change_pct"].mean()) if "change_pct" in hotel_changes.columns else 0
            df["log_price_drops"] = int((hotel_changes.get("direction", pd.Series()) == "down").sum())
            df["log_price_rises"] = int((hotel_changes.get("direction", pd.Series()) == "up").sum())
        else:
            df["log_price_changes_count"] = 0
            df["log_avg_change_pct"] = 0
            df["log_price_drops"] = 0
            df["log_price_rises"] = 0
    else:
        df["log_price_changes_count"] = 0
        df["log_avg_change_pct"] = 0
        df["log_price_drops"] = 0
        df["log_price_rises"] = 0

    # ── App Service prediction accuracy (compare past predictions to outcomes) ──
    prediction_logs = data.get("prediction_logs", pd.DataFrame())
    if not prediction_logs.empty and "hotel_id" in prediction_logs.columns:
        hotel_preds = prediction_logs[prediction_logs["hotel_id"] == hotel_id]
        if not hotel_preds.empty and "predicted_price" in hotel_preds.columns:
            df["log_predictions_count"] = len(hotel_preds)
            df["log_avg_predicted_change"] = float(hotel_preds["expected_change_pct"].mean()) if "expected_change_pct" in hotel_preds.columns else 0
        else:
            df["log_predictions_count"] = 0
            df["log_avg_predicted_change"] = 0
    else:
        df["log_predictions_count"] = 0
        df["log_avg_predicted_change"] = 0

    # Drop NaN rows from lag features (first 28 days)
    df = df.dropna(subset=["price_lag_1"]).reset_index(drop=True)

    return df


# ─── Training ────────────────────────────────────────────────────────

def train_hotel_model(hotel_id: int, df: pd.DataFrame) -> dict:
    """Train a LightGBM model for a single hotel.

    Uses LightGBM directly (no Darts/PyTorch dependency) for lightweight
    deployment on Azure App Service.

    Returns dict with metrics or error info.
    """
    import pickle
    import lightgbm as lgb
    from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error

    if df.empty or len(df) < 60:
        return {"hotel_id": hotel_id, "status": "skipped",
                "reason": f"Only {len(df)} days of data (need 60+)"}

    # Feature columns (includes lags, rolling stats, calendar, enrichments)
    covariate_candidates = [
        # Calendar
        "day_of_week", "month", "is_weekend", "is_holiday",
        "is_high_impact_holiday", "is_medium_impact_holiday",
        "is_holiday_eve", "days_to_next_holiday",
        "is_summer_vacation", "is_chanuka_break",
        # Hotel attributes
        "star_price_multiplier", "star_rating",
        # Market signals
        "price_update_velocity", "price_revision_intensity",
        "cancellation_rate", "price_vs_market",
        "price_stdev_market",
        # Scan stats
        "room_count", "price_std", "price_min", "price_max",
        # Lag features (from add_lag_features)
        "price_lag_1", "price_lag_3", "price_lag_7", "price_lag_14", "price_lag_28",
        # Rolling features (from add_rolling_features)
        "price_rolling_mean_7", "price_rolling_std_7",
        "price_rolling_mean_14", "price_rolling_std_14",
        "price_rolling_mean_28", "price_rolling_std_28",
        # Log-derived features
        "log_price_changes_count", "log_avg_change_pct",
        "log_price_drops", "log_price_rises",
        "log_predictions_count", "log_avg_predicted_change",
    ]
    feature_cols = [c for c in covariate_candidates if c in df.columns
                    and df[c].notna().sum() > len(df) * 0.5]

    if not feature_cols:
        return {"hotel_id": hotel_id, "status": "skipped",
                "reason": "No usable features after filtering"}

    # Ensure all numeric
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Train/test split: last 30 days for validation
    val_size = 30
    train_df = df.iloc[:-val_size].copy()
    val_df = df.iloc[-val_size:].copy()

    X_train = train_df[feature_cols].values
    y_train = train_df["price"].values
    X_val = val_df[feature_cols].values
    y_val = val_df["price"].values

    try:
        # Train LightGBM
        model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            min_child_samples=10,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=42,
            verbose=-1,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(20, verbose=False)],
        )

        # Evaluate
        y_pred = model.predict(X_val)
        mape_val = float(mean_absolute_percentage_error(y_val, y_pred)) * 100
        rmse_val = float(mean_squared_error(y_val, y_pred) ** 0.5)
        mae_val = float(mean_absolute_error(y_val, y_pred))

        # Save model (lightweight pickle — no Darts/PyTorch dependency)
        model_data = {
            "type": "lightgbm_direct",
            "model": model,
            "feature_cols": feature_cols,
            "hotel_id": hotel_id,
            "price_mean": float(df["price"].mean()),
            "price_std": float(df["price"].std()),
            "trained_at": datetime.utcnow().isoformat(),
            "metrics": {"mape": mape_val, "rmse": rmse_val, "mae": mae_val},
        }

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model_path = MODELS_DIR / f"price_model_{hotel_id}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model_data, f)

        result = {
            "hotel_id": hotel_id,
            "status": "trained",
            "model_path": str(model_path),
            "data_points": len(df),
            "date_range": f"{df['date'].min().date()} to {df['date'].max().date()}",
            "features_used": feature_cols,
            "n_features": len(feature_cols),
            "mape": mape_val,
            "rmse": rmse_val,
            "mae": mae_val,
        }
        logger.info("  ✓ Hotel %d: MAPE=%.2f%%, RMSE=%.2f, MAE=%.2f (%d days, %d features)",
                     hotel_id, mape_val, rmse_val, mae_val, len(df), len(feature_cols))
        return result

    except Exception as e:
        logger.warning("  ✗ Hotel %d: training failed — %s", hotel_id, e)
        return {"hotel_id": hotel_id, "status": "failed", "error": str(e)}


# ─── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train ML price models")
    parser.add_argument("--hotel", type=int, help="Train single hotel ID")
    parser.add_argument("--dry-run", action="store_true", help="Show data stats only")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Medici Price Prediction — ML Model Training")
    logger.info("=" * 60)

    # Load all data
    data = load_training_data()

    scans = data.get("scans", pd.DataFrame())
    if scans.empty:
        logger.error("No scan data available — cannot train models")
        sys.exit(1)

    # Determine which hotels to train
    hotel_ids = scans["hotel_id"].unique().tolist()
    if args.hotel:
        if args.hotel in hotel_ids:
            hotel_ids = [args.hotel]
        else:
            logger.error("Hotel %d not found in scan data. Available: %s", args.hotel, hotel_ids)
            sys.exit(1)

    logger.info("\nTraining targets: %d hotels", len(hotel_ids))
    for hid in sorted(hotel_ids):
        h_scans = scans[scans["hotel_id"] == hid]
        hotel_name = h_scans["hotel_name"].iloc[0] if "hotel_name" in h_scans.columns else "?"
        dates = h_scans["scan_date"]
        logger.info("  • Hotel %d (%s): %d scans, %s to %s",
                     hid, hotel_name, len(h_scans),
                     dates.min().date() if not dates.empty else "?",
                     dates.max().date() if not dates.empty else "?")

    if args.dry_run:
        logger.info("\n[DRY RUN] Would train %d models. Use without --dry-run to proceed.", len(hotel_ids))
        return

    # Ensure models directory exists
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Train each hotel
    logger.info("\n" + "=" * 60)
    logger.info("Starting model training...")
    logger.info("=" * 60)

    results = {}
    trained = 0
    failed = 0
    skipped = 0

    for i, hotel_id in enumerate(sorted(hotel_ids)):
        logger.info("\n[%d/%d] Training hotel %d...", i + 1, len(hotel_ids), hotel_id)
        df = build_hotel_daily_series(hotel_id, data)
        result = train_hotel_model(hotel_id, df)
        results[str(hotel_id)] = result

        if result["status"] == "trained":
            trained += 1
        elif result["status"] == "failed":
            failed += 1
        else:
            skipped += 1

    # Save training report
    report = {
        "training_ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "total_hotels": len(hotel_ids),
        "trained": trained,
        "failed": failed,
        "skipped": skipped,
        "data_sources": {
            "scans": len(data.get("scans", [])),
            "tprice": len(data.get("tprice", [])),
            "price_updates": len(data.get("price_updates", [])),
            "cancellations": len(data.get("cancellations", [])),
            "bookings": len(data.get("bookings", [])),
            "ai_search": len(data.get("ai_search", [])),
        },
        "models": results,
    }

    report_path = MODELS_DIR / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("\n" + "=" * 60)
    logger.info("Training complete!")
    logger.info("  Trained: %d | Failed: %d | Skipped: %d", trained, failed, skipped)
    logger.info("  Report: %s", report_path)
    logger.info("  Models: %s/price_model_*.pkl", MODELS_DIR)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
