from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def latest_audit_json(directory: Path) -> Path:
    candidates = sorted(directory.glob("put_data_source_audit_*.json"))
    if not candidates:
        raise FileNotFoundError("No put_data_source_audit_*.json files found")
    return candidates[-1]


def priority_row(source: dict) -> tuple[str, str, str]:
    freshness = source.get("freshness") or []
    statuses = [str(x.get("status", "unknown")).lower() for x in freshness]

    if "red" in statuses:
        return ("P1", "Investigate stale critical source and trigger refresh", "Today")
    if "yellow" in statuses:
        return ("P2", "Schedule refresh / verify ingestion lag", "Today")
    if not freshness or "unknown" in statuses:
        return ("P2", "Wire freshness signal for this source", "Today")
    return ("P3", "No action required", "Monitor")


def main() -> None:
    base = Path("DataAnalysisExpert")
    in_path = latest_audit_json(base)
    payload = json.loads(in_path.read_text(encoding="utf-8"))

    put = payload.get("put_summary", {})
    fresh = payload.get("freshness_summary", {})
    sources = payload.get("relevant_sources", [])
    stats = payload.get("prediction_source_stats", {})

    lines: list[str] = []
    lines.append("# PUT Data Source Audit — Markdown Summary")
    lines.append("")
    lines.append(f"- Generated at: {payload.get('generated_at_utc')}")
    lines.append(f"- Analysis run_ts: {payload.get('run_ts')}")
    lines.append(f"- Source JSON: {in_path.as_posix()}")
    lines.append("")

    lines.append("## PUT Snapshot")
    lines.append("")
    lines.append(f"- Total predictions: {put.get('total_predictions', 0)}")
    lines.append(f"- PUT count: {put.get('put_count', 0)}")
    lines.append(f"- CALL count: {put.get('call_count', 0)}")
    lines.append(f"- NEUTRAL count: {put.get('neutral_count', 0)}")
    lines.append(f"- PUT rate: {put.get('put_rate_pct', 0)}%")
    lines.append("")

    lines.append("## Freshness Overview")
    lines.append("")
    lines.append(f"- Overall status: {fresh.get('overall_status', 'unknown')}")
    lines.append(f"- Green: {fresh.get('green', 0)} | Yellow: {fresh.get('yellow', 0)} | Red: {fresh.get('red', 0)} | Unknown: {fresh.get('unknown', 0)}")
    lines.append(f"- Checked at: {payload.get('freshness_checked_at')}")
    lines.append("")

    lines.append("## Prediction Engine Inputs (Observed)")
    lines.append("")
    lines.append(f"- prediction_method_counts: {stats.get('prediction_method_counts', {})}")
    lines.append(f"- model_type_counts: {stats.get('model_type_counts', {})}")
    lines.append(f"- signal_source_counts: {stats.get('signal_source_counts', {})}")
    lines.append(f"- source_inputs_presence keys: {list((stats.get('source_inputs_presence') or {}).keys())}")
    lines.append("")

    lines.append("## Source Status Table")
    lines.append("")
    lines.append("| Source | Registry Status | Freshness | Last Updated | Priority | Action | ETA |")
    lines.append("|---|---|---|---|---|---|---|")

    for source in sources:
        freshness_items = source.get("freshness") or []
        if freshness_items:
            freshness_status = ", ".join(str(x.get("status", "unknown")) for x in freshness_items)
            last_updated = "; ".join(str(x.get("last_updated", "N/A")) for x in freshness_items)
        else:
            freshness_status = "unknown"
            last_updated = "N/A"

        prio, action, eta = priority_row(source)
        lines.append(
            f"| {source.get('name')} | {source.get('status')} | {freshness_status} | {last_updated} | {prio} | {action} | {eta} |"
        )

    lines.append("")
    lines.append("## Today Priority Plan")
    lines.append("")
    lines.append("1. P1: Resolve all red freshness sources before business-critical PUT monitoring.")
    lines.append("2. P2: Eliminate unknown freshness for Flights/Weather/Events caches.")
    lines.append("3. P2: Re-run audit after refresh and compare PUT rate delta.")
    lines.append("4. P3: Keep daily scheduled audit artifact for trend tracking.")

    out_path = base / f"put_data_source_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(out_path.as_posix())


if __name__ == "__main__":
    main()
