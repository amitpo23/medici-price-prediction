"""Deep audit of 8 No-API hotels in Noovy — check everything."""
import asyncio
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

VENUES = [5064, 5089, 5102, 5104, 5111, 5117, 5141]
# 5106 skipped — duplicate venue, already has working order under 854875


async def login(page):
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in")


async def audit(page, vid):
    result = {"vid": vid, "issues": []}
    await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")

    # 1. Check venue details (Lat/Lon, Short Name, Email, Timezone, Check-in/out)
    await page.goto(f"{NOOVY_URL}/venues")
    await page.wait_for_timeout(3000)
    try:
        await page.locator("table button").nth(1).click(timeout=5000)
        await page.wait_for_timeout(2000)

        name = await page.get_by_role("textbox", name="Name", exact=True).input_value()
        short = await page.get_by_role("textbox", name="Short Name").input_value()
        email = await page.get_by_role("textbox", name="General E-mail").input_value()
        lat = await page.get_by_role("textbox", name="Latitude").input_value()
        lon = await page.get_by_role("textbox", name="Longitude").input_value()
        addr = await page.get_by_role("textbox", name="Address").input_value()
        phone = await page.get_by_role("textbox", name="Phone").input_value()
        tz = await page.get_by_role("combobox", name="Timezone").input_value()
        supplier = await page.get_by_role("combobox", name="Connected to Supplier").input_value()

        result["name"] = name
        result["general"] = {"short": short, "email": email, "lat": lat, "lon": lon, "addr": addr, "phone": phone, "tz": tz, "supplier": supplier}

        if not short: result["issues"].append("SHORT_NAME_EMPTY")
        if not email: result["issues"].append("EMAIL_EMPTY")
        if not lat or not lon: result["issues"].append("COORDINATES_EMPTY")
        if tz != "America/New_York": result["issues"].append(f"TIMEZONE_WRONG: {tz}")
        if supplier == "none" or supplier == "None": result["issues"].append("SUPPLIER_NOT_CONNECTED")

        # Check Settings tab
        settings = page.get_by_role("tab", name="Settings")
        await settings.click()
        await page.wait_for_timeout(1000)

        checkin = await page.get_by_role("textbox", name="Check-in after:").input_value()
        checkout = await page.get_by_role("textbox", name="Check-out until:").input_value()
        result["settings"] = {"checkin": checkin, "checkout": checkout}
        if not checkin: result["issues"].append("CHECKIN_TIME_EMPTY")
        if not checkout: result["issues"].append("CHECKOUT_TIME_EMPTY")

        # Close dialog
        cancel = page.get_by_role("button", name="Cancel")
        await cancel.click()
        await page.wait_for_timeout(500)
        yes = page.get_by_role("button", name="Yes")
        try:
            if await yes.is_visible(timeout=1000):
                await yes.click()
                await page.wait_for_timeout(500)
        except:
            pass
    except Exception as e:
        result["issues"].append(f"VENUE_ERROR: {str(e)[:100]}")

    # 2. Check products (rooms + PMS codes)
    await page.goto(f"{NOOVY_URL}/products")
    await page.wait_for_timeout(3000)
    rooms = []
    rows = await page.query_selector_all("table tbody tr")
    for i, row in enumerate(rows):
        cells = await row.query_selector_all("td")
        if len(cells) < 5:
            continue
        title = (await cells[1].text_content()).strip()
        qty = (await cells[5].text_content()).strip() if len(cells) > 5 else "?"
        status_cell = cells[8] if len(cells) > 8 else None
        status = (await status_cell.text_content()).strip() if status_cell else "?"

        # Get PMS code
        edit = await row.query_selector("button")
        if edit:
            await edit.click()
            await page.wait_for_timeout(1500)
            pms = await page.get_by_role("textbox", name="PMS code").input_value()
            rooms.append({"title": title, "pms": pms, "qty": qty, "status": status})
            cancel = page.get_by_role("button", name="Cancel")
            await cancel.click()
            await page.wait_for_timeout(500)
            try:
                yes = page.get_by_role("button", name="Yes")
                if await yes.is_visible(timeout=1000):
                    await yes.click()
                    await page.wait_for_timeout(500)
            except:
                pass

    result["rooms"] = rooms
    if not rooms: result["issues"].append("NO_ROOMS")
    for r in rooms:
        if not r["pms"]: result["issues"].append(f"PMS_EMPTY: {r['title']}")

    # 3. Check rate plans
    await page.goto(f"{NOOVY_URL}/pricing-availability")
    await page.wait_for_timeout(3000)
    rate_plans = []
    try:
        rp_open = page.locator('[data-test-id="pricing-availability-plan-autocomplete"]').get_by_role('button', name='Open')
        await rp_open.click()
        await page.wait_for_timeout(1000)
        options = await page.query_selector_all('[role="option"]')
        for opt in options:
            text = (await opt.text_content()).strip()
            if text: rate_plans.append(text)
        rp_close = page.locator('[data-test-id="pricing-availability-plan-autocomplete"]').get_by_role('button', name='Close')
        try:
            await rp_close.click()
        except:
            pass
    except:
        rate_plans = ["ERROR"]
    result["rate_plans"] = rate_plans
    has_ro = any("room only" in rp.lower() or rp.lower().startswith("ro") or "refundable" in rp.lower() for rp in rate_plans)
    if not has_ro and rate_plans != ["ERROR"]:
        result["issues"].append(f"NO_RO_PLAN: {rate_plans}")

    # 4. Check April pricing (scan dates Apr 20-21)
    try:
        apr = page.get_by_role("tab", name="April")
        await apr.click()
        await page.wait_for_timeout(2000)
        # Check day 20 price
        body = await page.evaluate("() => document.body.innerText")
        has_price_20 = "20" in body and "$" in body
        result["april_pricing"] = "HAS_PRICES" if has_price_20 else "CHECK"
    except:
        result["april_pricing"] = "ERROR"

    if not result["issues"]:
        result["issues"] = ["OK"]
    return result


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await login(page)

        results = []
        for i, vid in enumerate(VENUES):
            print(f"\n[{i+1}/{len(VENUES)}] #{vid}...", end=" ", flush=True)
            try:
                r = await audit(page, vid)
                results.append(r)
                print(f"{r.get('name','?')}")
                print(f"  General: Short={r.get('general',{}).get('short','?')} Email={r.get('general',{}).get('email','?')[:20]} TZ={r.get('general',{}).get('tz','?')} Lat={r.get('general',{}).get('lat','?')} Supplier={r.get('general',{}).get('supplier','?')}")
                print(f"  Settings: CheckIn={r.get('settings',{}).get('checkin','?')} CheckOut={r.get('settings',{}).get('checkout','?')}")
                room_strs = [f"{rm['title']}(PMS={rm['pms']})" for rm in r.get('rooms',[])]
                print(f"  Rooms: {', '.join(room_strs)}")
                print(f"  Rate Plans: {', '.join(r.get('rate_plans',[]))}")
                print(f"  Issues: {', '.join(r['issues'])}")
            except Exception as e:
                print(f"FATAL: {e}")
                results.append({"vid": vid, "issues": [f"FATAL: {e}"]})

        print("\n" + "=" * 80)
        print("DEEP AUDIT — NO API HOTELS")
        print("=" * 80)
        for r in results:
            status = "✅ OK" if r["issues"] == ["OK"] else "❌ ISSUES"
            print(f"\n{status} #{r['vid']} {r.get('name','?')}")
            if r["issues"] != ["OK"]:
                for iss in r["issues"]:
                    print(f"  → {iss}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
