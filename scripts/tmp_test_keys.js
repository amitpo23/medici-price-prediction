/**
 * Test different location key formats. The server crashes (500) on location data.
 * Existing products use numeric IDs (e.g. locations[41092]).
 * Let's test: numeric, zero, string, and no location.  
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('test location key formats', async ({ browser }) => {
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

  await page.goto('https://hotel.tools/products/new');
  await page.waitForTimeout(2000);

  // Set venue context
  await page.evaluate((v) => {
    const sel = document.getElementById('venue_context_selector');
    if (sel) { sel.value = String(v); sel.dispatchEvent(new Event('change', { bubbles: true })); }
  }, 5080);
  await page.waitForTimeout(1000);

  async function tryPost(label, extraParams) {
    const result = await page.evaluate(async (params) => {
      const body = new URLSearchParams();
      body.append('product_type', 'room');
      body.append('title', 'TEST-' + params.label);
      body.append('short_name', params.label.substring(0, 3));
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
      body.append('__csrf', '');

      for (const [k, v] of Object.entries(params.extra)) {
        body.append(k, v);
      }

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
    }, { label, extra: extraParams });
    console.log(`${label}: ${result.status} — ${result.body.substring(0, 200)}`);
    return result;
  }

  // Test 1: No location at all
  console.log('=== Tests ===\n');
  await tryPost('NO-LOC', {});

  // Test 2: Location key = numeric 0
  await tryPost('LOC-0', {
    'locations[0][type]': 'venue',
    'locations[0][venue]': '5080',
    'states[location][0]': 'added'
  });

  // Test 3: Location key = numeric 1
  await tryPost('LOC-1', {
    'locations[1][type]': 'venue',
    'locations[1][venue]': '5080',
    'states[location][1]': 'added'
  });

  // Test 4: Location key = "new"
  await tryPost('LOC-NEW', {
    'locations[new][type]': 'venue',
    'locations[new][venue]': '5080',
    'states[location][new]': 'added'
  });

  // Test 5: Just venue field (no locations array)
  await tryPost('VENUE-ONLY', {
    'venue': '5080'
  });

  // Test 6: Location key = "new" WITHOUT states
  await tryPost('LOC-NO-STATE', {
    'locations[new][type]': 'venue',
    'locations[new][venue]': '5080'
  });

  // Test 7: Location with ALL fields including address
  await tryPost('LOC-FULL', {
    'locations[new-loc][type]': 'venue',
    'locations[new-loc][venue]': '5080',
    'locations[new-loc][country]': '',
    'locations[new-loc][address]': '',
    'states[location][new-loc]': 'added'
  });

  // Test 8: Just venue field + states
  await tryPost('VENUE+STATE', {
    'venue': '5080',
    'states[location][5080]': 'added'
  });

  // Test 9: venue_id (not venue)
  await tryPost('VENUE-ID', {
    'venue_id': '5080'
  });

  // Test 10: Location using format from existing product + extra type/venue  
  await tryPost('LOC-EXIST-FMT', {
    'locations[99999][address]': '',
    'locations[99999][type]': 'venue',
    'locations[99999][venue]': '5080',
    'states[location][99999]': 'added'
  });

  // Test 11: Try sending the form via the actual form method (non-PJAX, non-AJAX)
  console.log('\n=== TEST 11: Non-AJAX form submission ===');
  const t11 = await page.evaluate(async () => {
    const body = new URLSearchParams();
    body.append('product_type', 'room');
    body.append('title', 'TEST-PLAIN');
    body.append('short_name', 'TPL');
    body.append('base_price', '500');
    body.append('base_currency', 'USD');
    body.append('max_occupancy', '2');
    body.append('status', '1');
    body.append('meal_plan_type', 'RO');
    body.append('start_date', '2025-01-01');
    body.append('end_date', '2027-12-31');
    body.append('price_per', 'person');
    body.append('locations[0][type]', 'venue');
    body.append('locations[0][venue]', '5080');
    body.append('__csrf', '');

    // Regular POST without PJAX/AJAX headers
    const resp = await fetch('/products', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
      },
      body: body.toString(),
      credentials: 'same-origin'
    });
    const text = await resp.text();
    return { status: resp.status, body: text.substring(0, 300) };
  });
  console.log(`PLAIN: ${t11.status} — ${t11.body.substring(0, 200)}`);

  console.log('\nDone.');
  await ctx.close();
});
