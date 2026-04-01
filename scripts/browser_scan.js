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
    user: process.env.INNSTANT_USER || 'amit',
    pass: process.env.INNSTANT_PASS || '',
    account: process.env.INNSTANT_ACCOUNT || 'amit',
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
// Step 0: Fetch active hotels from SalesOffice.Orders
// ---------------------------------------------------------------------------
async function fetchHotelsFromDb() {
    log('Connecting to source DB for active hotels...');
    const pool = await sql.connect(SOURCE_DB);
    const result = await pool.request().query(`
        SELECT DISTINCT
            o.DestinationId AS InnstantId,
            h.name,
            h.Innstant_ZenithId AS VenueId,
            o.DateFrom,
            o.DateTo
        FROM [dbo].[SalesOffice.Orders] o
        JOIN Med_Hotels h ON h.InnstantId = o.DestinationId
        WHERE h.isActive = 1
          AND h.Innstant_ZenithId >= 5000
          AND o.IsActive = 1
        ORDER BY h.name
    `);
    await pool.close();
    log(`Found ${result.recordset.length} active hotels in Orders`);
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

async function scanAllHotels(hotels) {
    log(`Launching browser to scan ${hotels.length} hotels...`);
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport: { width: 1280, height: 800 },
    });
    const page = await context.newPage();

    await loginIfNeeded(page);

    const results = [];
    const batches = [];
    for (let i = 0; i < hotels.length; i += BATCH_SIZE) {
        batches.push(hotels.slice(i, i + BATCH_SIZE));
    }

    for (let b = 0; b < batches.length; b++) {
        const batch = batches[b];
        log(`Batch ${b + 1}/${batches.length} — ${batch.length} hotels`);
        for (const hotel of batch) {
            const result = await scanHotel(page, hotel);
            results.push(result);
            const status = result.knowaa
                ? (result.is1st ? '#1' : `#${result.rank}`)
                : (result.total > 0 ? 'NOT LISTED' : 'NO OFFERS');
            log(`  ${hotel.name}: ${status} (${result.total} offers)`);
        }
    }

    await browser.close();
    log(`Scan complete. ${results.length} hotels processed.`);
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

    log('Writing scan results to BrowserScanResults...');
    const pool = await sql.connect(SCAN_DB);

    // Ensure table exists
    await pool.request().query(`
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'SalesOffice.BrowserScanResults' AND schema_id = SCHEMA_ID('dbo'))
        BEGIN
            CREATE TABLE [dbo].[SalesOffice.BrowserScanResults] (
                Id INT IDENTITY(1,1) PRIMARY KEY,
                ScanDate DATETIME NOT NULL,
                CheckInDate DATE NOT NULL,
                CheckOutDate DATE NOT NULL,
                VenueId INT NULL,
                HotelId INT NULL,
                HotelName NVARCHAR(200) NULL,
                Category NVARCHAR(100) NULL,
                Board NVARCHAR(50) NULL,
                Price DECIMAL(10,2) NULL,
                PricePerNight DECIMAL(10,2) NULL,
                Currency NVARCHAR(10) NULL,
                Provider NVARCHAR(100) NULL,
                IsKnowaa BIT DEFAULT 0,
                KnowaaRank INT NULL,
                Nights INT NULL,
                CreatedAt DATETIME DEFAULT GETDATE()
            );
            CREATE INDEX IX_BrowserScanResults_ScanDate ON [dbo].[SalesOffice.BrowserScanResults](ScanDate);
            CREATE INDEX IX_BrowserScanResults_VenueId ON [dbo].[SalesOffice.BrowserScanResults](VenueId);
        END
    `);

    const scanDate = new Date(`${jsonReport.scanDate}T${jsonReport.scanTime}Z`);
    const checkIn = jsonReport.searchDates.checkIn;
    const checkOut = jsonReport.searchDates.checkOut;
    let inserted = 0;

    for (const hotel of jsonReport.hotels) {
        for (const offer of hotel.offers) {
            try {
                await pool.request()
                    .input('scanDate', sql.DateTime, scanDate)
                    .input('checkIn', sql.Date, checkIn)
                    .input('checkOut', sql.Date, checkOut)
                    .input('venueId', sql.Int, hotel.venueId)
                    .input('hotelId', sql.Int, hotel.hotelId)
                    .input('name', sql.NVarChar(200), hotel.name)
                    .input('cat', sql.NVarChar(100), offer.category)
                    .input('board', sql.NVarChar(50), offer.board)
                    .input('price', sql.Decimal(10, 2), offer.price)
                    .input('ppn', sql.Decimal(10, 2), offer.price)
                    .input('currency', sql.NVarChar(10), 'USD')
                    .input('provider', sql.NVarChar(100), offer.provider)
                    .input('isKnowaa', sql.Bit, offer.provider.includes('Knowaa') ? 1 : 0)
                    .input('rank', sql.Int, hotel.knowaaRank)
                    .input('nights', sql.Int, 1)
                    .query(`
                        INSERT INTO [dbo].[SalesOffice.BrowserScanResults]
                            (ScanDate, CheckInDate, CheckOutDate, VenueId, HotelId, HotelName,
                             Category, Board, Price, PricePerNight, Currency, Provider,
                             IsKnowaa, KnowaaRank, Nights)
                        VALUES
                            (@scanDate, @checkIn, @checkOut, @venueId, @hotelId, @name,
                             @cat, @board, @price, @ppn, @currency, @provider,
                             @isKnowaa, @rank, @nights)
                    `);
                inserted++;
            } catch (err) {
                log(`  ERROR inserting ${hotel.name}/${offer.provider}: ${err.message}`);
            }
        }
    }

    await pool.close();
    log(`Inserted ${inserted} rows into BrowserScanResults`);
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
        execSync(`git add shared-reports/ scan-reports/`, { cwd });
        const msg = `chore: automated browser-price-check scan ${new Date().toISOString().split('T')[0]}`;
        execSync(`git commit -m "${msg}\n\nCo-Authored-By: browser_scan.js <noreply@medici.com>"`, { cwd });
        execSync('git push origin main', { cwd });
        log('Reports pushed to GitHub');
    } catch (err) {
        log(`WARNING: git push failed: ${err.message}`);
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

    // Step 0: Fetch hotels
    const hotels = await fetchHotelsFromDb();
    if (!hotels.length) {
        log('ERROR: No active hotels found in Orders');
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
    await writeToDb(jsonReport);

    // Step 7: Git push
    gitPush(files);

    // Summary
    const s = jsonReport.summary;
    log('=== SUMMARY ===');
    log(`Hotels scanned: ${results.length}`);
    log(`Knowaa appears: ${s.knowaaAppears} (${pct(s.knowaaAppears, results.length)})`);
    log(`Knowaa #1:      ${s.knowaaFirst} (${pct(s.knowaaFirst, results.length)})`);
    log(`Not listed:     ${s.notListed} (${pct(s.notListed, results.length)})`);
    log(`No offers:      ${s.noOffers} (${pct(s.noOffers, results.length)})`);
    log('=== DONE ===');
}

main().catch(err => {
    console.error('FATAL:', err);
    process.exit(1);
});
