"""Unit tests for cache_aggregator.py — Azure SQL → Analytical Cache pipeline.

Tests the aggregator logic with mock data (no real Azure SQL needed).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

import pandas as pd
import pytest

from src.analytics.cache_aggregator import CacheAggregator


@pytest.fixture
def cache(tmp_path):
    """Create a real AnalyticalCache with temp database."""
    from src.analytics.analytical_cache import AnalyticalCache
    return AnalyticalCache(db_path=tmp_path / "test_agg.db")


@pytest.fixture
def aggregator(cache):
    """Create a CacheAggregator with mocked engine."""
    agg = CacheAggregator(cache=cache)
    agg._engine = MagicMock()
    return agg


# ── SQL Query Constants ──────────────────────────────────────────────


class TestSQLQueries:
    """Verify SQL query strings are well-formed."""

    def test_hotel_query_has_select(self):
        from src.analytics.cache_aggregator import _SQL_HOTELS
        assert "SELECT" in _SQL_HOTELS
        assert "Med_Hotels" in _SQL_HOTELS

    def test_market_daily_query_uses_price_history(self):
        from src.analytics.cache_aggregator import _SQL_MARKET_DAILY
        assert "SalesOffice.PriceHistory" in _SQL_MARKET_DAILY
        assert "AVG(NewPrice)" in _SQL_MARKET_DAILY

    def test_price_history_query(self):
        from src.analytics.cache_aggregator import _SQL_PRICE_HISTORY
        assert "SalesOffice.PriceHistory" in _SQL_PRICE_HISTORY
        assert "hotel_id" in _SQL_PRICE_HISTORY.lower()

    def test_volatility_query(self):
        from src.analytics.cache_aggregator import _SQL_VOLATILITY
        assert "STDEV" in _SQL_VOLATILITY
        assert "SalesOffice.PriceHistory" in _SQL_VOLATILITY

    def test_price_drops_query(self):
        from src.analytics.cache_aggregator import _SQL_PRICE_DROPS
        assert "PriceChange < -10" in _SQL_PRICE_DROPS

    def test_price_trend_query(self):
        from src.analytics.cache_aggregator import _SQL_PRICE_TREND
        assert "hotel_id" in _SQL_PRICE_TREND


# ── Reference Data Refresh ───────────────────────────────────────────


class TestRefreshReferenceData:
    """Tests for Layer 1 reference data refresh."""

    def test_refresh_hotels(self, aggregator):
        hotels_df = pd.DataFrame([
            {"hotel_id": 1, "hotel_name": "Beach Hotel", "city": "Miami",
             "stars": 4, "latitude": None, "longitude": None},
        ])
        aggregator._run_query = MagicMock(side_effect=[
            hotels_df,            # Hotels
            pd.DataFrame(),       # Categories (empty)
            pd.DataFrame(),       # Boards (empty)
        ])
        result = aggregator.refresh_reference_data()
        assert result["hotels"] == 1

    def test_refresh_all_reference(self, aggregator):
        hotels_df = pd.DataFrame([
            {"hotel_id": 1, "hotel_name": "H1", "city": "", "stars": 0,
             "latitude": None, "longitude": None},
        ])
        cats_df = pd.DataFrame([
            {"category_id": 1, "category_name": "standard"},
        ])
        boards_df = pd.DataFrame([
            {"board_id": 1, "board_name": "bb"},
        ])
        aggregator._run_query = MagicMock(side_effect=[hotels_df, cats_df, boards_df])
        result = aggregator.refresh_reference_data()
        assert result["hotels"] == 1
        assert result["categories"] == 1
        assert result["boards"] == 1

    def test_refresh_empty_data(self, aggregator):
        aggregator._run_query = MagicMock(return_value=pd.DataFrame())
        result = aggregator.refresh_reference_data()
        assert result["hotels"] == 0


# ── Market Data Refresh ──────────────────────────────────────────────


class TestRefreshMarketData:
    """Tests for Layer 2 market data refresh."""

    def test_refresh_market_daily(self, aggregator):
        market_df = pd.DataFrame([
            {"hotel_id": 1, "date": "2026-03-20", "room_type": "standard",
             "board": "bb", "avg_price": 200.0, "min_price": 180.0,
             "max_price": 220.0, "observation_count": 10},
        ])
        aggregator._run_query = MagicMock(side_effect=[
            market_df,        # Market daily
            pd.DataFrame(),   # Competitors (empty)
        ])
        result = aggregator.refresh_market_data()
        assert result["market_daily"] == 1

    def test_refresh_with_competitors(self, aggregator):
        market_df = pd.DataFrame([
            {"hotel_id": 1, "date": "2026-03-20", "room_type": "standard",
             "board": "bb", "avg_price": 200.0, "min_price": 180.0,
             "max_price": 220.0, "observation_count": 10},
        ])
        comp_df = pd.DataFrame([
            {"hotel_id": 1, "competitor_hotel_id": 2, "distance_km": 1.5,
             "star_diff": 0, "avg_price_ratio": 0.95, "market_pressure": 0.1},
        ])
        aggregator._run_query = MagicMock(side_effect=[market_df, comp_df])
        result = aggregator.refresh_market_data()
        assert result["market_daily"] == 1
        assert result["competitors"] == 1

    def test_refresh_empty_market(self, aggregator):
        aggregator._run_query = MagicMock(return_value=pd.DataFrame())
        result = aggregator.refresh_market_data()
        assert result["market_daily"] == 0


# ── Price History Retrieval ──────────────────────────────────────────


class TestPriceHistory:
    """Tests for price history data retrieval."""

    def test_get_price_history(self, aggregator):
        df = pd.DataFrame([
            {"hotel_id": 1, "room_price": 200.0, "snapshot_ts": "2026-03-20"},
        ])
        aggregator._run_query = MagicMock(return_value=df)
        result = aggregator.get_price_history(hotel_id=1, days_back=90)
        assert len(result) == 1

    def test_get_all_price_history(self, aggregator):
        df = pd.DataFrame([
            {"hotel_id": 1, "room_price": 200.0, "snapshot_ts": "2026-03-20"},
            {"hotel_id": 2, "room_price": 180.0, "snapshot_ts": "2026-03-20"},
        ])
        aggregator._run_query = MagicMock(return_value=df)
        result = aggregator.get_all_price_history(days_back=90)
        assert len(result) == 2

    def test_get_volatility_data(self, aggregator):
        df = pd.DataFrame([
            {"hotel_id": 1, "room_category": "standard", "total_changes": 50,
             "avg_volatility": 5.2, "price_std_dev": 12.0,
             "all_time_min": 150.0, "all_time_max": 280.0, "avg_price": 200.0},
        ])
        aggregator._run_query = MagicMock(return_value=df)
        result = aggregator.get_volatility_data()
        assert len(result) == 1

    def test_get_price_drops(self, aggregator):
        df = pd.DataFrame([
            {"HotelId": 1, "PriceChange": -25.0},
        ])
        aggregator._run_query = MagicMock(return_value=df)
        result = aggregator.get_price_drops()
        assert len(result) == 1

    def test_get_price_trend(self, aggregator):
        df = pd.DataFrame([
            {"snapshot_ts": "2026-03-18", "room_price": 195.0},
            {"snapshot_ts": "2026-03-19", "room_price": 200.0},
            {"snapshot_ts": "2026-03-20", "room_price": 198.0},
        ])
        aggregator._run_query = MagicMock(return_value=df)
        result = aggregator.get_price_trend(hotel_id=1, date_from="2026-05-15",
                                            room_category="standard", room_board="BB")
        assert len(result) == 3


# ── Full Refresh ─────────────────────────────────────────────────────


class TestFullRefresh:
    """Tests for full_refresh() orchestration."""

    def test_full_refresh(self, aggregator):
        # Layer 1
        hotels_df = pd.DataFrame([{"hotel_id": 1, "hotel_name": "H1", "city": "",
                                    "stars": 0, "latitude": None, "longitude": None}])
        # Layer 2
        market_df = pd.DataFrame([
            {"hotel_id": 1, "date": "2026-03-20", "room_type": "standard",
             "board": "bb", "avg_price": 200.0, "min_price": 180.0,
             "max_price": 220.0, "observation_count": 10},
        ])
        # Return different DFs for different calls
        call_count = [0]
        def mock_query(sql, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return hotels_df  # Hotels
            elif call_count[0] <= 3:
                return pd.DataFrame()  # Cats, Boards
            elif call_count[0] == 4:
                return market_df  # Market daily
            return pd.DataFrame()

        aggregator._run_query = mock_query
        result = aggregator.full_refresh()
        assert "layer1_hotels" in result
        assert result["layer1_hotels"] == 1

    def test_full_refresh_handles_errors(self, aggregator):
        def fail(*args, **kwargs):
            raise ConnectionError("DB down")
        aggregator._run_query = fail
        # Should not raise — errors are caught
        result = aggregator.full_refresh()
        assert isinstance(result, dict)


# ── Demand Zone Analysis ─────────────────────────────────────────────


class TestDemandZoneAnalysis:
    """Tests for demand zone analysis pipeline."""

    def test_empty_history(self, aggregator):
        aggregator._run_query = MagicMock(return_value=pd.DataFrame())
        result = aggregator.run_demand_zone_analysis(hotel_id=1)
        assert result == {"zones": 0, "breaks": 0}

    def test_with_bouncing_prices(self, aggregator):
        import numpy as np
        # Create bouncing price history
        n = 60
        prices = []
        going_up = True
        price = 200.0
        for i in range(n):
            if going_up:
                price += 4
                if price >= 220:
                    going_up = False
            else:
                price -= 4
                if price <= 180:
                    going_up = True
            prices.append(price)

        dates = pd.date_range("2026-01-01", periods=n, freq="D")
        df = pd.DataFrame({
            "hotel_id": [1] * n,
            "date_from": dates,
            "room_category": ["standard"] * n,
            "room_board": ["BB"] * n,
            "room_price": prices,
            "old_price": [p - 2 for p in prices],
            "price_change": [2.0] * n,
            "change_pct": [1.0] * n,
            "snapshot_ts": dates,
        })
        aggregator._run_query = MagicMock(return_value=df)
        result = aggregator.run_demand_zone_analysis(hotel_id=1)
        assert isinstance(result, dict)
        assert "zones" in result
        assert "breaks" in result

    def test_run_all_demand_zones_empty(self, aggregator):
        aggregator._run_query = MagicMock(return_value=pd.DataFrame())
        result = aggregator.run_all_demand_zones()
        assert result["total_zones"] == 0
        assert result["hotels_analyzed"] == 0


# ── Query Error Handling ─────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling in queries."""

    def test_query_failure_handled_by_full_refresh(self, aggregator):
        """full_refresh catches errors from individual refresh methods."""
        def fail(*args, **kwargs):
            raise ConnectionError("DB down")
        aggregator.refresh_reference_data = fail
        aggregator.refresh_market_data = fail
        # full_refresh wraps each layer in try/except
        result = aggregator.full_refresh()
        assert isinstance(result, dict)

    def test_competitor_failure_doesnt_break_market(self, aggregator):
        market_df = pd.DataFrame([
            {"hotel_id": 1, "date": "2026-03-20", "room_type": "standard",
             "board": "bb", "avg_price": 200.0, "min_price": 180.0,
             "max_price": 220.0, "observation_count": 10},
        ])
        call_count = [0]
        def mock_query(sql, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return market_df
            raise Exception("Competitor query failed")

        aggregator._run_query = mock_query
        result = aggregator.refresh_market_data()
        assert result["market_daily"] == 1
        assert result["competitors"] == 0
