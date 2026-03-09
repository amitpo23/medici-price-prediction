"""Real-time alert dispatcher with multi-channel support.

Dispatches alerts via configurable channels (Webhook, Telegram, Log)
with deduplication via SQLite cooldowns.

Usage:
    from src.services.alert_dispatcher import AlertDispatcher
    dispatcher = AlertDispatcher()
    dispatcher.dispatch(rule_id="surge_detected", severity="high",
                       message="5 rooms with >10% surge", rooms=[...])
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import requests

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

ALERT_DB_PATH = DATA_DIR / "alerts.db"
COOLDOWN_HOURS = int(os.environ.get("ALERT_COOLDOWN_HOURS", "4"))


# ---------------------------------------------------------------------------
# Channel interface
# ---------------------------------------------------------------------------


class AlertChannel(ABC):
    """Base class for alert channels."""

    @abstractmethod
    def send(self, payload: dict) -> bool:
        """Send an alert. Returns True on success."""


class LogChannel(AlertChannel):
    """Always-on channel that logs alerts to structured logging."""

    def send(self, payload: dict) -> bool:
        logger.info(
            "ALERT [%s] %s — %s (rooms: %d)",
            payload.get("severity", "info"),
            payload.get("rule_id", "unknown"),
            payload.get("message", ""),
            len(payload.get("rooms", [])),
        )
        return True


class WebhookChannel(AlertChannel):
    """HTTP POST webhook channel."""

    def __init__(self, url: str | None = None):
        self.url = url or os.environ.get("ALERT_WEBHOOK_URL", "")

    def send(self, payload: dict) -> bool:
        if not self.url:
            return False
        try:
            resp = requests.post(self.url, json=payload, timeout=10)
            return resp.status_code < 400
        except (requests.RequestException, OSError) as e:
            logger.warning("Webhook alert failed: %s", e)
            return False


class TelegramChannel(AlertChannel):
    """Telegram Bot API channel."""

    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, payload: dict) -> bool:
        if not self.token or not self.chat_id:
            return False

        rooms = payload.get("rooms", [])
        top_rooms = rooms[:3]
        top_lines = "\n".join(
            f"  {r.get('room_id', '?')} -> {r.get('signal', '?')} ({r.get('confidence', 0):.0%})"
            for r in top_rooms
        )

        text = (
            f"*Medici Alert: {payload.get('rule_id', 'unknown')}*\n"
            f"Severity: {payload.get('severity', 'info')}\n"
            f"Rooms: {len(rooms)} rooms triggered\n"
            f"Top signals:\n{top_lines}\n"
            f"[View Dashboard]({os.environ.get('DASHBOARD_URL', 'https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/dashboard')})"
        )

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            return resp.status_code == 200
        except (requests.RequestException, OSError) as e:
            logger.warning("Telegram alert failed: %s", e)
            return False


# ---------------------------------------------------------------------------
# Alert log (SQLite deduplication)
# ---------------------------------------------------------------------------


def _init_alert_db() -> None:
    """Create alert_log table if it doesn't exist."""
    conn = sqlite3.connect(str(ALERT_DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id     TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            channel     TEXT NOT NULL,
            severity    TEXT,
            message     TEXT,
            payload_json TEXT,
            rooms_json  TEXT,
            status      TEXT DEFAULT 'sent'
        );

        CREATE INDEX IF NOT EXISTS idx_alert_rule_ts
            ON alert_log(rule_id, timestamp);
    """)
    conn.close()


def _is_in_cooldown(rule_id: str) -> bool:
    """Check if a rule has fired within the cooldown period."""
    try:
        conn = sqlite3.connect(str(ALERT_DB_PATH))
        cutoff = (datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) FROM alert_log WHERE rule_id = ? AND timestamp > ? AND status = 'sent'",
            (rule_id, cutoff),
        ).fetchone()
        conn.close()
        return (row[0] or 0) > 0
    except sqlite3.Error:
        return False


def _log_alert(rule_id: str, channel: str, payload: dict, status: str = "sent") -> None:
    """Log an alert dispatch to the database."""
    try:
        conn = sqlite3.connect(str(ALERT_DB_PATH))
        conn.execute(
            """INSERT INTO alert_log (rule_id, timestamp, channel, severity, message, payload_json, rooms_json, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, datetime.utcnow().isoformat(), channel,
             payload.get("severity", ""),
             payload.get("message", ""),
             json.dumps(payload, default=str),
             json.dumps(payload.get("rooms", []), default=str),
             status),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.warning("Failed to log alert: %s", e)


# ---------------------------------------------------------------------------
# Query functions for API
# ---------------------------------------------------------------------------


def get_alert_history(days: int = 7) -> list[dict]:
    """Get alert log entries for the past N days."""
    try:
        _init_alert_db()
        conn = sqlite3.connect(str(ALERT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT * FROM alert_log WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 100",
            (cutoff,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("Failed to query alert history: %s", e, exc_info=True)
        return []


def get_alert_stats() -> dict:
    """Alert volume, top rules, channel distribution."""
    try:
        _init_alert_db()
        conn = sqlite3.connect(str(ALERT_DB_PATH))

        total = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0]
        last_24h = conn.execute(
            "SELECT COUNT(*) FROM alert_log WHERE timestamp > ?",
            ((datetime.utcnow() - timedelta(hours=24)).isoformat(),),
        ).fetchone()[0]

        # Top rules
        top_rules = conn.execute(
            "SELECT rule_id, COUNT(*) as cnt FROM alert_log GROUP BY rule_id ORDER BY cnt DESC LIMIT 5"
        ).fetchall()

        # By channel
        by_channel = conn.execute(
            "SELECT channel, COUNT(*) as cnt FROM alert_log GROUP BY channel"
        ).fetchall()

        conn.close()

        return {
            "total_alerts": total,
            "last_24h": last_24h,
            "top_rules": [{"rule_id": r[0], "count": r[1]} for r in top_rules],
            "by_channel": {r[0]: r[1] for r in by_channel},
        }
    except sqlite3.Error as e:
        logger.error("Failed to query alert stats: %s", e, exc_info=True)
        return {"total_alerts": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class AlertDispatcher:
    """Multi-channel alert dispatcher with deduplication."""

    def __init__(self):
        _init_alert_db()

        self.channels: list[tuple[str, AlertChannel]] = [
            ("log", LogChannel()),
        ]

        # Add webhook if configured
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
        if webhook_url:
            self.channels.append(("webhook", WebhookChannel(webhook_url)))

        # Add Telegram if configured
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            self.channels.append(("telegram", TelegramChannel(tg_token, tg_chat)))

    def dispatch(
        self,
        rule_id: str,
        severity: str = "info",
        message: str = "",
        rooms: list[dict] | None = None,
    ) -> dict:
        """Dispatch an alert to all configured channels.

        Respects cooldown — if the same rule_id fired within
        ALERT_COOLDOWN_HOURS, the alert is suppressed.

        Returns dict with dispatch results.
        """
        if _is_in_cooldown(rule_id):
            logger.debug("Alert %s suppressed (cooldown)", rule_id)
            return {"dispatched": False, "reason": "cooldown"}

        payload = {
            "rule_id": rule_id,
            "severity": severity,
            "message": message,
            "rooms": rooms or [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        results = {}
        for name, channel in self.channels:
            success = channel.send(payload)
            results[name] = "sent" if success else "failed"
            _log_alert(rule_id, name, payload, status="sent" if success else "failed")

        return {"dispatched": True, "channels": results}

    def test_alert(self) -> dict:
        """Fire a test alert to all channels."""
        return self.dispatch(
            rule_id="test_alert",
            severity="info",
            message="Test alert from Medici — all channels working",
            rooms=[{"room_id": 0, "signal": "TEST", "confidence": 1.0}],
        )
