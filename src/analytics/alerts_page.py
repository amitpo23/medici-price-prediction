"""Generate the Price Alert System HTML page.

Shows real-time alerts when contracts breach -5%/-10% thresholds.
Uses cached chart data (Tab 3 breach stats) plus live contract data.
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


def generate_alerts_html(charts_data: dict) -> str:
    """Build the Price Alert System HTML page from cached chart data."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    tab3 = charts_data.get("tab3", {})
    contracts_index = charts_data.get("contracts_index", {})

    # Collect alerts from Tab 3 breach data
    alerts = []
    hotel_summaries = {}

    for hid_str, breach_data in tab3.items():
        hid = int(hid_str)
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        breach_rates = breach_data.get("breach_rates", {})
        by_year = breach_rates.get("by_year", {})
        by_month = breach_rates.get("by_month", {})

        # Latest year stats
        latest_year = max(by_year.keys()) if by_year else None
        if latest_year:
            stats = by_year[latest_year]
            pct_5 = stats.get("pct_5", 0)
            pct_10 = stats.get("pct_10", 0)
            n = stats.get("n", 0)

            severity = "normal"
            if pct_10 > 30:
                severity = "critical"
            elif pct_5 > 50:
                severity = "warning"
            elif pct_5 > 20:
                severity = "caution"

            hotel_summaries[hid] = {
                "hotel_name": hotel_name,
                "year": latest_year,
                "breach_5_pct": pct_5,
                "breach_10_pct": pct_10,
                "n_contracts": n,
                "severity": severity,
            }

            if pct_10 > 20:
                alerts.append({
                    "type": "critical",
                    "hotel": hotel_name,
                    "message": f"{pct_10:.0f}% of contracts breached -10% in {latest_year}",
                    "metric": pct_10,
                })
            if pct_5 > 40:
                alerts.append({
                    "type": "warning",
                    "hotel": hotel_name,
                    "message": f"{pct_5:.0f}% of contracts breached -5% in {latest_year}",
                    "metric": pct_5,
                })

        # Monthly trend — check last 3 months
        if by_month:
            sorted_months = sorted(by_month.keys(), reverse=True)[:3]
            for month in sorted_months:
                mstats = by_month[month]
                if mstats.get("pct_10", 0) > 40:
                    alerts.append({
                        "type": "critical",
                        "hotel": hotel_name,
                        "message": f"{mstats['pct_10']:.0f}% breached -10% in {month}",
                        "metric": mstats["pct_10"],
                    })

        # Threshold counts
        threshold = breach_data.get("threshold_counts", {})
        by_year_th = threshold.get("by_year", {})
        if latest_year and latest_year in by_year_th:
            th = by_year_th[latest_year]
            if th.get("events_10", 0) > 10:
                alerts.append({
                    "type": "info",
                    "hotel": hotel_name,
                    "message": f"{th['events_10']} crossing events below -10% in {latest_year}",
                    "metric": th["events_10"],
                })

    # Sort alerts by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a["type"], 99))

    # Build alert cards HTML
    alert_cards = ""
    if not alerts:
        alert_cards = '<div class="no-alerts">No active alerts — all contracts within normal range</div>'
    else:
        for a in alerts:
            icon = {"critical": "!!", "warning": "!", "info": "i"}.get(a["type"], "?")
            alert_cards += f"""
            <div class="alert-card alert-{a['type']}">
                <div class="alert-icon">{icon}</div>
                <div class="alert-body">
                    <div class="alert-hotel">{a['hotel']}</div>
                    <div class="alert-msg">{a['message']}</div>
                </div>
            </div>"""

    # Hotel summary cards
    hotel_cards = ""
    for hid, hs in hotel_summaries.items():
        sev = hs["severity"]
        color_map = {"critical": "var(--red)", "warning": "var(--yellow)", "caution": "var(--orange)", "normal": "var(--green)"}
        border_color = color_map.get(sev, "var(--border)")
        hotel_cards += f"""
        <div class="hotel-alert-card" style="border-left:4px solid {border_color};">
            <h3>{hs['hotel_name']}</h3>
            <div class="alert-stats">
                <div class="alert-stat">
                    <span class="val" style="color:var(--yellow);">{hs['breach_5_pct']:.0f}%</span>
                    <span class="lbl">Breach -5%</span>
                </div>
                <div class="alert-stat">
                    <span class="val" style="color:var(--red);">{hs['breach_10_pct']:.0f}%</span>
                    <span class="lbl">Breach -10%</span>
                </div>
                <div class="alert-stat">
                    <span class="val">{hs['n_contracts']}</span>
                    <span class="lbl">Contracts ({hs['year']})</span>
                </div>
            </div>
        </div>"""

    # Monthly trend chart data
    monthly_labels = []
    monthly_5 = {}
    monthly_10 = {}
    for hid_str, breach_data in tab3.items():
        hid = int(hid_str)
        by_month = breach_data.get("breach_rates", {}).get("by_month", {})
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        monthly_5[hotel_name] = {}
        monthly_10[hotel_name] = {}
        for month, stats in sorted(by_month.items()):
            if month not in monthly_labels:
                monthly_labels.append(month)
            monthly_5[hotel_name][month] = stats.get("pct_5", 0)
            monthly_10[hotel_name][month] = stats.get("pct_10", 0)

    monthly_labels.sort()

    chart_datasets_5 = []
    colors = ["#6366f1", "#22c55e", "#eab308", "#ef4444"]
    for i, (hotel_name, data) in enumerate(monthly_5.items()):
        values = [data.get(m, 0) for m in monthly_labels]
        chart_datasets_5.append({
            "label": hotel_name,
            "data": values,
            "borderColor": colors[i % len(colors)],
            "tension": 0.3,
            "fill": False,
        })

    n_alerts = len(alerts)
    n_critical = sum(1 for a in alerts if a["type"] == "critical")
    n_hotels = len(hotel_summaries)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Price Alerts — Medici</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--surface2:#232733;--border:#2d3140;
--text:#e4e7ec;--text-dim:#8b90a0;--accent:#6366f1;--accent2:#818cf8;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;--orange:#f97316;--blue:#3b82f6;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',-apple-system,sans-serif;}}
.container{{max-width:1400px;margin:0 auto;padding:20px 24px;}}
h1{{font-size:1.8em;background:linear-gradient(135deg,#fca5a5,#ef4444);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}}
.subtitle{{color:var(--text-dim);margin-bottom:24px;}}
.kpi-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:16px 24px;flex:1;min-width:150px;text-align:center;}}
.kpi .val{{font-size:2em;font-weight:700;}}
.kpi .label{{color:var(--text-dim);font-size:0.85em;margin-top:4px;}}
.alerts-section{{margin-bottom:32px;}}
.alerts-section h2{{color:var(--text);margin-bottom:16px;font-size:1.2em;}}
.alert-card{{display:flex;gap:12px;align-items:center;background:var(--surface);
border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:8px;}}
.alert-critical{{border-left:4px solid var(--red);}}
.alert-warning{{border-left:4px solid var(--yellow);}}
.alert-info{{border-left:4px solid var(--blue);}}
.alert-icon{{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;
justify-content:center;font-weight:700;font-size:1.1em;flex-shrink:0;}}
.alert-critical .alert-icon{{background:rgba(239,68,68,0.2);color:var(--red);}}
.alert-warning .alert-icon{{background:rgba(234,179,8,0.2);color:var(--yellow);}}
.alert-info .alert-icon{{background:rgba(99,102,241,0.2);color:var(--accent);}}
.alert-hotel{{font-weight:600;font-size:0.95em;}}
.alert-msg{{color:var(--text-dim);font-size:0.9em;}}
.no-alerts{{background:var(--surface);border:1px solid var(--green);border-radius:8px;
padding:24px;text-align:center;color:var(--green);}}
.hotels-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin:24px 0;}}
.hotel-alert-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;}}
.hotel-alert-card h3{{color:var(--accent2);margin-bottom:12px;font-size:1.05em;}}
.alert-stats{{display:flex;gap:24px;}}
.alert-stat{{text-align:center;}}
.alert-stat .val{{display:block;font-size:1.6em;font-weight:700;}}
.alert-stat .lbl{{color:var(--text-dim);font-size:0.8em;}}
.chart-box{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:16px;margin:24px 0;}}
.chart-box h3{{color:var(--text-dim);margin-bottom:12px;}}
nav{{background:var(--surface);padding:10px 24px;border-bottom:1px solid var(--border);
display:flex;gap:16px;align-items:center;font-size:0.9em;flex-wrap:wrap;}}
nav a{{color:var(--text-dim);text-decoration:none;}}
nav a:hover{{color:var(--accent2);}}
nav .active{{color:var(--accent2);font-weight:600;}}
footer{{text-align:center;color:var(--text-dim);font-size:0.8em;padding:24px 0;margin-top:40px;
border-top:1px solid var(--border);}}
</style>
</head>
<body>
<nav>
    <a href="/api/v1/salesoffice/home">Home</a>
    <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
    <a href="/api/v1/salesoffice/charts">Charts</a>
    <a href="/api/v1/salesoffice/accuracy">Accuracy</a>
    <a href="/api/v1/salesoffice/providers">Providers</a>
    <a href="/api/v1/salesoffice/alerts" class="active">Alerts</a>
    <a href="/api/v1/salesoffice/freshness">Freshness</a>
</nav>
<div class="container">
<h1>Price Alert System</h1>
<p class="subtitle">Real-time monitoring of contracts breaching -5% and -10% thresholds</p>

<div class="kpi-row">
    <div class="kpi"><div class="val" style="color:{'var(--red)' if n_critical > 0 else 'var(--green)'};">{n_alerts}</div><div class="label">Active Alerts</div></div>
    <div class="kpi"><div class="val" style="color:var(--red);">{n_critical}</div><div class="label">Critical</div></div>
    <div class="kpi"><div class="val">{n_hotels}</div><div class="label">Hotels Monitored</div></div>
</div>

<div class="alerts-section">
    <h2>Active Alerts</h2>
    {alert_cards}
</div>

<div class="hotels-grid">
    {hotel_cards}
</div>

<div class="chart-box">
    <h3>Monthly Breach Rate Trend (-5% threshold)</h3>
    <canvas id="chartTrend"></canvas>
</div>

<footer>
    Price Alert System | Thresholds: -5% (warning) / -10% (critical) | Generated {now}<br>
    <a href="/api/v1/salesoffice/home" style="color:var(--accent2)">Back to Home</a>
</footer>
</div>

<script>
const labels = {json.dumps(monthly_labels)};
const datasets = {json.dumps(chart_datasets_5)};
new Chart(document.getElementById('chartTrend'), {{
    type: 'line',
    data: {{labels, datasets}},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{labels: {{color: '#8b90a0'}}}},
            title: {{display: false}}
        }},
        scales: {{
            x: {{ticks: {{color: '#8b90a0', maxRotation: 45}}, grid: {{color: '#2d3140'}}}},
            y: {{
                ticks: {{color: '#8b90a0', callback: v => v + '%'}},
                grid: {{color: '#2d3140'}},
                title: {{display: true, text: '% contracts breaching -5%', color: '#8b90a0'}}
            }}
        }}
    }}
}});
</script>
</body>
</html>"""
