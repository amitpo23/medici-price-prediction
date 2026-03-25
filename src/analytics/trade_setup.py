"""Trade Setup Calculator — Stop-Loss, Take-Profit, Position Sizing, Risk:Reward.

For each room with a CALL/PUT signal, computes a complete trade setup:
  - Entry price (current price or path forecast optimal entry)
  - Stop-loss (volatility-based or demand zone-based)
  - Take-profit (path forecast target or RR-based)
  - Risk:Reward ratio
  - Position size (Kelly criterion or ATR-based)
  - Maximum risk in USD

Consumes data from:
  - path_forecast.py (turning points, best buy/sell)
  - forward_curve.py (volatility at T, confidence bands)
  - options_engine.py (signal, confidence, Greeks)

Does NOT modify any of those files.

Safety: This is a NEW file.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from math import sqrt
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

# Stop-loss: multiplier × daily volatility × sqrt(holding_days)
STOP_VOL_MULTIPLIER = 2.0

# Minimum stop distance (% from entry) — prevents stops too tight
MIN_STOP_DISTANCE_PCT = 1.5

# Maximum stop distance (% from entry) — prevents stops too wide
MAX_STOP_DISTANCE_PCT = 15.0

# Minimum acceptable Risk:Reward ratio to show a setup
MIN_RISK_REWARD = 1.0

# Default max risk per trade (USD) — can be overridden
DEFAULT_MAX_RISK_USD = 100.0

# Kelly criterion safety fraction (half-Kelly for conservative sizing)
KELLY_FRACTION = 0.5

# Minimum win rate needed for Kelly to suggest position > 0
MIN_WIN_RATE_FOR_KELLY = 0.40


@dataclass
class TradeSetup:
    """Complete trade setup for one room option."""
    detail_id: int
    hotel_id: int
    setup_type: str = "primary"

    # Entry
    entry_price: float = 0.0
    entry_t: int = 0
    entry_date: str = ""

    # Stop-loss
    stop_loss: float = 0.0
    stop_distance_pct: float = 0.0
    stop_method: str = ""  # "volatility", "demand_zone", "turning_point"

    # Take-profit
    take_profit: float = 0.0
    target_distance_pct: float = 0.0
    target_method: str = ""  # "path_forecast", "rr_based", "demand_zone"

    # Risk management
    risk_reward_ratio: float = 0.0
    position_size: int = 1
    max_risk_usd: float = 0.0

    # Signal context
    signal: str = "NEUTRAL"
    confidence: float = 0.5
    setup_quality: str = "medium"  # "high", "medium", "low", "skip"
    reasons: dict = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = {}

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        """Check if this setup meets minimum trading criteria."""
        return (
            self.risk_reward_ratio >= MIN_RISK_REWARD
            and self.stop_distance_pct >= MIN_STOP_DISTANCE_PCT
            and self.entry_price > 0
            and self.signal in ("CALL", "PUT")
        )


def compute_trade_setup(
    detail_id: int,
    hotel_id: int,
    current_price: float,
    signal: str,
    confidence: float,
    sigma_1d: float,
    t_value: int,
    path_forecast: Optional[dict] = None,
    demand_zones: Optional[list[dict]] = None,
    turning_points: Optional[list[dict]] = None,
    win_rate: Optional[float] = None,
    avg_win_pct: Optional[float] = None,
    avg_loss_pct: Optional[float] = None,
    max_risk_usd: float = DEFAULT_MAX_RISK_USD,
) -> TradeSetup:
    """Compute a complete trade setup for a room option.

    Args:
        detail_id: Room detail ID
        hotel_id: Hotel ID
        current_price: Current room price ($)
        signal: CALL or PUT
        confidence: 0-1 confidence score
        sigma_1d: Daily volatility (%) from forward curve
        t_value: Days to check-in
        path_forecast: Optional PathForecast dict with best_buy/best_sell
        demand_zones: Optional list of demand zone dicts
        turning_points: Optional list of turning point dicts
        win_rate: Historical win rate (0-1) for Kelly sizing
        avg_win_pct: Average winning trade % for Kelly
        avg_loss_pct: Average losing trade % for Kelly (positive number)
        max_risk_usd: Maximum risk per trade in USD

    Returns:
        TradeSetup with entry, stop, target, position size, and RR ratio
    """
    if signal not in ("CALL", "PUT") or current_price <= 0:
        return TradeSetup(
            detail_id=detail_id, hotel_id=hotel_id,
            entry_price=current_price, signal=signal,
            confidence=confidence, setup_quality="skip",
            reasons={"skip": "No directional signal or invalid price"},
        )

    setup = TradeSetup(
        detail_id=detail_id, hotel_id=hotel_id,
        entry_price=current_price, entry_t=t_value,
        signal=signal, confidence=confidence,
    )
    reasons = {}

    # ── Step 1: Compute Stop-Loss ────────────────────────────────
    stop, stop_method = _compute_stop_loss(
        current_price, signal, sigma_1d, t_value,
        demand_zones, turning_points,
    )
    setup.stop_loss = round(stop, 2)
    setup.stop_method = stop_method

    if signal == "CALL":
        setup.stop_distance_pct = round((current_price - stop) / current_price * 100, 2)
    else:  # PUT
        setup.stop_distance_pct = round((stop - current_price) / current_price * 100, 2)

    reasons["stop"] = f"{stop_method}: ${stop:.2f} ({setup.stop_distance_pct:.1f}% from entry)"

    # ── Step 2: Compute Take-Profit ──────────────────────────────
    target, target_method = _compute_take_profit(
        current_price, signal, sigma_1d, t_value,
        setup.stop_distance_pct, path_forecast, demand_zones,
    )
    setup.take_profit = round(target, 2)
    setup.target_method = target_method

    if signal == "CALL":
        setup.target_distance_pct = round((target - current_price) / current_price * 100, 2)
    else:  # PUT
        setup.target_distance_pct = round((current_price - target) / current_price * 100, 2)

    reasons["target"] = f"{target_method}: ${target:.2f} ({setup.target_distance_pct:.1f}% from entry)"

    # ── Step 3: Risk:Reward Ratio ────────────────────────────────
    risk = abs(setup.stop_distance_pct)
    reward = abs(setup.target_distance_pct)
    setup.risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0.0

    reasons["rr"] = f"{setup.risk_reward_ratio:.2f}:1"

    # ── Step 4: Position Sizing ──────────────────────────────────
    setup.max_risk_usd = max_risk_usd
    setup.position_size = _compute_position_size(
        current_price, setup.stop_distance_pct,
        max_risk_usd, win_rate, avg_win_pct, avg_loss_pct,
    )

    reasons["size"] = f"{setup.position_size} contracts (max risk ${max_risk_usd:.0f})"

    # ── Step 5: Setup Quality ────────────────────────────────────
    setup.setup_quality = _assess_quality(setup)
    setup.reasons = reasons

    logger.debug(
        "Trade setup detail_id=%s: %s entry=$%.2f stop=$%.2f target=$%.2f RR=%.2f size=%d quality=%s",
        detail_id, signal, setup.entry_price, setup.stop_loss,
        setup.take_profit, setup.risk_reward_ratio,
        setup.position_size, setup.setup_quality,
    )
    return setup


def _compute_stop_loss(
    price: float,
    signal: str,
    sigma_1d: float,
    t_value: int,
    demand_zones: Optional[list[dict]] = None,
    turning_points: Optional[list[dict]] = None,
) -> tuple[float, str]:
    """Compute stop-loss level using best available method.

    Priority:
    1. Demand zone below/above entry (strongest support/resistance)
    2. Nearest turning point below/above entry
    3. Volatility-based (2 × σ × √holding_period)
    """
    # Holding period estimate: min(t_value, 14) — don't assume holding to expiry
    holding_days = min(max(t_value, 1), 14)

    # Method 1: Demand zone stop
    if demand_zones:
        zone_stop = _zone_based_stop(price, signal, demand_zones)
        if zone_stop is not None:
            distance_pct = abs(price - zone_stop) / price * 100
            if MIN_STOP_DISTANCE_PCT <= distance_pct <= MAX_STOP_DISTANCE_PCT:
                return zone_stop, "demand_zone"

    # Method 2: Turning point stop
    if turning_points:
        tp_stop = _turning_point_stop(price, signal, turning_points)
        if tp_stop is not None:
            distance_pct = abs(price - tp_stop) / price * 100
            if MIN_STOP_DISTANCE_PCT <= distance_pct <= MAX_STOP_DISTANCE_PCT:
                return tp_stop, "turning_point"

    # Method 3: Volatility-based stop (default)
    vol_pct = max(sigma_1d, 0.5)  # Floor at 0.5% daily vol
    stop_distance_pct = STOP_VOL_MULTIPLIER * vol_pct * sqrt(holding_days)
    stop_distance_pct = max(MIN_STOP_DISTANCE_PCT, min(MAX_STOP_DISTANCE_PCT, stop_distance_pct))

    if signal == "CALL":
        stop = price * (1 - stop_distance_pct / 100)
    else:  # PUT — stop is ABOVE entry
        stop = price * (1 + stop_distance_pct / 100)

    return round(stop, 2), "volatility"


def _zone_based_stop(price: float, signal: str, zones: list[dict]) -> Optional[float]:
    """Find the best demand zone for stop placement.

    For CALL: stop just below the nearest support zone below entry
    For PUT: stop just above the nearest resistance zone above entry
    """
    if signal == "CALL":
        # Find support zones below current price
        support_zones = [
            z for z in zones
            if z.get("zone_type") == "SUPPORT"
            and z.get("price_upper", 0) < price
            and not z.get("is_broken", False)
        ]
        if support_zones:
            # Closest support below price
            best = max(support_zones, key=lambda z: z["price_upper"])
            # Place stop just below the zone lower bound
            return best["price_lower"] * 0.995  # 0.5% buffer below zone
    else:  # PUT
        resistance_zones = [
            z for z in zones
            if z.get("zone_type") == "RESISTANCE"
            and z.get("price_lower", 0) > price
            and not z.get("is_broken", False)
        ]
        if resistance_zones:
            best = min(resistance_zones, key=lambda z: z["price_lower"])
            return best["price_upper"] * 1.005  # 0.5% buffer above zone
    return None


def _turning_point_stop(price: float, signal: str, turning_points: list[dict]) -> Optional[float]:
    """Find the nearest turning point for stop placement."""
    if signal == "CALL":
        # Find MIN turning points below entry
        mins_below = [
            tp for tp in turning_points
            if tp.get("type") == "MIN" and tp.get("price", 0) < price
        ]
        if mins_below:
            nearest = max(mins_below, key=lambda tp: tp["price"])
            return nearest["price"] * 0.995  # Buffer below
    else:  # PUT
        maxes_above = [
            tp for tp in turning_points
            if tp.get("type") == "MAX" and tp.get("price", 0) > price
        ]
        if maxes_above:
            nearest = min(maxes_above, key=lambda tp: tp["price"])
            return nearest["price"] * 1.005
    return None


def _compute_take_profit(
    price: float,
    signal: str,
    sigma_1d: float,
    t_value: int,
    stop_distance_pct: float,
    path_forecast: Optional[dict] = None,
    demand_zones: Optional[list[dict]] = None,
) -> tuple[float, str]:
    """Compute take-profit target.

    Priority:
    1. Path forecast best sell/buy point
    2. Demand zone (nearest resistance for CALL, support for PUT)
    3. Risk:Reward based (1.5× the stop distance)
    """
    # Method 1: Path forecast target
    if path_forecast:
        if signal == "CALL":
            pf_target = path_forecast.get("best_sell_price", 0)
            if pf_target > price * 1.01:  # At least 1% above entry
                return pf_target, "path_forecast"
        else:  # PUT
            pf_target = path_forecast.get("best_buy_price", 0)
            if 0 < pf_target < price * 0.99:  # At least 1% below entry
                return pf_target, "path_forecast"

    # Method 2: Demand zone target
    if demand_zones:
        zone_target = _zone_based_target(price, signal, demand_zones)
        if zone_target is not None:
            return zone_target, "demand_zone"

    # Method 3: RR-based (1.5× stop distance as minimum target)
    rr_multiplier = 1.5
    target_distance_pct = stop_distance_pct * rr_multiplier

    if signal == "CALL":
        target = price * (1 + target_distance_pct / 100)
    else:
        target = price * (1 - target_distance_pct / 100)

    return round(target, 2), "rr_based"


def _zone_based_target(price: float, signal: str, zones: list[dict]) -> Optional[float]:
    """Find demand zone for take-profit placement."""
    if signal == "CALL":
        # Target at nearest resistance above entry
        resistance_zones = [
            z for z in zones
            if z.get("zone_type") == "RESISTANCE"
            and z.get("price_lower", 0) > price * 1.01
            and not z.get("is_broken", False)
        ]
        if resistance_zones:
            nearest = min(resistance_zones, key=lambda z: z["price_lower"])
            return nearest["price_lower"]  # Sell at zone lower bound
    else:  # PUT
        support_zones = [
            z for z in zones
            if z.get("zone_type") == "SUPPORT"
            and z.get("price_upper", 0) < price * 0.99
            and not z.get("is_broken", False)
        ]
        if support_zones:
            nearest = max(support_zones, key=lambda z: z["price_upper"])
            return nearest["price_upper"]  # Buy at zone upper bound
    return None


def _compute_position_size(
    price: float,
    stop_distance_pct: float,
    max_risk_usd: float,
    win_rate: Optional[float] = None,
    avg_win_pct: Optional[float] = None,
    avg_loss_pct: Optional[float] = None,
) -> int:
    """Compute position size based on risk management.

    Uses Kelly criterion if historical stats available,
    otherwise simple max-risk based sizing.
    """
    if price <= 0 or stop_distance_pct <= 0:
        return 1

    # Risk per contract = price × stop_distance%
    risk_per_contract = price * (stop_distance_pct / 100)

    if risk_per_contract <= 0:
        return 1

    # Method 1: Kelly criterion (if historical data available)
    if (win_rate is not None and avg_win_pct is not None
            and avg_loss_pct is not None and win_rate >= MIN_WIN_RATE_FOR_KELLY):
        kelly_size = _kelly_position_size(
            price, risk_per_contract, max_risk_usd,
            win_rate, avg_win_pct, avg_loss_pct,
        )
        if kelly_size > 0:
            return kelly_size

    # Method 2: Simple risk-based sizing
    # How many contracts can we afford at max_risk_usd?
    size = int(max_risk_usd / risk_per_contract)
    return max(1, min(size, 50))  # Cap at 50 contracts


def _kelly_position_size(
    price: float,
    risk_per_contract: float,
    max_risk_usd: float,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
) -> int:
    """Kelly criterion for optimal position sizing.

    f* = (p × b - q) / b
    Where:
        p = win probability
        q = 1 - p
        b = avg_win / avg_loss (payoff ratio)

    Uses half-Kelly for conservative sizing.
    """
    if avg_loss_pct <= 0 or avg_win_pct <= 0:
        return 0

    p = win_rate
    q = 1 - p
    b = avg_win_pct / avg_loss_pct  # Payoff ratio

    kelly_fraction = (p * b - q) / b if b > 0 else 0

    if kelly_fraction <= 0:
        return 0  # Kelly says don't bet

    # Half-Kelly for safety
    adjusted_fraction = kelly_fraction * KELLY_FRACTION

    # Convert to contract count
    # kelly_fraction is the fraction of bankroll to risk
    # We use max_risk_usd as the "bankroll at risk"
    risk_amount = max_risk_usd * adjusted_fraction
    size = int(risk_amount / risk_per_contract)
    return max(1, min(size, 50))


def _assess_quality(setup: TradeSetup) -> str:
    """Assess overall quality of a trade setup.

    High: RR ≥ 2.0, confidence ≥ 0.7, stop from zone or TP
    Medium: RR ≥ 1.5, confidence ≥ 0.5
    Low: RR ≥ 1.0
    Skip: RR < 1.0 or other issues
    """
    rr = setup.risk_reward_ratio
    conf = setup.confidence

    if rr < MIN_RISK_REWARD:
        return "skip"

    if rr >= 2.0 and conf >= 0.70:
        if setup.stop_method in ("demand_zone", "turning_point"):
            return "high"
        return "high" if rr >= 2.5 else "medium"

    if rr >= 1.5 and conf >= 0.50:
        return "medium"

    if rr >= 1.0:
        return "low"

    return "skip"


def batch_compute_setups(
    options: list[dict],
    demand_zones_by_hotel: Optional[dict[int, list[dict]]] = None,
    trade_stats: Optional[dict] = None,
    max_risk_usd: float = DEFAULT_MAX_RISK_USD,
) -> list[TradeSetup]:
    """Compute trade setups for a batch of options.

    Args:
        options: List of option dicts from options_engine (must have:
            detail_id, hotel_id, S_t, recommendation, confidence, sigma_1d,
            days_to_checkin)
        demand_zones_by_hotel: {hotel_id: [zone dicts]}
        trade_stats: Historical trade stats from AnalyticalCache.get_trade_stats()
        max_risk_usd: Max risk per trade

    Returns:
        List of TradeSetup objects
    """
    win_rate = None
    avg_win_pct = None
    avg_loss_pct = None

    if trade_stats and trade_stats.get("total_trades", 0) >= 20:
        win_rate = trade_stats.get("win_rate", 0) / 100  # Convert from % to 0-1
        avg_win_pct = abs(trade_stats.get("avg_win_pct", 0))
        avg_loss_pct = abs(trade_stats.get("avg_loss_pct", 0))

    setups = []
    for opt in options:
        signal = opt.get("recommendation", opt.get("option_signal", "NEUTRAL"))
        if signal in ("NONE", "NEUTRAL", None):
            continue

        hotel_id = opt.get("hotel_id", 0)
        zones = (demand_zones_by_hotel or {}).get(hotel_id, [])

        # Extract turning points from path forecast if available
        turning_points = None
        pf = opt.get("path_forecast")
        if pf:
            turning_points = pf.get("turning_points", [])

        setup = compute_trade_setup(
            detail_id=opt.get("detail_id", 0),
            hotel_id=hotel_id,
            current_price=opt.get("S_t", opt.get("current_price", 0)),
            signal=signal,
            confidence=opt.get("confidence_score", opt.get("consensus_probability", 50)) / 100,
            sigma_1d=opt.get("sigma_1d", 1.0),
            t_value=opt.get("days_to_checkin", opt.get("T", 0)),
            path_forecast=pf,
            demand_zones=zones,
            turning_points=turning_points,
            win_rate=win_rate,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            max_risk_usd=max_risk_usd,
        )
        setups.append(setup)

    valid = sum(1 for s in setups if s.is_valid)
    logger.info(
        "Computed %d trade setups (%d valid, %d skipped)",
        len(setups), valid, len(setups) - valid,
    )
    return setups
