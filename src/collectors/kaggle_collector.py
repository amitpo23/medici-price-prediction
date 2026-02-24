"""Collect hotel pricing datasets from Kaggle."""

import os
import zipfile
from pathlib import Path

import pandas as pd

from src.collectors.base import BaseCollector
from config.settings import KAGGLE_USERNAME, KAGGLE_KEY, RAW_DATA_DIR


class KaggleCollector(BaseCollector):
    """Download and normalize hotel pricing datasets from Kaggle."""

    name = "kaggle"

    DATASETS = {
        "hotel_booking_demand": "jessemostipak/hotel-booking-demand",
        "hotel_prices": "djusdjus/hotel-rooms-prices-dataset",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._download_dir = RAW_DATA_DIR / "kaggle"

    def is_available(self) -> bool:
        if not KAGGLE_USERNAME or not KAGGLE_KEY:
            return False
        # Set env vars for kaggle API
        os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
        os.environ["KAGGLE_KEY"] = KAGGLE_KEY
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            return True
        except Exception:
            return False

    def collect(self, dataset_key: str = "hotel_booking_demand", **kwargs) -> pd.DataFrame:
        """Download and normalize a Kaggle dataset."""
        if dataset_key not in self.DATASETS:
            raise ValueError(f"Unknown dataset: {dataset_key}. Available: {list(self.DATASETS.keys())}")

        self._download_dir.mkdir(parents=True, exist_ok=True)
        dataset_ref = self.DATASETS[dataset_key]
        local_dir = self._download_dir / dataset_key

        # Check if already downloaded
        if not local_dir.exists() or not list(local_dir.glob("*.csv")):
            self._download_dataset(dataset_ref, local_dir)

        csv_files = list(local_dir.glob("*.csv"))
        if not csv_files:
            return pd.DataFrame()

        df = pd.read_csv(csv_files[0])

        normalizer = {
            "hotel_booking_demand": self._normalize_booking_demand,
            "hotel_prices": self._normalize_hotel_prices,
        }
        if dataset_key in normalizer:
            df = normalizer[dataset_key](df)

        return df

    def _download_dataset(self, dataset_ref: str, local_dir: Path) -> None:
        """Download a dataset from Kaggle."""
        os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
        os.environ["KAGGLE_KEY"] = KAGGLE_KEY

        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()

        local_dir.mkdir(parents=True, exist_ok=True)
        api.dataset_download_files(dataset_ref, path=str(local_dir), unzip=True)

    def _normalize_booking_demand(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize the jessemostipak/hotel-booking-demand dataset.

        This dataset has columns like: hotel, arrival_date_year, arrival_date_month,
        arrival_date_day_of_month, adr, is_canceled, etc.
        """
        if "adr" not in df.columns:
            return df

        # Build a date column from parts
        month_map = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12,
        }
        df = df.copy()
        df["month_num"] = df["arrival_date_month"].map(month_map)
        df["date"] = pd.to_datetime(
            df["arrival_date_year"].astype(str) + "-" +
            df["month_num"].astype(str) + "-" +
            df["arrival_date_day_of_month"].astype(str),
            errors="coerce",
        )

        # Map hotel type to star approximation
        star_map = {"Resort Hotel": 4.0, "City Hotel": 3.0}
        df["star_rating"] = df["hotel"].map(star_map)

        # Aggregate to daily averages
        daily = df.groupby(["date", "hotel"]).agg(
            price=("adr", "mean"),
            occupancy_rate=("is_canceled", lambda x: 1 - x.mean()),
            total_bookings=("adr", "count"),
        ).reset_index()

        daily["source"] = "kaggle_booking_demand"
        daily["hotel_id"] = daily["hotel"].str.lower().str.replace(" ", "_")
        daily["city"] = "Unknown"  # Dataset doesn't specify city
        daily["currency"] = "EUR"

        return daily[["date", "hotel_id", "price", "currency", "star_rating",
                       "occupancy_rate", "source", "city"]].dropna(subset=["date", "price"])

    def _normalize_hotel_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize the djusdjus/hotel-rooms-prices-dataset."""
        df = df.copy()
        # This dataset varies — adapt based on actual columns
        col_map = {}
        for col in df.columns:
            lower = col.lower()
            if "price" in lower or "rate" in lower or "cost" in lower:
                col_map["price"] = col
            elif "star" in lower or "rating" in lower:
                col_map["star_rating"] = col
            elif "city" in lower or "location" in lower:
                col_map["city"] = col
            elif "hotel" in lower or "name" in lower:
                col_map["hotel_id"] = col
            elif "date" in lower:
                col_map["date"] = col

        result = pd.DataFrame()
        if "price" in col_map:
            result["price"] = pd.to_numeric(df[col_map["price"]], errors="coerce")
        if "star_rating" in col_map:
            result["star_rating"] = pd.to_numeric(df[col_map["star_rating"]], errors="coerce")
        if "city" in col_map:
            result["city"] = df[col_map["city"]]
        if "hotel_id" in col_map:
            result["hotel_id"] = df[col_map["hotel_id"]].astype(str)
        if "date" in col_map:
            result["date"] = pd.to_datetime(df[col_map["date"]], errors="coerce")

        result["source"] = "kaggle_hotel_prices"
        return result.dropna(subset=["price"])
