"""HTML generation functions for the options dashboard.

Sprint 2.3 extracted all inline HTML to Jinja2 templates.
Sprint TD-1 removed 3,500 lines of dead legacy HTML code.

Active template: src/templates/options_board.html
"""
from __future__ import annotations

import json


def _generate_html(analysis: dict) -> str:
    """Generate the HTML dashboard from analysis results."""
    from src.analytics.report import generate_report

    report_path = generate_report(analysis)
    return report_path.read_text(encoding="utf-8")


def _html_escape(s: str) -> str:
    """Minimal HTML escaping for user-provided strings."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _generate_options_async_html(t_days: int | None = None, signal: str | None = None) -> str:
    """Generate a fast shell that loads options data asynchronously from the JSON API."""
    from src.utils.template_engine import render_template

    initial_t_days = "null" if t_days is None else str(int(t_days))
    initial_signal = json.dumps((signal or "").strip().upper())

    return render_template(
        "options_board.html",
        initial_t_days=initial_t_days,
        initial_signal=initial_signal,
    )


def _generate_options_html_legacy(rows: list[dict], analysis: dict, t_days: int | None) -> str:
    """Legacy wrapper — redirects to async version."""
    return _generate_options_async_html(t_days=t_days)
