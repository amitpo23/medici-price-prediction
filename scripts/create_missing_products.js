/**
 * Create missing Products in Hotel.Tools for 5 venues.
 * 
 * Based on create_products_26_venues.js (proven working approach).
 * Each venue needs ONE specific room type product.
 *
 * Usage:
 *   DRY RUN:  npx playwright test scripts/create_missing_products.js
 *   APPLY:    APPLY=1 npx playwright test scripts/create_missing_products.js
 */

const { test } = require('@playwright/test');

const TASKS = [
  { venueId: 5080, hotel: 'Pullman',     title: 'Apartment', shortName: 'APT',  pmsCode: 'APT' },
  { venueId: 5095, hotel: 'Cadet Hotel',  title: 'Superior',  shortName: 'SPR',  pmsCode: 'SPR' },
  { venueId: 5096, hotel: 'Marseilles',   title: 'Deluxe',    shortName: 'DLX',  pmsCode: 'DLX' },
  { venueId: 5098, hotel: 'Eurostars',    title: 'Executive', shortName: 'EXEC', pmsCode: 'EXEC' },
  { venueId: 5110, hotel: 'Breakwater',   title: 'Apartment', shortName: 'APT',  pmsCode: 'APT' },
  // 5103 Savoy, 5106 Hampton Inn, 5113 Cavalier — already have the product (verified)
];

const DRY_RUN = !(process.argv.includes('--apply') || process.env.APPLY === '1');
test.setTimeout(300_000);

function normalize(v) { return (v || '').toLowerCase().replace(/\s+/g, ' ').trim(); }

async function setVenueContext(page, venueId) {
  const resetBtn = page.getByRole('button', { name: /reset/i }).first();
  if (await resetBtn.count()) await resetBtn.click().catch(() => {});
  await page.waitForTimeout(500);

  await page.evaluate((vid) => {
    const sel = document.querySelector('#venue_context_selector');
    if (!sel) throw new Error('Venue selector not found');
    sel.value = String(vid);
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    sel.dispatchEvent(new Event('input', { bubbles: true }));
  }, venueId);

  await page.waitForTimeout(1000);
  const searchBtn = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn.count()) await searchBtn.click().catch(() => {});
  await page.waitForTimeout(1700);
}

async function setProductVenue(page, venueId) {
  const venueField = page.locator('select[name="venue"]');
  if (await venueField.count() === 0) throw new Error('select[name="venue"] not found');
  await venueField.selectOption(String(venueId));
  await venueField.dispatchEvent('change').catch(() => {});
  await venueField.dispatchEvent('input').catch(() => {});
  await page.waitForTimeout(300);
}

async function safeFill(page, selector, value) {
  if (!value) return;
  const el = page.locator(selector);
  if (await el.count() === 0) return;
  if (!(await el.isVisible()) || await el.isDisabled()) {
    // Fall back to JS setter for hidden/disabled fields
    await page.evaluate(({ sel, val }) => {
      const e = document.querySelector(sel);
      if (!e) return;
      e.value = val;
      e.dispatchEvent(new Event('input', { bubbles: true }));
      e.dispatchEvent(new Event('change', { bubbles: true }));
    }, { sel: selector, val: value });
    return;
  }
  const tag = await el.evaluate(e => e.tagName.toLowerCase());
  if (tag === 'select') {
    await el.selectOption(value);
  } else {
    await el.fill(value);
  }
}

test('create missing products for 5 venues', async ({ browser }) => {
  const accountName = process.env.HOTEL_TOOLS_ACCOUNT_NAME || 'Medici LIVE';
  const username = process.env.HOTEL_TOOLS_AGENT_NAME || 'zvi';
  const password = process.env.HOTEL_TOOLS_PASSWORD || 'karpad66';

  console.log(`Mode: ${DRY_RUN ? 'DRY RUN' : '🔴 APPLY'}`);
  console.log(`Tasks: ${TASKS.length} products to create\n`);

  if (DRY_RUN) {
    for (const t of TASKS) {
      console.log(`  Would create: ${t.hotel} (${t.venueId}) → ${t.title} (${t.pmsCode})`);
    }
    console.log('\nRun with APPLY=1 to create products.');
    return;
  }

  const context = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await context.newPage();

  // Login
  console.log('Logging in to Hotel.Tools...');
  await page.goto('https://hotel.tools/today-dashboard');
  await page.getByRole('textbox', { name: /account/i }).fill(accountName);
  await page.getByRole('textbox', { name: /agent|user/i }).fill(username);
  await page.getByRole('textbox', { name: /password/i }).fill(password);
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/today-dashboard**', { timeout: 15000 });
  console.log('Logged in.\n');

  const results = { created: [], skipped: [], errors: [] };

  for (const task of TASKS) {
    console.log(`--- ${task.hotel} (${task.venueId}) — ${task.title} (${task.pmsCode}) ---`);

    try {
      // Check if product already exists
      await page.goto('https://hotel.tools/products');
      await page.waitForTimeout(2000);
      await setVenueContext(page, task.venueId);

      const existingTitles = [];
      for (const row of await page.locator('table tbody tr').all()) {
        const cells = await row.locator('td').all();
        if (cells.length >= 2) {
          existingTitles.push(normalize(await cells[1].textContent()));
        }
      }

      if (existingTitles.includes(normalize(task.title))) {
        console.log(`  SKIP: "${task.title}" already exists`);
        results.skipped.push(task);
        continue;
      }

      // Create product
      await page.goto('https://hotel.tools/products/new');
      await page.waitForTimeout(1500);
      await setVenueContext(page, task.venueId);
      await setProductVenue(page, task.venueId);

      // Fill General tab fields
      await safeFill(page, '#f-product-type', 'room');
      await safeFill(page, '#f-title', task.title);
      await safeFill(page, '#f-short-name', task.shortName);
      await safeFill(page, '#f-base-price', '500');
      await safeFill(page, '#f-base-currency', 'USD');
      await safeFill(page, '#f-max-occupancy', '2');
      await safeFill(page, '#f-status', '1');

      // Date range
      await page.evaluate(() => {
        const set = (sel, val) => {
          const e = document.querySelector(sel);
          if (!e) return;
          e.value = val;
          e.dispatchEvent(new Event('input', { bubbles: true }));
          e.dispatchEvent(new Event('change', { bubbles: true }));
        };
        set('#f-start-date', '2025-01-01');
        set('#f-alt-start-date', '2025-01-01');
        set('#f-end-date', '2027-12-31');
        set('#f-alt-end-date', '2027-12-31');
      });

      // PMS code (try both known selectors)
      if (task.pmsCode) {
        await safeFill(page, '#rnd-f-pms_code', task.pmsCode);
        await safeFill(page, '#f-pms-code', task.pmsCode);
      }

      // Submit
      const saveBtn = page.getByRole('button', { name: /save|create|submit/i });
      if (await saveBtn.count() > 0) {
        await saveBtn.first().click();
        await page.waitForTimeout(3000);
      } else {
        throw new Error('Submit button not found');
      }

      // Verify creation
      await page.goto('https://hotel.tools/products');
      await page.waitForTimeout(1500);
      await setVenueContext(page, task.venueId);

      const updatedTitles = [];
      for (const row of await page.locator('table tbody tr').all()) {
        const cells = await row.locator('td').all();
        if (cells.length >= 2) {
          updatedTitles.push(normalize(await cells[1].textContent()));
        }
      }

      if (updatedTitles.includes(normalize(task.title))) {
        console.log(`  OK: "${task.title}" created successfully`);
        results.created.push(task);
      } else {
        console.log(`  WARN: "${task.title}" not found after submit — products: ${updatedTitles.join(', ')}`);
        results.errors.push({ ...task, error: 'Not found after submit' });
      }

    } catch (err) {
      console.log(`  ERROR: ${err.message}`);
      results.errors.push({ ...task, error: err.message.substring(0, 100) });
    }
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log(`SUMMARY: Created=${results.created.length} Skipped=${results.skipped.length} Errors=${results.errors.length}`);
  for (const r of results.created) console.log(`  + ${r.venueId} ${r.hotel}: ${r.title} (${r.pmsCode})`);
  for (const r of results.skipped) console.log(`  ~ ${r.venueId} ${r.hotel}: ${r.title}`);
  for (const r of results.errors) console.log(`  ! ${r.venueId} ${r.hotel}: ${r.title} — ${r.error}`);

  await context.close();
});
