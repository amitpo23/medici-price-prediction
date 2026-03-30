/**
 * Debug 401 on createProduct:
 * 1. Verify login succeeded
 * 2. Check product_list correct syntax
 * 3. Try introspecting productInputParameters
 * 4. Check if we can do ANY mutation
 */
const { test } = require('@playwright/test');
test.setTimeout(120_000);

test('debug noovy auth', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await ctx.newPage();

  // Login
  await page.goto('https://app.noovy.com');
  await page.waitForTimeout(3000);
  const accountField = page.getByRole('textbox', { name: /account/i }).or(page.locator('input[name*="account"]'));
  const userField = page.getByRole('textbox', { name: /user|agent/i }).or(page.locator('input[name*="user"], input[name*="agent"]'));
  const passField = page.locator('input[type="password"]');
  if (await accountField.count()) await accountField.first().fill('Medici LIVE');
  if (await userField.count()) await userField.first().fill('zvi');
  if (await passField.count()) await passField.first().fill('karpad66');
  const loginBtn = page.getByRole('button', { name: /login|sign in/i });
  if (await loginBtn.count()) await loginBtn.first().click();
  await page.waitForTimeout(5000);
  console.log('URL after login:', page.url());

  // Check if we're actually logged in
  const loginStatus = await page.evaluate(() => {
    return {
      cookies: document.cookie.split(';').map(c => c.trim().split('=')[0]),
      title: document.title,
      bodyText: document.body?.innerText?.substring(0, 200)
    };
  });
  console.log('Login status:', JSON.stringify(loginStatus, null, 2));

  // ===== Introspect productInputParameters =====
  console.log('\n=== Introspect productInputParameters ===');
  const inputType = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{
          __type(name: "productInputParameters") {
            name
            kind
            inputFields {
              name
              type {
                name
                kind
                ofType { name kind }
              }
            }
          }
        }`
      })
    });
    return await resp.json();
  });
  console.log(JSON.stringify(inputType, null, 2));

  // ===== Try product_list with no args =====
  console.log('\n=== product_list (no args) ===');
  const plResult = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{
          product_list {
            productId
            name
            shortName
            pmsCode
            venueId
            status
          }
        }`
      })
    });
    return await resp.json();
  });
  if (plResult.data?.product_list) {
    console.log(`Got ${plResult.data.product_list.length} products`);
    // Show products for target venues
    for (const vid of [5080, 5095, 5096, 5098, 5110]) {
      const vProducts = plResult.data.product_list.filter(p => p.venueId === vid);
      console.log(`  Venue ${vid}: ${vProducts.map(p => `${p.name}(${p.shortName}/${p.pmsCode}) s:${p.status}`).join(', ') || 'NONE'}`);
    }
  } else {
    console.log('product_list result:', JSON.stringify(plResult).substring(0, 500));
  }

  // ===== Get user profile =====
  console.log('\n=== User profile ===');
  const profile = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{ getProfile { userId name permissions } }`
      })
    });
    return await resp.json();
  });
  console.log('Profile:', JSON.stringify(profile, null, 2));

  // ===== Try allowed simple mutations =====
  console.log('\n=== Test changeProductStatus ===');
  // Use a known product ID from the product list
  if (plResult.data?.product_list?.length) {
    const knownProduct = plResult.data.product_list
      .filter(p => [5080, 5095, 5096, 5098, 5110].includes(p.venueId))[0];
    if (knownProduct) {
      console.log(`  Testing with product ${knownProduct.productId} (${knownProduct.name})`);
      const statusResult = await page.evaluate(async (pid) => {
        const resp = await fetch('/graphql/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: `mutation { changeProductStatus(productId: ${pid}, status: 1) { productId status } }`
          })
        });
        return await resp.json();
      }, knownProduct.productId);
      console.log('  changeProductStatus result:', JSON.stringify(statusResult, null, 2));
    }
  }

  // ===== Try createProduct with EXACT input type fields =====
  console.log('\n=== createProduct with exact schema fields ===');
  // Build the input based on the introspected fields
  if (inputType.data?.__type?.inputFields) {
    const fieldNames = inputType.data.__type.inputFields.map(f => f.name);
    console.log('  Input fields:', fieldNames.join(', '));
  }

  // Try with minimal fields
  const minCreate = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          createProduct(input: {
            venueId: 5080
            name: "Apartment"
            shortName: "APT"
            productType: room
            status: 1
          }) {
            productId
            name
          }
        }`
      })
    });
    return await resp.json();
  });
  console.log('Minimal createProduct:', JSON.stringify(minCreate, null, 2));

  console.log('\nDone.');
  await ctx.close();
});
