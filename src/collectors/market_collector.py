"""Collect competitor hotel pricing from Google Hotels via SerpApi."""
from __future__ import annotations

from datetime import date, timedelta
import logging

import pandas as pd

from src.collectors.base import BaseCollector
from config.settings import SERPAPI_KEY, ISRAEL_CITIES

logger = logging.getLogger(__name__)


class MarketCollector(BaseCollector):
    """Fetch competitor hotel prices from Google Hotels via SerpApi."""

    name = "market"

    def is_available(self) -> bool:
        if not SERPAPI_KEY:
            return False
        try:
            from serpapi import GoogleSearch
            search = GoogleSearch({
                "engine": "google_hotels",
                "q": "hotels in Tel Aviv Israel",
                "check_in_date": date.today().isoformat(),
                "check_out_date": (date.today() + timedelta(days=1)).isoformat(),
                "currency": "ILS",
                "api_key": SERPAPI_KEY,
            })
            result = search.get_dict()
            return "error" not in result
        except (ImportError, ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"SerpApi/Google Hotels not available: {e}")
            return False

    def collect(
        self,
        city: str = "Tel Aviv",
        check_in: str | None = None,
        check_out: str | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch hotel prices for a city from Google Hotels."""
        from serpapi import GoogleSearch

        if check_in is None:
            check_in = (date.today() + timedelta(days=7)).isoformat()
        if check_out is None:
            check_out = (date.today() + timedelta(days=8)).isoformat()

        try:
            search = GoogleSearch({
                "engine": "google_hotels",
                "q": f"hotels in {city} Israel",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "currency": "ILS",
                "gl": "il",
                "hl": "en",
                "api_key": SERPAPI_KEY,
            })
            result = search.get_dict()
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"Failed to fetch Google Hotels data for {city}: {e}")
            return pd.DataFrame()

        properties = result.get("properties", [])
        records = []
        for p in properties:
            price = p.get("rate_per_night", {}).get("extracted_lowest")
            if price is None:
                price = p.get("total_rate", {}).get("extracted_lowest")

            records.append({
                "hotel_id": p.get("name", "").lower().replace(" ", "_")[:50],
                "name": p.get("name", ""),
                "city": city,
                "star_rating": p.get("overall_rating"),
                "price": price,
                "currency": "ILS",
                "check_in": check_in,
                "check_out": check_out,
                "latitude": p.get("gps_coordinates", {}).get("latitude"),
                "longitude": p.get("gps_coordinates", {}).get("longitude"),
                "hotel_type": p.get("type", ""),
                "amenities": ", ".join(p.get("amenities", [])),
                "source": "google_hotels",
            })

        df = pd.DataFrame(records)
        if not df.empty:
            df["date"] = pd.to_datetime(check_in)
            df["price"] = pd.to_numeric(df["price"], errors="coerce")
        return df

    def collect_market_snapshot(self, cities: list[str] | None = None) -> pd.DataFrame:
        """Get current pricing across all Israeli hotel cities."""
        cities = cities or list(ISRAEL_CITIES.keys())
        all_data = []

        for city in cities:
            df = self.collect_cached(cache_key=f"market_{city}", city=city)
            if not df.empty:
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data, ignore_index=True)
