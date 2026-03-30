/**
 * Capture the actual POST body when creating a product
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('capture POST body', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await ctx.newPage();

  // Login
  await page.goto('https://hotel.tools/today-dashboard');
  await page.getByRole('textbox', { name: /account/i }).fill('Medici LIVE');
  await page.getByRole('textbox', { name: /agent|user/i }).fill('zvi');
  await page.getByRole('textbox', { name: /password/i }).fill('karpad66');
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/today-dashboard**', { timeout: 15000 });

  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);

  // Set venue context
  await page.evaluate(() => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = '5080'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.waitForTimeout(1000);
  const searchBtn = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn.count()) await searchBtn.click().catch(() => {});
  await page.waitForTimeout(1500);

  // Fill General tab
  await page.evaluate(() => {
    const set = (s, v) => { 
      const e = document.querySelector(s); 
      if (!e) return;
      e.value = v; 
      e.dispatchEvent(new Event('input', {bubbles:true})); 
      e.dispatchEvent(new Event('change', {bubbles:true}));
    };
    set('#f-product-type', 'room');
    set('#f-title', 'Apartment');
    set('#f-short-name', 'APT');
    set('#f-base-price', '500');
    set('#f-base-currency', 'USD');
    set('#f-max-occupancy', '2');
    set('#f-status', '1');
    set('#f-start-date', '2025-01-01');
    set('#f-alt-start-date', '2025-01-01');
    set('#f-end-date', '2027-12-31');
    set('#f-alt-end-date', '2027-12-31');
  });

  // Set PMS code
  await page.evaluate(() => {
    const pms = document.querySelector('[name="meta[pms_code]"]') || document.querySelector('#rnd-f-pms_code');
    if (pms) { pms.value = 'APT'; pms.dispatchEvent(new Event('input', {bubbles:true})); pms.dispatchEvent(new Event('change', {bubbles:true})); }
  });

  // Locations tab - use jQuery select2
  await page.locator('a[href="#products_form_locations"]').click();
  await page.waitForTimeout(1000);

  await page.evaluate(() => {
    const panel = document.getElementById('products_form_locations');
    const typeSelect = panel.querySelector('select[data-control="type"]');
    $(typeSelect).val('venue').trigger('change');
  });
  await page.waitForTimeout(2000);

  await page.evaluate(() => {
    const vsel = document.querySelector('select[name="venue"]');
    $(vsel).val('5080').trigger('change');
  });
  await page.waitForTimeout(1000);

  // Save Location
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Save Location')?.click();
  });
  await page.waitForTimeout(2000);

  // Back to General
  await page.locator('a[href="#products_form_general"]').click();
  await page.waitForTimeout(500);

  // Dump ALL form fields that will be submitted
  const allFields = await page.evaluate(() => {
    // Find the product form - it's the one with #f-title inside
    const forms = [...document.querySelectorAll('form')];
    let productForm = null;
    for (const f of forms) {
      if (f.querySelector('#f-title') || f.querySelector('[name="title"]')) {
        productForm = f;
        break;
      }
    }
    if (!productForm) {
      return { error: 'Product form not found', formCount: forms.length, formActions: forms.map(f => f.action) };
    }

    // Collect ALL inputs
    const fields = {};
    productForm.querySelectorAll('input, select, textarea').forEach(el => {
      if (!el.name) return;
      if (el.type === 'checkbox' && !el.checked) return;
      fields[el.name] = el.value?.substring(0, 100) || '';
    });

    return { action: productForm.action, method: productForm.method, fieldCount: Object.keys(fields).length, fields };
  });

  console.log('Product form:', allFields.action, allFields.method);
  console.log(`Fields (${allFields.fieldCount}):`);
  if (allFields.fields) {
    for (const [k, v] of Object.entries(allFields.fields).sort()) {
      console.log(`  ${k} = "${v}"`);
    }
  } else {
    console.log('ERROR:', JSON.stringify(allFields));
  }

  // Intercept the POST request to see the actual body
  page.on('request', req => {
    if (req.method() === 'POST' && req.url().includes('/products') && !req.url().includes('analytics')) {
      console.log(`\n=== POST REQUEST ===`);
      console.log(`URL: ${req.url()}`);
      console.log(`Content-Type: ${req.headers()['content-type']}`);
      const body = req.postData();
      console.log(`Body (${body?.length || 0} chars):`);
      if (body) {
        // Parse form-urlencoded
        const params = new URLSearchParams(body);
        for (const [k, v] of [...params.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
          console.log(`  ${k} = "${v.substring(0, 100)}"`);
        }
      }
    }
  });

  page.on('response', async resp => {
    if (resp.request().method() === 'POST' && resp.url().includes('/products') && !resp.url().includes('analytics')) {
      console.log(`\n=== POST RESPONSE ===`);
      console.log(`Status: ${resp.status()}`);
      console.log(`Headers: ${JSON.stringify(Object.fromEntries(resp.headers ? [...Object.entries(resp.headers())] : []))}`);
      try {
        const text = await resp.text();
        // Look for error messages in the HTML
        const errorMatch = text.match(/alert[^>]*>(.*?)<\/div>/s);
        if (errorMatch) console.log(`Error in response: ${errorMatch[1].trim().substring(0, 200)}`);
        // Look for "please specify" or "error"
        const msgMatch = text.match(/(please|error|failed|invalid|required)[^<]{0,200}/gi);
        if (msgMatch) console.log(`Messages: ${msgMatch.slice(0, 5).join(' | ')}`);
      } catch (e) {}
    }
  });

  // Submit
  const submitBtn = page.locator('button[type="submit"]').first();
  await submitBtn.click();
  await page.waitForTimeout(5000);

  console.log(`\nFinal URL: ${page.url()}`);

  await ctx.close();
});
