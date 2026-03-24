"""GMCVB Official Benchmarks — Miami-Dade hotel market data.

Source: Greater Miami Convention & Visitors Bureau
URL: https://www.miamiandbeaches.com/gmcvb-partners/research-statistics-reporting
Updated: Weekly (manually or via scraper)

These benchmarks feed the official_benchmark voter in the consensus engine.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Official ADR by zone — updated from GMCVB weekly reports
# Last updated: 2026-03-24 (week ending Mar 14, 2026)
OFFICIAL_ADR = {
    "miami_dade": 315.14,       # County-wide ADR
    "south_beach": 380.0,       # South Beach area estimate
    "mid_beach": 420.0,         # Mid-Beach luxury strip
    "downtown": 220.0,          # Downtown Miami
    "brickell": 280.0,          # Brickell financial district
    "airport": 150.0,           # Airport/Doral area
    "sunny_isles": 300.0,       # North Beach/Sunny Isles
}

OFFICIAL_OCCUPANCY = {
    "miami_dade": 87.3,         # County-wide occupancy %
}

OFFICIAL_REVPAR = {
    "miami_dade": 275.04,       # County-wide RevPAR
}


def get_official_adr(zone: str) -> float:
    """Get official ADR for a zone. Returns 0 if not available."""
    return OFFICIAL_ADR.get(zone, 0)


def get_market_summary() -> dict:
    """Get full market summary."""
    return {
        "adr": OFFICIAL_ADR,
        "occupancy": OFFICIAL_OCCUPANCY,
        "revpar": OFFICIAL_REVPAR,
        "source": "GMCVB Miami & Miami Beach",
        "last_updated": "2026-03-24",
    }
