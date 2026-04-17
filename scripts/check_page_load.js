#!/usr/bin/env node
// Quick check: does the hotel page load after fresh login, and what's on it?
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const CHROME_PATH = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PROJECT_ROOT = path.join(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: CHROME_PATH, args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'] });
    const context = await browser.newContext({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', viewport:{width:1280,height:800}, ignoreHTTPSErrors:true });

    // Load fresh cookies (just saved by login_and_scan.js)
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    const cookies = JSON.parse(fs.readFileSync(cookiePath,'utf8'));
    await context.addCookies(cookies);
    console.log('Loaded', cookies.length, 'cookies');

    const page = await context.newPage();

    // Navigate to Atwell Suites hotel search page
    const url = 'https://b2b.innstant.travel/hotel/atwell-suites-miami-brickell-853382?service=hotels&searchQuery=hotel-853382&startDate=2026-06-01&endDate=2026-06-02&account-country=US&adults=2';
    console.log('Navigating to hotel page...');
    await page.goto(url, { timeout: 30000, waitUntil: 'networkidle' });
    console.log('Final URL:', page.url());
    console.log('Title:', await page.title());

    // Check for redirect to login
    if (page.url().includes('/login')) {
        console.log('REDIRECTED TO LOGIN — session invalid for hotel searches');
        await browser.close();
        return;
    }

    // Look for any content
    const body = await page.evaluate(() => document.body.innerText.slice(0, 800));
    console.log('Body snippet:', body.replace(/\n+/g,' | '));

    // Check various selectors
    for (const sel of ['.search-result-item', '[class*=result]', '[class*=offer]', '[class*=room]', '[class*=rate]', '.results-container', '#results', '.hotel-rooms', '.room-list']) {
        const n = await page.$$(sel);
        if (n.length) console.log(`FOUND "${sel}": ${n.length} elements`);
    }

    // Get all classes
    const allClasses = await page.evaluate(() => {
        const s = new Set();
        document.querySelectorAll('[class]').forEach(el => el.className.split(' ').forEach(c => { if (c && c.length>3 && c.length<40) s.add(c); }));
        return [...s].sort();
    });
    console.log('All classes:', allClasses.join(', '));

    await browser.close();
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
