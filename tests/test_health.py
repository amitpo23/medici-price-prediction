"""Smoke tests — verify the app imports and basic endpoints respond."""
from __future__ import annotations

import pytest


def test_app_imports():
    """The FastAPI app should import without errors even without DB connections."""
    from src.api.main import app
    assert app is not None
    assert app.title == "Medici Price Prediction API"


def test_app_has_routes():
    """Verify key routes are registered."""
    from src.api.main import app

    paths = [route.path for route in app.routes]
    assert "/health" in paths
    assert "/api/v1/salesoffice/options" in paths


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """GET /health should return 200 with basic status."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert "version" in data
    assert "model_loaded" in data


@pytest.mark.asyncio
async def test_health_detailed(test_client):
    """GET /health?detail=true should return comprehensive status."""
    response = await test_client.get("/health?detail=true")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert "uptime_seconds" in data
    assert "data_sources" in data
    assert "cache" in data
    assert "predictions" in data
    assert "models" in data


@pytest.mark.asyncio
async def test_health_view_returns_html(test_client):
    """GET /health/view should return HTML dashboard."""
    response = await test_client.get("/health/view")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Medici Health Dashboard" in response.text


@pytest.mark.asyncio
async def test_root_redirects(test_client):
    """GET / should redirect to docs."""
    response = await test_client.get("/", follow_redirects=False)
    assert response.status_code in (307, 302, 200)
