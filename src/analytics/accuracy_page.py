"""Generate the Prediction Accuracy Tracker HTML page.

Shows backtest results: predicted vs actual settlement prices,
accuracy metrics per hotel and T-bucket, scatter plots.
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


def generate_accuracy_html(data: dict) -> str:
    """Build the Prediction Accuracy Tracker HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if data.get("error"):
        return _error_page(now, data["error"])

    overall = data.get("overall", {})
    hotels = data.get("hotels", {})
    yoy = data.get("yoy_accuracy", {})
    total_contracts = data.get("total_contracts", 0)
    total_obs = data.get("total_observations", 0)
    sources = data.get("sources_used", {})

    # KPI bar
    overall_by_t = overall.get("by_T", {})
    best_t = None
    best_within5 = 0
    for t_val, stats in overall_by_t.items():
        w5 = stats.get("within_5", 0)
        if w5 > best_within5:
            best_within5 = w5
            best_t = t_val

    avg_mape = 0
    if overall_by_t:
        avg_mape = sum(s.get("mape", 0) for s in overall_by_t.values()) / len(overall_by_t)

    # Build hotel cards
    hotel_cards = ""
    for hid, hdata in hotels.items():
        acc_by_t = hdata.get("accuracy_by_T", {})
        if not acc_by_t:
            continue
        rows = ""
        for t_val in sorted(acc_by_t.keys()):
            s = acc_by_t[t_val]
            mape_cls = "green" if s["mape"] < 5 else ("yellow" if s["mape"] < 10 else "red")
            dir_cls = "green" if s["direction_accuracy_pct"] > 60 else ("yellow" if s["direction_accuracy_pct"] > 45 else "red")
            rows += f"""<tr>
                <td>T-{t_val}</td>
                <td>{s['n_observations']}</td>
                <td class="clr-{mape_cls}">{s['mape']:.1f}%</td>
                <td class="clr-{dir_cls}">{s['direction_accuracy_pct']:.0f}%</td>
                <td>{s['within_5pct']:.0f}%</td>
                <td>{s['within_10pct']:.0f}%</td>
                <td>{s['mean_actual_change_pct']:+.1f}%</td>
                <td>{s['price_went_down_pct']:.0f}% / {s['price_went_up_pct']:.0f}%</td>
            </tr>"""

        hotel_cards += f"""
        <div class="hotel-card">
            <h3>{hdata.get('hotel_name', f'Hotel {hid}')}</h3>
            <table class="acc-table">
                <thead><tr>
                    <th>Lead Time</th><th>Samples</th><th>MAPE</th>
                    <th>Direction</th><th>Within 5%</th><th>Within 10%</th>
                    <th>Avg Change</th><th>Down/Up</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    # YoY comparison table
    yoy_rows = ""
    for year in sorted(yoy.keys()):
        s = yoy[year]
        yoy_rows += f"""<tr>
            <td>{year}</td><td>{s['n']}</td>
            <td>{s['mape']:.1f}%</td><td>{s['within_5']:.0f}%</td>
            <td>{s['pct_down']:.0f}%</td><td>{s['mean_change']:+.1f}%</td>
        </tr>"""

    # Scatter data for Chart.js (use default=str to handle any non-serializable types)
    scatter_data = json.dumps(overall.get("scatter", []), default=str)

    # T-bucket bar chart data
    t_bar_labels = []
    t_bar_mape = []
    t_bar_within5 = []
    for t_val in sorted(overall_by_t.keys()):
        s = overall_by_t[t_val]
        t_bar_labels.append(f"T-{t_val}")
        t_bar_mape.append(s.get("mape", 0))
        t_bar_within5.append(s.get("within_5", 0))

    sources_text = ", ".join(f"{k}: {v:,}" for k, v in sources.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prediction Accuracy Tracker — Medici</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--surface2:#232733;--border:#2d3140;
--text:#e4e7ec;--text-dim:#8b90a0;--accent:#6366f1;--accent2:#818cf8;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;--blue:#3b82f6;--cyan:#06b6d4;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',-apple-system,sans-serif;}}
.container{{max-width:1400px;margin:0 auto;padding:20px 24px;}}
h1{{font-size:1.8em;background:linear-gradient(135deg,#c7d2fe,#818cf8);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}}
.subtitle{{color:var(--text-dim);margin-bottom:24px;}}
.kpi-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:16px 24px;flex:1;min-width:180px;text-align:center;}}
.kpi .val{{font-size:2em;font-weight:700;color:var(--accent2);}}
.kpi .label{{color:var(--text-dim);font-size:0.85em;margin-top:4px;}}
.hotel-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:20px;margin-bottom:20px;}}
.hotel-card h3{{color:var(--accent2);margin-bottom:12px;}}
.acc-table{{width:100%;border-collapse:collapse;font-size:0.9em;}}
.acc-table th{{background:var(--surface2);color:var(--text-dim);padding:8px 12px;
text-align:left;border-bottom:1px solid var(--border);}}
.acc-table td{{padding:8px 12px;border-bottom:1px solid var(--border);}}
.clr-green{{color:var(--green);font-weight:600;}}
.clr-yellow{{color:var(--yellow);font-weight:600;}}
.clr-red{{color:var(--red);font-weight:600;}}
.charts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0;}}
.chart-box{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;}}
.chart-box h4{{color:var(--text-dim);margin-bottom:12px;font-size:0.95em;}}
.yoy-section{{margin:24px 0;}}
.yoy-section h3{{color:var(--accent2);margin-bottom:12px;}}
nav{{background:var(--surface);padding:10px 24px;border-bottom:1px solid var(--border);
display:flex;gap:16px;align-items:center;font-size:0.9em;flex-wrap:wrap;}}
nav a{{color:var(--text-dim);text-decoration:none;}}
nav a:hover{{color:var(--accent2);}}
nav .active{{color:var(--accent2);font-weight:600;}}
footer{{text-align:center;color:var(--text-dim);font-size:0.8em;padding:24px 0;margin-top:40px;
border-top:1px solid var(--border);}}
@media(max-width:768px){{.charts-grid{{grid-template-columns:1fr;}}
.kpi-row{{flex-direction:column;}}}}
</style>
</head>
<body>
<nav>
    <a href="/api/v1/salesoffice/home">Home</a>
    <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
    <a href="/api/v1/salesoffice/charts">Charts</a>
    <a href="/api/v1/salesoffice/accuracy" class="active">Accuracy</a>
    <a href="/api/v1/salesoffice/providers">Providers</a>
    <a href="/api/v1/salesoffice/alerts">Alerts</a>
    <a href="/api/v1/salesoffice/freshness">Freshness</a>
</nav>
<div class="container">
<h1>Prediction Accuracy Tracker</h1>
<p class="subtitle">Backtest results: how accurately historical prices predicted the settlement (check-in) price</p>

<div class="kpi-row">
    <div class="kpi"><div class="val">{total_contracts:,}</div><div class="label">Contracts Tested</div></div>
    <div class="kpi"><div class="val">{total_obs:,}</div><div class="label">Price Observations</div></div>
    <div class="kpi"><div class="val">{avg_mape:.1f}%</div><div class="label">Avg MAPE</div></div>
    <div class="kpi"><div class="val">{best_within5:.0f}%</div><div class="label">Best Within-5% (T-{best_t or '?'})</div></div>
</div>

<div class="charts-grid">
    <div class="chart-box">
        <h4>MAPE by Lead Time (lower is better)</h4>
        <canvas id="chartMAPE"></canvas>
    </div>
    <div class="chart-box">
        <h4>Predicted vs Actual (scatter)</h4>
        <canvas id="chartScatter"></canvas>
    </div>
</div>

{hotel_cards}

<div class="yoy-section">
    <h3>Year-over-Year Accuracy</h3>
    <table class="acc-table">
        <thead><tr><th>Year</th><th>Samples</th><th>MAPE</th><th>Within 5%</th><th>% Went Down</th><th>Avg Change</th></tr></thead>
        <tbody>{yoy_rows}</tbody>
    </table>
</div>

<footer>
    Prediction Accuracy Tracker | Sources: {sources_text} | Generated {now}<br>
    <a href="/api/v1/salesoffice/home" style="color:var(--accent2)">Back to Home</a>
</footer>
</div>

<script>
const scatterRaw = {scatter_data};
const tLabels = {json.dumps(t_bar_labels)};
const tMAPE = {json.dumps(t_bar_mape)};
const tWithin5 = {json.dumps(t_bar_within5)};

// MAPE bar chart
new Chart(document.getElementById('chartMAPE'), {{
    type: 'bar',
    data: {{
        labels: tLabels,
        datasets: [
            {{label: 'MAPE %', data: tMAPE, backgroundColor: '#6366f1', borderRadius: 4}},
            {{label: 'Within 5%', data: tWithin5, backgroundColor: '#22c55e', borderRadius: 4}}
        ]
    }},
    options: {{
        responsive: true,
        plugins: {{legend: {{labels: {{color: '#8b90a0'}}}}}},
        scales: {{
            x: {{ticks: {{color: '#8b90a0'}}, grid: {{color: '#2d3140'}}}},
            y: {{ticks: {{color: '#8b90a0'}}, grid: {{color: '#2d3140'}}}}
        }}
    }}
}});

// Scatter chart
const colors = {{'7':'#ef4444','14':'#eab308','30':'#22c55e','60':'#3b82f6','90':'#818cf8'}};
const datasets = {{}};
scatterRaw.forEach(p => {{
    const key = 'T-' + p.T;
    if (!datasets[key]) datasets[key] = {{label: key, data: [], backgroundColor: colors[p.T] || '#8b90a0', pointRadius: 3}};
    datasets[key].data.push({{x: p.predicted, y: p.actual}});
}});
const scatterDS = Object.values(datasets);
// Perfect prediction line
const allVals = scatterRaw.map(p => p.predicted).concat(scatterRaw.map(p => p.actual));
const minV = Math.min(...allVals) * 0.9;
const maxV = Math.max(...allVals) * 1.1;
scatterDS.push({{
    label: 'Perfect',
    data: [{{x: minV, y: minV}}, {{x: maxV, y: maxV}}],
    type: 'line', borderColor: '#4b5563', borderDash: [5,5], pointRadius: 0, borderWidth: 1
}});

new Chart(document.getElementById('chartScatter'), {{
    type: 'scatter',
    data: {{datasets: scatterDS}},
    options: {{
        responsive: true,
        plugins: {{legend: {{labels: {{color: '#8b90a0'}}}}}},
        scales: {{
            x: {{title: {{display: true, text: 'Price at T (Predicted)', color: '#8b90a0'}},
                 ticks: {{color: '#8b90a0'}}, grid: {{color: '#2d3140'}}}},
            y: {{title: {{display: true, text: 'Settlement Price (Actual)', color: '#8b90a0'}},
                 ticks: {{color: '#8b90a0'}}, grid: {{color: '#2d3140'}}}}
        }}
    }}
}});
</script>
</body>
</html>"""


def _error_page(now: str, error: str) -> str:
    """Return error page."""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Accuracy Tracker — Error</title>
<style>body{{background:#0f1117;color:#e4e7ec;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;min-height:100vh;}}
.box{{text-align:center;padding:40px;}}</style></head>
<body><div class="box"><h1>Prediction Accuracy Tracker</h1>
<p style="color:#ef4444;margin-top:16px;">{error}</p>
<p style="color:#8b90a0;margin-top:8px;">Generated {now}</p>
<a href="/api/v1/salesoffice/home" style="color:#818cf8;">Back to Home</a>
</div></body></html>"""
