/**
 * Probe: dump ALL form inputs from an existing product edit page
 * + attempt to create a product with injected hidden inputs for location
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('probe product form inputs', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await ctx.newPage();

  // Login
  await page.goto('https://hotel.tools/today-dashboard');
  await page.getByRole('textbox', { name: /account/i }).fill('Medici LIVE');
  await page.getByRole('textbox', { name: /agent|user/i }).fill('zvi');
  await page.getByRole('textbox', { name: /password/i }).fill('karpad66');
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/today-dashboard**', { timeout: 15000 });
  console.log('Logged in');

  // Open existing product for venue 5080 (BB product)
  await page.goto('https://hotel.tools/products/p.68b9e3e423a82/edit');
  await page.waitForTimeout(3000);

  // Dump ALL form inputs
  const formData = await page.evaluate(() => {
    const form = document.querySelector('form');
    if (!form) return { error: 'no form' };
    const inputs = [];
    form.querySelectorAll('input, select, textarea').forEach(el => {
      inputs.push({
        tag: el.tagName,
        type: el.type || '',
        name: el.name || '',
        id: el.id || '',
        value: (el.value || '').substring(0, 100),
        disabled: el.disabled,
        hidden: el.type === 'hidden' || !el.offsetParent
      });
    });
    return { action: form.action, method: form.method, inputCount: inputs.length, inputs };
  });

  console.log(`\nForm: ${formData.method} ${formData.action}`);
  console.log(`Total inputs: ${formData.inputCount}`);
  console.log('\n=== ALL NAMED INPUTS ===');
  for (const inp of formData.inputs) {
    if (inp.name) {
      console.log(`  ${inp.name} = "${inp.value}" (${inp.tag}/${inp.type}, hidden=${inp.hidden}, disabled=${inp.disabled})`);
    }
  }

  // Now test: go to /products/new with venue 5080 context
  // and inject location as hidden inputs instead of using the UI
  console.log('\n\n=== TEST: Create with injected location ===');
  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2000);

  // Set venue context
  await page.evaluate(() => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = '5080'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.waitForTimeout(1500);
  const searchBtn = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn.count()) await searchBtn.click().catch(() => {});
  await page.waitForTimeout(1500);

  // Fill form via JS
  await page.evaluate(() => {
    const set = (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      el.value = val;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    };
    set('#f-product-type', 'room');
    set('#f-title', 'TEST-Apartment');
    set('#f-short-name', 'TEST');
    set('#f-base-price', '500');
    set('#f-base-currency', 'USD');
    set('#f-max-occupancy', '2');
    set('#f-status', '1');
    set('#f-start-date', '2025-01-01');
    set('#f-alt-start-date', '2025-01-01');
    set('#f-end-date', '2027-12-31');
    set('#f-alt-end-date', '2027-12-31');
  });

  // APPROACH 1: Inject location hidden inputs matching the pattern from existing product
  await page.evaluate(() => {
    const form = document.querySelector('form.product-form') || document.querySelector('form');
    if (!form) return;
    const addInput = (name, val) => {
      const inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = name;
      inp.value = val;
      form.appendChild(inp);
    };
    addInput('locations[new-loc][type]', 'venue');
    addInput('locations[new-loc][venue]', '5080');
    addInput('locations[new-loc][country]', '');
    addInput('locations[new-loc][city]', '');
    addInput('locations[new-loc][address]', '');
  });

  // Capture response
  let postStatus = 0;
  let postUrl = '';
  page.on('response', resp => {
    if (resp.request().method() === 'POST' && resp.url().includes('products') && !resp.url().includes('analytics')) {
      postStatus = resp.status();
      postUrl = resp.url();
    }
  });

  // Submit  
  const submit = page.locator('button[type="submit"]').first();
  await submit.click();
  await page.waitForTimeout(4000);

  console.log(`POST ${postUrl} => ${postStatus}`);
  console.log(`Current URL after submit: ${page.url()}`);

  // Check for errors on page
  const errors = await page.evaluate(() => {
    const msgs = [];
    document.querySelectorAll('.alert, [role="alert"], .text-danger, .error, .alert-danger').forEach(el => {
      const t = el.textContent.trim();
      if (t && t.length > 2 && t.length < 300) msgs.push(t);
    });
    return msgs;
  });
  if (errors.length) console.log('Page errors:', errors);

  // If succeeded, clean up (delete the test product)
  if (postStatus === 200 || postStatus === 302 || page.url().includes('/edit')) {
    console.log('SUCCESS! Product appears to be created.');
    console.log('URL:', page.url());
  } else {
    console.log('FAILED. Trying APPROACH 2: use select2 UI clicks...');

    // APPROACH 2: Navigate back and try interacting with select2 UI
    await page.goto('https://hotel.tools/products/new');
    await page.waitForTimeout(2000);

    // Set venue context
    await page.evaluate(() => {
      const sel = document.getElementById('venue_context_selector');
      if (sel) { sel.value = '5080'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
    });
    await page.waitForTimeout(1500);
    if (await searchBtn.count()) await searchBtn.click().catch(() => {});
    await page.waitForTimeout(1500);

    // Fill form
    await page.evaluate(() => {
      const set = (sel, val) => {
        const el = document.querySelector(sel); if (!el) return;
        el.value = val;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      };
      set('#f-product-type', 'room');
      set('#f-title', 'TEST-Apartment2');
      set('#f-short-name', 'TST2');
      set('#f-base-price', '500');
      set('#f-base-currency', 'USD');
      set('#f-max-occupancy', '2');
      set('#f-status', '1');
    });

    // Go to Locations tab
    await page.locator('a[href="#products_form_locations"]').click();
    await page.waitForTimeout(1000);

    // Click the select2 container for location type
    const locPanel = page.locator('#products_form_locations');
    const select2Containers = locPanel.locator('.select2-container').filter({ hasNot: page.locator('[aria-disabled="true"]') });
    const s2count = await select2Containers.count();
    console.log(`\nselect2 containers in locations: ${s2count}`);

    // Dump all select2 containers
    const s2info = await page.evaluate(() => {
      const panel = document.getElementById('products_form_locations');
      if (!panel) return [];
      return [...panel.querySelectorAll('.select2-container')].map((c, i) => ({
        idx: i,
        disabled: c.classList.contains('select2-container--disabled'),
        text: c.querySelector('.select2-selection__rendered')?.textContent?.trim() || '',
        ariaDisabled: c.querySelector('[aria-disabled]')?.getAttribute('aria-disabled')
      }));
    });
    console.log('Select2 state:', JSON.stringify(s2info, null, 2));

    // Location type is already "Hotel" (venue) based on previous probes
    // Try clicking venue select2 and typing
    if (s2info.length >= 3 && !s2info[2].disabled) {
      // Click the venue select2
      const venueS2 = locPanel.locator('.select2-container').nth(2);
      await venueS2.click();
      await page.waitForTimeout(500);

      // Look for search input in the dropdown
      const s2Search = page.locator('.select2-search__field');
      if (await s2Search.count() > 0) {
        await s2Search.fill('Pullman');
        await page.waitForTimeout(1000);
        // Click first result
        const firstResult = page.locator('.select2-results__option').first();
        if (await firstResult.count() > 0) {
          const resultText = await firstResult.textContent();
          console.log(`First result: ${resultText}`);
          await firstResult.click();
          await page.waitForTimeout(500);
        }
      }
    }

    // Click Save Location
    await page.evaluate(() => {
      const btns = document.querySelectorAll('button');
      for (const b of btns) {
        if (b.textContent.trim() === 'Save Location') { b.click(); return; }
      }
    });
    await page.waitForTimeout(2000);

    // Check location entries
    const locEntries2 = await page.evaluate(() => {
      const panel = document.getElementById('products_form_locations');
      const blocks = panel?.querySelectorAll('.location-block[data-mode="view"]') || [];
      return [...blocks].map(b => ({
        id: b.dataset.id,
        isNew: b.dataset.new,
        typeId: b.querySelector('[data-typeid]')?.dataset.typeid || ''
      }));
    });
    console.log('Location blocks after save:', JSON.stringify(locEntries2));
  }

  await ctx.close();
});
