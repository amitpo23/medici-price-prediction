"""Audit Trail Viewer — event log monitoring with filters and payload expansion."""
from __future__ import annotations


def generate_audit_trail_html() -> str:
    """Return self-contained HTML for the Audit Trail dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audit Trail — Medici</title>
<style>
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --panel: #0f3460;
  --border: #1f4068;
  --text: #eee;
  --muted: #8899aa;
  --call: #00c853;
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
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}

.card-value {
  font-size: 24px;
  font-weight: 700;
  font-family: monospace;
  color: var(--text);
  margin-bottom: 4px;
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
  border-color: var(--accent);
  color: var(--accent);
}

/* ── Event Table ── */
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

.audit-table {
  width: 100%;
  border-collapse: collapse;
}

.audit-table thead {
  background: var(--panel);
}

.audit-table th {
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

.audit-table td {
  padding: 10px 12px;
  font-size: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.audit-table tbody tr:hover {
  background: rgba(66, 165, 245, 0.08);
}

.audit-row-expandable {
  cursor: pointer;
}

.event-type {
  font-weight: 600;
  color: var(--call);
}

.event-user {
  color: var(--muted);
  font-size: 11px;
}

.event-time {
  font-family: monospace;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
}

.expand-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--accent);
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 10px;
  font-weight: 600;
}

.expand-btn:hover {
  border-color: var(--accent);
  color: var(--call);
}

.expand-btn.open {
  background: var(--panel);
  color: var(--call);
}

/* ── Payload Viewer ── */
.payload-row {
  display: none;
}

.payload-row.show {
  display: table-row;
}

.payload-cell {
  padding: 12px;
  background: rgba(0, 200, 83, 0.05);
  border: 1px solid rgba(0, 200, 83, 0.2);
  font-family: monospace;
  font-size: 11px;
  color: #aaa;
}

.payload-content {
  max-height: 300px;
  overflow-y: auto;
  border-radius: 4px;
  padding: 8px;
  background: var(--bg);
}

/* ── Load More ── */
.load-more-container {
  text-align: center;
  padding: 20px;
}

.btn-load-more {
  background: var(--accent);
  color: #000;
  border: none;
  padding: 8px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}

.btn-load-more:hover {
  filter: brightness(1.1);
}

.btn-load-more:disabled {
  opacity: 0.5;
  cursor: default;
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

.error {
  background: rgba(255, 23, 68, 0.1);
  border: 1px solid #ff1744;
  border-radius: 8px;
  padding: 16px;
  color: #ff1744;
  margin-bottom: 16px;
}

@media (max-width: 900px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .event-description {
    max-width: 200px;
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
    <h1>Audit Trail</h1>
    <div class="header-right">
      <div class="status-badge" id="status">Loading...</div>
      <a href="/api/v1/salesoffice/home">&larr; Home</a>
    </div>
  </div>

  <!-- ═════════════════ Summary Cards ═════════════════ -->
  <div class="summary-cards" id="summary-cards">
    <div class="card">
      <div class="card-value" id="card-total">-</div>
      <div class="card-title">Total Events</div>
    </div>
    <div class="card">
      <div class="card-value" id="card-types">-</div>
      <div class="card-title">Event Types</div>
    </div>
    <div class="card">
      <div class="card-value" id="card-hotels">-</div>
      <div class="card-title">Hotels</div>
    </div>
    <div class="card">
      <div class="card-value" id="card-date">-</div>
      <div class="card-title">Latest Event</div>
    </div>
  </div>

  <!-- ═════════════════ Filter Bar ═════════════════ -->
  <div class="filter-bar">
    <div>
      <label>Event Type:</label>
      <select id="f-type">
        <option value="">All Types</option>
      </select>
    </div>
    <div>
      <label>Hotel:</label>
      <select id="f-hotel">
        <option value="">All Hotels</option>
      </select>
    </div>
    <div>
      <label>Date From:</label>
      <input type="date" id="f-date-from">
    </div>
    <div>
      <label>Date To:</label>
      <input type="date" id="f-date-to">
    </div>
    <div class="filter-spacer"></div>
    <button class="btn-refresh" id="btn-refresh">⟳ Refresh</button>
  </div>

  <!-- ═════════════════ Event Table ═════════════════ -->
  <div class="table-container">
    <div class="table-header">
      <span class="table-title">Event Log</span>
      <span class="table-count" id="table-count">0 events</span>
    </div>
    <div id="events-table-container">
      <div class="loading">Fetching audit trail...</div>
    </div>
  </div>

  <!-- ═════════════════ Load More ═════════════════ -->
  <div class="load-more-container" id="load-more-container">
    <button class="btn-load-more" id="btn-load-more">Load More</button>
  </div>

</div>

<script>
const API_BASE = '/api/v1/salesoffice';
let allEvents = [];
let displayedCount = 0;
const pageSize = 50;

async function loadAuditSummary() {
  try {
    const resp = await fetch(`${API_BASE}/audit/summary`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const summary = await resp.json();

    document.getElementById('card-total').textContent = summary.total_events || '-';
    document.getElementById('card-types').textContent = summary.event_types || '-';
    document.getElementById('card-hotels').textContent = summary.unique_hotels || '-';
    document.getElementById('card-date').textContent = formatDate(summary.latest_event) || '-';

    // Populate filter dropdowns
    if (summary.event_types_list) {
      const typeSelect = document.getElementById('f-type');
      const current = typeSelect.value;
      typeSelect.innerHTML = '<option value="">All Types</option>';
      summary.event_types_list.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t;
        opt.textContent = t;
        typeSelect.appendChild(opt);
      });
      typeSelect.value = current;
    }

    if (summary.hotels_list) {
      const hotelSelect = document.getElementById('f-hotel');
      const current = hotelSelect.value;
      hotelSelect.innerHTML = '<option value="">All Hotels</option>';
      summary.hotels_list.forEach(h => {
        const opt = document.createElement('option');
        opt.value = h;
        opt.textContent = h;
        hotelSelect.appendChild(opt);
      });
      hotelSelect.value = current;
    }
  } catch (err) {
    console.error('Failed to load audit summary:', err);
  }
}

async function loadAuditTrail() {
  try {
    const eventType = document.getElementById('f-type').value;
    const hotel = document.getElementById('f-hotel').value;
    const dateFrom = document.getElementById('f-date-from').value;
    const dateTo = document.getElementById('f-date-to').value;

    let url = `${API_BASE}/audit?limit=1000`;
    if (eventType) url += `&event_type=${encodeURIComponent(eventType)}`;
    if (hotel) url += `&hotel_id=${encodeURIComponent(hotel)}`;
    if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`;
    if (dateTo) url += `&date_to=${encodeURIComponent(dateTo)}`;

    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();
    allEvents = Array.isArray(data) ? data : data.events || [];

    displayedCount = 0;
    document.getElementById('status').textContent = 'Ready';
    document.getElementById('status').style.color = '#00c853';

    renderEvents();
  } catch (err) {
    console.error('Failed to load audit trail:', err);
    document.getElementById('events-table-container').innerHTML =
      `<div class="error">Error loading audit trail: ${err.message}</div>`;
    document.getElementById('status').textContent = 'Error';
    document.getElementById('status').style.color = '#ff1744';
  }
}

function renderEvents() {
  const newCount = Math.min(displayedCount + pageSize, allEvents.length);
  const displayed = allEvents.slice(0, newCount);

  document.getElementById('table-count').textContent = `${displayed.length} event${displayed.length !== 1 ? 's' : ''} (${allEvents.length} total)`;

  if (displayed.length === 0) {
    document.getElementById('events-table-container').innerHTML =
      '<div class="empty-state">No events matching filters</div>';
    document.getElementById('btn-load-more').style.display = 'none';
    return;
  }

  let html = '<table class="audit-table"><thead><tr>';
  html += '<th>Time</th>';
  html += '<th>Event Type</th>';
  html += '<th>Description</th>';
  html += '<th>Hotel</th>';
  html += '<th>User</th>';
  html += '<th></th>';
  html += '</tr></thead><tbody>';

  for (let i = 0; i < displayed.length; i++) {
    const evt = displayed[i];
    const rowId = `evt-${i}`;
    const payloadId = `payload-${i}`;

    const time = formatTime(evt.timestamp || evt.created_at);
    const type = evt.event_type || evt.type || '-';
    const desc = evt.description || evt.msg || '-';
    const hotel = evt.hotel_id || evt.hotel || '-';
    const user = evt.user || evt.actor || '-';
    const hasPayload = evt.payload || evt.metadata;

    html += `<tr class="audit-row-expandable" id="${rowId}">`;
    html += `<td><span class="event-time">${time}</span></td>`;
    html += `<td><span class="event-type">${escapeHtml(type)}</span></td>`;
    html += `<td>${escapeHtml(desc)}</td>`;
    html += `<td>${escapeHtml(String(hotel))}</td>`;
    html += `<td><span class="event-user">${escapeHtml(user)}</span></td>`;
    html += `<td><button class="expand-btn" data-id="${payloadId}" ${!hasPayload ? 'disabled' : ''}>${hasPayload ? '▼' : '-'}</button></td>`;
    html += '</tr>';

    if (hasPayload) {
      const payload = evt.payload || evt.metadata;
      const payloadJson = JSON.stringify(payload, null, 2);
      html += `<tr class="payload-row" id="${payloadId}">`;
      html += '<td colspan="6">';
      html += '<div class="payload-cell">';
      html += '<div class="payload-content"><pre>' + escapeHtml(payloadJson) + '</pre></div>';
      html += '</div>';
      html += '</td>';
      html += '</tr>';
    }
  }

  html += '</tbody></table>';
  document.getElementById('events-table-container').innerHTML = html;

  // Attach expand listeners
  document.querySelectorAll('.expand-btn:not([disabled])').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const payloadId = btn.dataset.id;
      const payloadRow = document.getElementById(payloadId);
      const isOpen = payloadRow.classList.contains('show');

      payloadRow.classList.toggle('show', !isOpen);
      btn.classList.toggle('open', !isOpen);
    });
  });

  displayedCount = newCount;
  const hasMore = displayedCount < allEvents.length;
  document.getElementById('btn-load-more').style.display = hasMore ? 'block' : 'none';
  document.getElementById('btn-load-more').disabled = !hasMore;
}

function formatTime(ts) {
  if (!ts) return '-';
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-US', { hour12: false });
  } catch {
    return String(ts).substring(0, 19);
  }
}

function formatDate(ts) {
  if (!ts) return '-';
  try {
    const d = new Date(ts);
    return d.toLocaleDateString('en-US');
  } catch {
    return String(ts).substring(0, 10);
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
document.getElementById('f-type').addEventListener('change', loadAuditTrail);
document.getElementById('f-hotel').addEventListener('change', loadAuditTrail);
document.getElementById('f-date-from').addEventListener('change', loadAuditTrail);
document.getElementById('f-date-to').addEventListener('change', loadAuditTrail);
document.getElementById('btn-refresh').addEventListener('click', loadAuditTrail);
document.getElementById('btn-load-more').addEventListener('click', () => {
  if (displayedCount < allEvents.length) {
    renderEvents();
  }
});

// Initial load
window.addEventListener('load', async () => {
  await loadAuditSummary();
  await loadAuditTrail();
});
</script>

</body>
</html>
"""
