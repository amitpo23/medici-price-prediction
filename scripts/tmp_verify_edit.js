/**
 * Confirm: EDITING an existing product also returns 500
 * This proves it's a server-side issue, not our form data
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('verify server product save', async ({ browser }) => {
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

  // Set venue context
  await page.evaluate((v) => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = String(v); sel.dispatchEvent(new Event('change', { bubbles: true })); }
  }, 5080);
  await page.waitForTimeout(1000);

  // ===== TEST A: Edit existing product via direct fetch =====
  console.log('=== TEST A: Edit existing product via fetch ===');
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);
  
  // Set venue context again on products page
  await page.evaluate((v) => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = String(v); sel.dispatchEvent(new Event('change', { bubbles: true })); }
  }, 5080);
  await page.waitForTimeout(1000);
  const searchBtn = page.getByRole('button', { name: /search/i }).first();
  if (await searchBtn.count()) await searchBtn.click().catch(() => {});
  await page.waitForTimeout(2000);

  // Get first product's edit link
  const editHref = await page.locator('table tbody tr a').first().getAttribute('href');
  console.log('  First product edit link:', editHref);

  if (editHref) {
    // Go to edit page
    await page.goto('https://hotel.tools' + editHref);
    await page.waitForTimeout(3000);
    console.log('  Edit page loaded:', page.url());

    // Get ALL form data from the edit page
    const formInfo = await page.evaluate(() => {
      const forms = document.querySelectorAll('form');
      const result = [];
      for (const form of forms) {
        const fd = new FormData(form);
        const entries = {};
        let count = 0;
        for (const [k, v] of fd.entries()) {
          entries[k] = String(v).substring(0, 100);
          count++;
        }
        result.push({
          id: form.id,
          action: form.action,
          method: form.method,
          fieldCount: count,
          sampleFields: Object.keys(entries).slice(0, 15)
        });
      }
      return result;
    });
    console.log('  Forms on edit page:', JSON.stringify(formInfo, null, 2));

    // Get the product form's action URL
    const productForm = formInfo.find(f => f.id && f.id.includes('product'));
    const formAction = productForm?.action || '';
    console.log('  Product form action:', formAction);

    // Serialize the existing form and POST it back unchanged
    const editResult = await page.evaluate(async () => {
      const form = document.querySelector('form[id*="product"]') || document.querySelector('form[action*="product"]');
      if (!form) {
        // Try finding form by method
        const allForms = [...document.querySelectorAll('form')];
        const postForm = allForms.find(f => f.method.toLowerCase() === 'post' && f.querySelectorAll('input').length > 5);
        if (!postForm) return { error: 'No product form found', formCount: allForms.length };
      }
      const targetForm = form || document.querySelector('form[method="post"]');
      const fd = new FormData(targetForm);
      const body = new URLSearchParams(fd).toString();
      
      const resp = await fetch(targetForm.action || window.location.href, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          'X-PJAX': 'true',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: body,
        credentials: 'same-origin'
      });
      const text = await resp.text();
      return { 
        status: resp.status, 
        body: text.substring(0, 1000),
        formAction: targetForm.action,
        formMethod: targetForm.method,
        paramCount: [...new URLSearchParams(body).keys()].length,
        csrfValue: new URLSearchParams(body).get('__csrf')
      };
    });
    console.log('  Edit re-submit result:', JSON.stringify(editResult, null, 2));
  }

  // ===== TEST B: Check permissions - can we even see the "New" button? =====
  console.log('\n=== TEST B: Check user permissions indicators ===');
  await page.goto('https://hotel.tools/products');
  await page.waitForTimeout(2000);
  
  const newProductLinks = await page.evaluate(() => {
    return [...document.querySelectorAll('a')].filter(a => {
      const text = (a.textContent || '').toLowerCase();
      return text.includes('new') || text.includes('add') || text.includes('create');
    }).map(a => ({ text: a.textContent.trim(), href: a.href }));
  });
  console.log('  New/Add/Create links:', JSON.stringify(newProductLinks, null, 2));

  // Check user role
  const userInfo = await page.evaluate(() => {
    return {
      bodyClasses: document.body.className,
      metaRole: document.querySelector('meta[name="user-role"]')?.content,
      menuItems: [...document.querySelectorAll('.sidebar-menu a, .nav-sidebar a')].slice(0, 10).map(a => a.textContent.trim()),
      userDisplay: document.querySelector('.user-name, .username, [data-user]')?.textContent?.trim()
    };
  });
  console.log('  User info:', JSON.stringify(userInfo, null, 2));

  // ===== TEST C: GET /products/new and check response closely =====
  console.log('\n=== TEST C: Check response headers on product API ===');
  const apiResult = await page.evaluate(async () => {
    // Try GET /products/new — should return the form
    const resp = await fetch('/products/new', { credentials: 'same-origin' });
    const headers = Object.fromEntries(resp.headers.entries());
    return { status: resp.status, headers: headers };
  });
  console.log('  GET /products/new:', JSON.stringify({ status: apiResult.status }, null, 2));

  // Try an OPTIONS request
  const optResult = await page.evaluate(async () => {
    const resp = await fetch('/products', { method: 'OPTIONS', credentials: 'same-origin' });
    return { status: resp.status };
  });
  console.log('  OPTIONS /products:', JSON.stringify(optResult, null, 2));

  console.log('\nDone.');
  await ctx.close();
});
