"""Backtest Engine — analyze historical signal accuracy from prediction_log.

Computes PnL, win rates, Sharpe ratios, and other metrics from the
prediction_log SQLite table (see accuracy_tracker.py for schema).

Each logged prediction becomes a trade:
  - CALL: entry at predicted_price, profit if actual > predicted
  - PUT: entry at predicted_price, profit if actual < predicted

Usage:
    from src.analytics.backtest_engine import run_backtest, BacktestReport

    report = run_backtest(days_back=90)
    print(f"Win rate: {report.win_rate:.1%}")
    print(f"Total PnL: ${report.total_pnl:.2f}")
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "prediction_tracker.db"


@dataclass
class BacktestTrade:
    """A single backtest trade from prediction_log."""

    detail_id: int
    hotel_id: int
    hotel_name: str
    signal: str  # CALL or PUT
    entry_date: str  # prediction_ts
    entry_price: float  # predicted_price
    exit_date: str  # checkin_date
    exit_price: float  # actual_price
    pnl: float
    pnl_pct: float
    holding_days: int
    correct: bool  # did signal direction match actual price movement?

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestReport:
    """Summary of backtest results."""

    period: str  # e.g. "2025-01-01 to 2025-12-31"
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # [0, 1]
    total_pnl: float
    avg_pnl_per_trade: float
    sharpe_ratio: float
    max_drawdown: float
    avg_holding_days: float
    by_signal: dict = field(default_factory=dict)  # {CALL: {...}, PUT: {...}}
    by_hotel: dict = field(default_factory=dict)  # {hotel_id: {...}}
    trades: list[BacktestTrade] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 2),
            "avg_pnl_per_trade": round(self.avg_pnl_per_trade, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "avg_holding_days": round(self.avg_holding_days, 2),
            "by_signal": self.by_signal,
            "by_hotel": self.by_hotel,
            "trades": [t.to_dict() for t in self.trades],
        }


def run_backtest(
    days_back: int = 90,
    db_path: Path | None = None,
) -> BacktestReport:
    """Run backtest on historical signals from prediction_log.

    Uses the accuracy tracker's prediction_log table which stores:
    - predicted signal (CALL/PUT/NEUTRAL)
    - predicted price
    - actual price (scored after check-in date passes)

    For each scored prediction:
    - CALL trade: profit if actual > predicted, loss if actual < predicted
    - PUT trade: profit if actual < predicted, loss if actual > predicted
    - NEUTRAL: excluded from backtest

    Args:
        days_back: How many days back to look (default 90).
        db_path: Optional custom prediction_tracker.db path.

    Returns:
        BacktestReport with trades, metrics, and aggregations.
    """
    path = db_path or DB_PATH

    # Check if database exists
    if not path.exists():
        logger.warning("Prediction tracker DB not found at %s", path)
        return _empty_report(days_back)

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row

        # Query scored predictions from the lookback period
        cutoff_ts = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

        query = """
            SELECT
                id,
                room_id AS detail_id,
                hotel_id,
                prediction_ts,
                checkin_date,
                predicted_price,
                predicted_signal,
                actual_price,
                actual_signal,
                signal_correct
            FROM prediction_log
            WHERE scored_at IS NOT NULL
              AND prediction_ts > ?
              AND predicted_signal IN ('CALL', 'PUT')
              AND actual_price IS NOT NULL
              AND predicted_price > 0
              AND actual_price > 0
            ORDER BY prediction_ts ASC
        """

        df = pd.read_sql_query(query, conn, params=(cutoff_ts,))
        conn.close()

        if df.empty:
            logger.info("No scored predictions in prediction_log for backtest")
            return _empty_report(days_back)

        # Convert date columns
        df["prediction_ts"] = pd.to_datetime(df["prediction_ts"])
        df["checkin_date"] = pd.to_datetime(df["checkin_date"])

        # Build trades
        trades: list[BacktestTrade] = []
        pnls: list[float] = []

        for _, row in df.iterrows():
            detail_id = int(row["detail_id"])
            hotel_id = int(row["hotel_id"])
            signal = str(row["predicted_signal"])
            predicted_price = float(row["predicted_price"])
            actual_price = float(row["actual_price"])
            holding_days = max(1, (row["checkin_date"] - row["prediction_ts"]).days)

            # Calculate PnL
            if signal == "CALL":
                # CALL: profit if actual > predicted
                pnl = actual_price - predicted_price
                correct = actual_price > predicted_price
            elif signal == "PUT":
                # PUT: profit if actual < predicted
                pnl = predicted_price - actual_price
                correct = actual_price < predicted_price
            else:
                continue

            pnl_pct = (pnl / predicted_price) * 100

            # Get hotel name (with fallback)
            hotel_name = f"Hotel {hotel_id}"

            trade = BacktestTrade(
                detail_id=detail_id,
                hotel_id=hotel_id,
                hotel_name=hotel_name,
                signal=signal,
                entry_date=row["prediction_ts"].isoformat(),
                entry_price=predicted_price,
                exit_date=row["checkin_date"].isoformat(),
                exit_price=actual_price,
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                holding_days=holding_days,
                correct=correct,
            )
            trades.append(trade)
            pnls.append(pnl)

        if not trades:
            return _empty_report(days_back)

        # Compute aggregated metrics
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        losing_trades = sum(1 for t in trades if t.pnl <= 0)
        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0
        avg_holding = np.mean([t.holding_days for t in trades])

        # Sharpe ratio (assuming 0% risk-free rate, daily periods)
        pnl_array = np.array(pnls)
        sharpe = _compute_sharpe(pnl_array)

        # Max drawdown
        max_dd = _compute_max_drawdown(pnl_array)

        # Period string
        min_date = min(t.entry_date for t in trades)
        max_date = max(t.exit_date for t in trades)
        period = f"{min_date[:10]} to {max_date[:10]}"

        # Aggregate by signal
        by_signal = {}
        for sig in ["CALL", "PUT"]:
            sig_trades = [t for t in trades if t.signal == sig]
            if sig_trades:
                sig_wins = sum(1 for t in sig_trades if t.pnl > 0)
                by_signal[sig] = {
                    "count": len(sig_trades),
                    "winning": sig_wins,
                    "win_rate": round(sig_wins / len(sig_trades), 4) if sig_trades else 0,
                    "total_pnl": round(sum(t.pnl for t in sig_trades), 2),
                    "avg_pnl": round(sum(t.pnl for t in sig_trades) / len(sig_trades), 2),
                    "avg_pnl_pct": round(
                        np.mean([t.pnl_pct for t in sig_trades]),
                        2,
                    ),
                }

        # Aggregate by hotel
        by_hotel = {}
        for hotel_id in df["hotel_id"].unique():
            hotel_trades = [t for t in trades if t.hotel_id == hotel_id]
            if hotel_trades:
                hotel_wins = sum(1 for t in hotel_trades if t.pnl > 0)
                hotel_name = hotel_trades[0].hotel_name
                by_hotel[hotel_id] = {
                    "name": hotel_name,
                    "count": len(hotel_trades),
                    "winning": hotel_wins,
                    "win_rate": round(
                        hotel_wins / len(hotel_trades),
                        4,
                    ) if hotel_trades else 0,
                    "total_pnl": round(sum(t.pnl for t in hotel_trades), 2),
                    "avg_pnl": round(
                        sum(t.pnl for t in hotel_trades) / len(hotel_trades),
                        2,
                    ),
                }

        # Build report
        report = BacktestReport(
            period=period,
            total_trades=len(trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=winning_trades / len(trades) if trades else 0,
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            avg_holding_days=avg_holding,
            by_signal=by_signal,
            by_hotel=by_hotel,
            trades=trades,
        )

        logger.info(
            "Backtest complete: %d trades, %.1f%% win rate, $%.2f total PnL, Sharpe=%.2f",
            len(trades), report.win_rate * 100, total_pnl, sharpe,
        )

        return report

    except sqlite3.Error as e:
        logger.error("Database error in run_backtest: %s", e, exc_info=True)
        return _empty_report(days_back)
    except Exception as e:
        logger.error("Unexpected error in run_backtest: %s", e, exc_info=True)
        return _empty_report(days_back)


def get_backtest_summary(days_back: int = 90) -> dict:
    """Get backtest summary without detailed trade list.

    Returns metrics only for performance/API efficiency.
    """
    report = run_backtest(days_back)

    return {
        "period": report.period,
        "total_trades": report.total_trades,
        "winning_trades": report.winning_trades,
        "losing_trades": report.losing_trades,
        "win_rate": round(report.win_rate, 4),
        "total_pnl": round(report.total_pnl, 2),
        "avg_pnl_per_trade": round(report.avg_pnl_per_trade, 2),
        "sharpe_ratio": round(report.sharpe_ratio, 4),
        "max_drawdown": round(report.max_drawdown, 4),
        "avg_holding_days": round(report.avg_holding_days, 2),
        "by_signal": report.by_signal,
        "by_hotel": report.by_hotel,
    }


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _empty_report(days_back: int) -> BacktestReport:
    """Return zero-valued report for empty backtest."""
    now = datetime.utcnow()
    start = now - timedelta(days=days_back)
    period = f"{start.date()} to {now.date()}"

    return BacktestReport(
        period=period,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        win_rate=0,
        total_pnl=0,
        avg_pnl_per_trade=0,
        sharpe_ratio=0,
        max_drawdown=0,
        avg_holding_days=0,
        by_signal={},
        by_hotel={},
        trades=[],
    )


def _compute_sharpe(pnls: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Compute Sharpe ratio from PnL array.

    Assumes daily PnL observations.

    Args:
        pnls: Array of profit/loss values.
        risk_free_rate: Annual risk-free rate (default 0%).

    Returns:
        Sharpe ratio (annualized, assuming 252 trading days per year).
    """
    if len(pnls) < 2:
        return 0.0

    mean_pnl = np.mean(pnls)
    std_pnl = np.std(pnls)

    if std_pnl == 0:
        return 0.0

    # Annualize: sqrt(252) * (mean / std)
    daily_sharpe = (mean_pnl - risk_free_rate) / std_pnl
    annual_sharpe = daily_sharpe * np.sqrt(252)

    return float(annual_sharpe)


def _compute_max_drawdown(pnls: np.ndarray) -> float:
    """Compute maximum drawdown from cumulative PnL.

    Args:
        pnls: Array of profit/loss values in chronological order.

    Returns:
        Max drawdown as fraction (negative value, e.g., -0.15 for -15%).
    """
    if len(pnls) == 0:
        return 0.0

    cumsum = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumsum)
    drawdown = (cumsum - running_max) / np.maximum(np.abs(running_max), 1e-8)
    max_dd = np.min(drawdown)

    return float(max_dd)
