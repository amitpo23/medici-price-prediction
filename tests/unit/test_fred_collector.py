"""Tests for FRED collector."""
import pytest
from src.collectors.fred_collector import get_hotel_ppi_trend, fetch_fred_series, SERIES


class TestFredCollector:
    """FRED collector tests — no API key required for baseline behavior."""

    def test_get_hotel_ppi_trend_no_key(self):
        """Without FRED_API_KEY, should return flat direction."""
        result = get_hotel_ppi_trend()
        assert result["direction"] == "flat"
        assert result["change_pct"] == 0
        assert result["latest"] == 0

    def test_fetch_fred_series_no_key(self):
        """Without FRED_API_KEY, fetch should return empty list."""
        result = fetch_fred_series(SERIES["hotel_ppi"])
        assert result == []

    def test_fetch_fred_series_luxury_no_key(self):
        """Luxury series also returns empty without key."""
        result = fetch_fred_series(SERIES["luxury_hotel_ppi"])
        assert result == []

    def test_series_ids_defined(self):
        """Both series IDs should be defined."""
        assert "hotel_ppi" in SERIES
        assert "luxury_hotel_ppi" in SERIES
        assert SERIES["hotel_ppi"] == "PCU721110721110"
        assert SERIES["luxury_hotel_ppi"] == "PCU721110721110103"
