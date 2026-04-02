# Trading Chart with Indicators — Design Spec

**Date:** 2026-04-02
**Status:** Approved
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

## Indicators (20 total)

### Group A: Price (from DB + SQLite)

| # | Indicator | Source | Y Axis | Update Freq | Type |
|---|-----------|--------|--------|-------------|------|
| 1 | **Price Scan** | SalesOffice.Details | $ | 3h | Coincident |
| 2 | **Forward Curve** | Bayesian prediction | $ | 3h | Leading |
| 3 | **Historical T-Pattern** | price_scans.db | $ | daily | Lagging |
| 4 | **YoY Price** | price_scans.db | $ | daily | Lagging |
| 5 | **Prophet Forecast** | Prophet model (NEW) | $ | daily | Leading |

### Group B: Demand (from DB)

| # | Indicator | Source | Y Axis | Update Freq | Type |
|---|-----------|--------|--------|-------------|------|
| 6 | **Booking Velocity** | MED_Book / MED_PreBook | bookings/day | daily | Leading |
| 7 | **Cancellation Rate** | MED_CancelBook | % | daily | Lagging |
| 8 | **Price Velocity** | RoomPriceUpdateLog | changes/day | daily | Coincident |
| 9 | **BTS Flights** | Bureau of Transportation (NEW) | passengers/mo | monthly | Leading |

### Group C: Supply & Competition (from DB + Browser)

| # | Indicator | Source | Y Axis | Update Freq | Type |
|---|-----------|--------|--------|-------------|------|
| 10 | **Provider Count** | SalesOffice.Details | count | 3h | Coincident |
| 11 | **Competitor Avg Price** | AI_Search_HotelData | $ | daily | Coincident |
| 12 | **Browser Rank** | BrowserScanResults | rank (1-30) | 8h | Coincident |
| 13 | **Airbnb Avg** | Inside Airbnb (NEW) | $ | monthly | Coincident |

### Group D: Macro (from APIs — NEW)

| # | Indicator | Source | Y Axis | Update Freq | Type |
|---|-----------|--------|--------|-------------|------|
| 14 | **JETS ETF** | yfinance (NEW) | $ | daily | Leading |
| 15 | **VIX Index** | yfinance (NEW) | index | daily | Leading |
| 16 | **Hotel REITs Avg** | yfinance (PK,HST,RLJ,APLE) (NEW) | $ | daily | Leading |
| 17 | **Hotel PPI** | FRED (existing) | index | monthly | Lagging |

### Group E: Environment (existing enrichments)

| # | Indicator | Source | Y Axis | Update Freq | Type |
|---|-----------|--------|--------|-------------|------|
| 18 | **Events** | events_collector | impact % | daily | Leading |
| 19 | **Seasonality** | seasonality index | multiplier | daily | Leading |

### Group F: Profitability

| # | Indicator | Source | Y Axis | Update Freq | Type |
|---|-----------|--------|--------|-------------|------|
| 20 | **Margin %** | buy price vs sell price | % | 3h | Coincident |

---

## Design Decisions (from review)

### 1. Monthly Indicator Interpolation

Indicators with monthly updates (BTS Flights, Airbnb, Hotel PPI) display as:
- **Interpolated line** between known monthly points (linear)
- **Dashed style** to indicate extrapolated values
- Tooltip shows "Extrapolated from [month] data"

### 2. Correlation Groups — Anti Double-Counting

Correlated indicators share ONE vote in consensus, not separate votes:

| Correlation Group | Indicators | Votes as |
|-------------------|-----------|----------|
| Travel Demand Macro | JETS ETF + Hotel REITs | 1 vote (avg direction) |
| Demand Volume | Booking Velocity + BTS Flights | 1 vote (avg direction) |
| Price Prediction | Forward Curve + Prophet | 1 vote (avg direction) |

**Result:** 20 indicators → **15 independent votes** in consensus.

### 3. Indicator Weights by Type

| Type | Weight | Rationale |
|------|--------|-----------|
| Leading | **1.5x** | Predicts what will happen — most valuable |
| Coincident | **1.0x** | Current state — baseline |
| Lagging | **0.5x** | Confirms what already happened — least valuable |

### 4. T-Aware Indicator Relevance

Indicators auto-dim (lower weight → 0) as T decreases:

| T Range | Active Indicators |
|---------|-------------------|
| T > 60 | All 20 — macro, monthly, everything relevant |
| T 30-60 | Disable BTS Flights, Airbnb (too slow to matter) |
| T 14-30 | Disable JETS, VIX, REITs, PPI (macro too distant) |
| T 7-14 | Only: Price, FC, Prophet, Bookings, Cancels, Providers, Competitors, Browser Rank, Margin |
| T < 7 | Only: Price, Bookings, Competitors, Browser Rank, Margin (execution mode) |

UI shows dimmed toggles for irrelevant indicators at current T.

### 5. Margin Indicator (#20)

```
Margin % = (sell_price - buy_price) / buy_price × 100
```

- **Green zone:** margin > 30% → HOLD or SELL signal
- **Yellow zone:** margin 10-30% → neutral
- **Red zone:** margin < 10% → avoid buying / consider PUT
- Source: SalesOffice.Details (sell) vs last purchase price

---

## Chart UI

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ [Hotel ▼] [Room ▼] [Date Range] [Overlay|Separate] T=47d    │
├──────────────────────────────────────────────────────────────┤
│ Toggle Bar:                                                  │
│ Price: ☑Scan ☑FC ☐Prophet ☐Historical ☐YoY                  │
│ Demand: ☑Bookings ☐Cancels ☐PriceVel ☐Flights               │
│ Macro: ☐JETS ☐VIX ☐REITs ☐PPI                               │
│ Supply: ☐Providers ☐Competitors ☐BrowserRank ☐Airbnb         │
│ Env: ☐Events ☐Seasonality  Profit: ☐Margin                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Main Panel: Price + overlays                          [$]   │
│  ── Price Scan line (white, solid)                           │
│  ── Forward Curve (cyan, dashed)                             │
│  ── Prophet (magenta, dashed)                                │
│  ── Historical T (yellow, dotted)                            │
│  ── YoY (gray, dotted)                                       │
│  ── ▲ BUY arrows (green) / ▼ SELL arrows (red)              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Panel 2: Demand                                             │
│  ── Booking Velocity (green) / Cancellations (red)           │
│  ── Price Velocity (orange) / BTS Flights (purple, dashed)   │
├──────────────────────────────────────────────────────────────┤
│  Panel 3: Macro                                              │
│  ── JETS (green) / VIX (red) / REITs (blue) / PPI (gray)    │
├──────────────────────────────────────────────────────────────┤
│  Panel 4: Supply                                             │
│  ── Providers / Competitor Avg / Browser Rank / Airbnb       │
├──────────────────────────────────────────────────────────────┤
│  Panel 5: Margin                                             │
│  ── Margin % line with green/yellow/red background zones     │
├──────────────────────────────────────────────────────────────┤
│  Panel 6: Consensus Signal Bar                               │
│  ██████████████░░░░░░  72% BUY  (11/15 votes agree)         │
│  Leading: 5/6 BUY | Coincident: 4/6 BUY | Lagging: 2/3 BUY │
└──────────────────────────────────────────────────────────────┘
```

### Display Modes

1. **Overlay** — all active indicators on one panel with dual Y axes
2. **Separate** — each indicator group gets its own panel (default)
3. **Single** — click one indicator to see it full-size

### Interactions

- **Toggle** — click to show/hide indicator line (no refresh)
- **Crosshair** — synced across all panels on hover
- **Click signal arrow** — popup with breakdown of which indicators voted BUY/SELL
- **Dimmed toggles** — indicators irrelevant at current T shown as grayed out
- **Dark theme** — Bloomberg style, matching Terminal V2

---

## BUY/SELL Signal Logic

### Per-Indicator Voting

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
| Browser Rank | Knowaa #1-3 | Knowaa not listed |
| JETS ETF | 5-day trend rising | 5-day trend falling |
| VIX | falling (stability) | rising (uncertainty) |
| Hotel REITs | 5-day trend rising | 5-day trend falling |
| Airbnb Avg | Airbnb > hotel price | Airbnb < hotel price |
| BTS Flights | MoM passengers increasing | MoM passengers decreasing |
| Events | major event within 14d | no events 30d |
| Seasonality | season index > 1.0 | season index < 1.0 |
| Hotel PPI | PPI MoM rising | PPI MoM falling |
| Margin % | margin < 15% (cheap to buy) | margin > 40% (expensive) |

### Consensus Calculation

1. Apply correlation grouping → 15 independent votes
2. Apply type weights (Leading 1.5x, Coincident 1.0x, Lagging 0.5x)
3. Apply T-aware filtering (disable irrelevant indicators)
4. Weighted vote: `score = sum(weight × direction) / sum(weights)`
5. **BUY signal** when score ≥ 0.66 (66%)
6. **SELL signal** when score ≤ 0.34 (34%)
7. **NEUTRAL** otherwise

---

## Backend: New Files

### New Collectors

#### `src/collectors/yfinance_collector.py`
- Extends `BaseCollector`, name = "yfinance"
- Pulls daily: JETS, PK, HST, RLJ, APLE, ^VIX
- Caches in SQLite `macro_indicators` table
- `COLLECTOR_YFINANCE_ENABLED=true`

#### `src/collectors/airbnb_collector.py`
- Extends `BaseCollector`, name = "airbnb"
- Downloads monthly CSV from Inside Airbnb (Miami Beach)
- URL: `http://data.insideairbnb.com/united-states/fl/miami/`
- Caches in SQLite `airbnb_prices` table
- `COLLECTOR_AIRBNB_ENABLED=true`

#### `src/collectors/bts_collector.py`
- Extends `BaseCollector`, name = "bts"
- Downloads monthly passenger data for MIA airport
- Caches in SQLite `bts_flights` table
- `COLLECTOR_BTS_ENABLED=true`

### New Analytics

#### `src/analytics/prophet_voter.py`
- Consensus voter #12
- Trains on price_scans.db per hotel×category
- Returns CALL/PUT/NEUTRAL + confidence
- Falls back to NEUTRAL if < 30 data points

#### `src/analytics/chart_indicators.py`
- Aggregates all 20 indicators into time series format
- Handles interpolation for monthly data
- Applies correlation grouping + T-aware filtering
- Computes per-point BUY/SELL signals

### New Router

#### `src/api/routers/chart_router.py`
- `GET /chart/indicators/{option_id}` — all indicator time series
- `GET /chart/signals/{option_id}` — BUY/SELL signal points
- `GET /dashboard/trading-chart` — HTML page

### New Template

#### `src/templates/trading_chart.html`
- Lightweight Charts (TradingView open source) or Chart.js
- Multi-panel layout with toggle bar
- Dark Bloomberg theme
- Synced crosshair, signal arrows, consensus bar

---

## API Response Format

### `GET /chart/indicators/{option_id}`

```json
{
  "option_id": "...",
  "hotel": "Cavalier Hotel",
  "check_in": "2026-04-20",
  "T": 18,
  "current_price": 100.04,
  "indicators": {
    "price_scan": {
      "label": "Price Scan",
      "group": "price",
      "color": "#FFFFFF",
      "style": "solid",
      "unit": "$",
      "type": "coincident",
      "weight": 1.0,
      "active_at_T": true,
      "vote": "BUY",
      "data": [{"t": "2026-03-01", "v": 95.0}, {"t": "2026-03-02", "v": 96.5}]
    },
    "jets_etf": {
      "label": "JETS ETF",
      "group": "macro",
      "color": "#4CAF50",
      "style": "solid",
      "unit": "$",
      "type": "leading",
      "weight": 1.5,
      "correlation_group": "travel_demand_macro",
      "active_at_T": false,
      "vote": "BUY",
      "data": [{"t": "2026-03-01", "v": 21.5}]
    }
  },
  "consensus": {
    "votes_buy": 11,
    "votes_sell": 4,
    "total_votes": 15,
    "score": 0.73,
    "signal": "BUY",
    "breakdown": {
      "leading": {"buy": 5, "sell": 1, "total": 6},
      "coincident": {"buy": 4, "sell": 2, "total": 6},
      "lagging": {"buy": 2, "sell": 1, "total": 3}
    }
  }
}
```

---

## What Does NOT Change

- Forward Curve code — untouched
- Ensemble weights — 55/25/20 stays
- Existing enrichments — all 9 stay
- Existing 11 consensus voters — untouched, Prophet is #12
- Existing dashboards — no modifications
- Existing API endpoints — no modifications
- Terminal V2 — untouched

---

## Implementation Plan

### Phase A: New Collectors (3 files)
1. `src/collectors/yfinance_collector.py` — JETS, VIX, REITs
2. `src/collectors/airbnb_collector.py` — Miami Beach CSV
3. `src/collectors/bts_collector.py` — MIA airport passengers

### Phase B: Chart Backend (2 files)
4. `src/analytics/chart_indicators.py` — aggregator + signal logic
5. `src/api/routers/chart_router.py` — 3 endpoints

### Phase C: Chart Frontend (1 file)
6. `src/templates/trading_chart.html` — full TradingView-style UI

### Phase D: Prophet Voter (1 file)
7. `src/analytics/prophet_voter.py` — consensus voter #12

### Phase E: Tests
8. Unit tests for collectors + chart_indicators + chart_router

---

## Dependencies to Add

```
yfinance>=0.2.0
prophet>=1.1.0
```
