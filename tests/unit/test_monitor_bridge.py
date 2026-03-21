"""Tests for the monitor bridge module (src.services.monitor_bridge)."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


def _isolate_dbs(test_case):
    """Helper: redirect all SQLite DBs to temp directory."""
    test_case._tmpdir = tempfile.mkdtemp()
    tmp = Path(test_case._tmpdir)

    import src.services.monitor_bridge as smb
    import src.services.alert_dispatcher as ad

    test_case._orig_monitor_db = smb.MONITOR_DB_PATH
    test_case._orig_alert_db = ad.ALERT_DB_PATH

    smb.MONITOR_DB_PATH = tmp / "monitor_bridge.db"
    ad.ALERT_DB_PATH = tmp / "alerts.db"


def _restore_dbs(test_case):
    import src.services.monitor_bridge as smb
    import src.services.alert_dispatcher as ad
    smb.MONITOR_DB_PATH = test_case._orig_monitor_db
    ad.ALERT_DB_PATH = test_case._orig_alert_db
    import shutil
    shutil.rmtree(test_case._tmpdir, ignore_errors=True)


def _sample_monitor_output(webjob_minutes=5, zenith_ok=True, gaps=None,
                            failed_orders=0, miss_rate=0, cancel_errors=0):
    """Create sample SystemMonitor output dict."""
    return {
        "results": {
            "webjob": {
                "last_log": {"order_id": 1234, "time": "2026-03-20 12:00",
                             "minutes_ago": webjob_minutes},
                "pending_orders": 0,
                "failed_orders": failed_orders,
                "active_orders": 100,
                "estimated_cycle_hours": 5.0,
            },
            "mapping": {
                "active_hotels": 10,
                "miss_rate_last_hour": miss_rate,
                "order_detail_gaps": gaps or [],
            },
            "zenith": {
                "status": "OK" if zenith_ok else "UNREACHABLE",
                "latency_ms": 500 if zenith_ok else 0,
                "error": "" if zenith_ok else "Connection refused",
            },
            "cancellation": {
                "cancel_errors_24h": cancel_errors,
                "active_bookings": 50,
            },
        },
        "alerts": [],
    }


class TestMonitorBridgeInit(unittest.TestCase):
    """Test MonitorBridge initialization and DB setup."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_import(self):
        from src.services.monitor_bridge import MonitorBridge
        self.assertIsNotNone(MonitorBridge)

    def test_init_creates_db(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        self.assertIsNotNone(bridge)
        # DB file should exist
        import src.services.monitor_bridge as smb
        self.assertTrue(os.path.exists(str(smb.MONITOR_DB_PATH)))


class TestMonitorBridgeIngest(unittest.TestCase):
    """Test monitor result ingestion and confidence adjustments."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_ingest_healthy_report(self):
        """Healthy report produces no adjustments."""
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_monitor_results(_sample_monitor_output())
        self.assertEqual(result["adjustments_applied"], 0)
        self.assertEqual(result["alerts_forwarded"], 0)

    def test_ingest_stale_webjob(self):
        """Stale WebJob creates webjob_stale adjustment."""
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        output = _sample_monitor_output(webjob_minutes=120)
        output["alerts"] = [
            {"severity": "CRITICAL", "component": "WebJob",
             "message": "No activity for 120 minutes"}
        ]
        result = bridge.ingest_monitor_results(output)
        adj_types = [a["type"] for a in result["adjustments"]]
        self.assertIn("webjob_stale", adj_types)
        self.assertEqual(result["alerts_forwarded"], 1)

    def test_ingest_zenith_unreachable(self):
        """Unreachable Zenith creates zenith_unreachable adjustment."""
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_monitor_results(
            _sample_monitor_output(zenith_ok=False)
        )
        adj_types = [a["type"] for a in result["adjustments"]]
        self.assertIn("zenith_unreachable", adj_types)

    def test_ingest_with_gaps(self):
        """ORDER≠DETAIL gaps create per-hotel adjustments."""
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        gaps = [
            {"hotel_id": 5093, "hotel": "Test", "gap": 3, "total": 50},
            {"hotel_id": 5094, "hotel": "Other", "gap": 1, "total": 30},
        ]
        result = bridge.ingest_monitor_results(
            _sample_monitor_output(gaps=gaps)
        )
        gap_adjs = [a for a in result["adjustments"]
                    if a["type"] == "order_detail_gaps"]
        self.assertEqual(len(gap_adjs), 2)
        hotel_ids = {a["hotel_id"] for a in gap_adjs}
        self.assertEqual(hotel_ids, {"5093", "5094"})

    def test_ingest_failed_orders(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_monitor_results(
            _sample_monitor_output(failed_orders=5)
        )
        adj_types = [a["type"] for a in result["adjustments"]]
        self.assertIn("failed_orders", adj_types)

    def test_ingest_high_miss_rate(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_monitor_results(
            _sample_monitor_output(miss_rate=20)
        )
        adj_types = [a["type"] for a in result["adjustments"]]
        self.assertIn("mapping_miss_high_rate", adj_types)

    def test_ingest_cancel_errors(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_monitor_results(
            _sample_monitor_output(cancel_errors=3)
        )
        adj_types = [a["type"] for a in result["adjustments"]]
        self.assertIn("cancel_errors", adj_types)


class TestConfidenceModifier(unittest.TestCase):
    """Test confidence modifier calculation."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_no_adjustments_returns_zero(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        self.assertEqual(bridge.get_confidence_modifier(), 0.0)

    def test_modifier_negative_after_issues(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        bridge.ingest_monitor_results(
            _sample_monitor_output(webjob_minutes=60, failed_orders=3)
        )
        modifier = bridge.get_confidence_modifier()
        self.assertLess(modifier, 0)

    def test_modifier_capped_at_minus_50(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        heavy = _sample_monitor_output(
            webjob_minutes=120, failed_orders=10,
            zenith_ok=False, miss_rate=50, cancel_errors=20,
        )
        bridge.ingest_monitor_results(heavy)
        self.assertEqual(bridge.get_confidence_modifier(), -0.50)

    def test_hotel_specific_modifier_worse(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        output = _sample_monitor_output(
            webjob_minutes=60,
            gaps=[{"hotel_id": 5093, "hotel": "Test", "gap": 5, "total": 50}],
        )
        bridge.ingest_monitor_results(output)
        mod_5093 = bridge.get_confidence_modifier("5093")
        mod_global = bridge.get_confidence_modifier()
        self.assertLessEqual(mod_5093, mod_global)

    def test_expired_adjustments_ignored(self):
        from src.services.monitor_bridge import MonitorBridge, _get_conn
        bridge = MonitorBridge()
        past = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        conn = _get_conn()
        conn.execute(
            """INSERT INTO confidence_adjustments
               (timestamp, hotel_id, adjustment_type, adjustment_value, reason, expires_at)
               VALUES (?, NULL, 'test', -0.2, 'expired', ?)""",
            (past, past),
        )
        conn.commit()
        conn.close()
        self.assertEqual(bridge.get_confidence_modifier(), 0.0)


class TestUnifiedStatus(unittest.TestCase):
    """Test unified health status."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_status_structure(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        status = bridge.get_unified_status()
        self.assertIn("checked_at", status)
        self.assertIn("trend", status)
        self.assertIn("active_adjustments", status)
        self.assertIn("history_24h", status)

    def test_trend_stable_with_no_history(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        status = bridge.get_unified_status()
        self.assertEqual(status["trend"], "stable")


class TestHistoryLogging(unittest.TestCase):
    """Test that operations are logged to history."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_ingest_logs_to_history(self):
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        bridge.ingest_monitor_results(_sample_monitor_output(webjob_minutes=60))
        history = bridge._get_recent_history(hours=1)
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]["source"], "monitor_ingest")


class TestAlertEscalation(unittest.TestCase):
    """Test alert escalation logic."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import src.services.alert_dispatcher as ad
        self._orig_db_path = ad.ALERT_DB_PATH
        ad.ALERT_DB_PATH = os.path.join(self._tmpdir, "alerts.db")

    def tearDown(self):
        import src.services.alert_dispatcher as ad
        ad.ALERT_DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_escalation_function_exists(self):
        from src.services.alert_dispatcher import _check_escalation
        result = _check_escalation("nonexistent_rule")
        self.assertIsNone(result)

    def test_dispatcher_with_escalation(self):
        from src.services.alert_dispatcher import AlertDispatcher
        dispatcher = AlertDispatcher()
        result = dispatcher.dispatch(
            rule_id="test_escalation_check",
            severity="info",
            message="Test alert",
        )
        self.assertIn("dispatched", result)

    def test_repeated_alerts_escalate(self):
        """Alert fired multiple times within window should escalate."""
        from src.services.alert_dispatcher import AlertDispatcher, _check_escalation, ESCALATION_THRESHOLD
        dispatcher = AlertDispatcher()

        # Fire alerts to build up count
        for i in range(ESCALATION_THRESHOLD + 1):
            from src.services.alert_dispatcher import _log_alert
            _log_alert(
                rule_id="test_repeat_rule",
                channel="log",
                payload={"severity": "warning", "message": f"test {i}"},
                status="sent",
            )

        escalated = _check_escalation("test_repeat_rule")
        self.assertIsNotNone(escalated)


class TestDataQualityAlertIntegration(unittest.TestCase):
    """Test data quality → alert dispatcher connection."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import src.services.alert_dispatcher as ad
        import src.analytics.data_quality as dq
        self._orig_alert_db = ad.ALERT_DB_PATH
        self._orig_health_db = dq.DB_PATH
        ad.ALERT_DB_PATH = os.path.join(self._tmpdir, "alerts.db")
        dq.DB_PATH = os.path.join(self._tmpdir, "source_health.db")

    def tearDown(self):
        import src.services.alert_dispatcher as ad
        import src.analytics.data_quality as dq
        ad.ALERT_DB_PATH = self._orig_alert_db
        dq.DB_PATH = self._orig_health_db
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_dispatch_method_exists(self):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        self.assertTrue(hasattr(scorer, "_dispatch_quality_alerts"))

    def test_dispatch_no_degraded(self):
        """No alerts dispatched when all sources are healthy."""
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        # Should not raise
        scorer._dispatch_quality_alerts([
            {"freshness_score": 0.9, "anomaly_flag": False, "name": "test"},
        ])

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    def test_dispatch_with_degraded(self, mock_dispatcher_cls):
        """Alert dispatched when source freshness is critically low."""
        from src.analytics.data_quality import DataQualityScorer
        mock_instance = MagicMock()
        mock_dispatcher_cls.return_value = mock_instance
        mock_instance.dispatch.return_value = {"dispatched": True}

        scorer = DataQualityScorer()
        scorer._dispatch_quality_alerts([
            {"freshness_score": 0.1, "anomaly_flag": False, "name": "stale_source", "source_id": "test"},
        ])

        mock_instance.dispatch.assert_called_once()
        call_kwargs = mock_instance.dispatch.call_args
        self.assertIn("degraded", call_kwargs.kwargs.get("rule_id", "") or call_kwargs[1].get("rule_id", ""))


if __name__ == "__main__":
    unittest.main()
