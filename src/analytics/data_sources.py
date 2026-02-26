"""Registry of external data sources for hotel price enrichment.

Each source has: name, url, category, access method, cost, status, and
a description of what metrics it provides.

Used by the dashboard to show available data pipelines.
"""
from __future__ import annotations

DATA_SOURCES = [
    {
        "id": "salesoffice",
        "name": "SalesOffice DB",
        "url": "medici-db (Azure SQL)",
        "category": "Internal Pricing",
        "access": "SQL query",
        "cost": "Free (internal)",
        "status": "active",
        "metrics": "Room prices, booking status, price history (3,906 records)",
        "update_freq": "Hourly",
    },
    {
        "id": "kiwi_flights",
        "name": "Kiwi.com Flights",
        "url": "https://www.kiwi.com",
        "category": "Travel Demand",
        "access": "MCP Tool",
        "cost": "Free",
        "status": "active",
        "metrics": "Flight prices/availability to Miami from 5 US cities",
        "update_freq": "On demand",
    },
    {
        "id": "open_meteo",
        "name": "Open-Meteo Weather",
        "url": "https://open-meteo.com",
        "category": "Weather",
        "access": "REST API (no key)",
        "cost": "Free",
        "status": "planned",
        "metrics": "Temperature, precipitation, UV index, weather codes",
        "update_freq": "Daily",
    },
    {
        "id": "predicthq",
        "name": "PredictHQ Events",
        "url": "https://www.predicthq.com",
        "category": "Events & Conferences",
        "access": "REST API (key required)",
        "cost": "Freemium (14-day trial)",
        "status": "planned",
        "metrics": "Event attendance predictions, accommodation impact, rank scores",
        "update_freq": "Daily",
    },
    {
        "id": "seatgeek",
        "name": "SeatGeek Events",
        "url": "https://seatgeek.com",
        "category": "Events & Conferences",
        "access": "REST API (free key)",
        "cost": "Free (500 events)",
        "status": "planned",
        "metrics": "Event dates, venues, ticket prices, popularity scores",
        "update_freq": "Daily",
    },
    {
        "id": "xotelo",
        "name": "Xotelo Hotel Prices",
        "url": "https://xotelo.com",
        "category": "Competitor Pricing",
        "access": "REST API (no key)",
        "cost": "Free",
        "status": "planned",
        "metrics": "Multi-OTA rates (Booking, Expedia, Hotels.com), pricing heatmap",
        "update_freq": "Daily",
    },
    {
        "id": "fred",
        "name": "FRED Economic Data",
        "url": "https://fred.stlouisfed.org",
        "category": "Economic Indicators",
        "access": "REST API (free key)",
        "cost": "Free",
        "status": "planned",
        "metrics": "CPI Lodging index, FL unemployment, consumer confidence",
        "update_freq": "Monthly",
    },
    {
        "id": "gmcvb",
        "name": "GMCVB Miami Tourism",
        "url": "https://www.miamiandbeaches.com",
        "category": "Hotel Industry Stats",
        "access": "PDF download + parse",
        "cost": "Free",
        "status": "planned",
        "metrics": "Weekly occupancy, ADR, RevPAR for Miami-Dade County",
        "update_freq": "Weekly",
    },
    {
        "id": "mia_airport",
        "name": "MIA Airport Traffic",
        "url": "https://www.miami-airport.com",
        "category": "Tourism Demand",
        "access": "PDF download + parse",
        "cost": "Free",
        "status": "planned",
        "metrics": "Monthly passenger volumes (55.9M/year), domestic vs international",
        "update_freq": "Monthly",
    },
    {
        "id": "bls",
        "name": "BLS Hotel CPI",
        "url": "https://www.bls.gov",
        "category": "Economic Indicators",
        "access": "REST API (free key)",
        "cost": "Free",
        "status": "planned",
        "metrics": "Hotel price index, accommodation employment, wage data",
        "update_freq": "Monthly",
    },
    {
        "id": "serpapi_hotels",
        "name": "Google Hotels (SerpApi)",
        "url": "https://serpapi.com",
        "category": "Competitor Pricing",
        "access": "REST API (key required)",
        "cost": "Freemium (100/mo)",
        "status": "planned",
        "metrics": "Real-time competitor hotel rates, star ratings, amenities",
        "update_freq": "Daily",
    },
    {
        "id": "miami_events_hardcoded",
        "name": "Miami Major Events Calendar",
        "url": "Internal hardcoded list",
        "category": "Events & Conferences",
        "access": "Hardcoded",
        "cost": "Free",
        "status": "active",
        "metrics": "8 major events (Art Basel, Ultra, F1, Miami Open, etc.)",
        "update_freq": "Annual",
    },
]


def get_sources_summary() -> dict:
    """Return summary of data sources grouped by status."""
    active = [s for s in DATA_SOURCES if s["status"] == "active"]
    planned = [s for s in DATA_SOURCES if s["status"] == "planned"]
    return {
        "total": len(DATA_SOURCES),
        "active": len(active),
        "planned": len(planned),
        "sources": DATA_SOURCES,
        "active_sources": active,
        "planned_sources": planned,
    }
