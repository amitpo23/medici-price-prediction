"""Demand analysis: elasticity, demand curves, optimal pricing."""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import linregress


def estimate_demand_curve(
    df: pd.DataFrame,
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
    method: str = "log_linear",
) -> dict:
    """Estimate the demand curve (price vs occupancy relationship).

    Methods:
        'linear': occupancy = a + b * price
        'log_linear': ln(occupancy) = a + b * ln(price)

    Returns dict with: method, coefficients, r_squared, demand_function (callable).
    """
    data = df[[price_col, occupancy_col]].dropna()
    data = data[(data[price_col] > 0) & (data[occupancy_col] > 0)]

    if len(data) < 10:
        return {
            "method": method,
            "coefficients": {"a": 0, "b": 0},
            "r_squared": 0.0,
            "demand_function": lambda price: 0.6,
            "error": "Insufficient data (need >= 10 rows)",
        }

    prices = data[price_col].values
    occupancy = data[occupancy_col].values

    if method == "log_linear":
        log_p = np.log(prices)
        log_o = np.log(np.clip(occupancy, 0.01, 1.0))
        slope, intercept, r_value, _, _ = linregress(log_p, log_o)

        def demand_func(price):
            return float(np.clip(np.exp(intercept + slope * np.log(max(price, 1))), 0, 1))

        return {
            "method": "log_linear",
            "coefficients": {"a": round(float(intercept), 6), "b": round(float(slope), 6)},
            "r_squared": round(float(r_value ** 2), 4),
            "demand_function": demand_func,
            "price_range": {"min": float(prices.min()), "max": float(prices.max())},
        }
    else:
        slope, intercept, r_value, _, _ = linregress(prices, occupancy)

        def demand_func(price):
            return float(np.clip(intercept + slope * price, 0, 1))

        return {
            "method": "linear",
            "coefficients": {"a": round(float(intercept), 6), "b": round(float(slope), 6)},
            "r_squared": round(float(r_value ** 2), 4),
            "demand_function": demand_func,
            "price_range": {"min": float(prices.min()), "max": float(prices.max())},
        }


def calculate_price_elasticity(
    df: pd.DataFrame,
    price_col: str = "price",
    occupancy_col: str = "occupancy_rate",
    window: int | None = None,
) -> float | pd.Series:
    """Calculate price elasticity of demand.

    Elasticity = (% change in occupancy) / (% change in price).
    For log-linear model, elasticity equals the slope coefficient.

    Args:
        window: If provided, calculate rolling elasticity.

    Returns single float (overall) or Series (rolling).
    """
    data = df[[price_col, occupancy_col]].dropna()
    data = data[(data[price_col] > 0) & (data[occupancy_col] > 0)]

    if len(data) < 10:
        return 0.0

    if window is not None:
        # Rolling elasticity
        pct_price = data[price_col].pct_change()
        pct_occ = data[occupancy_col].pct_change()
        elasticity = (pct_occ / pct_price.replace(0, np.nan)).rolling(window).median()
        return elasticity.fillna(0.0)

    # Overall: use log-log regression slope
    log_p = np.log(data[price_col].values)
    log_o = np.log(np.clip(data[occupancy_col].values, 0.01, 1.0))
    slope, _, _, _, _ = linregress(log_p, log_o)
    return round(float(slope), 4)


def find_optimal_price(
    demand_curve: dict,
    min_price: float = 200.0,
    max_price: float = 2000.0,
    rooms_available: int = 100,
    objective: str = "revenue",
) -> dict:
    """Find the price that maximizes revenue.

    Revenue = price * demand(price) * rooms_available.
    """
    demand_func = demand_curve.get("demand_function")
    if demand_func is None:
        return {"error": "No demand function available"}

    def neg_revenue(price):
        occ = demand_func(price)
        return -(price * occ * rooms_available)

    result = minimize_scalar(neg_revenue, bounds=(min_price, max_price), method="bounded")

    optimal_price = float(result.x)
    optimal_occ = demand_func(optimal_price)
    optimal_revenue = optimal_price * optimal_occ * rooms_available
    optimal_revpar = optimal_price * optimal_occ

    return {
        "optimal_price": round(optimal_price, 2),
        "expected_occupancy": round(optimal_occ, 3),
        "expected_revenue": round(optimal_revenue, 2),
        "expected_revpar": round(optimal_revpar, 2),
        "rooms_available": rooms_available,
        "price_range_searched": {"min": min_price, "max": max_price},
    }


def demand_sensitivity_table(
    demand_curve: dict,
    price_points: list[float] | None = None,
    rooms_available: int = 100,
) -> pd.DataFrame:
    """Generate a what-if table showing occupancy/revenue at different prices.

    Returns DataFrame: price, expected_occupancy, expected_revenue,
    expected_revpar, marginal_revenue.
    """
    demand_func = demand_curve.get("demand_function")
    if demand_func is None:
        return pd.DataFrame()

    if price_points is None:
        price_range = demand_curve.get("price_range", {"min": 200, "max": 2000})
        price_points = list(np.linspace(price_range["min"], price_range["max"], 20))

    records = []
    prev_revenue = None

    for price in sorted(price_points):
        occ = demand_func(price)
        revenue = price * occ * rooms_available
        revpar = price * occ

        marginal = 0.0
        if prev_revenue is not None and len(records) > 0:
            price_diff = price - records[-1]["price"]
            if price_diff > 0:
                marginal = (revenue - prev_revenue) / price_diff

        records.append({
            "price": round(price, 2),
            "expected_occupancy": round(occ, 3),
            "expected_revenue": round(revenue, 2),
            "expected_revpar": round(revpar, 2),
            "marginal_revenue": round(marginal, 2),
        })
        prev_revenue = revenue

    return pd.DataFrame(records)
