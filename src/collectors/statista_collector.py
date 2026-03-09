"""Collector for Miami monthly ADR benchmarks sourced from Statista exports.

This collector ingests local export files (JSON/CSV) from:
- data/raw/statista/
- ~/Downloads
- ~/Documents

It normalizes records into monthly Miami ADR values in USD.
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


class StatistaCollector(BaseCollector):
    """Collect and normalize monthly Miami ADR benchmark points from local exports."""

    name = "statista"

    DEFAULT_SOURCE_URL = (
        "https://www.statista.com/statistics/309128/"
        "overnight-accommodation-costs-miami-by-month/"
    )

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
        if not files:
            return pd.DataFrame()

        records: list[dict] = []
        for file_path in files:
            suffix = file_path.suffix.lower()
            if suffix == ".json":
                records.extend(self._parse_json_file(file_path, city=city))
            elif suffix == ".csv":
                records.extend(self._parse_csv_file(file_path, city=city))

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if df.empty:
            return df

        df["adr_usd"] = pd.to_numeric(df["adr_usd"], errors="coerce")
        df = df.dropna(subset=["month", "month_num", "adr_usd"])

        grouped = (
            df.groupby(["month_num", "month"], as_index=False)
            .agg(
                adr_usd=("adr_usd", "mean"),
                city=("city", "first"),
                source_name=("source_name", "first"),
                source_url=("source_url", "first"),
                source_file=("source_file", "first"),
                collected_ts=("collected_ts", "max"),
            )
            .sort_values("month_num")
        )

        grouped["adr_usd"] = grouped["adr_usd"].round(2)
        return grouped

    def save_processed_outputs(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {"status": "no_data", "rows": 0}

        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        monthly_csv = PROCESSED_DATA_DIR / "statista_miami_monthly_adr.csv"
        df.to_csv(monthly_csv, index=False)

        benchmark_payload = {
            "source": "trivago_statista",
            "source_url": self.DEFAULT_SOURCE_URL,
            "city": "Miami",
            "currency": "USD",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "monthly_adr": [
                {
                    "month": row["month"],
                    "month_num": int(row["month_num"]),
                    "adr_usd": float(row["adr_usd"]),
                }
                for _, row in df.iterrows()
            ],
            "coverage": {
                "months_count": int(len(df)),
                "min_adr": float(df["adr_usd"].min()),
                "max_adr": float(df["adr_usd"].max()),
            },
        }

        benchmark_json = DATA_DIR / "miami_benchmarks.json"
        benchmark_json.write_text(
            json.dumps(benchmark_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "status": "ok",
            "rows": int(len(df)),
            "processed_csv": str(monthly_csv),
            "benchmark_json": str(benchmark_json),
            "months_count": int(len(df)),
        }

    def _discover_files(
        self,
        search_paths: list[str] | None = None,
        include_downloads: bool = True,
        include_documents: bool = True,
    ) -> list[Path]:
        roots = [DATA_DIR / "raw" / "statista"]
        if include_downloads:
            roots.append(Path.home() / "Downloads")
        if include_documents:
            roots.append(Path.home() / "Documents")
        if search_paths:
            roots.extend(Path(p).expanduser() for p in search_paths)

        patterns = [
            "*statista*.json",
            "*statistica*.json",
            "*trivago*.json",
            "*miami*bench*.json",
            "*statista*.csv",
            "*statistica*.csv",
            "*trivago*.csv",
            "*miami*bench*.csv",
        ]

        files: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for pattern in patterns:
                for path in root.glob(pattern):
                    if not path.is_file():
                        continue
                    key = str(path.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    files.append(path)

        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def _parse_json_file(self, path: Path, city: str) -> list[dict]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read JSON file {path}: {e}")
            return []

        source_name = self._extract_source_name(payload, default="trivago_statista")
        source_url = self._extract_source_url(payload)
        rows = self._extract_month_rows(payload)
        return self._rows_to_records(rows, city=city, source_name=source_name, source_url=source_url, source_file=str(path))

    def _parse_csv_file(self, path: Path, city: str) -> list[dict]:
        try:
            df = pd.read_csv(path)
        except (FileNotFoundError, OSError, ValueError) as e:
            logger.warning(f"Failed to read CSV file {path}: {e}")
            return []

        if df.empty:
            return []

        cols = {c.lower().strip(): c for c in df.columns}
        month_col = None
        value_col = None

        month_candidates = ["month", "month_name", "period", "label"]
        value_candidates = ["adr", "avg_price", "average_price", "value", "price", "usd"]

        for c in month_candidates:
            if c in cols:
                month_col = cols[c]
                break
        for c in value_candidates:
            if c in cols:
                value_col = cols[c]
                break

        if month_col is None or value_col is None:
            return []

        rows = [
            {"month": str(r.get(month_col, "")), "adr": r.get(value_col)}
            for _, r in df.iterrows()
        ]
        return self._rows_to_records(
            rows,
            city=city,
            source_name="trivago_statista",
            source_url=self.DEFAULT_SOURCE_URL,
            source_file=str(path),
        )

    def _extract_month_rows(self, payload) -> list[dict]:
        if isinstance(payload, dict):
            for key in ("monthly_adr", "adr_by_month", "data", "series", "values", "rows"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    return rows
                if isinstance(rows, dict):
                    return [{"month": k, "adr": v} for k, v in rows.items()]
            if "August" in payload or "September" in payload:
                return [{"month": k, "adr": v} for k, v in payload.items()]
        if isinstance(payload, list):
            return payload
        return []

    def _rows_to_records(
        self,
        rows: list[dict],
        city: str,
        source_name: str,
        source_url: str,
        source_file: str,
    ) -> list[dict]:
        records: list[dict] = []
        ts = datetime.now(timezone.utc).isoformat()
        for row in rows:
            month_raw = row.get("month") or row.get("label") or row.get("period")
            adr_raw = row.get("adr")
            if adr_raw is None:
                adr_raw = row.get("value")
            if adr_raw is None:
                adr_raw = row.get("price")

            month_num, month_name = self._normalize_month(month_raw)
            adr_value = self._to_float(adr_raw)
            if month_num is None or adr_value is None:
                continue

            records.append(
                {
                    "month_num": month_num,
                    "month": month_name,
                    "adr_usd": adr_value,
                    "city": city,
                    "source_name": source_name,
                    "source_url": source_url or self.DEFAULT_SOURCE_URL,
                    "source_file": source_file,
                    "collected_ts": ts,
                }
            )
        return records

    @staticmethod
    def _extract_source_name(payload: dict, default: str) -> str:
        if isinstance(payload, dict):
            val = payload.get("source") or payload.get("source_name")
            if val:
                return str(val)
        return default

    def _extract_source_url(self, payload: dict) -> str:
        if isinstance(payload, dict):
            val = payload.get("source_url") or payload.get("url")
            if val:
                return str(val)
        return self.DEFAULT_SOURCE_URL

    @staticmethod
    def _normalize_month(value) -> tuple[int | None, str | None]:
        if value is None:
            return None, None

        text = str(value).strip()
        if not text:
            return None, None

        month_map = {
            "jan": (1, "January"),
            "january": (1, "January"),
            "feb": (2, "February"),
            "february": (2, "February"),
            "mar": (3, "March"),
            "march": (3, "March"),
            "apr": (4, "April"),
            "april": (4, "April"),
            "may": (5, "May"),
            "jun": (6, "June"),
            "june": (6, "June"),
            "jul": (7, "July"),
            "july": (7, "July"),
            "aug": (8, "August"),
            "august": (8, "August"),
            "sep": (9, "September"),
            "sept": (9, "September"),
            "september": (9, "September"),
            "oct": (10, "October"),
            "october": (10, "October"),
            "nov": (11, "November"),
            "november": (11, "November"),
            "dec": (12, "December"),
            "december": (12, "December"),
        }

        key = text.lower()
        if key in month_map:
            return month_map[key]

        try:
            parsed = pd.to_datetime(text, errors="raise")
            return int(parsed.month), parsed.strftime("%B")
        except (ValueError, TypeError):
            return None, None

    @staticmethod
    def _to_float(value) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return None
        cleaned = (
            text.replace("$", "")
            .replace(",", "")
            .replace("USD", "")
            .replace("usd", "")
            .strip()
        )
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
