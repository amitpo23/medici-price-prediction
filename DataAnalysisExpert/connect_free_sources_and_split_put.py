from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import csv

from src.analytics.analyzer import run_analysis
from src.analytics.booking_benchmarks import get_benchmarks_summary
from src.analytics.data_sources import DATA_SOURCES
from src.analytics.flights_store import get_demand_summary, init_flights_db
from src.analytics.hotel_knowledge import get_knowledge_summary
from src.analytics.miami_events_fetcher import refresh_api_events
from src.analytics.miami_weather import get_weather_forecast
from src.analytics.collector import collect_prices
from src.analytics.fred_store import get_fred_indicators
from src.api.routers._shared_state import _derive_option_signal

INTERNAL_SOURCE_NAMES = [
    "SalesOffice.Details",
    "SalesOffice.Orders",
    "AI_Search_HotelData",
    "SearchResultsSessionPollLog",
    "RoomPriceUpdateLog",
    "MED_Book / MED_CancelBook",
]


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


def count_signals(predictions: dict) -> dict:
    counter = Counter()
    for pred in (predictions or {}).values():
        try:
            counter[_derive_option_signal(pred)] += 1
        except (TypeError, ValueError):
            counter["UNKNOWN"] += 1

    total = sum(counter.values())
    put = counter.get("PUT", 0)
    return {
        "total": total,
        "put": put,
        "call": counter.get("CALL", 0),
        "neutral": counter.get("NEUTRAL", 0),
        "unknown": counter.get("UNKNOWN", 0),
        "put_rate_pct": round((put / total) * 100, 2) if total else 0.0,
    }


def connect_free_sources() -> dict:
    statuses: dict[str, dict] = {}

    try:
        weather = get_weather_forecast(days=14)
        statuses["open_meteo_weather"] = {
            "connected": True,
            "adjusted_days": len(weather),
        }
    except (ConnectionError, OSError, ValueError, KeyError, TypeError) as exc:
        statuses["open_meteo_weather"] = {
            "connected": False,
            "error": str(exc)[:200],
        }

    try:
        events = refresh_api_events(days_ahead=90)
        statuses["miami_events_apis"] = {
            "connected": True,
            "result": events,
        }
    except (ConnectionError, OSError, ValueError, KeyError, TypeError) as exc:
        statuses["miami_events_apis"] = {
            "connected": False,
            "error": str(exc)[:200],
        }

    try:
        init_flights_db()
        demand = get_demand_summary("Miami")
        statuses["kiwi_flights_store"] = {
            "connected": True,
            "indicator": demand.get("indicator"),
            "total_flights": demand.get("total_flights", 0),
        }
    except (ConnectionError, OSError, ValueError, KeyError, TypeError) as exc:
        statuses["kiwi_flights_store"] = {
            "connected": False,
            "error": str(exc)[:200],
        }

    try:
        benchmarks = get_benchmarks_summary()
        statuses["booking_benchmarks_dataset"] = {
            "connected": bool(benchmarks.get("status") == "ok"),
            "status": benchmarks.get("status"),
            "total_bookings": benchmarks.get("total_bookings", 0),
        }
    except (ConnectionError, OSError, ValueError, KeyError, TypeError) as exc:
        statuses["booking_benchmarks_dataset"] = {
            "connected": False,
            "error": str(exc)[:200],
        }

    try:
        knowledge = get_knowledge_summary()
        market = (knowledge or {}).get("market", {})
        statuses["tbo_market_knowledge"] = {
            "connected": market.get("status") == "ok",
            "total_hotels": market.get("total_hotels", 0),
        }
    except (ConnectionError, OSError, ValueError, KeyError, TypeError) as exc:
        statuses["tbo_market_knowledge"] = {
            "connected": False,
            "error": str(exc)[:200],
        }

    try:
        fred = get_fred_indicators()
        statuses["fred_economic"] = {
            "connected": bool(fred),
            "series_count": len(fred),
        }
    except (ConnectionError, OSError, ValueError, KeyError, TypeError) as exc:
        statuses["fred_economic"] = {
            "connected": False,
            "error": str(exc)[:200],
        }

    return statuses


def _connected_external_source_names(connections: dict[str, dict]) -> list[str]:
    mapping = {
        "open_meteo_weather": "Open-Meteo Weather",
        "miami_events_apis": "SeatGeek/Ticketmaster Events APIs",
        "kiwi_flights_store": "Kiwi Flights Store",
        "booking_benchmarks_dataset": "Booking Benchmarks Dataset",
        "tbo_market_knowledge": "TBO Market Knowledge",
        "fred_economic": "FRED Economic",
    }
    names = []
    for key, label in mapping.items():
        if bool((connections.get(key) or {}).get("connected")):
            names.append(label)
    return names


def _append_put_table(report: dict, out_dir: Path) -> dict:
    csv_path = out_dir / "put_split_table.csv"
    md_path = out_dir / "put_split_table.md"

    generated_at = report.get("generated_at_utc")
    run_ts_internal = report.get("split_analysis", {}).get("internal_only", {}).get("run_ts")
    run_ts_external = report.get("split_analysis", {}).get("external_only", {}).get("run_ts")
    internal_signals = report.get("split_analysis", {}).get("internal_only", {}).get("signals", {})
    external_signals = report.get("split_analysis", {}).get("external_only", {}).get("signals", {})
    delta = report.get("split_analysis", {}).get("delta", {})

    external_connected = _connected_external_source_names(
        report.get("free_sources_connection_status", {})
    )

    row = {
        "generated_at_utc": generated_at,
        "run_ts_internal": run_ts_internal,
        "run_ts_external": run_ts_external,
        "internal_put": internal_signals.get("put", 0),
        "internal_put_rate_pct": internal_signals.get("put_rate_pct", 0),
        "external_put": external_signals.get("put", 0),
        "external_put_rate_pct": external_signals.get("put_rate_pct", 0),
        "put_count_diff_external_minus_internal": delta.get("put_count_diff_external_minus_internal", 0),
        "put_rate_diff_external_minus_internal": delta.get("put_rate_diff_external_minus_internal", 0),
        "internal_sources": ", ".join(INTERNAL_SOURCE_NAMES),
        "external_sources_connected": ", ".join(external_connected) if external_connected else "None",
    }

    fieldnames = list(row.keys())
    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for item in reader:
            rows.append(item)

    lines = [
        "# PUT Split Table (Internal vs External)",
        "",
        "| generated_at_utc | internal_put | internal_put_rate_pct | external_put | external_put_rate_pct | put_count_diff_external_minus_internal | internal_sources | external_sources_connected |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]

    for item in rows[-50:]:
        safe_item = {
            key: str(value).replace("|", ",")
            for key, value in item.items()
        }
        lines.append(
            "| {generated_at_utc} | {internal_put} | {internal_put_rate_pct} | {external_put} | {external_put_rate_pct} | {put_count_diff_external_minus_internal} | {internal_sources} | {external_sources_connected} |".format(
                **safe_item
            )
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "csv": csv_path.as_posix(),
        "md": md_path.as_posix(),
    }


def run_split_analysis_once() -> tuple[dict, str, dict]:
    load_env_file(".env")

    free_catalog = [
        {
            "id": src.get("id"),
            "name": src.get("name"),
            "status": src.get("status"),
            "cost": src.get("cost"),
            "update_freq": src.get("update_freq"),
        }
        for src in DATA_SOURCES
        if "free" in str(src.get("cost", "")).lower()
    ]

    connections = connect_free_sources()

    collected_df = collect_prices()
    collected_count = 0 if collected_df is None else int(len(collected_df))

    internal_analysis = run_analysis(enrichment_profile="internal_only")
    external_analysis = run_analysis(enrichment_profile="external_only")

    internal_predictions = (internal_analysis or {}).get("predictions") or {}
    external_predictions = (external_analysis or {}).get("predictions") or {}

    report = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "free_sources_catalog": free_catalog,
        "free_sources_connection_status": connections,
        "collection": {
            "snapshot_rows_collected": collected_count,
        },
        "split_analysis": {
            "internal_only": {
                "run_ts": internal_analysis.get("run_ts") if isinstance(internal_analysis, dict) else None,
                "analysis_profile": internal_analysis.get("analysis_profile") if isinstance(internal_analysis, dict) else None,
                "signals": count_signals(internal_predictions),
            },
            "external_only": {
                "run_ts": external_analysis.get("run_ts") if isinstance(external_analysis, dict) else None,
                "analysis_profile": external_analysis.get("analysis_profile") if isinstance(external_analysis, dict) else None,
                "signals": count_signals(external_predictions),
            },
        },
    }

    int_put = report["split_analysis"]["internal_only"]["signals"]["put"]
    ext_put = report["split_analysis"]["external_only"]["signals"]["put"]
    report["split_analysis"]["delta"] = {
        "put_count_diff_external_minus_internal": ext_put - int_put,
        "put_rate_diff_external_minus_internal": round(
            report["split_analysis"]["external_only"]["signals"]["put_rate_pct"]
            - report["split_analysis"]["internal_only"]["signals"]["put_rate_pct"],
            2,
        ),
    }

    out_dir = Path("DataAnalysisExpert")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"split_put_free_sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    table_paths = _append_put_table(report, out_dir)

    return report, out_path.as_posix(), table_paths


def main() -> None:
    report, report_path, table_paths = run_split_analysis_once()

    print(
        json.dumps(
            {
                "report": report_path,
                "put_table_csv": table_paths.get("csv"),
                "put_table_md": table_paths.get("md"),
                "internal_only": report["split_analysis"]["internal_only"]["signals"],
                "external_only": report["split_analysis"]["external_only"]["signals"],
                "delta": report["split_analysis"]["delta"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
