# tests/unit/test_terminal_v2_page.py
"""Tests for Terminal V2 page generator."""
from __future__ import annotations

import pytest


class TestTerminalV2Page:
    """Terminal V2 page generator tests."""

    def test_generate_returns_html_string(self):
        from src.analytics.terminal_v2_page import generate_terminal_v2_html
        result = generate_terminal_v2_html()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_html_contains_terminal_marker(self):
        from src.analytics.terminal_v2_page import generate_terminal_v2_html
        html = generate_terminal_v2_html()
        assert "MEDICI TERMINAL" in html

    def test_html_contains_chart_container(self):
        from src.analytics.terminal_v2_page import generate_terminal_v2_html
        html = generate_terminal_v2_html()
        assert "chart-area" in html

    def test_html_contains_table_container(self):
        from src.analytics.terminal_v2_page import generate_terminal_v2_html
        html = generate_terminal_v2_html()
        assert "signal-table" in html

    def test_html_contains_sidebar(self):
        from src.analytics.terminal_v2_page import generate_terminal_v2_html
        html = generate_terminal_v2_html()
        assert "right-sidebar" in html

    def test_html_no_traceback(self):
        from src.analytics.terminal_v2_page import generate_terminal_v2_html
        html = generate_terminal_v2_html()
        assert "Traceback" not in html
