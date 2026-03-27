# src/analytics/terminal_v2_page.py
"""Terminal V2 — unified Bloomberg-style trading terminal."""
from __future__ import annotations

from src.utils.template_engine import render_template


def generate_terminal_v2_html() -> str:
    """Return self-contained HTML for the Terminal V2 dashboard."""
    return render_template("terminal_v2.html")
