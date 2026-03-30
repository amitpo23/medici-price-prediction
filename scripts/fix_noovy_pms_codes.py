"""Fix PMS codes for all blocked hotels in Noovy.

Automates: Login → switch hotel → Products → edit each room → set PMS code → save.

PMS code mapping (from Pullman reference):
  Standard → Stnd
  Deluxe → DLX
  Suite → Suite
  Superior → SPR

Usage:
  pip install playwright
  playwright install chromium
  python scripts/fix_noovy_pms_codes.py
"""
import asyncio
import time
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

# PMS code mapping: Short Name → PMS Exchange Code
PMS_MAP = {
    "Stnd": "Stnd",
    "Standard": "Stnd",
    "DLX": "DLX",
    "Deluxe": "DLX",
    "Suite": "Suite",
    "SUI": "Suite",
    "SPR": "SPR",
    "Superior": "SPR",
    "SUP": "SPR",
}

# All venue IDs to fix (from scan report — blocked + no API)
VENUES = [
    5073, 5075, 5084, 5094, 5113, 5115, 5116, 5124,
    5130, 5131, 5136, 5138, 5139, 5266, 5267, 5268,
    5274, 5275, 5276, 5277, 5278, 5279,
    5064, 5089, 5102, 5104, 5117, 5141, 5265,
]


async def login(page):
    """Login to Noovy."""
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in to Noovy")


async def fix_venue(page, venue_id):
    """Fix PMS codes for all rooms in a venue."""
    # Switch venue via cookie
    await page.evaluate(f"() => {{ document.cookie = 'hotelId={venue_id}; path=/'; }}")
    await page.goto(f"{NOOVY_URL}/products")
    await page.wait_for_timeout(3000)

    # Get venue name
    venue_name = await page.evaluate(
        "() => document.querySelector('[class*=\"venue\"], [class*=\"hotel\"]')?.textContent?.trim() || 'Unknown'"
    )

    # Find all edit buttons in the rooms table
    rows = await page.query_selector_all("table tbody tr")
    room_count = len(rows)

    if room_count == 0:
        print(f"  #{venue_id}: No rooms found")
        return {"venue": venue_id, "name": venue_name, "rooms": 0, "fixed": 0}

    fixed = 0
    rooms_info = []

    for i in range(room_count):
        # Re-query rows (DOM may change after dialog)
        rows = await page.query_selector_all("table tbody tr")
        if i >= len(rows):
            break

        row = rows[i]
        cells = await row.query_selector_all("td")
        if len(cells) < 3:
            continue

        room_title = await cells[1].text_content()
        room_title = room_title.strip() if room_title else "Unknown"

        # Click edit button
        edit_btn = await row.query_selector("button")
        if not edit_btn:
            continue
        await edit_btn.click()
        await page.wait_for_timeout(1500)

        # Check PMS code field
        pms_field = page.get_by_role("textbox", name="PMS code")
        current_pms = await pms_field.input_value()

        if current_pms:
            # PMS already set
            rooms_info.append({"room": room_title, "pms": current_pms, "action": "already_set"})
            # Close dialog
            cancel = page.get_by_role("button", name="Cancel")
            if await cancel.is_visible():
                await cancel.click()
                await page.wait_for_timeout(500)
                # Handle "Are you sure" dialog
                yes_btn = page.get_by_role("button", name="Yes")
                if await yes_btn.is_visible(timeout=1000):
                    await yes_btn.click()
                    await page.wait_for_timeout(500)
        else:
            # Determine correct PMS code from Short Name
            short_field = page.get_by_role("textbox", name="Short Name")
            short_name = await short_field.input_value()

            pms_code = PMS_MAP.get(short_name, PMS_MAP.get(room_title, short_name))

            if not pms_code:
                rooms_info.append({"room": room_title, "pms": "", "action": "unknown_mapping"})
                cancel = page.get_by_role("button", name="Cancel")
                if await cancel.is_visible():
                    await cancel.click()
                    await page.wait_for_timeout(500)
                continue

            # Fill PMS code
            await pms_field.fill(pms_code)
            await page.wait_for_timeout(500)

            # Click Save
            save_btn = None
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                text = await btn.text_content()
                disabled = await btn.get_attribute("disabled")
                if text and text.strip() == "Save" and disabled is None:
                    save_btn = btn
                    break

            if save_btn:
                await save_btn.click()
                await page.wait_for_timeout(2000)
                fixed += 1
                rooms_info.append({"room": room_title, "pms": pms_code, "action": "FIXED"})
                print(f"    ✅ {room_title} → PMS={pms_code}")
            else:
                rooms_info.append({"room": room_title, "pms": pms_code, "action": "save_disabled"})
                cancel = page.get_by_role("button", name="Cancel")
                if await cancel.is_visible():
                    await cancel.click()
                    await page.wait_for_timeout(500)

    result = {"venue": venue_id, "name": venue_name, "rooms": room_count, "fixed": fixed, "details": rooms_info}
    status = "FIXED" if fixed > 0 else ("OK" if all(r["action"] == "already_set" for r in rooms_info) else "CHECK")
    print(f"  #{venue_id} {venue_name}: {room_count} rooms, {fixed} fixed [{status}]")
    return result


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await login(page)

        results = []
        for i, vid in enumerate(VENUES):
            print(f"\n[{i+1}/{len(VENUES)}] Processing venue #{vid}...")
            try:
                result = await fix_venue(page, vid)
                results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({"venue": vid, "error": str(e)})

        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        total_fixed = sum(r.get("fixed", 0) for r in results)
        total_rooms = sum(r.get("rooms", 0) for r in results)
        errors = [r for r in results if "error" in r]
        print(f"Venues processed: {len(results)}")
        print(f"Total rooms: {total_rooms}")
        print(f"PMS codes fixed: {total_fixed}")
        print(f"Errors: {len(errors)}")

        for r in results:
            if "error" in r:
                print(f"  ❌ #{r['venue']}: {r['error']}")
            elif r.get("fixed", 0) > 0:
                print(f"  ✅ #{r['venue']} {r.get('name','')}: {r['fixed']} fixed")
            elif r.get("rooms", 0) == 0:
                print(f"  ⚠ #{r['venue']}: No rooms")
            else:
                details = r.get("details", [])
                if all(d["action"] == "already_set" for d in details):
                    print(f"  ✓ #{r['venue']} {r.get('name','')}: All PMS codes OK")
                else:
                    print(f"  ? #{r['venue']} {r.get('name','')}: {details}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
