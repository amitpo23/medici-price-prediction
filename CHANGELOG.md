# Changelog

All notable changes to the Medici Price Prediction system.

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
