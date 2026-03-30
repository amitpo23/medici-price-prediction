"""Audit remaining 12 venues not covered in first audit."""
import asyncio
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

VENUES = [5265, 5266, 5267, 5268, 5274, 5275, 5276, 5278, 5279, 5089, 5102, 5104]

# DB ratebycat for these venues
RATEBYCAT = {
    5265: [{"itc": "Stnd", "rpc": "13490"}],
    5266: [{"itc": "Stnd", "rpc": "13488"}],
    5267: [],  # No ratebycat!
    5268: [{"itc": "Stnd", "rpc": "13489"}],
    5274: [{"itc": "Stnd", "rpc": "13493"}],
    5275: [{"itc": "Stnd", "rpc": "13492"}],
    5276: [{"itc": "Stnd", "rpc": "13569"}],
    5278: [{"itc": "Stnd", "rpc": "13567"}],
    5279: [{"itc": "Stnd", "rpc": "13494"}],
    5089: [{"itc": "Stnd", "rpc": "12059"}, {"itc": "DLX", "rpc": "12059"}],
    5102: [{"itc": "Stnd", "rpc": "12070"}],
    5104: [{"itc": "Stnd", "rpc": "12072"}, {"itc": "Suite", "rpc": "12072"}],
}


async def login(page):
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in")


async def audit(page, vid):
    await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")

    # Products
    await page.goto(f"{NOOVY_URL}/products")
    await page.wait_for_timeout(3000)

    venue_name = await page.evaluate("() => document.querySelector('[class*=\"venue\"], [class*=\"hotel\"]')?.textContent?.trim() || ''")

    rows = await page.query_selector_all("table tbody tr")
    rooms = []
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) < 5:
            continue
        title = (await cells[1].text_content()).strip()

        edit_btn = await row.query_selector("button")
        if not edit_btn:
            continue
        await edit_btn.click()
        await page.wait_for_timeout(1500)

        pms = ""
        short = ""
        try:
            pms_f = page.get_by_role("textbox", name="PMS code")
            short_f = page.get_by_role("textbox", name="Short Name")
            pms = await pms_f.input_value() if await pms_f.is_visible() else ""
            short = await short_f.input_value() if await short_f.is_visible() else ""
        except:
            pass

        rooms.append({"title": title, "short": short, "pms": pms})

        cancel = page.get_by_role("button", name="Cancel")
        try:
            if await cancel.is_visible():
                await cancel.click()
                await page.wait_for_timeout(500)
                yes = page.get_by_role("button", name="Yes")
                try:
                    if await yes.is_visible(timeout=1000):
                        await yes.click()
                        await page.wait_for_timeout(500)
                except:
                    pass
        except:
            pass

    # Rate Plans
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
            if text:
                rate_plans.append(text)
        try:
            rp_close = page.locator('[data-test-id="pricing-availability-plan-autocomplete"]').get_by_role('button', name='Close')
            await rp_close.click()
        except:
            pass
    except:
        rate_plans = ["ERROR"]

    # Compare with DB
    db = RATEBYCAT.get(vid, [])
    issues = []

    for room in rooms:
        pms = room["pms"]
        if not pms:
            issues.append(f"PMS_EMPTY: {room['title']}")
        elif db:
            match = [d for d in db if d["itc"] == pms]
            if not match:
                ci = [d for d in db if d["itc"].lower() == pms.lower()]
                if ci:
                    issues.append(f"CASE_MISMATCH: {room['title']} Noovy='{pms}' DB='{ci[0]['itc']}'")
                else:
                    issues.append(f"NO_MATCH: {room['title']} Noovy='{pms}' DB={[d['itc'] for d in db]}")

    if not db:
        issues.append("NO_RATEBYCAT_IN_DB")

    has_ro = any("room only" in rp.lower() or rp.lower().startswith("ro") or "refundable" in rp.lower() for rp in rate_plans)
    if not has_ro and rate_plans and rate_plans != ["ERROR"]:
        issues.append(f"NO_RO_PLAN: {rate_plans}")

    if not rooms:
        issues.append("NO_ROOMS")

    if not issues:
        issues = ["OK"]

    return {"venue": vid, "name": venue_name, "rooms": rooms, "rate_plans": rate_plans, "issues": issues}


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
                rooms_str = ", ".join(f"{rm['title']}(PMS={rm['pms']})" for rm in r["rooms"])
                print(f"{r['name']}")
                print(f"  Rooms: {rooms_str}")
                print(f"  Rate Plans: {', '.join(r['rate_plans'])}")
                print(f"  Issues: {', '.join(r['issues'])}")
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"venue": vid, "issues": [f"FATAL: {e}"]})

        print("\n" + "=" * 80)
        print("REMAINING VENUES — ISSUES TO FIX")
        print("=" * 80)

        for r in results:
            if r["issues"] != ["OK"]:
                print(f"\n❌ #{r['venue']} {r.get('name','')}:")
                for iss in r["issues"]:
                    print(f"   {iss}")
            else:
                print(f"\n✅ #{r['venue']} {r.get('name','')}: OK")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
