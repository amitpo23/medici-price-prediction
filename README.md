# Medici Price Prediction

Hotel room options trading system with AI-powered price prediction, real-time scanning, and intelligent portfolio analytics.

**Live**: [medici-prediction-api.azurewebsites.net](https://medici-prediction-api.azurewebsites.net)

## Overview

Production system for hotel room price prediction and options-style trading signals:
- **Options Trading Dashboard** — 2,850+ rooms across 10 Miami hotels with CALL/PUT/NEUTRAL signals
- **Inline Trading Charts** — Expandable per-row chart panels with Forward Curve, scan history, and signal breakdown
- **Forward Curve Predictions** — Weighted ensemble: Forward Curve (50%), Historical Patterns (30%), ML (20%)
- **AI Intelligence** — Anomaly detection, risk assessment, Bayesian confidence, signal synthesis
- **Claude Analyst** — Natural language Q&A, executive briefs, smart metadata enrichment
- **Rules Engine** — 11 rule types, auto-generated alerts, preset templates
- **Scenario Analysis** — What-if modeling with 5 presets (Art Basel, Hurricane, Peak Season, etc.)
- **Real-Time Alerts** — Multi-channel dispatch (log, webhook, Telegram) with cooldown deduplication
- **Data Quality Scoring** — Per-source freshness/reliability/anomaly monitoring with auto weight adjustment
- **Prediction Accuracy** — Closed-loop tracking with MAE, MAPE, directional accuracy by signal/T-bucket/hotel
- **Real-time Scanning** — 3-hourly price collection from SalesOffice with scan history charts
- **12 Data Sources** — SalesOffice DB, weather, events, flights, competitor pricing, market benchmarks
- **340 Tests** — Unit + integration tests with GitHub Actions CI

## Architecture

```
+---------------------------------------------------------+
|                   Data Sources (12)                      |
|  SalesOffice DB | Weather | Events | Flights | CBS      |
|  Market Bench.  | Kaggle  | Competitors | Trading       |
+--------------------------+------------------------------+
                           |
+--------------------------v------------------------------+
|              Prediction Engine                          |
|  Forward Curve (50%) | Historical (30%) | ML (20%)     |
|  Momentum | Regime | Seasonality | Booking Window      |
+--------------------------+------------------------------+
                           |
+--------------------------v------------------------------+
|              AI & Analytics Layer                       |
|  AI Intelligence | Claude Analyst | Rules Engine        |
|  Scenario Engine | Accuracy Tracker | Data Quality      |
|  Alert Dispatcher | Anomaly Detection | Risk Assessment |
+--------------------------+------------------------------+
                           |
+--------------------------v------------------------------+
|              API Layer (90+ endpoints)                  |
|  5 Sub-Routers | Pagination | Rate Limiting | Auth     |
|  HTML Dashboard | JSON APIs | CSV Export | Health       |
+---------------------------------------------------------+
```

## Project Structure

```
medici-price-prediction/
├── config/
│   ├── settings.py             # Environment config
│   └── constants.py            # 30+ documented constants (ensemble weights, thresholds, caps)
├── data/                       # Data storage (gitignored)
├── docs/
│   ├── PREDICTION_ALGORITHM.md # 8-step prediction pipeline
│   ├── USAGE_GUIDE.md          # API usage & endpoint reference
│   └── salesoffice/            # SalesOffice system docs
├── src/
│   ├── analytics/              # Core analysis engine (17 modules)
│   │   ├── forward_curve.py       # Forward curve generation (700 lines)
│   │   ├── deep_predictor.py      # Weighted ensemble predictor (784 lines)
│   │   ├── ai_intelligence.py     # Anomaly, risk, Bayesian, signal synthesis (948 lines)
│   │   ├── claude_analyst.py      # Claude-powered Q&A & briefs (1,024 lines)
│   │   ├── scenario_engine.py     # What-if scenario analysis
│   │   ├── accuracy_tracker.py    # Prediction accuracy tracking
│   │   ├── data_quality.py        # Source freshness/reliability scoring
│   │   ├── momentum.py            # Price momentum signals
│   │   ├── regime.py              # Market regime detection
│   │   └── ...
│   ├── api/
│   │   ├── main.py                # FastAPI entry point (917 lines)
│   │   ├── analytics_dashboard.py # Thin shell assembling 5 sub-routers (~35 lines)
│   │   ├── middleware.py          # Correlation IDs, rate limiting, CORS
│   │   ├── models/                # Pagination models
│   │   └── routers/
│   │       ├── _shared_state.py       # Scheduler, caches, helpers (~795 lines)
│   │       ├── analytics_router.py    # JSON APIs: /options, /data, /forward-curve
│   │       ├── dashboard_router.py    # HTML pages: /dashboard, /yoy, /charts
│   │       ├── ai_router.py           # AI: /ai/ask, /ai/brief, /ai/explain
│   │       ├── market_router.py       # Market: /market/*, /flights, /events
│   │       └── export_router.py       # Exports: /export/csv/*, /export/summary
│   ├── rules/                  # Rules engine (5 modules, ~1,550 lines)
│   ├── collectors/             # Data source collectors (auto-discovery)
│   ├── data/                   # DB loaders & schemas (read-only enforced)
│   ├── features/               # Feature engineering
│   ├── models/                 # ML model definitions
│   ├── services/
│   │   ├── alert_dispatcher.py # Multi-channel alerts with deduplication
│   │   └── scheduler.py       # Background job scheduling
│   ├── templates/              # 11 Jinja2 HTML templates
│   └── utils/
│       ├── cache_manager.py    # Unified CacheManager (8 regions, TTL, LRU)
│       ├── config_validator.py # Startup environment validation
│       ├── logging_config.py   # Structured JSON logging
│       └── template_engine.py  # Jinja2 environment setup
├── tests/
│   ├── unit/                   # 193+ unit tests
│   └── integration/            # 14 integration tests
├── .github/workflows/test.yml  # CI pipeline
├── startup.sh                  # Azure deployment startup
└── requirements.txt            # Dependencies
```

## Key API Endpoints

All endpoints are under `/api/v1/salesoffice` unless noted.

### Options Trading
| Endpoint | Description |
|----------|-------------|
| `GET /options` | Full portfolio with predictions (paginated, default 100) |
| `GET /options/view` | Interactive HTML dashboard |
| `GET /options/legend` | Signal legend & color scale |
| `GET /options/detail/{detail_id}` | Trading chart data (FC, scans, signals) |

### AI Analyst
| Endpoint | Description |
|----------|-------------|
| `GET /ai/ask?q=...` | Natural language Q&A |
| `GET /ai/brief?lang=en` | Executive market brief |
| `GET /ai/explain/{id}` | Deep prediction breakdown |
| `GET /ai/metadata?limit=50` | Smart tags & enrichment |

### Scenario Analysis
| Endpoint | Description |
|----------|-------------|
| `POST /scenario/run` | Run what-if scenario with overrides |
| `GET /scenario/presets` | List 5 preset scenarios |
| `POST /scenario/compare` | Compare multiple scenarios side-by-side |

### Alerts & Monitoring
| Endpoint | Description |
|----------|-------------|
| `GET /alerts/history?days=7` | Alert log |
| `POST /alerts/test` | Fire test alert to all channels |
| `GET /alerts/stats` | Alert volume & top rules |
| `GET /data-quality/status` | All sources with quality scores |
| `GET /data-quality/history?source=...&days=30` | Source health history |

### Prediction Accuracy
| Endpoint | Description |
|----------|-------------|
| `GET /accuracy/summary?days=30` | MAE, MAPE, directional accuracy |
| `GET /accuracy/by-signal` | Precision/recall per CALL/PUT/NEUTRAL |
| `GET /accuracy/by-t-bucket` | Accuracy by T ranges (1-7, 8-14, ...) |
| `GET /accuracy/by-hotel` | Per-hotel accuracy |
| `GET /accuracy/trend` | Rolling 7/30-day accuracy |

### Rules Engine
| Endpoint | Description |
|----------|-------------|
| `POST /rules/` | Create alert rule |
| `GET /rules/` | List rules |
| `POST /rules/evaluate-all` | Run all active rules |
| `POST /rules/auto-generate` | ML-suggested rules |

### System & Health
| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with source status, cache metrics |
| `GET /health/view` | HTML health dashboard |
| `GET /status` | Collection & analysis status |
| `GET /sources/audit` | Data source validation |
| `GET /export/csv/contracts` | CSV export of contracts |
| `GET /export/summary` | Portfolio summary export |

## Getting Started

### Prerequisites
- Python 3.10+
- Access to SalesOffice Azure SQL database

### Installation
```bash
git clone https://github.com/amitpo23/medici-price-prediction.git
cd medici-price-prediction
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Configure environment variables
```

### Run Locally
```bash
uvicorn src.api.main:app --reload --port 8000
```

### Run Tests
```bash
python -m pytest tests/ -q
```

### Deploy to Azure
```bash
rm -f /tmp/medici-deploy.zip && \
zip -qr /tmp/medici-deploy.zip . -x "venv/*" ".git/*" "data/*" "__pycache__/*" "*.pyc" && \
az webapp deploy -g medici-prediction-rg -n medici-prediction-api \
  --src-path /tmp/medici-deploy.zip --type zip
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SALESOFFICE_DB_URL` | Azure SQL connection string | Required |
| `ANTHROPIC_API_KEY` | Claude API key (optional — fallback works without) | None |
| `CLAUDE_AI_MODEL` | Claude model for queries | `claude-haiku-4-20250514` |
| `AI_INTELLIGENCE_ENABLED` | Enable AI intelligence module | `true` |
| `API_KEYS` | Comma-separated API keys for auth | None (no auth) |
| `CORS_ORIGINS` | Allowed CORS origins | Same-origin |
| `ALERT_WEBHOOK_URL` | Webhook URL for alerts | None |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts | None |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alerts | None |
| `ALERT_COOLDOWN_HOURS` | Alert deduplication cooldown | `4` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Tech Stack

- **Framework**: FastAPI + Uvicorn + Gunicorn
- **ML**: scikit-learn, XGBoost, pandas, numpy
- **AI**: Anthropic Claude (Haiku/Sonnet) with rule-based fallback
- **Database**: Azure SQL (pyodbc/SQLAlchemy) read-only + SQLite for history
- **Templates**: Jinja2 with shared base template
- **Middleware**: slowapi (rate limiting), correlation IDs, CORS
- **Testing**: pytest with 340 tests, GitHub Actions CI
- **Deployment**: Azure App Service (Python 3.12)
