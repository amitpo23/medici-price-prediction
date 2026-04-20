const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/pw-browsers/chromium-1208/chrome-linux64/chrome';
const PROJECT_ROOT = path.join(__dirname, '..');
const INNSTANT = { user: 'Amit', pass: 'porat10', account: 'Knowaa', baseUrl: 'https://b2b.innstant.travel' };

function log(msg) { console.log(`[${new Date().toISOString().slice(11,19)}] ${msg}`); }

async function main() {
    const browser = await chromium.launch({ headless: true, executablePath: CHROME_PATH, args: ['--no-sandbox'] });
    const context = await browser.newContext({ 
        ignoreHTTPSErrors: true,
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });
    const page = await context.newPage();

    // Capture ALL requests including XHR
    const allRequests = [];
    page.on('request', req => {
        allRequests.push(`${req.method()} ${req.resourceType()} ${req.url()}`);
    });
    
    // Capture console messages
    const consoleMsgs = [];
    page.on('console', msg => {
        if (msg.type() === 'error' || msg.type() === 'warn') {
            consoleMsgs.push(`[${msg.type()}] ${msg.text()}`);
        }
    });

    const cookiePath = path.join(PROJECT_ROOT, '.innstant-cookies.json');
    if (fs.existsSync(cookiePath)) {
        await context.addCookies(JSON.parse(fs.readFileSync(cookiePath, 'utf8')));
    }
    
    // Navigate directly to hotel URL (skip home page)
    const hotelUrl = 'https://b2b.innstant.travel/hotel/citizenm-miami-brickell-hotel-854881?service=hotels&searchQuery=hotel-854881&startDate=2026-05-28&endDate=2026-05-29&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=';
    log(`Navigating directly to hotel URL...`);
    await page.goto(hotelUrl, { timeout: 60000, waitUntil: 'domcontentloaded' });
    
    // Wait and check every 5 seconds for results
    for (let i = 0; i < 8; i++) {
        await page.waitForTimeout(5000);
        const count = await page.evaluate(() => document.querySelectorAll('.search-result-item').length);
        const requests5s = allRequests.filter(r => r.includes('b2b.innstant') && r.includes('xhr') || r.includes('fetch'));
        log(`t=${5*(i+1)}s: .search-result-item count=${count}, XHR calls: ${requests5s.length}`);
        if (count > 0) break;
    }
    
    // Check for XHR requests
    const xhrRequests = allRequests.filter(r => r.includes('xhr') || r.includes('fetch'));
    log(`\nTotal XHR/Fetch requests: ${xhrRequests.length}`);
    xhrRequests.forEach(r => log('  ' + r.slice(0, 150)));
    
    // Console errors
    log(`\nConsole messages:`);
    consoleMsgs.forEach(m => log('  ' + m));
    
    // Check Vue.js state
    const vueState = await page.evaluate(() => {
        // Try to access Vue component data
        const el = document.querySelector('[data-v-app], [data-object]');
        return {
            searchModalOverlayVisible: document.querySelector('.search-modal-overlay') ? 
                getComputedStyle(document.querySelector('.search-modal-overlay')).display : 'not found',
            searchWidgetEl: !!document.querySelector('.search-widget'),
            searchResultItem: document.querySelectorAll('.search-result-item').length,
        };
    });
    log('\nVue state check: ' + JSON.stringify(vueState));
    
    await browser.close();
}

main().catch(err => { console.error('FATAL:', err.message); process.exit(1); });
