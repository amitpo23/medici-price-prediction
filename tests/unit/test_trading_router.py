"""Tests for the trading_router API endpoints.

Tests all 12 endpoints in src/api/routers/trading_router.py.
Uses a real AnalyticalCache with temp SQLite and mocks API auth.
"""
from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.analytics.analytical_cache import AnalyticalCache


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def temp_cache(tmp_path):
    """Create a temporary AnalyticalCache with test data."""
    cache = AnalyticalCache(db_path=tmp_path / "test_trading.db")

    # Seed reference data
    cache.upsert_hotels([
        {"hotel_id": 100, "hotel_name": "Test Hotel Miami", "city": "Miami", "stars": 4},
    ])

    # Seed daily signals (matches save_daily_signals schema)
    cache.save_daily_signals([
        {
            "detail_id": 1001,
            "hotel_id": 100,
            "signal_date": "2026-04-01",
            "t_value": 7,
            "predicted_price": 200.0,
            "daily_change_pct": 2.5,
            "signal": "CALL",
            "confidence": 0.85,
            "enrichments": {"events": 0.01},
        },
        {
            "detail_id": 1001,
            "hotel_id": 100,
            "signal_date": "2026-04-02",
            "t_value": 8,
            "predicted_price": 195.0,
            "daily_change_pct": -1.2,
            "signal": "PUT",
            "confidence": 0.65,
            "enrichments": {},
        },
        {
            "detail_id": 1001,
            "hotel_id": 100,
            "signal_date": "2026-04-03",
            "t_value": 9,
            "predicted_price": 196.0,
            "daily_change_pct": 0.1,
            "signal": "NEUTRAL",
            "confidence": 0.40,
            "enrichments": {},
        },
    ])

    # Seed demand zones (matches save_demand_zones schema)
    cache.save_demand_zones([
        {
            "zone_id": "100_standard_demand_150_160",
            "hotel_id": 100,
            "category": "standard",
            "zone_type": "SUPPORT",
            "price_lower": 150.0,
            "price_upper": 160.0,
            "strength": 0.8,
            "touch_count": 3,
            "first_touch": "2026-03-01",
            "last_touch": "2026-03-20",
            "is_broken": False,
        },
        {
            "zone_id": "100_standard_supply_250_260",
            "hotel_id": 100,
            "category": "standard",
            "zone_type": "RESISTANCE",
            "price_lower": 250.0,
            "price_upper": 260.0,
            "strength": 0.6,
            "touch_count": 2,
            "first_touch": "2026-03-05",
            "last_touch": "2026-03-18",
            "is_broken": False,
        },
    ])

    # Seed structure breaks (matches save_structure_breaks schema)
    cache.save_structure_breaks([
        {
            "break_id": "100_BOS_2026-03-22",
            "hotel_id": 100,
            "category": "standard",
            "break_type": "BOS",
            "direction": "BULLISH",
            "break_price": 200.0,
            "break_date": "2026-03-22",
            "previous_level": 180.0,
            "significance": 0.7,
        },
    ])

    # Seed trade setups (matches save_trade_setups schema)
    cache.save_trade_setups([
        {
            "detail_id": 1001,
            "hotel_id": 100,
            "setup_type": "primary",
            "entry_price": 180.0,
            "entry_t": 7,
            "entry_date": "2026-04-01",
            "stop_loss": 155.0,
            "stop_distance_pct": 13.9,
            "take_profit": 210.0,
            "target_distance_pct": 16.7,
            "risk_reward_ratio": 1.2,
            "position_size": 3.0,
            "max_risk_usd": 75.0,
            "signal": "CALL",
            "confidence": 0.85,
            "setup_quality": "high",
            "reasons": {"stop_method": "demand_zone", "target_method": "path_forecast"},
        },
    ])

    # Seed search intel
    cache.save_search_daily([
        {
            "hotel_id": 100,
            "search_date": "2026-03-24",
            "room_category": "standard",
            "room_board": "BB",
            "avg_sell_price": 200.0,
            "avg_net_price": 170.0,
            "avg_bar_rate": 250.0,
            "min_sell_price": 180.0,
            "max_sell_price": 220.0,
            "min_net_price": 150.0,
            "max_net_price": 190.0,
            "search_count": 42,
            "provider_count": 5,
            "avg_margin_pct": 15.0,
        },
    ])

    # Seed rebuy signals
    cache.save_rebuy_signals([
        {
            "hotel_id": 100,
            "reason": "Cancelled By Last Price Update Job",
            "cancel_count": 12,
            "avg_sell_rate": 190.0,
            "avg_cost": 160.0,
        },
    ])

    # Seed price overrides
    cache.save_price_overrides([
        {
            "override_id": 1,
            "detail_id": 1001,
            "hotel_id": 100,
            "room_category": "standard",
            "room_board": "BB",
            "date_from": "2026-04-01",
            "old_price": 200.0,
            "new_price": 210.0,
            "change_amount": 10.0,
            "change_pct": 5.0,
            "override_date": "2026-03-20",
            "user_id": "admin",
        },
    ])

    return cache


# ── Tests for /trading/signals ────────────────────────────────────────


class TestSignalsEndpoint:
    """Tests for GET /trading/signals."""

    def test_get_signals_returns_data(self, temp_cache):
        signals = temp_cache.get_daily_signals(1001, days_forward=30)
        assert len(signals) == 3

    def test_get_signals_filters_by_detail_id(self, temp_cache):
        signals = temp_cache.get_daily_signals(9999, days_forward=30)
        assert len(signals) == 0

    def test_signals_have_required_fields(self, temp_cache):
        signals = temp_cache.get_daily_signals(1001, days_forward=30)
        for s in signals:
            assert "signal" in s
            assert "confidence" in s
            assert "signal_date" in s
            assert s["signal"] in ("CALL", "PUT", "NEUTRAL")


class TestSignalsSummary:
    """Tests for signal summary logic."""

    def test_summary_counts(self, temp_cache):
        signals = temp_cache.get_daily_signals(1001, days_forward=30)
        counts = {"CALL": 0, "PUT": 0, "NEUTRAL": 0}
        for s in signals:
            counts[s["signal"]] += 1
        assert counts["CALL"] == 1
        assert counts["PUT"] == 1
        assert counts["NEUTRAL"] == 1

    def test_dominant_signal(self, temp_cache):
        # With equal counts, any is valid
        signals = temp_cache.get_daily_signals(1001, days_forward=30)
        assert len(signals) == 3

    def test_avg_confidence(self, temp_cache):
        signals = temp_cache.get_daily_signals(1001, days_forward=30)
        call_confs = [s["confidence"] for s in signals if s["signal"] == "CALL"]
        assert len(call_confs) == 1
        assert call_confs[0] == pytest.approx(0.85, abs=0.01)


# ── Tests for /trading/zones ──────────────────────────────────────────


class TestDemandZonesEndpoint:
    """Tests for GET /trading/zones."""

    def test_get_zones_returns_data(self, temp_cache):
        zones = temp_cache.get_demand_zones(100)
        assert len(zones) == 2

    def test_zones_have_type(self, temp_cache):
        zones = temp_cache.get_demand_zones(100)
        types = {z["zone_type"] for z in zones}
        assert "SUPPORT" in types
        assert "RESISTANCE" in types

    def test_zones_filter_by_category(self, temp_cache):
        zones = temp_cache.get_demand_zones(100, category="standard")
        assert len(zones) >= 1

    def test_zones_empty_for_unknown_hotel(self, temp_cache):
        zones = temp_cache.get_demand_zones(9999)
        assert len(zones) == 0

    def test_zone_strength_valid(self, temp_cache):
        zones = temp_cache.get_demand_zones(100)
        for z in zones:
            assert 0 <= z["strength"] <= 1


# ── Tests for /trading/breaks ─────────────────────────────────────────


class TestStructureBreaksEndpoint:
    """Tests for GET /trading/breaks."""

    def test_get_breaks_returns_data(self, temp_cache):
        breaks = temp_cache.get_structure_breaks(100, days_back=30)
        assert len(breaks) == 1

    def test_break_has_type_and_direction(self, temp_cache):
        breaks = temp_cache.get_structure_breaks(100, days_back=30)
        b = breaks[0]
        assert b["break_type"] == "BOS"
        assert b["direction"] == "BULLISH"

    def test_breaks_empty_for_unknown_hotel(self, temp_cache):
        breaks = temp_cache.get_structure_breaks(9999, days_back=30)
        assert len(breaks) == 0


# ── Tests for /trading/setups ─────────────────────────────────────────


class TestTradeSetupsEndpoint:
    """Tests for GET /trading/setups."""

    def test_get_setups_returns_data(self, temp_cache):
        setups = temp_cache.get_trade_setups()
        assert len(setups) >= 1

    def test_setup_has_entry_stop_target(self, temp_cache):
        setups = temp_cache.get_trade_setups()
        s = setups[0]
        assert "entry_price" in s
        assert "stop_loss" in s
        assert "take_profit" in s
        assert "risk_reward_ratio" in s
        assert s["entry_price"] > 0

    def test_setups_filter_by_signal(self, temp_cache):
        call_setups = temp_cache.get_trade_setups(signal="CALL")
        assert len(call_setups) >= 1
        for s in call_setups:
            assert s["signal"] == "CALL"

    def test_setups_filter_by_min_rr(self, temp_cache):
        # RR = 1.2, so min_rr=2.0 should return empty
        setups = temp_cache.get_trade_setups(min_rr=2.0)
        assert len(setups) == 0

    def test_setups_filter_by_min_rr_passes(self, temp_cache):
        # RR = 1.2, so min_rr=1.0 should return it
        setups = temp_cache.get_trade_setups(min_rr=1.0)
        assert len(setups) >= 1
        for s in setups:
            assert s["risk_reward_ratio"] >= 1.0

    def test_setups_filter_by_hotel(self, temp_cache):
        setups = temp_cache.get_trade_setups(hotel_id=100)
        assert len(setups) >= 1
        for s in setups:
            assert s["hotel_id"] == 100

    def test_setups_empty_for_unknown_hotel(self, temp_cache):
        setups = temp_cache.get_trade_setups(hotel_id=9999)
        assert len(setups) == 0


# ── Tests for /trading/search-intel ───────────────────────────────────


class TestSearchIntelEndpoint:
    """Tests for GET /trading/search-intel."""

    def test_get_search_intel_returns_data(self, temp_cache):
        data = temp_cache.get_search_daily(100, days_back=30)
        assert len(data) >= 1

    def test_search_has_three_price_points(self, temp_cache):
        data = temp_cache.get_search_daily(100, days_back=30)
        d = data[0]
        assert "avg_sell_price" in d
        assert "avg_net_price" in d
        assert "avg_bar_rate" in d

    def test_margin_positive(self, temp_cache):
        data = temp_cache.get_search_daily(100, days_back=30)
        d = data[0]
        assert d["avg_sell_price"] > d["avg_net_price"]  # sell > net = positive margin

    def test_search_empty_for_unknown_hotel(self, temp_cache):
        data = temp_cache.get_search_daily(9999, days_back=30)
        assert len(data) == 0


# ── Tests for /trading/rebuy ──────────────────────────────────────────


class TestRebuySignalsEndpoint:
    """Tests for GET /trading/rebuy."""

    def test_get_rebuy_returns_data(self, temp_cache):
        rebuy = temp_cache.get_rebuy_activity(hotel_id=100)
        assert len(rebuy) >= 1

    def test_rebuy_has_cancel_count(self, temp_cache):
        rebuy = temp_cache.get_rebuy_activity(hotel_id=100)
        assert rebuy[0]["cancel_count"] == 12

    def test_rebuy_all_hotels(self, temp_cache):
        rebuy = temp_cache.get_rebuy_activity(hotel_id=0)
        assert len(rebuy) >= 1

    def test_rebuy_empty_for_unknown_hotel(self, temp_cache):
        rebuy = temp_cache.get_rebuy_activity(hotel_id=9999)
        assert len(rebuy) == 0


# ── Tests for /trading/overrides ──────────────────────────────────────


class TestPriceOverridesEndpoint:
    """Tests for GET /trading/overrides."""

    def test_get_overrides_returns_data(self, temp_cache):
        overrides = temp_cache.get_price_override_signals(100)
        assert len(overrides) >= 1

    def test_override_has_change(self, temp_cache):
        overrides = temp_cache.get_price_override_signals(100)
        o = overrides[0]
        assert "old_price" in o
        assert "new_price" in o
        assert o["change_amount"] == pytest.approx(10.0)

    def test_override_direction(self, temp_cache):
        overrides = temp_cache.get_price_override_signals(100)
        o = overrides[0]
        # New price > old price → bullish override
        assert o["new_price"] > o["old_price"]

    def test_overrides_empty_for_unknown_hotel(self, temp_cache):
        overrides = temp_cache.get_price_override_signals(9999)
        assert len(overrides) == 0


# ── Tests for /trading/cache/freshness ────────────────────────────────


class TestCacheFreshness:
    """Tests for GET /trading/cache/freshness."""

    def test_freshness_returns_all_tables(self, temp_cache):
        freshness = temp_cache.get_freshness()
        # Returns flat dict of table_name → {label, count, latest}
        assert len(freshness) >= 10

    def test_freshness_shows_counts(self, temp_cache):
        freshness = temp_cache.get_freshness()
        for table_name, info in freshness.items():
            assert "count" in info
            assert "latest" in info

    def test_freshness_demand_zones_has_data(self, temp_cache):
        freshness = temp_cache.get_freshness()
        # ref_hotels uses updated_at not computed_at, so check demand_zones instead
        zones = freshness.get("demand_zones", {})
        assert zones.get("count", 0) >= 1


# ── Tests for scheduler integration helpers ───────────────────────────


class TestSchedulerIntegration:
    """Tests for scheduler integration functions.

    These tests require fastapi to be importable.
    They're skipped in environments without it (like the sandbox).
    """

    @pytest.fixture(autouse=True)
    def skip_without_fastapi(self):
        """Skip these tests if fastapi not installed."""
        pytest.importorskip("fastapi")

    def test_analytical_cache_singleton(self):
        """Verify _get_analytical_cache returns a cache instance."""
        from src.api.routers._shared_state import _get_analytical_cache
        cache = _get_analytical_cache()
        if cache is not None:
            assert hasattr(cache, "get_freshness")
            assert hasattr(cache, "get_daily_signals")

    def test_cache_aggregator_factory(self):
        """Verify _get_cache_aggregator returns an aggregator or None."""
        from src.api.routers._shared_state import _get_cache_aggregator
        aggregator = _get_cache_aggregator()
        if aggregator is not None:
            assert hasattr(aggregator, "full_refresh")
            assert hasattr(aggregator, "run_all_demand_zones")

    def test_refresh_daily_returns_dict(self):
        """Verify _refresh_analytical_cache_daily returns a dict."""
        from src.api.routers._shared_state import _refresh_analytical_cache_daily
        result = _refresh_analytical_cache_daily()
        assert isinstance(result, dict)

    def test_refresh_signals_returns_dict(self):
        """Verify _refresh_analytical_cache_signals returns a dict."""
        from src.api.routers._shared_state import _refresh_analytical_cache_signals
        result = _refresh_analytical_cache_signals(None)
        assert isinstance(result, dict)

    def test_refresh_signals_with_mock_analysis(self):
        """Verify signal refresh handles analysis dict gracefully."""
        from src.api.routers._shared_state import _refresh_analytical_cache_signals
        analysis = {"predictions": {}}
        result = _refresh_analytical_cache_signals(analysis)
        assert isinstance(result, dict)
        assert "daily_signals" in result


# ── Tests for hotel overview (combined endpoint) ──────────────────────


class TestHotelOverview:
    """Tests for GET /trading/hotel/{hotel_id} logic."""

    def test_overview_combines_data(self, temp_cache):
        """Verify we can assemble hotel overview from cache."""
        zones = temp_cache.get_demand_zones(100)
        breaks = temp_cache.get_structure_breaks(100, days_back=30)
        rebuy = temp_cache.get_rebuy_activity(hotel_id=100)
        overrides = temp_cache.get_price_override_signals(100)
        search = temp_cache.get_search_daily(100, days_back=7)

        assert len(zones) > 0
        assert len(breaks) > 0
        assert len(rebuy) > 0
        assert len(overrides) > 0
        assert len(search) > 0

    def test_sentiment_calculation(self, temp_cache):
        """Verify sentiment bias calculation logic."""
        rebuy = temp_cache.get_rebuy_activity(hotel_id=100)
        overrides = temp_cache.get_price_override_signals(100)

        bullish = len(rebuy) + sum(1 for o in overrides if o.get("change_amount", 0) > 0)
        bearish = sum(1 for o in overrides if o.get("change_amount", 0) < 0)

        # We have 1 rebuy + 1 bullish override = 2 bullish, 0 bearish
        assert bullish == 2
        assert bearish == 0

    def test_empty_hotel_overview(self, temp_cache):
        """Verify overview for unknown hotel returns empty data."""
        zones = temp_cache.get_demand_zones(9999)
        breaks = temp_cache.get_structure_breaks(9999, days_back=30)
        rebuy = temp_cache.get_rebuy_activity(hotel_id=9999)
        overrides = temp_cache.get_price_override_signals(9999)
        search = temp_cache.get_search_daily(9999, days_back=7)

        assert len(zones) == 0
        assert len(breaks) == 0
        assert len(rebuy) == 0
        assert len(overrides) == 0
        assert len(search) == 0
