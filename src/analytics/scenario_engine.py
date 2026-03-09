"""What-if scenario analysis for the prediction engine.

Applies override factors to cached predictions to model hypothetical
scenarios (event cancellations, weather events, demand surges, etc.)
without re-running the full prediction pipeline.

Usage:
    from src.analytics.scenario_engine import ScenarioEngine
    engine = ScenarioEngine(predictions)
    result = engine.run_scenario({"demand_multiplier": 1.5, "event_impact": 0})
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Preset scenarios ────────────────────────────────────────────────

PRESETS: dict[str, dict] = {
    "art_basel_cancelled": {
        "name": "Art Basel Cancelled",
        "description": "Major art event cancelled — demand drops significantly",
        "overrides": {"event_impact": 0, "demand_multiplier": 0.7},
    },
    "hurricane_warning": {
        "name": "Hurricane Warning",
        "description": "Category 3+ hurricane approaching — tourism halts",
        "overrides": {"weather_severity": "hurricane", "demand_multiplier": 0.5},
    },
    "peak_season_surge": {
        "name": "Peak Season Surge",
        "description": "Exceptional demand during peak season with competitor price increases",
        "overrides": {"demand_multiplier": 1.5, "competitor_delta": 15.0},
    },
    "recession_impact": {
        "name": "Recession Impact",
        "description": "Economic downturn reduces travel spend, competitors cut prices",
        "overrides": {"demand_multiplier": 0.6, "competitor_delta": -10.0},
    },
    "flight_surge": {
        "name": "Flight Surge",
        "description": "Airline capacity increase drives inbound travel surge",
        "overrides": {"flight_delta": 40.0, "demand_multiplier": 1.3},
    },
}


# Weather severity impact multipliers (daily % impact applied over prediction horizon)
WEATHER_IMPACTS: dict[str, float] = {
    "normal": 0.0,
    "rain": -0.05,
    "storm": -0.10,
    "heatwave": -0.03,
    "hurricane": -0.15,
    "clear": 0.02,
}

# Seasonal override multipliers (applied as % adjustment to final price)
SEASONAL_MULTIPLIERS: dict[str, float] = {
    "peak": 1.10,       # +10% for peak season
    "shoulder": 1.0,    # No adjustment
    "off": 0.88,        # -12% for off season
}


@dataclass
class ScenarioOverrides:
    """Validated scenario parameters."""
    event_impact: float | None = None      # 0-200 (percentage of normal event impact)
    flight_delta: float | None = None      # -50 to +50 (% change in flight demand)
    weather_severity: str | None = None    # normal/rain/storm/heatwave/hurricane/clear
    competitor_delta: float | None = None  # -20 to +20 (% competitor price change)
    demand_multiplier: float | None = None # 0.5 to 2.0
    seasonal_override: str | None = None   # peak/shoulder/off

    @classmethod
    def from_dict(cls, d: dict) -> ScenarioOverrides:
        return cls(
            event_impact=_clamp(d.get("event_impact"), 0, 200),
            flight_delta=_clamp(d.get("flight_delta"), -50, 50),
            weather_severity=d.get("weather_severity") if d.get("weather_severity") in WEATHER_IMPACTS else None,
            competitor_delta=_clamp(d.get("competitor_delta"), -20, 20),
            demand_multiplier=_clamp(d.get("demand_multiplier"), 0.5, 2.0),
            seasonal_override=d.get("seasonal_override") if d.get("seasonal_override") in SEASONAL_MULTIPLIERS else None,
        )


def _clamp(val, lo, hi) -> float | None:
    if val is None:
        return None
    try:
        v = float(val)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return None


class ScenarioEngine:
    """Apply scenario overrides to prediction results."""

    def __init__(self, predictions: dict):
        """Initialize with predictions dict (detail_id -> prediction)."""
        self.predictions = predictions

    def run_scenario(self, overrides: dict) -> dict:
        """Run a single scenario against current predictions.

        Args:
            overrides: Dict of override parameters.

        Returns:
            Dict with scenario metadata and delta table.
        """
        params = ScenarioOverrides.from_dict(overrides)

        deltas = []
        for detail_id, pred in self.predictions.items():
            baseline_price = float(pred.get("predicted_checkin_price", 0) or 0)
            current_price = float(pred.get("current_price", 0) or 0)

            if baseline_price <= 0 or current_price <= 0:
                continue

            # Compute scenario adjustment
            adjustment = self._compute_adjustment(pred, params)
            scenario_price = round(baseline_price * adjustment, 2)

            # Clamp to reasonable range (40% - 250% of current price)
            scenario_price = max(current_price * 0.40, min(current_price * 2.50, scenario_price))

            delta_dollars = round(scenario_price - baseline_price, 2)
            delta_pct = round((delta_dollars / baseline_price) * 100, 2) if baseline_price > 0 else 0.0

            # Check if signal would change
            baseline_signal = self._derive_signal(pred.get("expected_change_pct", 0))
            scenario_change_pct = ((scenario_price - current_price) / current_price * 100) if current_price > 0 else 0
            scenario_signal = self._derive_signal(scenario_change_pct)

            deltas.append({
                "detail_id": str(detail_id),
                "hotel_id": int(pred.get("hotel_id", 0)),
                "current_price": current_price,
                "baseline_price": baseline_price,
                "scenario_price": scenario_price,
                "delta_dollars": delta_dollars,
                "delta_pct": delta_pct,
                "baseline_signal": baseline_signal,
                "scenario_signal": scenario_signal,
                "signal_changed": baseline_signal != scenario_signal,
            })

        # Sort by absolute delta descending
        deltas.sort(key=lambda d: abs(d["delta_pct"]), reverse=True)

        # Summary stats
        total = len(deltas)
        signal_changed = sum(1 for d in deltas if d["signal_changed"])
        avg_delta = sum(d["delta_pct"] for d in deltas) / total if total > 0 else 0

        return {
            "overrides_applied": {k: v for k, v in overrides.items() if v is not None},
            "total_rooms": total,
            "signal_changes": signal_changed,
            "avg_delta_pct": round(avg_delta, 2),
            "deltas": deltas,
        }

    def compare_scenarios(self, scenarios: list[dict]) -> dict:
        """Run multiple scenarios and return comparison.

        Args:
            scenarios: List of dicts, each with "name" and "overrides".

        Returns:
            Comparison table across all scenarios.
        """
        results = []
        for scenario in scenarios[:5]:  # Cap at 5
            name = scenario.get("name", "unnamed")
            overrides = scenario.get("overrides", {})
            result = self.run_scenario(overrides)
            results.append({
                "name": name,
                "total_rooms": result["total_rooms"],
                "signal_changes": result["signal_changes"],
                "avg_delta_pct": result["avg_delta_pct"],
                "overrides": result["overrides_applied"],
            })

        return {
            "scenarios_compared": len(results),
            "results": results,
        }

    def _compute_adjustment(self, pred: dict, params: ScenarioOverrides) -> float:
        """Compute the multiplicative price adjustment for a scenario."""
        adjustment = 1.0

        # Event impact override: scale from baseline
        if params.event_impact is not None:
            # Baseline assumes 100% event impact
            # If event_impact=0 (cancelled), remove event effect
            # If event_impact=150, 50% more than normal
            event_factor = (params.event_impact - 100) / 100.0
            # Typical event impact is ~0.03-0.40% per day; scale modestly
            days = int(pred.get("days_to_checkin", 30) or 30)
            daily_impact = 0.002 * event_factor  # 0.2% daily
            adjustment *= (1.0 + daily_impact * min(days, 30))

        # Flight demand delta
        if params.flight_delta is not None:
            # Flight delta of +50% means more flights → more demand → higher prices
            flight_impact = params.flight_delta / 100.0 * 0.15  # 15% of flight change
            adjustment *= (1.0 + flight_impact)

        # Weather severity
        if params.weather_severity is not None:
            weather_pct = WEATHER_IMPACTS.get(params.weather_severity, 0.0)
            days = int(pred.get("days_to_checkin", 30) or 30)
            adjustment *= (1.0 + weather_pct * min(days, 14))

        # Competitor delta
        if params.competitor_delta is not None:
            # Competitors raising prices → we can raise too
            comp_impact = params.competitor_delta / 100.0 * 0.5  # 50% pass-through
            adjustment *= (1.0 + comp_impact)

        # Demand multiplier
        if params.demand_multiplier is not None:
            # Demand multiplier directly scales price proportionally (dampened)
            demand_factor = (params.demand_multiplier - 1.0) * 0.3  # 30% demand elasticity
            adjustment *= (1.0 + demand_factor)

        # Seasonal override
        if params.seasonal_override is not None:
            season_mult = SEASONAL_MULTIPLIERS.get(params.seasonal_override, 1.0)
            adjustment *= season_mult

        return adjustment

    @staticmethod
    def _derive_signal(change_pct) -> str:
        """Derive CALL/PUT/NEUTRAL from expected change %."""
        try:
            pct = float(change_pct or 0)
        except (TypeError, ValueError):
            return "NEUTRAL"
        if pct > 2:
            return "CALL"
        if pct < -2:
            return "PUT"
        return "NEUTRAL"


# ── Public API functions ────────────────────────────────────────────


def get_presets() -> list[dict]:
    """Return all preset scenarios."""
    return [
        {"id": k, **v}
        for k, v in PRESETS.items()
    ]


def run_scenario_from_cache(overrides: dict) -> dict:
    """Run a scenario using cached analysis predictions."""
    from src.utils.cache_manager import cache as _cm
    analysis = _cm.get_data("analytics")
    if not analysis:
        return {"error": "No cached analysis available. Wait for the first scan cycle."}

    predictions = analysis.get("predictions", {})
    if not predictions:
        return {"error": "No predictions in cached analysis."}

    engine = ScenarioEngine(predictions)
    return engine.run_scenario(overrides)


def compare_scenarios_from_cache(scenarios: list[dict]) -> dict:
    """Compare multiple scenarios using cached analysis predictions."""
    from src.utils.cache_manager import cache as _cm
    analysis = _cm.get_data("analytics")
    if not analysis:
        return {"error": "No cached analysis available. Wait for the first scan cycle."}

    predictions = analysis.get("predictions", {})
    if not predictions:
        return {"error": "No predictions in cached analysis."}

    engine = ScenarioEngine(predictions)
    return engine.compare_scenarios(scenarios)
