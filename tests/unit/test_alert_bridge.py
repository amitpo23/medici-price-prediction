"""Unit tests for alert_bridge module."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.analytics.alert_bridge import (
    dispatch_streaming_alerts,
    get_recent_dispatch_log,
    get_dispatch_stats,
)


@pytest.fixture
def sample_analysis():
    """Fixture: basic analysis dict."""
    return {
        "predictions": {
            "1": {
                "hotel_id": 100,
                "hotel_name": "Hotel A",
                "category": "Standard",
                "current_price": 200.0,
                "predicted_checkin_price": 210.0,
                "option_signal": "CALL",
                "option_confidence": 0.75,
                "forward_curve": [
                    {
                        "lower_bound": 190.0,
                        "upper_bound": 220.0,
                    }
                ],
                "regime": {"regime": "NORMAL"},
                "momentum": {"signal": "STABLE"},
            },
            "2": {
                "hotel_id": 101,
                "hotel_name": "Hotel B",
                "category": "Deluxe",
                "current_price": 300.0,
                "predicted_checkin_price": 285.0,
                "option_signal": "PUT",
                "option_confidence": 0.65,
                "forward_curve": [
                    {
                        "lower_bound": 280.0,
                        "upper_bound": 320.0,
                    }
                ],
                "regime": {"regime": "NORMAL"},
                "momentum": {"signal": "STABLE"},
            },
        },
        "data_quality": {
            "source_1": {
                "freshness_hours": 1.0,
                "reliability_score": 0.95,
            }
        },
    }


@pytest.fixture
def previous_analysis():
    """Fixture: previous analysis dict (for flip detection)."""
    return {
        "predictions": {
            "1": {
                "hotel_id": 100,
                "hotel_name": "Hotel A",
                "category": "Standard",
                "current_price": 195.0,
                "option_signal": "PUT",
                "momentum": {"signal": "STABLE"},
            }
        },
        "data_quality": {},
    }


class TestDispatchStreamingAlerts:
    """Test dispatch_streaming_alerts function."""

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    @patch("src.analytics.streaming_alerts.generate_alerts")
    def test_dispatch_success(self, mock_generate, mock_dispatcher_class, sample_analysis):
        """Test successful alert dispatch."""
        from src.analytics.streaming_alerts import StreamingAlert, AlertSummary

        mock_alert = StreamingAlert(
            alert_id="alert_1",
            alert_type="BAND_BREACH",
            severity="critical",
            detail_id=1,
            hotel_id=100,
            hotel_name="Hotel A",
            category="Standard",
            message="Price breach detected",
            data={"price": 200.0},
            created_at=datetime.utcnow().isoformat() + "Z",
            suppressed=False,
        )

        mock_summary = AlertSummary(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_generated=1,
            total_suppressed=0,
            total_new=1,
            by_type={"BAND_BREACH": 1},
            by_severity={"critical": 1},
            alerts=[mock_alert],
        )

        mock_generate.return_value = mock_summary

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = {
            "dispatched": True,
            "channels": {"log": "sent"},
        }
        mock_dispatcher_class.return_value = mock_dispatcher

        result = dispatch_streaming_alerts(sample_analysis)

        assert result["total_alerts"] == 1
        assert result["dispatched"] == 1
        assert result["suppressed"] == 0
        assert "BAND_BREACH" in result["by_type"]
        assert mock_dispatcher.dispatch.called

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    @patch("src.analytics.streaming_alerts.generate_alerts")
    def test_dispatch_with_multiple_alerts(self, mock_generate, mock_dispatcher_class, sample_analysis):
        """Test dispatch with multiple alerts."""
        from src.analytics.streaming_alerts import StreamingAlert, AlertSummary

        alerts = [
            StreamingAlert(
                alert_id="alert_1",
                alert_type="BAND_BREACH",
                severity="critical",
                detail_id=1,
                hotel_id=100,
                hotel_name="Hotel A",
                category="Standard",
                message="Price too high",
                data={},
                created_at=datetime.utcnow().isoformat() + "Z",
                suppressed=False,
            ),
            StreamingAlert(
                alert_id="alert_2",
                alert_type="SIGNAL_FLIP",
                severity="critical",
                detail_id=1,
                hotel_id=100,
                hotel_name="Hotel A",
                category="Standard",
                message="Signal flipped",
                data={},
                created_at=datetime.utcnow().isoformat() + "Z",
                suppressed=False,
            ),
        ]

        mock_summary = AlertSummary(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_generated=2,
            total_suppressed=0,
            total_new=2,
            by_type={"BAND_BREACH": 1, "SIGNAL_FLIP": 1},
            by_severity={"critical": 2},
            alerts=alerts,
        )

        mock_generate.return_value = mock_summary

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = {
            "dispatched": True,
            "channels": {"log": "sent"},
        }
        mock_dispatcher_class.return_value = mock_dispatcher

        result = dispatch_streaming_alerts(sample_analysis)

        assert result["total_alerts"] == 2
        assert result["dispatched"] == 2
        assert result["by_type"]["BAND_BREACH"] == 1
        assert result["by_type"]["SIGNAL_FLIP"] == 1
        assert mock_dispatcher.dispatch.call_count == 2

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    @patch("src.analytics.streaming_alerts.generate_alerts")
    def test_dispatch_suppressed_alerts(self, mock_generate, mock_dispatcher_class, sample_analysis):
        """Test handling of suppressed alerts (deduped)."""
        from src.analytics.streaming_alerts import StreamingAlert, AlertSummary

        alerts = [
            StreamingAlert(
                alert_id="alert_1",
                alert_type="BAND_BREACH",
                severity="critical",
                detail_id=1,
                hotel_id=100,
                hotel_name="Hotel A",
                category="Standard",
                message="Price breach",
                data={},
                created_at=datetime.utcnow().isoformat() + "Z",
                suppressed=True,
            ),
            StreamingAlert(
                alert_id="alert_2",
                alert_type="SIGNAL_FLIP",
                severity="critical",
                detail_id=1,
                hotel_id=100,
                hotel_name="Hotel A",
                category="Standard",
                message="Signal flipped",
                data={},
                created_at=datetime.utcnow().isoformat() + "Z",
                suppressed=False,
            ),
        ]

        mock_summary = AlertSummary(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_generated=2,
            total_suppressed=1,
            total_new=1,
            by_type={"BAND_BREACH": 1, "SIGNAL_FLIP": 1},
            by_severity={"critical": 2},
            alerts=alerts,
        )

        mock_generate.return_value = mock_summary

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = {
            "dispatched": True,
            "channels": {"log": "sent"},
        }
        mock_dispatcher_class.return_value = mock_dispatcher

        result = dispatch_streaming_alerts(sample_analysis)

        assert result["total_alerts"] == 2
        assert result["suppressed"] == 1
        assert result["dispatched"] == 1
        assert mock_dispatcher.dispatch.call_count == 1

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    @patch("src.analytics.streaming_alerts.generate_alerts")
    def test_dispatch_with_previous_analysis(
        self, mock_generate, mock_dispatcher_class, sample_analysis, previous_analysis
    ):
        """Test dispatch with previous analysis for flip detection."""
        from src.analytics.streaming_alerts import AlertSummary

        mock_summary = AlertSummary(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_generated=0,
            total_suppressed=0,
            total_new=0,
            by_type={},
            by_severity={},
            alerts=[],
        )

        mock_generate.return_value = mock_summary
        mock_dispatcher_class.return_value = MagicMock()

        result = dispatch_streaming_alerts(sample_analysis, previous_analysis)

        mock_generate.assert_called_once()
        args, kwargs = mock_generate.call_args
        assert args[0] == sample_analysis
        assert args[1] == previous_analysis

    def test_dispatch_missing_module(self, sample_analysis):
        """Test error handling for missing imports."""
        with patch("src.analytics.alert_bridge.dispatch_streaming_alerts") as mock_dispatch:
            mock_dispatch.side_effect = ImportError("streaming_alerts not found")

        # Call via try-catch since real function can handle it
        with patch("src.analytics.streaming_alerts.generate_alerts", side_effect=ImportError("test")):
            result = dispatch_streaming_alerts(sample_analysis)
            assert result["error"] is not None

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    @patch("src.analytics.streaming_alerts.generate_alerts")
    def test_rule_id_generation(self, mock_generate, mock_dispatcher_class, sample_analysis):
        """Test that rule_id is properly constructed."""
        from src.analytics.streaming_alerts import StreamingAlert, AlertSummary

        mock_alert = StreamingAlert(
            alert_id="test_id",
            alert_type="BAND_BREACH",
            severity="warning",
            detail_id=123,
            hotel_id=100,
            hotel_name="Hotel A",
            category="Standard",
            message="Test",
            data={},
            created_at=datetime.utcnow().isoformat() + "Z",
            suppressed=False,
        )

        mock_summary = AlertSummary(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_generated=1,
            total_suppressed=0,
            total_new=1,
            by_type={"BAND_BREACH": 1},
            by_severity={"warning": 1},
            alerts=[mock_alert],
        )

        mock_generate.return_value = mock_summary

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = {"dispatched": True, "channels": {}}
        mock_dispatcher_class.return_value = mock_dispatcher

        dispatch_streaming_alerts(sample_analysis)

        call_args = mock_dispatcher.dispatch.call_args
        assert call_args.kwargs["rule_id"] == "streaming_BAND_BREACH_123"

    @patch("src.services.alert_dispatcher.AlertDispatcher")
    @patch("src.analytics.streaming_alerts.generate_alerts")
    def test_room_data_extraction(self, mock_generate, mock_dispatcher_class, sample_analysis):
        """Test that room data is properly extracted and passed to dispatcher."""
        from src.analytics.streaming_alerts import StreamingAlert, AlertSummary

        mock_alert = StreamingAlert(
            alert_id="test_id",
            alert_type="SIGNAL_FLIP",
            severity="critical",
            detail_id=1,
            hotel_id=100,
            hotel_name="Hotel A",
            category="Standard",
            message="Test flip",
            data={},
            created_at=datetime.utcnow().isoformat() + "Z",
            suppressed=False,
        )

        mock_summary = AlertSummary(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_generated=1,
            total_suppressed=0,
            total_new=1,
            by_type={"SIGNAL_FLIP": 1},
            by_severity={"critical": 1},
            alerts=[mock_alert],
        )

        mock_generate.return_value = mock_summary

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = {"dispatched": True, "channels": {}}
        mock_dispatcher_class.return_value = mock_dispatcher

        dispatch_streaming_alerts(sample_analysis)

        call_args = mock_dispatcher.dispatch.call_args
        rooms = call_args.kwargs["rooms"]
        assert len(rooms) == 1
        assert rooms[0]["detail_id"] == 1
        assert rooms[0]["hotel_id"] == 100
        assert rooms[0]["signal"] == "CALL"
        assert rooms[0]["confidence"] == 0.75


class TestGetRecentDispatchLog:
    """Test get_recent_dispatch_log function."""

    @patch("src.services.alert_dispatcher.get_alert_history")
    def test_get_dispatch_log_success(self, mock_get_history):
        """Test successful dispatch log query."""
        mock_get_history.return_value = [
            {
                "rule_id": "streaming_BAND_BREACH_1",
                "severity": "critical",
                "message": "Price too high",
                "timestamp": "2025-03-20T10:00:00",
            },
            {
                "rule_id": "streaming_SIGNAL_FLIP_2",
                "severity": "critical",
                "message": "Signal changed",
                "timestamp": "2025-03-20T09:00:00",
            },
        ]

        result = get_recent_dispatch_log(hours_back=24)

        assert len(result) == 2
        assert result[0]["rule_id"] == "streaming_BAND_BREACH_1"

    @patch("src.services.alert_dispatcher.get_alert_history")
    def test_filter_by_alert_type(self, mock_get_history):
        """Test filtering by alert type."""
        mock_get_history.return_value = [
            {"rule_id": "streaming_BAND_BREACH_1", "severity": "critical"},
            {"rule_id": "streaming_SIGNAL_FLIP_2", "severity": "critical"},
            {"rule_id": "streaming_BAND_BREACH_3", "severity": "warning"},
        ]

        result = get_recent_dispatch_log(alert_type="BAND_BREACH")

        assert len(result) == 2
        assert all("BAND_BREACH" in r["rule_id"] for r in result)

    @patch("src.services.alert_dispatcher.get_alert_history")
    def test_filter_by_severity(self, mock_get_history):
        """Test filtering by severity."""
        mock_get_history.return_value = [
            {"rule_id": "streaming_BAND_BREACH_1", "severity": "critical"},
            {"rule_id": "streaming_SIGNAL_FLIP_2", "severity": "critical"},
            {"rule_id": "streaming_BAND_BREACH_3", "severity": "warning"},
        ]

        result = get_recent_dispatch_log(severity="critical")

        assert len(result) == 2
        assert all(r["severity"] == "critical" for r in result)

    @patch("src.services.alert_dispatcher.get_alert_history")
    def test_dispatch_log_error(self, mock_get_history):
        """Test error handling in dispatch log query."""
        mock_get_history.side_effect = Exception("Database error")

        result = get_recent_dispatch_log()

        assert result == []


class TestGetDispatchStats:
    """Test get_dispatch_stats function."""

    @patch("src.services.alert_dispatcher.get_alert_stats")
    def test_get_stats_success(self, mock_get_stats):
        """Test successful stats query."""
        mock_get_stats.return_value = {
            "total_alerts": 150,
            "last_24h": 25,
            "top_rules": [
                {"rule_id": "streaming_BAND_BREACH_1", "count": 10},
                {"rule_id": "streaming_SIGNAL_FLIP_2", "count": 8},
            ],
            "by_channel": {
                "log": 25,
                "webhook": 20,
                "telegram": 10,
            },
        }

        result = get_dispatch_stats()

        assert result["total_alerts"] == 150
        assert result["last_24h"] == 25
        assert len(result["top_rules"]) == 2
        assert result["by_channel"]["log"] == 25

    @patch("src.services.alert_dispatcher.get_alert_stats")
    def test_get_stats_error(self, mock_get_stats):
        """Test error handling in stats query."""
        mock_get_stats.side_effect = Exception("Stats query failed")

        result = get_dispatch_stats()

        assert result["total_alerts"] == 0
        assert "error" in result
