/**
 * Deep diagnostic: Investigate the product creation page structure.
 * Find the REAL product form, CSRF token, and submission mechanism.
 */
const { test } = require('@playwright/test');

test.setTimeout(120_000);

test('deep product form diagnostic', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await context.newPage();

  // Monitor ALL network requests
  page.on('request', (req) => {
    if (req.method() === 'POST') {
      console.log(`  [REQ] POST ${req.url()}`);
      const postData = req.postData();
      if (postData) {
        console.log(`    Body keys: ${postData.substring(0, 300)}`);
      }
    }
  });
  page.on('response', (resp) => {
    if (resp.request().method() === 'POST') {
      console.log(`  [RES] ${resp.status()} ${resp.url()}`);
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

  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2000);

  // Set venue context
  await page.evaluate(() => {
    const sel = document.querySelector('#venue_context_selector');
    if (sel) { sel.value = '5080'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.waitForTimeout(1000);
  const searchBtn = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn.count()) await searchBtn.click().catch(() => {});
  await page.waitForTimeout(1500);

  // 1. Find ALL forms on page
  console.log('=== ALL FORMS ===');
  const forms = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('form')).map((f, i) => ({
      index: i,
      id: f.id,
      action: f.action,
      method: f.method,
      className: f.className,
      fields: Array.from(f.querySelectorAll('input, select, textarea')).map(el => ({
        tag: el.tagName,
        name: el.name,
        id: el.id,
        type: el.type,
      })).slice(0, 30),
    }));
  });
  for (const f of forms) {
    console.log(`\nForm #${f.index}: id="${f.id}" class="${f.className}"`);
    console.log(`  action: ${f.action}`);
    console.log(`  method: ${f.method}`);
    console.log(`  fields (${f.fields.length}):`);
    for (const fld of f.fields) {
      console.log(`    ${fld.tag} name="${fld.name}" id="${fld.id}" type="${fld.type}"`);
    }
  }

  // 2. Find ALL buttons on page
  console.log('\n=== ALL BUTTONS ===');
  const buttons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button, input[type="submit"], a.btn')).map((b, i) => ({
      index: i,
      tag: b.tagName,
      type: b.type,
      text: b.textContent?.trim()?.substring(0, 50),
      className: b.className?.substring(0, 80),
      form: b.form?.id || b.form?.action || 'none',
      onclick: b.getAttribute('onclick')?.substring(0, 100),
      dataAction: b.getAttribute('data-action'),
    }));
  });
  for (const b of buttons) {
    console.log(`  #${b.index} <${b.tag}> type="${b.type}" text="${b.text}" form="${b.form}" onclick="${b.onclick || ''}" data-action="${b.dataAction || ''}"`);
  }

  // 3. Check for JavaScript-based form handling
  console.log('\n=== JS FORM HANDLERS ===');
  const jsHandlers = await page.evaluate(() => {
    // Check for product form initialization
    const results = [];
    
    // Look for jQuery form submission handlers
    if (window.jQuery) {
      results.push('jQuery available');
      // Check if there's a product form object
      const $forms = window.jQuery('form');
      results.push(`jQuery forms: ${$forms.length}`);
    }
    
    // Check for global product/form objects
    const globals = ['productForm', 'formManager', 'productManager', 'saveProduct', 'submitProduct', 'createProduct'];
    for (const g of globals) {
      if (window[g]) results.push(`window.${g} exists: ${typeof window[g]}`);
    }
    
    // Check for data-* attributes on save buttons
    const saveBtns = document.querySelectorAll('button');
    for (const btn of saveBtns) {
      const text = btn.textContent?.trim();
      if (/save|submit|create/i.test(text)) {
        results.push(`Save btn: "${text}" attrs: ${JSON.stringify(Object.fromEntries([...btn.attributes].map(a => [a.name, a.value.substring(0, 50)])))}`);
      }
    }

    return results;
  });
  for (const h of jsHandlers) console.log(`  ${h}`);

  // 4. Look for AJAX/fetch setup
  console.log('\n=== CSRF / META ===');
  const csrfInfo = await page.evaluate(() => {
    const metas = Array.from(document.querySelectorAll('meta')).map(m => ({
      name: m.name || m.getAttribute('property'),
      content: m.content?.substring(0, 50),
    })).filter(m => m.name);
    const hiddenInputs = Array.from(document.querySelectorAll('input[type="hidden"]')).map(i => ({
      name: i.name,
      value: i.value?.substring(0, 50),
      form: i.form?.id || 'none',
    }));
    return { metas, hiddenInputs };
  });
  console.log('Metas:', JSON.stringify(csrfInfo.metas, null, 2));
  console.log('Hidden inputs:', JSON.stringify(csrfInfo.hiddenInputs, null, 2));

  // 5. Locations tab deep dive
  console.log('\n=== LOCATIONS TAB ===');
  const locTab = page.locator('a[href="#locations"], [data-toggle="tab"]:has-text("Location")');
  if (await locTab.count() > 0) {
    await locTab.first().click();
    await page.waitForTimeout(1000);

    const locInfo = await page.evaluate(() => {
      const block = document.querySelector('.location-block');
      if (!block) return 'No .location-block found';
      
      const fields = Array.from(block.querySelectorAll('select, input')).map(el => ({
        tag: el.tagName,
        name: el.name,
        id: el.id,
        type: el.type,
        visible: el.offsetParent !== null,
        isSelect2: el.classList.contains('select2-hidden-accessible'),
        options: el.tagName === 'SELECT' ? Array.from(el.options).slice(0, 5).map(o => `${o.value}:${o.text.substring(0, 30)}`) : undefined,
      }));
      
      // Find add/save location button
      const btns = Array.from(block.querySelectorAll('button, a.btn, .btn')).map(b => ({
        text: b.textContent?.trim()?.substring(0, 50),
        className: b.className?.substring(0, 80),
        onclick: b.getAttribute('onclick')?.substring(0, 100),
      }));
      
      return { fields, btns, html: block.innerHTML.substring(0, 800) };
    });
    console.log(JSON.stringify(locInfo, null, 2));
  }

  // 6. Try filling form and clicking save — watch network
  console.log('\n=== FILL AND SUBMIT ===');
  
  // Go back to General tab
  const generalTab = page.locator('a[href="#general"], [data-toggle="tab"]:has-text("General")');
  if (await generalTab.count()) await generalTab.first().click();
  await page.waitForTimeout(500);

  // Fill via jQuery/JS
  const fillResult = await page.evaluate(() => {
    const results = [];
    const set = (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) { results.push(`${sel}: NOT FOUND`); return; }
      el.value = val;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      results.push(`${sel}: set to "${val}"`);
    };

    // Venue via jQuery select2
    if (window.jQuery) {
      const $v = window.jQuery('select[name="venue"]');
      if ($v.length) {
        $v.val('5080').trigger('change');
        results.push(`venue: jQuery set to 5080 (val=${$v.val()})`);
      }
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

    return results;
  });
  for (const r of fillResult) console.log(`  ${r}`);

  // Now click Save and watch
  console.log('\nClicking Save...');
  const saveBtns = page.getByRole('button', { name: /save|create|submit/i });
  const count = await saveBtns.count();
  for (let i = 0; i < count; i++) {
    const text = await saveBtns.nth(i).textContent();
    console.log(`  Button ${i}: "${text.trim()}"`);
  }

  if (count > 0) {
    // Click the first save button
    await saveBtns.first().click();
    await page.waitForTimeout(5000);
    console.log(`After click - URL: ${page.url()}`);

    // Check for validation errors
    const pageErrors = await page.evaluate(() => {
      const errs = [];
      document.querySelectorAll('.alert-danger, .error, .invalid-feedback, .text-danger, .help-block').forEach(el => {
        const t = el.textContent?.trim();
        if (t) errs.push(t.substring(0, 200));
      });
      // Also check for toast/notification
      document.querySelectorAll('.toast, .notification, .swal2-popup, .noty_body').forEach(el => {
        const t = el.textContent?.trim();
        if (t) errs.push(`[toast] ${t.substring(0, 200)}`);
      });
      return errs;
    });
    if (pageErrors.length) {
      console.log('Page messages:', JSON.stringify(pageErrors));
    }
  }

  await context.close();
});
