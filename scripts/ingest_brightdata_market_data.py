"""Ingest OTA pricing exports collected via Bright Data.

Usage:
  python scripts/ingest_brightdata_market_data.py
  python scripts/ingest_brightdata_market_data.py --path ~/Downloads --path ~/Documents
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.brightdata_market_collector import BrightDataMarketCollector


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Bright Data OTA exports")
    parser.add_argument("--path", action="append", default=[], help="Additional directory to scan")
    parser.add_argument("--city", default="Miami", help="Target city label")
    args = parser.parse_args()

    collector = BrightDataMarketCollector()
    df = collector.collect(city=args.city, search_paths=args.path)

    if df.empty:
        print(json.dumps({
            "status": "no_data",
            "message": (
                "No Bright Data OTA files found. Place JSON/CSV exports under "
                "data/raw/brightdata or pass --path."
            ),
        }, ensure_ascii=False, indent=2))
        return 0

    result = collector.save_processed_outputs(df)
    output = {
        "status": "ok",
        "rows": int(len(df)),
        **result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
