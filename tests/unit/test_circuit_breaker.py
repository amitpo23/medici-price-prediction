"""Unit tests for src.services.circuit_breaker — CircuitBreaker."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _isolate_dbs(test_case):
    """Redirect all SQLite DBs to temp directory."""
    test_case._tmpdir = tempfile.mkdtemp()
    tmp = Path(test_case._tmpdir)

    import src.services.circuit_breaker as cb
    import src.services.alert_dispatcher as ad

    test_case._orig_cb_db = cb.CB_DB_PATH
    test_case._orig_alert_db = ad.ALERT_DB_PATH

    cb.CB_DB_PATH = tmp / "circuit_breaker.db"
    ad.ALERT_DB_PATH = tmp / "alerts.db"


def _restore_dbs(test_case):
    import src.services.circuit_breaker as cb
    import src.services.alert_dispatcher as ad
    cb.CB_DB_PATH = test_case._orig_cb_db
    ad.ALERT_DB_PATH = test_case._orig_alert_db
    import shutil
    shutil.rmtree(test_case._tmpdir, ignore_errors=True)


class TestCircuitBreakerBasic(unittest.TestCase):
    """Test basic circuit breaker operations."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_import(self):
        from src.services.circuit_breaker import CircuitBreaker
        self.assertIsNotNone(CircuitBreaker)

    def test_allow_new_source(self):
        """New source should be allowed (CLOSED state)."""
        from src.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        self.assertTrue(cb.allow("test_source"))

    def test_record_success(self):
        from src.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_success("test_source")
        self.assertTrue(cb.allow("test_source"))

    def test_single_failure_still_allowed(self):
        from src.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure("test_source", "some error")
        self.assertTrue(cb.allow("test_source"))


class TestCircuitBreakerThreshold(unittest.TestCase):
    """Test circuit opening after threshold failures."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_opens_after_threshold(self):
        """Circuit should open after FAILURE_THRESHOLD consecutive failures."""
        from src.services.circuit_breaker import CircuitBreaker, FAILURE_THRESHOLD
        cb = CircuitBreaker()

        for i in range(FAILURE_THRESHOLD):
            cb.record_failure("flaky_source", f"error {i}")

        self.assertFalse(cb.allow("flaky_source"))

    def test_success_resets_count(self):
        """Success between failures should reset the count."""
        from src.services.circuit_breaker import CircuitBreaker, FAILURE_THRESHOLD
        cb = CircuitBreaker()

        # Fail twice
        cb.record_failure("source_a", "err1")
        cb.record_failure("source_a", "err2")
        # Success resets
        cb.record_success("source_a")
        # Fail once more — should still be under threshold
        cb.record_failure("source_a", "err3")

        self.assertTrue(cb.allow("source_a"))

    def test_other_sources_unaffected(self):
        """Opening one circuit doesn't affect others."""
        from src.services.circuit_breaker import CircuitBreaker, FAILURE_THRESHOLD
        cb = CircuitBreaker()

        for i in range(FAILURE_THRESHOLD):
            cb.record_failure("broken_source", f"error {i}")

        self.assertFalse(cb.allow("broken_source"))
        self.assertTrue(cb.allow("healthy_source"))


class TestCircuitBreakerRecovery(unittest.TestCase):
    """Test HALF_OPEN state and recovery."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_half_open_after_cooldown(self):
        """After cooldown, circuit should transition to HALF_OPEN."""
        from src.services.circuit_breaker import CircuitBreaker, FAILURE_THRESHOLD
        import src.services.circuit_breaker as cb_mod
        cb = CircuitBreaker()

        for i in range(FAILURE_THRESHOLD):
            cb.record_failure("source_x", f"error {i}")
        self.assertFalse(cb.allow("source_x"))

        # Manually set opened_at to the past
        import sqlite3
        conn = sqlite3.connect(str(cb_mod.CB_DB_PATH))
        from datetime import datetime, timedelta
        past = (datetime.utcnow() - timedelta(seconds=cb_mod.COOLDOWN_SECONDS + 10)).isoformat()
        conn.execute("UPDATE circuit_state SET opened_at = ? WHERE source_id = ?",
                      (past, "source_x"))
        conn.commit()
        conn.close()

        # Now it should transition to HALF_OPEN and allow
        self.assertTrue(cb.allow("source_x"))

    def test_success_after_half_open_closes(self):
        """Success in HALF_OPEN state should close the circuit."""
        from src.services.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker()

        # Manually set to HALF_OPEN
        cb._set_state("source_y", CircuitState.HALF_OPEN)
        self.assertTrue(cb.allow("source_y"))

        cb.record_success("source_y")
        # Should be CLOSED now
        state = cb._get_state("source_y")
        self.assertEqual(state["state"], "CLOSED")

    def test_failure_in_half_open_reopens(self):
        """Failure in HALF_OPEN state should reopen the circuit."""
        from src.services.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker()

        cb._set_state("source_z", CircuitState.HALF_OPEN)
        cb.record_failure("source_z", "probe failed")

        self.assertFalse(cb.allow("source_z"))


class TestCircuitBreakerStatus(unittest.TestCase):
    """Test status and events queries."""

    def setUp(self):
        _isolate_dbs(self)

    def tearDown(self):
        _restore_dbs(self)

    def test_status_empty(self):
        from src.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        status = cb.get_status()
        self.assertIn("sources", status)
        self.assertEqual(len(status["sources"]), 0)

    def test_status_after_failure(self):
        from src.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure("src_a", "err")
        status = cb.get_status()
        self.assertEqual(len(status["sources"]), 1)

    def test_events_logged(self):
        from src.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure("src_b", "err1")
        cb.record_success("src_b")
        events = cb.get_events("src_b", hours=1)
        self.assertGreater(len(events), 0)

    def test_reset(self):
        from src.services.circuit_breaker import CircuitBreaker, FAILURE_THRESHOLD
        cb = CircuitBreaker()
        for i in range(FAILURE_THRESHOLD):
            cb.record_failure("src_c", f"err{i}")
        self.assertFalse(cb.allow("src_c"))

        cb.reset("src_c")
        self.assertTrue(cb.allow("src_c"))


if __name__ == "__main__":
    unittest.main()
