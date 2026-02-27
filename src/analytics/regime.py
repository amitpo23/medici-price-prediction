"""Regime detection -- is a room behaving normally or abnormally?

Compares observed price behavior against the decay curve's expectation.
Like a trading desk's regime filter that flags when an instrument
diverges from its expected term structure.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RegimeState:
    """Regime classification for a single room."""
    regime: str          # NORMAL | TRENDING_UP | TRENDING_DOWN | VOLATILE | STALE
    z_score: float       # Divergence from expected in std units
    divergence_pct: float  # Actual vs expected cumulative change
    alert_level: str     # none | watch | warning
    description: str

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "z_score": round(self.z_score, 2),
            "divergence_pct": round(self.divergence_pct, 2),
            "alert_level": self.alert_level,
            "description": self.description,
        }


_DEFAULT_REGIME = RegimeState(
    regime="NORMAL", z_score=0.0, divergence_pct=0.0,
    alert_level="none", description="Insufficient data for regime detection",
)


def detect_regime(
    detail_id: int,
    current_price: float,
    all_snapshots: pd.DataFrame,
    curve,
    category: str = "",
    board: str = "",
) -> RegimeState:
    """Detect the price regime for a room.

    Walks the decay curve from the first observed price/T to the current T,
    then compares the expected price to the actual price.

    Args:
        detail_id: Room detail ID.
        current_price: Latest observed price.
        all_snapshots: All price snapshots.
        curve: DecayCurve instance.
        category: Room category (lowercase).
        board: Room board (lowercase).

    Returns:
        RegimeState with regime classification.
    """
    history = all_snapshots[all_snapshots["detail_id"] == detail_id].copy()
    if len(history) < 2:
        return _DEFAULT_REGIME

    history = history.sort_values("snapshot_ts")
    history["snapshot_ts"] = pd.to_datetime(history["snapshot_ts"])

    first_price = float(history.iloc[0]["room_price"])
    if first_price <= 0:
        return _DEFAULT_REGIME

    # Compute actual cumulative change
    actual_change_pct = (current_price - first_price) / first_price * 100

    # We need to know T at first observation and T now to walk the curve
    # Since we may not have date_from in snapshots easily, use the
    # observation span to estimate how much the curve would predict
    first_ts = history.iloc[0]["snapshot_ts"]
    last_ts = history.iloc[-1]["snapshot_ts"]
    span_days = max((last_ts - first_ts).total_seconds() / 86400, 0.5)

    # Walk the decay curve over the same span
    # We approximate: sum of daily changes over span_days
    # Since we don't know exact T here, use the average daily change
    expected_daily = curve.global_mean_daily_pct
    cat_offset = curve.category_offsets.get(category.lower(), 0.0)
    board_offset = curve.board_offsets.get(board.lower(), 0.0)
    adj_daily = expected_daily + cat_offset + board_offset

    expected_change_pct = adj_daily * span_days
    divergence_pct = actual_change_pct - expected_change_pct

    # Expected volatility over the span
    expected_vol = curve.global_std_daily_pct * sqrt(max(span_days, 1))
    expected_vol = max(expected_vol, 0.5)

    z_score = divergence_pct / expected_vol

    # Check for stale prices (no movement across many scans)
    prices = history["room_price"].values.astype(float)
    price_std = float(np.std(prices))
    is_stale = len(prices) >= 16 and price_std < 0.01

    # Check for high volatility
    if len(prices) >= 4:
        recent_returns = np.diff(prices) / np.maximum(prices[:-1], 0.01) * 100
        recent_vol = float(np.std(recent_returns))
    else:
        recent_vol = 0.0

    expected_scan_vol = curve.global_std_daily_pct / 2.83  # daily to ~3h (sqrt(8))
    is_volatile = recent_vol > 2 * max(expected_scan_vol, 0.3)

    # Classify regime
    if is_stale:
        regime = "STALE"
        alert = "watch"
        desc = f"Price unchanged across {len(prices)} scans ({span_days:.0f} days)"
    elif is_volatile:
        regime = "VOLATILE"
        alert = "watch"
        desc = f"Scan volatility {recent_vol:.2f}% vs expected {expected_scan_vol:.2f}%"
    elif z_score > 2.0:
        regime = "TRENDING_UP"
        alert = "warning" if z_score > 3.0 else "watch"
        desc = f"Price {divergence_pct:+.1f}% above expected ({z_score:.1f} sigma)"
    elif z_score < -2.0:
        regime = "TRENDING_DOWN"
        alert = "warning" if z_score < -3.0 else "watch"
        desc = f"Price {divergence_pct:+.1f}% below expected ({z_score:.1f} sigma)"
    elif abs(z_score) > 1.0:
        regime = "NORMAL"
        alert = "none"
        direction = "above" if z_score > 0 else "below"
        desc = f"Slight divergence: {direction} expected by {abs(divergence_pct):.1f}%"
    else:
        regime = "NORMAL"
        alert = "none"
        desc = "Tracking within expected range"

    return RegimeState(
        regime=regime,
        z_score=z_score,
        divergence_pct=divergence_pct,
        alert_level=alert,
        description=desc,
    )
