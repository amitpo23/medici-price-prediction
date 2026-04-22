#!/usr/bin/env node
/**
 * Standalone browser scan using cached hotel list.
 * Used when Azure SQL (port 1433) is unreachable from this environment.
 * Hotel list is sourced from the most recent scan JSON in scan-reports/.
 *
 * Usage: node scripts/scan_cached.js [--no-push]
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const FLAGS = {
    noPush: process.argv.includes('--no-push'),
};

const PROJECT_ROOT = path.join(__dirname, '..');

const INNSTANT = {
    user: process.env.INNSTANT_USER || 'Amit',
    pass: process.env.INNSTANT_PASS || 'porat10',
    account: process.env.INNSTANT_ACCOUNT || 'Knowaa',
    baseUrl: 'https://b2b.innstant.travel',
};

const HOTEL_TIMEOUT = 18000;
const SETTLE_DELAY = 3000;
const MAX_RETRIES = 3;

function log(msg) {
    const ts = new Date().toISOString().slice(11, 19);
    console.log(`[${ts}] ${msg}`);
}

function pct(n, total) {
    return total ? `${Math.round(n / total * 100)}%` : '0%';
}

function slugify(name) {
    return name
        .toLowerCase()
        .replace(/['']/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
}

function formatDate(d) {
    if (typeof d === 'string') return d.split('T')[0];
    return d.toISOString().split('T')[0];
}

function buildUrl(hotel) {
    const slug = `${slugify(hotel.name)}-${hotel.InnstantId}`;
    const dateFrom = formatDate(hotel.DateFrom);
    const dateTo = formatDate(hotel.DateTo);
    return `${INNSTANT.baseUrl}/hotel/${slug}?service=hotels&searchQuery=hotel-${hotel.InnstantId}&startDate=${dateFrom}&endDate=${dateTo}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=`;
}

// ---------------------------------------------------------------------------
// Hotel list: load from most recent JSON scan
// ---------------------------------------------------------------------------
function loadCachedHotels() {
    const scanDir = path.join(PROJECT_ROOT, 'scan-reports');
    const jsons = fs.readdirSync(scanDir)
        .filter(f => f.endsWith('_full_scan.json'))
        .sort()
        .reverse();

    if (!jsons.length) throw new Error('No cached scan JSON found in scan-reports/');

    const latest = path.join(scanDir, jsons[0]);
    log(`Loading hotel list from cached scan: ${jsons[0]}`);
    const data = JSON.parse(fs.readFileSync(latest, 'utf8'));

    // Deduplicate by InnstantId — use one scan entry per unique hotel
    const seen = new Set();
    const hotels = [];
    for (const h of data.hotels) {
        if (!seen.has(h.hotelId)) {
            seen.add(h.hotelId);
            hotels.push({
                InnstantId: h.hotelId,
                name: h.name,
                VenueId: h.venueId,
                DateFrom: data.searchDates.checkIn,
                DateTo: data.searchDates.checkOut,
            });
        }
    }
    log(`Loaded ${hotels.length} unique hotels (from ${data.hotels.length} entries) — search dates: ${data.searchDates.checkIn} → ${data.searchDates.checkOut}`);
    return hotels;
}

// ---------------------------------------------------------------------------
// Extraction function — runs inside the browser page
// ---------------------------------------------------------------------------
const EXTRACT_FN = () => {
    const items = document.querySelectorAll('.search-result-item');
    const offers = [];
    items.forEach(item => {
        const catEl = item.querySelector('.small-4,.medium-3');
        const cat = catEl ? catEl.textContent.trim().split('\n')[0].trim() : '?';
        item.querySelectorAll('.search-result-item-sub-section').forEach(section => {
            const text = section.textContent || '';
            if (/non-refundable/i.test(text)) return;
            const provLabel = section.querySelector('.provider-label');
            const provider = provLabel ? provLabel.textContent.trim() : '?';
            const priceEl = section.querySelector('h4');
            const price = priceEl ? parseFloat(priceEl.textContent.replace(/[$,\s]/g, '')) : null;
            const board = /BB|breakfast/i.test(text) ? 'BB' : 'RO';
            if (price) offers.push({ cat, board, price, provider });
        });
    });

    const knowaa = offers.filter(o => o.provider.includes('Knowaa'));
    const cheapest = offers.length ? Math.min(...offers.map(o => o.price)) : null;
    const kCheapest = knowaa.length ? Math.min(...knowaa.map(o => o.price)) : null;
    const byProv = {};
    offers.forEach(o => {
        if (!byProv[o.provider] || o.price < byProv[o.provider]) byProv[o.provider] = o.price;
    });

    return {
        total: offers.length,
        knowaa: knowaa.length > 0,
        kCnt: knowaa.length,
        cheap: cheapest,
        kCheap: kCheapest,
        is1st: kCheapest !== null && kCheapest <= cheapest,
        rank: kCheapest ? offers.filter(o => o.price < kCheapest).length + 1 : null,
        provs: [...new Set(offers.map(o => o.provider))],
        cats: [...new Set(offers.map(o => o.cat))],
        boards: [...new Set(offers.map(o => o.board))],
        kOffers: knowaa.map(o => ({ cat: o.cat, b: o.board, p: o.price })),
        byProv,
        allOffers: offers.map(o => ({
            category: o.cat,
            board: o.board,
            price: o.price,
            provider: o.provider,
        })),
    };
};

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------
async function loginIfNeeded(page) {
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    if (fs.existsSync(cookiePath)) {
        log('Loading saved cookies...');
        const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
        await page.context().addCookies(cookies);
    }

    await page.goto(INNSTANT.baseUrl);
    await page.waitForTimeout(4000);
    const url = page.url();
    if (!url.includes('/login') && !url.includes('/agent/login')) {
        log('Authenticated via saved cookies');
        return;
    }

    log('Logging in with credentials...');
    await page.fill('input[name="AccountName"]', INNSTANT.account);
    await page.fill('input[name="Username"]', INNSTANT.user);
    await page.click('input[name="Password"]');
    await page.waitForTimeout(500);
    await page.evaluate(() => {
        const el = document.querySelector('input[name="Password"]');
        if (el) el.removeAttribute('readonly');
    });
    await page.fill('input[name="Password"]', INNSTANT.pass);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(6000);

    const postUrl = page.url();
    if (postUrl.includes('/login')) {
        throw new Error('Login failed — check INNSTANT_USER/INNSTANT_PASS/INNSTANT_ACCOUNT');
    }

    const freshCookies = await page.context().cookies();
    const innstantCookies = freshCookies.filter(c => c.domain.includes('innstant'));
    fs.writeFileSync(cookiePath, JSON.stringify(innstantCookies, null, 2));
    log('Logged in and saved fresh cookies');
}

async function launchBrowser() {
    const browser = await chromium.launch({ headless: true, args: ['--ignore-certificate-errors'] });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        viewport: { width: 1280, height: 800 },
        ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await loginIfNeeded(page);
    return { browser, context, page };
}

async function scanHotel(page, hotel) {
    const url = buildUrl(hotel);
    log(`  → ${url}`);
    await page.goto(url);
    try {
        await page.waitForSelector('.search-result-item', { timeout: HOTEL_TIMEOUT });
        await page.waitForTimeout(SETTLE_DELAY);
    } catch {
        return {
            id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name,
            total: 0, knowaa: false, kCnt: 0, cheap: null, kCheap: null,
            is1st: false, rank: null, provs: [], cats: [], boards: [],
            kOffers: [], byProv: {}, allOffers: [],
        };
    }
    const data = await page.evaluate(EXTRACT_FN);
    return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, ...data };
}

async function scanAllHotels(hotels) {
    log(`Launching browser — scanning ${hotels.length} hotels...`);
    let { browser, page } = await launchBrowser();
    const results = [];

    for (let i = 0; i < hotels.length; i++) {
        const hotel = hotels[i];
        let retries = 0;
        let scanned = false;

        while (retries < MAX_RETRIES && !scanned) {
            try {
                const result = await scanHotel(page, hotel);
                results.push(result);
                const status = result.knowaa
                    ? (result.is1st ? `#1 @ $${result.kCheap?.toFixed(2)}` : `#${result.rank} @ $${result.kCheap?.toFixed(2)}`)
                    : (result.total > 0 ? `NOT LISTED (${result.total} offers)` : 'NO OFFERS');
                log(`  ${hotel.name}: ${status}`);
                scanned = true;
            } catch (err) {
                retries++;
                log(`  ERROR ${hotel.name} (attempt ${retries}/${MAX_RETRIES}): ${err.message}`);
                if (retries < MAX_RETRIES) {
                    log('  Relaunching browser...');
                    try { await browser.close(); } catch { /* already closed */ }
                    ({ browser, page } = await launchBrowser());
                }
            }
        }

        if (!scanned) {
            log(`  SKIPPING ${hotel.name} after ${MAX_RETRIES} failed attempts`);
            results.push({
                id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name,
                total: 0, knowaa: false, kCnt: 0, cheap: null, kCheap: null,
                is1st: false, rank: null, provs: [], cats: [], boards: [],
                kOffers: [], byProv: {}, allOffers: [], error: 'scan_failed',
            });
        }
    }

    try { await browser.close(); } catch { /* already closed */ }
    log(`Scan complete — ${results.length} hotels, ${results.filter(r => r.error).length} failed`);
    return results;
}

// ---------------------------------------------------------------------------
// Build reports
// ---------------------------------------------------------------------------
function buildJsonReport(results, hotels) {
    const now = new Date();
    const firstHotel = hotels[0];
    return {
        scanDate: now.toISOString().split('T')[0],
        scanTime: now.toISOString().split('T')[1].replace('Z', '').slice(0, 8),
        searchDates: {
            checkIn: formatDate(firstHotel.DateFrom),
            checkOut: formatDate(firstHotel.DateTo),
        },
        source: 'innstant_b2b_browser',
        note: 'Azure SQL unreachable — hotel list sourced from cached scan data',
        totalHotelsScanned: results.length,
        summary: {
            knowaaAppears: results.filter(r => r.knowaa).length,
            knowaaFirst: results.filter(r => r.is1st).length,
            notListed: results.filter(r => !r.knowaa && r.total > 0).length,
            noOffers: results.filter(r => r.total === 0).length,
        },
        hotels: results.map(r => ({
            hotelId: r.id,
            venueId: r.v,
            name: r.hotel,
            knowaaPresent: r.knowaa,
            knowaaIsCheapest: r.is1st,
            knowaaRank: r.rank,
            knowaaPrice: r.kCheap,
            cheapestPrice: r.cheap,
            cheapestProvider: r.is1st
                ? 'Knowaa_Global_zenith'
                : (r.provs.find(p => !p.includes('Knowaa')) || r.provs[0] || null),
            categories: r.cats,
            boards: r.boards,
            providers: r.provs,
            offers: r.allOffers || [],
        })),
    };
}

function buildMarkdownReport(results, jsonReport) {
    const s = jsonReport.summary;
    const scanDate = jsonReport.scanDate;
    const checkIn = jsonReport.searchDates.checkIn;
    const checkOut = jsonReport.searchDates.checkOut;

    const first = results.filter(r => r.is1st);
    const ranked = results.filter(r => r.knowaa && !r.is1st);
    const notListed = results.filter(r => !r.knowaa && r.total > 0);
    const noOffers = results.filter(r => r.total === 0);

    let md = `# Knowaa Full Competitive Scan — ${results.length} Hotels\n\n`;
    md += `**Scan:** ${scanDate} ${jsonReport.scanTime} UTC | **Dates:** ${checkIn} → ${checkOut} | **Refundable only**\n\n`;
    md += `> ℹ️ Azure SQL unreachable — hotel list from cached scan data (${results.length} unique hotels)\n\n`;

    md += `## Summary\n\n`;
    md += `| Metric | Value |\n|--------|-------|\n`;
    md += `| Hotels scanned | ${results.length} |\n`;
    md += `| Knowaa appears | **${s.knowaaAppears} (${pct(s.knowaaAppears, results.length)})** |\n`;
    md += `| Knowaa #1 | **${s.knowaaFirst} (${pct(s.knowaaFirst, results.length)})** |\n`;
    md += `| Not listed | ${s.notListed} (${pct(s.notListed, results.length)}) |\n`;
    md += `| No refundable offers | ${s.noOffers} (${pct(s.noOffers, results.length)}) |\n\n`;

    if (first.length) {
        md += `## A. Knowaa is CHEAPEST (#1) — ${first.length} hotel${first.length !== 1 ? 's' : ''}\n\n`;
        md += `| Hotel | Venue | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap |\n`;
        md += `|-------|-------|-----|-------|----------|-------|-------------|-----|\n`;
        for (const r of first) {
            const others = Object.entries(r.byProv).filter(([p]) => !p.includes('Knowaa'));
            const second = others.length ? others.sort((a, b) => a[1] - b[1])[0] : null;
            md += `| ${r.hotel} | ${r.v} | ${r.cats[0] || '-'} | ${r.boards[0] || '-'} | **$${r.kCheap.toFixed(2)}** | ${second ? '$' + second[1].toFixed(2) : 'Only provider'} | ${second ? second[0] : '-'} | ${second ? '-$' + (second[1] - r.kCheap).toFixed(2) : '-'} |\n`;
        }
        md += '\n';
    }

    if (ranked.length) {
        const secB = ranked.filter(r => r.rank === 2);
        const secC = ranked.filter(r => r.rank > 2);

        if (secB.length) {
            md += `## B. Knowaa Is #2 — ${secB.length} hotel${secB.length !== 1 ? 's' : ''}\n\n`;
            md += `| Hotel | Venue | Cat | Board | Knowaa $ | Cheapest $ | Provider | Rank | Gap |\n`;
            md += `|-------|-------|-----|-------|----------|-----------|----------|------|-----|\n`;
            for (const r of secB) {
                const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
                md += `| ${r.hotel} | ${r.v} | ${r.cats[0] || '-'} | ${r.boards[0] || '-'} | $${r.kCheap.toFixed(2)} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | #${r.rank} | +$${(r.kCheap - r.cheap).toFixed(2)} |\n`;
            }
            md += '\n';
        }

        if (secC.length) {
            md += `## C. Knowaa Is #3+ — ${secC.length} hotel${secC.length !== 1 ? 's' : ''}\n\n`;
            md += `| Hotel | Venue | Cat | Board | Knowaa $ | Rank | Cheapest $ | Provider | Gap |\n`;
            md += `|-------|-------|-----|-------|----------|------|-----------|----------|-----|\n`;
            for (const r of secC) {
                const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
                md += `| ${r.hotel} | ${r.v} | ${r.cats[0] || '-'} | ${r.boards[0] || '-'} | $${r.kCheap.toFixed(2)} | #${r.rank} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | +$${(r.kCheap - r.cheap).toFixed(2)} |\n`;
            }
            md += '\n';
        }
    }

    if (notListed.length) {
        md += `## D. Has Offers but NO Knowaa — ${notListed.length} hotel${notListed.length !== 1 ? 's' : ''}\n\n`;
        md += `| Hotel | Venue | Cheapest $ | Provider | Categories | Boards |\n`;
        md += `|-------|-------|-----------|----------|------------|--------|\n`;
        for (const r of notListed) {
            const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
            md += `| ${r.hotel} | ${r.v} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | ${r.cats.join(', ')} | ${r.boards.join(', ')} |\n`;
        }
        md += '\n';
    }

    if (noOffers.length) {
        md += `## E. No Refundable Offers — ${noOffers.length} hotel${noOffers.length !== 1 ? 's' : ''}\n\n`;
        md += `| Hotel | Venue |\n|-------|-------|\n`;
        for (const r of noOffers) {
            md += `| ${r.hotel} | ${r.v} |\n`;
        }
        md += '\n';
    }

    return md;
}

// ---------------------------------------------------------------------------
// Save + push
// ---------------------------------------------------------------------------
function saveReports(jsonReport, markdownReport) {
    const ts = `${jsonReport.scanDate}_${jsonReport.scanTime.replace(/:/g, '-').slice(0, 5)}`;
    const scanDir = path.join(PROJECT_ROOT, 'scan-reports');
    const sharedDir = path.join(PROJECT_ROOT, 'shared-reports');

    for (const dir of [scanDir, sharedDir]) {
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    }

    const jsonFile = `${ts}_full_scan.json`;
    const mdFile = `${jsonReport.scanDate}_full_${jsonReport.hotels.length}_hotels_report.md`;

    fs.writeFileSync(path.join(scanDir, jsonFile), JSON.stringify(jsonReport, null, 2));
    fs.writeFileSync(path.join(scanDir, mdFile), markdownReport);
    fs.writeFileSync(path.join(sharedDir, jsonFile), JSON.stringify(jsonReport, null, 2));
    fs.writeFileSync(path.join(sharedDir, mdFile), markdownReport);

    log(`Reports saved: ${jsonFile}, ${mdFile}`);
    return { jsonFile, mdFile, ts };
}

function gitPush(scanDate) {
    if (FLAGS.noPush) {
        log('Skipping git push (--no-push)');
        return;
    }

    try {
        const cwd = PROJECT_ROOT;
        try { execSync('git pull --rebase --autostash origin main', { cwd, stdio: 'pipe' }); } catch (_) {}
        execSync('git add scan-reports/ shared-reports/', { cwd });
        const msg = `chore: scheduled browser-price-check scan ${scanDate}`;
        execSync(`git commit -m "${msg}"`, { cwd });
        execSync('git push -u origin main', { cwd });
        log('Reports pushed to GitHub');
    } catch (err) {
        log(`WARNING: git push failed: ${err.message}`);
        try {
            const cwd = PROJECT_ROOT;
            execSync('git pull --rebase --autostash origin main', { cwd, stdio: 'pipe' });
            execSync('git push -u origin main', { cwd });
            log('Reports pushed to GitHub (retry)');
        } catch (err2) {
            log(`WARNING: git push failed after retry: ${err2.message}`);
        }
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
    log('=== Knowaa Browser Price Check (cached hotel list) ===');
    log(`Credentials: user=${INNSTANT.user}, account=${INNSTANT.account}`);

    const hotels = loadCachedHotels();

    const results = await scanAllHotels(hotels);

    const jsonReport = buildJsonReport(results, hotels);
    const markdownReport = buildMarkdownReport(results, jsonReport);

    const { jsonFile, mdFile, ts } = saveReports(jsonReport, markdownReport);

    // Summary
    const s = jsonReport.summary;
    log('=== SCAN SUMMARY ===');
    log(`Hotels scanned:       ${results.length}`);
    log(`Knowaa appears:       ${s.knowaaAppears} (${pct(s.knowaaAppears, results.length)})`);
    log(`Knowaa #1 (cheapest): ${s.knowaaFirst} (${pct(s.knowaaFirst, results.length)})`);
    log(`Not listed:           ${s.notListed} (${pct(s.notListed, results.length)})`);
    log(`No offers:            ${s.noOffers} (${pct(s.noOffers, results.length)})`);

    gitPush(jsonReport.scanDate);
    log('=== DONE ===');

    return { jsonFile, mdFile, jsonReport, results };
}

main().catch(err => {
    console.error('FATAL:', err);
    process.exit(1);
});
