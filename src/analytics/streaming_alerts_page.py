"""Streaming Alerts Panel — real-time alert monitoring dashboard."""
from __future__ import annotations


def generate_streaming_alerts_html() -> str:
    """Return self-contained HTML for the Streaming Alerts dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Streaming Alerts — Medici</title>
<style>
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --panel: #0f3460;
  --border: #1f4068;
  --text: #eee;
  --muted: #8899aa;
  --critical: #ff1744;
  --warning: #ff9800;
  --info: #42a5f5;
  --success: #00c853;
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
  max-width: 1400px;
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
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
  animation: pulse 2s infinite;
}

.status-dot.active {
  background: var(--success);
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

a {
  color: var(--info);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* ── Summary Cards ── */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
  font-family: monospace;
  margin-bottom: 4px;
}

.card-value.critical {
  color: var(--critical);
}

.card-value.warning {
  color: var(--warning);
}

.card-value.info {
  color: var(--info);
}

.card-value.success {
  color: var(--success);
}

.card-title {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ── Filter Bar ── */
.filter-bar {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-bar select,
.filter-bar input {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 12px;
}

.filter-bar label {
  font-size: 10px;
  color: var(--muted);
  text-transform: uppercase;
  margin-right: 4px;
}

.filter-spacer {
  flex: 1;
}

.btn-refresh {
  background: var(--panel);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}

.btn-refresh:hover {
  border-color: var(--info);
  color: var(--info);
}

/* ── Alerts Table ── */
.table-container {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  padding: 10px 14px;
}

.table-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
}

.table-count {
  font-size: 11px;
  color: var(--muted);
  font-family: monospace;
}

.alerts-table {
  width: 100%;
  border-collapse: collapse;
}

.alerts-table thead {
  background: var(--panel);
}

.alerts-table th {
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  text-align: left;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.alerts-table td {
  padding: 10px 12px;
  font-size: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.alerts-table tbody tr:hover {
  background: rgba(66, 165, 245, 0.08);
}

.severity-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.severity-badge.critical {
  background: rgba(255, 23, 68, 0.3);
  color: var(--critical);
}

.severity-badge.warning {
  background: rgba(255, 152, 0, 0.3);
  color: var(--warning);
}

.severity-badge.info {
  background: rgba(66, 165, 245, 0.3);
  color: var(--info);
}

.alert-type {
  font-weight: 600;
  color: var(--text);
}

.alert-message {
  color: var(--muted);
  max-width: 400px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-time {
  font-family: monospace;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
}

.loading {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-style: italic;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.error {
  background: rgba(255, 23, 68, 0.1);
  border: 1px solid var(--critical);
  border-radius: 8px;
  padding: 16px;
  color: var(--critical);
  margin-bottom: 16px;
}

@media (max-width: 900px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .alert-message {
    max-width: 150px;
  }

  .filter-bar {
    gap: 8px;
  }
}
</style>
</head>
<body>

<div class="page">

  <!-- ═════════════════ Header ═════════════════ -->
  <div class="header">
    <h1>Streaming Alerts</h1>
    <div class="header-right">
      <div class="status-badge">
        <div class="status-dot active"></div>
        <span id="status">Monitoring</span>
      </div>
      <a href="/api/v1/salesoffice/home">&larr; Home</a>
    </div>
  </div>

  <!-- ═════════════════ Summary Cards ═════════════════ -->
  <div class="summary-cards">
    <div class="card">
      <div class="card-value critical" id="card-critical">-</div>
      <div class="card-title">Critical</div>
    </div>
    <div class="card">
      <div class="card-value warning" id="card-warning">-</div>
      <div class="card-title">Warnings</div>
    </div>
    <div class="card">
      <div class="card-value info" id="card-info">-</div>
      <div class="card-title">Info</div>
    </div>
    <div class="card">
      <div class="card-value success" id="card-total">-</div>
      <div class="card-title">Total</div>
    </div>
  </div>

  <!-- ═════════════════ Filter Bar ═════════════════ -->
  <div class="filter-bar">
    <div>
      <label>Severity:</label>
      <select id="f-severity">
        <option value="">All</option>
        <option value="critical">Critical</option>
        <option value="warning">Warning</option>
        <option value="info">Info</option>
      </select>
    </div>
    <div>
      <label>Type:</label>
      <select id="f-type">
        <option value="">All Types</option>
      </select>
    </div>
    <div class="filter-spacer"></div>
    <button class="btn-refresh" id="btn-refresh">⟳ Refresh</button>
  </div>

  <!-- ═════════════════ Alerts Table ═════════════════ -->
  <div class="table-container">
    <div class="table-header">
      <span class="table-title">Active Alerts</span>
      <span class="table-count" id="table-count">0 alerts</span>
    </div>
    <div id="alerts-table-container">
      <div class="loading">Fetching alerts...</div>
    </div>
  </div>

</div>

<script>
const API_BASE = '/api/v1/salesoffice';
let allAlerts = [];
let refreshInterval = null;

async function loadAlerts() {
  try {
    const resp = await fetch(`${API_BASE}/streaming-alerts`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();
    allAlerts = Array.isArray(data) ? data : data.alerts || [];

    updateSummary();
    updateAlertTypeFilter();
    renderTable();
    document.getElementById('status').textContent = 'Monitoring';
  } catch (err) {
    console.error('Failed to load alerts:', err);
    document.getElementById('alerts-table-container').innerHTML =
      `<div class="error">Error loading alerts: ${err.message}</div>`;
    document.getElementById('status').textContent = 'Error';
  }
}

function updateSummary() {
  const critical = allAlerts.filter(a => a.severity === 'critical').length;
  const warning = allAlerts.filter(a => a.severity === 'warning').length;
  const info = allAlerts.filter(a => a.severity === 'info').length;
  const total = allAlerts.length;

  document.getElementById('card-critical').textContent = critical;
  document.getElementById('card-warning').textContent = warning;
  document.getElementById('card-info').textContent = info;
  document.getElementById('card-total').textContent = total;
}

function updateAlertTypeFilter() {
  const types = new Set();
  allAlerts.forEach(a => {
    if (a.alert_type) types.add(a.alert_type);
  });

  const sel = document.getElementById('f-type');
  const current = sel.value;
  sel.innerHTML = '<option value="">All Types</option>';

  Array.from(types).sort().forEach(t => {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  });

  sel.value = current;
}

function renderTable() {
  const severity = document.getElementById('f-severity').value;
  const type = document.getElementById('f-type').value;

  let filtered = allAlerts;
  if (severity) filtered = filtered.filter(a => a.severity === severity);
  if (type) filtered = filtered.filter(a => a.alert_type === type);

  document.getElementById('table-count').textContent = `${filtered.length} alert${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0) {
    document.getElementById('alerts-table-container').innerHTML =
      '<div class="empty-state"><div class="empty-state-icon">✓</div>No alerts matching filters</div>';
    return;
  }

  let html = '<table class="alerts-table"><thead><tr>';
  html += '<th>Severity</th>';
  html += '<th>Type</th>';
  html += '<th>Message</th>';
  html += '<th>Hotel</th>';
  html += '<th>Time</th>';
  html += '</tr></thead><tbody>';

  for (const alert of filtered) {
    const severity_class = alert.severity || 'info';
    const time = formatTime(alert.timestamp || alert.time);
    const message = alert.message || alert.msg || '-';
    const hotel = alert.hotel_id || alert.hotel || '-';
    const type = alert.alert_type || alert.type || '-';

    html += '<tr>';
    html += `<td><span class="severity-badge ${severity_class}">${(alert.severity || 'info').toUpperCase()}</span></td>`;
    html += `<td><span class="alert-type">${type}</span></td>`;
    html += `<td><span class="alert-message" title="${escapeHtml(message)}">${escapeHtml(message)}</span></td>`;
    html += `<td>${escapeHtml(String(hotel))}</td>`;
    html += `<td><span class="alert-time">${time}</span></td>`;
    html += '</tr>';
  }

  html += '</tbody></table>';
  document.getElementById('alerts-table-container').innerHTML = html;
}

function formatTime(ts) {
  if (!ts) return '-';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return String(ts).substring(0, 16);
  }
}

function escapeHtml(s) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return String(s).replace(/[&<>"']/g, c => map[c]);
}

// Event listeners
document.getElementById('f-severity').addEventListener('change', renderTable);
document.getElementById('f-type').addEventListener('change', renderTable);
document.getElementById('btn-refresh').addEventListener('click', loadAlerts);

// Initial load
window.addEventListener('load', () => {
  loadAlerts();
  // Auto-refresh every 60 seconds
  refreshInterval = setInterval(loadAlerts, 60 * 1000);
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>

</body>
</html>
"""
