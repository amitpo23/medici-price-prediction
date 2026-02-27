"""Momentum indicators from real-time 3-hour price scans.

Computes velocity, acceleration, and compares observed momentum
to the expected behavior from the decay curve — like a trading
desk's momentum oscillator.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MomentumState:
    """Momentum indicators for a single room."""
    velocity_3h: float        # Latest scan-to-scan % change (per 3h)
    velocity_24h: float       # Mean daily rate over last ~24h
    velocity_72h: float       # Mean daily rate over last ~72h
    acceleration: float       # velocity_24h - velocity_72h
    momentum_vs_expected: float  # Observed daily rate minus curve's expected
    signal: str               # ACCELERATING_UP | ACCELERATING_DOWN | NORMAL | INSUFFICIENT_DATA
    strength: float           # 0.0 - 1.0

    def to_dict(self) -> dict:
        return {
            "velocity_3h": round(self.velocity_3h, 4),
            "velocity_24h": round(self.velocity_24h, 4),
            "velocity_72h": round(self.velocity_72h, 4),
            "acceleration": round(self.acceleration, 4),
            "momentum_vs_expected": round(self.momentum_vs_expected, 4),
            "signal": self.signal,
            "strength": round(self.strength, 2),
        }


_INSUFFICIENT = MomentumState(
    velocity_3h=0, velocity_24h=0, velocity_72h=0,
    acceleration=0, momentum_vs_expected=0,
    signal="INSUFFICIENT_DATA", strength=0,
)


def compute_momentum(
    detail_id: int,
    all_snapshots: pd.DataFrame,
    expected_daily_at_t: float = 0.0,
    vol_at_t: float = 1.0,
) -> MomentumState:
    """Compute momentum indicators for a room from its snapshot history.

    Args:
        detail_id: The room detail ID.
        all_snapshots: All collected snapshots (DataFrame with snapshot_ts, detail_id, room_price).
        expected_daily_at_t: The decay curve's expected daily % change at current T.
        vol_at_t: The decay curve's volatility at current T.

    Returns:
        MomentumState with velocity, acceleration, and signal classification.
    """
    history = all_snapshots[all_snapshots["detail_id"] == detail_id].copy()
    if len(history) < 2:
        return _INSUFFICIENT

    history = history.sort_values("snapshot_ts")
    history["snapshot_ts"] = pd.to_datetime(history["snapshot_ts"])

    prices = history["room_price"].values.astype(float)
    timestamps = history["snapshot_ts"].values

    # Compute per-scan % changes
    pct_changes = np.diff(prices) / np.maximum(prices[:-1], 0.01) * 100
    time_diffs_hours = (
        np.diff(timestamps).astype("timedelta64[s]").astype(float) / 3600
    )

    # Normalize to per-3-hour rates
    valid_mask = time_diffs_hours > 0.5  # at least 30min gap
    if not valid_mask.any():
        return _INSUFFICIENT

    hourly_rates = np.where(
        valid_mask,
        pct_changes / np.maximum(time_diffs_hours, 0.5) * 3,
        0.0,
    )

    # Latest 3h velocity
    velocity_3h = float(hourly_rates[-1]) if len(hourly_rates) >= 1 else 0.0

    # 24h velocity: mean over scans in last 24 hours
    last_ts = timestamps[-1]
    hours_from_last = (last_ts - timestamps[:-1]).astype("timedelta64[s]").astype(float) / 3600

    mask_24h = hours_from_last <= 24
    velocity_24h_3h = float(np.mean(hourly_rates[mask_24h])) if mask_24h.any() else velocity_3h

    # 72h velocity
    mask_72h = hours_from_last <= 72
    velocity_72h_3h = float(np.mean(hourly_rates[mask_72h])) if mask_72h.any() else velocity_24h_3h

    # Convert to daily equivalent (8 three-hour periods per day)
    velocity_24h_daily = velocity_24h_3h * 8
    velocity_72h_daily = velocity_72h_3h * 8

    # Acceleration: is momentum increasing or decreasing?
    acceleration = velocity_24h_daily - velocity_72h_daily

    # Compare to expected from decay curve
    observed_daily = velocity_24h_daily
    momentum_vs_expected = observed_daily - expected_daily_at_t

    # Classify signal
    vol = max(vol_at_t, 0.5)
    signal, strength = _classify_signal(momentum_vs_expected, acceleration, vol)

    return MomentumState(
        velocity_3h=velocity_3h,
        velocity_24h=velocity_24h_daily,
        velocity_72h=velocity_72h_daily,
        acceleration=acceleration,
        momentum_vs_expected=momentum_vs_expected,
        signal=signal,
        strength=strength,
    )


def _classify_signal(
    mom_vs_expected: float,
    acceleration: float,
    vol: float,
) -> tuple[str, float]:
    """Classify the momentum signal.

    Returns (signal_name, strength 0-1).
    """
    if abs(mom_vs_expected) > 2 * vol:
        if mom_vs_expected > 0:
            signal = "ACCELERATING_UP"
        else:
            signal = "ACCELERATING_DOWN"
        strength = min(abs(mom_vs_expected) / (3 * vol), 1.0)
        return signal, strength

    if abs(acceleration) > vol:
        if acceleration > 0:
            return "ACCELERATING", min(abs(acceleration) / (2 * vol), 0.5)
        return "DECELERATING", min(abs(acceleration) / (2 * vol), 0.5)

    return "NORMAL", 0.0
