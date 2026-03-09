"""Export endpoints — CSV exports and weekly summary."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.api.middleware import limiter, RATE_LIMIT_EXPORT

export_router = APIRouter()


@export_router.get("/export/csv/contracts")
@limiter.limit(RATE_LIMIT_EXPORT)
def salesoffice_export_contracts(request: Request):
    """CSV export of contract price history."""
    from src.analytics.export_engine import export_contracts_csv

    try:
        csv_data = export_contracts_csv()
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=medici_contracts.csv"},
        )
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Export failed: {e}")


@export_router.get("/export/csv/providers")
@limiter.limit(RATE_LIMIT_EXPORT)
def salesoffice_export_providers(request: Request):
    """CSV export of provider pricing data."""
    from src.analytics.export_engine import export_providers_csv

    try:
        csv_data = export_providers_csv()
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=medici_providers.csv"},
        )
    except (OSError, ConnectionError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Export failed: {e}")


@export_router.get("/export/summary")
@limiter.limit(RATE_LIMIT_EXPORT)
def salesoffice_export_summary(request: Request, fmt: str = "json"):
    """Weekly summary digest — JSON or plain text. Use ?fmt=text for plain text."""
    from src.analytics.export_engine import generate_weekly_summary, generate_summary_text

    try:
        summary = generate_weekly_summary()
        if fmt == "text":
            text = generate_summary_text(summary)
            return PlainTextResponse(content=text)
        return JSONResponse(content=summary)
    except (ValueError, TypeError, KeyError, OSError) as e:
        raise HTTPException(status_code=503, detail=f"Summary generation failed: {e}")
