"""Collector registry for pipeline orchestration."""

import pandas as pd

from src.collectors.base import BaseCollector


class CollectorRegistry:
    """Registry that manages all data collectors."""

    def __init__(self):
        self._collectors: dict[str, BaseCollector] = {}

    def register(self, name: str, collector: BaseCollector) -> None:
        self._collectors[name] = collector

    def get(self, name: str) -> BaseCollector:
        return self._collectors[name]

    def available(self) -> list[str]:
        """Return names of collectors that are currently accessible."""
        return [name for name, c in self._collectors.items() if c.is_available()]

    def collect_all(self, **kwargs) -> dict[str, pd.DataFrame]:
        """Run all available collectors and return results."""
        results = {}
        for name in self.available():
            try:
                results[name] = self._collectors[name].collect_cached(
                    cache_key=f"{name}_latest", **kwargs
                )
            except Exception as e:
                print(f"Collector '{name}' failed: {e}")
        return results
