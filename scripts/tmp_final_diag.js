/**
 * Final diagnostic: 
 *   1) Capture ALL console messages during form submit
 *   2) Try pure Playwright UI clicks (no evaluate)
 *   3) Try submitting an EDIT of an existing product (to test if server works at all)
 */
const { test } = require('@playwright/test');
test.setTimeout(180_000);

test('final diagnostic', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await ctx.newPage();

  // Capture ALL console messages
  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => consoleMsgs.push({ type: 'pageerror', text: err.message }));

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

  // ===== PART 1: Try to EDIT an existing product (just re-save it) =====
  console.log('=== PART 1: Edit existing product (just re-save) ===');
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);
  await setVenueCtx(page, 5080);

  const editLink = page.locator('table tbody tr a').first();
  if (await editLink.count()) {
    const editUrl = await editLink.getAttribute('href');
    console.log('  Editing:', editUrl);
    await editLink.click();
    await page.waitForTimeout(3000);

    consoleMsgs.length = 0;
    let editStatus = 0;
    page.on('response', resp => {
      if (resp.request().method() === 'POST' || resp.request().method() === 'PUT') {
        editStatus = resp.status();
        console.log('  Response:', resp.status(), resp.url());
      }
    });

    // Just click the submit button without changing anything
    const saveBtn = page.locator('button[type="submit"]').first();
    if (await saveBtn.count()) {
      await saveBtn.click();
      await page.waitForTimeout(4000);
    }

    console.log('  Edit re-save result: HTTP', editStatus, 'URL:', page.url());
    if (consoleMsgs.some(m => m.type === 'error' || m.type === 'pageerror')) {
      console.log('  Console errors:', consoleMsgs.filter(m => m.type === 'error' || m.type === 'pageerror'));
    }
  }

  // ===== PART 2: Pure UI interaction — create product with real clicks =====
  console.log('\n=== PART 2: Pure UI product creation ===');
  consoleMsgs.length = 0;
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(3000);
  await setVenueCtx(page, 5080);

  // Use Playwright fill/selectOption with force
  // Product type
  await page.evaluate(() => {
    const sel = document.querySelector('#f-product-type');
    if (sel) { sel.value = 'room'; $(sel).trigger('change'); }
  });
  await page.waitForTimeout(300);

  await page.fill('#f-title', 'TEST-PURE-UI');
  await page.fill('#f-short-name', 'TPU');
  await page.fill('#f-base-price', '500');
  
  // Currency - use jQuery
  await page.evaluate(() => {
    const sel = document.querySelector('#f-base-currency');
    if (sel) { sel.value = 'USD'; $(sel).trigger('change'); }
  });

  await page.fill('#f-max-occupancy', '2');
  
  // Status
  await page.evaluate(() => {
    const sel = document.querySelector('#f-status');
    if (sel) { sel.value = '1'; $(sel).trigger('change'); }
  });

  // Dates via JS
  await page.evaluate(() => {
    ['#f-start-date', '#f-alt-start-date'].forEach(s => {
      const e = document.querySelector(s);
      if (e) { e.value = '2025-01-01'; e.dispatchEvent(new Event('change', {bubbles:true})); }
    });
    ['#f-end-date', '#f-alt-end-date'].forEach(s => {
      const e = document.querySelector(s);
      if (e) { e.value = '2027-12-31'; e.dispatchEvent(new Event('change', {bubbles:true})); }
    });
  });

  // ---- Locations tab with REAL clicks ----
  console.log('  Clicking Locations tab...');
  await page.click('a[href="#products_form_locations"]');
  await page.waitForTimeout(1500);

  // Click the location type select2 container to open it
  console.log('  Setting location type to venue via select2...');
  // Find the select2 that corresponds to the type select
  await page.evaluate(() => {
    const panel = document.getElementById('products_form_locations');
    const typeSelect = panel.querySelector('select[data-control="type"]');
    if (typeSelect) {
      $(typeSelect).val('venue').trigger('change');
    }
  });
  await page.waitForTimeout(2000);

  // Set venue
  console.log('  Setting venue to 5080...');
  await page.evaluate(() => {
    const venueSelect = document.querySelector('select[name="venue"]');
    if (venueSelect) {
      $(venueSelect).val('5080').trigger('change');
    }
  });
  await page.waitForTimeout(1500);

  // Click Save Location button with a REAL click
  console.log('  Clicking Save Location...');
  const saveLoc = page.locator('button', { hasText: 'Save Location' });
  if (await saveLoc.count()) {
    await saveLoc.first().click();
    await page.waitForTimeout(3000);
  } else {
    console.log('  Save Location button NOT found!');
  }

  // Check what was created
  const locData = await page.evaluate(() => {
    const form = document.getElementById('products_form');
    if (!form) return { error: 'no form' };
    const fd = new FormData(form);
    const relevant = {};
    for (const [k, v] of fd.entries()) {
      if (k.includes('location') || k.includes('venue') || k.includes('state') || k === '__csrf') {
        relevant[k] = v;
      }
    }
    return relevant;
  });
  console.log('  Form data after Save Location:', JSON.stringify(locData, null, 2));

  // Submit
  console.log('  Submitting...');
  let postStatus = 0;
  let postResp = '';
  const onResp = async resp => {
    if (resp.request().method() === 'POST' && resp.url().includes('/products') && !resp.url().includes('analytics')) {
      postStatus = resp.status();
      try { postResp = await resp.text(); } catch(e) {}
    }
  };
  page.on('response', onResp);

  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(5000);
  page.removeListener('response', onResp);

  console.log('  POST status:', postStatus, 'URL:', page.url());
  if (postResp) console.log('  Response:', postResp.substring(0, 300));

  // Console errors during submit
  const errors = consoleMsgs.filter(m => m.type === 'error' || m.type === 'pageerror' || m.type === 'warning');
  if (errors.length) {
    console.log('  Console errors/warnings:', JSON.stringify(errors.slice(0, 10), null, 2));
  }

  // ===== PART 3: Check if CSRF is a session thing — try getting a new page after editing =====
  console.log('\n=== PART 3: Check CSRF after visiting products list ===');
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);
  // From products list, click "New Product"
  const newBtn = page.locator('a[href="/products/new"], a:has-text("New Product"), a:has-text("Add Product")');
  if (await newBtn.count()) {
    console.log('  Found "New Product" link, clicking...');
    await newBtn.first().click();
    await page.waitForTimeout(3000);
  } else {
    console.log('  No "New Product" link found, navigating directly...');
    await page.goto('https://hotel.tools/products/new');
    await page.waitForTimeout(3000);
  }

  // Check CSRF value
  const csrfVal = await page.evaluate(() => {
    const inp = document.querySelector('input[name="__csrf"]');
    return inp ? inp.value : 'NOT FOUND';
  });
  console.log('  CSRF value after nav from products list:', csrfVal);

  console.log('\nDone.');
  await ctx.close();
});
