"""Full Noovy audit — collect all settings for failing hotels.

For each hotel: Products (rooms + PMS codes + Short Names), Rate Plans, Marketplace.
Compare against ratebycat DB to find mismatches.

Usage: python scripts/noovy_full_audit.py
"""
import asyncio
import json
from playwright.async_api import async_playwright

NOOVY_URL = "https://app.noovy.com"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

# All failing venues from scan report
# Zenith push fail (connected per Innstant)
ZENITH_FAIL = [5073, 5075, 5082, 5083, 5084, 5094, 5113, 5115, 5116, 5119, 5124, 5130, 5131, 5132, 5136, 5138, 5139, 5140, 5277]
# No API results
NO_API = [5064, 5117, 5131, 5132, 5140, 5141]
# Combine unique
ALL_VENUES = sorted(set(ZENITH_FAIL + NO_API))

# What ratebycat has in DB (from medici-db query)
RATEBYCAT = {
    5064: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12109"}],
    5073: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12033"}, {"board": "RO", "cat": 12, "itc": "Suite", "rpc": "12033"},
           {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "12886"}, {"board": "BB", "cat": 12, "itc": "Suite", "rpc": "12886"}],
    5075: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "13508"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13538"}],
    5082: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12046"}, {"board": "RO", "cat": 12, "itc": "Suite", "rpc": "12046"},
           {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13171"}, {"board": "BB", "cat": 12, "itc": "Suite", "rpc": "13171"}],
    5083: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12047"}, {"board": "RO", "cat": 4, "itc": "DLX", "rpc": "12047"},
           {"board": "RO", "cat": 12, "itc": "Suite", "rpc": "12047"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13172"},
           {"board": "BB", "cat": 4, "itc": "DLX", "rpc": "13172"}, {"board": "BB", "cat": 12, "itc": "Suite", "rpc": "13172"}],
    5084: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12048"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13173"}],
    5094: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12063"}, {"board": "RO", "cat": 4, "itc": "DLX", "rpc": "12063"}],
    5113: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12103"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "12866"}],
    5115: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12035"}, {"board": "RO", "cat": 2, "itc": "SPR", "rpc": "12035"},
           {"board": "RO", "cat": 3, "itc": "DRM", "rpc": "12035"}, {"board": "RO", "cat": 4, "itc": "DLX", "rpc": "12035"},
           {"board": "RO", "cat": 12, "itc": "Suite", "rpc": "12035"},
           {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13168"}, {"board": "BB", "cat": 2, "itc": "SPR", "rpc": "13168"},
           {"board": "BB", "cat": 3, "itc": "DRM", "rpc": "13168"}, {"board": "BB", "cat": 4, "itc": "DLX", "rpc": "13168"},
           {"board": "BB", "cat": 12, "itc": "Suite", "rpc": "13168"}],
    5116: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12105"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13536"}],
    5117: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "13486"}],
    5119: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12107"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13556"}],
    5124: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12112"}],
    5130: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12118"}],
    5131: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12119"}],
    5132: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12120"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13559"}],
    5136: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12124"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13565"}],
    5138: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12126"}],
    5139: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "13522"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13535"}],
    5140: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12128"}],
    5141: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "12129"}, {"board": "BB", "cat": 1, "itc": "Stnd", "rpc": "13560"}],
    5277: [{"board": "RO", "cat": 1, "itc": "Stnd", "rpc": "13487"}],
}


async def login(page):
    await page.goto(f"{NOOVY_URL}/")
    await page.get_by_role("textbox", name="Account Name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="User Name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in to Noovy")


async def audit_venue(page, vid):
    """Collect all settings for a venue."""
    result = {"venue": vid, "issues": []}

    # Switch venue
    await page.evaluate(f"() => {{ document.cookie = 'hotelId={vid}; path=/'; }}")

    # 1. Products — get rooms, PMS codes, Short Names
    await page.goto(f"{NOOVY_URL}/products")
    await page.wait_for_timeout(3000)

    venue_name = await page.evaluate("() => document.querySelector('[class*=\"venue\"], [class*=\"hotel\"]')?.textContent?.trim() || ''")
    result["name"] = venue_name

    # Get room rows
    rows = await page.query_selector_all("table tbody tr")
    rooms = []
    for i, row in enumerate(rows):
        cells = await row.query_selector_all("td")
        if len(cells) < 5:
            continue
        title = (await cells[1].text_content()).strip()
        base_qty = (await cells[5].text_content()).strip() if len(cells) > 5 else "?"

        # Click edit to get PMS code and Short Name
        edit_btn = await row.query_selector("button")
        if not edit_btn:
            continue
        await edit_btn.click()
        await page.wait_for_timeout(1500)

        pms_field = page.get_by_role("textbox", name="PMS code")
        short_field = page.get_by_role("textbox", name="Short Name")
        qty_field = page.get_by_role("textbox", name="Basic Occupancy")

        pms = await pms_field.input_value() if await pms_field.is_visible() else ""
        short = await short_field.input_value() if await short_field.is_visible() else ""
        occupancy = await qty_field.input_value() if await qty_field.is_visible() else ""

        # Check Base Quantity mode (Actual vs Arbitrary)
        qty_switch = page.get_by_role("switch").first
        # The Actual/Arbitrary is hard to read, skip for now

        rooms.append({"title": title, "short": short, "pms": pms, "base_qty": base_qty, "occupancy": occupancy})

        # Close dialog
        cancel = page.get_by_role("button", name="Cancel")
        if await cancel.is_visible():
            await cancel.click()
            await page.wait_for_timeout(500)
            yes_btn = page.get_by_role("button", name="Yes")
            try:
                if await yes_btn.is_visible(timeout=1000):
                    await yes_btn.click()
                    await page.wait_for_timeout(500)
            except:
                pass

    result["rooms"] = rooms

    # 2. Rate Plans from Rate Calendar
    await page.goto(f"{NOOVY_URL}/pricing-availability")
    await page.wait_for_timeout(3000)

    # Open rate plan dropdown
    try:
        rp_open = page.locator('[data-test-id="pricing-availability-plan-autocomplete"]').get_by_role('button', name='Open')
        await rp_open.click()
        await page.wait_for_timeout(1000)

        options = await page.query_selector_all('[role="option"]')
        rate_plans = []
        for opt in options:
            text = (await opt.text_content()).strip()
            if text:
                rate_plans.append(text)

        # Close dropdown
        rp_close = page.locator('[data-test-id="pricing-availability-plan-autocomplete"]').get_by_role('button', name='Close')
        try:
            await rp_close.click()
        except:
            pass

        result["rate_plans"] = rate_plans
    except:
        result["rate_plans"] = ["ERROR"]

    # 3. Marketplace — check Settings
    await page.goto(f"{NOOVY_URL}/marketplace")
    await page.wait_for_timeout(3000)

    mp_text = await page.evaluate("() => document.body.innerText.substring(0, 2000)")
    result["marketplace_has_medici"] = "Medici" in mp_text or "medici" in mp_text

    # 4. Compare with ratebycat DB
    db_entries = RATEBYCAT.get(vid, [])
    if rooms and db_entries:
        for room in rooms:
            pms = room["pms"]
            for db in db_entries:
                if db["itc"] != pms and db["itc"].lower() == pms.lower():
                    result["issues"].append(f"CASE_MISMATCH: Noovy PMS='{pms}' vs DB InvTypeCode='{db['itc']}'")
                elif pms and db["itc"] != pms and room["title"].lower() in ["standard", "standard room"]:
                    result["issues"].append(f"PMS_MISMATCH: Noovy PMS='{pms}' vs DB InvTypeCode='{db['itc']}' for {room['title']}")

    if not rooms:
        result["issues"].append("NO_ROOMS")
    if not any("room only" in rp.lower() or "ro" in rp.lower() or "refundable" in rp.lower() for rp in result.get("rate_plans", [])):
        result["issues"].append("NO_RO_RATE_PLAN")

    for room in rooms:
        if not room["pms"]:
            result["issues"].append(f"PMS_EMPTY: {room['title']}")

    if not result["issues"]:
        result["issues"] = ["OK"]

    return result


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await login(page)

        results = []
        for i, vid in enumerate(ALL_VENUES):
            print(f"\n[{i+1}/{len(ALL_VENUES)}] Auditing venue #{vid}...", end=" ", flush=True)
            try:
                r = await audit_venue(page, vid)
                results.append(r)
                issues_str = ", ".join(r["issues"])
                rooms_str = ", ".join(f"{rm['title']}(PMS={rm['pms']},Short={rm['short']})" for rm in r.get("rooms", []))
                rp_str = ", ".join(r.get("rate_plans", []))
                print(f"\n  Rooms: {rooms_str}")
                print(f"  Rate Plans: {rp_str}")
                print(f"  Marketplace: {'Yes' if r.get('marketplace_has_medici') else 'NO'}")
                print(f"  Issues: {issues_str}")
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"venue": vid, "issues": [f"FATAL: {e}"]})

        # Final report
        print("\n" + "=" * 100)
        print("NOOVY FULL AUDIT REPORT")
        print("=" * 100)

        all_issues = []
        for r in results:
            vid = r["venue"]
            name = r.get("name", "?")
            issues = r["issues"]
            rooms = r.get("rooms", [])
            rps = r.get("rate_plans", [])
            mp = r.get("marketplace_has_medici", False)
            db = RATEBYCAT.get(vid, [])

            print(f"\n--- Venue #{vid} {name} ---")

            # Rooms vs DB comparison
            for room in rooms:
                pms = room["pms"]
                short = room["short"]
                # Find matching DB entry
                matching_db = [d for d in db if d["itc"] == pms]
                if pms and not matching_db:
                    # Check case-insensitive
                    ci_match = [d for d in db if d["itc"].lower() == pms.lower()]
                    if ci_match:
                        print(f"  ⚠ {room['title']}: CASE MISMATCH — Noovy PMS='{pms}', DB InvTypeCode='{ci_match[0]['itc']}'")
                        all_issues.append({"venue": vid, "type": "CASE_MISMATCH", "noovy_pms": pms, "db_itc": ci_match[0]["itc"], "room": room["title"]})
                    else:
                        no_match = [d for d in db]
                        print(f"  ❌ {room['title']}: NO MATCH — Noovy PMS='{pms}', DB has: {[d['itc'] for d in no_match]}")
                        all_issues.append({"venue": vid, "type": "NO_MATCH", "noovy_pms": pms, "db_itcs": [d["itc"] for d in no_match], "room": room["title"]})
                elif not pms:
                    print(f"  ❌ {room['title']}: PMS CODE EMPTY")
                    all_issues.append({"venue": vid, "type": "PMS_EMPTY", "room": room["title"]})
                else:
                    print(f"  ✅ {room['title']}: PMS='{pms}' matches DB")

            # Rate plans
            has_ro = any("room only" in rp.lower() or rp.lower().startswith("ro") for rp in rps)
            has_refundable = any("refundable" in rp.lower() for rp in rps)
            if not has_ro and not has_refundable:
                print(f"  ⚠ No 'room only' rate plan! Has: {rps}")
                all_issues.append({"venue": vid, "type": "NO_RO_PLAN", "plans": rps})

            # Marketplace
            if not mp:
                print(f"  ⚠ Marketplace: Medici not found")
                all_issues.append({"venue": vid, "type": "NO_MARKETPLACE"})

        # Summary
        print("\n" + "=" * 100)
        print("ISSUES TO FIX IN NOOVY")
        print("=" * 100)

        pms_mismatches = [i for i in all_issues if i["type"] in ("CASE_MISMATCH", "NO_MATCH")]
        pms_empty = [i for i in all_issues if i["type"] == "PMS_EMPTY"]
        no_ro = [i for i in all_issues if i["type"] == "NO_RO_PLAN"]
        no_mp = [i for i in all_issues if i["type"] == "NO_MARKETPLACE"]

        if pms_mismatches:
            print(f"\n1. PMS CODE MISMATCHES ({len(pms_mismatches)}):")
            for i in pms_mismatches:
                if i["type"] == "CASE_MISMATCH":
                    print(f"   #{i['venue']} {i['room']}: Change Noovy PMS from '{i['noovy_pms']}' to '{i['db_itc']}' OR update DB InvTypeCode to '{i['noovy_pms']}'")
                else:
                    print(f"   #{i['venue']} {i['room']}: Noovy PMS='{i['noovy_pms']}', DB expects one of: {i['db_itcs']}")

        if pms_empty:
            print(f"\n2. PMS CODES EMPTY ({len(pms_empty)}):")
            for i in pms_empty:
                print(f"   #{i['venue']} {i['room']}")

        if no_ro:
            print(f"\n3. NO 'room only' RATE PLAN ({len(no_ro)}):")
            for i in no_ro:
                print(f"   #{i['venue']}: has {i['plans']}")

        if no_mp:
            print(f"\n4. MARKETPLACE NOT CONFIGURED ({len(no_mp)}):")
            for i in no_mp:
                print(f"   #{i['venue']}")

        if not all_issues:
            print("\nAll settings look correct in Noovy!")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
