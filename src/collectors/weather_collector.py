"""Collect weather data from Open-Meteo (free, no API key)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import requests

from src.collectors.base import BaseCollector
from config.settings import ISRAEL_CITIES

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherCollector(BaseCollector):
    """Fetch historical and forecast weather for Israeli cities."""

    name = "weather"

    def is_available(self) -> bool:
        try:
            r = requests.get(FORECAST_URL, params={
                "latitude": 32.08, "longitude": 34.78,
                "daily": "temperature_2m_max", "timezone": "Asia/Jerusalem",
                "forecast_days": 1,
            }, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def collect(
        self,
        cities: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch weather for specified cities and date range."""
        cities = cities or list(ISRAEL_CITIES.keys())
        if start_date is None:
            start_date = (date.today() - timedelta(days=365)).isoformat()
        if end_date is None:
            end_date = date.today().isoformat()

        all_data = []
        for city in cities:
            if city not in ISRAEL_CITIES:
                continue
            lat, lon = ISRAEL_CITIES[city]
            df = self._fetch_city(city, lat, lon, start_date, end_date)
            if not df.empty:
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data, ignore_index=True)

    def collect_forecast(self, cities: list[str] | None = None, days: int = 16) -> pd.DataFrame:
        """Fetch weather forecast for the next N days."""
        cities = cities or list(ISRAEL_CITIES.keys())
        all_data = []

        for city in cities:
            if city not in ISRAEL_CITIES:
                continue
            lat, lon = ISRAEL_CITIES[city]
            try:
                r = requests.get(FORECAST_URL, params={
                    "latitude": lat, "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                    "timezone": "Asia/Jerusalem",
                    "forecast_days": days,
                }, timeout=15)
                r.raise_for_status()
                data = r.json()["daily"]
                df = pd.DataFrame({
                    "date": pd.to_datetime(data["time"]),
                    "city": city,
                    "temperature_max": data["temperature_2m_max"],
                    "temperature_min": data["temperature_2m_min"],
                    "precipitation_mm": data["precipitation_sum"],
                    "weather_code": data["weather_code"],
                })
                all_data.append(df)
            except Exception:
                continue

        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data, ignore_index=True)

    def _fetch_city(
        self, city: str, lat: float, lon: float, start_date: str, end_date: str,
    ) -> pd.DataFrame:
        """Fetch historical weather for a single city."""
        try:
            r = requests.get(ARCHIVE_URL, params={
                "latitude": lat, "longitude": lon,
                "start_date": start_date, "end_date": end_date,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                "timezone": "Asia/Jerusalem",
            }, timeout=30)
            r.raise_for_status()
            data = r.json()["daily"]
            return pd.DataFrame({
                "date": pd.to_datetime(data["time"]),
                "city": city,
                "temperature_max": data["temperature_2m_max"],
                "temperature_min": data["temperature_2m_min"],
                "precipitation_mm": data["precipitation_sum"],
                "weather_code": data["weather_code"],
            })
        except Exception:
            return pd.DataFrame()
