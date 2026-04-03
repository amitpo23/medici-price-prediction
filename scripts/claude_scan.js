#!/usr/bin/env node
/**
 * Claude-environment browser scanner for Knowaa competitive pricing.
 * Uses system Chrome + egress proxy + fallback hotel list from last JSON.
 * Run: node scripts/claude_scan.js
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PROJECT_ROOT = path.join(__dirname, '..');
const SCAN_REPORTS = path.join(PROJECT_ROOT, 'scan-reports');
const SHARED_REPORTS = path.join(PROJECT_ROOT, 'shared-reports');
const CHROME_PATH = '/tmp/chrome/chrome-linux64/chrome';

// ---------------------------------------------------------------------------
// Proxy config (parse from HTTPS_PROXY env)
// ---------------------------------------------------------------------------
function parseProxy() {
    const raw = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || '';
    if (!raw) return null;
    try {
        const u = new URL(raw);
        return {
            server: `${u.protocol}//${u.hostname}:${u.port}`,
            username: decodeURIComponent(u.username),
            password: decodeURIComponent(u.password),
        };
    } catch {
        return null;
    }
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const INNSTANT = {
    user: process.env.INNSTANT_USER || 'Amit',
    pass: process.env.INNSTANT_PASS || 'porat10',
    account: process.env.INNSTANT_ACCOUNT || 'Knowaa',
    baseUrl: 'https://b2b.innstant.travel',
};

const HOTEL_TIMEOUT = 20000;
const SETTLE_DELAY = 3000;
const MAX_RETRIES = 3;
const BATCH_LOG_SIZE = 10;

// ---------------------------------------------------------------------------
// Hotel list: try DB fallback → last JSON scan
// ---------------------------------------------------------------------------
function loadHotelsFromLastScan() {
    const files = fs.readdirSync(SCAN_REPORTS)
        .filter(f => f.endsWith('_full_scan.json'))
        .sort()
        .reverse();
    if (!files.length) throw new Error('No previous scan JSON found in scan-reports/');
    const latest = path.join(SCAN_REPORTS, files[0]);
    log(`Loading hotel list from previous scan: ${files[0]}`);
    const data = JSON.parse(fs.readFileSync(latest, 'utf8'));
    // De-duplicate by hotelId
    const seen = new Set();
    const hotels = [];
    for (const h of data.hotels) {
        if (!seen.has(h.hotelId)) {
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
    log(`Loaded ${hotels.length} unique hotels (dates: ${data.searchDates.checkIn} → ${data.searchDates.checkOut})`);
    return hotels;
}

// ---------------------------------------------------------------------------
// URL builder
// ---------------------------------------------------------------------------
function slugify(name) {
    return name
        .toLowerCase()
        .replace(/['']/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
}

function buildUrl(hotel) {
    const slug = `${slugify(hotel.name)}-${hotel.InnstantId}`;
    const dateFrom = hotel.DateFrom.split('T')[0];
    const dateTo = hotel.DateTo.split('T')[0];
    return `${INNSTANT.baseUrl}/hotel/${slug}?service=hotels&searchQuery=hotel-${hotel.InnstantId}&startDate=${dateFrom}&endDate=${dateTo}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=`;
}

// ---------------------------------------------------------------------------
// Extraction function (runs inside browser)
// ---------------------------------------------------------------------------
const EXTRACT_FN = () => {
    const items = document.querySelectorAll('.search-result-item');
    const offers = [];
    items.forEach(item => {
        const catEl = item.querySelector('.small-4,.medium-3');
        const cat = catEl ? catEl.textContent.trim().split('\n')[0].trim() : '?';
        item.querySelectorAll('.search-result-item-sub-section').forEach(section => {
            const text = section.textContent || '';
            if (/non-refundable/i.test(text)) return; // skip NR
            const provLabel = section.querySelector('.provider-label');
            const provider = provLabel ? provLabel.textContent.trim() : '?';
            const priceEl = section.querySelector('h4');
            const price = priceEl ? parseFloat(priceEl.textContent.replace(/[$,\s]/g, '')) : null;
            const board = /BB|breakfast/i.test(text) ? 'BB' : 'RO';
            if (price && price > 0) offers.push({ cat, board, price, provider });
        });
    });

    const knowaa = offers.filter(o => o.provider.includes('Knowaa'));
    const cheapest = offers.length ? Math.min(...offers.map(o => o.price)) : null;
    const kCheapest = knowaa.length ? Math.min(...knowaa.map(o => o.price)) : null;
    const byProv = {};
    offers.forEach(o => {
        if (!byProv[o.provider] || o.price < byProv[o.provider]) byProv[o.provider] = o.price;
    });

    // rank = how many unique provider min-prices are cheaper than knowaa
    const provMinPrices = Object.values(byProv).sort((a, b) => a - b);
    const rank = kCheapest !== null
        ? provMinPrices.filter(p => p < kCheapest).length + 1
        : null;

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
// Browser launch + login
// ---------------------------------------------------------------------------
async function launchBrowser(proxy) {
    const launchOpts = {
        headless: true,
        executablePath: CHROME_PATH,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--ignore-certificate-errors'],
    };
    if (proxy) launchOpts.proxy = proxy;

    const browser = await chromium.launch(launchOpts);
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport: { width: 1280, height: 800 },
        ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await loginIfNeeded(page);
    return { browser, context, page };
}

async function loginIfNeeded(page) {
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    if (fs.existsSync(cookiePath)) {
        try {
            const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
            await page.context().addCookies(cookies);
            log('Loaded saved cookies');
        } catch { /* ignore */ }
    }

    await page.goto(INNSTANT.baseUrl, { timeout: 30000 });
    await page.waitForTimeout(3000);
    const url = page.url();

    if (!url.includes('/login') && !url.includes('/agent/login')) {
        log('Authenticated via saved cookies');
        return;
    }

    log('Logging in to Innstant B2B...');
    await page.fill('input[name="AccountName"]', INNSTANT.account);
    await page.fill('input[name="Username"]', INNSTANT.user);
    // Some builds make Password readonly — remove attribute
    await page.evaluate(() => {
        const el = document.querySelector('input[name="Password"]');
        if (el) { el.removeAttribute('readonly'); el.removeAttribute('disabled'); }
    });
    await page.fill('input[name="Password"]', INNSTANT.pass);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(6000);

    const postUrl = page.url();
    if (postUrl.includes('/login')) {
        throw new Error(`Login failed — still on ${postUrl}. Check credentials: user=${INNSTANT.user} account=${INNSTANT.account}`);
    }

    // Save cookies for next run
    const freshCookies = await page.context().cookies();
    const innstantCookies = freshCookies.filter(c => c.domain && c.domain.includes('innstant'));
    fs.writeFileSync(cookiePath, JSON.stringify(innstantCookies, null, 2));
    log(`Logged in successfully. Saved ${innstantCookies.length} cookies.`);
}

// ---------------------------------------------------------------------------
// Scan single hotel
// ---------------------------------------------------------------------------
async function scanHotel(page, hotel) {
    const url = buildUrl(hotel);
    await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
    try {
        await page.waitForSelector('.search-result-item', { timeout: HOTEL_TIMEOUT });
        await page.waitForTimeout(SETTLE_DELAY);
    } catch {
        return {
            id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name,
            total: 0, knowaa: false, kCnt: 0,
            cheap: null, kCheap: null, is1st: false, rank: null,
            provs: [], cats: [], boards: [], kOffers: [], byProv: {},
            allOffers: [],
        };
    }
    const data = await page.evaluate(EXTRACT_FN);
    return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, ...data };
}

// ---------------------------------------------------------------------------
// Scan all hotels with crash recovery
// ---------------------------------------------------------------------------
async function scanAllHotels(hotels, proxy) {
    log(`Launching browser to scan ${hotels.length} hotels...`);
    let { browser, page } = await launchBrowser(proxy);

    const results = [];
    let i = 0;

    while (i < hotels.length) {
        const hotel = hotels[i];
        let retries = 0;
        let scanned = false;

        while (retries < MAX_RETRIES && !scanned) {
            try {
                const result = await scanHotel(page, hotel);
                results.push(result);
                const status = result.knowaa
                    ? (result.is1st ? `#1 ($${result.kCheap?.toFixed(2)})` : `#${result.rank} ($${result.kCheap?.toFixed(2)} vs $${result.cheap?.toFixed(2)})`)
                    : (result.total > 0 ? `NOT LISTED (${result.total} offers)` : 'NO OFFERS');
                log(`  [${String(i + 1).padStart(2)}/${hotels.length}] ${hotel.name}: ${status}`);
                scanned = true;
            } catch (err) {
                retries++;
                log(`  ERROR ${hotel.name} (attempt ${retries}/${MAX_RETRIES}): ${err.message.slice(0, 80)}`);
                if (retries < MAX_RETRIES) {
                    log('  Relaunching browser...');
                    try { await browser.close(); } catch { /* already closed */ }
                    ({ browser, page } = await launchBrowser(proxy));
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

        i++;
        if (i % BATCH_LOG_SIZE === 0 && i < hotels.length) {
            log(`--- Progress: ${i}/${hotels.length} hotels scanned ---`);
        }
    }

    try { await browser.close(); } catch { /* already closed */ }
    log(`Scan complete. ${results.length} hotels processed (${results.filter(r => r.error).length} failed).`);
    return results;
}

// ---------------------------------------------------------------------------
// Build JSON report
// ---------------------------------------------------------------------------
function buildJsonReport(results, hotels) {
    const now = new Date();
    const firstHotel = hotels[0];
    return {
        scanDate: now.toISOString().split('T')[0],
        scanTime: now.toISOString().split('T')[1].replace('Z', '').slice(0, 8),
        searchDates: {
            checkIn: firstHotel.DateFrom.split('T')[0],
            checkOut: firstHotel.DateTo.split('T')[0],
        },
        source: 'innstant_b2b_browser_claude',
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
            cheapestProvider: r.provs[0] || null,
            categories: r.cats,
            boards: r.boards,
            providers: r.provs,
            offers: r.allOffers || [],
            error: r.error || null,
        })),
    };
}

// ---------------------------------------------------------------------------
// Build Markdown report (with trend comparison)
// ---------------------------------------------------------------------------
function pct(n, total) {
    return total ? `${Math.round(n / total * 100)}%` : '0%';
}

function loadPreviousScanSummary() {
    const files = fs.readdirSync(SCAN_REPORTS)
        .filter(f => f.endsWith('_full_scan.json'))
        .sort()
        .reverse();
    if (files.length < 1) return null;
    try {
        const prev = JSON.parse(fs.readFileSync(path.join(SCAN_REPORTS, files[0]), 'utf8'));
        return prev.summary;
    } catch { return null; }
}

function trendArrow(current, previous, field) {
    if (!previous) return '';
    const delta = current[field] - previous[field];
    if (delta > 0) return ` ▲${delta}`;
    if (delta < 0) return ` ▼${Math.abs(delta)}`;
    return ' →0';
}

function buildMarkdownReport(results, jsonReport, prevSummary) {
    const s = jsonReport.summary;
    const scanDate = jsonReport.scanDate;
    const scanTime = jsonReport.scanTime;
    const checkIn = jsonReport.searchDates.checkIn;
    const checkOut = jsonReport.searchDates.checkOut;
    const n = results.length;

    const sectionA = results.filter(r => r.is1st);
    const sectionB = results.filter(r => r.knowaa && !r.is1st);
    const sectionC = results.filter(r => !r.knowaa && r.total > 0);
    const sectionD = results.filter(r => r.total === 0);

    let md = `# Knowaa Competitive Scan — ${n} Hotels\n\n`;
    md += `> **Scan date:** ${scanDate} ${scanTime} UTC | **Check-in:** ${checkIn} → ${checkOut} | **Refundable only**\n\n`;

    // Summary table with trend
    md += `## Summary\n\n`;
    md += `| Metric | Value | Trend |\n|--------|-------|-------|\n`;
    md += `| Hotels scanned | ${n} | - |\n`;
    md += `| Knowaa appears | **${s.knowaaAppears} (${pct(s.knowaaAppears, n)})** |${trendArrow(s, prevSummary, 'knowaaAppears')} |\n`;
    md += `| Knowaa #1 (cheapest) | **${s.knowaaFirst} (${pct(s.knowaaFirst, n)})** |${trendArrow(s, prevSummary, 'knowaaFirst')} |\n`;
    md += `| Listed but not cheapest | ${sectionB.length} (${pct(sectionB.length, n)}) |${prevSummary ? ` ${sectionB.length - (prevSummary.knowaaAppears - prevSummary.knowaaFirst) > 0 ? '▲' : sectionB.length - (prevSummary.knowaaAppears - prevSummary.knowaaFirst) < 0 ? '▼' : '→'}` : ''} |\n`;
    md += `| Not listed (others have offers) | ${s.notListed} (${pct(s.notListed, n)}) |${trendArrow(s, prevSummary, 'notListed')} |\n`;
    md += `| No refundable offers | ${s.noOffers} (${pct(s.noOffers, n)}) |${trendArrow(s, prevSummary, 'noOffers')} |\n\n`;

    // Section A: Knowaa #1
    if (sectionA.length) {
        md += `## A — Knowaa is CHEAPEST (#1) — ${sectionA.length} hotels\n\n`;
        md += `| Hotel | VenueId | Knowaa Price | 2nd Price | 2nd Provider | Advantage |\n`;
        md += `|-------|---------|-------------|-----------|-------------|----------|\n`;
        for (const r of sectionA) {
            const others = Object.entries(r.byProv).filter(([p]) => !p.includes('Knowaa')).sort((a, b) => a[1] - b[1]);
            const second = others[0];
            md += `| ${r.hotel} | ${r.v} | **$${r.kCheap.toFixed(2)}** | ${second ? '$' + second[1].toFixed(2) : '-'} | ${second ? second[0] : '-'} | ${second ? `-$${(second[1] - r.kCheap).toFixed(2)}` : '-'} |\n`;
        }
        md += '\n';
    } else {
        md += `## A — Knowaa is CHEAPEST (#1) — 0 hotels\n\n_No hotels where Knowaa is cheapest._\n\n`;
    }

    // Section B: Knowaa listed but not cheapest
    if (sectionB.length) {
        md += `## B — Knowaa Listed But NOT Cheapest — ${sectionB.length} hotels\n\n`;
        md += `| Hotel | VenueId | Knowaa Price | Cheapest | Provider | Rank | Gap |\n`;
        md += `|-------|---------|-------------|----------|----------|------|-----|\n`;
        for (const r of sectionB) {
            const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
            md += `| ${r.hotel} | ${r.v} | $${r.kCheap.toFixed(2)} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | #${r.rank} | +$${(r.kCheap - r.cheap).toFixed(2)} |\n`;
        }
        md += '\n';
    }

    // Section C: Not listed (others have offers)
    if (sectionC.length) {
        md += `## C — Knowaa NOT Listed (competitors active) — ${sectionC.length} hotels\n\n`;
        md += `| Hotel | VenueId | Cheapest | Provider | Cats | Boards |\n`;
        md += `|-------|---------|---------|----------|------|--------|\n`;
        for (const r of sectionC) {
            const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
            md += `| ${r.hotel} | ${r.v} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | ${r.cats.join(', ')} | ${r.boards.join(', ')} |\n`;
        }
        md += '\n';
    }

    // Section D: No offers at all
    if (sectionD.length) {
        md += `## D — No Refundable Offers — ${sectionD.length} hotels\n\n`;
        md += `| Hotel | VenueId | Note |\n|-------|---------|------|\n`;
        for (const r of sectionD) {
            md += `| ${r.hotel} | ${r.v} | ${r.error === 'scan_failed' ? 'scan error' : 'no refundable offers'} |\n`;
        }
        md += '\n';
    }

    // Trend section
    if (prevSummary) {
        md += `## Trend vs Previous Scan\n\n`;
        md += `| Metric | Previous | Current | Change |\n|--------|----------|---------|--------|\n`;
        md += `| Knowaa appears | ${prevSummary.knowaaAppears} | ${s.knowaaAppears} | ${s.knowaaAppears - prevSummary.knowaaAppears > 0 ? '+' : ''}${s.knowaaAppears - prevSummary.knowaaAppears} |\n`;
        md += `| Knowaa #1 | ${prevSummary.knowaaFirst} | ${s.knowaaFirst} | ${s.knowaaFirst - prevSummary.knowaaFirst > 0 ? '+' : ''}${s.knowaaFirst - prevSummary.knowaaFirst} |\n`;
        md += `| Not listed | ${prevSummary.notListed} | ${s.notListed} | ${s.notListed - prevSummary.notListed > 0 ? '+' : ''}${s.notListed - prevSummary.notListed} |\n`;
        md += `| No offers | ${prevSummary.noOffers} | ${s.noOffers} | ${s.noOffers - prevSummary.noOffers > 0 ? '+' : ''}${s.noOffers - prevSummary.noOffers} |\n\n`;
    }

    md += `---\n_Generated by Knowaa Competitive Scanner (Claude agent) — ${scanDate} ${scanTime} UTC_\n`;
    return md;
}

// ---------------------------------------------------------------------------
// Save reports + git push
// ---------------------------------------------------------------------------
function saveReports(jsonReport, markdownReport) {
    const ts = `${jsonReport.scanDate}_${jsonReport.scanTime.replace(/:/g, '-').slice(0, 5)}`;
    for (const dir of [SCAN_REPORTS, SHARED_REPORTS]) {
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    }

    const jsonFile = `${ts}_full_scan.json`;
    const mdFile = `${jsonReport.scanDate}_full_${jsonReport.hotels.length}_hotels_report.md`;
    const competitiveFile = `${jsonReport.scanDate}_knowaa_competitive_report.md`;

    for (const dir of [SCAN_REPORTS, SHARED_REPORTS]) {
        fs.writeFileSync(path.join(dir, jsonFile), JSON.stringify(jsonReport, null, 2));
        fs.writeFileSync(path.join(dir, mdFile), markdownReport);
        fs.writeFileSync(path.join(dir, competitiveFile), markdownReport);
    }

    log(`Saved: ${jsonFile}, ${mdFile}`);
    return { jsonFile, mdFile, competitiveFile };
}

function gitPush(scanDate) {
    try {
        const cwd = PROJECT_ROOT;
        execSync('git add scan-reports/ shared-reports/', { cwd, stdio: 'pipe' });
        const msg = `chore: scheduled browser-price-check scan ${scanDate}`;
        execSync(`git commit -m "${msg}"`, { cwd, stdio: 'pipe' });
        execSync('git push -u origin main', { cwd, stdio: 'pipe' });
        log('Reports committed and pushed to GitHub');
    } catch (err) {
        const output = err.stdout?.toString() || err.stderr?.toString() || err.message;
        log(`WARNING: git operation issue: ${output.slice(0, 200)}`);
    }
}

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------
function log(msg) {
    const ts = new Date().toISOString().slice(11, 19);
    console.log(`[${ts}] ${msg}`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
    log('=== Knowaa Browser Price Check (Claude agent) ===');

    const proxy = parseProxy();
    log(proxy ? `Proxy: ${proxy.server} (user: ${proxy.username.slice(0, 20)}...)` : 'No proxy');

    // Load hotels from last scan (DB not available in Claude env)
    const hotels = loadHotelsFromLastScan();
    if (!hotels.length) { log('ERROR: No hotels found'); process.exit(1); }

    // Load previous summary for trend comparison (before scan runs)
    const prevSummary = loadPreviousScanSummary();
    log(prevSummary ? `Previous summary: appears=${prevSummary.knowaaAppears}, #1=${prevSummary.knowaaFirst}` : 'No previous scan for trend');

    // Scan
    const results = await scanAllHotels(hotels, proxy);

    // Build reports
    const jsonReport = buildJsonReport(results, hotels);
    const markdownReport = buildMarkdownReport(results, jsonReport, prevSummary);

    // Save
    saveReports(jsonReport, markdownReport);

    // Git push
    gitPush(jsonReport.scanDate);

    // Final summary
    const s = jsonReport.summary;
    log('=== FINAL SUMMARY ===');
    log(`Hotels scanned:  ${results.length}`);
    log(`Knowaa appears:  ${s.knowaaAppears} (${pct(s.knowaaAppears, results.length)})`);
    log(`Knowaa #1:       ${s.knowaaFirst} (${pct(s.knowaaFirst, results.length)})`);
    log(`Not listed:      ${s.notListed} (${pct(s.notListed, results.length)})`);
    log(`No offers:       ${s.noOffers} (${pct(s.noOffers, results.length)})`);
    log('=== DONE ===');
}

main().catch(err => {
    console.error('FATAL:', err.message || err);
    process.exit(1);
});
