"""Tests for the real-time alert dispatcher."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def temp_alert_db(monkeypatch, tmp_path):
    """Use a temporary database for each test."""
    db_path = tmp_path / "test_alerts.db"
    import src.services.alert_dispatcher as dispatcher
    monkeypatch.setattr(dispatcher, "ALERT_DB_PATH", db_path)
    dispatcher._init_alert_db()
    return db_path


# ── AlertChannel implementations ────────────────────────────────────


class TestLogChannel:
    """Test LogChannel always succeeds."""

    def test_send_returns_true(self):
        from src.services.alert_dispatcher import LogChannel
        channel = LogChannel()
        result = channel.send({"rule_id": "test", "severity": "info", "message": "test", "rooms": []})
        assert result is True

    def test_send_with_rooms(self):
        from src.services.alert_dispatcher import LogChannel
        channel = LogChannel()
        result = channel.send({
            "rule_id": "surge",
            "severity": "high",
            "message": "5 rooms surging",
            "rooms": [{"room_id": 1}, {"room_id": 2}],
        })
        assert result is True


class TestWebhookChannel:
    """Test WebhookChannel without a URL configured."""

    def test_no_url_returns_false(self, monkeypatch):
        monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
        from src.services.alert_dispatcher import WebhookChannel
        channel = WebhookChannel(url="")
        result = channel.send({"rule_id": "test"})
        assert result is False


class TestTelegramChannel:
    """Test TelegramChannel without credentials."""

    def test_no_credentials_returns_false(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        from src.services.alert_dispatcher import TelegramChannel
        channel = TelegramChannel(token="", chat_id="")
        result = channel.send({"rule_id": "test", "rooms": []})
        assert result is False


# ── Alert DB (deduplication) ────────────────────────────────────────


class TestAlertDb:
    """Test alert database initialization and operations."""

    def test_table_created(self, temp_alert_db):
        conn = sqlite3.connect(str(temp_alert_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_log'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_index_created(self, temp_alert_db):
        conn = sqlite3.connect(str(temp_alert_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "idx_alert_rule_ts" in indexes

    def test_log_alert_inserts(self, temp_alert_db):
        from src.services.alert_dispatcher import _log_alert
        _log_alert("test_rule", "log", {"severity": "info", "message": "hello", "rooms": []})

        conn = sqlite3.connect(str(temp_alert_db))
        count = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0]
        conn.close()
        assert count == 1


class TestCooldown:
    """Test cooldown deduplication."""

    def test_no_cooldown_when_empty(self, temp_alert_db):
        from src.services.alert_dispatcher import _is_in_cooldown
        assert _is_in_cooldown("new_rule") is False

    def test_in_cooldown_after_alert(self, temp_alert_db):
        from src.services.alert_dispatcher import _log_alert, _is_in_cooldown
        _log_alert("surge_detected", "log", {"severity": "high", "message": "test", "rooms": []}, status="sent")
        assert _is_in_cooldown("surge_detected") is True

    def test_different_rule_not_in_cooldown(self, temp_alert_db):
        from src.services.alert_dispatcher import _log_alert, _is_in_cooldown
        _log_alert("surge_detected", "log", {"severity": "high", "message": "test", "rooms": []}, status="sent")
        assert _is_in_cooldown("drop_detected") is False


# ── AlertDispatcher ─────────────────────────────────────────────────


class TestAlertDispatcher:
    """Test the dispatcher class."""

    def test_creates_with_log_channel(self, monkeypatch):
        monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        from src.services.alert_dispatcher import AlertDispatcher
        dispatcher = AlertDispatcher()
        channel_names = [name for name, _ in dispatcher.channels]
        assert "log" in channel_names

    def test_dispatch_returns_sent(self, monkeypatch):
        monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from src.services.alert_dispatcher import AlertDispatcher
        dispatcher = AlertDispatcher()
        result = dispatcher.dispatch(
            rule_id="test_dispatch",
            severity="info",
            message="Testing dispatch",
            rooms=[{"room_id": 1, "signal": "CALL", "confidence": 0.8}],
        )
        assert result["dispatched"] is True
        assert "log" in result["channels"]
        assert result["channels"]["log"] == "sent"

    def test_dispatch_respects_cooldown(self, temp_alert_db, monkeypatch):
        monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from src.services.alert_dispatcher import AlertDispatcher
        dispatcher = AlertDispatcher()

        # First dispatch succeeds
        result1 = dispatcher.dispatch(rule_id="cooldown_test", severity="info", message="first")
        assert result1["dispatched"] is True

        # Second dispatch is suppressed by cooldown
        result2 = dispatcher.dispatch(rule_id="cooldown_test", severity="info", message="second")
        assert result2["dispatched"] is False
        assert result2["reason"] == "cooldown"

    def test_test_alert(self, monkeypatch):
        monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from src.services.alert_dispatcher import AlertDispatcher
        dispatcher = AlertDispatcher()
        result = dispatcher.test_alert()
        assert result["dispatched"] is True


# ── Query functions ─────────────────────────────────────────────────


class TestGetAlertHistory:
    """Test alert history query."""

    def test_empty_returns_empty_list(self, temp_alert_db):
        from src.services.alert_dispatcher import get_alert_history
        result = get_alert_history(days=7)
        assert result == []

    def test_returns_logged_alerts(self, temp_alert_db):
        from src.services.alert_dispatcher import _log_alert, get_alert_history
        _log_alert("rule_a", "log", {"severity": "info", "message": "hi", "rooms": []})
        _log_alert("rule_b", "webhook", {"severity": "high", "message": "surge", "rooms": [{"room_id": 1}]})

        result = get_alert_history(days=7)
        assert len(result) == 2
        assert result[0]["rule_id"] in ("rule_a", "rule_b")


class TestGetAlertStats:
    """Test alert stats query."""

    def test_empty_db(self, temp_alert_db):
        from src.services.alert_dispatcher import get_alert_stats
        result = get_alert_stats()
        assert result["total_alerts"] == 0

    def test_with_alerts(self, temp_alert_db):
        from src.services.alert_dispatcher import _log_alert, get_alert_stats
        _log_alert("rule_a", "log", {"severity": "info", "message": "x", "rooms": []})
        _log_alert("rule_a", "webhook", {"severity": "info", "message": "x", "rooms": []})
        _log_alert("rule_b", "log", {"severity": "high", "message": "y", "rooms": []})

        result = get_alert_stats()
        assert result["total_alerts"] == 3
        assert result["last_24h"] == 3
        assert len(result["top_rules"]) >= 1
        assert "log" in result["by_channel"]


# ── API endpoints (via TestClient) ──────────────────────────────────


class TestAlertApiEndpoints:
    """Test alert API endpoints through FastAPI TestClient."""

    def test_alerts_history_endpoint(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/salesoffice/alerts/history?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data

    def test_alerts_stats_endpoint(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/salesoffice/alerts/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_alerts" in data

    def test_alerts_test_endpoint(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/salesoffice/alerts/test")
        # May be 200 or 401 depending on API key config
        assert resp.status_code in (200, 401)
