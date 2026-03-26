"""Cross-Hotel Correlation Matrix — price co-movement across Miami hotels.

Correlation types:
  - Hotel-to-hotel: Do prices move together?
  - Category-to-category: Standard vs Deluxe dynamics
  - Board-to-board: RO vs BB co-movement

Method: Rolling Pearson correlation on daily % changes from forward curve.
Window: 30-day rolling (configurable).
Output: N×N correlation matrix + heatmap data.

This module is READ-ONLY — pure computation from cached analysis predictions.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

DEFAULT_WINDOW_DAYS = 30
MIN_OVERLAP_POINTS = 5  # minimum shared FC points to compute correlation


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class CorrelationPair:
    """Correlation between two hotels."""
    hotel_a_id: int
    hotel_a_name: str
    hotel_b_id: int
    hotel_b_name: str
    correlation: float  # -1 to 1
    samples: int  # number of overlapping data points
    relationship: str = ""  # "strong_positive", "moderate_positive", "weak", etc.

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in asdict(self).items()}


@dataclass
class CorrelationMatrix:
    """Full correlation analysis result."""
    timestamp: str = ""
    n_hotels: int = 0
    window_days: int = DEFAULT_WINDOW_DAYS

    # Matrix data (for heatmap rendering)
    hotel_ids: list[int] = field(default_factory=list)
    hotel_names: list[str] = field(default_factory=list)
    matrix: list[list[float]] = field(default_factory=list)  # NxN

    # Top correlations
    strongest_positive: list[CorrelationPair] = field(default_factory=list)
    strongest_negative: list[CorrelationPair] = field(default_factory=list)

    # Category correlations
    category_matrix: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "n_hotels": self.n_hotels,
            "window_days": self.window_days,
            "hotel_ids": self.hotel_ids,
            "hotel_names": self.hotel_names,
            "matrix": [[round(v, 4) for v in row] for row in self.matrix],
            "strongest_positive": [p.to_dict() for p in self.strongest_positive],
            "strongest_negative": [p.to_dict() for p in self.strongest_negative],
            "category_matrix": self.category_matrix,
        }


# ── Core Computation ─────────────────────────────────────────────────

def compute_correlation_matrix(
    analysis: dict,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> CorrelationMatrix:
    """Compute hotel-to-hotel price correlation from forward curve data.

    For each hotel, extracts average daily_change_pct per FC date,
    then computes Pearson correlation between each pair.

    Args:
        analysis: Full analysis dict with predictions.
        window_days: Number of FC days to use for correlation.

    Returns:
        CorrelationMatrix with NxN matrix and ranked pairs.
    """
    result = CorrelationMatrix(
        timestamp=datetime.utcnow().isoformat() + "Z",
        window_days=window_days,
    )

    predictions = analysis.get("predictions", {})
    if not predictions:
        return result

    # Step 1: Collect daily_change_pct per hotel, keyed by FC date index
    # hotel_id → {t_index: [daily_change_pct values across rooms]}
    hotel_changes: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    hotel_names: dict[int, str] = {}

    for detail_id, pred in predictions.items():
        hotel_id = int(pred.get("hotel_id", 0) or 0)
        if hotel_id <= 0:
            continue

        hotel_names[hotel_id] = str(pred.get("hotel_name", f"Hotel {hotel_id}"))

        fc = pred.get("forward_curve") or []
        for i, pt in enumerate(fc[:window_days]):
            change = float(pt.get("daily_change_pct", 0) or 0)
            hotel_changes[hotel_id][i].append(change)

    if len(hotel_changes) < 2:
        return result

    # Step 2: Average daily change per hotel per t-index
    hotel_series: dict[int, list[float]] = {}
    for hid, t_map in hotel_changes.items():
        series = []
        for t in range(window_days):
            values = t_map.get(t, [])
            if values:
                series.append(sum(values) / len(values))
            else:
                series.append(0.0)
        hotel_series[hid] = series

    # Step 3: Build correlation matrix
    sorted_ids = sorted(hotel_series.keys())
    n = len(sorted_ids)
    result.hotel_ids = sorted_ids
    result.hotel_names = [hotel_names.get(hid, "") for hid in sorted_ids]
    result.n_hotels = n

    matrix = [[0.0] * n for _ in range(n)]
    pairs: list[CorrelationPair] = []

    for i in range(n):
        matrix[i][i] = 1.0  # self-correlation
        for j in range(i + 1, n):
            hid_a = sorted_ids[i]
            hid_b = sorted_ids[j]
            series_a = hotel_series[hid_a]
            series_b = hotel_series[hid_b]

            corr, samples = _pearson_correlation(series_a, series_b)
            matrix[i][j] = corr
            matrix[j][i] = corr

            pairs.append(CorrelationPair(
                hotel_a_id=hid_a,
                hotel_a_name=hotel_names.get(hid_a, ""),
                hotel_b_id=hid_b,
                hotel_b_name=hotel_names.get(hid_b, ""),
                correlation=corr,
                samples=samples,
                relationship=_classify_correlation(corr),
            ))

    result.matrix = matrix

    # Rank pairs
    pairs.sort(key=lambda p: p.correlation, reverse=True)
    result.strongest_positive = [p for p in pairs if p.correlation > 0][:5]
    result.strongest_negative = [p for p in pairs if p.correlation < 0][-5:][::-1]

    # Step 4: Category correlation
    result.category_matrix = _compute_category_correlation(predictions, window_days)

    return result


# ── Category Correlation ─────────────────────────────────────────────

def _compute_category_correlation(
    predictions: dict,
    window_days: int,
) -> dict:
    """Compute correlation between room categories across all hotels."""
    cat_changes: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for detail_id, pred in predictions.items():
        category = str(pred.get("category", "")).lower()
        if not category:
            continue

        fc = pred.get("forward_curve") or []
        for i, pt in enumerate(fc[:window_days]):
            change = float(pt.get("daily_change_pct", 0) or 0)
            cat_changes[category][i].append(change)

    # Average per category per t
    cat_series: dict[str, list[float]] = {}
    for cat, t_map in cat_changes.items():
        series = []
        for t in range(window_days):
            values = t_map.get(t, [])
            series.append(sum(values) / len(values) if values else 0.0)
        cat_series[cat] = series

    if len(cat_series) < 2:
        return {}

    sorted_cats = sorted(cat_series.keys())
    result: dict[str, dict[str, float]] = {}

    for i, cat_a in enumerate(sorted_cats):
        result[cat_a] = {}
        for j, cat_b in enumerate(sorted_cats):
            if cat_a == cat_b:
                result[cat_a][cat_b] = 1.0
            else:
                corr, _ = _pearson_correlation(cat_series[cat_a], cat_series[cat_b])
                result[cat_a][cat_b] = round(corr, 4)

    return result


# ── Helpers ──────────────────────────────────────────────────────────

def _pearson_correlation(x: list[float], y: list[float]) -> tuple[float, int]:
    """Compute Pearson correlation coefficient.

    Returns (correlation, n_samples). Returns (0.0, 0) if insufficient data.
    """
    n = min(len(x), len(y))
    if n < MIN_OVERLAP_POINTS:
        return 0.0, 0

    x = x[:n]
    y = y[:n]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    var_y = sum((y[i] - mean_y) ** 2 for i in range(n))

    denom = math.sqrt(var_x * var_y)
    if denom < 1e-12:
        return 0.0, n

    return cov / denom, n


def _classify_correlation(r: float) -> str:
    """Classify correlation strength."""
    abs_r = abs(r)
    if abs_r >= 0.7:
        return "strong_positive" if r > 0 else "strong_negative"
    elif abs_r >= 0.4:
        return "moderate_positive" if r > 0 else "moderate_negative"
    elif abs_r >= 0.2:
        return "weak_positive" if r > 0 else "weak_negative"
    else:
        return "negligible"
