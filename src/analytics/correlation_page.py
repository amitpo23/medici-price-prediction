"""Correlation Heat Map — visualize inter-hotel price correlation matrix."""
from __future__ import annotations


def generate_correlation_html() -> str:
    """Return self-contained HTML for the Correlation Heat Map dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Correlation Heat Map — Medici</title>
<style>
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --panel: #0f3460;
  --border: #1f4068;
  --text: #eee;
  --muted: #8899aa;
  --call: #00c853;
  --put: #ff1744;
  --accent: #42a5f5;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px;
}

.page {
  max-width: 1600px;
  margin: 0 auto;
  padding: 12px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--panel);
  border-bottom: 2px solid var(--border);
  padding: 16px;
  border-radius: 0 0 8px 8px;
  margin-bottom: 16px;
}

.header h1 {
  font-size: 24px;
  font-weight: 700;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.status-badge {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: 4px;
  color: var(--muted);
}

a {
  color: var(--accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* ── Summary Cards ── */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}

.card-title {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.card-value {
  font-size: 24px;
  font-weight: 700;
  font-family: monospace;
  color: var(--text);
}

.card-value.positive {
  color: var(--call);
}

.card-value.negative {
  color: var(--put);
}

.card-subtitle {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
}

/* ── Heat Map Container ── */
.heatmap-container {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
  overflow-x: auto;
}

.heatmap-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.heatmap-grid {
  display: grid;
  gap: 1px;
  background: var(--bg);
  padding: 8px;
  border-radius: 4px;
  min-width: 500px;
}

.hm-header-row {
  display: grid;
  gap: 1px;
  grid-template-columns: 120px repeat(auto-fit, minmax(60px, 1fr));
  margin-bottom: 8px;
}

.hm-header-cell {
  background: var(--panel);
  padding: 8px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  border-radius: 3px;
}

.hm-row {
  display: grid;
  gap: 1px;
  grid-template-columns: 120px repeat(auto-fit, minmax(60px, 1fr));
  align-items: center;
  margin-bottom: 1px;
}

.hm-label {
  background: var(--panel);
  padding: 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 3px;
  word-break: break-word;
}

.hm-cell {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  font-family: monospace;
  border-radius: 3px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hm-cell:hover {
  transform: scale(1.05);
  box-shadow: 0 0 8px rgba(66, 165, 245, 0.5);
}

.hm-cell.corr-pos-strong {
  background: rgba(0, 200, 83, 0.6);
  color: #fff;
}

.hm-cell.corr-pos-med {
  background: rgba(0, 200, 83, 0.35);
  color: #ccc;
}

.hm-cell.corr-pos-weak {
  background: rgba(0, 200, 83, 0.15);
  color: #999;
}

.hm-cell.corr-neg-strong {
  background: rgba(255, 23, 68, 0.6);
  color: #fff;
}

.hm-cell.corr-neg-med {
  background: rgba(255, 23, 68, 0.35);
  color: #ccc;
}

.hm-cell.corr-neg-weak {
  background: rgba(255, 23, 68, 0.15);
  color: #999;
}

.hm-cell.corr-zero {
  background: rgba(117, 117, 117, 0.15);
  color: #888;
}

.hm-cell.diagonal {
  background: var(--bg);
  color: var(--muted);
}

/* ── Pairs Section ── */
.pairs-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.pairs-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}

.pairs-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.pair-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 12px;
}

.pair-item:last-child {
  border-bottom: none;
}

.pair-hotels {
  font-weight: 600;
  flex: 1;
}

.pair-value {
  font-family: monospace;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 3px;
  margin-left: 8px;
}

.pair-value.positive {
  background: rgba(0, 200, 83, 0.2);
  color: var(--call);
}

.pair-value.negative {
  background: rgba(255, 23, 68, 0.2);
  color: var(--put);
}

/* ── Filter Bar ── */
.filter-bar {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-bar select,
.filter-bar input {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 5px 8px;
  font-size: 12px;
}

.filter-bar label {
  font-size: 10px;
  color: var(--muted);
  text-transform: uppercase;
  margin-right: 4px;
}

.loading {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-style: italic;
}

.error {
  background: rgba(255, 23, 68, 0.1);
  border: 1px solid var(--put);
  border-radius: 8px;
  padding: 16px;
  color: var(--put);
  margin-bottom: 16px;
}

@media (max-width: 900px) {
  .pairs-section {
    grid-template-columns: 1fr;
  }

  .hm-header-row,
  .hm-row {
    grid-template-columns: 100px repeat(auto-fit, minmax(50px, 1fr));
  }

  .hm-cell,
  .hm-header-cell,
  .hm-label {
    font-size: 10px;
    padding: 6px;
  }
}
</style>
</head>
<body>

<div class="page">

  <!-- ═════════════════ Header ═════════════════ -->
  <div class="header">
    <h1>Correlation Heat Map</h1>
    <div class="header-right">
      <div class="status-badge" id="status">Loading...</div>
      <a href="/api/v1/salesoffice/home">&larr; Home</a>
    </div>
  </div>

  <!-- ═════════════════ Summary Cards ═════════════════ -->
  <div class="summary-cards" id="summary-cards">
    <div class="card">
      <div class="card-title">Hotels Analyzed</div>
      <div class="card-value" id="card-hotels">-</div>
      <div class="card-subtitle">in correlation matrix</div>
    </div>
    <div class="card">
      <div class="card-title">Strongest Positive</div>
      <div class="card-value positive" id="card-strongest-pos">-</div>
      <div class="card-subtitle" id="card-strongest-pos-pair">-</div>
    </div>
    <div class="card">
      <div class="card-title">Strongest Negative</div>
      <div class="card-value negative" id="card-strongest-neg">-</div>
      <div class="card-subtitle" id="card-strongest-neg-pair">-</div>
    </div>
    <div class="card">
      <div class="card-title">Average Correlation</div>
      <div class="card-value" id="card-avg">-</div>
      <div class="card-subtitle">across all pairs</div>
    </div>
  </div>

  <!-- ═════════════════ Heat Map ═════════════════ -->
  <div class="heatmap-container" id="heatmap-container">
    <div class="heatmap-title">Inter-Hotel Price Correlation</div>
    <div class="heatmap-grid" id="heatmap">
      <div class="loading">Fetching correlation data...</div>
    </div>
  </div>

  <!-- ═════════════════ Pairs Section ═════════════════ -->
  <div class="pairs-section">
    <div class="pairs-box">
      <div class="pairs-title">Top 5 Positive Correlations</div>
      <div id="pairs-positive" class="loading">Loading...</div>
    </div>
    <div class="pairs-box">
      <div class="pairs-title">Top 5 Negative Correlations</div>
      <div id="pairs-negative" class="loading">Loading...</div>
    </div>
  </div>

</div>

<script>
const API_BASE = '/api/v1/salesoffice';

async function loadCorrelation() {
  try {
    const resp = await fetch(`${API_BASE}/correlation`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    renderHeatmap(data);
    updateSummary(data);
    updatePairs(data);

    document.getElementById('status').textContent = 'Ready';
    document.getElementById('status').style.color = '#00c853';
  } catch (err) {
    console.error('Failed to load correlation:', err);
    document.getElementById('heatmap-container').innerHTML =
      `<div class="error">Error loading correlation data: ${err.message}</div>`;
    document.getElementById('status').textContent = 'Error';
    document.getElementById('status').style.color = '#ff1744';
  }
}

function renderHeatmap(data) {
  const { hotels, matrix } = data;
  if (!hotels || !matrix) return;

  const hm = document.getElementById('heatmap');
  let html = '';

  // Header row
  html += '<div class="hm-header-row">';
  html += '<div class="hm-header-cell"></div>';
  for (const hotel of hotels) {
    html += `<div class="hm-header-cell">${hotel}</div>`;
  }
  html += '</div>';

  // Data rows
  for (let i = 0; i < hotels.length; i++) {
    html += '<div class="hm-row">';
    html += `<div class="hm-label">${hotels[i]}</div>`;

    for (let j = 0; j < hotels.length; j++) {
      const val = matrix[i][j];
      let cls = 'hm-cell';

      if (i === j) {
        cls += ' diagonal';
      } else if (val > 0.5) {
        cls += ' corr-pos-strong';
      } else if (val > 0.25) {
        cls += ' corr-pos-med';
      } else if (val > 0.05) {
        cls += ' corr-pos-weak';
      } else if (val < -0.5) {
        cls += ' corr-neg-strong';
      } else if (val < -0.25) {
        cls += ' corr-neg-med';
      } else if (val < -0.05) {
        cls += ' corr-neg-weak';
      } else {
        cls += ' corr-zero';
      }

      const valStr = val.toFixed(3);
      html += `<div class="${cls}" title="${hotels[i]} ↔ ${hotels[j]}: ${valStr}">${valStr}</div>`;
    }

    html += '</div>';
  }

  hm.innerHTML = html;
}

function updateSummary(data) {
  const { hotels, matrix } = data;
  document.getElementById('card-hotels').textContent = hotels.length;

  let allVals = [];
  for (let i = 0; i < hotels.length; i++) {
    for (let j = i + 1; j < hotels.length; j++) {
      allVals.push({ val: matrix[i][j], i, j });
    }
  }

  const positives = allVals.filter(x => x.val > 0).sort((a, b) => b.val - a.val);
  const negatives = allVals.filter(x => x.val < 0).sort((a, b) => a.val - b.val);

  if (positives.length > 0) {
    const pos = positives[0];
    document.getElementById('card-strongest-pos').textContent = pos.val.toFixed(3);
    document.getElementById('card-strongest-pos-pair').textContent =
      `${hotels[pos.i]} ↔ ${hotels[pos.j]}`;
  }

  if (negatives.length > 0) {
    const neg = negatives[0];
    document.getElementById('card-strongest-neg').textContent = neg.val.toFixed(3);
    document.getElementById('card-strongest-neg-pair').textContent =
      `${hotels[neg.i]} ↔ ${hotels[neg.j]}`;
  }

  const avg = allVals.length > 0 ? allVals.reduce((s, x) => s + x.val, 0) / allVals.length : 0;
  document.getElementById('card-avg').textContent = avg.toFixed(3);
}

function updatePairs(data) {
  const { hotels, matrix } = data;

  let allPairs = [];
  for (let i = 0; i < hotels.length; i++) {
    for (let j = i + 1; j < hotels.length; j++) {
      allPairs.push({
        h1: hotels[i],
        h2: hotels[j],
        val: matrix[i][j],
      });
    }
  }

  const positives = allPairs.filter(p => p.val > 0).sort((a, b) => b.val - a.val).slice(0, 5);
  const negatives = allPairs.filter(p => p.val < 0).sort((a, b) => a.val - b.val).slice(0, 5);

  let posHtml = '';
  for (const p of positives) {
    posHtml += `
      <div class="pair-item">
        <div class="pair-hotels">${p.h1} ↔ ${p.h2}</div>
        <div class="pair-value positive">${p.val.toFixed(3)}</div>
      </div>
    `;
  }
  document.getElementById('pairs-positive').innerHTML = posHtml || '<div style="color: var(--muted); padding: 8px;">No positive correlations found</div>';

  let negHtml = '';
  for (const p of negatives) {
    negHtml += `
      <div class="pair-item">
        <div class="pair-hotels">${p.h1} ↔ ${p.h2}</div>
        <div class="pair-value negative">${p.val.toFixed(3)}</div>
      </div>
    `;
  }
  document.getElementById('pairs-negative').innerHTML = negHtml || '<div style="color: var(--muted); padding: 8px;">No negative correlations found</div>';
}

// Load on page load
window.addEventListener('load', loadCorrelation);

// Auto-refresh every 5 minutes
setInterval(loadCorrelation, 5 * 60 * 1000);
</script>

</body>
</html>
"""
