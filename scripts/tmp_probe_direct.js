/**
 * Deep probe: compare existing product location format vs new product location format
 * Then try injecting exact existing-product format
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('probe location formats', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await ctx.newPage();

  // Login
  await page.goto('https://hotel.tools/today-dashboard');
  await page.getByRole('textbox', { name: /account/i }).fill('Medici LIVE');
  await page.getByRole('textbox', { name: /agent|user/i }).fill('zvi');
  await page.getByRole('textbox', { name: /password/i }).fill('karpad66');
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/today-dashboard**', { timeout: 15000 });
  console.log('Logged in\n');

  // Set venue context to 5080
  async function setVenueCtx(pg, vid) {
    await pg.evaluate((v) => {
      const sel = document.getElementById('venue_context_selector');
      if (sel) { sel.value = String(v); sel.dispatchEvent(new Event('change', { bubbles: true })); }
    }, vid);
    await pg.waitForTimeout(1000);
    const btn = pg.getByRole('button', { name: /search/i }).first();
    if (await btn.count()) await btn.click().catch(() => {});
    await pg.waitForTimeout(1500);
  }

  // ===== PART 1: Examine existing product's location hidden inputs =====
  console.log('=== PART 1: Existing product location format ===');
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);
  await setVenueCtx(page, 5080);

  // Click first product to edit
  const firstRow = page.locator('table tbody tr').first();
  if (await firstRow.count()) {
    await firstRow.locator('a').first().click();
    await page.waitForTimeout(3000);
    console.log('Edit page URL:', page.url());

    // Dump ALL hidden inputs with "location" in name
    const locInputs = await page.evaluate(() => {
      const inputs = [...document.querySelectorAll('input[name*="location"]')];
      return inputs.map(i => ({ type: i.type, name: i.name, value: i.value }));
    });
    console.log('Location hidden inputs:', JSON.stringify(locInputs, null, 2));

    // Dump the location blocks
    const locBlocks = await page.evaluate(() => {
      const blocks = [...document.querySelectorAll('[data-typeid]')];
      return blocks.map(b => ({
        typeid: b.dataset.typeid,
        html: b.outerHTML.substring(0, 500)
      }));
    });
    console.log('Location blocks:', JSON.stringify(locBlocks, null, 2));

    // Get the FULL form serialization
    const formData = await page.evaluate(() => {
      const form = document.querySelector('form#products_form, form[action*="product"]');
      if (!form) return 'NO FORM FOUND';
      const fd = new FormData(form);
      const entries = {};
      for (const [k, v] of fd.entries()) {
        if (k.includes('location') || k === 'venue' || k === '__csrf') {
          entries[k] = v;
        }
      }
      return entries;
    });
    console.log('Form serialization (location+venue+csrf):', JSON.stringify(formData, null, 2));
  }

  // ===== PART 2: Try submitting to /products with direct fetch (bypassing form) =====
  console.log('\n\n=== PART 2: Direct POST via page.evaluate fetch ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);
  await setVenueCtx(page, 5080);

  const directResult = await page.evaluate(async () => {
    const body = new URLSearchParams();
    body.append('product_type', 'room');
    body.append('title', 'TEST-DIRECT');
    body.append('short_name', 'TD');
    body.append('base_price', '500');
    body.append('base_currency', 'USD');
    body.append('max_occupancy', '2');
    body.append('status', '1');
    body.append('meal_plan_type', 'RO');
    body.append('start_date', '2025-01-01');
    body.append('end_date', '2027-12-31');
    body.append('price_per', 'person');
    body.append('affects_price_occupancy', '1');
    body.append('affects_price_date', '1');
    body.append('affects_price_los', '1');
    // Location with venue ID as key (matching existing product format)
    body.append('locations[5080][type]', 'venue');
    body.append('locations[5080][venue]', '5080');
    body.append('__csrf', '');
    
    const resp = await fetch('/products', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-PJAX': 'true',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body.toString(),
      credentials: 'same-origin'
    });
    const text = await resp.text();
    return { status: resp.status, body: text.substring(0, 500), headers: Object.fromEntries(resp.headers.entries()) };
  });
  console.log('Direct POST result:', JSON.stringify(directResult, null, 2));

  // ===== PART 3: Try with NO __csrf at all =====
  console.log('\n\n=== PART 3: Direct POST without __csrf ===');
  const nocsrfResult = await page.evaluate(async () => {
    const body = new URLSearchParams();
    body.append('product_type', 'room');
    body.append('title', 'TEST-NOCSRF');
    body.append('short_name', 'TN');
    body.append('base_price', '500');
    body.append('base_currency', 'USD');
    body.append('max_occupancy', '2');
    body.append('status', '1');
    body.append('meal_plan_type', 'RO');
    body.append('start_date', '2025-01-01');
    body.append('end_date', '2027-12-31');
    body.append('price_per', 'person');
    body.append('affects_price_occupancy', '1');
    body.append('affects_price_date', '1');
    body.append('affects_price_los', '1');
    body.append('locations[5080][type]', 'venue');
    body.append('locations[5080][venue]', '5080');
    // NO __csrf at all
    
    const resp = await fetch('/products', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-PJAX': 'true',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body.toString(),
      credentials: 'same-origin'
    });
    const text = await resp.text();
    return { status: resp.status, body: text.substring(0, 500) };
  });
  console.log('No-CSRF POST result:', JSON.stringify(nocsrfResult, null, 2));

  // ===== PART 4: Try minimal payload (like API) =====
  console.log('\n\n=== PART 4: Minimal POST ===');
  const minResult = await page.evaluate(async () => {
    const body = new URLSearchParams();
    body.append('product_type', 'room');
    body.append('title', 'TEST-MIN');
    body.append('short_name', 'TM');
    body.append('base_price', '500');
    body.append('base_currency', 'USD');
    body.append('status', '1');
    body.append('locations[5080][type]', 'venue');
    body.append('locations[5080][venue]', '5080');
    
    const resp = await fetch('/products', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body.toString(),
      credentials: 'same-origin'
    });
    const text = await resp.text();
    return { status: resp.status, body: text.substring(0, 500) };
  });
  console.log('Minimal POST result:', JSON.stringify(minResult, null, 2));

  console.log('\nDone.');
  await ctx.close();
});
