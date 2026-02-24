"""Unified data schemas for all data sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class HotelRecord:
    hotel_id: str
    name: str
    city: str
    country: str = "IL"
    star_rating: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    region: str | None = None
    hotel_type: str | None = None


@dataclass
class PriceRecord:
    date: date
    hotel_id: str
    price: float
    currency: str = "ILS"
    room_type: str | None = None
    source: str = "azure_sql"
    occupancy_rate: float | None = None
    competitor_avg_price: float | None = None
    star_rating: float | None = None
    city: str | None = None


@dataclass
class EventRecord:
    event_id: str
    name: str
    start_date: date
    end_date: date
    city: str
    country: str = "IL"
    category: str = "other"  # holiday, conference, festival, sports
    expected_attendance: int | None = None
    source: str = "hebcal"


@dataclass
class WeatherRecord:
    date: date
    city: str
    temperature_max: float
    temperature_min: float
    precipitation_mm: float
    weather_code: int = 0
