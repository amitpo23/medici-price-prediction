# Medici Price Prediction — Project Context

## What This System Is

Medici Price Prediction is a **Decision Brain** for hotel room pricing. It models hotel rooms as financial instruments, generates CALL/PUT/NEUTRAL signals with confidence levels, and provides AI-powered analytics. It **never** executes trades or changes prices — all decisions remain with the operator or the Medici trading platform.

## Core Architecture (4 Layers)

```
Layer 1: Data Collection → 12 active sources (Azure SQL, APIs, files)
Layer 2: Prediction Engine → Weighted ensemble: Forward Curve 50% + Historical 30% + ML 20%
Layer 3: AI Intelligence → Anomaly detection, risk assessment, Claude Q&A, rules engine
Layer 4: API & Dashboard → FastAPI 90+ endpoints, HTML dashboard, JSON/CSV export
```

## Key Numbers

- **2,850+ rooms** across 10 Miami hotels
- **90+ API endpoints** under `/api/v1/salesoffice`
- **~32,000 lines** of Python code
- **12 active + 5 planned** data sources
- Deployed on **Azure App Service** (Python 3.12)

## Project Structure

```
src/
  api/
    analytics_dashboard.py → Thin shell (~35 lines) assembling 5 sub-routers
    routers/
      _shared_state.py     → Scheduler, analysis cache, computation helpers
      _options_html_gen.py  → HTML generator (extracted from monolith)
      analytics_router.py   → ~25 JSON endpoints: /options, /data, /simple, /forward-curve, etc.
      dashboard_router.py   → 12 HTML endpoints: /dashboard, /yoy, /charts, /accuracy, etc.
      ai_router.py          → 5 AI endpoints: /ai/ask, /ai/brief, /ai/explain, /ai/metadata
      market_router.py      → 18 market endpoints: /market/*, /flights, /events, /knowledge
      export_router.py      → 3 export endpoints: /export/csv/*, /export/summary
    models/
      pagination.py      → PaginatedResponse, paginate(), pagination_params dependency
    main.py              → FastAPI entry, /predict, /train
  analytics/        → Core engine: forward_curve, deep_predictor, ai_intelligence, claude_analyst,
                      momentum, regime, seasonality, options_engine, accuracy_engine, etc.
  collectors/       → Data source collectors (weather, events, market, kaggle, CBS, trading)
  data/             → DB loaders, schemas, trading_db.py (READ-ONLY enforced)
  features/         → Feature engineering pipeline for ML
  models/           → ML model definitions (LightGBM, XGBoost)
  rules/            → Rules engine: 11 rule types, auto-generation, presets
  services/         → Service layer
  utils/            → cache_manager.py (unified CacheManager), config_validator.py
config/             → settings.py (env vars + CACHE_CONFIG), market configs
data/               → SQLite DB, benchmarks JSON, raw/processed data
docs/               → PREDICTION_ALGORITHM.md, INTEGRATION_SPEC.md, USAGE_GUIDE.md
scripts/            → Training, deployment, utility scripts
tests/
  unit/             → test_forward_curve, test_deep_predictor, test_options_engine,
                      test_config_validator, test_cache_manager, test_pagination,
                      test_logging_config, test_rate_limiting (237 tests total)
  integration/      → test_api_endpoints (14 tests)
```

## Critical Rules — DO NOT BREAK

1. **Read-only database access**: `src/data/trading_db.py` uses SQLAlchemy event listener to block all INSERT/UPDATE/DELETE. Never disable this.
2. **Decision Brain boundary**: The system must NEVER execute trades, change prices, or perform actions in SalesOffice. It only reads and recommends.
3. **Claude AI fallback**: Every AI feature must work without an API key via rule-based fallback. Never make Claude API a hard dependency.
4. **Ensemble weights**: 50/30/20 split (FC/Historical/ML) is documented and validated. Don't change without A/B testing evidence.

## Prediction Pipeline

```
Price Scan (every 3h) → SQLite storage → Build Forward Curve (Bayesian smoothed)
  → Apply 9 enrichments (events, seasonality, demand, weather, competitors, cancellations, ...)
  → Combine with Historical Patterns (30%) and ML (20%)
  → Generate CALL/PUT/NEUTRAL signal with confidence
  → Cache results → Serve via API
```

### Enrichment Adjustments (daily % impact on forward curve)
- Events: +0.03% to +0.40% (Art Basel is highest)
- Seasonality: multiplier ×3.0 on (index - 1.0), Feb peak +9.9%, Sep trough -15.5%
- Demand (flights): HIGH +0.15%, LOW -0.15%
- Weather: rain -0.05%, clear +0.02%, hurricane -0.15%
- Competitor pressure: ±0.20%
- Cancellation risk: -0.25% max

## Tech Stack

- **Framework**: FastAPI + Uvicorn + Gunicorn
- **ML**: scikit-learn, XGBoost, pandas, numpy
- **AI**: Anthropic Claude (Haiku fast / Sonnet deep) + rule-based fallback
- **Database**: Azure SQL (pyodbc/SQLAlchemy) read-only + SQLite for price history
- **Deploy**: Azure App Service, zip deploy via build_deploy.py

## Completed Sprints

- **Sprint 1.1**: Test infrastructure (pytest, conftest, GitHub Actions)
- **Sprint 1.2**: Integration tests for critical API endpoints (14 tests)
- **Sprint 1.3**: Unit tests for prediction core — forward_curve, deep_predictor, options_engine (120+ tests)
- **Sprint 1.4**: Fixed 81 bare `except Exception` handlers with specific exception types + logging
- **Sprint 1.5**: Startup config validation (`src/utils/config_validator.py`) with 23 tests
- **Sprint 2.1**: Split monolith router — 4,293-line `analytics_dashboard.py` → thin shell + 5 sub-routers
- **Sprint 2.2**: Unified 8 independent cache systems into single `CacheManager` with 40 tests
- **Sprint 2.3**: Extract HTML to Jinja2 templates — 11 page generators now use `render_template()`
- **Sprint 3.1**: API pagination — `paginate()` utility + 4 endpoints (`/options`, `/data`, `/simple`, `/ai/metadata`) with `?limit=&offset=&all=true`
- **Sprint 3.2**: Structured JSON logging — `python-json-logger`, `CorrelationIdMiddleware` (X-Request-ID), replaced all 28 `print()` calls
- **Sprint 3.3**: Rate limiting (`slowapi`) + multi-key API auth + CORS middleware — 100/min data, 20/min AI, 10/min export
- **Sprint 3.4**: Health check dashboard — enhanced `/health?detail=true` with data source freshness + HTML dashboard at `/health/view`
- **Sprint 4.1**: Prediction feedback loop — `accuracy_tracker.py` with SQLite `prediction_log`, daily scoring job, 5 accuracy API endpoints
- **Sprint 4.2**: Real-time alert system — `alert_dispatcher.py` with 3 channels (Log/Webhook/Telegram), SQLite dedup, 3 alert API endpoints
- **Sprint 4.3**: Data quality scoring — `data_quality.py` with freshness/reliability/anomaly scores, auto weight adjustment, 2 API endpoints
- **Sprint 4.4**: Scenario analysis engine — `scenario_engine.py` with 5 presets, what-if overrides (events/demand/weather/competitors/seasonal), 3 API endpoints
- **Sprint 2.4**: Collector registry auto-discovery with `COLLECTOR_{NAME}_ENABLED` env var toggle
- **Sprint 2.5**: Extracted 30+ magic numbers to `config/constants.py` (ensemble weights, enrichment caps, thresholds)

## Remaining Technical Debt

All planned sprints are complete. Minor cleanup opportunities:
- Additional Jinja2 template extraction for remaining HTML generators
- Further test coverage for collectors and feature engineering

## Coding Conventions

- Python 3.12, type hints everywhere
- FastAPI routers for API endpoints
- SQLAlchemy for database access (always read-only)
- Logger over print() — use `logger = logging.getLogger(__name__)`
- Config via environment variables (see `.env.example`)
- Hebrew + English bilingual support in AI endpoints

## When Making Changes

1. **Run existing code checks first**: `python3 -m py_compile <file>` before committing
2. **Respect the 4-layer architecture**: Don't put API logic in analytics, don't put analytics in collectors
3. **Every new feature needs**: unit test, error handling (no bare except), logging, docstring
4. **Cache changes**: When modifying prediction logic, ensure caches are invalidated
5. **New endpoints**: Add to the appropriate router in `src/api/routers/`, not to analytics_dashboard.py
6. **New data sources**: Implement as a collector in `src/collectors/` extending `base.py`
