#!/usr/bin/env node
// Test: navigate hotel page → click Show Rooms → capture results
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const CHROME_PATH = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PROJECT_ROOT = path.join(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: CHROME_PATH, args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'] });
    const context = await browser.newContext({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', viewport:{width:1280,height:900}, ignoreHTTPSErrors:true });

    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
    await context.addCookies(cookies);

    const page = await context.newPage();
    const url = 'https://b2b.innstant.travel/hotel/atwell-suites-miami-brickell-853382?service=hotels&searchQuery=hotel-853382&startDate=2026-06-01&endDate=2026-06-02&account-country=US&adults=2';

    console.log('Navigating...');
    await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    console.log('URL:', page.url());

    // Find all links/buttons with "Show Rooms" or "Search" text
    const buttons = await page.evaluate(() => {
        const results = [];
        document.querySelectorAll('a, button, [role=button], input[type=submit], .call-to-action').forEach(el => {
            const txt = el.textContent.trim().slice(0, 50);
            if (txt) results.push({ tag: el.tagName, class: el.className.slice(0,80), text: txt, href: el.href || '' });
        });
        return results.filter(r => /show|search|room|result|book|avail/i.test(r.text));
    });
    console.log('Clickable elements:', JSON.stringify(buttons, null, 2));

    // Try clicking the Show Rooms / search trigger
    const showRooms = await page.$('a.call-to-action, .call-to-action a, a:has-text("Show Rooms"), button:has-text("Show Rooms"), [href*="searchQuery"]');
    if (showRooms) {
        console.log('Found Show Rooms button, clicking...');
        await showRooms.click();
        await page.waitForTimeout(3000);
        console.log('After click URL:', page.url());
    } else {
        console.log('No Show Rooms button found by CSS selector, trying text click...');
        try {
            await page.click('text=Show Rooms', { timeout: 5000 });
            await page.waitForTimeout(3000);
            console.log('After text click URL:', page.url());
        } catch { console.log('Text click failed'); }
    }

    // Wait for results
    try {
        await page.waitForSelector('.search-result-item', { timeout: 20000 });
        const count = (await page.$$('.search-result-item')).length;
        console.log('search-result-item count:', count);

        const offers = await page.evaluate(() => {
            const items = document.querySelectorAll('.search-result-item');
            const out = [];
            items.forEach(item => {
                const cat = item.querySelector('.small-4,.medium-3')?.textContent.trim() || '?';
                item.querySelectorAll('.search-result-item-sub-section').forEach(section => {
                    const text = section.textContent || '';
                    if (/non-refundable/i.test(text)) return;
                    const prov = section.querySelector('.provider-label')?.textContent.trim() || '?';
                    const price = parseFloat(section.querySelector('h4')?.textContent.replace(/[$,\s]/g,'') || '0');
                    if (price > 0) out.push({ cat, prov, price });
                });
            });
            return out;
        });
        console.log('Offers found:', JSON.stringify(offers.slice(0,10), null, 2));
    } catch {
        console.log('No .search-result-item found after click');
        const body = await page.evaluate(() => document.body.innerText.slice(0, 500));
        console.log('Page body:', body.replace(/\n+/g,' | '));
    }

    await browser.close();
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
