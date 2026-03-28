const { chromium } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

const ACCOUNT = process.env.HOTEL_TOOLS_ACCOUNT_NAME || process.env.NOOVY_ACCOUNT_NAME || '';
const AGENT = process.env.HOTEL_TOOLS_AGENT_NAME || process.env.HOTEL_TOOLS_USERNAME || '';
const PASSWORD = process.env.HOTEL_TOOLS_PASSWORD || process.env.NOOVY_PASSWORD || '';

function normalize(value) {
  return (value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

async function loginHotelTools(page) {
  await page.goto('https://hotel.tools/today-dashboard', { waitUntil: 'domcontentloaded' });
  await page.getByRole('textbox', { name: /account name|account/i }).first().fill(ACCOUNT);
  await page.getByRole('textbox', { name: /agent name|user name|agent|user/i }).first().fill(AGENT);
  await page.getByRole('textbox', { name: /password/i }).first().fill(PASSWORD);
  await page.getByRole('button', { name: /login/i }).first().click();
  await page.waitForTimeout(3000);
  await page.goto('https://hotel.tools/products', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
}

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

async function readProductRows(page) {
  return page.locator('table tbody tr').evaluateAll((rows) =>
    rows.map((row) => {
      const cells = Array.from(row.querySelectorAll('td')).map((cell) =>
        (cell.textContent || '').replace(/\s+/g, ' ').trim(),
      );
      const editLink = row.querySelector('a[href*="/products/"][href*="/edit"]');
      return {
        title: cells[1] || '',
        productType: (cells[4] || '').toLowerCase(),
        editHref: editLink ? editLink.getAttribute('href') : '',
      };
    }),
  );
}

async function readTemplateFromEditPage(page, editHref) {
  const fullUrl = editHref.startsWith('http') ? editHref : `https://hotel.tools${editHref}`;
  await page.goto(fullUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);

  return page.evaluate(() => {
    const read = (selector) => {
      const element = document.querySelector(selector);
      return element ? element.value || '' : '';
    };
    return {
      productType: read('#f-product-type') || 'meal_plan',
      title: read('#f-title'),
      shortName: read('#f-short-name'),
      mealPlanType: read('#f-meal-plan-type') || 'BB',
      basePrice: read('#f-base-price') || '0',
      minPrice: read('#f-min-price') || '0',
      realPrice: read('#f-real-price') || '0',
      baseCurrency: read('#f-base-currency') || 'USD',
      baseQuantity: read('#f-base-quantity') || '1',
      affectedBy: read('#f-affected'),
      maxOccupancy: read('#f-max-occupancy') || '2',
      startDate: read('#f-alt-start-date'),
      endDate: read('#f-alt-end-date'),
      exclusive: read('#f-exclusive') || '0',
      tags: read('#f-tags'),
      productOrder: read('#f-product-order') || '0',
      roomsReserve: read('#f-rooms-reserve') || '0',
      status: read('#f-status') || '1',
      pmsCode: read('#rnd-f-pms_code') || '',
    };
  });
}

async function createProduct(page, venueId, template) {
  await page.goto('https://hotel.tools/products/new', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);

  await page.evaluate((selectedVenueId) => {
    const selector = document.querySelector('#venue_context_selector');
    if (!selector) throw new Error('Venue selector on new page not found');
    selector.value = String(selectedVenueId);
    selector.dispatchEvent(new Event('change', { bubbles: true }));
    selector.dispatchEvent(new Event('input', { bubbles: true }));
  }, venueId);

  await page.locator('#f-product-type').selectOption(template.productType || 'meal_plan');
  await page.waitForTimeout(400);
  await page.locator('#f-title').fill(template.title || 'room only');
  await page.locator('#f-short-name').fill(template.shortName || 'RO');
  if (await page.locator('#f-meal-plan-type').count()) {
    await page.locator('#f-meal-plan-type').selectOption(template.mealPlanType || 'RO');
  }

  await page.locator('#f-base-price').fill(template.basePrice || '0');
  if (await page.locator('#f-min-price').count()) await page.locator('#f-min-price').fill(template.minPrice || '0');
  if (await page.locator('#f-real-price').count()) await page.locator('#f-real-price').fill(template.realPrice || '0');
  await page.locator('#f-base-currency').selectOption(template.baseCurrency || 'USD');
  await page.locator('#f-base-quantity').fill(template.baseQuantity || '1');

  if (await page.locator('#f-max-occupancy').count()) {
    await page.locator('#f-max-occupancy').fill(template.maxOccupancy || '2');
  }

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
  }, { startDate: template.startDate || '', endDate: template.endDate || '' });

  if (await page.locator('#f-exclusive').count()) await page.locator('#f-exclusive').selectOption(template.exclusive || '0');
  if (await page.locator('#f-tags').count()) await page.locator('#f-tags').fill(template.tags || '');
  if (await page.locator('#f-product-order').count()) await page.locator('#f-product-order').fill(template.productOrder || '0');
  if (await page.locator('#f-rooms-reserve').count()) await page.locator('#f-rooms-reserve').fill(template.roomsReserve || '0');
  if (await page.locator('#f-status').count()) await page.locator('#f-status').selectOption(template.status || '1');
  if (await page.locator('#rnd-f-pms_code').count()) await page.locator('#rnd-f-pms_code').fill(template.pmsCode || 'RO');

  await page
    .locator('button:has-text("Submit"), input[type="submit"], button[type="submit"]')
    .first()
    .click();
  await page.waitForTimeout(2000);
}

async function main() {
  if (!ACCOUNT || !AGENT || !PASSWORD) {
    throw new Error('Missing HOTEL_TOOLS credentials in environment');
  }

  const compareFiles = fs
    .readdirSync(path.resolve('data', 'reports'))
    .filter((name) => name.startsWith('inventory_compare_innstant_hoteltools_') && name.endsWith('.json'))
    .sort();
  if (!compareFiles.length) {
    throw new Error('Comparison report not found');
  }

  const latestComparePath = path.resolve('data', 'reports', compareFiles[compareFiles.length - 1]);
  const compare = JSON.parse(fs.readFileSync(latestComparePath, 'utf8'));
  const targetVenueIds = compare.rows
    .filter((row) => Array.isArray(row.missingBoardsInHotelTools) && row.missingBoardsInHotelTools.includes('RO'))
    .map((row) => Number(row.venueId))
    .filter((value) => Number.isFinite(value) && value > 0);

  const uniqueTargets = Array.from(new Set(targetVenueIds)).sort((a, b) => a - b);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1700, height: 1100 } });

  const report = {
    sourceReport: latestComparePath.replace(/\\/g, '/'),
    targets: uniqueTargets,
    created: [],
    skipped: [],
    errors: [],
    startedAt: new Date().toISOString(),
  };

  try {
    await loginHotelTools(page);

    await page.goto('https://hotel.tools/products', { waitUntil: 'domcontentloaded' });
    await setVenueContext(page, 5077);
    const refRows = await readProductRows(page);
    const bb = refRows.find((row) => {
      const title = normalize(row.title);
      return row.editHref && (
        title.includes('bed and breakfast')
        || title === 'b&b'
        || title === 'bb'
        || title.includes('breakfast')
      );
    });
    if (!bb) {
      const titles = refRows.map((row) => row.title).filter(Boolean);
      throw new Error(`Reference BB product not found in venue 5077. Titles: ${titles.join(' | ')}`);
    }

    const bbTemplate = await readTemplateFromEditPage(page, bb.editHref);
    const roTemplate = {
      ...bbTemplate,
      productType: 'meal_plan',
      title: 'room only',
      shortName: 'RO',
      mealPlanType: 'RO',
      basePrice: '0',
      minPrice: '0',
      realPrice: '0',
      pmsCode: 'RO',
    };

    for (const venueId of uniqueTargets) {
      try {
        await page.goto('https://hotel.tools/products', { waitUntil: 'domcontentloaded' });
        await setVenueContext(page, venueId);
        const rows = await readProductRows(page);
        const titles = rows.map((row) => normalize(row.title));
        const hasRO = titles.some((title) => title === 'room only' || title === 'ro' || title.includes('room only'));

        if (hasRO) {
          report.skipped.push({ venueId, reason: 'RO already exists' });
          continue;
        }

        await createProduct(page, venueId, roTemplate);
        report.created.push({ venueId, title: roTemplate.title });
      } catch (error) {
        report.errors.push({ venueId, error: String(error) });
      }
    }
  } finally {
    await browser.close();
  }

  report.finishedAt = new Date().toISOString();
  const out = path.resolve('data', 'reports', `hoteltools_ro_fix_${Date.now()}.json`);
  fs.writeFileSync(out, JSON.stringify(report, null, 2), 'utf8');
  console.log('report', out.replace(/\\/g, '/'));
  console.log('summary', JSON.stringify({
    targets: report.targets.length,
    created: report.created.length,
    skipped: report.skipped.length,
    errors: report.errors.length,
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
