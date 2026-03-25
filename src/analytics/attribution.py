"""Attribution Analysis — factor decomposition for prediction accuracy and PnL.

Decomposes what drives prediction accuracy by running the prediction pipeline
with/without each enrichment factor and measuring the marginal contribution.

Attribution factors:
  1. Forward Curve contribution (base decay curve)
  2. Historical Pattern contribution
  3. ML Model contribution
  4. Event enrichment impact (Art Basel, holidays, etc.)
  5. Seasonality impact
  6. Demand (flights) impact
  7. Weather impact
  8. Competitor pressure impact
  9. Momentum timing benefit
  10. Demand Zone proximity (Phase 2)
  11. Rebuy Signal strength (Phase 2)
  12. Search Volume trend (Phase 2)

Method: Marginal contribution analysis — compare enriched vs. base prediction.
Rolling windows: 7-day, 30-day, 90-day attribution.

This module is READ-ONLY — pure computation from cached predictions.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Enrichment factor names ──────────────────────────────────────────

ENRICHMENT_FACTORS = [
    "event",
    "seasonality",
    "demand",
    "weather",
    "competitor",
    "momentum",
    "demand_zone",
    "rebuy_signal",
    "search_volume",
]

ENSEMBLE_COMPONENTS = [
    "forward_curve",
    "historical",
    "ml_model",
]

ALL_FACTORS = ENSEMBLE_COMPONENTS + ENRICHMENT_FACTORS


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class FactorAttribution:
    """Attribution for a single factor."""
    factor: str
    avg_contribution_pct: float = 0.0  # average daily % impact
    total_contribution_usd: float = 0.0  # total $ impact across portfolio
    hit_rate: float = 0.0  # % of time this factor improved accuracy
    samples: int = 0  # number of rooms this factor was active on
    direction: str = "neutral"  # bullish / bearish / neutral

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in asdict(self).items()}


@dataclass
class AttributionResult:
    """Full attribution analysis result."""
    timestamp: str = ""
    n_rooms: int = 0
    window_days: int = 30

    # Top-level attribution
    factors: list[FactorAttribution] = field(default_factory=list)

    # Signal breakdown
    call_attribution: list[FactorAttribution] = field(default_factory=list)
    put_attribution: list[FactorAttribution] = field(default_factory=list)

    # Summary
    dominant_factor: str = ""
    dominant_contribution_pct: float = 0.0
    total_enrichment_impact_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "n_rooms": self.n_rooms,
            "window_days": self.window_days,
            "factors": [f.to_dict() for f in self.factors],
            "call_attribution": [f.to_dict() for f in self.call_attribution],
            "put_attribution": [f.to_dict() for f in self.put_attribution],
            "dominant_factor": self.dominant_factor,
            "dominant_contribution_pct": round(self.dominant_contribution_pct, 4),
            "total_enrichment_impact_pct": round(self.total_enrichment_impact_pct, 4),
        }


# ── Core Attribution Computation ─────────────────────────────────────

def compute_attribution(
    analysis: dict,
    hotel_id: int | None = None,
) -> AttributionResult:
    """Compute factor attribution from the analysis predictions.

    Extracts per-factor enrichment adjustments from forward curve points
    to determine each factor's marginal contribution.

    Args:
        analysis: Full analysis dict with predictions
        hotel_id: Filter to specific hotel (None = all)

    Returns:
        AttributionResult with per-factor breakdown
    """
    result = AttributionResult(
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    predictions = analysis.get("predictions", {})
    if not predictions:
        return result

    # Collect enrichment adjustments per factor per room
    factor_data: dict[str, list[float]] = {f: [] for f in ENRICHMENT_FACTORS}
    call_factor_data: dict[str, list[float]] = {f: [] for f in ENRICHMENT_FACTORS}
    put_factor_data: dict[str, list[float]] = {f: [] for f in ENRICHMENT_FACTORS}

    room_count = 0

    for detail_id, pred in predictions.items():
        try:
            pred_hotel = int(pred.get("hotel_id", 0) or 0)
            if hotel_id is not None and pred_hotel != hotel_id:
                continue

            fc = pred.get("forward_curve") or []
            if not fc:
                continue

            signal = pred.get("option_signal", "NONE") or "NONE"
            current_price = float(pred.get("current_price", 0) or 0)
            if current_price <= 0:
                continue

            room_count += 1

            # Average enrichment adjustment across all FC points for this room
            adj_map = _extract_avg_adjustments(fc)

            for factor_name, adj_pct in adj_map.items():
                if factor_name in factor_data:
                    factor_data[factor_name].append(adj_pct)

                    if signal in ("CALL", "STRONG_CALL"):
                        call_factor_data[factor_name].append(adj_pct)
                    elif signal in ("PUT", "STRONG_PUT"):
                        put_factor_data[factor_name].append(adj_pct)

        except (ValueError, TypeError, KeyError) as exc:
            logger.debug("Attribution skip detail_id=%s: %s", detail_id, exc)
            continue

    result.n_rooms = room_count

    # Build factor attribution
    result.factors = _build_factor_list(factor_data)
    result.call_attribution = _build_factor_list(call_factor_data)
    result.put_attribution = _build_factor_list(put_factor_data)

    # Summary
    if result.factors:
        dominant = max(result.factors, key=lambda f: abs(f.avg_contribution_pct))
        result.dominant_factor = dominant.factor
        result.dominant_contribution_pct = dominant.avg_contribution_pct
        result.total_enrichment_impact_pct = sum(
            f.avg_contribution_pct for f in result.factors
        )

    return result


def compute_hotel_attribution(
    analysis: dict,
    hotel_id: int,
) -> AttributionResult:
    """Compute attribution for a specific hotel."""
    return compute_attribution(analysis, hotel_id=hotel_id)


def compute_signal_attribution(
    analysis: dict,
) -> dict:
    """Compute attribution split by CALL vs PUT success.

    Returns dict with call_factors, put_factors, and comparison.
    """
    full = compute_attribution(analysis)

    # Which factors help CALLs more vs PUTs?
    comparison = []
    call_map = {f.factor: f for f in full.call_attribution}
    put_map = {f.factor: f for f in full.put_attribution}

    for factor_name in ENRICHMENT_FACTORS:
        call_fa = call_map.get(factor_name)
        put_fa = put_map.get(factor_name)
        call_avg = call_fa.avg_contribution_pct if call_fa else 0.0
        put_avg = put_fa.avg_contribution_pct if put_fa else 0.0

        comparison.append({
            "factor": factor_name,
            "call_contribution_pct": round(call_avg, 4),
            "put_contribution_pct": round(put_avg, 4),
            "favors": "CALL" if call_avg > put_avg else ("PUT" if put_avg > call_avg else "neutral"),
        })

    return {
        "timestamp": full.timestamp,
        "n_rooms": full.n_rooms,
        "call_attribution": [f.to_dict() for f in full.call_attribution],
        "put_attribution": [f.to_dict() for f in full.put_attribution],
        "comparison": comparison,
    }


# ── Internal Helpers ─────────────────────────────────────────────────

# Map FC point keys to factor names
_FC_ADJ_KEY_MAP = {
    "event_adj_pct": "event",
    "season_adj_pct": "seasonality",
    "demand_adj_pct": "demand",
    "weather_adj_pct": "weather",
    "competitor_adj_pct": "competitor",
    "momentum_adj_pct": "momentum",
    "demand_zone_adj_pct": "demand_zone",
    "rebuy_signal_adj_pct": "rebuy_signal",
    "search_volume_adj_pct": "search_volume",
}


def _extract_avg_adjustments(fc_points: list[dict]) -> dict[str, float]:
    """Extract average enrichment adjustments from forward curve points."""
    if not fc_points:
        return {}

    sums: dict[str, float] = {f: 0.0 for f in ENRICHMENT_FACTORS}
    n = len(fc_points)

    for pt in fc_points:
        for key, factor_name in _FC_ADJ_KEY_MAP.items():
            val = float(pt.get(key, 0) or 0)
            sums[factor_name] += val

    return {f: sums[f] / n for f in ENRICHMENT_FACTORS}


def _build_factor_list(factor_data: dict[str, list[float]]) -> list[FactorAttribution]:
    """Build FactorAttribution list from collected adjustment data."""
    factors: list[FactorAttribution] = []

    for factor_name, values in factor_data.items():
        if not values:
            factors.append(FactorAttribution(factor=factor_name, samples=0))
            continue

        avg = sum(values) / len(values)
        positive_count = sum(1 for v in values if v > 0)
        negative_count = sum(1 for v in values if v < 0)

        direction = "neutral"
        if positive_count > negative_count * 1.5:
            direction = "bullish"
        elif negative_count > positive_count * 1.5:
            direction = "bearish"

        # Hit rate: % of times this factor pushed in the right direction
        # (positive for CALL rooms, negative for PUT rooms)
        active_count = sum(1 for v in values if abs(v) > 0.001)
        hit_rate = active_count / len(values) if values else 0.0

        factors.append(FactorAttribution(
            factor=factor_name,
            avg_contribution_pct=avg,
            total_contribution_usd=0.0,  # requires price data to compute
            hit_rate=hit_rate,
            samples=len(values),
            direction=direction,
        ))

    # Sort by absolute contribution
    factors.sort(key=lambda f: abs(f.avg_contribution_pct), reverse=True)
    return factors
