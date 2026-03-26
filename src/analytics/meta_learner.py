"""Adaptive Signal Weighting (Meta-Learner) — learn which signals work best per context.

Tracks signal accuracy by regime, T-range, hotel, and season, then computes
dynamic weight adjustments as an overlay on top of the base 50/30/20 ensemble.

Key principle: The base weights in config/constants.py are NEVER changed.
This module computes a dynamic overlay that adjusts weights ±20% per context.

Approach:
  - Track signal accuracy by: regime, T-range, hotel, season
  - Compute context-specific weight adjustments
  - Consensus scoring: how many sub-signals agree?
  - Guardrail: weights stay within ±20% of base (30%-70% range for FC at 50%)

Storage: SQLite meta_learner.db for historical accuracy tracking.
This module is READ-ONLY on prediction data — it only writes to its own DB.
"""
from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from pathlib import Path

from config.constants import (
    ENSEMBLE_WEIGHT_FORWARD_CURVE,
    ENSEMBLE_WEIGHT_HISTORICAL,
    ENSEMBLE_WEIGHT_ML,
)

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

MAX_WEIGHT_DEVIATION = 0.20  # ±20% from base weights
MIN_SAMPLES_FOR_ADJUSTMENT = 20  # need 20+ observations to adjust
DECAY_FACTOR = 0.95  # exponential decay for older observations

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
META_DB_PATH = _DB_DIR / "meta_learner.db"

# T-range buckets
T_RANGES = {
    "short": (0, 7),
    "medium": (8, 21),
    "long": (22, 60),
    "very_long": (61, 999),
}

# Season buckets (month → season)
MONTH_TO_SEASON = {
    1: "winter", 2: "winter", 3: "spring", 4: "spring",
    5: "spring", 6: "summer", 7: "summer", 8: "summer",
    9: "fall", 10: "fall", 11: "fall", 12: "winter",
}


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class WeightAdjustment:
    """Dynamic weight adjustment for a specific context."""
    context: str = ""          # e.g. "regime=NORMAL,t_range=short"
    fc_weight: float = ENSEMBLE_WEIGHT_FORWARD_CURVE
    hist_weight: float = ENSEMBLE_WEIGHT_HISTORICAL
    ml_weight: float = ENSEMBLE_WEIGHT_ML
    adjustment_reason: str = ""
    samples: int = 0
    confidence: float = 0.0    # 0-1, how confident in the adjustment

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in asdict(self).items()}


@dataclass
class ConsensusScore:
    """How many sub-signals agree on direction."""
    detail_id: int = 0
    fc_signal: str = ""        # CALL/PUT/NONE from forward curve alone
    hist_signal: str = ""      # from historical alone
    ml_signal: str = ""        # from ML alone
    ensemble_signal: str = ""  # final combined signal
    agreement_count: int = 0   # how many agree (0-3)
    agreement_pct: float = 0.0 # agreement_count / 3
    unanimous: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetaLearnerReport:
    """Full meta-learner analysis report."""
    timestamp: str = ""
    base_weights: dict = field(default_factory=dict)

    # Context-specific adjustments
    by_regime: list[WeightAdjustment] = field(default_factory=list)
    by_t_range: list[WeightAdjustment] = field(default_factory=list)
    by_season: list[WeightAdjustment] = field(default_factory=list)

    # Consensus analysis
    avg_consensus: float = 0.0
    unanimous_pct: float = 0.0
    consensus_distribution: dict = field(default_factory=dict)  # {0: n, 1: n, 2: n, 3: n}

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "base_weights": self.base_weights,
            "by_regime": [a.to_dict() for a in self.by_regime],
            "by_t_range": [a.to_dict() for a in self.by_t_range],
            "by_season": [a.to_dict() for a in self.by_season],
            "avg_consensus": round(self.avg_consensus, 4),
            "unanimous_pct": round(self.unanimous_pct, 4),
            "consensus_distribution": self.consensus_distribution,
            "recommendations": self.recommendations,
        }


# ── Database ─────────────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS signal_accuracy (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id       INTEGER NOT NULL,
    hotel_id        INTEGER NOT NULL,
    signal_date     TEXT NOT NULL,
    regime          TEXT DEFAULT 'NORMAL',
    t_value         INTEGER DEFAULT 0,
    t_range         TEXT DEFAULT 'medium',
    season          TEXT DEFAULT 'winter',
    fc_signal       TEXT DEFAULT 'NONE',
    hist_signal     TEXT DEFAULT 'NONE',
    ml_signal       TEXT DEFAULT 'NONE',
    ensemble_signal TEXT DEFAULT 'NONE',
    actual_direction TEXT DEFAULT 'NONE',
    fc_correct      INTEGER DEFAULT 0,
    hist_correct    INTEGER DEFAULT 0,
    ml_correct      INTEGER DEFAULT 0,
    ensemble_correct INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sa_regime ON signal_accuracy(regime);
CREATE INDEX IF NOT EXISTS idx_sa_t_range ON signal_accuracy(t_range);
CREATE INDEX IF NOT EXISTS idx_sa_season ON signal_accuracy(season);
CREATE INDEX IF NOT EXISTS idx_sa_hotel ON signal_accuracy(hotel_id);
"""


@contextmanager
def _get_meta_db(db_path: Path | None = None):
    """Thread-safe connection to meta_learner.db."""
    path = db_path or META_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_meta_db(db_path: Path | None = None) -> None:
    """Create tables if they don't exist."""
    with _get_meta_db(db_path) as conn:
        conn.executescript(_CREATE_TABLES)


# ── Consensus Scoring ────────────────────────────────────────────────

def compute_consensus(analysis: dict) -> list[ConsensusScore]:
    """Compute consensus scores from analysis predictions.

    Checks how many sub-signals (FC, Historical, ML) agree on direction.

    Args:
        analysis: Full analysis dict with predictions.

    Returns:
        List of ConsensusScore per room.
    """
    predictions = analysis.get("predictions", {})
    results: list[ConsensusScore] = []

    for detail_id, pred in predictions.items():
        try:
            ensemble_signal = pred.get("option_signal", "NONE") or "NONE"

            # Extract per-source signals if available
            sources = pred.get("source_signals") or {}
            fc_signal = sources.get("forward_curve", ensemble_signal)
            hist_signal = sources.get("historical", "NONE")
            ml_signal = sources.get("ml", "NONE")

            # If no per-source breakdown, infer from probability direction
            if not sources:
                prob = pred.get("probability") or {}
                p_up = float(prob.get("up", 50)) / 100
                p_down = float(prob.get("down", 50)) / 100
                fc_signal = "CALL" if p_up > 0.6 else ("PUT" if p_down > 0.6 else "NONE")
                hist_signal = fc_signal  # same direction assumed
                ml_signal = fc_signal

            # Count agreements
            signals = [fc_signal, hist_signal, ml_signal]
            direction = _signal_direction(ensemble_signal)
            agreement = sum(1 for s in signals if _signal_direction(s) == direction)

            results.append(ConsensusScore(
                detail_id=int(detail_id),
                fc_signal=fc_signal,
                hist_signal=hist_signal,
                ml_signal=ml_signal,
                ensemble_signal=ensemble_signal,
                agreement_count=agreement,
                agreement_pct=agreement / 3.0,
                unanimous=(agreement == 3),
            ))
        except (ValueError, TypeError, KeyError):
            continue

    return results


def compute_meta_learner_report(
    analysis: dict,
    db_path: Path | None = None,
) -> MetaLearnerReport:
    """Full meta-learner report with weight adjustments and consensus.

    Args:
        analysis: Full analysis dict.
        db_path: Optional meta_learner.db path for accuracy history.

    Returns:
        MetaLearnerReport with context-specific adjustments.
    """
    report = MetaLearnerReport(
        timestamp=datetime.utcnow().isoformat() + "Z",
        base_weights={
            "forward_curve": ENSEMBLE_WEIGHT_FORWARD_CURVE,
            "historical": ENSEMBLE_WEIGHT_HISTORICAL,
            "ml": ENSEMBLE_WEIGHT_ML,
        },
    )

    # Consensus analysis
    consensus_scores = compute_consensus(analysis)
    if consensus_scores:
        report.avg_consensus = sum(c.agreement_pct for c in consensus_scores) / len(consensus_scores)
        report.unanimous_pct = sum(1 for c in consensus_scores if c.unanimous) / len(consensus_scores)

        dist = {0: 0, 1: 0, 2: 0, 3: 0}
        for c in consensus_scores:
            dist[c.agreement_count] = dist.get(c.agreement_count, 0) + 1
        report.consensus_distribution = dist

    # Context-specific analysis from predictions
    predictions = analysis.get("predictions", {})
    regime_stats = _group_accuracy_by(predictions, "regime")
    t_range_stats = _group_accuracy_by_t_range(predictions)
    season_stats = _group_accuracy_by_season(predictions)

    report.by_regime = [_make_adjustment(ctx, stats) for ctx, stats in regime_stats.items()]
    report.by_t_range = [_make_adjustment(ctx, stats) for ctx, stats in t_range_stats.items()]
    report.by_season = [_make_adjustment(ctx, stats) for ctx, stats in season_stats.items()]

    # Recommendations
    if report.unanimous_pct < 0.3:
        report.recommendations.append(
            "Low consensus (<30% unanimous) — signals are diverging, "
            "consider reducing position sizes"
        )
    if report.avg_consensus > 0.8:
        report.recommendations.append(
            "High consensus (>80%) — strong signal agreement, "
            "higher confidence in current signals"
        )

    return report


def get_weight_for_context(
    regime: str = "NORMAL",
    t_value: int = 14,
    season: str | None = None,
    db_path: Path | None = None,
) -> WeightAdjustment:
    """Get adjusted weights for a specific context.

    Falls back to base weights if insufficient data.

    Args:
        regime: Current regime (NORMAL, TRENDING_UP, etc.)
        t_value: Days to check-in
        season: Season name (auto-detected if None)
        db_path: Optional meta_learner.db path

    Returns:
        WeightAdjustment with context-specific weights
    """
    if season is None:
        season = MONTH_TO_SEASON.get(date.today().month, "winter")

    t_range = _get_t_range(t_value)

    # Try to load from DB
    init_meta_db(db_path)
    with _get_meta_db(db_path) as conn:
        rows = conn.execute("""
            SELECT fc_correct, hist_correct, ml_correct, ensemble_correct
            FROM signal_accuracy
            WHERE regime = ? AND t_range = ? AND season = ?
            ORDER BY created_at DESC LIMIT 100
        """, (regime, t_range, season)).fetchall()

    if len(rows) < MIN_SAMPLES_FOR_ADJUSTMENT:
        return WeightAdjustment(
            context=f"regime={regime},t_range={t_range},season={season}",
            fc_weight=ENSEMBLE_WEIGHT_FORWARD_CURVE,
            hist_weight=ENSEMBLE_WEIGHT_HISTORICAL,
            ml_weight=ENSEMBLE_WEIGHT_ML,
            adjustment_reason="insufficient_data",
            samples=len(rows),
            confidence=0.0,
        )

    # Compute accuracy rates with exponential decay
    fc_score = 0.0
    hist_score = 0.0
    ml_score = 0.0
    total_weight = 0.0

    for i, row in enumerate(rows):
        w = DECAY_FACTOR ** i
        fc_score += int(row["fc_correct"]) * w
        hist_score += int(row["hist_correct"]) * w
        ml_score += int(row["ml_correct"]) * w
        total_weight += w

    if total_weight > 0:
        fc_acc = fc_score / total_weight
        hist_acc = hist_score / total_weight
        ml_acc = ml_score / total_weight
    else:
        fc_acc = hist_acc = ml_acc = 0.5

    # Adjust weights proportionally, clamped to ±MAX_WEIGHT_DEVIATION
    total_acc = fc_acc + hist_acc + ml_acc
    if total_acc > 0:
        fc_w = _clamp_weight(fc_acc / total_acc, ENSEMBLE_WEIGHT_FORWARD_CURVE)
        hist_w = _clamp_weight(hist_acc / total_acc, ENSEMBLE_WEIGHT_HISTORICAL)
        ml_w = _clamp_weight(ml_acc / total_acc, ENSEMBLE_WEIGHT_ML)
    else:
        fc_w = ENSEMBLE_WEIGHT_FORWARD_CURVE
        hist_w = ENSEMBLE_WEIGHT_HISTORICAL
        ml_w = ENSEMBLE_WEIGHT_ML

    # Normalize to sum to 1.0
    total_w = fc_w + hist_w + ml_w
    if total_w > 0:
        fc_w /= total_w
        hist_w /= total_w
        ml_w /= total_w

    return WeightAdjustment(
        context=f"regime={regime},t_range={t_range},season={season}",
        fc_weight=fc_w,
        hist_weight=hist_w,
        ml_weight=ml_w,
        adjustment_reason="accuracy_based",
        samples=len(rows),
        confidence=min(1.0, len(rows) / 100),
    )


# ── Internal Helpers ─────────────────────────────────────────────────

def _signal_direction(signal: str) -> str:
    """Normalize signal to direction."""
    if signal in ("CALL", "STRONG_CALL"):
        return "UP"
    elif signal in ("PUT", "STRONG_PUT"):
        return "DOWN"
    return "FLAT"


def _get_t_range(t: int) -> str:
    """Map T value to range bucket."""
    for name, (lo, hi) in T_RANGES.items():
        if lo <= t <= hi:
            return name
    return "very_long"


def _clamp_weight(proposed: float, base: float) -> float:
    """Clamp weight to base ± MAX_WEIGHT_DEVIATION."""
    lo = max(0.01, base - MAX_WEIGHT_DEVIATION)
    hi = min(0.99, base + MAX_WEIGHT_DEVIATION)
    return max(lo, min(hi, proposed))


def _group_accuracy_by(
    predictions: dict, key: str
) -> dict[str, dict[str, int]]:
    """Group predictions by a regime-like key and count signal directions."""
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "call": 0, "put": 0, "none": 0})

    for detail_id, pred in predictions.items():
        regime_info = pred.get("regime") or {}
        group_val = str(regime_info.get(key, "NORMAL"))
        signal = pred.get("option_signal", "NONE") or "NONE"

        groups[group_val]["total"] += 1
        if signal in ("CALL", "STRONG_CALL"):
            groups[group_val]["call"] += 1
        elif signal in ("PUT", "STRONG_PUT"):
            groups[group_val]["put"] += 1
        else:
            groups[group_val]["none"] += 1

    return dict(groups)


def _group_accuracy_by_t_range(predictions: dict) -> dict[str, dict[str, int]]:
    """Group predictions by T-range bucket."""
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "call": 0, "put": 0, "none": 0})

    for detail_id, pred in predictions.items():
        t = int(pred.get("days_to_checkin", 0) or 0)
        t_range = _get_t_range(t)
        signal = pred.get("option_signal", "NONE") or "NONE"

        groups[t_range]["total"] += 1
        if signal in ("CALL", "STRONG_CALL"):
            groups[t_range]["call"] += 1
        elif signal in ("PUT", "STRONG_PUT"):
            groups[t_range]["put"] += 1
        else:
            groups[t_range]["none"] += 1

    return dict(groups)


def _group_accuracy_by_season(predictions: dict) -> dict[str, dict[str, int]]:
    """Group predictions by season."""
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "call": 0, "put": 0, "none": 0})

    for detail_id, pred in predictions.items():
        checkin = pred.get("date_from", "")
        season = "unknown"
        if checkin and len(checkin) >= 7:
            try:
                month = int(checkin[5:7])
                season = MONTH_TO_SEASON.get(month, "unknown")
            except (ValueError, IndexError):
                pass

        signal = pred.get("option_signal", "NONE") or "NONE"
        groups[season]["total"] += 1
        if signal in ("CALL", "STRONG_CALL"):
            groups[season]["call"] += 1
        elif signal in ("PUT", "STRONG_PUT"):
            groups[season]["put"] += 1
        else:
            groups[season]["none"] += 1

    return dict(groups)


def _make_adjustment(context: str, stats: dict) -> WeightAdjustment:
    """Create a WeightAdjustment from group stats."""
    total = stats.get("total", 0)
    calls = stats.get("call", 0)
    puts = stats.get("put", 0)

    # If mostly CALLs in this context, FC tends to be more useful
    # If balanced, keep base weights
    fc_w = ENSEMBLE_WEIGHT_FORWARD_CURVE
    hist_w = ENSEMBLE_WEIGHT_HISTORICAL
    ml_w = ENSEMBLE_WEIGHT_ML

    reason = "base_weights"
    if total >= MIN_SAMPLES_FOR_ADJUSTMENT:
        call_ratio = calls / total if total > 0 else 0.5
        # More directional signals → FC is doing more work
        if call_ratio > 0.6 or call_ratio < 0.4:
            fc_w += 0.05
            hist_w -= 0.025
            ml_w -= 0.025
            reason = "directional_bias"

    return WeightAdjustment(
        context=context,
        fc_weight=fc_w,
        hist_weight=hist_w,
        ml_weight=ml_w,
        adjustment_reason=reason,
        samples=total,
        confidence=min(1.0, total / 100),
    )
