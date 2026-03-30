/**
 * Create products in Hotel.Tools for 26 venues that have NO Zenith products
 *
 * Zenith API probe (2026-03-27) confirmed these venues return 1 RoomStay
 * but with EMPTY RatePlanCode/InvTypeCode — meaning the venue shell exists
 * but no actual products are configured.
 *
 * Strategy: Use apply_noovy_reference_clone.js approach
 *   Reference: Venue 5077 (SLS Lux Brickell) — has 7 products (3 rooms × RO+BB + 1 extra)
 *   Target: 26 venues needing products
 *
 * After products are created, re-probe Zenith to get actual RPC/ITC codes,
 * then INSERT correct mappings into Med_Hotels_ratebycat.
 *
 * Usage:
 *   DRY RUN:  npx playwright test scripts/create_products_26_venues.js
 *   APPLY:    npx playwright test scripts/create_products_26_venues.js -- --apply
 */

const { test, expect } = require('@playwright/test');

function normalize(value) {
  return (value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function inferRoomPmsCode(title, fallback = '') {
  const normalizedTitle = normalize(title);
  if (normalizedTitle.includes('superior') || normalizedTitle === 'spr' || normalizedTitle === 'sup') {
    return 'SPR';
  }
  if (normalizedTitle.includes('deluxe') || normalizedTitle === 'dlx') {
    return 'DLX';
  }
  if (normalizedTitle.includes('suite') || normalizedTitle === 'sui') {
    return 'Suite';
  }
  if (normalizedTitle.includes('standard') || normalizedTitle === 'stnd') {
    return 'Stnd';
  }
  return fallback;
}

const REFERENCE_VENUE = 5077; // SLS Lux Brickell — working reference

// 26 venues with NO products (confirmed by Zenith API probe)
const TARGET_VENUES = [
  // Group B — have Innstant API results but Zenith push fails
  { venueId: 5073, hotelId: 6661,   name: 'Loews Miami Beach Hotel' },
  { venueId: 5075, hotelId: 193899, name: 'The Villa Casa Casuarina' },
  { venueId: 5082, hotelId: 733781, name: 'DoubleTree by Hilton Miami Doral' },
  { venueId: 5115, hotelId: 254198, name: 'Hilton Cabana Miami Beach' },
  { venueId: 5116, hotelId: 846428, name: 'Kimpton Hotel Palomar South Beach' },
  { venueId: 5119, hotelId: 854710, name: 'citizenM Miami South Beach' },
  { venueId: 5132, hotelId: 277280, name: 'Hotel Gaythering' },
  { venueId: 5138, hotelId: 851633, name: 'THE LANDON BAY HARBOR' },
  { venueId: 5139, hotelId: 851939, name: 'SERENA Hotel Aventura Miami' },
  { venueId: 5140, hotelId: 301583, name: 'The Gates Hotel South Beach' },
  { venueId: 5266, hotelId: 6654,   name: 'Dorchester Hotel' },
  { venueId: 5267, hotelId: 301645, name: 'Gale South Beach' },
  { venueId: 5268, hotelId: 19977,  name: 'Fontainebleau Miami Beach' },
  { venueId: 5274, hotelId: 701659, name: 'Generator Miami' },
  { venueId: 5276, hotelId: 6482,   name: 'InterContinental Miami' },
  { venueId: 5278, hotelId: 852725, name: 'Gale Miami Hotel and Residences' },
  { venueId: 5279, hotelId: 301640, name: 'Hilton Garden Inn Miami SB' },
  // Group D — Innstant returns 0 API results
  { venueId: 5083, hotelId: 20706,  name: 'Hilton Miami Airport' },
  { venueId: 5113, hotelId: 66737,  name: 'Cavalier Hotel' },
  { venueId: 5117, hotelId: 855711, name: 'The Albion Hotel' },
  { venueId: 5124, hotelId: 68833,  name: 'Grand Beach Hotel Miami' },
  { venueId: 5130, hotelId: 67387,  name: 'HOLIDAY INN EXPRESS HOTEL & SUITES' },
  { venueId: 5131, hotelId: 286236, name: 'Hotel Croydon' },
  { venueId: 5136, hotelId: 31226,  name: "Kimpton Angler's Hotel" },
  { venueId: 5141, hotelId: 31433,  name: 'Metropole South Beach' },
  { venueId: 5265, hotelId: 414146, name: 'Hotel Belleza' },
  { venueId: 5275, hotelId: 21842,  name: 'Miami International Airport Hotel' },
  { venueId: 5277, hotelId: 87197,  name: 'The Catalina Hotel & Beach Club' },
];

const DRY_RUN = !(process.argv.includes('--apply') || process.env.APPLY === '1');
const REQUESTED_VENUES = (process.env.VENUES || '')
  .split(',')
  .map(value => Number.parseInt(value.trim(), 10))
  .filter(Number.isFinite);
const SELECTED_TARGET_VENUES = REQUESTED_VENUES.length > 0
  ? TARGET_VENUES.filter(target => REQUESTED_VENUES.includes(target.venueId))
  : TARGET_VENUES;

test.setTimeout(600_000); // 10 minutes

async function setVenueContext(page, venueId) {
  const resetButton = page.getByRole('button', { name: /reset/i }).first();
  if (await resetButton.count()) {
    await resetButton.click().catch(() => undefined);
    await page.waitForTimeout(500);
  }

  await page.evaluate((selectedVenueId) => {
    const selector = document.querySelector('#venue_context_selector');
    if (!selector) throw new Error('Venue selector not found');
    selector.value = String(selectedVenueId);
    selector.dispatchEvent(new Event('change', { bubbles: true }));
    selector.dispatchEvent(new Event('input', { bubbles: true }));
  }, venueId);

  await page.waitForTimeout(1000);
  const searchButton = page.getByRole('button', { name: /search/i }).first();
  if (await searchButton.count()) {
    await searchButton.click().catch(() => undefined);
  }
  await page.waitForTimeout(1700);
}

async function setProductVenue(page, venueId) {
  const venueField = page.locator('select[name="venue"]');
  if (await venueField.count() === 0) {
    throw new Error('Product venue field not found');
  }

  await venueField.selectOption(String(venueId));
  await venueField.dispatchEvent('change').catch(() => undefined);
  await venueField.dispatchEvent('input').catch(() => undefined);
  await page.waitForTimeout(300);
}

test('create products for 26 empty venues', async ({ browser }) => {
  const accountName = process.env.HOTEL_TOOLS_ACCOUNT_NAME || process.env.NOOVY_ACCOUNT_NAME;
  const username = process.env.HOTEL_TOOLS_AGENT_NAME || process.env.HOTEL_TOOLS_USERNAME || process.env.NOOVY_USERNAME;
  const password = process.env.HOTEL_TOOLS_PASSWORD || process.env.NOOVY_PASSWORD;

  if (!accountName || !username || !password) {
    console.log('Missing HOTEL_TOOLS credentials. Set HOTEL_TOOLS_ACCOUNT_NAME, HOTEL_TOOLS_AGENT_NAME, HOTEL_TOOLS_PASSWORD');
    return;
  }

  console.log(`Mode: ${DRY_RUN ? 'DRY RUN' : '🔴 APPLY'}`);
  console.log(`Reference venue: ${REFERENCE_VENUE}`);
  console.log(`Target venues: ${SELECTED_TARGET_VENUES.length}`);
  if (REQUESTED_VENUES.length > 0) {
    console.log(`Requested filter: ${REQUESTED_VENUES.join(', ')}`);
  }
  console.log();

  const context = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await context.newPage();

  // --- Login to Hotel.Tools ---
  console.log('Logging in to Hotel.Tools...');
  await page.goto('https://hotel.tools/today-dashboard');
  await page.getByRole('textbox', { name: /account/i }).fill(accountName);
  await page.getByRole('textbox', { name: /agent|user/i }).fill(username);
  await page.getByRole('textbox', { name: /password/i }).fill(password);
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/today-dashboard**', { timeout: 15000 });
  console.log('Logged in.');

  // --- Read reference venue products ---
  console.log(`\nReading reference venue ${REFERENCE_VENUE}...`);
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);

  // Set venue context
  await setVenueContext(page, REFERENCE_VENUE);

  // Read product table
  const productRows = await page.locator('table tbody tr').all();
  const templates = [];
  const seenTemplateTitles = new Set();

  for (const row of productRows) {
    const cells = await row.locator('td').all();
    if (cells.length < 5) continue;

    const title = (await cells[1].textContent()).trim();
    const productType = normalize(await cells[4].textContent());
    const normalizedTitle = normalize(title);

    // Product-failure hotels need missing room products, not meal-plan rows.
    if (productType !== 'room') {
      continue;
    }

    if (!normalizedTitle || seenTemplateTitles.has(normalizedTitle)) {
      continue;
    }

    // Get edit link
    const editLink = await row.locator('a[href*="/products/"]').first();
    if (await editLink.count() === 0) continue;

    const href = await editLink.getAttribute('href');
    console.log(`  Reading template: ${title} (${productType}) — ${href}`);

    // Navigate to edit page to read full template
    await page.goto(`https://hotel.tools${href}`);
    await page.waitForTimeout(1500);

    const template = {
      productType: await safeValue(page, '#f-product-type'),
      title: await safeValue(page, '#f-title'),
      shortName: await safeValue(page, '#f-short-name'),
      mealPlanType: await safeValue(page, '#f-meal-plan-type'),
      basePrice: await safeValue(page, '#f-base-price'),
      minPrice: await safeValue(page, '#f-min-price'),
      realPrice: await safeValue(page, '#f-real-price'),
      baseCurrency: await safeValue(page, '#f-base-currency'),
      baseQuantity: await safeValue(page, '#f-base-quantity'),
      affectedBy: await safeValue(page, '#f-affected'),
      maxOccupancy: await safeValue(page, '#f-max-occupancy'),
      startDate: await safeValue(page, '#f-alt-start-date') || await safeValue(page, '#f-start-date'),
      endDate: await safeValue(page, '#f-alt-end-date') || await safeValue(page, '#f-end-date'),
      exclusive: await safeValue(page, '#f-exclusive'),
      tags: await safeValue(page, '#f-tags'),
      productOrder: await safeValue(page, '#f-product-order'),
      roomsReserve: await safeValue(page, '#f-rooms-reserve'),
      status: await safeValue(page, '#f-status'),
      pmsCode: await safeValue(page, '#rnd-f-pms_code') || await safeValue(page, '#f-pms-code'),
    };

    template.pmsCode = inferRoomPmsCode(template.title, template.pmsCode);
    if (!template.shortName) {
      template.shortName = template.pmsCode;
    }

    seenTemplateTitles.add(normalizedTitle);
    templates.push(template);
    await page.goto('https://hotel.tools/products');
    await page.waitForTimeout(1000);
    await setVenueContext(page, REFERENCE_VENUE);
  }

  console.log(`\nLoaded ${templates.length} templates from reference venue.`);

  if (DRY_RUN) {
    console.log('\n=== DRY RUN — would create these products ===');
      for (const t of SELECTED_TARGET_VENUES) {
      console.log(`\nVenue ${t.venueId} (${t.name}):`);
      for (const tmpl of templates) {
        console.log(`  + ${tmpl.productType}: ${tmpl.title} (${tmpl.shortName}) — ${tmpl.baseCurrency} ${tmpl.basePrice}`);
      }
    }
    console.log('\n=== Run with --apply to create products ===');
    return;
  }

  // --- APPLY mode: create products ---
  const report = { created: [], skipped: [], errors: [], timestamp: new Date().toISOString() };

  for (const target of SELECTED_TARGET_VENUES) {
    console.log(`\n--- Processing venue ${target.venueId} (${target.name}) ---`);

    try {
      await page.goto('https://hotel.tools/products');
      await page.waitForTimeout(2000);

      await setVenueContext(page, target.venueId);

      // Check existing products
      const existingRows = await page.locator('table tbody tr').count();
      const existingTitles = [];
      for (const row of await page.locator('table tbody tr').all()) {
        const cells = await row.locator('td').all();
        if (cells.length >= 2) {
          existingTitles.push(normalize(await cells[1].textContent()));
        }
      }

      let createdCount = 0;
      for (const tmpl of templates) {
        const normalizedTitle = normalize(tmpl.title);
        if (existingTitles.includes(normalizedTitle)) {
          console.log(`  SKIP: "${tmpl.title}" already exists`);
          continue;
        }

        console.log(`  CREATE: "${tmpl.title}" (${tmpl.productType})`);

        await page.goto('https://hotel.tools/products/new');
        await page.waitForTimeout(1500);
        await setVenueContext(page, target.venueId);
        await setProductVenue(page, target.venueId);

        // Fill form
        await safeFill(page, '#f-product-type', tmpl.productType);
        await safeFill(page, '#f-title', tmpl.title);
        await safeFill(page, '#f-short-name', tmpl.shortName);
        await safeFill(page, '#f-base-price', tmpl.basePrice);
        if (tmpl.minPrice) await safeFill(page, '#f-min-price', tmpl.minPrice);
        if (tmpl.realPrice) await safeFill(page, '#f-real-price', tmpl.realPrice);
        await safeFill(page, '#f-base-currency', tmpl.baseCurrency);
        if (tmpl.baseQuantity) await safeFill(page, '#f-base-quantity', tmpl.baseQuantity);
        if (tmpl.affectedBy) await safeFill(page, '#f-affected', tmpl.affectedBy);
        if (tmpl.maxOccupancy) await safeFill(page, '#f-max-occupancy', tmpl.maxOccupancy);

        await page.evaluate(({ startDate, endDate }) => {
          const set = (selector, value) => {
            const element = document.querySelector(selector);
            if (!element) return;
            element.value = value || '';
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
          };
          set('#f-start-date', startDate || '');
          set('#f-alt-start-date', startDate || '');
          set('#f-end-date', endDate || '');
          set('#f-alt-end-date', endDate || '');
        }, { startDate: tmpl.startDate || '', endDate: tmpl.endDate || '' });

        if (tmpl.exclusive) await safeFill(page, '#f-exclusive', tmpl.exclusive);
        if (tmpl.tags) await safeFill(page, '#f-tags', tmpl.tags);
        if (tmpl.productOrder) await safeFill(page, '#f-product-order', tmpl.productOrder);
        if (tmpl.roomsReserve) await safeFill(page, '#f-rooms-reserve', tmpl.roomsReserve);
        await safeFill(page, '#f-status', tmpl.status || '1');
        if (tmpl.pmsCode) {
          await safeFill(page, '#rnd-f-pms_code', tmpl.pmsCode);
          await safeFill(page, '#f-pms-code', tmpl.pmsCode);
        }

        // Submit
        const saveBtn = page.getByRole('button', { name: /save|create|submit/i });
        if (await saveBtn.count() > 0) {
          await saveBtn.first().click();
          await page.waitForTimeout(3000);
        }

        await page.goto('https://hotel.tools/products');
        await page.waitForTimeout(1500);
        await setVenueContext(page, target.venueId);
        const updatedTitles = [];
        for (const row of await page.locator('table tbody tr').all()) {
          const cells = await row.locator('td').all();
          if (cells.length >= 2) {
            updatedTitles.push(normalize(await cells[1].textContent()));
          }
        }
        if (!updatedTitles.includes(normalizedTitle)) {
          throw new Error(`Product did not persist after submit: ${tmpl.title}`);
        }
        existingTitles.push(normalizedTitle);
        createdCount++;
      }

      report.created.push({ venueId: target.venueId, name: target.name, count: createdCount });
    } catch (err) {
      console.log(`  ERROR: ${err.message}`);
      report.errors.push({ venueId: target.venueId, name: target.name, error: err.message });
    }
  }

  // Save report
  const fs = require('fs');
  const reportPath = `data/reports/create_products_26_venues_${Date.now()}.json`;
  fs.mkdirSync('data/reports', { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nReport saved: ${reportPath}`);
  console.log(`Created: ${report.created.length} venues, Errors: ${report.errors.length}`);

  await context.close();
});

// Helpers
async function safeValue(page, selector) {
  const el = page.locator(selector);
  if (await el.count() === 0) return '';
  const tag = await el.evaluate(e => e.tagName.toLowerCase());
  if (tag === 'select') return await el.inputValue();
  return await el.inputValue();
}

async function safeFill(page, selector, value) {
  if (!value) return;
  const el = page.locator(selector);
  if (await el.count() === 0) return;
  if (!(await el.isVisible()) || await el.isDisabled()) return;
  const tag = await el.evaluate(e => e.tagName.toLowerCase());
  if (tag === 'select') {
    await el.selectOption(value);
  } else {
    await el.fill(value);
  }
}
