/**
 * Quick test: Can we create a product in Hotel.Tools?
 * Tests ONE product (Pullman 5080, Apartment/APT) with network monitoring.
 * Captures HTTP response to determine if the 500 bug is fixed.
 */
const { test, expect } = require('@playwright/test');

test.setTimeout(120_000);

test('test product creation on Hotel.Tools', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await context.newPage();

  // Monitor network for POST /products
  const responses = [];
  page.on('response', (resp) => {
    const url = resp.url();
    if (url.includes('/products') && resp.request().method() === 'POST') {
      responses.push({ url, status: resp.status(), statusText: resp.statusText() });
      console.log(`  [NET] POST ${url} → ${resp.status()} ${resp.statusText()}`);
    }
  });

  // Login
  console.log('Logging in...');
  await page.goto('https://hotel.tools/today-dashboard');
  await page.getByRole('textbox', { name: /account/i }).fill('Medici LIVE');
  await page.getByRole('textbox', { name: /agent|user/i }).fill('zvi');
  await page.getByRole('textbox', { name: /password/i }).fill('karpad66');
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/today-dashboard**', { timeout: 15000 });
  console.log('Logged in.\n');

  // Navigate to new product form
  console.log('Going to /products/new ...');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2000);

  // Set venue context (top-of-page venue filter)
  console.log('Setting venue context to 5080 (Pullman) ...');
  await page.evaluate(() => {
    const sel = document.querySelector('#venue_context_selector');
    if (sel) {
      sel.value = '5080';
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  await page.waitForTimeout(1000);
  const searchBtn = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn.count()) await searchBtn.click().catch(() => {});
  await page.waitForTimeout(1500);

  // Read form structure to understand what fields exist
  console.log('\n--- Form Structure ---');
  const formInfo = await page.evaluate(() => {
    const info = {};
    // Check all selects, inputs, textareas
    document.querySelectorAll('select, input, textarea').forEach(el => {
      const name = el.name || el.id || '';
      if (!name) return;
      const tag = el.tagName.toLowerCase();
      const type = el.type || '';
      const visible = el.offsetParent !== null;
      const isSelect2 = el.classList.contains('select2-hidden-accessible');
      info[name] = { tag, type, visible, isSelect2, value: el.value };
    });
    return info;
  });
  
  // Log key fields
  const keyFields = ['venue', 'f-product-type', 'f-title', 'f-short-name', 'f-base-price', 
                     'f-base-currency', 'f-max-occupancy', 'f-status', 'rnd-f-pms_code', 'f-pms-code',
                     'f-start-date', 'f-end-date', 'f-alt-start-date', 'f-alt-end-date'];
  for (const key of keyFields) {
    const f = formInfo[key];
    if (f) {
      console.log(`  ${key}: ${f.tag}${f.type ? '/' + f.type : ''} visible=${f.visible} select2=${f.isSelect2} val="${f.value}"`);
    }
  }

  // Check for location-related fields
  const locationFields = Object.entries(formInfo).filter(([k]) => k.toLowerCase().includes('location'));
  console.log(`\nLocation fields: ${JSON.stringify(locationFields.map(([k, v]) => k))}`);

  // Check for CSRF token
  const csrf = await page.evaluate(() => {
    const el = document.querySelector('input[name="_token"]') || document.querySelector('meta[name="csrf-token"]');
    return el ? (el.value || el.content || '(empty)') : '(not found)';
  });
  console.log(`CSRF token: ${csrf.substring(0, 20)}...`);

  // Fill form using JavaScript (bypassing select2 visibility issues)
  console.log('\n--- Filling Form ---');
  
  await page.evaluate(() => {
    const set = (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      el.value = val;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    };

    // Use jQuery/select2 API for venue dropdown
    const $venue = window.jQuery && window.jQuery('select[name="venue"]');
    if ($venue && $venue.length) {
      $venue.val('5080').trigger('change');
      console.log('  venue: set via jQuery');
    } else {
      set('select[name="venue"]', '5080');
    }

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

    // PMS code
    set('#rnd-f-pms_code', 'APT');
    set('#f-pms-code', 'APT');
  });
  await page.waitForTimeout(500);

  // Verify form values
  const filledValues = await page.evaluate(() => {
    const get = (sel) => {
      const el = document.querySelector(sel);
      return el ? el.value : '(not found)';
    };
    return {
      venue: get('select[name="venue"]'),
      productType: get('#f-product-type'),
      title: get('#f-title'),
      shortName: get('#f-short-name'),
      basePrice: get('#f-base-price'),
      pmsCode: get('#rnd-f-pms_code') || get('#f-pms-code'),
      status: get('#f-status'),
    };
  });
  console.log('Filled values:', JSON.stringify(filledValues));

  // Check if there's a Locations tab that needs attention
  const locationsTab = page.locator('a[href="#locations"], [data-toggle="tab"]:has-text("Location")');
  const hasLocTab = await locationsTab.count() > 0;
  console.log(`\nLocations tab present: ${hasLocTab}`);

  if (hasLocTab) {
    console.log('Clicking Locations tab...');
    await locationsTab.first().click();
    await page.waitForTimeout(1000);

    // Check what's on the locations pane
    const locContent = await page.evaluate(() => {
      const pane = document.querySelector('#locations, .tab-pane.locations, [id*="location"]');
      if (!pane) return 'no pane found';
      return pane.innerHTML.substring(0, 500);
    });
    console.log(`Locations pane content: ${locContent.substring(0, 300)}`);
  }

  // Read form action to understand the POST target
  const formAction = await page.evaluate(() => {
    const form = document.querySelector('form');
    return form ? { action: form.action, method: form.method, enctype: form.enctype } : null;
  });
  console.log(`\nForm: ${JSON.stringify(formAction)}`);

  // Read what the form would POST
  const formData = await page.evaluate(() => {
    const form = document.querySelector('form');
    if (!form) return null;
    const fd = new FormData(form);
    const data = {};
    for (const [key, value] of fd.entries()) {
      if (data[key]) {
        if (!Array.isArray(data[key])) data[key] = [data[key]];
        data[key].push(value);
      } else {
        data[key] = value;
      }
    }
    return data;
  });
  console.log('Form data keys:', formData ? Object.keys(formData).join(', ') : 'null');
  if (formData) {
    // Show key values (not _token for security)
    const { _token, ...rest } = formData;
    console.log('Form data (no token):', JSON.stringify(rest, null, 2));
  }

  // Now submit and capture what happens
  console.log('\n--- Submitting Form ---');
  const saveBtn = page.getByRole('button', { name: /save|create|submit/i });
  const btnCount = await saveBtn.count();
  console.log(`Save/Submit buttons found: ${btnCount}`);

  if (btnCount > 0) {
    // Wait for response
    const [response] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/products') && resp.request().method() === 'POST', { timeout: 15000 }).catch(() => null),
      saveBtn.first().click(),
    ]);

    if (response) {
      console.log(`\n🔴 POST Response: ${response.status()} ${response.statusText()}`);
      console.log(`URL: ${response.url()}`);
      
      // Try to get response body
      try {
        const body = await response.text();
        if (response.status() >= 400) {
          // Show first 500 chars of error
          console.log(`Error body (first 500 chars): ${body.substring(0, 500)}`);
        } else {
          console.log(`Response body length: ${body.length}`);
          // Check if redirected to product page (success)
          if (body.includes('Product saved') || body.includes('product-edit') || body.includes('products/')) {
            console.log('✅ Product appears to be created successfully!');
          }
        }
      } catch (e) {
        console.log(`Could not read response body: ${e.message}`);
      }
    } else {
      console.log('No POST response captured (may have been a redirect)');
    }

    await page.waitForTimeout(3000);
    
    // Check current URL after submit
    console.log(`Current URL after submit: ${page.url()}`);
    
    // Check for error messages on page
    const errors = await page.evaluate(() => {
      const alerts = document.querySelectorAll('.alert-danger, .error, .invalid-feedback, .text-danger');
      return Array.from(alerts).map(a => a.textContent.trim()).filter(Boolean);
    });
    if (errors.length) {
      console.log(`Page errors: ${JSON.stringify(errors)}`);
    }
  }

  // Verify: go to products list and check if Apartment exists for 5080
  console.log('\n--- Verification ---');
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);
  await page.evaluate(() => {
    const sel = document.querySelector('#venue_context_selector');
    if (sel) {
      sel.value = '5080';
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  await page.waitForTimeout(1000);
  const searchBtn2 = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn2.count()) await searchBtn2.click().catch(() => {});
  await page.waitForTimeout(2000);

  const products = await page.evaluate(() => {
    const rows = document.querySelectorAll('table tbody tr');
    return Array.from(rows).map(row => {
      const cells = row.querySelectorAll('td');
      return cells.length >= 3 ? {
        id: cells[0]?.textContent?.trim(),
        title: cells[1]?.textContent?.trim(),
        type: cells.length > 4 ? cells[4]?.textContent?.trim() : '',
      } : null;
    }).filter(Boolean);
  });
  console.log(`\nProducts for venue 5080:`);
  for (const p of products) {
    console.log(`  ${p.id} — ${p.title} (${p.type})`);
  }

  const hasApartment = products.some(p => p.title.toLowerCase().includes('apartment'));
  console.log(`\n${hasApartment ? '✅ Apartment product EXISTS' : '❌ Apartment product NOT found'}`);

  await context.close();
});
