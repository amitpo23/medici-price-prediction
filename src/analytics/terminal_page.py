"""Trading Terminal — unified dark-themed dashboard for hotel options traders."""
from __future__ import annotations

from src.utils.template_engine import render_template


def generate_terminal_html() -> str:
    """Return self-contained HTML for the Trading Terminal dashboard."""
    return render_template("terminal.html")
