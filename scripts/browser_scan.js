#!/usr/bin/env node
/**
 * Standalone Innstant B2B browser scanner.
 *
 * Scans all active Knowaa hotels on Innstant, extracts competitive pricing,
 * writes JSON + Markdown reports, optionally writes to BrowserScanResults DB,
 * and pushes results to GitHub.
 *
 * Usage:
 *   node scripts/browser_scan.js                  # full scan
 *   node scripts/browser_scan.js --dry-run        # scan but skip DB + git push
 *   node scripts/browser_scan.js --no-db          # scan + git push, skip DB
 *   node scripts/browser_scan.js --no-push        # scan + DB, skip git push
 *
 * Environment variables (or .env file):
 *   INNSTANT_USER       — Innstant B2B username (default: amit)
 *   INNSTANT_PASS       — Innstant B2B password
 *   INNSTANT_ACCOUNT    — Innstant account name (default: amit)
 *   SOURCE_DB_SERVER    — Azure SQL server for SalesOffice.Orders
 *   SOURCE_DB_NAME      — Database name (default: medici-db)
 *   SOURCE_DB_USER      — DB user for reading Orders
 *   SOURCE_DB_PASS      — DB password for reading Orders
 *   SCAN_DB_SERVER      — Azure SQL server for BrowserScanResults (defaults to SOURCE_DB_SERVER)
 *   SCAN_DB_NAME        — Database name (defaults to SOURCE_DB_NAME)
 *   SCAN_DB_USER        — DB user for writing scan results
 *   SCAN_DB_PASS        — DB password for writing scan results
 */

const { chromium } = require('playwright');
const sql = require('mssql');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const RunReporter = require('./run_reporter');

// ---------------------------------------------------------------------------
// Load .env if present
// ---------------------------------------------------------------------------
const envPath = path.join(__dirname, '..', '.env');
if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf8').split('\n');
    for (const line of lines) {
        const match = line.match(/^\s*([\w]+)\s*=\s*(.+?)\s*$/);
        if (match && !process.env[match[1]]) {
            process.env[match[1]] = match[2].replace(/^["']|["']$/g, '');
        }
    }
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const FLAGS = {
    dryRun: process.argv.includes('--dry-run'),
    noDb: process.argv.includes('--no-db'),
    noPush: process.argv.includes('--no-push'),
};

const INNSTANT = {
    user: process.env.INNSTANT_USER || 'Amit',
    pass: process.env.INNSTANT_PASS || '',
    account: process.env.INNSTANT_ACCOUNT || 'knowaa',
    baseUrl: 'https://b2b.innstant.travel',
};

const SOURCE_DB = {
    server: process.env.SOURCE_DB_SERVER || 'medici-sql-server.database.windows.net',
    database: process.env.SOURCE_DB_NAME || 'medici-db',
    user: process.env.SOURCE_DB_USER || 'prediction_reader',
    password: process.env.SOURCE_DB_PASS || '',
    options: { encrypt: true, trustServerCertificate: false, requestTimeout: 30000 },
};

const SCAN_DB = {
    server: process.env.SCAN_DB_SERVER || SOURCE_DB.server,
    database: process.env.SCAN_DB_NAME || SOURCE_DB.database,
    user: process.env.SCAN_DB_USER || 'agent_scanner',
    password: process.env.SCAN_DB_PASS || '',
    options: { encrypt: true, trustServerCertificate: false, requestTimeout: 30000 },
};

const BATCH_SIZE = 19;
const HOTEL_TIMEOUT = 15000;
const SETTLE_DELAY = 2000;
const PROJECT_ROOT = path.join(__dirname, '..');

// ---------------------------------------------------------------------------
// Step 0: Fetch active hotels
// ---------------------------------------------------------------------------
// Dual-source: prefer hotels we actually hold rooms for (MED_Book), with
// the exact dates of those holdings. When MED_Book is empty (e.g. after
// a SalesOffice.Orders cleanup like 2026-04-15 where all orders were
// deleted), fall back to a visibility-probe over every active Knowaa
// Miami hotel with a 30-day-out date window — that keeps the scan alive
// instead of returning 0 hotels.
async function fetchHotelsFromDb() {
    log('Connecting to source DB for active hotels...');
    const pool = await sql.connect(SOURCE_DB);

    // UNION of two sources so coverage is broad enough for medici-hotels'
    // gap analytics. Priority order:
    //   1. MED_Book — rooms we currently hold, with real booking dates.
    //   2. SalesOffice.Orders — active sales-order hotels, real per-order dates.
    //
    // 2026-04-26: switched SalesOffice rows from a fixed today+30 window to the
    // actual o.DateFrom/o.DateTo. The fixed window meant all 50 sales-order
    // hotels were probed on the same date — when that date fell on a high-
    // demand US weekend (e.g. Memorial Day), Knowaa rarely cleared so the
    // browser scan reported 9% visibility while the API saw 73%. Using the
    // order's own date aligns the browser with what the API probe is doing
    // and with what we actually try to sell.
    const result = await pool.request().query(`
        ;WITH AllHotels AS (
            SELECT
                h.InnstantId,
                h.name,
                h.Innstant_ZenithId AS VenueId,
                b.startDate AS DateFrom,
                b.endDate AS DateTo,
                1 AS source_rank
            FROM MED_Book b
            JOIN Med_Hotels h ON h.HotelId = b.HotelId
            WHERE b.IsActive = 1 AND h.isActive = 1 AND h.Innstant_ZenithId >= 5000
            UNION ALL
            SELECT
                h.InnstantId, h.name, h.Innstant_ZenithId AS VenueId,
                CAST(o.DateFrom AS DATE) AS DateFrom,
                CAST(o.DateTo   AS DATE) AS DateTo,
                2 AS source_rank
            FROM [SalesOffice.Orders] o
            JOIN Med_Hotels h ON h.HotelId = CAST(o.DestinationId AS INT)
            WHERE o.IsActive = 1
              AND o.DestinationType = 'hotel'
              AND h.Innstant_ZenithId > 0
              AND o.DateFrom >= CAST(GETDATE() AS DATE)
        ),
        Ranked AS (
            SELECT *,
                   -- Pick the earliest upcoming date per venue, MED_Book first.
                   ROW_NUMBER() OVER (
                       PARTITION BY VenueId
                       ORDER BY source_rank, DateFrom
                   ) AS rn
            FROM AllHotels
        )
        SELECT InnstantId, name, VenueId, DateFrom, DateTo
        FROM Ranked
        WHERE rn = 1
        ORDER BY VenueId
    `);

    await pool.close();
    log(`Found ${result.recordset.length} distinct venues (MED_Book holdings + SalesOffice.Orders)`);
    return result.recordset;
}

// ---------------------------------------------------------------------------
// Step 1-2: Login + scan hotels
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
    const dateFrom = formatDate(hotel.DateFrom);
    const dateTo = formatDate(hotel.DateTo);
    return `${INNSTANT.baseUrl}/hotel/${slug}?service=hotels&searchQuery=hotel-${hotel.InnstantId}&startDate=${dateFrom}&endDate=${dateTo}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=`;
}

function formatDate(d) {
    if (typeof d === 'string') return d.split('T')[0];
    return d.toISOString().split('T')[0];
}

// Extraction function — runs inside the browser page
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

async function loginIfNeeded(page) {
    // Strategy 1: Load saved cookies from .innstant-cookies.json
    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    if (fs.existsSync(cookiePath)) {
        log('Loading saved cookies...');
        const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
        await page.context().addCookies(cookies);
    }

    // Check if cookies work
    await page.goto(INNSTANT.baseUrl);
    await page.waitForTimeout(3000);
    const url = page.url();
    if (!url.includes('/login') && !url.includes('/agent/login')) {
        log('Authenticated via saved cookies');
        return;
    }

    // Strategy 2: Try login with credentials
    log('Cookies expired — logging in with credentials...');
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
    await page.waitForTimeout(5000);

    const postUrl = page.url();
    if (postUrl.includes('/login')) {
        throw new Error(
            'Login failed. Update cookies by running in Playwright MCP:\n' +
            '  1. Navigate to b2b.innstant.travel (already logged in)\n' +
            '  2. Extract cookies with browser_run_code\n' +
            '  3. Save to .innstant-cookies.json'
        );
    }

    // Save fresh cookies for next run
    const freshCookies = await page.context().cookies();
    const innstantCookies = freshCookies.filter(c => c.domain.includes('innstant'));
    fs.writeFileSync(cookiePath, JSON.stringify(innstantCookies, null, 2));
    log('Logged in and saved fresh cookies');
}

async function scanHotel(page, hotel) {
    const url = buildUrl(hotel);
    await page.goto(url);
    try {
        await page.waitForSelector('.search-result-item', { timeout: HOTEL_TIMEOUT });
        await page.waitForTimeout(SETTLE_DELAY);
    } catch {
        return {
            id: hotel.InnstantId,
            v: hotel.VenueId,
            hotel: hotel.name,
            total: 0, knowaa: false, kCnt: 0,
            cheap: null, kCheap: null, is1st: false, rank: null,
            provs: [], cats: [], boards: [], kOffers: [], byProv: {},
            allOffers: [],
        };
    }
    const data = await page.evaluate(EXTRACT_FN);
    return { id: hotel.InnstantId, v: hotel.VenueId, hotel: hotel.name, ...data };
}

const MAX_RETRIES = 3;

async function launchBrowser() {
    const browser = await chromium.launch({ headless: true });
    registerBrowser(browser);   // SIGTERM handler will close this if job is cancelled
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport: { width: 1280, height: 800 },
    });
    const page = await context.newPage();
    await loginIfNeeded(page);
    return { browser, context, page };
}

async function scanAllHotels(hotels) {
    log(`Launching browser to scan ${hotels.length} hotels...`);
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
                    ? (result.is1st ? '#1' : `#${result.rank}`)
                    : (result.total > 0 ? 'NOT LISTED' : 'NO OFFERS');
                log(`  ${hotel.name}: ${status} (${result.total} offers)`);
                scanned = true;
            } catch (err) {
                retries++;
                log(`  ERROR scanning ${hotel.name} (attempt ${retries}/${MAX_RETRIES}): ${err.message}`);
                if (retries < MAX_RETRIES) {
                    log('  Relaunching browser...');
                    try { await browser.close(); } catch { /* already closed */ }
                    ({ browser, context, page } = await launchBrowser());
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
        if (i % BATCH_SIZE === 0 && i < hotels.length) {
            log(`Batch ${Math.floor(i / BATCH_SIZE)}/${Math.ceil(hotels.length / BATCH_SIZE)} complete`);
        }
    }

    try { await browser.close(); } catch { /* already closed */ }
    log(`Scan complete. ${results.length} hotels processed (${results.filter(r => r.error).length} failed).`);
    return results;
}

// ---------------------------------------------------------------------------
// Step 3-5: Build reports
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
            offers: (r.allOffers || []),
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

    md += `## Summary\n\n`;
    md += `| Metric | Value |\n|--------|-------|\n`;
    md += `| Hotels scanned | ${results.length} |\n`;
    md += `| Knowaa appears | **${s.knowaaAppears} (${pct(s.knowaaAppears, results.length)})** |\n`;
    md += `| Knowaa #1 | **${s.knowaaFirst} (${pct(s.knowaaFirst, results.length)})** |\n`;
    md += `| Not listed | ${s.notListed} (${pct(s.notListed, results.length)}) |\n`;
    md += `| No refundable offers | ${s.noOffers} (${pct(s.noOffers, results.length)}) |\n\n`;

    // Section A: Knowaa #1
    if (first.length) {
        md += `## A. Knowaa is CHEAPEST (#1) — ${first.length} hotels\n\n`;
        md += `| Hotel | Venue | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap |\n`;
        md += `|-------|-------|-----|-------|----------|-------|-------------|-----|\n`;
        for (const r of first) {
            const others = Object.entries(r.byProv).filter(([p]) => !p.includes('Knowaa'));
            const second = others.length ? others.sort((a, b) => a[1] - b[1])[0] : null;
            md += `| ${r.hotel} | ${r.v} | ${r.cats[0] || '-'} | ${r.boards[0] || '-'} | **$${r.kCheap.toFixed(2)}** | ${second ? '$' + second[1].toFixed(2) : '-'} | ${second ? second[0] : '-'} | ${second ? '-$' + (second[1] - r.kCheap).toFixed(2) : '-'} |\n`;
        }
        md += '\n';
    }

    // Section B: Knowaa #2-3+
    if (ranked.length) {
        md += `## B. Knowaa Listed But Not Cheapest — ${ranked.length} hotels\n\n`;
        md += `| Hotel | Venue | Cat | Board | Knowaa $ | Cheapest $ | Provider | Rank | Gap |\n`;
        md += `|-------|-------|-----|-------|----------|-----------|----------|------|-----|\n`;
        for (const r of ranked) {
            const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
            md += `| ${r.hotel} | ${r.v} | ${r.cats[0] || '-'} | ${r.boards[0] || '-'} | $${r.kCheap.toFixed(2)} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | #${r.rank} | +$${(r.kCheap - r.cheap).toFixed(2)} |\n`;
        }
        md += '\n';
    }

    // Section C: Not listed
    if (notListed.length) {
        md += `## C. Knowaa NOT Listed (offers from others exist) — ${notListed.length} hotels\n\n`;
        md += `| Hotel | Venue | Cheapest $ | Provider | Categories | Boards |\n`;
        md += `|-------|-------|-----------|----------|------------|--------|\n`;
        for (const r of notListed) {
            const cheapProv = Object.entries(r.byProv).sort((a, b) => a[1] - b[1])[0];
            md += `| ${r.hotel} | ${r.v} | $${r.cheap.toFixed(2)} | ${cheapProv ? cheapProv[0] : '-'} | ${r.cats.join(', ')} | ${r.boards.join(', ')} |\n`;
        }
        md += '\n';
    }

    // Section D: No offers
    if (noOffers.length) {
        md += `## D. No Refundable Offers — ${noOffers.length} hotels\n\n`;
        md += `| Hotel | Venue |\n|-------|-------|\n`;
        for (const r of noOffers) {
            md += `| ${r.hotel} | ${r.v} |\n`;
        }
        md += '\n';
    }

    return md;
}

function pct(n, total) {
    return total ? `${Math.round(n / total * 100)}%` : '0%';
}

// ---------------------------------------------------------------------------
// Step 6: Write to DB
// ---------------------------------------------------------------------------
async function writeToDb(jsonReport) {
    if (FLAGS.dryRun || FLAGS.noDb) {
        log(FLAGS.dryRun ? '[DRY RUN] Skipping DB write' : 'Skipping DB write (--no-db)');
        return 0;
    }

    if (!SCAN_DB.password) {
        log('WARNING: SCAN_DB_PASS not set — skipping DB write');
        return 0;
    }

    log('Writing scan results to [SalesOffice.BrowserScanResults]...');
    const pool = await sql.connect(SCAN_DB);

    const cityForVenue = (venueId) => {
        if (!venueId) return 'other';
        if (venueId >= 5000 && venueId <= 5999) return 'miami';
        if (venueId >= 2863 && venueId <= 2904) return 'dubai';
        if (venueId >= 2964 && venueId <= 2998) return 'paris';
        if (venueId >= 3001 && venueId <= 3073) return 'israel';
        if (venueId >= 2914 && venueId <= 2930) return 'egypt';
        if (venueId >= 2945 && venueId <= 2955) return 'lasvegas';
        return 'other';
    };

    const categoryBucket = (raw) => {
        const c = (raw || '').toLowerCase();
        if (c.includes('standard')) return 'standard';
        if (c.includes('deluxe')) return 'deluxe';
        if (c.includes('suite')) return 'suite';
        return 'other';
    };

    const scanTimestamp = new Date(`${jsonReport.scanDate}T${jsonReport.scanTime}Z`);
    const apiScanFile = `${jsonReport.scanDate}_${jsonReport.scanTime.replace(/:/g, '-').slice(0, 5)}_full_scan.json`;
    let inserted = 0;

    for (const hotel of jsonReport.hotels) {
        const offers = hotel.offers || [];
        const cheapest = { standard: null, deluxe: null, suite: null, other: null };
        for (const off of offers) {
            const b = categoryBucket(off.category);
            if (cheapest[b] === null || off.price < cheapest[b]) cheapest[b] = off.price;
        }
        const status = offers.length > 0 ? 'OK' : 'NO_RESULTS';
        let cheapestOverallOffer = null;
        for (const off of offers) {
            if (!cheapestOverallOffer || off.price < cheapestOverallOffer.price) cheapestOverallOffer = off;
        }

        try {
            await pool.request()
                .input('city', sql.NVarChar(50), cityForVenue(hotel.venueId))
                .input('venueId', sql.Int, hotel.venueId)
                .input('hotelId', sql.Int, hotel.hotelId)
                .input('hotelName', sql.NVarChar(200), (hotel.name || '').slice(0, 200))
                .input('totalRooms', sql.Int, offers.length)
                .input('refundableRooms', sql.Int, null)
                .input('cheapestStandard', sql.Float, cheapest.standard)
                .input('cheapestDeluxe', sql.Float, cheapest.deluxe)
                .input('cheapestSuite', sql.Float, cheapest.suite)
                .input('cheapestOther', sql.Float, cheapest.other)
                .input('cheapestOverall', sql.Float, hotel.cheapestPrice ?? (cheapestOverallOffer && cheapestOverallOffer.price))
                .input('cheapestCategory', sql.NVarChar(50), cheapestOverallOffer && cheapestOverallOffer.category)
                .input('cheapestBoard', sql.NVarChar(50), cheapestOverallOffer && cheapestOverallOffer.board)
                .input('cheapestProvider', sql.NVarChar(100), hotel.cheapestProvider || (cheapestOverallOffer && cheapestOverallOffer.provider))
                .input('scanStatus', sql.NVarChar(50), status)
                .input('currencyCode', sql.NVarChar(10), 'USD')
                .input('scanTimestamp', sql.DateTime, scanTimestamp)
                .input('apiScanFile', sql.NVarChar(500), apiScanFile)
                .input('createdBy', sql.NVarChar(100), process.env.CREATED_BY || 'local')
                // RawJson: full per-hotel offers (category/board/provider/price) so
                // downstream consumers don't need to fetch the JSON report file.
                // Shared across medici-price-prediction + medici-hotels via this DB.
                .input('rawJson', sql.NVarChar(sql.MAX), JSON.stringify({
                    venueId: hotel.venueId, hotelId: hotel.hotelId,
                    name: hotel.name, offers,
                    cheapestPrice: hotel.cheapestPrice,
                    cheapestProvider: hotel.cheapestProvider,
                }))
                .query(`
                    INSERT INTO [SalesOffice.BrowserScanResults]
                        (City, VenueId, HotelId, HotelName,
                         TotalRooms, RefundableRooms,
                         CheapestStandard, CheapestDeluxe, CheapestSuite, CheapestOther,
                         CheapestOverall, CheapestCategory, CheapestBoard, CheapestProvider,
                         ScanStatus, CurrencyCode, ScanTimestamp, ApiScanFile, CreatedBy,
                         RawJson)
                    VALUES
                        (@city, @venueId, @hotelId, @hotelName,
                         @totalRooms, @refundableRooms,
                         @cheapestStandard, @cheapestDeluxe, @cheapestSuite, @cheapestOther,
                         @cheapestOverall, @cheapestCategory, @cheapestBoard, @cheapestProvider,
                         @scanStatus, @currencyCode, @scanTimestamp, @apiScanFile, @createdBy,
                         @rawJson)
                `);
            inserted++;
        } catch (err) {
            log(`  ERROR inserting ${hotel.name}: ${err.message}`);
        }
    }

    await pool.close();
    log(`Inserted ${inserted}/${jsonReport.hotels.length} rows into [SalesOffice.BrowserScanResults]`);
    return inserted;
}

// ---------------------------------------------------------------------------
// Step 7: Save files + git push
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

    // Write to scan-reports/
    fs.writeFileSync(path.join(scanDir, jsonFile), JSON.stringify(jsonReport, null, 2));
    fs.writeFileSync(path.join(scanDir, mdFile), markdownReport);

    // Copy to shared-reports/
    fs.writeFileSync(path.join(sharedDir, jsonFile), JSON.stringify(jsonReport, null, 2));
    fs.writeFileSync(path.join(sharedDir, mdFile), markdownReport);

    log(`Reports saved: ${jsonFile}, ${mdFile}`);
    return { jsonFile, mdFile };
}

function gitPush(files) {
    if (FLAGS.dryRun || FLAGS.noPush) {
        log(FLAGS.dryRun ? '[DRY RUN] Skipping git push' : 'Skipping git push (--no-push)');
        return;
    }

    try {
        const cwd = PROJECT_ROOT;
        // --autostash keeps .claude-memory.md (auto-updated by post-commit hook) from blocking rebase
        try { execSync('git pull --rebase --autostash origin main', { cwd }); } catch (_) {}
        execSync(`git add shared-reports/ scan-reports/`, { cwd });
        const msg = `chore: automated browser-price-check scan ${new Date().toISOString().split('T')[0]}`;
        execSync(`git commit -m "${msg}\n\nCo-Authored-By: browser_scan.js <noreply@medici.com>"`, { cwd });
        execSync('git push origin main', { cwd });
        log('Reports pushed to GitHub');
    } catch (err) {
        // Retry once after pull
        try {
            const cwd = PROJECT_ROOT;
            execSync('git pull --rebase --autostash origin main', { cwd });
            execSync('git push origin main', { cwd });
            log('Reports pushed to GitHub (after retry)');
        } catch (err2) {
            log(`WARNING: git push failed after retry: ${err2.message}`);
        }
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
    log('=== Knowaa Browser Price Check ===');
    log(`Flags: ${JSON.stringify(FLAGS)}`);

    // Open a small connection just for the run-log row (separate from the
    // scan-DB pool which is opened/closed inside writeToDb).
    let logPool = null;
    let reporter = null;
    if (!FLAGS.dryRun) {
        try {
            logPool = await new sql.ConnectionPool(SCAN_DB).connect();
            reporter = new RunReporter(logPool, {
                agentName: 'browser-scan',
                summary: { flags: FLAGS },
            });
            await reporter.start();
        } catch (e) {
            log(`WARN: RunReporter start failed (continuing): ${e.message}`);
            reporter = null;
        }
    }

    try {
        // Step 0: Fetch hotels
        const hotels = await fetchHotelsFromDb();
        if (!hotels.length) {
            log('ERROR: No active hotels found in Orders');
            if (reporter) {
                reporter.summary.error = 'no_hotels';
                await reporter.finish('failure');
            }
            process.exit(1);
        }

        // Step 1-2: Scan
        const results = await scanAllHotels(hotels);

        // Step 3-4: Build reports
        const jsonReport = buildJsonReport(results, hotels);
        const markdownReport = buildMarkdownReport(results, jsonReport);

        // Step 5: Save files
        const files = saveReports(jsonReport, markdownReport);

        // Step 6: Write to DB
        const inserted = await writeToDb(jsonReport);

        // Step 7: Git push
        gitPush(files);

        if (reporter) {
            const s = jsonReport.summary || {};
            reporter.summary = {
                ...reporter.summary,
                hotels_total: results.length,
                rows_inserted: inserted || 0,
                knowaa_appears: s.knowaaAppears,
                knowaa_first: s.knowaaFirst,
                not_listed: s.notListed,
            };
            await reporter.finish('success');
        }

        // Summary
        const s = jsonReport.summary;
        log('=== SUMMARY ===');
        log(`Hotels scanned: ${results.length}`);
        log(`Knowaa appears: ${s.knowaaAppears} (${pct(s.knowaaAppears, results.length)})`);
        log(`Knowaa #1:      ${s.knowaaFirst} (${pct(s.knowaaFirst, results.length)})`);
        log(`Not listed:     ${s.notListed} (${pct(s.notListed, results.length)})`);
        log(`No offers:      ${s.noOffers} (${pct(s.noOffers, results.length)})`);
        log('=== DONE ===');
    } catch (err) {
        if (reporter) {
            try { await reporter.finish('failure', err); } catch (_) {}
        }
        throw err;
    } finally {
        if (logPool) {
            try { await logPool.close(); } catch (_) {}
        }
    }
}

// Graceful shutdown on SIGTERM (GHA runner cancel, docker stop, etc.).
// registerBrowser() is called from launchBrowser() so the handle is
// available at kill time and Chromium doesn't leak.
let _activeBrowser = null;
function registerBrowser(b) { _activeBrowser = b; }

const _gracefulShutdown = async (signal) => {
    log(`Received ${signal} — closing browser`);
    try { if (_activeBrowser) await _activeBrowser.close(); } catch (_) {}
    process.exit(0);
};
process.on('SIGTERM', () => _gracefulShutdown('SIGTERM'));
process.on('SIGINT',  () => _gracefulShutdown('SIGINT'));

main().catch(err => {
    console.error('FATAL:', err);
    process.exit(1);
});
