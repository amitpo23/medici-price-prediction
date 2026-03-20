"""Source Comparison dashboard — per-source analysis without ensemble blending."""
from __future__ import annotations


def generate_sources_html() -> str:
    """Return async HTML shell for the source comparison dashboard.

    Loads data from /api/v1/salesoffice/sources/compare via fetch(),
    renders source-by-source comparison tables client-side.
    """
    return _SOURCES_HTML


_SOURCES_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Source Comparison — Medici Price Prediction</title>
<style>
:root {
  --bg: #f8fafc; --surface: #ffffff; --border: #e2e8f0;
  --text: #0f172a; --muted: #64748b;
  --call: #16a34a; --put: #dc2626; --neutral: #64748b;
  --accent: #2563eb; --warn: #f59e0b; --danger-bg: #fef2f2;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: var(--bg); color: var(--text); font-size: 14px; }
.page { max-width: 1400px; margin: 0 auto; padding: 16px; }
h1 { font-size: 20px; margin-bottom: 4px; }
.subtitle { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.status-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.chip { background: var(--surface); border: 1px solid var(--border);
        border-radius: 6px; padding: 4px 10px; font-size: 12px; }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
         gap: 10px; margin-bottom: 16px; }
.card { background: var(--surface); border: 1px solid var(--border);
        border-radius: 8px; padding: 12px; text-align: center; }
.card .label { font-size: 11px; color: var(--muted); text-transform: uppercase;
               letter-spacing: 0.5px; margin-bottom: 4px; }
.card .value { font-size: 22px; font-weight: 700; }
.card .value.warn { color: var(--warn); }
.card .value.danger { color: var(--put); }

.controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
            margin-bottom: 16px; }
.controls select, .controls input { padding: 6px 10px; border: 1px solid var(--border);
  border-radius: 6px; font-size: 13px; background: var(--surface); }
.controls label { display: flex; align-items: center; gap: 4px; font-size: 13px; }

/* Comparison items */
.comp-list { display: flex; flex-direction: column; gap: 12px; }
.comp-item { background: var(--surface); border: 1px solid var(--border);
             border-radius: 10px; overflow: hidden; }
.comp-item.disagreement { border-color: #fca5a5; background: var(--danger-bg); }
.comp-header { display: flex; justify-content: space-between; align-items: center;
               padding: 10px 16px; cursor: pointer; }
.comp-header:hover { background: #f1f5f9; }
.comp-item.disagreement .comp-header:hover { background: #fef2f2; }
.comp-hotel { font-weight: 600; font-size: 14px; }
.comp-badges { display: flex; gap: 6px; align-items: center; }
.comp-body { display: none; padding: 16px; }
.comp-item.open .comp-body { display: block; }

/* Signal pills */
.pill { display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 11px; font-weight: 600; letter-spacing: 0.3px; }
.pill.call { background: #dcfce7; color: var(--call); }
.pill.put { background: #fee2e2; color: var(--put); }
.pill.neutral { background: #f1f5f9; color: var(--neutral); }
.pill.disagree { background: #fef3c7; color: #92400e; }
.pill.agrees { background: #dcfce7; color: var(--call); }
.pill.disagrees { background: #fee2e2; color: var(--put); }

/* Source table */
.src-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 12px; }
.src-table th { background: #f1f5f9; padding: 6px 10px; text-align: left;
                font-weight: 600; font-size: 11px; text-transform: uppercase;
                letter-spacing: 0.5px; border-bottom: 2px solid var(--border); }
.src-table td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
.src-table tr:hover { background: #f8fafc; }
.src-table tr.conflict td { background: #fef2f2; }

/* Consensus summary */
.consensus { display: flex; gap: 16px; align-items: center; flex-wrap: wrap;
             padding: 10px 14px; background: #f8fafc; border-radius: 8px;
             margin-bottom: 12px; font-size: 13px; }
.consensus-label { font-size: 11px; color: var(--muted); text-transform: uppercase; }

/* Vote bar */
.vote-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden;
            width: 160px; background: #e2e8f0; }
.vote-call { background: var(--call); }
.vote-put { background: var(--put); }
.vote-neutral { background: #94a3b8; }

/* Pagination */
.pager { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; }
.pager button { padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px;
                background: var(--surface); cursor: pointer; font-size: 13px; }
.pager button:disabled { opacity: 0.4; cursor: default; }

.loading-box { text-align: center; padding: 60px 20px; color: var(--muted); }
.spinner { display: inline-block; width: 32px; height: 32px;
           border: 3px solid var(--border); border-top-color: var(--accent);
           border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .comp-badges { flex-wrap: wrap; }
  .consensus { flex-direction: column; gap: 8px; }
}
</style>
</head>
<body>
<div class="page">
  <h1>Source Comparison</h1>
  <p class="subtitle">What each data source says independently &mdash; no ensemble, no enrichments.
     <a href="/api/v1/salesoffice/home">&larr; Home</a></p>

  <div class="status-bar">
    <div class="chip" id="chip-status">Loading...</div>
    <div class="chip" id="chip-count">Options: --</div>
    <div class="chip" id="chip-disagree">Disagreements: --</div>
  </div>

  <div class="cards">
    <div class="card"><div class="label">Total Options</div><div class="value" id="stat-total">--</div></div>
    <div class="card"><div class="label">Disagreements</div><div class="value danger" id="stat-disagree">--</div></div>
    <div class="card"><div class="label">Avg Consensus</div><div class="value" id="stat-consensus">--</div></div>
    <div class="card"><div class="label">Ensemble Agrees</div><div class="value" id="stat-agrees">--</div></div>
  </div>

  <div class="controls">
    <label>Hotel: <select id="filter-hotel"><option value="">All Hotels</option></select></label>
    <label><input type="checkbox" id="filter-disagree"> Disagreements only</label>
    <button id="btn-apply" style="padding:6px 14px;border:1px solid var(--border);border-radius:6px;background:var(--accent);color:#fff;cursor:pointer;">Apply</button>
  </div>

  <div id="content">
    <div class="loading-box"><div class="spinner"></div><p style="margin-top:12px">Loading source comparisons...</p></div>
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
const S = { offset: 0, limit: 30, comps: [], total: 0, disagreeTotal: 0 };

function esc(v) { const d = document.createElement('div'); d.textContent = v; return d.innerHTML; }
function fmt$(v) { return '$' + Number(v).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}); }
function fmtPct(v) { return (v >= 0 ? '+' : '') + Number(v).toFixed(1) + '%'; }
function pillClass(dir) { return dir === 'CALL' ? 'call' : dir === 'PUT' ? 'put' : 'neutral'; }

async function fetchComps() {
  const hotel = document.getElementById('filter-hotel').value;
  const disagreeOnly = document.getElementById('filter-disagree').checked;
  const params = new URLSearchParams({
    limit: String(S.limit), offset: String(S.offset)
  });
  if (hotel) params.set('hotel_id', hotel);
  if (disagreeOnly) params.set('disagreements_only', 'true');

  document.getElementById('chip-status').textContent = 'Fetching...';
  try {
    const r = await fetch('/api/v1/salesoffice/sources/compare?' + params.toString());
    if (r.status === 503) {
      document.getElementById('chip-status').textContent = 'Cache warming...';
      setTimeout(fetchComps, 15000);
      return;
    }
    const data = await r.json();
    S.comps = data.comparisons || [];
    S.total = data.total || 0;
    S.disagreeTotal = data.disagreements_in_total || 0;
    renderAll();
    document.getElementById('chip-status').textContent = 'Ready';
    document.getElementById('chip-count').textContent = 'Options: ' + S.total;
    document.getElementById('chip-disagree').textContent = 'Disagreements: ' + S.disagreeTotal;
  } catch (e) {
    document.getElementById('chip-status').textContent = 'Error: ' + e.message;
  }
}

function renderAll() {
  // Stats
  document.getElementById('stat-total').textContent = S.total;
  document.getElementById('stat-disagree').textContent = S.disagreeTotal;
  if (S.comps.length > 0) {
    const avgCons = S.comps.reduce((s, c) => s + (c.consensus_strength || 0), 0) / S.comps.length;
    document.getElementById('stat-consensus').textContent = (avgCons * 100).toFixed(0) + '%';
    const agrees = S.comps.filter(c => c.ensemble_vs_consensus === 'AGREES').length;
    document.getElementById('stat-agrees').textContent =
      ((agrees / S.comps.length) * 100).toFixed(0) + '%';
  }

  // Hotel filter
  const hotelSelect = document.getElementById('filter-hotel');
  if (hotelSelect.options.length <= 1 && S.comps.length > 0) {
    const hotels = new Map();
    S.comps.forEach(c => hotels.set(c.hotel_id, c.hotel_name));
    [...hotels.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([id, name]) => {
      const opt = document.createElement('option');
      opt.value = id; opt.textContent = name;
      hotelSelect.appendChild(opt);
    });
  }

  // Render items
  const container = document.getElementById('content');
  if (S.comps.length === 0) {
    container.innerHTML = '<div class="loading-box"><p>No comparisons found.</p></div>';
    return;
  }

  container.innerHTML = S.comps.map((c, idx) => {
    const isDisagree = c.disagreement_flag;
    const preds = c.source_predictions || [];
    const stats = c.source_stats || [];
    const nCall = c.n_sources_call || 0;
    const nPut = c.n_sources_put || 0;
    const nNeutral = c.n_sources_neutral || 0;
    const total = nCall + nPut + nNeutral || 1;

    return '<div class="comp-item ' + (isDisagree ? 'disagreement' : '') + '">' +
      '<div class="comp-header" onclick="toggleComp(' + idx + ')">' +
        '<div>' +
          '<span class="comp-hotel">' + esc(c.hotel_name) + '</span>' +
          ' <span style="color:var(--muted);font-size:12px">' + esc(c.category) + ' / ' + esc(c.board) +
          ' &middot; T=' + c.current_t + 'd &middot; ' + fmt$(c.current_price) + '</span>' +
        '</div>' +
        '<div class="comp-badges">' +
          '<span class="pill ' + pillClass(c.consensus_direction) + '">Consensus: ' + c.consensus_direction + '</span>' +
          (isDisagree ? '<span class="pill disagree">CONFLICT</span>' : '') +
          '<span class="pill ' + (c.ensemble_vs_consensus === 'AGREES' ? 'agrees' : c.ensemble_vs_consensus === 'DISAGREES' ? 'disagrees' : 'neutral') + '">' +
            'Ensemble ' + c.ensemble_vs_consensus + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="comp-body">' +
        '<div class="consensus">' +
          '<div><div class="consensus-label">Consensus</div>' +
            '<span class="pill ' + pillClass(c.consensus_direction) + '" style="font-size:13px">' +
            c.consensus_direction + ' (' + (c.consensus_strength * 100).toFixed(0) + '%)</span></div>' +
          '<div><div class="consensus-label">Vote</div>' +
            '<div style="display:flex;gap:8px;align-items:center">' +
              '<div class="vote-bar">' +
                '<div class="vote-call" style="width:' + (nCall / total * 100) + '%"></div>' +
                '<div class="vote-neutral" style="width:' + (nNeutral / total * 100) + '%"></div>' +
                '<div class="vote-put" style="width:' + (nPut / total * 100) + '%"></div>' +
              '</div>' +
              '<span style="font-size:11px;color:var(--muted)">' + nCall + 'C / ' + nNeutral + 'N / ' + nPut + 'P</span>' +
            '</div></div>' +
          '<div><div class="consensus-label">Ensemble</div>' +
            '<span class="pill ' + pillClass(c.ensemble_direction) + '">' + c.ensemble_direction + '</span>' +
            ' ' + fmt$(c.ensemble_price) + '</div>' +
        '</div>' +
        (preds.length > 0 ? '<table class="src-table"><thead><tr>' +
          '<th>Source</th><th>Direction</th><th>Predicted Price</th><th>Change</th>' +
          '<th>Confidence</th><th>Basis</th><th>Observations</th></tr></thead><tbody>' +
          preds.map((p, pi) => {
            const conflict = (p.direction === 'CALL' && nPut > 0) || (p.direction === 'PUT' && nCall > 0);
            return '<tr class="' + (conflict ? 'conflict' : '') + '">' +
              '<td style="font-weight:500">' + esc(p.source_label) + '</td>' +
              '<td><span class="pill ' + pillClass(p.direction) + '">' + p.direction + '</span></td>' +
              '<td>' + fmt$(p.predicted_price) + '</td>' +
              '<td style="color:' + (p.predicted_change_pct >= 0 ? 'var(--call)' : 'var(--put)') + ';font-weight:600">' +
                fmtPct(p.predicted_change_pct) + '</td>' +
              '<td>' + (p.confidence > 0 ? (p.confidence * 100).toFixed(0) + '%' : '--') + '</td>' +
              '<td style="color:var(--muted);font-size:11px">' + esc(p.basis) + '</td>' +
              '<td>' + (stats[pi] ? (stats[pi].n_observations || '--') : '--') + '</td>' +
            '</tr>';
          }).join('') +
        '</tbody></table>' : '<p style="color:var(--muted)">No source predictions available</p>') +
      '</div>' +
    '</div>';
  }).join('');

  // Pagination
  document.getElementById('pager-info').textContent =
    'Showing ' + (S.offset + 1) + '-' + Math.min(S.offset + S.limit, S.total) + ' of ' + S.total;
  document.getElementById('btn-prev').disabled = S.offset === 0;
  document.getElementById('btn-next').disabled = S.offset + S.limit >= S.total;
}

function toggleComp(idx) {
  document.querySelectorAll('.comp-item')[idx]?.classList.toggle('open');
}

// Events
document.getElementById('btn-apply').addEventListener('click', () => { S.offset = 0; fetchComps(); });
document.getElementById('btn-prev').addEventListener('click', () => { S.offset = Math.max(0, S.offset - S.limit); fetchComps(); });
document.getElementById('btn-next').addEventListener('click', () => { S.offset += S.limit; fetchComps(); });

// Init
fetchComps();
</script>
</body>
</html>"""
