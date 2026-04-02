/**
 * Fix ALL missing Products in Hotel.Tools for Miami hotels.
 *
 * Based on create_products_26_venues.js (proven working approach).
 * Creates ONLY the specific missing products per venue (from audit report).
 *
 * Usage:
 *   DRY RUN:  HOTEL_TOOLS_ACCOUNT_NAME="Medici LIVE" HOTEL_TOOLS_AGENT_NAME=zvi HOTEL_TOOLS_PASSWORD=karpad66 npx playwright test scripts/fix_missing_products.js
 *   APPLY:    HOTEL_TOOLS_ACCOUNT_NAME="Medici LIVE" HOTEL_TOOLS_AGENT_NAME=zvi HOTEL_TOOLS_PASSWORD=karpad66 APPLY=1 npx playwright test scripts/fix_missing_products.js
 *   SINGLE:   VENUES=5080 APPLY=1 npx playwright test scripts/fix_missing_products.js
 */

const { test } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Product definitions — each ITC code maps to a room product template
const PRODUCT_TEMPLATES = {
  Stnd:  { title: 'Standard',      shortName: 'Stnd',  pmsCode: 'Stnd' },
  DLX:   { title: 'Deluxe',        shortName: 'DLX',   pmsCode: 'DLX' },
  Suite: { title: 'Suite',         shortName: 'Suite',  pmsCode: 'Suite' },
  SPR:   { title: 'Superior',      shortName: 'SPR',   pmsCode: 'SPR' },
  APT:   { title: 'Apartment',     shortName: 'APT',   pmsCode: 'APT' },
  DRM:   { title: 'Dormitory',     shortName: 'DRM',   pmsCode: 'DRM' },
  EXEC:  { title: 'Executive',     shortName: 'EXEC',  pmsCode: 'EXEC' },
  DBL:   { title: 'Double',        shortName: 'DBL',   pmsCode: 'DBL' },
  OV2Q:  { title: 'Ocean View',    shortName: 'OV2Q',  pmsCode: 'OV2Q' },
  '1QSR': { title: 'Queen Standard', shortName: '1QSR', pmsCode: '1QSR' },
};

// Complete missing products list from audit (2026-04-02)
const MISSING_PRODUCTS = {
  5073: { name: 'Loews Miami Beach', missing: ['DLX'] },
  5075: { name: 'Villa Casa Casuarina', missing: ['Suite'] },
  5077: { name: 'SLS LUX Brickell', missing: ['SPR'] },
  5079: { name: 'citizenM Brickell', missing: ['DLX', 'SPR', 'Suite'] },
  5080: { name: 'Pullman Miami Airport', missing: ['APT', 'EXEC'] },
  5081: { name: 'Embassy Suites', missing: ['DLX', 'SPR', 'DRM'] },
  5083: { name: 'Hilton Miami Airport', missing: ['DRM'] },
  5084: { name: 'Hilton Downtown', missing: ['DLX', 'SPR'] },
  5089: { name: 'Fairwind Hotel', missing: ['SPR', 'Suite'] },
  5090: { name: 'Dream South Beach', missing: ['DLX', 'SPR'] },
  5092: { name: 'Iberostar Berkeley', missing: ['SPR', 'APT'] },
  5093: { name: 'Hilton Bentley SB', missing: ['SPR', 'APT'] },
  5095: { name: 'Cadet Hotel', missing: ['DLX', 'SPR'] },
  5096: { name: 'Marseilles Hotel', missing: ['DLX', 'SPR', 'DRM'] },
  5097: { name: 'Hyatt Centric SB', missing: ['SPR', 'Suite'] },
  5098: { name: 'Eurostars Langford', missing: ['SPR', 'APT', 'DRM', 'EXEC'] },
  5100: { name: 'Crystal Beach Suites', missing: ['Stnd', 'DLX', 'SPR'] },
  5101: { name: 'Atwell Suites Brickell', missing: ['DLX', 'SPR'] },
  5103: { name: 'Savoy Hotel', missing: ['SPR'] },
  5104: { name: 'Sole Miami', missing: ['DLX', 'SPR'] },
  5105: { name: 'MB Hotel', missing: ['SPR'] },
  5107: { name: 'Freehand Miami', missing: ['DLX', 'DRM'] },
  5108: { name: 'Gabriel South Beach', missing: ['SPR'] },
  5109: { name: 'Riu Plaza Miami Beach', missing: ['SPR', 'Suite'] },
  5110: { name: 'Breakwater South Beach', missing: ['APT'] },
  5115: { name: 'Hilton Cabana', missing: ['DRM'] },
  5117: { name: 'Albion Hotel', missing: ['DLX', 'APT', 'DRM'] },
  5124: { name: 'Grand Beach Hotel', missing: ['Suite'] },
  5130: { name: 'Holiday Inn Express', missing: ['Suite'] },
  5131: { name: 'Hotel Croydon', missing: ['Suite'] },
  5136: { name: 'Kimpton Anglers', missing: ['DLX', 'APT', 'Suite'] },
  5139: { name: 'SERENA Aventura', missing: ['DLX', 'SPR', 'Suite'] },
  5265: { name: 'Hotel Belleza', missing: ['Stnd', 'SPR', 'DBL'] },
  5266: { name: 'Dorchester Hotel', missing: ['Stnd', 'Suite', 'APT', 'DBL'] },
  5267: { name: 'Gale South Beach', missing: ['1QSR'] },
  5268: { name: 'Fontainebleau', missing: ['Stnd', 'DLX', 'Suite', 'APT', 'OV2Q'] },
  5274: { name: 'Generator Miami', missing: ['DLX', 'SPR', 'Suite', 'DRM'] },
  5276: { name: 'InterContinental Miami', missing: ['DLX', 'Suite'] },
  5278: { name: 'Gale Miami Hotel', missing: ['Suite', 'APT'] },
};

const DRY_RUN = !(process.argv.includes('--apply') || process.env.APPLY === '1');
const REQUESTED_VENUES = (process.env.VENUES || '')
  .split(',')
  .map(v => Number.parseInt(v.trim(), 10))
  .filter(Number.isFinite);

function normalize(v) { return (v || '').toLowerCase().replace(/\s+/g, ' ').trim(); }

test.setTimeout(900_000); // 15 min

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
  // select[name="venue"] is select2-hidden-accessible — cannot use selectOption
  // Must set via JS evaluate
  await page.evaluate((vid) => {
    const sel = document.querySelector('select[name="venue"]');
    if (!sel) throw new Error('Product venue field not found');
    sel.value = String(vid);
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    sel.dispatchEvent(new Event('input', { bubbles: true }));
    // Also try jQuery/select2 if available
    if (typeof jQuery !== 'undefined') {
      try { jQuery(sel).val(String(vid)).trigger('change'); } catch(e) {}
    }
  }, venueId);
  await page.waitForTimeout(300);
}

async function safeFill(page, selector, value) {
  if (!value) return;
  const el = page.locator(selector);
  if (await el.count() === 0) return;
  if (!(await el.isVisible()) || await el.isDisabled()) {
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

test('fix all missing products', async ({ browser }) => {
  const accountName = process.env.HOTEL_TOOLS_ACCOUNT_NAME || 'Medici LIVE';
  const username = process.env.HOTEL_TOOLS_AGENT_NAME || 'zvi';
  const password = process.env.HOTEL_TOOLS_PASSWORD || 'karpad66';

  // Filter venues if requested
  const venues = REQUESTED_VENUES.length > 0
    ? Object.fromEntries(Object.entries(MISSING_PRODUCTS).filter(([k]) => REQUESTED_VENUES.includes(Number(k))))
    : MISSING_PRODUCTS;

  const totalProducts = Object.values(venues).reduce((s, v) => s + v.missing.length, 0);

  console.log(`Mode: ${DRY_RUN ? 'DRY RUN (add APPLY=1 to create)' : '🔴 APPLY — CREATING PRODUCTS'}`);
  console.log(`Venues: ${Object.keys(venues).length}`);
  console.log(`Products to create: ${totalProducts}\n`);

  if (DRY_RUN) {
    for (const [vid, info] of Object.entries(venues)) {
      console.log(`  ${vid} ${info.name}:`);
      for (const itc of info.missing) {
        const tmpl = PRODUCT_TEMPLATES[itc];
        console.log(`    + ${tmpl ? tmpl.title : itc} (${itc})`);
      }
    }
    console.log(`\nTotal: ${totalProducts} products across ${Object.keys(venues).length} venues`);
    console.log('Run with APPLY=1 to create products.');
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

  const report = { created: [], skipped: [], errors: [], timestamp: new Date().toISOString() };

  for (const [venueId, info] of Object.entries(venues)) {
    const vid = Number(venueId);
    console.log(`\n--- ${vid} ${info.name} (${info.missing.length} missing) ---`);

    for (const itc of info.missing) {
      const tmpl = PRODUCT_TEMPLATES[itc];
      if (!tmpl) {
        console.log(`  SKIP: Unknown ITC '${itc}'`);
        report.errors.push({ venueId: vid, itc, error: 'Unknown ITC code' });
        continue;
      }

      try {
        // Check if already exists
        await page.goto('https://hotel.tools/products');
        await page.waitForTimeout(1500);
        await setVenueContext(page, vid);

        const existingTitles = [];
        for (const row of await page.locator('table tbody tr').all()) {
          const cells = await row.locator('td').all();
          if (cells.length >= 2) {
            existingTitles.push(normalize(await cells[1].textContent()));
          }
        }

        if (existingTitles.includes(normalize(tmpl.title))) {
          console.log(`  SKIP: "${tmpl.title}" already exists`);
          report.skipped.push({ venueId: vid, hotel: info.name, product: tmpl.title });
          continue;
        }

        console.log(`  CREATE: "${tmpl.title}" (${itc})`);

        // Go to new product form
        await page.goto('https://hotel.tools/products/new');
        await page.waitForTimeout(1500);
        await setVenueContext(page, vid);
        await setProductVenue(page, vid);

        // Fill form
        await safeFill(page, '#f-product-type', 'room');
        await safeFill(page, '#f-title', tmpl.title);
        await safeFill(page, '#f-short-name', tmpl.shortName);
        await safeFill(page, '#f-base-price', '500');
        await safeFill(page, '#f-base-currency', 'USD');
        await safeFill(page, '#f-max-occupancy', '2');
        await safeFill(page, '#f-status', '1');

        // Dates
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

        // PMS code
        await safeFill(page, '#rnd-f-pms_code', tmpl.pmsCode);
        await safeFill(page, '#f-pms-code', tmpl.pmsCode);

        // Submit
        const saveBtn = page.getByRole('button', { name: /save|create|submit/i });
        if (await saveBtn.count() > 0) {
          await saveBtn.first().click();
          await page.waitForTimeout(3000);
        } else {
          throw new Error('Submit button not found');
        }

        // Verify
        await page.goto('https://hotel.tools/products');
        await page.waitForTimeout(1500);
        await setVenueContext(page, vid);

        const updatedTitles = [];
        for (const row of await page.locator('table tbody tr').all()) {
          const cells = await row.locator('td').all();
          if (cells.length >= 2) {
            updatedTitles.push(normalize(await cells[1].textContent()));
          }
        }

        if (updatedTitles.includes(normalize(tmpl.title))) {
          console.log(`  ✓ "${tmpl.title}" created successfully`);
          report.created.push({ venueId: vid, hotel: info.name, product: tmpl.title, itc });
        } else {
          console.log(`  ✗ "${tmpl.title}" NOT found after submit`);
          report.errors.push({ venueId: vid, hotel: info.name, product: tmpl.title, itc, error: 'Not found after submit' });
        }

      } catch (err) {
        console.log(`  ERROR: ${err.message.substring(0, 100)}`);
        report.errors.push({ venueId: vid, hotel: info.name, product: tmpl.title, itc, error: err.message.substring(0, 200) });
      }
    }
  }

  // Summary
  console.log(`\n${'='.repeat(60)}`);
  console.log(`SUMMARY`);
  console.log(`  Created: ${report.created.length}`);
  console.log(`  Skipped: ${report.skipped.length}`);
  console.log(`  Errors:  ${report.errors.length}`);
  console.log(`${'='.repeat(60)}`);

  if (report.created.length > 0) {
    console.log('\nCreated:');
    for (const r of report.created) console.log(`  ✓ ${r.venueId} ${r.hotel}: ${r.product} (${r.itc})`);
  }
  if (report.errors.length > 0) {
    console.log('\nErrors:');
    for (const r of report.errors) console.log(`  ✗ ${r.venueId} ${r.hotel || ''}: ${r.product || r.itc} — ${r.error}`);
  }

  // Save report
  const reportDir = path.join(__dirname, '..', 'data', 'reports');
  fs.mkdirSync(reportDir, { recursive: true });
  const reportPath = path.join(reportDir, `fix_missing_products_${Date.now()}.json`);
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nReport: ${reportPath}`);

  await context.close();
});
