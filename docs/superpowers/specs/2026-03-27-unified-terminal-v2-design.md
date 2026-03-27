# Medici Terminal V2 — Unified Trading Terminal Design Spec

## Overview

Replace all 9 existing dashboards with a single Bloomberg/TWS-style trading terminal for hotel room options. One HTML template, one URL, all capabilities.

**Replaces:** Command Center, Unified Terminal, Macro Terminal, Trading Terminal, Options Board, Charts Page, Path Forecast, Override Queue, Opportunity Queue.

**URL:** `/dashboard/terminal-v2`

**Design Reference:** Interactive Brokers TWS Desktop — dark theme, multi-panel, professional trading UX.

## Architecture

Single Jinja2 template (`src/templates/terminal_v2.html`) rendered by a thin page generator (`src/analytics/terminal_v2_page.py`). All data fetched client-side from existing 90+ API endpoints. No new backend endpoints required for MVP.

```
terminal_v2.html (Jinja2 template)
  └── JavaScript client
       ├── API Service layer (fetch wrappers)
       ├── State Manager (selected room, filters, mode)
       ├── Table Component
       ├── Chart Component (3 synced panels)
       ├── HeatMap Component
       ├── Sidebar Component (alerts, queues, rules)
       └── Filter Component
```

## Layout

```
┌─[Header]────────────────────────────────────────────────────┐
│ MEDICI TERMINAL ● LIVE │ CALL:142 PUT:89 NEUT:231 │ 4050rm  │
├─[Filter Strip]──────────────────────────────────────────────┤
│ [All|CALL|PUT] Hotel▼ Zone▼ T:0-180▼ Category▼ Board▼ 🔍   │
├─────────────────────────────────────────┬───────────────────┤
│                                         │                   │
│  SIGNAL TABLE (resizable, top half)     │  RIGHT SIDEBAR    │
│                                         │  240px fixed      │
│  13 columns, sortable, selectable       │                   │
│  click row → charts update below        │  ⚡ Alerts        │
│                                         │  🔻 Override Q    │
├─ ─ ─ ─ [resize handle] ─ ─ ─ ─ ─ ─ ─ ─│  🔺 Opportunity Q │
│                                         │  📋 Rules         │
│  CHART AREA (bottom half)               │  ℹ️ Selected Info  │
│  Tabs: [📈 Chart] [🗺️ HeatMap]          │                   │
│                                         │                   │
│  3 synced panels:                       │                   │
│  1. Price (scan history + FC)           │                   │
│  2. Velocity (rate of change bars)      │                   │
│  3. Voter Timeline (14 agents)          │                   │
│                                         │                   │
│  [Voter Toggle Bar + Consensus]         │                   │
└─────────────────────────────────────────┴───────────────────┘
```

## Components

### 1. Header Bar (36px)

- Left: "MEDICI TERMINAL" logo + green "● LIVE" indicator + last scan timestamp
- Right: Portfolio stats — `CALL:N | PUT:N | NEUT:N | Total rooms | ⚡ N alerts`
- Auto-updates every 60s via `/api/v1/salesoffice/macro/summary`

### 2. Filter Strip (32px)

Single horizontal row of controls:

| Control | Type | Default | API Param |
|---------|------|---------|-----------|
| Signal | Toggle buttons (All/CALL/PUT) | All | Client-side filter |
| Hotel | Dropdown (multi-select) | All | Client-side filter |
| Zone | Dropdown | All | Client-side filter |
| T Range | Dropdown (0-7, 8-14, 15-30, 31-60, 61-90, 91+) | 0-180 | Client-side filter |
| Category | Dropdown | All | Client-side filter |
| Board | Dropdown | All | Client-side filter |
| Search | Text input | Empty | Client-side filter |
| Reset | Button | — | Clears all |

All filtering is client-side on pre-loaded data. No API calls on filter change.

### 3. Signal Table (top half, resizable)

13 columns, sortable by click on header:

| # | Column | Source | Format |
|---|--------|--------|--------|
| 1 | Hotel | prediction.hotel_name | Text |
| 2 | Cat/Board | prediction.room_category + room_board | "DLX BB" |
| 3 | Check-in | prediction.checkin_date | "Apr 28" |
| 4 | T | computed days to checkin | "32d" (color: <14d red, <30d amber, else gray) |
| 5 | Price | prediction.current_price | "$285" bold white |
| 6 | Signal | prediction.option_signal | Badge: green CALL / red PUT / gray NEUT |
| 7 | Cons% | prediction.consensus_probability | "78%" colored by signal |
| 8 | Δ24h | prediction.scan_history.velocity_24h or last change | "+4.4%" green/red |
| 9 | Sparkline | prediction.scan_history.scan_price_series | Unicode block chars "▁▂▃▄▅▆▇" |
| 10 | ↑/↓ | scan_history.scan_actual_rises / drops | "12/4" green/red |
| 11 | Rate/d | computed from scan_history | "+$4/d" |
| 12 | Direction | scan_history.scan_trend + momentum | "↑↑ Bullish" / "↓ Bearish" / "─ Sideways" |
| 13 | Target | prediction.predicted_price | "$320" colored |

**Behavior:**
- Click row → selected (blue left border + highlight)
- Selected row triggers chart area update (3 API calls in parallel)
- Keyboard: ↑/↓ to navigate, Enter to select
- Sort: click header toggles asc/desc, default sort by |Cons%| descending
- Pagination: virtual scroll (render visible rows only) for 4000+ rows performance

**Data source:** `GET /api/v1/salesoffice/options?limit=5000&profile=lite`
- Loaded once at startup, refreshed every 60s
- `profile=lite` skips heavy computation for fast initial load

### 4. Resize Handle (4px)

Draggable horizontal bar between table and chart area. Stores position in localStorage. Default: 45% table / 55% chart.

### 5. Chart Area (bottom half)

#### 5.1 Mode Tabs

Two modes sharing the same space:
- **📈 Chart** (default) — 3 synced panels + voter overlays
- **🗺️ HeatMap** — Hotel × T-bucket matrix (from Macro Terminal)

Right side of tab bar shows selected room context: "Marriott SB — DLX BB — Apr 28 (T=32)"

#### 5.2 Chart Mode — 3 Synced Panels

All three panels share synchronized X-axis (time/T). Hover crosshair syncs across all three.

**Panel 1: Price Chart (flex: 3)**

Split view with vertical dashed line at "TODAY":
- **Left side (Scan History):** Actual price observations from scan_price_series. Solid green/red line with dots at each scan point. Area fill below with 15% opacity.
- **Right side (Forward Curve):** Predicted prices from FC. Dashed blue line with confidence band (shaded area). Target price dot at end.
- **Overlays (toggleable):**
  - Buy/Sell markers (from path_forecast: best trade points)
  - Competitor average line (dashed, from zone avg)
  - Demand zones (horizontal bands for support/resistance)
  - Voter annotations (icons positioned on timeline — see Voter Overlay section)

Data sources:
- Scan history: `GET /api/v1/salesoffice/scan-history/{detail_id}`
- Forward curve: `GET /api/v1/salesoffice/forward-curve/{detail_id}?raw=true`
- Path forecast: `GET /api/v1/salesoffice/path-forecast/{detail_id}`
- Demand zones: `GET /api/v1/salesoffice/trading/zones`

**Panel 2: Velocity Chart (flex: 1)**

Vertical bars showing rate of change per scan/day:
- Green bars = positive change (price rose)
- Red bars = negative change (price fell)
- Bar height = magnitude of change
- Computed from scan_price_series consecutive differences

**Panel 3: Voter Timeline (flex: 1.2)**

Grid with 14 rows (one per voter) × N columns (time periods):
- Each cell = small colored square: green (CALL), red (PUT), gray (NEUTRAL)
- Left labels: FC, Velocity, Events, Competitors, Seasonality, Flights, Weather, Peers, Bookings, Historical, Benchmark, ScanDrop, Provider, Margin
- Shows how each voter's signal evolved over time/T

Data source: `GET /api/v1/salesoffice/signal/consensus/{detail_id}` — current snapshot. Historical voter data derived from daily_signals enrichment_json.

#### 5.3 Voter Overlay System

14 voters, each toggleable via the Voter Toggle Bar below charts:

| Voter | Icon | Overlay Type | Data Source |
|-------|------|-------------|-------------|
| Forward Curve | 📈 | Main price line (always on) | forward-curve endpoint |
| Scan Velocity | ⚡ | Arrows ↑↓ with % at scan points | scan-history |
| Events | ★ | Star icons at event dates on timeline | /events |
| Competitors | 🏨 | Dashed line of zone average price | /market/competitors |
| Seasonality | 📅 | Background band (high=green, low=red tint) | FC enrichments |
| Flights | ✈ | Icons at demand spikes on timeline | /flights/demand |
| Weather | ☁ | Icons at weather events (rain/hurricane) | /market/weather |
| Peers | 👥 | Dots showing peer hotel prices | /hotel-peers |
| Bookings | 📊 | — (shown in voter timeline only) | consensus endpoint |
| Historical | 📜 | — (shown in voter timeline only) | consensus endpoint |
| Benchmark | 📏 | Horizontal line at official ADR | /market/official-benchmarks |
| Scan Drop | ⚠ | — (shown in voter timeline only) | consensus endpoint |
| Provider | 🔗 | — (shown in voter timeline only) | consensus endpoint |
| Margin | 💰 | — (shown in voter timeline only) | consensus endpoint |

Toggle bar at bottom of chart area:
- Each voter = clickable chip with colored dot + name
- ON = border highlighted, layer visible
- OFF = dimmed, layer hidden
- Right side: Consensus bar (green/red/gray proportional) + "78% CALL (11/14)"

#### 5.4 HeatMap Mode

Hotel × T-bucket matrix (migrated from Macro Terminal):
- Rows: Hotels (grouped by zone)
- Columns: T-buckets (0-14d, 15-30d, 31-60d, 61-90d, 91+d)
- Cell color: dominant signal (green=CALL, red=PUT, gray=NEUT), intensity=confidence
- Cell text: count of rooms in that bucket
- Click cell → filters table above to that hotel+T range

Data source: `GET /api/v1/salesoffice/macro/summary`

### 6. Right Sidebar (240px, fixed)

Collapsible via toggle button (chevron). Collapsed state stores in localStorage.

#### 6.1 Alerts Section

- Header: "⚡ ALERTS" + red badge with count
- Feed: latest 10 alerts, auto-refresh every 30s
- Each alert: severity bar (red/amber/blue) + message + time ago
- Click alert → selects the relevant room in table + scrolls to it
- Data: `GET /api/v1/salesoffice/streaming-alerts?limit=10`

#### 6.2 Override Queue Section

- Header: "🔻 OVERRIDE QUEUE" + pending count
- List: recent overrides with status (pending/picked/done/failed)
- Action button: "▼ Queue Override for Selected" (disabled if no room selected or signal != PUT)
- Click button → POST to `/api/v1/salesoffice/override/new` with selected detail_id, default $1 discount
- Data: `GET /api/v1/salesoffice/override/queue`

#### 6.3 Opportunity Queue Section

- Header: "🔺 OPPORTUNITY QUEUE" + pending count
- List: recent opportunities with status
- Action button: "▲ Queue Buy for Selected" (disabled if no room selected or signal != CALL)
- Click button → POST to `/api/v1/salesoffice/opportunity/new` with selected detail_id
- Data: `GET /api/v1/salesoffice/opportunity/queue`

#### 6.4 Rules Section

- Header: "📋 RULES" + "+ Add" link
- List: active rules (name + brief detail + active status)
- "▶ Trigger Rules Now" button → POST to rules trigger endpoint
- Data: `GET /api/v1/salesoffice/override/rules` + `GET /api/v1/salesoffice/opportunity/rules`

#### 6.5 Selected Room Info

- Shows when a room is selected in the table
- Details: Hotel name, Category, Board, Check-in, T, Price, Target, Trade potential
- Accuracy (30d): from `/accuracy/summary`
- Data Quality: from prediction data

### 7. Chart Library

All charts use **Chart.js v4** (already in project). Specific plugins:
- `chartjs-plugin-annotation` — for voter icon overlays, demand zone bands, buy/sell markers
- `chartjs-plugin-crosshair` — for synced crosshair across 3 panels

No new chart library required.

## Data Flow

### Startup Sequence

```
1. Page load
2. Parallel fetch:
   a. GET /options?limit=5000&profile=lite → populate table
   b. GET /macro/summary → populate header stats + heatmap data
   c. GET /streaming-alerts?limit=10 → populate alerts
   d. GET /override/queue → populate override section
   e. GET /opportunity/queue → populate opportunity section
   f. GET /override/rules + /opportunity/rules → populate rules
3. Render table with first batch
4. Auto-select first CALL or PUT row
5. Trigger chart load for selected row
```

### Room Selection Sequence

```
User clicks table row (detail_id = X)
  ├── GET /forward-curve/X?raw=true
  ├── GET /scan-history/X
  ├── GET /path-forecast/X
  ├── GET /signal/consensus/X
  └── GET /trading/zones (if not cached)
All 5 calls in parallel → render charts when all complete
```

### Auto-Refresh Cycles

| Component | Interval | Endpoint |
|-----------|----------|----------|
| Header stats | 60s | /macro/summary |
| Signal table | 60s | /options?profile=lite |
| Alerts feed | 30s | /streaming-alerts |
| Queue status | 60s | /override/queue + /opportunity/queue |
| Charts | Manual (on row select) | Multiple |

## Styling

- **Theme:** Dark, Bloomberg/TWS inspired
- **Background:** `#080c14` (near black)
- **Panel backgrounds:** `#0f172a` (dark navy)
- **Borders:** `#1e293b` (subtle gray)
- **Text primary:** `#e2e8f0`
- **Text secondary:** `#64748b`
- **CALL/Bullish:** `#10b981` (green)
- **PUT/Bearish:** `#ef4444` (red)
- **NEUTRAL:** `#6b7280` (gray)
- **Accent:** `#3b82f6` (blue)
- **Font:** `'SF Mono', 'Fira Code', 'Cascadia Code', monospace` — 11px base
- **No rounded corners** on main panels (sharp, professional)
- **Minimal padding** — data density over whitespace

## Performance Targets

- Initial load: < 2s (lite profile, no heavy computation)
- Room selection → charts rendered: < 1s
- Table sort/filter: < 100ms (client-side, no API call)
- Memory: < 150MB for 5000 rows with all chart instances
- Virtual scrolling for table (only render visible rows)

## Migration Path

### Phase 1: Build Terminal V2 (this spec)
- New template + page generator
- New route `/dashboard/terminal-v2`
- All existing dashboards remain accessible

### Phase 2: Validate & Iterate
- User testing on production data
- Adjust column widths, chart proportions
- Add missing features identified during testing

### Phase 3: Deprecate Old Dashboards
- Redirect `/dashboard/command-center` → `/dashboard/terminal-v2`
- Redirect `/dashboard/unified-terminal` → `/dashboard/terminal-v2`
- Keep old templates for 30 days, then remove

## Files to Create

| File | Purpose | Est. Lines |
|------|---------|------------|
| `src/templates/terminal_v2.html` | Main Jinja2 template (HTML + CSS + JS) | ~2500 |
| `src/analytics/terminal_v2_page.py` | Thin page generator | ~15 |
| `src/api/routers/dashboard_router.py` | Add route (edit existing) | +5 |
| `tests/unit/test_terminal_v2.py` | Route + page generator tests | ~30 |

## Files NOT Changed

- No changes to any existing API endpoint
- No changes to analytics engines
- No changes to prediction pipeline
- No changes to database layer
- No changes to existing dashboards (until Phase 3)

## Out of Scope

- Mobile responsive layout (desktop-first, like TWS)
- WebSocket real-time updates (polling is sufficient for 3h scan cycle)
- New API endpoints (all data accessible via existing 90+ endpoints)
- Changes to prediction algorithms or voter weights
- User authentication or multi-user support
