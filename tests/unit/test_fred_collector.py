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


class TestFREDCollector:
    """Tests for the FREDCollector BaseCollector subclass."""

    def test_collector_has_name(self):
        from src.collectors.fred_collector import FREDCollector
        c = FREDCollector()
        assert c.name == "fred"

    def test_collector_not_available_without_key(self):
        """Without FRED_API_KEY env var, should not be available."""
        import os
        import importlib
        import src.collectors.fred_collector as fmod

        old = os.environ.get("FRED_API_KEY", "")
        os.environ["FRED_API_KEY"] = ""
        try:
            importlib.reload(fmod)
            c = fmod.FREDCollector()
            assert not c.is_available()
        finally:
            if old:
                os.environ["FRED_API_KEY"] = old
            else:
                os.environ.pop("FRED_API_KEY", None)
            importlib.reload(fmod)

    def test_collector_returns_empty_df_without_key(self):
        from src.collectors.fred_collector import FREDCollector
        import pandas as pd
        c = FREDCollector()
        df = c.collect()
        assert isinstance(df, pd.DataFrame)
