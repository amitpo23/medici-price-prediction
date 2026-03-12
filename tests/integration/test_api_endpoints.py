"""Integration tests for the 10 most critical API endpoints.

Tests hit the real FastAPI app — no mocks, no fake data.
Endpoints that require DB/cache return 503 when unavailable — that's
correct behavior. Tests verify proper HTTP responses, never 500/crashes.
"""
from __future__ import annotations

import pytest


# ── 1. GET /health ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(test_client):
    """Health endpoint must always return 200 with status field."""
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "model_loaded" in data
    assert "Traceback" not in resp.text


# ── 2. GET /api/v1/salesoffice/options ───────────────────────────────

@pytest.mark.asyncio
async def test_options_responds(test_client):
    """Options endpoint returns 200 with rows or 503 if cache cold — never 500."""
    resp = await test_client.get("/api/v1/salesoffice/options?profile=lite")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "rows" in data
        assert isinstance(data["rows"], list)
        assert "total_rows" in data


@pytest.mark.asyncio
async def test_options_with_t_days(test_client):
    """Options endpoint accepts t_days parameter without crashing."""
    resp = await test_client.get("/api/v1/salesoffice/options?t_days=7&profile=lite")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("t_days_requested") == 7


@pytest.mark.asyncio
async def test_options_single_source_mode_responds(test_client):
    """Single-source mode should respond without crashing when a source is selected."""
    resp = await test_client.get(
        "/api/v1/salesoffice/options?profile=lite&source=forward_curve&source_only=true"
    )
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("analysis_mode") == "source_only"
        assert data.get("selected_source") == "forward_curve"


@pytest.mark.asyncio
async def test_options_basic_source_mode_responds(test_client):
    """Basic data-source mode should respond without crashing for standalone source analysis."""
    resp = await test_client.get(
        "/api/v1/salesoffice/options?profile=lite&source=cancellation_data&source_only=true"
    )
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("analysis_mode") == "source_only"
        assert data.get("selected_source") == "cancellation_data"


@pytest.mark.asyncio
async def test_options_row_shape(test_client):
    """Each options row must have core fields when data is available."""
    resp = await test_client.get("/api/v1/salesoffice/options?profile=lite")
    if resp.status_code == 200:
        data = resp.json()
        rows = data.get("rows", [])
        if rows:
            row = rows[0]
            required_keys = [
                "detail_id", "hotel_id", "option_signal",
                "current_price", "predicted_checkin_price",
                "expected_min_price", "expected_max_price",
                "sources", "quality",
            ]
            for key in required_keys:
                assert key in row, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_options_lite_payload_is_compact(test_client):
    """Lite options rows should avoid shipping bulky modal-only payload fields."""
    resp = await test_client.get("/api/v1/salesoffice/options?profile=lite")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        rows = data.get("rows", [])
        if rows:
            row = rows[0]
            scan_history = row.get("scan_history") or {}
            assert "scan_price_series" not in scan_history
            source_predictions = row.get("source_predictions") or {}
            if source_predictions:
                sample = next(iter(source_predictions.values()))
                assert "reasoning" not in sample


# ── 3. GET /api/v1/salesoffice/options/detail/{id} ───────────────────

@pytest.mark.asyncio
async def test_options_detail_invalid_id(test_client):
    """Detail with non-existent ID returns 404 or 503 (cold cache) — never 500."""
    resp = await test_client.get("/api/v1/salesoffice/options/detail/999999999")
    assert resp.status_code in (200, 404, 503)
    assert "Traceback" not in resp.text


# ── 4. GET /api/v1/salesoffice/ai/ask ────────────────────────────────

@pytest.mark.asyncio
async def test_ai_ask_responds(test_client):
    """AI ask endpoint returns a structured response or 503 — never 500."""
    resp = await test_client.get("/api/v1/salesoffice/ai/ask?q=what+hotels")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)


# ── 5. GET /api/v1/salesoffice/ai/brief ──────────────────────────────

@pytest.mark.asyncio
async def test_ai_brief_responds(test_client):
    """AI brief returns executive summary or 503 — never 500."""
    resp = await test_client.get("/api/v1/salesoffice/ai/brief")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)


# ── 6. GET /api/v1/salesoffice/data ──────────────────────────────────

@pytest.mark.asyncio
async def test_data_responds(test_client):
    """Raw data endpoint returns JSON dict or 503 — never 500."""
    resp = await test_client.get("/api/v1/salesoffice/data")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)


# ── 7. GET /api/v1/salesoffice/export/csv/contracts ──────────────────

@pytest.mark.asyncio
async def test_export_csv_contracts(test_client):
    """CSV export returns proper content type."""
    resp = await test_client.get("/api/v1/salesoffice/export/csv/contracts")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "csv" in content_type or "text" in content_type or "octet" in content_type
    assert "Traceback" not in resp.text


# ── 8. GET /api/v1/salesoffice/rules ─────────────────────────────────

@pytest.mark.asyncio
async def test_rules_list(test_client):
    """Rules endpoint returns a list."""
    resp = await test_client.get("/api/v1/salesoffice/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "Traceback" not in resp.text


# ── 9. GET /api/v1/salesoffice/freshness ─────────────────────────────

@pytest.mark.asyncio
async def test_freshness_returns_html(test_client):
    """Freshness page returns HTML content."""
    resp = await test_client.get("/api/v1/salesoffice/freshness")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "html" in content_type
    assert "Traceback" not in resp.text


# ── 10. GET /api/v1/salesoffice/status ───────────────────────────────

@pytest.mark.asyncio
async def test_status_returns_json(test_client):
    """Status endpoint returns JSON with core status fields."""
    resp = await test_client.get("/api/v1/salesoffice/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "snapshots_collected" in data
    assert "Traceback" not in resp.text


# ── Bonus: options/legend ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_options_legend(test_client):
    """Legend endpoint returns schema for UI rendering."""
    resp = await test_client.get("/api/v1/salesoffice/options/legend")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "legend_version" in data or "info_icon_rules" in data or "scale" in data
    assert "Traceback" not in resp.text


@pytest.mark.asyncio
async def test_options_view_returns_async_html(test_client):
    """Options HTML shell should render immediately without waiting for analytics."""
    resp = await test_client.get("/api/v1/salesoffice/options/view")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "html" in content_type
    assert "Options Trading Signals" in resp.text
    assert "/api/v1/salesoffice/options/warmup" in resp.text
    assert "Prediction engine" in resp.text
    assert "Source view" in resp.text
    assert "Selected source $" in resp.text
    assert "Booking Cancellations" in resp.text
    assert "Source-only prediction" in resp.text
    assert "Graph mode" in resp.text
    assert "Source comparison" in resp.text
    assert "Scan-only zoom" in resp.text
    assert "Traceback" not in resp.text


# ── Bonus: sources/audit ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sources_audit(test_client):
    """Sources audit returns data source info or 503 if cache cold."""
    resp = await test_client.get("/api/v1/salesoffice/sources/audit")
    assert resp.status_code in (200, 503)
    assert "Traceback" not in resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
