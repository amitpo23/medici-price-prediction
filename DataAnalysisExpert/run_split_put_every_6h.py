from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from DataAnalysisExpert.connect_free_sources_and_split_put import run_split_analysis_once

INTERVAL_SECONDS = 6 * 60 * 60


def _append_daemon_log(message: str) -> None:
    out_dir = Path("DataAnalysisExpert")
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "split_put_scheduler.log"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def main() -> None:
    _append_daemon_log("Scheduler started (every 6 hours)")

    while True:
        try:
            report, report_path, table_paths = run_split_analysis_once()
            payload = {
                "report": report_path,
                "put_table_csv": table_paths.get("csv"),
                "put_table_md": table_paths.get("md"),
                "internal_only": report.get("split_analysis", {}).get("internal_only", {}).get("signals", {}),
                "external_only": report.get("split_analysis", {}).get("external_only", {}).get("signals", {}),
                "delta": report.get("split_analysis", {}).get("delta", {}),
            }
            _append_daemon_log(f"Run success: {json.dumps(payload, ensure_ascii=False)}")
            print(json.dumps(payload, ensure_ascii=False))
        except (ConnectionError, OSError, RuntimeError, ValueError, TypeError) as exc:
            _append_daemon_log(f"Run failed: {str(exc)}")
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
