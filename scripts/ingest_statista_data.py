"""Ingest Statista-derived Miami ADR benchmark data into the local pipeline.

Usage:
  python scripts/ingest_statista_data.py
  python scripts/ingest_statista_data.py --path ~/Downloads
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.statista_collector import StatistaCollector


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Statista Miami monthly ADR data")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Additional directory to search for Statista files (can be provided multiple times)",
    )
    parser.add_argument("--city", default="Miami", help="City label for the benchmark output")
    args = parser.parse_args()

    collector = StatistaCollector()
    df = collector.collect(city=args.city, search_paths=args.path)

    if df.empty:
        result = {
            "status": "no_data",
            "message": (
                "No Statista benchmark files found. "
                "Place JSON/CSV exports under data/raw/statista or pass --path."
            ),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    save_result = collector.save_processed_outputs(df)
    output = {
        "status": "ok",
        "rows": int(len(df)),
        "months": [str(m) for m in df["month"].tolist()],
        **save_result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
