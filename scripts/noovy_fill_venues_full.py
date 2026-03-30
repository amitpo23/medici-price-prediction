"""Fill ALL required venue fields for 6 hotels in Noovy.
General tab: Short Name, Email, Timezone, Address, Phone, Lat, Lon
Settings tab: Check-in after (15:00), Check-out until (11:00)
"""
import asyncio
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

HOTELS = [
    {"vid": 5274, "short": "Generator", "email": "miami@staygenerator.com", "address": "3120 Collins Ave, Miami Beach, FL 33140", "phone": "7864965730", "lat": "25.8060", "lon": "-80.1254"},
    {"vid": 5275, "short": "MIA Hotel", "email": "info@miahotel.com", "address": "Concourse E, MIA, Miami, FL 33122", "phone": "3058714100", "lat": "25.7952", "lon": "-80.2796"},
    {"vid": 5276, "short": "IC Miami", "email": "icmiami@ihg.com", "address": "100 Chopin Plaza, Miami, FL 33131", "phone": "3055771000", "lat": "25.7724", "lon": "-80.1855"},
    {"vid": 5277, "short": "Catalina", "email": "info@catalinahotel.com", "address": "1732 Collins Ave, Miami Beach, FL 33139", "phone": "3056741160", "lat": "25.7931", "lon": "-80.1300"},
    {"vid": 5278, "short": "Gale Miami", "email": "info@galehotelmiami.com", "address": "159 NE 6th St, Miami, FL 33132", "phone": "3057684253", "lat": "25.7763", "lon": "-80.1905"},
    {"vid": 5279, "short": "HGI SoBe", "email": "miasbgi@hilton.com", "address": "2940 Collins Ave, Miami Beach, FL 33140", "phone": "3056427656", "lat": "25.8060", "lon": "-80.1254"},
]


async def login(page):
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in")


async def fill_venue(page, h):
    vid = h["vid"]
    print(f"\n  #{vid}...", end=" ", flush=True)

    await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")
    await page.goto(f"{NOOVY_URL}/venues")
    await page.wait_for_timeout(3000)

    # Click edit button (second button in row)
    try:
        await page.locator("table button").nth(1).click(timeout=5000)
        await page.wait_for_timeout(2000)
    except:
        print("EDIT FAILED")
        return False

    # === GENERAL TAB ===
    try:
        short = page.get_by_role("textbox", name="Short Name")
        email = page.get_by_role("textbox", name="General E-mail")
        addr = page.get_by_role("textbox", name="Address")
        phone = page.get_by_role("textbox", name="Phone")
        lat = page.get_by_role("textbox", name="Latitude")
        lon = page.get_by_role("textbox", name="Longitude")

        # Fill only if empty
        if not await short.input_value():
            await short.fill(h["short"])
        if not await email.input_value():
            await email.fill(h["email"])
        await addr.fill(h["address"])
        await phone.fill(h["phone"])
        await lat.fill(h["lat"])
        await lon.fill(h["lon"])

        # Fix timezone if wrong
        tz = page.get_by_role("combobox", name="Timezone")
        tz_val = await tz.input_value()
        if tz_val != "America/New_York":
            tz_open = page.locator('[data-test-id="venue-timezone-autocomplete"]').get_by_role("button", name="Open")
            try:
                await tz_open.click(timeout=2000)
            except:
                # Try clicking the combobox directly
                await tz.click()
            await page.wait_for_timeout(500)
            ny = page.get_by_role("option", name="America/New_York")
            await ny.click()
            await page.wait_for_timeout(500)
    except Exception as e:
        print(f"GENERAL FAILED: {e}")
        return False

    # === SETTINGS TAB ===
    try:
        settings_tab = page.get_by_role("tab", name="Settings")
        await settings_tab.click()
        await page.wait_for_timeout(1000)

        checkin = page.get_by_role("textbox", name="Check-in after:")
        checkout = page.get_by_role("textbox", name="Check-out until:")

        ci_val = await checkin.input_value()
        co_val = await checkout.input_value()

        if not ci_val:
            await checkin.fill("15:00")
        if not co_val:
            await checkout.fill("11:00")
    except Exception as e:
        print(f"SETTINGS FAILED: {e}")

    # === SAVE ===
    await page.wait_for_timeout(500)
    try:
        saves = page.get_by_role("button", name="Save")
        count = await saves.count()
        # Find enabled save button
        for i in range(count):
            btn = saves.nth(i)
            disabled = await btn.get_attribute("disabled")
            if disabled is None:
                await btn.click()
                await page.wait_for_timeout(2000)
                body = await page.evaluate("() => document.body.innerText.substring(0, 500)")
                if "Venue is edited" in body or "Success" in body:
                    print("✅ Saved!")
                    return True
                else:
                    print("⚠ Save clicked")
                    return True
        print("❌ All Save buttons disabled")
        return False
    except Exception as e:
        print(f"SAVE FAILED: {e}")
        return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await login(page)

        ok = 0
        for i, h in enumerate(HOTELS):
            print(f"[{i+1}/{len(HOTELS)}]", end="")
            if await fill_venue(page, h):
                ok += 1

        print(f"\n\nDone: {ok}/{len(HOTELS)} venues updated")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
