from collections import Counter
from pathlib import Path
import os

from src.api.routers._shared_state import (
    _derive_option_signal,
    _rebuild_cached_analysis_from_snapshots,
    _run_collection_cycle,
)


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


def main() -> None:
    analysis = _rebuild_cached_analysis_from_snapshots()
    if not analysis:
        load_env_file(".env")
        analysis = _run_collection_cycle()
        if not analysis:
            print({"error": "No analysis could be rebuilt from snapshots or collected from source"})
            return

    predictions = analysis.get("predictions") or {}
    signals = []
    for pred in predictions.values():
        try:
            signals.append(_derive_option_signal(pred))
        except (TypeError, ValueError):
            signals.append("UNKNOWN")

    counts = Counter(signals)

    print(
        {
            "run_ts": analysis.get("run_ts"),
            "total_rows": len(signals),
            "put_count": counts.get("PUT", 0),
            "call_count": counts.get("CALL", 0),
            "neutral_count": counts.get("NEUTRAL", 0),
            "unknown_count": counts.get("UNKNOWN", 0),
        }
    )


if __name__ == "__main__":
    main()
