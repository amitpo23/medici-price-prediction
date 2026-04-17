#!/usr/bin/env node
/**
 * Login + scan — fresh login before scanning all 42 Miami hotels.
 * Run: node scripts/login_and_scan.js
 */

const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const { execSync } = require('child_process');

const CHROME_PATH = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PROJECT_ROOT = path.join(__dirname, '..');
const SCAN_REPORTS = path.join(PROJECT_ROOT, 'scan-reports');
const SHARED_REPORTS = path.join(PROJECT_ROOT, 'shared-reports');

const INNSTANT = {
    user: process.env.INNSTANT_USER || 'Amit',
    pass: process.env.INNSTANT_PASS || 'porat10',
    account: process.env.INNSTANT_ACCOUNT || 'Knowaa',
    baseUrl: 'https://b2b.innstant.travel',
};

const HOTEL_TIMEOUT = 25000;
const SETTLE_DELAY = 4000;
const MAX_RETRIES = 3;

function log(msg) {
    console.log(`[${new Date().toISOString().slice(11,19)}] ${msg}`);
}

function slugify(name) {
    return name.toLowerCase().replace(/['']/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
}

function buildUrl(hotel) {
    const slug = `${slugify(hotel.name)}-${hotel.InnstantId}`;
    const dateFrom = hotel.DateFrom.split('T')[0];
    const dateTo = hotel.DateTo.split('T')[0];
    // Use simpler URL without payAtTheHotel filter (get all refundable offers, filter in JS)
    return `${INNSTANT.baseUrl}/hotel/${slug}?service=hotels&searchQuery=hotel-${hotel.InnstantId}&startDate=${dateFrom}&endDate=${dateTo}&account-country=US&adults=2`;
}

function loadHotels() {
    const files = fs.readdirSync(SCAN_REPORTS)
        .filter(f => f.endsWith('_full_scan.json') && !f.includes('2026-04-17_08-26'))
        .sort().reverse();
    if (!files.length) throw new Error('No scan JSON found');
    const latest = path.join(SCAN_REPORTS, files[0]);
    log(`Hotel list from: ${files[0]}`);
    const data = JSON.parse(fs.readFileSync(latest, 'utf8'));
    const seen = new Set();
    const hotels = [];
    for (const h of data.hotels) {
        if (!seen.has(h.hotelId) && h.venueId >= 5000) {
            seen.add(h.hotelId);
            hotels.push({
                InnstantId: h.hotelId,
                VenueId: h.venueId,
                name: h.name,
                DateFrom: data.searchDates.checkIn,
                DateTo: data.searchDates.checkOut,
            });
        }
    }
    log(`Loaded ${hotels.length} unique hotels`);
    return hotels;
}

// EXTRACT_FN — runs inside browser page
const EXTRACT_FN = () => {
    const items = document.querySelectorAll('.search-result-item');
    const offers = [];
    items.forEach(item => {
        const catEl = item.querySelector('.small-4,.medium-3,.room-category,.category-name');
        const cat = catEl ? catEl.textContent.trim().split('\n')[0].trim() : '?';
        item.querySelectorAll('.search-result-item-sub-section').forEach(section => {
            const text = section.textContent || '';
            if (/non-refundable/i.test(text)) return;
            const provLabel = section.querySelector('.provider-label');
            const provider = provLabel ? provLabel.textContent.trim() : '?';
            const priceEl = section.querySelector('h4');
            const price = priceEl ? parseFloat(priceEl.textContent.replace(/[$,\s]/g,'')) : null;
            const board = /BB|breakfast/i.test(text) ? 'BB' : 'RO';
            if (price && price > 0) offers.push({ cat, board, price, provider });
        });
    });
    const knowaa = offers.filter(o => o.provider && o.provider.includes('Knowaa'));
    const cheapest = offers.length ? Math.min(...offers.map(o => o.price)) : null;
    const kCheapest = knowaa.length ? Math.min(...knowaa.map(o => o.price)) : null;
    const byProv = {};
    offers.forEach(o => { if (!byProv[o.provider] || o.price < byProv[o.provider]) byProv[o.provider] = o.price; });
    const provMinPrices = Object.values(byProv).sort((a,b) => a-b);
    const rank = kCheapest !== null ? provMinPrices.filter(p => p < kCheapest).length + 1 : null;
    return {
        total: offers.length,
        knowaa: knowaa.length > 0,
        kCnt: knowaa.length,
        cheap: cheapest,
        kCheap: kCheapest,
        is1st: kCheapest !== null && rank === 1,
        rank,
        provs: [...new Set(offers.map(o => o.provider))],
        cats: [...new Set(offers.map(o => o.cat))],
        boards: [...new Set(offers.map(o => o.board))],
        byProv,
        allOffers: offers.map(o => ({ category: o.cat, board: o.board, price: o.price, provider: o.provider })),
    };
};

async function login(page) {
    log('Navigating to Innstant B2B login...');
    await page.goto(`${INNSTANT.baseUrl}/agent/login`, { timeout: 30000 });
    await page.waitForTimeout(3000);

    // Fill login form
    await page.fill('input[name="AccountName"]', INNSTANT.account);
    await page.fill('input[name="Username"]', INNSTANT.user);
    await page.evaluate(() => {
        const el = document.querySelector('input[name="Password"]');
        if (el) { el.removeAttribute('readonly'); el.removeAttribute('disabled'); }
    });
    await page.fill('input[name="Password"]', INNSTANT.pass);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(7000);

    const postUrl = page.url();
    if (postUrl.includes('/login')) {
        const body = await page.evaluate(() => document.body.innerText.slice(0, 300));
        throw new Error(`Login failed. URL: ${postUrl} | Body: ${body}`);
    }
    log(`Login successful. URL: ${postUrl}`);

    // Save cookies
    const cookies = await page.context().cookies();
    const innstantCookies = cookies.filter(c => c.domain && c.domain.includes('innstant'));
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    fs.writeFileSync(cookiePath, JSON.stringify(innstantCookies, null, 2));
    log(`Saved ${innstantCookies.length} cookies`);
}

async function scanHotel(page, hotel) {
    const url = buildUrl(hotel);
    await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    // Innstant B2B hotel page requires clicking "Show Rooms" / search trigger
    // to load room offers — URL params alone do not auto-submit the search
    const alreadyHasResults = await page.$('.search-result-item');
    if (!alreadyHasResults) {
        try {
            // Try the call-to-action anchor (Show Rooms link on hotel page)
            const trigger = await page.$('.call-to-action a, a.call-to-action, button.call-to-action');
            if (trigger) {
                await trigger.click();
                await page.waitForTimeout(2000);
            } else {
                // Fallback: click any visible "Show Rooms" or "Search" text
                await page.click('text=Show Rooms', { timeout: 3000 }).catch(() => {});
            }
        } catch { /* no trigger found, proceed anyway */ }
    }

    try {
        await page.waitForSelector('.search-result-item', { timeout: HOTEL_TIMEOUT });
        await page.waitForTimeout(SETTLE_DELAY);
    } catch {
        return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, total: 0, knowaa: false, kCnt: 0, cheap: null, kCheap: null, is1st: false, rank: null, provs: [], cats: [], boards: [], byProv: {}, allOffers: [] };
    }
    const data = await page.evaluate(EXTRACT_FN);
    return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, ...data };
}

function pct(n, total) { return total ? `${Math.round(n/total*100)}%` : '0%'; }

function buildReport(results, scanDate, scanTime, checkIn, checkOut) {
    const n = results.length;
    const sA = results.filter(r => r.is1st);
    const sB = results.filter(r => r.knowaa && !r.is1st && r.rank === 2);
    const sC_plus = results.filter(r => r.knowaa && !r.is1st && r.rank > 2);
    const sD = results.filter(r => !r.knowaa && r.total > 0);
    const sE = results.filter(r => r.total === 0);

    const knowaaAppears = results.filter(r => r.knowaa).length;
    const knowaaFirst = sA.length;
    const notListed = sD.length;
    const noOffers = sE.length;

    // Load previous for comparison
    let prev = null;
    try {
        const files = fs.readdirSync(SCAN_REPORTS).filter(f => f.endsWith('_full_scan.json') && !f.includes('2026-04-17_08-26')).sort().reverse();
        if (files.length) prev = JSON.parse(fs.readFileSync(path.join(SCAN_REPORTS, files[0]), 'utf8')).summary;
    } catch {}

    const delta = (cur, old, field) => {
        if (!old) return '';
        const d = cur - old[field];
        return d === 0 ? ' → same' : d > 0 ? ` ↑ +${d}` : ` ↓ ${d}`;
    };

    let md = `# Knowaa Competitive Intelligence Report — ${scanDate}_${scanTime}\n\n`;
    md += `**Scan Date:** ${scanDate} ${scanTime} UTC  \n`;
    md += `**Check-in:** ${checkIn} → **Check-out:** ${checkOut} (1 night)  \n`;
    md += `**Provider:** Knowaa_Global_zenith  \n`;
    md += `**Filter:** Refundable offers only | All room types | RO + BB boards  \n`;
    md += `**Source:** Live browser scan via Innstant B2B (fresh login)  \n`;
    md += prev ? `**Compared to:** Previous scan summary (knowaaAppears=${prev.knowaaAppears}, #1=${prev.knowaaFirst})  \n` : '';
    md += `\n---\n\n## Executive Summary\n\n`;
    md += `| Metric | Current | Previous | Δ |\n|--------|---------|----------|---|\n`;
    md += `| Total Hotels Scanned | ${n} | ${prev ? n : '-'} | - |\n`;
    md += `| **Knowaa #1 (cheapest)** | **${knowaaFirst} (${pct(knowaaFirst,n)})** | ${prev ? prev.knowaaFirst : '-'} | **${delta(knowaaFirst, prev, 'knowaaFirst')}** |\n`;
    md += `| Knowaa #2 | ${sB.length} (${pct(sB.length,n)}) | - | - |\n`;
    md += `| Knowaa #3+ (listed, not top) | ${sC_plus.length} (${pct(sC_plus.length,n)}) | - | - |\n`;
    md += `| Hotels with offers, no Knowaa | ${notListed} (${pct(notListed,n)}) | ${prev ? prev.notListed : '-'} | ${delta(notListed, prev, 'notListed')} |\n`;
    md += `| No refundable offers | ${noOffers} (${pct(noOffers,n)}) | ${prev ? prev.noOffers : '-'} | ${delta(noOffers, prev, 'noOffers')} |\n\n---\n\n`;

    // Section A
    md += `## Section A — Knowaa is #1 (Cheapest) ✅\n\n`;
    if (sA.length) {
        md += `*${sA.length} hotel(s) where Knowaa_Global_zenith is the cheapest refundable provider.*\n\n`;
        md += `| Hotel | Venue ID | Our Price | 2nd Cheapest | Gap | Providers |\n|-------|----------|-----------|--------------|-----|----------|\n`;
        for (const r of sA) {
            const others = Object.entries(r.byProv).filter(([p]) => !p.includes('Knowaa')).sort((a,b) => a[1]-b[1]);
            const second = others[0];
            md += `| ${r.hotel} | ${r.v} | **$${r.kCheap.toFixed(2)}** | ${second ? '$'+second[1].toFixed(2) : '-'} | ${second ? '-$'+(second[1]-r.kCheap).toFixed(2) : '-'} | ${r.provs.join(', ')} |\n`;
        }
    } else {
        md += `*No hotels where Knowaa is cheapest.*\n`;
    }
    md += '\n---\n\n';

    // Section B
    md += `## Section B — Knowaa is #2 ⚠️\n\n`;
    if (sB.length) {
        md += `*${sB.length} hotel(s) where Knowaa is ranked #2.*\n\n`;
        md += `| Hotel | Venue ID | Our Price | Cheapest | Cheapest Provider | Gap $ | Gap % |\n|-------|----------|-----------|----------|-------------------|-------|-------|\n`;
        for (const r of sB) {
            const cheapProv = Object.entries(r.byProv).sort((a,b) => a[1]-b[1])[0];
            const gap = r.kCheap - r.cheap;
            const gapPct = (gap / r.cheap * 100).toFixed(1);
            md += `| ${r.hotel} | ${r.v} | $${r.kCheap.toFixed(2)} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | +$${gap.toFixed(2)} | +${gapPct}% |\n`;
        }
    } else {
        md += `*No hotels where Knowaa is ranked #2.*\n`;
    }
    md += '\n---\n\n';

    // Section C
    md += `## Section C — Knowaa is #3+ (Listed but Not Competitive) 🔴\n\n`;
    if (sC_plus.length) {
        md += `*${sC_plus.length} hotel(s) where Knowaa is listed but ranked 3rd or lower.*\n\n`;
        md += `| Hotel | Venue ID | Our Price | Cheapest | Rank | Gap $ | Gap % | Cheapest Provider |\n|-------|----------|-----------|----------|------|-------|-------|------------------|\n`;
        for (const r of sC_plus) {
            const cheapProv = Object.entries(r.byProv).sort((a,b) => a[1]-b[1])[0];
            const gap = r.kCheap - r.cheap;
            const gapPct = (gap / r.cheap * 100).toFixed(1);
            md += `| ${r.hotel} | ${r.v} | $${r.kCheap.toFixed(2)} | $${r.cheap.toFixed(2)} | #${r.rank} | +$${gap.toFixed(2)} | +${gapPct}% | ${cheapProv ? cheapProv[0] : '-'} |\n`;
        }
    } else {
        md += `*No hotels in this category.*\n`;
    }
    md += '\n---\n\n';

    // Section D
    md += `## Section D — Hotels with Offers but NO Knowaa 🚫\n\n`;
    if (sD.length) {
        md += `*${sD.length} hotel(s) have refundable offers available but Knowaa_Global_zenith is absent.*\n\n`;
        md += `| Hotel | Venue ID | Cheapest Price | Cheapest Provider | All Providers |\n|-------|----------|---------------|-------------------|---------------|\n`;
        for (const r of sD) {
            const cheapProv = Object.entries(r.byProv).sort((a,b) => a[1]-b[1])[0];
            md += `| ${r.hotel} | ${r.v} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | ${r.provs.join(', ')} |\n`;
        }
    } else {
        md += `*All active hotels have Knowaa listed.*\n`;
    }
    md += '\n---\n\n';

    // Section E
    md += `## Section E — No Refundable Offers 🚫\n\n`;
    if (sE.length) {
        md += `*${sE.length} hotel(s) with zero refundable offers from any provider.*\n\n`;
        md += `| Hotel | Venue ID |\n|-------|----------|\n`;
        for (const r of sE) {
            md += `| ${r.hotel} | ${r.v} |\n`;
        }
    } else {
        md += `*All active hotels have at least some refundable offers.*\n`;
    }
    md += '\n---\n\n';

    // Sentinel flags
    const sentinels = results.filter(r => r.kCheap && r.kCheap >= 500);
    if (sentinels.length) {
        md += `## Notes & Flags\n\n### ⚠️ Sentinel Prices Detected\n\n`;
        md += `Hotels with Knowaa price ≥ $500 may have placeholder/sentinel pricing:\n\n`;
        md += `| Hotel | Venue ID | Knowaa Price |\n|-------|----------|--------------|\n`;
        for (const r of sentinels) {
            md += `| ${r.hotel} | ${r.v} | $${r.kCheap.toFixed(2)} |\n`;
        }
        md += '\n';
    }

    return { md, summary: { knowaaAppears, knowaaFirst, notListed, noOffers } };
}

async function main() {
    log('=== Knowaa Login + Scan (fresh session) ===');

    const hotels = loadHotels();

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
    const page = await context.newPage();

    // Fresh login
    await login(page);

    // Scan all hotels with crash recovery
    const results = [];
    for (let i = 0; i < hotels.length; i++) {
        const hotel = hotels[i];
        let retries = 0, done = false;
        while (retries < MAX_RETRIES && !done) {
            try {
                const r = await scanHotel(page, hotel);
                results.push(r);
                const status = r.knowaa ? (r.is1st ? `#1 ($${r.kCheap.toFixed(2)})` : `#${r.rank} ($${r.kCheap.toFixed(2)} vs $${r.cheap.toFixed(2)})`) : (r.total > 0 ? `NOT LISTED (${r.total} offers)` : 'NO OFFERS');
                log(`  [${String(i+1).padStart(2)}/${hotels.length}] ${hotel.name}: ${status}`);
                done = true;
            } catch (err) {
                retries++;
                log(`  ERROR ${hotel.name} (attempt ${retries}): ${err.message.slice(0,80)}`);
                if (retries < MAX_RETRIES) {
                    log('  Re-logging in...');
                    try { await login(page); } catch { /* ignore */ }
                }
            }
        }
        if (!done) {
            results.push({ id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, total: 0, knowaa: false, kCnt: 0, cheap: null, kCheap: null, is1st: false, rank: null, provs: [], cats: [], boards: [], byProv: {}, allOffers: [], error: 'scan_failed' });
            log(`  SKIPPED ${hotel.name} after ${MAX_RETRIES} attempts`);
        }
        if ((i+1) % 10 === 0) log(`--- Progress: ${i+1}/${hotels.length} ---`);
    }

    await browser.close();
    log(`Scan complete: ${results.length} hotels, ${results.filter(r => r.error).length} failed`);

    // Build reports
    const now = new Date();
    const scanDate = now.toISOString().split('T')[0];
    const scanTime = now.toISOString().split('T')[1].slice(0,8).replace(/:/g,'-');
    const ts = `${scanDate}_${scanTime.slice(0,5)}`;
    const checkIn = hotels[0].DateFrom.split('T')[0];
    const checkOut = hotels[0].DateTo.split('T')[0];

    const { md, summary } = buildReport(results, scanDate, scanTime.replace(/-/g,':'), checkIn, checkOut);

    const jsonReport = {
        scanDate, scanTime: scanTime.replace(/-/g,':'),
        searchDates: { checkIn, checkOut },
        source: 'innstant_b2b_browser_fresh_login',
        totalHotelsScanned: results.length,
        summary,
        hotels: results.map(r => ({
            hotelId: r.id, venueId: r.v, name: r.hotel,
            knowaaPresent: r.knowaa, knowaaIsCheapest: r.is1st,
            knowaaRank: r.rank, knowaaPrice: r.kCheap, cheapestPrice: r.cheap,
            cheapestProvider: r.total > 0 ? Object.entries(r.byProv).sort((a,b)=>a[1]-b[1])[0]?.[0] : null,
            categories: r.cats, boards: r.boards, providers: r.provs,
            offers: r.allOffers || [], error: r.error || null,
        })),
    };

    for (const dir of [SCAN_REPORTS, SHARED_REPORTS]) {
        fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(path.join(dir, `${ts}_full_scan.json`), JSON.stringify(jsonReport, null, 2));
        fs.writeFileSync(path.join(dir, `${scanDate}_full_${results.length}_hotels_report.md`), md);
        fs.writeFileSync(path.join(dir, `${scanDate}_knowaa_competitive_report.md`), md);
    }
    log(`Saved reports: ${ts}_full_scan.json`);

    // Git push
    try {
        execSync('git add scan-reports/ shared-reports/', { cwd: PROJECT_ROOT, stdio: 'pipe' });
        execSync(`git commit -m "chore: scheduled browser-price-check scan ${scanDate}"`, { cwd: PROJECT_ROOT, stdio: 'pipe' });
        execSync('git push -u origin main', { cwd: PROJECT_ROOT, stdio: 'pipe' });
        log('Committed and pushed to GitHub');
    } catch (err) {
        log('Git warning: ' + (err.stdout?.toString() || err.stderr?.toString() || err.message).slice(0, 200));
    }

    log('=== FINAL SUMMARY ===');
    log(`Hotels: ${results.length} | Knowaa appears: ${summary.knowaaAppears} | #1: ${summary.knowaaFirst} | Not listed: ${summary.notListed} | No offers: ${summary.noOffers}`);
    log('=== DONE ===');
}

main().catch(err => { console.error('FATAL:', err.message); process.exit(1); });
