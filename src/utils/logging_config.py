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
from contextvars import ContextVar

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
