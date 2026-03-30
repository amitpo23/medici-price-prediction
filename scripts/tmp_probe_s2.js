/**
 * Probe: Interact with Location tab select2 elements step by step
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('probe select2 location', async ({ browser }) => {
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

  // Navigate to /products/new
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

  // Click Locations tab
  await page.locator('a[href="#products_form_locations"]').click();
  await page.waitForTimeout(1000);
  console.log('On Locations tab');

  // Step 1: Check what's visible
  const visibleS2 = await page.evaluate(() => {
    const panel = document.getElementById('products_form_locations');
    const containers = [...panel.querySelectorAll('.select2-container')];
    return containers.map((c, i) => ({
      idx: i,
      visible: !!(c.offsetParent || c.offsetWidth > 0),
      text: c.querySelector('.select2-selection__rendered')?.textContent?.trim() || '',
      rect: c.getBoundingClientRect()
    }));
  });
  console.log('Select2 visibility:', JSON.stringify(visibleS2, null, 2));

  // Step 2: Click location type select2 (should be the first VISIBLE one)
  // Use select2's jQuery API to set "venue"
  const hasJQuery = await page.evaluate(() => typeof $ !== 'undefined' || typeof jQuery !== 'undefined');
  console.log(`jQuery available: ${hasJQuery}`);

  if (hasJQuery) {
    // Use jQuery select2 API
    console.log('\n--- Using jQuery select2 API ---');
    
    // Set location type to "venue" via select2
    const typeResult = await page.evaluate(() => {
      const panel = document.getElementById('products_form_locations');
      const typeSelect = panel.querySelector('select[data-control="type"]');
      if (!typeSelect) return 'type select not found';
      $(typeSelect).val('venue').trigger('change');
      return 'set type=venue via jQuery';
    });
    console.log(typeResult);
    await page.waitForTimeout(2000);

    // Check what happened
    const afterType = await page.evaluate(() => {
      const panel = document.getElementById('products_form_locations');
      const containers = [...panel.querySelectorAll('.select2-container')];
      return containers.map((c, i) => ({
        idx: i,
        visible: !!(c.offsetParent || c.offsetWidth > 0),
        text: c.querySelector('.select2-selection__rendered')?.textContent?.trim() || ''
      }));
    });
    console.log('After type=venue:', JSON.stringify(afterType));

    // Set venue via select2 jQuery
    const venueResult = await page.evaluate(() => {
      const vsel = document.querySelector('select[name="venue"]');
      if (!vsel) return 'venue select not found';
      // Check if it has the venue ID as option
      const has5080 = [...vsel.options].some(o => o.value === '5080');
      if (!has5080) return `venue 5080 not in options (${vsel.options.length} options)`;
      $(vsel).val('5080').trigger('change');
      return `set venue=5080 via jQuery (${vsel.options.length} options)`;
    });
    console.log(venueResult);
    await page.waitForTimeout(1500);

    // Check venue selection rendered text
    const venueText = await page.evaluate(() => {
      const panel = document.getElementById('products_form_locations');
      // The venue select2 should show the hotel name now
      const containers = [...panel.querySelectorAll('.select2-container')];
      return containers.map((c, i) => ({
        idx: i,
        text: c.querySelector('.select2-selection__rendered')?.textContent?.trim() || '',
        visible: !!(c.offsetParent || c.offsetWidth > 0)
      }));
    });
    console.log('After venue set:', JSON.stringify(venueText));

    // Click Save Location
    const saveResult = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button')];
      const saveBtn = btns.find(b => b.textContent.trim() === 'Save Location');
      if (!saveBtn) return 'Save Location button not found';
      saveBtn.click();
      return 'clicked';
    });
    console.log('Save Location:', saveResult);
    await page.waitForTimeout(2500);

    // Check location blocks
    const blocks = await page.evaluate(() => {
      const panel = document.getElementById('products_form_locations');
      const locBlocks = panel?.querySelectorAll('.location-block[data-mode="view"]') || [];
      return [...locBlocks].map(b => ({
        id: b.dataset.id,
        isNew: b.dataset.new,
        html: b.innerHTML.substring(0, 500)
      }));
    });
    console.log(`\nLocation blocks: ${blocks.length}`);
    for (const b of blocks) {
      console.log(`  Block ${b.id} (new=${b.isNew}): ${b.html.substring(0, 200)}`);
    }

    // Check the hidden inputs generated
    const locInputs = await page.evaluate(() => {
      const form = document.querySelector('form.product-form') || document.querySelector('form[method="post"]');
      if (!form) {
        // Try to find any form with product data
        const forms = [...document.querySelectorAll('form')];
        for (const f of forms) {
          if (f.querySelector('#f-title')) return { formAction: f.action, inputs: 'found product form' };
        }
        return { error: 'no product form found', forms: forms.map(f => f.action) };
      }
      const inputs = [];
      form.querySelectorAll('input, select, textarea').forEach(el => {
        if (el.name && (el.name.includes('location') || el.name.includes('meta') || el.name.includes('pms'))) {
          inputs.push({ name: el.name, value: el.value?.substring(0, 50) || '', type: el.type });
        }
      });
      return { formAction: form.action, locationInputs: inputs };
    });
    console.log('\nForm location inputs:', JSON.stringify(locInputs, null, 2));

    // Now try to submit
    // First go back to General tab and fill fields
    await page.locator('a[href="#products_form_general"]').click();
    await page.waitForTimeout(500);

    await page.evaluate(() => {
      const set = (s, v) => { const e = document.querySelector(s); if (e) { e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }};
      set('#f-product-type', 'room');
      set('#f-title', 'TEST-Apt-Probe');
      set('#f-short-name', 'TST');
      set('#f-base-price', '500');
      set('#f-base-currency', 'USD');
      set('#f-max-occupancy', '2');
      set('#f-status', '1');
      set('#f-start-date', '2025-01-01');
      set('#f-alt-start-date', '2025-01-01');
      set('#f-end-date', '2027-12-31');
      set('#f-alt-end-date', '2027-12-31');
    });

    let postStatus = 0;
    page.on('response', resp => {
      if (resp.request().method() === 'POST' && resp.url().includes('products') && !resp.url().includes('analytics')) {
        postStatus = resp.status();
      }
    });

    const submitBtn = page.locator('button[type="submit"]').first();
    await submitBtn.click();
    await page.waitForTimeout(4000);

    console.log(`\nPOST status: ${postStatus}`);
    console.log(`URL after submit: ${page.url()}`);

    const pageErrors = await page.evaluate(() => {
      return [...document.querySelectorAll('.alert, .alert-danger, .text-danger')].map(e => e.textContent.trim().substring(0, 200));
    });
    if (pageErrors.length) console.log('Errors:', pageErrors);

    // If we got redirected to edit page, it worked!
    if (page.url().includes('/edit')) {
      console.log('\n*** SUCCESS - product created! ***');
      // Delete it so we don't pollute
      // ... would need delete endpoint
    }

  } else {
    console.log('No jQuery on page - cannot use select2 API');
  }

  await ctx.close();
});
