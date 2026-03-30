"""Generate the consolidated landing page — unified dashboard hub.

Links to all available pages with mini-status indicators and KPIs.
"""
from __future__ import annotations

from datetime import datetime

from src.utils.template_engine import render_template

# Page definitions — static data for the landing page cards
_PAGES = [
    {"title": "Trading Terminal (PRIMARY)", "url": "/api/v1/salesoffice/dashboard/terminal-v2",
     "icon": "&#x1F4BB;", "description": "PRIMARY — Bloomberg-style trading terminal with charts, consensus votes, arbitrage, and keyboard navigation", "category": "core"},
    {"title": "Command Center", "url": "/api/v1/salesoffice/dashboard/command-center",
     "icon": "&#x1F3AE;", "description": "Unified 3-column trading — navigate, analyze, and execute from one screen", "category": "core"},
    {"title": "Macro Terminal", "url": "/api/v1/salesoffice/dashboard/macro",
     "icon": "&#x1F30D;", "description": "Portfolio-level trading view — heat map, drill-down, all hotels at once", "category": "core"},
    {"title": "Analytics Dashboard", "url": "/api/v1/salesoffice/dashboard",
     "icon": "&#x1F4CA;", "description": "Full interactive Plotly dashboard with room prices, predictions, and trading signals", "category": "core"},
    {"title": "Chart Pack", "url": "/api/v1/salesoffice/charts",
     "icon": "&#x1F4C8;", "description": "12 Chart.js charts across 3 tabs: contract path, term structure, opportunity stats", "category": "core"},
    {"title": "Year-over-Year", "url": "/api/v1/salesoffice/yoy",
     "icon": "&#x1F4C5;", "description": "Multi-year decay curve comparison, calendar spread, and benchmarks", "category": "core"},
    {"title": "Options Trading", "url": "/api/v1/salesoffice/options/view",
     "icon": "&#x1F3AF;", "description": "CALL/PUT signals, expiry-relative analytics, and hedging strategies", "category": "core"},
    {"title": "Price Insights", "url": "/api/v1/salesoffice/insights",
     "icon": "&#x1F4A1;", "description": "When prices go up/down, days below/above today's price, volatility", "category": "core"},
    {"title": "Prediction Accuracy", "url": "/api/v1/salesoffice/accuracy",
     "icon": "&#x1F3AF;", "description": "Backtest: predicted vs actual settlement prices, MAPE, direction accuracy", "category": "intelligence"},
    {"title": "Provider Comparison", "url": "/api/v1/salesoffice/providers",
     "icon": "&#x1F4B0;", "description": "129 providers compared: net prices, margins, market share from 8.3M records", "category": "intelligence"},
    {"title": "Price Alerts", "url": "/api/v1/salesoffice/alerts",
     "icon": "&#x1F6A8;", "description": "Real-time alerts when contracts breach -5%/-10% thresholds", "category": "intelligence"},
    {"title": "Data Freshness", "url": "/api/v1/salesoffice/freshness",
     "icon": "&#x2705;", "description": "Monitor last-update times for all 14+ data sources", "category": "system"},
    {"title": "System Info", "url": "/api/v1/salesoffice/info",
     "icon": "&#x2139;", "description": "Documentation, glossary, API reference, and data source registry", "category": "system"},
    {"title": "Export & Reports", "url": "/api/v1/salesoffice/export/summary",
     "icon": "&#x1F4E4;", "description": "Weekly digest, CSV downloads for contracts and provider data", "category": "system"},
]

_API_ENDPOINTS = [
    ("/data", "Raw analysis JSON"),
    ("/simple", "Simplified human-readable JSON"),
    ("/simple/text", "Plain text report"),
    ("/backtest", "Walk-forward backtest"),
    ("/status", "Quick health check"),
    ("/decay-curve", "Empirical decay curve"),
    ("/events", "Miami events data"),
    ("/data-sources", "Data source registry"),
    ("/benchmarks", "Booking benchmarks"),
    ("/market/db-overview", "Full DB overview"),
    ("/export/csv/contracts", "CSV: Contract prices"),
    ("/export/csv/providers", "CSV: Provider data"),
    ("/export/summary", "Weekly summary JSON"),
]


def generate_landing_html(status: dict | None = None) -> str:
    """Build the consolidated landing page HTML."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    s = status or {}

    return render_template(
        "landing.html",
        now=now,
        total_rooms=s.get("total_rooms", "..."),
        total_hotels=s.get("total_hotels", "..."),
        snapshots=s.get("snapshots_collected", "..."),
        scheduler_running=s.get("scheduler_running", False),
        core_pages=[p for p in _PAGES if p["category"] == "core"],
        intel_pages=[p for p in _PAGES if p["category"] == "intelligence"],
        system_pages=[p for p in _PAGES if p["category"] == "system"],
        api_endpoints=_API_ENDPOINTS,
    )
