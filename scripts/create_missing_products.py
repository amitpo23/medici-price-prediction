"""
Create missing Products in Hotel.Tools for 8 venues with partial push.

Uses the Locations tab workflow:
1. Fill General tab fields
2. Switch to Locations tab, select venue, Save Location
3. Switch back to General tab and Submit

Products needed:
  5080 Pullman     — APT (Apartment)
  5095 Cadet Hotel — SPR (Superior)
  5096 Marseilles  — DLX (Deluxe)
  5098 Eurostars   — EXEC (Executive)
  5103 Savoy       — DLX (Deluxe)
  5106 Hampton Inn — DLX (Deluxe)
  5110 Breakwater  — APT (Apartment)
  5113 Cavalier    — DLX (Deluxe)
"""
import asyncio
import json
from playwright.async_api import async_playwright

HT_URL = "https://hotel.tools"
ACCOUNT = "Medici LIVE"
USER = "zvi"
PASSWORD = "karpad66"

TASKS = [
    {"venueId": 5080, "hotel": "Pullman",     "title": "Apartment",  "short": "APT",  "pms": "APT"},
    {"venueId": 5095, "hotel": "Cadet Hotel",  "title": "Superior",   "short": "SPR",  "pms": "SPR"},
    {"venueId": 5096, "hotel": "Marseilles",   "title": "Deluxe",     "short": "DLX",  "pms": "DLX"},
    {"venueId": 5098, "hotel": "Eurostars",    "title": "Executive",  "short": "EXEC", "pms": "EXEC"},
    # 5103 Savoy, 5106 Hampton Inn, 5113 Cavalier — already have Deluxe (verified)
    {"venueId": 5110, "hotel": "Breakwater",   "title": "Apartment",  "short": "APT",  "pms": "APT"},
]


async def set_venue_context(page, venue_id):
    """Switch top-level Hotel.Tools venue context."""
    await page.evaluate(f"""() => {{
        const sel = document.getElementById('venue_context_selector');
        if (sel) {{
            sel.value = '{venue_id}';
            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}""")
    await page.wait_for_timeout(1500)
    search_btn = page.get_by_role("button", name="search").first
    if await search_btn.count() > 0:
        try:
            await search_btn.click()
        except Exception:
            pass
    await page.wait_for_timeout(1500)


async def check_product_exists(page, venue_id, product_title):
    """Check if product already exists for venue."""
    await page.goto(f"{HT_URL}/products")
    await page.wait_for_timeout(2000)
    await set_venue_context(page, venue_id)

    existing = await page.evaluate("""() => {
        return [...document.querySelectorAll('table tbody tr')].map(r => {
            const cells = r.querySelectorAll('td');
            return cells.length >= 2 ? cells[1].textContent.trim().toLowerCase() : '';
        });
    }""")
    return product_title.lower() in existing


async def create_product(page, venue_id, title, short_name, pms_code):
    """Create a product in Hotel.Tools using proper form workflow."""
    await page.goto(f"{HT_URL}/products/new")
    await page.wait_for_timeout(2500)

    # Set venue context
    await set_venue_context(page, venue_id)

    # ====== STEP 1: Fill General tab ======
    await page.evaluate(f"""() => {{
        const set = (sel, val) => {{
            const el = document.querySelector(sel);
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }};
        set('#f-product-type', 'room');
        set('#f-title', '{title}');
        set('#f-short-name', '{short_name}');
        set('#f-base-price', '500');
        set('#f-base-currency', 'USD');
        set('#f-max-occupancy', '2');
        set('#f-status', '1');
        set('#rnd-f-pms_code', '{pms_code}');
        set('#f-start-date', '2025-01-01');
        set('#f-alt-start-date', '2025-01-01');
        set('#f-end-date', '2027-12-31');
        set('#f-alt-end-date', '2027-12-31');
    }}""")
    await page.wait_for_timeout(500)

    # ====== STEP 2: Locations tab — add venue via select2 JS API ======
    loc_tab = page.locator('a[href="#products_form_locations"]')
    if await loc_tab.count() > 0:
        await loc_tab.click()
        await page.wait_for_timeout(1500)

    # All location selects use select2 — must use jQuery/select2 API, not native select
    # Step 2a: Set location type to "venue" using select2
    await page.evaluate("""() => {
        const panel = document.getElementById('products_form_locations');
        if (!panel) return;
        const selects = panel.querySelectorAll('select');
        // First select is location type
        if (selects.length >= 1) {
            const sel = selects[0];
            sel.value = 'venue';
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            // Also try jQuery/select2 trigger
            if (typeof $ !== 'undefined') {
                $(sel).val('venue').trigger('change');
            }
        }
    }""")
    await page.wait_for_timeout(2000)

    # Step 2b: Set country to "US"
    await page.evaluate("""() => {
        const csel = document.querySelector('[data-control="country-selector"]');
        if (csel) {
            csel.value = 'US';
            csel.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof $ !== 'undefined') {
                $(csel).val('US').trigger('change');
            }
        }
    }""")
    await page.wait_for_timeout(2500)

    # Step 2c: Set venue
    await page.evaluate(f"""() => {{
        const vsel = document.querySelector('select[name="venue"]');
        if (vsel) {{
            vsel.value = '{venue_id}';
            vsel.dispatchEvent(new Event('change', {{ bubbles: true }}));
            if (typeof $ !== 'undefined') {{
                $(vsel).val('{venue_id}').trigger('change');
            }}
        }}
    }}""")
    await page.wait_for_timeout(1500)

    # Verify location values
    loc_vals = await page.evaluate("""() => {
        const panel = document.getElementById('products_form_locations');
        if (!panel) return [];
        const sels = panel.querySelectorAll('select');
        return [...sels].map((s, i) => ({
            idx: i, name: s.name || s.dataset.control || s.className.substring(0,30),
            value: s.value, optCount: s.options.length, visible: s.offsetParent !== null
        }));
    }""")
    print(f"    Location selects: {json.dumps(loc_vals)}")

    # Click "Save Location" via JS
    save_result = await page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const txt = b.textContent.trim();
            if (txt === 'Save Location' || txt === 'save location') {
                b.click();
                return 'clicked: ' + txt;
            }
        }
        // Also try input[type=button]
        const inputs = document.querySelectorAll('input[type="button"], a.btn');
        for (const inp of inputs) {
            const txt = (inp.value || inp.textContent || '').trim();
            if (txt.toLowerCase().includes('save location')) {
                inp.click();
                return 'clicked input: ' + txt;
            }
        }
        return 'not found';
    }""")
    print(f"    Save Location: {save_result}")
    await page.wait_for_timeout(2500)

    # Check if location was saved
    loc_entries = await page.evaluate("""() => {
        const panel = document.getElementById('products_form_locations');
        if (!panel) return 'no panel';
        const items = panel.querySelectorAll('tr, .badge, .tag, .chip, .list-group-item, .location-item');
        const texts = [];
        items.forEach(el => {
            const t = el.textContent.trim();
            if (t && t.length > 2 && t.length < 200) texts.push(t.substring(0, 80));
        });
        return texts;
    }""")
    print(f"    Location entries: {loc_entries}")

    # ====== STEP 3: Switch back to General tab ======
    gen_tab = page.locator('a[href="#products_form_general"]')
    if await gen_tab.count() > 0:
        await gen_tab.click()
        await page.wait_for_timeout(500)

    # Verify form values
    form = await page.evaluate("""() => {
        const g = s => { const e = document.querySelector(s); return e ? e.value : 'N/A'; };
        return { title: g('#f-title'), short: g('#f-short-name'), price: g('#f-base-price'),
                 curr: g('#f-base-currency'), pms: g('#rnd-f-pms_code'), status: g('#f-status') };
    }""")
    print(f"    Form: {json.dumps(form)}")

    # ====== STEP 4: Submit ======
    resp_status = {"code": 0}
    def on_response(resp):
        if resp.request.method == "POST" and "products" in resp.url and "analytics" not in resp.url:
            resp_status["code"] = resp.status
    page.on("response", on_response)

    submit_btn = page.locator('button[type="submit"]').first
    await submit_btn.click()
    await page.wait_for_timeout(4000)

    page.remove_listener("response", on_response)

    print(f"    POST response: {resp_status['code']}")

    # Check errors
    errors = await page.evaluate("""() => {
        const msgs = [];
        document.querySelectorAll('.alert, [role="alert"], .text-danger, .error').forEach(el => {
            const t = el.textContent.trim();
            if (t && t.length > 2) msgs.push(t.substring(0, 100));
        });
        return msgs;
    }""")
    if errors:
        print(f"    Errors: {errors}")

    return resp_status["code"] in (200, 201, 302)


async def main():
    results = {"created": [], "skipped": [], "errors": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1700, "height": 1100})
        page = await context.new_page()

        # Login
        print("Logging in to Hotel.Tools...")
        await page.goto(f"{HT_URL}/today-dashboard")
        await page.wait_for_timeout(2000)
        await page.get_by_role("textbox", name="Account name").fill(ACCOUNT)
        await page.get_by_role("textbox", name="Agent name").fill(USER)
        await page.get_by_role("textbox", name="Password").fill(PASSWORD)
        await page.get_by_role("button", name="Login").click()
        await page.wait_for_url("**/today-dashboard**", timeout=15000)
        print("Logged in.\n")

        for task in TASKS:
            vid = task["venueId"]
            hotel = task["hotel"]
            title = task["title"]
            short = task["short"]
            pms = task["pms"]

            print(f"--- Venue {vid} ({hotel}) — Creating {title} ({pms}) ---")

            try:
                # Check if exists
                exists = await check_product_exists(page, vid, title)
                if exists:
                    print(f"  SKIP: '{title}' already exists")
                    results["skipped"].append({"venueId": vid, "hotel": hotel, "product": title})
                    continue

                # Create
                ok = await create_product(page, vid, title, short, pms)

                # Verify
                exists_after = await check_product_exists(page, vid, title)
                if exists_after:
                    print(f"  OK: '{title}' ({pms}) created for venue {vid}")
                    results["created"].append({"venueId": vid, "hotel": hotel, "product": title, "pms": pms})
                elif ok:
                    print(f"  UNCERTAIN: POST ok but product not in list — may need page refresh")
                    results["created"].append({"venueId": vid, "hotel": hotel, "product": title, "pms": pms, "note": "uncertain"})
                else:
                    print(f"  FAILED: '{title}' not created for venue {vid}")
                    results["errors"].append({"venueId": vid, "hotel": hotel, "product": title, "error": "POST failed"})

            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}")
                results["errors"].append({"venueId": vid, "hotel": hotel, "product": title, "error": str(e)[:100]})

        await context.close()
        await browser.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: Created={len(results['created'])} Skipped={len(results['skipped'])} Errors={len(results['errors'])}")
    for r in results["created"]:
        print(f"  + {r['venueId']} {r['hotel']}: {r['product']} ({r['pms']})")
    for r in results["skipped"]:
        print(f"  ~ {r['venueId']} {r['hotel']}: {r['product']}")
    for r in results["errors"]:
        print(f"  ! {r['venueId']} {r['hotel']}: {r['product']} — {r['error']}")


if __name__ == "__main__":
    asyncio.run(main())
