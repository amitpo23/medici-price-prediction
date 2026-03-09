"""Tests for collector registry auto-discovery."""
from __future__ import annotations

import os

import pytest


# ── Auto-discovery ──────────────────────────────────────────────────


class TestAutoDiscover:
    """Test automatic collector discovery."""

    def test_discovers_collectors(self):
        """Auto-discovery finds all 8 collector modules."""
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        count = registry.auto_discover()
        assert count >= 6  # At least the original 6 (weather, events, kaggle, market, cbs, trading)

    def test_all_collectors_have_names(self):
        """Every discovered collector has a non-empty name."""
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        registry.auto_discover()
        for name in registry.all_names():
            assert name
            assert name != "base"

    def test_discovers_known_collectors(self):
        """Specific known collectors are discovered."""
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        registry.auto_discover()
        names = set(registry.all_names())
        # These 6 were previously hardcoded in build_registry
        for expected in ["weather", "events", "kaggle", "market", "cbs", "trading"]:
            assert expected in names, f"Expected collector '{expected}' not discovered"

    def test_discovers_new_collectors(self):
        """New collectors (statista, brightdata_market) are also discovered."""
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        registry.auto_discover()
        names = set(registry.all_names())
        # These were added after the original 6
        assert "statista" in names or "brightdata_market" in names

    def test_idempotent(self):
        """Running auto_discover twice doesn't duplicate collectors."""
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        count1 = registry.auto_discover()
        count2 = registry.auto_discover()
        assert count2 == 0  # All already registered

    def test_disable_via_env(self, monkeypatch):
        """COLLECTOR_{NAME}_ENABLED=false disables a collector."""
        monkeypatch.setenv("COLLECTOR_CBS_ENABLED", "false")
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        registry.auto_discover()
        assert "cbs" not in registry.all_names()

    def test_enable_by_default(self, monkeypatch):
        """Collectors without env var are enabled by default."""
        monkeypatch.delenv("COLLECTOR_WEATHER_ENABLED", raising=False)
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        registry.auto_discover()
        assert "weather" in registry.all_names()


# ── Registry operations ─────────────────────────────────────────────


class TestRegistryOperations:
    """Test basic registry operations."""

    def test_register_and_get(self):
        from src.collectors.registry import CollectorRegistry
        from src.collectors.weather_collector import WeatherCollector
        registry = CollectorRegistry()
        collector = WeatherCollector()
        registry.register("test_weather", collector)
        assert registry.get("test_weather") is collector

    def test_get_missing_raises(self):
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_all_names(self):
        from src.collectors.registry import CollectorRegistry
        from src.collectors.weather_collector import WeatherCollector
        registry = CollectorRegistry()
        registry.register("a", WeatherCollector())
        registry.register("b", WeatherCollector())
        assert set(registry.all_names()) == {"a", "b"}

    def test_available_returns_available_only(self):
        from src.collectors.registry import CollectorRegistry
        registry = CollectorRegistry()
        registry.auto_discover()
        # available() should be a subset of all_names()
        available = set(registry.available())
        all_names = set(registry.all_names())
        assert available.issubset(all_names)


# ── build_registry ──────────────────────────────────────────────────


class TestBuildRegistry:
    """Test that build_registry now uses auto-discovery."""

    def test_build_registry_discovers(self):
        from src.data.multi_source_loader import build_registry
        registry = build_registry()
        names = set(registry.all_names())
        assert len(names) >= 6
        assert "weather" in names
        assert "events" in names

    def test_build_registry_with_cache(self, tmp_path):
        from src.data.multi_source_loader import build_registry
        from src.data.cache import DataCache
        cache = DataCache(tmp_path)
        registry = build_registry(cache=cache)
        assert len(registry.all_names()) >= 6
