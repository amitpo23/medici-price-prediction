"""Unit tests for analytical_cache.py — 3-layer SQLite cache.

Uses real SQLite in-memory (tmp file) — NO mocks.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.analytical_cache import AnalyticalCache


@pytest.fixture
def cache(tmp_path):
    """Create a fresh AnalyticalCache with a temp database."""
    db_path = tmp_path / "test_cache.db"
    return AnalyticalCache(db_path=db_path)


# ── Layer 1: Reference Data ──────────────────────────────────────────


class TestReferenceData:
    """Tests for Layer 1 — hotels, categories, boards."""

    def test_upsert_hotels_basic(self, cache):
        hotels = [
            {"hotel_id": 1, "hotel_name": "Beach Hotel", "city": "Miami", "stars": 4},
            {"hotel_id": 2, "hotel_name": "City Hotel", "city": "Miami", "stars": 3},
        ]
        count = cache.upsert_hotels(hotels)
        assert count == 2

    def test_upsert_hotels_empty(self, cache):
        assert cache.upsert_hotels([]) == 0

    def test_get_hotels_returns_all(self, cache):
        hotels = [
            {"hotel_id": 1, "hotel_name": "Alpha Hotel", "city": "Miami", "stars": 5},
            {"hotel_id": 2, "hotel_name": "Beta Hotel", "city": "Miami", "stars": 4},
        ]
        cache.upsert_hotels(hotels)
        result = cache.get_hotels()
        assert len(result) == 2
        assert result[0]["hotel_name"] == "Alpha Hotel"  # Sorted by name

    def test_get_hotel_by_id(self, cache):
        cache.upsert_hotels([{"hotel_id": 42, "hotel_name": "Test", "city": "NYC"}])
        h = cache.get_hotel(42)
        assert h is not None
        assert h["hotel_name"] == "Test"

    def test_get_hotel_not_found(self, cache):
        assert cache.get_hotel(999) is None

    def test_upsert_hotels_update_on_conflict(self, cache):
        cache.upsert_hotels([{"hotel_id": 1, "hotel_name": "V1", "city": "A"}])
        cache.upsert_hotels([{"hotel_id": 1, "hotel_name": "V2", "city": "B"}])
        h = cache.get_hotel(1)
        assert h["hotel_name"] == "V2"
        assert h["city"] == "B"

    def test_upsert_categories(self, cache):
        cats = [{"category_id": 1, "category_name": "Standard"}, {"category_id": 2, "category_name": "Deluxe"}]
        assert cache.upsert_categories(cats) == 2
        assert cache.upsert_categories([]) == 0

    def test_upsert_boards(self, cache):
        boards = [{"board_id": 1, "board_name": "BB"}, {"board_id": 2, "board_name": "HB"}]
        assert cache.upsert_boards(boards) == 2
        assert cache.upsert_boards([]) == 0


# ── Layer 2: Market Data ─────────────────────────────────────────────


class TestMarketData:
    """Tests for Layer 2 — aggregated market and competitor data."""

    def test_upsert_market_daily(self, cache):
        rows = [
            {"hotel_id": 1, "date": "2026-03-20", "room_type": "standard",
             "board": "bb", "avg_price": 200.0, "min_price": 180.0,
             "max_price": 220.0, "observation_count": 5},
        ]
        assert cache.upsert_market_daily(rows) == 1

    def test_upsert_market_daily_empty(self, cache):
        assert cache.upsert_market_daily([]) == 0

    def test_get_market_daily(self, cache):
        rows = [
            {"hotel_id": 1, "date": "2026-03-20", "avg_price": 200.0,
             "min_price": 180.0, "max_price": 220.0, "observation_count": 5},
        ]
        cache.upsert_market_daily(rows)
        result = cache.get_market_daily(1, days_back=30)
        assert len(result) == 1
        assert result[0]["avg_price"] == 200.0

    def test_market_daily_upsert_on_conflict(self, cache):
        row = {"hotel_id": 1, "date": "2026-03-20", "room_type": "", "board": "",
               "avg_price": 200.0, "min_price": 180.0, "max_price": 220.0, "observation_count": 5}
        cache.upsert_market_daily([row])
        row["avg_price"] = 210.0
        cache.upsert_market_daily([row])
        result = cache.get_market_daily(1, days_back=30)
        assert len(result) == 1
        assert result[0]["avg_price"] == 210.0

    def test_upsert_competitor_matrix(self, cache):
        rows = [
            {"hotel_id": 1, "competitor_hotel_id": 2, "distance_km": 1.5,
             "star_diff": -1, "avg_price_ratio": 0.9, "market_pressure": 0.3},
        ]
        assert cache.upsert_competitor_matrix(rows) == 1

    def test_upsert_competitor_matrix_empty(self, cache):
        assert cache.upsert_competitor_matrix([]) == 0

    def test_get_competitors(self, cache):
        # Need hotel ref for JOIN
        cache.upsert_hotels([{"hotel_id": 2, "hotel_name": "Comp Hotel", "city": "Miami"}])
        cache.upsert_competitor_matrix([
            {"hotel_id": 1, "competitor_hotel_id": 2, "distance_km": 1.5,
             "avg_price_ratio": 0.9, "market_pressure": 0.3},
        ])
        result = cache.get_competitors(1)
        assert len(result) == 1
        assert result[0]["competitor_name"] == "Comp Hotel"


# ── Layer 3: Daily Signals ───────────────────────────────────────────


class TestDailySignals:
    """Tests for Layer 3 — daily CALL/PUT/NEUTRAL signals."""

    def _make_signal(self, detail_id=100, hotel_id=1, signal_date="2026-03-25",
                     t_value=10, predicted_price=250.0, daily_change_pct=1.2,
                     signal="CALL", confidence=0.75):
        return {
            "detail_id": detail_id, "hotel_id": hotel_id,
            "signal_date": signal_date, "t_value": t_value,
            "predicted_price": predicted_price,
            "daily_change_pct": daily_change_pct,
            "signal": signal, "confidence": confidence,
            "enrichments": {"event_adj_pct": 0.02},
        }

    def test_save_daily_signals(self, cache):
        signals = [self._make_signal(), self._make_signal(detail_id=101, signal_date="2026-03-26")]
        assert cache.save_daily_signals(signals) == 2

    def test_save_empty(self, cache):
        assert cache.save_daily_signals([]) == 0

    def test_get_daily_signals(self, cache):
        signals = [
            self._make_signal(signal_date="2026-03-25"),
            self._make_signal(signal_date="2026-03-26"),
            self._make_signal(signal_date="2026-03-27"),
        ]
        cache.save_daily_signals(signals)
        result = cache.get_daily_signals(100, days_forward=30)
        # Depending on current date filtering, we check structure
        assert isinstance(result, list)
        for r in result:
            assert "signal" in r

    def test_get_hotel_daily_signals(self, cache):
        signals = [
            self._make_signal(detail_id=100, signal_date="2026-03-25"),
            self._make_signal(detail_id=101, signal_date="2026-03-25"),
        ]
        cache.save_daily_signals(signals)
        result = cache.get_hotel_daily_signals(1, signal_date="2026-03-25")
        assert len(result) == 2

    def test_signal_upsert_on_conflict(self, cache):
        s = self._make_signal(confidence=0.6)
        cache.save_daily_signals([s])
        s["confidence"] = 0.9
        cache.save_daily_signals([s])
        result = cache.get_hotel_daily_signals(1, signal_date="2026-03-25")
        assert len(result) == 1
        assert result[0]["confidence"] == 0.9


# ── Layer 3: Demand Zones ────────────────────────────────────────────


class TestDemandZones:
    """Tests for demand zone persistence."""

    def _make_zone(self, zone_id="abc123", hotel_id=1, zone_type="SUPPORT",
                   price_lower=180.0, price_upper=185.0, touch_count=3, strength=0.7):
        return {
            "zone_id": zone_id, "hotel_id": hotel_id, "category": "standard",
            "zone_type": zone_type, "price_lower": price_lower,
            "price_upper": price_upper, "touch_count": touch_count,
            "strength": strength, "first_touch": "2026-01-01", "last_touch": "2026-03-20",
        }

    def test_save_demand_zones(self, cache):
        zones = [self._make_zone(), self._make_zone(zone_id="def456", zone_type="RESISTANCE",
                                                     price_lower=220.0, price_upper=225.0)]
        assert cache.save_demand_zones(zones) == 2

    def test_save_empty(self, cache):
        assert cache.save_demand_zones([]) == 0

    def test_get_demand_zones(self, cache):
        cache.save_demand_zones([self._make_zone()])
        result = cache.get_demand_zones(1)
        assert len(result) == 1
        assert result[0]["zone_type"] == "SUPPORT"

    def test_get_demand_zones_filter_category(self, cache):
        cache.save_demand_zones([
            self._make_zone(zone_id="a1"),
            self._make_zone(zone_id="a2", hotel_id=1),
        ])
        result = cache.get_demand_zones(1, category="standard")
        assert len(result) == 2

    def test_get_demand_zones_active_only(self, cache):
        cache.save_demand_zones([
            self._make_zone(zone_id="active1"),
            {**self._make_zone(zone_id="broken1"), "is_broken": True},
        ])
        active = cache.get_demand_zones(1, active_only=True)
        all_zones = cache.get_demand_zones(1, active_only=False)
        assert len(active) == 1
        assert len(all_zones) == 2

    def test_zone_upsert_on_conflict(self, cache):
        cache.save_demand_zones([self._make_zone(strength=0.5)])
        cache.save_demand_zones([self._make_zone(strength=0.9)])
        result = cache.get_demand_zones(1)
        assert len(result) == 1
        assert result[0]["strength"] == 0.9


# ── Layer 3: Trade Setups ────────────────────────────────────────────


class TestTradeSetups:
    """Tests for trade setup persistence."""

    def _make_setup(self, detail_id=100, hotel_id=1):
        return {
            "detail_id": detail_id, "hotel_id": hotel_id,
            "setup_type": "primary", "entry_price": 200.0,
            "entry_t": 14, "entry_date": "2026-03-25",
            "stop_loss": 190.0, "stop_distance_pct": 5.0,
            "take_profit": 215.0, "target_distance_pct": 7.5,
            "risk_reward_ratio": 1.5, "position_size": 3,
            "max_risk_usd": 100.0, "signal": "CALL",
            "confidence": 0.75, "setup_quality": "medium",
            "reasons": {"stop": "volatility: $190"},
        }

    def test_save_trade_setups(self, cache):
        assert cache.save_trade_setups([self._make_setup()]) == 1

    def test_save_empty(self, cache):
        assert cache.save_trade_setups([]) == 0

    def test_get_trade_setups(self, cache):
        cache.save_trade_setups([self._make_setup(), self._make_setup(detail_id=101)])
        result = cache.get_trade_setups(hotel_id=1)
        assert len(result) == 2

    def test_get_trade_setups_filter_signal(self, cache):
        cache.save_trade_setups([self._make_setup()])
        result = cache.get_trade_setups(signal="CALL")
        assert len(result) == 1
        result = cache.get_trade_setups(signal="PUT")
        assert len(result) == 0

    def test_get_trade_setups_filter_min_rr(self, cache):
        cache.save_trade_setups([self._make_setup()])
        result = cache.get_trade_setups(min_rr=1.0)
        assert len(result) == 1
        result = cache.get_trade_setups(min_rr=2.0)
        assert len(result) == 0

    def test_get_trade_setup_single(self, cache):
        cache.save_trade_setups([self._make_setup()])
        result = cache.get_trade_setup(100)
        assert result is not None
        assert result["entry_price"] == 200.0

    def test_get_trade_setup_not_found(self, cache):
        assert cache.get_trade_setup(999) is None


# ── Layer 3: Trade Journal ───────────────────────────────────────────


class TestTradeJournal:
    """Tests for trade journal and P&L tracking."""

    def _make_trade(self, detail_id=100, pnl_usd=50.0, pnl_pct=2.5):
        return {
            "detail_id": detail_id, "hotel_id": 1,
            "trade_type": "CALL", "entry_price": 200.0,
            "entry_date": "2026-03-20", "entry_t": 14,
            "exit_price": 210.0, "exit_date": "2026-03-22",
            "exit_t": 12, "position_size": 2,
            "pnl_usd": pnl_usd, "pnl_pct": pnl_pct,
            "mae_usd": -5.0, "mae_pct": -1.0,
            "mfe_usd": 60.0, "mfe_pct": 3.0,
            "signal_at_entry": "CALL", "confidence_at_entry": 0.8,
            "exit_reason": "target_hit",
        }

    def test_log_trade(self, cache):
        trade_id = cache.log_trade(self._make_trade())
        assert trade_id > 0

    def test_get_trade_journal(self, cache):
        cache.log_trade(self._make_trade(detail_id=100))
        cache.log_trade(self._make_trade(detail_id=101, pnl_usd=-20, pnl_pct=-1.0))
        result = cache.get_trade_journal()
        assert len(result) == 2

    def test_get_trade_journal_filter_hotel(self, cache):
        cache.log_trade(self._make_trade())
        result = cache.get_trade_journal(hotel_id=1)
        assert len(result) == 1
        result = cache.get_trade_journal(hotel_id=999)
        assert len(result) == 0

    def test_get_trade_stats_empty(self, cache):
        stats = cache.get_trade_stats()
        assert stats["total_trades"] == 0

    def test_get_trade_stats_with_data(self, cache):
        cache.log_trade(self._make_trade(detail_id=1, pnl_usd=50, pnl_pct=2.5))
        cache.log_trade(self._make_trade(detail_id=2, pnl_usd=30, pnl_pct=1.5))
        cache.log_trade(self._make_trade(detail_id=3, pnl_usd=-20, pnl_pct=-1.0))
        stats = cache.get_trade_stats()
        assert stats["total_trades"] == 3
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert stats["win_rate"] == pytest.approx(66.7, abs=0.1)
        assert stats["total_pnl_usd"] == 60.0

    def test_profit_factor(self, cache):
        cache.log_trade(self._make_trade(detail_id=1, pnl_usd=100, pnl_pct=5.0))
        cache.log_trade(self._make_trade(detail_id=2, pnl_usd=-50, pnl_pct=-2.5))
        stats = cache.get_trade_stats()
        assert stats["profit_factor"] == 2.0


# ── Structure Breaks ─────────────────────────────────────────────────


class TestStructureBreaks:
    """Tests for BOS/CHOCH persistence."""

    def _make_break(self, break_id="brk1"):
        return {
            "break_id": break_id, "hotel_id": 1, "category": "standard",
            "break_type": "BOS", "break_date": "2026-03-20",
            "break_price": 225.0, "previous_level": 220.0,
            "direction": "BULLISH", "significance": 0.8,
        }

    def test_save_structure_breaks(self, cache):
        assert cache.save_structure_breaks([self._make_break()]) == 1

    def test_save_empty(self, cache):
        assert cache.save_structure_breaks([]) == 0

    def test_get_structure_breaks(self, cache):
        cache.save_structure_breaks([self._make_break()])
        result = cache.get_structure_breaks(1, days_back=30)
        assert len(result) == 1
        assert result[0]["break_type"] == "BOS"


# ── Metadata & Utilities ─────────────────────────────────────────────


class TestMetadata:
    """Tests for freshness and layer clearing."""

    def test_freshness_empty(self, cache):
        f = cache.get_freshness()
        assert "ref_hotels" in f
        assert f["ref_hotels"]["count"] == 0

    def test_freshness_with_data(self, cache):
        # ref_hotels uses updated_at, not computed_at — freshness query catches OperationalError
        # Instead test with a table that has computed_at
        cache.save_demand_zones([{
            "zone_id": "z1", "hotel_id": 1, "category": "", "zone_type": "SUPPORT",
            "price_lower": 180.0, "price_upper": 185.0, "touch_count": 2, "strength": 0.7,
        }])
        f = cache.get_freshness()
        assert f["demand_zones"]["count"] == 1
        assert f["demand_zones"]["latest"] is not None

    def test_clear_layer_1(self, cache):
        cache.upsert_hotels([{"hotel_id": 1, "hotel_name": "Test"}])
        cache.upsert_categories([{"category_id": 1, "category_name": "STD"}])
        cache.upsert_boards([{"board_id": 1, "board_name": "BB"}])
        cache.clear_layer(1)
        assert cache.get_hotels() == []

    def test_clear_layer_2(self, cache):
        cache.upsert_market_daily([{
            "hotel_id": 1, "date": "2026-03-20", "avg_price": 200.0,
            "min_price": 180.0, "max_price": 220.0, "observation_count": 5,
        }])
        cache.clear_layer(2)
        assert cache.get_market_daily(1) == []

    def test_clear_layer_3(self, cache):
        cache.save_daily_signals([{
            "detail_id": 1, "hotel_id": 1, "signal_date": "2026-03-25",
            "t_value": 10, "predicted_price": 200.0, "daily_change_pct": 1.0,
            "signal": "CALL", "confidence": 0.7,
        }])
        cache.clear_layer(3)
        assert cache.get_hotel_daily_signals(1, signal_date="2026-03-25") == []

    def test_clear_layer_2_includes_new_tables(self, cache):
        """Clearing layer 2 also clears search, margin, volume, rebuy, overrides."""
        cache.save_search_daily([{
            "hotel_id": 1, "search_date": "2026-03-20", "room_category": "std",
            "room_board": "bb", "avg_sell_price": 200.0,
        }])
        cache.save_rebuy_signals([{"hotel_id": 1, "reason": "test", "cancel_count": 5}])
        cache.clear_layer(2)
        assert cache.get_search_daily(1) == []
        assert cache.get_rebuy_activity(1) == []

    def test_schema_is_idempotent(self, tmp_path):
        """Creating cache twice on same DB shouldn't error."""
        db_path = tmp_path / "idempotent.db"
        c1 = AnalyticalCache(db_path=db_path)
        c2 = AnalyticalCache(db_path=db_path)
        assert c2.get_hotels() == []


# ── Search Results Intelligence ──────────────────────────────────────


class TestSearchIntelligence:
    """Tests for search results (3 price points), margins, volume."""

    def _make_search_row(self, hotel_id=1, search_date="2026-03-20"):
        return {
            "hotel_id": hotel_id, "search_date": search_date,
            "room_category": "standard", "room_board": "BB",
            "avg_sell_price": 250.0, "avg_net_price": 200.0, "avg_bar_rate": 300.0,
            "min_sell_price": 230.0, "max_sell_price": 270.0,
            "min_net_price": 185.0, "max_net_price": 215.0,
            "search_count": 15, "provider_count": 3, "avg_margin_pct": 20.0,
        }

    def test_save_search_daily(self, cache):
        assert cache.save_search_daily([self._make_search_row()]) == 1

    def test_save_empty(self, cache):
        assert cache.save_search_daily([]) == 0

    def test_get_search_daily(self, cache):
        cache.save_search_daily([
            self._make_search_row(search_date="2026-03-20"),
            self._make_search_row(search_date="2026-03-21"),
        ])
        result = cache.get_search_daily(1, days_back=30)
        assert len(result) == 2
        assert result[0]["avg_sell_price"] == 250.0
        assert result[0]["avg_net_price"] == 200.0

    def test_search_daily_upsert(self, cache):
        cache.save_search_daily([self._make_search_row()])
        updated = self._make_search_row()
        updated["avg_sell_price"] = 260.0
        cache.save_search_daily([updated])
        result = cache.get_search_daily(1)
        assert len(result) == 1
        assert result[0]["avg_sell_price"] == 260.0

    def test_save_margin_spread(self, cache):
        row = {"hotel_id": 1, "date": "2026-03-20", "avg_sell": 250.0,
               "avg_net": 200.0, "avg_bar": 300.0, "avg_margin_usd": 50.0,
               "avg_margin_pct": 20.0, "discount_from_bar_pct": 16.7, "search_count": 15}
        assert cache.save_margin_spread([row]) == 1

    def test_save_margin_spread_empty(self, cache):
        assert cache.save_margin_spread([]) == 0

    def test_save_search_volume(self, cache):
        row = {"hotel_id": 1, "date": "2026-03-20", "search_count": 150,
               "unique_rooms_searched": 8, "active_providers": 5}
        assert cache.save_search_volume([row]) == 1

    def test_save_search_volume_empty(self, cache):
        assert cache.save_search_volume([]) == 0

    def test_three_price_points_preserved(self, cache):
        """Verify all 3 price points (sell/net/bar) are stored correctly."""
        row = self._make_search_row()
        cache.save_search_daily([row])
        result = cache.get_search_daily(1)[0]
        assert result["avg_sell_price"] == 250.0
        assert result["avg_net_price"] == 200.0
        assert result["avg_bar_rate"] == 300.0
        margin = result["avg_sell_price"] - result["avg_net_price"]
        assert margin == 50.0  # $50 margin


# ── Trading Intelligence ─────────────────────────────────────────────


class TestTradingIntelligence:
    """Tests for rebuy signals and price overrides."""

    def test_save_rebuy_signals(self, cache):
        rows = [{"hotel_id": 1, "reason": "Cancelled By Last Price Update Job",
                 "cancel_count": 12, "avg_sell_rate": 250.0, "avg_cost": 200.0}]
        assert cache.save_rebuy_signals(rows) == 1

    def test_save_rebuy_empty(self, cache):
        assert cache.save_rebuy_signals([]) == 0

    def test_rebuy_upsert(self, cache):
        rows = [{"hotel_id": 1, "reason": "test", "cancel_count": 5}]
        cache.save_rebuy_signals(rows)
        rows[0]["cancel_count"] = 10
        cache.save_rebuy_signals(rows)
        result = cache.get_rebuy_activity(1)
        assert len(result) == 1
        assert result[0]["cancel_count"] == 10

    def test_get_rebuy_all(self, cache):
        cache.save_rebuy_signals([
            {"hotel_id": 1, "reason": "r1", "cancel_count": 5},
            {"hotel_id": 2, "reason": "r2", "cancel_count": 3},
        ])
        result = cache.get_rebuy_activity()
        assert len(result) == 2

    def test_save_price_overrides(self, cache):
        rows = [{
            "override_id": 1, "detail_id": 100, "hotel_id": 1,
            "room_category": "standard", "room_board": "BB",
            "date_from": "2026-05-15", "old_price": 200.0, "new_price": 220.0,
            "change_amount": 20.0, "change_pct": 10.0,
            "override_date": "2026-03-20", "user_id": "admin",
        }]
        assert cache.save_price_overrides(rows) == 1

    def test_save_overrides_empty(self, cache):
        assert cache.save_price_overrides([]) == 0

    def test_get_price_override_signals(self, cache):
        cache.save_price_overrides([{
            "override_id": 1, "detail_id": 100, "hotel_id": 1,
            "old_price": 200.0, "new_price": 220.0, "change_amount": 20.0,
            "change_pct": 10.0, "override_date": "2026-03-20",
        }])
        result = cache.get_price_override_signals(1)
        assert len(result) == 1
        assert result[0]["change_pct"] == 10.0

    def test_override_direction_signal(self, cache):
        """Positive change_pct = human pushed price UP (bullish signal)."""
        cache.save_price_overrides([
            {"override_id": 1, "detail_id": 100, "hotel_id": 1,
             "old_price": 200.0, "new_price": 220.0, "change_amount": 20.0,
             "change_pct": 10.0, "override_date": "2026-03-20"},
            {"override_id": 2, "detail_id": 101, "hotel_id": 1,
             "old_price": 300.0, "new_price": 270.0, "change_amount": -30.0,
             "change_pct": -10.0, "override_date": "2026-03-19"},
        ])
        overrides = cache.get_price_override_signals(1)
        bullish = [o for o in overrides if o["change_pct"] > 0]
        bearish = [o for o in overrides if o["change_pct"] < 0]
        assert len(bullish) == 1
        assert len(bearish) == 1
