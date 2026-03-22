"""Command Center — unified 3-column trading dashboard."""
from __future__ import annotations

from src.utils.template_engine import render_template


def generate_command_center_html() -> str:
    """Return self-contained HTML for the Command Center dashboard."""
    return render_template("command_center.html")
