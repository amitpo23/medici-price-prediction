"""Unit tests for execution_quality.py — Execution Quality & Slippage."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.analytics.execution_quality import (
    ExecutionMetrics,
    SlippageDetail,
    ExecutionQualityReport,
    compute_execution_quality,
    compute_slippage_analysis,
    _compute_exec_time_hours,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db_dir(tmp_path):
    return tmp_path


@pytest.fixture
def opp_db(db_dir):
    """Opportunity queue DB with mixed status entries."""
    path = db_dir / "opportunity_queue.db"
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE opportunity_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id INTEGER, hotel_id INTEGER, hotel_name TEXT,
            category TEXT, board TEXT, checkin_date TEXT,
            buy_price REAL, push_price REAL, predicted_price REAL,
            profit_usd REAL, max_rooms INTEGER, signal TEXT,
            confidence TEXT, status TEXT, created_at TEXT,
            picked_at TEXT, completed_at TEXT, error_message TEXT,
            opp_id INTEGER, trigger_type TEXT, batch_id TEXT,
            board_id INTEGER, category_id INTEGER
        )
    """)

    now = datetime.utcnow()
    t1_created = (now - timedelta(hours=2)).isoformat() + "Z"
    t1_done = now.isoformat() + "Z"
    t2_created = (now - timedelta(hours=5)).isoformat() + "Z"
    t2_done = (now - timedelta(hours=1)).isoformat() + "Z"

    # Done — good prediction match
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, buy_price, push_price,
         predicted_price, signal, status, created_at, completed_at)
        VALUES (100, 1, 'Hotel A', 150.0, 200.0, 155.0, 'CALL', 'done', ?, ?)
    """, (t1_created, t1_done))

    # Done — bigger slippage
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, buy_price, push_price,
         predicted_price, signal, status, created_at, completed_at)
        VALUES (101, 1, 'Hotel A', 200.0, 250.0, 220.0, 'CALL', 'done', ?, ?)
    """, (t2_created, t2_done))

    # Done STRONG_CALL
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, buy_price, push_price,
         predicted_price, signal, status, created_at, completed_at)
        VALUES (102, 2, 'Hotel B', 180.0, 230.0, 185.0, 'STRONG_CALL', 'done', ?, ?)
    """, (t1_created, t1_done))

    # Failed
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, buy_price, push_price,
         predicted_price, signal, status, created_at, error_message)
        VALUES (103, 2, 'Hotel B', 100.0, 150.0, 110.0, 'CALL', 'failed', ?, 'timeout')
    """, (t1_created,))

    # Pending
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, buy_price, push_price,
         predicted_price, signal, status, created_at)
        VALUES (104, 3, 'Hotel C', 120.0, 170.0, 130.0, 'CALL', 'pending', ?)
    """, (t1_created,))

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def ovr_db(db_dir):
    """Override queue DB."""
    path = db_dir / "override_queue.db"
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE override_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id INTEGER, hotel_id INTEGER, hotel_name TEXT,
            category TEXT, board TEXT, checkin_date TEXT,
            current_price REAL, discount_usd REAL, target_price REAL,
            signal TEXT, confidence TEXT, path_min_price REAL,
            status TEXT, created_at TEXT, picked_at TEXT,
            completed_at TEXT, error_message TEXT,
            trigger_type TEXT, batch_id TEXT
        )
    """)

    now = datetime.utcnow()
    t_created = (now - timedelta(hours=1)).isoformat() + "Z"
    t_done = now.isoformat() + "Z"

    # Done override
    conn.execute("""
        INSERT INTO override_requests
        (detail_id, hotel_id, hotel_name, current_price, discount_usd,
         target_price, signal, status, created_at, completed_at)
        VALUES (200, 1, 'Hotel A', 300.0, 5.0, 295.0, 'PUT', 'done', ?, ?)
    """, (t_created, t_done))

    # Failed override
    conn.execute("""
        INSERT INTO override_requests
        (detail_id, hotel_id, hotel_name, current_price, discount_usd,
         target_price, signal, status, created_at, error_message)
        VALUES (201, 1, 'Hotel A', 250.0, 3.0, 247.0, 'PUT', 'failed', ?, 'zenith_error')
    """, (t_created,))

    conn.commit()
    conn.close()
    return path


# ── Test Execution Quality Report ────────────────────────────────────

class TestExecutionQuality:
    def test_combined_report(self, opp_db, ovr_db):
        report = compute_execution_quality(opp_db_path=opp_db, ovr_db_path=ovr_db)
        assert isinstance(report, ExecutionQualityReport)
        assert report.timestamp
        assert report.total_executions == 4  # 3 opp done + 1 ovr done
        assert report.combined_fill_rate > 0

    def test_opportunity_metrics(self, opp_db, db_dir):
        report = compute_execution_quality(
            opp_db_path=opp_db, ovr_db_path=db_dir / "x.db"
        )
        m = report.opportunity_metrics
        assert m.queue_type == "opportunity"
        assert m.total_queued == 5
        assert m.done_count == 3
        assert m.failed_count == 1
        assert m.pending_count == 1
        assert m.fill_rate == pytest.approx(0.6, abs=0.01)  # 3/5
        assert m.rejection_rate == pytest.approx(0.2, abs=0.01)  # 1/5

    def test_override_metrics(self, ovr_db, db_dir):
        report = compute_execution_quality(
            opp_db_path=db_dir / "x.db", ovr_db_path=ovr_db
        )
        m = report.override_metrics
        assert m.queue_type == "override"
        assert m.total_queued == 2
        assert m.done_count == 1
        assert m.failed_count == 1
        assert m.fill_rate == pytest.approx(0.5)

    def test_slippage_stats(self, opp_db, db_dir):
        report = compute_execution_quality(
            opp_db_path=opp_db, ovr_db_path=db_dir / "x.db"
        )
        m = report.opportunity_metrics
        assert m.avg_slippage_usd > 0
        assert m.avg_slippage_pct > 0
        assert m.max_slippage_usd > 0

    def test_execution_time(self, opp_db, db_dir):
        report = compute_execution_quality(
            opp_db_path=opp_db, ovr_db_path=db_dir / "x.db"
        )
        m = report.opportunity_metrics
        assert m.avg_execution_time_hours > 0

    def test_no_dbs(self, db_dir):
        report = compute_execution_quality(
            opp_db_path=db_dir / "x.db",
            ovr_db_path=db_dir / "y.db"
        )
        assert report.total_executions == 0
        assert report.combined_fill_rate == 0.0

    def test_by_signal(self, opp_db, db_dir):
        report = compute_execution_quality(
            opp_db_path=opp_db, ovr_db_path=db_dir / "x.db"
        )
        by_sig = report.opportunity_metrics.by_signal
        assert "CALL" in by_sig
        assert by_sig["CALL"]["done"] >= 2


# ── Test Slippage Analysis ───────────────────────────────────────────

class TestSlippageAnalysis:
    def test_basic(self, opp_db):
        slippages = compute_slippage_analysis(opp_db_path=opp_db)
        assert len(slippages) == 3  # 3 done entries
        assert all(isinstance(s, SlippageDetail) for s in slippages)

    def test_sorted_by_worst(self, opp_db):
        slippages = compute_slippage_analysis(opp_db_path=opp_db)
        # Should be sorted by slippage_pct descending
        for i in range(len(slippages) - 1):
            assert slippages[i].slippage_pct >= slippages[i + 1].slippage_pct

    def test_top_n(self, opp_db):
        slippages = compute_slippage_analysis(opp_db_path=opp_db, top_n=1)
        assert len(slippages) == 1

    def test_no_db(self, db_dir):
        slippages = compute_slippage_analysis(opp_db_path=db_dir / "x.db")
        assert slippages == []

    def test_slippage_values(self, opp_db):
        slippages = compute_slippage_analysis(opp_db_path=opp_db)
        for s in slippages:
            assert s.slippage_usd >= 0
            assert s.slippage_pct >= 0
            assert s.detail_id > 0

    def test_to_dict(self, opp_db):
        slippages = compute_slippage_analysis(opp_db_path=opp_db)
        d = slippages[0].to_dict()
        assert "slippage_usd" in d
        assert "execution_time_hours" in d


# ── Test Helpers ─────────────────────────────────────────────────────

class TestExecTimeHelper:
    def test_valid_timestamps(self):
        t1 = "2026-03-25T10:00:00Z"
        t2 = "2026-03-25T12:00:00Z"
        assert _compute_exec_time_hours(t1, t2) == pytest.approx(2.0, abs=0.01)

    def test_empty_timestamps(self):
        assert _compute_exec_time_hours("", "") == 0.0
        assert _compute_exec_time_hours("2026-03-25T10:00:00Z", "") == 0.0

    def test_invalid_timestamps(self):
        assert _compute_exec_time_hours("invalid", "also_invalid") == 0.0


# ── Test to_dict ─────────────────────────────────────────────────────

class TestReportToDict:
    def test_full_report(self, opp_db, ovr_db):
        report = compute_execution_quality(opp_db_path=opp_db, ovr_db_path=ovr_db)
        d = report.to_dict()
        assert "opportunity_metrics" in d
        assert "override_metrics" in d
        assert "total_executions" in d
        assert "combined_fill_rate" in d

    def test_metrics_to_dict(self):
        m = ExecutionMetrics(queue_type="test", total_queued=10, done_count=7)
        d = m.to_dict()
        assert d["queue_type"] == "test"
        assert d["total_queued"] == 10
