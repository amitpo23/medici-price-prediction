"""FastAPI endpoint for hotel price predictions."""

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import API_HOST, API_PORT, MODEL_PATH
from src.models.forecaster import HotelPriceForecaster
from src.data.supabase_loader import load_daily_pricing

app = FastAPI(
    title="Medici Price Prediction API",
    description="Hotel price forecasting and dynamic pricing recommendations",
    version="0.1.0",
)

# Global model reference — loaded on startup
_forecaster: HotelPriceForecaster | None = None


@app.on_event("startup")
async def load_model():
    global _forecaster
    model_path = MODEL_PATH / "price_model.pkl"
    if model_path.exists():
        _forecaster = HotelPriceForecaster.load(model_path)


class PredictionRequest(BaseModel):
    days_ahead: int = 30
    room_type: str | None = None


class PredictionResponse(BaseModel):
    predictions: list[dict]
    model_name: str
    horizon: int


class TrainRequest(BaseModel):
    model_name: str = "lightgbm"
    start_date: str | None = None
    end_date: str | None = None


class TrainResponse(BaseModel):
    metrics: dict
    model_name: str
    message: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": _forecaster is not None,
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    if _forecaster is None:
        raise HTTPException(status_code=503, detail="No model loaded. Train a model first via POST /train")

    predictions = _forecaster.predict(n_days=request.days_ahead)
    return PredictionResponse(
        predictions=predictions.to_dict(orient="records"),
        model_name=_forecaster.model_name,
        horizon=request.days_ahead,
    )


@app.post("/train", response_model=TrainResponse)
async def train(request: TrainRequest):
    global _forecaster

    df = load_daily_pricing(start_date=request.start_date, end_date=request.end_date)
    if df.empty:
        raise HTTPException(status_code=404, detail="No pricing data found in Supabase")

    _forecaster = HotelPriceForecaster(model_name=request.model_name)
    metrics = _forecaster.train(df)
    _forecaster.save()

    return TrainResponse(
        metrics=metrics,
        model_name=request.model_name,
        message="Model trained and saved successfully",
    )


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
