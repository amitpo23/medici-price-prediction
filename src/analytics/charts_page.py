"""Generate the Chart Pack page.

3 tabs:
  Tab 1: Room/Contract Path     — single contract deep dive (Charts 1-4)
  Tab 2: 3-Year Term Structure  — aggregate multi-year (Charts 5-9)
  Tab 3: Expiry-Relative Stats  — breach/opportunity analysis (Charts 10-12)
"""
from __future__ import annotations

import json
from datetime import datetime

from src.analytics.yoy_analysis import _safe_color
from src.utils.template_engine import render_template

HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_charts_html(charts_data: dict) -> str:
    """Build the full Charts HTML page from pre-computed data."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if not charts_data:
        return render_template(
            "error.html",
            title="Chart Pack",
            message="No Chart Data Available",
            detail="The data query is still loading. Please try again in a moment.",
            now=now,
        )

    attribution = charts_data.get("source_attribution", {})
    enrichments = charts_data.get("enrichments", {})

    tab1 = _build_contract_path_tab(charts_data)
    tab2 = _build_term_structure_tab(charts_data, enrichments.get("seasonality", {}))
    tab3 = _build_opportunity_stats_tab(charts_data, enrichments.get("velocity", {}))
    return render_template(
        "charts.html",
        now=now,
        tab1_html=tab1,
        tab2_html=tab2,
        tab3_html=tab3,
        coverage_bar_html=_coverage_bar_html(attribution),
        footer_sources_text=_footer_sources_text(attribution),
    )


# ── Data source attribution helpers ──────────────────────────────────────


def _source_strip_html(sources: list[dict], extra_label: str = "") -> str:
    """Build a collapsible data source attribution strip."""
    if not sources:
        return ""

    total_rows = sum(s.get("rows", 0) for s in sources if isinstance(s.get("rows"), int))
    all_years = set()
    for s in sources:
        for y in s.get("years", []):
            all_years.add(y)
    year_range = f"{min(all_years)}-{max(all_years)}" if all_years else "N/A"
    n_sources = len(sources)

    cards = ""
    for s in sources:
        rows_str = f"{s['rows']:,}" if isinstance(s.get("rows"), int) else str(s.get("rows", ""))
        status_cls = "badge-live" if s.get("status") == "live" else "badge-archive"
        status_txt = "Live" if s.get("status") == "live" else "Archive"
        cards += (
            f'<div class="source-mini-card">'
            f'<span class="source-mini-name">{s["name"]}</span>'
            f'<span class="source-mini-rows">{rows_str} rows</span>'
            f'<span class="source-mini-years">{s.get("year_range", "")}</span>'
            f'<span class="source-mini-freq">{s.get("update_freq", "")}</span>'
            f'<span class="badge {status_cls}">{status_txt}</span>'
            f'</div>'
        )

    extra = f' | {extra_label}' if extra_label else ""
    return (
        '<details class="source-strip">'
        '<summary class="source-summary">'
        f'<span>Data Sources: <strong>{n_sources}</strong> sources | '
        f'<strong>{total_rows:,}</strong> rows | '
        f'<strong>{year_range}</strong>{extra}</span>'
        '<span class="source-toggle">Details</span>'
        '</summary>'
        f'<div class="source-details">{cards}</div>'
        '</details>'
    )


def _coverage_bar_html(attribution: dict | None) -> str:
    """Compact coverage stats bar between header and tabs."""
    if not attribution or not attribution.get("total_rows"):
        return ""
    total = attribution.get("total_rows", 0)
    year_range = attribution.get("year_range", "N/A")
    hotels = attribution.get("hotels", 0)
    contracts = attribution.get("contracts", 0)
    n_sources = len(attribution.get("sources", []))
    return (
        '<div class="coverage-bar"><div class="container">'
        f'<span class="cov-item"><strong>{total:,}</strong> price observations</span>'
        f'<span class="cov-item"><strong>{year_range}</strong> year coverage</span>'
        f'<span class="cov-item"><strong>{hotels}</strong> hotels tracked</span>'
        f'<span class="cov-item"><strong>{contracts:,}</strong> unique contracts</span>'
        f'<span class="cov-item"><strong>{n_sources}+</strong> data sources</span>'
        '</div></div>'
    )


def _footer_sources_text(attribution: dict | None) -> str:
    """Generate footer text listing data sources."""
    if not attribution or not attribution.get("sources"):
        return ""
    names = [s["name"] for s in attribution["sources"]]
    return f'Powered by {len(names)} sources: {", ".join(names)}. &mdash; '


# ── Tab 1: Room/Contract Path (AJAX-driven) ─────────────────────────────


def _build_contract_path_tab(charts_data: dict) -> str:
    contracts_index = charts_data.get("contracts_index", {})

    if not contracts_index:
        return (
            '<div class="no-data" style="padding:60px;text-align:center;">'
            'No contract data available.</div>'
        )

    # Build hotel dropdown
    hotel_opts = "".join(
        f'<option value="{hid}">{HOTEL_NAMES.get(int(hid), f"Hotel {hid}")}</option>'
        for hid in sorted(contracts_index.keys(), key=int)
    )

    # Serialize contracts index for JS
    contracts_json = json.dumps(contracts_index, default=str)

    # First hotel's contracts for initial dropdown
    first_hid = next(iter(sorted(contracts_index.keys(), key=int)))
    first_contracts = contracts_index.get(first_hid, contracts_index.get(int(first_hid), []))
    contract_opts = "".join(
        f'<option value="{i}">{c["checkin_date"]} | {c["category"]} | {c["board"]} ({c["n_scans"]} scans)</option>'
        for i, c in enumerate(first_contracts)
    )

    # Source strip for Tab 1
    tab1_sources = [
        {"name": "SalesOffice.Details + Orders", "rows": "~39K", "years": [2024, 2025],
         "year_range": "2024-2025", "update_freq": "Hourly", "status": "live"},
        {"name": "MED_SearchHotels", "rows": "7M", "years": [2020, 2021, 2022, 2023],
         "year_range": "2020-2023", "update_freq": "Static", "status": "archive"},
        {"name": "AI_Search_HotelData (Market)", "rows": "8.5M", "years": [2024, 2025],
         "year_range": "2024-2025", "update_freq": "Real-time", "status": "live"},
    ]

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> Select a hotel and contract (check-in date + room type + board). '
        'Charts load on-demand from live data. '
        '<strong>Chart 1</strong>: actual price over time. '
        '<strong>Chart 2</strong>: same data indexed by T (days to check-in). '
        '<strong>Chart 3</strong>: how far above/below settlement. '
        '<strong>Chart 4</strong>: premium vs competitor market average.'
        '</div>'

        + _source_strip_html(tab1_sources, "+ Events + Weather + Flights + Xotelo enrichments")

        + '<div id="cp-enrichments" class="cp-enrichments" style="display:none;"></div>'
        '<div id="cp-sources-used" class="cp-sources-used" style="display:none;"></div>'

        '<div class="ts-filters">'
        f'<label class="ts-label">Hotel<select id="cp-hotel" onchange="cpHotelChange()">{hotel_opts}</select></label>'
        f'<label class="ts-label">Contract<select id="cp-contract" onchange="cpLoadContract()">{contract_opts}</select></label>'
        '<label class="ts-label">Market Radius'
        '<select id="cp-radius">'
        '<option value="3">3 km</option>'
        '<option value="5" selected>5 km</option>'
        '<option value="10">10 km</option>'
        '</select></label>'
        '<label class="ts-label">Star Filter'
        '<select id="cp-stars">'
        '<option value="">All Stars</option>'
        '<option value="3">3-star</option>'
        '<option value="4">4-star</option>'
        '<option value="5">5-star</option>'
        '</select></label>'
        '</div>'

        '<div id="cp-meta" class="cp-meta" style="display:none;"></div>'
        '<div id="cp-loading" class="cp-loading" style="display:none;">'
        '<div class="cp-spinner"></div>Loading contract data...</div>'

        '<div class="ts-grid">'

        # Chart 1: Realized Price Path
        '<div class="ts-panel">'
        '<div class="ts-panel-title">1. Full Realized Price Path</div>'
        '<div class="ts-panel-desc">X: scan date. Y: price ($). '
        'The complete price history of this contract from first scan to check-in.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-realized"></canvas></div>'
        '</div>'

        # Chart 2: T-Space Path
        '<div class="ts-panel">'
        '<div class="ts-panel-title">2. Price Path in T-Space</div>'
        '<div class="ts-panel-desc">X: T days to check-in (90 to 0). Y: price ($). '
        'Options-style view: how price evolves as expiry approaches.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-tspace"></canvas></div>'
        '</div>'

        # Chart 3: Relative-to-Expiry
        '<div class="ts-panel">'
        '<div class="ts-panel-title">3. Relative-to-Expiry Path</div>'
        '<div class="ts-panel-desc">X: T days. Y: (price - S_exp) / S_exp %. '
        'Dashed lines at -5%, -10%, +5%, +10%. S_exp = settlement price at check-in.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-relexp"></canvas></div>'
        '</div>'

        # Chart 4: Market Premium
        '<div class="ts-panel">'
        '<div class="ts-panel-title">4. Market Premium Path</div>'
        '<div class="ts-panel-desc">X: T days. Y: premium vs market avg (%). '
        'Shows where our price sits vs competitor average at each lead time.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-premium"></canvas></div>'
        '</div>'

        '</div>'  # end .ts-grid
    )

    # JavaScript for Tab 1
    js = (
        '<script>\n'
        '(function() {\n'
        'const CP_CONTRACTS = ' + contracts_json + ';\n'
        'let _cpCh = {};\n'
        '\n'
        'const CP_OPTS = {\n'
        '  responsive: true, maintainAspectRatio: false,\n'
        '  plugins: { legend: { labels: { color: "#e4e7ec", padding: 14 } },\n'
        '             tooltip: { mode: "index", intersect: false } },\n'
        '};\n'
        'function cpYaxis(label) {\n'
        '  return { title: { display: true, text: label, color: "#8b90a0" },\n'
        '           ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } }; }\n'
        'const CP_X_DATE = {\n'
        '  title: { display: true, text: "Scan Date", color: "#8b90a0" },\n'
        '  ticks: { color: "#8b90a0", maxRotation: 45 }, grid: { color: "#2d3140" } };\n'
        'const CP_X_T = { reverse: true,\n'
        '  title: { display: true, text: "T (days to check-in)", color: "#8b90a0" },\n'
        '  ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } };\n'
        '\n'
        'window.cpHotelChange = function() {\n'
        '  const hotel = document.getElementById("cp-hotel").value;\n'
        '  const contracts = CP_CONTRACTS[hotel] || [];\n'
        '  const sel = document.getElementById("cp-contract");\n'
        '  sel.innerHTML = contracts.map((c, i) =>\n'
        '    `<option value="${i}">${c.checkin_date} | ${c.category} | ${c.board} (${c.n_scans} scans)</option>`\n'
        '  ).join("");\n'
        '  if (contracts.length > 0) window.cpLoadContract();\n'
        '};\n'
        '\n'
        'window.cpLoadContract = async function() {\n'
        '  const hotel = document.getElementById("cp-hotel").value;\n'
        '  const idx = parseInt(document.getElementById("cp-contract").value);\n'
        '  const contracts = CP_CONTRACTS[hotel] || [];\n'
        '  if (idx >= contracts.length) return;\n'
        '  const c = contracts[idx];\n'
        '  const radius = document.getElementById("cp-radius").value;\n'
        '  const stars = document.getElementById("cp-stars").value;\n'
        '\n'
        '  document.getElementById("cp-loading").style.display = "flex";\n'
        '  document.getElementById("cp-meta").style.display = "none";\n'
        '\n'
        '  const url = `/api/v1/salesoffice/charts/contract-data`\n'
        '    + `?hotel_id=${hotel}&checkin_date=${c.checkin_date}`\n'
        '    + `&category=${encodeURIComponent(c.category)}`\n'
        '    + `&board=${encodeURIComponent(c.board)}`\n'
        '    + `&radius_km=${radius}`\n'
        '    + (stars ? `&stars=${stars}` : "");\n'
        '\n'
        '  try {\n'
        '    const resp = await fetch(url);\n'
        '    const data = await resp.json();\n'
        '    cpRender(data);\n'
        '  } catch(e) {\n'
        '    console.error("Failed to load contract:", e);\n'
        '  } finally {\n'
        '    document.getElementById("cp-loading").style.display = "none";\n'
        '  }\n'
        '};\n'
        '\n'
        'function cpRender(data) {\n'
        '  const meta = data.contract_meta || {};\n'
        '  const metaEl = document.getElementById("cp-meta");\n'
        '  if (meta.hotel_name) {\n'
        '    metaEl.innerHTML = `<div class="cp-meta-row">'
        '<span class="cp-tag">${meta.hotel_name}</span>'
        '<span class="cp-tag">Check-in: ${meta.checkin_date}</span>'
        '<span class="cp-tag">${meta.category} | ${meta.board}</span>'
        '<span class="cp-tag">S_exp: $${meta.S_exp}</span>'
        '<span class="cp-tag">${meta.n_scans} scans</span>'
        '<span class="cp-tag">Range: $${meta.min_price} - $${meta.max_price}</span>'
        '</div>`;\n'
        '    metaEl.style.display = "block";\n'
        '  }\n'
        '\n'
        '  // Enrichment tags\n'
        '  const enr = data.enrichments || {};\n'
        '  const enrEl = document.getElementById("cp-enrichments");\n'
        '  let enrHtml = "";\n'
        '  if (enr.events) {\n'
        '    enrHtml += `<span class="cp-tag cp-tag--event">Event: ${enr.events.event_names.join(", ")} (${enr.events.impact_level})</span>`;\n'
        '  }\n'
        '  if (enr.weather) {\n'
        '    enrHtml += `<span class="cp-tag cp-tag--weather">${enr.weather.summary} (${enr.weather.adjustment_pct > 0 ? "+" : ""}${enr.weather.adjustment_pct}%)</span>`;\n'
        '  }\n'
        '  if (enr.flights) {\n'
        '    const fc = enr.flights.indicator === "HIGH" ? "cp-tag--flights-high" : enr.flights.indicator === "MEDIUM" ? "cp-tag--flights-med" : "cp-tag--flights-low";\n'
        '    enrHtml += `<span class="cp-tag ${fc}">Flights: ${enr.flights.indicator}${enr.flights.avg_price ? " ($" + enr.flights.avg_price + " avg)" : ""}</span>`;\n'
        '  }\n'
        '  if (enr.xotelo && enr.xotelo.latest_rates && enr.xotelo.latest_rates.length > 0) {\n'
        '    const r = enr.xotelo.latest_rates[0];\n'
        '    enrHtml += `<span class="cp-tag cp-tag--xotelo">OTA Median: $${r.median_rate || "N/A"}</span>`;\n'
        '  }\n'
        '  if (enrHtml) { enrEl.innerHTML = enrHtml; enrEl.style.display = "flex"; }\n'
        '  else { enrEl.style.display = "none"; }\n'
        '\n'
        '  // Sources used\n'
        '  const src = data.sources_used || {};\n'
        '  const srcEl = document.getElementById("cp-sources-used");\n'
        '  if (src.n_rows) {\n'
        '    let srcParts = [`<span class="cp-tag cp-tag--src">${src.n_rows} data points</span>`];\n'
        '    if (src.by_source) {\n'
        '      Object.entries(src.by_source).forEach(([k,v]) => {\n'
        '        srcParts.push(`<span class="cp-tag cp-tag--src">${k}: ${v} rows</span>`);\n'
        '      });\n'
        '    }\n'
        '    if (src.market) srcParts.push(`<span class="cp-tag cp-tag--src">${src.market}</span>`);\n'
        '    srcEl.innerHTML = srcParts.join("");\n'
        '    srcEl.style.display = "flex";\n'
        '  }\n'
        '\n'
        '  // Chart 1: Realized path\n'
        '  cpLine("ch-realized", data.chart1_realized_path.scan_dates,\n'
        '    [{ label: "Price ($)", data: data.chart1_realized_path.prices,\n'
        '       borderColor: "#818cf8", backgroundColor: "rgba(129,140,248,0.1)",\n'
        '       fill: true, tension: 0.3, pointRadius: 3 }],\n'
        '    CP_X_DATE, cpYaxis("Price ($)"));\n'
        '\n'
        '  // Chart 2: T-space\n'
        '  cpLine("ch-tspace", data.chart2_t_space_path.T_values,\n'
        '    [{ label: "Price ($)", data: data.chart2_t_space_path.prices,\n'
        '       borderColor: "#06b6d4", backgroundColor: "rgba(6,182,212,0.1)",\n'
        '       fill: true, tension: 0.3, pointRadius: 3 }],\n'
        '    CP_X_T, cpYaxis("Price ($)"));\n'
        '\n'
        '  // Chart 3: Relative-to-expiry with threshold lines\n'
        '  const relDs = [{ label: "Rel-to-Expiry %", data: data.chart3_rel_expiry.rel_pct,\n'
        '    borderColor: "#22c55e", backgroundColor: "rgba(34,197,94,0.1)",\n'
        '    fill: true, tension: 0.3, pointRadius: 3 }];\n'
        '  // Add threshold lines via annotation plugin or dataset hacks\n'
        '  const thresholds = data.chart3_rel_expiry.thresholds || [-10,-5,5,10];\n'
        '  const relLabels = data.chart3_rel_expiry.T_values;\n'
        '  thresholds.forEach(th => {\n'
        '    relDs.push({ label: `${th}%`, data: relLabels.map(() => th),\n'
        '      borderColor: th < 0 ? "rgba(239,68,68,0.4)" : "rgba(234,179,8,0.4)",\n'
        '      borderDash: [5,5], pointRadius: 0, borderWidth: 1, fill: false });\n'
        '  });\n'
        '  cpLine("ch-relexp", relLabels, relDs, CP_X_T, cpYaxis("% vs Settlement"));\n'
        '\n'
        '  // Chart 4: Market premium\n'
        '  const mp = data.chart4_market_premium;\n'
        '  if (mp.no_market_data) {\n'
        '    const canvas = document.getElementById("ch-premium");\n'
        '    if (_cpCh["ch-premium"]) { _cpCh["ch-premium"].destroy(); delete _cpCh["ch-premium"]; }\n'
        '    canvas.parentElement.innerHTML = \'<div class="no-data" style="padding:40px;text-align:center;">No market competitor data available for this contract. Try increasing the radius.</div>\';\n'
        '  } else {\n'
        '    cpLine("ch-premium", mp.T_values,\n'
        '      [{ label: "Premium vs Market %", data: mp.premium_pct,\n'
        '         borderColor: "#eab308", backgroundColor: "rgba(234,179,8,0.1)",\n'
        '         fill: true, tension: 0.3, pointRadius: 3, spanGaps: true },\n'
        '       { label: "0% (At Market)", data: mp.T_values.map(() => 0),\n'
        '         borderColor: "rgba(255,255,255,0.2)", borderDash: [5,5],\n'
        '         pointRadius: 0, borderWidth: 1, fill: false }],\n'
        '      CP_X_T, cpYaxis("Premium vs Market (%)"));\n'
        '  }\n'
        '}\n'
        '\n'
        'function cpLine(id, labels, datasets, xOpts, yOpts) {\n'
        '  if (_cpCh[id]) { _cpCh[id].destroy(); }\n'
        '  const ctx = document.getElementById(id);\n'
        '  if (!ctx) return;\n'
        '  _cpCh[id] = new Chart(ctx, {\n'
        '    type: "line",\n'
        '    data: { labels: labels, datasets: datasets },\n'
        '    options: { ...CP_OPTS, scales: { x: xOpts, y: yOpts } }\n'
        '  });\n'
        '}\n'
        '\n'
        '// Auto-load first contract on tab activation\n'
        'document.addEventListener("DOMContentLoaded", function() {\n'
        '  const contracts = CP_CONTRACTS[document.getElementById("cp-hotel").value] || [];\n'
        '  if (contracts.length > 0) window.cpLoadContract();\n'
        '});\n'
        '})();\n'
        '</script>\n'
    )

    return html + js


# ── Tab 2: 3-Year Term Structure (reuses term_structure_engine data) ─────


def _build_term_structure_tab(charts_data: dict, seasonality: dict | None = None) -> str:
    tab2 = charts_data.get("tab2", {})
    available = {hid: hdata for hid, hdata in tab2.items() if hdata.get("combos")}

    if not available:
        return (
            '<div class="no-data" style="padding:60px;text-align:center;">'
            'Term structure data is loading. Please refresh in ~30 seconds.</div>'
        )

    # Build hotel dropdown
    hotel_opts = "".join(
        f'<option value="{hid}">{HOTEL_NAMES.get(int(hid), f"Hotel {hid}")}</option>'
        for hid in sorted(available)
    )

    # First hotel's combos
    first_hid = next(iter(sorted(available)))
    first_combos = available[first_hid].get("combos", [])
    combo_opts = "".join(f'<option value="{c}">{c}</option>' for c in first_combos)

    # Serialize data for JS
    serializable = {str(hid): hdata for hid, hdata in available.items()}
    json_data = json.dumps(serializable, default=str)

    # Source strip for Tab 2
    attr = charts_data.get("source_attribution", {})
    tab2_sources = attr.get("sources", [])

    # Seasonality bar HTML
    seasonality_html = ""
    if seasonality and seasonality.get("months"):
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        months = seasonality["months"]
        cells = ""
        for m in month_names:
            val = months.get(m, 1.0)
            # Color: green for peak (>1.0), red for trough (<1.0)
            if val >= 1.05:
                bg = f"rgba(34,197,94,{min((val-1.0)*4, 0.6):.2f})"
            elif val <= 0.95:
                bg = f"rgba(239,68,68,{min((1.0-val)*4, 0.6):.2f})"
            else:
                bg = "transparent"
            cells += f'<td style="background:{bg};text-align:center;padding:6px 8px;">{val:.3f}</td>'

        seasonality_html = (
            '<div class="ts-panel ts-panel--full">'
            '<div class="ts-panel-title">Miami Monthly Demand Index</div>'
            '<div class="ts-panel-desc">Seasonal multiplier: 1.0 = average month. '
            '<span class="savings">Green = peak demand</span>, '
            '<span class="premium">Red = low demand</span>. '
            f'Source: {seasonality.get("source", "Kaggle Hotel Booking Demand")}.</div>'
            '<div class="table-wrap"><table class="heatmap-table"><thead><tr>'
            + "".join(f'<th>{m}</th>' for m in month_names)
            + '</tr></thead><tbody><tr>' + cells + '</tr></tbody></table></div>'
            '</div>'
        )

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> Select a hotel and room/board combination. '
        'All 5 charts update instantly. '
        '<span style="color:#6366f1;font-weight:600;">Indigo = 2023</span> &nbsp;'
        '<span style="color:#06b6d4;font-weight:600;">Cyan = 2024</span> &nbsp;'
        '<span style="color:#22c55e;font-weight:600;">Green = 2025</span>. '
        'Compare curve shapes to spot structural changes in price behavior by year.</div>'

        + _source_strip_html(tab2_sources)

        + '<div class="ts-filters">'
        f'<label class="ts-label">Hotel<select id="ts-hotel" onchange="tsHotelChange()">{hotel_opts}</select></label>'
        f'<label class="ts-label">Room / Board<select id="ts-combo" onchange="tsRender()">{combo_opts}</select></label>'
        '</div>'

        '<div class="ts-grid">'

        # Chart 5
        '<div class="ts-panel">'
        '<div class="ts-panel-title">5. Avg Daily % Change by T</div>'
        '<div class="ts-panel-desc">Average daily price change at each lead time. '
        'Where 2025 diverges from 2023/2024 marks the structural shift point.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-delta"></canvas></div>'
        '</div>'

        # Chart 6
        '<div class="ts-panel">'
        '<div class="ts-panel-title">6. Cumulative Normalized Path (base=100 at T=90)</div>'
        '<div class="ts-panel-desc">Compounded price path from 90 days out to expiry. '
        'Flat then spike = last-minute squeeze. Linear = steady pressure.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-cumul"></canvas></div>'
        '</div>'

        # Chart 7
        '<div class="ts-panel">'
        '<div class="ts-panel-title">7. Realized Volatility by T</div>'
        '<div class="ts-panel-desc">Std dev of daily % changes. '
        'If 2025 spikes earlier, instability has shifted forward in the booking window.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-vol"></canvas></div>'
        '</div>'

        # Chart 8
        '<div class="ts-panel">'
        '<div class="ts-panel-title">8. % Up-Days by T</div>'
        '<div class="ts-panel-desc">Fraction of days where price rose. '
        'At T=7: if 2025 > 70% vs 2023 < 55%, abnormal upward pressure is confirmed.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-pctup"></canvas></div>'
        '</div>'

        # Chart 9 — heatmap, full width
        '<div class="ts-panel ts-panel--full">'
        '<div class="ts-panel-title">9. Heatmap: Avg Daily % Change (T x Year)</div>'
        '<div class="ts-panel-desc">Same data as Chart 5 as a color matrix. '
        '<span class="savings">Green</span> = prices falling (buy opportunity). '
        '<span class="premium">Red</span> = prices rising.</div>'
        '<div id="ch-heatmap" class="table-wrap"></div>'
        '</div>'

        + seasonality_html

        + '</div>'  # end .ts-grid
    )

    # JavaScript for Tab 2
    js = (
        '<script>\n'
        '(function() {\n'
        'const TS_DATA = ' + json_data + ';\n'
        'const YEAR_COLORS = {"2023":"#6366f1","2024":"#06b6d4","2025":"#22c55e"};\n'
        'const YEARS = ["2023","2024","2025"];\n'
        'const TS_OPTS = {\n'
        '  responsive: true, maintainAspectRatio: false,\n'
        '  plugins: { legend: { labels: { color: "#e4e7ec", padding: 14 } },\n'
        '             tooltip: { mode: "index", intersect: false } },\n'
        '};\n'
        'const TS_X = { reverse: true,\n'
        '  title: { display: true, text: "T (days to check-in)", color: "#8b90a0" },\n'
        '  ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } };\n'
        'function tsY(label) {\n'
        '  return { title: { display: true, text: label, color: "#8b90a0" },\n'
        '           ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } }; }\n'
        'let _tsCh = {};\n'
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
        '  tsLine("ch-delta", T, d.avg_delta, "Avg Daily \\u0394%");\n'
        '  tsLine("ch-cumul", T, d.cumulative, "Normalized Price");\n'
        '  tsLine("ch-vol",   T, d.volatility, "Std Dev \\u0394%");\n'
        '  tsLine("ch-pctup", T, d.pct_up, "% Days Positive");\n'
        '  tsHeatmap("ch-heatmap", d.heatmap);\n'
        '};\n'
        '\n'
        'function tsLine(id, tVals, yearData, yLabel) {\n'
        '  if (_tsCh[id]) { _tsCh[id].destroy(); }\n'
        '  const ctx = document.getElementById(id);\n'
        '  if (!ctx) return;\n'
        '  _tsCh[id] = new Chart(ctx, {\n'
        '    type: "line",\n'
        '    data: { labels: tVals,\n'
        '      datasets: YEARS.map(yr => ({\n'
        '        label: yr, data: (yearData || {})[yr] || [],\n'
        '        borderColor: YEAR_COLORS[yr], backgroundColor: "transparent",\n'
        '        tension: 0.3, pointRadius: 4, pointHoverRadius: 6,\n'
        '        spanGaps: true, borderWidth: 2 })) },\n'
        '    options: { ...TS_OPTS, scales: { x: TS_X, y: tsY(yLabel) } }\n'
        '  });\n'
        '}\n'
        '\n'
        'function tsHeatmap(id, hmData) {\n'
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
        '  // Defer render until tab is visible\n'
        '  const obs = new MutationObserver(function() {\n'
        '    const tab = document.getElementById("tab-ts3yr");\n'
        '    if (tab && tab.classList.contains("active") && document.getElementById("ch-delta")) {\n'
        '      window.tsRender();\n'
        '    }\n'
        '  });\n'
        '  const tab = document.getElementById("tab-ts3yr");\n'
        '  if (tab) obs.observe(tab, { attributes: true, attributeFilter: ["class"] });\n'
        '});\n'
        '})();\n'
        '</script>\n'
    )

    return html + js


# ── Tab 3: Expiry-Relative Opportunity Stats ─────────────────────────────


def _build_opportunity_stats_tab(charts_data: dict, velocity: dict | None = None) -> str:
    tab3 = charts_data.get("tab3", {})

    if not tab3:
        return (
            '<div class="no-data" style="padding:60px;text-align:center;">'
            'Opportunity statistics data is loading. Please refresh in ~30 seconds.</div>'
        )

    # Build hotel dropdown
    hotel_opts = "".join(
        f'<option value="{hid}">{HOTEL_NAMES.get(int(hid), f"Hotel {hid}")}</option>'
        for hid in sorted(tab3.keys(), key=int)
    )

    # Serialize data for JS
    serializable = {str(hid): hdata for hid, hdata in tab3.items()}
    json_data = json.dumps(serializable, default=str)

    # Source strip for Tab 3
    attr = charts_data.get("source_attribution", {})
    tab3_sources = attr.get("sources", [])

    # Velocity data as JSON for JS
    velocity_json = json.dumps(velocity or {}, default=str)

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> These charts analyze completed contracts from the last 6 months. '
        'They reveal how often and by how much contract prices dipped below their final settlement price '
        'during the booking window. Deeper dips = larger buying opportunities that existed in the market. '
        '<span class="savings">Green/negative</span> = price was below settlement (potential buy). '
        '<span class="premium">Red/positive</span> = price was above settlement.</div>'

        + _source_strip_html(tab3_sources, "+ RoomPriceUpdateLog (82K events)")

        + '<div class="ts-filters">'
        f'<label class="ts-label">Hotel<select id="opp-hotel" onchange="oppRender()">{hotel_opts}</select></label>'
        '</div>'

        # Velocity KPIs
        '<div id="opp-velocity" class="kpi-row">'
        '<div class="kpi-mini"><span class="kpi-mini-value" id="vel-updates">-</span><span class="kpi-mini-label">Price Updates</span></div>'
        '<div class="kpi-mini"><span class="kpi-mini-value" id="vel-rooms">-</span><span class="kpi-mini-label">Rooms Tracked</span></div>'
        '<div class="kpi-mini"><span class="kpi-mini-value" id="vel-avg">-</span><span class="kpi-mini-label">Avg Price</span></div>'
        '<div class="kpi-mini"><span class="kpi-mini-value" id="vel-stdev">-</span><span class="kpi-mini-label">Price Std Dev</span></div>'
        '<div class="kpi-mini kpi-mini--src"><span class="kpi-mini-label">Source: RoomPriceUpdateLog</span></div>'
        '</div>'

        '<div class="ts-grid">'

        # Chart 10
        '<div class="ts-panel ts-panel--full">'
        '<div class="ts-panel-title">10. Distribution of Min Relative-to-Expiry (by Year)</div>'
        '<div class="ts-panel-desc">Histogram: for each completed contract, the deepest drawdown below settlement. '
        'Contracts in the &lt;-10% bucket represented large pre-expiry buying opportunities.</div>'
        '<div class="ts-canvas-wrap ts-canvas-wrap--bar"><canvas id="ch-minrel-dist"></canvas></div>'
        '</div>'

        # Chart 11
        '<div class="ts-panel">'
        '<div class="ts-panel-title">11. Breach Rates: % Contracts Below Threshold</div>'
        '<div class="ts-panel-desc">What % of contracts dipped below -5% and -10% of settlement, by year. '
        'Higher bars = more buying opportunities existed.</div>'
        '<div class="ts-canvas-wrap ts-canvas-wrap--bar"><canvas id="ch-breach-rates"></canvas></div>'
        '</div>'

        # Chart 12
        '<div class="ts-panel">'
        '<div class="ts-panel-title">12. Breach Duration & Crossing Events</div>'
        '<div class="ts-panel-desc">Total scan-days below threshold vs number of crossing events. '
        'Many short events = volatile. Few long ones = sustained discount periods.</div>'
        '<div class="ts-canvas-wrap ts-canvas-wrap--bar"><canvas id="ch-breach-counts"></canvas></div>'
        '</div>'

        '</div>'  # end .ts-grid
    )

    # JavaScript for Tab 3
    js = (
        '<script>\n'
        '(function() {\n'
        'const OPP_DATA = ' + json_data + ';\n'
        'const VEL_DATA = ' + velocity_json + ';\n'
        'const YEAR_COLORS = {"2023":"#6366f1","2024":"#06b6d4","2025":"#22c55e"};\n'
        'const YEARS = ["2023","2024","2025"];\n'
        'const OPP_OPTS = {\n'
        '  responsive: true, maintainAspectRatio: false,\n'
        '  plugins: { legend: { labels: { color: "#e4e7ec", padding: 14 } },\n'
        '             tooltip: { mode: "index", intersect: false } },\n'
        '};\n'
        'let _oppCh = {};\n'
        '\n'
        'window.oppRender = function() {\n'
        '  const hotel = document.getElementById("opp-hotel").value;\n'
        '  const d = OPP_DATA[hotel];\n'
        '  if (!d) return;\n'
        '\n'
        '  // Update velocity KPIs\n'
        '  const vel = VEL_DATA[hotel] || {};\n'
        '  document.getElementById("vel-updates").textContent = vel.total_updates ? vel.total_updates.toLocaleString() : "-";\n'
        '  document.getElementById("vel-rooms").textContent = vel.unique_rooms ? vel.unique_rooms.toLocaleString() : "-";\n'
        '  document.getElementById("vel-avg").textContent = vel.avg_price ? "$" + vel.avg_price.toLocaleString() : "-";\n'
        '  document.getElementById("vel-stdev").textContent = vel.price_stdev ? "$" + vel.price_stdev.toFixed(1) : "-";\n'
        '\n'
        '  // Chart 10: min_rel distribution histogram\n'
        '  const mrd = d.min_rel_dist;\n'
        '  if (_oppCh["ch-minrel-dist"]) _oppCh["ch-minrel-dist"].destroy();\n'
        '  const ctx10 = document.getElementById("ch-minrel-dist");\n'
        '  if (ctx10 && mrd) {\n'
        '    _oppCh["ch-minrel-dist"] = new Chart(ctx10, {\n'
        '      type: "bar",\n'
        '      data: { labels: mrd.buckets || [],\n'
        '        datasets: YEARS.map(yr => ({\n'
        '          label: yr, data: mrd[yr] || [],\n'
        '          backgroundColor: YEAR_COLORS[yr] + "99",\n'
        '          borderColor: YEAR_COLORS[yr], borderWidth: 1 })) },\n'
        '      options: { ...OPP_OPTS,\n'
        '        scales: {\n'
        '          x: { title: { display: true, text: "Min Rel-to-Expiry Bucket", color: "#8b90a0" },\n'
        '               ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } },\n'
        '          y: { title: { display: true, text: "# Contracts", color: "#8b90a0" },\n'
        '               ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } } } }\n'
        '    });\n'
        '  }\n'
        '\n'
        '  // Chart 11: breach rates by year\n'
        '  const br = d.breach_rates;\n'
        '  if (_oppCh["ch-breach-rates"]) _oppCh["ch-breach-rates"].destroy();\n'
        '  const ctx11 = document.getElementById("ch-breach-rates");\n'
        '  if (ctx11 && br && br.by_year) {\n'
        '    const yrs = Object.keys(br.by_year).sort();\n'
        '    _oppCh["ch-breach-rates"] = new Chart(ctx11, {\n'
        '      type: "bar",\n'
        '      data: { labels: yrs,\n'
        '        datasets: [\n'
        '          { label: "Below -5%", data: yrs.map(y => br.by_year[y].pct_5),\n'
        '            backgroundColor: "rgba(234,179,8,0.7)", borderColor: "#eab308", borderWidth: 1 },\n'
        '          { label: "Below -10%", data: yrs.map(y => br.by_year[y].pct_10),\n'
        '            backgroundColor: "rgba(239,68,68,0.7)", borderColor: "#ef4444", borderWidth: 1 }\n'
        '        ] },\n'
        '      options: { ...OPP_OPTS,\n'
        '        scales: {\n'
        '          x: { ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } },\n'
        '          y: { title: { display: true, text: "% of Contracts", color: "#8b90a0" },\n'
        '               ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } } } }\n'
        '    });\n'
        '  }\n'
        '\n'
        '  // Chart 12: breach counts by year\n'
        '  const tc = d.threshold_counts;\n'
        '  if (_oppCh["ch-breach-counts"]) _oppCh["ch-breach-counts"].destroy();\n'
        '  const ctx12 = document.getElementById("ch-breach-counts");\n'
        '  if (ctx12 && tc && tc.by_year) {\n'
        '    const yrs = Object.keys(tc.by_year).sort();\n'
        '    _oppCh["ch-breach-counts"] = new Chart(ctx12, {\n'
        '      type: "bar",\n'
        '      data: { labels: yrs,\n'
        '        datasets: [\n'
        '          { label: "Days < -5%", data: yrs.map(y => tc.by_year[y].days_5),\n'
        '            backgroundColor: "rgba(234,179,8,0.6)", stack: "days" },\n'
        '          { label: "Days < -10%", data: yrs.map(y => tc.by_year[y].days_10),\n'
        '            backgroundColor: "rgba(239,68,68,0.6)", stack: "days" },\n'
        '          { label: "Crossings -5%", data: yrs.map(y => tc.by_year[y].events_5),\n'
        '            backgroundColor: "rgba(6,182,212,0.6)", stack: "events" },\n'
        '          { label: "Crossings -10%", data: yrs.map(y => tc.by_year[y].events_10),\n'
        '            backgroundColor: "rgba(99,102,241,0.6)", stack: "events" }\n'
        '        ] },\n'
        '      options: { ...OPP_OPTS,\n'
        '        scales: {\n'
        '          x: { stacked: true, ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } },\n'
        '          y: { stacked: true,\n'
        '               title: { display: true, text: "Count", color: "#8b90a0" },\n'
        '               ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } } } }\n'
        '    });\n'
        '  }\n'
        '};\n'
        '\n'
        'document.addEventListener("DOMContentLoaded", function() {\n'
        '  const obs = new MutationObserver(function() {\n'
        '    const tab = document.getElementById("tab-opportunity");\n'
        '    if (tab && tab.classList.contains("active") && document.getElementById("ch-minrel-dist")) {\n'
        '      window.oppRender();\n'
        '    }\n'
        '  });\n'
        '  const tab = document.getElementById("tab-opportunity");\n'
        '  if (tab) obs.observe(tab, { attributes: true, attributeFilter: ["class"] });\n'
        '});\n'
        '})();\n'
        '</script>\n'
    )

    return html + js
