"""Tests for the unified CacheManager."""
from __future__ import annotations

import threading
import time

import pytest

from src.utils.cache_manager import CacheManager, CacheRegion


# ── CacheRegion tests ─────────────────────────────────────────────────


class TestCacheRegion:
    """Test CacheRegion — the building block for each cache."""

    def test_get_set_basic(self):
        """Basic set and get returns the value."""
        region = CacheRegion(name="test", ttl=60)
        region.set("key1", {"data": 42})
        assert region.get("key1") == {"data": 42}

    def test_get_missing_key_returns_none(self):
        """Getting a non-existent key returns None."""
        region = CacheRegion(name="test", ttl=60)
        assert region.get("missing") is None

    def test_ttl_expiration(self):
        """Entries expire after TTL seconds."""
        region = CacheRegion(name="test", ttl=1)
        region.set("key1", "value1")
        assert region.get("key1") == "value1"
        time.sleep(1.1)
        assert region.get("key1") is None

    def test_ttl_zero_never_expires(self):
        """TTL=0 means entries never expire."""
        region = CacheRegion(name="test", ttl=0)
        region.set("key1", "value1")
        # Can't actually wait forever — just verify it returns the value
        assert region.get("key1") == "value1"

    def test_max_size_eviction(self):
        """When max_size is exceeded, oldest entries are evicted."""
        region = CacheRegion(name="test", ttl=60, max_size=3)
        region.set("a", 1)
        time.sleep(0.01)
        region.set("b", 2)
        time.sleep(0.01)
        region.set("c", 3)
        assert region.size == 3
        # Adding 4th should evict oldest ("a")
        time.sleep(0.01)
        region.set("d", 4)
        assert region.size == 3
        assert region.get("a") is None
        assert region.get("b") == 2
        assert region.get("d") == 4

    def test_max_size_zero_unlimited(self):
        """max_size=0 means no size limit."""
        region = CacheRegion(name="test", ttl=60, max_size=0)
        for i in range(100):
            region.set(f"key{i}", i)
        assert region.size == 100

    def test_clear(self):
        """Clear removes all entries."""
        region = CacheRegion(name="test", ttl=60)
        region.set("a", 1)
        region.set("b", 2)
        assert region.size == 2
        region.clear()
        assert region.size == 0
        assert region.get("a") is None

    def test_has_key(self):
        """has() checks for non-expired existence."""
        region = CacheRegion(name="test", ttl=1)
        assert region.has("key1") is False
        region.set("key1", "val")
        assert region.has("key1") is True
        time.sleep(1.1)
        assert region.has("key1") is False

    def test_hit_miss_counting(self):
        """Hits and misses are tracked."""
        region = CacheRegion(name="test", ttl=60)
        region.set("key1", "val")
        region.get("key1")    # hit
        region.get("key1")    # hit
        region.get("missing") # miss
        assert region._hits == 2
        assert region._misses == 1
        assert abs(region.hit_rate - 2 / 3) < 0.01

    def test_hit_rate_zero_when_no_accesses(self):
        """Hit rate is 0.0 when no gets have been called."""
        region = CacheRegion(name="test", ttl=60)
        assert region.hit_rate == 0.0

    def test_loading_flag(self):
        """Loading flag can be set and read."""
        region = CacheRegion(name="test", ttl=60)
        assert region.is_loading is False
        region.is_loading = True
        assert region.is_loading is True
        region.is_loading = False
        assert region.is_loading is False

    def test_status_returns_dict(self):
        """status() returns a dict with expected keys."""
        region = CacheRegion(name="test", ttl=60, max_size=100)
        region.set("k", "v")
        region.get("k")
        s = region.status()
        assert s["size"] == 1
        assert s["max_size"] == 100
        assert s["ttl_seconds"] == 60
        assert s["hits"] == 1
        assert s["misses"] == 0
        assert s["hit_rate"] == 1.0
        assert s["loading"] is False

    def test_status_unlimited_max_size(self):
        """status() shows 'unlimited' when max_size=0."""
        region = CacheRegion(name="test", ttl=60, max_size=0)
        assert region.status()["max_size"] == "unlimited"

    def test_status_never_expires_ttl(self):
        """status() shows 'never' when ttl=0."""
        region = CacheRegion(name="test", ttl=0)
        assert region.status()["ttl_seconds"] == "never"

    def test_overwrite_existing_key(self):
        """Setting the same key again overwrites the value."""
        region = CacheRegion(name="test", ttl=60)
        region.set("key1", "old")
        region.set("key1", "new")
        assert region.get("key1") == "new"
        assert region.size == 1

    def test_eviction_prefers_expired_entries(self):
        """When evicting, expired entries are removed first."""
        region = CacheRegion(name="test", ttl=1, max_size=3)
        region.set("a", 1)
        time.sleep(1.1)  # "a" is now expired
        region.set("b", 2)
        region.set("c", 3)
        # Adding "d" — "a" should be evicted (expired) before "b" or "c"
        region.set("d", 4)
        assert region.get("a") is None
        assert region.get("b") == 2
        assert region.get("c") == 3
        assert region.get("d") == 4

    def test_thread_safety(self):
        """Multiple threads can read/write without errors."""
        region = CacheRegion(name="test", ttl=60, max_size=50)
        errors = []

        def writer(start):
            try:
                for i in range(start, start + 20):
                    region.set(f"key{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    region.get("key1")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(20,)),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ── CacheManager tests ────────────────────────────────────────────────


class TestCacheManager:
    """Test CacheManager — the unified cache facade."""

    def setup_method(self):
        self.cm = CacheManager()
        self.cm.register("fast", ttl=1, max_size=10)
        self.cm.register("slow", ttl=3600, max_size=0)

    def test_register_returns_region(self):
        """register() returns the CacheRegion instance."""
        region = self.cm.register("new", ttl=30)
        assert isinstance(region, CacheRegion)
        assert region.name == "new"

    def test_region_lookup(self):
        """region() returns the correct CacheRegion."""
        r = self.cm.region("fast")
        assert r is not None
        assert r.name == "fast"
        assert r.ttl == 1

    def test_region_lookup_missing(self):
        """region() returns None for unknown name."""
        assert self.cm.region("nonexistent") is None

    def test_get_set_key_value(self):
        """Key-value get/set on a named region."""
        self.cm.set("slow", "mykey", {"val": 99})
        assert self.cm.get("slow", "mykey") == {"val": 99}

    def test_get_from_unknown_region(self):
        """Getting from unknown region returns None."""
        assert self.cm.get("nonexistent", "key") is None

    def test_set_to_unknown_region_is_noop(self):
        """Setting to unknown region is a no-op."""
        self.cm.set("nonexistent", "key", "val")  # should not raise

    def test_get_data_set_data(self):
        """Single-value get_data/set_data for regions like 'yoy'."""
        self.cm.set_data("slow", {"summary": [1, 2, 3]})
        assert self.cm.get_data("slow") == {"summary": [1, 2, 3]}

    def test_has_data(self):
        """has_data checks for single-value presence."""
        assert self.cm.has_data("slow") is False
        self.cm.set_data("slow", {"x": 1})
        assert self.cm.has_data("slow") is True

    def test_has_data_unknown_region(self):
        """has_data on unknown region returns False."""
        assert self.cm.has_data("nonexistent") is False

    def test_loading_flags(self):
        """is_loading / set_loading proxy to region."""
        assert self.cm.is_loading("fast") is False
        self.cm.set_loading("fast", True)
        assert self.cm.is_loading("fast") is True
        self.cm.set_loading("fast", False)
        assert self.cm.is_loading("fast") is False

    def test_loading_unknown_region(self):
        """is_loading on unknown region returns False."""
        assert self.cm.is_loading("nonexistent") is False

    def test_clear_region(self):
        """clear() removes all entries from a specific region."""
        self.cm.set("slow", "k1", 1)
        self.cm.set("slow", "k2", 2)
        self.cm.clear("slow")
        assert self.cm.get("slow", "k1") is None
        assert self.cm.get("slow", "k2") is None

    def test_clear_all(self):
        """clear_all() empties all regions."""
        self.cm.set("fast", "k", 1)
        self.cm.set("slow", "k", 2)
        self.cm.clear_all()
        assert self.cm.get("fast", "k") is None
        assert self.cm.get("slow", "k") is None

    def test_status(self):
        """status() returns dict with all region statuses."""
        self.cm.set("fast", "k", "v")
        s = self.cm.status()
        assert "fast" in s
        assert "slow" in s
        assert s["fast"]["size"] == 1
        assert s["slow"]["size"] == 0

    def test_regions_list(self):
        """regions property returns list of registered names."""
        assert "fast" in self.cm.regions
        assert "slow" in self.cm.regions

    def test_ttl_expiry_through_manager(self):
        """TTL expiry works through the CacheManager facade."""
        self.cm.set("fast", "k", "val")
        assert self.cm.get("fast", "k") == "val"
        time.sleep(1.1)
        assert self.cm.get("fast", "k") is None

    def test_max_size_through_manager(self):
        """Max size eviction works through the CacheManager facade."""
        for i in range(15):
            self.cm.set("fast", f"k{i}", i)
            time.sleep(0.01)
        region = self.cm.region("fast")
        assert region.size <= 10


# ── Singleton tests ───────────────────────────────────────────────────


class TestCacheSingleton:
    """Test the module-level cache singleton."""

    def test_singleton_has_all_regions(self):
        """The module-level cache has all configured regions."""
        from src.utils.cache_manager import cache

        expected = ["analytics", "yoy", "options_expiry", "charts",
                     "accuracy", "provider", "ai", "analyst"]
        for name in expected:
            assert name in cache.regions, f"Missing region: {name}"

    def test_singleton_ai_config(self):
        """AI region has correct max_size."""
        from src.utils.cache_manager import cache

        ai = cache.region("ai")
        assert ai is not None
        assert ai.max_size == 500

    def test_singleton_analyst_config(self):
        """Analyst region has correct max_size."""
        from src.utils.cache_manager import cache

        analyst = cache.region("analyst")
        assert analyst is not None
        assert analyst.max_size == 200

    def test_singleton_analytics_no_ttl(self):
        """Analytics region has ttl=0 (never expires)."""
        from src.utils.cache_manager import cache

        analytics = cache.region("analytics")
        assert analytics is not None
        assert analytics.ttl == 0

    def test_singleton_yoy_ttl(self):
        """YoY region has 6-hour TTL."""
        from src.utils.cache_manager import cache

        yoy = cache.region("yoy")
        assert yoy is not None
        assert yoy.ttl == 21600

    def test_singleton_status(self):
        """Singleton status returns all 8 regions."""
        from src.utils.cache_manager import cache

        s = cache.status()
        assert len(s) == 8
