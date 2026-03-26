"""Unit tests for backtest_engine module."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from src.analytics.backtest_engine import (
    BacktestTrade,
    BacktestReport,
    run_backtest,
    get_backtest_summary,
    _compute_sharpe,
    _compute_max_drawdown,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary prediction_tracker.db with sample data."""
    db_path = tmp_path / "prediction_tracker.db"

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_log (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id               INTEGER NOT NULL,
            hotel_id              INTEGER NOT NULL,
            prediction_ts         TEXT    NOT NULL,
            checkin_date          TEXT    NOT NULL,
            t_at_prediction       INTEGER NOT NULL,
            predicted_price       REAL    NOT NULL,
            predicted_signal      TEXT,
            predicted_confidence  REAL,
            actual_price          REAL,
            actual_signal         TEXT,
            error_pct             REAL,
            error_abs             REAL,
            signal_correct        INTEGER,
            scored_at             TEXT
        )
    """)

    now = datetime.utcnow()

    # Insert sample trades: mix of CALL and PUT, winning and losing
    predictions = [
        # CALL trades
        (1, 100, (now - timedelta(days=10)).isoformat(), (now - timedelta(days=3)).isoformat(), 7, 200.0, "CALL", 0.75, 210.0, "CALL", 5.0, 10.0, 1, now.isoformat()),
        (2, 100, (now - timedelta(days=9)).isoformat(), (now - timedelta(days=2)).isoformat(), 7, 250.0, "CALL", 0.80, 240.0, "PUT", -4.0, -10.0, 0, now.isoformat()),
        (3, 101, (now - timedelta(days=15)).isoformat(), (now - timedelta(days=8)).isoformat(), 7, 300.0, "CALL", 0.70, 315.0, "CALL", 5.0, 15.0, 1, now.isoformat()),
        # PUT trades
        (4, 101, (now - timedelta(days=12)).isoformat(), (now - timedelta(days=5)).isoformat(), 7, 350.0, "PUT", 0.65, 330.0, "PUT", -5.7, -20.0, 1, now.isoformat()),
        (5, 102, (now - timedelta(days=8)).isoformat(), (now - timedelta(days=1)).isoformat(), 7, 150.0, "PUT", 0.60, 160.0, "CALL", 6.7, 10.0, 0, now.isoformat()),
        (6, 100, (now - timedelta(days=20)).isoformat(), (now - timedelta(days=13)).isoformat(), 7, 180.0, "CALL", 0.75, 195.0, "CALL", 8.3, 15.0, 1, now.isoformat()),
    ]

    conn.executemany(
        """INSERT INTO prediction_log
           (room_id, hotel_id, prediction_ts, checkin_date, t_at_prediction,
            predicted_price, predicted_signal, predicted_confidence,
            actual_price, actual_signal, error_pct, error_abs,
            signal_correct, scored_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        predictions,
    )

    conn.commit()
    conn.close()

    return db_path


class TestBacktestTrade:
    """Test BacktestTrade dataclass."""

    def test_trade_creation(self):
        """Test creating a BacktestTrade."""
        trade = BacktestTrade(
            detail_id=1,
            hotel_id=100,
            hotel_name="Hotel A",
            signal="CALL",
            entry_date="2025-03-15T10:00:00",
            entry_price=200.0,
            exit_date="2025-03-22T10:00:00",
            exit_price=210.0,
            pnl=10.0,
            pnl_pct=5.0,
            holding_days=7,
            correct=True,
        )

        assert trade.detail_id == 1
        assert trade.hotel_id == 100
        assert trade.signal == "CALL"
        assert trade.pnl == 10.0
        assert trade.pnl_pct == 5.0

    def test_trade_to_dict(self):
        """Test converting BacktestTrade to dict."""
        trade = BacktestTrade(
            detail_id=1,
            hotel_id=100,
            hotel_name="Hotel A",
            signal="CALL",
            entry_date="2025-03-15T10:00:00",
            entry_price=200.0,
            exit_date="2025-03-22T10:00:00",
            exit_price=210.0,
            pnl=10.0,
            pnl_pct=5.0,
            holding_days=7,
            correct=True,
        )

        trade_dict = trade.to_dict()

        assert isinstance(trade_dict, dict)
        assert trade_dict["detail_id"] == 1
        assert trade_dict["pnl"] == 10.0


class TestBacktestReport:
    """Test BacktestReport dataclass."""

    def test_report_creation(self):
        """Test creating a BacktestReport."""
        report = BacktestReport(
            period="2025-01-01 to 2025-03-31",
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=0.60,
            total_pnl=1500.0,
            avg_pnl_per_trade=15.0,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            avg_holding_days=7.5,
            by_signal={"CALL": {"count": 50, "win_rate": 0.65}},
            by_hotel={100: {"count": 30, "win_rate": 0.60}},
            trades=[],
        )

        assert report.total_trades == 100
        assert report.win_rate == 0.60
        assert report.total_pnl == 1500.0

    def test_report_to_dict(self):
        """Test converting BacktestReport to dict."""
        report = BacktestReport(
            period="2025-01-01 to 2025-03-31",
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=0.60,
            total_pnl=1500.0,
            avg_pnl_per_trade=15.0,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            avg_holding_days=7.5,
            trades=[],
        )

        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert report_dict["total_trades"] == 100
        assert report_dict["win_rate"] == 0.6
        assert "sharpe_ratio" in report_dict


class TestRunBacktest:
    """Test run_backtest function."""

    def test_backtest_with_sample_data(self, temp_db):
        """Test backtest with sample data."""
        report = run_backtest(days_back=30, db_path=temp_db)

        assert report.total_trades > 0
        assert report.winning_trades + report.losing_trades == report.total_trades
        assert 0 <= report.win_rate <= 1
        assert report.period is not None

    def test_backtest_separates_call_put(self, temp_db):
        """Test that backtest correctly separates CALL and PUT trades."""
        report = run_backtest(days_back=30, db_path=temp_db)

        assert "CALL" in report.by_signal or "PUT" in report.by_signal
        if "CALL" in report.by_signal:
            assert report.by_signal["CALL"]["count"] > 0
        if "PUT" in report.by_signal:
            assert report.by_signal["PUT"]["count"] > 0

    def test_backtest_calculates_pnl(self, temp_db):
        """Test that PnL is correctly calculated."""
        report = run_backtest(days_back=30, db_path=temp_db)

        if report.trades:
            # At least one trade should exist
            trade = report.trades[0]
            assert trade.pnl is not None
            assert trade.pnl_pct is not None

            # Verify PnL calculation for CALL trades
            if trade.signal == "CALL":
                expected_pnl = trade.exit_price - trade.entry_price
                assert abs(trade.pnl - expected_pnl) < 0.01

            # Verify PnL calculation for PUT trades
            if trade.signal == "PUT":
                expected_pnl = trade.entry_price - trade.exit_price
                assert abs(trade.pnl - expected_pnl) < 0.01

    def test_backtest_empty_database(self, tmp_path):
        """Test backtest with empty/nonexistent database."""
        db_path = tmp_path / "empty.db"

        report = run_backtest(days_back=90, db_path=db_path)

        assert report.total_trades == 0
        assert report.winning_trades == 0
        assert report.win_rate == 0
        assert len(report.trades) == 0

    def test_backtest_nosuchfile(self, tmp_path):
        """Test backtest with nonexistent database."""
        db_path = tmp_path / "nonexistent.db"

        report = run_backtest(days_back=90, db_path=db_path)

        assert report.total_trades == 0
        assert len(report.trades) == 0

    def test_backtest_by_hotel(self, temp_db):
        """Test that backtest aggregates by hotel correctly."""
        report = run_backtest(days_back=30, db_path=temp_db)

        if report.by_hotel:
            for hotel_id, hotel_stats in report.by_hotel.items():
                assert "count" in hotel_stats
                assert "win_rate" in hotel_stats
                assert "total_pnl" in hotel_stats
                assert hotel_stats["count"] > 0

    def test_backtest_win_rate_calculation(self, temp_db):
        """Test win rate is correctly calculated."""
        report = run_backtest(days_back=30, db_path=temp_db)

        if report.total_trades > 0:
            expected_wr = report.winning_trades / report.total_trades
            assert abs(report.win_rate - expected_wr) < 0.0001

    def test_backtest_days_filter(self, temp_db):
        """Test that days_back filter is respected."""
        # Get all trades
        report_all = run_backtest(days_back=365, db_path=temp_db)

        # Get only recent trades
        report_recent = run_backtest(days_back=5, db_path=temp_db)

        # Recent should have fewer or equal trades
        assert report_recent.total_trades <= report_all.total_trades


class TestGetBacktestSummary:
    """Test get_backtest_summary function."""

    def test_summary_without_trades(self, temp_db, monkeypatch):
        """Test summary generation."""
        # Monkeypatch DB_PATH to use temp database
        import src.analytics.backtest_engine
        monkeypatch.setattr(src.analytics.backtest_engine, "DB_PATH", temp_db)

        summary = get_backtest_summary(days_back=30)

        assert "period" in summary
        assert "total_trades" in summary
        assert "win_rate" in summary
        assert "total_pnl" in summary
        assert "sharpe_ratio" in summary
        assert "max_drawdown" in summary

    def test_summary_no_trades_in_db(self, tmp_path, monkeypatch):
        """Test summary when database is empty."""
        db_path = tmp_path / "empty.db"

        import src.analytics.backtest_engine
        monkeypatch.setattr(src.analytics.backtest_engine, "DB_PATH", db_path)

        summary = get_backtest_summary(days_back=90)

        assert summary["total_trades"] == 0
        assert summary["win_rate"] == 0
        assert summary["total_pnl"] == 0


class TestComputeSharpe:
    """Test _compute_sharpe helper."""

    def test_sharpe_zero_std(self):
        """Test Sharpe with zero standard deviation."""
        pnls = np.array([100.0, 100.0, 100.0])

        sharpe = _compute_sharpe(pnls)

        assert sharpe == 0.0

    def test_sharpe_positive_returns(self):
        """Test Sharpe with all positive returns."""
        pnls = np.array([10.0, 20.0, 15.0, 25.0, 30.0])

        sharpe = _compute_sharpe(pnls)

        assert sharpe > 0  # All positive should give positive Sharpe

    def test_sharpe_with_losses(self):
        """Test Sharpe with mixed returns."""
        pnls = np.array([10.0, -5.0, 15.0, -8.0, 20.0])

        sharpe = _compute_sharpe(pnls)

        # Should be finite
        assert np.isfinite(sharpe)

    def test_sharpe_single_value(self):
        """Test Sharpe with single value."""
        pnls = np.array([100.0])

        sharpe = _compute_sharpe(pnls)

        assert sharpe == 0.0


class TestComputeMaxDrawdown:
    """Test _compute_max_drawdown helper."""

    def test_max_drawdown_all_positive(self):
        """Test max drawdown with all positive returns."""
        pnls = np.array([10.0, 20.0, 30.0, 40.0])

        dd = _compute_max_drawdown(pnls)

        assert dd == 0.0  # No drawdown when all positive

    def test_max_drawdown_with_loss(self):
        """Test max drawdown with a loss."""
        pnls = np.array([100.0, -50.0, 50.0])

        dd = _compute_max_drawdown(pnls)

        assert dd < 0  # Drawdown should be negative

    def test_max_drawdown_severe_loss(self):
        """Test max drawdown with severe loss."""
        pnls = np.array([100.0, -100.0, 50.0])

        dd = _compute_max_drawdown(pnls)

        assert dd < -0.5  # More than 50% drawdown

    def test_max_drawdown_empty(self):
        """Test max drawdown with empty array."""
        pnls = np.array([])

        dd = _compute_max_drawdown(pnls)

        assert dd == 0.0

    def test_max_drawdown_monotonic_increase(self):
        """Test max drawdown with strictly increasing cumsum."""
        pnls = np.array([10.0, 20.0, 15.0, 25.0])

        dd = _compute_max_drawdown(pnls)

        assert dd == 0.0


class TestBacktestCorrectSignal:
    """Test correct signal detection in trades."""

    def test_call_trade_correct(self, temp_db):
        """Test that CALL trade correctness is calculated."""
        report = run_backtest(days_back=30, db_path=temp_db)

        call_trades = [t for t in report.trades if t.signal == "CALL"]
        if call_trades:
            for trade in call_trades:
                if trade.exit_price > trade.entry_price:
                    assert trade.correct is True
                else:
                    assert trade.correct is False

    def test_put_trade_correct(self, temp_db):
        """Test that PUT trade correctness is calculated."""
        report = run_backtest(days_back=30, db_path=temp_db)

        put_trades = [t for t in report.trades if t.signal == "PUT"]
        if put_trades:
            for trade in put_trades:
                if trade.exit_price < trade.entry_price:
                    assert trade.correct is True
                else:
                    assert trade.correct is False


class TestBacktestHoldingDays:
    """Test holding days calculation."""

    def test_holding_days_at_least_one(self, temp_db):
        """Test that holding_days is at least 1."""
        report = run_backtest(days_back=30, db_path=temp_db)

        for trade in report.trades:
            assert trade.holding_days >= 1


class TestBacktestIntegration:
    """Integration tests for backtest system."""

    def test_full_backtest_flow(self, temp_db):
        """Test complete backtest flow from DB to report."""
        # Run backtest
        report = run_backtest(days_back=30, db_path=temp_db)

        # Verify report structure
        assert report.total_trades > 0
        assert len(report.trades) > 0
        assert len(report.by_signal) > 0

        # Convert to dict
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        assert "trades" in report_dict
        assert isinstance(report_dict["trades"], list)

    def test_backtest_consistency(self, temp_db):
        """Test that backtest results are consistent across runs."""
        report1 = run_backtest(days_back=30, db_path=temp_db)
        report2 = run_backtest(days_back=30, db_path=temp_db)

        assert report1.total_trades == report2.total_trades
        assert report1.win_rate == report2.win_rate
        assert report1.total_pnl == report2.total_pnl
