"""Data quality scoring for all data sources.

Computes freshness, reliability, and anomaly scores per source,
and auto-adjusts enrichment weights when sources degrade.

Usage:
    from src.analytics.data_quality import DataQualityScorer
    scorer = DataQualityScorer()
    status = scorer.score_all()
    history = scorer.get_history(source_id="open_meteo", days=30)
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime, timedelta

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "source_health.db"

# Expected fetch intervals per source (hours)
EXPECTED_INTERVALS: dict[str, float] = {
    "salesoffice": 1.0,
    "ai_search_hotel_data": 4.0,
    "search_results_poll_log": 4.0,
    "room_price_update_log": 4.0,
    "med_prebook": 24.0,
    "med_search_hotels": 999.0,  # static archive
    "salesoffice_log": 4.0,
    "cancellation_data": 24.0,
    "destinations_geo": 168.0,  # weekly
    "kiwi_flights": 24.0,
    "open_meteo": 24.0,
    "seatgeek": 24.0,
    "miami_events_hardcoded": 720.0,  # monthly
    "fred": 720.0,
    "tbo_hotels": 720.0,
    "hotel_booking_dataset": 720.0,
    "trivago_statista": 720.0,
    "brightdata_mcp": 168.0,
    "ota_brightdata_exports": 168.0,
}

# Sources whose weights should never be reduced
PROTECTED_SOURCES = {"salesoffice"}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_quality_db() -> None:
    """Create the source_health table if it doesn't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS source_health (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            freshness_score REAL    NOT NULL,
            reliability_score REAL  NOT NULL,
            anomaly_flag    INTEGER DEFAULT 0,
            weight_override REAL,
            error_message   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_sh_source_ts
            ON source_health(source_id, timestamp);
    """)
    conn.close()


def _log_health(
    source_id: str,
    freshness_score: float,
    reliability_score: float,
    anomaly_flag: bool = False,
    weight_override: float | None = None,
    error_message: str | None = None,
) -> None:
    """Record a source health snapshot."""
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO source_health
               (source_id, timestamp, freshness_score, reliability_score,
                anomaly_flag, weight_override, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_id, datetime.utcnow().isoformat(),
             round(freshness_score, 4), round(reliability_score, 4),
             1 if anomaly_flag else 0, weight_override, error_message),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.warning("Failed to log source health for %s: %s", source_id, e)


class DataQualityScorer:
    """Score data source quality using freshness, reliability, and anomaly detection."""

    def __init__(self):
        init_quality_db()

    def score_all(self) -> dict:
        """Score all sources and return status report.

        Uses the freshness engine for current freshness data,
        then computes reliability from 30-day history and anomaly flags.
        """
        from src.analytics.freshness_engine import build_freshness_data

        freshness_data = build_freshness_data()
        sources = freshness_data.get("sources", [])

        scored = []
        for src in sources:
            source_id = src.get("id", src.get("source", "unknown"))
            age_hours = src.get("age_hours")

            # Freshness score: exponential decay from expected interval
            freshness = self._compute_freshness(source_id, age_hours)

            # Reliability: 30-day success rate from history
            reliability = self._compute_reliability(source_id)

            # Anomaly: flag if freshness drops significantly
            anomaly = freshness < 0.3 and reliability > 0.7

            # Auto weight adjustment
            weight_override = None
            if source_id not in PROTECTED_SOURCES and freshness < 0.5:
                weight_override = round(freshness, 3)

            _log_health(source_id, freshness, reliability, anomaly, weight_override)

            scored.append({
                "source_id": source_id,
                "name": src.get("name", source_id),
                "freshness_score": round(freshness, 3),
                "reliability_score": round(reliability, 3),
                "anomaly_flag": anomaly,
                "weight_override": weight_override,
                "status": src.get("status", "unknown"),
                "age_hours": round(age_hours, 1) if age_hours is not None else None,
                "last_updated": src.get("last_updated"),
            })

        # Overall status
        avg_freshness = sum(s["freshness_score"] for s in scored) / len(scored) if scored else 0
        anomaly_count = sum(1 for s in scored if s["anomaly_flag"])

        # Dispatch alerts for degraded sources
        self._dispatch_quality_alerts(scored)

        return {
            "checked_at": datetime.utcnow().isoformat(),
            "total_sources": len(scored),
            "avg_freshness": round(avg_freshness, 3),
            "anomaly_count": anomaly_count,
            "sources": scored,
        }

    def _compute_freshness(self, source_id: str, age_hours: float | None) -> float:
        """Exponential decay freshness score (0-1).

        score = exp(-age / expected_interval)
        """
        if age_hours is None or age_hours < 0:
            return 0.5  # Unknown → assume medium

        expected = EXPECTED_INTERVALS.get(source_id, 24.0)
        if expected >= 999:
            return 1.0  # Static source, always fresh

        ratio = age_hours / expected
        return max(0.0, min(1.0, math.exp(-ratio + 1)))

    def _compute_reliability(self, source_id: str) -> float:
        """30-day rolling reliability score (0-1).

        Based on ratio of good freshness readings (>0.5) in history.
        """
        try:
            conn = _get_conn()
            cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
            rows = conn.execute(
                """SELECT freshness_score FROM source_health
                   WHERE source_id = ? AND timestamp > ?
                   ORDER BY timestamp DESC LIMIT 100""",
                (source_id, cutoff),
            ).fetchall()
            conn.close()

            if not rows:
                return 1.0  # No history → assume reliable

            good = sum(1 for r in rows if r[0] > 0.5)
            return round(good / len(rows), 3)
        except sqlite3.Error:
            return 1.0

    def _dispatch_quality_alerts(self, scored: list[dict]) -> None:
        """Dispatch alerts for sources with freshness below threshold.

        Connects data quality scoring to the alert dispatcher so degraded
        sources trigger notifications via configured channels (Log/Webhook/Telegram).
        """
        degraded = [s for s in scored if s.get("freshness_score", 1.0) < 0.3]
        anomalies = [s for s in scored if s.get("anomaly_flag")]

        if not degraded and not anomalies:
            return

        try:
            from src.services.alert_dispatcher import AlertDispatcher
            dispatcher = AlertDispatcher()

            # Alert for critically degraded sources (freshness < 0.3)
            if degraded:
                source_names = [s.get("name", s.get("source_id", "?")) for s in degraded]
                dispatcher.dispatch(
                    rule_id="data_quality_degraded",
                    severity="warning",
                    message=(
                        f"{len(degraded)} data source(s) critically degraded "
                        f"(freshness < 0.3): {', '.join(source_names[:5])}"
                    ),
                    rooms=[],
                )

            # Separate alert for anomalies (sudden freshness drop on normally reliable source)
            if anomalies:
                source_names = [s.get("name", s.get("source_id", "?")) for s in anomalies]
                dispatcher.dispatch(
                    rule_id="data_quality_anomaly",
                    severity="high",
                    message=(
                        f"{len(anomalies)} data source anomaly detected "
                        f"(reliable source suddenly stale): {', '.join(source_names[:5])}"
                    ),
                    rooms=[],
                )

        except (ImportError, Exception) as e:
            logger.warning("Failed to dispatch quality alerts: %s", e)

    def get_weight_adjustments(self) -> dict[str, float]:
        """Get current weight overrides for degraded sources.

        Returns dict mapping source_id → weight (0-1).
        Only includes sources that need adjustment.
        """
        try:
            conn = _get_conn()
            # Get latest health record per source that has a weight override
            rows = conn.execute(
                """SELECT source_id, weight_override
                   FROM source_health
                   WHERE weight_override IS NOT NULL
                   AND id IN (
                       SELECT MAX(id) FROM source_health
                       GROUP BY source_id
                   )"""
            ).fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows if r[1] is not None and r[1] < 1.0}
        except sqlite3.Error:
            return {}


# ── Query functions for API ─────────────────────────────────────────


def get_quality_status() -> dict:
    """Get current quality status for all sources."""
    scorer = DataQualityScorer()
    return scorer.score_all()


def get_quality_history(source_id: str, days: int = 30) -> dict:
    """Get quality history for a specific source."""
    try:
        init_quality_db()
        conn = _get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT * FROM source_health
               WHERE source_id = ? AND timestamp > ?
               ORDER BY timestamp DESC LIMIT 200""",
            (source_id, cutoff),
        ).fetchall()
        conn.close()

        history = [dict(r) for r in rows]
        return {
            "source_id": source_id,
            "days": days,
            "total_records": len(history),
            "history": history,
        }
    except sqlite3.Error as e:
        logger.error("Failed to query quality history: %s", e, exc_info=True)
        return {"source_id": source_id, "error": str(e)}
