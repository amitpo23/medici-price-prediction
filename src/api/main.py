"""FastAPI endpoint for hotel price predictions."""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import API_HOST, API_PORT, MODEL_PATH
from src.models.forecaster import HotelPriceForecaster
from src.models.pricing import DynamicPricer
from src.data.db_loader import load_daily_pricing
from src.data.multi_source_loader import MultiSourceLoader

app = FastAPI(
    title="Medici Price Prediction API",
    description="Hotel price forecasting and dynamic pricing with multi-source data",
    version="0.2.0",
)

# Global references
_forecaster: Optional[HotelPriceForecaster] = None
_loader: Optional[MultiSourceLoader] = None
_pricer = DynamicPricer()


@app.on_event("startup")
async def startup():
    global _forecaster, _loader
    model_path = MODEL_PATH / "price_model.pkl"
    if model_path.exists():
        _forecaster = HotelPriceForecaster.load(model_path)
    _loader = MultiSourceLoader()


# --- Request/Response Models ---

class PredictionRequest(BaseModel):
    days_ahead: int = 30
    room_type: Optional[str] = None


class HotelPredictionRequest(BaseModel):
    city: str = "Tel Aviv"
    star_rating: float = 3.0
    days_ahead: int = 30


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


class TrainResponse(BaseModel):
    metrics: dict
    model_name: str
    message: str
    sources_used: Optional[List[str]] = None


# --- Endpoints ---

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": _forecaster is not None,
    }


@app.get("/data/sources")
async def list_data_sources():
    """List all configured data sources and their availability."""
    if _loader is None:
        return {"sources": {}}
    return {"sources": _loader.available_sources()}


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """Predict prices using the currently loaded model."""
    if _forecaster is None:
        raise HTTPException(status_code=503, detail="No model loaded. Train first via POST /train")

    predictions = _forecaster.predict(n_days=request.days_ahead)
    return PredictionResponse(
        predictions=predictions.to_dict(orient="records"),
        model_name=_forecaster.model_name,
        horizon=request.days_ahead,
    )


@app.post("/predict/hotel")
async def predict_hotel(request: HotelPredictionRequest):
    """Predict price for a specific hotel profile with pricing recommendations."""
    if _forecaster is None:
        raise HTTPException(status_code=503, detail="No model loaded. Train first via POST /train")

    predictions = _forecaster.predict(n_days=request.days_ahead)

    # Apply dynamic pricing adjustments based on hotel attributes
    results = []
    for _, row in predictions.iterrows():
        rec = _pricer.calculate_recommended_price(
            predicted_price=row["predicted_price"],
            is_weekend=pd.Timestamp(row["date"]).dayofweek in (4, 5),
            star_rating=request.star_rating,
        )
        rec["date"] = str(row["date"])
        rec["city"] = request.city
        rec["star_rating"] = request.star_rating
        results.append(rec)

    return {"predictions": results, "hotel_profile": request.model_dump()}


@app.post("/train", response_model=TrainResponse)
async def train(request: TrainRequest):
    """Train from Azure SQL database only."""
    global _forecaster

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
async def train_multi_source(request: MultiSourceTrainRequest):
    """Train using all available data sources (Azure SQL + public datasets + enrichment)."""
    global _forecaster

    if _loader is None:
        raise HTTPException(status_code=500, detail="Multi-source loader not initialized")

    df = _loader.prepare_training_dataset(
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found from any source")

    _forecaster = HotelPriceForecaster(model_name=request.model_name)
    metrics = _forecaster.train_auto(df)
    _forecaster.save()

    sources = _loader.available_sources()
    active = [name for name, available in sources.items() if available]

    return TrainResponse(
        metrics=metrics,
        model_name=request.model_name,
        message=f"Model trained with {len(df)} rows from {len(active)} sources",
        sources_used=active,
    )


@app.get("/market/{city}")
async def get_market_snapshot(city: str):
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
    return {
        "available": list(HotelPriceForecaster.AVAILABLE_MODELS.keys()),
        "current": _forecaster.model_name if _forecaster else None,
    }


def start():
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    start()
