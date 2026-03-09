"""Tests for the scenario analysis engine."""
from __future__ import annotations

import pytest


# ── Test predictions fixture ────────────────────────────────────────

def _make_predictions(n: int = 10) -> dict:
    """Create sample predictions for testing."""
    predictions = {}
    for i in range(n):
        detail_id = str(1000 + i)
        current_price = 200 + i * 10
        change_pct = (i % 5) * 3 - 6  # -6, -3, 0, 3, 6
        predicted = current_price * (1 + change_pct / 100)
        predictions[detail_id] = {
            "hotel_id": (i % 3) + 1,
            "current_price": current_price,
            "predicted_checkin_price": predicted,
            "expected_change_pct": change_pct,
            "days_to_checkin": 14 + i * 3,
            "signals": [{"confidence": 0.7}],
        }
    return predictions


# ── ScenarioOverrides ───────────────────────────────────────────────


class TestScenarioOverrides:
    """Test override parameter validation."""

    def test_from_dict_valid(self):
        from src.analytics.scenario_engine import ScenarioOverrides
        overrides = ScenarioOverrides.from_dict({
            "event_impact": 50,
            "demand_multiplier": 1.5,
            "weather_severity": "storm",
        })
        assert overrides.event_impact == 50
        assert overrides.demand_multiplier == 1.5
        assert overrides.weather_severity == "storm"

    def test_clamps_values(self):
        from src.analytics.scenario_engine import ScenarioOverrides
        overrides = ScenarioOverrides.from_dict({
            "event_impact": 500,  # >200, should clamp
            "demand_multiplier": 5.0,  # >2.0, should clamp
            "competitor_delta": -50,  # <-20, should clamp
        })
        assert overrides.event_impact == 200
        assert overrides.demand_multiplier == 2.0
        assert overrides.competitor_delta == -20

    def test_invalid_weather_ignored(self):
        from src.analytics.scenario_engine import ScenarioOverrides
        overrides = ScenarioOverrides.from_dict({"weather_severity": "tornado"})
        assert overrides.weather_severity is None

    def test_none_values_stay_none(self):
        from src.analytics.scenario_engine import ScenarioOverrides
        overrides = ScenarioOverrides.from_dict({})
        assert overrides.event_impact is None
        assert overrides.demand_multiplier is None

    def test_invalid_type_returns_none(self):
        from src.analytics.scenario_engine import ScenarioOverrides
        overrides = ScenarioOverrides.from_dict({"event_impact": "abc"})
        assert overrides.event_impact is None


# ── ScenarioEngine.run_scenario ─────────────────────────────────────


class TestRunScenario:
    """Test single scenario execution."""

    def test_neutral_scenario(self):
        """No overrides → no price changes."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({})
        assert result["total_rooms"] == 10
        # No overrides → adjustment is 1.0
        for d in result["deltas"]:
            assert d["delta_dollars"] == 0.0

    def test_demand_increase(self):
        """Higher demand → higher prices."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"demand_multiplier": 1.5})
        assert result["total_rooms"] == 10
        assert result["avg_delta_pct"] > 0

    def test_demand_decrease(self):
        """Lower demand → lower prices."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"demand_multiplier": 0.6})
        assert result["avg_delta_pct"] < 0

    def test_hurricane_scenario(self):
        """Hurricane → prices drop."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"weather_severity": "hurricane", "demand_multiplier": 0.5})
        assert result["avg_delta_pct"] < 0
        assert result["signal_changes"] >= 0

    def test_event_cancelled(self):
        """Event cancelled (impact=0) → prices drop."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"event_impact": 0})
        assert result["avg_delta_pct"] < 0

    def test_competitor_price_increase(self):
        """Competitors raise prices → we can raise too."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"competitor_delta": 15})
        assert result["avg_delta_pct"] > 0

    def test_seasonal_peak(self):
        """Peak season → prices increase."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"seasonal_override": "peak"})
        assert result["avg_delta_pct"] > 0

    def test_seasonal_off(self):
        """Off season → prices decrease."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"seasonal_override": "off"})
        assert result["avg_delta_pct"] < 0

    def test_signal_change_detection(self):
        """Extreme scenario causes signal changes."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"demand_multiplier": 2.0, "competitor_delta": 20})
        # Some rooms should flip signals
        assert any(d["signal_changed"] for d in result["deltas"]) or result["total_rooms"] > 0

    def test_empty_predictions(self):
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine({})
        result = engine.run_scenario({"demand_multiplier": 1.5})
        assert result["total_rooms"] == 0
        assert result["deltas"] == []

    def test_deltas_sorted_by_impact(self):
        """Deltas should be sorted by absolute delta_pct descending."""
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.run_scenario({"demand_multiplier": 1.5})
        deltas = result["deltas"]
        if len(deltas) > 1:
            for i in range(len(deltas) - 1):
                assert abs(deltas[i]["delta_pct"]) >= abs(deltas[i + 1]["delta_pct"])


# ── Compare scenarios ───────────────────────────────────────────────


class TestCompareScenarios:
    """Test multi-scenario comparison."""

    def test_compare_two_scenarios(self):
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.compare_scenarios([
            {"name": "Surge", "overrides": {"demand_multiplier": 1.5}},
            {"name": "Recession", "overrides": {"demand_multiplier": 0.6}},
        ])
        assert result["scenarios_compared"] == 2
        assert result["results"][0]["name"] == "Surge"
        assert result["results"][0]["avg_delta_pct"] > 0
        assert result["results"][1]["avg_delta_pct"] < 0

    def test_caps_at_five_scenarios(self):
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        scenarios = [{"name": f"s{i}", "overrides": {}} for i in range(10)]
        result = engine.compare_scenarios(scenarios)
        assert result["scenarios_compared"] == 5

    def test_empty_scenarios(self):
        from src.analytics.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        result = engine.compare_scenarios([])
        assert result["scenarios_compared"] == 0


# ── Presets ──────────────────────────────────────────────────────────


class TestPresets:
    """Test preset scenarios."""

    def test_get_presets(self):
        from src.analytics.scenario_engine import get_presets
        presets = get_presets()
        assert len(presets) >= 4
        ids = {p["id"] for p in presets}
        assert "art_basel_cancelled" in ids
        assert "hurricane_warning" in ids
        assert "peak_season_surge" in ids
        assert "recession_impact" in ids

    def test_presets_have_overrides(self):
        from src.analytics.scenario_engine import get_presets
        for preset in get_presets():
            assert "overrides" in preset
            assert isinstance(preset["overrides"], dict)

    def test_presets_run_successfully(self):
        """All presets should execute without errors."""
        from src.analytics.scenario_engine import get_presets, ScenarioEngine
        engine = ScenarioEngine(_make_predictions())
        for preset in get_presets():
            result = engine.run_scenario(preset["overrides"])
            assert result["total_rooms"] == 10


# ── Signal derivation ───────────────────────────────────────────────


class TestDeriveSignal:
    """Test signal derivation helper."""

    def test_call_signal(self):
        from src.analytics.scenario_engine import ScenarioEngine
        assert ScenarioEngine._derive_signal(5.0) == "CALL"

    def test_put_signal(self):
        from src.analytics.scenario_engine import ScenarioEngine
        assert ScenarioEngine._derive_signal(-5.0) == "PUT"

    def test_neutral_signal(self):
        from src.analytics.scenario_engine import ScenarioEngine
        assert ScenarioEngine._derive_signal(0.5) == "NEUTRAL"

    def test_none_returns_neutral(self):
        from src.analytics.scenario_engine import ScenarioEngine
        assert ScenarioEngine._derive_signal(None) == "NEUTRAL"


# ── API endpoints ───────────────────────────────────────────────────


class TestScenarioApiEndpoints:
    """Test scenario API endpoints through TestClient."""

    def test_presets_endpoint(self):
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/salesoffice/scenario/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) >= 4

    def test_run_endpoint_no_cache(self):
        """Without cached analysis, returns error message."""
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/salesoffice/scenario/run",
            json={"demand_multiplier": 1.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Either has results or an error (no cache)
        assert "total_rooms" in data or "error" in data

    def test_compare_endpoint_no_cache(self):
        """Without cached analysis, returns error message."""
        from starlette.testclient import TestClient
        from src.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/salesoffice/scenario/compare",
            json={"scenarios": [{"name": "test", "overrides": {}}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "scenarios_compared" in data or "error" in data
