"""Path Forecast Engine — full price path analysis with turning points.

Instead of a single CALL/PUT signal, this engine analyzes the complete
predicted price path from T=now to T=0 (check-in) and identifies:

- All turning points (local minima = buy opportunities, local maxima = sell opportunities)
- Expected number of ups and downs along the path
- Minimum and maximum predicted prices with their T values
- Optimal entry/exit points for trading
- Per-segment direction, magnitude, and probability

This treats each room option as having a FULL LIFECYCLE, not a single direction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class PathSegment:
    """One directional segment of the price path (up or down)."""
    t_start: int              # T at segment start (higher T = further from check-in)
    t_end: int                # T at segment end
    date_start: str           # Calendar date at start
    date_end: str             # Calendar date at end
    price_start: float        # Price at segment start
    price_end: float          # Price at segment end
    direction: str            # "UP" or "DOWN"
    change_pct: float         # % change over segment
    change_abs: float         # Absolute $ change
    duration_days: int        # Number of days in segment
    avg_daily_change_pct: float  # Average daily % change
    confidence: float         # Average confidence in this segment (0-1)


@dataclass
class TurningPoint:
    """A local min or max on the price path."""
    t: int                    # T (days to check-in) at this point
    date: str                 # Calendar date
    price: float              # Predicted price
    type: str                 # "MIN" (buy opportunity) or "MAX" (sell opportunity)
    lower_bound: float        # 95% CI lower
    upper_bound: float        # 95% CI upper
    significance: float       # How significant vs noise (0-1)


@dataclass
class PathForecast:
    """Complete path forecast for one option/room."""
    detail_id: int
    hotel_id: int
    hotel_name: str
    category: str
    board: str
    checkin_date: str
    current_price: float
    current_t: int

    # Path summary
    predicted_min_price: float = 0.0
    predicted_min_t: int = 0
    predicted_min_date: str = ""
    predicted_max_price: float = 0.0
    predicted_max_t: int = 0
    predicted_max_date: str = ""
    predicted_final_price: float = 0.0

    # Movement counts
    num_up_segments: int = 0
    num_down_segments: int = 0
    total_up_pct: float = 0.0       # Cumulative upward movement
    total_down_pct: float = 0.0     # Cumulative downward movement (negative)
    net_change_pct: float = 0.0     # Net change from current to final

    # Trading signals
    best_buy_t: int = 0             # T with lowest predicted price
    best_buy_date: str = ""
    best_buy_price: float = 0.0
    best_sell_t: int = 0            # T with highest predicted price after best_buy
    best_sell_date: str = ""
    best_sell_price: float = 0.0
    max_trade_profit_pct: float = 0.0  # Best buy→sell profit %

    # Components
    segments: list[PathSegment] = field(default_factory=list)
    turning_points: list[TurningPoint] = field(default_factory=list)
    daily_prices: list[dict] = field(default_factory=list)  # Full day-by-day path

    # Metadata
    data_quality: str = "medium"    # high/medium/low/extrapolated
    source: str = "ensemble"        # ensemble, forward_curve, raw_salesoffice, etc.
    enrichments_applied: bool = True

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict."""
        result = asdict(self)
        return result


# ── Smoothing ────────────────────────────────────────────────────────

# Minimum price change (%) to register as a new segment direction.
# Below this threshold, movement is considered noise.
DIRECTION_THRESHOLD_PCT = 0.5

# Minimum segment duration (days) to avoid micro-oscillation noise
MIN_SEGMENT_DAYS = 2


def _smooth_prices(daily_prices: list[dict], window: int = 3) -> list[float]:
    """Simple moving average to reduce noise for turning point detection.

    Uses a centered window. Falls back to raw prices at the edges.
    """
    prices = [p["predicted_price"] for p in daily_prices]
    n = len(prices)
    if n <= window:
        return prices

    smoothed = list(prices)  # copy
    half = window // 2
    for i in range(half, n - half):
        smoothed[i] = sum(prices[i - half: i + half + 1]) / window

    return smoothed


# ── Core Analysis ────────────────────────────────────────────────────

def analyze_path(
    forward_curve_points: list[dict],
    detail_id: int,
    hotel_id: int,
    hotel_name: str,
    category: str,
    board: str,
    checkin_date: str,
    current_price: float,
    current_t: int,
    source: str = "ensemble",
    enrichments_applied: bool = True,
    data_quality: str = "medium",
) -> PathForecast:
    """Analyze a forward curve to produce a full path forecast.

    Args:
        forward_curve_points: List of ForwardPoint dicts from predict_forward_curve
            or from raw source analysis. Each must have at minimum:
            - date, t, predicted_price, daily_change_pct
            Optional: lower_bound, upper_bound, volatility_at_t
        detail_id: Room detail ID
        hotel_id: Hotel ID
        hotel_name: Hotel name
        category: Room category
        board: Board type
        checkin_date: Check-in date string
        current_price: Current observed price
        current_t: Current T (days to check-in)
        source: Data source label
        enrichments_applied: Whether enrichments were included
        data_quality: Data density quality level

    Returns:
        PathForecast with complete path analysis.
    """
    forecast = PathForecast(
        detail_id=detail_id,
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        category=category,
        board=board,
        checkin_date=checkin_date,
        current_price=round(current_price, 2),
        current_t=current_t,
        source=source,
        enrichments_applied=enrichments_applied,
        data_quality=data_quality,
    )

    if not forward_curve_points:
        forecast.predicted_final_price = current_price
        forecast.predicted_min_price = current_price
        forecast.predicted_max_price = current_price
        return forecast

    # Build daily prices list (including current as day 0)
    daily_prices = [
        {
            "date": "today",
            "t": current_t,
            "predicted_price": round(current_price, 2),
            "daily_change_pct": 0.0,
            "lower_bound": round(current_price, 2),
            "upper_bound": round(current_price, 2),
            "volatility_at_t": 0.0,
        }
    ]
    for pt in forward_curve_points:
        daily_prices.append({
            "date": pt.get("date", ""),
            "t": int(pt.get("t", 0)),
            "predicted_price": round(float(pt.get("predicted_price", current_price)), 2),
            "daily_change_pct": round(float(pt.get("daily_change_pct", 0)), 4),
            "lower_bound": round(float(pt.get("lower_bound", pt.get("predicted_price", current_price))), 2),
            "upper_bound": round(float(pt.get("upper_bound", pt.get("predicted_price", current_price))), 2),
            "volatility_at_t": round(float(pt.get("volatility_at_t", 0)), 4),
        })

    forecast.daily_prices = daily_prices

    # Final price
    forecast.predicted_final_price = daily_prices[-1]["predicted_price"]
    forecast.net_change_pct = round(
        (forecast.predicted_final_price / current_price - 1.0) * 100.0
        if current_price > 0 else 0.0, 2
    )

    # Find global min and max
    _find_extremes(forecast, daily_prices)

    # Find turning points (smoothed to avoid noise)
    smoothed = _smooth_prices(daily_prices)
    _find_turning_points(forecast, daily_prices, smoothed)

    # Build directional segments
    _build_segments(forecast, daily_prices)

    # Compute trading opportunities
    _find_best_trade(forecast, daily_prices)

    return forecast


def _find_extremes(forecast: PathForecast, daily_prices: list[dict]) -> None:
    """Find global min and max prices in the path."""
    min_price = float("inf")
    max_price = float("-inf")
    min_idx = 0
    max_idx = 0

    for i, dp in enumerate(daily_prices):
        price = dp["predicted_price"]
        if price < min_price:
            min_price = price
            min_idx = i
        if price > max_price:
            max_price = price
            max_idx = i

    forecast.predicted_min_price = round(min_price, 2)
    forecast.predicted_min_t = daily_prices[min_idx]["t"]
    forecast.predicted_min_date = daily_prices[min_idx]["date"]
    forecast.predicted_max_price = round(max_price, 2)
    forecast.predicted_max_t = daily_prices[max_idx]["t"]
    forecast.predicted_max_date = daily_prices[max_idx]["date"]


def _find_turning_points(
    forecast: PathForecast,
    daily_prices: list[dict],
    smoothed_prices: list[float],
) -> None:
    """Identify local minima and maxima in the smoothed price path."""
    n = len(smoothed_prices)
    if n < 3:
        return

    turning_points: list[TurningPoint] = []

    for i in range(1, n - 1):
        prev_p = smoothed_prices[i - 1]
        curr_p = smoothed_prices[i]
        next_p = smoothed_prices[i + 1]

        # Skip if changes are below noise threshold
        change_from_prev = abs(curr_p - prev_p) / prev_p * 100 if prev_p > 0 else 0
        change_to_next = abs(next_p - curr_p) / curr_p * 100 if curr_p > 0 else 0

        if change_from_prev < DIRECTION_THRESHOLD_PCT * 0.3 and change_to_next < DIRECTION_THRESHOLD_PCT * 0.3:
            continue

        dp = daily_prices[i]
        is_min = curr_p <= prev_p and curr_p <= next_p and curr_p < prev_p
        is_max = curr_p >= prev_p and curr_p >= next_p and curr_p > prev_p

        if is_min or is_max:
            # Significance: how big is the turning point relative to overall price range?
            price_range = max(smoothed_prices) - min(smoothed_prices)
            if price_range > 0:
                local_magnitude = max(abs(curr_p - prev_p), abs(curr_p - next_p))
                significance = min(1.0, local_magnitude / price_range)
            else:
                significance = 0.0

            turning_points.append(TurningPoint(
                t=dp["t"],
                date=dp["date"],
                price=round(dp["predicted_price"], 2),
                type="MIN" if is_min else "MAX",
                lower_bound=round(dp.get("lower_bound", dp["predicted_price"]), 2),
                upper_bound=round(dp.get("upper_bound", dp["predicted_price"]), 2),
                significance=round(significance, 3),
            ))

    # Filter out insignificant turning points
    forecast.turning_points = [tp for tp in turning_points if tp.significance >= 0.1]


def _build_segments(forecast: PathForecast, daily_prices: list[dict]) -> None:
    """Build directional segments from the daily price path.

    A new segment starts when direction reverses and the cumulative
    change exceeds the noise threshold.
    """
    if len(daily_prices) < 2:
        return

    segments: list[PathSegment] = []
    seg_start_idx = 0
    current_direction: Optional[str] = None
    peak_in_segment = daily_prices[0]["predicted_price"]
    trough_in_segment = daily_prices[0]["predicted_price"]

    for i in range(1, len(daily_prices)):
        price = daily_prices[i]["predicted_price"]
        start_price = daily_prices[seg_start_idx]["predicted_price"]

        if start_price <= 0:
            continue

        change_pct = (price / start_price - 1.0) * 100.0
        new_direction = "UP" if change_pct > 0 else "DOWN"

        peak_in_segment = max(peak_in_segment, price)
        trough_in_segment = min(trough_in_segment, price)

        # Direction reversal detection: check if we've reversed significantly
        if current_direction is not None and new_direction != current_direction:
            reversal_magnitude = abs(change_pct)
            if reversal_magnitude >= DIRECTION_THRESHOLD_PCT and (i - seg_start_idx) >= MIN_SEGMENT_DAYS:
                # Close the previous segment at i-1
                _close_segment(segments, daily_prices, seg_start_idx, i - 1)
                seg_start_idx = i - 1
                peak_in_segment = price
                trough_in_segment = price
                current_direction = new_direction
        elif current_direction is None and abs(change_pct) >= DIRECTION_THRESHOLD_PCT:
            current_direction = new_direction

    # Close the last segment
    if seg_start_idx < len(daily_prices) - 1:
        _close_segment(segments, daily_prices, seg_start_idx, len(daily_prices) - 1)

    forecast.segments = segments
    forecast.num_up_segments = sum(1 for s in segments if s.direction == "UP")
    forecast.num_down_segments = sum(1 for s in segments if s.direction == "DOWN")
    forecast.total_up_pct = round(sum(s.change_pct for s in segments if s.direction == "UP"), 2)
    forecast.total_down_pct = round(sum(s.change_pct for s in segments if s.direction == "DOWN"), 2)


def _close_segment(
    segments: list[PathSegment],
    daily_prices: list[dict],
    start_idx: int,
    end_idx: int,
) -> None:
    """Create a PathSegment from start to end index."""
    start = daily_prices[start_idx]
    end = daily_prices[end_idx]
    price_start = start["predicted_price"]
    price_end = end["predicted_price"]

    if price_start <= 0:
        return

    change_pct = (price_end / price_start - 1.0) * 100.0
    duration = end_idx - start_idx

    # Compute average confidence from volatility
    volatilities = [
        daily_prices[j].get("volatility_at_t", 0)
        for j in range(start_idx, end_idx + 1)
    ]
    avg_vol = sum(volatilities) / len(volatilities) if volatilities else 0
    # Lower volatility = higher confidence in direction
    confidence = max(0.2, min(0.95, 1.0 - avg_vol / 5.0))

    segments.append(PathSegment(
        t_start=start["t"],
        t_end=end["t"],
        date_start=start["date"],
        date_end=end["date"],
        price_start=round(price_start, 2),
        price_end=round(price_end, 2),
        direction="UP" if change_pct > 0 else "DOWN",
        change_pct=round(change_pct, 2),
        change_abs=round(price_end - price_start, 2),
        duration_days=max(duration, 1),
        avg_daily_change_pct=round(change_pct / max(duration, 1), 4),
        confidence=round(confidence, 3),
    ))


def _find_best_trade(forecast: PathForecast, daily_prices: list[dict]) -> None:
    """Find the optimal buy-low → sell-high opportunity along the path.

    Scans for the maximum profit trade: buy at any point, sell at any later point.
    """
    n = len(daily_prices)
    if n < 2:
        return

    best_profit_pct = 0.0
    best_buy_idx = 0
    best_sell_idx = 0
    min_price_so_far = daily_prices[0]["predicted_price"]
    min_idx_so_far = 0

    for i in range(1, n):
        price = daily_prices[i]["predicted_price"]
        if min_price_so_far > 0:
            profit_pct = (price / min_price_so_far - 1.0) * 100.0
            if profit_pct > best_profit_pct:
                best_profit_pct = profit_pct
                best_buy_idx = min_idx_so_far
                best_sell_idx = i

        if price < min_price_so_far:
            min_price_so_far = price
            min_idx_so_far = i

    if best_profit_pct > 0:
        buy = daily_prices[best_buy_idx]
        sell = daily_prices[best_sell_idx]
        forecast.best_buy_t = buy["t"]
        forecast.best_buy_date = buy["date"]
        forecast.best_buy_price = round(buy["predicted_price"], 2)
        forecast.best_sell_t = sell["t"]
        forecast.best_sell_date = sell["date"]
        forecast.best_sell_price = round(sell["predicted_price"], 2)
        forecast.max_trade_profit_pct = round(best_profit_pct, 2)


# ── Batch Analysis ───────────────────────────────────────────────────

def analyze_portfolio_paths(
    analysis: dict,
    source: str = "ensemble",
) -> list[dict]:
    """Analyze path forecasts for all active options in the portfolio.

    Args:
        analysis: The full analysis dict from _get_or_run_analysis(),
                  containing 'predictions' with forward_curve per detail.
        source: Label for the data source.

    Returns:
        List of PathForecast dicts, sorted by max_trade_profit_pct descending.
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        logger.info("path_forecast: no predictions available")
        return []

    results: list[dict] = []

    for detail_id, pred in predictions.items():
        try:
            fc_points = pred.get("forward_curve") or []
            if not fc_points:
                continue

            current_price = float(pred.get("current_price", 0) or 0)
            if current_price <= 0:
                continue

            pf = analyze_path(
                forward_curve_points=fc_points,
                detail_id=int(detail_id),
                hotel_id=int(pred.get("hotel_id", 0)),
                hotel_name=str(pred.get("hotel_name", "")),
                category=str(pred.get("category", "")),
                board=str(pred.get("board", "")),
                checkin_date=str(pred.get("date_from", "")),
                current_price=current_price,
                current_t=int(pred.get("days_to_checkin", 0)),
                source=source,
                enrichments_applied=True,
                data_quality=str(pred.get("confidence_quality", "medium")),
            )

            results.append(pf.to_dict())

        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("path_forecast: skipped detail %s: %s", detail_id, exc)
            continue

    # Sort by best trading opportunity
    results.sort(key=lambda r: r.get("max_trade_profit_pct", 0), reverse=True)

    logger.info("path_forecast: analyzed %d options", len(results))
    return results
