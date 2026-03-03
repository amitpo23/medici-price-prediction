"""Generate the Options Trading HTML page.

Two main sections:
  Section A: Tomorrow — daily CALL/PUT/NONE signals per active contract (ex-ante)
  Section B: Vs Expiry — 6-month drawdown/breach analytics (ex-post)
  Section C: Signal Validation — hit-rate placeholder
"""
from __future__ import annotations

from datetime import datetime

from src.analytics.options_engine import compute_next_day_signals

HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_options_html(analysis: dict, expiry_data: dict) -> str:
    """Build the full Options Trading HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    signals = compute_next_day_signals(analysis)
    sec_a = _build_section_a(signals)
    sec_b = _build_section_b(expiry_data)
    sec_c = _build_section_c()
    return _wrap_page(now, sec_a, sec_b, sec_c)


# ── Section A: Tomorrow — CALL/PUT/NONE ──────────────────────────────

def _build_section_a(signals: list[dict]) -> str:
    if not signals:
        return """<div class="empty-state">
            <p>No active contract signals available. The analysis cache may still be warming up.</p>
        </div>"""

    # Count by type
    calls = sum(1 for s in signals if s["recommendation"] == "CALL")
    puts  = sum(1 for s in signals if s["recommendation"] == "PUT")
    nones = sum(1 for s in signals if s["recommendation"] == "NONE")

    summary_html = f"""
    <div class="summary-bar">
        <span class="pill-call">{calls} CALL</span>
        <span class="pill-put">{puts} PUT</span>
        <span class="pill-none">{nones} NONE</span>
        <span class="summary-note">signals for {len(set(s["checkin_date"] for s in signals))} check-in dates</span>
    </div>"""

    # Group by hotel
    by_hotel: dict[int, list[dict]] = {}
    for s in signals:
        hid = s["hotel_id"] or 0
        by_hotel.setdefault(hid, []).append(s)

    html = summary_html
    for hid, hotel_signals in sorted(by_hotel.items()):
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        h_calls = sum(1 for s in hotel_signals if s["recommendation"] == "CALL")
        h_puts  = sum(1 for s in hotel_signals if s["recommendation"] == "PUT")

        rows = ""
        for s in hotel_signals:
            rec   = s["recommendation"]
            conf  = s["confidence"]
            row_cls = (
                "row-call" if rec == "CALL" else
                "row-put"  if rec == "PUT"  else ""
            )
            sig_badge = (
                f'<span class="badge-call">{rec}</span>' if rec == "CALL" else
                f'<span class="badge-put">{rec}</span>'  if rec == "PUT"  else
                f'<span class="badge-none">{rec}</span>'
            )
            conf_cls = "conf-high" if conf == "High" else "conf-med" if conf == "Med" else "conf-low"

            exp_r = s["expected_return_1d"]
            exp_html = f'<span class="{"pos" if exp_r >= 0 else "neg"}">{exp_r:+.2f}%</span>'
            mom_cls = {
                "ACCELERATING_UP": "mom-up",
                "ACCELERATING_DOWN": "mom-down",
            }.get(s["momentum_signal"], "")
            regime_cls = {
                "VOLATILE": "reg-bad",
                "STALE": "reg-bad",
                "TRENDING_UP": "reg-up",
                "TRENDING_DOWN": "reg-down",
            }.get(s["regime"], "")

            rows += f"""<tr class="{row_cls}">
                <td class="date-cell">{s["checkin_date"]}</td>
                <td class="t-cell">{s["T"]}d</td>
                <td>{s["category"].title()}</td>
                <td>{s["board"].upper()}</td>
                <td class="price-cell">${s["S_t"]:,.0f}</td>
                <td>{exp_html}</td>
                <td class="sigma-cell">{s["sigma_1d"]:.3f}%</td>
                <td class="prob-cell">{s["P_up"]:.0f}%</td>
                <td class="prob-cell">{s["P_down"]:.0f}%</td>
                <td><span class="{mom_cls}">{s["momentum_signal"]}</span></td>
                <td><span class="{regime_cls}">{s["regime"]}</span></td>
                <td>{sig_badge}</td>
                <td class="{conf_cls}">{conf}</td>
            </tr>"""

        html += f"""
        <div class="hotel-section">
            <div class="hotel-header-row">
                <span class="hotel-title">{hotel_name}</span>
                <span class="pill-call sm">{h_calls} CALL</span>
                <span class="pill-put sm">{h_puts} PUT</span>
            </div>
            <div class="table-wrap">
            <table class="signals-table">
                <thead><tr>
                    <th>Check-in</th><th>T</th><th>Category</th><th>Board</th>
                    <th>Price</th><th>E[r_1d]</th><th>&sigma;</th>
                    <th>P_up</th><th>P_down</th>
                    <th>Momentum</th><th>Regime</th>
                    <th>Signal</th><th>Conf</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            </div>
        </div>"""

    return html


# ── Section B: Vs Expiry ──────────────────────────────────────────────

def _build_section_b(expiry_data: dict) -> str:
    if not expiry_data:
        return """<div class="loading-panel">
            <div class="loading-icon">⏳</div>
            <p><strong>Historical analysis is loading in the background.</strong></p>
            <p class="dim">The 6-month expiry-relative metrics are being computed from the database.
            Refresh in ~30 seconds to see results.</p>
        </div>"""

    summaries_raw = expiry_data.get("summaries", [])
    rollups = expiry_data.get("rollups", {})

    if not summaries_raw:
        return '<p class="dim">No completed contracts found in the last 6 months.</p>'

    import pandas as pd
    summaries = pd.DataFrame(summaries_raw)

    html = ""

    for hid_key, rollup in sorted(rollups.items()):
        hid = int(hid_key)
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        n = rollup["total_contracts"]

        # Insight sentence
        med = rollup.get("median_min_rel")
        p10 = rollup.get("p10_min_rel")
        med_str = f"{med:+.1f}%" if med is not None else "N/A"
        p10_str = f"{p10:+.1f}%" if p10 is not None else "N/A"
        insight = (
            f"Over 6 months, <strong>{rollup['pct_below_10']}%</strong> of contracts "
            f"dropped &gt;10% below their final check-in price at some point. "
            f"Median drawdown vs expiry: <strong>{med_str}</strong> &middot; "
            f"Worst 10th percentile: <strong>{p10_str}</strong>."
        )

        kpi_html = f"""
        <div class="kpi-strip">
            <div class="kpi-card"><div class="kpi-val">{n}</div><div class="kpi-label">contracts</div></div>
            <div class="kpi-card highlight-5"><div class="kpi-val">{rollup['pct_below_5']}%</div><div class="kpi-label">had day below −5%</div></div>
            <div class="kpi-card highlight-10"><div class="kpi-val">{rollup['pct_below_10']}%</div><div class="kpi-label">had day below −10%</div></div>
            <div class="kpi-card"><div class="kpi-val">{rollup['avg_days_below_5']:.1f}</div><div class="kpi-label">avg days below −5%</div></div>
            <div class="kpi-card"><div class="kpi-val">{rollup['total_events_10']}</div><div class="kpi-label">total events at −10%</div></div>
        </div>
        <p class="insight-text">{insight}</p>"""

        # Contract table, grouped by category
        hotel_summ = summaries[summaries["hotel_id"] == hid]
        contract_sections = ""

        for cat, cat_grp in sorted(hotel_summ.groupby("category")):
            uid = f"exp_{hid}_{cat}"
            cnt_5  = int((cat_grp["min_rel"] <= -5.0).sum())
            cnt_10 = int((cat_grp["min_rel"] <= -10.0).sum())
            badge5  = f'<span class="badge-breach5">{cnt_5} below −5%</span>' if cnt_5 else ""
            badge10 = f'<span class="badge-breach10">{cnt_10} below −10%</span>' if cnt_10 else ""

            rows = ""
            for _, row in cat_grp.sort_values("checkin_date", ascending=False).iterrows():
                min_r = row["min_rel"]
                max_r = row["max_rel"]
                min_cls = "breach-10" if min_r <= -10 else "breach-5" if min_r <= -5 else "breach-0" if min_r < 0 else ""
                fallback_flag = "⚠" if row.get("settlement_fallback") else ""
                rows += f"""<tr>
                    <td class="date-cell">{row["checkin_date"]}</td>
                    <td>{row["board"].upper()}</td>
                    <td>${row["S_exp"]:,.0f}</td>
                    <td class="{min_cls}">{min_r:+.1f}%</td>
                    <td class="{"pos" if max_r > 0 else ""}">{max_r:+.1f}%</td>
                    <td>{row["days_below_5"]}</td>
                    <td>{row["days_below_10"]}</td>
                    <td>{row["events_below_5"]}</td>
                    <td>{row["events_below_10"]}</td>
                    <td>{row["n_scans"]}</td>
                    <td class="flag-cell">{fallback_flag}</td>
                </tr>"""

            contract_sections += f"""
            <div class="comp-row">
                <div class="comp-row-header" onclick="toggle('{uid}')">
                    <span class="comp-room">{cat.title()}</span>
                    <span class="dim">{len(cat_grp)} contracts</span>
                    <span>{badge5} {badge10}</span>
                    <span class="comp-toggle" id="arrow_{uid}">&#9654;</span>
                </div>
                <div class="comp-detail" id="{uid}" style="display:none">
                    <table class="comp-table">
                        <thead><tr>
                            <th>Check-in</th><th>Board</th><th>S_exp</th>
                            <th>Min Rel</th><th>Max Rel</th>
                            <th>Days&lt;−5%</th><th>Days&lt;−10%</th>
                            <th>Ev&lt;−5%</th><th>Ev&lt;−10%</th>
                            <th>Scans</th><th></th>
                        </tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            </div>"""

        html += f"""
        <div class="hotel-section">
            <div class="hotel-header-row">
                <span class="hotel-title">{hotel_name}</span>
            </div>
            {kpi_html}
            {contract_sections}
        </div>"""

    return html


# ── Section C: Signal Validation ─────────────────────────────────────

def _build_section_c() -> str:
    return """
    <div class="comp-row">
        <div class="comp-row-header" onclick="toggle('validation_panel')">
            <span class="comp-room">Hit-Rate Tracking</span>
            <span class="dim">Coming soon</span>
            <span class="comp-toggle" id="arrow_validation_panel">&#9654;</span>
        </div>
        <div class="comp-detail" id="validation_panel" style="display:none">
            <div class="validation-stub">
                <p><strong>What this will show:</strong></p>
                <ul>
                    <li>For each CALL signal issued: did the price go up the next day? → hit_rate_call</li>
                    <li>For each PUT signal issued: did the price go down? → hit_rate_put</li>
                    <li>Accuracy breakdown by hotel, T-bucket, confidence level</li>
                </ul>
                <p class="dim">Requires daily signal history. Currently, signals are computed fresh on each request.
                Persistent signal storage will be added in a future update.</p>
            </div>
        </div>
    </div>"""


# ── Page wrapper ──────────────────────────────────────────────────────

def _wrap_page(now: str, sec_a: str, sec_b: str, sec_c: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medici — Options Trading Signals</title>
<style>
:root {{
    --bg:#0f1117; --surface:#1a1d27; --surface2:#232733;
    --border:#2d3140; --text:#e4e7ec; --text-dim:#8b90a0;
    --accent:#6366f1; --accent2:#818cf8;
    --green:#22c55e; --red:#ef4444; --yellow:#eab308; --cyan:#06b6d4;
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}}
.container{{max-width:1500px;margin:0 auto;padding:0 24px;}}
.header{{background:linear-gradient(135deg,#1e1b4b,#312e81);padding:32px 0;border-bottom:1px solid var(--border);}}
.header h1{{font-size:2em;font-weight:700;background:linear-gradient(135deg,#c7d2fe,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
.header p{{color:var(--text-dim);margin-top:6px;}}
.nav-links{{display:flex;gap:16px;padding:10px 0;}}
.nav-links a{{color:var(--text-dim);text-decoration:none;font-size:0.85em;}}
.nav-links a:hover{{color:var(--accent2);}}

/* Tabs */
.tab-bar{{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;}}
.tab-bar .container{{display:flex;}}
.tab-btn{{padding:14px 24px;background:none;border:none;border-bottom:3px solid transparent;color:var(--text-dim);font-size:0.95em;font-weight:500;cursor:pointer;transition:all 0.2s;font-family:inherit;}}
.tab-btn:hover{{color:var(--text);background:var(--surface2);}}
.tab-btn.active{{color:var(--accent2);border-bottom-color:var(--accent2);background:rgba(99,102,241,0.08);}}
.tab-content{{display:none;padding:24px 0;}}
.tab-content.active{{display:block;}}

/* Section explainer */
.explainer{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin:0 0 20px;font-size:0.9em;color:var(--text-dim);}}
.explainer strong{{color:var(--text);}}

/* Hotel section */
.hotel-section{{margin-bottom:32px;}}
.hotel-header-row{{display:flex;align-items:center;gap:12px;padding-bottom:8px;border-bottom:1px solid var(--border);margin-bottom:12px;}}
.hotel-title{{font-size:1.15em;font-weight:700;color:var(--accent2);}}

/* Summary bar */
.summary-bar{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 18px;}}
.summary-note{{color:var(--text-dim);font-size:0.85em;}}

/* Signal badges */
.pill-call{{background:rgba(34,197,94,0.15);color:var(--green);border:1px solid rgba(34,197,94,0.3);border-radius:20px;padding:4px 14px;font-size:0.85em;font-weight:700;}}
.pill-put{{background:rgba(239,68,68,0.15);color:var(--red);border:1px solid rgba(239,68,68,0.3);border-radius:20px;padding:4px 14px;font-size:0.85em;font-weight:700;}}
.pill-none{{background:rgba(139,144,160,0.15);color:var(--text-dim);border:1px solid rgba(139,144,160,0.3);border-radius:20px;padding:4px 14px;font-size:0.85em;font-weight:600;}}
.pill-call.sm,.pill-put.sm,.pill-none.sm{{padding:2px 10px;font-size:0.78em;}}
.badge-call{{background:rgba(34,197,94,0.2);color:var(--green);border-radius:4px;padding:2px 8px;font-size:0.8em;font-weight:700;}}
.badge-put{{background:rgba(239,68,68,0.2);color:var(--red);border-radius:4px;padding:2px 8px;font-size:0.8em;font-weight:700;}}
.badge-none{{background:rgba(139,144,160,0.15);color:var(--text-dim);border-radius:4px;padding:2px 8px;font-size:0.8em;}}
.badge-breach5{{background:rgba(234,179,8,0.15);color:var(--yellow);border-radius:4px;padding:2px 8px;font-size:0.78em;font-weight:600;}}
.badge-breach10{{background:rgba(239,68,68,0.15);color:var(--red);border-radius:4px;padding:2px 8px;font-size:0.78em;font-weight:600;}}

/* Signals table (Section A) */
.table-wrap{{overflow-x:auto;margin-bottom:12px;}}
.signals-table{{width:100%;border-collapse:collapse;font-size:0.82em;}}
.signals-table th{{background:var(--surface2);padding:9px 10px;text-align:center;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);border-right:1px solid var(--border);white-space:nowrap;}}
.signals-table td{{padding:7px 10px;text-align:center;border-bottom:1px solid var(--border);border-right:1px solid var(--border);color:var(--text-dim);}}
.signals-table tbody tr:hover td{{background:var(--surface2);}}
.row-call td{{background:rgba(34,197,94,0.05);}}
.row-put td{{background:rgba(239,68,68,0.05);}}
.t-cell{{font-weight:600;color:var(--accent2);}}
.date-cell,.price-cell{{font-weight:600;color:var(--text);}}
.sigma-cell{{color:var(--text-dim);font-size:0.9em;}}
.prob-cell{{font-weight:600;}}
.pos{{color:var(--green);}}
.neg{{color:var(--red);}}
.mom-up{{color:var(--green);font-weight:600;}}
.mom-down{{color:var(--red);font-weight:600;}}
.reg-bad{{color:var(--red);font-weight:600;}}
.reg-up{{color:var(--green);}}
.reg-down{{color:var(--red);}}
.conf-high{{color:var(--green);font-weight:700;}}
.conf-med{{color:var(--yellow);font-weight:600;}}
.conf-low{{color:var(--text-dim);}}

/* KPI strip (Section B) */
.kpi-strip{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:12px;}}
.kpi-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 18px;text-align:center;min-width:110px;}}
.kpi-card.highlight-5{{border-color:rgba(234,179,8,0.4);}}
.kpi-card.highlight-10{{border-color:rgba(239,68,68,0.4);}}
.kpi-val{{font-size:1.6em;font-weight:700;color:var(--text);}}
.kpi-label{{font-size:0.75em;color:var(--text-dim);margin-top:2px;}}
.insight-text{{font-size:0.9em;color:var(--text-dim);margin-bottom:16px;line-height:1.5;}}
.insight-text strong{{color:var(--text);}}

/* Breach colors */
.breach-10{{color:var(--red);font-weight:700;}}
.breach-5{{color:var(--yellow);font-weight:600;}}
.breach-0{{color:var(--text-dim);}}
.flag-cell{{color:var(--yellow);}}

/* Collapsible rows (Section B) */
.comp-row{{background:var(--surface);border:1px solid var(--border);border-radius:8px;margin:4px 0;}}
.comp-row-header{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;cursor:pointer;font-size:0.9em;gap:16px;flex-wrap:wrap;}}
.comp-row-header:hover{{background:var(--surface2);}}
.comp-room{{font-weight:600;min-width:100px;}}
.comp-toggle{{color:var(--text-dim);transition:transform 0.2s;}}
.comp-toggle.open{{transform:rotate(90deg);}}
.comp-detail{{padding:0 16px 16px;overflow-x:auto;}}
.comp-table{{width:100%;border-collapse:collapse;font-size:0.82em;}}
.comp-table th{{background:var(--surface2);padding:8px 10px;text-align:left;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);}}
.comp-table td{{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text-dim);}}

/* Misc */
.dim{{color:var(--text-dim);font-size:0.85em;}}
.empty-state{{padding:40px;text-align:center;color:var(--text-dim);}}
.loading-panel{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:32px;text-align:center;color:var(--text-dim);}}
.loading-icon{{font-size:2em;margin-bottom:12px;}}
.validation-stub{{padding:16px;color:var(--text-dim);font-size:0.9em;}}
.validation-stub ul{{margin:8px 0 8px 20px;}}
.validation-stub li{{margin:4px 0;}}
.footer{{text-align:center;padding:32px 0;color:var(--text-dim);font-size:0.85em;border-top:1px solid var(--border);margin-top:24px;}}
</style>
</head>
<body>

<div class="header">
<div class="container">
    <h1>Options Trading Signals</h1>
    <p>Room contracts as options &mdash; CALL/PUT signals + expiry-relative analytics</p>
    <div class="nav-links">
        <a href="/api/v1/salesoffice/insights">Insights</a>
        <a href="/api/v1/salesoffice/yoy">YoY Comparison</a>
        <a href="/api/v1/salesoffice/charts">Charts</a>
        <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
        <a href="/api/v1/salesoffice/info">Documentation</a>
    </div>
</div>
</div>

<div class="tab-bar">
<div class="container">
    <button class="tab-btn active" onclick="switchTab('signals',this)">Tomorrow &mdash; CALL/PUT</button>
    <button class="tab-btn" onclick="switchTab('expiry',this)">Vs Expiry (6M)</button>
    <button class="tab-btn" onclick="switchTab('validation',this)">Validation</button>
</div>
</div>

<div class="container">

<div id="tab-signals" class="tab-content active">
    <div class="explainer">
        <strong>How to read (Section A):</strong>
        CALL = price expected to rise tomorrow (P_up &ge; 60%, positive acceleration, healthy regime).
        PUT = price expected to fall. NONE = signal suppressed (STALE/VOLATILE regime, low data quality, or probability below threshold).
        E[r_1d] is the expected 1-day return from the decay curve + momentum adjustment. &sigma; is realized 1-day volatility at that T.
    </div>
    {sec_a}
</div>

<div id="tab-expiry" class="tab-content">
    <div class="explainer">
        <strong>How to read (Section B):</strong>
        Each row is a completed contract (check-in date in last 6 months).
        S_exp = settlement price (price at T&asymp;0, i.e., the actual check-in price).
        Min/Max Rel = highest discount and premium vs S_exp, measured across all scan days.
        <strong>Days below &minus;5%/&minus;10%</strong>: how many scan days had price &ge; 5%/10% cheaper than the final price.
        <strong>Events</strong>: how many times the price entered that zone (crossings, not days).
        &nbsp;<span style="color:var(--yellow)">⚠</span> = settlement fallback used (T &gt; 3 days before check-in).
    </div>
    {sec_b}
</div>

<div id="tab-validation" class="tab-content">
    <div class="explainer">
        <strong>Signal Validation:</strong>
        Tracks historical hit-rate of CALL/PUT signals against actual next-day price moves.
        Requires persistent signal storage (coming soon).
    </div>
    {sec_c}
</div>

</div>

<div class="footer">
    <p>Medici Price Prediction Engine &mdash; Generated {now}</p>
</div>

<script>
function switchTab(name, btn) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    btn.classList.add('active');
}}
function toggle(id) {{
    const el = document.getElementById(id);
    const arrow = document.getElementById('arrow_' + id);
    if (!el) return;
    if (el.style.display === 'none') {{
        el.style.display = 'block';
        if (arrow) arrow.classList.add('open');
    }} else {{
        el.style.display = 'none';
        if (arrow) arrow.classList.remove('open');
    }}
}}
</script>
</body>
</html>"""
