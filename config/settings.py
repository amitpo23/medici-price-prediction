"""Project configuration loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
CACHE_DIR = DATA_DIR / "cache"

# Rules engine database (SQLite)
RULES_DB_DIR = DATA_DIR / "rules"
RULES_DB_PATH = RULES_DB_DIR / "pricing_rules.db"

# Ensure directories exist
for _dir in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR, CACHE_DIR, RULES_DB_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# Azure SQL Database (prediction system's own DB)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Medici Hotels Trading DB (READ-ONLY access)
MEDICI_DB_URL = os.getenv("MEDICI_DB_URL", "")
TRADING_CACHE_TTL_MINUTES = int(os.getenv("TRADING_CACHE_TTL_MINUTES", "5"))
TRADING_ANALYSIS_INTERVAL_MINUTES = int(os.getenv("TRADING_ANALYSIS_INTERVAL_MINUTES", "30"))

# Runtime environment / scheduler controls
ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "production")).strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"
SALESOFFICE_COLLECTION_INTERVAL_SECONDS = int(
    os.getenv("SALESOFFICE_COLLECTION_INTERVAL_SECONDS", "10800")
)
SALESOFFICE_SCHEDULER_ENABLED = os.getenv("SALESOFFICE_SCHEDULER_ENABLED", "true").lower() in (
    "true", "1", "yes"
)
SALESOFFICE_ALLOW_NON_PROD_SCHEDULER = os.getenv(
    "SALESOFFICE_ALLOW_NON_PROD_SCHEDULER", "false"
).lower() in ("true", "1", "yes")
SALESOFFICE_ON_DEMAND_WARMUP_ENABLED = os.getenv(
    "SALESOFFICE_ON_DEMAND_WARMUP_ENABLED", "false"
).lower() in ("true", "1", "yes")
SALESOFFICE_CACHE_PERSISTENCE_ENABLED = os.getenv(
    "SALESOFFICE_CACHE_PERSISTENCE_ENABLED", "true"
).lower() in ("true", "1", "yes")
SALESOFFICE_PRECOMPUTE_T_DAYS = int(os.getenv("SALESOFFICE_PRECOMPUTE_T_DAYS", "7"))
SALESOFFICE_PRECOMPUTE_DETAIL_LIMIT = int(
    os.getenv("SALESOFFICE_PRECOMPUTE_DETAIL_LIMIT", "25")
)

# API Authentication for trading integration
PREDICTION_API_KEY = os.getenv("PREDICTION_API_KEY", "")

# External API Keys
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME", "")
KAGGLE_KEY = os.getenv("KAGGLE_KEY", "")
PREDICTHQ_API_KEY = os.getenv("PREDICTHQ_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")
SEATGEEK_CLIENT_ID = os.getenv("SEATGEEK_CLIENT_ID", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
MAKCORPS_API_KEY = os.getenv("MAKCORPS_API_KEY", "")

# AI Intelligence (Anthropic Claude)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_AI_MODEL = os.getenv("CLAUDE_AI_MODEL", "claude-haiku-4-20250514")
AI_INTELLIGENCE_ENABLED = os.getenv("AI_INTELLIGENCE_ENABLED", "true").lower() in ("true", "1", "yes")

# Cache
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

# Unified cache regions — {name: {ttl_seconds, max_size}}
# ttl=0 means no expiry; max_size=0 means unlimited
CACHE_CONFIG: dict[str, dict[str, int]] = {
    "analytics":      {"ttl": 0,     "max_size": 0},     # main analysis, refreshed by scheduler
    "yoy":            {"ttl": 21600, "max_size": 0},     # 6 hours
    "options_expiry": {"ttl": 21600, "max_size": 0},     # 6 hours
    "charts":         {"ttl": 21600, "max_size": 0},     # 6 hours
    "accuracy":       {"ttl": 21600, "max_size": 0},     # 6 hours
    "provider":       {"ttl": 21600, "max_size": 0},     # 6 hours
    "ai":             {"ttl": int(os.getenv("AI_CACHE_TTL_SECONDS", "1800")),  "max_size": 500},
    "analyst":        {"ttl": int(os.getenv("ANALYST_CACHE_TTL", "600")),      "max_size": 200},
    "salesoffice_options": {"ttl": 0, "max_size": 64},
    "salesoffice_detail":  {"ttl": 0, "max_size": 1000},
}

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Model
MODEL_PATH = MODELS_DIR
FORECAST_HORIZON = int(os.getenv("FORECAST_HORIZON", "30"))

# Analytics
ANALYTICS_CACHE_TTL_HOURS = int(os.getenv("ANALYTICS_CACHE_TTL_HOURS", "6"))
DEFAULT_CONFIDENCE_LEVELS = [0.80, 0.95]
BOOTSTRAP_N_SAMPLES = int(os.getenv("BOOTSTRAP_N_SAMPLES", "200"))

# Israel — city coordinates for weather/geo
ISRAEL_CITIES = {
    "Tel Aviv":  (32.0853, 34.7818),
    "Jerusalem": (31.7683, 35.2137),
    "Eilat":     (29.5577, 34.9519),
    "Haifa":     (32.7940, 34.9896),
    "Dead Sea":  (31.5000, 35.5000),
    "Tiberias":  (32.7922, 35.5312),
    "Netanya":   (32.3215, 34.8532),
    "Herzliya":  (32.1629, 34.8446),
}
