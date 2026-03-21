# Trading Terminal — Build Prompt for Claude Code

## Context

The Medici Price Prediction system has all the data and APIs needed, but lacks a unified trading view. The current dashboards are scattered — path forecast on one page, source comparison on another, YoY on a third, enrichments buried in JSON. A trader can't see the full picture on one screen.

## Goal

Build a **Trading Terminal** — a single unified dashboard page at `/dashboard/terminal` that gives a B2B hotel options trader everything they need to make a decision on one screen.

## What Exists (APIs You MUST Use)

All data is available. Do NOT create new analytics modules. Only consume existing endpoints:

```
# Per-option deep dive:
GET /api/v1/salesoffice/forward-curve/{detail_id}          → Full enriched forward curve (day-by-day)
GET /api/v1/salesoffice/forward-curve/{detail_id}?raw=true  → Raw curve + enriched curve + per-enrichment deltas
GET /api/v1/salesoffice/path-forecast/{detail_id}           → Turning points, segments, best trade, min/max
GET /api/v1/salesoffice/sources/compare/{detail_id}         → Per-source predictions + consensus + disagreement
GET /api/v1/salesoffice/sources/raw/{source_name}/{detail_id} → Single source stats + prediction
GET /api/v1/salesoffice/options/detail/{detail_id}          → Full prediction with signals, momentum, regime

# List views:
GET /api/v1/salesoffice/options?limit=50&offset=0           → All signals with path + source enrichment (8 new fields)
GET /api/v1/salesoffice/path-forecast?hotel_id=X&min_profit=Y → Portfolio path forecasts sorted by profit
GET /api/v1/salesoffice/sources/compare?disagreements_only=true → Options where sources disagree

# Chart data:
GET /api/v1/salesoffice/charts/contract-data?detail_id=X    → Historical scan prices for one contract
GET /api/v1/salesoffice/decay-curve                          → System-wide decay curve
GET /api/v1/salesoffice/accuracy/by-t-bucket                 → Prediction accuracy by T-range
GET /api/v1/salesoffice/accuracy/summary?days=30             → Overall accuracy stats

# Market context:
GET /api/v1/salesoffice/events                               → Miami events with multipliers
GET /api/v1/salesoffice/flights/demand                       → Flight demand indicator
GET /api/v1/salesoffice/market/weather                       → Weather forecast
```

## Architecture

### File Structure
```
src/analytics/terminal_page.py     → HTML generator (single file, self-contained)
src/api/routers/dashboard_router.py → Add route: GET /dashboard/terminal
```

### Chart Library
Use **Chart.js** (already loaded in other dashboards via CDN). Do NOT use Plotly (too heavy). Use Canvas API only for custom overlays on Chart.js charts.

### Data Loading
Use the async fetch pattern from existing dashboards:
1. HTML shell loads instantly
2. JavaScript fetches data from APIs
3. Charts render client-side
4. Hotel dropdown changes trigger re-fetch

## The Terminal Layout

### Header Bar
- Hotel dropdown (populated from /options)
- Option/contract dropdown (filtered by selected hotel)
- Auto-refresh toggle (poll every 180s when ON)
- Last updated timestamp

### Main Area — 3 Sections

#### Section 1: Price Path Chart (60% of screen width, top)

One large Chart.js canvas with MULTIPLE LINES on the same chart:

| Line | Source | Style | API |
|------|--------|-------|-----|
| Ensemble Forecast | /forward-curve/{id} | Solid blue, 2px | forward_curve array |
| Raw Decay Curve | /forward-curve/{id}?raw=true | Dashed gray, 1px | raw_forward_curve array |
| Historical Pattern | /sources/raw/historical_pattern/{id} | Dotted orange, 1px | prediction.predicted_price as horizontal line at target |
| ML Forecast | /sources/raw/ml_forecast/{id} | Dotted green, 1px | prediction.predicted_price as horizontal line |
| Confidence Band | /forward-curve/{id} | Light blue fill between lower_bound and upper_bound | forward_curve[].lower_bound, upper_bound |
| Actual History | /charts/contract-data?detail_id={id} | Solid black, 1px | Historical scan prices (past data) |

**Annotations on the chart:**
- Turning points from /path-forecast/{id}: MIN points as green triangles ▲, MAX points as red triangles ▼
- Best buy point: green dashed horizontal line at best_buy_price
- Best sell point: red dashed horizontal line at best_sell_price
- Events from /events: vertical shaded bands on event date ranges (label on top)

**X-axis:** Date (from today to check-in)
**Y-axis:** Price ($)
**Hover:** Show all line values at the hovered date

#### Section 2: Enrichment Decomposition (60% width, below chart)

A **stacked bar chart** (Chart.js) showing daily enrichment impact:

For each day on the forward curve, show a stacked bar with:
- event_adj_pct (red)
- season_adj_pct (orange)
- demand_adj_pct (blue)
- momentum_adj_pct (purple)
- weather_adj_pct (cyan)
- competitor_adj_pct (green)

Data source: /forward-curve/{id} → forward_curve[].event_adj_pct, season_adj_pct, etc.

This lets the trader see: "On April 15, the price bump is 70% events + 20% seasonality + 10% demand"

X-axis synced with the price chart above.

#### Section 3: Side Panel (40% width, right side)

**3A: Signal Summary Box (top of side panel)**
From /options/detail/{id} and /path-forecast/{id}:
```
Signal: CALL (High) ← recommendation + confidence
Current: $245 | Predicted: $270 (+10.2%)
Min: $228 @ T=45 (Apr 5) ← path_min_price, path_min_t
Max: $270 @ T=15 (May 5) ← path_max_price, path_max_t
Reversals: 3 ← path_num_reversals
Best Trade: +18.4% ← path_best_trade_pct
Regime: TRENDING | Momentum: ACCELERATING_UP
```

Color the signal badge: CALL=green, PUT=red, NONE=gray

**3B: Source Consensus Panel (middle of side panel)**
From /sources/compare/{id}:

For each source, one row:
```
[Forward Curve]  CALL  ✓  conf: 72%  ($268)
[Historical]     CALL  ✓  conf: 65%  ($275)
[ML Forecast]    PUT   ✗  conf: 55%  ($238)
[AI Search]      CALL  ✓  conf: —    ($262)
─────────────────────────────────────────────
Consensus: CALL (75%) | Ensemble: CALL ← AGREES
```

If source_disagreement is true, show a RED warning banner:
"⚠ SOURCES DISAGREE — verify before trading"

**3C: Accuracy & Context (bottom of side panel)**
From /accuracy/summary and /accuracy/by-t-bucket:
```
Accuracy at this T-range:
  Direction: 68% correct
  Within 5%: 45% of predictions
  MAPE: 7.2%

Data Quality: HIGH (15+ observations)
Last Scan: 2 hours ago
```

### Options List (Below Terminal)

A table of ALL options for the selected hotel, with click-to-load into the terminal:

Columns: detail_id | Category | Board | Check-in | T | Price | Signal | Conf | Path Min→Max | Best Trade% | Source Consensus | ⚠

From /options?hotel_id=X — already includes the 8 path+source fields.

Click a row → loads that option into the terminal above.

Sort by: Signal, Best Trade%, Disagreement flag.

## Styling

- Dark background (#1a1a2e) with light text (#eee) — trading terminal aesthetic
- Chart.js dark theme (gridLines gray, text white)
- Signal badges: CALL=#00c853, PUT=#ff1744, NONE=#757575
- Turning point MIN=#00e676, MAX=#ff5252
- Confidence band: rgba(33,150,243,0.15)
- Font: monospace for numbers, sans-serif for labels
- Responsive: stack vertically on mobile (chart full width, then panel below)

## Key Implementation Rules

1. **Single file**: terminal_page.py generates complete HTML with embedded JS/CSS
2. **No new analytics**: consume ONLY existing API endpoints listed above
3. **Async loading**: HTML shell first, then fetch all data for selected option
4. **Chart.js only**: no Plotly, no D3, no external libs beyond Chart.js CDN
5. **Dark theme**: this is a trading terminal, not a report
6. **Hebrew support**: all text labels should work RTL (use dir="auto")
7. **Error handling**: graceful degradation if any API returns 404/503
8. **Performance**: lazy-load option details only on click, don't pre-fetch all

## Route Registration

In dashboard_router.py, add:
```python
@dashboard_router.get("/dashboard/terminal", response_class=HTMLResponse)
async def dashboard_terminal(request: Request):
    from src.analytics.terminal_page import generate_terminal_html
    return HTMLResponse(content=generate_terminal_html())
```

## Test

After building, verify:
1. `python3 -m py_compile src/analytics/terminal_page.py`
2. The HTML loads at /dashboard/terminal
3. Hotel dropdown populates from /options
4. Selecting an option loads all charts
5. All 6 lines render on the price chart
6. Enrichment stacked bar shows below
7. Side panel shows signal + sources + accuracy
8. Options table is clickable
9. Disagreement warning appears when sources conflict
