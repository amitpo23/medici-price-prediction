"""Collector registry with auto-discovery for pipeline orchestration.

Auto-discovers all BaseCollector subclasses in the src/collectors/ directory,
instantiates them, and registers them by their `name` attribute.

Collectors can be enabled/disabled via COLLECTOR_{NAME}_ENABLED env vars.

Usage:
    from src.collectors.registry import CollectorRegistry
    registry = CollectorRegistry()
    registry.auto_discover()  # Scans src/collectors/ for subclasses
    results = registry.collect_all()
"""
from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

import pandas as pd

from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Directory containing collector modules
_COLLECTORS_DIR = Path(__file__).parent


class CollectorRegistry:
    """Registry that manages all data collectors with auto-discovery."""

    def __init__(self):
        self._collectors: dict[str, BaseCollector] = {}

    def register(self, name: str, collector: BaseCollector) -> None:
        """Register a collector by name."""
        self._collectors[name] = collector
        logger.debug("Registered collector: %s (%s)", name, type(collector).__name__)

    def get(self, name: str) -> BaseCollector:
        """Get a registered collector by name."""
        return self._collectors[name]

    def all_names(self) -> list[str]:
        """Return all registered collector names."""
        return list(self._collectors.keys())

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
            except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                logger.warning("Collector '%s' failed: %s", name, e)
        return results

    def auto_discover(self, cache=None) -> int:
        """Scan src/collectors/ for BaseCollector subclasses and register them.

        Skips collectors disabled via COLLECTOR_{NAME}_ENABLED=false env vars.

        Args:
            cache: Optional DataCache instance to pass to collectors.

        Returns:
            Number of collectors registered.
        """
        registered = 0

        for module_path in sorted(_COLLECTORS_DIR.glob("*_collector.py")):
            module_name = module_path.stem
            full_module = f"src.collectors.{module_name}"

            try:
                module = importlib.import_module(full_module)
            except (ImportError, OSError) as e:
                logger.warning("Failed to import collector module %s: %s", full_module, e)
                continue

            # Find all BaseCollector subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseCollector)
                    and attr is not BaseCollector
                    and hasattr(attr, "name")
                    and attr.name != "base"
                ):
                    collector_name = attr.name

                    # Check env var: COLLECTOR_{NAME}_ENABLED (default true)
                    env_key = f"COLLECTOR_{collector_name.upper()}_ENABLED"
                    enabled = os.environ.get(env_key, "true").lower()
                    if enabled in ("false", "0", "no"):
                        logger.info("Collector '%s' disabled via %s", collector_name, env_key)
                        continue

                    # Skip if already registered
                    if collector_name in self._collectors:
                        continue

                    try:
                        instance = attr(cache=cache)
                        self.register(collector_name, instance)
                        registered += 1
                    except (TypeError, OSError, ValueError) as e:
                        logger.warning(
                            "Failed to instantiate collector %s (%s): %s",
                            collector_name, attr_name, e,
                        )

        logger.info("Auto-discovery registered %d collectors: %s", registered, self.all_names())
        return registered
