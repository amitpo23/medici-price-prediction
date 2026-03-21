# Medici Price Prediction — Session Primer

## Current State (2026-03-21)

### Production
- **Azure B2**, Always On, 23 hotels, 4,050+ rooms
- **Deploy zip:** 220 files
- **Tests:** 625+ unit + 26 integration, all passing (1 pre-existing failure)

### Sessions 2026-03-20 — 2026-03-21 (20+ commits)

#### Core Fixes
1. **Collector fix** — `d.IsDeleted = 0` filter. Was 6,089 → now ~4,050 (matches admin)
2. **sources/compare perf** — removed `compute_next_day_signals` from single-detail endpoint (was blocking 30+ sec)
3. **Signals cache** — `_get_cached_signals()` precomputes signals in collection cycle, non-blocking on request path

#### Analytics Engines
4. **Path Forecast** — full price lifecycle: turning points, segments, best trade
5. **Raw Source Analyzer** — per-source stats, consensus, enrichment stripping
6. **Source Attribution** — 4 isolated tracks (FC/Historical/ML/Ensemble), enrichment decomposition, agreement rate (69.8%)
7. **Group Actions** — bulk CALL/PUT execution with GroupFilter (signal, hotel, category, board, confidence, T, price). 57 tests

#### Execution System
8. **Override Queue** — SQLite job queue for PUT signals (undercut by $X). 38 tests
9. **Opportunity Queue** — SQLite job queue for CALL signals (buy + push at +$50). 40 tests
10. **Skills imported** — `insert-opp/` + `price-override/` in local `skills/`

#### Dashboards
11. **Trading Terminal** (`/dashboard/terminal`) — Chart.js multi-line price chart, enrichment stacked bar, signal/sources/accuracy panels, options table with Override/Buy buttons, bulk bar
12. **Path Forecast** (`/dashboard/path-forecast`) — price paths with Canvas charts
13. **Source Comparison** (`/dashboard/sources`) — per-source analysis
14. **Override Queue** (`/dashboard/override-queue`) — queue management
15. **Opportunity Queue** (`/dashboard/opportunity-queue`) — queue management

#### Options Enrichment
16. 8 new fields in every `/options` row: `path_min/max_price/t`, `path_num_reversals`, `path_best_trade_pct`, `source_consensus`, `source_disagreement`
17. Forward curve raw mode: `?raw=true` strips enrichments

#### Infrastructure
18. **build_deploy.py** — 350MB → 572KB (excluded venv, node_modules, mcp-servers)
19. **Portfolio Greeks** + **Circuit Breaker** + **Monitor Bridge** — committed from previous sessions
20. **Jinja2 extraction** — terminal.html template

### API Endpoints Added
- `/path-forecast`, `/path-forecast/{id}`
- `/sources/compare`, `/sources/compare/{id}`, `/sources/raw/{source}/{id}`
- `/forward-curve/{id}?raw=true`
- `/override/request`, `/override/bulk`, `/override/queue`, `/override/pending`, `/override/{id}/complete`, `/override/history`
- `/opportunity/request`, `/opportunity/bulk`, `/opportunity/queue`, `/opportunity/pending`, `/opportunity/{id}/complete`, `/opportunity/history`
- `/group/preview`, `/group/override`, `/group/opportunity`
- `/attribution`, `/attribution/sources`, `/attribution/enrichments`, `/attribution/agreement`, `/attribution/hotel/{id}`

### Next Session — Planned
- **Active Rooms Selector** — extend prediction to MED_Book (IsActive=1) beyond SalesOffice Details
- Analyze unsold inventory, compare buy vs market price, predict sell probability by T

### Production URLs
- Trading Terminal: `/api/v1/salesoffice/dashboard/terminal`
- Options board: `/api/v1/salesoffice/options/view`
- Override Queue: `/api/v1/salesoffice/dashboard/override-queue`
- Opportunity Queue: `/api/v1/salesoffice/dashboard/opportunity-queue`
- Path forecast: `/api/v1/salesoffice/dashboard/path-forecast`
- Source comparison: `/api/v1/salesoffice/dashboard/sources`
