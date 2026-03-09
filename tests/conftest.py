"""Shared test fixtures for Medici Price Prediction.

Provides FastAPI test client for hitting real app endpoints.
No mocks — tests run against the actual application with graceful degradation.
"""
from __future__ import annotations

import os

import pytest

# Set env defaults so app starts without requiring secrets
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("MEDICI_DB_URL", "")
os.environ.setdefault("PREDICTION_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("AI_INTELLIGENCE_ENABLED", "false")


@pytest.fixture()
def test_client():
    """FastAPI AsyncClient hitting the real app — no mocks."""
    from httpx import ASGITransport, AsyncClient
    from src.api.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
