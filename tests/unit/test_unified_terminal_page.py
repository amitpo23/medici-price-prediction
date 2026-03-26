"""Tests for the Unified Trading Terminal page generator."""
from __future__ import annotations

import pytest

from src.analytics.unified_terminal_page import generate_unified_terminal_html


class TestUnifiedTerminalPage:
    """Tests for generate_unified_terminal_html."""

    def test_returns_html_string(self):
        html = generate_unified_terminal_html()
        assert isinstance(html, str)
        assert len(html) > 1000

    def test_contains_doctype(self):
        html = generate_unified_terminal_html()
        assert "<!DOCTYPE html>" in html

    def test_contains_title(self):
        html = generate_unified_terminal_html()
        assert "Unified Trading Terminal" in html

    def test_contains_dark_theme(self):
        html = generate_unified_terminal_html()
        assert "#1a1a2e" in html

    def test_contains_three_columns(self):
        html = generate_unified_terminal_html()
        assert "grid-template-columns" in html
        assert 'class="col"' in html

    def test_contains_portfolio_panel(self):
        html = generate_unified_terminal_html()
        assert "Portfolio Summary" in html
        assert "portfolio-body" in html

    def test_contains_correlation_panel(self):
        html = generate_unified_terminal_html()
        assert "Cross-Hotel Correlation" in html
        assert "corr-canvas" in html

    def test_contains_meta_learner_panel(self):
        html = generate_unified_terminal_html()
        assert "Meta-Learner Consensus" in html
        assert "meta-body" in html

    def test_contains_signal_table(self):
        html = generate_unified_terminal_html()
        assert "Active Signals" in html
        assert "sig-tbody" in html
        assert "data-sort" in html

    def test_contains_attribution_chart(self):
        html = generate_unified_terminal_html()
        assert "Signal Attribution" in html
        assert "attr-canvas" in html

    def test_contains_streaming_alerts(self):
        html = generate_unified_terminal_html()
        assert "Streaming Alerts" in html
        assert "alerts-body" in html

    def test_contains_audit_trail(self):
        html = generate_unified_terminal_html()
        assert "Audit Trail" in html
        assert "audit-body" in html

    def test_contains_execution_quality(self):
        html = generate_unified_terminal_html()
        assert "Execution Quality" in html
        assert "exec-body" in html

    def test_contains_auto_refresh(self):
        html = generate_unified_terminal_html()
        assert "setInterval" in html
        assert "60000" in html

    def test_contains_alert_fast_refresh(self):
        html = generate_unified_terminal_html()
        assert "30000" in html

    def test_contains_api_endpoints(self):
        html = generate_unified_terminal_html()
        assert "/positions/pnl" in html
        assert "/correlation" in html
        assert "/meta-learner" in html
        assert "/streaming-alerts" in html
        assert "/execution/quality" in html
        assert "/attribution/enrichments" in html

    def test_contains_chartjs(self):
        html = generate_unified_terminal_html()
        assert "chart.js" in html.lower() or "Chart" in html

    def test_mobile_responsive(self):
        html = generate_unified_terminal_html()
        assert "@media" in html
        assert "1024px" in html

    def test_signal_badges(self):
        html = generate_unified_terminal_html()
        assert ".sig.call" in html
        assert ".sig.put" in html
        assert ".sig.neutral" in html

    def test_command_center_link(self):
        html = generate_unified_terminal_html()
        assert "command-center" in html
