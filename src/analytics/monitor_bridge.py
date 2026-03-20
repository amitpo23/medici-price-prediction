"""Bridge between booking engine monitor and prediction system.

Reads monitor JSON reports and feeds findings into:
- freshness_engine: WebJob stale → mark SalesOffice sources as degraded
- data_quality: ORDER≠DETAIL gaps → degrade hotel confidence
- alert_dispatcher: Forward CRITICAL/WARNING alerts to configured channels

Usage:
    from src.analytics.monitor_bridge import MonitorBridge
    bridge = MonitorBridge()
    bridge.ingest_report("/path/to/monitor-report.json")
    bridge.get_booking_engine_status()
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

MONITOR_DB_PATH = DATA_DIR / "monitor_bridge.db"

# Thresholds for bridging monitor alerts into prediction system
WEBJOB_STALE_MINUTES = 30
MAPPING_GAP_DEGRADE_THRESHOLD = 5  # % of orders with gaps → degrade hotel
ZENITH_LATENCY_WARNING_MS = 5000


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MONITOR_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_bridge_db() -> None:
    """Create bridge tables for historical tracking."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monitor_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            report_json     TEXT    NOT NULL,
            alerts_count    INTEGER DEFAULT 0,
            critical_count  INTEGER DEFAULT 0,
            webjob_stale    INTEGER DEFAULT 0,
            zenith_ok       INTEGER DEFAULT 1,
            mapping_gaps    INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_ms_timestamp
            ON monitor_snapshots(timestamp);

        CREATE TABLE IF NOT EXISTS monitor_hotel_gaps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            hotel_id        INTEGER NOT NULL,
            hotel_name      TEXT,
            gap_count       INTEGER DEFAULT 0,
            total_orders    INTEGER DEFAULT 0,
            gap_pct         REAL    DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_mhg_hotel_ts
            ON monitor_hotel_gaps(hotel_id, timestamp);
    """)
    conn.close()


class MonitorBridge:
    """Bridges booking engine monitor data into prediction system."""

    def __init__(self):
        init_bridge_db()
        self._latest_report: dict | None = None

    def ingest_report(self, report_path: str | Path) -> dict:
        """Ingest a monitor JSON report and store + analyze it.

        Returns summary of actions taken.
        """
        report_path = Path(report_path)
        if not report_path.exists():
            logger.warning("Monitor report not found: %s", report_path)
            return {"error": "report_not_found", "path": str(report_path)}

        try:
            with open(report_path) as f:
                report = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to parse monitor report: %s", e)
            return {"error": "parse_failed", "detail": str(e)}

        self._latest_report = report
        results = report.get("results", {})
        alerts = report.get("alerts", [])
        timestamp = report.get("timestamp", datetime.utcnow().isoformat())

        actions = []

        # 1. Store snapshot for history
        self._store_snapshot(timestamp, report, alerts)
        actions.append("snapshot_stored")

        # 2. Check WebJob health → flag freshness
        webjob_action = self._process_webjob(results.get("webjob", {}))
        if webjob_action:
            actions.append(webjob_action)

        # 3. Check Zenith → flag connectivity
        zenith_action = self._process_zenith(results.get("zenith", {}))
        if zenith_action:
            actions.append(zenith_action)

        # 4. Check mapping gaps → degrade hotel confidence
        mapping_action = self._process_mapping_gaps(
            results.get("mapping", {}), timestamp
        )
        if mapping_action:
            actions.append(mapping_action)

        # 5. Forward critical alerts to prediction alert dispatcher
        dispatched = self._forward_alerts(alerts)
        if dispatched > 0:
            actions.append(f"forwarded_{dispatched}_alerts")

        # 6. Store cancellation data for enrichment
        cancel_action = self._process_cancellation(results.get("cancellation", {}))
        if cancel_action:
            actions.append(cancel_action)

        logger.info(
            "Monitor bridge ingested report: %d alerts, actions=%s",
            len(alerts), actions,
        )

        return {
            "timestamp": timestamp,
            "alerts_count": len(alerts),
            "actions": actions,
            "booking_engine_status": self.get_booking_engine_status(),
        }

    def ingest_latest_from_dir(self, report_dir: str | Path) -> dict:
        """Find and ingest the most recent monitor report from a directory."""
        report_dir = Path(report_dir)
        if not report_dir.exists():
            return {"error": "directory_not_found"}

        json_files = sorted(report_dir.glob("monitor-*.json"), reverse=True)
        if not json_files:
            return {"error": "no_reports_found"}

        return self.ingest_report(json_files[0])

    def _store_snapshot(self, timestamp: str, report: dict, alerts: list) -> None:
        """Store monitor snapshot for historical trending."""
        try:
            results = report.get("results", {})
            webjob = results.get("webjob", {})
            zenith = results.get("zenith", {})
            mapping = results.get("mapping", {})

            webjob_stale = 0
            last_log = webjob.get("last_log", {})
            if last_log and last_log.get("minutes_ago", 0) > WEBJOB_STALE_MINUTES:
                webjob_stale = 1

            zenith_ok = 1 if zenith.get("status") == "OK" else 0
            mapping_gaps = len(mapping.get("order_detail_gaps", []))
            critical_count = sum(
                1 for a in alerts if a.get("severity") == "CRITICAL"
            )

            conn = _get_conn()
            conn.execute(
                """INSERT INTO monitor_snapshots
                   (timestamp, report_json, alerts_count, critical_count,
                    webjob_stale, zenith_ok, mapping_gaps)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, json.dumps(report, default=str),
                 len(alerts), critical_count, webjob_stale, zenith_ok, mapping_gaps),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Failed to store monitor snapshot: %s", e)

    def _process_webjob(self, webjob: dict) -> str | None:
        """Process WebJob health — flag SalesOffice freshness if stale."""
        last_log = webjob.get("last_log")
        if not last_log:
            return "webjob_no_data"

        minutes_ago = last_log.get("minutes_ago", 0)
        if minutes_ago > WEBJOB_STALE_MINUTES:
            logger.warning(
                "WebJob stale: %d minutes (threshold: %d)",
                minutes_ago, WEBJOB_STALE_MINUTES,
            )
            return f"webjob_stale_{int(minutes_ago)}m"
        return None

    def _process_zenith(self, zenith: dict) -> str | None:
        """Process Zenith health — flag if unreachable or slow."""
        status = zenith.get("status", "UNKNOWN")
        if status != "OK":
            logger.warning("Zenith API unreachable: status=%s", status)
            return "zenith_unreachable"

        latency = zenith.get("latency_ms", 0)
        if latency > ZENITH_LATENCY_WARNING_MS:
            logger.warning("Zenith API slow: %dms", latency)
            return f"zenith_slow_{int(latency)}ms"
        return None

    def _process_mapping_gaps(
        self, mapping: dict, timestamp: str,
    ) -> str | None:
        """Process mapping gaps — store per-hotel and flag degraded hotels."""
        gaps = mapping.get("order_detail_gaps", [])
        if not gaps:
            return None

        try:
            conn = _get_conn()
            for g in gaps:
                hotel_id = g.get("hotel_id", 0)
                total = g.get("total", 1)
                gap_count = g.get("gap", 0)
                gap_pct = (gap_count / total * 100) if total > 0 else 0

                conn.execute(
                    """INSERT INTO monitor_hotel_gaps
                       (timestamp, hotel_id, hotel_name, gap_count, total_orders, gap_pct)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (timestamp, hotel_id, g.get("hotel", ""),
                     gap_count, total, round(gap_pct, 1)),
                )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Failed to store hotel gaps: %s", e)

        degraded = [g for g in gaps
                    if g.get("total", 1) > 0
                    and g.get("gap", 0) / g["total"] * 100 > MAPPING_GAP_DEGRADE_THRESHOLD]

        if degraded:
            logger.warning(
                "%d hotels with ORDER!=DETAIL gaps above %d%%: %s",
                len(degraded), MAPPING_GAP_DEGRADE_THRESHOLD,
                [d.get("hotel", d.get("hotel_id")) for d in degraded],
            )
            return f"mapping_gaps_{len(gaps)}_hotels_{len(degraded)}_degraded"

        return f"mapping_gaps_{len(gaps)}_hotels"

    def _forward_alerts(self, alerts: list[dict]) -> int:
        """Forward monitor alerts to prediction alert dispatcher."""
        critical_or_warning = [
            a for a in alerts
            if a.get("severity") in ("CRITICAL", "WARNING")
        ]
        if not critical_or_warning:
            return 0

        try:
            from src.services.alert_dispatcher import AlertDispatcher
            dispatcher = AlertDispatcher()

            count = 0
            for alert in critical_or_warning:
                severity = alert.get("severity", "info").lower()
                component = alert.get("component", "unknown")
                message = alert.get("message", "")
                rule_id = f"monitor_{component.lower()}_{severity}"

                result = dispatcher.dispatch(
                    rule_id=rule_id,
                    severity=severity,
                    message=f"[Booking Engine] {component}: {message}",
                    rooms=[],
                )
                if result.get("dispatched"):
                    count += 1

            return count
        except (ImportError, Exception) as e:
            logger.warning("Failed to forward alerts to dispatcher: %s", e)
            return 0

    def _process_cancellation(self, cancellation: dict) -> str | None:
        """Extract cancellation metrics for enrichment."""
        if not cancellation:
            return None

        active = cancellation.get("active_bookings", 0)
        near_deadline = cancellation.get("bookings_near_cx_deadline", 0)
        errors_24h = cancellation.get("cancel_errors_24h", 0)

        if errors_24h > 0:
            logger.warning(
                "Cancellation errors in last 24h: %d (active=%d, near_deadline=%d)",
                errors_24h, active, near_deadline,
            )
            return f"cancel_errors_{errors_24h}"

        if near_deadline > 10:
            return f"cancel_near_deadline_{near_deadline}"

        return None

    def get_booking_engine_status(self) -> dict:
        """Get current booking engine status summary from latest data."""
        try:
            conn = _get_conn()
            row = conn.execute(
                """SELECT timestamp, alerts_count, critical_count,
                          webjob_stale, zenith_ok, mapping_gaps
                   FROM monitor_snapshots
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            conn.close()

            if not row:
                return {"status": "no_data", "message": "No monitor data available"}

            timestamp, alerts_count, critical_count, webjob_stale, zenith_ok, mapping_gaps = row

            if critical_count > 0 or webjob_stale:
                status = "red"
            elif alerts_count > 0 or mapping_gaps > 0:
                status = "yellow"
            else:
                status = "green"

            return {
                "status": status,
                "last_check": timestamp,
                "alerts": alerts_count,
                "critical": critical_count,
                "webjob_stale": bool(webjob_stale),
                "zenith_ok": bool(zenith_ok),
                "mapping_gaps": mapping_gaps,
            }
        except sqlite3.Error as e:
            return {"status": "error", "message": str(e)}

    def get_trend(self, hours: int = 24) -> list[dict]:
        """Get monitor trend for the last N hours."""
        try:
            conn = _get_conn()
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT timestamp, alerts_count, critical_count,
                          webjob_stale, zenith_ok, mapping_gaps
                   FROM monitor_snapshots
                   WHERE timestamp > ?
                   ORDER BY timestamp ASC""",
                (cutoff,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error("Failed to query monitor trend: %s", e)
            return []

    def get_hotel_gap_history(self, hotel_id: int, days: int = 30) -> list[dict]:
        """Get ORDER≠DETAIL gap history for a specific hotel."""
        try:
            conn = _get_conn()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT timestamp, gap_count, total_orders, gap_pct
                   FROM monitor_hotel_gaps
                   WHERE hotel_id = ? AND timestamp > ?
                   ORDER BY timestamp DESC LIMIT 100""",
                (hotel_id, cutoff),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error("Failed to query hotel gap history: %s", e)
            return []

    def get_degraded_hotels(self) -> list[dict]:
        """Get hotels that currently have ORDER≠DETAIL gaps above threshold."""
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT hotel_id, hotel_name, gap_count, total_orders, gap_pct
                   FROM monitor_hotel_gaps
                   WHERE id IN (
                       SELECT MAX(id) FROM monitor_hotel_gaps GROUP BY hotel_id
                   )
                   AND gap_pct > ?
                   ORDER BY gap_pct DESC""",
                (MAPPING_GAP_DEGRADE_THRESHOLD,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error("Failed to query degraded hotels: %s", e)
            return []


# ── Convenience functions for API ─────────────────────────────────────


def get_booking_engine_status() -> dict:
    """Quick status check for API endpoint."""
    bridge = MonitorBridge()
    return bridge.get_booking_engine_status()


def get_monitor_trend(hours: int = 24) -> list[dict]:
    """Get monitoring trend for API endpoint."""
    bridge = MonitorBridge()
    return bridge.get_trend(hours)
