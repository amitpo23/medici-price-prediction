"""LightRAG configuration for Medici Price Prediction.

Builds a knowledge graph from hotel pricing data, events,
weather, and market signals for intelligent Q&A.
"""

import os
from pathlib import Path

# Storage directory for LightRAG knowledge graph
LIGHTRAG_WORKING_DIR = os.getenv(
    "LIGHTRAG_WORKING_DIR",
    str(Path(__file__).parent.parent / "data" / "lightrag_store")
)

# LLM configuration (uses same Claude key as the rest of Medici)
LIGHTRAG_LLM_CONFIG = {
    "provider": "anthropic",
    "model": os.getenv("LIGHTRAG_MODEL", "claude-haiku-4-5-20251001"),
    "api_key_env": "ANTHROPIC_API_KEY",
    "max_tokens": 4096,
}

# Embedding configuration
LIGHTRAG_EMBEDDING_CONFIG = {
    "provider": os.getenv("LIGHTRAG_EMBEDDING_PROVIDER", "openai"),
    "model": os.getenv("LIGHTRAG_EMBEDDING_MODEL", "text-embedding-3-small"),
    "api_key_env": "OPENAI_API_KEY",
}

# Data sources to ingest into knowledge graph
LIGHTRAG_DATA_SOURCES = [
    "prediction_reports",     # Historical prediction signals
    "event_data",             # Miami events (Art Basel, etc.)
    "weather_data",           # Weather impact records
    "market_signals",         # Flight/demand data
    "accuracy_reports",       # Prediction accuracy tracking
    "scenario_analyses",      # What-if scenario results
]

# Query modes: local, global, hybrid, naive, mix
DEFAULT_QUERY_MODE = "hybrid"
