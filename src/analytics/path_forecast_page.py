"""Path Forecast dashboard — full price lifecycle visualization."""
from __future__ import annotations


def generate_path_forecast_html() -> str:
    """Return async HTML shell for the path forecast dashboard.

    Loads data from /api/v1/salesoffice/path-forecast via fetch(),
    renders interactive price path charts and segment tables client-side.
    """
    return _PATH_FORECAST_HTML


_PATH_FORECAST_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Path Forecast — Medici Price Prediction</title>
<style>
:root {
  --bg: #f8fafc; --surface: #ffffff; --border: #e2e8f0;
  --text: #0f172a; --muted: #64748b;
  --call: #16a34a; --put: #dc2626; --neutral: #64748b;
  --up: #16a34a; --down: #dc2626; --accent: #2563eb;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: var(--bg); color: var(--text); font-size: 14px; }
.page { max-width: 1400px; margin: 0 auto; padding: 16px; }
h1 { font-size: 20px; margin-bottom: 4px; }
.subtitle { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Status bar */
.status-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.chip { background: var(--surface); border: 1px solid var(--border);
        border-radius: 6px; padding: 4px 10px; font-size: 12px; }

/* Cards */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
         gap: 10px; margin-bottom: 16px; }
.card { background: var(--surface); border: 1px solid var(--border);
        border-radius: 8px; padding: 12px; text-align: center; }
.card .label { font-size: 11px; color: var(--muted); text-transform: uppercase;
               letter-spacing: 0.5px; margin-bottom: 4px; }
.card .value { font-size: 22px; font-weight: 700; }
.card .value.up { color: var(--up); }
.card .value.down { color: var(--down); }

/* Controls */
.controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
            margin-bottom: 16px; }
.controls select, .controls input { padding: 6px 10px; border: 1px solid var(--border);
  border-radius: 6px; font-size: 13px; background: var(--surface); }

/* Path items */
.path-list { display: flex; flex-direction: column; gap: 16px; }
.path-item { background: var(--surface); border: 1px solid var(--border);
             border-radius: 10px; overflow: hidden; }
.path-header { display: flex; justify-content: space-between; align-items: center;
               padding: 12px 16px; border-bottom: 1px solid var(--border);
               cursor: pointer; }
.path-header:hover { background: #f1f5f9; }
.path-hotel { font-weight: 600; font-size: 15px; }
.path-meta { display: flex; gap: 16px; font-size: 12px; color: var(--muted); }
.path-body { display: none; padding: 16px; }
.path-item.open .path-body { display: block; }

/* Chart container */
.chart-wrap { position: relative; width: 100%; height: 280px; margin-bottom: 16px; }
.chart-wrap canvas { width: 100% !important; height: 100% !important; }

/* Segments table */
.seg-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 12px; }
.seg-table th { background: #f1f5f9; padding: 6px 10px; text-align: left;
                font-weight: 600; font-size: 11px; text-transform: uppercase;
                letter-spacing: 0.5px; border-bottom: 2px solid var(--border); }
.seg-table td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
.seg-table tr:hover { background: #f8fafc; }

/* Trade box */
.trade-box { background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
             border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px;
             display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }
.trade-box.no-trade { background: #f8fafc; border-color: var(--border); }
.trade-label { font-size: 11px; color: var(--muted); text-transform: uppercase; }
.trade-value { font-size: 18px; font-weight: 700; }
.trade-arrow { font-size: 20px; color: var(--up); }

/* Pills */
.pill { display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 11px; font-weight: 600; }
.pill.up { background: #dcfce7; color: var(--up); }
.pill.down { background: #fee2e2; color: var(--down); }

/* Turning point markers */
.tp-list { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.tp-tag { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.tp-tag.min { background: #dbeafe; color: #1d4ed8; }
.tp-tag.max { background: #fef3c7; color: #92400e; }

/* Pagination */
.pager { display: flex; justify-content: space-between; align-items: center;
         padding: 12px 0; }
.pager button { padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px;
                background: var(--surface); cursor: pointer; font-size: 13px; }
.pager button:disabled { opacity: 0.4; cursor: default; }

/* Loading */
.loading-box { text-align: center; padding: 60px 20px; color: var(--muted); }
.spinner { display: inline-block; width: 32px; height: 32px;
           border: 3px solid var(--border); border-top-color: var(--accent);
           border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .path-meta { flex-direction: column; gap: 4px; }
  .trade-box { flex-direction: column; gap: 8px; }
}
</style>
</head>
<body>
<div class="page">
  <h1>Path Forecast</h1>
  <p class="subtitle">Full price lifecycle analysis &mdash; turning points, segments, optimal trades.
     <a href="/api/v1/salesoffice/home">&larr; Home</a></p>

  <div class="status-bar">
    <div class="chip" id="chip-status">Loading...</div>
    <div class="chip" id="chip-count">Paths: --</div>
    <div class="chip" id="chip-time">--</div>
  </div>

  <div class="cards">
    <div class="card"><div class="label">Total Paths</div><div class="value" id="stat-total">--</div></div>
    <div class="card"><div class="label">Avg Trade Profit</div><div class="value" id="stat-avg-profit">--</div></div>
    <div class="card"><div class="label">Best Opportunity</div><div class="value up" id="stat-best">--</div></div>
    <div class="card"><div class="label">Avg Segments</div><div class="value" id="stat-avg-seg">--</div></div>
  </div>

  <div class="controls">
    <label>Hotel: <select id="filter-hotel"><option value="">All Hotels</option></select></label>
    <label>Min Profit %: <input type="number" id="filter-profit" value="0" min="0" step="1" style="width:80px"></label>
    <button id="btn-apply" style="padding:6px 14px;border:1px solid var(--border);border-radius:6px;background:var(--accent);color:#fff;cursor:pointer;">Apply</button>
  </div>

  <div id="content">
    <div class="loading-box"><div class="spinner"></div><p style="margin-top:12px">Loading path forecasts...</p></div>
  </div>

  <div class="pager">
    <div id="pager-info">--</div>
    <div>
      <button id="btn-prev" disabled>&larr; Previous</button>
      <button id="btn-next" disabled>Next &rarr;</button>
    </div>
  </div>
</div>

<script>
const S = { offset: 0, limit: 20, paths: [], total: 0 };

function esc(v) { const d = document.createElement('div'); d.textContent = v; return d.innerHTML; }
function fmt$(v) { return '$' + Number(v).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}); }
function fmtPct(v) { return (v >= 0 ? '+' : '') + Number(v).toFixed(1) + '%'; }

async function fetchPaths() {
  const hotel = document.getElementById('filter-hotel').value;
  const minProfit = document.getElementById('filter-profit').value || '0';
  const params = new URLSearchParams({
    limit: String(S.limit), offset: String(S.offset), min_profit: minProfit
  });
  if (hotel) params.set('hotel_id', hotel);

  document.getElementById('chip-status').textContent = 'Fetching...';
  try {
    const r = await fetch('/api/v1/salesoffice/path-forecast?' + params.toString());
    if (r.status === 503) {
      document.getElementById('chip-status').textContent = 'Cache warming...';
      setTimeout(fetchPaths, 15000);
      return;
    }
    const data = await r.json();
    S.paths = data.paths || [];
    S.total = data.total || 0;
    renderAll();
    document.getElementById('chip-status').textContent = 'Ready';
    document.getElementById('chip-count').textContent = 'Paths: ' + S.total;
    document.getElementById('chip-time').textContent = new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById('chip-status').textContent = 'Error: ' + e.message;
  }
}

function renderAll() {
  // Stats
  if (S.paths.length > 0) {
    document.getElementById('stat-total').textContent = S.total;
    const avgProfit = S.paths.reduce((s, p) => s + (p.max_trade_profit_pct || 0), 0) / S.paths.length;
    document.getElementById('stat-avg-profit').textContent = fmtPct(avgProfit);
    const best = S.paths[0];
    document.getElementById('stat-best').textContent = fmtPct(best.max_trade_profit_pct || 0);
    const avgSeg = S.paths.reduce((s, p) => s + (p.num_up_segments || 0) + (p.num_down_segments || 0), 0) / S.paths.length;
    document.getElementById('stat-avg-seg').textContent = avgSeg.toFixed(1);
  }

  // Populate hotel filter (first load only)
  const hotelSelect = document.getElementById('filter-hotel');
  if (hotelSelect.options.length <= 1 && S.paths.length > 0) {
    const hotels = new Map();
    S.paths.forEach(p => hotels.set(p.hotel_id, p.hotel_name));
    [...hotels.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([id, name]) => {
      const opt = document.createElement('option');
      opt.value = id; opt.textContent = name;
      hotelSelect.appendChild(opt);
    });
  }

  // Render path items
  const container = document.getElementById('content');
  if (S.paths.length === 0) {
    container.innerHTML = '<div class="loading-box"><p>No path forecasts found.</p></div>';
    return;
  }

  container.innerHTML = S.paths.map((p, idx) => {
    const netClass = p.net_change_pct >= 0 ? 'up' : 'down';
    const segments = p.segments || [];
    const tps = p.turning_points || [];
    const hasTrade = p.max_trade_profit_pct > 0;
    const canvasId = 'chart-' + idx;

    return '<div class="path-item" data-idx="' + idx + '">' +
      '<div class="path-header" onclick="togglePath(' + idx + ')">' +
        '<div>' +
          '<span class="path-hotel">' + esc(p.hotel_name) + '</span>' +
          ' <span style="color:var(--muted);font-size:12px">' + esc(p.category) + ' / ' + esc(p.board) + '</span>' +
        '</div>' +
        '<div class="path-meta">' +
          '<span>Now: ' + fmt$(p.current_price) + '</span>' +
          '<span>Final: ' + fmt$(p.predicted_final_price) + '</span>' +
          '<span class="pill ' + netClass + '">' + fmtPct(p.net_change_pct) + '</span>' +
          '<span>T=' + p.current_t + 'd</span>' +
          (hasTrade ? '<span style="color:var(--up);font-weight:600">Trade: ' + fmtPct(p.max_trade_profit_pct) + '</span>' : '') +
        '</div>' +
      '</div>' +
      '<div class="path-body">' +
        '<div class="chart-wrap"><canvas id="' + canvasId + '"></canvas></div>' +
        (tps.length > 0 ? '<div class="tp-list">' +
          tps.map(tp => '<span class="tp-tag ' + (tp.type === 'MIN' ? 'min' : 'max') + '">' +
            tp.type + ' T=' + tp.t + ' ' + fmt$(tp.price) + '</span>').join('') +
        '</div>' : '') +
        (hasTrade ? '<div class="trade-box">' +
          '<div><div class="trade-label">Buy</div><div class="trade-value" style="color:var(--up)">' +
            fmt$(p.best_buy_price) + '</div><div style="font-size:11px;color:var(--muted)">T=' + p.best_buy_t + ' (' + esc(p.best_buy_date) + ')</div></div>' +
          '<div class="trade-arrow">&rarr;</div>' +
          '<div><div class="trade-label">Sell</div><div class="trade-value" style="color:var(--put)">' +
            fmt$(p.best_sell_price) + '</div><div style="font-size:11px;color:var(--muted)">T=' + p.best_sell_t + ' (' + esc(p.best_sell_date) + ')</div></div>' +
          '<div><div class="trade-label">Profit</div><div class="trade-value" style="color:var(--up)">' +
            fmtPct(p.max_trade_profit_pct) + '</div></div>' +
        '</div>' : '<div class="trade-box no-trade"><span style="color:var(--muted)">No significant trade opportunity</span></div>') +
        (segments.length > 0 ? '<table class="seg-table"><thead><tr>' +
          '<th>Direction</th><th>From</th><th>To</th><th>Days</th>' +
          '<th>Start Price</th><th>End Price</th><th>Change</th><th>Confidence</th></tr></thead><tbody>' +
          segments.map(s => '<tr>' +
            '<td><span class="pill ' + (s.direction === 'UP' ? 'up' : 'down') + '">' + s.direction + '</span></td>' +
            '<td>T=' + s.t_start + '</td><td>T=' + s.t_end + '</td>' +
            '<td>' + s.duration_days + '</td>' +
            '<td>' + fmt$(s.price_start) + '</td><td>' + fmt$(s.price_end) + '</td>' +
            '<td style="color:' + (s.change_pct >= 0 ? 'var(--up)' : 'var(--down)') + ';font-weight:600">' + fmtPct(s.change_pct) + '</td>' +
            '<td>' + (s.confidence * 100).toFixed(0) + '%</td>' +
          '</tr>').join('') +
        '</tbody></table>' : '') +
      '</div>' +
    '</div>';
  }).join('');

  // Pagination
  document.getElementById('pager-info').textContent =
    'Showing ' + (S.offset + 1) + '-' + Math.min(S.offset + S.limit, S.total) + ' of ' + S.total;
  document.getElementById('btn-prev').disabled = S.offset === 0;
  document.getElementById('btn-next').disabled = S.offset + S.limit >= S.total;
}

function togglePath(idx) {
  const items = document.querySelectorAll('.path-item');
  const item = items[idx];
  if (!item) return;
  const wasOpen = item.classList.contains('open');
  item.classList.toggle('open');
  if (!wasOpen) {
    const canvasId = 'chart-' + idx;
    const canvas = document.getElementById(canvasId);
    if (canvas && !canvas.dataset.drawn) {
      drawPathChart(canvas, S.paths[idx]);
      canvas.dataset.drawn = '1';
    }
  }
}

function drawPathChart(canvas, path) {
  const dp = path.daily_prices || [];
  if (dp.length < 2) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = rect.width, H = rect.height;

  const prices = dp.map(d => d.predicted_price);
  const lowers = dp.map(d => d.lower_bound || d.predicted_price);
  const uppers = dp.map(d => d.upper_bound || d.predicted_price);
  const allVals = [...prices, ...lowers, ...uppers];
  const minP = Math.min(...allVals) * 0.98;
  const maxP = Math.max(...allVals) * 1.02;
  const pad = { top: 20, right: 60, bottom: 30, left: 60 };

  function x(i) { return pad.left + (i / (dp.length - 1)) * (W - pad.left - pad.right); }
  function y(v) { return pad.top + (1 - (v - minP) / (maxP - minP)) * (H - pad.top - pad.bottom); }

  // Grid
  ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const val = minP + (maxP - minP) * i / 4;
    const yy = y(val);
    ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(W - pad.right, yy); ctx.stroke();
    ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + Math.round(val), pad.left - 6, yy + 3);
  }

  // Confidence band
  ctx.fillStyle = 'rgba(37, 99, 235, 0.08)';
  ctx.beginPath();
  dp.forEach((d, i) => { i === 0 ? ctx.moveTo(x(i), y(uppers[i])) : ctx.lineTo(x(i), y(uppers[i])); });
  for (let i = dp.length - 1; i >= 0; i--) ctx.lineTo(x(i), y(lowers[i]));
  ctx.closePath(); ctx.fill();

  // Price line
  ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2;
  ctx.beginPath();
  prices.forEach((p, i) => { i === 0 ? ctx.moveTo(x(i), y(p)) : ctx.lineTo(x(i), y(p)); });
  ctx.stroke();

  // Current price reference line
  ctx.strokeStyle = '#94a3b8'; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(pad.left, y(path.current_price)); ctx.lineTo(W - pad.right, y(path.current_price)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('Current ' + fmt$(path.current_price), W - pad.right + 4, y(path.current_price) + 3);

  // Turning points
  const tps = path.turning_points || [];
  tps.forEach(tp => {
    const tpIdx = dp.findIndex(d => d.t === tp.t);
    if (tpIdx < 0) return;
    const cx = x(tpIdx), cy = y(tp.price);
    ctx.fillStyle = tp.type === 'MIN' ? '#2563eb' : '#f59e0b';
    ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#0f172a'; ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(tp.type + ' ' + fmt$(tp.price), cx, cy - 10);
  });

  // Buy/sell markers
  if (path.max_trade_profit_pct > 0) {
    const buyIdx = dp.findIndex(d => d.t === path.best_buy_t);
    const sellIdx = dp.findIndex(d => d.t === path.best_sell_t);
    if (buyIdx >= 0) {
      ctx.fillStyle = '#16a34a';
      ctx.beginPath(); ctx.moveTo(x(buyIdx), y(prices[buyIdx]) + 8);
      ctx.lineTo(x(buyIdx) - 5, y(prices[buyIdx]) + 16);
      ctx.lineTo(x(buyIdx) + 5, y(prices[buyIdx]) + 16); ctx.fill();
      ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('BUY', x(buyIdx), y(prices[buyIdx]) + 26);
    }
    if (sellIdx >= 0) {
      ctx.fillStyle = '#dc2626';
      ctx.beginPath(); ctx.moveTo(x(sellIdx), y(prices[sellIdx]) - 8);
      ctx.lineTo(x(sellIdx) - 5, y(prices[sellIdx]) - 16);
      ctx.lineTo(x(sellIdx) + 5, y(prices[sellIdx]) - 16); ctx.fill();
      ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('SELL', x(sellIdx), y(prices[sellIdx]) - 22);
    }
  }

  // X-axis labels (T values)
  ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(dp.length / 6));
  for (let i = 0; i < dp.length; i += step) {
    ctx.fillText('T=' + dp[i].t, x(i), H - 6);
  }
}

// Events
document.getElementById('btn-apply').addEventListener('click', () => { S.offset = 0; fetchPaths(); });
document.getElementById('btn-prev').addEventListener('click', () => { S.offset = Math.max(0, S.offset - S.limit); fetchPaths(); });
document.getElementById('btn-next').addEventListener('click', () => { S.offset += S.limit; fetchPaths(); });
document.getElementById('filter-profit').addEventListener('keydown', e => { if (e.key === 'Enter') { S.offset = 0; fetchPaths(); } });

// Init
fetchPaths();
</script>
</body>
</html>"""
