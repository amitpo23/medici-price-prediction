/**
 * Find CSRF token and fix remaining issues for product creation
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('find csrf and create product', async ({ browser }) => {
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

  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2500);

  // Find CSRF token
  const csrfSearch = await page.evaluate(() => {
    const results = {};
    // Check meta tags
    document.querySelectorAll('meta').forEach(m => {
      const name = m.getAttribute('name') || m.getAttribute('property') || '';
      if (name.toLowerCase().includes('csrf') || name.toLowerCase().includes('token')) {
        results['meta_' + name] = m.content;
      }
    });
    // Check cookies
    results.cookies = document.cookie;
    // Check hidden inputs with csrf
    document.querySelectorAll('input[name*="csrf"], input[name*="token"], input[name="_token"]').forEach(el => {
      results['input_' + el.name] = el.value;
    });
    // Check JS variables
    if (window.__csrf) results.window_csrf = window.__csrf;
    if (window.csrf_token) results.window_csrf_token = window.csrf_token;
    if (window._token) results.window_token = window._token;
    // Check script tags for csrf patterns
    document.querySelectorAll('script').forEach(s => {
      const text = s.textContent || '';
      const match = text.match(/csrf[_\-]?token['":\s]+=?\s*['"]([^'"]+)['"]/i);
      if (match) results.script_csrf = match[1];
      const match2 = text.match(/__csrf['":\s]+=?\s*['"]([^'"]+)['"]/i);
      if (match2) results.script_csrf2 = match2[1];
    });
    // Check all data attributes
    document.querySelectorAll('[data-csrf], [data-token]').forEach(el => {
      results['data_' + el.tagName] = el.dataset.csrf || el.dataset.token;
    });
    // Check the product form specifically for __csrf field
    const csrfField = document.querySelector('input[name="__csrf"]');
    if (csrfField) {
      results.csrf_field = { value: csrfField.value, type: csrfField.type, id: csrfField.id, parent: csrfField.parentElement?.tagName };
    }
    // Check all forms for csrf inputs
    document.querySelectorAll('form').forEach((f, i) => {
      const csrf = f.querySelector('input[name="__csrf"]');
      if (csrf) results['form' + i + '_csrf'] = csrf.value;
    });
    return results;
  });
  console.log('\nCSRF search results:', JSON.stringify(csrfSearch, null, 2));

  // Also check the page HTML for csrf patterns
  const pageContent = await page.content();
  const csrfMatches = pageContent.match(/__csrf[^a-z].*?['"](.*?)['"]/g);
  if (csrfMatches) console.log('\nHTML csrf matches:', csrfMatches.slice(0, 5));

  // Check X-PJAX response header - the server uses PJAX
  // Maybe the CSRF is set via an AJAX header
  const csrfFromCookies = await page.evaluate(() => {
    const cookies = {};
    document.cookie.split(';').forEach(c => {
      const [k, v] = c.trim().split('=');
      if (k) cookies[k] = v;
    });
    return cookies;
  });
  console.log('\nCookies:', JSON.stringify(csrfFromCookies, null, 2));

  await ctx.close();
});
