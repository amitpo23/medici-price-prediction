/**
 * Step 2: Introspect createProduct mutation signature and create products
 */
const { test } = require('@playwright/test');
test.setTimeout(300_000);

const TARGETS = [
  { venueId: 5080, hotel: 'Pullman Miami Airport',   product: 'Apartment', shortName: 'APT', pmsCode: 'APT' },
  { venueId: 5095, hotel: 'Cadet Hotel',             product: 'Superior',  shortName: 'SPR', pmsCode: 'SPR' },
  { venueId: 5096, hotel: 'Marseilles Hotel',         product: 'Deluxe',    shortName: 'DLX', pmsCode: 'DLX' },
  { venueId: 5098, hotel: 'Eurostars Langford',       product: 'Executive', shortName: 'EXEC', pmsCode: 'EXEC' },
  { venueId: 5110, hotel: 'Hotel Breakwater',          product: 'Apartment', shortName: 'APT', pmsCode: 'APT' },
];

test('introspect and create products', async ({ browser }) => {
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
  console.log('Logged in. URL:', page.url());

  // ===== Introspect createProduct =====
  console.log('\n=== Introspecting createProduct mutation ===');
  const introspect = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{
          __type(name: "Mutation") {
            fields {
              name
              args {
                name
                type {
                  name
                  kind
                  ofType { name kind ofType { name kind } }
                  inputFields {
                    name
                    type { name kind ofType { name kind ofType { name kind } } }
                  }
                }
              }
            }
          }
        }`
      })
    });
    const data = await resp.json();
    const field = data.data?.__type?.fields?.find(f => f.name === 'createProduct');
    return field || data;
  });
  console.log('createProduct args:', JSON.stringify(introspect, null, 2));

  // ===== Introspect product_list query =====
  console.log('\n=== Introspecting product_list query ===');
  const plIntrospect = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{
          __type(name: "Query") {
            fields(includeDeprecated: true) {
              name
              args {
                name
                type {
                  name
                  kind
                  ofType { name kind }
                }
              }
            }
          }
        }`
      })
    });
    const data = await resp.json();
    const field = data.data?.__type?.fields?.find(f => f.name === 'product_list');
    return field || { error: 'not found', all: data.data?.__type?.fields?.map(f => f.name).slice(0, 30) };
  });
  console.log('product_list args:', JSON.stringify(plIntrospect, null, 2));

  // ===== Introspect ProductChangeTypeEnum =====
  console.log('\n=== ProductChangeTypeEnum values ===');
  const enumVals = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{ __type(name: "ProductChangeTypeEnum") { enumValues { name description } } }`
      })
    });
    return (await resp.json()).data?.__type?.enumValues;
  });
  console.log('Enum values:', JSON.stringify(enumVals));

  // ===== Query products for venue 5080 (correct syntax) =====
  console.log('\n=== Querying products for 5080 ===');
  const products5080 = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{
          product_list(venueId: 5080) {
            productId
            name
            shortName
            pmsCode
            status
            productType
          }
        }`
      })
    });
    return await resp.json();
  });
  console.log('Products 5080:', JSON.stringify(products5080, null, 2));

  // ===== Try createProduct with correct types =====
  console.log('\n=== Creating test product (Apartment for 5080) ===');
  const createResult = await page.evaluate(async () => {
    const resp = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          createProduct(
            venueId: 5080
            name: "Apartment"
            shortName: "APT"
            productType: room
            basePrice: 500
            baseCurrency: "USD"
            status: 1
            baseQuantity: 10
            maxOccupancy: 2
            pmsCode: "APT"
          ) {
            productId
            name
            shortName
            pmsCode
            status
          }
        }`
      })
    });
    return await resp.json();
  });
  console.log('Create result:', JSON.stringify(createResult, null, 2));

  // If it requires an input object, try that
  if (createResult.errors) {
    console.log('\n=== Trying with input object ===');
    const createResult2 = await page.evaluate(async () => {
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
              basePrice: 500
              baseCurrency: "USD"
              status: 1
              baseQuantity: 10
              maxOccupancy: 2
              pmsCode: "APT"
            }) {
              productId
              name
              shortName
              pmsCode
              status
            }
          }`
        })
      });
      return await resp.json();
    });
    console.log('Create with input result:', JSON.stringify(createResult2, null, 2));
  }

  console.log('\nDone.');
  await ctx.close();
});
