"""Booking behavior benchmarks from hotel-booking-dataset.

Source: github.com/mpolinowski/hotel-booking-dataset
Based on 117,429 bookings across City Hotels and Resort Hotels (2015-2017).

Provides:
- Seasonality index (monthly ADR relative to annual average)
- Lead time vs cancellation model
- Market segment benchmarks
- Weekend premium and room type change rates
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_BENCHMARKS_FILE = _DATA_DIR / "booking_benchmarks.json"

# Cache
_benchmarks: dict | None = None


def _load_benchmarks() -> dict:
    """Load benchmarks from JSON file."""
    global _benchmarks
    if _benchmarks is not None:
        return _benchmarks

    if not _BENCHMARKS_FILE.exists():
        logger.warning("Benchmarks file not found: %s", _BENCHMARKS_FILE)
        _benchmarks = {}
        return _benchmarks

    with open(_BENCHMARKS_FILE, encoding="utf-8") as f:
        _benchmarks = json.load(f)

    logger.info(
        "Loaded booking benchmarks: %d bookings, %s",
        _benchmarks.get("total_bookings", 0),
        _benchmarks.get("source", "unknown"),
    )
    return _benchmarks


def get_seasonality_index(month: str) -> float:
    """Get ADR seasonality index for a month.

    Returns multiplier relative to annual average (1.0 = average).
    E.g. August = 1.37 (37% above average), January = 0.695 (30% below).
    """
    bm = _load_benchmarks()
    return bm.get("seasonality_index", {}).get(month, 1.0)


def get_seasonality_all() -> dict[str, float]:
    """Get seasonality index for all months."""
    bm = _load_benchmarks()
    return bm.get("seasonality_index", {})


def get_cancel_probability(lead_time_days: int) -> float:
    """Estimate cancellation probability based on lead time.

    Based on 117K bookings. Key insight: longer lead = higher cancel risk.
    0-7 days: 9.6%, 181-365 days: 55.5%
    """
    bm = _load_benchmarks()
    buckets = bm.get("lead_time_buckets", {})

    if lead_time_days <= 7:
        return buckets.get("0-7d", {}).get("cancel_rate", 0.10)
    if lead_time_days <= 30:
        return buckets.get("8-30d", {}).get("cancel_rate", 0.28)
    if lead_time_days <= 60:
        return buckets.get("31-60d", {}).get("cancel_rate", 0.36)
    if lead_time_days <= 90:
        return buckets.get("61-90d", {}).get("cancel_rate", 0.40)
    if lead_time_days <= 180:
        return buckets.get("91-180d", {}).get("cancel_rate", 0.45)
    return buckets.get("181-365d", {}).get("cancel_rate", 0.56)


def get_city_hotel_benchmarks() -> dict:
    """Get benchmarks for City Hotels (closest to our Miami hotels).

    Returns avg ADR, cancel rate, lead time, repeat guest rate, etc.
    """
    bm = _load_benchmarks()
    return bm.get("city_hotel_benchmarks", {})


def get_market_segment_benchmarks() -> dict:
    """Get ADR and cancel rates by market segment."""
    bm = _load_benchmarks()
    adr = bm.get("market_segment_adr", {})
    cancel = bm.get("market_segment_cancel", {})
    return {
        seg: {"avg_adr": adr.get(seg, 0), "cancel_rate": cancel.get(seg, 0)}
        for seg in set(list(adr.keys()) + list(cancel.keys()))
    }


def get_benchmarks_summary() -> dict:
    """Full benchmarks summary for API/dashboard."""
    bm = _load_benchmarks()
    if not bm:
        return {"status": "no_data"}

    return {
        "status": "ok",
        "source": bm.get("source", ""),
        "total_bookings": bm.get("total_bookings", 0),
        "years": bm.get("years", ""),
        "seasonality": bm.get("seasonality_index", {}),
        "lead_time_buckets": bm.get("lead_time_buckets", {}),
        "weekend_premium_pct": bm.get("weekend_premium_pct", 0),
        "city_hotel": bm.get("city_hotel_benchmarks", {}),
        "market_segments": get_market_segment_benchmarks(),
    }
