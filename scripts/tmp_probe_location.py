"""Deep probe of Location tab and PMS code for venue 5080."""
import asyncio, json
from playwright.async_api import async_playwright

HT_URL = "https://hotel.tools"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1700, "height": 1100})

        # Login
        await page.goto(f"{HT_URL}/today-dashboard")
        await page.wait_for_timeout(2000)
        await page.get_by_role("textbox", name="Account name").fill("Medici LIVE")
        await page.get_by_role("textbox", name="Agent name").fill("zvi")
        await page.get_by_role("textbox", name="Password").fill("karpad66")
        await page.get_by_role("button", name="Login").click()
        await page.wait_for_url("**/today-dashboard**", timeout=15000)
        print("Logged in.\n")

        # Go to existing product for 5080 to see how location looks
        # First, check products list for 5080
        await page.goto(f"{HT_URL}/products")
        await page.wait_for_timeout(2000)
        await page.evaluate("""() => {
            const sel = document.getElementById('venue_context_selector');
            if (sel) { sel.value = '5080'; sel.dispatchEvent(new Event('change',{bubbles:true})); }
        }""")
        await page.wait_for_timeout(2000)
        btn = page.get_by_role("button", name="search").first
        if await btn.count() > 0:
            try: await btn.click()
            except: pass
        await page.wait_for_timeout(2000)

        # Get product links
        products = await page.evaluate("""() => {
            return [...document.querySelectorAll('table tbody tr')].map(r => {
                const cells = r.querySelectorAll('td');
                const link = r.querySelector('a');
                return {
                    name: cells.length >= 2 ? cells[1].textContent.trim() : '',
                    href: link ? link.href : '',
                    id: link ? link.href.split('/').pop() : ''
                };
            });
        }""")
        print("Products for 5080:", json.dumps(products, indent=2))

        # Open the first product (e.g. Standard) to study its Location tab
        if products and products[0].get("href"):
            edit_url = products[0]["href"].replace("/products/", "/products/edit/") if "/edit/" not in products[0]["href"] else products[0]["href"]
            # Try to find the edit link
            first_link = await page.evaluate("""() => {
                const a = document.querySelector('table tbody tr a');
                return a ? a.href : null;
            }""")
            if first_link:
                print(f"\nOpening product: {first_link}")
                await page.goto(first_link)
                await page.wait_for_timeout(3000)

                # Check current URL
                print(f"Current URL: {page.url}")

                # Look at Locations tab in edit mode
                loc_tab = page.locator('a[href="#products_form_locations"]')
                if await loc_tab.count() > 0:
                    await loc_tab.click()
                    await page.wait_for_timeout(1500)

                # Dump the FULL HTML of locations panel
                loc_html = await page.evaluate("""() => {
                    const panel = document.getElementById('products_form_locations');
                    return panel ? panel.innerHTML.substring(0, 5000) : 'NOT FOUND';
                }""")
                print(f"\nLocations panel HTML:\n{loc_html}")

                # Also check PMS code field
                gen_tab = page.locator('a[href="#products_form_general"]')
                if await gen_tab.count() > 0:
                    await gen_tab.click()
                    await page.wait_for_timeout(500)

                pms_info = await page.evaluate("""() => {
                    const el = document.querySelector('#rnd-f-pms_code');
                    if (!el) return 'Element #rnd-f-pms_code NOT FOUND';
                    return {
                        id: el.id, name: el.name, type: el.type, value: el.value,
                        disabled: el.disabled, visible: el.offsetParent !== null,
                        parent: el.parentElement ? el.parentElement.className : 'none',
                        tagName: el.tagName
                    };
                }""")
                print(f"\nPMS code field: {json.dumps(pms_info)}")

                # Check ALL inputs with "pms" in name or id
                pms_all = await page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('input, select, textarea').forEach(el => {
                        const id = (el.id || '').toLowerCase();
                        const name = (el.name || '').toLowerCase();
                        if (id.includes('pms') || name.includes('pms') || name.includes('meta')) {
                            results.push({
                                tag: el.tagName, id: el.id, name: el.name,
                                type: el.type, value: el.value,
                                visible: el.offsetParent !== null
                            });
                        }
                    });
                    return results;
                }""")
                print(f"\nAll PMS/meta fields: {json.dumps(pms_all, indent=2)}")

        # Now go to /products/new and capture the Save Location AJAX behavior
        print("\n\n=== PROBING /products/new ===")
        await page.goto(f"{HT_URL}/products/new")
        await page.wait_for_timeout(2500)

        # Set venue context
        await page.evaluate("""() => {
            const sel = document.getElementById('venue_context_selector');
            if (sel) { sel.value = '5080'; sel.dispatchEvent(new Event('change',{bubbles:true})); }
        }""")
        await page.wait_for_timeout(1500)

        # Capture network requests
        requests_log = []
        def on_request(req):
            if req.method in ("POST", "PUT", "PATCH"):
                requests_log.append({"method": req.method, "url": req.url, "postData": (req.post_data or "")[:500]})
        page.on("request", on_request)

        # Go to locations tab
        loc_tab = page.locator('a[href="#products_form_locations"]')
        if await loc_tab.count() > 0:
            await loc_tab.click()
            await page.wait_for_timeout(1000)

        # Set location type
        await page.evaluate("""() => {
            const panel = document.getElementById('products_form_locations');
            const sels = panel.querySelectorAll('select');
            if (sels.length >= 1) {
                sels[0].value = 'venue';
                sels[0].dispatchEvent(new Event('change', { bubbles: true }));
                if (typeof $ !== 'undefined') $(sels[0]).val('venue').trigger('change');
            }
        }""")
        await page.wait_for_timeout(2000)

        # Set country
        await page.evaluate("""() => {
            const csel = document.querySelector('[data-control="country-selector"]');
            if (csel) {
                csel.value = 'US';
                csel.dispatchEvent(new Event('change', { bubbles: true }));
                if (typeof $ !== 'undefined') $(csel).val('US').trigger('change');
            }
        }""")
        await page.wait_for_timeout(2000)

        # Set venue
        await page.evaluate("""() => {
            const vsel = document.querySelector('select[name="venue"]');
            if (vsel) {
                vsel.value = '5080';
                vsel.dispatchEvent(new Event('change', { bubbles: true }));
                if (typeof $ !== 'undefined') $(vsel).val('5080').trigger('change');
            }
        }""")
        await page.wait_for_timeout(1500)

        # Before clicking save, dump location panel HTML
        loc_html_new = await page.evaluate("""() => {
            const panel = document.getElementById('products_form_locations');
            return panel ? panel.innerHTML.substring(0, 5000) : 'NOT FOUND';
        }""")
        print(f"\nLocations panel BEFORE save:\n{loc_html_new[:2000]}")

        # Click Save Location
        await page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if (b.textContent.trim() === 'Save Location') { b.click(); return 'clicked'; }
            }
            return 'not found';
        }""")
        await page.wait_for_timeout(3000)

        # After clicking save
        loc_html_after = await page.evaluate("""() => {
            const panel = document.getElementById('products_form_locations');
            return panel ? panel.innerHTML.substring(0, 5000) : 'NOT FOUND';
        }""")
        print(f"\nLocations panel AFTER save:\n{loc_html_after[:2000]}")

        # Check for any network requests triggered by Save Location
        print(f"\nNetwork requests during location save: {json.dumps(requests_log, indent=2)}")

        # Check for hidden inputs that might store location data
        hidden_loc = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('input[type="hidden"]').forEach(el => {
                const name = el.name || '';
                if (name.includes('location') || name.includes('venue') || name.includes('loca')) {
                    results.push({ name: el.name, value: el.value, id: el.id });
                }
            });
            // Also check for any dynamically added inputs
            document.querySelectorAll('input').forEach(el => {
                const name = el.name || '';
                if (name.includes('location') || name.includes('venue')) {
                    results.push({ name: el.name, value: el.value, type: el.type, id: el.id });
                }
            });
            return results;
        }""")
        print(f"\nHidden location inputs: {json.dumps(hidden_loc, indent=2)}")

        page.remove_listener("request", on_request)
        await browser.close()

asyncio.run(main())
