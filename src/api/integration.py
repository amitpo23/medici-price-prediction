"""Trading integration API — endpoints for the decision brain.

Exposes read-only analysis of trading data:
  - Health check for trading DB connectivity
  - Opportunity analysis (BUY/PASS)
  - Booking analysis (HOLD/REPRICE/CONSIDER_CANCEL)
  - Portfolio analysis
  - Hotel price forecast
  - Active recommendations (from scheduler)
  - Daily performance report

All endpoints are advisory only — no actions are executed.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from config.settings import PREDICTION_API_KEY

router = APIRouter(prefix="/api/v1", tags=["trading-integration"])


# ── Auth ─────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(default="")) -> str:
    """Validate API key if one is configured."""
    if PREDICTION_API_KEY and x_api_key != PREDICTION_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


# ── Request / Response Models ────────────────────────────────────────

class SupplierOption(BaseModel):
    source_name: str = "Unknown"
    source_id: Optional[int] = None
    buy_price: float
    currency: str = "USD"
    is_free_cancellation: bool = False
    cancellation_deadline: Optional[str] = None


class OpportunityRequest(BaseModel):
    hotel_id: int
    date_from: str
    date_to: str
    buy_price: float
    push_price: Optional[float] = None
    supplier_options: list[SupplierOption] = Field(default_factory=list)
    category_id: Optional[int] = None
    board_id: Optional[int] = None
    adults: int = 2
    children: int = 0
    currency: str = "USD"
    opportunity_id: Optional[str] = None


class AnalysisResponse(BaseModel):
    type: str
    confidence: float
    reasoning: list[str]
    hotel_id: int
    price_data: Optional[dict] = None
    risk_data: Optional[dict] = None
    market_context: Optional[dict] = None
    impact_factors: list[dict] = Field(default_factory=list)
    booking_reference: Optional[int] = None
    opportunity_reference: Optional[str] = None


class PortfolioResponse(BaseModel):
    total_bookings: int
    analyzed: int
    hotels_in_portfolio: int
    attention_items: list[dict]
    attention_count: int
    recommendation_breakdown: dict
    statistics: dict
    summary: str


class ForecastResponse(BaseModel):
    hotel_id: int
    predictions: list[dict]
    model_name: Optional[str] = None
    horizon: int


class DailyReportResponse(BaseModel):
    date: str
    portfolio_summary: dict
    market_summary: dict
    recommendations_count: int
    top_opportunities: list[dict]
    top_risks: list[dict]


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/health/trading")
async def trading_health():
    """Check trading DB connectivity and system status."""
    try:
        from src.data.trading_db import check_connection
        connected = check_connection()
        return {
            "trading_db_connected": connected,
            "status": "ok" if connected else "disconnected",
            "message": "Trading DB accessible" if connected else "Cannot reach medici-db — check MEDICI_DB_URL",
        }
    except Exception as e:
        return {
            "trading_db_connected": False,
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__,
        }


@router.post("/analyze/opportunity", response_model=AnalysisResponse)
async def analyze_opportunity(
    request: OpportunityRequest,
    _key: str = Depends(verify_api_key),
):
    """Analyze a buy opportunity → BUY or PASS recommendation.

    Called by medici-hotels when a new opportunity appears.
    """
    from src.models.recommender import TradingRecommender
    from src.features.trading import compute_trading_metrics
    from src.data.trading_db import load_all_bookings, check_connection

    recommender = TradingRecommender()

    # Get predicted market price (use forecaster if available, else estimate)
    predicted_price = _get_predicted_price(request.hotel_id, request.date_from)

    # Get confidence interval
    ci = _get_confidence_interval(request.hotel_id, request.date_from)

    # Get occupancy forecast
    occupancy = _get_occupancy_forecast(request.hotel_id, request.date_from)

    # Get competitor price from market data
    competitor_price = _get_competitor_price(request.hotel_id)

    # Get seasonal context
    seasonal = _get_seasonal_context(request.date_from)

    # Get hotel trading metrics (if DB available)
    hotel_metrics = None
    if check_connection():
        try:
            bookings = load_all_bookings(days_back=90)
            if not bookings.empty:
                metrics_df = compute_trading_metrics(bookings)
                hotel_row = metrics_df[metrics_df["HotelId"] == request.hotel_id]
                if not hotel_row.empty:
                    hotel_metrics = hotel_row.iloc[0].to_dict()
        except Exception:
            pass

    # Pick best supplier if multiple options provided
    best_buy_price = request.buy_price
    if request.supplier_options:
        best = min(request.supplier_options, key=lambda s: s.buy_price)
        best_buy_price = best.buy_price

    result = recommender.analyze_opportunity(
        opportunity={
            "hotel_id": request.hotel_id,
            "buy_price": best_buy_price,
            "push_price": request.push_price,
            "date_from": request.date_from,
            "date_to": request.date_to,
            "opportunity_id": request.opportunity_id,
        },
        predicted_price=predicted_price,
        confidence_interval=ci,
        occupancy_forecast=occupancy,
        competitor_price=competitor_price,
        seasonal_context=seasonal,
        hotel_metrics=hotel_metrics,
    )

    return AnalysisResponse(**result)


@router.get("/analyze/booking/{pre_book_id}", response_model=AnalysisResponse)
async def analyze_booking(
    pre_book_id: int,
    _key: str = Depends(verify_api_key),
):
    """Analyze an existing booking → HOLD, REPRICE, or CONSIDER_CANCEL."""
    from src.data.trading_db import load_booking_by_prebook_id, check_connection
    from src.models.recommender import TradingRecommender

    if not check_connection():
        raise HTTPException(status_code=503, detail="Trading DB not connected")

    booking = load_booking_by_prebook_id(pre_book_id)
    if booking.empty:
        raise HTTPException(status_code=404, detail=f"Booking {pre_book_id} not found")

    row = booking.iloc[0]
    hotel_id = int(row.get("HotelId", 0))
    date_from = str(row.get("DateFrom", ""))

    predicted_price = _get_predicted_price(hotel_id, date_from)
    ci = _get_confidence_interval(hotel_id, date_from)
    occupancy = _get_occupancy_forecast(hotel_id, date_from)
    competitor_price = _get_competitor_price(hotel_id)

    recommender = TradingRecommender()
    result = recommender.analyze_booking(
        row, predicted_price, ci, occupancy, competitor_price,
    )

    return AnalysisResponse(**result)


@router.get("/analyze/portfolio", response_model=PortfolioResponse)
async def analyze_portfolio(
    _key: str = Depends(verify_api_key),
):
    """Analyze the full active booking portfolio."""
    from src.data.trading_db import load_active_bookings, check_connection
    from src.models.recommender import TradingRecommender

    if not check_connection():
        raise HTTPException(status_code=503, detail="Trading DB not connected")

    bookings = load_active_bookings()
    if bookings.empty:
        return PortfolioResponse(
            total_bookings=0, analyzed=0, hotels_in_portfolio=0,
            attention_items=[], attention_count=0,
            recommendation_breakdown={}, statistics={},
            summary="No active bookings",
        )

    # Build predictions dict for all hotels in portfolio
    hotel_ids = bookings["HotelId"].unique()
    predictions = {}
    occupancy_forecasts = {}

    for hid in hotel_ids:
        hid = int(hid)
        hotel_bookings = bookings[bookings["HotelId"] == hid]
        date_from = str(hotel_bookings.iloc[0].get("DateFrom", ""))
        predictions[hid] = _get_predicted_price(hid, date_from)
        occ = _get_occupancy_forecast(hid, date_from)
        if occ is not None:
            occupancy_forecasts[hid] = occ

    recommender = TradingRecommender()
    result = recommender.analyze_portfolio(
        bookings, predictions, occupancy_forecasts or None,
    )

    return PortfolioResponse(**result)


@router.get("/forecast/{hotel_id}", response_model=ForecastResponse)
async def forecast_hotel(
    hotel_id: int,
    days: int = 30,
    include_intervals: bool = True,
    _key: str = Depends(verify_api_key),
):
    """Get price forecast for a specific hotel."""
    from src.api.main import _forecaster

    if _forecaster is None:
        raise HTTPException(status_code=503, detail="No model loaded. Train first via POST /train")

    predictions = _forecaster.predict(
        n_days=days,
        include_intervals=include_intervals,
    )

    return ForecastResponse(
        hotel_id=hotel_id,
        predictions=predictions.to_dict(orient="records"),
        model_name=_forecaster.model_name,
        horizon=days,
    )


@router.get("/recommendations/active")
async def get_active_recommendations(
    _key: str = Depends(verify_api_key),
):
    """Get all current recommendations from the last analysis run.

    Results come from the background scheduler (if running).
    """
    from src.services.scheduler import get_latest_results

    results = get_latest_results()
    if not results:
        return {
            "status": "no_data",
            "message": "No analysis has run yet. Wait for scheduler or trigger via /analyze/portfolio.",
            "recommendations": [],
        }

    return {
        "status": "ok",
        "last_run": results.get("last_run"),
        "portfolio": results.get("portfolio"),
        "recommendations_count": results.get("recommendations_count", 0),
    }


@router.get("/report/daily", response_model=DailyReportResponse)
async def daily_report(
    _key: str = Depends(verify_api_key),
):
    """Generate a daily performance report."""
    from datetime import date
    from src.data.trading_db import load_active_bookings, load_all_bookings, check_connection
    from src.models.recommender import TradingRecommender

    today = str(date.today())

    if not check_connection():
        return DailyReportResponse(
            date=today,
            portfolio_summary={"error": "Trading DB not connected"},
            market_summary={},
            recommendations_count=0,
            top_opportunities=[],
            top_risks=[],
        )

    # Portfolio summary
    active = load_active_bookings()
    recommender = TradingRecommender()

    hotel_ids = active["HotelId"].unique() if not active.empty else []
    predictions = {}
    for hid in hotel_ids:
        hid = int(hid)
        hotel_bookings = active[active["HotelId"] == hid]
        date_from = str(hotel_bookings.iloc[0].get("DateFrom", ""))
        predictions[hid] = _get_predicted_price(hid, date_from)

    portfolio = recommender.analyze_portfolio(active, predictions) if not active.empty else {}

    # Extract top risks (CONSIDER_CANCEL and ALERT items)
    attention = portfolio.get("attention_items", [])
    top_risks = [
        item for item in attention
        if item.get("recommendation") in ("CONSIDER_CANCEL", "ALERT")
    ][:5]

    # Top opportunities (REPRICE items — upside potential)
    top_opps = [
        item for item in attention
        if item.get("recommendation") == "REPRICE"
    ][:5]

    return DailyReportResponse(
        date=today,
        portfolio_summary=portfolio.get("statistics", {}),
        market_summary={
            "total_active": len(active),
            "hotels": len(hotel_ids),
        },
        recommendations_count=len(attention),
        top_opportunities=top_opps,
        top_risks=top_risks,
    )


# ── Helper functions ─────────────────────────────────────────────────

def _get_predicted_price(hotel_id: int, date_from: str) -> float:
    """Get ML-predicted market price. Falls back to push price average."""
    try:
        from src.api.main import _forecaster
        if _forecaster is not None:
            predictions = _forecaster.predict(n_days=30)
            if not predictions.empty:
                return float(predictions["predicted_price"].mean())
    except Exception:
        pass

    # Fallback: use historical average from trading data
    try:
        from src.data.trading_db import load_all_bookings, check_connection
        if check_connection():
            bookings = load_all_bookings(days_back=90)
            if not bookings.empty:
                hotel_bookings = bookings[bookings["HotelId"] == hotel_id]
                if not hotel_bookings.empty:
                    return float(hotel_bookings["PushPrice"].mean())
                return float(bookings["PushPrice"].mean())
    except Exception:
        pass

    return 250.0  # Last resort default


def _get_confidence_interval(
    hotel_id: int, date_from: str,
) -> tuple[float, float] | None:
    """Get confidence interval for predicted price."""
    try:
        from src.api.main import _forecaster
        if _forecaster is not None:
            predictions = _forecaster.predict(n_days=30, include_intervals=True)
            if "lower_80" in predictions.columns and "upper_80" in predictions.columns:
                return (
                    float(predictions["lower_80"].mean()),
                    float(predictions["upper_80"].mean()),
                )
    except Exception:
        pass
    return None


def _get_occupancy_forecast(hotel_id: int, date_from: str) -> float | None:
    """Get occupancy forecast for a hotel."""
    try:
        from src.api.main import _occupancy_predictor
        if _occupancy_predictor is not None:
            import pandas as pd
            future = pd.DataFrame({"date": [pd.Timestamp(date_from)]})
            future["month"] = future["date"].dt.month
            future["day_of_week"] = future["date"].dt.dayofweek
            future["is_weekend"] = future["day_of_week"].isin([4, 5]).astype(int)
            result = _occupancy_predictor.predict(future)
            if "predicted_occupancy" in result.columns:
                return float(result["predicted_occupancy"].iloc[0])
    except Exception:
        pass
    return None


def _get_competitor_price(hotel_id: int) -> float | None:
    """Get competitor average price for a hotel."""
    try:
        from src.api.main import _loader
        if _loader is not None:
            collector = _loader.registry.get("market")
            if collector.is_available():
                market = collector.collect_cached(cache_key="market_snapshot")
                if not market.empty and "price" in market.columns:
                    return float(market["price"].mean())
    except Exception:
        pass
    return None


def _get_seasonal_context(date_str: str) -> dict:
    """Build seasonal context from a date string."""
    import pandas as pd
    try:
        dt = pd.Timestamp(date_str)
        month = dt.month
        season_map = {
            12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "autumn", 10: "autumn", 11: "autumn",
        }

        # Check for Hebrew holidays
        is_holiday = False
        try:
            from pyluach.dates import HebrewDate
            from pyluach.hebrewcal import Year as HebrewYear
            hd = HebrewDate.from_pydate(dt.date())
            year = HebrewYear(hd.year)
            holidays = year.holidays()
            for holiday in holidays:
                if hasattr(holiday, "date") and holiday.date == hd:
                    is_holiday = True
                    break
        except Exception:
            pass

        return {
            "season": season_map.get(month, "unknown"),
            "is_holiday": is_holiday,
            "is_weekend": dt.dayofweek in (4, 5),
            "month": month,
        }
    except Exception:
        return {"season": "unknown", "is_holiday": False, "is_weekend": False}
