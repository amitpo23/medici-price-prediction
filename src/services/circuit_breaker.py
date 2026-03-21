"""Circuit breaker for data source collectors.

Prevents repeated calls to a failing data source. After N consecutive
failures, the circuit "opens" and all subsequent calls return immediately
with an error until the cooldown period expires, at which point a single
"probe" call is allowed through.

States:
    CLOSED  — normal operation, calls go through
    OPEN    — source has failed N times, calls blocked
    HALF_OPEN — cooldown expired, one probe call allowed

Usage:
    from src.services.circuit_breaker import circuit_breaker

    # Before calling a data source
    if not circuit_breaker.allow("salesoffice"):
        logger.warning("salesoffice is circuit-broken, skipping")
        return fallback_data

    try:
        data = collector.collect()
        circuit_breaker.record_success("salesoffice")
    except Exception:
        circuit_breaker.record_failure("salesoffice")
        raise
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from enum import Enum

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

CB_DB_PATH = DATA_DIR / "circuit_breaker.db"

# Configuration
FAILURE_THRESHOLD = int(__import__("os").environ.get("CB_FAILURE_THRESHOLD", "3"))
COOLDOWN_SECONDS = int(__import__("os").environ.get("CB_COOLDOWN_SECONDS", "300"))  # 5 min


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CB_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_cb_db() -> None:
    """Create circuit breaker tables."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS circuit_state (
            source_id       TEXT PRIMARY KEY,
            state           TEXT NOT NULL DEFAULT 'CLOSED',
            failure_count   INTEGER DEFAULT 0,
            last_failure_at TEXT,
            last_success_at TEXT,
            opened_at       TEXT,
            last_error      TEXT
        );

        CREATE TABLE IF NOT EXISTS circuit_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            source_id   TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            detail      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ce_source_ts
            ON circuit_events(source_id, timestamp);
    """)
    conn.close()


class CircuitBreaker:
    """Thread-safe circuit breaker for data sources."""

    def __init__(self):
        _init_cb_db()
        self._lock = threading.Lock()

    def allow(self, source_id: str) -> bool:
        """Check if a call to this source should be allowed.

        Returns True if the circuit is CLOSED or HALF_OPEN (probe allowed).
        Returns False if OPEN and cooldown has not expired.
        """
        with self._lock:
            state_info = self._get_state(source_id)
            state = state_info.get("state", CircuitState.CLOSED)

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                # Check if cooldown has expired → transition to HALF_OPEN
                opened_at = state_info.get("opened_at")
                if opened_at:
                    try:
                        opened_dt = datetime.fromisoformat(opened_at)
                        if datetime.utcnow() - opened_dt > timedelta(seconds=COOLDOWN_SECONDS):
                            self._set_state(source_id, CircuitState.HALF_OPEN)
                            self._log_event(source_id, "half_open", "Cooldown expired, allowing probe")
                            logger.info("Circuit breaker %s: OPEN → HALF_OPEN (probe allowed)", source_id)
                            return True
                    except (ValueError, TypeError):
                        pass
                return False

            # HALF_OPEN — allow the probe
            return True

    def record_success(self, source_id: str) -> None:
        """Record a successful call — reset the circuit to CLOSED."""
        with self._lock:
            state_info = self._get_state(source_id)
            old_state = state_info.get("state", CircuitState.CLOSED)

            conn = _get_conn()
            conn.execute(
                """INSERT INTO circuit_state (source_id, state, failure_count, last_success_at)
                   VALUES (?, 'CLOSED', 0, ?)
                   ON CONFLICT(source_id) DO UPDATE SET
                       state = 'CLOSED',
                       failure_count = 0,
                       last_success_at = excluded.last_success_at""",
                (source_id, datetime.utcnow().isoformat()),
            )
            conn.commit()
            conn.close()

            if old_state != CircuitState.CLOSED:
                self._log_event(source_id, "closed", f"Recovery from {old_state}")
                logger.info("Circuit breaker %s: %s → CLOSED (recovered)", source_id, old_state)

    def record_failure(self, source_id: str, error: str = "") -> None:
        """Record a failed call. Opens circuit after threshold reached."""
        with self._lock:
            state_info = self._get_state(source_id)
            current_failures = state_info.get("failure_count", 0) + 1
            current_state = state_info.get("state", CircuitState.CLOSED)
            now = datetime.utcnow().isoformat()

            # If HALF_OPEN probe failed → go back to OPEN
            if current_state == CircuitState.HALF_OPEN:
                self._update_state(source_id, CircuitState.OPEN, current_failures, now, error)
                self._log_event(source_id, "open", f"Probe failed: {error[:100]}")
                self._dispatch_alert(source_id, error, current_failures)
                logger.warning("Circuit breaker %s: HALF_OPEN → OPEN (probe failed)", source_id)
                return

            # Check threshold
            if current_failures >= FAILURE_THRESHOLD:
                self._update_state(source_id, CircuitState.OPEN, current_failures, now, error)
                self._log_event(source_id, "open", f"Threshold {FAILURE_THRESHOLD} reached: {error[:100]}")
                self._dispatch_alert(source_id, error, current_failures)
                logger.warning(
                    "Circuit breaker %s: CLOSED → OPEN (%d consecutive failures)",
                    source_id, current_failures,
                )
            else:
                self._update_state(source_id, CircuitState.CLOSED, current_failures, now, error)
                self._log_event(source_id, "failure", f"Failure {current_failures}/{FAILURE_THRESHOLD}: {error[:100]}")
                logger.info(
                    "Circuit breaker %s: failure %d/%d",
                    source_id, current_failures, FAILURE_THRESHOLD,
                )

    def get_status(self) -> dict:
        """Get status of all circuit breakers."""
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM circuit_state ORDER BY source_id").fetchall()
            conn.close()
            return {
                "sources": [dict(r) for r in rows],
                "open_circuits": [dict(r) for r in rows if r["state"] == "OPEN"],
            }
        except sqlite3.Error:
            return {"sources": [], "error": "db unavailable"}

    def get_events(self, source_id: str | None = None, hours: int = 24) -> list[dict]:
        """Get circuit breaker events for debugging."""
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            if source_id:
                rows = conn.execute(
                    "SELECT * FROM circuit_events WHERE source_id = ? AND timestamp > ? ORDER BY timestamp DESC LIMIT 50",
                    (source_id, cutoff),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM circuit_events WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 100",
                    (cutoff,),
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []

    def reset(self, source_id: str) -> None:
        """Manually reset a circuit breaker to CLOSED."""
        with self._lock:
            conn = _get_conn()
            conn.execute("DELETE FROM circuit_state WHERE source_id = ?", (source_id,))
            conn.commit()
            conn.close()
            self._log_event(source_id, "manual_reset", "Circuit manually reset")
            logger.info("Circuit breaker %s: manually reset to CLOSED", source_id)

    # ── Internal helpers ──────────────────────────────────────────────

    def _get_state(self, source_id: str) -> dict:
        try:
            conn = _get_conn()
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM circuit_state WHERE source_id = ?", (source_id,)
            ).fetchone()
            conn.close()
            return dict(row) if row else {"state": CircuitState.CLOSED, "failure_count": 0}
        except sqlite3.Error:
            return {"state": CircuitState.CLOSED, "failure_count": 0}

    def _set_state(self, source_id: str, state: CircuitState) -> None:
        conn = _get_conn()
        now = datetime.utcnow().isoformat()
        opened_at = now if state == CircuitState.OPEN else None
        conn.execute(
            """INSERT INTO circuit_state (source_id, state, opened_at)
               VALUES (?, ?, ?)
               ON CONFLICT(source_id) DO UPDATE SET
                   state = excluded.state,
                   opened_at = COALESCE(excluded.opened_at, circuit_state.opened_at)""",
            (source_id, state.value, opened_at),
        )
        conn.commit()
        conn.close()

    def _update_state(
        self, source_id: str, state: CircuitState,
        failure_count: int, last_failure_at: str, error: str,
    ) -> None:
        conn = _get_conn()
        opened_at = last_failure_at if state == CircuitState.OPEN else None
        conn.execute(
            """INSERT INTO circuit_state (source_id, state, failure_count, last_failure_at, opened_at, last_error)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_id) DO UPDATE SET
                   state = excluded.state,
                   failure_count = excluded.failure_count,
                   last_failure_at = excluded.last_failure_at,
                   opened_at = CASE WHEN excluded.state = 'OPEN'
                                    THEN COALESCE(excluded.opened_at, circuit_state.opened_at)
                                    ELSE circuit_state.opened_at END,
                   last_error = excluded.last_error""",
            (source_id, state.value, failure_count, last_failure_at, opened_at, error[:200]),
        )
        conn.commit()
        conn.close()

    def _log_event(self, source_id: str, event_type: str, detail: str) -> None:
        try:
            conn = _get_conn()
            conn.execute(
                "INSERT INTO circuit_events (timestamp, source_id, event_type, detail) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), source_id, event_type, detail[:200]),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

    def _dispatch_alert(self, source_id: str, error: str, failures: int) -> None:
        """Dispatch alert when circuit opens."""
        try:
            from src.services.alert_dispatcher import AlertDispatcher
            dispatcher = AlertDispatcher()
            dispatcher.dispatch(
                rule_id=f"circuit_breaker_{source_id}",
                severity="high",
                message=(
                    f"Circuit breaker OPEN for '{source_id}': "
                    f"{failures} consecutive failures. "
                    f"Last error: {error[:100]}. "
                    f"Source will be retried after {COOLDOWN_SECONDS}s cooldown."
                ),
                rooms=[],
            )
        except (ImportError, Exception) as e:
            logger.warning("Failed to dispatch circuit breaker alert: %s", e)


# Lazy singleton — defer DB creation until first use
_circuit_breaker_instance: CircuitBreaker | None = None


def _get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker_instance
    if _circuit_breaker_instance is None:
        _circuit_breaker_instance = CircuitBreaker()
    return _circuit_breaker_instance


class _LazyCircuitBreaker:
    """Proxy that lazily initialises the real CircuitBreaker on first access."""

    def __getattr__(self, name: str):
        return getattr(_get_circuit_breaker(), name)


circuit_breaker: CircuitBreaker = _LazyCircuitBreaker()  # type: ignore[assignment]
