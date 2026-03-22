# Pre-Command Center UI Baseline
**Date:** 2026-03-22
**Git Tag:** `v2.1.0-ui-baseline`
**Purpose:** Snapshot of all UI components before Command Center build begins.
**Revert:** `git checkout v2.1.0-ui-baseline`

---

## Dashboard Inventory (17 templates, 5,304 lines total)

### Primary Dashboards

| Dashboard | Template | Lines | Endpoint | Theme |
|-----------|----------|-------|----------|-------|
| Macro Terminal | `macro_terminal.html` | 650 | `/dashboard/macro` | Dark (embedded CSS) |
| Trading Terminal | `terminal.html` | 836 | `/dashboard/terminal` | Dark (embedded CSS) |
| Options Board | `options_board.html` | 1,866 | `/options/view` | Light |
| Landing / Home | `landing.html` | 132 | `/home` | Gradient + Cards |

### Secondary Dashboards

| Dashboard | Template | Lines | Endpoint |
|-----------|----------|-------|----------|
| Charts (3-tab) | `charts.html` | 163 | `/charts` |
| Accuracy | `accuracy.html` | 173 | `/accuracy` |
| Alerts | `alerts.html` | 152 | `/alerts` |
| Health | `health.html` | 126 | `/health/view` |
| Year-over-Year | `yoy.html` | 183 | `/yoy` |
| Options Signals | `options.html` | 192 | `/options` |
| Providers | `provider.html` | 163 | `/providers` |
| Freshness | `freshness.html` | 80 | `/freshness` |
| Insights | `insights.html` | 257 | `/insights` |
| Info | `info.html` | 257 | `/info` |

### Shared

| File | Lines | Purpose |
|------|-------|---------|
| `base.html` | 17 | Jinja2 base template |
| `partials/nav.html` | 9 | Navigation bar (9 links) |
| `static/base.css` | 140 | Shared design system |
| `loading.html` | 38 | Loading placeholder |
| `error.html` | 10 | Error page |

---

## Page Generators (Python backend)

| Module | Lines | Serves |
|--------|-------|--------|
| `terminal_page.py` | 9 | Trading Terminal data |
| `landing_page.py` | 72 | Home hub |
| `path_forecast_page.py` | 408 | Path Forecast dashboard |
| `sources_page.py` | 309 | Source Comparison |
| `override_queue_page.py` | 235 | Override Queue dashboard |
| `opportunity_queue_page.py` | 217 | Opportunity Queue dashboard |
| `options_page.py` | 272 | Options Board data |
| `group_actions.py` | 429 | Bulk CALL/PUT actions |

---

## Routers

| Router | Lines | Endpoints |
|--------|-------|-----------|
| `dashboard_router.py` | 398 | 12 HTML dashboard endpoints |
| `analytics_router.py` | 2,919 | ~25 JSON data endpoints |
| `_options_html_gen.py` | 3,551 | HTML table/row generation |
| `_shared_state.py` | 1,104 | Scheduler, cache, computation helpers |
| `ai_router.py` | 279 | 5 AI endpoints |
| `market_router.py` | 299 | 18 market endpoints |
| `export_router.py` | 59 | 3 export endpoints |
| `monitor_router.py` | 151 | Health, ingest, adjustments |

---

## Design System (base.css)

**Colors (Dark Theme):**
- Background: `#0f1117` / Surface: `#1a1d27`, `#232733`
- Borders: `#2d3140`
- Text: `#e4e7ec` (primary), `#8b90a0` (dimmed)
- Accent: `#6366f1`, `#818cf8` (indigo)
- CALL: `#22c55e` / PUT: `#ef4444` / NEUTRAL: `#757575`

**Layout:**
- Max-width: 1200px
- Grid: `repeat(auto-fill, minmax(340px, 1fr))`
- Font: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- Base size: 13px (dark), 14px (light)

---

## Current Workflow (requires 5+ page jumps)

```
1. /home                    → See system status
2. /dashboard/macro         → Portfolio heatmap, identify PUT/CALL
3. Click hotel row          → Drilldown (still in macro)
4. Click option             → /dashboard/terminal (new page)
5. Analyze chart+signals    → Decide
6. /dashboard/sources       → Verify source consensus (new page)
7. /dashboard/path-forecast → Check turning points (new page)
8. Click Override/Buy       → Action queued
9. /dashboard/override-queue → Monitor execution (new page)
```

**Problem:** 5+ page navigations to complete one trade decision.

---

## API Endpoints Used by Dashboards

### Macro Terminal
- `GET /macro/summary` — total options, signal counts, avg confidence
- `GET /macro/sources/{source}` — heatmap data by prediction source
- `GET /macro/drops` — recent price drops
- `GET /group/preview` — bulk action preview

### Trading Terminal
- `GET /options` — paginated options list
- `GET /forward-curve/{id}` — price forecast by T
- `GET /sources/compare/{id}` — per-source signal breakdown
- `GET /charts/contract-data` — historical scan prices (async)
- `POST /override/queue` — queue PUT override
- `POST /opportunity/queue` — queue CALL buy

### Options Board
- `GET /options?all=true` — full options list with enrichments
- `GET /simple` — simplified signal view

### Path Forecast
- `GET /path-forecast/{id}` — turning points, segments, best trade

### Queues
- `GET /override/queue/status` — pending/active/done overrides
- `GET /opportunity/queue/status` — CALL opportunity status

---

## What Will Change (Command Center plan)

All capabilities above will be consolidated into a single 3-column layout:
- **Left:** Smart Navigator (filters, mini heatmap, options table)
- **Center:** Charts Zone (price path + overlays, enrichments, term structure)
- **Right:** Intelligence (signals, sources, accuracy) + Queue Sidebar

Existing dashboards will remain accessible as secondary/admin views.

---

## Recovery Instructions

To revert to this exact state:
```bash
git checkout v2.1.0-ui-baseline
```

To create a branch from this point:
```bash
git checkout -b fix/revert-from-baseline v2.1.0-ui-baseline
```
