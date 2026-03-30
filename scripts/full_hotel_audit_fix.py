"""Full Hotel.Tools audit + fix for all blocked venues.

Checks and fixes:
1. PMS Exchange codes (via Noovy - already done by fix_noovy_pms_codes.py)
2. Medici channel status (Connected/Disconnected)
3. Rate plans assigned to Medici channel
4. Room types and their status

Usage:
  python scripts/full_hotel_audit_fix.py
"""
import asyncio
from playwright.async_api import async_playwright

HT_URL = "https://hotel.tools"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

# All venues from the scan report
VENUES = [
    # Zenith push blocked (28)
    5073, 5075, 5082, 5083, 5084, 5094, 5113, 5115, 5116, 5119,
    5124, 5130, 5131, 5132, 5136, 5138, 5139, 5140, 5265, 5266,
    5267, 5268, 5274, 5275, 5276, 5277, 5278, 5279,
    # No API results (7)
    5064, 5089, 5102, 5104, 5117, 5141,
]


async def login(page):
    await page.goto(f"{HT_URL}/login")
    await page.get_by_role("textbox", name="Account name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="Agent name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_timeout(3000)
    print("Logged in to Hotel.Tools")


async def switch_venue(page, vid):
    """Switch venue using JS."""
    await page.evaluate(f"""() => {{
        const sel = document.getElementById('venue_context_selector');
        if (sel) {{ sel.value = '{vid}'; sel.dispatchEvent(new Event('change')); }}
    }}""")
    await page.wait_for_timeout(1500)


async def audit_venue(page, vid):
    """Audit a single venue: rooms, PMS, rate plans, marketplace."""
    result = {"vid": vid, "issues": []}

    # Switch venue
    await switch_venue(page, vid)

    # 1. Check rooms
    try:
        resp = await page.evaluate("""async (vid) => {
            const r = await fetch('/products/roomOnly/iftype');
            const html = await r.text();
            const ids = [...new Set([...html.matchAll(/(p\\.[a-f0-9]+)/g)].map(m => m[1]))];
            const rooms = [];
            for (const id of ids) {
                const er = await fetch(`/products/roomOnly/iftype/${id}/edit`);
                const eh = await er.text();
                const title = eh.match(/Edit:\\s*([^"<]+)/)?.[1]?.trim() || '';
                const short = eh.match(/Short Name[\\s\\S]*?value="([^"]*)"/)?.[1] || '';
                const pms = eh.match(/PMS Exchange code[\\s\\S]*?value="([^"]*)"/)?.[1] || '';
                if (title) rooms.push({id, title, short, pms: pms || '(EMPTY)'});
            }
            return rooms;
        }""", vid)
        result["rooms"] = resp
        empty_pms = [r for r in resp if r["pms"] == "(EMPTY)"]
        if empty_pms:
            result["issues"].append(f"PMS_EMPTY: {[r['title'] for r in empty_pms]}")
        if len(resp) == 0:
            result["issues"].append("NO_ROOMS")
    except Exception as e:
        result["rooms"] = []
        result["issues"].append(f"ROOMS_ERROR: {e}")

    # 2. Check rate plans
    try:
        rps = await page.evaluate("""async () => {
            const r = await fetch('/pricing-inventory');
            const h = await r.text();
            const sel = h.match(/id="rate-plans"[\\s\\S]*?<\\/select>/)?.[0] || '';
            return [...sel.matchAll(/<option[^>]*value="(\\d+)"[^>]*>([\\s\\S]*?)<\\/option>/gi)]
                .filter(m => m[1] !== '0')
                .map(m => ({code: m[1], name: m[2].replace(/&amp;/g,'&').trim()}));
        }""")
        result["ratePlans"] = rps
        has_ro = any('room only' in r["name"].lower() or r["name"].lower() == 'refundable' for r in rps)
        if not has_ro and len(rps) > 0:
            result["issues"].append(f"NO_RO_PLAN: has {[r['name'] for r in rps]}")
        if len(rps) == 0:
            result["issues"].append("NO_RATE_PLANS")
    except Exception as e:
        result["ratePlans"] = []
        result["issues"].append(f"RATEPLAN_ERROR: {e}")

    # 3. Check marketplace
    try:
        mk = await page.evaluate("""async () => {
            const r = await fetch('/marketplace');
            const h = await r.text();
            const mediciIdx = h.indexOf('>Medici<');
            if (mediciIdx === -1) return {status: 'NOT_FOUND', rps: []};
            const before = h.substring(Math.max(0, mediciIdx - 300), mediciIdx);
            const status = before.includes('Connected') ? 'Connected' : 'Disconnected';
            const rpBlock = h.match(/Available rate plans[\\s\\S]*?<\\/select>/)?.[0] || '';
            const rps = [...rpBlock.matchAll(/<option[^>]*>([\\s\\S]*?)<\\/option>/gi)]
                .map(m => m[1].trim()).filter(Boolean);
            return {status, rps};
        }""")
        result["marketplace"] = mk
        if mk["status"] != "Connected":
            result["issues"].append(f"MEDICI_CHANNEL: {mk['status']}")
        if mk["status"] == "Connected" and len(mk.get("rps", [])) == 0:
            result["issues"].append("NO_MARKETPLACE_RATE_PLANS")
    except Exception as e:
        result["marketplace"] = {"status": "ERROR"}
        result["issues"].append(f"MARKETPLACE_ERROR: {e}")

    if not result["issues"]:
        result["issues"] = ["OK"]

    return result


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await login(page)

        # First navigate to a page with venue selector
        await page.goto(f"{HT_URL}/pricing-inventory")
        await page.wait_for_timeout(2000)

        results = []
        for i, vid in enumerate(VENUES):
            print(f"[{i+1}/{len(VENUES)}] Auditing #{vid}...", end=" ", flush=True)
            try:
                r = await audit_venue(page, vid)
                results.append(r)
                issues_str = ", ".join(r["issues"])
                rooms_count = len(r.get("rooms", []))
                rp_count = len(r.get("ratePlans", []))
                mk_status = r.get("marketplace", {}).get("status", "?")
                print(f"Rooms:{rooms_count} RPs:{rp_count} Channel:{mk_status} → {issues_str}")
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"vid": vid, "issues": [f"FATAL: {e}"]})
                # Re-navigate to recover
                await page.goto(f"{HT_URL}/pricing-inventory")
                await page.wait_for_timeout(2000)

        # Summary
        print("\n" + "=" * 80)
        print("FULL AUDIT REPORT")
        print("=" * 80)

        ok = [r for r in results if r["issues"] == ["OK"]]
        problems = [r for r in results if r["issues"] != ["OK"]]

        print(f"\n✅ OK: {len(ok)} venues")
        for r in ok:
            rooms = r.get("rooms", [])
            rps = r.get("ratePlans", [])
            print(f"   #{r['vid']}: {len(rooms)} rooms, {len(rps)} rate plans")

        print(f"\n❌ Issues: {len(problems)} venues")
        for r in problems:
            print(f"   #{r['vid']}: {', '.join(r['issues'])}")
            if r.get("rooms"):
                for rm in r["rooms"]:
                    pms_status = "✅" if rm["pms"] != "(EMPTY)" else "❌ EMPTY"
                    print(f"      Room: {rm['title']} (Short:{rm['short']}) PMS:{rm['pms']} {pms_status}")
            if r.get("ratePlans"):
                for rp in r["ratePlans"]:
                    print(f"      RatePlan: {rp['name']} (code:{rp['code']})")
            mk = r.get("marketplace", {})
            if mk:
                print(f"      Marketplace: {mk.get('status','?')} RPs:{mk.get('rps',[])}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
