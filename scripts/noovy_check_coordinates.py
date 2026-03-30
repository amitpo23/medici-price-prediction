"""Check coordinates for all failing hotels in Noovy."""
import asyncio
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

ALL_VENUES = [
    5064, 5073, 5075, 5082, 5083, 5084, 5089, 5094, 5102, 5104,
    5113, 5115, 5116, 5117, 5119, 5124, 5130, 5131, 5132, 5136,
    5138, 5139, 5140, 5141, 5265, 5266, 5267, 5268, 5274, 5275,
    5276, 5277, 5278, 5279,
    # Also check working ones for reference
    5080, 5081, 5077, 5079,
    # The 3 new hotels
    5105, 5106,
]


async def login(page):
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in")


async def check_venue(page, vid):
    await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")
    await page.goto(f"{NOOVY_URL}/venues")
    await page.wait_for_timeout(2000)

    # Click edit button on the venue row
    edit_btn = page.locator('table button').nth(1)
    try:
        await edit_btn.click(timeout=3000)
        await page.wait_for_timeout(1500)

        # Get lat/lon from dialog
        lat_field = page.get_by_role("textbox", name="Latitude")
        lon_field = page.get_by_role("textbox", name="Longitude")
        name_field = page.get_by_role("textbox", name="Name", exact=True)

        lat = await lat_field.input_value() if await lat_field.is_visible(timeout=2000) else ""
        lon = await lon_field.input_value() if await lon_field.is_visible(timeout=2000) else ""
        name = await name_field.input_value() if await name_field.is_visible(timeout=2000) else ""

        # Close dialog
        cancel = page.get_by_role("button", name="Cancel")
        if await cancel.is_visible(timeout=1000):
            await cancel.click()
            await page.wait_for_timeout(500)
            yes = page.get_by_role("button", name="Yes")
            try:
                if await yes.is_visible(timeout=1000):
                    await yes.click()
                    await page.wait_for_timeout(500)
            except:
                pass

        return {"venue": vid, "name": name, "lat": lat, "lon": lon}
    except Exception as e:
        return {"venue": vid, "name": "?", "lat": "ERROR", "lon": str(e)}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await login(page)

        results = []
        for i, vid in enumerate(ALL_VENUES):
            print(f"[{i+1}/{len(ALL_VENUES)}] #{vid}...", end=" ", flush=True)
            r = await check_venue(page, vid)
            results.append(r)
            lat_ok = "✅" if r["lat"] and r["lat"] != "ERROR" and r["lat"] != "0" else "❌ MISSING"
            print(f"{r['name'][:30]:30s} Lat={r['lat'] or 'EMPTY':12s} Lon={r['lon'] or 'EMPTY':12s} {lat_ok}")

        print("\n" + "=" * 80)
        print("MISSING COORDINATES")
        print("=" * 80)
        missing = [r for r in results if not r["lat"] or r["lat"] in ("", "0", "ERROR")]
        if missing:
            for r in missing:
                print(f"  ❌ #{r['venue']} {r['name']}: Lat={r['lat']} Lon={r['lon']}")
        else:
            print("  All venues have coordinates ✅")

        # Check duplicates
        print("\n" + "=" * 80)
        print("DUPLICATE COORDINATES")
        print("=" * 80)
        coords = {}
        for r in results:
            if r["lat"] and r["lat"] not in ("", "0", "ERROR"):
                key = f"{r['lat']},{r['lon']}"
                if key not in coords:
                    coords[key] = []
                coords[key].append(r)
        for key, venues in coords.items():
            if len(venues) > 1:
                labels = [f"#{v['venue']} {v['name'][:25]}" for v in venues]
                print(f"  ⚠ {key}: {', '.join(labels)}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
