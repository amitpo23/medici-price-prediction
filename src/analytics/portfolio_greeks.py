"""Portfolio Greeks — options-style risk metrics for hotel room contracts.

Treats each room contract as an option where:
  - Underlying (S) = current room price
  - Strike/Target = predicted check-in price
  - Expiry (T) = check-in date
  - Volatility (σ) = forward curve volatility at T

Greeks calculated:
  Theta  — daily time decay: how much predicted value changes per day
  Delta  — price sensitivity: portfolio change per $1 in room price
  Vega   — volatility sensitivity: prediction change per 1% vol shift
  VaR    — Value at Risk at 95% confidence (1-day horizon)
  CVaR   — Conditional VaR (expected loss beyond VaR)

This module is READ-ONLY — it only computes metrics from cached predictions.
It NEVER executes trades or modifies prices.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np

from config.constants import (
    CI_Z_SCORE,
    DATA_DENSITY_MEDIUM,
    MIN_VOLATILITY,
)

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────
VAR_CONFIDENCE = 0.95          # 95th percentile
VAR_Z = 1.645                  # Z-score for 95% one-tail
CVAR_TAIL_SAMPLES = 1000       # Monte Carlo samples for CVaR
GREEKS_MIN_DATA_POINTS = 5     # Minimum FC points to compute Greeks
MAX_PORTFOLIO_ROOMS = 10_000   # Safety cap


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class RoomGreeks:
    """Greeks for a single room contract."""
    detail_id: int
    hotel_id: int
    hotel_name: str
    category: str
    board: str
    checkin_date: str
    T: int                      # Days to check-in
    current_price: float        # S_t
    predicted_price: float      # Forward curve terminal price
    signal: str                 # CALL / PUT / NONE

    # Greeks
    theta: float                # ΔP/Δt — daily time decay ($)
    delta: float                # ∂V/∂S — price sensitivity (0-1)
    vega: float                 # ∂V/∂σ — vol sensitivity ($)
    sigma_1d: float             # Daily volatility (%)

    # Risk
    var_1d: float               # 1-day VaR ($) at 95% confidence
    position_value: float       # predicted_price - current_price ($)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PortfolioGreeks:
    """Aggregated Greeks for the entire portfolio."""
    timestamp: str
    n_contracts: int
    n_calls: int
    n_puts: int
    n_none: int

    # Aggregated Greeks
    total_theta: float          # Sum of daily theta across all positions ($)
    avg_delta: float            # Weighted average delta
    total_vega: float           # Sum of vega ($)
    avg_sigma: float            # Average daily volatility (%)

    # Risk metrics
    portfolio_var_95: float     # Portfolio VaR at 95% ($)
    portfolio_cvar_95: float    # Portfolio CVaR at 95% ($)
    total_exposure: float       # Sum of |position_value| ($)
    total_unrealized_pnl: float # Sum of (predicted - current) ($)

    # Concentration
    max_hotel_exposure_pct: float   # Largest hotel as % of total
    max_hotel_name: str

    # Per-hotel breakdown
    hotel_greeks: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


# ── Computation Functions ────────────────────────────────────────────

def compute_room_greeks(pred: dict) -> RoomGreeks | None:
    """Compute Greeks for a single room contract from its prediction data.

    Args:
        pred: A single prediction dict from the analysis cache, containing:
            - current_price, predicted_checkin_price, days_to_checkin
            - forward_curve (list of FC points with predicted_price, volatility_at_t)
            - option_signal, hotel_id, hotel_name, category, board, date_from

    Returns:
        RoomGreeks dataclass or None if insufficient data.
    """
    try:
        current_price = float(pred.get("current_price", 0) or 0)
        predicted_price = float(pred.get("predicted_checkin_price", 0) or 0)
        T = int(pred.get("days_to_checkin", 0) or 0)
        signal = pred.get("option_signal", "NONE") or "NONE"
        fc = pred.get("forward_curve") or []

        if current_price <= 0 or T <= 0 or len(fc) < GREEKS_MIN_DATA_POINTS:
            return None

        # ── Theta: daily time decay ──────────────────────────────
        # Rate at which predicted value changes per day
        # θ = (predicted_price - current_price) / T
        position_value = predicted_price - current_price
        theta = position_value / T if T > 0 else 0.0

        # More precise theta from FC: price change at T vs T-1
        if len(fc) >= 2:
            p_today = float(fc[0].get("predicted_price", current_price))
            p_tomorrow = float(fc[1].get("predicted_price", current_price))
            theta = p_tomorrow - p_today  # Daily $ change

        # ── Delta: price sensitivity ─────────────────────────────
        # For CALL: delta ≈ probability of price going up (0 to 1)
        # For PUT: delta ≈ -probability of price going down (-1 to 0)
        prob = pred.get("probability") or {}
        p_up = float(prob.get("up", 50)) / 100.0
        p_down = float(prob.get("down", 50)) / 100.0

        if signal in ("CALL", "STRONG_CALL"):
            delta = p_up
        elif signal in ("PUT", "STRONG_PUT"):
            delta = -p_down
        else:
            delta = p_up - p_down  # Net directional exposure

        # ── Sigma: daily volatility ──────────────────────────────
        sigma_1d = float(fc[0].get("volatility_at_t", MIN_VOLATILITY)) if fc else MIN_VOLATILITY
        sigma_1d = max(sigma_1d, MIN_VOLATILITY)

        # ── Vega: volatility sensitivity ─────────────────────────
        # How much does the prediction change if vol shifts by 1%?
        # ν ≈ S × √T × N'(d1) in Black-Scholes terms
        # Simplified: vega = current_price × sigma_1d × √T / 100
        vega = current_price * (sigma_1d / 100.0) * math.sqrt(T)

        # ── VaR: 1-day Value at Risk ─────────────────────────────
        # VaR_95 = |position_value| × σ_1d × Z_95 / 100
        var_1d = abs(current_price) * (sigma_1d / 100.0) * VAR_Z

        return RoomGreeks(
            detail_id=int(pred.get("detail_id", 0)),
            hotel_id=int(pred.get("hotel_id", 0)),
            hotel_name=pred.get("hotel_name", ""),
            category=pred.get("category", ""),
            board=pred.get("board", ""),
            checkin_date=pred.get("date_from", ""),
            T=T,
            current_price=round(current_price, 2),
            predicted_price=round(predicted_price, 2),
            signal=signal,
            theta=round(theta, 4),
            delta=round(delta, 4),
            vega=round(vega, 2),
            sigma_1d=round(sigma_1d, 4),
            var_1d=round(var_1d, 2),
            position_value=round(position_value, 2),
        )

    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        logger.debug("Greeks computation failed for %s: %s", pred.get("detail_id"), exc)
        return None


def compute_portfolio_greeks(analysis: dict) -> PortfolioGreeks:
    """Compute aggregated Greeks for the entire portfolio.

    Args:
        analysis: The full analysis dict from the prediction cache,
                  containing "predictions" mapping detail_id → prediction.

    Returns:
        PortfolioGreeks with aggregated metrics.
    """
    predictions = analysis.get("predictions", {})
    room_greeks: list[RoomGreeks] = []

    for detail_id, pred in predictions.items():
        rg = compute_room_greeks(pred)
        if rg is not None:
            room_greeks.append(rg)

    n = len(room_greeks)
    if n == 0:
        return _empty_portfolio()

    # ── Aggregations ─────────────────────────────────────────────
    n_calls = sum(1 for rg in room_greeks if rg.signal in ("CALL", "STRONG_CALL"))
    n_puts = sum(1 for rg in room_greeks if rg.signal in ("PUT", "STRONG_PUT"))
    n_none = n - n_calls - n_puts

    total_theta = sum(rg.theta for rg in room_greeks)

    # Weighted delta by position value
    total_abs_value = sum(abs(rg.current_price) for rg in room_greeks) or 1.0
    avg_delta = sum(rg.delta * abs(rg.current_price) for rg in room_greeks) / total_abs_value

    total_vega = sum(rg.vega for rg in room_greeks)
    avg_sigma = sum(rg.sigma_1d for rg in room_greeks) / n

    total_exposure = sum(abs(rg.position_value) for rg in room_greeks)
    total_unrealized = sum(rg.position_value for rg in room_greeks)

    # ── Portfolio VaR (diversified) ──────────────────────────────
    # Simple approach: sum of individual VaRs with correlation discount
    # More conservative than sqrt-sum (which assumes zero correlation)
    individual_vars = [rg.var_1d for rg in room_greeks]
    sum_var = sum(individual_vars)

    # Diversification benefit: assume average correlation ~0.3 within hotels
    # VaR_portfolio = sqrt(sum(VaR_i^2) + 2*rho*sum_i<j(VaR_i*VaR_j))
    # Simplified: use sqrt of sum of squares * (1 + rho*(n-1)) / n
    rho = 0.3  # Assumed average intra-portfolio correlation
    var_array = np.array(individual_vars)
    if len(var_array) > 1:
        sum_sq = np.sum(var_array ** 2)
        cross_terms = 2 * rho * np.sum(np.triu(np.outer(var_array, var_array), k=1))
        portfolio_var = math.sqrt(sum_sq + cross_terms)
    else:
        portfolio_var = sum_var

    # ── CVaR (Expected Shortfall) ────────────────────────────────
    # CVaR ≈ VaR × E[Z | Z > z_alpha] / z_alpha
    # For normal distribution: CVaR ≈ VaR × φ(z) / (1-Φ(z)) / z
    # φ(1.645) ≈ 0.1031, (1 - Φ(1.645)) = 0.05
    # E[Z | Z > 1.645] = 0.1031 / 0.05 = 2.063
    cvar_multiplier = 2.063 / VAR_Z  # ≈ 1.254
    portfolio_cvar = portfolio_var * cvar_multiplier

    # ── Concentration ────────────────────────────────────────────
    hotel_exposure: dict[int, float] = {}
    hotel_names: dict[int, str] = {}
    hotel_rooms: dict[int, list[RoomGreeks]] = {}

    for rg in room_greeks:
        hid = rg.hotel_id
        hotel_exposure[hid] = hotel_exposure.get(hid, 0) + abs(rg.position_value)
        hotel_names[hid] = rg.hotel_name
        hotel_rooms.setdefault(hid, []).append(rg)

    max_hotel_id = max(hotel_exposure, key=hotel_exposure.get) if hotel_exposure else 0
    max_hotel_exp = hotel_exposure.get(max_hotel_id, 0)
    max_hotel_pct = (max_hotel_exp / total_exposure * 100) if total_exposure > 0 else 0

    # ── Per-hotel breakdown ──────────────────────────────────────
    hotel_greeks_list = []
    for hid, rooms in sorted(hotel_rooms.items(), key=lambda x: -hotel_exposure.get(x[0], 0)):
        h_n = len(rooms)
        h_theta = sum(r.theta for r in rooms)
        h_vega = sum(r.vega for r in rooms)
        h_exposure = hotel_exposure.get(hid, 0)
        h_calls = sum(1 for r in rooms if r.signal in ("CALL", "STRONG_CALL"))
        h_puts = sum(1 for r in rooms if r.signal in ("PUT", "STRONG_PUT"))
        h_var = math.sqrt(sum(r.var_1d ** 2 for r in rooms) * (1 + rho * (h_n - 1)) / h_n) if h_n > 0 else 0

        hotel_greeks_list.append({
            "hotel_id": hid,
            "hotel_name": hotel_names.get(hid, ""),
            "n_contracts": h_n,
            "n_calls": h_calls,
            "n_puts": h_puts,
            "total_theta": round(h_theta, 2),
            "total_vega": round(h_vega, 2),
            "exposure": round(h_exposure, 2),
            "var_95": round(h_var, 2),
            "exposure_pct": round(h_exposure / total_exposure * 100, 1) if total_exposure > 0 else 0,
        })

    return PortfolioGreeks(
        timestamp=datetime.utcnow().isoformat() + "Z",
        n_contracts=n,
        n_calls=n_calls,
        n_puts=n_puts,
        n_none=n_none,
        total_theta=round(total_theta, 2),
        avg_delta=round(avg_delta, 4),
        total_vega=round(total_vega, 2),
        avg_sigma=round(avg_sigma, 4),
        portfolio_var_95=round(portfolio_var, 2),
        portfolio_cvar_95=round(portfolio_cvar, 2),
        total_exposure=round(total_exposure, 2),
        total_unrealized_pnl=round(total_unrealized, 2),
        max_hotel_exposure_pct=round(max_hotel_pct, 1),
        max_hotel_name=hotel_names.get(max_hotel_id, ""),
        hotel_greeks=hotel_greeks_list,
    )


def compute_hotel_greeks(analysis: dict, hotel_id: int) -> dict:
    """Compute Greeks for a specific hotel.

    Returns dict with hotel summary + list of per-room Greeks.
    """
    predictions = analysis.get("predictions", {})
    room_greeks: list[RoomGreeks] = []

    for detail_id, pred in predictions.items():
        if int(pred.get("hotel_id", 0)) != hotel_id:
            continue
        rg = compute_room_greeks(pred)
        if rg is not None:
            room_greeks.append(rg)

    if not room_greeks:
        return {"hotel_id": hotel_id, "error": "No data", "rooms": []}

    n = len(room_greeks)
    total_theta = sum(rg.theta for rg in room_greeks)
    total_vega = sum(rg.vega for rg in room_greeks)
    avg_sigma = sum(rg.sigma_1d for rg in room_greeks) / n
    total_exposure = sum(abs(rg.position_value) for rg in room_greeks)
    total_pnl = sum(rg.position_value for rg in room_greeks)

    # Sort rooms by |position_value| descending
    room_greeks.sort(key=lambda r: abs(r.position_value), reverse=True)

    return {
        "hotel_id": hotel_id,
        "hotel_name": room_greeks[0].hotel_name if room_greeks else "",
        "n_contracts": n,
        "n_calls": sum(1 for r in room_greeks if r.signal in ("CALL", "STRONG_CALL")),
        "n_puts": sum(1 for r in room_greeks if r.signal in ("PUT", "STRONG_PUT")),
        "total_theta": round(total_theta, 2),
        "total_vega": round(total_vega, 2),
        "avg_sigma": round(avg_sigma, 4),
        "total_exposure": round(total_exposure, 2),
        "total_unrealized_pnl": round(total_pnl, 2),
        "rooms": [rg.to_dict() for rg in room_greeks],
    }


def _empty_portfolio() -> PortfolioGreeks:
    """Return an empty PortfolioGreeks when no data is available."""
    return PortfolioGreeks(
        timestamp=datetime.utcnow().isoformat() + "Z",
        n_contracts=0, n_calls=0, n_puts=0, n_none=0,
        total_theta=0, avg_delta=0, total_vega=0, avg_sigma=0,
        portfolio_var_95=0, portfolio_cvar_95=0,
        total_exposure=0, total_unrealized_pnl=0,
        max_hotel_exposure_pct=0, max_hotel_name="",
        hotel_greeks=[],
    )
