# Execution UI — Claude Code Implementation Prompt

## What You Are Building

Add **execution actions** to the Medici prediction system's Options page and Trading Terminal. The system already has two SQLite-backed job queues with full API endpoints:

1. **Price Override Queue** (PUT signals) — undercut competitors by $X
2. **Opportunity Queue** (CALL signals) — buy at market price, resell at +$50

Both backends are 100% done and tested. Your job is **UI only**: buttons, forms, inline status, and one new dashboard page.

---

## CRITICAL: Do NOT Modify These Files

- `src/analytics/override_queue.py` — 38 tests passing
- `src/analytics/opportunity_queue.py` — 40 tests passing
- The 14 `/override/*` and `/opportunity/*` endpoints in `src/api/routers/analytics_router.py`

---

## API Reference

### Override (PUT) Endpoints

```
POST /api/v1/salesoffice/override/request
  Body: { "detail_id": 12345, "discount_usd": 1.0 }
  Response: { "request_id": 7, "detail_id": 12345, "current_price": 250.0,
              "target_price": 249.0, "discount_usd": 1.0, "status": "pending" }

POST /api/v1/salesoffice/override/bulk
  Body: { "discount_usd": 2.0, "hotel_id": 66814 }   ← hotel_id optional
  Response: { "batch_id": "bulk-...", "count": 14, "requests": [...] }

GET /api/v1/salesoffice/override/queue?status=pending&hotel_id=X&limit=50&offset=0
  Response: { "requests": [...], "total": 57, "stats": {"pending":5,"picked":2,"done":47,"failed":3,"total":57} }

GET /api/v1/salesoffice/override/history?days=30
  Response: { "total":57, "done":47, "failed":3, "success_rate_pct":89.2,
              "avg_discount_usd":1.85, "total_discount_volume_usd":86.95,
              "by_hotel": [{"hotel_id":66814,"hotel_name":"Sunrise","total":25,"done":23,"failed":2},...] }
```

### Opportunity (CALL) Endpoints

```
POST /api/v1/salesoffice/opportunity/request
  Body: { "detail_id": 12345, "max_rooms": 1 }
  Response: { "request_id": 3, "detail_id": 12345, "buy_price": 200.0,
              "push_price": 250.0, "predicted_price": 260.0,
              "profit_usd": 60.0, "max_rooms": 1, "status": "pending" }
  ⚠ Returns 400 if predicted profit < $50

POST /api/v1/salesoffice/opportunity/bulk
  Body: { "max_rooms": 1, "hotel_id": 66814 }   ← hotel_id optional
  Response: { "batch_id": "OPP-...", "count": 8, "markup_usd": 50.0, "requests": [...] }

GET /api/v1/salesoffice/opportunity/queue?status=pending&hotel_id=X&limit=50&offset=0
  Response: { "requests": [...], "total": 19, "stats": {"pending":2,"picked":1,"done":15,"failed":1,"total":19,
              "avg_profit_usd":62.5,"total_profit_usd":937.5} }

GET /api/v1/salesoffice/opportunity/history?days=30
  Response: { "total":19, "done":15, "failed":1, "success_rate_pct":93.8,
              "avg_profit_usd":62.5, "total_profit_usd":937.5,
              "by_hotel": [{"hotel_id":66814,"hotel_name":"Sunrise","total":10,"done":9,"failed":1,"total_profit_usd":560.0},...] }
```

### Guardrails (enforced server-side, also validate client-side)

| Rule | Override (PUT) | Opportunity (CALL) |
|------|----------------|-------------------|
| Trigger | PUT / STRONG_PUT signals | CALL / STRONG_CALL signals |
| User input | discount_usd ($0.01–$10.00) | max_rooms (1–30) |
| Auto-computed | target = current - discount | push = buy + $50 |
| Eligibility | Any PUT signal | predicted - buy >= $50 |
| Max bulk | 100 per batch | 50 per batch |

---

## Task 1: Options Page — Per-Row Action Buttons

**File to modify:** `src/analytics/options_page.py` (the `_build_section_a` function that generates the signals table)

**Template to modify:** `src/templates/options.html` (add JavaScript for override/opportunity actions)

### What to add to each table row

After the existing "Conf" column, add a new **Action** column with one of these states:

**If signal is PUT or STRONG_PUT:**
```html
<td><button class="btn-override" data-detail="12345" data-price="250.00">⬇ Override</button></td>
```

**If signal is CALL or STRONG_CALL AND the options row includes `predicted_price` data AND predicted_price - S_t >= 50:**
```html
<td><button class="btn-buyopp" data-detail="12345" data-buy="200.00" data-predicted="260.00">⬆ Buy Opp</button></td>
```

**If CALL but predicted profit < $50:**
```html
<td><span class="action-disabled" title="Predicted profit < $50">⬆ (< $50)</span></td>
```

**If NONE or no data:**
```html
<td><span class="action-disabled">—</span></td>
```

### Inline form — Override (on click)

Replace the button content with an inline form:
```
Discount: [$1.00] → Target: $249.00   [✓ Queue] [✗]
```
- Default discount: $1.00
- Live update: as user types discount, recompute target = price - discount
- Client validation: 0 < discount ≤ 10, target ≥ $50
- Submit: `POST /override/request { detail_id, discount_usd }`
- Success: replace with `🕐 #7 Queued`
- Error: show red text

### Inline form — Opportunity (on click)

Replace the button content with:
```
Buy $200 → Push $250 (+$50) | Profit: $60   Rooms: [1] [✓ Queue] [✗]
```
- Rooms default: 1, max 30
- push_price and profit are read-only (computed server-side: buy+$50)
- Submit: `POST /opportunity/request { detail_id, max_rooms }`
- Success: replace with `🕐 #3 Queued`
- Error: show red text (e.g., "Predicted profit $30 below minimum $50")

### Important: Where to get predicted_price

The signals returned by `compute_next_day_signals()` include `predicted_price` — check if this field exists. If it does, use it. If not, you need to get it from the analysis predictions:

```python
# In _build_section_a, the signal dict 's' should have:
predicted_price = s.get("predicted_price", 0)  # from the ensemble prediction
current_price = s.get("S_t", 0)
profit = predicted_price - current_price  # >= 50 for eligibility
```

If `predicted_price` is not in the signal dict, pull it from the analysis dict that's passed to `generate_options_html()`:
```python
pred = analysis.get("predictions", {}).get(str(s["detail_id"]), {})
predicted_price = pred.get("predicted_price", 0)
```

Add `predicted_price` and `detail_id` as data attributes on each row so JavaScript can use them.

---

## Task 2: Options Page — Bulk Controls Bar

**Where:** Above the signals table in `_build_section_a` (or in the template), add a control bar:

```html
<div class="execution-bar">
  <!-- Override bulk -->
  <div class="exec-section exec-put">
    <span class="exec-label">⬇ Bulk Override PUTs</span>
    <label>Discount: $<input type="number" id="bulk-discount" value="1.00" min="0.01" max="10" step="0.50"></label>
    <label>Hotel: <select id="bulk-hotel-put"><option value="">All</option><!-- populated by JS --></select></label>
    <button id="btn-bulk-override" class="btn-exec btn-put">▶ Queue All PUTs</button>
    <span id="put-count" class="exec-count">-- PUT signals</span>
  </div>
  <!-- Opportunity bulk -->
  <div class="exec-section exec-call">
    <span class="exec-label">⬆ Bulk Buy CALLs</span>
    <label>Rooms: <input type="number" id="bulk-rooms" value="1" min="1" max="30" step="1"></label>
    <label>Hotel: <select id="bulk-hotel-call"><option value="">All</option></select></label>
    <button id="btn-bulk-opp" class="btn-exec btn-call">▶ Queue Eligible CALLs</button>
    <span id="call-count" class="exec-count">-- eligible CALLs (≥$50 profit)</span>
  </div>
  <!-- Queue status -->
  <div class="exec-status">
    <span id="q-status-override">Override: loading...</span> |
    <span id="q-status-opp">Opportunities: loading...</span> |
    <a href="/api/v1/salesoffice/dashboard/override-queue">View Override Queue →</a> |
    <a href="/api/v1/salesoffice/dashboard/opportunity-queue">View Opp Queue →</a>
  </div>
</div>
```

**JavaScript behavior:**
- On page load: count PUT and eligible CALL signals from the rendered table (use data attributes)
- `[▶ Queue All PUTs]`: confirm dialog → `POST /override/bulk { discount_usd, hotel_id }`
- `[▶ Queue Eligible CALLs]`: confirm dialog → `POST /opportunity/bulk { max_rooms, hotel_id }`
- Queue status: `GET /override/queue` + `GET /opportunity/queue` → show "3 pending | 12 done | 1 failed"

---

## Task 3: Opportunity Queue Dashboard Page

Create a NEW page at `/dashboard/opportunity-queue` modeled on the existing Override Queue page at `src/analytics/override_queue_page.py`.

**New file:** `src/analytics/opportunity_queue_page.py`

Use the exact same pattern as `override_queue_page.py` (self-contained HTML with embedded CSS/JS, dark theme), but adapted for opportunities:

### Key differences from Override Queue page:

1. **Title:** "Opportunity Queue" not "Override Queue"
2. **Stats cards:** Replace "Avg Discount" and "Volume" with "Avg Profit" and "Total Profit"
3. **Table columns:** Replace Price/Discount/Target with Buy/Push/Predicted/Profit/Rooms/OppID
4. **API endpoints:** Use `/opportunity/queue` and `/opportunity/history` instead of `/override/queue` and `/override/history`
5. **Colors:** Use green (#00c853) accent instead of amber (#ff9800)

### Table columns:
```
# | Detail | Hotel | Category | Buy | Push | Predicted | Profit | Rooms | Signal | Status | OppID | Created | Error
```

### Stats cards:
```
Pending | Picked | Done | Failed | Total | Success Rate | Avg Profit | Total Profit
```

### Navigation links:
```
← Terminal | Home | Override Queue
```

### Route registration — add to `src/api/routers/dashboard_router.py`:
```python
@dashboard_router.get("/dashboard/opportunity-queue", response_class=HTMLResponse)
async def dashboard_opportunity_queue(request: Request):
    from src.analytics.opportunity_queue_page import generate_opportunity_queue_html
    return HTMLResponse(content=generate_opportunity_queue_html())
```

---

## Task 4: Navigation Updates

Add "Override Queue" and "Opportunity Queue" links to the navigation in:
- The landing page (`src/analytics/landing_page.py`) if it has a nav section
- The terminal page (`src/analytics/terminal_page.py`) header
- The options page template (`src/templates/options.html`)
- Both queue pages (cross-link to each other)

---

## Task 5: Terminal Integration (if terminal exists)

If `src/analytics/terminal_page.py` has been built with the Signal Summary panel (Section 3A), add execution buttons there:

**For PUT signals:**
```
──────────────────────────
Discount: [$1.00] [⬇ Override]
```

**For CALL signals with profit >= $50:**
```
──────────────────────────
Buy: $200 → Push: $250 | Profit: $60
Rooms: [1] [⬆ Buy Opp]
```

---

## Styling

### Existing theme
The Override Queue page uses dark theme. The Options page may use a lighter theme. Match whatever the existing page uses.

### New CSS classes needed (add to the relevant template/page):

```css
/* Execution bar */
.execution-bar { background: rgba(0,0,0,0.3); border: 1px solid #333; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
.exec-section { display: flex; align-items: center; gap: 10px; padding: 6px 0; flex-wrap: wrap; }
.exec-label { font-weight: 600; min-width: 160px; }
.exec-count { color: #999; font-size: 12px; }
.btn-exec { padding: 6px 16px; border-radius: 4px; border: none; cursor: pointer; font-weight: 600; font-size: 12px; }
.btn-put { background: #ff9800; color: #000; }
.btn-call { background: #00c853; color: #000; }
.btn-put:hover { background: #ffb74d; }
.btn-call:hover { background: #69f0ae; }

/* Per-row action buttons */
.btn-override { background: #ff9800; color: #000; border: none; padding: 3px 10px; border-radius: 3px; cursor: pointer; font-size: 11px; font-weight: 600; }
.btn-buyopp { background: #00c853; color: #000; border: none; padding: 3px 10px; border-radius: 3px; cursor: pointer; font-size: 11px; font-weight: 600; }
.action-disabled { color: #666; font-size: 11px; }

/* Inline forms */
.inline-form { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; }
.inline-form input { width: 60px; padding: 2px 4px; border: 1px solid #ff9800; background: rgba(0,0,0,0.3); color: #eee; border-radius: 3px; text-align: right; }
.inline-form .btn-confirm { background: #4caf50; color: #fff; border: none; padding: 2px 8px; border-radius: 3px; cursor: pointer; }
.inline-form .btn-cancel { background: #666; color: #fff; border: none; padding: 2px 8px; border-radius: 3px; cursor: pointer; }

/* Toast */
.toast { position: fixed; top: 20px; right: 20px; padding: 10px 20px; border-radius: 6px; color: #fff; font-size: 13px; z-index: 9999; animation: slideIn 0.3s ease; }
.toast.success { background: #4caf50; }
.toast.error { background: #f44336; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
```

---

## JavaScript Patterns

### Toast notification
```javascript
function showToast(msg, type='success') {
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 5000);
}
```

### POST helper
```javascript
async function apiPost(url, body) {
  const r = await fetch('/api/v1/salesoffice' + url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
```

### Override inline form
```javascript
function openOverrideForm(btn) {
  const detail = btn.dataset.detail;
  const price = parseFloat(btn.dataset.price);
  const td = btn.parentElement;
  td.innerHTML = `<div class="inline-form">
    -$<input type="number" id="disc-${detail}" value="1.00" min="0.01" max="10" step="0.50"
       oninput="document.getElementById('tgt-${detail}').textContent='$'+(${price}-this.value).toFixed(2)">
    → <span id="tgt-${detail}">$${(price-1).toFixed(2)}</span>
    <button class="btn-confirm" onclick="submitOverride(${detail},this)">✓</button>
    <button class="btn-cancel" onclick="cancelForm(this,'override',${detail},${price})">✗</button>
  </div>`;
}

async function submitOverride(detailId, btn) {
  const discount = parseFloat(document.getElementById('disc-'+detailId).value);
  try {
    const data = await apiPost('/override/request', { detail_id: detailId, discount_usd: discount });
    btn.closest('td').innerHTML = `<span style="color:#ffc107">🕐 #${data.request_id} Queued</span>`;
    showToast(`Queued override #${data.request_id}: -$${discount}`);
  } catch(e) {
    showToast(e.message, 'error');
  }
}
```

### Opportunity inline form
```javascript
function openOppForm(btn) {
  const detail = btn.dataset.detail;
  const buy = parseFloat(btn.dataset.buy);
  const predicted = parseFloat(btn.dataset.predicted);
  const push = buy + 50;
  const profit = (predicted - buy).toFixed(2);
  const td = btn.parentElement;
  td.innerHTML = `<div class="inline-form">
    Buy $${buy.toFixed(0)} → Push $${push.toFixed(0)} | +$${profit}
    Rooms: <input type="number" id="rooms-${detail}" value="1" min="1" max="30" step="1" style="width:40px;border-color:#00c853">
    <button class="btn-confirm" onclick="submitOpp(${detail},this)">✓</button>
    <button class="btn-cancel" onclick="cancelForm(this,'opp',${detail},${buy})">✗</button>
  </div>`;
}

async function submitOpp(detailId, btn) {
  const rooms = parseInt(document.getElementById('rooms-'+detailId).value);
  try {
    const data = await apiPost('/opportunity/request', { detail_id: detailId, max_rooms: rooms });
    btn.closest('td').innerHTML = `<span style="color:#00c853">🕐 #${data.request_id} Queued</span>`;
    showToast(`Queued opp #${data.request_id}: buy=$${data.buy_price}→push=$${data.push_price} profit=$${data.profit_usd}`);
  } catch(e) {
    showToast(e.message, 'error');
  }
}
```

---

## Implementation Order

1. **Options page per-row buttons** — modify `options_page.py` to add Action column with data attributes + add JS to template
2. **Options page bulk bar** — add execution bar HTML above the signals table + JS handlers
3. **Opportunity Queue page** — create `opportunity_queue_page.py` by cloning `override_queue_page.py` and adapting
4. **Route registration** — add `/dashboard/opportunity-queue` to `dashboard_router.py`
5. **Navigation links** — update nav in landing, terminal, options, both queue pages
6. **Terminal integration** — if terminal panel exists, add execution buttons

---

## Verification Checklist

After each task, verify:

```bash
python3 -m py_compile src/analytics/options_page.py
python3 -m py_compile src/analytics/opportunity_queue_page.py
python3 -m py_compile src/api/routers/dashboard_router.py
```

Then manually check:
- [ ] Options page loads at `/options` without errors
- [ ] PUT rows show ⬇ Override button
- [ ] CALL rows with $50+ profit show ⬆ Buy Opp button
- [ ] CALL rows with < $50 profit show grayed out indicator
- [ ] Clicking Override opens inline discount form
- [ ] Clicking Buy Opp opens inline rooms form
- [ ] Submitting Override queues request (verify: GET /override/queue)
- [ ] Submitting Opportunity queues request (verify: GET /opportunity/queue)
- [ ] Bulk Override button queues all PUTs
- [ ] Bulk Opportunity button queues eligible CALLs
- [ ] Confirmation dialogs appear for bulk actions
- [ ] Opportunity Queue page loads at `/dashboard/opportunity-queue`
- [ ] Queue page shows correct stats, table, hotel breakdown
- [ ] Navigation links work across all pages
- [ ] Existing tests still pass: `python -m pytest tests/unit/ -o "addopts=" --ignore=tests/unit/test_api_endpoints.py`
