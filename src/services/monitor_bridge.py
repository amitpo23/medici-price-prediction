"""Bridge between the Medici Monitor system and the Price Prediction engine.

Provides three capabilities:
1. Scheduled health checks — polls /health?detail=true and dispatches alerts on degradation
2. Monitor result ingestion — takes SystemMonitor output and adjusts prediction confidence
3. Unified health status — combines prediction engine + booking engine health

Usage:
    from src.services.monitor_bridge import MonitorBridge
    bridge = MonitorBridge()

    # Run health-based alerting (call every 30 min)
    bridge.check_health_and_alert()

    # Ingest external monitor results (from system_monitor.py)
    bridge.ingest_monitor_results(monitor_json)

    # Get unified status
    status = bridge.get_unified_status()
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

MONITOR_DB_PATH = DATA_DIR / "monitor_bridge.db"

# Severity mapping from monitor alerts to dispatcher severity
_SEVERITY_MAP = {
    "CRITICAL": "critical",
    "ERROR": "high",
    "WARNING": "warning",
    "INFO": "info",
}

# How monitor findings affect prediction confidence
CONFIDENCE_ADJUSTMENTS = {
    # Operational health
    "webjob_stale": -0.20,          # WebJob > 30 min → reduce confidence 20%
    "zenith_unreachable": -0.25,     # API down → major confidence reduction
    "failed_orders": -0.10,          # Failed orders → reduce confidence 10%
    # Data quality
    "order_detail_gaps": -0.15,      # ORDER≠DETAIL → reduce hotel confidence 15%
    "mapping_miss_high_rate": -0.10, # High miss rate → reduce confidence 10%
    "no_bb_mapping": -0.10,          # Hotel lacks BB mapping → incomplete data
    # Skills health
    "override_failures": -0.15,      # PriceOverride failures → prices may diverge
    "scan_cycle_slow": -0.10,        # Scan cycle > 24h → stale prices
    # Cancellation signals
    "cancel_errors": -0.05,          # Cancel errors → minor confidence reduction
    "high_cx_deadline": -0.05,       # Many bookings near CX deadline → volatility
}

# Market signals extracted from monitor (not just confidence, but enrichment data)
# These flow into the prediction engine as real-time signals
MARKET_SIGNALS = {
    "insert_opp_activity": "market_dynamism",     # High BackOfficeOPT activity
    "ro_bb_ratio": "board_composition",            # Room Only vs Bed & Breakfast
    "active_bookings_count": "demand_indicator",   # Live booking volume
    "cx_deadline_count": "supply_volatility",      # Upcoming cancellation window
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MONITOR_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_monitor_db() -> None:
    """Create monitor_history and confidence_adjustments tables."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monitor_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT 'health_check',
            status      TEXT NOT NULL,
            alerts_json TEXT,
            results_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_mh_ts
            ON monitor_history(timestamp);

        CREATE TABLE IF NOT EXISTS confidence_adjustments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            hotel_id    TEXT,
            adjustment_type TEXT NOT NULL,
            adjustment_value REAL NOT NULL,
            reason      TEXT,
            expires_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ca_hotel_ts
            ON confidence_adjustments(hotel_id, timestamp);

        CREATE INDEX IF NOT EXISTS idx_ca_expires
            ON confidence_adjustments(expires_at);

        CREATE TABLE IF NOT EXISTS market_signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            hotel_id    TEXT,
            signal_type TEXT NOT NULL,
            signal_value REAL NOT NULL,
            metadata    TEXT,
            expires_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ms_type_ts
            ON market_signals(signal_type, timestamp);

        CREATE INDEX IF NOT EXISTS idx_ms_hotel
            ON market_signals(hotel_id, timestamp);
    """)
    conn.close()


class MonitorBridge:
    """Bridges monitor findings to prediction engine confidence and alerting."""

    def __init__(self):
        init_monitor_db()

    # ── 1. Health-based alerting ───────────────────────────────────────

    def check_health_and_alert(self) -> dict:
        """Poll the prediction engine health endpoint and dispatch alerts.

        Should be called periodically (every 30 minutes).
        Returns dict with health status and any alerts dispatched.
        """
        try:
            from src.analytics.freshness_engine import build_freshness_data
            from src.utils.cache_manager import cache
        except ImportError as e:
            logger.warning("Cannot import health dependencies: %s", e)
            return {"error": str(e)}

        alerts_dispatched = []

        # Check freshness
        try:
            freshness = build_freshness_data()
            overall = freshness.get("summary", {}).get("overall_status", "unknown")

            if overall in ("red", "yellow"):
                stale_sources = [
                    s for s in freshness.get("sources", [])
                    if s.get("status") in ("red", "stale")
                ]
                if stale_sources:
                    severity = "critical" if overall == "red" else "warning"
                    alert = self._dispatch_alert(
                        rule_id="health_freshness_degraded",
                        severity=severity,
                        message=(
                            f"Health check: {len(stale_sources)} source(s) stale. "
                            f"Overall: {overall}. "
                            f"Sources: {', '.join(s.get('name', '?') for s in stale_sources[:5])}"
                        ),
                    )
                    alerts_dispatched.append(alert)
        except (OSError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Health freshness check failed: %s", e)
            alert = self._dispatch_alert(
                rule_id="health_check_error",
                severity="critical",
                message=f"Health check failed — cannot evaluate freshness: {str(e)[:100]}",
            )
            alerts_dispatched.append(alert)

        # Check prediction cache age
        try:
            analytics_data = cache.get_data("analytics")
            if analytics_data:
                last_scan = analytics_data.get("run_ts")
                if last_scan:
                    scan_dt = datetime.fromisoformat(
                        last_scan.replace("Z", "+00:00")
                    ) if isinstance(last_scan, str) else last_scan
                    scan_age_hours = (
                        datetime.utcnow() - scan_dt.replace(tzinfo=None)
                    ).total_seconds() / 3600
                    if scan_age_hours > 6:
                        alert = self._dispatch_alert(
                            rule_id="health_predictions_stale",
                            severity="high",
                            message=f"Predictions are {scan_age_hours:.1f}h old (threshold: 6h)",
                        )
                        alerts_dispatched.append(alert)
            else:
                alert = self._dispatch_alert(
                    rule_id="health_no_predictions",
                    severity="warning",
                    message="No prediction data in cache — engine may not have run",
                )
                alerts_dispatched.append(alert)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("Prediction cache check failed: %s", e)

        # Log to history
        status = "healthy" if not alerts_dispatched else "degraded"
        self._log_history("health_check", status, alerts_dispatched)

        return {
            "status": status,
            "checked_at": datetime.utcnow().isoformat(),
            "alerts_dispatched": len(alerts_dispatched),
            "alerts": alerts_dispatched,
        }

    # ── 2. Monitor result ingestion ────────────────────────────────────

    def ingest_monitor_results(self, monitor_output: dict) -> dict:
        """Ingest results from system_monitor.py and apply confidence adjustments.

        Args:
            monitor_output: Dict with "results" and "alerts" keys from SystemMonitor.

        Returns:
            Dict with adjustments applied and alerts forwarded.
        """
        results = monitor_output.get("results", {})
        monitor_alerts = monitor_output.get("alerts", [])
        adjustments_applied = []
        alerts_forwarded = []

        # Forward monitor alerts to our dispatcher
        for alert in monitor_alerts:
            severity = _SEVERITY_MAP.get(alert.get("severity", "INFO"), "info")
            component = alert.get("component", "unknown")
            forwarded = self._dispatch_alert(
                rule_id=f"monitor_{component.lower()}",
                severity=severity,
                message=f"[Monitor] {alert.get('message', '')}",
            )
            alerts_forwarded.append(forwarded)

        # Apply confidence adjustments based on findings
        now = datetime.utcnow()
        expires = (now + timedelta(hours=1)).isoformat()

        # WebJob stale
        webjob = results.get("webjob", {})
        last_log = webjob.get("last_log", {})
        if last_log and last_log.get("minutes_ago", 0) > 30:
            adj = self._apply_adjustment(
                hotel_id=None,  # Global
                adj_type="webjob_stale",
                value=CONFIDENCE_ADJUSTMENTS["webjob_stale"],
                reason=f"WebJob stale: {last_log['minutes_ago']:.0f}min since last activity",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # Failed orders
        if webjob.get("failed_orders", 0) > 0:
            adj = self._apply_adjustment(
                hotel_id=None,
                adj_type="failed_orders",
                value=CONFIDENCE_ADJUSTMENTS["failed_orders"],
                reason=f"{webjob['failed_orders']} failed orders detected",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # ORDER≠DETAIL gaps (per hotel)
        mapping = results.get("mapping", {})
        for gap in mapping.get("order_detail_gaps", []):
            hotel_id = str(gap.get("hotel_id", ""))
            if hotel_id:
                adj = self._apply_adjustment(
                    hotel_id=hotel_id,
                    adj_type="order_detail_gaps",
                    value=CONFIDENCE_ADJUSTMENTS["order_detail_gaps"],
                    reason=f"ORDER≠DETAIL gap: {gap.get('gap', 0)} gaps / {gap.get('total', 0)} orders",
                    expires_at=expires,
                )
                adjustments_applied.append(adj)

        # High mapping miss rate
        if mapping.get("miss_rate_last_hour", 0) > 10:
            adj = self._apply_adjustment(
                hotel_id=None,
                adj_type="mapping_miss_high_rate",
                value=CONFIDENCE_ADJUSTMENTS["mapping_miss_high_rate"],
                reason=f"Mapping miss rate: {mapping['miss_rate_last_hour']}/hour",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # Zenith unreachable
        zenith = results.get("zenith", {})
        if zenith.get("status") in ("UNREACHABLE", "ERROR"):
            adj = self._apply_adjustment(
                hotel_id=None,
                adj_type="zenith_unreachable",
                value=CONFIDENCE_ADJUSTMENTS["zenith_unreachable"],
                reason=f"Zenith API: {zenith.get('status')} — {zenith.get('error', '')}",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # Cancel errors
        cancellation = results.get("cancellation", {})
        if cancellation.get("cancel_errors_24h", 0) > 0:
            adj = self._apply_adjustment(
                hotel_id=None,
                adj_type="cancel_errors",
                value=CONFIDENCE_ADJUSTMENTS["cancel_errors"],
                reason=f"{cancellation['cancel_errors_24h']} cancellation errors in 24h",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # ── Deep extraction from booking engine DB ─────────────────

        # Scan cycle too slow → prices may be stale
        cycle_hours = webjob.get("estimated_cycle_hours", 0)
        if cycle_hours > 24:
            adj = self._apply_adjustment(
                hotel_id=None,
                adj_type="scan_cycle_slow",
                value=CONFIDENCE_ADJUSTMENTS["scan_cycle_slow"],
                reason=f"Scan cycle {cycle_hours:.0f}h exceeds 24h threshold",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # PriceOverride failures → executed price differs from predicted
        skills = results.get("skills", {})
        po = skills.get("price_override", {})
        po_total = po.get("total", 0) or 0
        po_failed = po.get("failed", 0) or 0
        if po_total > 0 and po_failed > 0:
            fail_pct = po_failed / po_total * 100
            if fail_pct > 20:
                adj = self._apply_adjustment(
                    hotel_id=None,
                    adj_type="override_failures",
                    value=CONFIDENCE_ADJUSTMENTS["override_failures"],
                    reason=f"PriceOverride: {po_failed} failures ({fail_pct:.0f}% of {po_total})",
                    expires_at=expires,
                )
                adjustments_applied.append(adj)

        # Bookings near CX deadline → supply may shift
        near_cx = cancellation.get("bookings_near_cx_deadline", 0)
        if near_cx > 10:
            adj = self._apply_adjustment(
                hotel_id=None,
                adj_type="high_cx_deadline",
                value=CONFIDENCE_ADJUSTMENTS["high_cx_deadline"],
                reason=f"{near_cx} bookings within 5 days of cancellation deadline",
                expires_at=expires,
            )
            adjustments_applied.append(adj)

        # ── Market signals (enrichment data for prediction) ────────
        signals_stored = []

        # InsertOpp activity → market dynamism indicator
        insert_opp = skills.get("insert_opp", {})
        opp_24h = insert_opp.get("last_24h", 0) or 0
        if opp_24h > 0:
            self._store_signal(
                signal_type="market_dynamism",
                value=min(1.0, opp_24h / 50.0),  # Normalize: 50+ opps/day = max
                metadata=json.dumps({"raw_count": opp_24h, "active": insert_opp.get("active", 0)}),
                expires_at=expires,
            )
            signals_stored.append("market_dynamism")

        # Active bookings count → demand indicator
        active_bookings = cancellation.get("active_bookings", 0)
        if active_bookings > 0:
            self._store_signal(
                signal_type="demand_indicator",
                value=min(1.0, active_bookings / 200.0),  # Normalize: 200+ = max
                metadata=json.dumps({"active_bookings": active_bookings}),
                expires_at=expires,
            )
            signals_stored.append("demand_indicator")

        # RO:BB ratio from orders → board composition signal
        orders = results.get("orders", {})
        details = orders.get("details", {})
        ro_count = details.get("ro", 0) or 0
        bb_count = details.get("bb", 0) or 0
        if ro_count + bb_count > 0:
            bb_ratio = bb_count / (ro_count + bb_count)
            self._store_signal(
                signal_type="board_composition",
                value=round(bb_ratio, 4),
                metadata=json.dumps({"ro": ro_count, "bb": bb_count, "total": ro_count + bb_count}),
                expires_at=expires,
            )
            signals_stored.append("board_composition")

        # Near-CX bookings → supply volatility
        if near_cx > 0:
            self._store_signal(
                signal_type="supply_volatility",
                value=min(1.0, near_cx / 30.0),  # Normalize: 30+ = max
                metadata=json.dumps({"near_cx_deadline": near_cx,
                                      "active_bookings": active_bookings}),
                expires_at=expires,
            )
            signals_stored.append("supply_volatility")

        # PriceOverride push success rate → execution quality
        po_pushed = po.get("pushed", 0) or 0
        po_pending = po.get("pending", 0) or 0
        if po_total > 0:
            self._store_signal(
                signal_type="price_execution_quality",
                value=round(po_pushed / po_total, 4) if po_total > 0 else 1.0,
                metadata=json.dumps({"pushed": po_pushed, "pending": po_pending,
                                      "failed": po_failed, "total": po_total}),
                expires_at=expires,
            )
            signals_stored.append("price_execution_quality")

        # Log to history
        self._log_history("monitor_ingest", "processed", alerts_forwarded, results)

        return {
            "ingested_at": now.isoformat(),
            "alerts_forwarded": len(alerts_forwarded),
            "adjustments_applied": len(adjustments_applied),
            "adjustments": adjustments_applied,
            "market_signals_stored": signals_stored,
        }

    # ── 3. Confidence adjustment queries ──────────────────────────────

    def get_active_adjustments(self, hotel_id: str | None = None) -> list[dict]:
        """Get active (non-expired) confidence adjustments.

        Args:
            hotel_id: Filter by hotel, or None for global + all hotels.
        """
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            now = datetime.utcnow().isoformat()

            if hotel_id:
                rows = conn.execute(
                    """SELECT * FROM confidence_adjustments
                       WHERE (hotel_id = ? OR hotel_id IS NULL)
                       AND expires_at > ?
                       ORDER BY timestamp DESC""",
                    (hotel_id, now),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM confidence_adjustments
                       WHERE expires_at > ?
                       ORDER BY timestamp DESC""",
                    (now,),
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.warning("Failed to get active adjustments: %s", e)
            return []

    def get_confidence_modifier(self, hotel_id: str | None = None) -> float:
        """Calculate the total confidence modifier for a hotel.

        Returns a value between -1.0 and 0.0 to add to prediction confidence.
        Adjustments stack but are capped at -0.50 (50% max reduction).
        """
        adjustments = self.get_active_adjustments(hotel_id)
        if not adjustments:
            return 0.0

        # Deduplicate: take worst adjustment per type
        by_type: dict[str, float] = {}
        for adj in adjustments:
            adj_type = adj.get("adjustment_type", "")
            value = adj.get("adjustment_value", 0.0)
            if adj_type not in by_type or value < by_type[adj_type]:
                by_type[adj_type] = value

        total = sum(by_type.values())
        return max(-0.50, total)  # Cap at 50% reduction

    # ── 4. Unified health status ──────────────────────────────────────

    def get_unified_status(self) -> dict:
        """Combined health status from prediction engine + monitor history.

        Returns a merged view suitable for a unified dashboard.
        """
        # Recent monitor history
        history = self._get_recent_history(hours=24)

        # Active adjustments
        adjustments = self.get_active_adjustments()

        # Trend: is the system improving or degrading?
        recent_alerts = [h for h in history if h.get("status") != "healthy"]
        trend = "stable"
        if len(recent_alerts) > 3:
            trend = "degrading"
        elif len(history) > 0 and len(recent_alerts) == 0:
            trend = "improving"

        return {
            "checked_at": datetime.utcnow().isoformat(),
            "trend": trend,
            "active_adjustments": len(adjustments),
            "confidence_modifier_global": self.get_confidence_modifier(),
            "history_24h": {
                "total_checks": len(history),
                "healthy": sum(1 for h in history if h["status"] == "healthy"),
                "degraded": sum(1 for h in history if h["status"] != "healthy"),
                "alerts_total": sum(
                    len(json.loads(h.get("alerts_json", "[]")))
                    for h in history
                ),
            },
            "adjustments": adjustments,
            "market_signals": self.get_market_signals(),
        }

    # ── 5. Market signals (enrichment data for prediction) ────────────

    def get_market_signals(self) -> dict[str, dict]:
        """Get latest non-expired market signals from monitor data.

        Returns dict keyed by signal_type with value, metadata, and timestamp.
        These signals can be consumed by the prediction engine enrichments.
        """
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            now = datetime.utcnow().isoformat()

            # Get the latest signal per type that hasn't expired
            rows = conn.execute(
                """SELECT signal_type, signal_value, metadata, timestamp
                   FROM market_signals
                   WHERE expires_at > ?
                   AND id IN (
                       SELECT MAX(id) FROM market_signals
                       WHERE expires_at > ?
                       GROUP BY signal_type
                   )""",
                (now, now),
            ).fetchall()
            conn.close()

            signals = {}
            for r in rows:
                meta = {}
                try:
                    meta = json.loads(r["metadata"]) if r["metadata"] else {}
                except (json.JSONDecodeError, TypeError):
                    pass
                signals[r["signal_type"]] = {
                    "value": r["signal_value"],
                    "metadata": meta,
                    "updated_at": r["timestamp"],
                }
            return signals
        except sqlite3.Error as e:
            logger.warning("Failed to get market signals: %s", e)
            return {}

    def get_signal(self, signal_type: str) -> float | None:
        """Get a single market signal value. Returns None if not available."""
        signals = self.get_market_signals()
        sig = signals.get(signal_type)
        return sig["value"] if sig else None

    # ── Internal helpers ──────────────────────────────────────────────

    def _store_signal(
        self,
        signal_type: str,
        value: float,
        metadata: str = "",
        hotel_id: str | None = None,
        expires_at: str = "",
    ) -> None:
        """Store a market signal for the prediction engine."""
        try:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO market_signals
                   (timestamp, hotel_id, signal_type, signal_value, metadata, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.utcnow().isoformat(), hotel_id, signal_type,
                 value, metadata, expires_at),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Failed to store market signal %s: %s", signal_type, e)

    def _dispatch_alert(self, rule_id: str, severity: str, message: str) -> dict:
        """Dispatch through the alert dispatcher, with fallback to logging."""
        try:
            from src.services.alert_dispatcher import AlertDispatcher
            dispatcher = AlertDispatcher()
            result = dispatcher.dispatch(
                rule_id=rule_id,
                severity=severity,
                message=message,
                rooms=[],
            )
            return {"rule_id": rule_id, "severity": severity, **result}
        except (ImportError, Exception) as e:
            logger.error("Alert dispatch failed for %s: %s", rule_id, e)
            logger.warning("ALERT [%s] %s: %s", severity, rule_id, message)
            return {"rule_id": rule_id, "severity": severity, "dispatched": False, "error": str(e)}

    def _apply_adjustment(
        self,
        hotel_id: str | None,
        adj_type: str,
        value: float,
        reason: str,
        expires_at: str,
    ) -> dict:
        """Record a confidence adjustment."""
        try:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO confidence_adjustments
                   (timestamp, hotel_id, adjustment_type, adjustment_value, reason, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.utcnow().isoformat(), hotel_id, adj_type, value, reason, expires_at),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Failed to apply adjustment: %s", e)

        return {
            "hotel_id": hotel_id,
            "type": adj_type,
            "value": value,
            "reason": reason,
            "expires_at": expires_at,
        }

    def _log_history(
        self,
        source: str,
        status: str,
        alerts: list | None = None,
        results: dict | None = None,
    ) -> None:
        """Log a monitor check to history."""
        try:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO monitor_history
                   (timestamp, source, status, alerts_json, results_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    datetime.utcnow().isoformat(),
                    source,
                    status,
                    json.dumps(alerts or [], default=str),
                    json.dumps(results, default=str) if results else None,
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Failed to log monitor history: %s", e)

    def _get_recent_history(self, hours: int = 24) -> list[dict]:
        """Get monitor history for the last N hours."""
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT * FROM monitor_history
                   WHERE timestamp > ?
                   ORDER BY timestamp DESC LIMIT 100""",
                (cutoff,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []
