/**
 * Create missing products via Noovy GraphQL API (bypasses broken Hotel.Tools product creation)
 * 
 * Hotel.Tools POST /products returns HTTP 500 (known bug since 2026-03-14).
 * Noovy's GraphQL createProduct mutation might work as an alternative.
 * 
 * Step 1: Login to Noovy
 * Step 2: Query existing products for target venues
 * Step 3: Create missing products via mutation
 * Step 4: Verify
 */
const { test } = require('@playwright/test');
test.setTimeout(300_000);

const TARGETS = [
  { venueId: 5080, hotel: 'Pullman Miami Airport',  product: 'Apartment', shortName: 'APT', pmsCode: 'APT' },
  { venueId: 5095, hotel: 'Cadet Hotel',            product: 'Superior',  shortName: 'SPR', pmsCode: 'SPR' },
  { venueId: 5096, hotel: 'Marseilles Hotel',        product: 'Deluxe',    shortName: 'DLX', pmsCode: 'DLX' },
  { venueId: 5098, hotel: 'Eurostars Langford',      product: 'Executive', shortName: 'EXEC', pmsCode: 'EXEC' },
  { venueId: 5110, hotel: 'Hotel Breakwater',         product: 'Apartment', shortName: 'APT', pmsCode: 'APT' },
];

test('create products via Noovy GraphQL', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1700, height: 1100 } });
  const page = await ctx.newPage();

  // ===== Step 1: Login to Noovy =====
  console.log('Step 1: Logging in to Noovy...');
  await page.goto('https://app.noovy.com');
  await page.waitForTimeout(3000);

  // Fill login form
  const accountField = page.getByRole('textbox', { name: /account/i }).or(page.locator('input[name*="account"]'));
  const userField = page.getByRole('textbox', { name: /user|agent/i }).or(page.locator('input[name*="user"], input[name*="agent"]'));
  const passField = page.locator('input[type="password"]');

  if (await accountField.count()) await accountField.first().fill('Medici LIVE');
  if (await userField.count()) await userField.first().fill('zvi');
  if (await passField.count()) await passField.first().fill('karpad66');

  const loginBtn = page.getByRole('button', { name: /login|sign in/i });
  if (await loginBtn.count()) await loginBtn.first().click();
  await page.waitForTimeout(5000);

  console.log('  Current URL:', page.url());

  // ===== Step 2: Test GraphQL connectivity =====
  console.log('\nStep 2: Testing GraphQL API...');

  // First test: simple query
  const testResult = await page.evaluate(async () => {
    try {
      const resp = await fetch('/graphql/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: `{ __schema { queryType { name } mutationType { name } } }` 
        })
      });
      const data = await resp.json();
      return { status: resp.status, data };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log('  Schema test:', JSON.stringify(testResult, null, 2));

  // ===== Step 3: Query existing products for target venues =====
  console.log('\nStep 3: Querying existing products...');
  
  for (const target of TARGETS) {
    const products = await page.evaluate(async (venueId) => {
      try {
        const resp = await fetch('/graphql/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: `query($venueId: Int!) {
              product_list(filter: { venueId: $venueId, productType: "room" }) {
                productId
                name
                shortName
                pmsCode
                status
              }
            }`,
            variables: { venueId }
          })
        });
        return await resp.json();
      } catch (e) {
        return { error: e.message };
      }
    }, target.venueId);
    
    console.log(`  Venue ${target.venueId} (${target.hotel}):`);
    if (products.data?.product_list) {
      for (const p of products.data.product_list) {
        console.log(`    - ${p.name} (${p.shortName}) PMS:${p.pmsCode} Status:${p.status} ID:${p.productId}`);
      }
      // Check if target product already exists
      const existing = products.data.product_list.find(p => 
        p.shortName === target.shortName || p.pmsCode === target.pmsCode
      );
      if (existing) {
        console.log(`    >>> ${target.product} ALREADY EXISTS (ID: ${existing.productId})`);
        target.skip = true;
      } else {
        console.log(`    >>> ${target.product} (${target.pmsCode}) NEEDS CREATION`);
      }
    } else {
      console.log(`    Result:`, JSON.stringify(products).substring(0, 200));
    }
  }

  // ===== Step 4: Check available mutations =====
  console.log('\nStep 4: Checking createProduct mutation...');
  const mutationCheck = await page.evaluate(async () => {
    try {
      // Check what mutations are available
      const resp = await fetch('/graphql/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `{
            __schema {
              mutationType {
                fields {
                  name
                  description
                }
              }
            }
          }`
        })
      });
      const data = await resp.json();
      if (data.data?.__schema?.mutationType?.fields) {
        return data.data.__schema.mutationType.fields
          .filter(f => f.name.toLowerCase().includes('product'))
          .map(f => ({ name: f.name, description: f.description }));
      }
      return data;
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log('  Product-related mutations:', JSON.stringify(mutationCheck, null, 2));

  // ===== Step 5: Try to create one product =====
  const toCreate = TARGETS.filter(t => !t.skip);
  if (toCreate.length === 0) {
    console.log('\nAll products already exist! Nothing to create.');
    await ctx.close();
    return;
  }

  console.log(`\nStep 5: Creating ${toCreate.length} products...`);
  const firstTarget = toCreate[0];

  const createResult = await page.evaluate(async (target) => {
    try {
      const resp = await fetch('/graphql/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `mutation CreateProduct($input: CreateProductInput!) {
            createProduct(input: $input) {
              productId
              name
              status
            }
          }`,
          variables: {
            input: {
              venueId: target.venueId,
              name: target.product,
              shortName: target.shortName,
              productType: "room",
              basePrice: 500,
              baseCurrency: "USD",
              status: "active",
              baseQuantity: 10,
              maxOccupancy: 2,
              pmsCode: target.pmsCode,
              locations: [{
                venueId: target.venueId,
                countryCode: "US"
              }]
            }
          }
        })
      });
      const data = await resp.json();
      return { status: resp.status, data };
    } catch (e) {
      return { error: e.message };
    }
  }, firstTarget);

  console.log(`  Create ${firstTarget.product} for ${firstTarget.hotel}:`, JSON.stringify(createResult, null, 2));

  // If mutation doesn't exist, try alternative input format
  if (createResult.data?.errors) {
    console.log('\n  Trying alternative mutation format...');
    const altResult = await page.evaluate(async (target) => {
      try {
        const resp = await fetch('/graphql/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: `mutation {
              createProduct(input: {
                venueId: ${target.venueId}
                name: "${target.product}"
                shortName: "${target.shortName}"
                productType: "room"
                basePrice: 500
                baseCurrency: "USD"
                status: "active"
                baseQuantity: 10
                maxOccupancy: 2
                pmsCode: "${target.pmsCode}"
              }) {
                productId
                name
                status
              }
            }`
          })
        });
        const data = await resp.json();
        return { status: resp.status, data };
      } catch (e) {
        return { error: e.message };
      }
    }, firstTarget);
    console.log(`  Alternative result:`, JSON.stringify(altResult, null, 2));
  }

  console.log('\nDone.');
  await ctx.close();
});
