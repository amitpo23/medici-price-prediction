"""Tests for the pagination model and utilities."""
from __future__ import annotations

import pytest

from src.api.models.pagination import paginate


# ── paginate() core logic ────────────────────────────────────────────


class TestPaginate:
    """Test the paginate() helper function."""

    def _items(self, n: int) -> list[dict]:
        """Generate n sample items."""
        return [{"id": i, "name": f"item_{i}"} for i in range(n)]

    def test_basic_first_page(self):
        """First page returns correct slice and metadata."""
        items = self._items(50)
        result = paginate(items, limit=10, offset=0)
        assert len(result["items"]) == 10
        assert result["total"] == 50
        assert result["limit"] == 10
        assert result["offset"] == 0
        assert result["has_more"] is True
        assert result["items"][0]["id"] == 0
        assert result["items"][9]["id"] == 9

    def test_second_page(self):
        """Second page starts at correct offset."""
        items = self._items(50)
        result = paginate(items, limit=10, offset=10)
        assert len(result["items"]) == 10
        assert result["offset"] == 10
        assert result["has_more"] is True
        assert result["items"][0]["id"] == 10
        assert result["items"][9]["id"] == 19

    def test_last_page(self):
        """Last page has fewer items and has_more=False."""
        items = self._items(25)
        result = paginate(items, limit=10, offset=20)
        assert len(result["items"]) == 5
        assert result["has_more"] is False
        assert result["total"] == 25

    def test_exact_page_boundary(self):
        """When total is exact multiple of limit, last page has has_more=False."""
        items = self._items(20)
        result = paginate(items, limit=10, offset=10)
        assert len(result["items"]) == 10
        assert result["has_more"] is False

    def test_offset_beyond_total(self):
        """Offset beyond total returns empty items list."""
        items = self._items(10)
        result = paginate(items, limit=10, offset=100)
        assert result["items"] == []
        assert result["total"] == 10
        assert result["has_more"] is False

    def test_single_item(self):
        """Single item list returns correctly."""
        items = self._items(1)
        result = paginate(items, limit=100, offset=0)
        assert len(result["items"]) == 1
        assert result["total"] == 1
        assert result["has_more"] is False

    def test_empty_list(self):
        """Empty list returns empty result."""
        result = paginate([], limit=10, offset=0)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["has_more"] is False

    def test_limit_larger_than_total(self):
        """Limit larger than total returns all items."""
        items = self._items(5)
        result = paginate(items, limit=100, offset=0)
        assert len(result["items"]) == 5
        assert result["has_more"] is False

    def test_return_all_flag(self):
        """return_all=True bypasses pagination."""
        items = self._items(500)
        result = paginate(items, limit=10, offset=50, return_all=True)
        assert len(result["items"]) == 500
        assert result["total"] == 500
        assert result["has_more"] is False
        assert result["_all"] is True

    def test_return_all_empty_list(self):
        """return_all=True with empty list."""
        result = paginate([], limit=10, offset=0, return_all=True)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["_all"] is True

    def test_large_dataset(self):
        """Pagination handles large dataset correctly."""
        items = self._items(3000)
        result = paginate(items, limit=100, offset=2900)
        assert len(result["items"]) == 100
        assert result["has_more"] is False
        assert result["items"][0]["id"] == 2900

    def test_items_not_mutated(self):
        """Original list is not modified by pagination."""
        items = self._items(50)
        original_len = len(items)
        paginate(items, limit=10, offset=0)
        assert len(items) == original_len

    def test_offset_zero_limit_one(self):
        """Single item per page works."""
        items = self._items(5)
        result = paginate(items, limit=1, offset=0)
        assert len(result["items"]) == 1
        assert result["has_more"] is True
        assert result["items"][0]["id"] == 0

    def test_sequential_pages_cover_all_items(self):
        """Iterating through all pages returns every item exactly once."""
        items = self._items(23)
        limit = 5
        all_collected = []
        offset = 0
        while True:
            result = paginate(items, limit=limit, offset=offset)
            all_collected.extend(result["items"])
            if not result["has_more"]:
                break
            offset += limit
        assert len(all_collected) == 23
        assert [item["id"] for item in all_collected] == list(range(23))


# ── pagination_params dependency ─────────────────────────────────────


class TestPaginationParams:
    """Test the FastAPI dependency function with explicit values (as FastAPI would inject)."""

    def test_custom_values(self):
        from src.api.models.pagination import pagination_params
        result = pagination_params(limit=50, offset=200, all=True)
        assert result == {"limit": 50, "offset": 200, "all": True}

    def test_explicit_defaults(self):
        from src.api.models.pagination import pagination_params
        result = pagination_params(limit=100, offset=0, all=False)
        assert result == {"limit": 100, "offset": 0, "all": False}
