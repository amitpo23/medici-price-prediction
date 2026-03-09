"""Startup configuration validator — fail fast on missing or invalid config.

Called at app startup to verify all required environment variables are set
and properly formatted. Returns a health report for logging/diagnostics.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def validate_config() -> dict:
    """Validate all configuration and return a health report.

    Returns:
        {
            "valid": bool,        # True if no errors (warnings are OK)
            "warnings": [...],    # Non-fatal issues
            "errors": [...],      # Fatal issues
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Required for core functionality ──────────────────────────
    db_url = os.getenv("DATABASE_URL", "")
    medici_db = os.getenv("MEDICI_DB_URL", "")

    if not db_url and not medici_db:
        warnings.append(
            "Neither DATABASE_URL nor MEDICI_DB_URL is set — "
            "running in offline mode (no live data)"
        )
    elif db_url and not _is_valid_connection_string(db_url):
        errors.append("DATABASE_URL is set but not a valid connection string")
    elif medici_db and not _is_valid_connection_string(medici_db):
        errors.append("MEDICI_DB_URL is set but not a valid connection string")

    # ── Required for deploy ──────────────────────────────────────
    api_key = os.getenv("PREDICTION_API_KEY", "")
    if not api_key:
        warnings.append(
            "PREDICTION_API_KEY not set — API authentication disabled"
        )
    elif len(api_key) < 8:
        warnings.append("PREDICTION_API_KEY is very short — consider a stronger key")

    # ── AI Intelligence (optional — fallback works without it) ───
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    ai_enabled = os.getenv("AI_INTELLIGENCE_ENABLED", "true").lower() in ("true", "1", "yes")

    if ai_enabled and not anthropic_key:
        warnings.append(
            "AI_INTELLIGENCE_ENABLED is true but ANTHROPIC_API_KEY not set — "
            "AI features will fall back to rule-based analysis"
        )
    elif anthropic_key and not anthropic_key.startswith("sk-"):
        warnings.append("ANTHROPIC_API_KEY doesn't start with 'sk-' — verify it's correct")

    # ── Optional external data sources ───────────────────────────
    _optional_keys = {
        "SEATGEEK_CLIENT_ID": "SeatGeek events",
        "FRED_API_KEY": "FRED economic data",
        "PREDICTHQ_API_KEY": "PredictHQ events",
        "MAKCORPS_API_KEY": "Makcorps hotel comparisons",
        "KAGGLE_USERNAME": "Kaggle datasets",
        "KAGGLE_KEY": "Kaggle datasets",
        "SERPAPI_KEY": "SerpAPI search",
        "TICKETMASTER_API_KEY": "Ticketmaster events",
    }

    missing_optional = []
    for key, desc in _optional_keys.items():
        val = os.getenv(key, "")
        if not val:
            missing_optional.append(f"{key} ({desc})")

    if missing_optional:
        warnings.append(
            f"Optional API keys not set — some enrichment sources disabled: "
            f"{', '.join(missing_optional)}"
        )

    # ── Validate numeric env vars ────────────────────────────────
    _numeric_vars = {
        "API_PORT": "8000",
        "CACHE_TTL_HOURS": "24",
        "FORECAST_HORIZON": "30",
        "ANALYTICS_CACHE_TTL_HOURS": "6",
        "TRADING_CACHE_TTL_MINUTES": "5",
        "BOOTSTRAP_N_SAMPLES": "200",
    }

    for key, default in _numeric_vars.items():
        val = os.getenv(key, default)
        try:
            int(val)
        except (ValueError, TypeError):
            errors.append(f"{key}='{val}' is not a valid integer")

    valid = len(errors) == 0
    return {"valid": valid, "warnings": warnings, "errors": errors}


def log_config_report(report: dict) -> None:
    """Log the config validation report at appropriate levels."""
    if report["errors"]:
        for err in report["errors"]:
            logger.error("CONFIG ERROR: %s", err)

    if report["warnings"]:
        for warn in report["warnings"]:
            logger.warning("CONFIG WARNING: %s", warn)

    if report["valid"]:
        n_warn = len(report["warnings"])
        if n_warn:
            logger.info("Config valid with %d warning(s) — running in degraded mode", n_warn)
        else:
            logger.info("Config valid — all systems nominal")
    else:
        logger.error(
            "Config invalid — %d error(s). Fix before deploying to production.",
            len(report["errors"]),
        )


def _is_valid_connection_string(url: str) -> bool:
    """Basic check that a connection string looks plausible."""
    if not url or not url.strip():
        return False
    # Accept common patterns: mssql+pyodbc://, sqlite:///, postgresql://, etc.
    valid_prefixes = ("mssql", "sqlite", "postgresql", "mysql", "Driver=", "Server=")
    return any(url.startswith(p) for p in valid_prefixes)
