"""Generate the consolidated landing page — unified dashboard hub.

Links to all available pages with mini-status indicators and KPIs.
"""
from __future__ import annotations

from datetime import datetime


def generate_landing_html(status: dict | None = None) -> str:
    """Build the consolidated landing page HTML."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Defaults
    s = status or {}
    total_rooms = s.get("total_rooms", "...")
    total_hotels = s.get("total_hotels", "...")
    scheduler_running = s.get("scheduler_running", False)
    snapshots = s.get("snapshots_collected", "...")
    scheduler_badge = (
        '<span class="badge badge-green">Running</span>' if scheduler_running
        else '<span class="badge badge-red">Stopped</span>'
    )

    pages = [
        {
            "title": "Analytics Dashboard",
            "url": "/api/v1/salesoffice/dashboard",
            "icon": "&#x1F4CA;",
            "description": "Full interactive Plotly dashboard with room prices, predictions, and trading signals",
            "category": "core",
        },
        {
            "title": "Chart Pack",
            "url": "/api/v1/salesoffice/charts",
            "icon": "&#x1F4C8;",
            "description": "12 Chart.js charts across 3 tabs: contract path, term structure, opportunity stats",
            "category": "core",
        },
        {
            "title": "Year-over-Year",
            "url": "/api/v1/salesoffice/yoy",
            "icon": "&#x1F4C5;",
            "description": "Multi-year decay curve comparison, calendar spread, and benchmarks",
            "category": "core",
        },
        {
            "title": "Options Trading",
            "url": "/api/v1/salesoffice/options",
            "icon": "&#x1F3AF;",
            "description": "CALL/PUT signals, expiry-relative analytics, and hedging strategies",
            "category": "core",
        },
        {
            "title": "Price Insights",
            "url": "/api/v1/salesoffice/insights",
            "icon": "&#x1F4A1;",
            "description": "When prices go up/down, days below/above today's price, volatility",
            "category": "core",
        },
        {
            "title": "Prediction Accuracy",
            "url": "/api/v1/salesoffice/accuracy",
            "icon": "&#x1F3AF;",
            "description": "Backtest: predicted vs actual settlement prices, MAPE, direction accuracy",
            "category": "intelligence",
        },
        {
            "title": "Provider Comparison",
            "url": "/api/v1/salesoffice/providers",
            "icon": "&#x1F4B0;",
            "description": "129 providers compared: net prices, margins, market share from 8.3M records",
            "category": "intelligence",
        },
        {
            "title": "Price Alerts",
            "url": "/api/v1/salesoffice/alerts",
            "icon": "&#x1F6A8;",
            "description": "Real-time alerts when contracts breach -5%/-10% thresholds",
            "category": "intelligence",
        },
        {
            "title": "Data Freshness",
            "url": "/api/v1/salesoffice/freshness",
            "icon": "&#x2705;",
            "description": "Monitor last-update times for all 14+ data sources",
            "category": "system",
        },
        {
            "title": "System Info",
            "url": "/api/v1/salesoffice/info",
            "icon": "&#x2139;",
            "description": "Documentation, glossary, API reference, and data source registry",
            "category": "system",
        },
        {
            "title": "Export & Reports",
            "url": "/api/v1/salesoffice/export/summary",
            "icon": "&#x1F4E4;",
            "description": "Weekly digest, CSV downloads for contracts and provider data",
            "category": "system",
        },
    ]

    # Group by category
    core_pages = [p for p in pages if p["category"] == "core"]
    intel_pages = [p for p in pages if p["category"] == "intelligence"]
    system_pages = [p for p in pages if p["category"] == "system"]

    def _build_cards(page_list: list[dict]) -> str:
        cards = ""
        for p in page_list:
            cards += f"""
            <a href="{p['url']}" class="page-card">
                <div class="card-icon">{p['icon']}</div>
                <div class="card-body">
                    <div class="card-title">{p['title']}</div>
                    <div class="card-desc">{p['description']}</div>
                </div>
                <div class="card-arrow">&#x2192;</div>
            </a>"""
        return cards

    # API endpoints reference
    api_endpoints = [
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
    api_rows = ""
    for path, desc in api_endpoints:
        full = f"/api/v1/salesoffice{path}"
        api_rows += f'<tr><td><a href="{full}" class="api-link">{full}</a></td><td>{desc}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Medici Price Prediction — Home</title>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--surface2:#232733;--border:#2d3140;
--text:#e4e7ec;--text-dim:#8b90a0;--accent:#6366f1;--accent2:#818cf8;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;--cyan:#06b6d4;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',-apple-system,sans-serif;}}
.container{{max-width:1200px;margin:0 auto;padding:20px 24px;}}
.hero{{text-align:center;padding:32px 0 24px;}}
.hero h1{{font-size:2.2em;background:linear-gradient(135deg,#c7d2fe,#818cf8,#6366f1);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}}
.hero p{{color:var(--text-dim);font-size:1.05em;max-width:600px;margin:0 auto;}}
.status-bar{{display:flex;gap:16px;justify-content:center;margin:20px 0 32px;flex-wrap:wrap;}}
.status-item{{background:var(--surface);border:1px solid var(--border);border-radius:8px;
padding:10px 20px;display:flex;align-items:center;gap:8px;}}
.status-item .val{{font-weight:700;color:var(--accent2);}}
.badge{{padding:2px 10px;border-radius:12px;font-size:0.8em;font-weight:600;}}
.badge-green{{background:rgba(34,197,94,0.15);color:var(--green);}}
.badge-red{{background:rgba(239,68,68,0.15);color:var(--red);}}
.section-title{{font-size:1.1em;color:var(--text-dim);margin:28px 0 12px;
text-transform:uppercase;letter-spacing:1px;font-weight:600;}}
.cards-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;}}
.page-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:16px;display:flex;gap:12px;align-items:center;text-decoration:none;color:var(--text);
transition:all 0.2s;}}
.page-card:hover{{border-color:var(--accent);background:var(--surface2);transform:translateY(-2px);}}
.card-icon{{font-size:1.8em;width:48px;text-align:center;flex-shrink:0;}}
.card-body{{flex:1;}}
.card-title{{font-weight:600;font-size:1.05em;margin-bottom:4px;}}
.card-desc{{color:var(--text-dim);font-size:0.85em;line-height:1.4;}}
.card-arrow{{color:var(--text-dim);font-size:1.2em;flex-shrink:0;}}
.page-card:hover .card-arrow{{color:var(--accent2);}}
.api-section{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:20px;margin:24px 0;}}
.api-section h3{{color:var(--accent2);margin-bottom:12px;}}
.api-table{{width:100%;border-collapse:collapse;font-size:0.85em;}}
.api-table th{{text-align:left;padding:6px 12px;color:var(--text-dim);
border-bottom:1px solid var(--border);}}
.api-table td{{padding:6px 12px;border-bottom:1px solid var(--border);}}
.api-link{{color:var(--cyan);text-decoration:none;font-family:monospace;}}
.api-link:hover{{text-decoration:underline;}}
footer{{text-align:center;color:var(--text-dim);font-size:0.8em;padding:24px 0;margin-top:40px;
border-top:1px solid var(--border);}}
@media(max-width:768px){{.cards-grid{{grid-template-columns:1fr;}}
.status-bar{{flex-direction:column;align-items:center;}}}}
</style>
</head>
<body>
<div class="container">

<div class="hero">
    <h1>Medici Price Prediction</h1>
    <p>Hotel price analytics engine — 28M+ rows, 72 tables, 14+ data sources powering real-time predictions</p>
</div>

<div class="status-bar">
    <div class="status-item"><span>Rooms:</span><span class="val">{total_rooms}</span></div>
    <div class="status-item"><span>Hotels:</span><span class="val">{total_hotels}</span></div>
    <div class="status-item"><span>Snapshots:</span><span class="val">{snapshots}</span></div>
    <div class="status-item"><span>Scheduler:</span>{scheduler_badge}</div>
</div>

<div class="section-title">Core Analytics</div>
<div class="cards-grid">{_build_cards(core_pages)}</div>

<div class="section-title">Intelligence & Monitoring</div>
<div class="cards-grid">{_build_cards(intel_pages)}</div>

<div class="section-title">System & Exports</div>
<div class="cards-grid">{_build_cards(system_pages)}</div>

<div class="api-section">
    <h3>API Endpoints</h3>
    <table class="api-table">
        <thead><tr><th>Endpoint</th><th>Description</th></tr></thead>
        <tbody>{api_rows}</tbody>
    </table>
</div>

<footer>
    Medici Price Prediction Engine | Azure App Service (B1) | Generated {now}<br>
    <span style="color:var(--text-dim);">medici-prediction-api.azurewebsites.net</span>
</footer>
</div>
</body>
</html>"""
