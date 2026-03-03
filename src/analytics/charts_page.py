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
        return _empty_page(now)

    tab1 = _build_contract_path_tab(charts_data)
    tab2 = _build_term_structure_tab(charts_data)
    tab3 = _build_opportunity_stats_tab(charts_data)
    return _wrap_page(now, tab1, tab2, tab3)


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

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> Select a hotel and contract (check-in date + room type + board). '
        'Charts load on-demand from live data. '
        '<strong>Chart 1</strong>: actual price over time. '
        '<strong>Chart 2</strong>: same data indexed by T (days to check-in). '
        '<strong>Chart 3</strong>: how far above/below settlement. '
        '<strong>Chart 4</strong>: premium vs competitor market average.'
        '</div>'

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


def _build_term_structure_tab(charts_data: dict) -> str:
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

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> Select a hotel and room/board combination. '
        'All 5 charts update instantly. '
        '<span style="color:#6366f1;font-weight:600;">Indigo = 2023</span> &nbsp;'
        '<span style="color:#06b6d4;font-weight:600;">Cyan = 2024</span> &nbsp;'
        '<span style="color:#22c55e;font-weight:600;">Green = 2025</span>. '
        'Compare curve shapes to spot structural changes in price behavior by year.</div>'

        '<div class="ts-filters">'
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

        '</div>'  # end .ts-grid
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


def _build_opportunity_stats_tab(charts_data: dict) -> str:
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

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> These charts analyze completed contracts from the last 6 months. '
        'They reveal how often and by how much contract prices dipped below their final settlement price '
        'during the booking window. Deeper dips = larger buying opportunities that existed in the market. '
        '<span class="savings">Green/negative</span> = price was below settlement (potential buy). '
        '<span class="premium">Red/positive</span> = price was above settlement.</div>'

        '<div class="ts-filters">'
        f'<label class="ts-label">Hotel<select id="opp-hotel" onchange="oppRender()">{hotel_opts}</select></label>'
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


# ── Page wrapper ──────────────────────────────────────────────────────────


def _empty_page(now: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Chart Pack</title></head>
<body style="background:#0f1117;color:#e4e7ec;font-family:sans-serif;padding:40px;text-align:center;">
<h1>No Chart Data Available</h1>
<p>The data query is still loading. Please try again in a moment.</p>
<p style="color:#8b90a0;font-size:0.85em;">Generated {now}</p>
</body></html>"""


def _wrap_page(now: str, tab1: str, tab2: str, tab3: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medici — Chart Pack</title>
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

/* Shared */
.hotel-header{{font-size:1.2em;font-weight:700;color:var(--accent2);margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--border);}}
.explainer{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin:0 0 20px;font-size:0.9em;color:var(--text-dim);}}
.explainer strong{{color:var(--text);}}
.savings{{color:var(--green);font-weight:600;}}
.premium{{color:var(--red);font-weight:600;}}
.no-data{{color:var(--text-dim);font-style:italic;padding:20px 0;}}

/* Tables */
.table-wrap{{overflow-x:auto;margin-bottom:20px;}}
.heatmap-table{{width:100%;border-collapse:collapse;font-size:0.85em;}}
.heatmap-table th{{background:var(--surface2);padding:10px 12px;text-align:center;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);border-right:1px solid var(--border);white-space:nowrap;}}
.heatmap-table td{{padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);border-right:1px solid var(--border);font-size:0.88em;color:var(--text);}}
.heatmap-table tbody tr:hover td{{filter:brightness(1.2);}}
.t-cell{{font-weight:600;color:var(--accent2);text-align:right;background:var(--surface)!important;}}
.empty-cell{{color:var(--text-dim);}}

/* Filters & Charts */
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

/* Contract meta tags (Tab 1) */
.cp-meta{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 18px;margin-bottom:16px;}}
.cp-meta-row{{display:flex;flex-wrap:wrap;gap:10px;}}
.cp-tag{{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 12px;font-size:0.82em;font-weight:500;}}
.cp-loading{{display:none;align-items:center;justify-content:center;gap:12px;padding:40px;color:var(--text-dim);}}
.cp-spinner{{width:24px;height:24px;border:3px solid var(--border);border-top:3px solid var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}

.footer{{text-align:center;padding:32px 0;color:var(--text-dim);font-size:0.85em;border-top:1px solid var(--border);margin-top:24px;}}
</style>
</head>
<body>

<div class="header">
<div class="container">
    <h1>Chart Pack — Price Behavior Analysis</h1>
    <p>Contract-level deep dive, multi-year term structure, and opportunity statistics</p>
    <div class="nav-links">
        <a href="/api/v1/salesoffice/insights">Insights</a>
        <a href="/api/v1/salesoffice/options">Options</a>
        <a href="/api/v1/salesoffice/yoy">Year-over-Year</a>
        <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
        <a href="/api/v1/salesoffice/info">Documentation</a>
    </div>
</div>
</div>

<div class="tab-bar">
<div class="container">
    <button class="tab-btn active" onclick="switchTab('contract',this)">Room/Contract Path</button>
    <button class="tab-btn" onclick="switchTab('ts3yr',this)">3-Year Term Structure</button>
    <button class="tab-btn" onclick="switchTab('opportunity',this)">Expiry-Relative Stats</button>
</div>
</div>

<div class="container">
    <div id="tab-contract" class="tab-content active">{tab1}</div>
    <div id="tab-ts3yr" class="tab-content">{tab2}</div>
    <div id="tab-opportunity" class="tab-content">{tab3}</div>
</div>

<div class="footer">
    <p>Medici Price Prediction Engine &mdash; Chart Pack &mdash; Generated {now}</p>
</div>

<script>
function switchTab(name, btn) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    btn.classList.add('active');
    // Trigger render for tabs that defer rendering
    if (name === 'ts3yr' && typeof tsRender === 'function') {{ tsRender(); }}
    if (name === 'opportunity' && typeof oppRender === 'function') {{ oppRender(); }}
}}
</script>
</body>
</html>"""
