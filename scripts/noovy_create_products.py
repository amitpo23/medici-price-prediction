"""Create missing Products via Noovy UI (app.noovy.com) — PROVEN WORKING.

Flow per product:
1. Click "+ New Product"
2. Click Product Type → Room
3. Fill Name, Short Name, BasePrice=500, Occupancy=2
4. Click Currency Open → US Dollar
5. Re-click Product Type → Room (MUI quirk: loses value after currency)
6. Click Locations tab (auto-filled with current venue)
7. Click Save

Usage:
  python3 scripts/noovy_create_products.py                    # All venues
  python3 scripts/noovy_create_products.py --venue 5080       # Single venue
  python3 scripts/noovy_create_products.py --dry-run          # Preview only
"""
import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright

ACCOUNT = os.getenv("NOOVY_ACCOUNT", "Medici LIVE")
USER = os.getenv("NOOVY_USER", "zvi")
PASSWORD = os.getenv("NOOVY_PASS", "karpad66")

MISSING_PRODUCTS = {
    5073: {"name": "Loews Miami Beach", "missing": ["DLX"]},
    5075: {"name": "Villa Casa Casuarina", "missing": ["Suite"]},
    5077: {"name": "SLS LUX Brickell", "missing": ["SPR"]},
    5079: {"name": "citizenM Brickell", "missing": ["DLX", "SPR", "Suite"]},
    5080: {"name": "Pullman Miami Airport", "missing": []},  # DONE
    5081: {"name": "Embassy Suites", "missing": ["DLX", "SPR", "DRM"]},
    5083: {"name": "Hilton Miami Airport", "missing": ["DRM"]},
    5084: {"name": "Hilton Downtown", "missing": ["DLX", "SPR"]},
    5089: {"name": "Fairwind Hotel", "missing": ["SPR", "Suite"]},
    5090: {"name": "Dream South Beach", "missing": ["DLX", "SPR"]},
    5092: {"name": "Iberostar Berkeley", "missing": ["SPR", "APT"]},
    5093: {"name": "Hilton Bentley SB", "missing": ["SPR", "APT"]},
    5095: {"name": "Cadet Hotel", "missing": ["DLX", "SPR"]},
    5096: {"name": "Marseilles Hotel", "missing": ["DLX", "SPR", "DRM"]},
    5097: {"name": "Hyatt Centric SB", "missing": ["SPR", "Suite"]},
    5098: {"name": "Eurostars Langford", "missing": ["SPR", "APT", "DRM", "EXEC"]},
    5100: {"name": "Crystal Beach Suites", "missing": ["Stnd", "DLX", "SPR"]},
    5101: {"name": "Atwell Suites Brickell", "missing": ["DLX", "SPR"]},
    5103: {"name": "Savoy Hotel", "missing": ["SPR"]},
    5104: {"name": "Sole Miami", "missing": ["DLX", "SPR"]},
    5105: {"name": "MB Hotel", "missing": ["SPR"]},
    5107: {"name": "Freehand Miami", "missing": ["DLX", "DRM"]},
    5108: {"name": "Gabriel South Beach", "missing": ["SPR"]},
    5109: {"name": "Riu Plaza Miami Beach", "missing": ["SPR", "Suite"]},
    5110: {"name": "Breakwater South Beach", "missing": ["APT"]},
    5115: {"name": "Hilton Cabana", "missing": ["DRM"]},
    5117: {"name": "Albion Hotel", "missing": ["DLX", "APT", "DRM"]},
    5124: {"name": "Grand Beach Hotel", "missing": ["Suite"]},
    5130: {"name": "Holiday Inn Express", "missing": ["Suite"]},
    5131: {"name": "Hotel Croydon", "missing": ["Suite"]},
    5136: {"name": "Kimpton Anglers", "missing": ["DLX", "APT", "Suite"]},
    5139: {"name": "SERENA Aventura", "missing": ["DLX", "SPR", "Suite"]},
    5265: {"name": "Hotel Belleza", "missing": ["Stnd", "SPR", "DBL"]},
    5266: {"name": "Dorchester Hotel", "missing": ["Stnd", "Suite", "APT", "DBL"]},
    5267: {"name": "Gale South Beach", "missing": ["1QSR"]},
    5268: {"name": "Fontainebleau", "missing": ["Stnd", "DLX", "Suite", "APT", "OV2Q"]},
    5274: {"name": "Generator Miami", "missing": ["DLX", "SPR", "Suite", "DRM"]},
    5276: {"name": "InterContinental Miami", "missing": ["DLX", "Suite"]},
    5278: {"name": "Gale Miami Hotel", "missing": ["Suite", "APT"]},
}

ITC_TO_NAME = {
    "Stnd": ("Standard", "Stnd"),
    "DLX": ("Deluxe", "DLX"),
    "Suite": ("Suite", "Suite"),
    "SPR": ("Superior", "SPR"),
    "APT": ("Apartment", "APT"),
    "DRM": ("Dormitory", "DRM"),
    "EXEC": ("Executive", "EXEC"),
    "DBL": ("Double", "DBL"),
    "OV2Q": ("Ocean View", "OV2Q"),
    "1QSR": ("Queen Standard", "1QSR"),
}


async def switch_venue(page, venue_id, venue_name):
    """Switch Noovy venue context via sidebar dropdown."""
    # Click the hotel dropdown in sidebar
    dropdown = page.locator('text=Hotel').first
    # Use direct navigation instead
    await page.evaluate(f"""() => {{
        document.cookie = 'hotelId={venue_id}; path=/';
    }}""")
    await page.goto("https://app.noovy.com/products")
    await page.wait_for_timeout(2000)

    # Verify venue
    body = await page.text_content("body")
    if str(venue_id) in body or venue_name.split()[0] in body:
        return True

    # Try clicking venue selector
    try:
        selector = page.locator(f'text="{venue_name}"').first
        if await selector.count() > 0:
            return True
    except Exception:
        pass

    return False


async def create_product(page, product_name, short_name):
    """Create a single product in current venue. Returns True on success."""

    # 1. Click New Product
    new_btn = page.get_by_text("New Product").last
    await new_btn.click()
    await page.wait_for_timeout(800)

    # 2. Product Type = Room (MUI Select — must click then pick option)
    pt_combo = page.locator('[id*="productType"]').first
    await pt_combo.click()
    await page.wait_for_timeout(400)
    room_opt = page.locator('[role="option"]', has_text="Room")
    await room_opt.click()
    await page.wait_for_timeout(400)

    # 3. Fill text fields
    await page.get_by_role("textbox", name="Name", exact=True).fill(product_name)
    await page.get_by_role("textbox", name="Short Name").fill(short_name)
    await page.get_by_role("textbox", name="BasePrice").fill("500")
    await page.get_by_role("textbox", name="Basic Occupancy").fill("2")

    # 4. Currency = USD (click Open button → select US Dollar)
    open_btns = page.get_by_role("button", name="Open")
    await open_btns.first.click()
    await page.wait_for_timeout(500)
    usd_opt = page.locator('[role="option"]', has_text="US Dollar")
    if await usd_opt.count() > 0:
        await usd_opt.click()
        await page.wait_for_timeout(300)
    else:
        # Close dropdown and try without currency change
        await page.keyboard.press("Escape")

    # 5. Re-select Product Type = Room (MUI loses it after currency)
    pt_check = await page.evaluate('() => document.querySelector("input[name=\\"general.productType\\"]")?.value || ""')
    if not pt_check:
        pt_combo2 = page.locator('[id*="productType"]').first
        await pt_combo2.click()
        await page.wait_for_timeout(300)
        room_opt2 = page.locator('[role="option"]', has_text="Room")
        if await room_opt2.count() > 0:
            await room_opt2.click()
            await page.wait_for_timeout(300)

    # 6. Click Locations tab
    loc_tab = page.get_by_role("tab", name="Locations")
    await loc_tab.click()
    await page.wait_for_timeout(500)

    # 7. Click Save
    save_btn = page.get_by_role("button", name="Save")
    if await save_btn.is_disabled():
        # Try re-selecting Product Type one more time
        gen_tab = page.get_by_role("tab", name="General")
        await gen_tab.click()
        await page.wait_for_timeout(300)
        pt_combo3 = page.locator('[id*="productType"]').first
        await pt_combo3.click()
        await page.wait_for_timeout(300)
        room_opt3 = page.locator('[role="option"]', has_text="Room")
        if await room_opt3.count() > 0:
            await room_opt3.click()
            await page.wait_for_timeout(300)
        await loc_tab.click()
        await page.wait_for_timeout(500)

    if await save_btn.is_disabled():
        print(f"    WARN: Save still disabled for {product_name}")
        # Force close dialog
        close_btn = page.locator("dialog button").first
        if await close_btn.count() > 0:
            await close_btn.click()
        return False

    await save_btn.click()
    await page.wait_for_timeout(2000)

    return True


async def main():
    dry_run = "--dry-run" in sys.argv
    venue_filter = None
    if "--venue" in sys.argv:
        idx = sys.argv.index("--venue")
        venue_filter = int(sys.argv[idx + 1])

    venues = {k: v for k, v in MISSING_PRODUCTS.items() if v["missing"]}
    if venue_filter:
        venues = {k: v for k, v in venues.items() if k == venue_filter}

    total = sum(len(v["missing"]) for v in venues.values())
    print(f"{'DRY RUN' if dry_run else 'CREATING'} — {total} products across {len(venues)} venues\n")

    if dry_run:
        for vid, info in venues.items():
            print(f"  {vid} {info['name']}:")
            for itc in info["missing"]:
                name, short = ITC_TO_NAME.get(itc, (itc, itc))
                print(f"    + {name} ({short})")
        print(f"\nRun without --dry-run to create.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()

        # Login
        print("Logging in to Noovy...")
        await page.goto("https://app.noovy.com")
        await page.wait_for_timeout(2000)
        await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
        await page.get_by_role("textbox", name="User Name").fill(USER)
        await page.get_by_role("textbox", name="Password").fill(PASSWORD)
        await page.locator('[data-test-id="login-form-submit"]').click()
        await page.wait_for_timeout(3000)
        print("Logged in.\n")

        report = {"created": [], "skipped": [], "errors": []}

        for vid, info in venues.items():
            print(f"--- {vid} {info['name']} ({len(info['missing'])} products) ---")

            # Switch venue
            await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")
            await page.goto("https://app.noovy.com/products")
            await page.wait_for_timeout(2000)

            # Read existing products
            existing = await page.evaluate("""() => {
                const rows = document.querySelectorAll('table tbody tr');
                return [...rows].map(r => r.querySelectorAll('td')[1]?.textContent?.trim()?.toLowerCase()).filter(Boolean);
            }""")

            for itc in info["missing"]:
                name, short = ITC_TO_NAME.get(itc, (itc, itc))

                if name.lower() in existing:
                    print(f"  SKIP: {name} already exists")
                    report["skipped"].append({"venue": vid, "product": name})
                    continue

                print(f"  CREATE: {name} ({short})...", end=" ")

                try:
                    ok = await create_product(page, name, short)

                    if ok:
                        # Verify
                        await page.wait_for_timeout(1000)
                        products_after = await page.evaluate("""() => {
                            const rows = document.querySelectorAll('table tbody tr');
                            return [...rows].map(r => r.querySelectorAll('td')[1]?.textContent?.trim()?.toLowerCase()).filter(Boolean);
                        }""")

                        if name.lower() in products_after:
                            print("OK ✓")
                            report["created"].append({"venue": vid, "hotel": info["name"], "product": name, "itc": itc})
                            existing.append(name.lower())
                        else:
                            print("NOT FOUND after save")
                            report["errors"].append({"venue": vid, "product": name, "error": "not found after save"})
                    else:
                        print("FAILED (Save disabled)")
                        report["errors"].append({"venue": vid, "product": name, "error": "save disabled"})

                except Exception as e:
                    print(f"ERROR: {e}")
                    report["errors"].append({"venue": vid, "product": name, "error": str(e)[:100]})
                    # Try to recover — close dialog if open
                    try:
                        close = page.locator("dialog button").first
                        if await close.count() > 0:
                            await close.click()
                            await page.wait_for_timeout(500)
                    except Exception:
                        pass

        # Summary
        print(f"\n{'='*60}")
        print(f"Created: {len(report['created'])}")
        print(f"Skipped: {len(report['skipped'])}")
        print(f"Errors:  {len(report['errors'])}")
        print(f"{'='*60}")

        for r in report["created"]:
            print(f"  ✓ {r['venue']} {r['hotel']}: {r['product']}")
        for r in report["errors"]:
            print(f"  ✗ {r['venue']}: {r['product']} — {r['error']}")

        # Save report
        report_path = "scripts/noovy_create_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport: {report_path}")

        await ctx.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
