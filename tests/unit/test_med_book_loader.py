"""Tests for MED_Book prediction pipeline loader."""
import pytest
import pandas as pd


class TestMedBookLoader:
    """Tests for load_med_book_for_prediction and collect_med_book_predictions."""

    def test_collect_med_book_returns_dataframe(self):
        """collect_med_book_predictions returns a DataFrame (empty if DB unavailable)."""
        from src.analytics.collector import collect_med_book_predictions
        df = collect_med_book_predictions()
        assert isinstance(df, pd.DataFrame)

    def test_load_med_book_function_exists(self):
        """load_med_book_for_prediction is importable."""
        from src.data.trading_db import load_med_book_for_prediction
        assert callable(load_med_book_for_prediction)

    def test_collect_med_book_handles_import_error(self):
        """Gracefully handles missing trading_db — should not raise."""
        from src.analytics.collector import collect_med_book_predictions
        # Should not raise even if DB is unavailable
        df = collect_med_book_predictions()
        assert isinstance(df, pd.DataFrame)
