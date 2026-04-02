# Trading Chart with Indicators — Design Spec

**Date:** 2026-04-02
**Status:** Draft
**Goal:** TradingView-style multi-indicator chart for hotel room pricing decisions (BUY/SELL)

---

## Concept

Each hotel room is a financial instrument. Each data source is an **indicator** with its own line on the chart. The user toggles indicators on/off and sees BUY (CALL) / SELL (PUT) signals where multiple indicators agree.

## New Endpoint

`/dashboard/trading-chart` — standalone HTML page, does NOT modify any existing dashboard.

## Data Flow

```
API endpoints (new)          →  Frontend chart (Lightweight Charts / Chart.js)
/api/v1/salesoffice/chart/indicators/{option_id}  →  Returns all indicator time series
/api/v1/salesoffice/chart/signals/{option_id}     →  Returns BUY/SELL signal points
```

---

## Indicators (19 total)

### Group A: Price (from DB + SQLite)

| # | Indicator | Source | Y Axis | Update Freq |
|---|-----------|--------|--------|-------------|
| 1 | **Price Scan** | SalesOffice.Details | $ | 3h |
| 2 | **Forward Curve** | Bayesian prediction | $ | 3h |
| 3 | **Historical T-Pattern** | price_scans.db | $ | daily |
| 4 | **YoY Price** | price_scans.db | $ | daily |
| 5 | **Prophet Forecast** | Prophet model (NEW) | $ | daily |

### Group B: Demand (from DB)

| # | Indicator | Source | Y Axis | Update Freq |
|---|-----------|--------|--------|-------------|
| 6 | **Booking Velocity** | MED_Book / MED_PreBook | bookings/day | daily |
| 7 | **Cancellation Rate** | MED_CancelBook | % | daily |
| 8 | **Price Velocity** | RoomPriceUpdateLog | changes/day | daily |
| 9 | **BTS Flights** | Bureau of Transportation (NEW) | passengers/mo | monthly |

### Group C: Supply & Competition (from DB + Browser)

| # | Indicator | Source | Y Axis | Update Freq |
|---|-----------|--------|--------|-------------|
| 10 | **Provider Count** | SalesOffice.Details | count | 3h |
| 11 | **Competitor Avg Price** | AI_Search_HotelData | $ | daily |
| 12 | **Browser Rank** | BrowserScanResults | rank (1-30) | 8h |
| 13 | **Airbnb Avg** | Inside Airbnb (NEW) | $ | monthly |

### Group D: Macro (from APIs — NEW)

| # | Indicator | Source | Y Axis | Update Freq |
|---|-----------|--------|--------|-------------|
| 14 | **JETS ETF** | yfinance (NEW) | $ | daily |
| 15 | **VIX Index** | yfinance (NEW) | index | daily |
| 16 | **Hotel REITs Avg** | yfinance (PK,HST,RLJ,APLE) (NEW) | $ | daily |
| 17 | **Hotel PPI** | FRED (existing) | index | monthly |

### Group E: Environment (existing enrichments)

| # | Indicator | Source | Y Axis | Update Freq |
|---|-----------|--------|--------|-------------|
| 18 | **Events** | events_collector | impact % | daily |
| 19 | **Seasonality** | seasonality index | multiplier | daily |

---

## Chart UI

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ [Hotel Selector ▼]  [Date Range]  [Overlay | Separate]      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Main Panel: Price + overlays                          [$]   │
│  ── Price Scan line (white)                                  │
│  ── Forward Curve (cyan dashed)                              │
│  ── Prophet (magenta dashed)                                 │
│  ── Historical T (yellow)                                    │
│  ── YoY (gray)                                               │
│  ── BUY arrows (green ▲) / SELL arrows (red ▼)              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Panel 2: Demand indicators                                  │
│  ── Booking Velocity (green) / Cancellations (red)           │
│  ── Price Velocity (orange) / BTS Flights (purple)           │
├──────────────────────────────────────────────────────────────┤
│  Panel 3: Macro indicators                                   │
│  ── JETS (green) / VIX (red) / REITs (blue) / PPI (gray)    │
├──────────────────────────────────────────────────────────────┤
│  Panel 4: Supply                                             │
│  ── Provider Count / Competitor Avg / Browser Rank / Airbnb  │
├──────────────────────────────────────────────────────────────┤
│  Panel 5: Consensus Signal Bar                               │
│  ██████████████░░░░░░  72% BUY  (13/18 indicators agree)    │
└──────────────────────────────────────────────────────────────┘
```

### Toggle Bar (top)

```
Price:    ☑ Scan  ☑ FC  ☐ Prophet  ☐ Historical  ☐ YoY
Demand:   ☑ Bookings  ☐ Cancels  ☐ PriceVel  ☐ Flights
Macro:    ☐ JETS  ☐ VIX  ☐ REITs  ☐ PPI
Supply:   ☐ Providers  ☐ Competitors  ☐ BrowserRank  ☐ Airbnb
Env:      ☐ Events  ☐ Seasonality
```

- Click toggle → show/hide line on chart (no refresh)
- Each indicator has unique color + optional right Y axis
- Hover crosshair synced across all panels
- Dark theme (Bloomberg style, matching Terminal V2)

### Display Modes

1. **Overlay** — all active indicators on one panel with dual Y axes
2. **Separate** — each indicator group gets its own panel (default)
3. **Single** — click one indicator to see it full-size

### BUY/SELL Signal Logic

Each indicator votes BUY or SELL based on its own logic:

| Indicator | BUY (CALL) when | SELL (PUT) when |
|-----------|----------------|-----------------|
| Price Scan | price dropping (below FC) | price rising (above FC) |
| Forward Curve | FC > current price | FC < current price |
| Prophet | forecast > current | forecast < current |
| Historical T | historical rose at this T | historical fell at this T |
| Booking Velocity | accelerating | decelerating |
| Cancellation Rate | low / decreasing | high / increasing |
| Price Velocity | slowing down | accelerating up |
| Provider Count | decreasing (less supply) | increasing (more supply) |
| Competitor Avg | competitors expensive | competitors cheap |
| Browser Rank | Knowaa is #1 | Knowaa not listed |
| JETS ETF | rising (travel demand up) | falling |
| VIX | falling (stability) | rising (uncertainty) |
| Hotel REITs | rising | falling |
| Airbnb Avg | Airbnb expensive (hotel cheaper) | Airbnb cheap |
| BTS Flights | passengers increasing | passengers decreasing |
| Events | major event coming | no events |
| Seasonality | peak season | off season |
| Hotel PPI | PPI rising (industry up) | PPI falling |

**Signal arrow** appears on chart when ≥66% of active indicators agree (same threshold as consensus engine).

---

## Backend: New API Endpoints

### `GET /chart/indicators/{option_id}`

Returns time series for all indicators for a specific option.

```json
{
  "option_id": "...",
  "hotel": "Cavalier Hotel",
  "check_in": "2026-04-20",
  "current_price": 100.04,
  "indicators": {
    "price_scan": {
      "label": "Price Scan",
      "group": "price",
      "color": "#FFFFFF",
      "unit": "$",
      "data": [{"t": "2026-03-01", "v": 95.0}, {"t": "2026-03-02", "v": 96.5}, ...]
    },
    "forward_curve": {
      "label": "Forward Curve",
      "group": "price",
      "color": "#00E5FF",
      "unit": "$",
      "data": [...]
    },
    "jets_etf": {
      "label": "JETS ETF",
      "group": "macro",
      "color": "#4CAF50",
      "unit": "$",
      "data": [...]
    },
    ...
  }
}
```

### `GET /chart/signals/{option_id}`

Returns BUY/SELL signal points for the chart.

```json
{
  "signals": [
    {"t": "2026-03-15", "type": "BUY", "confidence": 0.78, "agreeing": 14, "total": 18},
    {"t": "2026-03-20", "type": "SELL", "confidence": 0.66, "agreeing": 12, "total": 18}
  ]
}
```

---

## New Collectors (additive only)

### `src/collectors/yfinance_collector.py`
- Extends `BaseCollector`
- Pulls: JETS, PK, HST, RLJ, APLE, ^VIX
- Caches in SQLite `macro_indicators` table
- `COLLECTOR_YFINANCE_ENABLED=true`
- Dependency: `yfinance` pip package

### `src/collectors/airbnb_collector.py`
- Extends `BaseCollector`
- Downloads monthly CSV from Inside Airbnb (Miami Beach)
- Caches in SQLite `airbnb_prices` table
- `COLLECTOR_AIRBNB_ENABLED=true`
- No API key needed — public CSV

### `src/collectors/bts_collector.py`
- Extends `BaseCollector`
- Downloads monthly passenger data for MIA airport
- Caches in SQLite `bts_flights` table
- `COLLECTOR_BTS_ENABLED=true`
- No API key needed — public data

### `src/analytics/prophet_voter.py`
- New consensus voter (#12)
- Trains on price_scans.db history per hotel
- Returns CALL/PUT/NEUTRAL + confidence
- Falls back to NEUTRAL if insufficient data (<30 points)
- Dependency: `prophet` pip package

---

## What Does NOT Change

- Forward Curve code — untouched
- Ensemble weights — 55/25/20 stays
- Existing enrichments — all 9 stay
- Existing 11 voters — untouched, Prophet is #12
- Existing dashboards — no modifications
- Existing API endpoints — no modifications
- Terminal V2 — untouched

---

## Implementation Order

1. **yfinance collector** — fastest, 1 file
2. **Airbnb collector** — CSV download, 1 file
3. **BTS collector** — CSV download, 1 file
4. **Chart API endpoints** — 2 endpoints in new `chart_router.py`
5. **Chart HTML page** — `trading_chart.html` template
6. **Prophet voter** — last (needs `prophet` install + training logic)

---

## Dependencies to Add

```
yfinance>=0.2.0
prophet>=1.1.0
```
