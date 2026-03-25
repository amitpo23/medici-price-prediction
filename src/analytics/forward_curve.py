"""Forward Curve Engine -- algo-trading style price prediction.

Models hotel room prices like futures contracts:
- T = days to check-in (time to expiration)
- Decay curve = empirical expected daily price change at each T
- Forward curve = predicted price path from now to check-in

Built from historical scan-pair observations, smoothed with
Bayesian shrinkage and overlapping bins for robustness.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from math import exp, sqrt

import numpy as np
import pandas as pd

from config.constants import (
    MIN_VOLATILITY,
    BAYESIAN_K,
    MAX_PREDICTION_HORIZON,
    DATA_DENSITY_HIGH,
    DATA_DENSITY_MEDIUM,
    DEMAND_IMPACT_HIGH,
    DEMAND_IMPACT_LOW,
    COMPETITOR_IMPACT_MAX,
    CANCELLATION_IMPACT_MAX,
    PROVIDER_IMPACT_MAX,
    SEASONALITY_MULTIPLIER,
    MOMENTUM_DECAY_RATE,
    MOMENTUM_IMPACT_SCALE,
    EVENT_RAMP_DAYS,
    EVENT_TAPER_DAYS,
    DAILY_CHANGE_CAP,
    CI_Z_SCORE,
    DEMAND_ZONE_IMPACT_MAX,
    REBUY_SIGNAL_IMPACT_MAX,
    SEARCH_VOLUME_IMPACT_MAX,
)

logger = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class DecayCurvePoint:
    """One point on the empirical decay curve."""
    t: int
    n_observations: float  # effective weighted count
    mean_daily_pct: float
    median_daily_pct: float
    std_daily_pct: float
    p_up: float
    p_down: float
    p_stable: float


@dataclass
class DecayCurve:
    """Complete empirical decay curve indexed by T (days to check-in)."""
    points: dict[int, DecayCurvePoint] = field(default_factory=dict)
    category_offsets: dict[str, float] = field(default_factory=dict)
    board_offsets: dict[str, float] = field(default_factory=dict)
    global_mean_daily_pct: float = 0.0
    global_std_daily_pct: float = 1.0
    total_observations: int = 0
    total_tracks: int = 0
    max_t: int = MAX_PREDICTION_HORIZON

    def get_daily_change(self, t: int) -> float:
        """Expected daily % change at T days before check-in."""
        t = max(1, min(t, self.max_t))
        if t in self.points:
            return self.points[t].median_daily_pct
        # Interpolate from nearest points
        return self._interpolate("median_daily_pct", t)

    def get_volatility(self, t: int) -> float:
        """Daily volatility (std %) at T days before check-in."""
        t = max(1, min(t, self.max_t))
        if t in self.points:
            return max(self.points[t].std_daily_pct, _MIN_VOL)
        return max(self._interpolate("std_daily_pct", t), _MIN_VOL)

    def get_probabilities(self, t: int) -> dict:
        """Up/down/stable probabilities at T."""
        t = max(1, min(t, self.max_t))
        if t in self.points:
            p = self.points[t]
            return {"up": round(p.p_up, 1), "down": round(p.p_down, 1), "stable": round(p.p_stable, 1)}
        return {"up": 30.0, "down": 30.0, "stable": 40.0}

    def get_data_density(self, t: int) -> str:
        """How much data backs the curve at this T."""
        t = max(1, min(t, self.max_t))
        if t in self.points:
            n = self.points[t].n_observations
            if n >= DATA_DENSITY_HIGH:
                return "high"
            if n >= DATA_DENSITY_MEDIUM:
                return "medium"
            return "low"
        return "extrapolated"

    def _interpolate(self, attr: str, t: int) -> float:
        """Linear interpolation between nearest known points."""
        known = sorted(self.points.keys())
        if not known:
            return getattr(self, f"global_{attr}", 0.0) if "std" not in attr else _MIN_VOL

        if t <= known[0]:
            return getattr(self.points[known[0]], attr)
        if t >= known[-1]:
            return getattr(self.points[known[-1]], attr)

        # Find bracketing points
        lo = max(k for k in known if k <= t)
        hi = min(k for k in known if k >= t)
        if lo == hi:
            return getattr(self.points[lo], attr)

        lo_val = getattr(self.points[lo], attr)
        hi_val = getattr(self.points[hi], attr)
        frac = (t - lo) / (hi - lo)
        return lo_val + (hi_val - lo_val) * frac

    def to_summary(self) -> dict:
        """Compact summary for API/logging."""
        sample_ts = [1, 3, 7, 14, 21, 30, 45, 60, 90, 120]
        curve_snapshot = []
        for t in sample_ts:
            if t <= self.max_t:
                curve_snapshot.append({
                    "t": t,
                    "expected_daily_pct": round(self.get_daily_change(t), 4),
                    "volatility": round(self.get_volatility(t), 4),
                    "density": self.get_data_density(t),
                })
        return {
            "total_tracks": self.total_tracks,
            "total_observations": self.total_observations,
            "global_mean_daily_pct": round(self.global_mean_daily_pct, 4),
            "max_t": self.max_t,
            "category_offsets": {k: round(v, 4) for k, v in self.category_offsets.items()},
            "board_offsets": {k: round(v, 4) for k, v in self.board_offsets.items()},
            "curve_snapshot": curve_snapshot,
        }


@dataclass
class ForwardPoint:
    """One day on the predicted forward curve."""
    date: str
    t: int
    predicted_price: float
    daily_change_pct: float
    cumulative_change_pct: float
    lower_bound: float
    upper_bound: float
    volatility_at_t: float
    dow: str
    event_adj_pct: float = 0.0
    season_adj_pct: float = 0.0
    demand_adj_pct: float = 0.0
    momentum_adj_pct: float = 0.0
    weather_adj_pct: float = 0.0
    competitor_adj_pct: float = 0.0
    # Phase 2 enrichments (NEW — defaults preserve backward compat)
    demand_zone_adj_pct: float = 0.0
    rebuy_signal_adj_pct: float = 0.0
    search_volume_adj_pct: float = 0.0


@dataclass
class ForwardCurve:
    """Complete forward curve prediction for one room."""
    detail_id: int
    hotel_id: int
    category: str
    board: str
    current_price: float
    current_t: int
    points: list[ForwardPoint] = field(default_factory=list)
    curve_type: str = "empirical"
    confidence_quality: str = "medium"


# ── Constants ────────────────────────────────────────────────────────

_MIN_VOL = MIN_VOLATILITY
_BAYESIAN_K = BAYESIAN_K
_DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Bin configuration: (max_t, bin_width, step)
_BIN_CONFIG = [
    (30, 5, 1),
    (60, 7, 2),
    (90, 10, 3),
    (180, 14, 7),
]


# ── Decay Curve Builder ─────────────────────────────────────────────

def build_decay_curve(historical_df: pd.DataFrame) -> DecayCurve:
    """Build empirical decay curve from historical price tracks.

    Args:
        historical_df: DataFrame with columns: order_id, hotel_id,
            room_category, room_board, room_price, scan_date, date_from.

    Returns:
        DecayCurve with smoothed T-indexed expected changes.
    """
    if historical_df.empty or len(historical_df) < 50:
        logger.warning("Not enough data for decay curve (%d rows)", len(historical_df))
        return _default_curve()

    df = historical_df.copy()
    df["scan_date"] = pd.to_datetime(df["scan_date"])
    df["date_from_dt"] = pd.to_datetime(df["date_from"])
    df["room_price"] = pd.to_numeric(df["room_price"], errors="coerce")
    df = df.dropna(subset=["room_price", "scan_date", "date_from_dt"])

    # Extract T-observations from consecutive scan pairs
    observations = _extract_t_observations(df)

    if len(observations) < 20:
        logger.warning("Not enough T-observations (%d), using defaults", len(observations))
        return _default_curve()

    obs_df = pd.DataFrame(observations)
    logger.info(
        "Extracted %d T-observations from tracks (T range: %d-%d)",
        len(obs_df), int(obs_df["t"].min()), int(obs_df["t"].max()),
    )

    # Global statistics
    global_mean = float(obs_df["daily_pct"].mean())
    global_std = float(obs_df["daily_pct"].std()) if len(obs_df) > 1 else 1.0

    # Build binned + smoothed curve
    curve_points = _build_smoothed_points(obs_df, global_mean)

    # Category and board offsets
    cat_offsets = _compute_offsets(obs_df, "category", global_mean)
    board_offsets = _compute_offsets(obs_df, "board", global_mean)

    n_tracks = obs_df["track_id"].nunique()
    max_t = int(obs_df["t"].max())

    curve = DecayCurve(
        points=curve_points,
        category_offsets=cat_offsets,
        board_offsets=board_offsets,
        global_mean_daily_pct=round(global_mean, 4),
        global_std_daily_pct=round(global_std, 4),
        total_observations=len(obs_df),
        total_tracks=n_tracks,
        max_t=min(max_t, MAX_PREDICTION_HORIZON),
    )

    logger.info(
        "Decay curve built: %d tracks, %d observations, %d T-points, "
        "global mean %.4f%%/day, cat offsets: %s",
        n_tracks, len(obs_df), len(curve_points),
        global_mean, cat_offsets,
    )
    return curve


def _extract_t_observations(df: pd.DataFrame) -> list[dict]:
    """Extract daily-normalized price change observations at each T.

    For each historical track, takes consecutive scan pairs and computes
    the daily rate of change, assigned to the T at the midpoint.
    """
    observations = []
    tracks = df.groupby(["order_id", "hotel_id", "room_category", "room_board"])

    for key, grp in tracks:
        grp = grp.sort_values("scan_date")
        if len(grp) < 2:
            continue

        order_id, hotel_id, category, board = key
        track_id = f"{order_id}|{hotel_id}|{category}|{board}"
        date_from = grp.iloc[0]["date_from_dt"]

        prices = grp["room_price"].values
        dates = grp["scan_date"].values

        for i in range(1, len(grp)):
            price_prev = float(prices[i - 1])
            price_curr = float(prices[i])
            if price_prev <= 0:
                continue

            scan_prev = pd.Timestamp(dates[i - 1])
            scan_curr = pd.Timestamp(dates[i])
            gap_days = (scan_curr - scan_prev).total_seconds() / 86400

            if gap_days < 0.1:  # skip near-simultaneous scans
                continue

            # Daily normalized change
            pct_change = (price_curr - price_prev) / price_prev * 100
            daily_pct = pct_change / gap_days

            # Cap extreme outliers
            daily_pct = max(-DAILY_CHANGE_CAP, min(DAILY_CHANGE_CAP, daily_pct))

            # T at midpoint of observation window
            midpoint = scan_prev + (scan_curr - scan_prev) / 2
            t = max(1, int((date_from - midpoint).total_seconds() / 86400))

            # Weight: closer scans produce more reliable daily rates
            weight = 1.0 / (1.0 + 0.1 * gap_days)

            observations.append({
                "track_id": track_id,
                "t": t,
                "daily_pct": daily_pct,
                "weight": weight,
                "hotel_id": int(hotel_id),
                "category": str(category).lower(),
                "board": str(board).lower() if board else "unknown",
                "gap_days": gap_days,
            })

    return observations


def _build_smoothed_points(obs_df: pd.DataFrame, global_mean: float) -> dict[int, DecayCurvePoint]:
    """Build smoothed decay curve points using overlapping bins + Bayesian shrinkage."""
    points = {}
    max_t = int(obs_df["t"].max())

    # Generate bin centers using the config
    bin_centers = []
    for max_t_for_config, width, step in _BIN_CONFIG:
        prev_max = bin_centers[-1] if bin_centers else 0
        t = prev_max + step
        while t <= min(max_t_for_config, max_t):
            bin_centers.append(t)
            t += step

    for t_center in bin_centers:
        # Determine bin half-width based on T range
        half_width = _get_half_width(t_center)

        # Select observations within the bin
        mask = (obs_df["t"] >= t_center - half_width) & (obs_df["t"] <= t_center + half_width)
        subset = obs_df[mask]

        if len(subset) < 2:
            continue

        # Distance-weighted statistics
        distances = np.abs(subset["t"].values - t_center).astype(float)
        dist_weights = 1.0 / (1.0 + distances)
        scan_weights = subset["weight"].values
        weights = dist_weights * scan_weights

        vals = subset["daily_pct"].values
        w_sum = weights.sum()

        if w_sum < 0.01:
            continue

        # Weighted mean
        w_mean = float(np.average(vals, weights=weights))

        # Weighted std
        w_var = float(np.average((vals - w_mean) ** 2, weights=weights))
        w_std = max(sqrt(w_var), _MIN_VOL)

        # Median (unweighted, robust)
        w_median = float(np.median(vals))

        # Bayesian shrinkage toward global mean
        effective_n = float(w_sum)
        shrunk_mean = (effective_n * w_mean + _BAYESIAN_K * global_mean) / (effective_n + _BAYESIAN_K)
        shrunk_median = (effective_n * w_median + _BAYESIAN_K * global_mean) / (effective_n + _BAYESIAN_K)

        # Probabilities
        n_total = len(vals)
        p_up = float((vals > 0.1).sum()) / n_total * 100
        p_down = float((vals < -0.1).sum()) / n_total * 100
        p_stable = 100.0 - p_up - p_down

        points[t_center] = DecayCurvePoint(
            t=t_center,
            n_observations=round(effective_n, 1),
            mean_daily_pct=round(shrunk_mean, 4),
            median_daily_pct=round(shrunk_median, 4),
            std_daily_pct=round(w_std, 4),
            p_up=round(p_up, 1),
            p_down=round(p_down, 1),
            p_stable=round(p_stable, 1),
        )

    # Fill gaps via linear interpolation for integer T values
    if points:
        known_ts = sorted(points.keys())
        for t in range(known_ts[0], known_ts[-1] + 1):
            if t not in points:
                # Interpolate from neighbors
                lo = max(k for k in known_ts if k <= t)
                hi = min(k for k in known_ts if k >= t)
                if lo == hi:
                    continue
                frac = (t - lo) / (hi - lo)
                lo_p = points[lo]
                hi_p = points[hi]
                points[t] = DecayCurvePoint(
                    t=t,
                    n_observations=round(lo_p.n_observations * (1 - frac) + hi_p.n_observations * frac, 1),
                    mean_daily_pct=round(lo_p.mean_daily_pct * (1 - frac) + hi_p.mean_daily_pct * frac, 4),
                    median_daily_pct=round(lo_p.median_daily_pct * (1 - frac) + hi_p.median_daily_pct * frac, 4),
                    std_daily_pct=round(max(lo_p.std_daily_pct * (1 - frac) + hi_p.std_daily_pct * frac, _MIN_VOL), 4),
                    p_up=round(lo_p.p_up * (1 - frac) + hi_p.p_up * frac, 1),
                    p_down=round(lo_p.p_down * (1 - frac) + hi_p.p_down * frac, 1),
                    p_stable=round(lo_p.p_stable * (1 - frac) + hi_p.p_stable * frac, 1),
                )

    return points


def _get_half_width(t: int) -> int:
    """Get bin half-width based on T value."""
    if t <= 30:
        return 2
    if t <= 60:
        return 3
    if t <= 90:
        return 5
    return 7


def _compute_offsets(obs_df: pd.DataFrame, group_col: str, global_mean: float) -> dict[str, float]:
    """Compute additive offsets per category or board."""
    offsets = {}
    for name, grp in obs_df.groupby(group_col):
        if len(grp) >= 10:
            grp_median = float(grp["daily_pct"].median())
            offsets[str(name)] = round(grp_median - global_mean, 4)
    return offsets


def _default_curve() -> DecayCurve:
    """Fallback curve when not enough historical data."""
    points = {}
    for t in range(1, MAX_PREDICTION_HORIZON + 1):
        points[t] = DecayCurvePoint(
            t=t,
            n_observations=0,
            mean_daily_pct=-0.01,
            median_daily_pct=-0.01,
            std_daily_pct=1.0,
            p_up=30.0,
            p_down=30.0,
            p_stable=40.0,
        )
    return DecayCurve(
        points=points,
        global_mean_daily_pct=-0.01,
        global_std_daily_pct=1.0,
        total_observations=0,
        total_tracks=0,
        max_t=MAX_PREDICTION_HORIZON,
    )


# ── Enrichments Helper ───────────────────────────────────────────────

@dataclass
class Enrichments:
    """Collected enrichment signals for a forward curve walk."""
    demand_indicator: str = "NO_DATA"
    events: list[dict] = field(default_factory=list)
    seasonality_index: dict[str, float] = field(default_factory=dict)
    weather_signal: dict[str, float] = field(default_factory=dict)   # {date_str: adj_pct}
    competitor_pressure: float = 0.0                                   # -1.0 to +1.0
    price_velocity: float = 0.0                                        # 0-1 normalized update frequency
    cancellation_risk: float = 0.0                                     # 0-1 cancel rate for this hotel
    provider_pressure: float = 0.0                                     # -1.0 to +1.0 from search results
    # Phase 2 enrichments (from analytical_cache — NEW, default=safe)
    demand_zone_proximity: float = 0.0                                  # -1.0 (near resistance) to +1.0 (near support)
    rebuy_signal_strength: float = 0.0                                  # 0-1 normalized rebuy activity
    search_volume_trend: float = 0.0                                    # 0-1 normalized; 0.5 = neutral

    def get_event_daily_adj(self, date: datetime) -> float:
        """Event impact for a specific date, spread across event window."""
        total_adj = 0.0
        for ev in self.events:
            start = ev.get("start_date")
            end = ev.get("end_date")
            mult = ev.get("multiplier", 0)
            if not start or not end or mult <= 0:
                continue

            start_dt = pd.Timestamp(start)
            end_dt = pd.Timestamp(end)
            date_ts = pd.Timestamp(date)

            # Impact window: 3 days before to 2 days after
            impact_start = start_dt - timedelta(days=EVENT_RAMP_DAYS)
            impact_end = end_dt + timedelta(days=EVENT_TAPER_DAYS)

            if impact_start <= date_ts <= impact_end:
                impact_days = max((impact_end - impact_start).days, 1)
                # Ramp up before event, peak during, taper after
                if date_ts < start_dt:
                    ramp = (date_ts - impact_start).days / EVENT_RAMP_DAYS
                    total_adj += mult * 100 * max(ramp, 0.1) / impact_days
                elif date_ts > end_dt:
                    taper = 1.0 - (date_ts - end_dt).days / EVENT_TAPER_DAYS
                    total_adj += mult * 100 * max(taper, 0.1) / impact_days
                else:
                    total_adj += mult * 100 / impact_days

        return total_adj

    def get_season_daily_adj(self, date: datetime) -> float:
        """Seasonality adjustment for a specific date, spread to daily."""
        if not self.seasonality_index:
            return 0.0
        month_name = date.strftime("%B")
        idx = self.seasonality_index.get(month_name, 1.0)
        # Convert monthly index deviation to daily adjustment
        # idx=1.099 (Feb/Dec, Miami snowbird peak) → ~+0.30%/day upward pressure
        # idx=0.845 (Sep, Miami hurricane season trough) → ~-0.47%/day downward
        return (idx - 1.0) * SEASONALITY_MULTIPLIER

    def get_demand_daily_adj(self) -> float:
        """Demand-based daily adjustment."""
        if self.demand_indicator == "HIGH":
            return DEMAND_IMPACT_HIGH
        if self.demand_indicator == "LOW":
            return DEMAND_IMPACT_LOW
        return 0.0

    def get_weather_daily_adj(self, date: datetime) -> float:
        """Daily adjustment from weather forecast for a specific date.

        Returns 0.0 if no weather data is available for the date.
        """
        return self.weather_signal.get(date.strftime("%Y-%m-%d"), 0.0)

    def get_competitor_daily_adj(self) -> float:
        """Daily adjustment from competitor rate pressure.

        Scaled to ±0.20%/day maximum impact.
        Positive pressure (we're cheaper) → upward pressure on prices.
        Negative pressure (we're expensive) → downward pressure on prices.
        """
        return self.competitor_pressure * COMPETITOR_IMPACT_MAX

    def get_velocity_daily_adj(self) -> float:
        """Daily adjustment from price update velocity.

        High velocity (many price changes) → market is active, prices volatile.
        Velocity is non-directional (fast changes = up OR down), so returns 0.
        Impact is captured via increased volatility in confidence bands.
        """
        return 0.0  # non-directional; was incorrectly biasing upward

    def get_cancel_risk_adj(self) -> float:
        """Daily adjustment from cancellation risk.

        High cancel rate → downward pressure on predicted price
        (rooms may become available, increasing supply).
        Scaled to -0.25%/day maximum impact at 100% cancel rate.
        """
        return -self.cancellation_risk * CANCELLATION_IMPACT_MAX

    def get_provider_pressure_adj(self) -> float:
        """Daily adjustment from multi-provider search results.

        Positive = providers raising prices → upward pressure.
        Negative = providers dropping prices → downward pressure.
        Scaled to ±0.20%/day maximum impact.
        """
        return self.provider_pressure * PROVIDER_IMPACT_MAX

    # ── Phase 2 enrichments (from analytical_cache) ───────────────────

    def get_demand_zone_daily_adj(self) -> float:
        """Daily adjustment from demand zone proximity.

        Positive proximity (+1.0) = price near strong support zone → upward pressure.
        Negative proximity (-1.0) = price near resistance zone → downward pressure.
        Scaled to ±0.10%/day maximum impact.
        """
        return self.demand_zone_proximity * DEMAND_ZONE_IMPACT_MAX

    def get_rebuy_signal_daily_adj(self) -> float:
        """Daily adjustment from rebuy signal activity.

        Rebuy = cancellation due to price drop >10%, then rebook at lower price.
        Always a CALL (upward) signal: price already dropped, likely to recover.
        Scaled to +0.12%/day at max strength.
        """
        return self.rebuy_signal_strength * REBUY_SIGNAL_IMPACT_MAX

    def get_search_volume_daily_adj(self) -> float:
        """Daily adjustment from search volume trend.

        0.5 = neutral (average volume).
        >0.5 = above-average searches → more interest → upward pressure.
        <0.5 = below-average → less demand → downward pressure.
        Scaled to ±0.04%/day (centered at 0.5).
        """
        return (self.search_volume_trend - 0.5) * SEARCH_VOLUME_IMPACT_MAX


# ── Forward Curve Prediction ─────────────────────────────────────────

def predict_forward_curve(
    detail_id: int,
    hotel_id: int,
    current_price: float,
    current_t: int,
    category: str,
    board: str,
    curve: DecayCurve,
    momentum_state: dict | None = None,
    enrichments: Enrichments | None = None,
) -> ForwardCurve:
    """Walk the decay curve day-by-day to produce a forward price path.

    Args:
        detail_id: Room detail ID.
        hotel_id: Hotel ID.
        current_price: Latest observed price.
        current_t: Days to check-in from now.
        category: Room category (lowercase).
        board: Room board type (lowercase).
        curve: The empirical DecayCurve.
        momentum_state: Dict with momentum_vs_expected and strength.
        enrichments: External signals (events, seasonality, demand).

    Returns:
        ForwardCurve with day-by-day predicted prices.
    """
    if current_t <= 0:
        return ForwardCurve(
            detail_id=detail_id, hotel_id=hotel_id,
            category=category, board=board,
            current_price=current_price, current_t=0,
        )

    if enrichments is None:
        enrichments = Enrichments()
    if momentum_state is None:
        momentum_state = {"momentum_vs_expected": 0.0, "strength": 0.0}

    cat_offset = curve.category_offsets.get(category.lower(), 0.0)
    board_offset = curve.board_offsets.get(board.lower(), 0.0)
    mom_vs_expected = momentum_state.get("momentum_vs_expected", 0.0)

    now = datetime.utcnow()
    predicted_price = current_price
    cumulative_variance = 0.0
    points = []

    for day_idx in range(current_t):
        t = current_t - day_idx  # countdown: current_t, current_t-1, ..., 1
        pred_date = now + timedelta(days=day_idx + 1)

        # Base expected change from empirical curve
        base_pct = curve.get_daily_change(t)

        # Category + board offsets
        offset_pct = cat_offset + board_offset

        # Momentum adjustment (decays with ~7-day half-life)
        mom_decay = exp(-MOMENTUM_DECAY_RATE * day_idx)
        mom_adj = mom_vs_expected * mom_decay * MOMENTUM_IMPACT_SCALE

        # Enrichment adjustments
        event_adj = enrichments.get_event_daily_adj(pred_date)
        season_adj = enrichments.get_season_daily_adj(pred_date)
        demand_adj = enrichments.get_demand_daily_adj()
        weather_adj = enrichments.get_weather_daily_adj(pred_date)
        comp_adj = enrichments.get_competitor_daily_adj()
        velocity_adj = enrichments.get_velocity_daily_adj()
        cancel_adj = enrichments.get_cancel_risk_adj()
        provider_adj = enrichments.get_provider_pressure_adj()
        # Phase 2 enrichments (from analytical_cache)
        dz_adj = enrichments.get_demand_zone_daily_adj()
        rebuy_adj = enrichments.get_rebuy_signal_daily_adj()
        sv_adj = enrichments.get_search_volume_daily_adj()

        # Total daily change
        total_daily_pct = (base_pct + offset_pct + mom_adj + event_adj
                           + season_adj + demand_adj + weather_adj + comp_adj
                           + velocity_adj + cancel_adj + provider_adj
                           + dz_adj + rebuy_adj + sv_adj)

        # Apply change (multiplicative)
        predicted_price *= (1.0 + total_daily_pct / 100.0)

        # Accumulate variance for confidence intervals
        vol = curve.get_volatility(t)
        cumulative_variance += (vol / 100.0 * predicted_price) ** 2
        cum_std = sqrt(cumulative_variance)

        cumulative_pct = (predicted_price / current_price - 1.0) * 100.0

        points.append(ForwardPoint(
            date=pred_date.strftime("%Y-%m-%d"),
            t=t - 1,  # days remaining after this day
            predicted_price=round(predicted_price, 2),
            daily_change_pct=round(total_daily_pct, 4),
            cumulative_change_pct=round(cumulative_pct, 2),
            lower_bound=round(predicted_price - CI_Z_SCORE * cum_std, 2),
            upper_bound=round(predicted_price + CI_Z_SCORE * cum_std, 2),
            volatility_at_t=round(vol, 4),
            dow=_DOW_NAMES[pred_date.weekday()],
            event_adj_pct=round(event_adj, 4),
            season_adj_pct=round(season_adj, 4),
            demand_adj_pct=round(demand_adj, 4),
            momentum_adj_pct=round(mom_adj, 4),
            weather_adj_pct=round(weather_adj, 4),
            competitor_adj_pct=round(comp_adj, 4),
            demand_zone_adj_pct=round(dz_adj, 4),
            rebuy_signal_adj_pct=round(rebuy_adj, 4),
            search_volume_adj_pct=round(sv_adj, 4),
        ))

    # Determine confidence quality from data density at current T
    density = curve.get_data_density(current_t)

    # ── Monitor bridge: apply confidence modifier + market signal boost ──
    monitor_modifier = 0.0
    market_context = {}
    try:
        from src.services.monitor_bridge import MonitorBridge
        bridge = MonitorBridge()
        monitor_modifier = bridge.get_confidence_modifier(hotel_id=str(hotel_id))
        signals = bridge.get_market_signals()
        if signals:
            demand_sig = signals.get("demand_indicator", {}).get("value", 0)
            board_sig = signals.get("board_composition", {}).get("value", 0)
            volatility_sig = signals.get("supply_volatility", {}).get("value", 0)
            market_context = {
                "demand_indicator": demand_sig,
                "board_composition": board_sig,
                "supply_volatility": volatility_sig,
                "confidence_modifier": monitor_modifier,
            }
    except (ImportError, OSError, Exception):
        pass  # Monitor bridge is optional — never block predictions

    # Downgrade confidence quality if monitor flags issues
    if monitor_modifier <= -0.30:
        density = "low" if density in ("medium", "low") else "medium"
    elif monitor_modifier <= -0.15 and density == "high":
        density = "medium"

    fc = ForwardCurve(
        detail_id=detail_id,
        hotel_id=hotel_id,
        category=category,
        board=board,
        current_price=current_price,
        current_t=current_t,
        points=points,
        curve_type="empirical" if curve.total_tracks > 0 else "default",
        confidence_quality=density,
    )
    # Attach monitor context as extra attributes for downstream consumers
    fc.monitor_modifier = monitor_modifier  # type: ignore[attr-defined]
    fc.market_context = market_context       # type: ignore[attr-defined]
    return fc
