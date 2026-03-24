# Medici Price Prediction — Session Primer

## Current State (2026-03-24)

### Production
- **Azure B2**, Always On, 23 hotels, 4,050+ rooms
- **Deploy zip:** 220 files
- **Tests:** 859 unit + integration, all passing

### Session 2026-03-24 — v2.6.0 Release

#### 1. MCP medici-db Fix
- Fixed JS server credentials: `prediction_readonly` → `prediction_reader` with correct password
- Both JS and Python MCP servers now use same `prediction_reader` user

#### 2. Voter Data Enrichment — Events + Peers Connected
- **Events voter** now receives real MIAMI_MAJOR_EVENTS data, classified by checkin date:
  - "upcoming" if checkin during event or within 3 days of event end
  - "past" if checkin 1-7 days after event
- **Peers voter** now receives real peer price directions (up/down) from same zone+tier predictions
- Wired in both `options_engine.py` (signal computation) and `analytics_router.py` (API endpoint)
- 7 new unit tests

#### 3. FRED Collector — Proper BaseCollector
- Added `FREDCollector(BaseCollector)` class with registry auto-discovery
- SQLite persistence to `data/fred_data.db`
- Fetches 5 FRED series (Hotel PPI, Luxury PPI, Employment, Lodging CPI, FL Hospitality Jobs)
- Graceful fallback when `FRED_API_KEY` not set
- 3 new unit tests

#### 4. Active Rooms Selector — MED_Book Prediction
- Added `load_med_book_for_prediction()` to `trading_db.py`
  - Filters: IsActive=1, IsSold=0, DateFrom >= today
  - Schema maps to SalesOffice format (detail_id prefixed `MB_`)
- Added `collect_med_book_predictions()` to `collector.py`
- 3 new unit tests

#### 5. Command Center Polish
- **Term Structure chart tab** — scatter plot of all hotel rooms at their T/price, selected room highlighted
- **Source Breakdown bar chart** — horizontal bars showing CALL/PUT/NEUTRAL per source
- **Category headers** in consensus panel (Leading/Coincident/Lagging)
- All charts use Chart.js, match dark theme, destroy old instances on refresh

### Previous Sessions (2026-03-20 — 2026-03-21)

#### Core Fixes
1. Collector fix — `d.IsDeleted = 0` filter (6,089 → ~4,050)
2. sources/compare perf — removed blocking signal compute
3. Signals cache — precomputed non-blocking

#### Analytics Engines
4. Path Forecast, Raw Source Analyzer, Source Attribution, Group Actions

#### Execution System
5. Override Queue (38 tests), Opportunity Queue (40 tests), Skills imported

#### Dashboards
6. Trading Terminal, Path Forecast, Source Comparison, Override/Opportunity Queues

### Next Session — Planned
- **Deploy v2.6.0** to Azure and verify in production
- **FRED API key** — get key from https://fred.stlouisfed.org and set in Azure App Service
- **MED_Book integration** — wire `collect_med_book_predictions()` into main collection cycle
- **Voter calibration** — tune thresholds after observing real events/peers data
- **Active Rooms dashboard** — UI panel for MED_Book inventory analysis

### Production URLs
- Command Center: `/api/v1/salesoffice/dashboard/command-center`
- Trading Terminal: `/api/v1/salesoffice/dashboard/terminal`
- Options board: `/api/v1/salesoffice/options/view`
- Override Queue: `/api/v1/salesoffice/dashboard/override-queue`
- Opportunity Queue: `/api/v1/salesoffice/dashboard/opportunity-queue`
