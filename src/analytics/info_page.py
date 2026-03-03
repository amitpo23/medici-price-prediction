"""Generate the system information & documentation page.

Provides a comprehensive, user-friendly HTML page explaining:
- How the prediction engine works
- What each data source provides
- How to read all numbers and metrics
- Glossary of terms
- API reference with live links
"""
from __future__ import annotations

from datetime import datetime


def generate_info_html(data_sources: list[dict], db_stats: dict | None = None) -> str:
    """Generate the full info/documentation HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    active_sources = [s for s in data_sources if s["status"] == "active"]
    planned_sources = [s for s in data_sources if s["status"] == "planned"]

    total_rows = db_stats.get("total_rows", 0) if db_stats else 0
    total_tables = db_stats.get("total_tables", 0) if db_stats else 0
    total_size_mb = db_stats.get("total_size_mb", 0) if db_stats else 0

    # Build data sources HTML
    active_html = ""
    for s in active_sources:
        active_html += f"""
        <div class="source-card active">
            <div class="source-header">
                <span class="source-name">{s['name']}</span>
                <span class="badge badge-active">Active</span>
            </div>
            <div class="source-category">{s['category']}</div>
            <div class="source-metrics">{s['metrics']}</div>
            <div class="source-meta">
                <span>Access: {s['access']}</span>
                <span>Update: {s['update_freq']}</span>
                <span>Cost: {s['cost']}</span>
            </div>
        </div>"""

    planned_html = ""
    for s in planned_sources:
        planned_html += f"""
        <div class="source-card planned">
            <div class="source-header">
                <span class="source-name">{s['name']}</span>
                <span class="badge badge-planned">Planned</span>
            </div>
            <div class="source-category">{s['category']}</div>
            <div class="source-metrics">{s['metrics']}</div>
            <div class="source-meta">
                <span>Access: {s['access']}</span>
                <span>Cost: {s['cost']}</span>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medici Price Prediction — System Information</title>
<style>
:root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #232733;
    --border: #2d3140;
    --text: #e4e7ec;
    --text-dim: #8b90a0;
    --accent: #6366f1;
    --accent2: #818cf8;
    --green: #22c55e;
    --red: #ef4444;
    --yellow: #eab308;
    --blue: #3b82f6;
    --cyan: #06b6d4;
    --orange: #f97316;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px 24px; }}
.header {{
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
    padding: 40px 0;
    border-bottom: 1px solid var(--border);
}}
.header h1 {{
    font-size: 2.2em;
    font-weight: 700;
    background: linear-gradient(135deg, #c7d2fe, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.header p {{ color: var(--text-dim); font-size: 1.1em; margin-top: 8px; }}
.nav-bar {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 0;
    position: sticky;
    top: 0;
    z-index: 100;
}}
.nav-links {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.nav-links a {{
    color: var(--text-dim);
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.85em;
    transition: all 0.2s;
}}
.nav-links a:hover {{ color: var(--text); background: var(--surface2); }}
.nav-links a.active {{ color: var(--accent2); background: rgba(99,102,241,0.15); }}

section {{ padding: 48px 0; border-bottom: 1px solid var(--border); }}
section:last-child {{ border-bottom: none; }}
h2 {{
    font-size: 1.6em;
    font-weight: 700;
    margin-bottom: 24px;
    color: var(--accent2);
}}
h3 {{
    font-size: 1.2em;
    font-weight: 600;
    margin: 24px 0 12px;
    color: var(--text);
}}
p {{ margin-bottom: 12px; color: var(--text-dim); }}
p strong {{ color: var(--text); }}

.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 24px 0;
}}
.kpi {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}}
.kpi-value {{
    font-size: 2em;
    font-weight: 700;
    color: var(--accent2);
}}
.kpi-label {{
    font-size: 0.85em;
    color: var(--text-dim);
    margin-top: 4px;
}}

.explainer {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
}}
.explainer-title {{
    font-weight: 600;
    font-size: 1.05em;
    color: var(--text);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.explainer p {{ margin-bottom: 8px; }}
.explainer ul {{ padding-left: 20px; margin: 8px 0; }}
.explainer li {{ color: var(--text-dim); margin: 4px 0; }}
.explainer li strong {{ color: var(--text); }}

.formula {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.9em;
    color: var(--cyan);
    margin: 12px 0;
    overflow-x: auto;
}}

.source-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
    transition: border-color 0.2s;
}}
.source-card:hover {{ border-color: var(--accent); }}
.source-card.active {{ border-left: 3px solid var(--green); }}
.source-card.planned {{ border-left: 3px solid var(--yellow); }}
.source-header {{ display: flex; justify-content: space-between; align-items: center; }}
.source-name {{ font-weight: 600; font-size: 1.05em; }}
.source-category {{ color: var(--accent2); font-size: 0.85em; margin: 4px 0; }}
.source-metrics {{ color: var(--text-dim); font-size: 0.9em; margin: 8px 0; }}
.source-meta {{
    display: flex;
    gap: 16px;
    font-size: 0.8em;
    color: var(--text-dim);
    margin-top: 8px;
    flex-wrap: wrap;
}}

.badge {{
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75em;
    font-weight: 600;
    text-transform: uppercase;
}}
.badge-active {{ background: rgba(34,197,94,0.15); color: var(--green); }}
.badge-planned {{ background: rgba(234,179,8,0.15); color: var(--yellow); }}

.api-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 0.9em;
}}
.api-table th {{
    background: var(--surface2);
    color: var(--text);
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid var(--border);
}}
.api-table td {{
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
}}
.api-table tr:hover td {{ background: rgba(99,102,241,0.05); }}
.api-table a {{
    color: var(--cyan);
    text-decoration: none;
}}
.api-table a:hover {{ text-decoration: underline; }}
code {{
    background: var(--surface2);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85em;
    color: var(--cyan);
}}

.glossary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 16px;
    margin: 16px 0;
}}
.glossary-item {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 20px;
}}
.glossary-term {{
    font-weight: 600;
    color: var(--accent2);
    font-size: 1em;
    margin-bottom: 4px;
}}
.glossary-def {{ color: var(--text-dim); font-size: 0.9em; }}

.flow-step {{
    display: flex;
    gap: 16px;
    margin: 16px 0;
    align-items: flex-start;
}}
.flow-number {{
    background: var(--accent);
    color: white;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    flex-shrink: 0;
}}
.flow-content {{ flex: 1; }}
.flow-content h4 {{
    font-weight: 600;
    color: var(--text);
    margin-bottom: 4px;
}}
.flow-content p {{ margin-bottom: 0; }}

.footer {{
    text-align: center;
    padding: 32px 0;
    color: var(--text-dim);
    font-size: 0.85em;
}}
</style>
</head>
<body>

<div class="header">
<div class="container">
    <h1>Medici Price Prediction Engine</h1>
    <p>Algo-trading style hotel price forecasting system — System Information & Documentation</p>
</div>
</div>

<div class="nav-bar">
<div class="container">
    <div class="nav-links">
        <a href="#overview" class="active">Overview</a>
        <a href="#how-it-works">How It Works</a>
        <a href="#prediction">Prediction Engine</a>
        <a href="#signals">Trading Signals</a>
        <a href="#data-sources">Data Sources</a>
        <a href="#glossary">Glossary</a>
        <a href="#api">API Reference</a>
        <a href="/api/v1/salesoffice/charts">Charts</a>
        <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
    </div>
</div>
</div>

<div class="container">

<!-- ── Overview ──────────────────────────────────────────── -->
<section id="overview">
<h2>System Overview</h2>

<div class="kpi-grid">
    <div class="kpi">
        <div class="kpi-value">{total_rows:,}</div>
        <div class="kpi-label">Total Data Points</div>
    </div>
    <div class="kpi">
        <div class="kpi-value">{total_tables}</div>
        <div class="kpi-label">Database Tables</div>
    </div>
    <div class="kpi">
        <div class="kpi-value">{len(active_sources)}</div>
        <div class="kpi-label">Active Data Sources</div>
    </div>
    <div class="kpi">
        <div class="kpi-value">{len(data_sources)}</div>
        <div class="kpi-label">Total Sources (Active + Planned)</div>
    </div>
    <div class="kpi">
        <div class="kpi-value">{total_size_mb:,} MB</div>
        <div class="kpi-label">Database Size</div>
    </div>
    <div class="kpi">
        <div class="kpi-value">4</div>
        <div class="kpi-label">Active Hotels Monitored</div>
    </div>
</div>

<div class="explainer">
    <div class="explainer-title">What is Medici Price Prediction?</div>
    <p>This system monitors hotel room prices in <strong>real-time</strong> and predicts future price movements using an <strong>algo-trading approach</strong>. It treats hotel rooms like financial futures contracts:</p>
    <ul>
        <li><strong>The "underlying asset"</strong> is the hotel room for a specific check-in date</li>
        <li><strong>T (time to expiration)</strong> is the number of days until check-in</li>
        <li><strong>The decay curve</strong> shows how prices typically change as check-in approaches</li>
        <li><strong>Momentum signals</strong> detect when a room is moving faster than expected</li>
    </ul>
    <p>Every <strong>3 hours</strong>, the system scans all active hotel rooms, records the new prices, and updates its predictions. It uses <strong>{total_rows:,} data points</strong> across {len(active_sources)} active data sources to make predictions.</p>
</div>

<div class="explainer">
    <div class="explainer-title">Hotels Currently Monitored</div>
    <ul>
        <li><strong>Breakwater South Beach</strong> (ID: 66814) — South Beach, Miami | 64,350 market data points</li>
        <li><strong>citizenM Miami Brickell</strong> (ID: 854881) — Brickell, Miami | 6,360 market data points</li>
        <li><strong>Embassy Suites Miami Airport</strong> (ID: 20702) — Airport, Miami | 34,921 market data points</li>
        <li><strong>Hilton Miami Downtown</strong> (ID: 24982) — Downtown, Miami | 2,390 market data points</li>
    </ul>
</div>
</section>

<!-- ── How It Works ──────────────────────────────────────── -->
<section id="how-it-works">
<h2>How It Works — Step by Step</h2>

<div class="flow-step">
    <div class="flow-number">1</div>
    <div class="flow-content">
        <h4>Data Collection (every 3 hours)</h4>
        <p>The system queries the SalesOffice database for all active hotel room prices. Each scan records the <strong>room price, category, board type, and check-in date</strong>. This creates a time-series of price observations for every room.</p>
    </div>
</div>

<div class="flow-step">
    <div class="flow-number">2</div>
    <div class="flow-content">
        <h4>Build the Decay Curve (from historical data)</h4>
        <p>Using <strong>all historical scan pairs</strong> (consecutive observations of the same room), the system calculates how prices typically change at each value of T (days to check-in). For example: "At T=30, prices typically drop 0.05% per day. At T=7, prices typically rise 0.3% per day." This is smoothed using <strong>Bayesian shrinkage</strong> to handle sparse data.</p>
    </div>
</div>

<div class="flow-step">
    <div class="flow-number">3</div>
    <div class="flow-content">
        <h4>Walk the Forward Curve (day-by-day prediction)</h4>
        <p>Starting from today's price, the system <strong>walks forward day by day</strong> along the decay curve, applying the expected daily percentage change at each T value. This is <strong>non-linear</strong> — the predicted path curves based on how hotel prices actually behave at different lead times.</p>
    </div>
</div>

<div class="flow-step">
    <div class="flow-number">4</div>
    <div class="flow-content">
        <h4>Apply Enrichments (events, seasonality, demand)</h4>
        <p>The curve walk is adjusted by external factors: <strong>events</strong> (like Art Basel or F1 Miami, spread over a ramp-peak-taper window), <strong>seasonality</strong> (monthly adjustment from 117K historical bookings), and <strong>flight demand</strong> (price signals from Kiwi.com flights to Miami).</p>
    </div>
</div>

<div class="flow-step">
    <div class="flow-number">5</div>
    <div class="flow-content">
        <h4>Compute Momentum (real-time signals)</h4>
        <p>From the last few 3-hour scans, the system computes <strong>velocity</strong> (how fast the price is changing over 3h, 24h, and 72h windows) and <strong>acceleration</strong> (is the change speeding up or slowing down?). It compares this to what the decay curve expects — if the room is moving faster than expected, it generates a signal.</p>
    </div>
</div>

<div class="flow-step">
    <div class="flow-number">6</div>
    <div class="flow-content">
        <h4>Detect Regime (is this room behaving normally?)</h4>
        <p>The system compares actual price behavior to the expected path and computes a <strong>z-score</strong> (how many standard deviations away from expected). This classifies each room into a regime: <strong>NORMAL</strong>, <strong>TRENDING UP/DOWN</strong>, <strong>VOLATILE</strong>, or <strong>STALE</strong>.</p>
    </div>
</div>

<div class="flow-step">
    <div class="flow-number">7</div>
    <div class="flow-content">
        <h4>Generate Report & Confidence Intervals</h4>
        <p>The final output includes the <strong>predicted price for each day</strong> until check-in, with <strong>80% and 95% confidence bands</strong>. These bands are computed from the historical volatility at each T value — wider bands mean more uncertainty.</p>
    </div>
</div>
</section>

<!-- ── Prediction Engine ─────────────────────────────────── -->
<section id="prediction">
<h2>Understanding the Predictions</h2>

<div class="explainer">
    <div class="explainer-title">Decay Curve — "How prices typically move"</div>
    <p>The decay curve is the <strong>heart of the prediction engine</strong>. It shows the expected daily percentage price change at each T (days to check-in).</p>
    <p><strong>How to read it:</strong></p>
    <ul>
        <li><strong>Negative values</strong> (e.g., -0.05% at T=60) mean prices typically <em>decrease</em> at that lead time</li>
        <li><strong>Positive values</strong> (e.g., +0.3% at T=5) mean prices typically <em>increase</em> as check-in nears</li>
        <li><strong>Volatility</strong> shows how much prices vary — high volatility = less predictable</li>
        <li><strong>Density</strong> shows how much data backs this estimate — "dense" = many observations, "sparse" = few, "extrapolated" = estimated</li>
    </ul>
    <div class="formula">
    Smoothed daily change = (N * empirical_mean + K * global_mean) / (N + K)
    where K=5 (Bayesian prior strength), N = number of observations at that T
    </div>
    <p>This means: with few observations, the estimate is pulled toward the global average. With many observations, it trusts the local data more.</p>
</div>

<div class="explainer">
    <div class="explainer-title">Forward Curve — "Where the price is heading"</div>
    <p>The forward curve walks day-by-day from today's price to check-in, applying the decay curve at each step:</p>
    <div class="formula">
    Day 1: price_1 = current_price * (1 + daily_change_at_T / 100)
    Day 2: price_2 = price_1 * (1 + daily_change_at_T-1 / 100)
    ... and so on until check-in
    </div>
    <p><strong>How to read the forward curve chart:</strong></p>
    <ul>
        <li><strong>The line</strong> is the predicted price path</li>
        <li><strong>The shaded band</strong> is the confidence interval (80% inner, 95% outer)</li>
        <li><strong>Wider bands</strong> = more uncertainty (further into the future or higher volatility)</li>
        <li><strong>If current price is above the predicted line</strong>, the room is <em>overpriced</em> vs. history</li>
        <li><strong>If current price is below the predicted line</strong>, the room is <em>underpriced</em> vs. history</li>
    </ul>
</div>

<div class="explainer">
    <div class="explainer-title">Confidence Intervals — "How sure are we?"</div>
    <p>Every prediction comes with <strong>80% and 95% confidence bands</strong>:</p>
    <ul>
        <li><strong>80% band</strong>: We expect the actual price to fall within this range 80% of the time</li>
        <li><strong>95% band</strong>: We expect the actual price to fall within this range 95% of the time</li>
        <li><strong>Confidence quality</strong>: rated "high" (many observations, low volatility), "medium", or "low" (sparse data, high volatility)</li>
    </ul>
    <div class="formula">
    Upper bound = predicted_price * (1 + z * cumulative_volatility / 100)
    Lower bound = predicted_price * (1 - z * cumulative_volatility / 100)
    where z=1.28 for 80%, z=1.96 for 95%
    </div>
</div>

<div class="explainer">
    <div class="explainer-title">Category & Board Offsets</div>
    <p>Different room types and meal plans have different price dynamics:</p>
    <ul>
        <li><strong>Category offset</strong>: How much faster/slower this room type changes vs. average (e.g., suites may change +0.02% faster per day than standard rooms)</li>
        <li><strong>Board offset</strong>: Meal plan impact (RO = room only, BB = bed & breakfast, HB = half board, FB = full board, AI = all inclusive)</li>
    </ul>
    <p>These offsets are <strong>added to the base decay curve</strong> to get the room-specific expected change.</p>
</div>
</section>

<!-- ── Trading Signals ───────────────────────────────────── -->
<section id="signals">
<h2>Understanding Trading Signals</h2>

<div class="explainer">
    <div class="explainer-title">Momentum — "How fast is the price moving?"</div>
    <p>Momentum tracks the <strong>speed of price changes</strong> from recent 3-hour scans:</p>
    <ul>
        <li><strong>Velocity 3h</strong>: Price change in the last 3-hour scan window (raw speed)</li>
        <li><strong>Velocity 24h</strong>: Price change rate over 24 hours, annualized to daily (smoothed speed)</li>
        <li><strong>Velocity 72h</strong>: Price change rate over 72 hours (trend speed)</li>
        <li><strong>Acceleration</strong>: Is the velocity <em>increasing or decreasing</em>? Positive = prices accelerating upward</li>
        <li><strong>Momentum vs. Expected</strong>: How does actual velocity compare to what the decay curve predicts?</li>
    </ul>
    <p><strong>Signal types:</strong></p>
    <ul>
        <li><strong>ACCELERATING_UP</strong> — Price rising much faster than expected (momentum &gt; 2x volatility)</li>
        <li><strong>ACCELERATING_DOWN</strong> — Price falling much faster than expected</li>
        <li><strong>ACCELERATING</strong> — Acceleration is high (price changes speeding up)</li>
        <li><strong>DECELERATING</strong> — Acceleration is negative (price changes slowing down)</li>
        <li><strong>NORMAL</strong> — Price moving as expected</li>
        <li><strong>INSUFFICIENT_DATA</strong> — Not enough scans to compute</li>
    </ul>
</div>

<div class="explainer">
    <div class="explainer-title">Regime Detection — "Is this room behaving normally?"</div>
    <p>Regime detection classifies each room's behavior using a <strong>z-score</strong> (standard deviations from expected):</p>
    <ul>
        <li><strong>NORMAL</strong> (z-score between -2 and +2) — Room is following the expected path</li>
        <li><strong>TRENDING_UP</strong> (z-score &gt; +2) — Room is significantly above expected price. Consider selling at this price level.</li>
        <li><strong>TRENDING_DOWN</strong> (z-score &lt; -2) — Room is significantly below expected price. Potential buying opportunity.</li>
        <li><strong>VOLATILE</strong> (recent volatility &gt; 2x expected) — Room is swinging wildly. Prediction reliability is reduced.</li>
        <li><strong>STALE</strong> (no price changes in 16+ scans) — Price hasn't moved. May indicate data issue or no availability.</li>
    </ul>
    <p><strong>Alert levels:</strong></p>
    <ul>
        <li><strong>None</strong> — Everything normal</li>
        <li><strong>Watch</strong> (|z-score| &gt; 1.5) — Worth monitoring</li>
        <li><strong>Warning</strong> (|z-score| &gt; 2.5) — Significant divergence, action may be needed</li>
    </ul>
</div>

<div class="explainer">
    <div class="explainer-title">Market Data — "Where do we stand vs. the market?"</div>
    <p>With <strong>8.5 million search results</strong>, the system benchmarks your hotel prices against the broader market:</p>
    <ul>
        <li><strong>Average Market Price</strong>: What competitors in the same city are charging</li>
        <li><strong>Price Percentile</strong>: Where your price sits vs. all room options (e.g., 30th percentile = cheaper than 70% of options)</li>
        <li><strong>Net vs. Gross Margin</strong>: From 8.3M search results — the difference between what you charge and what you pay (your profit margin)</li>
        <li><strong>Provider Comparison</strong>: Prices from 129 different providers — which provider gives the best rate?</li>
        <li><strong>Price Velocity</strong>: How fast prices are changing across all hotels — is the market moving?</li>
    </ul>
</div>
</section>

<!-- ── Data Sources ───────────────────────────────────────── -->
<section id="data-sources">
<h2>Data Sources ({len(data_sources)} Total)</h2>

<h3>Active Sources ({len(active_sources)})</h3>
{active_html}

<h3>Planned Sources ({len(planned_sources)})</h3>
{planned_html}
</section>

<!-- ── Glossary ──────────────────────────────────────────── -->
<section id="glossary">
<h2>Glossary of Terms</h2>

<div class="glossary-grid">
    <div class="glossary-item">
        <div class="glossary-term">T (Time to Check-in)</div>
        <div class="glossary-def">Number of days between the scan date (now) and the check-in date. Like "time to expiration" in options trading. T=30 means check-in is 30 days away.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Decay Curve</div>
        <div class="glossary-def">The empirical curve showing expected daily price change at each T value. Built from thousands of historical scan-pair observations with Bayesian smoothing.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Forward Curve</div>
        <div class="glossary-def">The predicted price path from today to check-in. Generated by walking the decay curve day-by-day with multiplicative compounding.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Scan / Snapshot</div>
        <div class="glossary-def">A single observation of all room prices at a point in time. The system takes a scan every 3 hours, recording prices for all monitored rooms.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Momentum</div>
        <div class="glossary-def">The velocity (speed) and acceleration of price changes from recent scans. Computed over 3h, 24h, and 72h windows and compared to expected movement.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Regime</div>
        <div class="glossary-def">The behavioral classification of a room: NORMAL, TRENDING_UP, TRENDING_DOWN, VOLATILE, or STALE. Based on z-score divergence from expected price path.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Z-Score</div>
        <div class="glossary-def">How many standard deviations the actual price is from the expected price. Z=0 is exactly on target. Z=+2 means the price is 2 standard deviations above expected (unusually high).</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Bayesian Shrinkage</div>
        <div class="glossary-def">A statistical technique that blends sparse local data with a global average. Prevents wild estimates when we have few observations. K=5 means 5 "virtual" observations pull toward the mean.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Volatility</div>
        <div class="glossary-def">How much prices vary at a given T value. High volatility = prices swing a lot = wider confidence bands = less certainty in predictions. Minimum floor: 0.5% daily.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Confidence Band (80% / 95%)</div>
        <div class="glossary-def">The range where we expect the actual future price to fall. 80% band: 4 out of 5 times. 95% band: 19 out of 20 times. Wider = less certain.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Board Type</div>
        <div class="glossary-def">Meal plan included with the room. RO = Room Only, BB = Bed & Breakfast, HB = Half Board (dinner), FB = Full Board (all meals), AI = All Inclusive.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Room Category</div>
        <div class="glossary-def">The type of room: Standard, Superior, Deluxe, Suite. Each category has its own price dynamics and offset from the base decay curve.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Enrichment</div>
        <div class="glossary-def">External data layered onto the base prediction: events (Art Basel, F1), seasonality (monthly pattern), and flight demand (Kiwi.com). Each adds/subtracts a daily % adjustment.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Gross vs. Net Price</div>
        <div class="glossary-def">Gross = what the customer pays. Net = what you pay the supplier. The difference is your margin. Tracked from 8.3M search results across 129 providers.</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">SalesOffice</div>
        <div class="glossary-def">The scanning system that searches hotel availability across multiple providers every 3 hours. It creates Orders (what to scan) and Details (what it found).</div>
    </div>
    <div class="glossary-item">
        <div class="glossary-term">Price Velocity</div>
        <div class="glossary-def">How fast prices are changing per unit time. Computed from the RoomPriceUpdateLog (82K events). High velocity = market is moving fast.</div>
    </div>
</div>
</section>

<!-- ── API Reference ─────────────────────────────────────── -->
<section id="api">
<h2>API Reference</h2>

<p>All endpoints are available at <code>https://medici-prediction-api.azurewebsites.net</code>. All return JSON unless noted.</p>

<h3>Core Analytics</h3>
<table class="api-table">
<tr><th>Endpoint</th><th>Description</th><th>Returns</th></tr>
<tr>
    <td><a href="/api/v1/salesoffice/dashboard">/dashboard</a></td>
    <td>Interactive HTML dashboard with charts and predictions</td>
    <td>HTML page with Plotly charts</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/data">/data</a></td>
    <td>Raw analysis JSON — all predictions, statistics, model info</td>
    <td>Full analysis object</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/status">/status</a></td>
    <td>System health: snapshots, rooms, hotels, scheduler status</td>
    <td>Status summary</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/simple">/simple</a></td>
    <td>Simplified human-readable analysis</td>
    <td>Simplified JSON</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/decay-curve">/decay-curve</a></td>
    <td>Empirical term structure — expected daily change at each T</td>
    <td>Curve points + category offsets</td>
</tr>
<tr>
    <td>/forward-curve/&lt;detail_id&gt;</td>
    <td>Full forward curve for a specific room with momentum & regime</td>
    <td>Predicted price path + signals</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/backtest">/backtest</a></td>
    <td>Backtest prediction accuracy against historical data</td>
    <td>Accuracy metrics</td>
</tr>
</table>

<h3>Enrichment Data</h3>
<table class="api-table">
<tr><th>Endpoint</th><th>Description</th><th>Returns</th></tr>
<tr>
    <td><a href="/api/v1/salesoffice/events">/events</a></td>
    <td>Miami events calendar — Art Basel, Ultra, F1, etc.</td>
    <td>Event list with impact scores</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/flights/demand">/flights/demand</a></td>
    <td>Flight demand indicator — prices from 5 US cities to Miami</td>
    <td>Flight price data</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/knowledge">/knowledge</a></td>
    <td>Hotel knowledge base — all 4 hotels</td>
    <td>Hotel profiles + competitor analysis</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/benchmarks">/benchmarks</a></td>
    <td>Booking benchmarks from 117K historical bookings</td>
    <td>Seasonality, ADR, lead time models</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/data-sources">/data-sources</a></td>
    <td>List of all {len(data_sources)} data sources with status</td>
    <td>Source registry</td>
</tr>
</table>

<h3>Market Intelligence (28M rows)</h3>
<table class="api-table">
<tr><th>Endpoint</th><th>Description</th><th>Data Size</th></tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/db-overview">/market/db-overview</a></td>
    <td>Full database overview — all tables with row counts & sizes</td>
    <td>72 tables, {total_rows:,} rows</td>
</tr>
<tr>
    <td>/market/search-data?hotel_id=X&days_back=N</td>
    <td>Raw AI search price data for a hotel</td>
    <td>8.5M rows total</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/search-summary">/market/search-summary</a></td>
    <td>Aggregated market stats per hotel — avg price, min, max, room types</td>
    <td>6,013 hotels</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/search-results">/market/search-results</a></td>
    <td>Provider-level pricing — net vs gross, margins, 129 providers</td>
    <td>8.3M rows total</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/price-updates">/market/price-updates</a></td>
    <td>Every price change event tracked</td>
    <td>82K events</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/price-velocity">/market/price-velocity</a></td>
    <td>Price change speed per hotel — avg, stdev, update frequency</td>
    <td>Per hotel aggregation</td>
</tr>
<tr>
    <td>/market/competitors/&lt;hotel_id&gt;?radius_km=N</td>
    <td>Find competitor hotels within radius using geo coordinates</td>
    <td>745K hotels with lat/long</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/prebooks">/market/prebooks</a></td>
    <td>Pre-booking data with provider and pricing</td>
    <td>10.7K prebooks</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/cancellations">/market/cancellations</a></td>
    <td>Cancellation history with reasons</td>
    <td>4.7K cancellations</td>
</tr>
<tr>
    <td><a href="/api/v1/salesoffice/market/hotels-geo">/market/hotels-geo</a></td>
    <td>Hotel metadata with coordinates, stars, country</td>
    <td>745K hotels</td>
</tr>
</table>

<h3>Documentation</h3>
<table class="api-table">
<tr><th>Endpoint</th><th>Description</th></tr>
<tr>
    <td><a href="/api/v1/salesoffice/info">/info</a></td>
    <td>This page — system information, documentation, and glossary</td>
</tr>
</table>

</section>

</div>

<div class="footer">
    <p>Medici Price Prediction Engine | Generated {now} | {total_rows:,} data points | {len(active_sources)} active sources</p>
</div>

</body>
</html>"""
