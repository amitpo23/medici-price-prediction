"""Debug: open Hotel.Tools product form and dump all form fields."""
import asyncio
import json
import os
from playwright.async_api import async_playwright

HT_URL = "https://hotel.tools"
ACCOUNT = os.getenv("NOOVY_ACCOUNT", "Medici LIVE")
USER = os.getenv("NOOVY_USER", "zvi")
PASSWORD = os.getenv("NOOVY_PASS", "karpad66")
VENUE = 5080  # Pullman


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1700, "height": 1100})
        page = await context.new_page()

        # Login
        print("Logging in...")
        await page.goto(f"{HT_URL}/today-dashboard")
        await page.wait_for_timeout(2000)
        await page.get_by_role("textbox", name="Account name").fill(ACCOUNT)
        await page.get_by_role("textbox", name="Agent name").fill(USER)
        await page.get_by_role("textbox", name="Password").fill(PASSWORD)
        await page.get_by_role("button", name="Login").click()
        await page.wait_for_url("**/today-dashboard**", timeout=15000)
        print("Logged in.\n")

        # Switch venue
        await page.evaluate(f"""() => {{
            const sel = document.getElementById('venue_context_selector');
            if (sel) {{ sel.value = '{VENUE}'; sel.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
        }}""")
        await page.wait_for_timeout(3000)

        # Go to new product form
        await page.goto(f"{HT_URL}/products/new")
        await page.wait_for_timeout(3000)

        # Switch venue again on new page
        await page.evaluate(f"""() => {{
            const sel = document.getElementById('venue_context_selector');
            if (sel) {{ sel.value = '{VENUE}'; sel.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
        }}""")
        await page.wait_for_timeout(2000)

        # Dump ALL form fields on General tab
        general_fields = await page.evaluate("""() => {
            const fields = [];
            document.querySelectorAll('input, select, textarea').forEach(el => {
                fields.push({
                    tag: el.tagName,
                    type: el.type || '',
                    id: el.id || '',
                    name: el.name || '',
                    class: el.className?.substring(0, 50) || '',
                    value: el.value || '',
                    visible: el.offsetParent !== null,
                    placeholder: el.placeholder || '',
                });
            });
            return fields;
        }""")
        print("=== GENERAL TAB FIELDS ===")
        for f in general_fields:
            if f['visible']:
                print(f"  [{f['tag']}] id={f['id']} name={f['name']} type={f['type']} value='{f['value']}' placeholder='{f['placeholder']}'")

        # Check all tabs
        tabs = await page.evaluate("""() => {
            return [...document.querySelectorAll('a[data-toggle="tab"], .nav-link, .tab-link')].map(t => ({
                text: t.textContent.trim(),
                href: t.getAttribute('href'),
                visible: t.offsetParent !== null,
            }));
        }""")
        print("\n=== TABS ===")
        for t in tabs:
            print(f"  {t['text']} -> {t['href']} (visible={t['visible']})")

        # Click Locations tab
        loc_tab = page.locator('a[href="#products_form_locations"]')
        if await loc_tab.count() > 0:
            await loc_tab.click()
            await page.wait_for_timeout(2000)

            loc_fields = await page.evaluate("""() => {
                const panel = document.getElementById('products_form_locations');
                if (!panel) return 'no panel';
                const fields = [];
                panel.querySelectorAll('select, input, button').forEach(el => {
                    fields.push({
                        tag: el.tagName,
                        type: el.type || '',
                        id: el.id || '',
                        name: el.name || el.dataset?.control || '',
                        class: el.className?.substring(0, 60) || '',
                        value: el.value || '',
                        visible: el.offsetParent !== null,
                        text: el.textContent?.trim()?.substring(0, 40) || '',
                        optCount: el.options?.length || 0,
                    });
                });
                return fields;
            }""")
            print("\n=== LOCATIONS TAB FIELDS ===")
            for f in loc_fields:
                print(f"  [{f['tag']}] id={f['id']} name={f['name']} type={f['type']} value='{f['value']}' opts={f['optCount']} visible={f['visible']} text='{f['text']}'")
        else:
            print("\n  Locations tab not found!")

        print("\n\n=== BROWSER OPEN — INSPECT MANUALLY ===")
        print("Press Ctrl+C to close when done.")
        try:
            await asyncio.sleep(300)  # Keep open 5 min
        except KeyboardInterrupt:
            pass

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
