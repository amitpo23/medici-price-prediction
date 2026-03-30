/**
 * Test 3 approaches in sequence:
 * A) Just set venue field (like original script) — no Save Location
 * B) Set venue field + location data 
 * C) Remove venue param from form before submit
 */
const { test } = require('@playwright/test');
test.setTimeout(180_000);

test('test product creation approaches', async ({ browser }) => {
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

  async function fillProduct(pg, title, shortName) {
    await pg.evaluate(({ t, s }) => {
      const set = (sel, val) => {
        const e = document.querySelector(sel); if (!e) return;
        e.value = val;
        e.dispatchEvent(new Event('input', {bubbles:true}));
        e.dispatchEvent(new Event('change', {bubbles:true}));
      };
      set('#f-product-type', 'room');
      set('#f-title', t);
      set('#f-short-name', s);
      set('#f-base-price', '500');
      set('#f-base-currency', 'USD');
      set('#f-max-occupancy', '2');
      set('#f-status', '1');
      set('#f-start-date', '2025-01-01');
      set('#f-alt-start-date', '2025-01-01');
      set('#f-end-date', '2027-12-31');
      set('#f-alt-end-date', '2027-12-31');
    }, { t: title, s: shortName });
  }

  async function trySubmit(pg, label) {
    let postStatus = 0;
    let postBody = '';
    const onReq = req => {
      if (req.method() === 'POST' && req.url().includes('/products') && !req.url().includes('analytics')) {
        postBody = req.postData() || '';
        const params = new URLSearchParams(postBody);
        console.log(`  POST fields: ${[...params.keys()].filter(k => k.includes('venue') || k.includes('location') || k === '__csrf').join(', ')}`);
        console.log(`  venue = "${params.get('venue') || ''}", csrf = "${params.get('__csrf') || ''}"`);
      }
    };
    const onResp = resp => {
      if (resp.request().method() === 'POST' && resp.url().includes('/products') && !resp.url().includes('analytics')) {
        postStatus = resp.status();
      }
    };
    pg.on('request', onReq);
    pg.on('response', onResp);

    const btn = pg.locator('button[type="submit"]').first();
    await btn.click();
    await pg.waitForTimeout(4000);

    pg.removeListener('request', onReq);
    pg.removeListener('response', onResp);

    console.log(`  ${label}: POST => ${postStatus}, URL => ${pg.url()}`);
    return postStatus;
  }

  // ============ APPROACH A: Like original script — set venue select, no Save Location ============
  console.log('=== APPROACH A: Set venue select only (no Save Location) ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);
  await setVenueCtx(page, 5080);
  await fillProduct(page, 'TEST-A', 'TA');

  // Set venue field via jQuery (on the Locations tab select)
  await page.evaluate(() => {
    const vsel = document.querySelector('select[name="venue"]');
    if (vsel) $(vsel).val('5080').trigger('change');
  });
  await page.waitForTimeout(500);

  let result = await trySubmit(page, 'A');
  if (result === 200 || result === 302 || page.url().includes('/edit')) {
    console.log('  >>> SUCCESS A!\n');
  }

  // ============ APPROACH B: Set venue + Save Location + set venue field ============  
  console.log('\n=== APPROACH B: Save Location + venue field ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);
  await setVenueCtx(page, 5080);
  await fillProduct(page, 'TEST-B', 'TB');

  // Go to locations tab
  await page.locator('a[href="#products_form_locations"]').click();
  await page.waitForTimeout(1000);

  // Set location type + venue via jQuery select2
  await page.evaluate(() => {
    const panel = document.getElementById('products_form_locations');
    const typeSelect = panel.querySelector('select[data-control="type"]');
    $(typeSelect).val('venue').trigger('change');
  });
  await page.waitForTimeout(2000);
  await page.evaluate(() => {
    $(document.querySelector('select[name="venue"]')).val('5080').trigger('change');
  });
  await page.waitForTimeout(1000);

  // Save Location
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Save Location')?.click();
  });
  await page.waitForTimeout(2000);

  // Back to general tab
  await page.locator('a[href="#products_form_general"]').click();
  await page.waitForTimeout(500);

  // ALSO set the new-location-form venue field (in case it matters)
  await page.evaluate(() => {
    // After Save Location, there's a NEW empty venue select for the next location
    const venueSels = document.querySelectorAll('select[name="venue"]');
    venueSels.forEach(s => {
      if (!s.disabled) { $(s).val('5080').trigger('change'); }
    });
  });

  result = await trySubmit(page, 'B');
  if (result === 200 || result === 302 || page.url().includes('/edit')) {
    console.log('  >>> SUCCESS B!\n');
  }

  // ============ APPROACH C: Remove all empty location fields before submit ============
  console.log('\n=== APPROACH C: Save Location + remove empty venue selects ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);
  await setVenueCtx(page, 5080);
  await fillProduct(page, 'TEST-C', 'TC');

  // Locations tab + Save Location (same as B)
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

  await page.locator('a[href="#products_form_general"]').click();
  await page.waitForTimeout(500);

  // Remove the "create new location" form block entirely to prevent empty venue=
  await page.evaluate(() => {
    const createBlock = document.querySelector('.location-block[data-mode="create"]');
    if (createBlock) createBlock.remove();
  });

  result = await trySubmit(page, 'C');
  if (result === 200 || result === 302 || page.url().includes('/edit')) {
    console.log('  >>> SUCCESS C!\n');
  }

  // ============ APPROACH D: Intercept fetch/XHR and fix the POST body ============
  console.log('\n=== APPROACH D: Intercept and fix POST body ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);
  await setVenueCtx(page, 5080);
  await fillProduct(page, 'TEST-D', 'TD');

  // Save Location same as B
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
  await page.locator('a[href="#products_form_general"]').click();
  await page.waitForTimeout(500);

  // Intercept the POST via route
  await page.route('**/products', async (route, req) => {
    if (req.method() !== 'POST') { route.continue(); return; }
    const body = req.postData() || '';
    const params = new URLSearchParams(body);
    // Fix: set venue to 5080
    params.set('venue', '5080');
    // Ensure location data
    const newBody = params.toString();
    console.log(`  Intercepted POST, fixed venue=5080`);
    route.continue({ postData: newBody });
  });

  result = await trySubmit(page, 'D');
  if (result === 200 || result === 302 || page.url().includes('/edit')) {
    console.log('  >>> SUCCESS D!\n');
  }
  await page.unroute('**/products');

  console.log('\nDone. Check which approach worked.');
  await ctx.close();
});
