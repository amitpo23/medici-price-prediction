#!/usr/bin/env node
// Debug: check what Innstant B2B returns for one hotel
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');

const CHROME_PATH = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PROJECT_ROOT = path.join(__dirname, '..');

(async () => {
    const browser = await chromium.launch({
        headless: true,
        executablePath: CHROME_PATH,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport: { width: 1280, height: 800 },
        ignoreHTTPSErrors: true,
    });

    // Load cookies
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    if (fs.existsSync(cookiePath)) {
        const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
        await context.addCookies(cookies);
        console.log('Loaded cookies:', cookies.length);
    }

    const page = await context.newPage();

    // First check if we're still logged in
    await page.goto('https://b2b.innstant.travel', { timeout: 30000 });
    await page.waitForTimeout(4000);
    const homeUrl = page.url();
    console.log('Home URL:', homeUrl);
    const homeTitle = await page.title();
    console.log('Home title:', homeTitle);

    if (homeUrl.includes('/login') || homeUrl.includes('/agent/login')) {
        console.log('SESSION EXPIRED - need to re-login');

        // Try login with default creds
        await page.fill('input[name="AccountName"]', 'Knowaa').catch(() => {});
        await page.fill('input[name="Username"]', 'Amit').catch(() => {});
        await page.evaluate(() => {
            const el = document.querySelector('input[name="Password"]');
            if (el) { el.removeAttribute('readonly'); el.removeAttribute('disabled'); }
        });
        await page.fill('input[name="Password"]', 'porat10').catch(() => {});
        await page.click('button[type="submit"]').catch(() => {});
        await page.waitForTimeout(6000);
        console.log('After login URL:', page.url());
    } else {
        console.log('Already authenticated');
    }

    // Test the claude_scan.js URL
    const urlClaude = 'https://b2b.innstant.travel/hotel/atwell-suites-miami-brickell-853382?service=hotels&searchQuery=hotel-853382&startDate=2026-06-01&endDate=2026-06-02&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=';
    // Test the SKILL.md URL pattern
    const urlSkill = 'https://b2b.innstant.travel/hotel/atwell-suites-miami-brickell-853382?searchQuery=hotel-853382&startDate=2026-06-01&endDate=2026-06-02&account-country=US&adults=2';

    for (const [label, url] of [['claude_scan URL', urlClaude], ['SKILL URL', urlSkill]]) {
        console.log('\n--- Testing:', label, '---');
        console.log('URL:', url);
        await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(8000);
        console.log('Current URL:', page.url());
        console.log('Title:', await page.title());

        const selectors = ['.search-result-item', '.hotel-offer', '.room-item', '[data-offer]', '.offer-row', '.rate-row', '.search-results'];
        for (const sel of selectors) {
            const els = await page.$$(sel);
            if (els.length > 0) console.log(`  FOUND ${sel}: ${els.length} elements`);
        }

        // Get all class names on the page
        const classes = await page.evaluate(() => {
            const all = document.querySelectorAll('[class]');
            const cls = new Set();
            all.forEach(el => el.className.split(' ').forEach(c => { if (c && c.length > 3) cls.add(c); }));
            return [...cls].slice(0, 50);
        });
        console.log('  Classes on page:', classes.join(', '));

        const body = await page.evaluate(() => document.body.innerText.slice(0, 600));
        console.log('  Body:', body.replace(/\n+/g, ' | '));
    }

    await browser.close();
})().catch(e => {
    console.error('FATAL:', e.message);
    process.exit(1);
});
