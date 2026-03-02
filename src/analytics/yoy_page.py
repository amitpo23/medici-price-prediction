"""Generate the Year-over-Year price comparison page.

4 tabs:
  Tab 1: Decay Curve by Year — T × Year heatmap of avg daily % change
  Tab 2: YoY Comparison     — current year vs prior years, z-score alerts + industry benchmark
  Tab 3: Calendar Spread    — avg price per (check-in month, T, year)
  Tab 4: External Benchmarks — Hotel Booking Demand & TBO Hotels dataset context
"""
from __future__ import annotations

import json
from datetime import datetime

from src.analytics.yoy_analysis import _safe_color, _safe_price_color

# Maps our T-bucket values → lead-time bucket keys in booking_benchmarks.json
_T_TO_LEAD: dict[int, str] = {
    1: "0-7d", 3: "0-7d", 5: "0-7d", 7: "0-7d",
    10: "8-30d", 14: "8-30d", 21: "8-30d", 30: "8-30d",
    45: "31-60d", 60: "31-60d",
    90: "61-90d",
}

# Month names → seasonality index keys
_MONTH_TO_SEASON_KEY: dict[str, str] = {
    "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
    "May": "May", "Jun": "June", "Jul": "July", "Aug": "August",
    "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December",
}

# ── Embedded benchmark data (avoids runtime file dependency on Azure) ─────────

# Source: hotel-booking-dataset (mpolinowski/GitHub), 117K bookings 2015-2017
_BENCHMARKS: dict = {
    "source": "hotel-booking-dataset (mpolinowski/GitHub)",
    "total_bookings": 117429,
    "years": "2015-2017",
    "hotel_types": {"City Hotel": 78121, "Resort Hotel": 39308},
    "seasonality_index": {
        "January": 0.695, "February": 0.724, "March": 0.787, "April": 0.982,
        "May": 1.067, "June": 1.14, "July": 1.242, "August": 1.37,
        "September": 1.031, "October": 0.867, "November": 0.73, "December": 0.81,
    },
    "lead_time_buckets": {
        "0-7d":    {"cancel_rate": 0.097, "avg_adr": 95.47,  "bookings": 18608},
        "8-30d":   {"cancel_rate": 0.281, "avg_adr": 109.91, "bookings": 18651},
        "31-60d":  {"cancel_rate": 0.366, "avg_adr": 107.18, "bookings": 16819},
        "61-90d":  {"cancel_rate": 0.397, "avg_adr": 107.43, "bookings": 12487},
        "91-180d": {"cancel_rate": 0.449, "avg_adr": 109.66, "bookings": 26311},
        "181-365d":{"cancel_rate": 0.556, "avg_adr": 95.61,  "bookings": 21424},
    },
    "weekend_premium_pct": 4.3,
    "city_hotel_benchmarks": {
        "avg_adr": 106.87, "median_adr": 100.0, "cancel_rate": 0.422,
        "avg_lead_time_days": 111.0, "repeat_guest_rate": 0.021,
        "avg_booking_changes": 0.18, "room_change_rate": 0.087,
    },
    "market_segment_adr": {
        "Aviation": 102.74, "Corporate": 70.45, "Direct": 117.69,
        "Groups": 80.51, "Offline TA/TO": 88.35, "Online TA": 117.96,
    },
    "market_segment_cancel": {
        "Aviation": 0.221, "Corporate": 0.189, "Direct": 0.154,
        "Groups": 0.617, "Offline TA/TO": 0.346, "Online TA": 0.369,
    },
}

# Source: TBO Hotels Dataset — Miami area supply (2978 hotels)
_TBO_STATS: dict = {
    "total": 2978,
    "ratings": {
        "ThreeStar": 1333, "FourStar": 591, "TwoStar": 514,
        "All": 439, "FiveStar": 69, "OneStar": 32,
    },
    "cities": {
        "Miami": 953, "Miami Beach": 599, "Fort Lauderdale": 590,
        "Miami South Beach": 279, "Hollywood Beach/Fort Lauderdale": 221,
        "Miami Beach - Sunny Isles": 93, "Pompano Beach/Fort Lauderdale": 70,
        "Lauderdale-by-the-Sea": 47,
    },
}

HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_yoy_html(yoy_data: dict) -> str:
    """Build the full YoY HTML page from pre-computed analysis dicts."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if not yoy_data:
        return _empty_page(now)

    tab1 = _build_decay_tab(yoy_data)
    tab2 = _build_yoy_comparison_tab(yoy_data, _BENCHMARKS)
    tab3 = _build_calendar_spread_tab(yoy_data)
    tab4 = _build_external_benchmarks_tab(_BENCHMARKS, _TBO_STATS)
    term_data = {hid: data.get("term_structure", {}) for hid, data in yoy_data.items()}
    tab5 = _build_term_structure_tab(term_data)

    return _wrap_page(now, tab1, tab2, tab3, tab4, tab5)


# ── Tab 1: Decay Curve by Year ────────────────────────────────────────

def _build_decay_tab(yoy_data: dict) -> str:
    html = """
    <div class="explainer">
        <strong>How to read:</strong> Each cell shows the average daily % price change at that T (days to check-in) for that year.
        <span class="savings">Green</span> = prices were falling at that lead time (buy opportunity).
        <span class="premium">Red</span> = prices were rising (sell / hold signal).
        Darker = stronger signal. Cells with fewer than 3 observations show <em>—</em>.
    </div>"""

    for hotel_id, data in yoy_data.items():
        pivot = data.get("pivot", {})
        if not pivot or not pivot.get("rows"):
            continue

        hotel_name = HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}")
        years = pivot["years"]
        rows = pivot["rows"]

        # Column headers
        year_headers = "".join(f"<th>{y}</th>" for y in years)
        current_yr = max(years) if years else 2025

        table_rows = ""
        for row in rows:
            T = row["T"]
            yr_cells = ""
            for yr in years:
                cell = row["years"].get(yr)
                if cell is None:
                    yr_cells += '<td class="empty-cell">—</td>'
                else:
                    avg = cell["avg"]
                    n = cell["n"]
                    bg = _safe_color(avg)
                    sign = "+" if avg >= 0 else ""
                    yr_cells += f'<td style="background:{bg}" title="{n} obs">{sign}{avg:.3f}%<span class="n-obs">{n}</span></td>'

            # Delta vs last year
            delta = row.get("delta_vs_ly")
            delta_html = "—"
            if delta is not None:
                bg = _safe_color(delta, scale=0.3)
                sign = "+" if delta >= 0 else ""
                delta_cls = "premium" if delta > 0 else "savings"
                delta_html = f'<span class="{delta_cls}">{sign}{delta:.3f}%</span>'

            table_rows += f"""<tr>
                <td class="t-cell">{row["label"]}</td>
                {yr_cells}
                <td>{delta_html}</td>
            </tr>"""

        html += f"""
        <h3 class="hotel-header">{hotel_name}</h3>
        <div class="table-wrap">
        <table class="heatmap-table">
            <thead><tr>
                <th>T</th>
                {year_headers}
                <th>Δ vs LY</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
        </div>"""

    return html


# ── Tab 2: YoY Comparison ─────────────────────────────────────────────

def _benchmark_adr(T: int, month_name: str, benchmarks: dict) -> float | None:
    """Compute seasonally-adjusted industry benchmark ADR for a given T and month."""
    if not benchmarks:
        return None
    bucket = _T_TO_LEAD.get(T)
    if not bucket:
        return None
    lead_data = benchmarks.get("lead_time_buckets", {}).get(bucket, {})
    base_adr = lead_data.get("avg_adr")
    if not base_adr:
        return None
    season_key = _MONTH_TO_SEASON_KEY.get(month_name)
    season_factor = benchmarks.get("seasonality_index", {}).get(season_key, 1.0) if season_key else 1.0
    return round(base_adr * season_factor, 2)


def _build_yoy_comparison_tab(yoy_data: dict, benchmarks: dict) -> str:
    has_benchmarks = bool(benchmarks)
    benchmark_note = (
        ' Industry ADR from <em>Hotel Booking Demand dataset (2015–2017, 117K bookings)</em>, '
        'seasonally adjusted by month. Use as directional context only — not Miami-specific.'
        if has_benchmarks else ""
    )
    html = f"""
    <div class="explainer">
        <strong>How to read:</strong> For each room category, check-in month, and T (days to check-in),
        this compares the average price this year vs. last year.
        <span class="alert-warning-pill">Warning</span> (Z &gt; 2.5) means this year's price is significantly
        above the historical pattern. <span class="savings">Green</span> = cheaper than last year.
        <span class="premium">Red</span> = more expensive than last year.{benchmark_note}
    </div>"""

    for hotel_id, data in yoy_data.items():
        comparison = data.get("comparison", [])
        if not comparison:
            continue

        hotel_name = HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}")
        html += f'<h3 class="hotel-header">{hotel_name}</h3>'

        # Group by category
        by_cat: dict[str, list[dict]] = {}
        for row in comparison:
            cat = row["category"]
            by_cat.setdefault(cat, []).append(row)

        for cat, rows in sorted(by_cat.items()):
            warnings = sum(1 for r in rows if r["alert"] == "warning")
            watches = sum(1 for r in rows if r["alert"] == "watch")
            uid = f"yoy_{hotel_id}_{cat}"

            table_rows = ""
            for r in rows:
                alert = r.get("alert", "normal")
                row_cls = "row-warning" if alert == "warning" else "row-watch" if alert == "watch" else ""

                yoy_pct = r.get("yoy_pct")
                yoy_html = "—"
                if yoy_pct is not None:
                    cls = "premium" if yoy_pct > 0 else "savings"
                    yoy_html = f'<span class="{cls}">{yoy_pct:+.1f}%</span>'

                zscore = r.get("zscore")
                z_html = "—"
                if zscore is not None:
                    zcls = "z-warning" if abs(zscore) > 2.5 else "z-watch" if abs(zscore) > 1.5 else "z-normal"
                    z_html = f'<span class="{zcls}">{zscore:+.2f}</span>'

                curr_price = r.get("current_avg_price")
                last_price = r.get("last_year_avg_price")
                curr_html = f"${curr_price:,.0f}" if curr_price else "—"
                last_html = f"${last_price:,.0f}" if last_price else "—"

                # Industry benchmark ADR (seasonally adjusted)
                bench_adr = _benchmark_adr(r["T_bucket"], r["checkin_month_name"], benchmarks)
                bench_html = "—"
                if bench_adr and curr_price:
                    pct_vs_bench = (curr_price - bench_adr) / bench_adr * 100
                    sign = "+" if pct_vs_bench >= 0 else ""
                    b_cls = "premium" if pct_vs_bench > 5 else "savings" if pct_vs_bench < -5 else ""
                    bench_html = (
                        f'<span title="Industry ADR: ${bench_adr:,.0f}">'
                        f'${bench_adr:,.0f} '
                        f'<span class="{b_cls}" style="font-size:0.8em">({sign}{pct_vs_bench:.0f}%)</span>'
                        f'</span>'
                    )
                elif bench_adr:
                    bench_html = f"${bench_adr:,.0f}"

                bench_col = f"<td>{bench_html}</td>" if has_benchmarks else ""
                table_rows += f"""<tr class="{row_cls}">
                    <td>{r["checkin_month_name"]}</td>
                    <td>{r["T_bucket"]}d</td>
                    <td>{last_html} <span class="n-obs">n={r["last_year_n"]}</span></td>
                    <td>{curr_html} <span class="n-obs">n={r["current_n"]}</span></td>
                    <td>{yoy_html}</td>
                    {bench_col}
                    <td>{z_html}</td>
                    <td>{"⚠" if alert == "warning" else "👁" if alert == "watch" else "✓"}</td>
                </tr>"""

            alert_summary = ""
            if warnings:
                alert_summary += f'<span class="alert-warning-pill">{warnings} warnings</span> '
            if watches:
                alert_summary += f'<span class="alert-watch-pill">{watches} watches</span>'

            bench_th = "<th>Industry ADR</th>" if has_benchmarks else ""
            html += f"""
            <div class="comp-row">
                <div class="comp-row-header" onclick="toggle('{uid}')">
                    <span class="comp-room">{cat.title()}</span>
                    <span>{len(rows)} data points</span>
                    <span>{alert_summary}</span>
                    <span class="comp-toggle" id="arrow_{uid}">&#9654;</span>
                </div>
                <div class="comp-detail" id="{uid}" style="display:none">
                    <table class="comp-table">
                        <thead><tr>
                            <th>Month</th><th>T</th>
                            <th>{rows[0].get("last_year", "LY")} Avg</th>
                            <th>{rows[0].get("current_year", "CY")} Avg</th>
                            <th>YoY %</th>{bench_th}
                            <th>Z-Score</th><th>Flag</th>
                        </tr></thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>"""

    return html


# ── Tab 3: Calendar Spread ────────────────────────────────────────────

def _build_calendar_spread_tab(yoy_data: dict) -> str:
    html = """
    <div class="explainer">
        <strong>How to read:</strong> For each check-in month and T (days to check-in),
        this shows the average price across different years. Cells are colored relative to
        the most recent year — <span class="savings">green</span> = cheaper than this year's price,
        <span class="premium">red</span> = more expensive. Blank = no data for that combination.
    </div>"""

    for hotel_id, data in yoy_data.items():
        spread = data.get("spread", {})
        if not spread or not spread.get("months"):
            continue

        hotel_name = HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}")
        years = spread["years"]
        months = spread["months"]

        html += f'<h3 class="hotel-header">{hotel_name}</h3>'

        year_headers = "".join(f"<th>{y}</th>" for y in years)
        current_yr = max(years) if years else 2025

        for month_name, month_data in months.items():
            rows = month_data.get("rows", [])
            if not rows:
                continue

            table_rows = ""
            for row in rows:
                yr_prices = row["years"]
                ref_price = yr_prices.get(current_yr)

                yr_cells = ""
                for yr in years:
                    price = yr_prices.get(yr)
                    if price is None:
                        yr_cells += '<td class="empty-cell">—</td>'
                    else:
                        bg = _safe_price_color(price, ref_price) if yr != current_yr else "transparent"
                        yr_cells += f'<td style="background:{bg}">${price:,.0f}</td>'

                table_rows += f'<tr><td class="t-cell">{row["label"]}</td>{yr_cells}</tr>'

            html += f"""
            <div class="spread-section">
                <div class="spread-header" onclick="toggleSpread('{hotel_id}_{month_name}')">
                    <span class="month-label">Check-in: {month_name}</span>
                    <span class="comp-toggle" id="arrow_{hotel_id}_{month_name}">&#9654;</span>
                </div>
                <div id="spread_{hotel_id}_{month_name}" style="display:none">
                    <table class="heatmap-table">
                        <thead><tr><th>T</th>{year_headers}</tr></thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>"""

    return html


# ── Tab 4: External Benchmarks ────────────────────────────────────────

def _build_external_benchmarks_tab(benchmarks: dict, tbo_stats: dict) -> str:
    """Build the External Benchmarks panel from booking_benchmarks.json and TBO CSV."""

    # ── Hotel Booking Demand Dataset ─────────────────────────────────
    hbd_html = '<p class="no-data">Hotel Booking Demand dataset not available.</p>'

    if benchmarks:
        src = benchmarks.get("source", "Hotel Booking Demand")
        total = benchmarks.get("total_bookings", 0)
        years = benchmarks.get("years", "N/A")
        city_bm = benchmarks.get("city_hotel_benchmarks", {})

        # Seasonality bar chart
        season = benchmarks.get("seasonality_index", {})
        season_rows = ""
        for month, idx in season.items():
            pct = idx * 100
            bar_w = min(int(idx * 70), 100)
            bar_cls = "bar-high" if idx >= 1.2 else "bar-mid" if idx >= 1.0 else "bar-low"
            season_rows += f"""<tr>
                <td class="bm-month">{month[:3]}</td>
                <td class="bm-idx">{idx:.3f}</td>
                <td>
                    <div class="bar-bg">
                        <div class="bar-fill {bar_cls}" style="width:{bar_w}%"></div>
                    </div>
                </td>
                <td class="bm-note">{"Peak season" if idx >= 1.2 else "High season" if idx >= 1.0 else "Low season"}</td>
            </tr>"""

        # Lead-time ADR table
        lead_rows = ""
        for bucket, bdata in benchmarks.get("lead_time_buckets", {}).items():
            adr = bdata.get("avg_adr", 0)
            cancel = bdata.get("cancel_rate", 0)
            n = bdata.get("bookings", 0)
            lead_rows += f"""<tr>
                <td class="bm-month">{bucket}</td>
                <td>${adr:,.2f}</td>
                <td>{cancel * 100:.1f}%</td>
                <td class="bm-note">{n:,} bookings</td>
            </tr>"""

        # Market segment
        seg_rows = ""
        seg_adr = benchmarks.get("market_segment_adr", {})
        seg_cancel = benchmarks.get("market_segment_cancel", {})
        for seg, adr in sorted(seg_adr.items(), key=lambda x: -x[1]):
            cancel = seg_cancel.get(seg, 0)
            seg_rows += f"""<tr>
                <td class="bm-month">{seg}</td>
                <td>${adr:,.2f}</td>
                <td>{cancel * 100:.1f}%</td>
            </tr>"""

        hbd_html = f"""
        <div class="bm-meta">
            <span class="bm-badge">Source: {src}</span>
            <span class="bm-badge">{total:,} total bookings</span>
            <span class="bm-badge">{years}</span>
            <span class="bm-badge">City Hotel avg ADR: ${city_bm.get('avg_adr', 0):,.2f}</span>
            <span class="bm-badge">Cancel rate: {city_bm.get('cancel_rate', 0) * 100:.1f}%</span>
            <span class="bm-badge">Avg lead time: {city_bm.get('avg_lead_time_days', 0):.0f}d</span>
        </div>

        <div class="bm-grid">
            <div class="bm-panel">
                <h4 class="bm-panel-title">Seasonality Index by Month</h4>
                <p class="bm-desc">Index &gt; 1.0 = above-average demand. Apply to ADR benchmarks for seasonal pricing context.</p>
                <table class="bm-table">
                    <thead><tr><th>Month</th><th>Index</th><th>Relative demand</th><th></th></tr></thead>
                    <tbody>{season_rows}</tbody>
                </table>
            </div>
            <div class="bm-panel">
                <h4 class="bm-panel-title">Average Daily Rate by Lead Time (T)</h4>
                <p class="bm-desc">Industry ADR at different booking windows. These are the benchmarks used in the YoY Comparison tab.</p>
                <table class="bm-table">
                    <thead><tr><th>Lead Time</th><th>Avg ADR</th><th>Cancel Rate</th><th>Sample</th></tr></thead>
                    <tbody>{lead_rows}</tbody>
                </table>
            </div>
            <div class="bm-panel">
                <h4 class="bm-panel-title">ADR by Market Segment</h4>
                <p class="bm-desc">Direct bookings command the highest ADR. Groups and Corporate the lowest.</p>
                <table class="bm-table">
                    <thead><tr><th>Segment</th><th>Avg ADR</th><th>Cancel Rate</th></tr></thead>
                    <tbody>{seg_rows}</tbody>
                </table>
            </div>
        </div>"""

    # ── TBO Hotels Dataset ────────────────────────────────────────────
    tbo_html = '<p class="no-data">TBO Hotels dataset not available.</p>'

    if tbo_stats:
        total = tbo_stats.get("total", 0)
        ratings = tbo_stats.get("ratings", {})
        cities = tbo_stats.get("cities", {})

        rating_rows = "".join(
            f'<tr><td class="bm-month">{r}</td><td>{n:,}</td>'
            f'<td><div class="bar-bg"><div class="bar-fill bar-mid" style="width:{min(int(n/total*200),100)}%"></div></div></td></tr>'
            for r, n in sorted(ratings.items(), key=lambda x: -x[1])
        )
        city_rows = "".join(
            f'<tr><td class="bm-month">{c}</td><td>{n:,}</td></tr>'
            for c, n in sorted(cities.items(), key=lambda x: -x[1])
        )

        tbo_html = f"""
        <div class="bm-meta">
            <span class="bm-badge">Source: TBO Hotels Dataset (Kaggle)</span>
            <span class="bm-badge">{total:,} Miami-area hotels</span>
        </div>
        <div class="bm-grid">
            <div class="bm-panel">
                <h4 class="bm-panel-title">Hotel Distribution by Star Rating</h4>
                <p class="bm-desc">Market composition of Miami-area hotel supply by tier.</p>
                <table class="bm-table">
                    <thead><tr><th>Rating</th><th>Count</th><th>Share</th></tr></thead>
                    <tbody>{rating_rows}</tbody>
                </table>
            </div>
            <div class="bm-panel">
                <h4 class="bm-panel-title">Top Cities / Areas</h4>
                <p class="bm-desc">Hotel supply by city/area in the dataset.</p>
                <table class="bm-table">
                    <thead><tr><th>City / Area</th><th>Hotels</th></tr></thead>
                    <tbody>{city_rows}</tbody>
                </table>
            </div>
        </div>"""

    return f"""
    <div class="explainer">
        <strong>External Benchmarks:</strong> Industry-wide data from two open datasets used
        to contextualize our internal YoY price analysis. These are not Miami-specific but provide
        directional signals about pricing patterns, seasonality, and lead-time behavior.
    </div>

    <h3 class="hotel-header">Hotel Booking Demand Dataset</h3>
    {hbd_html}

    <h3 class="hotel-header" style="margin-top:32px">TBO Hotels Dataset — Miami Area Supply</h3>
    {tbo_html}
    """


# ── Tab 5: Term Structure ─────────────────────────────────────────────

def _build_term_structure_tab(term_data: dict) -> str:
    """Build Term Structure tab with 6 Chart.js charts + client-side filtering."""
    # Filter to hotels that actually have data
    available = {hid: hdata for hid, hdata in term_data.items() if hdata and hdata.get("combos")}

    if not available:
        return (
            '<div class="no-data" style="padding:60px;text-align:center;">'
            'Term structure data is loading — please refresh in ~30 seconds.</div>'
        )

    # Build hotel dropdown
    hotel_opts = "".join(
        f'<option value="{hid}">{HOTEL_NAMES.get(int(hid), f"Hotel {hid}")}</option>'
        for hid in sorted(available)
    )

    # First hotel's combos for initial combo dropdown
    first_hid = next(iter(sorted(available)))
    first_combos = available[first_hid].get("combos", [])
    combo_opts = "".join(f'<option value="{c}">{c}</option>' for c in first_combos)

    # Serialize all data to JSON (embedded in page, drives all charts client-side)
    # Convert int keys to str for JSON compatibility
    serializable = {str(hid): hdata for hid, hdata in available.items()}
    json_data = json.dumps(serializable, default=str)

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> Select a hotel and room/board combination. '
        'All 6 charts update instantly — no page reload. '
        '<span style="color:#6366f1;font-weight:600;">Indigo = 2023</span> &nbsp;'
        '<span style="color:#06b6d4;font-weight:600;">Cyan = 2024</span> &nbsp;'
        '<span style="color:#22c55e;font-weight:600;">Green = 2025</span>. '
        'Only clean observations (n&ge;3 per T-bucket) are plotted.</div>'

        '<div class="ts-filters">'
        f'<label class="ts-label">Hotel<select id="ts-hotel" onchange="tsHotelChange()">{hotel_opts}</select></label>'
        f'<label class="ts-label">Room / Board<select id="ts-combo" onchange="tsRender()">{combo_opts}</select></label>'
        '</div>'

        '<div class="ts-grid">'

        # Chart 1
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9312; Avg Daily &Delta;% by T</div>'
        '<div class="ts-panel-desc">Average daily price change at each lead time. Where 2025 diverges from 2023/2024 marks the structural shift point.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-delta"></canvas></div>'
        '</div>'

        # Chart 2
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9313; Cumulative Path (base&nbsp;=&nbsp;100 at T=90)</div>'
        '<div class="ts-panel-desc">Compounded price path from 90 days out to expiry. Flat then spike = last-minute squeeze. Linear = steady pressure.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-cumul"></canvas></div>'
        '</div>'

        # Chart 3
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9314; Realized Volatility by T</div>'
        '<div class="ts-panel-desc">Std dev of daily % changes. If 2025 spikes earlier than prior years, instability moved forward in the booking window.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-vol"></canvas></div>'
        '</div>'

        # Chart 4
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9315; % Days with Positive &Delta;%</div>'
        '<div class="ts-panel-desc">Fraction of days where price rose. At T=7: if 2025 &gt; 70% vs 2023 &lt; 55% — abnormal upward pressure confirmed.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-pctup"></canvas></div>'
        '</div>'

        # Chart 5 — full width
        '<div class="ts-panel ts-panel--full">'
        '<div class="ts-panel-title">&#9316; Min Rel-to-Expiry Distribution</div>'
        '<div class="ts-panel-desc">For each completed contract: minimum of (price&minus;S_exp)/S_exp&times;100. '
        'Shows whether large pre-expiry discounts (&minus;10%) still exist or have disappeared.</div>'
        '<div class="ts-canvas-wrap ts-canvas-wrap--bar"><canvas id="ch-minrel"></canvas></div>'
        '</div>'

        # Chart 6 — heatmap, full width
        '<div class="ts-panel ts-panel--full">'
        '<div class="ts-panel-title">&#9317; Heatmap &mdash; Avg Daily &Delta;% (T &times; Year)</div>'
        '<div class="ts-panel-desc">Same data as Chart &#9312; as a color matrix. '
        '<span class="savings">Green</span> = prices falling (buy opportunity). '
        '<span class="premium">Red</span> = prices rising. Hot zones jump out immediately.</div>'
        '<div id="ch-heatmap" class="table-wrap"></div>'
        '</div>'

        '</div>'  # end .ts-grid
    )

    # JavaScript — string concatenation avoids f-string brace conflicts with JS objects
    js = (
        '<script>\n'
        '(function() {\n'
        'const TS_DATA = ' + json_data + ';\n'
        'const YEAR_COLORS = {"2023":"#6366f1","2024":"#06b6d4","2025":"#22c55e"};\n'
        'const YEARS = ["2023","2024","2025"];\n'
        'const CHART_OPTS = {\n'
        '  responsive: true, maintainAspectRatio: false,\n'
        '  plugins: { legend: { labels: { color: "#e4e7ec", padding: 14 } },\n'
        '             tooltip: { mode: "index", intersect: false } },\n'
        '};\n'
        'const AXIS_X = { reverse: true,\n'
        '  title: { display: true, text: "T (days to check-in)", color: "#8b90a0" },\n'
        '  ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } };\n'
        'function yAxis(label) {\n'
        '  return { title: { display: true, text: label, color: "#8b90a0" },\n'
        '           ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } }; }\n'
        'let _ch = {};\n'
        '\n'
        'window.tsHotelChange = function() {\n'
        '  const hotel = document.getElementById("ts-hotel").value;\n'
        '  const combos = (TS_DATA[hotel] || {}).combos || [];\n'
        '  const sel = document.getElementById("ts-combo");\n'
        '  sel.innerHTML = combos.map(c => `<option value="${c}">${c}</option>`).join("");\n'
        '  window.tsRender();\n'
        '};\n'
        '\n'
        'window.tsRender = function() {\n'
        '  const hotel = document.getElementById("ts-hotel").value;\n'
        '  const combo = document.getElementById("ts-combo").value;\n'
        '  const hdata = TS_DATA[hotel];\n'
        '  if (!hdata) return;\n'
        '  const d = (hdata.data || {})[combo];\n'
        '  if (!d) return;\n'
        '  const T = d.t_values;\n'
        '  _line("ch-delta", T, d.avg_delta, "Avg Daily \\u0394%");\n'
        '  _line("ch-cumul", T, d.cumulative, "Normalized Price");\n'
        '  _line("ch-vol",   T, d.volatility, "Std Dev \\u0394%");\n'
        '  _line("ch-pctup", T, d.pct_up, "% Days Positive");\n'
        '  _bar("ch-minrel", d.min_rel_hist);\n'
        '  _heatmap("ch-heatmap", d.heatmap);\n'
        '};\n'
        '\n'
        'function _line(id, tVals, yearData, yLabel) {\n'
        '  if (_ch[id]) { _ch[id].destroy(); }\n'
        '  const ctx = document.getElementById(id);\n'
        '  if (!ctx) return;\n'
        '  _ch[id] = new Chart(ctx, {\n'
        '    type: "line",\n'
        '    data: { labels: tVals,\n'
        '      datasets: YEARS.map(yr => ({\n'
        '        label: yr, data: (yearData || {})[yr] || [],\n'
        '        borderColor: YEAR_COLORS[yr], backgroundColor: "transparent",\n'
        '        tension: 0.3, pointRadius: 4, pointHoverRadius: 6,\n'
        '        spanGaps: true, borderWidth: 2 })) },\n'
        '    options: { ...CHART_OPTS, scales: { x: AXIS_X, y: yAxis(yLabel) } }\n'
        '  });\n'
        '}\n'
        '\n'
        'function _bar(id, histData) {\n'
        '  if (_ch[id]) { _ch[id].destroy(); }\n'
        '  const ctx = document.getElementById(id);\n'
        '  if (!ctx || !histData) return;\n'
        '  _ch[id] = new Chart(ctx, {\n'
        '    type: "bar",\n'
        '    data: { labels: histData.buckets || [],\n'
        '      datasets: YEARS.map(yr => ({\n'
        '        label: yr, data: histData[yr] || [],\n'
        '        backgroundColor: YEAR_COLORS[yr] + "99",\n'
        '        borderColor: YEAR_COLORS[yr], borderWidth: 1 })) },\n'
        '    options: { ...CHART_OPTS,\n'
        '      scales: {\n'
        '        x: { title: { display: true, text: "Min Rel-to-Expiry", color: "#8b90a0" },\n'
        '             ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } },\n'
        '        y: { title: { display: true, text: "# Contracts", color: "#8b90a0" },\n'
        '             ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } } } }\n'
        '  });\n'
        '}\n'
        '\n'
        'function _heatmap(id, hmData) {\n'
        '  const el = document.getElementById(id);\n'
        '  if (!el || !hmData) return;\n'
        '  const tVals = hmData.t_values || [];\n'
        '  const yrs = hmData.years || [];\n'
        '  const matrix = hmData.matrix || {};\n'
        '  let h = \'<table class="heatmap-table"><thead><tr><th>T</th>\';\n'
        '  yrs.forEach(yr => h += `<th>${yr}</th>`);\n'
        '  h += "</tr></thead><tbody>";\n'
        '  tVals.forEach((T, ti) => {\n'
        '    h += `<tr><td class="t-cell">${T}d</td>`;\n'
        '    yrs.forEach(yr => {\n'
        '      const v = (matrix[yr] || [])[ti];\n'
        '      if (v === null || v === undefined) {\n'
        '        h += \'<td class="empty-cell">&mdash;</td>\';\n'
        '      } else {\n'
        '        const alpha = Math.min(0.15 + Math.abs(v) / 0.5 * 0.55, 0.70);\n'
        '        const bg = v < 0\n'
        '          ? `rgba(34,197,94,${alpha.toFixed(2)})`\n'
        '          : `rgba(239,68,68,${alpha.toFixed(2)})`;\n'
        '        h += `<td style="background:${bg}">${v > 0 ? "+" : ""}${v.toFixed(3)}%</td>`;\n'
        '      }\n'
        '    });\n'
        '    h += "</tr>";\n'
        '  });\n'
        '  h += "</tbody></table>";\n'
        '  el.innerHTML = h;\n'
        '}\n'
        '\n'
        'document.addEventListener("DOMContentLoaded", function() {\n'
        '  if (document.getElementById("ch-delta")) window.tsRender();\n'
        '});\n'
        '})();\n'
        '</script>\n'
    )

    return html + js


# ── Page wrapper ──────────────────────────────────────────────────────

def _empty_page(now: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>YoY Comparison</title></head>
<body style="background:#0f1117;color:#e4e7ec;font-family:sans-serif;padding:40px;text-align:center;">
<h1>No YoY Data Available</h1>
<p>The historical data query is still loading. Please try again in a moment.</p>
<p style="color:#8b90a0;font-size:0.85em;">Generated {now}</p>
</body></html>"""


def _wrap_page(now: str, tab1: str, tab2: str, tab3: str, tab4: str, tab5: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medici — Year-over-Year Price Comparison</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{
    --bg:#0f1117; --surface:#1a1d27; --surface2:#232733;
    --border:#2d3140; --text:#e4e7ec; --text-dim:#8b90a0;
    --accent:#6366f1; --accent2:#818cf8;
    --green:#22c55e; --red:#ef4444; --yellow:#eab308; --cyan:#06b6d4;
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}}
.container{{max-width:1400px;margin:0 auto;padding:0 24px;}}
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

/* Hotel headers */
.hotel-header{{font-size:1.2em;font-weight:700;color:var(--accent2);margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--border);}}
.hotel-header:first-child{{margin-top:0;}}

/* Explainer */
.explainer{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin:0 0 20px;font-size:0.9em;color:var(--text-dim);}}
.explainer strong{{color:var(--text);}}

/* Heatmap table */
.table-wrap{{overflow-x:auto;margin-bottom:20px;}}
.heatmap-table{{width:100%;border-collapse:collapse;font-size:0.85em;}}
.heatmap-table th{{background:var(--surface2);padding:10px 12px;text-align:center;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);border-right:1px solid var(--border);white-space:nowrap;}}
.heatmap-table td{{padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);border-right:1px solid var(--border);font-size:0.88em;color:var(--text);position:relative;}}
.heatmap-table tbody tr:hover td{{filter:brightness(1.2);}}
.t-cell{{font-weight:600;color:var(--accent2);text-align:right;background:var(--surface)!important;}}
.empty-cell{{color:var(--text-dim);}}
.n-obs{{display:block;font-size:0.7em;color:var(--text-dim);}}

/* Comparison rows (Tab 2) */
.comp-row{{background:var(--surface);border:1px solid var(--border);border-radius:8px;margin:4px 0;}}
.comp-row-header{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;cursor:pointer;font-size:0.9em;gap:16px;flex-wrap:wrap;}}
.comp-row-header:hover{{background:var(--surface2);}}
.comp-room{{font-weight:600;min-width:100px;}}
.comp-toggle{{color:var(--text-dim);transition:transform 0.2s;}}
.comp-toggle.open{{transform:rotate(90deg);}}
.comp-detail{{padding:0 16px 16px;overflow-x:auto;}}
.comp-table{{width:100%;border-collapse:collapse;font-size:0.85em;}}
.comp-table th{{background:var(--surface2);padding:8px 10px;text-align:left;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);}}
.comp-table td{{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text-dim);}}
.comp-table .row-warning td{{background:rgba(239,68,68,0.06);}}
.comp-table .row-watch td{{background:rgba(234,179,8,0.06);}}

/* Alert pills */
.alert-warning-pill{{background:rgba(239,68,68,0.15);color:var(--red);padding:2px 8px;border-radius:10px;font-size:0.78em;font-weight:600;}}
.alert-watch-pill{{background:rgba(234,179,8,0.15);color:var(--yellow);padding:2px 8px;border-radius:10px;font-size:0.78em;font-weight:600;}}

/* Z-score colors */
.z-warning{{color:var(--red);font-weight:700;}}
.z-watch{{color:var(--yellow);font-weight:600;}}
.z-normal{{color:var(--green);}}

/* Calendar spread (Tab 3) */
.spread-section{{background:var(--surface);border:1px solid var(--border);border-radius:8px;margin:6px 0;}}
.spread-header{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;cursor:pointer;}}
.spread-header:hover{{background:var(--surface2);}}
.month-label{{font-weight:600;color:var(--text);}}

/* Shared */
.savings{{color:var(--green);font-weight:600;}}
.premium{{color:var(--red);font-weight:600;}}
.footer{{text-align:center;padding:32px 0;color:var(--text-dim);font-size:0.85em;border-top:1px solid var(--border);margin-top:24px;}}

/* External Benchmarks (Tab 4) */
.bm-meta{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;}}
.bm-badge{{background:rgba(99,102,241,0.15);color:var(--accent2);border:1px solid rgba(99,102,241,0.3);border-radius:20px;padding:4px 12px;font-size:0.8em;font-weight:600;}}
.bm-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;margin-bottom:24px;}}
.bm-panel{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;}}
.bm-panel-title{{font-size:1em;font-weight:700;color:var(--text);margin-bottom:6px;}}
.bm-desc{{font-size:0.82em;color:var(--text-dim);margin-bottom:12px;line-height:1.4;}}
.bm-table{{width:100%;border-collapse:collapse;font-size:0.83em;}}
.bm-table th{{background:var(--surface2);padding:7px 10px;text-align:left;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);}}
.bm-table td{{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text-dim);}}
.bm-month{{font-weight:600;color:var(--text);white-space:nowrap;}}
.bm-idx,.bm-note{{white-space:nowrap;}}
.bar-bg{{background:var(--surface2);border-radius:4px;height:10px;width:120px;overflow:hidden;}}
.bar-fill{{height:100%;border-radius:4px;}}
.bar-high{{background:var(--red);}}
.bar-mid{{background:var(--cyan);}}
.bar-low{{background:var(--text-dim);}}
.no-data{{color:var(--text-dim);font-style:italic;padding:20px 0;}}

/* Term Structure (Tab 5) */
.ts-filters{{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-radius:10px;margin-bottom:20px;}}
.ts-label{{font-size:0.85em;color:var(--text-dim);display:flex;flex-direction:column;gap:4px;}}
.ts-label select{{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:0.9em;font-family:inherit;cursor:pointer;min-width:200px;}}
.ts-label select:focus{{outline:none;border-color:var(--accent);}}
.ts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
@media(max-width:900px){{.ts-grid{{grid-template-columns:1fr;}}}}
.ts-panel{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;}}
.ts-panel--full{{grid-column:1/-1;}}
.ts-panel-title{{font-size:0.95em;font-weight:700;color:var(--accent2);margin-bottom:4px;}}
.ts-panel-desc{{font-size:0.8em;color:var(--text-dim);margin-bottom:12px;line-height:1.4;}}
.ts-canvas-wrap{{height:280px;position:relative;}}
.ts-canvas-wrap--bar{{height:260px;}}
</style>
</head>
<body>

<div class="header">
<div class="container">
    <h1>Year-over-Year Price Comparison</h1>
    <p>Calendar spread analysis &mdash; how prices behave at each T across multiple years</p>
    <div class="nav-links">
        <a href="/api/v1/salesoffice/insights">Insights</a>
        <a href="/api/v1/salesoffice/options">Options</a>
        <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
        <a href="/api/v1/salesoffice/info">Documentation</a>
    </div>
</div>
</div>

<div class="tab-bar">
<div class="container">
    <button class="tab-btn active" onclick="switchTab('decay',this)">Decay Curve by Year</button>
    <button class="tab-btn" onclick="switchTab('yoy',this)">YoY Comparison</button>
    <button class="tab-btn" onclick="switchTab('spread',this)">Calendar Spread</button>
    <button class="tab-btn" onclick="switchTab('benchmarks',this)">External Benchmarks</button>
    <button class="tab-btn" onclick="switchTab('ts',this)">Term Structure</button>
</div>
</div>

<div class="container">
    <div id="tab-decay" class="tab-content active">{tab1}</div>
    <div id="tab-yoy" class="tab-content">{tab2}</div>
    <div id="tab-spread" class="tab-content">{tab3}</div>
    <div id="tab-benchmarks" class="tab-content">{tab4}</div>
    <div id="tab-ts" class="tab-content">{tab5}</div>
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
    if (name === 'ts' && typeof tsRender === 'function') {{ tsRender(); }}
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
function toggleSpread(id) {{
    const el = document.getElementById('spread_' + id);
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
