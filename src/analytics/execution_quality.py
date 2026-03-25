"""Execution Quality & Slippage — track how well execution matches predictions.

Metrics:
  - Slippage: |predicted_price - actual_execution_price|
  - Fill rate: % of queued opportunities/overrides that became done
  - Rejection rate: % that failed
  - Timing score: Did we execute at optimal T?
  - Price improvement: actual vs predicted at queue time

Data source: opportunity_queue.db + override_queue.db
Compares predicted_price at queue time vs actual outcome.

This module is READ-ONLY — only reads from queue databases.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
OPPORTUNITY_DB_PATH = _DB_DIR / "opportunity_queue.db"
OVERRIDE_DB_PATH = _DB_DIR / "override_queue.db"


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class ExecutionMetrics:
    """Execution quality metrics for a queue type."""
    queue_type: str = ""          # "opportunity" or "override"
    total_queued: int = 0
    done_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    picked_count: int = 0

    fill_rate: float = 0.0       # done / total
    rejection_rate: float = 0.0  # failed / total

    # Slippage (CALL only: predicted vs buy price)
    avg_slippage_usd: float = 0.0
    avg_slippage_pct: float = 0.0
    max_slippage_usd: float = 0.0

    # Price improvement
    avg_price_improvement_usd: float = 0.0
    avg_price_improvement_pct: float = 0.0

    # Timing
    avg_execution_time_hours: float = 0.0  # created → done
    min_execution_time_hours: float = 0.0
    max_execution_time_hours: float = 0.0

    # By signal
    by_signal: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in asdict(self).items()}


@dataclass
class SlippageDetail:
    """Per-trade slippage analysis."""
    detail_id: int = 0
    hotel_id: int = 0
    hotel_name: str = ""
    signal: str = ""
    predicted_price: float = 0.0
    execution_price: float = 0.0
    slippage_usd: float = 0.0
    slippage_pct: float = 0.0
    execution_time_hours: float = 0.0

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in asdict(self).items()}


@dataclass
class ExecutionQualityReport:
    """Combined execution quality report."""
    timestamp: str = ""
    opportunity_metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    override_metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)

    # Combined metrics
    total_executions: int = 0
    combined_fill_rate: float = 0.0
    combined_rejection_rate: float = 0.0

    # Worst slippages
    worst_slippages: list[SlippageDetail] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "opportunity_metrics": self.opportunity_metrics.to_dict(),
            "override_metrics": self.override_metrics.to_dict(),
            "total_executions": self.total_executions,
            "combined_fill_rate": round(self.combined_fill_rate, 4),
            "combined_rejection_rate": round(self.combined_rejection_rate, 4),
            "worst_slippages": [s.to_dict() for s in self.worst_slippages],
        }


# ── Core Computation ─────────────────────────────────────────────────

def compute_execution_quality(
    opp_db_path: Path | None = None,
    ovr_db_path: Path | None = None,
) -> ExecutionQualityReport:
    """Compute execution quality from both queue databases.

    Returns:
        ExecutionQualityReport with metrics for opportunities and overrides.
    """
    report = ExecutionQualityReport(
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    opp_path = opp_db_path or OPPORTUNITY_DB_PATH
    ovr_path = ovr_db_path or OVERRIDE_DB_PATH

    if opp_path.exists():
        try:
            report.opportunity_metrics = _compute_opportunity_metrics(opp_path)
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Failed to compute opportunity metrics: %s", exc)

    if ovr_path.exists():
        try:
            report.override_metrics = _compute_override_metrics(ovr_path)
        except (sqlite3.Error, OSError) as exc:
            logger.warning("Failed to compute override metrics: %s", exc)

    # Combined
    total_q = (report.opportunity_metrics.total_queued +
               report.override_metrics.total_queued)
    total_done = (report.opportunity_metrics.done_count +
                  report.override_metrics.done_count)
    total_failed = (report.opportunity_metrics.failed_count +
                    report.override_metrics.failed_count)

    report.total_executions = total_done
    report.combined_fill_rate = total_done / total_q if total_q > 0 else 0.0
    report.combined_rejection_rate = total_failed / total_q if total_q > 0 else 0.0

    return report


def compute_slippage_analysis(
    opp_db_path: Path | None = None,
    top_n: int = 20,
) -> list[SlippageDetail]:
    """Compute per-trade slippage for opportunity queue.

    Slippage = |predicted_price - buy_price| / predicted_price
    Only applies to CALL positions (opportunities).

    Args:
        opp_db_path: Path to opportunity_queue.db
        top_n: Number of worst slippage trades to return

    Returns:
        List of SlippageDetail sorted by worst slippage first.
    """
    opp_path = opp_db_path or OPPORTUNITY_DB_PATH
    if not opp_path.exists():
        return []

    conn = sqlite3.connect(str(opp_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM opportunity_queue WHERE status = 'done'"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()

    slippages: list[SlippageDetail] = []

    for row in rows:
        r = dict(row)
        predicted = float(r.get("predicted_price", 0) or 0)
        buy_price = float(r.get("buy_price", 0) or 0)

        if predicted <= 0 or buy_price <= 0:
            continue

        slippage_usd = abs(predicted - buy_price)
        slippage_pct = (slippage_usd / predicted) * 100

        # Execution time
        exec_hours = _compute_exec_time_hours(
            r.get("created_at", ""), r.get("completed_at", "")
        )

        slippages.append(SlippageDetail(
            detail_id=r.get("detail_id", 0),
            hotel_id=r.get("hotel_id", 0),
            hotel_name=r.get("hotel_name", ""),
            signal=r.get("signal", "CALL"),
            predicted_price=predicted,
            execution_price=buy_price,
            slippage_usd=slippage_usd,
            slippage_pct=slippage_pct,
            execution_time_hours=exec_hours,
        ))

    # Sort by worst slippage
    slippages.sort(key=lambda s: s.slippage_pct, reverse=True)
    return slippages[:top_n]


# ── Internal Helpers ─────────────────────────────────────────────────

def _compute_opportunity_metrics(db_path: Path) -> ExecutionMetrics:
    """Compute metrics from opportunity_queue.db."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM opportunity_queue").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return ExecutionMetrics(queue_type="opportunity")
    conn.close()

    metrics = ExecutionMetrics(queue_type="opportunity")
    metrics.total_queued = len(rows)

    if not rows:
        return metrics

    done_rows = []
    exec_times: list[float] = []
    slippages_usd: list[float] = []
    slippages_pct: list[float] = []
    improvements_usd: list[float] = []
    improvements_pct: list[float] = []
    signal_counts: dict[str, dict[str, int]] = {}

    for row in rows:
        r = dict(row)
        status = r.get("status", "")
        signal = r.get("signal", "CALL")

        if signal not in signal_counts:
            signal_counts[signal] = {"total": 0, "done": 0, "failed": 0}
        signal_counts[signal]["total"] += 1

        if status == "done":
            metrics.done_count += 1
            signal_counts[signal]["done"] += 1
            done_rows.append(r)

            # Execution time
            hours = _compute_exec_time_hours(
                r.get("created_at", ""), r.get("completed_at", "")
            )
            if hours > 0:
                exec_times.append(hours)

            # Slippage: predicted vs actual buy price
            predicted = float(r.get("predicted_price", 0) or 0)
            buy_price = float(r.get("buy_price", 0) or 0)
            if predicted > 0 and buy_price > 0:
                slip_usd = abs(predicted - buy_price)
                slip_pct = (slip_usd / predicted) * 100
                slippages_usd.append(slip_usd)
                slippages_pct.append(slip_pct)

                # Price improvement: positive = we got a better price
                improvement = predicted - buy_price  # positive = we paid less
                improvements_usd.append(improvement)
                improvements_pct.append((improvement / predicted) * 100)

        elif status == "failed":
            metrics.failed_count += 1
            signal_counts[signal]["failed"] += 1
        elif status == "pending":
            metrics.pending_count += 1
        elif status == "picked":
            metrics.picked_count += 1

    # Rates
    if metrics.total_queued > 0:
        metrics.fill_rate = metrics.done_count / metrics.total_queued
        metrics.rejection_rate = metrics.failed_count / metrics.total_queued

    # Slippage stats
    if slippages_usd:
        metrics.avg_slippage_usd = sum(slippages_usd) / len(slippages_usd)
        metrics.avg_slippage_pct = sum(slippages_pct) / len(slippages_pct)
        metrics.max_slippage_usd = max(slippages_usd)

    # Price improvement
    if improvements_usd:
        metrics.avg_price_improvement_usd = sum(improvements_usd) / len(improvements_usd)
        metrics.avg_price_improvement_pct = sum(improvements_pct) / len(improvements_pct)

    # Timing
    if exec_times:
        metrics.avg_execution_time_hours = sum(exec_times) / len(exec_times)
        metrics.min_execution_time_hours = min(exec_times)
        metrics.max_execution_time_hours = max(exec_times)

    metrics.by_signal = signal_counts
    return metrics


def _compute_override_metrics(db_path: Path) -> ExecutionMetrics:
    """Compute metrics from override_queue.db."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM override_requests").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return ExecutionMetrics(queue_type="override")
    conn.close()

    metrics = ExecutionMetrics(queue_type="override")
    metrics.total_queued = len(rows)

    if not rows:
        return metrics

    exec_times: list[float] = []

    for row in rows:
        r = dict(row)
        status = r.get("status", "")

        if status == "done":
            metrics.done_count += 1
            hours = _compute_exec_time_hours(
                r.get("created_at", ""), r.get("completed_at", "")
            )
            if hours > 0:
                exec_times.append(hours)
        elif status == "failed":
            metrics.failed_count += 1
        elif status == "pending":
            metrics.pending_count += 1
        elif status == "picked":
            metrics.picked_count += 1

    if metrics.total_queued > 0:
        metrics.fill_rate = metrics.done_count / metrics.total_queued
        metrics.rejection_rate = metrics.failed_count / metrics.total_queued

    if exec_times:
        metrics.avg_execution_time_hours = sum(exec_times) / len(exec_times)
        metrics.min_execution_time_hours = min(exec_times)
        metrics.max_execution_time_hours = max(exec_times)

    return metrics


def _compute_exec_time_hours(created_at: str, completed_at: str) -> float:
    """Compute execution time in hours between two ISO timestamps."""
    if not created_at or not completed_at:
        return 0.0
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        delta = completed - created
        return max(0.0, delta.total_seconds() / 3600)
    except (ValueError, TypeError):
        return 0.0
