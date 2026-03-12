"""Tests for SalesOffice shared state warmup behavior."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.routers import _shared_state as shared_state


def test_get_or_run_analysis_kicks_off_background_warmup(monkeypatch):
    """Cold cache should start warmup and fail fast with 503 instead of blocking."""
    calls: dict[str, int | bool] = {
        "warmup_called": 0,
    }

    shared_state._analysis_warming.clear()

    monkeypatch.setattr(shared_state._cm, "get_data", lambda name: None)

    def _fake_kickoff():
        calls["warmup_called"] += 1
        return {
            "detail": "Analysis cache is cold. Warmup started — retry in 60 seconds.",
            "retry_after": 60,
        }

    monkeypatch.setattr(shared_state, "_kickoff_analysis_warmup", _fake_kickoff)

    with pytest.raises(HTTPException) as exc:
        shared_state._get_or_run_analysis()

    assert exc.value.status_code == 503
    assert exc.value.headers == {"Retry-After": "60"}
    assert calls["warmup_called"] == 1


def test_kickoff_analysis_warmup_disabled_outside_production(monkeypatch):
    """Cold cache should not start scheduler when non-production warmup is disabled."""
    shared_state._analysis_warming.clear()

    monkeypatch.setattr(shared_state._cm, "get_data", lambda name: None)
    monkeypatch.setattr(shared_state, "_restore_salesoffice_persisted_state", lambda: False)
    monkeypatch.setattr(shared_state, "SALESOFFICE_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(shared_state, "IS_PRODUCTION", False)
    monkeypatch.setattr(shared_state, "SALESOFFICE_ALLOW_NON_PROD_SCHEDULER", False)

    warmup = shared_state._kickoff_analysis_warmup()

    assert warmup["cache_ready"] is False
    assert warmup["analysis_warming"] is False
    assert warmup["scheduler_running"] is False
    assert warmup["started"] is False
    assert "disabled outside production" in str(warmup["detail"])


def test_get_cached_analysis_restores_persisted_cache(monkeypatch):
    """Cached analysis lookup should restore persisted state before failing cold."""
    calls = {"restored": 0}

    data_state = {"value": None}

    def fake_get_data(name):
        return data_state["value"]

    def fake_restore():
        calls["restored"] += 1
        data_state["value"] = {"run_ts": "2026-03-11T00:00:00Z"}
        return True

    monkeypatch.setattr(shared_state._cm, "get_data", fake_get_data)
    monkeypatch.setattr(shared_state, "_restore_salesoffice_persisted_state", fake_restore)

    analysis = shared_state._get_cached_analysis()

    assert analysis == {"run_ts": "2026-03-11T00:00:00Z"}
    assert calls["restored"] == 1
