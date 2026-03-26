"""Unified Trading Terminal — mission control consolidating all Medici analytics.

Single dark-themed page with 3-column layout:
  Left:   Portfolio summary, correlation heatmap, meta-learner consensus
  Center: Live signal table, backtest badges, attribution chart
  Right:  Streaming alerts, audit trail, execution quality

All data loaded via fetch() from existing API endpoints.
Auto-refresh every 60s (alerts every 30s).
"""
from __future__ import annotations

from src.utils.template_engine import render_template


def generate_unified_terminal_html() -> str:
    """Return self-contained HTML for the Unified Trading Terminal."""
    return render_template("unified_terminal.html")
