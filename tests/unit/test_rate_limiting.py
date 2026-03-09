"""Tests for rate limiting, API key validation, and CORS middleware."""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI, Depends, Header, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient


# ── verify_api_key ───────────────────────────────────────────────────


class TestVerifyApiKey:
    """Test the centralized verify_api_key function."""

    def test_no_key_configured_allows_any(self, monkeypatch):
        """When PREDICTION_API_KEY is empty, any key is valid."""
        monkeypatch.setenv("PREDICTION_API_KEY", "")
        from src.api.middleware import verify_api_key
        assert verify_api_key("anything") is True
        assert verify_api_key("") is True

    def test_single_key_valid(self, monkeypatch):
        """Single configured key validates correctly."""
        monkeypatch.setenv("PREDICTION_API_KEY", "secret123")
        from src.api.middleware import verify_api_key
        assert verify_api_key("secret123") is True

    def test_single_key_invalid(self, monkeypatch):
        """Wrong key is rejected."""
        monkeypatch.setenv("PREDICTION_API_KEY", "secret123")
        from src.api.middleware import verify_api_key
        assert verify_api_key("wrong") is False

    def test_multiple_keys_comma_separated(self, monkeypatch):
        """Multiple comma-separated keys all work."""
        monkeypatch.setenv("PREDICTION_API_KEY", "key1,key2,key3")
        from src.api.middleware import verify_api_key
        assert verify_api_key("key1") is True
        assert verify_api_key("key2") is True
        assert verify_api_key("key3") is True
        assert verify_api_key("key4") is False

    def test_multiple_keys_with_spaces(self, monkeypatch):
        """Spaces around keys are trimmed."""
        monkeypatch.setenv("PREDICTION_API_KEY", " key1 , key2 ")
        from src.api.middleware import verify_api_key
        assert verify_api_key("key1") is True
        assert verify_api_key("key2") is True

    def test_empty_key_rejected_when_configured(self, monkeypatch):
        """Empty key is rejected when a key is configured."""
        monkeypatch.setenv("PREDICTION_API_KEY", "secret")
        from src.api.middleware import verify_api_key
        assert verify_api_key("") is False


# ── Rate limiter setup ───────────────────────────────────────────────


class TestRateLimiter:
    """Test that rate limiter is properly configured."""

    def test_limiter_instance_exists(self):
        from src.api.middleware import limiter
        assert limiter is not None

    def test_rate_limit_constants(self):
        from src.api.middleware import RATE_LIMIT_DATA, RATE_LIMIT_AI, RATE_LIMIT_EXPORT
        assert "100" in RATE_LIMIT_DATA
        assert "20" in RATE_LIMIT_AI
        assert "10" in RATE_LIMIT_EXPORT

    def test_rate_limit_handler_returns_429(self):
        """Rate limit exceeded handler is registered on the app."""
        from src.api.middleware import setup_middleware, limiter
        from slowapi.errors import RateLimitExceeded

        app = FastAPI()
        setup_middleware(app)

        # Verify the exception handler is registered
        assert RateLimitExceeded in app.exception_handlers
        assert app.state.limiter is limiter


# ── CORS setup ───────────────────────────────────────────────────────


class TestCorsSetup:
    """Test CORS middleware configuration."""

    def test_cors_with_no_origins(self, monkeypatch):
        """No CORS_ORIGINS means empty allow list (same-origin only)."""
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        from src.api.middleware import setup_cors

        app = FastAPI()
        setup_cors(app)
        # Middleware is added without error
        assert len(app.user_middleware) >= 1

    def test_cors_with_configured_origins(self, monkeypatch):
        """CORS_ORIGINS configures allowed origins."""
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com,https://app.example.com")
        from src.api.middleware import setup_cors

        app = FastAPI()
        setup_cors(app)
        assert len(app.user_middleware) >= 1


# ── setup_middleware integration ─────────────────────────────────────


class TestSetupMiddleware:
    """Test the full middleware setup."""

    def test_setup_middleware_adds_all(self, monkeypatch):
        """setup_middleware adds rate limiter, CORS, and correlation ID."""
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        from src.api.middleware import setup_middleware

        app = FastAPI()
        setup_middleware(app)

        # Should have limiter on app state
        assert hasattr(app.state, "limiter")

        # Should have middlewares added
        assert len(app.user_middleware) >= 2  # CORS + CorrelationId

    def test_correlation_id_works_with_full_setup(self, monkeypatch):
        """Full middleware stack still returns X-Request-ID."""
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        from src.api.middleware import setup_middleware

        app = FastAPI()

        @app.get("/ping")
        def ping():
            return {"pong": True}

        setup_middleware(app)
        client = TestClient(app)

        response = client.get("/ping")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
