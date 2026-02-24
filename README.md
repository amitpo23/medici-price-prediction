# Medici Price Prediction 🏨📈

Hotel price prediction and dynamic pricing system for the Medici Hotels platform.

## Overview

This project aims to build a prediction system that:
- **Forecasts hotel room prices** based on historical data, seasonality, events, and market conditions
- **Connects to existing databases** (Supabase) to leverage booking and pricing data
- **Provides pricing recommendations** for optimal revenue management
- **Monitors competitor pricing** to adjust strategies in real-time

## Project Status

🚧 **In Development** — Architecture and technology decisions in progress.

## Planned Architecture

```
┌─────────────────────────────────────────────┐
│              Data Sources                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Supabase │ │ Innstant │ │ Competitor   │ │
│  │ (booking │ │ GoGlobal │ │ Pricing      │ │
│  │  data)   │ │ (supply) │ │ (scraped)    │ │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
└───────┼────────────┼───────────────┼─────────┘
        │            │               │
┌───────▼────────────▼───────────────▼─────────┐
│           Data Pipeline / ETL                 │
│  - Data collection & cleaning                 │
│  - Feature engineering                        │
│  - Time series preparation                    │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│           ML / Prediction Engine              │
│  - Price forecasting models                   │
│  - Demand prediction                          │
│  - Dynamic pricing optimization               │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│           API / Integration Layer             │
│  - REST API for predictions                   │
│  - Integration with Medici backend            │
│  - Dashboard / monitoring                     │
└──────────────────────────────────────────────┘
```

## Project Structure

```
medici-price-prediction/
├── data/                  # Data storage (gitignored)
│   ├── raw/               # Raw data from sources
│   ├── processed/         # Cleaned & transformed data
│   └── models/            # Trained model artifacts
├── notebooks/             # Jupyter notebooks for exploration
├── src/                   # Source code
│   ├── data/              # Data loading & processing
│   ├── features/          # Feature engineering
│   ├── models/            # ML model definitions & training
│   ├── api/               # API endpoints
│   └── utils/             # Helper functions
├── tests/                 # Unit & integration tests
├── config/                # Configuration files
├── docs/                  # Documentation
├── .env.example           # Environment variables template
├── .gitignore
├── requirements.txt       # Python dependencies
└── README.md
```

## Getting Started

### Prerequisites
- Python 3.10+
- Access to Medici Supabase database

### Installation
```bash
git clone https://github.com/YOUR_USERNAME/medici-price-prediction.git
cd medici-price-prediction
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Configure your environment variables
```

## Key References

### Forecasting Frameworks
- [Darts](https://github.com/unit8co/darts) — Comprehensive time series forecasting
- [PyTorch Forecasting](https://github.com/sktime/pytorch-forecasting) — Deep learning forecasting
- [Time-Series-Library](https://github.com/thuml/Time-Series-Library) — Academic benchmark models

### Hotel-Specific
- [hotel-modelling](https://github.com/MGCodesandStats/hotel-modelling) — ADR prediction with ARIMA/LSTM
- [Dynamic-Price](https://github.com/gitvivekgupta/Dynamic-Price) — Dynamic pricing for hotels
- [RevPy](https://github.com/flix-tech/RevPy) — Revenue management tools

## License

Private — Medici Hotels
