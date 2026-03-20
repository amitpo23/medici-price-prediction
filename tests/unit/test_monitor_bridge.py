"""Tests for the monitor bridge module."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestMonitorBridgeInit(unittest.TestCase):
    """Test MonitorBridge initialization and DB setup."""

    def setUp(self):
        """Redirect monitor DB to temp directory."""
        self._tmpdir = tempfile.mkdtemp()
        import src.analytics.monitor_bridge as mb
        self._orig_db_path = mb.MONITOR_DB_PATH
        mb.MONITOR_DB_PATH = os.path.join(self._tmpdir, "monitor_bridge.db")

    def tearDown(self):
        import src.analytics.monitor_bridge as mb
        mb.MONITOR_DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_import(self):
        from src.analytics.monitor_bridge import MonitorBridge
        self.assertIsNotNone(MonitorBridge)

    def test_init_creates_db(self):
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        self.assertIsNotNone(bridge)

    def test_no_data_status(self):
        """Status returns no_data when no reports have been ingested."""
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        status = bridge.get_booking_engine_status()
        self.assertEqual(status.get("status"), "no_data")


class TestMonitorBridgeIngest(unittest.TestCase):
    """Test report ingestion logic."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import src.analytics.monitor_bridge as mb
        self._orig_db_path = mb.MONITOR_DB_PATH
        mb.MONITOR_DB_PATH = os.path.join(self._tmpdir, "monitor_bridge.db")

    def tearDown(self):
        import src.analytics.monitor_bridge as mb
        mb.MONITOR_DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _sample_report(self, webjob_minutes=5, zenith_ok=True, gaps=None):
        """Create a sample monitor report."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "results": {
                "webjob": {
                    "last_log": {
                        "order_id": 1234,
                        "time": "2026-03-20 12:00:00",
                        "minutes_ago": webjob_minutes,
                    },
                    "in_progress": [],
                    "pending_orders": 0,
                    "failed_orders": 0,
                    "active_orders": 100,
                    "estimated_cycle_hours": 5.0,
                },
                "tables": {
                    "SalesOffice.Orders": {"total": 100, "active": 100},
                },
                "mapping": {
                    "active_hotels": 10,
                    "hotels_with_bb": 8,
                    "open_misses": [],
                    "miss_rate_last_hour": 0,
                    "order_detail_gaps": gaps or [],
                },
                "zenith": {
                    "status": "OK" if zenith_ok else "UNREACHABLE",
                    "latency_ms": 500 if zenith_ok else 0,
                    "http_status": 200 if zenith_ok else 0,
                },
                "cancellation": {
                    "bookings_near_cx_deadline": 0,
                    "cancellations_24h": 1,
                    "cancel_errors_24h": 0,
                    "active_bookings": 50,
                },
            },
            "alerts": [],
        }

    def test_ingest_healthy_report(self):
        """Healthy report produces green status."""
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self._sample_report(), f)
            path = f.name

        try:
            result = bridge.ingest_report(path)
            self.assertIn("actions", result)
            self.assertIn("snapshot_stored", result["actions"])
            status = result.get("booking_engine_status", {})
            self.assertEqual(status.get("status"), "green")
        finally:
            os.unlink(path)

    def test_ingest_stale_webjob(self):
        """Stale WebJob produces webjob_stale action."""
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()

        report = self._sample_report(webjob_minutes=120)
        report["alerts"] = [
            {"severity": "CRITICAL", "component": "WebJob",
             "message": "No activity for 120 minutes"}
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(report, f)
            path = f.name

        try:
            result = bridge.ingest_report(path)
            actions = result.get("actions", [])
            self.assertTrue(any("webjob_stale" in a for a in actions))
        finally:
            os.unlink(path)

    def test_ingest_zenith_unreachable(self):
        """Unreachable Zenith produces zenith_unreachable action."""
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()

        report = self._sample_report(zenith_ok=False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(report, f)
            path = f.name

        try:
            result = bridge.ingest_report(path)
            actions = result.get("actions", [])
            self.assertTrue(any("zenith" in a for a in actions))
        finally:
            os.unlink(path)

    def test_ingest_with_gaps(self):
        """ORDER≠DETAIL gaps produce mapping action."""
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()

        gaps = [
            {"hotel": "Test Hotel", "hotel_id": 999, "gap": 10, "total": 50},
        ]
        report = self._sample_report(gaps=gaps)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(report, f)
            path = f.name

        try:
            result = bridge.ingest_report(path)
            actions = result.get("actions", [])
            self.assertTrue(any("mapping" in a for a in actions))
        finally:
            os.unlink(path)

    def test_ingest_nonexistent_file(self):
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        result = bridge.ingest_report("/nonexistent/path.json")
        self.assertEqual(result.get("error"), "report_not_found")

    def test_ingest_invalid_json(self):
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            path = f.name

        try:
            result = bridge.ingest_report(path)
            self.assertEqual(result.get("error"), "parse_failed")
        finally:
            os.unlink(path)


class TestMonitorBridgeTrend(unittest.TestCase):
    """Test trend and history queries."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import src.analytics.monitor_bridge as mb
        self._orig_db_path = mb.MONITOR_DB_PATH
        mb.MONITOR_DB_PATH = os.path.join(self._tmpdir, "monitor_bridge.db")

    def tearDown(self):
        import src.analytics.monitor_bridge as mb
        mb.MONITOR_DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_get_trend_empty(self):
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        trend = bridge.get_trend(hours=1)
        self.assertIsInstance(trend, list)

    def test_get_degraded_hotels(self):
        from src.analytics.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        degraded = bridge.get_degraded_hotels()
        self.assertIsInstance(degraded, list)


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
