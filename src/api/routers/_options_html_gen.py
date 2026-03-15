"""HTML generation functions for the options dashboard."""
from __future__ import annotations

import json

def _generate_html(analysis: dict) -> str:
    """Generate the HTML dashboard from analysis results."""
    from src.analytics.report import generate_report
    from config.settings import DATA_DIR

    report_path = generate_report(analysis)

    # Read and return the HTML
    return report_path.read_text(encoding="utf-8")


def _html_escape(s: str) -> str:
    """Minimal HTML escaping for user-provided strings."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _generate_options_async_html(t_days: int | None = None, signal: str | None = None) -> str:
    """Generate a fast shell that loads options data asynchronously from the JSON API."""
    initial_t_days = "null" if t_days is None else str(int(t_days))
    initial_signal = json.dumps((signal or "").strip().upper())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SalesOffice — Options Board</title>
<style>
  :root {{
    --bg: #f8fafc;
    --surface: #ffffff;
    --surface-2: #eef2ff;
    --border: #e2e8f0;
    --text: #0f172a;
    --text-dim: #64748b;
    --call: #16a34a;
    --put: #dc2626;
    --neutral: #64748b;
    --accent: #4f46e5;
    --accent-2: #7c3aed;
    --warn: #f59e0b;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .page {{ max-width: 1500px; margin: 0 auto; padding: 20px; }}
  .hero {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 18px; }}
  .hero h1 {{ margin: 0 0 6px; font-size: 30px; }}
  .hero p {{ margin: 0; color: var(--text-dim); max-width: 800px; }}
  .hero-actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .hero-actions a, .hero-actions button {{ border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: 10px; padding: 10px 14px; text-decoration: none; cursor: pointer; font-weight: 600; }}
  .hero-actions button.primary {{ background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%); color: #fff; border: 0; }}
  .status-bar {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
  .status-chip {{ background: var(--surface); border: 1px solid var(--border); border-radius: 999px; padding: 8px 12px; color: var(--text-dim); }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px; box-shadow: 0 8px 20px rgba(15, 23, 42, .04); }}
  .card .label {{ color: var(--text-dim); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
  .card .value {{ margin-top: 6px; font-size: 28px; font-weight: 700; }}
  .controls {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 14px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; }}
  .controls label {{ font-size: 12px; color: var(--text-dim); display: flex; flex-direction: column; gap: 6px; }}
  .controls input, .controls select {{ min-width: 140px; border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; background: #fff; color: var(--text); }}
  .controls-note {{ width: 100%; margin-top: 4px; color: var(--text-dim); font-size: 12px; }}
  .controls .checkbox-label {{ flex-direction: row; align-items: center; gap: 8px; margin-top: 18px; color: var(--text); font-size: 13px; }}
  .controls .checkbox-label input {{ min-width: auto; width: 16px; height: 16px; padding: 0; }}
  .source-badges {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .source-badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 8px; background: var(--surface-2); color: var(--accent); font-size: 11px; font-weight: 700; }}
  .status-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
  .status-panel.loading {{ border-color: #c7d2fe; background: #eef2ff; }}
  .status-panel.warning {{ border-color: #fed7aa; background: #fff7ed; }}
  .status-panel.error {{ border-color: #fecaca; background: #fef2f2; }}
  .status-title {{ font-weight: 700; margin-bottom: 6px; }}
  .status-text {{ color: var(--text-dim); }}
  .status-meta {{ margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap; color: var(--text-dim); font-size: 12px; }}
  .table-shell {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }}
  .table-scroll {{ overflow: auto; max-height: 70vh; }}
  table {{ width: 100%; border-collapse: collapse; min-width: 1100px; }}
  thead th {{ position: sticky; top: 0; z-index: 1; background: #f8fafc; color: var(--text-dim); text-align: left; font-size: 12px; font-weight: 700; letter-spacing: .03em; padding: 12px; border-bottom: 1px solid var(--border); }}
  tbody td {{ padding: 12px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tbody tr:hover {{ background: #f8fafc; }}
  .pill {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 700; }}
  .pill.call {{ background: rgba(22, 163, 74, .12); color: var(--call); }}
  .pill.put {{ background: rgba(220, 38, 38, .12); color: var(--put); }}
  .pill.neutral {{ background: rgba(100, 116, 139, .12); color: var(--neutral); }}
  .quality {{ font-weight: 700; }}
  .quality.high {{ color: var(--call); }}
  .quality.medium {{ color: var(--warn); }}
  .quality.low {{ color: var(--put); }}
  .muted {{ color: var(--text-dim); }}
  .num.pos {{ color: var(--call); font-weight: 700; }}
  .num.neg {{ color: var(--put); font-weight: 700; }}
  .row-actions button {{ border: 1px solid var(--border); background: #fff; border-radius: 8px; padding: 8px 10px; cursor: pointer; font-weight: 600; }}
  .pager {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px; border-top: 1px solid var(--border); background: #f8fafc; flex-wrap: wrap; }}
  .pager .buttons {{ display: flex; gap: 8px; }}
  .pager button {{ border: 1px solid var(--border); background: #fff; border-radius: 10px; padding: 10px 14px; cursor: pointer; font-weight: 600; }}
  .pager button:disabled {{ opacity: .45; cursor: not-allowed; }}
  .empty {{ padding: 28px; text-align: center; color: var(--text-dim); }}
  .modal-backdrop {{ position: fixed; inset: 0; background: rgba(15, 23, 42, .55); display: none; align-items: center; justify-content: center; padding: 20px; }}
  .modal-backdrop.open {{ display: flex; }}
  .modal {{ width: min(760px, 100%); background: var(--surface); border-radius: 16px; box-shadow: 0 30px 60px rgba(15,23,42,.25); overflow: hidden; }}
  .modal-head {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 18px; border-bottom: 1px solid var(--border); }}
  .modal-head h2 {{ margin: 0; font-size: 20px; }}
  .modal-head button {{ border: 0; background: transparent; font-size: 28px; cursor: pointer; color: var(--text-dim); }}
  .modal-body {{ padding: 18px; }}
  .detail-chart-wrap {{ margin-bottom: 18px; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: #fbfdff; }}
  .detail-chart-wrap canvas {{ width: 100%; height: 260px; display: block; }}
  .chart-toolbar {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }}
  .chart-toolbar label {{ font-size: 12px; color: var(--text-dim); display: flex; flex-direction: column; gap: 6px; }}
  .chart-toolbar select {{ min-width: 160px; border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; background: #fff; color: var(--text); }}
  .chart-toolbar .toggle-row {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding-top: 18px; }}
  .chart-toolbar .toggle-row label {{ flex-direction: row; align-items: center; gap: 6px; color: var(--text); font-size: 13px; }}
  .chart-toolbar .source-toggle-group {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding-top: 18px; }}
  .chart-toolbar .source-toggle-group label {{ flex-direction: row; align-items: center; gap: 6px; color: var(--text); font-size: 13px; }}
  .chart-legend {{ display: flex; gap: 12px; flex-wrap: wrap; color: var(--text-dim); font-size: 12px; margin-top: 8px; }}
  .legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
  .legend-swatch {{ width: 14px; height: 3px; border-radius: 999px; }}
  .detail-chart-title {{ font-size: 14px; font-weight: 700; margin: 0 0 10px; }}
  .detail-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }}
  .detail-card {{ border: 1px solid var(--border); border-radius: 12px; padding: 12px; background: #fafafa; }}
  .detail-card .k {{ font-size: 12px; color: var(--text-dim); margin-bottom: 6px; }}
  .detail-card .v {{ font-size: 20px; font-weight: 700; }}
  .detail-section {{ margin-top: 14px; }}
  .detail-section h3 {{ margin: 0 0 8px; font-size: 14px; }}
  .detail-list {{ margin: 0; padding-left: 18px; color: var(--text-dim); }}
  .detail-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .detail-table th, .detail-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
  .detail-table th {{ color: var(--text-dim); font-weight: 700; background: #f8fafc; }}
  .detail-grid-2 {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }}
  .empty-mini {{ color: var(--text-dim); font-size: 12px; }}
  @media (max-width: 900px) {{
    .hero h1 {{ font-size: 24px; }}
    .controls {{ align-items: stretch; }}
    .controls label {{ width: 100%; }}
    .controls input, .controls select {{ width: 100%; }}
    .detail-grid-2 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="hero">
    <div>
      <h1>Options Trading Signals</h1>
      <p>Fast shell mode: the page opens immediately, then loads cached analytics asynchronously without changing the underlying prediction model.</p>
    </div>
    <div class="hero-actions">
      <button class="primary" id="refresh-btn" type="button">Refresh data</button>
      <a href="/api/v1/salesoffice/options?profile=lite">JSON API</a>
      <a href="/api/v1/salesoffice/options/legend">Legend</a>
      <a href="/api/v1/salesoffice/home">Home</a>
    </div>
  </div>

  <div class="status-bar">
    <div class="status-chip">Delivery: Async shell</div>
    <div class="status-chip" id="run-ts-chip">Last run: --</div>
    <div class="status-chip" id="cache-chip">Cache: checking...</div>
    <div class="status-chip" id="rows-chip">Rows: --</div>
  </div>

  <div class="cards">
    <div class="card"><div class="label">Total Rows</div><div class="value" id="stat-total">--</div></div>
    <div class="card"><div class="label">CALL on page</div><div class="value" id="stat-call">--</div></div>
    <div class="card"><div class="label">PUT on page</div><div class="value" id="stat-put">--</div></div>
    <div class="card"><div class="label">Neutral on page</div><div class="value" id="stat-neutral">--</div></div>
  </div>

  <div class="controls">
    <label>
      Search current page
      <input id="search-input" type="text" placeholder="Hotel, category, board...">
    </label>
    <label>
      Signal
      <select id="signal-filter">
        <option value="">All</option>
        <option value="CALL">CALL</option>
        <option value="PUT">PUT</option>
        <option value="NEXT_PUT">NEXT PUT (scan drop)</option>
        <option value="NEUTRAL">NEUTRAL</option>
      </select>
    </label>
    <label>
      Prediction engine
      <select id="source-filter">
        <option value="">All sources</option>
        <option value="salesoffice">SalesOffice DB</option>
        <option value="forward_curve">Forward curve</option>
        <option value="med_search_hotels">MED Search Hotels</option>
        <option value="historical_pattern">Historical pattern</option>
        <option value="ml_forecast">ML forecast</option>
        <option value="room_price_update_log">Room Price Update Log</option>
        <option value="hotel_booking_dataset">Hotel Booking Demand Dataset</option>
        <option value="cancellation_data">Booking Cancellations</option>
        <option value="kiwi_flights">Kiwi Flights</option>
        <option value="open_meteo">Open-Meteo Weather</option>
        <option value="miami_events_hardcoded">Miami Major Events</option>
        <option value="seatgeek">SeatGeek Events</option>
        <option value="ai_search_hotel_data">AI Search Hotel Data</option>
        <option value="search_results_poll_log">Search Results Poll Log</option>
        <option value="med_prebook">MED PreBook</option>
        <option value="tbo_hotels">TBO Hotels Dataset</option>
        <option value="ota_brightdata_exports">OTA Market Rates</option>
        <option value="destinations_geo">Destinations &amp; Hotel Geo Data</option>
        <option value="salesoffice_log">SalesOffice Action Log</option>
      </select>
    </label>
    <label>
      Source view
      <select id="source-mode-filter">
        <option value="all">All predictions</option>
        <option value="filter">Filter rows by source</option>
        <option value="source_only">Source-only prediction</option>
      </select>
    </label>
    <label>
      Horizon days
      <input id="t-days-input" type="number" min="1" step="1" placeholder="all">
    </label>
    <label>
      Page size
      <select id="limit-select">
        <option value="50">50</option>
        <option value="100" selected>100</option>
        <option value="200">200</option>
      </select>
    </label>
    <div class="controls-note">Selecting a prediction engine now switches to Source-only prediction by default, so changing the source updates the forecast immediately. Use Filter rows by source only when you want to keep the ensemble forecast and just narrow the list.</div>
  </div>

  <div class="status-panel loading" id="status-panel">
    <div class="status-title">Preparing options dataset</div>
    <div class="status-text" id="status-text">Connecting to the cached analytics API...</div>
    <div class="status-meta" id="status-meta"></div>
  </div>

  <div class="table-shell">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Hotel</th>
            <th>Category</th>
            <th>Board</th>
            <th>Check-in</th>
            <th>Signal</th>
            <th>Current $</th>
            <th>Predicted $</th>
            <th id="selected-source-price-head">Selected source $</th>
            <th>Change %</th>
            <th>Min / Max</th>
            <th>Quality</th>
            <th>Scans</th>
            <th>Scan trend</th>
            <th>Next Scan</th>
            <th>Sources</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="table-body">
          <tr><td class="empty" colspan="17">Loading...</td></tr>
        </tbody>
      </table>
    </div>
    <div class="pager">
      <div id="pager-summary">Page 1</div>
      <div class="buttons">
        <button id="prev-btn" type="button">Previous</button>
        <button id="next-btn" type="button">Next</button>
      </div>
    </div>
  </div>
</div>

<div class="modal-backdrop" id="detail-backdrop">
  <div class="modal">
    <div class="modal-head">
      <h2 id="detail-title">Room detail</h2>
      <button type="button" id="detail-close">&times;</button>
    </div>
    <div class="modal-body" id="detail-body">
      Loading detail...
    </div>
  </div>
</div>

<script>
const state = {{
  offset: 0,
  limit: 100,
  totalRows: 0,
  runTs: null,
  search: '',
  signal: {initial_signal},
  source: '',
  sourceMode: 'all',
  sourceOnly: false,
  tDays: {initial_t_days},
  loading: false,
  rows: [],
  filteredRows: [],
  pollTimer: null,
  detailView: null,
}};

const el = {{
  tableBody: document.getElementById('table-body'),
  statusPanel: document.getElementById('status-panel'),
  statusText: document.getElementById('status-text'),
  statusMeta: document.getElementById('status-meta'),
  cacheChip: document.getElementById('cache-chip'),
  rowsChip: document.getElementById('rows-chip'),
  runTsChip: document.getElementById('run-ts-chip'),
  total: document.getElementById('stat-total'),
  call: document.getElementById('stat-call'),
  put: document.getElementById('stat-put'),
  neutral: document.getElementById('stat-neutral'),
  selectedSourcePriceHead: document.getElementById('selected-source-price-head'),
  searchInput: document.getElementById('search-input'),
  signalFilter: document.getElementById('signal-filter'),
  sourceFilter: document.getElementById('source-filter'),
  sourceModeFilter: document.getElementById('source-mode-filter'),
  tDaysInput: document.getElementById('t-days-input'),
  limitSelect: document.getElementById('limit-select'),
  prevBtn: document.getElementById('prev-btn'),
  nextBtn: document.getElementById('next-btn'),
  pagerSummary: document.getElementById('pager-summary'),
  refreshBtn: document.getElementById('refresh-btn'),
  detailBackdrop: document.getElementById('detail-backdrop'),
  detailTitle: document.getElementById('detail-title'),
  detailBody: document.getElementById('detail-body'),
  detailClose: document.getElementById('detail-close'),
}};

el.signalFilter.value = state.signal || '';
el.sourceFilter.value = state.source || '';
el.sourceModeFilter.value = state.sourceMode;
el.limitSelect.value = String(state.limit);
if (Number.isInteger(state.tDays)) {{
  el.tDaysInput.value = String(state.tDays);
}}

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({{
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }})[ch]);
}}

function formatCurrency(value) {{
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? '$' + num.toLocaleString(undefined, {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) : '--';
}}

function formatPercent(value) {{
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return '--';
  return (num > 0 ? '+' : '') + num.toFixed(1) + '%';
}}

function signalClass(signal) {{
  const key = String(signal || '').toLowerCase();
  if (key === 'call') return 'call';
  if (key === 'put' || key === 'strong_put' || key === 'next_put') return 'put';
  return 'neutral';
}}

function computeNextScanSignal(row) {{
  /* Next-scan price drop prediction (price-drop skill).
     Predicts if price will drop ≥5% in the next 3h scan cycle. */
  const scan = row.scan_history || {{}};
  const cur = Number(row.current_price || 0);
  const expMin = Number(row.expected_min_price || 0);
  const drops = Number(scan.scan_actual_drops || 0);
  const rises = Number(scan.scan_actual_rises || 0);
  const scans = Number(scan.scan_snapshots || 0);
  const trend = String(scan.scan_trend || '');
  const changePct = Number(scan.scan_price_change_pct || 0);
  const maxDrop = Number(scan.scan_max_single_drop || 0);
  const putDeclines = Number(row.put_decline_count || 0);

  let score = 0;

  // Velocity: recent price trend
  if (scans >= 2 && changePct < 0) {{
    const avgPerScan = changePct / Math.max(1, scans - 1);
    if (avgPerScan < -5) score += 35;
    else if (avgPerScan < -3) score += 25;
    else if (avgPerScan < -1) score += 10;
  }}

  // Acceleration: trending down
  if (trend === 'down') score += 15;

  // Drop frequency
  const totalMoves = drops + rises;
  if (totalMoves > 0) {{
    const freq = drops / totalMoves;
    if (freq > 0.5) score += 20;
    else if (freq > 0.3) score += 10;
  }}

  // Consecutive drops (if trending down with multiple drops)
  if (trend === 'down' && drops >= 3) score += 20;
  else if (trend === 'down' && drops >= 2) score += 15;
  else if (drops >= 1) score += 5;

  // Expected min below current (forward curve sees dip)
  if (cur > 0 && expMin > 0) {{
    const minPct = (expMin - cur) / cur * 100;
    if (minPct <= -5) score += 10;
  }}

  // Max historical single drop was big
  if (cur > 0 && maxDrop / cur * 100 > 10) score += 10;
  else if (cur > 0 && maxDrop / cur * 100 > 5) score += 5;

  // Category volatility
  const cat = String(row.category || '').toLowerCase();
  if (cat.includes('suite') || cat.includes('deluxe')) score += 5;

  // Classify
  let label, cls, detail = '';
  if (score >= 70) {{
    label = 'STRONG PUT';
    cls = 'put';
    detail = '<br><span class="muted">drop expected</span>';
  }} else if (score >= 50) {{
    label = 'PUT';
    cls = 'put';
    detail = '<br><span class="muted">likely drop</span>';
  }} else if (score >= 30) {{
    label = 'WATCH';
    cls = 'neutral';
    detail = '';
  }} else {{
    label = '--';
    cls = '';
    detail = '';
  }}

  return {{ label, cls, detail, score }};
}}

function setStatus(kind, title, text, meta = []) {{
  el.statusPanel.className = 'status-panel ' + kind;
  el.statusPanel.querySelector('.status-title').textContent = title;
  el.statusText.textContent = text;
  el.statusMeta.innerHTML = meta.map((item) => '<span>' + escapeHtml(item) + '</span>').join('');
}}

function updateSummary() {{
  const rows = state.filteredRows;
  const calls = rows.filter((row) => row.option_signal === 'CALL').length;
  const puts = rows.filter((row) => row.option_signal === 'PUT').length;
  const neutrals = rows.length - calls - puts;
  el.total.textContent = String(state.totalRows || 0);
  el.call.textContent = String(calls);
  el.put.textContent = String(puts);
  el.neutral.textContent = String(neutrals);
  el.rowsChip.textContent = 'Rows: ' + rows.length + ' shown / ' + (state.totalRows || 0) + ' total';
  el.runTsChip.textContent = 'Last run: ' + (state.runTs || '--');
  if (state.source && state.sourceMode !== 'all') {{
    if (state.sourceMode === 'source_only') {{
      el.cacheChip.textContent = 'Cache: ready • prediction=' + state.source;
    }} else {{
      el.cacheChip.textContent = 'Cache: ready • filter=' + state.source + ' • prediction=ensemble';
    }}
  }} else {{
    el.cacheChip.textContent = 'Cache: ready';
  }}

  const pageNumber = Math.floor(state.offset / state.limit) + 1;
  const totalPages = Math.max(1, Math.ceil((state.totalRows || 0) / state.limit));
  el.pagerSummary.textContent = 'Page ' + pageNumber + ' of ' + totalPages + ' • offset ' + state.offset;
  el.prevBtn.disabled = state.offset <= 0 || state.loading;
  el.nextBtn.disabled = state.loading || (state.offset + state.limit >= state.totalRows);
  updateSourcePriceHeader();
}}

function updateSourcePriceHeader() {{
  if (!el.selectedSourcePriceHead) return;
  const sourceLabel = state.source ? getSourceDisplayName(state.source) : 'Selected source';
  el.selectedSourcePriceHead.textContent = sourceLabel + ' $';
}}

function applySearch() {{
  const q = state.search.trim().toLowerCase();
  if (!q) {{
    state.filteredRows = [...state.rows];
  }} else {{
    state.filteredRows = state.rows.filter((row) => [
      row.hotel_name,
      row.category,
      row.board,
      row.option_signal,
      row.detail_id,
    ].some((value) => String(value ?? '').toLowerCase().includes(q)));
  }}
  // Client-side filter: NEXT_PUT — show only rooms with next-scan PUT signal
  if (state.signal === 'NEXT_PUT') {{
    state.filteredRows = state.filteredRows.filter((row) => {{
      const ns = computeNextScanSignal(row);
      return ns.score >= 50;  // PUT or STRONG_PUT
    }});
  }}
  renderRows();
}}

function renderRows() {{
  if (!state.filteredRows.length) {{
    el.tableBody.innerHTML = '<tr><td class="empty" colspan="17">No rows match the current view.</td></tr>';
    updateSummary();
    return;
  }}

  el.tableBody.innerHTML = state.filteredRows.map((row) => {{
    const quality = row.quality || {{}};
    const optionLevels = row.option_levels || {{}};
    const scan = row.scan_history || {{}};
    const signal = String(row.option_signal || 'NEUTRAL').toUpperCase();
    const change = Number(row.expected_change_pct || 0);
    const changeCls = change > 0 ? 'pos' : (change < 0 ? 'neg' : '');
    const levelText = optionLevels.label ? ' • ' + optionLevels.label : '';
    const scanTrend = String(scan.scan_trend || 'no_data');
    const scanDelta = Number(scan.scan_price_change_pct || 0);
    const scanDeltaCls = scanDelta > 0 ? 'pos' : (scanDelta < 0 ? 'neg' : '');
    // Next-scan drop prediction (price-drop skill)
    const nextScan = computeNextScanSignal(row);
    const selectedSourcePrice = state.source ? getRowSourcePredictedPrice(row, state.source) : null;
    const selectedSourceHtml = state.source
      ? ((selectedSourcePrice != null ? formatCurrency(selectedSourcePrice) : '<span class="muted">--</span>') + '<br><span class="muted">' + escapeHtml(getSourceDisplayName(state.source)) + '</span>')
      : '<span class="muted">Select source</span>';
    const sourceHtml = Array.isArray(row.sources) && row.sources.length
      ? '<div class="source-badges">' + row.sources.map((item) => '<span class="source-badge">' + escapeHtml((item && item.source) || 'unknown') + '</span>').join('') + '</div>'
      : '<span class="muted">--</span>';
    return `
      <tr>
        <td>${{escapeHtml(row.detail_id)}}</td>
        <td><strong>${{escapeHtml(row.hotel_name || '')}}</strong></td>
        <td>${{escapeHtml(row.category || '')}}</td>
        <td>${{escapeHtml(row.board || '')}}</td>
        <td>${{escapeHtml(row.date_from || '')}}</td>
        <td><span class="pill ${{signalClass(signal)}}">${{escapeHtml(signal)}}${{escapeHtml(levelText)}}</span></td>
        <td>${{formatCurrency(row.current_price)}}</td>
        <td>${{formatCurrency(row.predicted_checkin_price)}}</td>
        <td>${{selectedSourceHtml}}</td>
        <td class="num ${{changeCls}}">${{formatPercent(change)}}</td>
        <td>${{formatCurrency(row.expected_min_price)}} / ${{formatCurrency(row.expected_max_price)}}</td>
        <td><span class="quality ${{String(quality.label || '').toLowerCase()}}">${{escapeHtml(quality.label || '--')}}</span><br><span class="muted">score ${{quality.score != null ? Number(quality.score).toFixed(2) : '--'}}</span></td>
        <td>${{escapeHtml(scan.scan_snapshots ?? 0)}}</td>
        <td><span class="muted">${{escapeHtml(scanTrend)}}</span><br><span class="num ${{scanDeltaCls}}">${{formatPercent(scanDelta)}}</span></td>
        <td><span class="pill ${{nextScan.cls}}">${{nextScan.label}}</span>${{nextScan.detail}}</td>
        <td>${{sourceHtml}}</td>
        <td class="row-actions"><button type="button" data-detail-id="${{escapeHtml(row.detail_id)}}">Chart + analysis</button></td>
      </tr>`;
  }}).join('');

  updateSummary();
}}

function buildOptionsUrl() {{
  const params = new URLSearchParams();
  params.set('profile', 'lite');
  params.set('include_chart', 'false');
  params.set('include_system_context', 'false');
  params.set('include_metadata', 'false');
  params.set('limit', String(state.limit));
  params.set('offset', String(state.offset));
  if (state.signal && state.signal !== 'NEXT_PUT') params.set('signal', state.signal);
  if (state.source) params.set('source', state.source);
  if (state.source && state.sourceMode === 'source_only') params.set('source_only', 'true');
  if (Number.isInteger(state.tDays) && state.tDays > 0) params.set('t_days', String(state.tDays));
  return '/api/v1/salesoffice/options?' + params.toString();
}}

function buildScanRows(scanSeries) {{
  if (!Array.isArray(scanSeries) || !scanSeries.length) {{
    return '<div class="empty-mini">No scan-by-scan history available yet.</div>';
  }}
  let previousPrice = null;
  const rows = scanSeries.map((point, idx) => {{
    const price = Number((point && point.price) || 0);
    const delta = previousPrice == null ? null : price - previousPrice;
    const deltaCls = delta == null ? '' : (delta > 0 ? 'pos' : (delta < 0 ? 'neg' : ''));
    previousPrice = price;
    return `
      <tr>
        <td>${{idx + 1}}</td>
        <td>${{escapeHtml((point && point.date) || '--')}}</td>
        <td>${{formatCurrency(price)}}</td>
        <td class="num ${{deltaCls}}">${{delta == null ? '--' : formatCurrency(delta)}}</td>
      </tr>`;
  }}).join('');
  return '<table class="detail-table"><thead><tr><th>#</th><th>Scan date</th><th>Observed price</th><th>Change vs previous</th></tr></thead><tbody>' + rows + '</tbody></table>';
}}

function buildSourcesTable(sources) {{
  if (!Array.isArray(sources) || !sources.length) {{
    return '<div class="empty-mini">No per-source analysis metadata is available for this row.</div>';
  }}
  const rows = sources.map((item) => `
    <tr>
      <td>${{escapeHtml((item && item.source) || '--')}}</td>
      <td>${{item && item.predicted_price != null ? formatCurrency(item.predicted_price) : '--'}}</td>
      <td>${{item && item.weight != null ? Number(item.weight).toFixed(2) : '--'}}</td>
      <td>${{item && item.confidence != null ? Number(item.confidence).toFixed(2) : '--'}}</td>
      <td>${{escapeHtml((item && item.reasoning) || '--')}}</td>
    </tr>`).join('');
  return '<table class="detail-table"><thead><tr><th>Source</th><th>Predicted $</th><th>Weight</th><th>Confidence</th><th>Reasoning</th></tr></thead><tbody>' + rows + '</tbody></table>';
}}

function filterSeriesByWindow(series, windowValue, keepTail = false) {{
  if (!Array.isArray(series)) return [];
  if (!windowValue || windowValue === 'all') return series;
  const limit = Number.parseInt(windowValue, 10);
  if (!Number.isFinite(limit) || limit <= 0) return series;
  return keepTail ? series.slice(-limit) : series.slice(0, limit);
}}

function getDetailSourceOptions(row, detail) {{
  const sourceSet = new Set();
  if (Array.isArray(detail.available_sources)) {{
    detail.available_sources.forEach((item) => item && sourceSet.add(String(item).trim().toLowerCase()));
  }}
  if (detail && detail.source_predictions && typeof detail.source_predictions === 'object') {{
    Object.keys(detail.source_predictions).forEach((item) => item && sourceSet.add(String(item).trim().toLowerCase()));
  }}
  if (row && row.source_predictions && typeof row.source_predictions === 'object') {{
    Object.keys(row.source_predictions).forEach((item) => item && sourceSet.add(String(item).trim().toLowerCase()));
  }}
  if (Array.isArray(row.sources)) {{
    row.sources.forEach((item) => {{
      const key = String((item && item.source) || '').trim().toLowerCase();
      if (key) sourceSet.add(key);
    }});
  }}
  return ['ensemble', ...Array.from(sourceSet)];
}}

function getSourceDisplayName(source) {{
  if (source === 'ensemble') return 'Ensemble';
  if (source === 'salesoffice') return 'SalesOffice DB';
  if (source === 'forward_curve') return 'Forward curve';
  if (source === 'med_search_hotels') return 'MED Search Hotels';
  if (source === 'historical_pattern') return 'Historical pattern';
  if (source === 'ml_forecast') return 'ML forecast';
  if (source === 'room_price_update_log') return 'Room Price Update Log';
  if (source === 'hotel_booking_dataset') return 'Hotel Booking Demand Dataset';
  if (source === 'cancellation_data') return 'Booking Cancellations';
  if (source === 'kiwi_flights') return 'Kiwi Flights';
  if (source === 'open_meteo') return 'Open-Meteo Weather';
  if (source === 'miami_events_hardcoded') return 'Miami Major Events';
  if (source === 'seatgeek') return 'SeatGeek Events';
  if (source === 'predicthq') return 'PredictHQ Events';
  if (source === 'ai_search_hotel_data') return 'AI Search Hotel Data';
  if (source === 'search_results_poll_log') return 'Search Results Poll Log';
  if (source === 'med_prebook') return 'MED PreBook';
  if (source === 'tbo_hotels') return 'TBO Hotels Dataset';
  if (source === 'ota_brightdata_exports') return 'OTA Market Rates';
  if (source === 'destinations_geo') return 'Destinations & Hotel Geo Data';
  if (source === 'salesoffice_log') return 'SalesOffice Action Log';
  if (source === 'xotelo') return 'Xotelo';
  if (source === 'serpapi_hotels') return 'Google Hotels';
  if (source === 'trivago_statista') return 'Trivago ADR';
  return String(source || '--');
}}

function getSourceColor(source) {{
  return ({{
    ensemble: '#3b82f6',
    salesoffice: '#1d4ed8',
    forward_curve: '#2563eb',
    med_search_hotels: '#6d28d9',
    historical_pattern: '#8b5cf6',
    ml_forecast: '#14b8a6',
    room_price_update_log: '#ea580c',
    hotel_booking_dataset: '#f59e0b',
    cancellation_data: '#dc2626',
    kiwi_flights: '#16a34a',
    open_meteo: '#0ea5e9',
    miami_events_hardcoded: '#db2777',
    seatgeek: '#be185d',
    predicthq: '#ec4899',
    ai_search_hotel_data: '#7c3aed',
    search_results_poll_log: '#0891b2',
    med_prebook: '#0f766e',
    tbo_hotels: '#9333ea',
    ota_brightdata_exports: '#7e22ce',
    destinations_geo: '#6366f1',
    salesoffice_log: '#475569',
    xotelo: '#a855f7',
    serpapi_hotels: '#c026d3',
    trivago_statista: '#d946ef',
    scans: '#f97316',
    delta: '#dc2626',
  }})[source] || '#64748b';
}}

function getRowSourcePredictedPrice(row, source) {{
  if (row && row.source_predictions && row.source_predictions[source] && row.source_predictions[source].predicted_price != null) {{
    return Number(row.source_predictions[source].predicted_price);
  }}
  const item = (Array.isArray(row.sources) ? row.sources : []).find((entry) => String((entry && entry.source) || '').trim().toLowerCase() === source);
  return item && item.predicted_price != null ? Number(item.predicted_price) : null;
}}

function buildCompareSeries(detailState) {{
  const row = detailState.row || {{}};
  const detailCache = detailState.detailCache || {{}};
  const currentPrice = Number((detailState.detail || {{}}).cp || row.current_price || 0);
  const selectedSources = Array.isArray(detailState.compareSources) ? detailState.compareSources : ['ensemble'];

  return selectedSources.map((sourceKey) => {{
    const payload = detailCache[sourceKey];
    if (payload && Array.isArray(payload.fc) && payload.fc.length) {{
      return {{
        key: sourceKey,
        label: getSourceDisplayName(sourceKey),
        color: getSourceColor(sourceKey),
        points: payload.fc.map((point, idx) => ({{
          x: idx,
          label: point.d || `P${{idx + 1}}`,
          value: Number(point.p || 0),
        }})).filter((point) => Number.isFinite(point.value) && point.value > 0),
      }};
    }}

    const predictedPrice = sourceKey === 'ensemble'
      ? Number((detailState.detail || {{}}).pp || row.predicted_checkin_price || 0)
      : getRowSourcePredictedPrice(row, sourceKey);

    return {{
      key: sourceKey,
      label: getSourceDisplayName(sourceKey),
      color: getSourceColor(sourceKey),
      points: [
        {{ x: 0, label: 'Now', value: currentPrice }},
        {{ x: 1, label: 'Target', value: Number(predictedPrice || currentPrice) }},
      ].filter((point) => Number.isFinite(point.value) && point.value > 0),
    }};
  }}).filter((series) => Array.isArray(series.points) && series.points.length);
}}

function buildScanLegend(scanMetric) {{
  const metricKey = scanMetric === 'delta' ? 'delta' : 'scans';
  const label = metricKey === 'delta' ? 'Scan delta' : 'Observed scan price';
  return `<span class="legend-item"><span class="legend-swatch" style="background:${{getSourceColor(metricKey)}}"></span>${{label}}</span>`;
}}

function drawComparisonChart(canvas, detailState) {{
  if (!canvas || !detailState) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth || 680;
  const height = 240;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const seriesList = buildCompareSeries(detailState);
  const allPoints = seriesList.flatMap((series) => series.points || []);
  const validValues = allPoints.map((point) => Number(point.value || 0)).filter((value) => Number.isFinite(value) && value > 0);
  if (!validValues.length) {{
    ctx.fillStyle = '#64748b';
    ctx.font = '13px sans-serif';
    ctx.fillText('No source comparison data available', 20, 40);
    return;
  }}

  const left = 48;
  const right = width - 16;
  const top = 20;
  const bottom = height - 32;
  const chartWidth = right - left;
  const chartHeight = bottom - top;
  const minValue = Math.min.apply(null, validValues);
  const maxValue = Math.max.apply(null, validValues);
  const pad = Math.max((maxValue - minValue) * 0.08, 5);
  const low = minValue - pad;
  const high = maxValue + pad;
  const range = Math.max(high - low, 1);
  const maxPoints = Math.max(...seriesList.map((series) => series.points.length), 2);
  const xCount = Math.max(maxPoints - 1, 1);

  function x(idx) {{ return left + (idx / xCount) * chartWidth; }}
  function y(value) {{ return bottom - ((value - low) / range) * chartHeight; }}

  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {{
    const yy = top + (i / 4) * chartHeight;
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
  }}
  ctx.fillStyle = '#64748b';
  ctx.font = '11px sans-serif';
  ctx.fillText(high.toFixed(0), 4, top + 4);
  ctx.fillText(low.toFixed(0), 8, bottom);

  seriesList.forEach((series) => {{
    ctx.strokeStyle = series.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    series.points.forEach((point, idx) => {{
      const px = x(point.x != null ? point.x : idx);
      const py = y(point.value);
      if (idx === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();

    series.points.forEach((point, idx) => {{
      const px = x(point.x != null ? point.x : idx);
      const py = y(point.value);
      ctx.beginPath();
      ctx.arc(px, py, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = series.color;
      ctx.fill();
    }});
  }});
}}

function drawScanZoomChart(canvas, scanSeries, options = {{}}) {{
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth || 680;
  const height = 220;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const filtered = filterSeriesByWindow(Array.isArray(scanSeries) ? scanSeries : [], options.window || 'all', true);
  if (!filtered.length) {{
    ctx.fillStyle = '#64748b';
    ctx.font = '13px sans-serif';
    ctx.fillText('No scan zoom data available', 20, 40);
    return;
  }}

  const metric = options.metric || 'price';
  let previousPrice = null;
  const points = filtered.map((item, idx) => {{
    const price = Number((item && item.price) || 0);
    const value = metric === 'delta'
      ? (previousPrice == null ? 0 : price - previousPrice)
      : price;
    previousPrice = price;
    return {{ x: idx, value, label: (item && item.date) || `S${{idx + 1}}` }};
  }}).filter((point) => Number.isFinite(point.value));

  const values = points.map((point) => point.value);
  const minValue = Math.min.apply(null, values);
  const maxValue = Math.max.apply(null, values);
  const left = 48;
  const right = width - 16;
  const top = 20;
  const bottom = height - 32;
  const chartWidth = right - left;
  const chartHeight = bottom - top;
  const pad = Math.max((maxValue - minValue) * 0.12, metric === 'delta' ? 2 : 5);
  const low = minValue - pad;
  const high = maxValue + pad;
  const range = Math.max(high - low, 1);
  const xCount = Math.max(points.length - 1, 1);
  const color = metric === 'delta' ? getSourceColor('delta') : getSourceColor('scans');

  function x(idx) {{ return left + (idx / xCount) * chartWidth; }}
  function y(value) {{ return bottom - ((value - low) / range) * chartHeight; }}

  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {{
    const yy = top + (i / 4) * chartHeight;
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
  }}
  if (metric === 'delta' && low < 0 && high > 0) {{
    const zeroY = y(0);
    ctx.strokeStyle = 'rgba(100,116,139,0.5)';
    ctx.beginPath();
    ctx.moveTo(left, zeroY);
    ctx.lineTo(right, zeroY);
    ctx.stroke();
  }}
  ctx.fillStyle = '#64748b';
  ctx.font = '11px sans-serif';
  ctx.fillText(high.toFixed(0), 4, top + 4);
  ctx.fillText(low.toFixed(0), 8, bottom);

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, idx) => {{
    const px = x(idx);
    const py = y(point.value);
    if (idx === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }});
  ctx.stroke();

  points.forEach((point, idx) => {{
    const px = x(idx);
    const py = y(point.value);
    ctx.beginPath();
    ctx.arc(px, py, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }});
}}

function drawDetailChart(canvas, detail, scanSeries, options = {{}}) {{
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth || 680;
  const height = 260;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const windowValue = options.window || 'all';
  const fc = options.showForecast === false ? [] : filterSeriesByWindow(Array.isArray(detail.fc) ? detail.fc : [], windowValue, false);
  const scans = options.showScans === false ? [] : filterSeriesByWindow(Array.isArray(scanSeries) ? scanSeries : [], windowValue, true);
  const showBand = options.showBand !== false;
  const prices = [];
  fc.forEach((item) => prices.push(Number(item.p || 0), Number(item.lo || item.p || 0), Number(item.hi || item.p || 0)));
  scans.forEach((item) => prices.push(Number(item.price || 0)));
  const validPrices = prices.filter((value) => Number.isFinite(value) && value > 0);
  if (!validPrices.length) {{
    ctx.fillStyle = '#64748b';
    ctx.font = '13px sans-serif';
    ctx.fillText('No chart data available', 20, 40);
    return;
  }}

  const minPrice = Math.min.apply(null, validPrices);
  const maxPrice = Math.max.apply(null, validPrices);
  const left = 48;
  const right = width - 16;
  const top = 20;
  const bottom = height - 32;
  const chartWidth = right - left;
  const chartHeight = bottom - top;
  const yPad = Math.max((maxPrice - minPrice) * 0.08, 5);
  const low = minPrice - yPad;
  const high = maxPrice + yPad;
  const range = Math.max(high - low, 1);
  const xCount = Math.max(scans.length + fc.length - 1, 1);

  function x(idx) {{ return left + (idx / xCount) * chartWidth; }}
  function y(price) {{ return bottom - ((price - low) / range) * chartHeight; }}

  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {{
    const yy = top + (i / 4) * chartHeight;
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
  }}

  ctx.fillStyle = '#64748b';
  ctx.font = '11px sans-serif';
  ctx.fillText(high.toFixed(0), 4, top + 4);
  ctx.fillText(low.toFixed(0), 8, bottom);

  if (scans.length) {{
    ctx.strokeStyle = '#f97316';
    ctx.lineWidth = 2;
    ctx.beginPath();
    scans.forEach((point, idx) => {{
      const px = x(idx);
      const py = y(Number(point.price || 0));
      if (idx === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();
    scans.forEach((point, idx) => {{
      const px = x(idx);
      const py = y(Number(point.price || 0));
      ctx.beginPath();
      ctx.arc(px, py, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#f97316';
      ctx.fill();
    }});
  }}

  if (fc.length) {{
    const start = Math.max(scans.length - 1, 0);
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 2;
    ctx.beginPath();
    fc.forEach((point, idx) => {{
      const px = x(start + idx);
      const py = y(Number(point.p || 0));
      if (idx === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();
    fc.forEach((point, idx) => {{
      const px = x(start + idx);
      if (showBand) {{
        const hi = y(Number(point.hi || point.p || 0));
        const lo = y(Number(point.lo || point.p || 0));
        ctx.strokeStyle = 'rgba(59,130,246,0.25)';
        ctx.beginPath();
        ctx.moveTo(px, hi);
        ctx.lineTo(px, lo);
        ctx.stroke();
      }}
      ctx.beginPath();
      ctx.arc(px, y(Number(point.p || 0)), 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#3b82f6';
      ctx.fill();
    }});
  }}
}}

async function fetchDetailPayload(detailId, selectedMode) {{
  const detailUrl = new URL('/api/v1/salesoffice/options/detail/' + encodeURIComponent(detailId), window.location.origin);
  if (selectedMode && selectedMode !== 'ensemble') {{
    detailUrl.searchParams.set('source', selectedMode);
    detailUrl.searchParams.set('source_only', 'true');
  }} else {{
    if (state.source) detailUrl.searchParams.set('source', state.source);
    if (state.sourceOnly && state.source) detailUrl.searchParams.set('source_only', 'true');
  }}
  const response = await fetch(detailUrl.toString(), {{ cache: 'no-store' }});
  if (!response.ok) throw new Error('Detail request failed with ' + response.status);
  return response.json();
}}

async function ensureDetailComparePayloads(detailId, sources) {{
  if (!state.detailView) return;
  const requested = Array.isArray(sources) ? sources : [];
  const missing = requested.filter((item) => item !== 'ensemble' && !state.detailView.detailCache[item]);
  if (!missing.length) return;

  const results = await Promise.all(missing.map(async (item) => [item, await fetchDetailPayload(detailId, item)]));
  results.forEach(([item, payload]) => {{
    state.detailView.detailCache[item] = payload;
  }});
}}

function renderDetailModal(detailId) {{
  const detailState = state.detailView;
  if (!detailState) return;
  const detail = detailState.detail || {{}};
  const row = detailState.row || {{}};
  const scanSeries = Array.isArray(detail.scan)
    ? detail.scan.map((point) => ({{ date: (point && point.d) || '--', price: Number((point && point.p) || 0) }}))
    : ((((row.scan_history || {{}}).scan_price_series) || []).map((point) => ({{ date: (point && point.date) || '--', price: Number((point && point.price) || 0) }})));
  const adjustments = detail.adj || {{}};
  const chartId = 'detail-chart-canvas';
  const compareChartId = 'detail-compare-chart-canvas';
  const scanZoomChartId = 'detail-scan-zoom-chart-canvas';
  const sourceOptions = getDetailSourceOptions(row, detail);
  const selectedMode = detailState.selectedMode || 'ensemble';
  const compareSources = Array.isArray(detailState.compareSources) ? detailState.compareSources : ['ensemble'];

  el.detailBody.innerHTML = `
      <div class="detail-chart-wrap">
        <div class="detail-chart-title">Primary option chart</div>
        <div class="chart-toolbar">
          <label>
            Graph mode
            <select id="detail-source-mode">
              ${{sourceOptions.map((item) => `<option value="${{escapeHtml(item)}}" ${{item === selectedMode ? 'selected' : ''}}>${{item === 'ensemble' ? 'Ensemble view' : ('Source only: ' + item)}}</option>`).join('')}}
            </select>
          </label>
          <label>
            Graph window
            <select id="detail-window-filter">
              <option value="all">All points</option>
              <option value="7" ${{detailState.window === '7' ? 'selected' : ''}}>7 points</option>
              <option value="14" ${{detailState.window === '14' ? 'selected' : ''}}>14 points</option>
              <option value="30" ${{detailState.window === '30' ? 'selected' : ''}}>30 points</option>
            </select>
          </label>
          <div class="toggle-row">
            <label><input id="detail-toggle-scans" type="checkbox" ${{detailState.showScans ? 'checked' : ''}}>Actual scans</label>
            <label><input id="detail-toggle-forecast" type="checkbox" ${{detailState.showForecast ? 'checked' : ''}}>Forecast path</label>
            <label><input id="detail-toggle-band" type="checkbox" ${{detailState.showBand ? 'checked' : ''}}>Confidence band</label>
          </div>
        </div>
        <canvas id="${{chartId}}"></canvas>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-swatch" style="background:#f97316"></span>Actual scans</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#3b82f6"></span>Predicted path</span>
          <span class="legend-item"><span class="legend-swatch" style="background:rgba(59,130,246,0.25)"></span>Prediction band</span>
        </div>
      </div>
      <div class="detail-chart-wrap">
        <div class="detail-chart-title">Source comparison</div>
        <div class="chart-toolbar">
          <div class="source-toggle-group">
            ${{sourceOptions.map((item) => `<label><input class="detail-compare-source" type="checkbox" value="${{escapeHtml(item)}}" ${{compareSources.includes(item) ? 'checked' : ''}}> ${{escapeHtml(getSourceDisplayName(item))}}</label>`).join('')}}
          </div>
        </div>
        <canvas id="${{compareChartId}}"></canvas>
        <div class="chart-legend">
          ${{compareSources.map((item) => `<span class="legend-item"><span class="legend-swatch" style="background:${{getSourceColor(item)}}"></span>${{escapeHtml(getSourceDisplayName(item))}}</span>`).join('')}}
        </div>
      </div>
      <div class="detail-chart-wrap">
        <div class="detail-chart-title">Scan-only zoom</div>
        <div class="chart-toolbar">
          <label>
            Zoom window
            <select id="detail-scan-window-filter">
              <option value="all">All scans</option>
              <option value="7" ${{detailState.scanWindow === '7' ? 'selected' : ''}}>Last 7 scans</option>
              <option value="14" ${{detailState.scanWindow === '14' ? 'selected' : ''}}>Last 14 scans</option>
              <option value="30" ${{detailState.scanWindow === '30' ? 'selected' : ''}}>Last 30 scans</option>
            </select>
          </label>
          <label>
            Scan metric
            <select id="detail-scan-metric-filter">
              <option value="price" ${{detailState.scanMetric === 'price' ? 'selected' : ''}}>Observed price</option>
              <option value="delta" ${{detailState.scanMetric === 'delta' ? 'selected' : ''}}>Change vs previous scan</option>
            </select>
          </label>
        </div>
        <canvas id="${{scanZoomChartId}}"></canvas>
        <div class="chart-legend">
          ${{buildScanLegend(detailState.scanMetric)}}
        </div>
      </div>
      <div class="detail-grid">
        <div class="detail-card"><div class="k">Current</div><div class="v">${{formatCurrency(detail.cp)}}</div></div>
        <div class="detail-card"><div class="k">Predicted</div><div class="v">${{formatCurrency(detail.pp)}}</div></div>
        <div class="detail-card"><div class="k">Expected min</div><div class="v">${{formatCurrency(detail.mn)}}</div></div>
        <div class="detail-card"><div class="k">Expected max</div><div class="v">${{formatCurrency(detail.mx)}}</div></div>
        <div class="detail-card"><div class="k">Signal</div><div class="v">${{escapeHtml(detail.sig || '--')}}</div></div>
        <div class="detail-card"><div class="k">Observed scans</div><div class="v">${{escapeHtml(detail.scans ?? 0)}}</div></div>
        <div class="detail-card"><div class="k">Analysis mode</div><div class="v">${{escapeHtml(detail.analysis_mode || 'ensemble')}}</div></div>
        <div class="detail-card"><div class="k">Selected source</div><div class="v">${{escapeHtml(detail.selected_source || 'all')}}</div></div>
      </div>
      <div class="detail-section">
        <h3>Adjustments</h3>
        <ul class="detail-list">
          <li>Events: ${{Number(adjustments.ev || 0).toFixed(2)}}%</li>
          <li>Seasonality: ${{Number(adjustments.se || 0).toFixed(2)}}%</li>
          <li>Demand: ${{Number(adjustments.dm || 0).toFixed(2)}}%</li>
          <li>Momentum: ${{Number(adjustments.mo || 0).toFixed(2)}}%</li>
          <li>Weather: ${{Number(adjustments.we || 0).toFixed(2)}}%</li>
        </ul>
      </div>
      <div class="detail-section">
        <h3>Observed path</h3>
        <ul class="detail-list">
          <li>Drops: ${{escapeHtml(detail.drops ?? 0)}}</li>
          <li>Rises: ${{escapeHtml(detail.rises ?? 0)}}</li>
          <li>Quality: ${{escapeHtml(detail.q || '--')}}</li>
          <li>Expected change: ${{formatPercent(detail.chg || 0)}}</li>
        </ul>
      </div>
      <div class="detail-grid-2 detail-section">
        <div>
          <h3>Scan-by-scan changes</h3>
          ${{buildScanRows(scanSeries)}}
        </div>
        <div>
          <h3>Per-source analysis</h3>
          ${{buildSourcesTable(Object.values(detail.source_predictions || row.source_predictions || {{}}))}}
          <div class="detail-section">
            <h3>Derived weights</h3>
            <ul class="detail-list">
              <li>Selected source price: ${{detail.selected_source_price != null ? formatCurrency(detail.selected_source_price) : '--'}} • confidence ${{detail.selected_source_confidence != null ? Number(detail.selected_source_confidence).toFixed(2) : '--'}}</li>
              <li>Selected source reasoning: ${{escapeHtml(detail.selected_source_reasoning || '--')}}</li>
              <li>Forward curve: weight ${{Number(detail.fcW || 0).toFixed(2)}} • confidence ${{Number(detail.fcC || 0).toFixed(2)}}</li>
              <li>Historical: weight ${{Number(detail.hiW || 0).toFixed(2)}} • confidence ${{Number(detail.hiC || 0).toFixed(2)}}</li>
            </ul>
          </div>
        </div>
      </div>`;

  requestAnimationFrame(() => drawDetailChart(document.getElementById(chartId), detail, scanSeries, detailState));
  requestAnimationFrame(() => drawComparisonChart(document.getElementById(compareChartId), detailState));
  requestAnimationFrame(() => drawScanZoomChart(document.getElementById(scanZoomChartId), scanSeries, {{ window: detailState.scanWindow || 'all', metric: detailState.scanMetric || 'price' }}));

  const sourceModeEl = document.getElementById('detail-source-mode');
  const windowEl = document.getElementById('detail-window-filter');
  const scansEl = document.getElementById('detail-toggle-scans');
  const forecastEl = document.getElementById('detail-toggle-forecast');
  const bandEl = document.getElementById('detail-toggle-band');
  const compareSourceEls = Array.from(document.querySelectorAll('.detail-compare-source'));
  const scanWindowEl = document.getElementById('detail-scan-window-filter');
  const scanMetricEl = document.getElementById('detail-scan-metric-filter');

  if (sourceModeEl) {{
    sourceModeEl.addEventListener('change', async (event) => {{
      const mode = event.target.value || 'ensemble';
      state.detailView.selectedMode = mode;
      el.detailBody.textContent = 'Loading filtered graph...';
      try {{
        state.detailView.detail = await fetchDetailPayload(detailId, mode);
        state.detailView.detailCache[mode] = state.detailView.detail;
        renderDetailModal(detailId);
      }} catch (error) {{
        el.detailBody.textContent = error.message || 'Failed to load filtered graph.';
      }}
    }});
  }}

  if (windowEl) {{
    windowEl.addEventListener('change', (event) => {{
      state.detailView.window = event.target.value || 'all';
      drawDetailChart(document.getElementById(chartId), state.detailView.detail, scanSeries, state.detailView);
    }});
  }}
  if (scansEl) {{
    scansEl.addEventListener('change', (event) => {{
      state.detailView.showScans = !!event.target.checked;
      drawDetailChart(document.getElementById(chartId), state.detailView.detail, scanSeries, state.detailView);
    }});
  }}
  if (forecastEl) {{
    forecastEl.addEventListener('change', (event) => {{
      state.detailView.showForecast = !!event.target.checked;
      drawDetailChart(document.getElementById(chartId), state.detailView.detail, scanSeries, state.detailView);
    }});
  }}
  if (bandEl) {{
    bandEl.addEventListener('change', (event) => {{
      state.detailView.showBand = !!event.target.checked;
      drawDetailChart(document.getElementById(chartId), state.detailView.detail, scanSeries, state.detailView);
    }});
  }}
  compareSourceEls.forEach((checkbox) => {{
    checkbox.addEventListener('change', async () => {{
      const selected = compareSourceEls.filter((item) => item.checked).map((item) => item.value);
      state.detailView.compareSources = selected.length ? selected : ['ensemble'];
      try {{
        await ensureDetailComparePayloads(detailId, state.detailView.compareSources);
      }} catch (error) {{
        console.warn('Failed to prefetch comparison payload', error);
      }}
      renderDetailModal(detailId);
    }});
  }});
  if (scanWindowEl) {{
    scanWindowEl.addEventListener('change', (event) => {{
      state.detailView.scanWindow = event.target.value || 'all';
      drawScanZoomChart(document.getElementById(scanZoomChartId), scanSeries, {{ window: state.detailView.scanWindow, metric: state.detailView.scanMetric || 'price' }});
    }});
  }}
  if (scanMetricEl) {{
    scanMetricEl.addEventListener('change', (event) => {{
      state.detailView.scanMetric = event.target.value || 'price';
      drawScanZoomChart(document.getElementById(scanZoomChartId), scanSeries, {{ window: state.detailView.scanWindow || 'all', metric: state.detailView.scanMetric }});
    }});
  }}
}}

async function startWarmup() {{
  try {{
    await fetch('/api/v1/salesoffice/options/warmup', {{ method: 'POST' }});
  }} catch (error) {{
    console.warn('Warmup trigger failed', error);
  }}
}}

async function fetchStatus() {{
  const response = await fetch('/api/v1/salesoffice/status', {{ cache: 'no-store' }});
  if (!response.ok) throw new Error('Status request failed with ' + response.status);
  return response.json();
}}

function ensurePolling() {{
  if (state.pollTimer) return;
  state.pollTimer = window.setInterval(async () => {{
    try {{
      const status = await fetchStatus();
      el.cacheChip.textContent = 'Cache: ' + (status.cache_ready ? 'ready' : (status.analysis_warming ? 'warming' : 'cold'));
      setStatus(
        status.cache_ready ? 'loading' : 'warning',
        status.cache_ready ? 'Cache ready — loading rows' : 'Analysis warmup in progress',
        status.cache_ready ? 'Cached analysis is ready. Fetching page data now.' : 'The prediction engine is rebuilding in the background.',
        [
          'snapshots ' + (status.snapshots_collected ?? '--'),
          'rooms ' + (status.total_rooms ?? '--'),
          'scheduler ' + ((status.scheduler_running ? 'running' : 'stopped')),
        ]
      );
      if (status.cache_ready) {{
        stopPolling();
        void fetchRows();
      }}
    }} catch (error) {{
      console.warn('Polling failed', error);
    }}
  }}, 10000);
}}

function stopPolling() {{
  if (state.pollTimer) {{
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }}
}}

async function fetchRows() {{
  if (state.loading) return;
  state.loading = true;
  updateSummary();
  setStatus('loading', 'Loading options rows', 'Reading cached options data from the API...');

  try {{
    const response = await fetch(buildOptionsUrl(), {{ cache: 'no-store' }});
    if (response.status === 503) {{
      await startWarmup();
      const retryAfter = response.headers.get('Retry-After') || '30';
      el.cacheChip.textContent = 'Cache: warming';
      setStatus('warning', 'Cache is warming up', 'The options dataset is rebuilding in the background.', ['retry after ~' + retryAfter + 's']);
      state.rows = [];
      state.filteredRows = [];
      renderRows();
      ensurePolling();
      return;
    }}

    if (!response.ok) {{
      throw new Error('Options request failed with ' + response.status);
    }}

    const payload = await response.json();
    stopPolling();
    state.rows = Array.isArray(payload.rows) ? payload.rows : [];
    state.totalRows = Number(payload.total_rows || 0);
    state.runTs = payload.run_ts || null;
    state.sourceOnly = state.sourceMode === 'source_only';
    el.cacheChip.textContent = 'Cache: ready';
    setStatus('loading', 'Options data loaded', 'Page data was loaded from the cached JSON endpoint.', [
      'profile ' + (payload.profile_applied || 'lite'),
      'mode ' + (state.sourceMode === 'source_only' ? 'source_only' : (state.sourceMode === 'filter' ? 'source_filter' : 'ensemble')),
      (state.source ? 'source ' + state.source : 'all sources'),
      'page size ' + state.limit,
      'offset ' + state.offset,
    ]);
    applySearch();
  }} catch (error) {{
    console.error(error);
    setStatus('error', 'Failed to load options data', error.message || 'Unknown error');
    el.tableBody.innerHTML = '<tr><td class="empty" colspan="17">Failed to load data. Use Refresh to try again.</td></tr>';
  }} finally {{
    state.loading = false;
    updateSummary();
  }}
}}

async function openDetail(detailId) {{
  el.detailBackdrop.classList.add('open');
  el.detailTitle.textContent = 'Room ' + detailId + ' detail';
  el.detailBody.textContent = 'Loading detail...';
  try {{
    const row = state.rows.find((item) => String(item.detail_id) === String(detailId)) || {{}};
    const selectedMode = state.source && state.sourceMode !== 'all' ? state.source : 'ensemble';
    const detail = await fetchDetailPayload(detailId, selectedMode);
    state.detailView = {{
      detailId,
      row,
      detail,
      selectedMode,
      detailCache: {{ [selectedMode]: detail }},
      window: 'all',
      showScans: true,
      showForecast: true,
      showBand: true,
      compareSources: ['ensemble', ...(state.source ? [state.source] : [])],
      scanWindow: 'all',
      scanMetric: 'price',
    }};
    await ensureDetailComparePayloads(detailId, state.detailView.compareSources);
    renderDetailModal(detailId);
  }} catch (error) {{
    el.detailBody.textContent = error.message || 'Failed to load detail.';
  }}
}}

el.tableBody.addEventListener('click', (event) => {{
  const button = event.target.closest('button[data-detail-id]');
  if (!button) return;
  void openDetail(button.getAttribute('data-detail-id'));
}});

el.detailClose.addEventListener('click', () => el.detailBackdrop.classList.remove('open'));
el.detailBackdrop.addEventListener('click', (event) => {{ if (event.target === el.detailBackdrop) el.detailBackdrop.classList.remove('open'); }});

el.searchInput.addEventListener('input', (event) => {{
  state.search = event.target.value || '';
  applySearch();
}});

el.signalFilter.addEventListener('change', (event) => {{
  state.signal = event.target.value || '';
  state.offset = 0;
  void fetchRows();
}});

el.sourceFilter.addEventListener('change', (event) => {{
  state.source = event.target.value || '';
  if (!state.source) {{
    state.sourceMode = 'all';
  }} else {{
    state.sourceMode = 'source_only';
  }}
  state.sourceOnly = state.sourceMode === 'source_only';
  el.sourceModeFilter.value = state.sourceMode;
  state.offset = 0;
  void fetchRows();
}});

el.sourceModeFilter.addEventListener('change', (event) => {{
  const nextMode = event.target.value || 'all';
  state.sourceMode = state.source ? nextMode : 'all';
  state.sourceOnly = state.sourceMode === 'source_only';
  event.target.value = state.sourceMode;
  state.offset = 0;
  void fetchRows();
}});

el.tDaysInput.addEventListener('change', (event) => {{
  const raw = String(event.target.value || '').trim();
  state.tDays = raw ? Number.parseInt(raw, 10) : null;
  state.offset = 0;
  void fetchRows();
}});

el.limitSelect.addEventListener('change', (event) => {{
  state.limit = Number.parseInt(event.target.value, 10) || 100;
  state.offset = 0;
  void fetchRows();
}});

el.prevBtn.addEventListener('click', () => {{
  state.offset = Math.max(0, state.offset - state.limit);
  void fetchRows();
}});

el.nextBtn.addEventListener('click', () => {{
  if (state.offset + state.limit < state.totalRows) {{
    state.offset += state.limit;
    void fetchRows();
  }}
}});

el.refreshBtn.addEventListener('click', async () => {{
  await startWarmup();
  void fetchRows();
}});

window.addEventListener('beforeunload', stopPolling);
void fetchRows();
</script>
</body>
</html>
"""


def _generate_options_html(rows: list[dict], analysis: dict, t_days: int | None) -> str:
    """Generate a self-contained interactive HTML dashboard for options."""
    total = len(rows)
    calls = sum(1 for r in rows if r["option_signal"] == "CALL")
    puts = sum(1 for r in rows if r["option_signal"] == "PUT")
    neutrals = total - calls - puts
    run_ts = analysis.get("run_ts", "")

    # Build table rows HTML
    table_rows = []
    for r in rows:
        sig = r["option_signal"]
        chg = r["expected_change_pct"]
        lvl = r["level"]

        if sig == "CALL":
            sig_cls = "sig-call"
            sig_badge = f'<span class="badge badge-call">CALL L{lvl}</span>'
        elif sig == "PUT":
            sig_cls = "sig-put"
            sig_badge = f'<span class="badge badge-put">PUT L{lvl}</span>'
        else:
            sig_cls = "sig-neutral"
            sig_badge = '<span class="badge badge-neutral">NEUTRAL</span>'

        chg_cls = "pct-up" if chg > 0 else ("pct-down" if chg < 0 else "")
        chg_arrow = "&#9650;" if chg > 0 else ("&#9660;" if chg < 0 else "")

        q_score = r["quality_score"]
        q_cls = "q-high" if q_score >= 0.75 else ("q-med" if q_score >= 0.5 else "q-low")

        put_info = ""
        exp_drops = r.get("expected_future_drops", 0)
        if r["put_decline_count"] > 0:
            put_info = (
                f'{r["put_decline_count"]} drops, '
                f'total ${r["put_total_decline"]:.0f}, '
                f'max ${r["put_largest_decline"]:.0f}'
            )
        elif exp_drops > 0:
            put_info = f'~{exp_drops:.0f} expected drops (prob-based)'

        # Scan history cells
        s_snaps = r.get("scan_snapshots", 0)
        s_drops = r.get("scan_actual_drops", 0)
        s_rises = r.get("scan_actual_rises", 0)
        s_chg = r.get("scan_price_change", 0)
        s_chg_pct = r.get("scan_price_change_pct", 0)
        s_first = r.get("first_scan_price")
        s_latest = r.get("latest_scan_price")
        s_trend = r.get("scan_trend", "no_data")
        s_total_drop = r.get("scan_total_drop_amount", 0)
        s_total_rise = r.get("scan_total_rise_amount", 0)
        s_max_drop = r.get("scan_max_single_drop", 0)
        s_max_rise = r.get("scan_max_single_rise", 0)
        s_first_date = r.get("first_scan_date") or ""
        s_latest_date = r.get("latest_scan_date") or ""

        scan_chg_cls = "pct-up" if s_chg > 0 else ("pct-down" if s_chg < 0 else "")
        scan_chg_arrow = "&#9650;" if s_chg > 0.5 else ("&#9660;" if s_chg < -0.5 else "")
        scan_first_str = f"${s_first:,.0f}" if s_first else "-"

        # Rich Actual D/R: colored pill with drop/rise counts
        if s_snaps > 1:
            dr_title = (
                f"Since {s_first_date[:10]}: "
                f"{s_drops} drops (total ${s_total_drop:.0f}, max ${s_max_drop:.0f}) | "
                f"{s_rises} rises (total ${s_total_rise:.0f}, max ${s_max_rise:.0f})"
            )
            drop_part = f'<span class="scan-drop">{s_drops}&#9660;</span>' if s_drops else '<span class="scan-zero">0&#9660;</span>'
            rise_part = f'<span class="scan-rise">{s_rises}&#9650;</span>' if s_rises else '<span class="scan-zero">0&#9650;</span>'
            scan_hist_str = f'<span class="scan-dr" title="{dr_title}">{drop_part} {rise_part}</span>'
        else:
            scan_hist_str = '<span class="scan-nodata">-</span>'

        # Scan trend badge
        if s_trend == "down":
            trend_badge = '<span class="trend-badge trend-down">&#9660;</span>'
        elif s_trend == "up":
            trend_badge = '<span class="trend-badge trend-up">&#9650;</span>'
        elif s_trend == "stable":
            trend_badge = '<span class="trend-badge trend-stable">&#9644;</span>'
        else:
            trend_badge = ''

        # Chart icon — only show if we have >1 scan
        scan_series = r.get("scan_price_series", [])
        if len(scan_series) > 1:
            series_json = json.dumps(scan_series).replace("'", "&#39;")
            esc_hotel = _html_escape(json.dumps(r["hotel_name"]))
            det_id = r["detail_id"]
            chart_icon = (
                f'<button class="chart-btn" title="View scan price chart" '
                f"onclick='showChart({det_id}, "
                f"{esc_hotel}, "
                f"this.dataset.series)' "
                f"data-series='{series_json}'>"
                f'&#128200;</button>'
            )
        else:
            chart_icon = '<span class="chart-btn-empty" title="Not enough scan data">-</span>'

        # Market benchmark cell (hotel vs same-star avg in same city)
        mkt_avg = r.get("market_avg_price", 0)
        mkt_pressure = r.get("market_pressure", 0)
        mkt_hotels = r.get("market_competitor_hotels", 0)
        mkt_city = r.get("market_city", "")
        mkt_stars = r.get("market_stars", 0)

        # Per-source prediction cells
        fc_p = r.get("fc_price")
        fc_w = r.get("fc_weight", 0)
        fc_c = r.get("fc_confidence", 0)
        ev_adj = r.get("event_adj_total", 0)
        se_adj = r.get("season_adj_total", 0)
        dm_adj = r.get("demand_adj_total", 0)
        mo_adj = r.get("momentum_adj_total", 0)
        if fc_p is not None:
            fc_cls = "pct-up" if fc_p > r["current_price"] else ("pct-down" if fc_p < r["current_price"] else "")
            fc_chg = (fc_p - r["current_price"]) / r["current_price"] * 100 if r["current_price"] > 0 else 0
            fc_title = (
                f"FC predicted: ${fc_p:,.0f} ({fc_chg:+.1f}%) | "
                f"Weight: {fc_w:.0%} | Confidence: {fc_c:.0%} | "
                f"Adjustments: events {ev_adj:+.1f}%, season {se_adj:+.1f}%, "
                f"demand {dm_adj:+.1f}%, momentum {mo_adj:+.1f}%"
            )
            fc_cell = f'${fc_p:,.0f} <small class="{fc_cls}">({fc_chg:+.0f}%)</small>'
        else:
            fc_cls = ""
            fc_title = "No forward curve data"
            fc_cell = "-"

        hist_p = r.get("hist_price")
        hist_w = r.get("hist_weight", 0)
        hist_c = r.get("hist_confidence", 0)
        if hist_p is not None:
            hist_cls = "pct-up" if hist_p > r["current_price"] else ("pct-down" if hist_p < r["current_price"] else "")
            hist_chg = (hist_p - r["current_price"]) / r["current_price"] * 100 if r["current_price"] > 0 else 0
            hist_title = (
                f"Historical predicted: ${hist_p:,.0f} ({hist_chg:+.1f}%) | "
                f"Weight: {hist_w:.0%} | Confidence: {hist_c:.0%}"
            )
            hist_cell = f'${hist_p:,.0f} <small class="{hist_cls}">({hist_chg:+.0f}%)</small>'
        else:
            hist_cls = ""
            hist_title = "No historical pattern data for this hotel/period"
            hist_cell = '<span style="color:#94a3b8">-</span>'
        if mkt_avg and mkt_avg > 0:
            mkt_cls = "pct-up" if r["current_price"] < mkt_avg else ("pct-down" if r["current_price"] > mkt_avg else "")
            mkt_pct = (r["current_price"] - mkt_avg) / mkt_avg * 100
            mkt_arrow = "&#9660;" if mkt_pct < -1 else ("&#9650;" if mkt_pct > 1 else "")
            mkt_title = (
                f"{mkt_city} {mkt_stars}★ avg: ${mkt_avg:,.0f} | "
                f"{mkt_hotels} competitor hotels | "
                f"You are {mkt_pct:+.1f}% vs market"
            )
            mkt_str = f'{mkt_arrow} ${mkt_avg:,.0f} <small>({mkt_pct:+.0f}%)</small>'
        else:
            mkt_cls = ""
            mkt_title = "No market data for this hotel's city/star combo"
            mkt_str = "-"

        # ── Scan min/max from actual monitoring ──
        scan_min = r.get("scan_min_price")
        scan_max = r.get("scan_max_price")
        pred_min = r["expected_min_price"]
        pred_max = r["expected_max_price"]

        if scan_min is not None and s_snaps > 1:
            min_title = f"Scan min: ${scan_min:,.0f} (actual) | Predicted min: ${pred_min:,.0f} (FC path)"
            min_cell = f'<span class="price-dual">${scan_min:,.0f}<small class="pred-sub">pred ${pred_min:,.0f}</small></span>'
        else:
            min_title = f"Predicted min: ${pred_min:,.0f} (forward curve path)"
            min_cell = f'${pred_min:,.2f}'

        if scan_max is not None and s_snaps > 1:
            max_title = f"Scan max: ${scan_max:,.0f} (actual) | Predicted max: ${pred_max:,.0f} (FC path)"
            max_cell = f'<span class="price-dual">${scan_max:,.0f}<small class="pred-sub">pred ${pred_max:,.0f}</small></span>'
        else:
            max_title = f"Predicted max: ${pred_max:,.0f} (forward curve path)"
            max_cell = f'${pred_max:,.2f}'

        # ── Source detail JSON for popup ──
        src_detail = {
            "method": r.get("prediction_method", ""),
            "signals": [],
            "adjustments": {"events": ev_adj, "season": se_adj, "demand": dm_adj, "momentum": mo_adj},
            "factors": r.get("explanation_factors", []),
        }
        if fc_p is not None:
            src_detail["signals"].append({
                "source": "Forward Curve", "price": fc_p, "weight": fc_w,
                "confidence": fc_c, "reasoning": r.get("fc_reasoning", ""),
            })
        if hist_p is not None:
            src_detail["signals"].append({
                "source": "Historical Pattern", "price": hist_p, "weight": hist_w,
                "confidence": hist_c, "reasoning": r.get("hist_reasoning", ""),
            })
        ml_p = r.get("ml_price")
        if ml_p is not None:
            src_detail["signals"].append({
                "source": "ML Forecast", "price": ml_p, "weight": 0,
                "confidence": 0, "reasoning": r.get("ml_reasoning", ""),
            })
        src_json = json.dumps(src_detail).replace("'", "&#39;").replace('"', "&quot;")

        # ── Chart + Sources combined cell ──
        if len(scan_series) > 1:
            chart_cell = (
                f'<button class="chart-btn" title="Scan price chart" '
                f"onclick='showChart({det_id}, "
                f"{esc_hotel}, "
                f"this.dataset.series)' "
                f"data-series='{series_json}'>"
                f'&#128200;</button>'
                f'<button class="src-btn" title="Source detail" '
                f'onclick="showSources(this)" '
                f'data-sources="{src_json}" '
                f'data-hotel="{_html_escape(r["hotel_name"])}" '
                f'data-detail-id="{r["detail_id"]}">'
                f'&#128269;</button>'
            )
        else:
            chart_cell = (
                f'<button class="src-btn" title="Source detail" '
                f'onclick="showSources(this)" '
                f'data-sources="{src_json}" '
                f'data-hotel="{_html_escape(r["hotel_name"])}" '
                f'data-detail-id="{r["detail_id"]}">'
                f'&#128269;</button>'
            )

        # ── AI Intelligence cell ──
        ai_risk_data = r.get("ai_risk", {})
        ai_anomaly_data = r.get("ai_anomaly", {})
        ai_conviction = r.get("ai_conviction", "")
        ai_risk_level = ai_risk_data.get("risk_level", "")
        ai_risk_score = ai_risk_data.get("risk_score", 0)
        ai_is_anomaly = ai_anomaly_data.get("is_anomaly", False)
        ai_anomaly_type = ai_anomaly_data.get("anomaly_type", "")
        ai_anomaly_sev = ai_anomaly_data.get("severity", "none")

        # Build AI badge
        risk_cls_map = {"low": "ai-low", "medium": "ai-med", "high": "ai-high", "extreme": "ai-ext"}
        ai_risk_cls = risk_cls_map.get(ai_risk_level, "ai-low")
        ai_title_parts = [f"Risk: {ai_risk_level} ({ai_risk_score:.0%})"]
        if ai_conviction:
            ai_title_parts.append(f"Conviction: {ai_conviction}")
        if ai_is_anomaly:
            ai_title_parts.append(f"Anomaly: {ai_anomaly_type} ({ai_anomaly_sev})")
        ai_title = " | ".join(ai_title_parts)

        ai_badge = f'<span class="ai-badge {ai_risk_cls}" title="{ai_title}">'
        ai_badge += f'{ai_risk_level[:3].upper()}'
        if ai_is_anomaly:
            ai_badge += f' <span class="ai-anomaly-dot" title="{ai_anomaly_type}: {ai_anomaly_data.get("explanation", "")}">&#9888;</span>'
        ai_badge += '</span>'

        table_rows.append(
            f'<tr class="{sig_cls}" '
            f'data-signal="{sig}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-change="{chg}" '
            f'data-detail-id="{r["detail_id"]}" '
            f'data-current-price="{r["current_price"]}">'
            f'<td class="col-id sticky-col sc-id"><button class="expand-btn" id="eb-{r["detail_id"]}" onclick="toggleDetail({r["detail_id"]})" title="Expand trading chart">&#9660;</button> {r["detail_id"]}</td>'
            f'<td class="col-hotel sticky-col sc-hotel" title="{_html_escape(r["hotel_name"])}">{_html_escape(r["hotel_name"][:30])}</td>'
            f'<td>{_html_escape(r["category"])}</td>'
            f'<td>{_html_escape(r["board"])}</td>'
            f'<td>{_html_escape(str(r["date_from"] or ""))}</td>'
            f'<td class="num">{r["days_to_checkin"] or ""}</td>'
            f'<td>{sig_badge}</td>'
            f'<td class="num">${r["current_price"]:,.2f}</td>'
            f'<td class="num">${r["predicted_checkin_price"]:,.2f}</td>'
            f'<td class="num {chg_cls}">{chg_arrow} {chg:+.1f}%</td>'
            f'<td class="num {fc_cls}" title="{fc_title}">{fc_cell}</td>'
            f'<td class="num {hist_cls}" title="{hist_title}">{hist_cell}</td>'
            f'<td class="num" title="{min_title}">{min_cell}</td>'
            f'<td class="num" title="{max_title}">{max_cell}</td>'
            f'<td class="num">{r["touches_min"]}/{r["touches_max"]}</td>'
            f'<td class="num">{r["changes_gt_20"]}</td>'
            f'<td class="num">{r["put_decline_count"]}</td>'
            f'<td><span class="q-dot {q_cls}" title="{r["quality_label"]} ({q_score:.2f})">'
            f'{r["quality_label"]}</span></td>'
            f'<td class="num">{s_snaps}</td>'
            f'<td class="num">{scan_first_str}</td>'
            f'<td class="scan-col">{scan_hist_str}</td>'
            f'<td class="num {scan_chg_cls}" title="drop ${s_total_drop:.0f} / rise ${s_total_rise:.0f}">{trend_badge} {scan_chg_arrow} {s_chg_pct:+.1f}%</td>'
            f'<td class="col-chart">{chart_cell}</td>'
            f'<td class="col-put">{put_info}</td>'
            f'<td class="num {mkt_cls}" title="{mkt_title}">{mkt_str}</td>'
            f'<td class="col-rules"><button class="rules-btn" title="Set pricing rules" '
            f'onclick="openRulesPanel(this)" '
            f'data-detail-id="{r["detail_id"]}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-board="{_html_escape(r["board"])}" '
            f'data-price="{r["current_price"]}" '
            f'data-signal="{sig}">'
            f'&#9881; Rules</button></td>'
            f'<td class="col-ai">{ai_badge}</td>'
            f'</tr>'
        )

# ── Detail row (empty shell — data loaded lazily via AJAX) ──
        table_rows.append(
            f'<tr class="detail-row" id="detail-{r["detail_id"]}">' 
            f'<td colspan="27">'
            f'<div class="detail-panel" id="dp-{r["detail_id"]}">' 
            f'<div class="detail-chart-wrap">'
            f'<div class="detail-chart-title">Price Trajectory &mdash; Forward Curve + Actual Scans</div>'
            f'<canvas class="detail-canvas" id="dc-{r["detail_id"]}" width="700" height="200"></canvas>'
            f'<div class="detail-legend">'
            f'<span><span class="leg-line" style="background:#3b82f6"></span> Forward Curve</span>'
            f'<span><span class="leg-line" style="background:rgba(59,130,246,.15);height:6px"></span> Confidence Band</span>'
            f'<span><span class="leg-dot" style="background:#f97316"></span> Actual Scans</span>'
            f'<span><span class="leg-line" style="background:#10b981;height:1px;border-top:1px dashed #10b981"></span> Current $</span>'
            f'<span><span class="leg-line" style="background:#a855f7;height:1px;border-top:1px dashed #a855f7"></span> Predicted $</span>'
            f'</div></div>'
            f'<div class="detail-info-wrap" id="di-{r["detail_id"]}">' 
            f'</div></div>'
            f'</td></tr>'
        )

    rows_html = "\n".join(table_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SalesOffice Options Dashboard</title>
<style>
  :root {{
    --call: #16a34a; --call-bg: #dcfce7; --call-row: #f0fdf4;
    --put: #dc2626; --put-bg: #fee2e2; --put-row: #fef2f2;
    --neutral: #6b7280; --neutral-bg: #f3f4f6;
    --border: #e5e7eb; --header-bg: #1e293b; --header-fg: #f8fafc;
    --bg: #f8fafc; --card-bg: #fff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: #1e293b; font-size: 13px; }}

  .top-bar {{ background: var(--header-bg); color: var(--header-fg);
              padding: 14px 24px; display: flex; justify-content: space-between;
              align-items: center; }}
  .top-bar h1 {{ font-size: 18px; font-weight: 600; }}
  .top-bar .ts {{ font-size: 11px; opacity: 0.7; }}

  .cards {{ display: flex; gap: 14px; padding: 18px 24px; flex-wrap: wrap; }}
  .card {{ background: var(--card-bg); border-radius: 10px; padding: 16px 22px;
           min-width: 140px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
           border-left: 4px solid var(--border); }}
  .card.c-total {{ border-left-color: #3b82f6; }}
  .card.c-call  {{ border-left-color: var(--call); }}
  .card.c-put   {{ border-left-color: var(--put); }}
  .card.c-neut  {{ border-left-color: var(--neutral); }}
  .card .num-big {{ font-size: 28px; font-weight: 700; }}
  .card .label {{ font-size: 11px; text-transform: uppercase; color: #64748b;
                  margin-top: 2px; letter-spacing: 0.5px; }}

  .controls {{ padding: 8px 24px 12px; display: flex; gap: 10px; flex-wrap: wrap;
               align-items: center; }}
  .controls input, .controls select {{ padding: 7px 12px; border: 1px solid var(--border);
    border-radius: 6px; font-size: 13px; background: #fff; }}
  .controls input {{ width: 260px; }}
  .controls select {{ min-width: 110px; }}
  .controls label {{ font-size: 12px; color: #64748b; margin-right: 2px; }}

  .table-wrap {{ overflow-x: auto; padding: 0 24px 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  thead {{ background: #f1f5f9; position: sticky; top: 0; z-index: 2; }}
  th {{ padding: 10px 10px; text-align: left; font-weight: 600; font-size: 11px;
       text-transform: uppercase; letter-spacing: .4px; color: #475569;
       border-bottom: 2px solid var(--border); cursor: pointer; white-space: nowrap;
       user-select: none; }}
  th:hover {{ background: #e2e8f0; }}
  th .arrow {{ font-size: 10px; margin-left: 3px; opacity: .4; }}
  th.sorted .arrow {{ opacity: 1; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  tr:hover {{ background: #f1f5f9; }}
  tr.sig-call {{ background: var(--call-row); }}
  tr.sig-put  {{ background: var(--put-row); }}

  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}

  .badge {{ display: inline-block; padding: 3px 9px; border-radius: 12px;
            font-size: 11px; font-weight: 600; letter-spacing: .3px; }}
  .badge-call    {{ background: var(--call-bg); color: var(--call); }}
  .badge-put     {{ background: var(--put-bg);  color: var(--put); }}
  .badge-neutral {{ background: var(--neutral-bg); color: var(--neutral); }}

  .pct-up   {{ color: var(--call); font-weight: 600; }}
  .pct-down {{ color: var(--put);  font-weight: 600; }}

  .q-dot {{ padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 600; }}
  .q-high {{ background: #dcfce7; color: #15803d; }}
  .q-med  {{ background: #fef9c3; color: #a16207; }}
  .q-low  {{ background: #fee2e2; color: #b91c1c; }}

  .col-hotel {{ max-width: 180px; overflow: hidden; text-overflow: ellipsis; }}

  /* ── Sticky first columns ───────────────────────────────────── */
  .sticky-col {{ position: sticky; z-index: 3; background: inherit; }}
  .sc-id {{ left: 0; min-width: 55px; }}
  .sc-hotel {{ left: 55px; min-width: 160px; border-right: 2px solid #cbd5e1; }}
  thead .sticky-col {{ z-index: 5; background: #f1f5f9; }}
  tr.sig-call .sticky-col {{ background: var(--call-row); }}
  tr.sig-put .sticky-col {{ background: var(--put-row); }}
  tr:hover .sticky-col {{ background: #f1f5f9; }}
  td.sticky-col {{ background: #fff; }}
  tr.sig-call td.sticky-col {{ background: var(--call-row); }}
  tr.sig-put td.sticky-col {{ background: var(--put-row); }}

  /* ── Source columns ─────────────────────────────────────────── */
  .src-col {{ background: #f5f3ff !important; }}
  td:nth-child(11), td:nth-child(12) {{ background: rgba(245,243,255,.45); font-size: 12px; }}
  .col-put {{ font-size: 11px; color: #64748b; max-width: 200px;
              overflow: hidden; text-overflow: ellipsis; }}
  .col-id {{ color: #94a3b8; font-size: 11px; }}
  .scan-col {{ font-size: 11px; }}

  .scan-dr {{ display: inline-flex; gap: 6px; align-items: center; }}
  .scan-drop {{ color: var(--put); font-weight: 700; font-size: 12px; }}
  .scan-rise {{ color: var(--call); font-weight: 700; font-size: 12px; }}
  .scan-zero {{ color: #94a3b8; font-size: 12px; }}
  .scan-nodata {{ color: #cbd5e1; }}

  .trend-badge {{ display: inline-block; font-size: 10px; margin-right: 2px; }}
  .trend-down {{ color: var(--put); }}
  .trend-up {{ color: var(--call); }}
  .trend-stable {{ color: #94a3b8; }}

  .chart-btn {{ background: none; border: 1px solid var(--border); border-radius: 5px;
                cursor: pointer; font-size: 14px; padding: 2px 6px; line-height: 1;
                transition: background .15s; }}
  .chart-btn:hover {{ background: #e2e8f0; }}
  .chart-btn-empty {{ color: #cbd5e1; font-size: 12px; }}
  .col-chart {{ text-align: center; }}

  /* ── Source detail button ─── */
  .src-btn {{ background: none; border: 1px solid #c7d2fe; border-radius: 5px;
              cursor: pointer; font-size: 13px; padding: 2px 5px; line-height: 1;
              transition: background .15s; margin-left: 3px; }}
  .src-btn:hover {{ background: #eef2ff; }}

  /* ── Price dual display (scan / pred) ─── */
  .price-dual {{ display: flex; flex-direction: column; line-height: 1.2; }}
  .price-dual .pred-sub {{ font-size: 9px; color: #94a3b8; }}

  /* ── Source detail modal ─── */
  .src-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                  background: rgba(0,0,0,.4); z-index: 150; justify-content: center; align-items: center; }}
  .src-overlay.open {{ display: flex; }}
  .src-box {{ background: #fff; border-radius: 14px; padding: 24px; width: 560px;
              max-width: 95vw; max-height: 85vh; overflow-y: auto;
              box-shadow: 0 12px 40px rgba(0,0,0,.3); position: relative; }}
  .src-close {{ position: absolute; top: 12px; right: 16px; font-size: 20px;
                cursor: pointer; color: #64748b; background: none; border: none; }}
  .src-close:hover {{ color: #1e293b; }}
  .src-title {{ font-size: 15px; font-weight: 700; margin-bottom: 4px; color:#1e293b; }}
  .src-subtitle {{ font-size: 11px; color:#64748b; margin-bottom: 14px; }}
  .src-signals {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }}
  .src-signal {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }}
  .src-signal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
  .src-signal-name {{ font-weight: 700; font-size: 13px; color: #1e293b; }}
  .src-signal-price {{ font-size: 15px; font-weight: 700; }}
  .src-signal-bar {{ height: 6px; border-radius: 3px; background: #e2e8f0; margin-bottom: 4px; }}
  .src-signal-fill {{ height: 100%; border-radius: 3px; }}
  .src-signal-meta {{ font-size: 10px; color: #64748b; }}
  .src-signal-reasoning {{ font-size: 10px; color: #475569; margin-top: 4px; padding: 4px 6px;
                           background: #f1f5f9; border-radius: 4px; line-height: 1.4; }}
  .src-adj {{ margin-bottom: 16px; }}
  .src-adj h4 {{ font-size: 12px; font-weight: 700; color: #475569; margin: 0 0 8px; }}
  .src-adj-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .src-adj-item {{ background: #f1f5f9; border-radius: 8px; padding: 8px; text-align: center; }}
  .src-adj-val {{ font-size: 16px; font-weight: 700; }}
  .src-adj-val.pos {{ color: var(--call); }}
  .src-adj-val.neg {{ color: var(--put); }}
  .src-adj-label {{ font-size: 9px; color: #64748b; text-transform: uppercase; }}
  .src-factors {{ font-size: 10px; color: #64748b; margin-top: 8px; }}

  /* Modal overlay */
  .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,.45); z-index: 100; justify-content: center;
                    align-items: center; }}
  .modal-overlay.open {{ display: flex; }}
  .modal-box {{ background: #fff; border-radius: 12px; padding: 24px; width: 680px;
                max-width: 95vw; max-height: 90vh; overflow-y: auto;
                box-shadow: 0 8px 32px rgba(0,0,0,.25); position: relative; }}
  .modal-close {{ position: absolute; top: 12px; right: 16px; font-size: 20px;
                  cursor: pointer; color: #64748b; background: none; border: none; }}
  .modal-close:hover {{ color: #1e293b; }}
  .modal-title {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; color: #1e293b; }}
  .modal-subtitle {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
  .modal-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
  .modal-stat {{ background: #f1f5f9; border-radius: 8px; padding: 10px 14px; min-width: 90px; }}
  .modal-stat .val {{ font-size: 20px; font-weight: 700; }}
  .modal-stat .lbl {{ font-size: 10px; text-transform: uppercase; color: #64748b; }}
  .modal-stat.drop .val {{ color: var(--put); }}
  .modal-stat.rise .val {{ color: var(--call); }}

  .footer {{ text-align: center; padding: 18px; font-size: 11px; color: #94a3b8; }}

  /* ── Info-icon tooltips ─────────────────────────────────────── */
  .info-icon {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 14px; height: 14px; border-radius: 50%; background: #94a3b8;
    color: #fff; font-size: 9px; font-weight: 700; font-style: normal;
    margin-left: 4px; cursor: help; position: relative; vertical-align: middle;
    flex-shrink: 0; line-height: 1;
  }}
  .info-icon:hover {{ background: #3b82f6; }}
  .info-tip {{
    display: none; position: absolute; bottom: calc(100% + 8px); left: 50%;
    transform: translateX(-50%); width: 290px; padding: 10px 12px;
    background: #1e293b; color: #f1f5f9; font-size: 11px; font-weight: 400;
    line-height: 1.45; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.3);
    z-index: 200; text-transform: none; letter-spacing: 0; white-space: normal;
    pointer-events: auto;
  }}
  .info-tip::after {{
    content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    border: 6px solid transparent; border-top-color: #1e293b;
  }}
  .info-icon:hover .info-tip, .info-tip.active {{ display: block; }}
  /* Right-edge tooltips: shift left so they don't overflow */
  th:nth-child(n+18) .info-tip {{ left: auto; right: 0; transform: none; }}
  th:nth-child(n+18) .info-tip::after {{ left: auto; right: 12px; transform: none; }}
  .info-tip b {{ color: #93c5fd; }}
  .info-tip .src-tag {{ display: inline-block; background: #334155; padding: 1px 5px;
    border-radius: 3px; font-size: 10px; margin: 2px 2px 0 0; }}

  @media (max-width: 900px) {{
    .cards {{ padding: 12px; gap: 8px; }}
    .controls {{ padding: 8px 12px; }}
    .table-wrap {{ padding: 0 8px 16px; }}
    .controls input {{ width: 100%; }}
    .info-tip {{ width: 220px; }}
  }}

  /* ── Rules Column ───────────────────────────────────────────── */
  .col-rules {{ text-align: center; white-space: nowrap; }}
  .rules-btn {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; border: none; border-radius: 6px; padding: 4px 10px;
    font-size: 11px; font-weight: 600; cursor: pointer; letter-spacing: .3px;
    transition: all .2s; display: inline-flex; align-items: center; gap: 4px;
  }}
  .rules-btn:hover {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); transform: translateY(-1px); box-shadow: 0 2px 8px rgba(99,102,241,.35); }}

  /* ── AI Intelligence Column ─────────────────────────────────── */
  .col-ai {{ text-align: center; white-space: nowrap; }}
  .ai-badge {{
    display: inline-flex; align-items: center; gap: 3px;
    padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700;
    letter-spacing: .4px; border: 1.5px solid transparent;
  }}
  .ai-low {{ background: #dcfce7; color: #166534; border-color: #86efac; }}
  .ai-med {{ background: #fef9c3; color: #854d0e; border-color: #fde047; }}
  .ai-high {{ background: #fee2e2; color: #991b1b; border-color: #fca5a5; }}
  .ai-ext {{ background: #dc2626; color: #fff; border-color: #b91c1c; animation: ai-pulse 1.5s infinite; }}
  @keyframes ai-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
  .ai-anomaly-dot {{ color: #f59e0b; font-size: 12px; cursor: help; }}
  .ai-ext .ai-anomaly-dot {{ color: #fef08a; }}

  /* ── Inline Trading Detail Row ──────────────────────────────── */
  .detail-row {{ display: none; }}
  .detail-row.open {{ display: table-row; }}
  .detail-row > td {{ padding: 0 !important; border-bottom: 2px solid #3b82f6; background: #f8fafc; }}
  .detail-panel {{
    display: flex; gap: 0; padding: 16px 20px; min-height: 220px;
    border-top: 2px solid #3b82f6;
  }}
  .detail-chart-wrap {{
    flex: 1 1 60%; min-width: 0; position: relative;
  }}
  .detail-chart-title {{
    font-size: 11px; font-weight: 700; color: #475569; margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: .5px;
  }}
  .detail-canvas {{
    width: 100%; height: 200px; border: 1px solid #e2e8f0; border-radius: 8px;
    background: #fff;
  }}
  .detail-legend {{
    display: flex; gap: 14px; margin-top: 6px; font-size: 10px; color: #64748b;
  }}
  .detail-legend span {{ display: flex; align-items: center; gap: 4px; }}
  .detail-legend .leg-dot {{
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  }}
  .detail-legend .leg-line {{
    width: 16px; height: 2px; display: inline-block; border-radius: 1px;
  }}
  .detail-info-wrap {{
    flex: 0 0 320px; padding-left: 20px; border-left: 1px solid #e2e8f0;
    display: flex; flex-direction: column; gap: 10px; overflow-y: auto; max-height: 260px;
  }}
  .detail-section {{ }}
  .detail-section h4 {{
    font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
    letter-spacing: .6px; margin: 0 0 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px;
  }}
  .detail-signals {{ display: flex; flex-direction: column; gap: 4px; }}
  .detail-sig-row {{
    display: flex; align-items: center; gap: 6px; font-size: 11px;
  }}
  .detail-sig-name {{ width: 80px; font-weight: 600; color: #475569; white-space: nowrap; }}
  .detail-sig-bar {{ flex: 1; height: 10px; background: #e2e8f0; border-radius: 5px; overflow: hidden; position: relative; }}
  .detail-sig-fill {{ height: 100%; border-radius: 5px; transition: width .3s; }}
  .detail-sig-fill.fc {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
  .detail-sig-fill.hist {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
  .detail-sig-fill.ml {{ background: linear-gradient(90deg, #8b5cf6, #a78bfa); }}
  .detail-sig-val {{ font-size: 10px; color: #64748b; width: 60px; text-align: right; white-space: nowrap; }}
  .detail-adj-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  }}
  .detail-adj-item {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 5px 8px; text-align: center;
  }}
  .detail-adj-val {{ font-size: 13px; font-weight: 700; }}
  .detail-adj-val.pos {{ color: var(--call); }}
  .detail-adj-val.neg {{ color: var(--put); }}
  .detail-adj-val.zero {{ color: #94a3b8; }}
  .detail-adj-label {{ font-size: 8px; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; }}
  .detail-meta-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 3px; font-size: 10px;
  }}
  .detail-meta-item {{ display: flex; justify-content: space-between; padding: 2px 0; }}
  .detail-meta-key {{ color: #94a3b8; }}
  .detail-meta-val {{ font-weight: 600; color: #475569; }}
  .expand-btn {{
    background: none; border: none; cursor: pointer; font-size: 11px;
    color: #64748b; padding: 0 3px; transition: transform .2s;
  }}
  .expand-btn:hover {{ color: #3b82f6; }}
  .expand-btn.open {{ transform: rotate(180deg); }}
  @media (max-width: 900px) {{
    .detail-panel {{ flex-direction: column; }}
    .detail-info-wrap {{ flex: auto; padding-left: 0; padding-top: 12px; border-left: none; border-top: 1px solid #e2e8f0; max-height: none; }}
  }}

  /* ── Rules Modal / Panel ────────────────────────────────────── */
  .rules-overlay {{
    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,.5); z-index: 300; justify-content: center; align-items: flex-start;
    padding-top: 60px;
  }}
  .rules-overlay.open {{ display: flex; }}
  .rules-panel {{
    background: #fff; border-radius: 14px; padding: 0; width: 520px;
    max-width: 95vw; max-height: 80vh; overflow-y: auto;
    box-shadow: 0 12px 48px rgba(0,0,0,.3); position: relative;
  }}
  .rules-panel-header {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; padding: 18px 24px; border-radius: 14px 14px 0 0;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .rules-panel-header h2 {{ font-size: 16px; font-weight: 700; margin: 0; }}
  .rules-panel-header .rules-close {{
    background: rgba(255,255,255,.2); border: none; color: #fff; font-size: 18px;
    cursor: pointer; border-radius: 50%; width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
  }}
  .rules-panel-header .rules-close:hover {{ background: rgba(255,255,255,.35); }}
  .rules-panel-body {{ padding: 20px 24px; }}

  .rules-context {{
    background: #f1f5f9; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;
    font-size: 12px; color: #475569; line-height: 1.5;
  }}
  .rules-context .ctx-label {{ font-weight: 700; color: #1e293b; }}
  .rules-context .ctx-val {{ color: #6366f1; font-weight: 600; }}

  /* Scope selector */
  .rules-scope {{ margin-bottom: 18px; }}
  .rules-scope h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .scope-options {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .scope-opt {{
    flex: 1; min-width: 130px; padding: 10px 12px; border: 2px solid var(--border);
    border-radius: 8px; cursor: pointer; text-align: center; transition: all .15s;
    background: #fff;
  }}
  .scope-opt:hover {{ border-color: #a5b4fc; background: #eef2ff; }}
  .scope-opt.selected {{ border-color: #6366f1; background: #eef2ff; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }}
  .scope-opt .scope-icon {{ font-size: 20px; display: block; margin-bottom: 4px; }}
  .scope-opt .scope-label {{ font-size: 12px; font-weight: 600; color: #1e293b; }}
  .scope-opt .scope-desc {{ font-size: 10px; color: #64748b; margin-top: 2px; }}

  /* Preset buttons */
  .rules-presets {{ margin-bottom: 18px; }}
  .rules-presets h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .preset-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }}
  .preset-card {{
    padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px;
    cursor: pointer; transition: all .15s; background: #fff; text-align: center;
  }}
  .preset-card:hover {{ border-color: #a5b4fc; background: #eef2ff; transform: translateY(-1px); }}
  .preset-card.selected {{ border-color: #6366f1; background: #eef2ff; box-shadow: 0 0 0 2px rgba(99,102,241,.2); }}
  .preset-card .preset-icon {{ font-size: 22px; display: block; margin-bottom: 2px; }}
  .preset-card .preset-name {{ font-size: 11px; font-weight: 700; color: #1e293b; }}
  .preset-card .preset-desc {{ font-size: 10px; color: #64748b; margin-top: 3px; line-height: 1.3; }}

  /* Custom rules section */
  .rules-custom {{ margin-bottom: 18px; }}
  .rules-custom h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .custom-rule-row {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
    padding: 8px 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border);
  }}
  .custom-rule-row label {{ font-size: 11px; font-weight: 600; color: #475569; min-width: 90px; }}
  .custom-rule-row input, .custom-rule-row select {{
    padding: 5px 8px; border: 1px solid var(--border); border-radius: 5px;
    font-size: 12px; width: 120px;
  }}
  .custom-rule-row .rule-toggle {{
    width: 36px; height: 20px; border-radius: 10px; border: none;
    background: #cbd5e1; cursor: pointer; position: relative; transition: background .2s;
  }}
  .custom-rule-row .rule-toggle.on {{ background: #6366f1; }}
  .custom-rule-row .rule-toggle::after {{
    content: ''; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
    border-radius: 50%; background: #fff; transition: left .2s;
  }}
  .custom-rule-row .rule-toggle.on::after {{ left: 18px; }}

  /* Action buttons */
  .rules-actions {{
    display: flex; gap: 10px; justify-content: flex-end; padding-top: 14px;
    border-top: 1px solid var(--border);
  }}
  .rules-actions button {{
    padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all .15s;
  }}
  .btn-cancel {{
    background: #fff; color: #64748b; border: 1px solid var(--border);
  }}
  .btn-cancel:hover {{ background: #f1f5f9; }}
  .btn-apply {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; border: none;
  }}
  .btn-apply:hover {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); box-shadow: 0 2px 8px rgba(99,102,241,.35); }}

  /* Toast notification */
  .rules-toast {{
    position: fixed; bottom: 24px; right: 24px; background: #1e293b; color: #f8fafc;
    padding: 12px 20px; border-radius: 10px; font-size: 13px; font-weight: 500;
    box-shadow: 0 4px 16px rgba(0,0,0,.25); z-index: 400;
    transform: translateY(80px); opacity: 0; transition: all .3s ease;
  }}
  .rules-toast.show {{ transform: translateY(0); opacity: 1; }}
  .rules-toast .toast-icon {{ margin-right: 8px; }}
</style>
</head>
<body>

<div class="top-bar">
  <h1>SalesOffice &mdash; Options Board</h1>
  <span class="ts">Last run: {_html_escape(str(run_ts))}</span>
</div>

<div class="cards">
  <div class="card c-total"><div class="num-big">{total}</div><div class="label">Total Options</div></div>
  <div class="card c-call"><div class="num-big">{calls}</div><div class="label">CALL</div></div>
  <div class="card c-put"><div class="num-big">{puts}</div><div class="label">PUT</div></div>
  <div class="card c-neut"><div class="num-big">{neutrals}</div><div class="label">Neutral</div></div>
</div>

<div class="controls">
  <label for="search">Search:</label>
  <input id="search" type="text" placeholder="Filter by hotel name, category...">
  <label for="sig-filter">Signal:</label>
  <select id="sig-filter">
    <option value="">All</option>
    <option value="CALL">CALL</option>
    <option value="PUT">PUT</option>
    <option value="NEUTRAL">NEUTRAL</option>
  </select>
  <label for="q-filter">Quality:</label>
  <select id="q-filter">
    <option value="">All</option>
    <option value="HIGH">HIGH</option>
    <option value="MEDIUM">MEDIUM</option>
    <option value="LOW">LOW</option>
  </select>
</div>

<div class="table-wrap">
<table id="opts-table">
<thead><tr>
  <th data-col="0" data-type="num" class="sticky-col sc-id">ID<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Detail ID</b><br>Unique room identifier from SalesOffice DB.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="1" data-type="str" class="sticky-col sc-hotel">Hotel<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Hotel Name</b><br>Property name from Med_Hotels table joined via HotelID.<br><span class="src-tag">Med_Hotels</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="2" data-type="str">Category<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Room Category</b><br>Mapped from RoomCategoryID: 1=Standard, 2=Superior, 4=Deluxe, 12=Suite. Affects forward-curve category offset in prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="3" data-type="str">Board<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Board Type</b><br>Meal plan from BoardId: RO, BB, HB, FB, AI, etc. Adds a board offset to the forward curve prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="4" data-type="str">Check-in<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Check-in Date</b><br>Booked arrival date from the order. This is the target date (T=0) for the forward curve walk.<br><span class="src-tag">SalesOffice.Orders</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="5" data-type="num">Days<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Days to Check-in</b><br>Calendar days from today to check-in. This is the T value &mdash; how many steps the forward curve walks.<br>Formula: <b>check_in_date &minus; today</b></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="6" data-type="str">Signal<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Option Signal (CALL / PUT / NEUTRAL)</b><br>&bull; <b>CALL</b>: price expected to rise (&ge;0.5%) or prob_up &gt; prob_down+0.1<br>&bull; <b>PUT</b>: price expected to drop (&le;&minus;0.5%) or prob_down &gt; prob_up+0.1<br>&bull; <b>L1-L10</b>: confidence level (65% change magnitude + 35% probability &times; quality)<br><span class="src-tag">Forward Curve 50%</span> <span class="src-tag">Historical 30%</span> <span class="src-tag">ML 20%</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="7" data-type="num">Current $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Current Room Price</b><br>Latest price from the most recent hourly scan of SalesOffice.Details. This is the starting point for the forward curve.<br><span class="src-tag">SalesOffice.Details</span> <span class="src-tag">Hourly scan</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="8" data-type="num">Predicted $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Predicted Check-in Price (Ensemble)</b><br>Weighted ensemble of 2-3 signals:<br>&bull; <b>Forward Curve (50%)</b>: day-by-day walk with decay + events + season + weather adjustments<br>&bull; <b>Historical Pattern (30%)</b>: same-month prior-year average + lead-time adjustment<br>&bull; <b>ML Model (20%)</b>: if trained model exists (currently inactive)<br>Weights are scaled by each signal's confidence then normalized.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Open-Meteo</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="9" data-type="num">Change %<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Price Change %</b><br>Percentage difference between predicted check-in price and current price.<br>Formula: <b>(predicted &divide; current &minus; 1) &times; 100</b><br>Green = price expected to rise, Red = expected to drop.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="10" data-type="num" class="src-col">FC $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Forward Curve Prediction</b><br>Price predicted by the <b>Forward Curve</b> model alone (weight ~50%).<br>Day-by-day random walk with:<br>&bull; Decay rate from {'{'}model_info.total_tracks{'}'} price tracks<br>&bull; Event adjustments (Miami events, holidays)<br>&bull; Season adjustments (monthly ADR patterns)<br>&bull; Demand adjustments (flight demand index)<br>&bull; Momentum adjustments (recent price trend)<br>Hover for full adjustment breakdown.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span> <span class="src-tag">Flights</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="11" data-type="num" class="src-col">Hist $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Historical Pattern Prediction</b><br>Price predicted by <b>Historical Patterns</b> alone (weight ~30%).<br>Same-month prior-year average price adjusted by:<br>&bull; Lead-time offset (how far from check-in)<br>&bull; Day-of-week patterns<br>&bull; Year-over-year trend<br>Only available when historical data exists for this hotel/period combination.<br><span class="src-tag">medici-db Historical</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="12" data-type="num">Min $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Minimum Price</b><br>Lowest price point on the forward curve between now and check-in.<br>Formula: <b>min(all daily predicted prices)</b><br>This is the predicted best buying opportunity in the path.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="13" data-type="num">Max $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Maximum Price</b><br>Highest price point on the forward curve between now and check-in.<br>Formula: <b>max(all daily predicted prices)</b><br>Peak predicted price before check-in.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="14" data-type="str">Touches<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Touches Min / Max</b><br>How many times the forward curve touches the min and max price levels (within $0.01).<br>Format: <b>min_touches / max_touches</b><br>High touch count = price lingers at that level (support/resistance).</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="15" data-type="num">Big Moves<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Big Price Moves (&gt;$20)</b><br>Count of day-to-day predicted price changes greater than $20 on the forward curve.<br>More big moves = higher volatility expected.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="16" data-type="num">Exp Drops<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Price Drops</b><br>Number of day-to-day drops predicted by the forward curve between now and check-in.<br>Higher count for PUT signals = more predicted decline episodes.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="17" data-type="str">Quality<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Prediction Quality Score</b><br>Blended confidence metric:<br>&bull; 60% from data availability (scan count, price history depth, hotel coverage)<br>&bull; 40% from mean signal confidence<br>Levels: <b>HIGH</b> (&ge;0.75), <b>MEDIUM</b> (&ge;0.50), <b>LOW</b> (&lt;0.50)<br>Higher = more data backing the prediction.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="18" data-type="num">Scans<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Count (Actual)</b><br>Number of real price snapshots collected from medici-db since tracking started (Feb 23).<br>Scanned every ~3 hours. More scans = better trend visibility.<br><span class="src-tag">SalesOffice.Details.DateCreated</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="19" data-type="num">1st Price<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>First Scan Price</b><br>The room price at the earliest recorded scan. Used as baseline to measure actual price movement since tracking began.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="20" data-type="str">Actual D/R<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Actual Drops / Rises (Observed)</b><br>Real price drops and rises observed across actual scans &mdash; NOT predictions.<br>&bull; <b style="color:#ef4444">Red number&#9660;</b> = count of scans where price decreased<br>&bull; <b style="color:#22c55e">Green number&#9650;</b> = count of scans where price increased<br>Hover for total $ amounts and max single move.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="21" data-type="num">Scan Chg%<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Price Change %</b><br>Actual price change from first scan to current price.<br>Formula: <b>(latest &minus; first) &divide; first &times; 100</b><br>Trend badge: &#9650; up, &#9660; down, &#9644; stable.<br>This is REAL observed data, not a prediction.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="22" data-type="str">Chart<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Price Chart</b><br>Click &#128200; to view price history chart showing all actual scan prices over time with colored dots (red=drop, green=rise).<br>Requires &ge;2 scans.</span></span></th>
  <th data-col="23" data-type="str">PUT Detail<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>PUT Decline Details</b><br>Breakdown of predicted downward moves on the forward curve:<br>&bull; <b>drops</b>: count of decline days<br>&bull; <b>total $</b>: sum of all daily drops<br>&bull; <b>max $</b>: largest single-day drop<br>Only shown for rooms with predicted declines.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="24" data-type="num">Mkt &#9733;$<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Market Benchmark (same &#9733; avg)</b><br>Average price of all other hotels with the <b>same star rating</b> in the <b>same city</b> from AI_Search_HotelData (8.5M records, 6K+ hotels, 323 cities).<br>&bull; <b style="color:#22c55e">Green</b>: our price &lt; market avg (well-positioned)<br>&bull; <b style="color:#ef4444">Red</b>: our price &gt; market avg (premium priced)<br>Hover for N competitor hotels and city.<br><span class="src-tag">AI_Search_HotelData</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="25" data-type="str">Rules<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Pricing Rules</b><br>Set pricing rules for this room, hotel, or all hotels.<br>&bull; <b>Scope</b>: This row / This hotel / All hotels<br>&bull; <b>Presets</b>: Conservative, Moderate, Aggressive, Seasonal High, Fire Sale, Wait for Drop, Exclude AI<br>&bull; <b>Custom</b>: Price ceiling/floor, markup %, target price, category/board exclusions<br>Rules are applied at Step 5 (Flatten &amp; Group) of the SalesOffice scanning pipeline.<br><span class="src-tag">Rules Engine</span></span></span></th>
  <th data-col="26" data-type="str">AI<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>AI Intelligence</b><br>Claude-powered risk assessment and anomaly detection.<br>&bull; <b style="color:#22c55e">LOW</b>: Standard conditions, low risk<br>&bull; <b style="color:#f59e0b">MED</b>: Moderate risk, some uncertainty<br>&bull; <b style="color:#ef4444">HIG</b>: High risk, large predicted moves or limited data<br>&bull; <b style="color:#dc2626">EXT</b>: Extreme risk, urgent review needed<br>&bull; &#9888; = Anomaly detected (spike, dip, stale, divergence)<br>Click <a href="/api/v1/salesoffice/options/ai-insights" style="color:#60a5fa">AI Insights</a> for full analysis.<br><span class="src-tag">AI Intelligence Engine</span></span></span></th>
</tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="footer">
  Medici Price Prediction &mdash; Options Dashboard
  &bull; {total} rows
  &bull; T={t_days or "all"} days
  &bull; <a href="/api/v1/salesoffice/options?profile=lite" style="color:#3b82f6">JSON API</a>
  &bull; <a href="/api/v1/salesoffice/options/legend" style="color:#3b82f6">Legend</a>
  &bull; <a href="/api/v1/salesoffice/options/ai-insights" style="color:#a78bfa">&#129302; AI Insights</a>
</div>

<!-- Scan Chart Modal -->
<div id="chart-modal" class="modal-overlay">
  <div class="modal-box">
    <button class="modal-close" onclick="closeChart()">&times;</button>
    <div class="modal-title" id="chart-title"></div>
    <div class="modal-subtitle" id="chart-subtitle"></div>
    <div class="modal-stats" id="chart-stats"></div>
    <canvas id="chart-canvas" width="620" height="260" style="width:100%;border:1px solid #e5e7eb;border-radius:8px"></canvas>
  </div>
</div>

<!-- Source Detail Modal -->
<div id="src-overlay" class="src-overlay">
  <div class="src-box">
    <button class="src-close" onclick="closeSources()">&times;</button>
    <div class="src-title" id="src-title">Prediction Sources</div>
    <div class="src-subtitle" id="src-subtitle"></div>
    <div class="src-signals" id="src-signals"></div>
    <div class="src-adj">
      <h4>&#128200; Forward Curve Adjustments</h4>
      <div class="src-adj-grid" id="src-adjustments"></div>
    </div>
    <div class="src-factors" id="src-factors" style="display:none"></div>
  </div>
</div>

<!-- Rules Panel Modal -->
<div id="rules-overlay" class="rules-overlay">
  <div class="rules-panel">
    <div class="rules-panel-header">
      <h2>&#9881; Pricing Rules</h2>
      <button class="rules-close" onclick="closeRulesPanel()">&times;</button>
    </div>
    <div class="rules-panel-body">
      <!-- Context info -->
      <div class="rules-context" id="rules-context">
        <span class="ctx-label">Room:</span> <span class="ctx-val" id="rc-room">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Hotel:</span> <span class="ctx-val" id="rc-hotel">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Price:</span> <span class="ctx-val" id="rc-price">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Signal:</span> <span class="ctx-val" id="rc-signal">-</span>
      </div>

      <!-- Scope selector -->
      <div class="rules-scope">
        <h3>&#127919; Apply Scope</h3>
        <div class="scope-options">
          <div class="scope-opt selected" data-scope="row" onclick="selectScope(this)">
            <span class="scope-icon">&#128196;</span>
            <span class="scope-label">This Room</span>
            <span class="scope-desc">Only this specific room option</span>
          </div>
          <div class="scope-opt" data-scope="hotel" onclick="selectScope(this)">
            <span class="scope-icon">&#127976;</span>
            <span class="scope-label" id="scope-hotel-label">This Hotel</span>
            <span class="scope-desc">All rooms for this hotel</span>
          </div>
          <div class="scope-opt" data-scope="all" onclick="selectScope(this)">
            <span class="scope-icon">&#127758;</span>
            <span class="scope-label">All Hotels</span>
            <span class="scope-desc">Apply to every hotel</span>
          </div>
        </div>
      </div>

      <!-- Preset selection -->
      <div class="rules-presets">
        <h3>&#9889; Quick Presets</h3>
        <div class="preset-grid">
          <div class="preset-card" data-preset="conservative" onclick="selectPreset(this)">
            <span class="preset-icon">&#128737;</span>
            <span class="preset-name">Conservative</span>
            <span class="preset-desc">Low markup, tight ceiling, safe floor</span>
          </div>
          <div class="preset-card" data-preset="moderate" onclick="selectPreset(this)">
            <span class="preset-icon">&#9878;</span>
            <span class="preset-name">Moderate</span>
            <span class="preset-desc">Balanced markup with reasonable bounds</span>
          </div>
          <div class="preset-card" data-preset="aggressive" onclick="selectPreset(this)">
            <span class="preset-icon">&#128640;</span>
            <span class="preset-name">Aggressive</span>
            <span class="preset-desc">Higher markup, wider price range</span>
          </div>
          <div class="preset-card" data-preset="seasonal_high" onclick="selectPreset(this)">
            <span class="preset-icon">&#9728;</span>
            <span class="preset-name">Seasonal High</span>
            <span class="preset-desc">Peak season premium pricing</span>
          </div>
          <div class="preset-card" data-preset="fire_sale" onclick="selectPreset(this)">
            <span class="preset-icon">&#128293;</span>
            <span class="preset-name">Fire Sale</span>
            <span class="preset-desc">Deep discount, move inventory fast</span>
          </div>
          <div class="preset-card" data-preset="wait_for_drop" onclick="selectPreset(this)">
            <span class="preset-icon">&#9202;</span>
            <span class="preset-name">Wait for Drop</span>
            <span class="preset-desc">Hold until price drops below threshold</span>
          </div>
          <div class="preset-card" data-preset="exclude_ai" onclick="selectPreset(this)">
            <span class="preset-icon">&#128683;</span>
            <span class="preset-name">Exclude AI</span>
            <span class="preset-desc">No AI pricing &mdash; use supplier price</span>
          </div>
        </div>
      </div>

      <!-- Custom rules -->
      <div class="rules-custom">
        <h3>&#128295; Custom Rules</h3>
        <div class="custom-rule-row">
          <label>Price Ceiling</label>
          <input type="number" id="rule-ceiling" placeholder="Max price $" step="1">
          <span style="font-size:11px;color:#64748b">Maximum allowed price</span>
        </div>
        <div class="custom-rule-row">
          <label>Price Floor</label>
          <input type="number" id="rule-floor" placeholder="Min price $" step="1">
          <span style="font-size:11px;color:#64748b">Minimum allowed price</span>
        </div>
        <div class="custom-rule-row">
          <label>Markup %</label>
          <input type="number" id="rule-markup" placeholder="e.g. 5" step="0.5" min="-50" max="100">
          <span style="font-size:11px;color:#64748b">Add/subtract % from predicted</span>
        </div>
        <div class="custom-rule-row">
          <label>Target Price</label>
          <input type="number" id="rule-target" placeholder="Override price $" step="1">
          <span style="font-size:11px;color:#64748b">Force a specific price</span>
        </div>
      </div>

      <!-- Summary of what will be applied -->
      <div id="rules-summary" style="display:none; background:#eef2ff; border-radius:8px; padding:12px 16px; margin-bottom:14px; font-size:12px; color:#4338ca; border:1px solid #c7d2fe;">
        <strong>&#9989; Rules to apply:</strong> <span id="rules-summary-text"></span>
      </div>

      <!-- Actions -->
      <div class="rules-actions">
        <button class="btn-cancel" onclick="closeRulesPanel()">Cancel</button>
        <button class="btn-apply" onclick="applyRules()">&#9889; Apply Rules</button>
      </div>
    </div>
  </div>
</div>

<!-- Toast notification -->
<div id="rules-toast" class="rules-toast">
  <span class="toast-icon">&#9989;</span> <span id="toast-msg">Rules applied</span>
</div>

<script>
/* ── Info-tip click toggle (global) ──────────────────────── */
function toggleTip(el, e) {{
  if (!e) e = window.event;
  /* If clicked on the tooltip text itself, stop propagation and return (don't close) */
  if (e && e.target && e.target.closest && e.target.closest('.info-tip')) {{
    if (e.stopPropagation) e.stopPropagation();
    return;
  }}
  var tip = el.querySelector('.info-tip');
  if (!tip) return;
  var isOpen = tip.classList.contains('active');
  document.querySelectorAll('.info-tip.active').forEach(function(t) {{ t.classList.remove('active'); }});
  if (!isOpen) tip.classList.add('active');
  if (e && e.stopPropagation) e.stopPropagation();
}}
document.addEventListener('click', function() {{
  document.querySelectorAll('.info-tip.active').forEach(function(t) {{ t.classList.remove('active'); }});
}});

(function() {{
  const table = document.getElementById('opts-table');
  const tbody = table.querySelector('tbody');
  const headers = table.querySelectorAll('th');
  const searchBox = document.getElementById('search');
  const sigFilter = document.getElementById('sig-filter');
  const qFilter = document.getElementById('q-filter');

  // Sort
  let sortCol = -1, sortAsc = true;
  headers.forEach(th => {{
    th.addEventListener('click', function(e) {{
      if (e.target.closest('.info-icon')) return;   /* skip sort when clicking info */
      const col = parseInt(this.dataset.col);
      const type = this.dataset.type;
      if (sortCol === col) {{ sortAsc = !sortAsc; }} else {{ sortCol = col; sortAsc = true; }}
      headers.forEach(h => h.classList.remove('sorted'));
      this.classList.add('sorted');
      const arrow = this.querySelector('.arrow');
      if (arrow) arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';

      const rowsArr = Array.from(tbody.querySelectorAll('tr'));
      rowsArr.sort((a, b) => {{
        let av = a.children[col].textContent.trim();
        let bv = b.children[col].textContent.trim();
        if (type === 'num') {{
          av = parseFloat(av.replace(/[$,%,\\s,\\u25B2,\\u25BC,\\u2594]/g, '')) || 0;
          bv = parseFloat(bv.replace(/[$,%,\\s,\\u25B2,\\u25BC,\\u2594]/g, '')) || 0;
          return sortAsc ? av - bv : bv - av;
        }}
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
      rowsArr.forEach(r => tbody.appendChild(r));
    }});
  }});

  // Filter
  function applyFilters() {{
    const q = searchBox.value.toLowerCase();
    const sig = sigFilter.value;
    const qual = qFilter.value;
    const allRows = tbody.querySelectorAll('tr');
    allRows.forEach(r => {{
      const text = r.textContent.toLowerCase();
      const rSig = r.dataset.signal || '';
      const rQual = r.querySelector('.q-dot') ? r.querySelector('.q-dot').textContent.trim() : '';
      const matchQ = !q || text.includes(q);
      const matchSig = !sig || rSig === sig;
      const matchQual = !qual || rQual === qual;
      r.style.display = (matchQ && matchSig && matchQual) ? '' : 'none';
    }});
  }}
  searchBox.addEventListener('input', applyFilters);
  sigFilter.addEventListener('change', applyFilters);
  qFilter.addEventListener('change', applyFilters);
}})();

/* ── Chart Modal Functions ──────────────────────────────────────── */
function showChart(detailId, hotelName, seriesJson) {{
  let series;
  try {{ series = JSON.parse(seriesJson); }} catch(e) {{ return; }}
  if (!series || series.length < 2) return;

  const modal = document.getElementById('chart-modal');
  const canvas = document.getElementById('chart-canvas');
  const ctx = canvas.getContext('2d');

  // Title
  document.getElementById('chart-title').textContent =
    'Scan Price History — ' + hotelName + ' (ID: ' + detailId + ')';
  document.getElementById('chart-subtitle').textContent =
    series.length + ' scans from ' + series[0].date.substring(0,10) +
    ' to ' + series[series.length-1].date.substring(0,10);

  // Stats
  const prices = series.map(s => s.price);
  const firstP = prices[0], lastP = prices[prices.length-1];
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  let drops=0, rises=0;
  for (let i=1; i<prices.length; i++) {{
    if (prices[i] < prices[i-1] - 0.01) drops++;
    else if (prices[i] > prices[i-1] + 0.01) rises++;
  }}
  const chg = lastP - firstP;
  const chgPct = firstP > 0 ? (chg / firstP * 100) : 0;

  document.getElementById('chart-stats').innerHTML =
    '<div class="modal-stat"><div class="val">$' + firstP.toFixed(0) + '</div><div class="lbl">First Scan</div></div>' +
    '<div class="modal-stat"><div class="val">$' + lastP.toFixed(0) + '</div><div class="lbl">Latest</div></div>' +
    '<div class="modal-stat drop"><div class="val">' + drops + '</div><div class="lbl">Drops &#9660;</div></div>' +
    '<div class="modal-stat rise"><div class="val">' + rises + '</div><div class="lbl">Rises &#9650;</div></div>' +
    '<div class="modal-stat"><div class="val">$' + minP.toFixed(0) + '</div><div class="lbl">Min</div></div>' +
    '<div class="modal-stat"><div class="val">$' + maxP.toFixed(0) + '</div><div class="lbl">Max</div></div>' +
    '<div class="modal-stat ' + (chg < 0 ? 'drop' : 'rise') + '">' +
    '<div class="val">' + (chg >= 0 ? '+' : '') + chgPct.toFixed(1) + '%</div>' +
    '<div class="lbl">Total Change</div></div>';

  // Draw chart on canvas
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const padL = 60, padR = 20, padT = 20, padB = 40;
  const cw = W - padL - padR, ch = H - padT - padB;
  const pRange = maxP - minP || 1;
  const n = prices.length;

  // Grid
  ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 0.5;
  for (let i=0; i<=4; i++) {{
    const y = padT + ch * i / 4;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + cw, y); ctx.stroke();
    const pLabel = maxP - (pRange * i / 4);
    ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + pLabel.toFixed(0), padL - 6, y + 4);
  }}

  // X axis labels
  ctx.fillStyle = '#94a3b8'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(n / 6));
  for (let i=0; i<n; i+=step) {{
    const x = padL + (i / (n-1)) * cw;
    ctx.fillText(series[i].date.substring(5,10), x, H - 8);
  }}

  // Price line
  ctx.beginPath();
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
  for (let i=0; i<n; i++) {{
    const x = padL + (i / (n-1)) * cw;
    const y = padT + ch - ((prices[i] - minP) / pRange) * ch;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  // Fill under
  const lastX = padL + cw;
  ctx.lineTo(lastX, padT + ch); ctx.lineTo(padL, padT + ch); ctx.closePath();
  ctx.fillStyle = 'rgba(59,130,246,.08)'; ctx.fill();

  // Dots on price changes
  for (let i=0; i<n; i++) {{
    const x = padL + (i / (n-1)) * cw;
    const y = padT + ch - ((prices[i] - minP) / pRange) * ch;
    let color = '#3b82f6';
    if (i > 0 && prices[i] < prices[i-1] - 0.01) color = '#dc2626';
    else if (i > 0 && prices[i] > prices[i-1] + 0.01) color = '#16a34a';
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
  }}

  modal.classList.add('open');
}}

function closeChart() {{
  document.getElementById('chart-modal').classList.remove('open');
}}
document.getElementById('chart-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeChart();
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') {{ closeChart(); closeRulesPanel(); closeSources(); }}
}});

/* ── Inline Trading Detail Panel ────────────────────────────── */
function toggleDetail(detailId) {{
  var row = document.getElementById('detail-' + detailId);
  var btn = document.getElementById('eb-' + detailId);
  if (!row) return;
  var isOpen = row.classList.contains('open');
  if (isOpen) {{
    row.classList.remove('open');
    if (btn) btn.classList.remove('open');
  }} else {{
    row.classList.add('open');
    if (btn) btn.classList.add('open');
    // Fetch detail data lazily on first open
    if (!row.dataset.drawn) {{
      row.dataset.drawn = '1';
      var infoWrap = document.getElementById('di-' + detailId);
      if (infoWrap) infoWrap.innerHTML = '<div style="padding:20px;color:#94a3b8;font-size:12px">Loading...</div>';
      fetch('/api/v1/salesoffice/options/detail/' + detailId)
        .then(function(r) {{ return r.json(); }})
        .then(function(dd) {{
          drawTradingChart(detailId, dd);
          buildDetailInfo(detailId, dd);
        }})
        .catch(function(err) {{
          console.error('Detail fetch failed:', err);
          if (infoWrap) infoWrap.innerHTML = '<div style="padding:20px;color:#dc2626;font-size:12px">Failed to load detail data</div>';
        }});
    }}
  }}
}}

function drawTradingChart(detailId, dd) {{
  var canvas = document.getElementById('dc-' + detailId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  var fc = dd.fc || [];
  var scan = dd.scan || [];
  if (fc.length === 0 && scan.length === 0) {{
    ctx.fillStyle = '#94a3b8'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('No chart data available', W/2, H/2);
    return;
  }}

  // Collect all prices to determine Y range
  var allP = [];
  fc.forEach(function(pt) {{ allP.push(pt.p, pt.lo, pt.hi); }});
  scan.forEach(function(pt) {{ allP.push(pt.p); }});
  allP.push(dd.cp, dd.pp);
  var minP = Math.min.apply(null, allP.filter(function(v){{return v>0;}}));
  var maxP = Math.max.apply(null, allP);
  var pPad = (maxP - minP) * 0.08 || 5;
  minP -= pPad; maxP += pPad;
  var pRange = maxP - minP || 1;

  // All dates for X axis (forward curve dates are the main timeline)
  var allDates = fc.map(function(pt){{return pt.d;}});

  // Scans are PAST data, FC is FUTURE. Scans go on the LEFT, FC on the RIGHT
  // Build a unified timeline: [scan dates] + [fc dates]
  var scanDates = scan.map(function(s){{return s.d;}});
  // Remove duplicate dates
  var seen = {{}};
  var timeline = [];
  scanDates.forEach(function(d) {{ if (!seen[d]) {{ seen[d]=1; timeline.push({{d:d, src:'scan'}}); }} }});
  allDates.forEach(function(d) {{ if (!seen[d]) {{ seen[d]=1; timeline.push({{d:d, src:'fc'}}); }} }});

  var n = timeline.length;
  if (n === 0) return;

  var padL = 56, padR = 16, padT = 14, padB = 28;
  var cw = W - padL - padR, ch = H - padT - padB;

  // Helper: date to X
  var dateIdx = {{}};
  timeline.forEach(function(t, i) {{ dateIdx[t.d] = i; }});
  function dateToX(d) {{ var idx = dateIdx[d]; return idx !== undefined ? padL + (idx / Math.max(n-1,1)) * cw : -1; }}
  function priceToY(p) {{ return padT + ch - ((p - minP) / pRange) * ch; }}

  // Background
  ctx.fillStyle = '#fafbfc'; ctx.fillRect(padL, padT, cw, ch);

  // Grid lines
  ctx.strokeStyle = '#f1f5f9'; ctx.lineWidth = 0.5;
  for (var gi=0; gi<=5; gi++) {{
    var gy = padT + ch * gi / 5;
    ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL + cw, gy); ctx.stroke();
    var gp = maxP - (pRange * gi / 5);
    ctx.fillStyle = '#94a3b8'; ctx.font = '9px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + gp.toFixed(0), padL - 4, gy + 3);
  }}

  // X axis labels (strip #N suffixes used for uniqueness)
  ctx.fillStyle = '#94a3b8'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(n / 8));
  for (var xi=0; xi<n; xi+=xStep) {{
    var xx = padL + (xi / Math.max(n-1,1)) * cw;
    var lbl = timeline[xi].d.split('#')[0];
    ctx.fillText(lbl, xx, H - 6);
  }}

  // Vertical divider between scan period and FC period
  var firstFcDate = allDates[0];
  var divX = dateToX(firstFcDate);
  if (divX > padL + 10 && scanDates.length > 0) {{
    ctx.save();
    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1; ctx.setLineDash([3,3]);
    ctx.beginPath(); ctx.moveTo(divX, padT); ctx.lineTo(divX, padT+ch); ctx.stroke();
    ctx.restore();
    // Labels
    ctx.fillStyle = '#94a3b8'; ctx.font = 'bold 8px sans-serif';
    ctx.textAlign = 'right'; ctx.fillText('ACTUAL', divX - 4, padT + 10);
    ctx.textAlign = 'left'; ctx.fillText('FORECAST', divX + 4, padT + 10);
  }}

  // ── Confidence band (FC) ──
  if (fc.length > 1) {{
    ctx.beginPath();
    fc.forEach(function(pt, i) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.hi);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }});
    for (var i=fc.length-1; i>=0; i--) {{
      var x = dateToX(fc[i].d); if (x < 0) continue;
      ctx.lineTo(x, priceToY(fc[i].lo));
    }}
    ctx.closePath();
    ctx.fillStyle = 'rgba(59,130,246,.10)'; ctx.fill();
  }}

  // ── Forward Curve line ──
  if (fc.length > 0) {{
    ctx.beginPath();
    ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
    var started = false;
    fc.forEach(function(pt) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.p);
      if (!started) {{ ctx.moveTo(x, y); started = true; }} else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}

  // ── Actual scan line ──
  if (scan.length > 1) {{
    ctx.beginPath();
    ctx.strokeStyle = '#f97316'; ctx.lineWidth = 1.5;
    var started2 = false;
    scan.forEach(function(pt) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.p);
      if (!started2) {{ ctx.moveTo(x, y); started2 = true; }} else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}

  // ── Scan dots ──
  scan.forEach(function(pt, i) {{
    var x = dateToX(pt.d); if (x < 0) return;
    var y = priceToY(pt.p);
    var clr = '#f97316';
    if (i > 0) {{
      if (pt.p < scan[i-1].p - 0.01) clr = '#dc2626';
      else if (pt.p > scan[i-1].p + 0.01) clr = '#16a34a';
    }}
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2);
    ctx.fillStyle = clr; ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.5; ctx.stroke();
  }});

  // ── Current price dashed line ──
  ctx.save();
  ctx.strokeStyle = '#10b981'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  var cpY = priceToY(dd.cp);
  ctx.beginPath(); ctx.moveTo(padL, cpY); ctx.lineTo(padL+cw, cpY); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = '#10b981'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('$' + dd.cp.toFixed(0), padL+cw+2, cpY+3);

  // ── Predicted price dashed line ──
  ctx.save();
  ctx.strokeStyle = '#a855f7'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  var ppY = priceToY(dd.pp);
  ctx.beginPath(); ctx.moveTo(padL, ppY); ctx.lineTo(padL+cw, ppY); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = '#a855f7'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('$' + dd.pp.toFixed(0), padL+cw+2, ppY+3);

  // ── Min/Max markers on FC ──
  if (fc.length > 0) {{
    var mnPt = fc.reduce(function(a,b){{return a.p < b.p ? a : b;}});
    var mxPt = fc.reduce(function(a,b){{return a.p > b.p ? a : b;}});
    // Min marker
    var mnX = dateToX(mnPt.d), mnY = priceToY(mnPt.p);
    if (mnX > 0) {{
      ctx.beginPath(); ctx.arc(mnX, mnY, 4, 0, Math.PI*2);
      ctx.fillStyle = '#ef4444'; ctx.fill();
      ctx.fillStyle = '#ef4444'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('$' + mnPt.p.toFixed(0), mnX, mnY + 13);
    }}
    // Max marker
    var mxX = dateToX(mxPt.d), mxY = priceToY(mxPt.p);
    if (mxX > 0) {{
      ctx.beginPath(); ctx.arc(mxX, mxY, 4, 0, Math.PI*2);
      ctx.fillStyle = '#3b82f6'; ctx.fill();
      ctx.fillStyle = '#3b82f6'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('$' + mxPt.p.toFixed(0), mxX, mxY - 8);
    }}
  }}
}}

function buildDetailInfo(detailId, dd) {{
  var wrap = document.getElementById('di-' + detailId);
  if (!wrap) return;
  var h = '';

  // ── Signal Weights ──
  h += '<div class="detail-section"><h4>Signal Weights</h4><div class="detail-signals">';
  if (dd.fcP) {{
    h += '<div class="detail-sig-row"><span class="detail-sig-name">Forward Curve</span>' +
         '<div class="detail-sig-bar"><div class="detail-sig-fill fc" style="width:' + (dd.fcW*100).toFixed(0) + '%"></div></div>' +
         '<span class="detail-sig-val">$' + dd.fcP.toFixed(0) + ' (' + (dd.fcW*100).toFixed(0) + '%)</span></div>';
  }}
  if (dd.hiP) {{
    h += '<div class="detail-sig-row"><span class="detail-sig-name">Historical</span>' +
         '<div class="detail-sig-bar"><div class="detail-sig-fill hist" style="width:' + (dd.hiW*100).toFixed(0) + '%"></div></div>' +
         '<span class="detail-sig-val">$' + dd.hiP.toFixed(0) + ' (' + (dd.hiW*100).toFixed(0) + '%)</span></div>';
  }}
  h += '</div></div>';

  // ── Adjustments ──
  var adj = dd.adj || {{}};
  h += '<div class="detail-section"><h4>FC Adjustments (cumulative %)</h4><div class="detail-adj-grid">';
  var adjItems = [
    {{k:'Events', v:adj.ev}}, {{k:'Season', v:adj.se}},
    {{k:'Demand', v:adj.dm}}, {{k:'Momentum', v:adj.mo}}
  ];
  adjItems.forEach(function(a) {{
    var cls = a.v > 0.01 ? 'pos' : (a.v < -0.01 ? 'neg' : 'zero');
    h += '<div class="detail-adj-item"><div class="detail-adj-val ' + cls + '">' +
         (a.v >= 0 ? '+' : '') + a.v.toFixed(1) + '%</div>' +
         '<div class="detail-adj-label">' + a.k + '</div></div>';
  }});
  h += '</div></div>';

  // ── Market & Signals ──
  h += '<div class="detail-section"><h4>Key Metrics</h4><div class="detail-meta-grid">';
  var sigClr = dd.sig === 'CALL' ? 'var(--call)' : (dd.sig === 'PUT' ? 'var(--put)' : 'var(--neutral)');
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Signal</span><span class="detail-meta-val" style="color:' + sigClr + '">' + dd.sig + '</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Change</span><span class="detail-meta-val" style="color:' + (dd.chg>=0?'var(--call)':'var(--put)') + '">' + (dd.chg>=0?'+':'') + dd.chg.toFixed(1) + '%</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Quality</span><span class="detail-meta-val">' + dd.q + '</span></div>';
  if (dd.mkt > 0) {{
    h += '<div class="detail-meta-item"><span class="detail-meta-key">Mkt Avg</span><span class="detail-meta-val">$' + dd.mkt.toFixed(0) + '</span></div>';
  }}
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Scans</span><span class="detail-meta-val">' + dd.scans + '</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Actual D/R</span><span class="detail-meta-val">' +
       '<span style="color:var(--put)">' + dd.drops + '&#9660;</span> ' +
       '<span style="color:var(--call)">' + dd.rises + '&#9650;</span></span></div>';
  h += '</div></div>';

  // ── Momentum & Regime ──
  var mom = dd.mom || {{}};
  var reg = dd.reg || {{}};
  if (mom.signal || reg.regime) {{
    h += '<div class="detail-section"><h4>Momentum &amp; Regime</h4><div class="detail-meta-grid">';
    if (mom.signal) {{
      h += '<div class="detail-meta-item"><span class="detail-meta-key">Momentum</span><span class="detail-meta-val">' + mom.signal + '</span></div>';
      if (mom.velocity_24h !== undefined) {{
        h += '<div class="detail-meta-item"><span class="detail-meta-key">Velocity 24h</span><span class="detail-meta-val">' + (mom.velocity_24h >= 0 ? '+' : '') + Number(mom.velocity_24h).toFixed(1) + '%</span></div>';
      }}
    }}
    if (reg.regime) {{
      h += '<div class="detail-meta-item"><span class="detail-meta-key">Regime</span><span class="detail-meta-val">' + reg.regime + '</span></div>';
    }}
    h += '</div></div>';
  }}

  wrap.innerHTML = h;
}}

/* ── Source Detail Modal Functions ───────────────────────────── */
function showSources(btn) {{
  var raw = btn.getAttribute('data-sources');
  if (!raw) return;
  raw = raw.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  var data;
  try {{ data = JSON.parse(raw); }} catch(e) {{ console.error('src parse', e); return; }}

  var hotel = btn.getAttribute('data-hotel') || '';
  var detId = btn.getAttribute('data-detail-id') || '';

  document.getElementById('src-title').textContent = 'Prediction Sources \u2014 ' + hotel;
  document.getElementById('src-subtitle').textContent = 'ID: ' + detId + ' | Method: ' + (data.method || 'ensemble');

  /* Signals */
  var sigHtml = '';
  var colors = {{'Forward Curve':'#3b82f6', 'Historical Pattern':'#f59e0b', 'ML Forecast':'#8b5cf6'}};
  (data.signals || []).forEach(function(s) {{
    var c = colors[s.source] || '#64748b';
    var wPct = Math.round((s.weight || 0) * 100);
    var confPct = Math.round((s.confidence || 0) * 100);
    var priceCls = '';
    sigHtml += '<div class="src-signal">';
    sigHtml += '<div class="src-signal-header">';
    sigHtml += '<span class="src-signal-name" style="color:' + c + '">' + s.source + '</span>';
    sigHtml += '<span class="src-signal-price">$' + (s.price ? s.price.toFixed(0) : '-') + '</span>';
    sigHtml += '</div>';
    sigHtml += '<div class="src-signal-bar"><div class="src-signal-fill" style="width:' + wPct + '%;background:' + c + '"></div></div>';
    sigHtml += '<div class="src-signal-meta">Weight: ' + wPct + '% | Confidence: ' + confPct + '%</div>';
    if (s.reasoning) {{
      sigHtml += '<div class="src-signal-reasoning">' + s.reasoning + '</div>';
    }}
    sigHtml += '</div>';
  }});
  document.getElementById('src-signals').innerHTML = sigHtml || '<div style="color:#94a3b8">No signal data available</div>';

  /* Adjustments */
  var adj = data.adjustments || {{}};
  var adjHtml = '';
  ['events','season','demand','momentum'].forEach(function(k) {{
    var v = adj[k] || 0;
    var pct = (v * 100).toFixed(1);
    var cls = v > 0.001 ? 'pos' : (v < -0.001 ? 'neg' : '');
    adjHtml += '<div class="src-adj-item"><div class="src-adj-val ' + cls + '">' + (v >= 0 ? '+' : '') + pct + '%</div>';
    adjHtml += '<div class="src-adj-label">' + k + '</div></div>';
  }});
  document.getElementById('src-adjustments').innerHTML = adjHtml;

  /* Factors */
  var factors = data.factors || [];
  if (factors.length > 0) {{
    document.getElementById('src-factors').innerHTML = '<strong>Key factors:</strong> ' + factors.join(' &bull; ');
    document.getElementById('src-factors').style.display = '';
  }} else {{
    document.getElementById('src-factors').style.display = 'none';
  }}

  document.getElementById('src-overlay').classList.add('open');
}}

function closeSources() {{
  document.getElementById('src-overlay').classList.remove('open');
}}
document.getElementById('src-overlay').addEventListener('click', function(e) {{
  if (e.target === this) closeSources();
}});

/* ── Rules Panel Logic ──────────────────────────────────────── */
var _rulesState = {{
  detailId: null,
  hotel: '',
  category: '',
  board: '',
  price: 0,
  signal: '',
  scope: 'row',
  preset: null,
}};

function openRulesPanel(btn) {{
  _rulesState.detailId = btn.dataset.detailId;
  _rulesState.hotel = btn.dataset.hotel;
  _rulesState.category = btn.dataset.category;
  _rulesState.board = btn.dataset.board;
  _rulesState.price = parseFloat(btn.dataset.price) || 0;
  _rulesState.signal = btn.dataset.signal;
  _rulesState.scope = 'row';
  _rulesState.preset = null;

  // Fill context
  document.getElementById('rc-room').textContent = '#' + _rulesState.detailId + ' (' + _rulesState.category + ' / ' + _rulesState.board + ')';
  document.getElementById('rc-hotel').textContent = _rulesState.hotel;
  document.getElementById('rc-price').textContent = '$' + _rulesState.price.toFixed(2);
  var sigEl = document.getElementById('rc-signal');
  sigEl.textContent = _rulesState.signal;
  sigEl.style.color = _rulesState.signal === 'CALL' ? 'var(--call)' : (_rulesState.signal === 'PUT' ? 'var(--put)' : 'var(--neutral)');

  // Update hotel scope label
  document.getElementById('scope-hotel-label').textContent = _rulesState.hotel.substring(0, 20) || 'This Hotel';

  // Reset selections
  document.querySelectorAll('.scope-opt').forEach(function(el) {{ el.classList.remove('selected'); }});
  document.querySelector('.scope-opt[data-scope="row"]').classList.add('selected');
  document.querySelectorAll('.preset-card').forEach(function(el) {{ el.classList.remove('selected'); }});

  // Clear custom inputs
  document.getElementById('rule-ceiling').value = '';
  document.getElementById('rule-floor').value = '';
  document.getElementById('rule-markup').value = '';
  document.getElementById('rule-target').value = '';
  document.getElementById('rules-summary').style.display = 'none';

  document.getElementById('rules-overlay').classList.add('open');
}}

function closeRulesPanel() {{
  document.getElementById('rules-overlay').classList.remove('open');
}}

document.getElementById('rules-overlay').addEventListener('click', function(e) {{
  if (e.target === this) closeRulesPanel();
}});

function selectScope(el) {{
  document.querySelectorAll('.scope-opt').forEach(function(s) {{ s.classList.remove('selected'); }});
  el.classList.add('selected');
  _rulesState.scope = el.dataset.scope;
  updateRulesSummary();
}}

function selectPreset(el) {{
  var wasSelected = el.classList.contains('selected');
  document.querySelectorAll('.preset-card').forEach(function(c) {{ c.classList.remove('selected'); }});
  if (!wasSelected) {{
    el.classList.add('selected');
    _rulesState.preset = el.dataset.preset;
  }} else {{
    _rulesState.preset = null;
  }}
  updateRulesSummary();
}}

function updateRulesSummary() {{
  var parts = [];
  var scopeText = _rulesState.scope === 'row' ? 'Room #' + _rulesState.detailId :
                  _rulesState.scope === 'hotel' ? 'All rooms in ' + _rulesState.hotel :
                  'All hotels';

  if (_rulesState.preset) {{
    parts.push('Preset: <b>' + _rulesState.preset + '</b>');
  }}

  var ceiling = document.getElementById('rule-ceiling').value;
  var floor = document.getElementById('rule-floor').value;
  var markup = document.getElementById('rule-markup').value;
  var target = document.getElementById('rule-target').value;

  if (ceiling) parts.push('Ceiling: $' + ceiling);
  if (floor) parts.push('Floor: $' + floor);
  if (markup) parts.push('Markup: ' + markup + '%');
  if (target) parts.push('Target: $' + target);

  var summaryEl = document.getElementById('rules-summary');
  if (parts.length > 0) {{
    document.getElementById('rules-summary-text').innerHTML =
      '<b>Scope:</b> ' + scopeText + ' &nbsp;|&nbsp; ' + parts.join(' &nbsp;|&nbsp; ');
    summaryEl.style.display = 'block';
  }} else {{
    summaryEl.style.display = 'none';
  }}
}}

// Update summary when custom inputs change
['rule-ceiling', 'rule-floor', 'rule-markup', 'rule-target'].forEach(function(id) {{
  document.getElementById(id).addEventListener('input', updateRulesSummary);
}});

function applyRules() {{
  var scopeText = _rulesState.scope === 'row' ? 'Room #' + _rulesState.detailId :
                  _rulesState.scope === 'hotel' ? _rulesState.hotel :
                  'All Hotels';

  var rulesCount = 0;
  var rulesList = [];

  if (_rulesState.preset) {{
    rulesCount++;
    rulesList.push(_rulesState.preset);
  }}
  if (document.getElementById('rule-ceiling').value) {{
    rulesCount++;
    rulesList.push('ceiling=$' + document.getElementById('rule-ceiling').value);
  }}
  if (document.getElementById('rule-floor').value) {{
    rulesCount++;
    rulesList.push('floor=$' + document.getElementById('rule-floor').value);
  }}
  if (document.getElementById('rule-markup').value) {{
    rulesCount++;
    rulesList.push('markup=' + document.getElementById('rule-markup').value + '%');
  }}
  if (document.getElementById('rule-target').value) {{
    rulesCount++;
    rulesList.push('target=$' + document.getElementById('rule-target').value);
  }}

  if (rulesCount === 0) {{
    showToast('&#9888; Please select a preset or set custom rules', '#f59e0b');
    return;
  }}

  // Update button(s) in the table to show rules are set
  var targetBtns = [];
  if (_rulesState.scope === 'row') {{
    var btn = document.querySelector('.rules-btn[data-detail-id="' + _rulesState.detailId + '"]');
    if (btn) targetBtns.push(btn);
  }} else if (_rulesState.scope === 'hotel') {{
    document.querySelectorAll('.rules-btn[data-hotel="' + _rulesState.hotel.replace(/"/g, '\\\\"') + '"]').forEach(function(b) {{ targetBtns.push(b); }});
  }} else {{
    document.querySelectorAll('.rules-btn').forEach(function(b) {{ targetBtns.push(b); }});
  }}

  targetBtns.forEach(function(b) {{
    b.innerHTML = '&#9881; ' + rulesCount + ' rule' + (rulesCount > 1 ? 's' : '');
    b.style.background = 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)';
    b.title = 'Active rules: ' + rulesList.join(', ') + ' | Scope: ' + scopeText;
  }});

  closeRulesPanel();
  showToast('&#9989; ' + rulesCount + ' rule' + (rulesCount > 1 ? 's' : '') + ' set for ' + scopeText, '#16a34a');

  // TODO: Wire to API  POST /api/v1/salesoffice/rules/
  // The backend connection will be wired in the next step
  console.log('Rules applied:', {{
    scope: _rulesState.scope,
    detailId: _rulesState.detailId,
    hotel: _rulesState.hotel,
    preset: _rulesState.preset,
    ceiling: document.getElementById('rule-ceiling').value,
    floor: document.getElementById('rule-floor').value,
    markup: document.getElementById('rule-markup').value,
    target: document.getElementById('rule-target').value,
  }});
}}

function showToast(msg, bgColor) {{
  var toast = document.getElementById('rules-toast');
  document.getElementById('toast-msg').innerHTML = msg;
  if (bgColor) toast.style.background = bgColor;
  toast.classList.add('show');
  setTimeout(function() {{ toast.classList.remove('show'); }}, 3000);
}}
</script>
</body>
</html>"""

