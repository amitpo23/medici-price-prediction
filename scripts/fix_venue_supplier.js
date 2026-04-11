/**
 * Fix connected_to_supplier on all 21 ZENITH-FAIL venues.
 * Root cause: venue edit page General tab has connected_to_supplier="" (should be "Medici")
 * 
 * Phase 1: Test on ONE venue (5140 - Gates Hotel), verify with reload
 * Phase 2: Apply to all 21 remaining venues
 */
const { test, expect } = require('@playwright/test');

const FAILING_VENUES = [
  { id: '5075', name: 'Villa Casa Casuarina' },
  { id: '5115', name: 'Hilton Cabana Miami Beach' },
  { id: '5116', name: 'Kimpton Hotel Palomar SB' },
  { id: '5119', name: 'citizenM Miami SB' },
  { id: '5124', name: 'Grand Beach Hotel Miami' },
  { id: '5130', name: 'Holiday Inn Express' },
  { id: '5132', name: 'Hôtel Gaythering' },
  { id: '5136', name: 'Kimpton Angler\'s' },
  { id: '5138', name: 'The Landon Bay Harbor' },
  { id: '5139', name: 'SERENA Hotel Aventura' },
  { id: '5140', name: 'Gates Hotel South Beach' },
  { id: '5265', name: 'Hotel Belleza' },
  { id: '5266', name: 'Dorchester Hotel' },
  { id: '5267', name: 'Gale South Beach' },
  { id: '5268', name: 'Fontainebleau Miami Beach' },
  { id: '5274', name: 'Generator Miami' },
  { id: '5275', name: 'Miami Intl Airport Hotel' },
  { id: '5276', name: 'InterContinental Miami' },
  { id: '5277', name: 'Catalina Hotel & Beach Club' },
  { id: '5278', name: 'Gale Miami Hotel' },
  { id: '5279', name: 'Hilton Garden Inn Miami SB' },
];

test('fix connected_to_supplier on failing venues', async ({ page }) => {
  test.setTimeout(600000); // 10 minutes

  // === LOGIN ===
  await page.goto('https://hotel.tools/login');
  await page.waitForTimeout(2000);
  await page.locator('input[name="account"]').fill('Medici LIVE');
  await page.locator('input[name="agent"]').fill('zvi');
  await page.locator('input[name="password"]').fill('karpad66');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(5000);
  console.log('Logged in');

  const results = [];

  for (const venue of FAILING_VENUES) {
    console.log(`\n=== Processing venue ${venue.id}: ${venue.name} ===`);

    // Navigate to venue edit page
    await page.goto(`https://hotel.tools/venues/${venue.id}/edit`, { timeout: 15000 });
    await page.waitForTimeout(2000);

    // Check current value of connected_to_supplier
    const currentVal = await page.evaluate(() => {
      const sel = document.querySelector('select[name="connected_to_supplier"]');
      if (!sel) return { found: false };
      return {
        found: true,
        value: sel.value,
        options: Array.from(sel.options).map(o => ({ value: o.value, text: o.text })),
      };
    });

    if (!currentVal.found) {
      console.log(`  ERROR: connected_to_supplier SELECT not found`);
      results.push({ id: venue.id, name: venue.name, status: 'ERROR', detail: 'select not found' });
      continue;
    }

    console.log(`  Current value: "${currentVal.value}"`);
    console.log(`  Options: ${currentVal.options.map(o => `"${o.value}"`).join(', ')}`);

    if (currentVal.value === 'Medici') {
      console.log(`  ALREADY SET — skipping`);
      results.push({ id: venue.id, name: venue.name, status: 'ALREADY_SET', detail: 'Medici' });
      continue;
    }

    // Check if "Medici" is in the options
    const hasMediciOption = currentVal.options.some(o => o.value === 'Medici');
    if (!hasMediciOption) {
      console.log(`  ERROR: "Medici" not in dropdown options`);
      results.push({ id: venue.id, name: venue.name, status: 'ERROR', detail: 'no Medici option' });
      continue;
    }

    // Set the value to "Medici"
    await page.selectOption('select[name="connected_to_supplier"]', 'Medici');
    await page.waitForTimeout(500);

    // Verify it was set
    const newVal = await page.evaluate(() => {
      const sel = document.querySelector('select[name="connected_to_supplier"]');
      return sel ? sel.value : null;
    });
    console.log(`  Set to: "${newVal}"`);

    // Click the Submit button (button[type="submit"])
    const submitBtn = page.locator('form button[type="submit"]').first();
    if (await submitBtn.count() === 0) {
      console.log('  ERROR: No submit button found');
      results.push({ id: venue.id, name: venue.name, status: 'ERROR', detail: 'no submit button' });
      continue;
    }

    console.log('  Clicking Submit...');
    await Promise.all([
      page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}),
      submitBtn.click(),
    ]);
    await page.waitForTimeout(3000);

    // Verify by reloading the page and checking the value
    await page.goto(`https://hotel.tools/venues/${venue.id}/edit`, { timeout: 15000 });
    await page.waitForTimeout(2000);

    const verifyVal = await page.evaluate(() => {
      const sel = document.querySelector('select[name="connected_to_supplier"]');
      return sel ? sel.value : null;
    });
    console.log(`  After save, value is: "${verifyVal}"`);

    if (verifyVal === 'Medici') {
      console.log(`  SUCCESS!`);
      results.push({ id: venue.id, name: venue.name, status: 'FIXED', detail: `was "${currentVal.value}" -> "Medici"` });
    } else {
      console.log(`  FAILED — value did not persist`);
      results.push({ id: venue.id, name: venue.name, status: 'FAILED', detail: `still "${verifyVal}"` });
    }
  }

  // === SUMMARY ===
  console.log('\n\n========== SUMMARY ==========');
  const fixed = results.filter(r => r.status === 'FIXED');
  const already = results.filter(r => r.status === 'ALREADY_SET');
  const failed = results.filter(r => r.status === 'FAILED');
  const errors = results.filter(r => r.status === 'ERROR');

  console.log(`Fixed: ${fixed.length}`);
  fixed.forEach(r => console.log(`  ${r.id} ${r.name}: ${r.detail}`));
  console.log(`Already set: ${already.length}`);
  already.forEach(r => console.log(`  ${r.id} ${r.name}`));
  console.log(`Failed: ${failed.length}`);
  failed.forEach(r => console.log(`  ${r.id} ${r.name}: ${r.detail}`));
  console.log(`Errors: ${errors.length}`);
  errors.forEach(r => console.log(`  ${r.id} ${r.name}: ${r.detail}`));
  console.log(`\nTotal: ${results.length} / ${FAILING_VENUES.length}`);
});
