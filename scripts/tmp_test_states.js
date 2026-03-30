/**
 * Test with states[location] tracking field — discovered from existing product serialization
 * Existing product has: locations[41092][address]="" + states[location][41092]="added"
 * The "Save Location" UI creates locations[l-rnd-xxx] but NO states[] entry — that's the bug!
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('test with states field', async ({ browser }) => {
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

  // ===== TEST 1: Direct fetch with states field =====
  console.log('=== TEST 1: Direct fetch with states[location] ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2000);

  // Set venue context
  await page.evaluate((v) => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = String(v); sel.dispatchEvent(new Event('change', { bubbles: true })); }
  }, 5080);
  await page.waitForTimeout(1000);

  const test1 = await page.evaluate(async () => {
    const body = new URLSearchParams();
    body.append('product_type', 'room');
    body.append('title', 'TEST-STATES-1');
    body.append('short_name', 'TS1');
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
    // Location with states tracking
    body.append('locations[new-1][type]', 'venue');
    body.append('locations[new-1][venue]', '5080');
    body.append('locations[new-1][address]', '');
    body.append('locations[new-1][country]', '');
    body.append('states[location][new-1]', 'added');
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
    return { status: resp.status, url: resp.url, body: text.substring(0, 500) };
  });
  console.log('Result 1:', JSON.stringify(test1, null, 2));

  // ===== TEST 2: Same but no country/address/csrf =====
  console.log('\n=== TEST 2: States + minimal location fields ===');
  const test2 = await page.evaluate(async () => {
    const body = new URLSearchParams();
    body.append('product_type', 'room');
    body.append('title', 'TEST-STATES-2');
    body.append('short_name', 'TS2');
    body.append('base_price', '500');
    body.append('base_currency', 'USD');
    body.append('max_occupancy', '2');
    body.append('status', '1');
    body.append('meal_plan_type', 'RO');
    body.append('start_date', '2025-01-01');
    body.append('end_date', '2027-12-31');
    body.append('price_per', 'person');
    body.append('locations[new-loc][type]', 'venue');
    body.append('locations[new-loc][venue]', '5080');
    body.append('states[location][new-loc]', 'added');

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
  console.log('Result 2:', JSON.stringify(test2, null, 2));

  // ===== TEST 3: Use Save Location via UI then inject states field before submit =====
  console.log('\n=== TEST 3: UI Save Location + inject states field + form submit ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);

  // Set venue context
  await page.evaluate((v) => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = String(v); sel.dispatchEvent(new Event('change', { bubbles: true })); }
  }, 5080);
  await page.waitForTimeout(1000);

  // Fill form
  await page.evaluate(() => {
    const set = (sel, val) => {
      const e = document.querySelector(sel); if (!e) return;
      e.value = val;
      e.dispatchEvent(new Event('input', {bubbles:true}));
      e.dispatchEvent(new Event('change', {bubbles:true}));
    };
    set('#f-product-type', 'room');
    set('#f-title', 'TEST-STATES-3');
    set('#f-short-name', 'TS3');
    set('#f-base-price', '500');
    set('#f-base-currency', 'USD');
    set('#f-max-occupancy', '2');
    set('#f-status', '1');
    set('#f-start-date', '2025-01-01');
    set('#f-alt-start-date', '2025-01-01');
    set('#f-end-date', '2027-12-31');
    set('#f-alt-end-date', '2027-12-31');
  });

  // Go to Locations tab and save a location via UI
  await page.locator('a[href="#products_form_locations"]').click();
  await page.waitForTimeout(1000);
  await page.evaluate(() => {
    const panel = document.getElementById('products_form_locations');
    $(panel.querySelector('select[data-control="type"]')).val('venue').trigger('change');
  });
  await page.waitForTimeout(2000);
  await page.evaluate(() => {
    $(document.querySelector('select[name="venue"]')).val('5080').trigger('change');
  });
  await page.waitForTimeout(1000);
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Save Location')?.click();
  });
  await page.waitForTimeout(2000);

  // Get the location ID that was created
  const locId = await page.evaluate(() => {
    const inputs = [...document.querySelectorAll('input[name*="locations["]')];
    for (const inp of inputs) {
      const m = inp.name.match(/locations\[([^\]]+)\]\[type\]/);
      if (m) return m[1];
    }
    return null;
  });
  console.log('  Location block ID:', locId);

  // NOW inject the states[location] field
  if (locId) {
    await page.evaluate((lid) => {
      const form = document.getElementById('products_form');
      if (!form) return;
      const stateInput = document.createElement('input');
      stateInput.type = 'hidden';
      stateInput.name = `states[location][${lid}]`;
      stateInput.value = 'added';
      form.appendChild(stateInput);
      console.log('Injected states[location][' + lid + '] = added');
    }, locId);
  }

  // Go back to General tab and submit
  await page.locator('a[href="#products_form_general"]').click();
  await page.waitForTimeout(500);

  // Intercept to log the full POST
  let postStatus = 0;
  page.on('request', req => {
    if (req.method() === 'POST' && req.url().includes('/products')) {
      const params = new URLSearchParams(req.postData() || '');
      const stateEntries = [...params.entries()].filter(([k]) => k.includes('states'));
      console.log('  states entries in POST:', JSON.stringify(stateEntries));
      console.log('  location entries in POST:', JSON.stringify(
        [...params.entries()].filter(([k]) => k.includes('location')).map(([k,v]) => `${k}=${v}`)
      ));
    }
  });
  page.on('response', resp => {
    if (resp.request().method() === 'POST' && resp.url().includes('/products')) {
      postStatus = resp.status();
    }
  });

  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(4000);

  console.log('  Submit result: HTTP', postStatus, 'URL:', page.url());
  if (postStatus >= 200 && postStatus < 400) {
    console.log('  >>> SUCCESS! <<<');
  }

  console.log('\nDone.');
  await ctx.close();
});
