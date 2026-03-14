"""Tests for structured logging configuration and middleware."""
from __future__ import annotations

import json
import logging

import pytest


# ── logging_config ───────────────────────────────────────────────────


class TestConfigureLogging:
    """Test the configure_logging() function."""

    def test_configure_sets_json_formatter(self):
        """Root logger uses JSON formatter after configure."""
        from src.utils.logging_config import configure_logging
        configure_logging()

        root = logging.getLogger()
        assert len(root.handlers) >= 1
        handler = root.handlers[0]
        from pythonjsonlogger.json import JsonFormatter
        assert isinstance(handler.formatter, JsonFormatter)

    def test_log_output_is_json(self, capfd):
        """Logger emits valid JSON lines."""
        from src.utils.logging_config import configure_logging
        configure_logging()

        test_logger = logging.getLogger("test.json_output")
        test_logger.info("hello from test")

        captured = capfd.readouterr()
        # Parse each non-empty line as JSON
        lines = [l for l in captured.err.strip().split("\n") if l.strip()]
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert record["message"] == "hello from test"
        assert "timestamp" in record
        assert record["level"] == "INFO"
        assert "memory_rss_mb" in record
        assert isinstance(record["memory_rss_mb"], (int, float))
        assert record["memory_rss_mb"] >= 0

    def test_log_includes_correlation_id(self, capfd):
        """Correlation ID from contextvar appears in log output."""
        from src.utils.logging_config import configure_logging, correlation_id_var
        configure_logging()

        token = correlation_id_var.set("test-req-123")
        try:
            test_logger = logging.getLogger("test.correlation")
            test_logger.info("correlated message")

            captured = capfd.readouterr()
            lines = [l for l in captured.err.strip().split("\n") if l.strip()]
            record = json.loads(lines[-1])
            assert record["correlation_id"] == "test-req-123"
        finally:
            correlation_id_var.reset(token)

    def test_log_level_from_env(self, monkeypatch):
        """LOG_LEVEL env var controls root logger level."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        from src.utils.logging_config import configure_logging
        configure_logging()

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_log_level_default_info(self, monkeypatch):
        """Default log level is INFO when env var not set."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        from src.utils.logging_config import configure_logging
        configure_logging()

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_uvicorn_access_logger_silenced(self):
        """Uvicorn access logger is set to WARNING to reduce noise."""
        from src.utils.logging_config import configure_logging
        configure_logging()

        uvicorn_access = logging.getLogger("uvicorn.access")
        assert uvicorn_access.level == logging.WARNING

    def test_memory_snapshot_helper_returns_numeric_value(self):
        """Memory snapshot helper returns a numeric RSS field when available."""
        from src.utils.logging_config import _get_process_memory_snapshot

        snapshot = _get_process_memory_snapshot()
        if snapshot is None:
            pytest.skip("Process memory snapshot is unavailable on this platform")

        assert "memory_rss_mb" in snapshot
        assert isinstance(snapshot["memory_rss_mb"], (int, float))
        assert snapshot["memory_rss_mb"] >= 0


# ── correlation_id_var ───────────────────────────────────────────────


class TestCorrelationIdVar:
    """Test the correlation_id context variable."""

    def test_default_is_empty_string(self):
        from src.utils.logging_config import correlation_id_var
        assert correlation_id_var.get("") == ""

    def test_set_and_get(self):
        from src.utils.logging_config import correlation_id_var
        token = correlation_id_var.set("abc123")
        try:
            assert correlation_id_var.get() == "abc123"
        finally:
            correlation_id_var.reset(token)

    def test_reset_restores_default(self):
        from src.utils.logging_config import correlation_id_var
        token = correlation_id_var.set("temp-id")
        correlation_id_var.reset(token)
        assert correlation_id_var.get("") == ""


# ── CorrelationIdMiddleware ──────────────────────────────────────────


class TestCorrelationIdMiddleware:
    """Test the CorrelationIdMiddleware via the test client."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from httpx import ASGITransport, AsyncClient
        from src.api.middleware import CorrelationIdMiddleware
        from src.utils.logging_config import correlation_id_var

        test_app = FastAPI()
        test_app.add_middleware(CorrelationIdMiddleware)

        @test_app.get("/test-endpoint")
        async def test_endpoint():
            return JSONResponse(content={"correlation_id": correlation_id_var.get("")})

        from starlette.testclient import TestClient
        return TestClient(test_app)

    def test_generates_request_id_if_not_provided(self, client):
        """Middleware generates X-Request-ID when not in request."""
        response = client.get("/test-endpoint")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) > 0

    def test_echoes_provided_request_id(self, client):
        """Middleware echoes back the X-Request-ID from request."""
        response = client.get(
            "/test-endpoint",
            headers={"X-Request-ID": "my-custom-id-42"},
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "my-custom-id-42"

    def test_correlation_id_available_in_handler(self, client):
        """Handler can access correlation_id via contextvar."""
        response = client.get(
            "/test-endpoint",
            headers={"X-Request-ID": "handler-test-99"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correlation_id"] == "handler-test-99"

    def test_correlation_id_reset_after_request(self, client):
        """Correlation ID is reset after request completes."""
        from src.utils.logging_config import correlation_id_var

        client.get("/test-endpoint", headers={"X-Request-ID": "temp-id"})
        # After request, the contextvar should be reset
        assert correlation_id_var.get("") == ""
