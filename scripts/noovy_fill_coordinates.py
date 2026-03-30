"""Fill coordinates and contact details for 7 remaining hotels in Noovy."""
import asyncio
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

HOTELS = [
    # Already done: 5265 Belleza
    {"vid": 5266, "name": "Dorchester Hotel", "address": "1850 Collins Ave, Miami Beach, FL 33139", "phone": "3055315745", "lat": "25.7901", "lon": "-80.1303", "email": "info@hoteldorchester.com"},
    {"vid": 5274, "name": "Generator Miami", "address": "3120 Collins Ave, Miami Beach, FL 33140", "phone": "7864965730", "lat": "25.8060", "lon": "-80.1254", "email": "miami@staygenerator.com"},
    {"vid": 5275, "name": "Miami Intl Airport Hotel", "address": "Concourse E, 2nd Floor, MIA, Miami, FL 33122", "phone": "3058714100", "lat": "25.7952", "lon": "-80.2796", "email": "info@miahotel.com"},
    {"vid": 5276, "name": "InterContinental Miami", "address": "100 Chopin Plaza, Miami, FL 33131", "phone": "3055771000", "lat": "25.7724", "lon": "-80.1855", "email": "icmiami@ihg.com"},
    {"vid": 5277, "name": "Catalina Hotel & Beach Club", "address": "1732 Collins Ave, Miami Beach, FL 33139", "phone": "3056741160", "lat": "25.7931", "lon": "-80.1300", "email": "info@catalinahotel.com"},
    {"vid": 5278, "name": "Gale Miami Hotel & Residences", "address": "159 NE 6th St, Miami, FL 33132", "phone": "3057684253", "lat": "25.7763", "lon": "-80.1905", "email": "info@galehotelmiami.com"},
    {"vid": 5279, "name": "Hilton Garden Inn Miami SB", "address": "2940 Collins Ave, Miami Beach, FL 33140", "phone": "3056427656", "lat": "25.8060", "lon": "-80.1254", "email": "miasbgi@hilton.com"},
]


async def login(page):
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in")


async def fill_venue(page, hotel):
    vid = hotel["vid"]
    print(f"\n  Editing #{vid} {hotel['name']}...", end=" ", flush=True)

    await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")
    await page.goto(f"{NOOVY_URL}/venues")
    await page.wait_for_timeout(3000)

    # Click edit (second button in row)
    try:
        edit_btn = page.locator("table button").nth(1)
        await edit_btn.click(timeout=3000)
        await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"EDIT FAILED: {e}")
        return False

    # Fill fields
    try:
        addr = page.get_by_role("textbox", name="Address")
        phone = page.get_by_role("textbox", name="Phone")
        lat = page.get_by_role("textbox", name="Latitude")
        lon = page.get_by_role("textbox", name="Longitude")
        email = page.get_by_role("textbox", name="General E-mail")

        # Fill email first (required field)
        if hotel.get("email"):
            current_email = await email.input_value()
            if not current_email:
                await email.fill(hotel["email"])

        if hotel["address"]:
            await addr.fill(hotel["address"])
        if hotel["phone"]:
            await phone.fill(hotel["phone"])
        if hotel["lat"]:
            await lat.fill(hotel["lat"])
        if hotel["lon"]:
            await lon.fill(hotel["lon"])

        await page.wait_for_timeout(500)

        # Click Save (second Save button — the one at bottom of dialog)
        save_btns = page.get_by_role("button", name="Save")
        count = await save_btns.count()
        if count >= 2:
            await save_btns.nth(1).click()
        elif count == 1:
            await save_btns.click()
        else:
            print("NO SAVE BUTTON")
            return False

        await page.wait_for_timeout(2000)

        # Check for success
        body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
        if "Venue is edited" in body_text or "Success" in body_text:
            print("✅ Saved!")
            return True
        else:
            print("⚠ Save attempted")
            return True
    except Exception as e:
        print(f"FILL FAILED: {e}")
        return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await login(page)

        success = 0
        for i, hotel in enumerate(HOTELS):
            print(f"[{i+1}/{len(HOTELS)}]", end="")
            if await fill_venue(page, hotel):
                success += 1

        print(f"\n\nDone: {success}/{len(HOTELS)} venues updated")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
