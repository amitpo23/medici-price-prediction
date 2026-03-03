"""FastAPI endpoint for hotel price predictions and analytics."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import API_HOST, API_PORT, MODEL_PATH

# Lazy imports — heavy ML modules (darts, sklearn) loaded only when needed
# This allows the server to start even if darts is not installed,
# so the trading integration endpoints remain functional.

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Medici Price Prediction API",
    description="Hotel price forecasting, dynamic pricing, and analytics with multi-source data",
    version="0.4.0",
)

# Trading integration endpoints (no heavy deps)
from src.api.integration import router as integration_router
app.include_router(integration_router)

# SalesOffice analytics dashboard
from src.api.analytics_dashboard import router as analytics_dashboard_router
app.include_router(analytics_dashboard_router)

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
    global _forecaster, _loader, _occupancy_predictor

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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": _forecaster is not None,
        "occupancy_model_loaded": _occupancy_predictor is not None,
    }


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
        except Exception:
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
