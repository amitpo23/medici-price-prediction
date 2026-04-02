#!/usr/bin/env node
/**
 * CI-compatible Innstant B2B browser scanner.
 * Handles: proxy auth, existing chromium binary, DB fallback from last scan JSON.
 *
 * Usage: node scripts/browser_scan_ci.js [--dry-run] [--no-push]
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const FLAGS = {
    dryRun: process.argv.includes('--dry-run'),
    noPush: process.argv.includes('--no-push'),
};

const PROJECT_ROOT = path.join(__dirname, '..');
const SCAN_DATE = '2026-04-02';
const CHECK_IN = '2026-04-20';
const CHECK_OUT = '2026-04-21';

const INNSTANT = {
    user: process.env.INNSTANT_USER || 'Amit',
    pass: process.env.INNSTANT_PASS || 'porat10',
    account: process.env.INNSTANT_ACCOUNT || 'Knowaa',
    baseUrl: 'https://b2b.innstant.travel',
};

// Chromium binary path (pre-installed in environment)
const CHROMIUM_PATH = '/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome';

// Extract proxy from env
function getProxyConfig() {
    const proxyUrl = process.env.http_proxy || process.env.HTTP_PROXY || '';
    const m = proxyUrl.match(/^https?:\/\/([^:]+):([^@]+)@(.+)$/);
    if (m) {
        return { server: 'http://' + m[3], username: m[1], password: m[2] };
    }
    return null;
}

const HOTEL_TIMEOUT = 20000;
const SETTLE_DELAY = 3000;
const MAX_RETRIES = 3;

// ---------------------------------------------------------------------------
// Fallback hotel list (from most recent scan JSON when DB unreachable)
// ---------------------------------------------------------------------------
function loadHotelsFromLastScan() {
    const scanDir = path.join(PROJECT_ROOT, 'scan-reports');
    const files = fs.readdirSync(scanDir)
        .filter(f => f.endsWith('_full_scan.json'))
        .sort()
        .reverse();

    if (!files.length) throw new Error('No previous scan JSON found in scan-reports/');

    const latest = files[0];
    log(`Loading hotel list from fallback: ${latest}`);
    const data = JSON.parse(fs.readFileSync(path.join(scanDir, latest), 'utf8'));
    return data.hotels.map(h => ({
        InnstantId: h.hotelId,
        VenueId: h.venueId,
        name: h.name,
        DateFrom: CHECK_IN,
        DateTo: CHECK_OUT,
    }));
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
    return `${INNSTANT.baseUrl}/hotel/${slug}?service=hotels&searchQuery=hotel-${hotel.InnstantId}&startDate=${CHECK_IN}&endDate=${CHECK_OUT}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=`;
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
            if (/non-refundable/i.test(text)) return;
            const provLabel = section.querySelector('.provider-label');
            const provider = provLabel ? provLabel.textContent.trim() : '?';
            const priceEl = section.querySelector('h4');
            const price = priceEl ? parseFloat(priceEl.textContent.replace(/[$,\s]/g, '')) : null;
            const board = /BB|breakfast/i.test(text) ? 'BB' : 'RO';
            if (price && provider !== '?') offers.push({ cat, board, price, provider });
        });
    });

    const knowaa = offers.filter(o => o.provider.includes('Knowaa'));
    const cheapest = offers.length ? Math.min(...offers.map(o => o.price)) : null;
    const kCheapest = knowaa.length ? Math.min(...knowaa.map(o => o.price)) : null;

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
        allOffers: offers.map(o => ({
            category: o.cat,
            board: o.board,
            price: o.price,
            provider: o.provider,
        })),
    };
};

// ---------------------------------------------------------------------------
// Browser management
// ---------------------------------------------------------------------------
async function launchBrowser() {
    const proxy = getProxyConfig();
    const launchOpts = {
        headless: true,
        executablePath: CHROMIUM_PATH,
        args: ['--ignore-certificate-errors', '--no-sandbox', '--disable-setuid-sandbox'],
    };
    if (proxy) launchOpts.proxy = proxy;

    const browser = await chromium.launch(launchOpts);
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        viewport: { width: 1280, height: 800 },
    });
    const page = await context.newPage();
    await loginIfNeeded(page);
    return { browser, context, page };
}

async function loginIfNeeded(page) {
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    if (fs.existsSync(cookiePath)) {
        const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
        await page.context().addCookies(cookies);
        log('Loaded saved cookies');
    }

    await page.goto(INNSTANT.baseUrl, { timeout: 30000 });
    await page.waitForTimeout(3000);

    if (!page.url().includes('/login') && !page.url().includes('/agent/login')) {
        log('Authenticated via saved cookies');
        return;
    }

    log('Logging in...');

    await page.fill('input[name="AccountName"]', INNSTANT.account);
    await page.fill('input[name="Username"]', INNSTANT.user);

    // Password field is readonly — use JS to set value and fire events
    await page.evaluate((pass) => {
        const el = document.querySelector('input[name="Password"]');
        if (el) {
            el.removeAttribute('readonly');
            el.value = pass;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }, INNSTANT.pass);

    await page.waitForTimeout(500);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(8000);

    if (page.url().includes('/login')) {
        const errText = await page.evaluate(() => {
            const el = document.querySelector('.error, .alert, [class*="error"]');
            return el ? el.textContent.trim() : 'unknown error';
        });
        throw new Error(`Login failed. Error: ${errText}`);
    }

    // Save cookies
    const freshCookies = await page.context().cookies();
    const innstantCookies = freshCookies.filter(c => c.domain.includes('innstant'));
    fs.writeFileSync(cookiePath, JSON.stringify(innstantCookies, null, 2));
    log('Logged in and saved cookies');
}

// ---------------------------------------------------------------------------
// Scan a single hotel
// ---------------------------------------------------------------------------
async function scanHotel(page, hotel) {
    const url = buildUrl(hotel);
    try {
        await page.goto(url, { timeout: HOTEL_TIMEOUT });
        await page.waitForSelector('.search-result-item', { timeout: HOTEL_TIMEOUT });
        await page.waitForTimeout(SETTLE_DELAY);
    } catch {
        return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, total: 0, knowaa: false, kCnt: 0, cheap: null, kCheap: null, is1st: false, rank: null, provs: [], cats: [], boards: [], kOffers: [], allOffers: [] };
    }
    const data = await page.evaluate(EXTRACT_FN);
    return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, ...data };
}

async function scanAllHotels(hotels) {
    log(`Scanning ${hotels.length} hotels...`);
    let { browser, context, page } = await launchBrowser();
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
                    ? (result.is1st ? '#1 CHEAPEST' : `#${result.rank}`)
                    : (result.total > 0 ? 'NOT LISTED' : 'NO OFFERS');
                log(`  [${i + 1}/${hotels.length}] ${hotel.name}: ${status} (${result.total} offers)`);
                scanned = true;
            } catch (err) {
                retries++;
                log(`  ERROR ${hotel.name} (attempt ${retries}/${MAX_RETRIES}): ${err.message.slice(0, 100)}`);
                if (retries < MAX_RETRIES) {
                    try { await browser.close(); } catch { /* ignore */ }
                    ({ browser, context, page } = await launchBrowser());
                }
            }
        }

        if (!scanned) {
            log(`  SKIPPING ${hotel.name} after ${MAX_RETRIES} attempts`);
            results.push({ id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, total: 0, knowaa: false, kCnt: 0, cheap: null, kCheap: null, is1st: false, rank: null, provs: [], cats: [], boards: [], kOffers: [], allOffers: [], error: 'scan_failed' });
        }
        i++;
    }

    try { await browser.close(); } catch { /* ignore */ }
    return results;
}

// ---------------------------------------------------------------------------
// Build JSON report
// ---------------------------------------------------------------------------
function buildJsonReport(results, hotels) {
    const now = new Date();
    const scanTime = now.toISOString().slice(11, 19);

    const hotelReports = results.map(r => {
        const sorted = (r.allOffers || []).sort((a, b) => a.price - b.price);
        const knowaaOffers = sorted.filter(o => o.provider.includes('Knowaa'));
        const cheapestPrice = sorted.length ? sorted[0].price : null;
        const cheapestProvider = sorted.length ? sorted[0].provider : null;
        const knowaaPresent = knowaaOffers.length > 0;
        const knowaaPrice = knowaaPresent ? Math.min(...knowaaOffers.map(o => o.price)) : null;
        const knowaaIsCheapest = knowaaPrice !== null && knowaaPrice <= cheapestPrice;
        const knowaaRank = knowaaPrice ? sorted.filter(o => o.price < knowaaPrice).length + 1 : null;

        return {
            hotelId: r.id,
            venueId: r.v,
            name: r.hotel,
            knowaaPresent,
            knowaaIsCheapest,
            knowaaRank,
            knowaaPrice,
            cheapestPrice,
            cheapestProvider,
            categories: r.cats || [],
            boards: r.boards || [],
            providers: r.provs || [],
            offers: sorted,
            error: r.error || null,
        };
    });

    const knowaaAppears = hotelReports.filter(h => h.knowaaPresent).length;
    const knowaaFirst = hotelReports.filter(h => h.knowaaIsCheapest).length;
    const notListed = hotelReports.filter(h => h.cheapestPrice && !h.knowaaPresent).length;
    const noOffers = hotelReports.filter(h => !h.cheapestPrice).length;

    return {
        scanDate: SCAN_DATE,
        scanTime,
        searchDates: { checkIn: CHECK_IN, checkOut: CHECK_OUT },
        source: 'innstant_b2b_browser',
        totalHotelsScanned: hotelReports.length,
        summary: { knowaaAppears, knowaaFirst, notListed, noOffers },
        hotels: hotelReports,
    };
}

// ---------------------------------------------------------------------------
// Load previous scan for comparison
// ---------------------------------------------------------------------------
function loadPreviousScan() {
    const scanDir = path.join(PROJECT_ROOT, 'scan-reports');
    const files = fs.readdirSync(scanDir)
        .filter(f => f.endsWith('_full_scan.json') && !f.startsWith(SCAN_DATE))
        .sort()
        .reverse();
    if (!files.length) return null;
    try {
        return JSON.parse(fs.readFileSync(path.join(scanDir, files[0]), 'utf8'));
    } catch {
        return null;
    }
}

// ---------------------------------------------------------------------------
// Build Markdown report
// ---------------------------------------------------------------------------
function buildMarkdownReport(jsonReport) {
    const prev = loadPreviousScan();
    const s = jsonReport.summary;
    const total = jsonReport.totalHotelsScanned;
    const withOffers = total - s.noOffers;

    function pct(n, d) { return d ? `${Math.round(n / d * 100)}%` : '0%'; }
    function delta(cur, prevVal) {
        if (prevVal === undefined || prevVal === null) return '';
        const d = cur - prevVal;
        return d > 0 ? ` **(+${d})**` : d < 0 ? ` **(${d})**` : ' *(=)*';
    }

    const prevS = prev ? prev.summary : null;
    const prevTotal = prev ? prev.totalHotelsScanned : null;

    let md = `# Knowaa Competitive Scan — ${total} Hotels\n\n`;
    md += `**Scan:** ${SCAN_DATE} ${jsonReport.scanTime} UTC | **Source:** Innstant B2B live browser scan\n`;
    md += `**Search dates:** ${CHECK_IN} → ${CHECK_OUT} (1 night, 2 adults) | **Filter:** Refundable only\n`;
    md += `**Provider:** \`Knowaa_Global_zenith\` | **Account:** Knowaa/Amit\n\n---\n\n`;

    // Summary table
    md += `## Summary\n\n`;
    md += `| Metric | Today (${jsonReport.scanTime.slice(0, 5)}) |`;
    if (prevS) md += ` Previous (${prev.scanDate}) | Δ |`;
    md += `\n|--------|---------|`;
    if (prevS) md += `---------|---|`;
    md += `\n`;

    const rows = [
        ['Hotels scanned', total, prevTotal],
        ['Hotels w/ refundable offers', withOffers, prevTotal ? prevTotal - prevS.noOffers : null],
        ['Knowaa appears', `**${s.knowaaAppears} (${pct(s.knowaaAppears, withOffers)})**`, prevS ? prevS.knowaaAppears : null],
        ['Knowaa #1 (cheapest)', `**${s.knowaaFirst} (${pct(s.knowaaFirst, withOffers)})**`, prevS ? prevS.knowaaFirst : null],
        ['Offers, NO Knowaa', `${s.notListed} (${pct(s.notListed, withOffers)})`, prevS ? prevS.notListed : null],
        ['No refundable offers', `${s.noOffers} (${pct(s.noOffers, total)})`, prevS ? prevS.noOffers : null],
    ];

    for (const [label, cur, prevVal] of rows) {
        const curNum = typeof cur === 'string' ? parseInt(cur) : cur;
        md += `| ${label} | ${cur} |`;
        if (prevS) md += ` ${prevVal} | ${typeof curNum === 'number' && prevVal !== null ? delta(curNum, prevVal) : ''} |`;
        md += `\n`;
    }

    md += `\n---\n\n`;

    // Section A: Knowaa #1
    const sectionA = jsonReport.hotels.filter(h => h.knowaaIsCheapest);
    md += `## Section A — Knowaa is #1 (Cheapest) — ${sectionA.length} hotels\n\n`;
    if (sectionA.length) {
        md += `| Hotel | Venue | Knowaa Price | Cheapest | Room | Board | Providers |\n`;
        md += `|-------|-------|-------------|----------|------|-------|----------|\n`;
        for (const h of sectionA) {
            const roomTypes = h.categories.join(', ') || '—';
            const boards = h.boards.join(', ') || '—';
            const otherProvs = h.providers.filter(p => !p.includes('Knowaa')).join(', ') || '—';
            md += `| ${h.name} | ${h.venueId} | **$${h.knowaaPrice?.toFixed(2)}** | $${h.cheapestPrice?.toFixed(2)} | ${roomTypes} | ${boards} | ${otherProvs} |\n`;
        }
    } else {
        md += `*No hotels where Knowaa is cheapest.*\n`;
    }
    md += `\n`;

    // Section B: Knowaa #2
    const sectionB = jsonReport.hotels.filter(h => h.knowaaPresent && !h.knowaaIsCheapest && h.knowaaRank === 2);
    md += `## Section B — Knowaa is #2 — ${sectionB.length} hotels\n\n`;
    if (sectionB.length) {
        md += `| Hotel | Venue | Knowaa Price | Cheapest | Gap | Cheaper Provider |\n`;
        md += `|-------|-------|-------------|----------|-----|------------------|\n`;
        for (const h of sectionB) {
            const gap = h.knowaaPrice && h.cheapestPrice ? (h.knowaaPrice - h.cheapestPrice).toFixed(2) : '?';
            md += `| ${h.name} | ${h.venueId} | $${h.knowaaPrice?.toFixed(2)} | $${h.cheapestPrice?.toFixed(2)} | +$${gap} | ${h.cheapestProvider || '—'} |\n`;
        }
    } else {
        md += `*No hotels where Knowaa is second cheapest.*\n`;
    }
    md += `\n`;

    // Section C: Knowaa #3+
    const sectionC = jsonReport.hotels.filter(h => h.knowaaPresent && !h.knowaaIsCheapest && (h.knowaaRank === null || h.knowaaRank >= 3));
    md += `## Section C — Knowaa is #3+ — ${sectionC.length} hotels\n\n`;
    if (sectionC.length) {
        md += `| Hotel | Venue | Rank | Knowaa Price | Cheapest | Gap | Cheapest Provider |\n`;
        md += `|-------|-------|------|-------------|----------|-----|-------------------|\n`;
        for (const h of sectionC) {
            const gap = h.knowaaPrice && h.cheapestPrice ? (h.knowaaPrice - h.cheapestPrice).toFixed(2) : '?';
            md += `| ${h.name} | ${h.venueId} | #${h.knowaaRank || '?'} | $${h.knowaaPrice?.toFixed(2)} | $${h.cheapestPrice?.toFixed(2)} | +$${gap} | ${h.cheapestProvider || '—'} |\n`;
        }
    } else {
        md += `*No hotels where Knowaa is ranked 3rd or lower.*\n`;
    }
    md += `\n`;

    // Section D: Offers but no Knowaa
    const sectionD = jsonReport.hotels.filter(h => h.cheapestPrice && !h.knowaaPresent);
    md += `## Section D — Has Offers but NO Knowaa — ${sectionD.length} hotels\n\n`;
    if (sectionD.length) {
        md += `| Hotel | Venue | Cheapest | Provider | Room Types | Boards |\n`;
        md += `|-------|-------|----------|----------|------------|--------|\n`;
        for (const h of sectionD) {
            const rooms = h.categories.join(', ') || '—';
            const boards = h.boards.join(', ') || '—';
            md += `| ${h.name} | ${h.venueId} | $${h.cheapestPrice?.toFixed(2)} | ${h.cheapestProvider || '—'} | ${rooms} | ${boards} |\n`;
        }
    } else {
        md += `*All hotels with offers have Knowaa listed.*\n`;
    }
    md += `\n`;

    // Section E: No refundable offers
    const sectionE = jsonReport.hotels.filter(h => !h.cheapestPrice);
    md += `## Section E — No Refundable Offers — ${sectionE.length} hotels\n\n`;
    if (sectionE.length) {
        md += `| Hotel | Venue |\n|-------|-------|\n`;
        for (const h of sectionE) {
            md += `| ${h.name} | ${h.venueId} |\n`;
        }
    } else {
        md += `*All hotels have refundable offers.*\n`;
    }
    md += `\n`;

    // Trend comparison
    if (prev) {
        md += `---\n\n## Trend vs ${prev.scanDate} ${prev.scanTime?.slice(0, 5) || ''}\n\n`;
        const prevHotels = {};
        prev.hotels.forEach(h => { prevHotels[h.hotelId] = h; });

        const improved = [];
        const worsened = [];
        const unchanged = [];
        const newMissing = [];

        for (const h of jsonReport.hotels) {
            const p = prevHotels[h.hotelId];
            if (!p) continue;
            const curRank = h.knowaaPresent ? (h.knowaaIsCheapest ? 1 : h.knowaaRank) : null;
            const prevRank = p.knowaaPresent ? (p.knowaaIsCheapest ? 1 : p.knowaaRank) : null;
            if (curRank !== null && prevRank !== null && curRank < prevRank) improved.push({ name: h.name, from: prevRank, to: curRank });
            else if (curRank !== null && prevRank !== null && curRank > prevRank) worsened.push({ name: h.name, from: prevRank, to: curRank });
            else if (curRank === null && prevRank !== null) newMissing.push({ name: h.name, prevRank });
        }

        if (improved.length) {
            md += `### Improved (better rank)\n`;
            improved.forEach(h => { md += `- **${h.name}**: #${h.from} → #${h.to}\n`; });
            md += `\n`;
        }
        if (worsened.length) {
            md += `### Worsened (worse rank)\n`;
            worsened.forEach(h => { md += `- **${h.name}**: #${h.from} → #${h.to}\n`; });
            md += `\n`;
        }
        if (newMissing.length) {
            md += `### Newly Missing (was ranked, now absent)\n`;
            newMissing.forEach(h => { md += `- **${h.name}**: was #${h.prevRank}\n`; });
            md += `\n`;
        }
        if (!improved.length && !worsened.length && !newMissing.length) {
            md += `*No rank changes vs previous scan.*\n\n`;
        }
    }

    md += `---\n*Generated by Knowaa Competitive Scanner — ${SCAN_DATE} ${jsonReport.scanTime} UTC*\n`;
    return md;
}

// ---------------------------------------------------------------------------
// Save reports + git push
// ---------------------------------------------------------------------------
function saveReports(jsonReport, mdReport) {
    const ts = `${SCAN_DATE}_${jsonReport.scanTime.replace(/:/g, '-').slice(0, 5)}`;
    const scanDir = path.join(PROJECT_ROOT, 'scan-reports');
    const sharedDir = path.join(PROJECT_ROOT, 'shared-reports');

    for (const dir of [scanDir, sharedDir]) {
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    }

    const jsonFile = `${ts}_full_scan.json`;
    const mdFile = `${SCAN_DATE}_full_${jsonReport.totalHotelsScanned}_hotels_report.md`;
    const compFile = `${SCAN_DATE}_knowaa_competitive_report.md`;

    // scan-reports/
    fs.writeFileSync(path.join(scanDir, jsonFile), JSON.stringify(jsonReport, null, 2));
    fs.writeFileSync(path.join(scanDir, mdFile), mdReport);
    fs.writeFileSync(path.join(scanDir, compFile), mdReport);

    // shared-reports/
    fs.writeFileSync(path.join(sharedDir, jsonFile), JSON.stringify(jsonReport, null, 2));
    fs.writeFileSync(path.join(sharedDir, mdFile), mdReport);

    log(`Reports saved: ${jsonFile}, ${mdFile}`);
    return { jsonFile, mdFile };
}

function gitPush() {
    if (FLAGS.dryRun || FLAGS.noPush) {
        log(FLAGS.dryRun ? '[DRY RUN] Skipping git push' : 'Skipping git push (--no-push)');
        return;
    }
    try {
        const cwd = PROJECT_ROOT;
        execSync('git add scan-reports/ shared-reports/', { cwd });
        const msg = `chore: scheduled browser-price-check scan ${SCAN_DATE}`;
        execSync(`git commit -m "${msg}"`, { cwd, stdio: 'pipe' });
        execSync('git push -u origin main', { cwd });
        log('Reports pushed to GitHub');
    } catch (err) {
        log(`WARNING: git push failed: ${err.message.slice(0, 200)}`);
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function log(msg) {
    const ts = new Date().toISOString().slice(11, 19);
    console.log(`[${ts}] ${msg}`);
}

async function main() {
    log('=== Knowaa Competitive Scanner ===');
    log(`Date: ${SCAN_DATE} | Dates: ${CHECK_IN} → ${CHECK_OUT}`);
    log(`Flags: ${JSON.stringify(FLAGS)}`);

    // Load hotels (from last JSON since DB unreachable)
    const hotels = loadHotelsFromLastScan();
    log(`Loaded ${hotels.length} hotels from fallback`);

    // Scan
    const results = await scanAllHotels(hotels);

    // Build reports
    const jsonReport = buildJsonReport(results, hotels);
    const mdReport = buildMarkdownReport(jsonReport);

    // Save + push
    saveReports(jsonReport, mdReport);
    gitPush();

    // Summary
    const s = jsonReport.summary;
    const withOffers = jsonReport.totalHotelsScanned - s.noOffers;
    log('=== SUMMARY ===');
    log(`Hotels: ${results.length} | w/offers: ${withOffers}`);
    log(`Knowaa appears: ${s.knowaaAppears} (${Math.round(s.knowaaAppears / withOffers * 100)}%)`);
    log(`Knowaa #1:      ${s.knowaaFirst} (${Math.round(s.knowaaFirst / withOffers * 100)}%)`);
    log(`Not listed:     ${s.notListed}`);
    log(`No offers:      ${s.noOffers}`);
    log('=== DONE ===');
}

main().catch(err => {
    console.error('FATAL:', err.message);
    process.exit(1);
});
