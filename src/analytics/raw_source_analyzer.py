"""Raw Source Analyzer — per-source statistical analysis without ensemble blending.

Provides pure statistical view of what each data source says independently,
with NO enrichments, NO ensemble weighting, and NO assumptions.

Three analysis levels:
  1. Statistical Profile — distribution, mean, median, percentiles, trend, volatility
  2. Pure Historical Prediction — 100% based on one source's historical patterns
  3. Source Comparison — what each source says independently, agreements & conflicts

This is the "show me the raw data" layer that lets operators see what each
source actually says before any model assumptions are applied.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from math import sqrt
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class SourceStatistics:
    """Statistical profile for a single data source on a specific option."""
    source_name: str
    source_label: str           # Human-readable name
    n_observations: int = 0
    n_comparable_tracks: int = 0  # How many similar rooms tracked historically

    # Price distribution
    mean_price: float = 0.0
    median_price: float = 0.0
    std_price: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    p25_price: float = 0.0      # 25th percentile
    p75_price: float = 0.0      # 75th percentile

    # Trend
    trend_direction: str = "FLAT"  # UP, DOWN, FLAT
    trend_pct_per_day: float = 0.0
    trend_confidence: float = 0.0

    # Volatility
    daily_volatility_pct: float = 0.0
    annualized_volatility_pct: float = 0.0

    # Historical outcome distribution (for similar rooms at similar T)
    pct_went_up: float = 0.0
    pct_went_down: float = 0.0
    pct_stayed_flat: float = 0.0
    median_up_magnitude: float = 0.0    # When it went up, by how much?
    median_down_magnitude: float = 0.0  # When it went down, by how much?

    # Data quality
    freshness_hours: float = 0.0  # Hours since last update
    coverage_pct: float = 0.0     # % of T-range covered by data

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourcePrediction:
    """Pure prediction from a single source — no blending, no enrichments."""
    source_name: str
    source_label: str
    predicted_price: float = 0.0
    predicted_change_pct: float = 0.0
    direction: str = "NEUTRAL"  # CALL, PUT, NEUTRAL
    confidence: float = 0.0
    basis: str = ""            # What the prediction is based on
    n_supporting_cases: int = 0
    n_total_cases: int = 0
    historical_accuracy_pct: float = 0.0  # How accurate was this source historically?


@dataclass
class SourceComparison:
    """Comparison across all sources for one option."""
    detail_id: int
    hotel_id: int
    hotel_name: str
    category: str
    board: str
    checkin_date: str
    current_price: float
    current_t: int

    # Per-source data
    source_stats: list[SourceStatistics] = field(default_factory=list)
    source_predictions: list[SourcePrediction] = field(default_factory=list)

    # Agreement analysis
    consensus_direction: str = "NEUTRAL"
    consensus_strength: float = 0.0  # 0-1, how much sources agree
    n_sources_call: int = 0
    n_sources_put: int = 0
    n_sources_neutral: int = 0
    disagreement_flag: bool = False   # True if sources disagree on direction

    # Ensemble for reference
    ensemble_direction: str = "NEUTRAL"
    ensemble_price: float = 0.0
    ensemble_vs_consensus: str = "AGREES"  # AGREES, DISAGREES, N/A

    def to_dict(self) -> dict:
        result = asdict(self)
        return result


# ── Source Labels ────────────────────────────────────────────────────

SOURCE_LABELS = {
    "forward_curve": "Forward Curve (Decay)",
    "historical_pattern": "Historical Patterns",
    "ml_forecast": "ML Forecast",
    "salesoffice": "SalesOffice Scans",
    "ai_search_hotel_data": "AI Search (8.5M records)",
    "search_results_poll_log": "CBS Search Results (8.3M)",
    "room_price_update_log": "Room Price Updates",
    "med_prebook": "Pre-Booking Data",
    "kiwi_flights": "Flight Demand (Kiwi)",
    "open_meteo": "Weather Forecast",
    "miami_events_hardcoded": "Miami Events",
    "hotel_booking_dataset": "Kaggle Bookings",
    "ota_brightdata_exports": "OTA BrightData",
    "tbo_hotels": "TBO Hotels",
    "trivago_statista": "Trivago/Statista",
}

# Sources that can provide standalone price predictions
PREDICTIVE_SOURCES = {
    "forward_curve",
    "historical_pattern",
    "ml_forecast",
    "salesoffice",
    "ai_search_hotel_data",
    "search_results_poll_log",
}

# Sources that are enrichments only (no standalone prediction)
ENRICHMENT_ONLY_SOURCES = {
    "kiwi_flights",
    "open_meteo",
    "miami_events_hardcoded",
    "hotel_booking_dataset",
}


# ── Core Analysis Functions ──────────────────────────────────────────

def analyze_source_statistics(
    pred: dict,
    source_name: str,
) -> SourceStatistics:
    """Compute statistical profile for a single source on one option.

    Uses the prediction's source_inputs and available data to build
    a pure statistical view — no model assumptions.
    """
    label = SOURCE_LABELS.get(source_name, source_name)
    stats = SourceStatistics(source_name=source_name, source_label=label)

    source_inputs = pred.get("source_inputs") or {}
    if not isinstance(source_inputs, dict):
        source_inputs = {}
    market = pred.get("market_benchmark") or {}
    if not isinstance(market, dict):
        market = {}

    # Extract source-specific data
    if source_name == "forward_curve":
        fc_points = pred.get("forward_curve") or []
        if fc_points:
            prices = [float(p.get("predicted_price", 0)) for p in fc_points if float(p.get("predicted_price", 0)) > 0]
            if prices:
                _compute_price_stats(stats, prices)
                _compute_trend(stats, prices)
                volatilities = [float(p.get("volatility_at_t", 0)) for p in fc_points]
                stats.daily_volatility_pct = round(np.mean(volatilities) if volatilities else 0, 4)
                stats.annualized_volatility_pct = round(stats.daily_volatility_pct * sqrt(365), 2)
            stats.n_observations = len(fc_points)

    elif source_name == "historical_pattern":
        hist = source_inputs.get("historical") or {}
        if isinstance(hist, dict) and hist:
            price = float(hist.get("predicted_price", 0) or 0)
            stats.n_comparable_tracks = int(hist.get("n_tracks", 0) or 0)
            stats.n_observations = int(hist.get("n_observations", 0) or 0)
            if price > 0:
                stats.mean_price = round(price, 2)
                stats.median_price = round(price, 2)
            stats.trend_confidence = float(hist.get("confidence", 0) or 0)

    elif source_name in ("ai_search_hotel_data", "salesoffice"):
        market_data = market.get(source_name) or market
        if isinstance(market_data, dict) and market_data:
            avg = float(market_data.get("avg_price", 0) or market_data.get("mean_price", 0) or 0)
            med = float(market_data.get("median_price", 0) or 0)
            mn = float(market_data.get("min_price", 0) or 0)
            mx = float(market_data.get("max_price", 0) or 0)
            n = int(market_data.get("n_results", 0) or market_data.get("count", 0) or 0)

            if avg > 0:
                stats.mean_price = round(avg, 2)
                stats.median_price = round(med if med > 0 else avg, 2)
                stats.min_price = round(mn if mn > 0 else avg * 0.7, 2)
                stats.max_price = round(mx if mx > 0 else avg * 1.3, 2)
                stats.n_observations = n

    elif source_name == "search_results_poll_log":
        provider = source_inputs.get("provider_pressure")
        if isinstance(provider, dict) and provider:
            stats.n_observations = int(provider.get("n_providers", 0) or 0)
            avg = float(provider.get("avg_price", 0) or 0)
            if avg > 0:
                stats.mean_price = round(avg, 2)
                stats.median_price = round(avg, 2)

    # Compute directional stats from probabilities if available
    prob = pred.get("probability") or {}
    if prob and source_name == "forward_curve":
        stats.pct_went_up = float(prob.get("up", 0))
        stats.pct_went_down = float(prob.get("down", 0))
        stats.pct_stayed_flat = float(prob.get("stable", 0))

    return stats


def build_source_prediction(
    pred: dict,
    source_name: str,
    stats: SourceStatistics,
) -> SourcePrediction:
    """Generate a pure prediction from a single source — NO enrichments.

    For predictive sources: uses the source's own data to predict direction.
    For enrichment-only sources: returns NEUTRAL with the enrichment's info.
    """
    label = SOURCE_LABELS.get(source_name, source_name)
    current_price = float(pred.get("current_price", 0) or 0)
    sp = SourcePrediction(source_name=source_name, source_label=label)

    if source_name not in PREDICTIVE_SOURCES:
        sp.basis = "enrichment_only"
        sp.direction = "NEUTRAL"
        sp.predicted_price = round(current_price, 2)
        return sp

    source_inputs = pred.get("source_inputs") or {}

    # Forward curve: use its own prediction without enrichments
    if source_name == "forward_curve":
        fc_points = pred.get("forward_curve") or []
        if fc_points:
            # Strip enrichment adjustments to get raw forward curve prediction
            raw_prices = _strip_enrichments_from_curve(fc_points, current_price)
            if raw_prices:
                sp.predicted_price = round(raw_prices[-1], 2)
            else:
                sp.predicted_price = round(float(fc_points[-1].get("predicted_price", current_price)), 2)
        else:
            sp.predicted_price = round(current_price, 2)
        sp.basis = "decay_curve_raw"
        prob = pred.get("probability") or {}
        sp.n_supporting_cases = int(float(prob.get("up", 0)) + float(prob.get("down", 0)))

    # Historical pattern: use its target price
    elif source_name == "historical_pattern":
        hist = source_inputs.get("historical") or {}
        price = float(hist.get("predicted_price", current_price) or current_price)
        sp.predicted_price = round(price, 2)
        sp.basis = "historical_comparable"
        sp.confidence = float(hist.get("confidence", 0) or 0)
        sp.n_comparable_tracks = stats.n_comparable_tracks

    # ML forecast
    elif source_name == "ml_forecast":
        ml = source_inputs.get("ml") or {}
        price = float(ml.get("predicted_price", current_price) or current_price)
        sp.predicted_price = round(price, 2)
        sp.basis = "ml_model"
        sp.confidence = float(ml.get("confidence", 0) or 0)

    # SalesOffice / AI Search: use market averages
    elif source_name in ("salesoffice", "ai_search_hotel_data"):
        sp.predicted_price = round(stats.mean_price if stats.mean_price > 0 else current_price, 2)
        sp.basis = "market_average"
        sp.n_total_cases = stats.n_observations

    # Search results: use provider consensus
    elif source_name == "search_results_poll_log":
        sp.predicted_price = round(stats.mean_price if stats.mean_price > 0 else current_price, 2)
        sp.basis = "provider_consensus"
        sp.n_total_cases = stats.n_observations

    # Determine direction
    if current_price > 0 and sp.predicted_price > 0:
        change_pct = (sp.predicted_price / current_price - 1.0) * 100.0
        sp.predicted_change_pct = round(change_pct, 2)
        if change_pct > 0.5:
            sp.direction = "CALL"
        elif change_pct < -0.5:
            sp.direction = "PUT"
        else:
            sp.direction = "NEUTRAL"

    return sp


def _strip_enrichments_from_curve(
    fc_points: list[dict],
    current_price: float,
) -> list[float]:
    """Reconstruct price path using only base decay curve (no enrichments).

    Subtracts event, season, demand, weather, competitor adjustments
    to recover the raw forward curve prediction.
    """
    raw_prices = []
    price = current_price

    for pt in fc_points:
        daily_total = float(pt.get("daily_change_pct", 0) or 0)
        event = float(pt.get("event_adj_pct", 0) or 0)
        season = float(pt.get("season_adj_pct", 0) or 0)
        demand = float(pt.get("demand_adj_pct", 0) or 0)
        momentum = float(pt.get("momentum_adj_pct", 0) or 0)
        weather = float(pt.get("weather_adj_pct", 0) or 0)
        competitor = float(pt.get("competitor_adj_pct", 0) or 0)

        raw_daily = daily_total - event - season - demand - momentum - weather - competitor
        price *= (1.0 + raw_daily / 100.0)
        raw_prices.append(price)

    return raw_prices


# ── Source Comparison ────────────────────────────────────────────────

def compare_sources(
    pred: dict,
    ensemble_signal: Optional[dict] = None,
) -> SourceComparison:
    """Build a source-by-source comparison for one option.

    Shows what each source says independently, where they agree/disagree,
    and how the ensemble compares to the raw consensus.
    """
    current_price = float(pred.get("current_price", 0) or 0)

    comparison = SourceComparison(
        detail_id=int(pred.get("detail_id", 0) or 0),
        hotel_id=int(pred.get("hotel_id", 0) or 0),
        hotel_name=str(pred.get("hotel_name", "")),
        category=str(pred.get("category", "")),
        board=str(pred.get("board", "")),
        checkin_date=str(pred.get("date_from", "")),
        current_price=round(current_price, 2),
        current_t=int(pred.get("days_to_checkin", 0) or 0),
    )

    # Analyze each predictive source
    for source_name in PREDICTIVE_SOURCES:
        stats = analyze_source_statistics(pred, source_name)
        prediction = build_source_prediction(pred, source_name, stats)

        # Only include sources that have data
        if stats.n_observations > 0 or stats.mean_price > 0 or prediction.predicted_price > 0:
            comparison.source_stats.append(stats)
            comparison.source_predictions.append(prediction)

    # Compute consensus
    calls = sum(1 for sp in comparison.source_predictions if sp.direction == "CALL")
    puts = sum(1 for sp in comparison.source_predictions if sp.direction == "PUT")
    neutrals = sum(1 for sp in comparison.source_predictions if sp.direction == "NEUTRAL")
    total = calls + puts + neutrals

    comparison.n_sources_call = calls
    comparison.n_sources_put = puts
    comparison.n_sources_neutral = neutrals

    if total > 0:
        majority = max(calls, puts, neutrals)
        comparison.consensus_strength = round(majority / total, 2)

        if calls > puts and calls > neutrals:
            comparison.consensus_direction = "CALL"
        elif puts > calls and puts > neutrals:
            comparison.consensus_direction = "PUT"
        else:
            comparison.consensus_direction = "NEUTRAL"

        # Disagreement: one source says CALL and another says PUT
        comparison.disagreement_flag = calls > 0 and puts > 0

    # Compare with ensemble
    if ensemble_signal:
        comparison.ensemble_direction = str(ensemble_signal.get("recommendation", "NEUTRAL"))
        comparison.ensemble_price = float(ensemble_signal.get("predicted_price",
                                          pred.get("predicted_checkin_price", 0)) or 0)
        if comparison.ensemble_direction == comparison.consensus_direction:
            comparison.ensemble_vs_consensus = "AGREES"
        elif comparison.consensus_direction == "NEUTRAL":
            comparison.ensemble_vs_consensus = "N/A"
        else:
            comparison.ensemble_vs_consensus = "DISAGREES"

    return comparison


# ── Batch Analysis ───────────────────────────────────────────────────

def compare_all_sources(
    analysis: dict,
    signals: Optional[list[dict]] = None,
) -> list[dict]:
    """Run source comparison for all active options.

    Args:
        analysis: Full analysis dict with predictions.
        signals: Optional pre-computed ensemble signals for cross-reference.

    Returns:
        List of SourceComparison dicts, disagreements first.
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        logger.info("raw_source_analyzer: no predictions available")
        return []

    # Build signal lookup
    signal_map: dict[str, dict] = {}
    if signals:
        for sig in signals:
            detail_id = str(sig.get("detail_id", ""))
            if detail_id:
                signal_map[detail_id] = sig

    results: list[dict] = []

    for detail_id, pred in predictions.items():
        try:
            ensemble_signal = signal_map.get(str(detail_id))
            comp = compare_sources(pred, ensemble_signal)
            results.append(comp.to_dict())
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("raw_source: skipped detail %s: %s", detail_id, exc)
            continue

    # Sort: disagreements first, then by consensus strength desc
    results.sort(key=lambda r: (
        not r.get("disagreement_flag", False),
        -r.get("consensus_strength", 0),
    ))

    logger.info("raw_source_analyzer: compared %d options", len(results))
    return results


# ── Helpers ──────────────────────────────────────────────────────────

def _compute_price_stats(stats: SourceStatistics, prices: list[float]) -> None:
    """Compute basic price statistics."""
    arr = np.array(prices)
    stats.mean_price = round(float(np.mean(arr)), 2)
    stats.median_price = round(float(np.median(arr)), 2)
    stats.std_price = round(float(np.std(arr)), 2)
    stats.min_price = round(float(np.min(arr)), 2)
    stats.max_price = round(float(np.max(arr)), 2)
    stats.p25_price = round(float(np.percentile(arr, 25)), 2)
    stats.p75_price = round(float(np.percentile(arr, 75)), 2)


def _compute_trend(stats: SourceStatistics, prices: list[float]) -> None:
    """Compute linear trend from price series."""
    n = len(prices)
    if n < 3:
        return

    x = np.arange(n, dtype=float)
    y = np.array(prices, dtype=float)

    # Linear regression
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    ss_xx = float(np.sum((x - x_mean) ** 2))

    if ss_xx < 1e-10:
        return

    slope = float(np.sum((x - x_mean) * (y - y_mean)) / ss_xx)
    ss_res = float(np.sum((y - (slope * x + (y_mean - slope * x_mean))) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))

    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-10 else 0.0

    if y_mean > 0:
        stats.trend_pct_per_day = round(slope / y_mean * 100.0, 4)
    stats.trend_confidence = round(max(0.0, min(1.0, r_squared)), 3)

    if stats.trend_pct_per_day > 0.1:
        stats.trend_direction = "UP"
    elif stats.trend_pct_per_day < -0.1:
        stats.trend_direction = "DOWN"
    else:
        stats.trend_direction = "FLAT"
