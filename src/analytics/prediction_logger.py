"""Structured event logger for prediction and price data.

Writes JSON-lines files to data/logs/ that serve as a persistent data source
for ML training. Every prediction cycle and every price collection event is
logged with full context, creating a growing historical dataset that captures:

- Price observations (what SalesOffice scanned)
- Predictions made (what the model predicted, with enrichments)
- Enrichment signals at the time of prediction

Log files rotate daily: data/logs/predictions_YYYY-MM-DD.jsonl
                        data/logs/prices_YYYY-MM-DD.jsonl

These are loaded by load_prediction_logs() / load_price_logs() in trading_db.py
and fed into the training pipeline as an additional data source.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Log directory — writable on Azure App Service
_LOG_DIR = Path(os.environ.get(
    "PREDICTION_LOG_DIR",
    str(Path(__file__).parent.parent.parent / "data" / "logs"),
))


def _ensure_dir():
    """Create log directory if it doesn't exist."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _write_event(filename_prefix: str, event: dict):
    """Append a single JSON event to the daily log file."""
    try:
        _ensure_dir()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        path = _LOG_DIR / f"{filename_prefix}_{today}.jsonl"
        line = json.dumps(event, default=str, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logger.debug("Failed to write %s event: %s", filename_prefix, e)


# ── Price observation events ──────────────────────────────────────────

def log_price_snapshot(df, snapshot_ts: datetime):
    """Log every price observation from a SalesOffice scan cycle.

    Called from collector.py after save_snapshot().
    Each row in df becomes one event with hotel_id, price, dates, etc.
    """
    if df is None or df.empty:
        return

    ts = snapshot_ts.isoformat() if snapshot_ts else datetime.utcnow().isoformat()
    count = 0

    for _, row in df.iterrows():
        event = {
            "type": "price_observation",
            "ts": ts,
            "hotel_id": int(row.get("hotel_id", 0)),
            "hotel_name": str(row.get("hotel_name", "")),
            "detail_id": int(row.get("detail_id", 0)) if "detail_id" in row.index else None,
            "room_price": float(row.get("room_price", 0)),
            "room_category": str(row.get("room_category", "")),
            "room_board": str(row.get("room_board", "")),
            "date_from": str(row.get("date_from", "")),
            "date_to": str(row.get("date_to", "")),
            "destination_id": int(row.get("destination_id", 0)) if "destination_id" in row.index else None,
        }
        _write_event("prices", event)
        count += 1

    logger.debug("Logged %d price observations", count)


# ── Prediction events ─────────────────────────────────────────────────

def log_prediction(
    detail_id: int,
    hotel_id: int,
    current_price: float,
    date_from,
    days_to_checkin: int,
    category: str,
    board: str,
    prediction_result: dict,
    enrichments_dict: dict | None = None,
    momentum_dict: dict | None = None,
    regime_dict: dict | None = None,
    run_ts: str | None = None,
):
    """Log a single room prediction with full context.

    Called from analyzer.py after deep_predictor.predict() returns a result.
    Captures the prediction + all signals that went into it.
    """
    pred = prediction_result or {}

    event = {
        "type": "prediction",
        "ts": run_ts or datetime.utcnow().isoformat(),
        "detail_id": detail_id,
        "hotel_id": hotel_id,
        "current_price": current_price,
        "predicted_price": pred.get("predicted_checkin_price"),
        "expected_change_pct": pred.get("expected_change_pct"),
        "date_from": str(date_from),
        "days_to_checkin": days_to_checkin,
        "category": category,
        "board": board,
        "model_type": pred.get("model_type"),
        "prediction_method": pred.get("prediction_method"),
        "confidence_quality": pred.get("confidence_quality"),
        # Signals breakdown
        "signals": [
            {
                "source": s.get("source"),
                "predicted_price": s.get("predicted_price"),
                "confidence": s.get("confidence"),
                "weight": s.get("weight"),
            }
            for s in pred.get("signals", [])
        ],
        # Enrichments at time of prediction
        "enrichments": enrichments_dict or {},
        # Momentum state
        "momentum": momentum_dict or {},
        # Regime state
        "regime": regime_dict or {},
    }
    _write_event("predictions", event)


# ── Scan history diff events ──────────────────────────────────────────

def log_price_change(
    detail_id: int,
    hotel_id: int,
    old_price: float,
    new_price: float,
    change_pct: float,
    scan_ts: str,
):
    """Log a detected price change between scans.

    Called from analyzer.py when _detect_price_changes() finds a change.
    """
    event = {
        "type": "price_change",
        "ts": scan_ts,
        "detail_id": detail_id,
        "hotel_id": hotel_id,
        "old_price": old_price,
        "new_price": new_price,
        "change_amount": round(new_price - old_price, 2),
        "change_pct": round(change_pct, 4),
        "direction": "up" if new_price > old_price else "down",
    }
    _write_event("price_changes", event)


# ── Log readers (for training pipeline) ───────────────────────────────

def load_prediction_logs(days_back: int = 90) -> list[dict]:
    """Load prediction events from the last N days of log files."""
    return _load_logs("predictions", days_back)


def load_price_logs(days_back: int = 90) -> list[dict]:
    """Load price observation events from the last N days of log files."""
    return _load_logs("prices", days_back)


def load_price_change_logs(days_back: int = 90) -> list[dict]:
    """Load price change events from the last N days of log files."""
    return _load_logs("price_changes", days_back)


def _load_logs(prefix: str, days_back: int) -> list[dict]:
    """Read all JSON-lines from log files matching prefix within date range."""
    events = []
    if not _LOG_DIR.exists():
        return events

    cutoff = datetime.utcnow().date()
    from datetime import timedelta
    start_date = cutoff - timedelta(days=days_back)

    for path in sorted(_LOG_DIR.glob(f"{prefix}_*.jsonl")):
        # Extract date from filename: predictions_2026-03-04.jsonl
        try:
            date_str = path.stem.split("_", 1)[1]  # "2026-03-04"
            from datetime import date as date_type
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if file_date < start_date:
                continue
        except (IndexError, ValueError):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as e:
            logger.warning("Failed to read log file %s: %s", path, e)

    return events


def get_log_stats() -> dict:
    """Return summary stats about available log data."""
    stats = {
        "log_dir": str(_LOG_DIR),
        "exists": _LOG_DIR.exists(),
        "files": {},
    }
    if not _LOG_DIR.exists():
        return stats

    for prefix in ("predictions", "prices", "price_changes"):
        files = list(_LOG_DIR.glob(f"{prefix}_*.jsonl"))
        total_lines = 0
        for f in files:
            try:
                with open(f) as fh:
                    total_lines += sum(1 for _ in fh)
            except Exception:
                pass
        stats["files"][prefix] = {
            "count": len(files),
            "total_events": total_lines,
            "date_range": (
                f"{files[0].stem.split('_', 1)[1]} to {files[-1].stem.split('_', 1)[1]}"
                if files else "none"
            ),
        }

    return stats
