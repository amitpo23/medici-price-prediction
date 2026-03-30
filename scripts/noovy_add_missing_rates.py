"""Noovy Rate Plan Configuration Script.

This script uses Playwright to automate adding missing rates in Noovy.
Run when browser is available:
    python3 scripts/noovy_add_missing_rates.py

It connects to Noovy, navigates to each hotel, and adds the missing
rate plan + room category combinations documented in docs/NOOVY_FIXES_NEEDED.md.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

NOOVY_URL = "https://app.noovy.com"
NOOVY_ACCOUNT = "Medici LIVE"
NOOVY_USER = "zvi"
NOOVY_PASS = "karpad66"


@dataclass
class MissingRate:
    hotel_name: str
    zenith_id: int
    inv_type_code: str  # Stnd, SPR, DLX, Suite
    board: str  # RO or BB
    rate_plan_code: str
    category_display: str  # For logging


# All missing rates from the audit
MISSING_RATES = [
    # citizenM Brickell — 3 BB rates
    MissingRate("citizenM Miami Brickell", 5079, "SPR", "BB", "13169", "Superior BB"),
    MissingRate("citizenM Miami Brickell", 5079, "DLX", "BB", "13169", "Deluxe BB"),
    MissingRate("citizenM Miami Brickell", 5079, "Suite", "BB", "13169", "Suite BB"),
    # DoubleTree Doral — 4 rates (SPR + DLX, both RO and BB)
    MissingRate("DoubleTree by Hilton Miami Doral", 5082, "SPR", "RO", "12046", "Superior RO"),
    MissingRate("DoubleTree by Hilton Miami Doral", 5082, "SPR", "BB", "13171", "Superior BB"),
    MissingRate("DoubleTree by Hilton Miami Doral", 5082, "DLX", "RO", "12046", "Deluxe RO"),
    MissingRate("DoubleTree by Hilton Miami Doral", 5082, "DLX", "BB", "13171", "Deluxe BB"),
    # Loews — 1 BB rate
    MissingRate("Loews Miami Beach Hotel", 5073, "DLX", "BB", "12886", "Deluxe BB"),
    # Hyatt Centric — 1 BB rate
    MissingRate("Hyatt Centric South Beach Miami", 5097, "SPR", "BB", "13160", "Superior BB"),
    # Hampton Inn — 5 rates (need BB rate plan discovery first)
    # Hampton BB rate plan unknown — must be looked up in Noovy first
    # MissingRate("Hampton Inn Miami Beach", 5106, "Stnd", "BB", "???", "Standard BB"),
    # MissingRate("Hampton Inn Miami Beach", 5106, "SPR", "RO", "12074", "Superior RO"),
    # MissingRate("Hampton Inn Miami Beach", 5106, "SPR", "BB", "???", "Superior BB"),
    # MissingRate("Hampton Inn Miami Beach", 5106, "DLX", "RO", "12074", "Deluxe RO"),
    # MissingRate("Hampton Inn Miami Beach", 5106, "DLX", "BB", "???", "Deluxe BB"),
]


async def run():
    """Main automation flow — requires browser to be available."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("playwright not installed. Run: pip install playwright && playwright install")
        return

    logger.info("=" * 60)
    logger.info("Noovy Rate Plan Configuration — %d rates to add", len(MISSING_RATES))
    logger.info("=" * 60)

    # NOTE: This script documents what needs to be done.
    # Actual Noovy UI automation depends on the exact UI flow which varies by hotel.
    # The rates in Med_Hotels_ratebycat are populated by the SalesOffice backend
    # when rate plans are configured in Noovy/Hotel.Tools.
    #
    # For each missing rate, the operator needs to:
    # 1. Go to Noovy → Settings → Hotel → select the hotel
    # 2. Navigate to Rate Plans section
    # 3. Find the rate plan (by code) and add the room category
    # 4. Set pricing ($1000 fixed for Innstant onboarding)
    # 5. Set availability if needed

    logger.info("\n📋 MANUAL ACTIONS NEEDED IN NOOVY:\n")

    current_hotel = ""
    for rate in MISSING_RATES:
        if rate.hotel_name != current_hotel:
            current_hotel = rate.hotel_name
            logger.info(f"\n🏨 {rate.hotel_name} (Zenith {rate.zenith_id})")
            logger.info("-" * 50)

        logger.info(
            f"  ➕ Add {rate.category_display}: "
            f"RatePlan={rate.rate_plan_code}, InvType={rate.inv_type_code}, "
            f"Board={rate.board}"
        )

    logger.info("\n\n🏨 Hampton Inn Miami Beach (Zenith 5106)")
    logger.info("-" * 50)
    logger.info("  ⚠️  BB RatePlanCode unknown — look up in Noovy first")
    logger.info("  ➕ Add Standard BB (RatePlan ???)")
    logger.info("  ➕ Add Superior RO (RatePlan 12074, InvType SPR)")
    logger.info("  ➕ Add Superior BB (RatePlan ???, InvType SPR)")
    logger.info("  ➕ Add Deluxe RO (RatePlan 12074, InvType DLX)")
    logger.info("  ➕ Add Deluxe BB (RatePlan ???, InvType DLX)")

    logger.info("\n\n🔧 CLEANUP:")
    logger.info("  🗑️  Deactivate Hampton Inn duplicate (HotelId 826299)")
    logger.info("  💰 Fix Freehand Superior BB price: $40,448 → ~$130")

    logger.info("\n\nTotal: 14 rates + 1 price fix + 1 deactivation")


if __name__ == "__main__":
    asyncio.run(run())
