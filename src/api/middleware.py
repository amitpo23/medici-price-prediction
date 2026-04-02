"""FastAPI middleware — correlation IDs, request logging, rate limiting."""
from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import FastAPI
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.utils.logging_config import correlation_id_var

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (shared instance — import in routers to decorate endpoints)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# Default limits by endpoint category
RATE_LIMIT_DATA = "100/minute"     # Data endpoints
RATE_LIMIT_AI = "20/minute"        # AI endpoints (Claude API costs)
RATE_LIMIT_EXPORT = "10/minute"    # Export endpoints


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 with Retry-After header."""
    retry_after = getattr(exc, "retry_after", 60)
    logger.warning(
        "Rate limit exceeded: %s %s from %s",
        request.method, request.url.path, get_remote_address(request),
    )
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

def verify_api_key(x_api_key: str) -> bool:
    """Validate an API key against configured keys.

    Supports multiple comma-separated keys via PREDICTION_API_KEY env var.
    Returns True if valid or if no key is configured (open access).
    """
    configured = os.environ.get("PREDICTION_API_KEY", "")
    if not configured:
        return True  # No key configured = open access

    valid_keys = {k.strip() for k in configured.split(",") if k.strip()}
    return x_api_key in valid_keys


# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------

def setup_cors(app: FastAPI) -> None:
    """Add CORS middleware based on CORS_ORIGINS env var."""
    origins_str = os.environ.get("CORS_ORIGINS", "")
    if origins_str:
        origins = [o.strip() for o in origins_str.split(",") if o.strip()]
    else:
        origins = []  # Same-origin only by default

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Api-Key"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )


# ---------------------------------------------------------------------------
# Setup helper — call from main.py
# ---------------------------------------------------------------------------

def warn_if_no_api_key() -> None:
    """Log CRITICAL warning if PREDICTION_API_KEY is not configured."""
    if not os.environ.get("PREDICTION_API_KEY", ""):
        logger.critical(
            "PREDICTION_API_KEY not set — API is OPEN ACCESS. "
            "Set PREDICTION_API_KEY env var for production."
        )


def setup_middleware(app: FastAPI) -> None:
    """Wire up all middleware and rate limiting on the app."""
    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # CORS
    setup_cors(app)

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Scheduler watchdog — restart if dead (checked every request, max once/60s)
    app.add_middleware(SchedulerWatchdogMiddleware)

    # Correlation ID (outermost = runs first)
    app.add_middleware(CorrelationIdMiddleware)

    # Warn if no API key configured
    warn_if_no_api_key()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if os.environ.get("IS_PRODUCTION"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class SchedulerWatchdogMiddleware(BaseHTTPMiddleware):
    """Restart SalesOffice scheduler if it died. Checks at most once per 60 seconds."""

    _last_check: float = 0.0

    async def dispatch(self, request: Request, call_next) -> Response:
        now = time.time()
        if now - SchedulerWatchdogMiddleware._last_check > 60:
            SchedulerWatchdogMiddleware._last_check = now
            try:
                from src.api.routers._shared_state import (
                    _salesoffice_scheduler_allowed,
                    _is_scheduler_running,
                    start_salesoffice_scheduler,
                )
                if _salesoffice_scheduler_allowed() and not _is_scheduler_running():
                    logger.warning("Watchdog: scheduler dead — restarting")
                    start_salesoffice_scheduler()
            except Exception as exc:
                logger.warning("Watchdog: scheduler restart failed: %s", exc)
        return await call_next(request)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Extract or generate X-Request-ID and set it in contextvars.

    - Reads X-Request-ID from incoming request headers.
    - Falls back to a generated UUID4 if not present.
    - Stores in correlation_id_var for access across the request.
    - Echoes the correlation ID back in the response headers.
    - Logs request start (method, path) and end (status, duration).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = correlation_id_var.set(request_id)

        start = time.perf_counter()
        path = request.url.path
        method = request.method

        logger.info("Request started: %s %s", method, path)

        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            logger.error(
                "Request failed: %s %s (%.3fs)",
                method, path, duration,
                exc_info=True,
            )
            raise
        finally:
            correlation_id_var.reset(token)

        duration = time.perf_counter() - start
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed: %s %s → %d (%.3fs)",
            method, path, response.status_code, duration,
        )

        return response
