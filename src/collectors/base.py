"""Abstract base class for all data collectors."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.data.cache import DataCache


class BaseCollector(ABC):
    """Base class for all data collectors."""

    name: str = "base"

    def __init__(self, cache: DataCache | None = None):
        self.cache = cache

    @abstractmethod
    def collect(self, **kwargs) -> pd.DataFrame:
        """Fetch data and return as normalized DataFrame."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this collector's data source is accessible."""

    def collect_cached(self, cache_key: str, **kwargs) -> pd.DataFrame:
        """Collect with caching. Falls back to fresh fetch on cache miss."""
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        df = self.collect(**kwargs)

        if self.cache and not df.empty:
            self.cache.set(cache_key, df)

        return df
