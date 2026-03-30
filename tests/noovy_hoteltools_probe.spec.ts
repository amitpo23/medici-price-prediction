import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const REPORT_DIR = path.join(process.cwd(), 'data', 'reports');
const NOOVY_USER = 'zvi';
const NOOVY_PASSWORD = 'karpad66';
const NOOVY_ACCOUNT = 'Medici LIVE';
const TARGET_HOTEL = 'Savoy Hotel';
const TARGET_VENUE = '196';

async function ensureReportDir() {
  await fs.mkdir(REPORT_DIR, { recursive: true });
}

async function collectNoovyDiagnostics(page: import('@playwright/test').Page, report: Record<string, unknown>) {
  const buttons = await page.locator('button').evaluateAll((elements) =>
    elements
      .map((element) => (element.textContent || '').trim())
      .filter(Boolean)
      .slice(0, 20)
  );
  const inputs = await page.locator('input').evaluateAll((elements) =>
    elements
      .map((element) => ({
        placeholder: element.getAttribute('placeholder') || '',
        type: element.getAttribute('type') || '',
        value: (element as HTMLInputElement).value || '',
      }))
      .slice(0, 20)
  );
  const selects = await page.locator('select').evaluateAll((elements) =>
    elements
      .map((element) => ({
        name: element.getAttribute('name') || '',
        value: (element as HTMLSelectElement).value || '',
      }))
      .slice(0, 20)
  );

  report.noovyDiagnostics = {
    buttons,
    inputs,
    selects,
  };
}

async function selectNoovyVenue(page: import('@playwright/test').Page, report: Record<string, unknown>) {
  const pushFinding = (message: string) => {
    const findings = report.findings as string[];
    findings.push(message);
  };

  const pushError = (message: string) => {
    const errors = report.errors as string[];
    errors.push(message);
  };

  const menuButton = page.locator('button').filter({ has: page.locator('svg') }).first();
  if (await menuButton.isVisible().catch(() => false)) {
    await menuButton.click().catch(() => {});
  }

  const openButton = page.getByRole('button', { name: /open/i }).last();
  if (!(await openButton.isVisible().catch(() => false))) {
    pushError('Could not find hotel venue selector open button in Noovy');
    return;
  }

  await openButton.click();
  const searchInput = page.locator('input').nth(3);
  if (await searchInput.isVisible().catch(() => false)) {
    await searchInput.fill(`${TARGET_HOTEL} #${TARGET_VENUE}`).catch(async () => {
      await searchInput.fill(TARGET_HOTEL);
    });
  }

  const venueOption = page.getByText(new RegExp(`${TARGET_HOTEL}.*${TARGET_VENUE}`, 'i')).first();
  if (!(await venueOption.isVisible().catch(() => false))) {
    const fallbackOption = page.getByText(new RegExp(TARGET_HOTEL, 'i')).first();
    if (await fallbackOption.isVisible().catch(() => false)) {
      await fallbackOption.click();
      pushFinding(`Selected Noovy venue using fallback hotel match for ${TARGET_HOTEL}`);
      return;
    }
    pushError(`Could not find Noovy venue option for ${TARGET_HOTEL} #${TARGET_VENUE}`);
    return;
  }

  await venueOption.click();
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  pushFinding(`Selected Noovy venue ${TARGET_HOTEL} #${TARGET_VENUE}`);
}

async function loginHotelTools(page: import('@playwright/test').Page, report: Record<string, unknown>) {
  const pushFinding = (message: string) => {
    const findings = report.findings as string[];
    findings.push(message);
  };

  const accountInput = page.getByPlaceholder(/account name/i).or(page.locator('input').nth(0));
  const userInput = page.getByPlaceholder(/agent name/i).or(page.locator('input').nth(1));
  const passwordInput = page.getByPlaceholder(/password/i).or(page.locator('input[type="password"]'));

  if (await accountInput.isVisible().catch(() => false)) {
    await accountInput.fill(NOOVY_ACCOUNT);
  }
  if (await userInput.isVisible().catch(() => false)) {
    await userInput.fill(NOOVY_USER);
  }
  if (await passwordInput.isVisible().catch(() => false)) {
    await passwordInput.fill(NOOVY_PASSWORD);
  }

  const loginButton = page.getByRole('button', { name: /login/i });
  if (await loginButton.isVisible().catch(() => false)) {
    await loginButton.click();
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
    pushFinding('Submitted direct Hotel.Tools login');
  }
}

test('probe noovy and hotel.tools product setup for Savoy 5103', async ({ page, context }) => {
  test.setTimeout(180_000);
  await ensureReportDir();

  const report: Record<string, unknown> = {
    startedAt: new Date().toISOString(),
    noovyLogin: null,
    hotelToolsAccess: null,
    findings: [],
    errors: [],
  };

  const pushFinding = (message: string) => {
    const findings = report.findings as string[];
    findings.push(message);
  };

  const pushError = (message: string) => {
    const errors = report.errors as string[];
    errors.push(message);
  };

  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('hotel.tools')) {
      return;
    }
    if (response.status() >= 500) {
      pushError(`HTTP ${response.status()} ${url}`);
    }
  });

  try {
    await page.goto('https://app.noovy.com', { waitUntil: 'domcontentloaded' });
    await page.screenshot({ path: path.join(REPORT_DIR, 'noovy-login-start.png'), fullPage: true });

    const accountInput = page.getByRole('textbox').nth(0);
    const userInput = page.getByRole('textbox').nth(1);
    const passwordInput = page.getByRole('textbox').nth(2).or(page.locator('input[type="password"]'));

    await accountInput.fill(NOOVY_ACCOUNT);
    await userInput.fill(NOOVY_USER);
    await page.locator('input[type="password"]').fill(NOOVY_PASSWORD);
    await page.getByRole('button', { name: /login/i }).click();
    await page.waitForLoadState('networkidle', { timeout: 60_000 });
    await collectNoovyDiagnostics(page, report);
    await selectNoovyVenue(page, report);
    await page.screenshot({ path: path.join(REPORT_DIR, 'noovy-after-login.png'), fullPage: true });

    report.noovyLogin = {
      url: page.url(),
      title: await page.title(),
    };
    pushFinding(`Noovy login landed on ${page.url()}`);

    const bodyText = await page.locator('body').innerText();
    if (/No Venue/i.test(bodyText)) {
      pushError('Noovy session has no active venue context');
    }

    await page.goto('https://hotel.tools', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 60_000 });
    await loginHotelTools(page, report);
    await page.screenshot({ path: path.join(REPORT_DIR, 'hoteltools-home.png'), fullPage: true });

    report.hotelToolsAccess = {
      url: page.url(),
      title: await page.title(),
    };
    pushFinding(`Hotel.Tools landing URL: ${page.url()}`);

    const hotelToolsText = await page.locator('body').innerText();
    if (/login/i.test(hotelToolsText) && /password/i.test(hotelToolsText)) {
      pushFinding('Hotel.Tools appears to require separate login or session did not carry over');
    }

    await page.goto('https://hotel.tools/products', { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
    await page.screenshot({ path: path.join(REPORT_DIR, 'hoteltools-products.png'), fullPage: true });
    pushFinding(`Hotel.Tools products URL after login attempt: ${page.url()}`);

    const storageStatePath = path.join(REPORT_DIR, 'noovy-hoteltools-storage-state.json');
    await context.storageState({ path: storageStatePath });
    pushFinding(`Saved storage state to ${storageStatePath}`);
  } catch (error) {
    pushError(error instanceof Error ? error.message : String(error));
    await page.screenshot({ path: path.join(REPORT_DIR, 'noovy-hoteltools-probe-error.png'), fullPage: true });
    throw error;
  } finally {
    report.finishedAt = new Date().toISOString();
    const reportPath = path.join(REPORT_DIR, `noovy_hoteltools_probe_${Date.now()}.json`);
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8');
  }
});