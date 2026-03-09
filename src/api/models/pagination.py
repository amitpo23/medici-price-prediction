"""Shared pagination utilities for API endpoints."""
from __future__ import annotations

from fastapi import Query


# ---------------------------------------------------------------------------
# Pagination dependency
# ---------------------------------------------------------------------------

def pagination_params(
    limit: int = Query(100, ge=1, le=1000, description="Items per page (1-1000)"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    all: bool = Query(False, alias="all", description="Return all items (bypass pagination)"),
) -> dict:
    """FastAPI dependency that extracts and validates pagination params."""
    return {"limit": limit, "offset": offset, "all": all}


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def paginate(items: list, limit: int, offset: int, return_all: bool = False) -> dict:
    """Slice a list and return a PaginatedResponse-shaped dict.

    Returns:
        dict with keys: items, total, limit, offset, has_more
        If return_all is True, returns all items with a
        X-Pagination-Warning flag.
    """
    total = len(items)

    if return_all:
        return {
            "items": items,
            "total": total,
            "limit": total,
            "offset": 0,
            "has_more": False,
            "_all": True,
        }

    end = offset + limit
    page = items[offset:end]
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": end < total,
    }
