"""Unit tests for position_tracker.py — Position Tracking & PnL."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.analytics.position_tracker import (
    Position,
    PnLSummary,
    init_positions_db,
    sync_positions_from_queues,
    update_positions_prices,
    get_positions,
    get_pnl_summary,
    CONCENTRATION_WARNING_PCT,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db_dir(tmp_path):
    """Temp directory for all test databases."""
    return tmp_path


@pytest.fixture
def positions_db(db_dir):
    """Initialized positions.db path."""
    path = db_dir / "positions.db"
    init_positions_db(path)
    return path


@pytest.fixture
def opp_db(db_dir):
    """Opportunity queue DB with test data."""
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
    now = datetime.utcnow().isoformat() + "Z"
    future = (date.today() + timedelta(days=14)).isoformat()
    past = (date.today() - timedelta(days=2)).isoformat()

    # Done CALL — future checkin (open position)
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, category, board, checkin_date,
         buy_price, push_price, predicted_price, profit_usd, signal,
         confidence, status, created_at, completed_at)
        VALUES (100, 1, 'Hotel Alpha', 'Standard', 'BB', ?, 150.0, 200.0,
                210.0, 60.0, 'CALL', 'High', 'done', ?, ?)
    """, (future, now, now))

    # Done CALL — past checkin (should close)
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, category, board, checkin_date,
         buy_price, push_price, predicted_price, profit_usd, signal,
         confidence, status, created_at, completed_at)
        VALUES (101, 1, 'Hotel Alpha', 'Deluxe', 'RO', ?, 200.0, 250.0,
                260.0, 60.0, 'CALL', 'Medium', 'done', ?, ?)
    """, (past, now, now))

    # Done CALL — hotel 2
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, category, board, checkin_date,
         buy_price, push_price, predicted_price, profit_usd, signal,
         confidence, status, created_at, completed_at)
        VALUES (200, 2, 'Hotel Beta', 'Standard', 'BB', ?, 180.0, 230.0,
                240.0, 60.0, 'STRONG_CALL', 'High', 'done', ?, ?)
    """, (future, now, now))

    # Pending (should NOT become a position)
    conn.execute("""
        INSERT INTO opportunity_queue
        (detail_id, hotel_id, hotel_name, category, board, checkin_date,
         buy_price, push_price, predicted_price, signal, status, created_at)
        VALUES (300, 3, 'Hotel Gamma', 'Standard', 'BB', ?, 100.0, 150.0,
                160.0, 'CALL', 'pending', ?)
    """, (future, now))

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def ovr_db(db_dir):
    """Override queue DB with test data."""
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
    now = datetime.utcnow().isoformat() + "Z"
    future = (date.today() + timedelta(days=10)).isoformat()

    # Done PUT
    conn.execute("""
        INSERT INTO override_requests
        (detail_id, hotel_id, hotel_name, category, board, checkin_date,
         current_price, discount_usd, target_price, signal, confidence,
         status, created_at, completed_at)
        VALUES (400, 1, 'Hotel Alpha', 'Superior', 'BB', ?, 300.0, 5.0,
                295.0, 'PUT', 'High', 'done', ?, ?)
    """, (future, now, now))

    conn.commit()
    conn.close()
    return path


# ── Test Init ────────────────────────────────────────────────────────

class TestInit:
    def test_init_creates_db(self, db_dir):
        path = db_dir / "test_positions.db"
        init_positions_db(path)
        assert path.exists()

    def test_init_creates_table(self, positions_db):
        conn = sqlite3.connect(str(positions_db))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "positions" in table_names

    def test_init_idempotent(self, positions_db):
        """Calling init twice doesn't error."""
        init_positions_db(positions_db)
        init_positions_db(positions_db)


# ── Test Sync ────────────────────────────────────────────────────────

class TestSync:
    def test_sync_opportunities(self, positions_db, opp_db, db_dir):
        result = sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db,
            ovr_db_path=db_dir / "nonexistent.db"
        )
        assert result["new_opportunities"] == 3  # 3 done entries
        assert result["new_overrides"] == 0

    def test_sync_overrides(self, positions_db, ovr_db, db_dir):
        result = sync_positions_from_queues(
            db_path=positions_db,
            opp_db_path=db_dir / "nonexistent.db",
            ovr_db_path=ovr_db
        )
        assert result["new_overrides"] == 1
        assert result["new_opportunities"] == 0

    def test_sync_both(self, positions_db, opp_db, ovr_db):
        result = sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        assert result["new_opportunities"] == 3
        assert result["new_overrides"] == 1

    def test_sync_idempotent(self, positions_db, opp_db, ovr_db):
        """Running sync twice doesn't duplicate."""
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        result = sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        assert result["new_opportunities"] == 0
        assert result["new_overrides"] == 0

    def test_sync_skips_pending(self, positions_db, opp_db, db_dir):
        """Pending queue entries are NOT imported."""
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db,
            ovr_db_path=db_dir / "nonexistent.db"
        )
        positions = get_positions(db_path=positions_db)
        detail_ids = [p.detail_id for p in positions]
        assert 300 not in detail_ids  # pending one


# ── Test Get Positions ───────────────────────────────────────────────

class TestGetPositions:
    def test_get_all(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        positions = get_positions(db_path=positions_db)
        assert len(positions) == 4  # 3 opps + 1 override

    def test_filter_by_hotel(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        hotel1 = get_positions(hotel_id=1, db_path=positions_db)
        assert len(hotel1) == 3  # 2 opps + 1 override

    def test_filter_by_signal(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        calls = get_positions(signal="CALL", db_path=positions_db)
        assert len(calls) == 3  # includes STRONG_CALL
        puts = get_positions(signal="PUT", db_path=positions_db)
        assert len(puts) == 1

    def test_position_fields(self, positions_db, opp_db, db_dir):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db,
            ovr_db_path=db_dir / "x.db"
        )
        positions = get_positions(db_path=positions_db)
        p = next(p for p in positions if p.detail_id == 100)
        assert p.source == "opportunity"
        assert p.hotel_name == "Hotel Alpha"
        assert p.entry_price == 150.0
        assert p.push_price == 200.0
        assert p.signal == "CALL"

    def test_empty_db(self, positions_db):
        positions = get_positions(db_path=positions_db)
        assert positions == []


# ── Test Update Prices ───────────────────────────────────────────────

class TestUpdatePrices:
    def test_update_unrealized_pnl(self, positions_db, opp_db, db_dir):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db,
            ovr_db_path=db_dir / "x.db"
        )
        analysis = {
            "predictions": {
                "100": {"current_price": 170.0},  # was 150 → +20 unrealized
                "200": {"current_price": 190.0},  # was 180 → +10 unrealized
            }
        }
        updated = update_positions_prices(analysis, db_path=positions_db)
        assert updated >= 2

        positions = get_positions(db_path=positions_db)
        p100 = next(p for p in positions if p.detail_id == 100)
        assert p100.current_price == 170.0
        assert p100.unrealized_pnl == 20.0  # CALL: 170 - 150

    def test_put_pnl_direction(self, positions_db, ovr_db, db_dir):
        """PUT positions profit when price goes DOWN."""
        sync_positions_from_queues(
            db_path=positions_db,
            opp_db_path=db_dir / "x.db",
            ovr_db_path=ovr_db
        )
        analysis = {
            "predictions": {
                "400": {"current_price": 280.0},  # was 295 target → profit of 15
            }
        }
        update_positions_prices(analysis, db_path=positions_db)
        positions = get_positions(db_path=positions_db)
        p400 = next(p for p in positions if p.detail_id == 400)
        assert p400.unrealized_pnl == 15.0  # PUT: 295 - 280

    def test_closes_past_checkin(self, positions_db, opp_db, db_dir):
        """Positions with past checkin_date get closed."""
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db,
            ovr_db_path=db_dir / "x.db"
        )
        analysis = {
            "predictions": {
                "101": {"current_price": 220.0},  # past checkin
            }
        }
        update_positions_prices(analysis, db_path=positions_db)
        positions = get_positions(db_path=positions_db)
        p101 = next(p for p in positions if p.detail_id == 101)
        assert p101.status == "CLOSED"
        assert p101.realized_pnl == 20.0  # 220 - 200

    def test_empty_analysis(self, positions_db):
        assert update_positions_prices({}, db_path=positions_db) == 0
        assert update_positions_prices({"predictions": {}}, db_path=positions_db) == 0


# ── Test PnL Summary ────────────────────────────────────────────────

class TestPnLSummary:
    def test_empty_summary(self, positions_db):
        summary = get_pnl_summary(db_path=positions_db)
        assert summary.total_positions == 0
        assert summary.total_pnl == 0.0

    def test_summary_with_positions(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        summary = get_pnl_summary(db_path=positions_db)
        assert summary.total_positions == 4
        assert summary.call_count == 3
        assert summary.put_count == 1
        assert summary.timestamp  # not empty

    def test_summary_hotel_breakdown(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        summary = get_pnl_summary(db_path=positions_db)
        assert len(summary.hotel_pnl) >= 2  # at least hotel 1 and 2

    def test_summary_filter_hotel(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        summary = get_pnl_summary(hotel_id=2, db_path=positions_db)
        assert summary.total_positions == 1
        assert summary.call_count == 1

    def test_win_loss_after_close(self, positions_db, opp_db, db_dir):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db,
            ovr_db_path=db_dir / "x.db"
        )
        # Close the past-checkin position with a profit
        analysis = {"predictions": {"101": {"current_price": 220.0}}}
        update_positions_prices(analysis, db_path=positions_db)

        summary = get_pnl_summary(db_path=positions_db)
        assert summary.closed_positions >= 1
        assert summary.winning_trades >= 1

    def test_to_dict(self, positions_db, opp_db, ovr_db):
        sync_positions_from_queues(
            db_path=positions_db, opp_db_path=opp_db, ovr_db_path=ovr_db
        )
        summary = get_pnl_summary(db_path=positions_db)
        d = summary.to_dict()
        assert "total_positions" in d
        assert "hotel_pnl" in d
        assert "warnings" in d


# ── Test Position.to_dict ────────────────────────────────────────────

class TestPositionModel:
    def test_to_dict(self):
        p = Position(
            detail_id=1, hotel_id=2, entry_price=100.0,
            unrealized_pnl=5.123456, status="OPEN"
        )
        d = p.to_dict()
        assert d["detail_id"] == 1
        assert d["unrealized_pnl"] == 5.12  # rounded to 2

    def test_defaults(self):
        p = Position()
        assert p.status == "OPEN"
        assert p.entry_price == 0.0
        assert p.signal == ""
