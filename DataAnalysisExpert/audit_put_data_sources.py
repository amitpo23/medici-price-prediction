from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.analytics.data_sources import DATA_SOURCES
from src.analytics.freshness_engine import build_freshness_data
from src.api.routers._shared_state import _derive_option_signal, _run_collection_cycle


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


def _freshness_map() -> dict[str, dict]:
    freshness = build_freshness_data()
    mapping: dict[str, dict] = {}
    for item in freshness.get("sources", []):
        mapping[str(item.get("name", "")).strip().lower()] = item
    return mapping


def _extract_prediction_source_stats(predictions: dict) -> dict:
    method_counter = Counter()
    model_type_counter = Counter()
    source_inputs_presence = Counter()
    per_signal_source_counter = Counter()

    for pred in predictions.values():
        method_counter[str(pred.get("prediction_method") or "unknown")] += 1
        model_type_counter[str(pred.get("model_type") or "unknown")] += 1

        source_inputs = pred.get("source_inputs") or {}
        for key in source_inputs.keys():
            source_inputs_presence[str(key)] += 1

        for signal in pred.get("signals") or []:
            per_signal_source_counter[str(signal.get("source") or "unknown")] += 1

    return {
        "prediction_method_counts": dict(method_counter),
        "model_type_counts": dict(model_type_counter),
        "source_inputs_presence": dict(source_inputs_presence),
        "signal_source_counts": dict(per_signal_source_counter),
    }


def _compute_put_summary(predictions: dict) -> dict:
    signal_counter = Counter()

    for pred in predictions.values():
        try:
            signal = _derive_option_signal(pred)
        except (TypeError, ValueError):
            signal = "UNKNOWN"
        signal_counter[signal] += 1

    total = sum(signal_counter.values())
    put_count = signal_counter.get("PUT", 0)
    put_rate = round((put_count / total) * 100, 2) if total else 0.0

    return {
        "total_predictions": total,
        "put_count": put_count,
        "call_count": signal_counter.get("CALL", 0),
        "neutral_count": signal_counter.get("NEUTRAL", 0),
        "unknown_count": signal_counter.get("UNKNOWN", 0),
        "put_rate_pct": put_rate,
    }


def _map_relevant_sources(freshness_by_name: dict[str, dict]) -> list[dict]:
    relevant = {
        "salesoffice": ["salesoffice.details", "salesoffice.orders"],
        "salesoffice_log": ["salesoffice.log"],
        "ai_search_hotel_data": ["ai_search_hoteldata"],
        "search_results_poll_log": ["searchresultssessionpolllog"],
        "room_price_update_log": ["roompriceupdatelog"],
        "med_prebook": ["med_prebook"],
        "open_meteo": ["weather cache"],
        "kiwi_flights": ["flights db"],
        "seatgeek": ["events db"],
        "hotel_booking_dataset": [],
        "tbo_hotels": [],
        "trivago_statista": [],
    }

    output = []
    for src in DATA_SOURCES:
        src_id = src.get("id")
        if src_id not in relevant:
            continue

        freshness_hits = []
        for key in relevant[src_id]:
            hit = freshness_by_name.get(key)
            if hit:
                freshness_hits.append({
                    "name": hit.get("name"),
                    "status": hit.get("status"),
                    "last_updated": hit.get("last_updated"),
                    "age_display": hit.get("age_display"),
                })

        output.append({
            "id": src_id,
            "name": src.get("name"),
            "status": src.get("status"),
            "category": src.get("category"),
            "update_freq": src.get("update_freq"),
            "metrics": src.get("metrics"),
            "freshness": freshness_hits,
        })

    return output


def main() -> None:
    load_env_file(".env")

    freshness = build_freshness_data()
    freshness_by_name = _freshness_map()

    analysis = _run_collection_cycle()
    if not analysis:
        print(json.dumps({"error": "analysis_unavailable"}, ensure_ascii=False))
        return

    predictions = analysis.get("predictions") or {}

    report = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "run_ts": analysis.get("run_ts"),
        "data_access": {
            "medici_db_url_set": bool(os.getenv("MEDICI_DB_URL")),
            "database_mode": "read_only_expected",
        },
        "put_summary": _compute_put_summary(predictions),
        "prediction_source_stats": _extract_prediction_source_stats(predictions),
        "relevant_sources": _map_relevant_sources(freshness_by_name),
        "freshness_summary": freshness.get("summary"),
        "freshness_checked_at": freshness.get("checked_at"),
        "analysis_top_level_sections": sorted(list(analysis.keys())),
    }

    out_dir = Path("DataAnalysisExpert")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"put_data_source_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "report": str(out_path).replace('\\\\', '/'),
        "run_ts": report["run_ts"],
        "put_summary": report["put_summary"],
        "freshness_summary": report["freshness_summary"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
