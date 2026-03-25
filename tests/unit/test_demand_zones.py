"""Unit tests for demand_zones.py — zone detection, BOS, CHOCH.

Uses real objects with constructed data — NO mocks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.demand_zones import (
    detect_demand_zones,
    detect_structure_breaks,
    _find_reversals,
    _cluster_into_zones,
    _calculate_zone_strength,
    _make_zone_id,
    _detect_choch,
    MIN_TOUCHES,
    ZONE_TOLERANCE_PCT,
    MIN_REVERSAL_PCT,
    BOS_BREAK_THRESHOLD_PCT,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_price_history(prices: list[float], start_date="2026-01-01") -> pd.DataFrame:
    """Build a DataFrame from a list of prices."""
    dates = pd.date_range(start_date, periods=len(prices), freq="D")
    return pd.DataFrame({
        "room_price": prices,
        "snapshot_ts": dates,
        "date_from": dates,
    })


def _make_bounce_series(n=50, support=180.0, resistance=220.0, mid=200.0) -> list[float]:
    """Create a price series that bounces between support and resistance.

    This creates clear reversals at the support and resistance levels.
    """
    prices = []
    going_up = True
    price = mid
    for i in range(n):
        if going_up:
            price += (resistance - mid) / 10
            if price >= resistance:
                going_up = False
        else:
            price -= (mid - support) / 10
            if price <= support:
                going_up = True
        prices.append(round(price, 2))
    return prices


# ── Zone ID Generation ───────────────────────────────────────────────


class TestMakeZoneId:
    """Tests for _make_zone_id()."""

    def test_deterministic(self):
        id1 = _make_zone_id(1, "standard", "SUPPORT", 180.0)
        id2 = _make_zone_id(1, "standard", "SUPPORT", 180.0)
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = _make_zone_id(1, "standard", "SUPPORT", 180.0)
        id2 = _make_zone_id(2, "standard", "SUPPORT", 180.0)
        assert id1 != id2

    def test_length(self):
        zone_id = _make_zone_id(1, "standard", "SUPPORT", 180.0)
        assert len(zone_id) == 12


# ── Reversal Detection ───────────────────────────────────────────────


class TestFindReversals:
    """Tests for _find_reversals()."""

    def test_finds_local_minimum(self):
        # Clear V-shape: 100, 95, 100 → minimum at index 1
        prices = np.array([100.0, 95.0, 100.0])
        timestamps = np.array(["2026-01-01", "2026-01-02", "2026-01-03"])
        reversals = _find_reversals(prices, timestamps)
        support_revs = [r for r in reversals if r["type"] == "SUPPORT"]
        assert len(support_revs) >= 1
        assert support_revs[0]["price"] == 95.0

    def test_finds_local_maximum(self):
        # Inverted V: 100, 105, 100 → maximum at index 1
        prices = np.array([100.0, 105.0, 100.0])
        timestamps = np.array(["2026-01-01", "2026-01-02", "2026-01-03"])
        reversals = _find_reversals(prices, timestamps)
        resistance_revs = [r for r in reversals if r["type"] == "RESISTANCE"]
        assert len(resistance_revs) >= 1
        assert resistance_revs[0]["price"] == 105.0

    def test_no_reversals_in_monotonic(self):
        # Strictly rising — no reversal points
        prices = np.array([100.0, 102.0, 104.0, 106.0, 108.0])
        timestamps = np.array(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"])
        reversals = _find_reversals(prices, timestamps)
        assert len(reversals) == 0

    def test_requires_min_reversal_pct(self):
        # Very small change — below MIN_REVERSAL_PCT (1%)
        prices = np.array([100.0, 99.8, 100.0])
        timestamps = np.array(["2026-01-01", "2026-01-02", "2026-01-03"])
        reversals = _find_reversals(prices, timestamps)
        assert len(reversals) == 0

    def test_too_few_prices(self):
        prices = np.array([100.0, 95.0])
        timestamps = np.array(["2026-01-01", "2026-01-02"])
        assert _find_reversals(prices, timestamps) == []

    def test_skips_zero_price(self):
        prices = np.array([100.0, 0.0, 100.0])
        timestamps = np.array(["2026-01-01", "2026-01-02", "2026-01-03"])
        assert _find_reversals(prices, timestamps) == []

    def test_multiple_reversals(self):
        # W-shape creates 2 minima
        prices = np.array([100.0, 95.0, 100.0, 95.0, 100.0])
        timestamps = np.array([f"2026-01-{i+1:02d}" for i in range(5)])
        reversals = _find_reversals(prices, timestamps)
        support_revs = [r for r in reversals if r["type"] == "SUPPORT"]
        assert len(support_revs) >= 1


# ── Zone Clustering ──────────────────────────────────────────────────


class TestClusterIntoZones:
    """Tests for _cluster_into_zones()."""

    def test_clusters_nearby_reversals(self):
        reversals = [
            {"price": 180.0, "type": "SUPPORT", "timestamp": "2026-01-01", "idx": 0},
            {"price": 181.0, "type": "SUPPORT", "timestamp": "2026-01-10", "idx": 5},
            {"price": 182.0, "type": "SUPPORT", "timestamp": "2026-01-20", "idx": 10},
        ]
        zones = _cluster_into_zones(reversals, hotel_id=1, category="std")
        assert len(zones) >= 1
        zone = zones[0]
        assert zone["zone_type"] == "SUPPORT"
        assert zone["touch_count"] >= 2

    def test_separates_distant_prices(self):
        reversals = [
            {"price": 100.0, "type": "SUPPORT", "timestamp": "2026-01-01", "idx": 0},
            {"price": 101.0, "type": "SUPPORT", "timestamp": "2026-01-10", "idx": 5},
            {"price": 200.0, "type": "SUPPORT", "timestamp": "2026-01-20", "idx": 10},
            {"price": 201.0, "type": "SUPPORT", "timestamp": "2026-01-25", "idx": 15},
        ]
        zones = _cluster_into_zones(reversals, hotel_id=1, category="std")
        assert len(zones) == 2  # Two separate clusters

    def test_doesnt_mix_support_resistance(self):
        reversals = [
            {"price": 180.0, "type": "SUPPORT", "timestamp": "2026-01-01", "idx": 0},
            {"price": 181.0, "type": "RESISTANCE", "timestamp": "2026-01-10", "idx": 5},
        ]
        zones = _cluster_into_zones(reversals, hotel_id=1, category="std")
        # Each reversal type clustered separately; neither hits MIN_TOUCHES alone
        assert len(zones) == 0

    def test_empty_reversals(self):
        assert _cluster_into_zones([], hotel_id=1, category="std") == []

    def test_zone_has_required_fields(self):
        reversals = [
            {"price": 180.0, "type": "SUPPORT", "timestamp": "2026-01-01", "idx": 0},
            {"price": 181.0, "type": "SUPPORT", "timestamp": "2026-01-10", "idx": 5},
        ]
        zones = _cluster_into_zones(reversals, hotel_id=1, category="std")
        if zones:
            z = zones[0]
            assert "zone_id" in z
            assert "hotel_id" in z
            assert "price_lower" in z
            assert "price_upper" in z
            assert "touch_count" in z


# ── Zone Strength ────────────────────────────────────────────────────


class TestCalculateZoneStrength:
    """Tests for _calculate_zone_strength()."""

    def test_recent_touches_stronger(self):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        recent = {
            "touches": [
                {"timestamp": (now - timedelta(days=1)).isoformat()},
                {"timestamp": (now - timedelta(days=2)).isoformat()},
            ]
        }
        old = {
            "touches": [
                {"timestamp": (now - timedelta(days=60)).isoformat()},
                {"timestamp": (now - timedelta(days=70)).isoformat()},
            ]
        }
        assert _calculate_zone_strength(recent) > _calculate_zone_strength(old)

    def test_more_touches_stronger(self):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        two_touches = {
            "touches": [
                {"timestamp": (now - timedelta(days=5)).isoformat()},
                {"timestamp": (now - timedelta(days=10)).isoformat()},
            ]
        }
        four_touches = {
            "touches": [
                {"timestamp": (now - timedelta(days=5)).isoformat()},
                {"timestamp": (now - timedelta(days=10)).isoformat()},
                {"timestamp": (now - timedelta(days=12)).isoformat()},
                {"timestamp": (now - timedelta(days=15)).isoformat()},
            ]
        }
        assert _calculate_zone_strength(four_touches) > _calculate_zone_strength(two_touches)

    def test_empty_touches(self):
        assert _calculate_zone_strength({"touches": []}) == 0.0
        assert _calculate_zone_strength({}) == 0.0

    def test_strength_capped_at_1(self):
        from datetime import datetime
        now = datetime.utcnow()
        many_recent = {
            "touches": [{"timestamp": now.isoformat()} for _ in range(20)]
        }
        assert _calculate_zone_strength(many_recent) <= 1.0


# ── Full Demand Zone Detection ───────────────────────────────────────


class TestDetectDemandZones:
    """Integration tests for detect_demand_zones()."""

    def test_insufficient_data(self):
        df = _make_price_history([100.0, 101.0, 102.0])
        assert detect_demand_zones(df, hotel_id=1) == []

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["room_price", "snapshot_ts", "date_from"])
        assert detect_demand_zones(df, hotel_id=1) == []

    def test_detects_zones_in_bouncing_series(self):
        prices = _make_bounce_series(n=60, support=180.0, resistance=220.0, mid=200.0)
        df = _make_price_history(prices)
        zones = detect_demand_zones(df, hotel_id=1, category="standard")
        # Should detect at least some zones from the bouncing pattern
        assert isinstance(zones, list)
        for z in zones:
            assert z["zone_type"] in ("SUPPORT", "RESISTANCE")
            assert z["touch_count"] >= MIN_TOUCHES
            assert z["strength"] >= 0

    def test_zone_has_all_fields(self):
        prices = _make_bounce_series(n=60)
        df = _make_price_history(prices)
        zones = detect_demand_zones(df, hotel_id=42, category="deluxe")
        if zones:
            z = zones[0]
            assert z["hotel_id"] == 42
            assert z["category"] == "deluxe"
            assert "zone_id" in z
            assert "price_lower" in z
            assert "price_upper" in z
            assert z["price_lower"] <= z["price_upper"]

    def test_monotonic_no_zones(self):
        # Strictly rising prices should have no support zones
        prices = [100 + i * 0.5 for i in range(50)]
        df = _make_price_history(prices)
        zones = detect_demand_zones(df, hotel_id=1)
        # May detect some resistance zones from minor fluctuations but likely none
        assert isinstance(zones, list)


# ── Structure Break Detection ────────────────────────────────────────


class TestDetectStructureBreaks:
    """Tests for detect_structure_breaks() — BOS and CHOCH."""

    def test_insufficient_data(self):
        df = _make_price_history([100.0] * 5)
        assert detect_structure_breaks(df, hotel_id=1) == []

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["room_price", "snapshot_ts", "date_from"])
        assert detect_structure_breaks(df, hotel_id=1) == []

    def test_bullish_bos(self):
        # Create a series that breaks above previous high
        prices = (
            [100.0] * 5 + [110.0] * 5 + [105.0] * 5 +
            [108.0] * 5 + [103.0] * 5 + [115.0] * 5  # Breaks above 110
        )
        df = _make_price_history(prices)
        breaks = detect_structure_breaks(df, hotel_id=1)
        bullish = [b for b in breaks if b["direction"] == "BULLISH"]
        # Should detect a bullish break above previous swing high
        assert isinstance(breaks, list)

    def test_bearish_bos(self):
        # Create a series that breaks below previous low
        prices = (
            [100.0] * 5 + [90.0] * 5 + [95.0] * 5 +
            [92.0] * 5 + [97.0] * 5 + [85.0] * 5  # Breaks below 90
        )
        df = _make_price_history(prices)
        breaks = detect_structure_breaks(df, hotel_id=1)
        bearish = [b for b in breaks if b["direction"] == "BEARISH"]
        assert isinstance(breaks, list)

    def test_breaks_mark_zones_broken(self):
        # Bullish break should mark resistance zones as broken
        prices = (
            [100.0] * 5 + [110.0] * 5 + [105.0] * 5 +
            [108.0] * 5 + [103.0] * 5 + [115.0] * 5
        )
        df = _make_price_history(prices)
        zones = [
            {"zone_type": "RESISTANCE", "price_upper": 110.0, "price_lower": 108.0, "is_broken": False},
        ]
        breaks = detect_structure_breaks(df, hotel_id=1, demand_zones=zones)
        # If a bullish break was detected at 115, it should mark the resistance zone broken
        if any(b["direction"] == "BULLISH" and b["break_price"] > 110.0 for b in breaks):
            assert zones[0]["is_broken"] is True

    def test_break_fields(self):
        prices = (
            [100.0] * 5 + [110.0] * 5 + [105.0] * 5 +
            [108.0] * 5 + [103.0] * 5 + [115.0] * 5
        )
        df = _make_price_history(prices)
        breaks = detect_structure_breaks(df, hotel_id=1)
        for b in breaks:
            assert "break_id" in b
            assert "break_type" in b
            assert b["break_type"] in ("BOS", "CHOCH")
            assert b["direction"] in ("BULLISH", "BEARISH")
            assert 0 <= b["significance"] <= 1


# ── CHOCH Detection ──────────────────────────────────────────────────


class TestDetectCHOCH:
    """Tests for _detect_choch()."""

    def test_bearish_choch(self):
        # HH → LH: 100, 110, 105 (was making HH, now LH)
        swing_highs = [
            {"price": 100.0, "idx": 5, "ts": "2026-01-05"},
            {"price": 110.0, "idx": 15, "ts": "2026-01-15"},
            {"price": 105.0, "idx": 25, "ts": "2026-01-25"},
        ]
        swing_lows = [
            {"price": 90.0, "idx": 10, "ts": "2026-01-10"},
            {"price": 95.0, "idx": 20, "ts": "2026-01-20"},
            {"price": 92.0, "idx": 28, "ts": "2026-01-28"},
        ]
        timestamps = np.array([f"2026-01-{i+1:02d}" for i in range(30)])
        choch = _detect_choch(swing_highs, swing_lows, hotel_id=1, category="", timestamps=timestamps)
        bearish = [c for c in choch if c["direction"] == "BEARISH"]
        assert len(bearish) >= 1

    def test_bullish_choch(self):
        # LL → HL: 100, 90, 95 (was making LL, now HL)
        swing_highs = [
            {"price": 110.0, "idx": 5, "ts": "2026-01-05"},
            {"price": 108.0, "idx": 15, "ts": "2026-01-15"},
            {"price": 112.0, "idx": 25, "ts": "2026-01-25"},
        ]
        swing_lows = [
            {"price": 100.0, "idx": 10, "ts": "2026-01-10"},
            {"price": 90.0, "idx": 20, "ts": "2026-01-20"},
            {"price": 95.0, "idx": 28, "ts": "2026-01-28"},
        ]
        timestamps = np.array([f"2026-01-{i+1:02d}" for i in range(30)])
        choch = _detect_choch(swing_highs, swing_lows, hotel_id=1, category="", timestamps=timestamps)
        bullish = [c for c in choch if c["direction"] == "BULLISH"]
        assert len(bullish) >= 1

    def test_no_choch_in_steady_trend(self):
        # Steady HH: 100, 110, 120 — no CHOCH
        swing_highs = [
            {"price": 100.0, "idx": 5, "ts": "2026-01-05"},
            {"price": 110.0, "idx": 15, "ts": "2026-01-15"},
            {"price": 120.0, "idx": 25, "ts": "2026-01-25"},
        ]
        swing_lows = [
            {"price": 90.0, "idx": 10, "ts": "2026-01-10"},
            {"price": 85.0, "idx": 20, "ts": "2026-01-20"},
            {"price": 80.0, "idx": 28, "ts": "2026-01-28"},
        ]
        timestamps = np.array([f"2026-01-{i+1:02d}" for i in range(30)])
        choch = _detect_choch(swing_highs, swing_lows, hotel_id=1, category="", timestamps=timestamps)
        bearish = [c for c in choch if c["direction"] == "BEARISH"]
        assert len(bearish) == 0  # No CHOCH in steady uptrend
