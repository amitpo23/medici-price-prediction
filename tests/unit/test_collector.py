"""Tests for SalesOffice collector query filters and runtime metadata."""
from __future__ import annotations

import sys
import types

import pandas as pd

from src.analytics import collector


def test_collector_queries_only_active_orders():
    """Collector queries should filter by IsActive=1 only (no WebJobStatus filter)."""
    assert "o.IsActive = 1" in collector.QUERY
    assert "WebJobStatus" not in collector.QUERY

    assert "o2.IsActive = 1" in collector.HISTORY_QUERY
    assert "WebJobStatus" not in collector.HISTORY_QUERY

    assert "o.IsActive = 1" in collector.SCAN_HISTORY_QUERY
    assert "WebJobStatus" not in collector.SCAN_HISTORY_QUERY


def test_collector_query_excludes_soft_deleted():
    """Main QUERY must filter out soft-deleted details (IsDeleted=0)."""
    assert "d.IsDeleted = 0" in collector.QUERY
    # History queries intentionally include soft-deleted rows for historical analysis
    assert "IsDeleted" not in collector.HISTORY_QUERY
    assert "IsDeleted" not in collector.SCAN_HISTORY_QUERY


def test_collect_prices_updates_runtime_and_converts_dates(monkeypatch):
    """Successful collection should report runtime metadata and normalize date fields."""
    sample = pd.DataFrame([
        {
            "detail_id": 1,
            "order_id": 11,
            "hotel_id": 66814,
            "hotel_name": "Breakwater South Beach",
            "room_category": 1,
            "room_board": 2,
            "room_price": 199.0,
            "room_code": "STD",
            "date_from": pd.Timestamp("2026-04-01"),
            "date_to": pd.Timestamp("2026-04-03"),
            "destination_id": 66814,
            "is_processed": 1,
        }
    ])
    captured: dict[str, object] = {}

    monkeypatch.setattr(collector, "init_db", lambda: None)
    monkeypatch.setattr(collector, "save_snapshot", lambda df, snapshot_ts=None: len(df))
    monkeypatch.setattr(collector.pd, "read_sql_query", lambda query, engine: sample.copy())

    import src.data.trading_db as trading_db
    monkeypatch.setattr(trading_db, "get_trading_engine", lambda: object())

    fake_logger = types.SimpleNamespace(log_price_snapshot=lambda df, snapshot_ts=None: captured.update({"logged": len(df)}))
    monkeypatch.setitem(sys.modules, "src.analytics.prediction_logger", fake_logger)

    df = collector.collect_prices()

    assert df["date_from"].iloc[0] == "2026-04-01"
    assert df["date_to"].iloc[0] == "2026-04-03"

    runtime = collector.get_collection_runtime_status()
    assert runtime["last_state"] == "success"
    assert runtime["last_rows_collected"] == 1
    assert runtime["last_hotels_collected"] == 1
    assert runtime["last_snapshot_rows_saved"] == 1
    assert runtime["last_successful_db_query_ts"] is not None
    assert runtime["last_error"] is None
    assert captured["logged"] == 1


def test_collect_prices_records_failed_runtime(monkeypatch):
    """Query failures should be reflected in runtime metadata."""
    monkeypatch.setattr(collector, "init_db", lambda: None)

    import src.data.trading_db as trading_db
    monkeypatch.setattr(trading_db, "get_trading_engine", lambda: object())
    monkeypatch.setattr(
        collector.pd,
        "read_sql_query",
        lambda query, engine: (_ for _ in ()).throw(ConnectionError("db down")),
    )

    df = collector.collect_prices()

    assert df.empty
    runtime = collector.get_collection_runtime_status()
    assert runtime["last_state"] == "failed"
    assert runtime["last_error"] == "db down"
    assert runtime["last_failure_ts"] is not None