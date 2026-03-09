"""Generate the Data Freshness Monitor HTML page.

Shows last-updated timestamp and staleness status for every data source.
"""
from __future__ import annotations

from datetime import datetime

from src.utils.template_engine import render_template


def generate_freshness_html(data: dict) -> str:
    """Build the Data Freshness Monitor HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return render_template(
        "freshness.html",
        active_page="freshness",
        now=now,
        summary=data.get("summary", {}),
        sources=data.get("sources", []),
        checked_at=data.get("checked_at", now),
    )
