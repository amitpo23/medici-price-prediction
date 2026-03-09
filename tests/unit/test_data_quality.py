"""Tests for the data quality scoring system."""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def temp_quality_db(monkeypatch, tmp_path):
    """Use a temporary database for each test."""
    db_path = tmp_path / "test_source_health.db"
    import src.analytics.data_quality as dq
    monkeypatch.setattr(dq, "DB_PATH", db_path)
    dq.init_quality_db()
    return db_path


# ── Database initialization ─────────────────────────────────────────


class TestInitQualityDb:
    """Test database creation."""

    def test_creates_table(self, temp_quality_db):
        conn = sqlite3.connect(str(temp_quality_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_health'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_index(self, temp_quality_db):
        conn = sqlite3.connect(str(temp_quality_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "idx_sh_source_ts" in indexes

    def test_idempotent(self, temp_quality_db):
        from src.analytics.data_quality import init_quality_db
        init_quality_db()
        init_quality_db()


# ── Log health ──────────────────────────────────────────────────────


class TestLogHealth:
    """Test health logging."""

    def test_inserts_record(self, temp_quality_db):
        from src.analytics.data_quality import _log_health
        _log_health("test_source", 0.8, 0.9, False, None, None)

        conn = sqlite3.connect(str(temp_quality_db))
        count = conn.execute("SELECT COUNT(*) FROM source_health").fetchone()[0]
        conn.close()
        assert count == 1

    def test_with_anomaly_and_weight(self, temp_quality_db):
        from src.analytics.data_quality import _log_health
        _log_health("degraded_source", 0.3, 0.8, True, 0.3, "stale data")

        conn = sqlite3.connect(str(temp_quality_db))
        row = conn.execute("SELECT * FROM source_health WHERE source_id = 'degraded_source'").fetchone()
        conn.close()
        assert row is not None


# ── Freshness computation ───────────────────────────────────────────


class TestComputeFreshness:
    """Test freshness scoring."""

    def test_fresh_data(self):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        # Age 0 for a 24h source → should be high (e^1 ≈ 2.7, clamped to 1.0)
        score = scorer._compute_freshness("open_meteo", 0.0)
        assert score > 0.9

    def test_stale_data(self):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        # Age 72h for a 24h source → very stale
        score = scorer._compute_freshness("open_meteo", 72.0)
        assert score < 0.3

    def test_static_source_always_fresh(self):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        score = scorer._compute_freshness("med_search_hotels", 1000.0)
        assert score == 1.0

    def test_none_age_returns_medium(self):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        score = scorer._compute_freshness("unknown", None)
        assert score == 0.5

    def test_unknown_source_uses_default(self):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        # Unknown source defaults to 24h expected interval
        # Age 48h for 24h source → exp(-48/24+1) = exp(-1) ≈ 0.37
        score = scorer._compute_freshness("nonexistent", 48.0)
        assert 0.0 < score < 0.5


# ── Reliability computation ─────────────────────────────────────────


class TestComputeReliability:
    """Test reliability scoring."""

    def test_empty_history_returns_one(self, temp_quality_db):
        from src.analytics.data_quality import DataQualityScorer
        scorer = DataQualityScorer()
        score = scorer._compute_reliability("new_source")
        assert score == 1.0

    def test_all_good_readings(self, temp_quality_db):
        from src.analytics.data_quality import _log_health, DataQualityScorer
        for _ in range(10):
            _log_health("reliable_src", 0.9, 1.0)
        scorer = DataQualityScorer()
        score = scorer._compute_reliability("reliable_src")
        assert score == 1.0

    def test_mixed_readings(self, temp_quality_db):
        from src.analytics.data_quality import _log_health, DataQualityScorer
        # 5 good, 5 bad
        for _ in range(5):
            _log_health("mixed_src", 0.8, 1.0)
        for _ in range(5):
            _log_health("mixed_src", 0.2, 1.0)
        scorer = DataQualityScorer()
        score = scorer._compute_reliability("mixed_src")
        assert 0.4 <= score <= 0.6


# ── Weight adjustments ──────────────────────────────────────────────


class TestWeightAdjustments:
    """Test auto weight adjustment."""

    def test_no_adjustments_for_healthy(self, temp_quality_db):
        from src.analytics.data_quality import _log_health, DataQualityScorer
        _log_health("healthy_src", 0.9, 1.0, weight_override=None)
        scorer = DataQualityScorer()
        adjustments = scorer.get_weight_adjustments()
        assert "healthy_src" not in adjustments

    def test_adjustment_for_degraded(self, temp_quality_db):
        from src.analytics.data_quality import _log_health, DataQualityScorer
        _log_health("degraded_src", 0.3, 0.8, weight_override=0.3)
        scorer = DataQualityScorer()
        adjustments = scorer.get_weight_adjustments()
        assert "degraded_src" in adjustments
        assert adjustments["degraded_src"] == 0.3

    def test_protected_source_not_adjusted(self):
        from src.analytics.data_quality import PROTECTED_SOURCES
        assert "salesoffice" in PROTECTED_SOURCES


# ── Query functions ─────────────────────────────────────────────────


class TestGetQualityHistory:
    """Test history query."""

    def test_empty_history(self, temp_quality_db):
        from src.analytics.data_quality import get_quality_history
        result = get_quality_history("unknown_src", days=7)
        assert result["total_records"] == 0

    def test_with_data(self, temp_quality_db):
        from src.analytics.data_quality import _log_health, get_quality_history
        _log_health("src_a", 0.8, 0.9)
        _log_health("src_a", 0.7, 0.85)
        result = get_quality_history("src_a", days=7)
        assert result["total_records"] == 2
        assert result["source_id"] == "src_a"


# ── API endpoints ───────────────────────────────────────────────────


class TestDataQualityApiEndpoints:
    """Test data quality API endpoints through TestClient."""

    def test_status_endpoint(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/salesoffice/data-quality/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert "total_sources" in data

    def test_history_endpoint(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/salesoffice/data-quality/history?source=open_meteo&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "open_meteo"

    def test_history_missing_source_param(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/salesoffice/data-quality/history")
        assert resp.status_code == 422  # Missing required param
