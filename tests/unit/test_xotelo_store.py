from __future__ import annotations

from src.analytics import xotelo_store


class _DummyResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"result": None}


def test_fetch_rates_handles_null_result_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(xotelo_store, "DB_PATH", tmp_path / "competitor_rates.sqlite")
    monkeypatch.setattr(xotelo_store.requests, "get", lambda *args, **kwargs: _DummyResponse())

    count = xotelo_store.fetch_rates(66814, days_ahead=7)

    assert count == 0