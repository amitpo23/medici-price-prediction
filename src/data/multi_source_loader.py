"""Unified ETL pipeline combining all data sources."""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

from src.data.cache import DataCache
from src.data.db_loader import load_daily_pricing, discover_schema
from src.collectors.registry import CollectorRegistry
from src.features.engineering import prepare_features
from config.settings import CACHE_DIR


def build_registry(cache: DataCache | None = None) -> CollectorRegistry:
    """Create and register all available collectors via auto-discovery."""
    if cache is None:
        cache = DataCache(CACHE_DIR)

    registry = CollectorRegistry()
    registry.auto_discover(cache=cache)
    return registry


class MultiSourceLoader:
    """Orchestrate data loading from all sources into a unified dataset."""

    def __init__(self, registry: CollectorRegistry | None = None, cache: DataCache | None = None):
        self.cache = cache or DataCache(CACHE_DIR)
        self.registry = registry or build_registry(self.cache)

    def available_sources(self) -> dict[str, bool]:
        """Check which data sources are currently accessible."""
        result = {}
        for name in self.registry.all_names():
            try:
                collector = self.registry.get(name)
                result[name] = collector.is_available()
            except KeyError:
                result[name] = False

        # Check Azure SQL
        try:
            discover_schema()
            result["azure_sql"] = True
        except (OSError, ConnectionError, ValueError) as e:
            logger.warning("Azure SQL schema discovery failed: %s", e)
            result["azure_sql"] = False

        return result

    def load_pricing_data(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        include_kaggle: bool = True,
        include_market: bool = True,
    ) -> pd.DataFrame:
        """Load and merge pricing data from all available sources.

        Primary: Azure SQL
        Secondary: Kaggle historical data, Google Hotels market data
        """
        parts = []

        # 1. Azure SQL (primary)
        try:
            azure_df = load_daily_pricing(start_date, end_date)
            if not azure_df.empty:
                azure_df["source"] = "azure_sql"
                parts.append(azure_df)
        except (OSError, ConnectionError, ValueError) as e:
            logger.warning("Azure SQL pricing load failed: %s", e)

        # 2. Kaggle historical data (for training breadth)
        if include_kaggle and "kaggle" in self.registry.available():
            try:
                kaggle_df = self.registry.get("kaggle").collect_cached(
                    cache_key="kaggle_booking_demand",
                    dataset_key="hotel_booking_demand",
                )
                if not kaggle_df.empty:
                    parts.append(kaggle_df)
            except (FileNotFoundError, OSError, ValueError, KeyError) as e:
                logger.warning("Kaggle data load failed: %s", e)

        # 3. Market snapshot (competitor context)
        if include_market and "market" in self.registry.available():
            try:
                market_df = self.registry.get("market").collect_cached(
                    cache_key="market_snapshot",
                )
                if not market_df.empty:
                    market_df["source"] = "google_hotels"
                    parts.append(market_df)
            except (ConnectionError, TimeoutError, ValueError, KeyError) as e:
                logger.warning("Market data load failed: %s", e)

        if not parts:
            return pd.DataFrame()

        combined = pd.concat(parts, ignore_index=True)

        # Ensure date column
        if "date" in combined.columns:
            combined["date"] = pd.to_datetime(combined["date"])
            combined = combined.sort_values("date").reset_index(drop=True)

        return combined

    def load_enrichment_data(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        year: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Load all enrichment data (events, weather, CBS stats)."""
        result = {}

        # Events
        if "events" in self.registry.available():
            try:
                result["events"] = self.registry.get("events").collect_cached(
                    cache_key=f"events_{year or 'current'}",
                    year=year,
                )
            except (ConnectionError, TimeoutError, ValueError, KeyError) as e:
                logger.warning("Events enrichment load failed: %s", e)
                result["events"] = pd.DataFrame()
        else:
            result["events"] = pd.DataFrame()

        # Weather
        if "weather" in self.registry.available():
            try:
                result["weather"] = self.registry.get("weather").collect_cached(
                    cache_key=f"weather_{start_date}_{end_date}",
                    start_date=start_date,
                    end_date=end_date,
                )
            except (ConnectionError, TimeoutError, ValueError, KeyError) as e:
                logger.warning("Weather enrichment load failed: %s", e)
                result["weather"] = pd.DataFrame()
        else:
            result["weather"] = pd.DataFrame()

        # CBS statistics
        if "cbs" in self.registry.available():
            try:
                result["cbs"] = self.registry.get("cbs").collect_cached(
                    cache_key="cbs_stats",
                )
            except (ConnectionError, TimeoutError, ValueError, KeyError) as e:
                logger.warning("CBS enrichment load failed: %s", e)
                result["cbs"] = pd.DataFrame()
        else:
            result["cbs"] = pd.DataFrame()

        return result

    def prepare_training_dataset(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Full pipeline: load all data, merge, engineer features, return training-ready df."""
        # 1. Load pricing
        pricing = self.load_pricing_data(start_date, end_date)
        if pricing.empty:
            return pd.DataFrame()

        # 2. Load enrichment
        enrichment = self.load_enrichment_data(start_date, end_date)

        # 2b. Load trading data (if available)
        trading_df = None
        if "trading" in self.registry.available():
            try:
                trading_df = self.registry.get("trading").collect_cached(
                    cache_key="trading_all_bookings",
                    data_type="all_bookings",
                )
            except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                logger.warning("Trading data load failed: %s", e)
                trading_df = None

        # 3. Run feature engineering with all available data
        df = prepare_features(
            pricing,
            date_col="date",
            price_col="price",
            events_df=enrichment.get("events"),
            weather_df=enrichment.get("weather"),
            trading_df=trading_df,
        )

        # 4. Drop rows with NaN from lag features (first ~30 rows)
        lag_cols = [c for c in df.columns if "_lag_" in c]
        if lag_cols:
            df = df.dropna(subset=lag_cols).reset_index(drop=True)

        return df
