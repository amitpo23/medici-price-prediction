"""Collector for OTA market pricing exports gathered via Bright Data.

Expected input files (JSON/CSV) under:
- data/raw/brightdata/
- optional extra paths (e.g. Downloads/Documents)

Supported platforms include Airbnb, Booking, Expedia, Agoda, Vrbo, Tripadvisor.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import pandas as pd

from config.settings import DATA_DIR, PROCESSED_DATA_DIR
from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class BrightDataMarketCollector(BaseCollector):
    name = "brightdata_market"

    SUPPORTED_PLATFORMS = {
        "airbnb", "booking", "booking.com", "expedia", "agoda", "vrbo", "tripadvisor"
    }

    def is_available(self) -> bool:
        return len(self._discover_files()) > 0

    def collect(
        self,
        city: str = "Miami",
        search_paths: list[str] | None = None,
        include_downloads: bool = True,
        include_documents: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        files = self._discover_files(
            search_paths=search_paths,
            include_downloads=include_downloads,
            include_documents=include_documents,
        )
        records: list[dict] = []
        for path in files:
            if path.suffix.lower() == ".json":
                records.extend(self._parse_json(path, city=city))
            elif path.suffix.lower() == ".csv":
                records.extend(self._parse_csv(path, city=city))

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if df.empty:
            return df

        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["platform", "hotel_name", "price"])
        df["platform"] = df["platform"].str.lower().str.strip()

        df = df[df["platform"].isin(self.SUPPORTED_PLATFORMS)]
        if df.empty:
            return df

        df["platform"] = df["platform"].replace({"booking.com": "booking"})
        return df

    def save_processed_outputs(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {"status": "no_data", "rows": 0}

        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = PROCESSED_DATA_DIR / "brightdata_ota_rates.csv"
        df.to_csv(csv_path, index=False)

        summary = self._build_summary(df)
        summary_path = PROCESSED_DATA_DIR / "brightdata_ota_summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "ok",
            "rows": int(len(df)),
            "processed_csv": str(csv_path),
            "summary_json": str(summary_path),
            "platforms": summary.get("platforms", {}),
        }

    def _discover_files(
        self,
        search_paths: list[str] | None = None,
        include_downloads: bool = True,
        include_documents: bool = True,
    ) -> list[Path]:
        roots = [DATA_DIR / "raw" / "brightdata"]
        if include_downloads:
            roots.append(Path.home() / "Downloads")
        if include_documents:
            roots.append(Path.home() / "Documents")
        if search_paths:
            roots.extend(Path(p).expanduser() for p in search_paths)

        patterns = [
            "*brightdata*.json", "*brightdata*.csv",
            "*airbnb*.json", "*airbnb*.csv",
            "*booking*.json", "*booking*.csv",
            "*expedia*.json", "*expedia*.csv",
            "*agoda*.json", "*agoda*.csv",
            "*vrbo*.json", "*vrbo*.csv",
            "*tripadvisor*.json", "*tripadvisor*.csv",
            "*ota*rates*.json", "*ota*rates*.csv",
        ]

        found: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for pattern in patterns:
                for p in root.glob(pattern):
                    if not p.is_file():
                        continue
                    key = str(p.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(p)

        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def _parse_json(self, path: Path, city: str) -> list[dict]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read JSON file {path}: {e}")
            return []

        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("results") or payload.get("rows") or []
            if isinstance(rows, dict):
                rows = [rows]
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []

        return [
            rec for rec in (self._normalize_row(r, city=city, source_file=str(path)) for r in rows)
            if rec is not None
        ]

    def _parse_csv(self, path: Path, city: str) -> list[dict]:
        try:
            df = pd.read_csv(path)
        except (FileNotFoundError, OSError, ValueError) as e:
            logger.warning(f"Failed to read CSV file {path}: {e}")
            return []

        return [
            rec for rec in (self._normalize_row(r.to_dict(), city=city, source_file=str(path)) for _, r in df.iterrows())
            if rec is not None
        ]

    def _normalize_row(self, row: dict, city: str, source_file: str) -> dict | None:
        platform = self._pick(row, "platform", "source", "site", "provider")
        hotel_name = self._pick(row, "hotel_name", "name", "property_name", "listing_name")
        price = self._pick(row, "price", "price_usd", "nightly_rate", "avg_price")
        check_in = self._pick(row, "check_in", "checkin", "date", "date_from")
        currency = self._pick(row, "currency") or "USD"
        row_city = self._pick(row, "city", "location") or city

        if platform is None:
            platform = self._infer_platform_from_file(source_file)

        price_num = self._to_float(price)
        if not platform or not hotel_name or price_num is None:
            return None

        return {
            "platform": str(platform).lower().strip(),
            "hotel_name": str(hotel_name).strip(),
            "city": str(row_city).strip(),
            "check_in": str(check_in) if check_in is not None else None,
            "price": float(price_num),
            "currency": str(currency).upper().strip(),
            "source": "brightdata_export",
            "source_file": source_file,
            "collected_ts": datetime.now(timezone.utc).isoformat(),
        }

    def _build_summary(self, df: pd.DataFrame) -> dict:
        platforms = {}
        for platform, grp in df.groupby("platform"):
            platforms[str(platform)] = {
                "rows": int(len(grp)),
                "hotels": int(grp["hotel_name"].nunique()),
                "avg_price": round(float(grp["price"].mean()), 2),
                "min_price": round(float(grp["price"].min()), 2),
                "max_price": round(float(grp["price"].max()), 2),
            }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": int(len(df)),
            "platforms": platforms,
        }

    @staticmethod
    def _pick(row: dict, *keys: str):
        lowered = {str(k).lower(): v for k, v in row.items()}
        for key in keys:
            if key in lowered and lowered[key] not in (None, ""):
                return lowered[key]
        return None

    @staticmethod
    def _to_float(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace("$", "").replace(",", "")
        try:
            return float(text)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _infer_platform_from_file(path: str) -> str | None:
        name = Path(path).name.lower()
        for platform in ("airbnb", "booking", "expedia", "agoda", "vrbo", "tripadvisor"):
            if platform in name:
                return platform
        return None
