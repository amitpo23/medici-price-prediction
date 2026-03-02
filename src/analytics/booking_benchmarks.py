"""Booking behavior benchmarks — Miami hotel market + Kaggle hotel-booking-dataset.

Sources:
- Seasonality & ADR: STR/CoStar 2024 (Miami-Dade County)
- Cancel rates & lead-time ratios: Kaggle hotel-booking-demand (117,429 bookings 2015-2017)
- Submarket ADR: STR/CoStar 2024 by submarket

Provides:
- Seasonality index (monthly ADR relative to annual average) — Miami-specific
- Lead time vs cancellation model
- Market segment benchmarks
- Weekend premium and room type change rates

NOTE: Embedded as Python dict so Azure deployment works without the data/ directory.
      The JSON file (data/booking_benchmarks.json) overrides the embedded data when present.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_BENCHMARKS_FILE = _DATA_DIR / "booking_benchmarks.json"

# Embedded Miami market data — primary source for Azure deployment
# (data/ directory is excluded from deploy.zip, so this dict is the fallback)
_EMBEDDED_DATA: dict = {
    "source": "Miami hotel market — STR/CoStar 2024 + Hotel Booking Demand dataset (Kaggle, 117,429 bookings 2015-2017)",
    "base_market": "Miami-Dade County",
    "seasonality_note": "Miami-specific: peak = Jan-Feb-Dec (snowbird/winter tourism), trough = Sep (hurricane season)",
    "total_bookings": 117429,
    "years": "2015-2017 (Kaggle cancel rates) + 2024 (Miami ADR/seasonality)",
    "hotel_types": {"City Hotel": 78121, "Resort Hotel": 39308},
    # Miami seasonality (inverted vs Europe — peak = Jan/Feb/Dec, trough = Sep)
    # Source: Kayak 2023-2024 monthly ADR / STR annual avg $222.12
    "seasonality_index": {
        "January": 1.056, "February": 1.099, "March": 1.014, "April": 0.972,
        "May": 0.930, "June": 0.887, "July": 0.908, "August": 0.887,
        "September": 0.845, "October": 0.866, "November": 0.930, "December": 1.099,
    },
    # Lead-time buckets: cancel rates from Kaggle CSV; ADR calibrated to Miami
    # Formula: Miami base $222.12 × (European bucket ADR / European overall avg $104.11)
    "lead_time_buckets": {
        "0-7d":    {"cancel_rate": 0.097, "avg_adr": 207.46, "bookings": 18608},
        "8-30d":   {"cancel_rate": 0.281, "avg_adr": 234.72, "bookings": 18651},
        "31-60d":  {"cancel_rate": 0.366, "avg_adr": 228.78, "bookings": 16819},
        "61-90d":  {"cancel_rate": 0.397, "avg_adr": 229.31, "bookings": 12487},
        "91-180d": {"cancel_rate": 0.449, "avg_adr": 234.08, "bookings": 26311},
        "181-365d": {"cancel_rate": 0.556, "avg_adr": 204.11, "bookings": 21424},
    },
    "weekend_premium_pct": 4.3,
    "city_hotel_benchmarks": {
        "avg_adr": 222.12,       # Miami STR/CoStar full-year 2024
        "median_adr": 210.0,
        "cancel_rate": 0.422,
        "avg_lead_time_days": 111.0,
        "repeat_guest_rate": 0.021,
        "avg_booking_changes": 0.18,
        "room_change_rate": 0.087,
    },
    # Market segment data from Kaggle (relative ratios directionally valid for Miami)
    "market_segment_adr": {
        "Aviation": 102.74, "Corporate": 70.45, "Direct": 117.69,
        "Groups": 80.51, "Offline TA/TO": 88.35, "Online TA": 117.96,
    },
    "market_segment_cancel": {
        "Aviation": 0.221, "Corporate": 0.189, "Direct": 0.154,
        "Groups": 0.617, "Offline TA/TO": 0.346, "Online TA": 0.369,
    },
    "miami_market_2024": {
        "annual_adr": 222.12,
        "annual_occupancy_pct": 73.9,
        "annual_revpar": 164.10,
        "airbnb_adr": 197.0,
        "airbnb_occupancy_pct": 69.0,
        "airbnb_revpar": 136.0,
        "peak_months": ["January", "February", "December"],
        "trough_month": "September",
        "source": "STR/CoStar 2024 + Airbtics Nov2024-Oct2025",
    },
}

# Cache
_benchmarks: dict | None = None


def _load_benchmarks() -> dict:
    """Load benchmarks — JSON file overrides embedded data when present."""
    global _benchmarks
    if _benchmarks is not None:
        return _benchmarks

    if _BENCHMARKS_FILE.exists():
        try:
            with open(_BENCHMARKS_FILE, encoding="utf-8") as f:
                _benchmarks = json.load(f)
            logger.info(
                "Loaded booking benchmarks from file: %d bookings, %s",
                _benchmarks.get("total_bookings", 0),
                _benchmarks.get("source", "unknown"),
            )
            return _benchmarks
        except Exception as exc:
            logger.warning("Failed to load benchmarks file, using embedded data: %s", exc)

    _benchmarks = _EMBEDDED_DATA
    logger.info(
        "Using embedded Miami booking benchmarks: %d bookings",
        _benchmarks.get("total_bookings", 0),
    )
    return _benchmarks


def get_seasonality_index(month: str) -> float:
    """Get ADR seasonality index for a month.

    Returns multiplier relative to annual average (1.0 = average).
    Miami: Feb/Dec = 1.099 (peak snowbird season), Sep = 0.845 (hurricane trough).
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
    0-7 days: 9.7%, 181-365 days: 55.6%
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
    """Get benchmarks for City Hotels (Miami STR/CoStar 2024).

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
        "miami_market_2024": bm.get("miami_market_2024", {}),
    }
