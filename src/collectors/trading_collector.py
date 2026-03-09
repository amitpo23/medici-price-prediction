"""Collect trading data from Medici Hotels trading database (medici-db).

Read-only collector — fetches bookings, opportunities, reservations,
and hotel reference data for analysis by the prediction engine.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

from src.collectors.base import BaseCollector
from src.data.trading_db import (
    check_connection,
    load_active_bookings,
    load_all_bookings,
    load_backoffice_opportunities,
    load_historical_prices,
    load_hotels,
    load_opportunities,
    load_reference_data,
    load_reservations,
)


class TradingCollector(BaseCollector):
    """Fetch trading data from medici-db (read-only)."""

    name = "trading"

    def is_available(self) -> bool:
        """Check if medici-db is accessible."""
        return check_connection()

    def collect(self, **kwargs) -> pd.DataFrame:
        """Collect trading data by type.

        Supported data_type values:
            active_bookings, all_bookings, opportunities,
            backoffice, reservations, hotels, historical_prices
        """
        data_type = kwargs.get("data_type", "active_bookings")

        if data_type == "active_bookings":
            return self._collect_active_bookings()
        if data_type == "all_bookings":
            return load_all_bookings(days_back=kwargs.get("days_back", 180))
        if data_type == "opportunities":
            return load_opportunities(days_back=kwargs.get("days_back", 90))
        if data_type == "backoffice":
            return load_backoffice_opportunities(
                days_back=kwargs.get("days_back", 180)
            )
        if data_type == "reservations":
            return load_reservations(days_back=kwargs.get("days_back", 90))
        if data_type == "hotels":
            return load_hotels()
        if data_type == "historical_prices":
            return load_historical_prices()

        return self._collect_active_bookings()

    def _collect_active_bookings(self) -> pd.DataFrame:
        """Collect active bookings (already enriched with hotel names via JOIN)."""
        return load_active_bookings()

    def collect_all_datasets(self) -> dict[str, pd.DataFrame]:
        """Collect all trading datasets as a dict of DataFrames.

        Used by the scheduler for full analysis runs.
        """
        datasets: dict[str, pd.DataFrame] = {}

        datasets["active_bookings"] = self.collect_cached(
            cache_key="trading_active_bookings", data_type="active_bookings"
        )
        datasets["all_bookings"] = self.collect_cached(
            cache_key="trading_all_bookings", data_type="all_bookings"
        )
        datasets["opportunities"] = self.collect_cached(
            cache_key="trading_opportunities", data_type="opportunities"
        )
        datasets["backoffice"] = self.collect_cached(
            cache_key="trading_backoffice", data_type="backoffice"
        )
        datasets["reservations"] = self.collect_cached(
            cache_key="trading_reservations", data_type="reservations"
        )
        datasets["hotels"] = self.collect_cached(
            cache_key="trading_hotels", data_type="hotels"
        )

        try:
            datasets["reference"] = load_reference_data()
        except (ConnectionError, OSError, ValueError) as e:
            logger.warning(f"Failed to load reference data from trading DB: {e}")
            datasets["reference"] = {}

        return datasets
