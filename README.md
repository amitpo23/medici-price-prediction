# Medici Price Prediction 🏨📈

Hotel room options trading system with AI-powered price prediction, real-time scanning, and intelligent portfolio analytics.

**Live**: [medici-prediction-api.azurewebsites.net](https://medici-prediction-api.azurewebsites.net)

## Overview

Production system for hotel room price prediction and options-style trading signals:
- **Options Trading Dashboard** — 2,850+ rooms across 10 Miami hotels with CALL/PUT/NEUTRAL signals
- **Forward Curve Predictions** — Weighted ensemble: Forward Curve (50%), Historical Patterns (30%), ML (20%)
- **AI Intelligence** — Anomaly detection, risk assessment, Bayesian confidence, signal synthesis
- **Claude Analyst** — Natural language Q&A, executive briefs, smart metadata enrichment
- **Rules Engine** — 11 rule types, auto-generated alerts, preset templates
- **Real-time Scanning** — 3-hourly price collection from SalesOffice with scan history charts
- **12 Data Sources** — SalesOffice DB, weather, events, flights, competitor pricing, market benchmarks

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Data Sources (12)                  │
│  SalesOffice DB │ Weather │ Events │ Flights │ CBS  │
│  Market Bench.  │ Kaggle  │ Competitors │ Trading   │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│              Prediction Engine                       │
│  Forward Curve (50%) │ Historical (30%) │ ML (20%)  │
│  Momentum │ Regime │ Seasonality │ Booking Window   │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│              AI Layer                                │
│  AI Intelligence │ Claude Analyst │ Rules Engine     │
│  Anomaly Detection │ Risk Assessment │ Smart Tags   │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│              API Layer (90+ endpoints)               │
│  FastAPI │ HTML Dashboard │ JSON APIs │ AI Q&A      │
│  Options Trading │ Rules CRUD │ Source Validation    │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
medici-price-prediction/
├── config/                 # Settings & environment config
├── data/                   # Data storage (gitignored)
│   ├── raw/                # Raw data from sources
│   ├── processed/          # Cleaned & transformed data
│   ├── models/             # Trained model artifacts
│   └── cache/              # Runtime caches
├── docs/                   # Documentation
│   ├── PREDICTION_ALGORITHM.md
│   └── USAGE_GUIDE.md
├── notebooks/              # Jupyter exploration notebooks
├── src/
│   ├── analytics/          # Core analysis engine
│   │   ├── ai_intelligence.py   # Anomaly, risk, Bayesian, signal synthesis (959 lines)
│   │   ├── claude_analyst.py    # Claude-powered Q&A, briefs, metadata (1,033 lines)
│   │   ├── deep_predictor.py    # Weighted ensemble predictor (764 lines)
│   │   ├── forward_curve.py     # Forward curve generation
│   │   ├── collector.py         # SalesOffice data collection
│   │   ├── analyzer.py          # Portfolio analysis
│   │   ├── momentum.py          # Price momentum signals
│   │   ├── regime.py            # Market regime detection
│   │   ├── seasonality.py       # Seasonal pattern analysis
│   │   └── ...                  # 17 analytics modules
│   ├── api/
│   │   ├── analytics_dashboard.py  # Main API + HTML dashboard (3,810 lines)
│   │   ├── rules_api.py            # Rules CRUD endpoints (509 lines)
│   │   ├── main.py                 # FastAPI app entry point
│   │   └── integration.py          # External integrations
│   ├── rules/               # Rules engine
│   │   ├── engine.py        # Rule evaluation (416 lines)
│   │   ├── models.py        # Pydantic models (251 lines)
│   │   ├── store.py         # JSON persistence (417 lines)
│   │   ├── auto_generator.py # ML-driven suggestions (259 lines)
│   │   └── presets.py       # Pre-built templates (210 lines)
│   ├── collectors/          # Data source collectors
│   ├── data/                # DB loaders & schemas
│   ├── features/            # Feature engineering
│   ├── models/              # ML model definitions
│   ├── services/            # Scheduler & services
│   └── utils/               # Helpers
├── tests/                   # Unit & integration tests
├── scripts/                 # DB setup scripts
├── startup.sh               # Azure deployment startup
├── requirements.txt         # Development dependencies
└── requirements-deploy.txt  # Production dependencies
```

## Key API Endpoints

### Options Trading
| Endpoint | Description |
|----------|-------------|
| `GET /options` | Full portfolio with predictions (2,850 rows) |
| `GET /options/view` | Interactive HTML dashboard |
| `GET /options/legend` | Signal legend & color scale |
| `GET /options/{detail_id}` | Single room details |

### AI Analyst
| Endpoint | Description |
|----------|-------------|
| `GET /ai/ask?q=...` | Natural language Q&A |
| `GET /ai/brief?lang=en` | Executive market brief |
| `GET /ai/explain/{id}` | Deep prediction breakdown |
| `GET /ai/metadata?limit=50` | Smart tags & enrichment |
| `GET /options/ai-insights` | Anomaly & risk analysis |

### Rules Engine
| Endpoint | Description |
|----------|-------------|
| `POST /rules/` | Create alert rule |
| `GET /rules/` | List rules |
| `POST /rules/evaluate-all` | Run all active rules |
| `POST /rules/auto-generate` | ML-suggested rules |
| `GET /rules/presets` | Available templates |

### Data & Status
| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /salesoffice/status` | Collection & analysis status |
| `GET /sources/audit` | Data source validation |

## Getting Started

### Prerequisites
- Python 3.10+
- Access to SalesOffice Azure SQL database

### Installation
```bash
git clone https://github.com/YOUR_USERNAME/medici-price-prediction.git
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

## Tech Stack

- **Framework**: FastAPI + Uvicorn + Gunicorn
- **ML**: scikit-learn, XGBoost, pandas, numpy
- **AI**: Anthropic Claude (Haiku/Sonnet) with rule-based fallback
- **Database**: Azure SQL (pyodbc/SQLAlchemy)
- **Deployment**: Azure App Service (Python 3.12)
- **Frontend**: Server-rendered HTML dashboard with vanilla JS charts
