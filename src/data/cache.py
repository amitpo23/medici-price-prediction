"""Disk-based cache for API responses and collected data."""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config.settings import CACHE_DIR, CACHE_TTL_HOURS


class DataCache:
    """Simple file-based cache using parquet for DataFrames."""

    def __init__(self, cache_dir: Path | None = None, ttl_hours: int | None = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.ttl = timedelta(hours=ttl_hours or CACHE_TTL_HOURS)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> pd.DataFrame | None:
        """Return cached DataFrame if exists and not expired."""
        meta_path = self._meta_path(key)
        data_path = self._data_path(key)

        if not meta_path.exists() or not data_path.exists():
            return None

        with open(meta_path) as f:
            meta = json.load(f)

        cached_at = datetime.fromisoformat(meta["cached_at"])
        if datetime.now() - cached_at > self.ttl:
            self.invalidate(key)
            return None

        return pd.read_parquet(data_path)

    def set(self, key: str, df: pd.DataFrame) -> None:
        """Cache a DataFrame with timestamp."""
        meta = {"cached_at": datetime.now().isoformat(), "rows": len(df)}

        df.to_parquet(self._data_path(key), index=False)
        with open(self._meta_path(key), "w") as f:
            json.dump(meta, f)

    def invalidate(self, key: str) -> None:
        """Remove a cached entry."""
        self._data_path(key).unlink(missing_ok=True)
        self._meta_path(key).unlink(missing_ok=True)

    def _safe_key(self, key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()

    def _data_path(self, key: str) -> Path:
        return self.cache_dir / f"{self._safe_key(key)}.parquet"

    def _meta_path(self, key: str) -> Path:
        return self.cache_dir / f"{self._safe_key(key)}.meta.json"
