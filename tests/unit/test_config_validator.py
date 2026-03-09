"""Unit tests for config_validator.py — startup config validation.

Tests use real os.environ manipulation — NO mocks.
"""
from __future__ import annotations

import os

import pytest

from src.utils.config_validator import validate_config, log_config_report, _is_valid_connection_string


# ── Helper to run validate_config with controlled env ───────────────


def _validate_with_env(overrides: dict) -> dict:
    """Run validate_config after setting specific env vars, then restore."""
    # Save originals
    saved = {}
    keys_to_clean = []
    for key, val in overrides.items():
        saved[key] = os.environ.get(key)
        if val is None:
            os.environ.pop(key, None)
            keys_to_clean.append(key)
        else:
            os.environ[key] = val

    try:
        return validate_config()
    finally:
        # Restore originals
        for key, original in saved.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


# ── Core validation tests ───────────────────────────────────────────


class TestValidateConfig:
    def test_minimal_valid_config(self):
        """With DB URL set, config should be valid."""
        report = _validate_with_env({
            "DATABASE_URL": "mssql+pyodbc://user:pass@server/db",
            "PREDICTION_API_KEY": "my-secure-key-123",
            "ANTHROPIC_API_KEY": "sk-ant-test-key",
        })
        assert report["valid"] is True
        assert len(report["errors"]) == 0

    def test_no_db_urls_warns(self):
        """Missing both DATABASE_URL and MEDICI_DB_URL should warn."""
        report = _validate_with_env({
            "DATABASE_URL": "",
            "MEDICI_DB_URL": "",
        })
        assert report["valid"] is True  # warning, not error
        warnings_text = " ".join(report["warnings"])
        assert "offline mode" in warnings_text

    def test_invalid_db_url_errors(self):
        """Invalid DATABASE_URL format should produce an error."""
        report = _validate_with_env({
            "DATABASE_URL": "not-a-connection-string",
            "MEDICI_DB_URL": "",
        })
        assert report["valid"] is False
        assert any("DATABASE_URL" in e for e in report["errors"])

    def test_valid_medici_db_url(self):
        """Valid MEDICI_DB_URL alone should not produce DB errors."""
        report = _validate_with_env({
            "DATABASE_URL": "",
            "MEDICI_DB_URL": "mssql+pyodbc://user:pass@server/db",
        })
        # Should not have DB-related errors
        db_errors = [e for e in report["errors"] if "DB_URL" in e]
        assert len(db_errors) == 0


class TestApiKeyValidation:
    def test_missing_prediction_key_warns(self):
        report = _validate_with_env({"PREDICTION_API_KEY": ""})
        warnings_text = " ".join(report["warnings"])
        assert "PREDICTION_API_KEY" in warnings_text

    def test_short_prediction_key_warns(self):
        report = _validate_with_env({"PREDICTION_API_KEY": "abc"})
        warnings_text = " ".join(report["warnings"])
        assert "short" in warnings_text


class TestAnthropicKeyValidation:
    def test_ai_enabled_no_key_warns(self):
        report = _validate_with_env({
            "AI_INTELLIGENCE_ENABLED": "true",
            "ANTHROPIC_API_KEY": "",
        })
        warnings_text = " ".join(report["warnings"])
        assert "ANTHROPIC_API_KEY" in warnings_text

    def test_ai_disabled_no_key_ok(self):
        """If AI is disabled, missing key shouldn't produce that specific warning."""
        report = _validate_with_env({
            "AI_INTELLIGENCE_ENABLED": "false",
            "ANTHROPIC_API_KEY": "",
        })
        ai_warnings = [w for w in report["warnings"] if "AI_INTELLIGENCE_ENABLED is true" in w]
        assert len(ai_warnings) == 0

    def test_bad_anthropic_key_format_warns(self):
        report = _validate_with_env({
            "ANTHROPIC_API_KEY": "bad-key-format",
        })
        warnings_text = " ".join(report["warnings"])
        assert "sk-" in warnings_text


class TestOptionalKeys:
    def test_missing_optional_keys_warns(self):
        """Missing optional keys should produce a warning, not an error."""
        report = _validate_with_env({
            "SEATGEEK_CLIENT_ID": "",
            "FRED_API_KEY": "",
        })
        assert report["valid"] is True
        warnings_text = " ".join(report["warnings"])
        assert "SEATGEEK_CLIENT_ID" in warnings_text or "enrichment" in warnings_text


class TestNumericVars:
    def test_invalid_port_errors(self):
        report = _validate_with_env({"API_PORT": "not_a_number"})
        assert report["valid"] is False
        assert any("API_PORT" in e for e in report["errors"])

    def test_valid_port_ok(self):
        report = _validate_with_env({"API_PORT": "8080"})
        port_errors = [e for e in report["errors"] if "API_PORT" in e]
        assert len(port_errors) == 0

    def test_invalid_cache_ttl_errors(self):
        report = _validate_with_env({"CACHE_TTL_HOURS": "abc"})
        assert report["valid"] is False
        assert any("CACHE_TTL_HOURS" in e for e in report["errors"])


# ── Connection string validation ────────────────────────────────────


class TestConnectionString:
    def test_mssql_valid(self):
        assert _is_valid_connection_string("mssql+pyodbc://user:pass@server/db") is True

    def test_sqlite_valid(self):
        assert _is_valid_connection_string("sqlite:///data/db.sqlite") is True

    def test_postgresql_valid(self):
        assert _is_valid_connection_string("postgresql://user:pass@localhost/db") is True

    def test_driver_valid(self):
        assert _is_valid_connection_string("Driver={ODBC Driver};Server=srv") is True

    def test_server_valid(self):
        assert _is_valid_connection_string("Server=myserver;Database=mydb") is True

    def test_empty_invalid(self):
        assert _is_valid_connection_string("") is False

    def test_random_string_invalid(self):
        assert _is_valid_connection_string("hello world") is False


# ── log_config_report ───────────────────────────────────────────────


class TestLogConfigReport:
    def test_valid_report_no_crash(self):
        """log_config_report should not crash on valid report."""
        report = {"valid": True, "warnings": [], "errors": []}
        log_config_report(report)  # should not raise

    def test_invalid_report_no_crash(self):
        report = {"valid": False, "warnings": ["warn1"], "errors": ["err1"]}
        log_config_report(report)  # should not raise

    def test_warnings_only_no_crash(self):
        report = {"valid": True, "warnings": ["some warning"], "errors": []}
        log_config_report(report)  # should not raise
