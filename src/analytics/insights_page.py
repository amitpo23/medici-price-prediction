"""Generate the Insights page — price up/down analysis with 3 tabs.

Tab 1: Insights — when prices go up / down, turning points, best windows
Tab 2: Days Below Today — all dates where predicted price < current price
Tab 3: Days Above Today — all dates where predicted price > current price

Optimized: renders summary rows per hotel, with collapsible detail tables
to keep the page under 500KB even with 1000+ rooms.
"""
from __future__ import annotations

from datetime import datetime


def generate_insights_html(analysis: dict) -> str:
    """Build the full insights HTML page from analysis predictions."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    predictions = analysis.get("predictions", {})

    if not predictions:
        return _empty_page(now)

    # Group predictions by hotel, only keep rooms that have daily data
    hotels: dict[str, list[dict]] = {}
    for detail_id, pred in predictions.items():
        hotel = pred.get("hotel_name", "Unknown")
        entry = {"detail_id": detail_id, **pred}
        hotels.setdefault(hotel, []).append(entry)

    # Sort rooms within each hotel by check-in date
    for rooms in hotels.values():
        rooms.sort(key=lambda r: (r.get("date_from", ""), r.get("category", "")))

    insights_html = _build_insights_tab(hotels)
    below_html = _build_comparison_tab(hotels, mode="below")
    above_html = _build_comparison_tab(hotels, mode="above")

    # Count totals for tab badges
    total_rooms = sum(len(r) for r in hotels.values())
    below_count = 0
    above_count = 0
    for rooms in hotels.values():
        for room in rooms:
            current = room.get("current_price", 0)
            for d in room.get("daily", []):
                p = d.get("predicted_price", 0)
                if p and current:
                    if p < current:
                        below_count += 1
                    elif p > current:
                        above_count += 1

    return _wrap_page(now, insights_html, below_html, above_html,
                      total_rooms, below_count, above_count)


# ── Tab 1: Insights ──────────────────────────────────────────────────

def _build_insights_tab(hotels: dict[str, list[dict]]) -> str:
    html = ""
    for hotel_name, rooms in hotels.items():
        # Hotel-level summary
        prices = [r.get("current_price", 0) for r in rooms if r.get("current_price")]
        changes = [r.get("expected_change_pct", 0) or 0 for r in rooms]
        avg_change = sum(changes) / len(changes) if changes else 0
        rising = sum(1 for c in changes if c > 1)
        dropping = sum(1 for c in changes if c < -1)
        stable = len(changes) - rising - dropping

        html += f"""
        <div class="hotel-section">
            <h3 class="hotel-header">{hotel_name}
                <span class="hotel-summary">{len(rooms)} rooms &middot;
                    <span class="{"premium" if avg_change > 0 else "savings"}">{avg_change:+.1f}% avg</span>
                    &middot; {rising} rising, {dropping} dropping, {stable} stable
                </span>
            </h3>"""

        # Group rooms by check-in date for compactness
        by_date: dict[str, list[dict]] = {}
        for room in rooms:
            dt = room.get("date_from", "N/A")
            by_date.setdefault(dt, []).append(room)

        for date_from, date_rooms in by_date.items():
            days = date_rooms[0].get("days_to_checkin", 0) if date_rooms else 0
            html += f'<div class="date-group"><div class="date-label">Check-in: {date_from} ({days}d away) &mdash; {len(date_rooms)} rooms</div>'

            for room in date_rooms:
                html += _insight_row(room)

            html += "</div>"

        html += "</div>"

    return html


def _insight_row(room: dict) -> str:
    """Compact single-line insight row per room."""
    detail_id = room.get("detail_id", "?")
    category = room.get("category", "N/A")
    board = room.get("board", "N/A")
    current = room.get("current_price", 0)
    predicted = room.get("predicted_checkin_price", current)
    change_pct = room.get("expected_change_pct", 0) or 0
    daily = room.get("daily", [])
    momentum = room.get("momentum", {})
    regime = room.get("regime", {})

    # Direction
    if change_pct > 1:
        trend_cls = "trend-up"
        trend_icon = "&#9650;"
        trend_text = f"+{change_pct:.1f}%"
    elif change_pct < -1:
        trend_cls = "trend-down"
        trend_icon = "&#9660;"
        trend_text = f"{change_pct:.1f}%"
    else:
        trend_cls = "trend-stable"
        trend_icon = "&#9654;"
        trend_text = f"{change_pct:+.1f}%"

    # Best/worst from daily
    best_info = ""
    if daily:
        prices = [(d.get("predicted_price", 0), d.get("date", "")) for d in daily if d.get("predicted_price")]
        if prices:
            best_p, best_d = min(prices, key=lambda x: x[0])
            worst_p, worst_d = max(prices, key=lambda x: x[0])
            if best_p < current:
                best_info = f'<span class="savings">Low: ${best_p:,.0f} ({best_d})</span>'
            if worst_p > current:
                best_info += f' <span class="premium">High: ${worst_p:,.0f} ({worst_d})</span>'

    mom_signal = momentum.get("signal", "N/A").replace("_", " ")
    regime_name = regime.get("regime", "N/A").replace("_", " ")
    alert = regime.get("alert_level", "none")
    row_cls = "alert-warning" if alert == "warning" else "alert-watch" if alert == "watch" else ""

    return f"""
    <div class="insight-row {row_cls}">
        <span class="row-room">{category} / {board}</span>
        <span class="row-price">${current:,.0f}</span>
        <span class="row-arrow">&rarr;</span>
        <span class="row-price">${predicted:,.0f}</span>
        <span class="row-trend {trend_cls}">{trend_icon} {trend_text}</span>
        <span class="row-signal">{mom_signal}</span>
        <span class="row-regime">{regime_name}</span>
        <span class="row-best">{best_info}</span>
        <span class="row-id">#{detail_id}</span>
    </div>"""


# ── Tab 2 & 3: Days Below / Above Today ──────────────────────────────

def _build_comparison_tab(hotels: dict[str, list[dict]], mode: str) -> str:
    """Build the below/above comparison tab with collapsible per-room tables."""
    html = ""
    grand_total = 0

    for hotel_name, rooms in hotels.items():
        hotel_rows = ""
        hotel_count = 0

        for room in rooms:
            current = room.get("current_price", 0)
            daily = room.get("daily", [])
            if not daily or not current:
                continue

            # Filter matching days
            matching = []
            for d in daily:
                price = d.get("predicted_price", 0)
                if not price:
                    continue
                diff = price - current
                if mode == "below" and price < current:
                    matching.append({**d, "diff": diff, "diff_pct": diff / current * 100})
                elif mode == "above" and price > current:
                    matching.append({**d, "diff": diff, "diff_pct": diff / current * 100})

            if not matching:
                continue

            hotel_count += len(matching)
            detail_id = room.get("detail_id", "?")
            category = room.get("category", "N/A")
            board = room.get("board", "N/A")
            date_from = room.get("date_from", "N/A")
            days = room.get("days_to_checkin", 0)

            if mode == "below":
                best = min(matching, key=lambda r: r["predicted_price"])
                summary_text = f'Best: ${best["predicted_price"]:,.0f} (save ${abs(best["diff"]):,.0f})'
                summary_cls = "savings"
            else:
                best = max(matching, key=lambda r: r["predicted_price"])
                summary_text = f'Peak: ${best["predicted_price"]:,.0f} (+${best["diff"]:,.0f})'
                summary_cls = "premium"

            # Build collapsed table rows
            table_rows = ""
            highlight_price = best["predicted_price"]
            for r in matching:
                is_hl = abs(r.get("predicted_price", 0) - highlight_price) < 0.01
                hl_cls = "highlight-row" if is_hl else ""
                diff_cls = "savings" if r["diff"] < 0 else "premium"
                table_rows += f"""<tr class="{hl_cls}">
                    <td>{r.get("date", "")}</td><td>{r.get("dow", "")}</td>
                    <td>{r.get("days_remaining", "")}d</td>
                    <td>${r.get("predicted_price", 0):,.0f}</td>
                    <td class="{diff_cls}">${r["diff"]:+,.0f} ({r["diff_pct"]:+.1f}%)</td>
                    <td>${r.get("lower_bound", 0):,.0f} - ${r.get("upper_bound", 0):,.0f}</td>
                </tr>"""

            uid = f"{mode}_{detail_id}"
            hotel_rows += f"""
            <div class="comp-row">
                <div class="comp-row-header" onclick="toggle('{uid}')">
                    <span class="comp-room">{category} / {board}</span>
                    <span class="comp-date">Check-in: {date_from} ({days}d)</span>
                    <span class="comp-now">${current:,.0f}</span>
                    <span class="comp-match-count">{len(matching)} days</span>
                    <span class="{summary_cls}">{summary_text}</span>
                    <span class="comp-toggle" id="arrow_{uid}">&#9654;</span>
                </div>
                <div class="comp-detail" id="{uid}" style="display:none">
                    <table class="comp-table">
                        <thead><tr>
                            <th>Date</th><th>Day</th><th>T</th>
                            <th>Predicted</th><th>vs Today</th><th>95% Range</th>
                        </tr></thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>"""

        if hotel_rows:
            grand_total += hotel_count
            label = "below" if mode == "below" else "above"
            html += f"""
            <h3 class="hotel-header">{hotel_name}
                <span class="hotel-summary">{hotel_count} day-room pairs {label} today's price</span>
            </h3>
            {hotel_rows}"""

    if not html:
        label = "below" if mode == "below" else "above"
        html = f'<div class="no-data">No predicted days {label} current prices found</div>'

    return html


# ── Page wrapper ─────────────────────────────────────────────────────

def _empty_page(now: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Insights</title></head>
<body style="background:#0f1117;color:#e4e7ec;font-family:sans-serif;padding:40px;text-align:center;">
<h1>No Predictions Available</h1>
<p>Run an analysis cycle first. The system collects prices every 3 hours.</p>
<p style="color:#8b90a0;font-size:0.85em;">Generated {now}</p>
</body></html>"""


def _wrap_page(now: str, insights_html: str, below_html: str, above_html: str,
               total_rooms: int, below_count: int, above_count: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medici Price Insights</title>
<style>
:root {{
    --bg: #0f1117; --surface: #1a1d27; --surface2: #232733;
    --border: #2d3140; --text: #e4e7ec; --text-dim: #8b90a0;
    --accent: #6366f1; --accent2: #818cf8;
    --green: #22c55e; --green-bg: rgba(34,197,94,0.1);
    --red: #ef4444; --red-bg: rgba(239,68,68,0.1);
    --yellow: #eab308; --blue: #3b82f6; --cyan: #06b6d4;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
.container {{ max-width:1300px; margin:0 auto; padding:0 24px; }}
.header {{ background:linear-gradient(135deg,#1e1b4b,#312e81); padding:32px 0; border-bottom:1px solid var(--border); }}
.header h1 {{ font-size:2em; font-weight:700; background:linear-gradient(135deg,#c7d2fe,#818cf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.header p {{ color:var(--text-dim); margin-top:6px; }}
.nav-links {{ display:flex; gap:16px; padding:10px 0; }}
.nav-links a {{ color:var(--text-dim); text-decoration:none; font-size:0.85em; }}
.nav-links a:hover {{ color:var(--accent2); }}

/* Tabs */
.tab-bar {{ background:var(--surface); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:100; }}
.tab-bar .container {{ display:flex; gap:0; }}
.tab-btn {{ padding:14px 24px; background:none; border:none; border-bottom:3px solid transparent; color:var(--text-dim); font-size:0.95em; font-weight:500; cursor:pointer; transition:all 0.2s; font-family:inherit; }}
.tab-btn:hover {{ color:var(--text); background:var(--surface2); }}
.tab-btn.active {{ color:var(--accent2); border-bottom-color:var(--accent2); background:rgba(99,102,241,0.08); }}
.tab-badge {{ background:var(--surface2); padding:1px 8px; border-radius:10px; font-size:0.8em; margin-left:6px; }}
.tab-content {{ display:none; padding:24px 0; }}
.tab-content.active {{ display:block; }}

/* Hotel headers */
.hotel-header {{ font-size:1.2em; font-weight:700; color:var(--accent2); margin:24px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
.hotel-header:first-child {{ margin-top:0; }}
.hotel-summary {{ font-size:0.7em; font-weight:400; color:var(--text-dim); margin-left:12px; }}

/* Insight rows (Tab 1) — compact grid rows */
.date-group {{ margin:8px 0 16px; }}
.date-label {{ font-size:0.85em; color:var(--text-dim); padding:6px 0; font-weight:500; }}
.insight-row {{
    display:grid; grid-template-columns: 140px 80px 30px 80px 70px 120px 100px 1fr 60px;
    gap:8px; align-items:center; padding:8px 12px; background:var(--surface);
    border:1px solid var(--border); border-radius:8px; margin:4px 0; font-size:0.88em;
}}
.insight-row:hover {{ border-color:var(--accent); }}
.insight-row.alert-warning {{ border-left:3px solid var(--red); }}
.insight-row.alert-watch {{ border-left:3px solid var(--yellow); }}
.row-room {{ font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.row-price {{ font-weight:600; text-align:right; }}
.row-arrow {{ color:var(--text-dim); text-align:center; }}
.row-trend {{ font-weight:600; white-space:nowrap; }}
.trend-up {{ color:var(--red); }}
.trend-down {{ color:var(--green); }}
.trend-stable {{ color:var(--blue); }}
.row-signal {{ color:var(--cyan); font-size:0.82em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.row-regime {{ color:var(--text-dim); font-size:0.82em; white-space:nowrap; }}
.row-best {{ font-size:0.82em; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.row-id {{ color:var(--text-dim); font-size:0.78em; text-align:right; }}

/* Comparison rows (Tab 2 & 3) — collapsible */
.comp-row {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; margin:4px 0; }}
.comp-row-header {{
    display:grid; grid-template-columns: 140px 160px 80px 80px 1fr 30px;
    gap:8px; align-items:center; padding:10px 14px; cursor:pointer; font-size:0.88em;
}}
.comp-row-header:hover {{ background:var(--surface2); }}
.comp-room {{ font-weight:600; }}
.comp-date {{ color:var(--text-dim); font-size:0.85em; }}
.comp-now {{ font-weight:600; text-align:right; }}
.comp-match-count {{ color:var(--accent2); font-weight:500; }}
.comp-toggle {{ color:var(--text-dim); transition:transform 0.2s; }}
.comp-toggle.open {{ transform:rotate(90deg); }}
.comp-detail {{ padding:0 14px 14px; }}
.comp-table {{ width:100%; border-collapse:collapse; font-size:0.85em; }}
.comp-table th {{ background:var(--surface2); padding:8px 10px; text-align:left; font-weight:600; color:var(--text); border-bottom:2px solid var(--border); }}
.comp-table td {{ padding:6px 10px; border-bottom:1px solid var(--border); color:var(--text-dim); }}
.comp-table tbody tr:hover td {{ background:rgba(99,102,241,0.05); }}
.comp-table .highlight-row td {{ background:rgba(99,102,241,0.1); font-weight:600; color:var(--text); }}

.savings {{ color:var(--green); font-weight:600; }}
.premium {{ color:var(--red); font-weight:600; }}
.no-data {{ color:var(--text-dim); font-style:italic; padding:24px; text-align:center; }}
.footer {{ text-align:center; padding:32px 0; color:var(--text-dim); font-size:0.85em; border-top:1px solid var(--border); margin-top:24px; }}

@media (max-width:900px) {{
    .insight-row {{ grid-template-columns:1fr 1fr; gap:4px; }}
    .comp-row-header {{ grid-template-columns:1fr 1fr; }}
}}
</style>
</head>
<body>

<div class="header">
<div class="container">
    <h1>Price Insights</h1>
    <p>Forward curve analysis &mdash; when prices go up, when they drop, and how they compare to today</p>
    <div class="nav-links">
        <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
        <a href="/api/v1/salesoffice/info">Documentation</a>
        <a href="/api/v1/salesoffice/data">Raw Data</a>
    </div>
</div>
</div>

<div class="tab-bar">
<div class="container">
    <button class="tab-btn active" onclick="switchTab('insights',this)">Insights <span class="tab-badge">{total_rooms}</span></button>
    <button class="tab-btn" onclick="switchTab('below',this)">Days Below Today <span class="tab-badge savings">{below_count}</span></button>
    <button class="tab-btn" onclick="switchTab('above',this)">Days Above Today <span class="tab-badge premium">{above_count}</span></button>
</div>
</div>

<div class="container">
    <div id="tab-insights" class="tab-content active">{insights_html}</div>
    <div id="tab-below" class="tab-content">{below_html}</div>
    <div id="tab-above" class="tab-content">{above_html}</div>
</div>

<div class="footer">
    <p>Medici Price Prediction Engine &mdash; Generated {now} &mdash; {total_rooms} rooms analyzed</p>
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
    if (el.style.display === 'none') {{
        el.style.display = 'block';
        arrow.classList.add('open');
    }} else {{
        el.style.display = 'none';
        arrow.classList.remove('open');
    }}
}}
</script>

</body>
</html>"""
