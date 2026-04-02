"""
Audit and create missing Products in Hotel.Tools for all Miami hotels.

TWO PHASES:
  Phase 1 (default): AUDIT — login, check each venue's products, report missing
  Phase 2 (--create): CREATE — read audit report, create missing products

Usage:
  python scripts/create_all_products.py                    # Audit only
  python scripts/create_all_products.py --create           # Create missing products
  python scripts/create_all_products.py --venue 5080       # Single venue audit
  python scripts/create_all_products.py --venue 5080 --create  # Create for single venue
  python scripts/create_all_products.py --headed           # Show browser
  python scripts/create_all_products.py --dry-run          # Show what would be created
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# ── Credentials ──────────────────────────────────────────────────────────────
HT_URL = "https://hotel.tools"
ACCOUNT = os.getenv("NOOVY_ACCOUNT", "Medici LIVE")
USER = os.getenv("NOOVY_USER", "zvi")
PASSWORD = os.getenv("NOOVY_PASS", "karpad66")

# ── ITC to Product mapping ───────────────────────────────────────────────────
ITC_TO_PRODUCT = {
    "Stnd":  {"title": "Standard",       "short": "Stnd",  "pms": "Stnd"},
    "DLX":   {"title": "Deluxe",         "short": "DLX",   "pms": "DLX"},
    "Suite": {"title": "Suite",          "short": "Suite", "pms": "Suite"},
    "SPR":   {"title": "Superior",       "short": "SPR",   "pms": "SPR"},
    "APT":   {"title": "Apartment",      "short": "APT",   "pms": "APT"},
    "DRM":   {"title": "Dormitory",      "short": "DRM",   "pms": "DRM"},
    "EXEC":  {"title": "Executive",      "short": "EXEC",  "pms": "EXEC"},
    "DBL":   {"title": "Double",         "short": "DBL",   "pms": "DBL"},
    "OV2Q":  {"title": "Ocean View",     "short": "OV2Q",  "pms": "OV2Q"},
    "1QSR":  {"title": "Queen Standard", "short": "1QSR",  "pms": "1QSR"},
}

# ── Miami hotels and required ITC codes ──────────────────────────────────────
MIAMI_HOTELS = {
    5064: {"name": "Hotel Chelsea",              "itc": ["Stnd"]},
    5073: {"name": "Loews Miami Beach",          "itc": ["Stnd", "DLX", "Suite"]},
    5075: {"name": "Villa Casa Casuarina",       "itc": ["Stnd", "Suite"]},
    5077: {"name": "SLS LUX Brickell",           "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5079: {"name": "citizenM Brickell",          "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5080: {"name": "Pullman Miami Airport",      "itc": ["Stnd", "DLX", "SPR", "Suite", "APT", "EXEC"]},
    5081: {"name": "Embassy Suites",             "itc": ["Stnd", "DLX", "SPR", "Suite", "DRM"]},
    5082: {"name": "DoubleTree Doral",           "itc": ["Stnd", "Suite"]},
    5083: {"name": "Hilton Miami Airport",       "itc": ["Stnd", "DLX", "Suite", "DRM"]},
    5084: {"name": "Hilton Downtown",            "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5089: {"name": "Fairwind Hotel",             "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5090: {"name": "Dream South Beach",          "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5092: {"name": "Iberostar Berkeley",         "itc": ["Stnd", "SPR", "APT"]},
    5093: {"name": "Hilton Bentley SB",          "itc": ["Stnd", "DLX", "SPR", "Suite", "APT"]},
    5094: {"name": "Grayson Hotel",              "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5095: {"name": "Cadet Hotel",                "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5096: {"name": "Marseilles Hotel",           "itc": ["Stnd", "DLX", "SPR", "Suite", "DRM"]},
    5097: {"name": "Hyatt Centric SB",           "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5098: {"name": "Eurostars Langford",         "itc": ["Stnd", "DLX", "SPR", "Suite", "APT", "DRM", "EXEC"]},
    5100: {"name": "Crystal Beach Suites",       "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5101: {"name": "Atwell Suites Brickell",     "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5102: {"name": "Notebook Miami Beach",       "itc": ["Stnd"]},
    5103: {"name": "Savoy Hotel",                "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5104: {"name": "Sole Miami",                 "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5105: {"name": "MB Hotel",                   "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5106: {"name": "Hampton Inn Mid Beach",      "itc": ["Stnd", "DLX"]},
    5107: {"name": "Freehand Miami",             "itc": ["Stnd", "DLX", "SPR", "Suite", "DRM"]},
    5108: {"name": "Gabriel South Beach",        "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5109: {"name": "Riu Plaza Miami Beach",      "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5110: {"name": "Breakwater South Beach",     "itc": ["Stnd", "DLX", "SPR", "Suite", "APT"]},
    5111: {"name": "Viajero Miami",              "itc": ["Stnd", "DLX", "SPR"]},
    5113: {"name": "Cavalier Hotel",             "itc": ["Stnd", "DLX"]},
    5115: {"name": "Hilton Cabana",              "itc": ["Stnd", "DLX", "SPR", "Suite", "DRM"]},
    5116: {"name": "Kimpton Palomar",            "itc": ["Stnd"]},
    5117: {"name": "Albion Hotel",               "itc": ["Stnd", "DLX", "APT", "DRM"]},
    5119: {"name": "citizenM South Beach",       "itc": ["Stnd"]},
    5124: {"name": "Grand Beach Hotel",          "itc": ["Stnd", "Suite"]},
    5130: {"name": "Holiday Inn Express",        "itc": ["Stnd", "Suite"]},
    5131: {"name": "Hotel Croydon",              "itc": ["Stnd", "Suite"]},
    5132: {"name": "Hotel Gaythering",           "itc": ["Stnd", "DLX"]},
    5136: {"name": "Kimpton Anglers",            "itc": ["Stnd", "DLX", "APT", "Suite"]},
    5138: {"name": "Landon Bay Harbor",          "itc": ["Stnd", "DLX"]},
    5139: {"name": "SERENA Aventura",            "itc": ["Stnd", "DLX", "SPR", "Suite"]},
    5140: {"name": "Gates Hotel SB",             "itc": ["Stnd"]},
    5141: {"name": "Metropole South Beach",      "itc": ["Stnd"]},
    5265: {"name": "Hotel Belleza",              "itc": ["Stnd", "SPR", "DBL"]},
    5266: {"name": "Dorchester Hotel",           "itc": ["Stnd", "Suite", "APT", "DBL"]},
    5267: {"name": "Gale South Beach",           "itc": ["Stnd", "Suite", "1QSR"]},
    5268: {"name": "Fontainebleau",              "itc": ["Stnd", "DLX", "Suite", "APT", "OV2Q"]},
    5274: {"name": "Generator Miami",            "itc": ["Stnd", "DLX", "SPR", "Suite", "DRM"]},
    5275: {"name": "Miami Intl Airport Hotel",   "itc": ["Stnd"]},
    5276: {"name": "InterContinental Miami",     "itc": ["Stnd", "DLX", "Suite"]},
    5277: {"name": "Catalina Hotel",             "itc": ["Stnd", "Suite", "EXEC"]},
    5278: {"name": "Gale Miami Hotel",           "itc": ["Stnd", "Suite", "APT"]},
    5279: {"name": "Hilton Garden Inn SB",       "itc": ["Stnd"]},
}

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

REPORT_PATH = Path(__file__).parent / "product_audit_report.json"


# ── Hotel.Tools helpers ──────────────────────────────────────────────────────

async def set_venue_context(page, venue_id: int):
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


async def get_existing_products(page, venue_id: int) -> list[str]:
    """Navigate to /products for a venue and return list of existing product titles (lowercase)."""
    await page.goto(f"{HT_URL}/products")
    await page.wait_for_timeout(2000)
    await set_venue_context(page, venue_id)

    existing = await page.evaluate("""() => {
        return [...document.querySelectorAll('table tbody tr')].map(r => {
            const cells = r.querySelectorAll('td');
            return cells.length >= 2 ? cells[1].textContent.trim().toLowerCase() : '';
        }).filter(t => t.length > 0);
    }""")
    return existing


async def create_product(page, venue_id: int, title: str, short_name: str, pms_code: str) -> bool:
    """Create a product in Hotel.Tools using the form workflow."""
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

    # Step 2a: Set location type to "venue"
    await page.evaluate("""() => {
        const panel = document.getElementById('products_form_locations');
        if (!panel) return;
        const selects = panel.querySelectorAll('select');
        if (selects.length >= 1) {
            const sel = selects[0];
            sel.value = 'venue';
            sel.dispatchEvent(new Event('change', { bubbles: true }));
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
    print(f"      Location selects: {json.dumps(loc_vals)}")

    # Click "Save Location"
    save_result = await page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const txt = b.textContent.trim();
            if (txt === 'Save Location' || txt === 'save location') {
                b.click();
                return 'clicked: ' + txt;
            }
        }
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
    print(f"      Save Location: {save_result}")
    await page.wait_for_timeout(2500)

    # Check location saved
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
    print(f"      Location entries: {loc_entries}")

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
    print(f"      Form: {json.dumps(form)}")

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

    print(f"      POST response: {resp_status['code']}")

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
        print(f"      {RED}Errors: {errors}{RESET}")

    return resp_status["code"] in (200, 201, 302)


async def login(page):
    """Login to Hotel.Tools."""
    print(f"{CYAN}Logging in to Hotel.Tools as {USER}@{ACCOUNT}...{RESET}")
    await page.goto(f"{HT_URL}/today-dashboard")
    await page.wait_for_timeout(2000)
    await page.get_by_role("textbox", name="Account name").fill(ACCOUNT)
    await page.get_by_role("textbox", name="Agent name").fill(USER)
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Login").click()
    await page.wait_for_url("**/today-dashboard**", timeout=15000)
    print(f"{GREEN}Logged in successfully.{RESET}\n")


# ── Phase 1: AUDIT ──────────────────────────────────────────────────────────

async def run_audit(page, venue_filter=None):
    """Audit all venues, return report dict."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_venues": 0,
        "total_required": 0,
        "total_existing": 0,
        "total_missing": 0,
        "venues": {},
    }

    hotels = MIAMI_HOTELS
    if venue_filter:
        if venue_filter not in hotels:
            print(f"{RED}Venue {venue_filter} not in MIAMI_HOTELS list.{RESET}")
            return report
        hotels = {venue_filter: hotels[venue_filter]}

    report["total_venues"] = len(hotels)

    for vid, info in sorted(hotels.items()):
        name = info["name"]
        required_itcs = info["itc"]
        required_titles = [ITC_TO_PRODUCT[itc]["title"].lower() for itc in required_itcs]

        print(f"{BOLD}[{vid}] {name}{RESET}  (requires: {', '.join(required_itcs)})")

        try:
            existing = await get_existing_products(page, vid)
            existing_lower = [e.lower() for e in existing]
        except Exception as e:
            print(f"  {RED}ERROR reading products: {e}{RESET}")
            report["venues"][str(vid)] = {
                "name": name,
                "error": str(e)[:200],
                "existing": [],
                "missing": [],
                "required": required_itcs,
            }
            continue

        missing_itcs = []
        for itc in required_itcs:
            product_info = ITC_TO_PRODUCT[itc]
            title_lower = product_info["title"].lower()
            if title_lower in existing_lower:
                print(f"  {GREEN}  [OK] {product_info['title']} ({itc}){RESET}")
                report["total_existing"] += 1
            else:
                print(f"  {YELLOW}  [MISSING] {product_info['title']} ({itc}){RESET}")
                missing_itcs.append(itc)
                report["total_missing"] += 1

        report["total_required"] += len(required_itcs)
        report["venues"][str(vid)] = {
            "name": name,
            "required": required_itcs,
            "existing": existing,
            "missing": missing_itcs,
        }
        print()

    # Save report
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'='*70}")
    print(f"{BOLD}AUDIT SUMMARY{RESET}")
    print(f"  Venues scanned:    {report['total_venues']}")
    print(f"  Products required: {report['total_required']}")
    print(f"  Products existing: {GREEN}{report['total_existing']}{RESET}")
    print(f"  Products missing:  {YELLOW}{report['total_missing']}{RESET}")
    print(f"  Report saved:      {REPORT_PATH}")
    print(f"{'='*70}")

    # Missing per venue
    if report["total_missing"] > 0:
        print(f"\n{BOLD}Missing products by venue:{RESET}")
        for vid_str, vdata in report["venues"].items():
            if vdata.get("missing"):
                labels = [f"{itc} ({ITC_TO_PRODUCT[itc]['title']})" for itc in vdata["missing"]]
                print(f"  {YELLOW}{vid_str} {vdata['name']}: {', '.join(labels)}{RESET}")

    return report


# ── Phase 2: CREATE ──────────────────────────────────────────────────────────

async def run_create(page, venue_filter=None, dry_run=False):
    """Read audit report and create missing products."""
    if not REPORT_PATH.exists():
        print(f"{RED}No audit report found at {REPORT_PATH}.{RESET}")
        print(f"Run without --create first to generate the audit report.")
        return

    with open(REPORT_PATH) as f:
        report = json.load(f)

    results = {"created": [], "skipped": [], "errors": [], "dry_run": []}

    for vid_str, vdata in sorted(report["venues"].items(), key=lambda x: int(x[0])):
        vid = int(vid_str)
        name = vdata["name"]
        missing = vdata.get("missing", [])

        if venue_filter and vid != venue_filter:
            continue

        if not missing:
            continue

        print(f"\n{BOLD}[{vid}] {name} — {len(missing)} missing product(s){RESET}")

        for itc in missing:
            product_info = ITC_TO_PRODUCT[itc]
            title = product_info["title"]
            short = product_info["short"]
            pms = product_info["pms"]

            if dry_run:
                print(f"  {CYAN}[DRY-RUN] Would create: {title} ({pms}) for venue {vid}{RESET}")
                results["dry_run"].append({"venueId": vid, "hotel": name, "product": title, "pms": pms})
                continue

            print(f"  {CYAN}Creating {title} ({pms})...{RESET}")

            try:
                ok = await create_product(page, vid, title, short, pms)

                # Verify
                existing_after = await get_existing_products(page, vid)
                exists_after = title.lower() in [e.lower() for e in existing_after]

                if exists_after:
                    print(f"  {GREEN}  OK: '{title}' ({pms}) created for venue {vid}{RESET}")
                    results["created"].append({"venueId": vid, "hotel": name, "product": title, "pms": pms})
                elif ok:
                    print(f"  {YELLOW}  UNCERTAIN: POST ok but product not visible in list{RESET}")
                    results["created"].append({
                        "venueId": vid, "hotel": name, "product": title,
                        "pms": pms, "note": "uncertain"
                    })
                else:
                    print(f"  {RED}  FAILED: '{title}' not created for venue {vid}{RESET}")
                    results["errors"].append({
                        "venueId": vid, "hotel": name, "product": title,
                        "error": "POST failed or product not found after creation"
                    })

            except Exception as e:
                print(f"  {RED}  ERROR: {type(e).__name__}: {e}{RESET}")
                results["errors"].append({
                    "venueId": vid, "hotel": name, "product": title,
                    "error": f"{type(e).__name__}: {str(e)[:100]}"
                })

    # Summary
    print(f"\n{'='*70}")
    print(f"{BOLD}CREATE SUMMARY{RESET}")
    if dry_run:
        print(f"  {CYAN}DRY RUN — no products were actually created{RESET}")
        print(f"  Would create: {len(results['dry_run'])} products")
        for r in results["dry_run"]:
            print(f"    + {r['venueId']} {r['hotel']}: {r['product']} ({r['pms']})")
    else:
        print(f"  Created:  {GREEN}{len(results['created'])}{RESET}")
        print(f"  Errors:   {RED}{len(results['errors'])}{RESET}")
        for r in results["created"]:
            note = f" ({r['note']})" if r.get("note") else ""
            print(f"    {GREEN}+ {r['venueId']} {r['hotel']}: {r['product']} ({r['pms']}){note}{RESET}")
        for r in results["errors"]:
            print(f"    {RED}! {r['venueId']} {r['hotel']}: {r['product']} — {r['error']}{RESET}")
    print(f"{'='*70}")

    # Save creation results
    results_path = Path(__file__).parent / "product_create_results.json"
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            **results,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Results saved: {results_path}")

    return results


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Audit & create Hotel.Tools products for Miami hotels")
    parser.add_argument("--create", action="store_true", help="Create missing products (Phase 2)")
    parser.add_argument("--venue", type=int, default=None, help="Process a single venue ID (e.g., 5080)")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode for debugging")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without doing it")
    args = parser.parse_args()

    headless = not args.headed

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1700, "height": 1100})
        page = await context.new_page()

        await login(page)

        if args.create:
            if args.dry_run:
                # Dry run doesn't need browser after login, but we keep it for consistency
                await run_create(page, venue_filter=args.venue, dry_run=True)
            else:
                await run_create(page, venue_filter=args.venue, dry_run=False)
        else:
            await run_audit(page, venue_filter=args.venue)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
