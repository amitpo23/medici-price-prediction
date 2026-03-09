"""Closed-loop prediction accuracy tracking.

Stores every prediction in a SQLite table, then scores them against
actual prices when the check-in date passes.

Usage:
    from src.analytics.accuracy_tracker import init_tracker_db, log_prediction, score_predictions

    init_tracker_db()
    log_prediction(room_id=123, hotel_id=456, ...)
    results = score_predictions()
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "prediction_tracker.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_tracker_db() -> None:
    """Create the prediction_log table if it doesn't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prediction_log (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id               INTEGER NOT NULL,
            hotel_id              INTEGER NOT NULL,
            prediction_ts         TEXT    NOT NULL,
            checkin_date          TEXT    NOT NULL,
            t_at_prediction       INTEGER NOT NULL,
            predicted_price       REAL    NOT NULL,
            predicted_signal      TEXT,
            predicted_confidence  REAL,
            actual_price          REAL,
            actual_signal         TEXT,
            error_pct             REAL,
            error_abs             REAL,
            signal_correct        INTEGER,
            scored_at             TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_pred_room
            ON prediction_log(room_id, checkin_date);

        CREATE INDEX IF NOT EXISTS idx_pred_hotel
            ON prediction_log(hotel_id, prediction_ts);

        CREATE INDEX IF NOT EXISTS idx_pred_scored
            ON prediction_log(scored_at);

        CREATE INDEX IF NOT EXISTS idx_pred_checkin
            ON prediction_log(checkin_date);
    """)
    conn.close()


def log_prediction(
    room_id: int,
    hotel_id: int,
    predicted_price: float,
    predicted_signal: str,
    predicted_confidence: float,
    checkin_date: str,
    t_at_prediction: int,
    prediction_ts: str | None = None,
) -> None:
    """Log a single prediction to the tracker database.

    Called after each prediction batch in the analyzer.
    Silently skips duplicates (same room + same prediction timestamp).
    """
    if prediction_ts is None:
        prediction_ts = datetime.utcnow().isoformat()

    try:
        conn = _get_conn()
        conn.execute(
            """INSERT OR IGNORE INTO prediction_log
               (room_id, hotel_id, prediction_ts, checkin_date, t_at_prediction,
                predicted_price, predicted_signal, predicted_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (room_id, hotel_id, prediction_ts, checkin_date,
             t_at_prediction, predicted_price, predicted_signal,
             predicted_confidence),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.warning("Failed to log prediction for room %d: %s", room_id, e)


def log_prediction_batch(predictions: dict, run_ts: str | None = None) -> int:
    """Log a batch of predictions from the analyzer.

    Args:
        predictions: dict mapping detail_id -> prediction dict
        run_ts: timestamp of the analysis run

    Returns:
        Number of predictions logged.
    """
    if run_ts is None:
        run_ts = datetime.utcnow().isoformat()

    rows = []
    for detail_id, pred in predictions.items():
        current_price = float(pred.get("current_price", 0) or 0)
        predicted_price = float(pred.get("predicted_checkin_price", current_price) or current_price)
        change_pct = float(pred.get("expected_change_pct", 0) or 0)
        days = int(pred.get("days_to_checkin", 0) or 0)
        checkin = pred.get("date_from", "")

        if not checkin or predicted_price <= 0:
            continue

        signal = "CALL" if change_pct > 2 else "PUT" if change_pct < -2 else "NEUTRAL"
        confidence = float(pred.get("confidence_quality_score", 0.5) or 0.5)
        # Derive confidence from signals if available
        signals = pred.get("signals", [])
        if signals:
            confidence = max(s.get("confidence", 0) for s in signals)

        rows.append((
            int(detail_id), int(pred.get("hotel_id", 0)),
            run_ts, checkin, days,
            predicted_price, signal, confidence,
        ))

    if not rows:
        return 0

    try:
        conn = _get_conn()
        conn.executemany(
            """INSERT OR IGNORE INTO prediction_log
               (room_id, hotel_id, prediction_ts, checkin_date, t_at_prediction,
                predicted_price, predicted_signal, predicted_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        inserted = conn.total_changes
        conn.close()
        logger.info("Logged %d predictions to tracker", inserted)
        return inserted
    except sqlite3.Error as e:
        logger.error("Failed to log prediction batch: %s", e, exc_info=True)
        return 0


def score_predictions() -> dict:
    """Score unscored predictions where check-in date has passed.

    Looks up actual prices from the price_store (latest scan near check-in).
    Returns summary of scored predictions.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        conn = _get_conn()

        # Find unscored predictions where checkin_date < today
        unscored = pd.read_sql_query(
            """SELECT id, room_id, hotel_id, checkin_date, predicted_price, predicted_signal
               FROM prediction_log
               WHERE scored_at IS NULL AND checkin_date < ?
               LIMIT 1000""",
            conn,
            params=(now,),
        )

        if unscored.empty:
            conn.close()
            return {"scored": 0, "message": "No unscored predictions ready"}

        # Look up actual prices from price_snapshots
        from src.analytics.price_store import DB_PATH as PRICE_DB_PATH
        price_conn = sqlite3.connect(str(PRICE_DB_PATH))

        scored_count = 0
        scored_at = datetime.utcnow().isoformat()

        for _, row in unscored.iterrows():
            # Get the latest price scan closest to check-in date
            actual_df = pd.read_sql_query(
                """SELECT room_price FROM price_snapshots
                   WHERE detail_id = ? AND date_from = ?
                   ORDER BY snapshot_ts DESC LIMIT 1""",
                price_conn,
                params=(int(row["room_id"]), row["checkin_date"]),
            )

            if actual_df.empty:
                continue

            actual_price = float(actual_df.iloc[0]["room_price"])
            predicted_price = float(row["predicted_price"])

            if predicted_price <= 0:
                continue

            error_pct = ((actual_price - predicted_price) / predicted_price) * 100
            error_abs = abs(actual_price - predicted_price)

            actual_signal = "CALL" if error_pct > 2 else "PUT" if error_pct < -2 else "NEUTRAL"
            signal_correct = 1 if row["predicted_signal"] == actual_signal else 0

            conn.execute(
                """UPDATE prediction_log
                   SET actual_price = ?, actual_signal = ?,
                       error_pct = ?, error_abs = ?,
                       signal_correct = ?, scored_at = ?
                   WHERE id = ?""",
                (actual_price, actual_signal, round(error_pct, 4),
                 round(error_abs, 2), signal_correct, scored_at,
                 int(row["id"])),
            )
            scored_count += 1

        conn.commit()
        price_conn.close()
        conn.close()

        logger.info("Scored %d predictions", scored_count)
        return {"scored": scored_count, "scored_at": scored_at}

    except (sqlite3.Error, OSError) as e:
        logger.error("Failed to score predictions: %s", e, exc_info=True)
        return {"scored": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Query functions for accuracy API endpoints
# ---------------------------------------------------------------------------


def get_accuracy_summary(days: int = 30) -> dict:
    """MAE, MAPE, directional accuracy for scored predictions."""
    try:
        conn = _get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        df = pd.read_sql_query(
            """SELECT error_pct, error_abs, signal_correct, predicted_signal, actual_signal
               FROM prediction_log
               WHERE scored_at IS NOT NULL AND prediction_ts > ?""",
            conn,
            params=(cutoff,),
        )
        conn.close()

        if df.empty:
            return {"days": days, "total_scored": 0, "message": "No scored predictions in range"}

        return {
            "days": days,
            "total_scored": len(df),
            "mae": round(df["error_abs"].mean(), 2),
            "mape": round(df["error_pct"].abs().mean(), 2),
            "directional_accuracy": round((df["signal_correct"].sum() / len(df)) * 100, 1),
            "within_5pct": round((df["error_pct"].abs() <= 5).sum() / len(df) * 100, 1),
            "within_10pct": round((df["error_pct"].abs() <= 10).sum() / len(df) * 100, 1),
            "mean_error_pct": round(df["error_pct"].mean(), 2),
        }
    except (sqlite3.Error, OSError) as e:
        logger.error("Accuracy summary query failed: %s", e, exc_info=True)
        return {"error": str(e)}


def get_accuracy_by_signal() -> dict:
    """Precision/recall per CALL/PUT/NEUTRAL."""
    try:
        conn = _get_conn()
        df = pd.read_sql_query(
            """SELECT predicted_signal, actual_signal, signal_correct,
                      error_pct, error_abs
               FROM prediction_log
               WHERE scored_at IS NOT NULL""",
            conn,
        )
        conn.close()

        if df.empty:
            return {"total_scored": 0, "signals": {}}

        result = {}
        for signal in ["CALL", "PUT", "NEUTRAL"]:
            predicted_as = df[df["predicted_signal"] == signal]
            actually_was = df[df["actual_signal"] == signal]

            tp = len(predicted_as[predicted_as["signal_correct"] == 1])
            fp = len(predicted_as[predicted_as["signal_correct"] == 0])
            fn = len(actually_was) - len(actually_was[actually_was["predicted_signal"] == signal])

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0

            result[signal] = {
                "predicted_count": len(predicted_as),
                "actual_count": len(actually_was),
                "true_positives": tp,
                "precision": round(precision * 100, 1),
                "recall": round(recall * 100, 1),
                "avg_error_pct": round(predicted_as["error_pct"].abs().mean(), 2) if not predicted_as.empty else 0,
            }

        return {"total_scored": len(df), "signals": result}
    except (sqlite3.Error, OSError) as e:
        logger.error("Accuracy by signal query failed: %s", e, exc_info=True)
        return {"error": str(e)}


def get_accuracy_by_t_bucket() -> dict:
    """Accuracy for T ranges: 1-7, 8-14, 15-30, 31-60, 61+."""
    buckets = [(1, 7), (8, 14), (15, 30), (31, 60), (61, 999)]

    try:
        conn = _get_conn()
        df = pd.read_sql_query(
            """SELECT t_at_prediction, error_pct, error_abs, signal_correct
               FROM prediction_log
               WHERE scored_at IS NOT NULL""",
            conn,
        )
        conn.close()

        if df.empty:
            return {"total_scored": 0, "buckets": []}

        result = []
        for low, high in buckets:
            bucket = df[(df["t_at_prediction"] >= low) & (df["t_at_prediction"] <= high)]
            if bucket.empty:
                continue
            label = f"{low}-{high}" if high < 999 else f"{low}+"
            result.append({
                "bucket": label,
                "count": len(bucket),
                "mape": round(bucket["error_pct"].abs().mean(), 2),
                "mae": round(bucket["error_abs"].mean(), 2),
                "directional_accuracy": round((bucket["signal_correct"].sum() / len(bucket)) * 100, 1),
                "within_5pct": round((bucket["error_pct"].abs() <= 5).sum() / len(bucket) * 100, 1),
            })

        return {"total_scored": len(df), "buckets": result}
    except (sqlite3.Error, OSError) as e:
        logger.error("Accuracy by T-bucket query failed: %s", e, exc_info=True)
        return {"error": str(e)}


def get_accuracy_by_hotel() -> dict:
    """Per-hotel accuracy metrics."""
    try:
        conn = _get_conn()
        df = pd.read_sql_query(
            """SELECT hotel_id, error_pct, error_abs, signal_correct
               FROM prediction_log
               WHERE scored_at IS NOT NULL""",
            conn,
        )
        conn.close()

        if df.empty:
            return {"total_scored": 0, "hotels": []}

        hotels = []
        for hotel_id, group in df.groupby("hotel_id"):
            hotels.append({
                "hotel_id": int(hotel_id),
                "count": len(group),
                "mape": round(group["error_pct"].abs().mean(), 2),
                "mae": round(group["error_abs"].mean(), 2),
                "directional_accuracy": round((group["signal_correct"].sum() / len(group)) * 100, 1),
                "mean_error_pct": round(group["error_pct"].mean(), 2),
            })

        hotels.sort(key=lambda h: h["mape"])
        return {"total_scored": len(df), "hotels": hotels}
    except (sqlite3.Error, OSError) as e:
        logger.error("Accuracy by hotel query failed: %s", e, exc_info=True)
        return {"error": str(e)}


def get_accuracy_trend(window_days: int = 7) -> dict:
    """Rolling accuracy trend (7-day and 30-day windows)."""
    try:
        conn = _get_conn()
        df = pd.read_sql_query(
            """SELECT prediction_ts, error_pct, signal_correct
               FROM prediction_log
               WHERE scored_at IS NOT NULL
               ORDER BY prediction_ts""",
            conn,
        )
        conn.close()

        if df.empty:
            return {"total_scored": 0, "trend": []}

        df["date"] = pd.to_datetime(df["prediction_ts"]).dt.date

        daily = df.groupby("date").agg(
            count=("error_pct", "size"),
            mape=("error_pct", lambda x: x.abs().mean()),
            directional=("signal_correct", "mean"),
        ).reset_index()

        daily["mape_7d"] = daily["mape"].rolling(7, min_periods=1).mean()
        daily["mape_30d"] = daily["mape"].rolling(30, min_periods=1).mean()
        daily["dir_7d"] = daily["directional"].rolling(7, min_periods=1).mean()

        trend = []
        for _, row in daily.iterrows():
            trend.append({
                "date": str(row["date"]),
                "count": int(row["count"]),
                "mape": round(float(row["mape"]), 2),
                "mape_7d": round(float(row["mape_7d"]), 2),
                "mape_30d": round(float(row["mape_30d"]), 2),
                "directional_accuracy_7d": round(float(row["dir_7d"]) * 100, 1),
            })

        return {"total_scored": len(df), "trend": trend}
    except (sqlite3.Error, OSError) as e:
        logger.error("Accuracy trend query failed: %s", e, exc_info=True)
        return {"error": str(e)}


def get_tracker_stats() -> dict:
    """Quick stats about the prediction tracker."""
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM prediction_log").fetchone()[0]
        scored = conn.execute("SELECT COUNT(*) FROM prediction_log WHERE scored_at IS NOT NULL").fetchone()[0]
        unscored = total - scored
        conn.close()
        return {"total": total, "scored": scored, "unscored": unscored}
    except (sqlite3.Error, OSError):
        return {"total": 0, "scored": 0, "unscored": 0}
