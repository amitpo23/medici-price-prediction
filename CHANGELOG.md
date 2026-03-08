# Changelog

All notable changes to the Medici Price Prediction system.

## [1.1.0] - 2026-03-08 - Inline Trading Charts & Lazy Detail Loading

### Added — Inline Trading Chart Panel
- **Expand button (▼)** in the ID column of every row in the options HTML dashboard
- **Trading chart per room**: Click ▼ to expand a detail panel below each row showing:
  - Forward Curve line (blue) with confidence band (light blue fill)
  - Adjusted Forward Curve line (orange) when enrichment adjustments differ
  - Actual scan price dots (green = rise, red = drop) overlaid on the same timeline
  - Current price (dashed blue) and predicted price (dashed green) horizontal lines
  - Min/Max price markers with labels
  - Unified date X-axis (MM-DD format) merging FC dates and scan dates
- **Detail info panel** next to each chart with:
  - Signal weights breakdown (Forward Curve %, Historical %, ML %)
  - FC adjustment totals (competitor, cancel, provider, demand, season, velocity)
  - Key metrics: current price, predicted price, change %, min/max expected
  - Momentum indicators (signal, strength, velocity)
  - Regime status (regime type, Z-score, alert level)
- **`drawTradingChart()`**: ~150 lines of Canvas rendering (FC line, confidence band, scan dots, price lines, markers, axis labels)
- **`buildDetailInfo()`**: ~60 lines of HTML info panel builder with signal/momentum/regime breakdown

### Added — Lazy AJAX Detail Loading
- **New endpoint `GET /options/detail/{detail_id}`**: Returns compact JSON for a single room's trading data
  - `fc[]` — Forward curve series (date, price, lower, upper)
  - `scan[]` — Scan history series (date, price)
  - `adj{}` — FC adjustment totals per enrichment source
  - `mom{}` — Momentum data (signal, strength, velocity)
  - `reg{}` — Regime data (type, Z-score, alert)
  - `fcW, fcC, fcP, hiW, hiC, hiP` — Signal weights and confidences
  - `cp, pp, mn, mx, sig, chg` — Current/predicted price, min/max, signal, change%
  - `drops, rises, scans` — Count of price drops, rises, total scans
- **`toggleDetail()` JS** fetches data on-demand via `fetch()` API on first expand
- **Loading indicator** ("Loading...") shown while data loads; error display on failure

### Performance
- **Page size reduced 51%**: 31 MB → 16 MB by removing 2,917 inline `<script>` blocks with base64-encoded JSON data
- Each detail fetch is ~5 KB, loaded only when user clicks expand
- Detail rows remain in DOM as lightweight shells (no embedded data)

### Fixed
- **Scan date format**: Changed from HH:MM to MM-DD to align with FC date axis
- **Duplicate same-day scans**: Handled with `#N` suffix for unique labels (stripped from X-axis display)
- **JSON escaping**: Resolved special character issues in embedded data (moved to server-side API)

### Technical
- `analytics_dashboard.py`: +484 lines (now 4,293 lines total)
- CSS: ~75 lines for detail panel (`.detail-row`, `.detail-content`, `.chart-wrapper`, `.chart-legend`, `.detail-info`)
- HTML: Hidden `<tr class="detail-row">` after each data row with `<canvas>` + info wrapper
- Row dict enriched with `fc_series`, `fc_adj_series`, `momentum`, `regime`, `yoy` fields
- Detail endpoint accesses `_get_or_run_analysis()` predictions cache

### Files Changed
- `src/api/analytics_dashboard.py` — New endpoint, CSS, JS (drawTradingChart, buildDetailInfo, toggleDetail), detail row HTML

---

## [1.0.0] - 2026-03-08 - AI Intelligence, Claude Analyst & Rules Engine

### Added — AI Intelligence Module (`ai_intelligence.py`, 959 lines)
- **Anomaly Detection**: Z-score based outlier detection across price, change%, and scan history
- **Signal Synthesis**: Multi-source signal aggregation (forward curve, historical, ML, momentum, regime)
- **Risk Assessment**: Bayesian risk scoring with composite risk levels (LOW/MEDIUM/HIGH/EXTREME)
- **Bayesian Confidence**: Prior-posterior confidence updates using prediction accuracy data
- **Market Narrative**: Auto-generated textual description of market conditions per room
- **Rule-Based Fallback**: Full functionality without API key — all AI features work offline

### Added — Claude Analyst Module (`claude_analyst.py`, 1033 lines)
- **Interactive Q&A** (`/ai/ask`): Natural language queries about portfolio, hotels, signals, events
  - Smart keyword routing: summary, risk/PUT, opportunities/CALL, hotel search, events, momentum, regime
  - Optional `detail_id` for room-specific questions, `deep=true` for Sonnet-powered analysis
  - Bilingual support (English/Hebrew)
- **Executive Market Brief** (`/ai/brief`): Auto-generated market summary with 5 sections
  - Market Pulse, Top Opportunities, Risk Alerts, Event Impact, Action Items
  - Language parameter: `lang=en` or `lang=he`
- **Deep Prediction Explainer** (`/ai/explain/{detail_id}`): Signal-by-signal breakdown
  - Forward Curve weight/confidence, Historical Pattern analysis, scan history, momentum, regime
  - AI risk assessment and anomaly flags when available
- **Smart Metadata Enrichment** (`/ai/metadata`): Per-room intelligent tagging
  - Tags: `hot_deal`, `watch`, `risky`, `stable`, `momentum_play`, `contrarian`, `premium_opportunity`
  - Actions: `BUY_NOW`, `WAIT`, `AVOID`, `MONITOR`, `HEDGE`
  - Confidence emoji, key factor identification, one-liner summary
  - Batch mode with configurable limit (default 50)
- **Response Caching**: 200-entry in-memory cache with 10-minute TTL
- **Claude Models**: Haiku for fast queries, Sonnet for deep analysis (configurable via env vars)

### Added — Rules Engine (7 files, ~2,076 lines)
- **Rule Types** (11): price_above, price_below, change_pct_above, change_pct_below, signal_is, hotel_is, category_is, board_is, date_before, date_after, composite (AND/OR)
- **Engine** (`src/rules/engine.py`, 416 lines): Evaluate rules against predictions, composite logic, bulk evaluation
- **Models** (`src/rules/models.py`, 251 lines): Pydantic models for rules, conditions, actions, results
- **Store** (`src/rules/store.py`, 417 lines): CRUD operations with JSON file persistence
- **Auto-Generator** (`src/rules/auto_generator.py`, 259 lines): ML-driven rule suggestions from portfolio data
- **Presets** (`src/rules/presets.py`, 210 lines): Pre-built rule templates (value hunter, risk monitor, etc.)
- **API** (`src/api/rules_api.py`, 509 lines): 16 RESTful endpoints for rule management
  - CRUD: create, read, update, delete, list, toggle
  - Evaluation: evaluate single, evaluate all, bulk evaluate
  - Auto-generation: suggest rules, apply suggestions
  - Presets: list presets, apply preset, get recommendation

### Added — New API Endpoints (20 total)
- `GET /ai/ask` — Natural language Q&A with portfolio data
- `GET /ai/brief` — Executive market brief (EN/HE)
- `GET /ai/explain/{detail_id}` — Deep prediction explanation
- `GET /ai/metadata` — Smart room tags & metadata enrichment
- `GET /options/ai-insights` — AI anomaly/risk/signal analysis per room
- `POST /rules/` — Create alert rule
- `GET /rules/` — List all rules
- `GET /rules/{id}` — Get rule by ID
- `PUT /rules/{id}` — Update rule
- `DELETE /rules/{id}` — Delete rule
- `POST /rules/{id}/toggle` — Enable/disable rule
- `POST /rules/evaluate` — Evaluate single rule
- `POST /rules/evaluate-all` — Evaluate all active rules
- `POST /rules/bulk-evaluate` — Bulk evaluate multiple rules
- `POST /rules/auto-generate` — ML-suggested rules from data
- `POST /rules/apply-suggestions` — Apply auto-generated rules
- `GET /rules/presets` — List preset rule templates
- `POST /rules/presets/{name}/apply` — Apply a preset
- `GET /rules/recommend` — Get rule recommendations for portfolio

### Fixed — Production Stability
- **OOM Crash**: Gunicorn 2 workers → 1 worker (prevented duplicate analysis pipelines exhausting memory)
- **Worker Timeout**: 600s → 900s (allows full 2850-room analysis to complete)
- **AI Enrichment Memory**: `deep_predictor.py` now filters snapshots by `detail_id` and limits to `tail(100)`
- **Fallback Keyword Routing**: "riskiest/worst/decline" correctly routes to PUT signals (not CALL)

### Changed — Configuration
- `startup.sh`: `-w 1 -k uvicorn.workers.UvicornWorker --timeout 900 --graceful-timeout 300`
- `config/settings.py`: Added `ANTHROPIC_API_KEY`, `CLAUDE_AI_MODEL`, `AI_INTELLIGENCE_ENABLED`
- `requirements.txt` / `requirements-deploy.txt`: Added `anthropic>=0.80.0`
- `src/api/main.py`: Registered rules router

### Files Added
- `src/analytics/ai_intelligence.py` — AI intelligence module (959 lines)
- `src/analytics/claude_analyst.py` — Claude analyst module (1,033 lines)
- `src/rules/__init__.py` — Rules package init
- `src/rules/engine.py` — Rules evaluation engine (416 lines)
- `src/rules/models.py` — Pydantic rule models (251 lines)
- `src/rules/store.py` — Rule persistence store (417 lines)
- `src/rules/auto_generator.py` — Auto rule generator (259 lines)
- `src/rules/presets.py` — Pre-built rule presets (210 lines)
- `src/api/rules_api.py` — Rules REST API (509 lines)

### Files Modified
- `src/api/analytics_dashboard.py` — +1,206 lines (AI endpoints, dashboard columns, AI insights)
- `src/analytics/deep_predictor.py` — +75 lines (AI enrichment integration)
- `config/settings.py` — +11 lines (AI configuration)
- `startup.sh` — Worker/timeout tuning
- `src/api/main.py` — Rules router registration
- `requirements.txt` / `requirements-deploy.txt` — Anthropic SDK

---

## [0.9.1] - 2026-03-04 - Forward Curve Enrichment Recalibration & Price Drop Detection

### Fixed — Critical Calculation Bugs (5 bugs)

- **Bug 1 — Enrichment scaling ~100× too small**: All 6 forward curve enrichment adjustments (competitor, cancel, provider, demand, season, velocity) contributed only 0.01–0.02%/day vs a 0.39% base drift — making the curve effectively a straight line. Enrichments never created any dips.
  - `get_competitor_daily_adj()`: `pressure * 0.02` → `pressure * 0.20` (10× increase)
  - `get_cancel_risk_adj()`: `-cancel * 0.015` → `-cancel * 0.25` (17× increase)
  - `get_provider_pressure_adj()`: `provider * 0.015` → `provider * 0.20` (13× increase)
  - `get_demand_daily_adj()`: `±0.02` → `±0.15` %/day (7.5× increase)
  - `get_season_daily_adj()`: `(idx-1.0) * 10/30` → `(idx-1.0) * 3.0` (monthly deviation as daily pct)
  - `get_velocity_daily_adj()`: `velocity * 0.01` → `return 0.0` (non-directional, was incorrectly biasing upward)

- **Bug 2 — `touches_expected_min/max` always returned 1**: Tolerance was $0.01 on $100–$900 prices — only the exact min/max point matched. Changed to 10% of the price range band (min $1).
  - **Before**: `{1: 1219}` (every row = 1)
  - **After**: distributed `{1: 77, 2: 371, 3: 362, 4: 213, 5: 53, 6: 4, 7: 141}`

- **Bug 3 — `count_price_changes_gt_20` always 0**: Was using direction reversals, but the forward curve is monotonic (all adjustments push same way per day). Changed to count "days with price decline" vs "days with price rise", which is what users actually need to see.
  - `count_price_changes_gt_20` → number of days price dropped
  - `count_price_changes_lte_20` → number of days price rose or stayed flat

- **Bug 4 — `put_decline_count` always 0**: Forward curve path never dipped because enrichments were too small (Bug 1). After rescaling, the curve now produces real dips (up to 6 per 7-day window).

- **Bug 5 — No probability-based expected drops**: `p_down` data (e.g., 27.7%) existed but was unused. Added `expected_future_drops` and `expected_future_rises` fields computed from `p_down * horizon`.

### Added — New Fields in Options API

- `expected_future_drops` — probability-based expected price drops over the T-horizon (e.g., `1.2–2.5` for 7 days)
- `expected_future_rises` — probability-based expected price rises over the T-horizon
- `put_decline_events` — array of individual decline events with dates, prices, drop amounts and percentages
- `put_downside_from_now_to_t_min` — dollar amount of expected downside from current price to T-min
- `put_rebound_from_t_min_to_checkin` — dollar rebound from T-min back to predicted check-in price
- Enhanced HTML dashboard (`/options/view`) with probability-based drop display

### Changed — Key Metrics Impact

| Metric | Before | After |
|--------|--------|-------|
| `touches_expected_min` | Always 1 | Distributed 1–7 |
| `touches_expected_max` | Always 1 | Distributed 1–7 |
| `count_price_changes_gt_20` (decline days) | Always 0 | 0–6 |
| `put_decline_count` | Always 0 | 1–6 |
| PUT signals | 29 | 139 |
| `expected_min < current_price` | 0 / 1,219 (0%) | 243 / 1,221 (19.9%) |
| `expected_future_drops` | N/A | 1.2–2.5 per 7 days |

### Technical

- All fixes applied in **both** code paths: JSON API (`/options`) and HTML view (`/options/view`)
- `_build_put_path_insights()` now accepts `probability` parameter for expected drop/rise calculations
- Forward curve enrichment methods in `forward_curve.py` recalibrated based on actual data distributions
- Velocity adjustment disabled (returns 0.0) — it was non-directional but was incorrectly biasing prices upward

### Files Changed
- `src/analytics/forward_curve.py` — 6 enrichment method rescaling
- `src/api/analytics_dashboard.py` — touches band, price change counting, put path insights, new fields

---

## [0.9.0] - 2026-03-04 - Scan History Analytics & Interactive Charts

### Added
- **Scan History from medici-db** — real historical price tracking from `[SalesOffice.Details].DateCreated`:
  - `load_scan_history()` in `collector.py`: queries all 3-hourly scan records from Azure SQL
  - `_build_scan_history()` in `analyzer.py`: matches rooms by `(order_id, hotel_id, room_category, room_board)` natural key
  - Tracks actual drops, rises, trend, total amounts, max single moves since scanning started (Feb 23)
  - Up to 23 scans per room with full price series for charting
- **Interactive Scan Chart Modal** in HTML dashboard (`/options/view`):
  - Chart icon (📈) per row — click to open price history chart
  - Canvas-rendered sparkline with date axis, price gridlines, colored dots (red=drop, green=rise)
  - Summary stats in modal: first/latest price, drops, rises, min, max, total change %
  - Keyboard (Esc) and overlay-click to close
- **Enhanced scan visualization** in dashboard table:
  - Rich "Actual D/R" column with colored drop/rise counters and hover tooltips
  - Trend badge (▲/▼/▬) next to Scan Chg% for quick visual scanning
  - Hover tooltips showing full breakdown (total drop/rise amounts, max single move)
- **`scan_price_series`** added to JSON API `scan_history` object — array of `{date, price}` for client-side charting
- New "Chart" column (col 20) in HTML dashboard — 767+ rows with clickable chart icons

### Fixed
- **Scan history data source** — was reading from local SQLite (1 snapshot on Azure due to `data/` excluded from deploy). Now reads directly from medici-db Azure SQL with full historical data

### Technical
- `SCAN_HISTORY_QUERY` in `collector.py` — efficient SQL against `[SalesOffice.Details]` with active order filter
- Per-scan-date aggregation (min price) to handle duplicate entries
- `scan_history_df` passed through `run_analysis()` → `_predict_prices()` → `_build_scan_history()` pipeline
- HTML dashboard now 22 columns (was 21) — all additive, no existing columns changed

---

## [0.8.1] - 2026-03-03 - Performance & Stability Fixes

### Fixed
- **Critical performance fix**: `_predict_prices()` called weather API per-room (1143 HTTP calls). Refactored to pre-compute shared enrichment data once and cache per hotel_id — **analysis time reduced from 564s to 18s (32x faster)**
- **Event loop blocking**: Changed ~39 `async def` endpoints to `def` across `analytics_dashboard.py`, `main.py`, and `integration.py`. FastAPI now runs these in thread pool, preventing event loop starvation on sync DB/analysis calls
- **Wrong SQL column**: `freshness_engine.py` referenced `DateInsert` on SalesOffice.Details table — corrected to `DateUpdated` per database schema
- **`load_latest_snapshot()` signature bug**: Was called with `hotel_id` argument but function takes no parameters — fixed to load full snapshot then filter by hotel_id
- **DB connection reliability**: Added `connect_timeout=10`, `pool_pre_ping=True`, reduced `pool_timeout` to 15s in `trading_db.py`

### Added
- `_compute_shared_enrichment_data()` helper in `analyzer.py` — single-call weather/events/seasonality/snapshot loader
- Missing dependencies `scipy>=1.11.0` and `statsmodels>=0.14.0` added to `requirements.txt`
- `.gitignore` entries for SQLite databases, deploy artifacts, and report files

### Changed
- `_build_enrichments()` now accepts optional `_shared` parameter for batch optimization
- Enrichments pre-computed per hotel_id (5 hotels) instead of per room (1133 rooms)

---

## [0.8.0] - 2026-02-27 - Algo-Trading Forward Curve Prediction Engine

### Added
- **Forward Curve Engine** (`forward_curve.py`):
  - Empirical decay curve built from historical scan-pair T-observations
  - Overlapping rolling bins with Bayesian shrinkage for sparse data robustness
  - Category/board additive offsets computed from track-level statistics
  - Day-by-day multiplicative curve walk (non-linear, not interpolated)
  - Per-T confidence intervals from historical volatility surface
  - Enrichments integration: events spread across impact window, seasonality as daily adj, demand as daily adj
- **Momentum Indicators** (`momentum.py`):
  - 3-hour scan velocity (latest, 24h avg, 72h avg) normalized to daily rates
  - Acceleration signal (velocity_24h vs velocity_72h)
  - Momentum-vs-expected comparison against decay curve at current T
  - Signal classification: ACCELERATING_UP, ACCELERATING_DOWN, NORMAL, INSUFFICIENT_DATA
  - Strength metric (0-1) based on deviation in volatility units
- **Regime Detection** (`regime.py`):
  - Compares observed price path to expected from decay curve walk
  - Z-score divergence analysis (actual vs expected cumulative change)
  - Regime classification: NORMAL, TRENDING_UP, TRENDING_DOWN, VOLATILE, STALE
  - Alert levels: none, watch, warning
- **Trading Signals Dashboard** section with:
  - Active signals table (momentum divergences sorted by strength)
  - Regime alerts table (rooms off expected path)
  - Decay curve term structure table (T vs expected daily change vs volatility)
  - Category offsets display
- Forward curve charts with **confidence bands** (shaded areas) and starting price markers
- Prediction table now shows **T-countdown**, momentum signal badges, and regime alerts
- New endpoints:
  - `GET /api/v1/salesoffice/forward-curve/{detail_id}` -- full forward curve with momentum + regime
  - `GET /api/v1/salesoffice/decay-curve` -- empirical term structure

### Changed
- Prediction engine completely replaced: 4-bucket linear model -> T-indexed forward curve walk
- Predictions now use per-T daily changes (non-linear) instead of total-change linear interpolation
- Confidence intervals now per-T (from empirical volatility at each T) instead of uniform sqrt widening
- Model info shows observations count and global mean daily pct instead of total avg change

---

## [0.7.0] - 2026-02-27 - Hotel Knowledge Base & Booking Benchmarks

### Added
- **Hotel knowledge base** (`hotel_knowledge.py`):
  - TBO Hotels dataset (Kaggle): 1,816 unique Miami metro hotels
  - Per-hotel competitive profiles: nearby hotels, rating mix, facilities
  - Geo-distance analysis: competitors within 2km radius
  - Amenity detection: pool, fitness, wifi, spa, beach, parking, etc.
  - Sub-market breakdown: South Beach (279), Miami Beach (612), Downtown (953), Fort Lauderdale (765)
- **Our hotels mapped**: Breakwater (303 nearby), citizenM (92), Embassy Suites (22), Hilton Downtown (37)
- **Booking behavior benchmarks** (`booking_benchmarks.py`):
  - Hotel Booking Demand dataset (GitHub mpolinowski): 117,429 bookings
  - Seasonality index: Jan (0.695) to Aug (1.370) — 37% seasonal swing
  - Lead time vs cancellation model: 9.7% (0-7d) to 55.6% (181-365d)
  - City Hotel benchmarks: $107 ADR, 42% cancel rate, 111d avg lead time
  - Market segment ADR: Direct ($115), Online TA ($117), Corporate ($69)
  - Weekend premium: +4.3% vs weekday-only stays
- Predictions now enriched with:
  - Seasonality adjustment (high-season check-in dates get price uplift)
  - Cancellation probability per room (based on lead time benchmarks)
- Dashboard **Market Intelligence** section with competitive position cards
- Dashboard **Booking Benchmarks** section with seasonality chart and lead time table
- New endpoints:
  - `GET /api/v1/salesoffice/knowledge` — full market intelligence JSON
  - `GET /api/v1/salesoffice/knowledge/{hotel_id}` — per-hotel competitive profile
  - `GET /api/v1/salesoffice/benchmarks` — booking behavior benchmarks
- Data sources: 5 active, 9 planned (14 total)
- Data files: `data/miami_hotels_tbo.csv`, `data/booking_benchmarks.json`, `data/hotel_bookings_raw.csv`

---

## [0.6.0] - 2026-02-26 - Events, Conferences & Data Sources Registry

### Added
- **Events & conferences system** (`events_store.py`):
  - 8 hardcoded major Miami events (Art Basel, Ultra, F1, Miami Open, etc.)
  - SQLite storage for dynamic events from APIs
  - Impact calculator: EXTREME/VERY_HIGH/HIGH/MODERATE/LOW per date
  - Attendance-based demand scoring
- **Data sources registry** (`data_sources.py`):
  - 12 sources cataloged: 3 active, 9 planned
  - Categories: Internal Pricing, Travel Demand, Weather, Events, Competitor Pricing, Economic Indicators
  - Includes: Open-Meteo, PredictHQ, SeatGeek, Xotelo, FRED, GMCVB, BLS, MIA Airport
- Dashboard shows **Events & Conferences** section with upcoming events table
- Dashboard shows **Data Sources** overview (active vs planned)
- Predictions adjusted by events: F1/Art Basel (+40%), Ultra/Miami Open (+25%)
- New endpoints:
  - `GET /api/v1/salesoffice/events` — events summary JSON
  - `GET /api/v1/salesoffice/data-sources` — data sources registry

---

## [0.5.0] - 2026-02-26 - Flight Demand Indicator (Kiwi.com)

### Added
- **Flight demand signal**: External enrichment from Kiwi.com flight data
  - Tracks flight prices from 5 major US cities to Miami (NYC, Chicago, Atlanta, Boston, LA)
  - Demand indicator: HIGH / MEDIUM / LOW based on avg flight prices and availability
  - SQLite storage for flight demand snapshots (`flights_store.py`)
- Dashboard shows **Flight Demand Indicator** section with:
  - Demand level gauge (color-coded)
  - Per-origin flight prices and availability table
  - Avg/min flight price, total flights available
- New endpoint: `GET /api/v1/salesoffice/flights/demand` — returns demand JSON
- Predictions now adjusted by flight demand:
  - HIGH demand → reduces expected downward price pressure by 30%
  - LOW demand → increases expected downward pressure by 20%

---

## [0.4.0] - 2026-02-26 - Data-Driven Price Predictions

### Added
- **Historical price model**: Predictions now based on 3,906 real price records from SalesOffice DB
  - 232 room-date tracks analyzed (first price -> last price over time)
  - Bucketed by booking window: 0-30d, 31-60d, 61-90d, 90+d
  - Per-category adjustments (suite, standard, deluxe, superior)
  - Probability breakdown per prediction (P(up), P(down), P(stable))
- `collector.py`: `load_historical_prices()` — pulls all records including soft-deleted for model training
- `analyzer.py`: `_build_historical_model()` — builds track-level model from real data
- Dashboard shows model source info and probability columns
- Debug endpoint: `GET /api/v1/salesoffice/debug`

### Changed
- **Prediction model completely replaced**: was simplistic +10% assumption, now data-driven
  - Old: all rooms predicted +13.5% increase (wrong)
  - New: avg change -0.6%, 258 stable, 156 slight down (matches reality)
- Track-level total changes instead of daily rate compounding (prevents unrealistic predictions)
- Trimmed means and capped outliers for statistical robustness
- Error handling: analysis failures now return detailed error messages instead of generic 500

### Fixed
- `src/data/` module missing from Azure deploy.zip (was excluded by `data` dir filter)
- Deploy script now only excludes top-level `data/` directory, not nested `src/data/`

---

## [0.3.0] - 2026-02-26 - SalesOffice Analytics Dashboard (Azure)

### Added
- **Live dashboard on Azure**: `https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/dashboard`
- `src/api/analytics_dashboard.py` — FastAPI router with 3 endpoints:
  - `GET /api/v1/salesoffice/dashboard` — Interactive HTML dashboard (Plotly)
  - `GET /api/v1/salesoffice/data` — Raw analysis JSON
  - `GET /api/v1/salesoffice/status` — Quick status check
- Background hourly scheduler for automatic price collection
- In-memory cache with thread lock for latest analysis results
- Startup/shutdown hooks in `main.py` for scheduler lifecycle

---

## [0.2.0] - 2026-02-26 - SalesOffice Price Analytics Engine

### Added
- **`src/analytics/` module** — complete price tracking and analysis pipeline:
  - `collector.py` — Pulls room prices from `[SalesOffice.Details]` + `[SalesOffice.Orders]` + `Med_Hotels`
  - `analyzer.py` — Statistical analysis: per-hotel, per-room, booking window, price changes
  - `price_store.py` — Local SQLite storage for hourly price snapshots
  - `report.py` — Self-contained HTML reports with Plotly.js charts (dark theme)
  - `runner.py` — CLI runner with `--schedule`, `--collect-only`, `--analyze-only` modes
- Filters: `IsActive=1`, `WebJobStatus LIKE 'Completed%'`, `NOT LIKE '%Mapping: 0%'`
- Board/category label handling for both int IDs and string names (`_safe_label()`)

### Coverage
- 4 active hotels: Breakwater South Beach, citizenM Miami Brickell, Embassy Suites Miami, Hilton Miami Downtown
- ~360-414 rooms tracked per snapshot
- Price range: $125 - $923

---

## [0.1.1] - 2026-02-26 - Trading Integration + Azure Deployment

### Added
- `src/api/integration.py` — Read-only decision brain for trading system
- Deployed to Azure App Service (B1 tier, Israel Central)
- `src/data/trading_db.py` — SQLAlchemy connection to medici-db

---

## [0.1.0] - Initial Setup

### Added
- Project structure with ML pipeline skeleton
- Multi-source data pipeline with 5 collectors
- Analytics suite: occupancy prediction, RevPAR, demand analysis
- SQLAlchemy + Azure SQL Database integration
