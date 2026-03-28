/**
 * Set rates via Hotel.Tools Bulk Update for all venues.
 * Opens the Bulk Update modal, selects All rooms × All rate plans,
 * sets price to $500, availability to "open", dates Apr 15 - Jun 30.
 *
 * Usage:
 *   DRY RUN:  node scripts/bulk_set_rates_v2.js
 *   APPLY:    APPLY=1 node scripts/bulk_set_rates_v2.js
 *   SINGLE:   VENUES=5082 APPLY=1 node scripts/bulk_set_rates_v2.js
 */

const { chromium } = require('playwright');
const fs = require('fs');

// All 36 venues from Quick Scan report (B=Zenith blocked + C=No API)
const DEFAULT_VENUES = [
  // B: Zenith Push Blocked (19)
  '5276','5266','5073','5268','5083','5275','5136','5115','5131',
  '5279','5267','5274','5082','5116','5138','5139','5278','5119','5094',
  // C: No API Results (17)
  '5141','5064','5100','5113','5110','5130','5124','5277',
  '5104','5089','5095','5075','5102','5132','5140','5265','5117'
];

const APPLY = process.env.APPLY === '1';
const TARGET_VENUES = process.env.VENUES ? process.env.VENUES.split(',') : DEFAULT_VENUES;
const DATE_RANGE = '15 Apr 2026 - 30 Jun 2026';
const PRICE = '500';

async function main() {
  console.log(`Mode: ${APPLY ? '🔴 APPLY' : '🟢 DRY RUN'}`);
  console.log(`Venues: ${TARGET_VENUES.length} — ${TARGET_VENUES.join(', ')}`);
  console.log(`Rate: $${PRICE} | Dates: ${DATE_RANGE}`);
  console.log();

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1700, height: 1100 } });

  // Login
  await page.goto('https://hotel.tools/login');
  await page.waitForTimeout(2000);
  await page.locator('input[name="account"]').fill('Medici LIVE');
  await page.locator('input[name="agent"]').fill('zvi');
  await page.locator('input[name="password"]').fill('karpad66');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(5000);
  if (page.url().includes('/login')) { console.log('Login failed!'); return; }
  console.log('Logged in.\n');

  const results = [];

  for (const vid of TARGET_VENUES) {
    console.log(`--- Venue ${vid} ---`);
    try {
      // Navigate to pricing page
      await page.goto('https://hotel.tools/pricing-inventory', { timeout: 15000 });
      await page.waitForTimeout(2000);
      await page.locator('#venue_context_selector').selectOption({ value: vid });
      await page.waitForTimeout(3000);

      // Open Bulk Update modal — wait for it to be fully visible
      await page.locator('button:has-text("Bulk update")').click();
      await page.waitForTimeout(3000);
      // Ensure modal is fully rendered by waiting for price select
      await page.locator('#cpaf-price').waitFor({ state: 'attached', timeout: 10000 }).catch(() => {});
      await page.waitForTimeout(1000);

      // Check options
      const rooms = [];
      for (const o of await page.locator('#bu-rooms option').all()) {
        const v = await o.getAttribute('value');
        const t = (await o.textContent()).trim();
        if (v && v !== '-1') rooms.push(t);
      }
      const rps = [];
      for (const o of await page.locator('#bu-rate-plans option').all()) {
        const v = await o.getAttribute('value');
        const t = (await o.textContent()).trim();
        if (v && v !== '-1') rps.push(`${v}=${t}`);
      }

      console.log(`  Rooms: [${rooms.join(', ')}]`);
      console.log(`  Rate Plans: [${rps.join(', ')}]`);

      if (rooms.length === 0 || rps.length === 0) {
        console.log('  SKIP: no rooms or rate plans');
        results.push({ venue: vid, status: 'skip' });
        // Close modal
        await page.locator('.modal button:has-text("Close")').first().click().catch(() => {});
        await page.waitForTimeout(500);
        continue;
      }

      if (!APPLY) {
        console.log(`  WOULD SET: $${PRICE} | ${DATE_RANGE} | All rooms × All rate plans`);
        results.push({ venue: vid, status: 'dry_run', rooms: rooms.length, ratePlans: rps.length });
        await page.locator('.modal button:has-text("Close")').first().click().catch(() => {});
        await page.waitForTimeout(500);
        continue;
      }

      // ---- APPLY ----

      // 1. Select All rooms
      await page.locator('#bu-rooms').selectOption({ value: '-1' });
      await page.waitForTimeout(500);

      // 2. Select All rate plans
      await page.locator('#bu-rate-plans').selectOption({ value: '-1' });
      await page.waitForTimeout(500);

      // 3. Set date range via jQuery daterangepicker API
      const dateSet = await page.evaluate(() => {
        const $el = $('#bulkUpdateDates');
        if (!$el.length) return 'element not found';
        const dp = $el.data('daterangepicker');
        if (!dp) return 'daterangepicker not initialized';
        // Use native Date objects — daterangepicker wraps them internally
        dp.setStartDate(new Date(2026, 3, 15)); // Apr 15
        dp.setEndDate(new Date(2026, 5, 30));   // Jun 30
        $el.trigger('apply.daterangepicker', [dp]);
        return `ok: ${dp.startDate.format('YYYY-MM-DD')} to ${dp.endDate.format('YYYY-MM-DD')}`;
      });
      console.log(`  Dates: ${dateSet}`);
      await page.waitForTimeout(1000);

      // 4-6. Set price, availability, and submit via JS (avoids strict mode violation on duplicate IDs)
      await page.evaluate((price) => {
        // Set price type to "fixed"
        const priceSel = document.querySelector('#cpaf-price');
        priceSel.value = 'fixed';
        priceSel.dispatchEvent(new Event('change', { bubbles: true }));
        // Set price amount
        const priceInput = document.querySelector('input[name="price[fixed][amount]"]');
        if (priceInput) {
          priceInput.value = price;
          priceInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
        // Set availability to "open"
        const availSel = document.querySelector('#cpaf-availability');
        availSel.value = 'open';
        availSel.dispatchEvent(new Event('change', { bubbles: true }));
      }, PRICE);
      await page.waitForTimeout(1000);

      // 7. Submit — click the visible Save button
      await page.evaluate(() => {
        const btns = [...document.querySelectorAll('.modal button[type="submit"]')];
        const visible = btns.find(b => b.offsetParent !== null);
        if (visible) visible.click();
      });
      await page.waitForTimeout(3000);

      // Check for errors
      const errorEl = page.locator('.modal .alert-danger, .modal .error, .notification-error');
      const hasError = await errorEl.count() > 0;
      if (hasError) {
        const errorText = await errorEl.first().textContent();
        console.log(`  ⚠️ Error: ${errorText.substring(0, 100)}`);
        results.push({ venue: vid, status: 'error', error: errorText.substring(0, 200) });
      } else {
        console.log('  ✅ Rates set');
        results.push({ venue: vid, status: 'applied', rooms: rooms.length, ratePlans: rps.length });
      }

    } catch (e) {
      console.log(`  ❌ ${e.message.substring(0, 100)}`);
      results.push({ venue: vid, status: 'error', error: e.message.substring(0, 200) });
    }
  }

  // Summary
  console.log(`\n${'='.repeat(60)}`);
  const applied = results.filter(r => r.status === 'applied').length;
  const dryRun = results.filter(r => r.status === 'dry_run').length;
  const skipped = results.filter(r => r.status === 'skip').length;
  const errors = results.filter(r => r.status === 'error').length;
  console.log(`Applied: ${applied} | DryRun: ${dryRun} | Skip: ${skipped} | Errors: ${errors}`);

  fs.mkdirSync('data/reports', { recursive: true });
  fs.writeFileSync(`data/reports/bulk_rates_${Date.now()}.json`, JSON.stringify(results, null, 2));

  await browser.close();
}

main().catch(console.error);
