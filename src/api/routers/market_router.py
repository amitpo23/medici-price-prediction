"""Market data endpoints — external data, flights, events, benchmarks, knowledge."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

market_router = APIRouter()


@market_router.get("/flights/demand")
async def salesoffice_flights_demand():
    """Flight demand indicator for Miami — based on Kiwi.com data."""
    from src.analytics.flights_store import get_demand_summary, init_flights_db

    init_flights_db()
    summary = get_demand_summary("Miami")
    return JSONResponse(content=summary)


@market_router.get("/events")
async def salesoffice_events():
    """Events and conferences in Miami — demand indicators."""
    from src.analytics.events_store import init_events_db, seed_major_events, get_events_summary

    init_events_db()
    seed_major_events()
    summary = get_events_summary()
    return JSONResponse(content=summary)


@market_router.get("/data-sources")
async def salesoffice_data_sources():
    """Registry of all data sources (active + planned)."""
    from src.analytics.data_sources import get_sources_summary

    return JSONResponse(content=get_sources_summary())


@market_router.get("/benchmarks")
async def salesoffice_benchmarks():
    """Booking behavior benchmarks — seasonality, lead time, cancellation models."""
    from src.analytics.booking_benchmarks import get_benchmarks_summary

    return JSONResponse(content=get_benchmarks_summary())


@market_router.get("/knowledge")
async def salesoffice_knowledge():
    """Hotel knowledge base — competitive landscape from TBO dataset."""
    from src.analytics.hotel_knowledge import get_knowledge_summary

    return JSONResponse(content=get_knowledge_summary())


@market_router.get("/knowledge/{hotel_id}")
async def salesoffice_hotel_profile(hotel_id: int):
    """Detailed profile for a specific SalesOffice hotel."""
    from src.analytics.hotel_knowledge import get_hotel_profile

    profile = get_hotel_profile(hotel_id)
    if "error" in profile:
        raise HTTPException(status_code=404, detail=profile["error"])
    return JSONResponse(content=profile)


# ── Market Data endpoints (mega-tables) ──────────────────────────────


@market_router.get("/market/search-data")
def market_search_data(hotel_id: int | None = None, days_back: int = 30):
    """AI Search Hotel Data — price history from 8.5M search records."""
    try:
        from src.data.trading_db import load_ai_search_data
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_ai_search_data(hotel_ids=hotel_ids, days_back=days_back)
        return {
            "source": "AI_Search_HotelData",
            "total_records": len(df),
            "hotels": df["HotelId"].nunique() if not df.empty else 0,
            "date_range": {
                "from": str(df["UpdatedAt"].min()) if not df.empty else None,
                "to": str(df["UpdatedAt"].max()) if not df.empty else None,
            },
            "records": df.to_dict(orient="records")[:500],
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Market data query failed: {e}")


@market_router.get("/market/search-summary")
def market_search_summary(hotel_id: int | None = None):
    """Aggregated market pricing stats per hotel from AI search data."""
    try:
        from src.data.trading_db import load_ai_search_summary
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_ai_search_summary(hotel_ids=hotel_ids)
        return {
            "source": "AI_Search_HotelData",
            "total_hotels": len(df),
            "hotels": df.to_dict(orient="records"),
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Summary query failed: {e}")


@market_router.get("/market/search-results")
def market_search_results(hotel_id: int | None = None, days_back: int = 7):
    """Search Results Poll Log — net/gross prices, providers, room details."""
    try:
        from src.data.trading_db import load_search_results_summary
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_search_results_summary(hotel_ids=hotel_ids)
        return {
            "source": "SearchResultsSessionPollLog",
            "total_hotels": len(df),
            "hotels": df.to_dict(orient="records"),
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Search results query failed: {e}")


@market_router.get("/market/price-updates")
def market_price_updates(days_back: int = 30):
    """Room price change events — every price update tracked."""
    try:
        from src.data.trading_db import load_price_updates
        df = load_price_updates(days_back=days_back)
        return {
            "source": "RoomPriceUpdateLog",
            "total_updates": len(df),
            "unique_rooms": df["PreBookId"].nunique() if not df.empty else 0,
            "updates": df.to_dict(orient="records")[:500],
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Price updates query failed: {e}")


@market_router.get("/market/price-velocity")
def market_price_velocity(hotel_id: int | None = None):
    """Price change velocity per hotel — how fast prices move."""
    try:
        from src.data.trading_db import load_price_update_velocity
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_price_update_velocity(hotel_ids=hotel_ids)
        # Replace NaN/NaT with None for JSON serialization
        df = df.where(df.notna(), None)
        records = df.to_dict(orient="records")
        # Convert datetime objects to strings
        for rec in records:
            for k, v in rec.items():
                if hasattr(v, "isoformat"):
                    rec[k] = v.isoformat()
        return {
            "source": "RoomPriceUpdateLog",
            "hotels": records,
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Velocity query failed: {e}")


@market_router.get("/market/competitors/{hotel_id}")
def market_competitors(hotel_id: int, radius_km: float = 5.0,
                              stars: int | None = None):
    """Find competitor hotels within radius using geo coordinates."""
    try:
        from src.data.trading_db import load_competitor_hotels
        df = load_competitor_hotels(hotel_id, radius_km=radius_km, stars=stars)
        return {
            "hotel_id": hotel_id,
            "radius_km": radius_km,
            "total_competitors": len(df),
            "competitors": df.to_dict(orient="records"),
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Competitor query failed: {e}")


@market_router.get("/market/prebooks")
def market_prebooks(hotel_id: int | None = None, days_back: int = 90):
    """Pre-booking data with provider pricing and cancellation policies."""
    try:
        from src.data.trading_db import load_prebooks
        hotel_ids = [hotel_id] if hotel_id else None
        df = load_prebooks(hotel_ids=hotel_ids, days_back=days_back)
        return {
            "source": "MED_PreBook",
            "total_prebooks": len(df),
            "prebooks": df.to_dict(orient="records"),
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Prebook query failed: {e}")


@market_router.get("/market/cancellations")
def market_cancellations(days_back: int = 365):
    """Booking cancellation history with reasons."""
    try:
        from src.data.trading_db import load_cancellations
        df = load_cancellations(days_back=days_back)
        return {
            "source": "MED_CancelBook",
            "total_cancellations": len(df),
            "cancellations": df.to_dict(orient="records"),
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Cancellation query failed: {e}")


@market_router.get("/market/hotels-geo")
def market_hotels_geo():
    """Hotel metadata with lat/long, stars, country."""
    try:
        from src.data.trading_db import load_hotels_with_geo
        df = load_hotels_with_geo()
        return {
            "source": "Med_Hotels + Med_Hotels_instant",
            "total_hotels": len(df),
            "hotels": df.to_dict(orient="records")[:200],
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Geo query failed: {e}")


@market_router.get("/market/weather")
async def market_weather():
    """Miami weather forecast + hurricane proximity status."""
    from src.analytics.miami_weather import get_weather_forecast, _check_hurricane_proximity
    return {
        "adjustments": get_weather_forecast(days=14),
        "hurricane_adj": _check_hurricane_proximity(),
    }


@market_router.get("/market/xotelo")
async def market_xotelo():
    """Competitor rates from Xotelo for all 4 Miami hotels."""
    from src.analytics.xotelo_store import get_rates_summary
    hotel_ids = [66814, 854881, 20702, 24982]
    return {str(hid): get_rates_summary(hid) for hid in hotel_ids}


@market_router.get("/market/fred")
async def market_fred():
    """FRED economic indicators for Miami hotel market context."""
    from src.analytics.fred_store import get_fred_indicators
    return get_fred_indicators()


@market_router.get("/market/kaggle-bookings")
async def market_kaggle_bookings():
    """Lead-time price curves + DOW premiums from Kaggle Hotel Booking Demand dataset."""
    from src.analytics.kaggle_bookings import get_summary
    return get_summary()


@market_router.get("/market/makcorps")
async def market_makcorps():
    """Makcorps historical OTA price data for our 4 Miami hotels."""
    from src.analytics.makcorps_store import get_summary
    return get_summary()


@market_router.get("/market/db-overview")
def market_db_overview():
    """Full database overview — all tables with row counts."""
    try:
        from src.data.trading_db import run_trading_query
        df = run_trading_query("""
            SELECT t.name AS table_name, p.rows AS row_count,
                   SUM(a.total_pages) * 8 / 1024 AS size_mb
            FROM sys.tables t
            INNER JOIN sys.indexes i ON t.object_id = i.object_id
            INNER JOIN sys.partitions p ON i.object_id = p.object_id
                AND i.index_id = p.index_id
            INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE i.index_id <= 1
            GROUP BY t.name, p.rows
            ORDER BY p.rows DESC
        """)
        return {
            "total_tables": len(df),
            "total_rows": int(df["row_count"].sum()),
            "total_size_mb": int(df["size_mb"].sum()),
            "tables": df.to_dict(orient="records"),
        }
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"DB overview failed: {e}")


@market_router.get("/cache/status")
def cache_status():
    """Cache status — regions, sizes, hit rates."""
    from src.utils.cache_manager import cache

    return JSONResponse(content=cache.status())
