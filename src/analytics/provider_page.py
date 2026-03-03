"""Generate the Provider Price Comparison HTML page.

Visualizes SearchResultsSessionPollLog data: provider rankings,
margin analysis, market share, and per-hotel best providers.
"""
from __future__ import annotations

import json
from datetime import datetime


HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_provider_html(data: dict) -> str:
    """Build the Provider Comparison HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if data.get("error"):
        return _error_page(now, data["error"])

    rankings = data.get("provider_rankings", [])
    hotel_comparisons = data.get("hotel_comparisons", {})
    best_providers = data.get("best_providers", {})
    total_records = data.get("total_records", 0)
    unique_providers = data.get("unique_providers", 0)
    date_range = data.get("date_range", {})
    source = data.get("source", "")

    # Top 15 providers for ranking table
    top_providers = rankings[:15]
    ranking_rows = ""
    for i, p in enumerate(top_providers, 1):
        avg_price = p.get("avg_net_price") or p.get("avg_gross_price", 0)
        margin_str = f"{p['avg_margin_pct']:.1f}%" if p.get("avg_margin_pct") is not None else "N/A"
        ranking_rows += f"""<tr>
            <td>{i}</td>
            <td>{p['provider_name']}</td>
            <td>${avg_price:,.0f}</td>
            <td>${p['avg_gross_price']:,.0f}</td>
            <td>{margin_str}</td>
            <td>{p['total_results']:,}</td>
            <td>{p['market_share_pct']:.1f}%</td>
        </tr>"""

    # Best provider cards
    best_cards = ""
    for hid, bp in best_providers.items():
        best_cards += f"""
        <div class="best-card">
            <div class="best-hotel">{bp['hotel_name']}</div>
            <div class="best-provider">{bp['provider']}</div>
            <div class="best-price">${bp['avg_price']:,.0f}<span> avg</span></div>
        </div>"""

    # Market share pie chart data (top 10)
    pie_labels = [p["provider_name"] for p in rankings[:10]]
    pie_values = [p["market_share_pct"] for p in rankings[:10]]
    other_share = 100 - sum(pie_values)
    if other_share > 0:
        pie_labels.append("Others")
        pie_values.append(round(other_share, 1))

    # Price comparison bar chart (top 10 by avg price)
    bar_labels = [p["provider_name"][:20] for p in top_providers[:10]]
    bar_gross = [p["avg_gross_price"] for p in top_providers[:10]]
    bar_net = [p.get("avg_net_price") or 0 for p in top_providers[:10]]

    # Per-hotel tables
    hotel_sections = ""
    for hid, hdata in hotel_comparisons.items():
        hname = hdata.get("hotel_name", f"Hotel {hid}")
        providers = hdata.get("providers", [])[:10]
        if not providers:
            continue
        prows = ""
        for p in providers:
            avg_p = p.get("avg_net_price") or p.get("avg_gross_price", 0)
            prows += f"""<tr>
                <td>{p['provider_name']}</td>
                <td>${avg_p:,.0f}</td>
                <td>${p['avg_gross_price']:,.0f}</td>
                <td>{p['total_results']:,}</td>
            </tr>"""
        hotel_sections += f"""
        <div class="hotel-section">
            <h3>{hname} <span class="dim">({hdata.get('total_results', 0):,} results)</span></h3>
            <table class="prov-table">
                <thead><tr><th>Provider</th><th>Avg Net</th><th>Avg Gross</th><th>Results</th></tr></thead>
                <tbody>{prows}</tbody>
            </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Provider Comparison — Medici</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--surface2:#232733;--border:#2d3140;
--text:#e4e7ec;--text-dim:#8b90a0;--accent:#6366f1;--accent2:#818cf8;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;--cyan:#06b6d4;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',-apple-system,sans-serif;}}
.container{{max-width:1400px;margin:0 auto;padding:20px 24px;}}
h1{{font-size:1.8em;background:linear-gradient(135deg,#67e8f9,#06b6d4);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}}
.subtitle{{color:var(--text-dim);margin-bottom:24px;}}
.kpi-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:16px 24px;flex:1;min-width:170px;text-align:center;}}
.kpi .val{{font-size:2em;font-weight:700;color:var(--cyan);}}
.kpi .label{{color:var(--text-dim);font-size:0.85em;margin-top:4px;}}
.best-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;}}
.best-card{{background:var(--surface);border:1px solid var(--green);border-radius:12px;
padding:16px;flex:1;min-width:200px;text-align:center;}}
.best-hotel{{color:var(--text-dim);font-size:0.85em;margin-bottom:4px;}}
.best-provider{{color:var(--green);font-weight:700;font-size:1.1em;}}
.best-price{{font-size:1.5em;font-weight:700;color:var(--text);margin-top:4px;}}
.best-price span{{font-size:0.5em;color:var(--text-dim);}}
.charts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0;}}
.chart-box{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;}}
.chart-box h4{{color:var(--text-dim);margin-bottom:12px;font-size:0.95em;}}
.prov-table{{width:100%;border-collapse:collapse;font-size:0.9em;margin-bottom:16px;}}
.prov-table th{{background:var(--surface2);color:var(--text-dim);padding:8px 12px;
text-align:left;border-bottom:1px solid var(--border);}}
.prov-table td{{padding:8px 12px;border-bottom:1px solid var(--border);}}
.hotel-section{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:20px;margin-bottom:20px;}}
.hotel-section h3{{color:var(--accent2);margin-bottom:12px;}}
.hotel-section .dim{{color:var(--text-dim);font-size:0.85em;font-weight:400;}}
nav{{background:var(--surface);padding:10px 24px;border-bottom:1px solid var(--border);
display:flex;gap:16px;align-items:center;font-size:0.9em;flex-wrap:wrap;}}
nav a{{color:var(--text-dim);text-decoration:none;}}
nav a:hover{{color:var(--accent2);}}
nav .active{{color:var(--accent2);font-weight:600;}}
footer{{text-align:center;color:var(--text-dim);font-size:0.8em;padding:24px 0;margin-top:40px;
border-top:1px solid var(--border);}}
@media(max-width:768px){{.charts-grid{{grid-template-columns:1fr;}}}}
</style>
</head>
<body>
<nav>
    <a href="/api/v1/salesoffice/home">Home</a>
    <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
    <a href="/api/v1/salesoffice/charts">Charts</a>
    <a href="/api/v1/salesoffice/accuracy">Accuracy</a>
    <a href="/api/v1/salesoffice/providers" class="active">Providers</a>
    <a href="/api/v1/salesoffice/alerts">Alerts</a>
    <a href="/api/v1/salesoffice/freshness">Freshness</a>
</nav>
<div class="container">
<h1>Provider Price Comparison</h1>
<p class="subtitle">Which providers offer the best net prices across {unique_providers} suppliers</p>

<div class="kpi-row">
    <div class="kpi"><div class="val">{total_records:,}</div><div class="label">Search Results</div></div>
    <div class="kpi"><div class="val">{unique_providers}</div><div class="label">Unique Providers</div></div>
    <div class="kpi"><div class="val">{date_range.get('from', 'N/A')}</div><div class="label">Data From</div></div>
    <div class="kpi"><div class="val">{date_range.get('to', 'N/A')}</div><div class="label">Data To</div></div>
</div>

<h2 style="color:var(--green);margin-bottom:12px;">Best Provider per Hotel</h2>
<div class="best-row">{best_cards}</div>

<div class="charts-grid">
    <div class="chart-box">
        <h4>Provider Market Share</h4>
        <canvas id="chartPie"></canvas>
    </div>
    <div class="chart-box">
        <h4>Price Comparison (Top 10)</h4>
        <canvas id="chartBar"></canvas>
    </div>
</div>

<h2 style="color:var(--accent2);margin:24px 0 12px;">Provider Rankings (Sorted by Lowest Net Price)</h2>
<div class="hotel-section">
<table class="prov-table">
    <thead><tr>
        <th>#</th><th>Provider</th><th>Avg Net</th><th>Avg Gross</th>
        <th>Margin</th><th>Results</th><th>Market Share</th>
    </tr></thead>
    <tbody>{ranking_rows}</tbody>
</table>
</div>

{hotel_sections}

<footer>
    Provider Price Comparison | Source: {source} | Period: {date_range.get('from', '?')} to {date_range.get('to', '?')} | Generated {now}<br>
    <a href="/api/v1/salesoffice/home" style="color:var(--accent2)">Back to Home</a>
</footer>
</div>

<script>
const pieColors = ['#6366f1','#22c55e','#eab308','#ef4444','#06b6d4','#f97316','#8b5cf6',
'#ec4899','#14b8a6','#64748b','#4b5563'];

new Chart(document.getElementById('chartPie'), {{
    type: 'doughnut',
    data: {{
        labels: {json.dumps(pie_labels, default=str)},
        datasets: [{{data: {json.dumps(pie_values, default=str)}, backgroundColor: pieColors}}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{position: 'right', labels: {{color: '#8b90a0', font: {{size: 11}}}}}}
        }}
    }}
}});

new Chart(document.getElementById('chartBar'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(bar_labels, default=str)},
        datasets: [
            {{label: 'Net Price', data: {json.dumps(bar_net, default=str)}, backgroundColor: '#22c55e', borderRadius: 4}},
            {{label: 'Gross Price', data: {json.dumps(bar_gross, default=str)}, backgroundColor: '#6366f1', borderRadius: 4}}
        ]
    }},
    options: {{
        responsive: true,
        plugins: {{legend: {{labels: {{color: '#8b90a0'}}}}}},
        scales: {{
            x: {{ticks: {{color: '#8b90a0', maxRotation: 45}}, grid: {{color: '#2d3140'}}}},
            y: {{ticks: {{color: '#8b90a0', callback: v => '$' + v}}, grid: {{color: '#2d3140'}}}}
        }}
    }}
}});
</script>
</body>
</html>"""


def _error_page(now: str, error: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Provider Comparison — Error</title>
<style>body{{background:#0f1117;color:#e4e7ec;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;min-height:100vh;}}
.box{{text-align:center;padding:40px;}}</style></head>
<body><div class="box"><h1>Provider Price Comparison</h1>
<p style="color:#ef4444;margin-top:16px;">{error}</p>
<p style="color:#8b90a0;margin-top:8px;">Generated {now}</p>
<a href="/api/v1/salesoffice/home" style="color:#818cf8;">Back to Home</a>
</div></body></html>"""
