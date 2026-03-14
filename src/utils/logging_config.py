"""Structured JSON logging configuration with correlation IDs.

Configures all loggers to emit JSON-formatted log lines with standard fields:
timestamp, level, module, function, message, correlation_id.

Usage:
    from src.utils.logging_config import configure_logging
    configure_logging()  # Call once at app startup
"""
from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar

try:
    import resource
except ImportError:  # pragma: no cover - non-Unix fallback
    resource = None

from pythonjsonlogger.json import JsonFormatter

# Context variable for request correlation ID (set by middleware)
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationJsonFormatter(JsonFormatter):
    """JSON formatter that injects correlation_id from contextvars."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["correlation_id"] = correlation_id_var.get("")
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        memory_snapshot = _get_process_memory_snapshot()
        if memory_snapshot is not None:
            log_record.update(memory_snapshot)


def _get_process_memory_snapshot() -> dict[str, float] | None:
    """Return normalized process memory usage fields for structured logs."""
    if resource is None:
        return None

    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
    except (AttributeError, OSError, ValueError):
        return None

    rss_raw = float(getattr(usage, "ru_maxrss", 0.0) or 0.0)
    if rss_raw <= 0:
        return None

    divisor = 1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
    rss_mb = round(rss_raw / divisor, 2)
    return {"memory_rss_mb": rss_mb}


def configure_logging() -> None:
    """Configure root logger with JSON formatter.

    Reads LOG_LEVEL from environment (default: INFO).
    Replaces any existing handlers on the root logger.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    formatter = CorrelationJsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
