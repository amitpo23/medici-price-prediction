"""Generate the Data Freshness Monitor HTML page.

Shows last-updated timestamp and staleness status for every data source.
"""
from __future__ import annotations

from datetime import datetime


def generate_freshness_html(data: dict) -> str:
    """Build the Data Freshness Monitor HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    sources = data.get("sources", [])
    summary = data.get("summary", {})
    overall = summary.get("overall_status", "unknown")
    n_green = summary.get("green", 0)
    n_yellow = summary.get("yellow", 0)
    n_red = summary.get("red", 0)
    n_unknown = summary.get("unknown", 0)
    total = summary.get("total", 0)

    overall_color = {"green": "var(--green)", "yellow": "var(--yellow)", "red": "var(--red)"}.get(overall, "var(--text-dim)")
    overall_label = {"green": "All Systems Healthy", "yellow": "Some Sources Stale", "red": "Critical Staleness Detected"}.get(overall, "Unknown")

    # Build source cards
    source_cards = ""
    for s in sources:
        status = s.get("status", "unknown")
        color = {"green": "var(--green)", "yellow": "var(--yellow)", "red": "var(--red)"}.get(status, "var(--text-dim)")
        dot = {"green": "#22c55e", "yellow": "#eab308", "red": "#ef4444"}.get(status, "#4b5563")
        age_str = s.get("age_display", "N/A")
        last_updated = s.get("last_updated", "Never")
        freq = s.get("frequency", "unknown")
        error = s.get("error", "")

        err_html = f'<div class="src-error">{error}</div>' if error else ""

        source_cards += f"""
        <div class="src-card" style="border-left:3px solid {color};">
            <div class="src-header">
                <span class="src-dot" style="background:{dot};"></span>
                <span class="src-name">{s['name']}</span>
                <span class="src-age" style="color:{color};">{age_str}</span>
            </div>
            <div class="src-desc">{s.get('description', '')}</div>
            <div class="src-meta">
                <span>Last: {last_updated}</span>
                <span>Freq: {freq}</span>
            </div>
            {err_html}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Freshness Monitor — Medici</title>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--surface2:#232733;--border:#2d3140;
--text:#e4e7ec;--text-dim:#8b90a0;--accent:#6366f1;--accent2:#818cf8;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',-apple-system,sans-serif;}}
.container{{max-width:1200px;margin:0 auto;padding:20px 24px;}}
h1{{font-size:1.8em;background:linear-gradient(135deg,#86efac,#22c55e);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}}
.subtitle{{color:var(--text-dim);margin-bottom:24px;}}
.overall-banner{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:20px;margin-bottom:24px;text-align:center;}}
.overall-status{{font-size:1.5em;font-weight:700;}}
.overall-detail{{color:var(--text-dim);margin-top:8px;font-size:0.95em;}}
.status-pills{{display:flex;gap:12px;justify-content:center;margin-top:12px;}}
.pill{{padding:4px 16px;border-radius:20px;font-size:0.85em;font-weight:600;}}
.pill-green{{background:rgba(34,197,94,0.15);color:var(--green);}}
.pill-yellow{{background:rgba(234,179,8,0.15);color:var(--yellow);}}
.pill-red{{background:rgba(239,68,68,0.15);color:var(--red);}}
.pill-gray{{background:rgba(75,85,99,0.15);color:var(--text-dim);}}
.sources-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;}}
.src-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px;}}
.src-header{{display:flex;align-items:center;gap:8px;margin-bottom:6px;}}
.src-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
.src-name{{font-weight:600;flex:1;}}
.src-age{{font-size:0.9em;font-weight:600;}}
.src-desc{{color:var(--text-dim);font-size:0.85em;margin-bottom:6px;}}
.src-meta{{display:flex;gap:16px;font-size:0.8em;color:var(--text-dim);}}
.src-error{{color:var(--red);font-size:0.8em;margin-top:4px;}}
nav{{background:var(--surface);padding:10px 24px;border-bottom:1px solid var(--border);
display:flex;gap:16px;align-items:center;font-size:0.9em;flex-wrap:wrap;}}
nav a{{color:var(--text-dim);text-decoration:none;}}
nav a:hover{{color:var(--accent2);}}
nav .active{{color:var(--accent2);font-weight:600;}}
footer{{text-align:center;color:var(--text-dim);font-size:0.8em;padding:24px 0;margin-top:40px;
border-top:1px solid var(--border);}}
.refresh-btn{{display:inline-block;margin-top:16px;padding:8px 24px;background:var(--accent);
color:white;border-radius:8px;text-decoration:none;font-size:0.9em;}}
.refresh-btn:hover{{background:var(--accent2);}}
</style>
</head>
<body>
<nav>
    <a href="/api/v1/salesoffice/home">Home</a>
    <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
    <a href="/api/v1/salesoffice/charts">Charts</a>
    <a href="/api/v1/salesoffice/accuracy">Accuracy</a>
    <a href="/api/v1/salesoffice/providers">Providers</a>
    <a href="/api/v1/salesoffice/alerts">Alerts</a>
    <a href="/api/v1/salesoffice/freshness" class="active">Freshness</a>
</nav>
<div class="container">
<h1>Data Freshness Monitor</h1>
<p class="subtitle">Real-time status of all {total} data sources powering the prediction engine</p>

<div class="overall-banner">
    <div class="overall-status" style="color:{overall_color};">{overall_label}</div>
    <div class="overall-detail">Checked at {data.get('checked_at', now)}</div>
    <div class="status-pills">
        <span class="pill pill-green">{n_green} Healthy</span>
        <span class="pill pill-yellow">{n_yellow} Stale</span>
        <span class="pill pill-red">{n_red} Critical</span>
        <span class="pill pill-gray">{n_unknown} Unknown</span>
    </div>
    <a href="/api/v1/salesoffice/freshness" class="refresh-btn">Refresh</a>
</div>

<div class="sources-grid">
    {source_cards}
</div>

<footer>
    Data Freshness Monitor | {total} sources checked | Generated {now}<br>
    <a href="/api/v1/salesoffice/home" style="color:var(--accent2)">Back to Home</a>
</footer>
</div>
</body>
</html>"""
