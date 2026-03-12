"""Unified cache manager with named regions, TTL, LRU eviction, and hit/miss tracking.

Replaces the 8 independent cache systems (analytics, yoy, options_expiry,
charts, accuracy, provider, ai, analyst) with a single CacheManager.

Each region has:
  - Per-key TTL expiration
  - Optional max_size with LRU eviction
  - Thread-safe access
  - Hit/miss counting for observability
  - Loading flag for background-load patterns
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# Default key for single-value cache regions (yoy, charts, etc.)
_DEFAULT_KEY = "__data__"


class CacheRegion:
    """A single named cache region with TTL and optional LRU eviction."""

    __slots__ = (
        "name", "ttl", "max_size",
        "_data", "_lock",
        "_hits", "_misses",
        "_loading",
    )

    def __init__(self, name: str, ttl: int, max_size: int = 0) -> None:
        self.name = name
        self.ttl = ttl            # seconds; 0 = never expires
        self.max_size = max_size   # 0 = unlimited
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._loading = False

    # ── Core get/set ──────────────────────────────────────────────────

    def get(self, key: str = _DEFAULT_KEY) -> Any | None:
        """Return cached value or None if missing/expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is not None:
                ts, val = entry
                if self.ttl == 0 or (time.time() - ts) < self.ttl:
                    self._hits += 1
                    return val
                # Expired — remove it
                del self._data[key]
            self._misses += 1
            return None

    def set(self, key: str, val: Any) -> None:
        """Store a value. Evicts oldest entries if over max_size."""
        with self._lock:
            self._data[key] = (time.time(), val)
            if self.max_size > 0 and len(self._data) > self.max_size:
                self._evict_unlocked()

    def has(self, key: str = _DEFAULT_KEY) -> bool:
        """Check if a non-expired entry exists."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False
            ts, _ = entry
            if self.ttl == 0 or (time.time() - ts) < self.ttl:
                return True
            del self._data[key]
            return False

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._data.clear()

    def delete(self, key: str) -> None:
        """Remove a single entry if it exists."""
        with self._lock:
            self._data.pop(key, None)

    def export_entries(self) -> dict[str, Any]:
        """Return all non-expired values in this region."""
        exported: dict[str, Any] = {}
        now = time.time()
        with self._lock:
            expired: list[str] = []
            for key, (ts, value) in self._data.items():
                if self.ttl > 0 and (now - ts) >= self.ttl:
                    expired.append(key)
                    continue
                exported[key] = value
            for key in expired:
                del self._data[key]
        return exported

    def import_entries(self, entries: dict[str, Any], clear_existing: bool = False) -> int:
        """Restore entries into this region using the current time as timestamp."""
        count = 0
        with self._lock:
            if clear_existing:
                self._data.clear()
            ts = time.time()
            for key, value in entries.items():
                self._data[key] = (ts, value)
                count += 1
            if self.max_size > 0 and len(self._data) > self.max_size:
                self._evict_unlocked()
        return count

    # ── Loading flag (for background-load patterns) ───────────────────

    @property
    def is_loading(self) -> bool:
        return self._loading

    @is_loading.setter
    def is_loading(self, value: bool) -> None:
        self._loading = value

    # ── Stats ─────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def status(self) -> dict:
        return {
            "size": self.size,
            "max_size": self.max_size if self.max_size > 0 else "unlimited",
            "ttl_seconds": self.ttl if self.ttl > 0 else "never",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
            "loading": self._loading,
        }

    # ── Internal ──────────────────────────────────────────────────────

    def _evict_unlocked(self) -> None:
        """Evict expired entries first, then oldest if still over max_size.

        Must be called while holding self._lock.
        """
        if self.ttl > 0:
            cutoff = time.time() - self.ttl
            expired = [k for k, (t, _) in self._data.items() if t < cutoff]
            for k in expired:
                del self._data[k]

        # If still over, remove oldest entries (LRU)
        while self.max_size > 0 and len(self._data) > self.max_size:
            oldest_key = min(self._data, key=lambda k: self._data[k][0])
            del self._data[oldest_key]


class CacheManager:
    """Unified cache manager with named regions.

    Usage:
        cache = CacheManager()
        cache.register("ai", ttl=1800, max_size=500)
        cache.set("ai", "some_key", value)
        result = cache.get("ai", "some_key")

    For single-value caches (yoy, charts, etc.):
        cache.set_data("yoy", data_dict)
        data = cache.get_data("yoy")
    """

    def __init__(self) -> None:
        self._regions: dict[str, CacheRegion] = {}

    def register(self, name: str, ttl: int, max_size: int = 0) -> CacheRegion:
        """Register a new cache region. Returns the CacheRegion instance."""
        region = CacheRegion(name=name, ttl=ttl, max_size=max_size)
        self._regions[name] = region
        return region

    def region(self, name: str) -> CacheRegion | None:
        """Get a cache region by name."""
        return self._regions.get(name)

    # ── Key-value operations (for multi-key caches: ai, analyst) ──────

    def get(self, region_name: str, key: str) -> Any | None:
        """Get a value from a named region."""
        r = self._regions.get(region_name)
        if r is None:
            return None
        return r.get(key)

    def set(self, region_name: str, key: str, val: Any) -> None:
        """Set a value in a named region."""
        r = self._regions.get(region_name)
        if r is None:
            return
        r.set(key, val)

    def delete(self, region_name: str, key: str) -> None:
        """Delete a key from a named region."""
        r = self._regions.get(region_name)
        if r is None:
            return
        r.delete(key)

    # ── Single-value operations (for yoy, charts, analytics, etc.) ────

    def get_data(self, region_name: str) -> Any | None:
        """Get the single cached value for a region."""
        return self.get(region_name, _DEFAULT_KEY)

    def set_data(self, region_name: str, val: Any) -> None:
        """Set the single cached value for a region."""
        self.set(region_name, _DEFAULT_KEY, val)

    def has_data(self, region_name: str) -> bool:
        """Check if a single-value region has non-expired data."""
        r = self._regions.get(region_name)
        if r is None:
            return False
        return r.has(_DEFAULT_KEY)

    # ── Loading flag helpers ──────────────────────────────────────────

    def is_loading(self, region_name: str) -> bool:
        r = self._regions.get(region_name)
        return r.is_loading if r else False

    def set_loading(self, region_name: str, value: bool) -> None:
        r = self._regions.get(region_name)
        if r:
            r.is_loading = value

    # ── Bulk operations ───────────────────────────────────────────────

    def clear(self, region_name: str) -> None:
        """Clear all entries in a region."""
        r = self._regions.get(region_name)
        if r:
            r.clear()

    def export_region(self, region_name: str) -> dict[str, Any]:
        """Export all non-expired values from a region."""
        r = self._regions.get(region_name)
        if r is None:
            return {}
        return r.export_entries()

    def import_region(
        self,
        region_name: str,
        entries: dict[str, Any],
        clear_existing: bool = False,
    ) -> int:
        """Restore values into a region."""
        r = self._regions.get(region_name)
        if r is None:
            return 0
        return r.import_entries(entries, clear_existing=clear_existing)

    def clear_all(self) -> None:
        """Clear all regions."""
        for r in self._regions.values():
            r.clear()

    # ── Status / observability ────────────────────────────────────────

    def status(self) -> dict:
        """Return status of all regions for the /cache/status endpoint."""
        return {name: r.status() for name, r in self._regions.items()}

    @property
    def regions(self) -> list[str]:
        return list(self._regions.keys())


# ── Module-level singleton ────────────────────────────────────────────
cache = CacheManager()


def _init_regions() -> None:
    """Register all cache regions from config/settings.py CACHE_CONFIG."""
    from config.settings import CACHE_CONFIG

    for name, cfg in CACHE_CONFIG.items():
        cache.register(name, ttl=cfg["ttl"], max_size=cfg.get("max_size", 0))


_init_regions()
