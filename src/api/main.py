"""FastAPI endpoint for hotel price predictions and analytics."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import API_HOST, API_PORT, MODEL_PATH
from src.utils.logging_config import configure_logging

# Configure structured JSON logging at import time (before any other loggers)
configure_logging()

# Lazy imports — heavy ML modules (darts, sklearn) loaded only when needed
# This allows the server to start even if darts is not installed,
# so the trading integration endpoints remain functional.

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Medici Price Prediction API",
    description="Hotel price forecasting, dynamic pricing, and analytics with multi-source data",
    version="1.1.0",
)

# Middleware: correlation IDs, rate limiting, CORS
from src.api.middleware import setup_middleware
setup_middleware(app)

# Trading integration endpoints (no heavy deps)
from src.api.integration import router as integration_router
app.include_router(integration_router)

# SalesOffice analytics dashboard
from src.api.analytics_dashboard import router as analytics_dashboard_router
app.include_router(analytics_dashboard_router)

# Pricing Rules Engine — Step 5 integration
from src.api.rules_api import router as rules_router
app.include_router(rules_router)

# Global references (populated at startup if ML deps are available)
_forecaster = None
_loader = None
_pricer = None
_occupancy_predictor = None
_training_data: Optional[pd.DataFrame] = None


def _init_pricer():
    """Lazy-init the DynamicPricer (lightweight, no heavy deps)."""
    global _pricer
    if _pricer is None:
        try:
            from src.models.pricing import DynamicPricer
            _pricer = DynamicPricer()
        except ImportError:
            logger.warning("DynamicPricer not available")
    return _pricer


@app.on_event("startup")
async def startup():
    global _forecaster, _loader, _occupancy_predictor, _startup_time
    _startup_time = datetime.utcnow()

    # Validate configuration
    from src.utils.config_validator import validate_config, log_config_report
    report = validate_config()
    log_config_report(report)
    if not report["valid"]:
        logger.error("Startup continuing despite config errors — some features may fail")

    # Try loading ML models — skip gracefully if deps missing
    try:
        from src.models.forecaster import HotelPriceForecaster
        model_path = MODEL_PATH / "price_model.pkl"
        if model_path.exists():
            _forecaster = HotelPriceForecaster.load(model_path)
            logger.info("Price forecaster loaded")
    except ImportError:
        logger.warning("darts not installed — price forecaster disabled. Trading endpoints still work.")

    try:
        from src.models.occupancy import OccupancyPredictor
        occ_path = MODEL_PATH / "occupancy_model.pkl"
        if occ_path.exists():
            _occupancy_predictor = OccupancyPredictor.load(occ_path)
            logger.info("Occupancy predictor loaded")
    except ImportError:
        logger.warning("sklearn not installed — occupancy predictor disabled.")

    try:
        from src.data.multi_source_loader import MultiSourceLoader
        _loader = MultiSourceLoader()
    except ImportError:
        logger.warning("MultiSourceLoader dependencies missing — some data sources disabled.")

    _init_pricer()

    # Start background trading analysis scheduler
    from src.services.scheduler import start_scheduler
    start_scheduler()

    # Start SalesOffice price collection scheduler (hourly)
    from src.api.analytics_dashboard import start_salesoffice_scheduler
    start_salesoffice_scheduler()


@app.on_event("shutdown")
async def shutdown():
    from src.services.scheduler import stop_scheduler
    stop_scheduler()
    from src.api.analytics_dashboard import stop_salesoffice_scheduler
    stop_salesoffice_scheduler()


# --- Request/Response Models ---

class PredictionRequest(BaseModel):
    days_ahead: int = 30
    room_type: Optional[str] = None
    include_intervals: bool = False


class HotelPredictionRequest(BaseModel):
    city: str = "Tel Aviv"
    star_rating: float = 3.0
    days_ahead: int = 30
    include_intervals: bool = False


class PredictionResponse(BaseModel):
    predictions: List[Dict]
    model_name: str
    horizon: int


class TrainRequest(BaseModel):
    model_name: str = "lightgbm"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MultiSourceTrainRequest(BaseModel):
    model_name: str = "lightgbm"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    include_kaggle: bool = True
    include_market: bool = True
    train_occupancy: bool = True


class TrainResponse(BaseModel):
    metrics: dict
    model_name: str
    message: str
    sources_used: Optional[List[str]] = None
    occupancy_metrics: Optional[Dict] = None


class SeasonalityResponse(BaseModel):
    city: str
    seasonal_strength: float
    peak_periods: List[Dict]
    monthly_profile: List[Dict]


class RevPARResponse(BaseModel):
    metrics: Dict
    time_series: List[Dict]
    forecast: Optional[List[Dict]] = None


class DemandCurveResponse(BaseModel):
    method: str
    coefficients: Dict
    r_squared: float
    elasticity: float
    optimal_price: float
    expected_occupancy_at_optimal: float
    expected_revpar_at_optimal: float
    sensitivity_table: List[Dict]


class MarketStatsResponse(BaseModel):
    city: str
    hotel_count: int
    avg_price: float
    median_price: float
    avg_occupancy: Optional[float] = None
    revpar: Optional[float] = None
    by_star_rating: Dict
    price_distribution: Dict


# --- Core Endpoints ---

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


_startup_time: datetime | None = None


@app.get("/health")
async def health(detail: bool = False):
    """Health check — basic or detailed.

    Use ?detail=true for comprehensive status with data source freshness,
    cache stats, and prediction signals.

    Alerting thresholds:
    - "healthy": all critical sources fresh
    - "degraded": any source stale (2x expected interval)
    - "unhealthy": primary DB unreachable or predictions stale >6 hours
    """
    uptime = (datetime.utcnow() - _startup_time).total_seconds() if _startup_time else 0

    if not detail:
        return {
            "status": "ok",
            "uptime_seconds": int(uptime),
            "version": app.version,
            "model_loaded": _forecaster is not None,
            "occupancy_model_loaded": _occupancy_predictor is not None,
        }

    # Detailed health check
    from src.analytics.freshness_engine import build_freshness_data
    from src.utils.cache_manager import cache

    # Data source freshness
    try:
        freshness = build_freshness_data()
        data_sources = {}
        for src_info in freshness.get("sources", []):
            data_sources[src_info["name"]] = {
                "status": src_info["status"],
                "last_updated": src_info.get("last_updated"),
                "age_display": src_info.get("age_display"),
            }
        freshness_overall = freshness.get("summary", {}).get("overall_status", "unknown")
    except (OSError, ConnectionError, ValueError, TypeError):
        data_sources = {"error": "Unable to check data sources"}
        freshness_overall = "unknown"

    # Cache stats
    cache_stats = cache.status()

    # Prediction signals
    predictions_info = {}
    analytics_data = cache.get_data("analytics")
    if analytics_data:
        predictions = analytics_data.get("predictions", {})
        signals = {"CALL": 0, "PUT": 0, "NEUTRAL": 0}
        for pred in predictions.values():
            change = float(pred.get("expected_change_pct", 0) or 0)
            if change > 2:
                signals["CALL"] += 1
            elif change < -2:
                signals["PUT"] += 1
            else:
                signals["NEUTRAL"] += 1
        predictions_info = {
            "total_rooms": len(predictions),
            "last_scan": analytics_data.get("run_ts"),
            "signals": signals,
        }

    # Determine overall health status
    status = "healthy"
    last_scan = predictions_info.get("last_scan")
    if last_scan:
        try:
            scan_dt = datetime.fromisoformat(last_scan.replace("Z", "+00:00")) if isinstance(last_scan, str) else last_scan
            scan_age_hours = (datetime.utcnow() - scan_dt.replace(tzinfo=None)).total_seconds() / 3600
            if scan_age_hours > 6:
                status = "unhealthy"
        except (ValueError, TypeError, AttributeError):
            pass

    if freshness_overall == "red":
        status = "unhealthy"
    elif freshness_overall == "yellow" and status == "healthy":
        status = "degraded"

    return {
        "status": status,
        "uptime_seconds": int(uptime),
        "version": app.version,
        "data_sources": data_sources,
        "cache": cache_stats,
        "predictions": predictions_info,
        "models": {
            "forecaster_loaded": _forecaster is not None,
            "occupancy_model_loaded": _occupancy_predictor is not None,
        },
    }


@app.get("/health/view", include_in_schema=False)
async def health_dashboard():
    """HTML health dashboard with auto-refresh."""
    from fastapi.responses import HTMLResponse
    from src.utils.template_engine import render_template
    from src.analytics.freshness_engine import build_freshness_data
    from src.utils.cache_manager import cache

    uptime = (datetime.utcnow() - _startup_time).total_seconds() if _startup_time else 0

    # Format uptime
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    uptime_display = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    # Freshness data
    try:
        freshness = build_freshness_data()
        sources = freshness.get("sources", [])
        overall_status = freshness.get("summary", {}).get("overall_status", "unknown")
    except (OSError, ConnectionError, ValueError, TypeError):
        sources = []
        overall_status = "unknown"

    # Predictions
    analytics_data = cache.get_data("analytics")
    total_rooms = 0
    signals_call = signals_put = signals_neutral = 0
    last_scan = None
    if analytics_data:
        predictions = analytics_data.get("predictions", {})
        total_rooms = len(predictions)
        last_scan = analytics_data.get("run_ts")
        for pred in predictions.values():
            change = float(pred.get("expected_change_pct", 0) or 0)
            if change > 2:
                signals_call += 1
            elif change < -2:
                signals_put += 1
            else:
                signals_neutral += 1

    html = render_template(
        "health.html",
        overall_status=overall_status,
        uptime_display=uptime_display,
        version=app.version,
        checked_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        sources=sources,
        cache_regions=cache.status(),
        total_rooms=total_rooms,
        signals_call=signals_call,
        signals_put=signals_put,
        signals_neutral=signals_neutral,
        last_scan=last_scan,
        forecaster_loaded=_forecaster is not None,
        occupancy_loaded=_occupancy_predictor is not None,
    )
    return HTMLResponse(content=html)


@app.get("/data/sources")
async def list_data_sources():
    """List all configured data sources and their availability."""
    if _loader is None:
        return {"sources": {}}
    return {"sources": _loader.available_sources()}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    """Predict prices using the currently loaded model."""
    if _forecaster is None:
        raise HTTPException(status_code=503, detail="No model loaded. Train first via POST /train")

    predictions = _forecaster.predict(
        n_days=request.days_ahead,
        include_intervals=request.include_intervals,
    )
    return PredictionResponse(
        predictions=predictions.to_dict(orient="records"),
        model_name=_forecaster.model_name,
        horizon=request.days_ahead,
    )


@app.post("/predict/hotel")
def predict_hotel(request: HotelPredictionRequest):
    """Predict price for a specific hotel profile with pricing recommendations."""
    if _forecaster is None:
        raise HTTPException(status_code=503, detail="No model loaded. Train first via POST /train")

    predictions = _forecaster.predict(
        n_days=request.days_ahead,
        include_intervals=request.include_intervals,
    )

    # Apply dynamic pricing adjustments based on hotel attributes
    pricer = _init_pricer()
    if pricer is None:
        raise HTTPException(status_code=503, detail="DynamicPricer not available")

    results = []
    for _, row in predictions.iterrows():
        rec = pricer.calculate_recommended_price(
            predicted_price=row["predicted_price"],
            is_weekend=pd.Timestamp(row["date"]).dayofweek in (4, 5),
            star_rating=request.star_rating,
        )
        rec["date"] = str(row["date"])
        rec["city"] = request.city
        rec["star_rating"] = request.star_rating

        # Include confidence intervals if requested
        for col in row.index:
            if col.startswith("lower_") or col.startswith("upper_"):
                rec[col] = float(row[col])

        results.append(rec)

    return {"predictions": results, "hotel_profile": request.model_dump()}


@app.post("/train", response_model=TrainResponse)
def train(request: TrainRequest):
    """Train from Azure SQL database only."""
    global _forecaster

    try:
        from src.models.forecaster import HotelPriceForecaster
        from src.data.db_loader import load_daily_pricing
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"ML dependencies not installed: {e}")

    df = load_daily_pricing(start_date=request.start_date, end_date=request.end_date)
    if df.empty:
        raise HTTPException(status_code=404, detail="No pricing data found in database")

    _forecaster = HotelPriceForecaster(model_name=request.model_name)
    metrics = _forecaster.train(df)
    _forecaster.save()

    return TrainResponse(
        metrics=metrics,
        model_name=request.model_name,
        message="Model trained and saved",
        sources_used=["azure_sql"],
    )


@app.post("/train/multi-source", response_model=TrainResponse)
def train_multi_source(request: MultiSourceTrainRequest):
    """Train using all available data sources (Azure SQL + public datasets + enrichment)."""
    global _forecaster, _occupancy_predictor, _training_data

    try:
        from src.models.forecaster import HotelPriceForecaster
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"ML dependencies not installed: {e}")

    if _loader is None:
        raise HTTPException(status_code=500, detail="Multi-source loader not initialized")

    df = _loader.prepare_training_dataset(
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found from any source")

    # Store training data for analytics
    _training_data = df.copy()

    _forecaster = HotelPriceForecaster(model_name=request.model_name)
    metrics = _forecaster.train_auto(df)
    _forecaster.save()

    # Train occupancy model if requested and occupancy data exists
    occ_metrics = None
    if request.train_occupancy and "occupancy_rate" in df.columns:
        try:
            from src.models.occupancy import OccupancyPredictor
            _occupancy_predictor = OccupancyPredictor()
            occ_metrics = _occupancy_predictor.train(df)
            _occupancy_predictor.save()
        except ImportError:
            logger.warning("sklearn not installed — skipping occupancy model training")

    sources = _loader.available_sources()
    active = [name for name, available in sources.items() if available]

    return TrainResponse(
        metrics=metrics,
        model_name=request.model_name,
        message=f"Model trained with {len(df)} rows from {len(active)} sources",
        sources_used=active,
        occupancy_metrics=occ_metrics,
    )


@app.post("/train/deep-models")
def train_deep_models(hotel_id: int | None = None, lite: bool = True):
    """Train per-hotel ML models for DeepPredictor Signal 3.

    Loads DB sources, builds features, trains per-hotel LightGBM models.
    These .pkl models are auto-detected by DeepPredictor at prediction time.

    Args:
        hotel_id: Train single hotel (None=all).
        lite: If True (default), use fast essential sources only.
              Set False for full training with all 12 DB sources.
    """
    import threading
    import traceback as _tb

    def _run_training(target_hotel: int | None, use_lite: bool = True):
        from config.settings import MODELS_DIR
        import json as _json

        # Write live status so /status endpoint can report it
        status_path = MODELS_DIR / "training_status.json"
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        def _write_status(phase: str, detail: str = ""):
            try:
                with open(status_path, "w") as sf:
                    _json.dump({"phase": phase, "detail": detail,
                                "ts": datetime.utcnow().isoformat()}, sf)
            except (OSError, ValueError):
                logger.warning("Failed to write training status file to %s", status_path)

        try:
            _write_status("importing", "Loading train_models module")
            from scripts.train_models import load_training_data, build_hotel_daily_series, train_hotel_model

            mode_label = "lite" if use_lite else "full"
            _write_status("loading_data", f"Loading training data ({mode_label} mode)")
            logger.info("Deep model training started (hotel=%s, mode=%s)", target_hotel or "ALL", mode_label)
            data = load_training_data(lite=use_lite)

            # Log data source sizes
            source_sizes = {k: len(v) if hasattr(v, '__len__') else 0 for k, v in data.items()}
            _write_status("data_loaded", _json.dumps(source_sizes, default=str))

            scans = data.get("scans", pd.DataFrame())
            if scans.empty:
                _write_status("error", "No scan data available")
                logger.error("Deep model training: no scan data")
                return

            hotel_ids = scans["hotel_id"].unique().tolist()
            if target_hotel:
                hotel_ids = [target_hotel] if target_hotel in hotel_ids else []

            trained, failed = 0, 0
            results = {}
            for i, hid in enumerate(sorted(hotel_ids)):
                _write_status("training", f"Hotel {hid} ({i+1}/{len(hotel_ids)})")
                df = build_hotel_daily_series(hid, data)
                result = train_hotel_model(hid, df)
                results[str(hid)] = result
                if result.get("status") == "trained":
                    trained += 1
                else:
                    failed += 1

            report_path = MODELS_DIR / "training_report.json"
            with open(report_path, "w") as f:
                _json.dump({"trained": trained, "failed": failed, "models": results,
                            "completed_at": datetime.utcnow().isoformat()}, f, indent=2, default=str)
            _write_status("done", f"trained={trained}, failed={failed}")
            logger.info("Deep model training done: %d trained, %d failed", trained, failed)
        except (OSError, ValueError, TypeError, ImportError) as e:
            err_detail = _tb.format_exc()
            _write_status("error", err_detail[-2000:])  # last 2000 chars of traceback
            logger.error("Deep model training failed: %s\n%s", e, err_detail)

    # Run in background thread to avoid HTTP timeout
    t = threading.Thread(target=_run_training, args=(hotel_id, lite), daemon=True)
    t.start()

    return {
        "status": "training_started",
        "hotel_id": hotel_id or "all",
        "mode": "lite" if lite else "full",
        "message": "Training running in background. Check /train/deep-models/status for progress.",
    }


@app.get("/train/deep-models/status")
def deep_models_status():
    """Check training status and available models."""
    from config.settings import MODELS_DIR
    import json as _json

    models = list(MODELS_DIR.glob("price_model_*.pkl"))
    report = {}
    report_path = MODELS_DIR / "training_report.json"
    if report_path.exists():
        with open(report_path) as f:
            report = _json.load(f)

    # Live training status
    live_status = {}
    status_path = MODELS_DIR / "training_status.json"
    if status_path.exists():
        try:
            with open(status_path) as f:
                live_status = _json.load(f)
        except (OSError, ValueError):
            logger.warning("Failed to parse live training status from %s", status_path)

    return {
        "models_count": len(models),
        "model_files": [m.name for m in models],
        "training_report": report,
        "live_status": live_status,
    }


@app.get("/train/deep-models/test")
def test_deep_training(hotel_id: int | None = None):
    """Fast synchronous training diagnostic — returns errors immediately.

    Step 1: test import
    Step 2: test scan data loading (just scans, not all 12 sources)
    Step 3 (if hotel_id): build series + train single hotel

    Without hotel_id, returns after step 2 with data stats.
    """
    import traceback as _tb

    result = {"steps": []}

    try:
        result["steps"].append("step1_import")
        from scripts.train_models import load_training_data, build_hotel_daily_series, train_hotel_model
        result["steps"].append("step1_import_ok")

        # Quick scan data test (just scans, skip heavy DB sources)
        result["steps"].append("step2_load_scans")
        from src.analytics.collector import load_historical_prices
        scan_df = load_historical_prices()
        scan_count = len(scan_df) if scan_df is not None else 0
        result["scan_rows"] = scan_count

        if scan_df is not None and not scan_df.empty:
            result["scan_columns"] = list(scan_df.columns)
            result["scan_hotels"] = int(scan_df["hotel_id"].nunique()) if "hotel_id" in scan_df.columns else 0
            result["scan_sample_ids"] = sorted(scan_df["hotel_id"].unique().tolist())[:10] if "hotel_id" in scan_df.columns else []
        else:
            result["error"] = "No scan data returned from load_historical_prices()"
            return result

        result["steps"].append("step2_scans_ok")

        # If hotel_id given, do full single-hotel training
        if hotel_id:
            result["steps"].append(f"step3_full_train_hotel_{hotel_id}")
            data = load_training_data()
            source_sizes = {k: len(v) if hasattr(v, '__len__') else 0 for k, v in data.items()}
            result["data_sources"] = source_sizes

            df = build_hotel_daily_series(hotel_id, data)
            result["series_rows"] = len(df)

            if df.empty:
                result["error"] = f"Hotel {hotel_id}: empty series"
                return result

            train_result = train_hotel_model(hotel_id, df)
            result["train_result"] = train_result

        result["status"] = "ok"

    except (ValueError, TypeError, KeyError, OSError, ImportError) as e:
        result["error"] = str(e)
        result["traceback"] = _tb.format_exc()

    return result


@app.get("/train/logs/stats")
def prediction_log_stats():
    """Check structured prediction/price log stats."""
    try:
        from src.analytics.prediction_logger import get_log_stats
        return get_log_stats()
    except (ValueError, TypeError, KeyError, OSError, ImportError) as e:
        return {"error": str(e)}


@app.get("/market/{city}")
def get_market_snapshot(city: str):
    """Get current market pricing for a city via Google Hotels."""
    if _loader is None:
        raise HTTPException(status_code=500, detail="Loader not initialized")

    try:
        collector = _loader.registry.get("market")
        if not collector.is_available():
            raise HTTPException(status_code=503, detail="Market collector not available (no SERPAPI_KEY)")
        df = collector.collect(city=city)
        if df.empty:
            return {"city": city, "hotels": [], "message": "No data found"}
        return {"city": city, "hotels": df.to_dict(orient="records")}
    except KeyError:
        raise HTTPException(status_code=503, detail="Market collector not registered")


@app.get("/models")
async def list_models():
    available_models = []
    try:
        from src.models.forecaster import HotelPriceForecaster
        available_models = list(HotelPriceForecaster.AVAILABLE_MODELS.keys())
    except ImportError:
        available_models = ["(darts not installed)"]

    return {
        "available": available_models,
        "current": _forecaster.model_name if _forecaster else None,
        "occupancy_model_loaded": _occupancy_predictor is not None,
    }


# --- Analytics Endpoints ---

@app.get("/analytics/overview")
def analytics_overview():
    """Summary KPIs across all available data."""
    from src.analytics.statistics import market_overview

    if _training_data is None:
        raise HTTPException(status_code=404, detail="No training data available. Train a model first.")

    return market_overview(_training_data)


@app.get("/analytics/seasonality/{city}")
def analytics_seasonality(city: str, period: int = 7):
    """Seasonal patterns for a specific city."""
    from src.analytics.seasonality import (
        decompose_series,
        seasonal_strength_index,
        identify_peak_periods,
        city_seasonal_profile,
    )

    if _training_data is None:
        raise HTTPException(status_code=404, detail="No training data available. Train a model first.")

    city_data = _training_data[_training_data["city"] == city] if "city" in _training_data.columns else _training_data
    if city_data.empty or "price" not in city_data.columns:
        raise HTTPException(status_code=404, detail=f"No pricing data for city: {city}")

    strength = seasonal_strength_index(city_data, period=period)
    peaks = identify_peak_periods(city_data, period=period)

    profile_df = city_seasonal_profile(
        _training_data if "city" in _training_data.columns else city_data
    )
    city_profile = profile_df[profile_df["city"] == city] if "city" in profile_df.columns else profile_df

    return SeasonalityResponse(
        city=city,
        seasonal_strength=round(strength, 4),
        peak_periods=peaks,
        monthly_profile=city_profile.to_dict(orient="records"),
    )


@app.get("/analytics/revpar")
def analytics_revpar(
    city: Optional[str] = None,
    star_rating: Optional[float] = None,
    freq: str = "W",
    include_forecast: bool = False,
    forecast_days: int = 30,
):
    """RevPAR metrics and optional forecast."""
    from src.analytics.revenue import compute_revenue_metrics, revenue_time_series, forecast_revpar

    if _training_data is None:
        raise HTTPException(status_code=404, detail="No training data available. Train a model first.")

    data = _training_data.copy()
    if city and "city" in data.columns:
        data = data[data["city"] == city]
    if star_rating is not None and "star_rating" in data.columns:
        data = data[data["star_rating"] == star_rating]

    if data.empty:
        raise HTTPException(status_code=404, detail="No data matching filters")

    # Current metrics
    group_cols = []
    if "city" in data.columns and data["city"].nunique() > 1:
        group_cols.append("city")
    metrics_df = compute_revenue_metrics(data, group_cols=group_cols or None)

    # Time series
    ts = revenue_time_series(data, freq=freq)

    # Optional forecast
    forecast_data = None
    if include_forecast and _forecaster is not None:
        try:
            price_fc = _forecaster.predict(n_days=forecast_days, include_intervals=True)
            occ_fc = None
            if _occupancy_predictor is not None:
                # Create a feature DataFrame for occupancy prediction
                future_dates = pd.DataFrame({"date": price_fc["date"]})
                future_dates["month"] = pd.to_datetime(future_dates["date"]).dt.month
                future_dates["day_of_week"] = pd.to_datetime(future_dates["date"]).dt.dayofweek
                future_dates["is_weekend"] = future_dates["day_of_week"].isin([4, 5]).astype(int)
                occ_fc = _occupancy_predictor.predict(future_dates)

            revpar_fc = forecast_revpar(price_fc, occ_fc)
            forecast_data = revpar_fc.to_dict(orient="records")
        except (ValueError, TypeError, KeyError, OSError) as e:
            logger.warning("RevPAR forecast computation failed: %s", e)
            forecast_data = None

    return RevPARResponse(
        metrics=metrics_df.to_dict(orient="records")[0] if len(metrics_df) == 1 else {"segments": metrics_df.to_dict(orient="records")},
        time_series=ts.to_dict(orient="records"),
        forecast=forecast_data,
    )


@app.get("/analytics/demand-curve")
def analytics_demand_curve(
    city: Optional[str] = None,
    star_rating: Optional[float] = None,
    method: str = "log_linear",
    rooms_available: int = 100,
):
    """Demand analysis: curve, elasticity, optimal price."""
    from src.analytics.demand import (
        estimate_demand_curve,
        calculate_price_elasticity,
        find_optimal_price,
        demand_sensitivity_table,
    )

    if _training_data is None:
        raise HTTPException(status_code=404, detail="No training data available. Train a model first.")

    data = _training_data.copy()
    if city and "city" in data.columns:
        data = data[data["city"] == city]
    if star_rating is not None and "star_rating" in data.columns:
        data = data[data["star_rating"] == star_rating]

    if "occupancy_rate" not in data.columns:
        raise HTTPException(status_code=404, detail="No occupancy data available for demand analysis")

    curve = estimate_demand_curve(data, method=method)
    if "error" in curve:
        raise HTTPException(status_code=400, detail=curve["error"])

    elasticity = calculate_price_elasticity(data)
    optimal = find_optimal_price(curve, rooms_available=rooms_available)
    sensitivity = demand_sensitivity_table(curve, rooms_available=rooms_available)

    return DemandCurveResponse(
        method=curve["method"],
        coefficients=curve["coefficients"],
        r_squared=curve["r_squared"],
        elasticity=elasticity,
        optimal_price=optimal["optimal_price"],
        expected_occupancy_at_optimal=optimal["expected_occupancy"],
        expected_revpar_at_optimal=optimal["expected_revpar"],
        sensitivity_table=sensitivity.to_dict(orient="records"),
    )


@app.get("/analytics/market-stats/{city}")
def analytics_market_stats(city: str):
    """Competitive market statistics for a city."""
    from src.analytics.statistics import city_statistics

    if _training_data is None:
        raise HTTPException(status_code=404, detail="No training data available. Train a model first.")

    stats = city_statistics(_training_data, city=city)
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])

    return MarketStatsResponse(
        city=stats["city"],
        hotel_count=stats["hotel_count"],
        avg_price=stats["avg_price"],
        median_price=stats["median_price"],
        avg_occupancy=stats.get("avg_occupancy"),
        revpar=stats.get("revpar"),
        by_star_rating=stats.get("by_star_rating", {}),
        price_distribution=stats["price_distribution"],
    )


def start():
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    start()
