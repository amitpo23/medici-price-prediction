const { chromium } = require('playwright');
const fs = require('fs');

const ALL_VENUES = [
  '5073','5075','5077','5082','5083','5113','5115','5116','5117','5119','5124',
  '5130','5131','5132','5136','5138','5139','5140','5141','5265','5266',
  '5267','5268','5274','5275','5276','5277','5278','5279','5064','5089',
  '5094','5102','5111'
];

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1700, height: 1100 } });

  await page.goto('https://hotel.tools/login');
  await page.waitForTimeout(2000);
  await page.locator('input[name="account"]').fill('Medici LIVE');
  await page.locator('input[name="agent"]').fill('zvi');
  await page.locator('input[name="password"]').fill('karpad66');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(5000);
  console.log('Logged in.');

  const results = {};
  const sqlLines = [];

  // Hotel ID lookup
  const hotelMap = {
    '5073':6661,'5075':193899,'5077':852120,'5082':733781,'5083':20706,
    '5113':66737,'5115':254198,'5116':846428,'5117':855711,'5119':854710,
    '5124':68833,'5130':67387,'5131':286236,'5132':277280,'5136':31226,
    '5138':851633,'5139':851939,'5140':301583,'5141':31433,'5265':414146,
    '5266':6654,'5267':301645,'5268':19977,'5274':701659,'5275':21842,
    '5276':6482,'5277':87197,'5278':852725,'5279':301640,
    '5064':32687,'5089':117491,'5094':855865,'5102':237547,'5111':31709
  };

  for (const vid of ALL_VENUES) {
    await page.goto('https://hotel.tools/pricing-inventory', { timeout: 15000 });
    await page.waitForTimeout(2000);
    await page.locator('#venue_context_selector').selectOption({ value: vid });
    await page.waitForTimeout(3000);

    // Read rate plans
    const rpOpts = await page.locator('#rate-plans option').all();
    const ratePlans = [];
    for (const o of rpOpts) {
      const val = await o.getAttribute('value');
      const text = (await o.textContent()).trim();
      if (val && val !== '0') ratePlans.push({ code: val, name: text });
    }

    // Read rooms
    const roomOpts = await page.locator('#rate-for-product-id option').all();
    const rooms = [];
    for (const o of roomOpts) {
      const val = await o.getAttribute('value');
      const text = (await o.textContent()).trim();
      if (val) rooms.push({ id: val, name: text });
    }

    // Bulk update rooms
    const buRoomOpts = await page.locator('#bu-rooms option').all();
    const buRooms = [];
    for (const o of buRoomOpts) {
      const val = await o.getAttribute('value');
      const text = (await o.textContent()).trim();
      if (val && val !== '-1') buRooms.push({ id: val, name: text });
    }

    const hid = hotelMap[vid] || 0;
    results[vid] = { hotelId: hid, ratePlans, rooms: buRooms };

    const rpSummary = ratePlans.map(r => `${r.code}=${r.name}`).join(', ');
    const roomSummary = buRooms.map(r => r.name).join(', ');
    console.log(`Venue ${vid} (Hotel ${hid}): RatePlans=[${rpSummary}] | Rooms=[${roomSummary}]`);

    // Generate SQL
    if (ratePlans.length > 0 && buRooms.length > 0) {
      sqlLines.push(`-- Venue ${vid} (HotelId=${hid})`);
      sqlLines.push(`DELETE FROM Med_Hotels_ratebycat WHERE HotelId = ${hid};`);

      // Map room names to CategoryId
      const catMap = (name) => {
        const n = name.toLowerCase();
        if (n.includes('suite')) return { id: 12, code: 'Suite' };
        if (n.includes('deluxe') || n.includes('dlx') || n.includes('exec')) return { id: 4, code: 'DLX' };
        if (n.includes('superior') || n.includes('spr')) return { id: 2, code: 'SPR' };
        return { id: 1, code: 'Stnd' };
      };

      // Map rate plan names to BoardId
      const boardMap = (name) => {
        const n = name.toLowerCase();
        if (n.includes('breakfast') || n.includes('bb')) return 2;
        return 1; // RO, Refundable, room only
      };

      for (const rp of ratePlans) {
        const boardId = boardMap(rp.name);
        for (const room of buRooms) {
          const cat = catMap(room.name);
          sqlLines.push(`INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (${hid}, ${boardId}, ${cat.id}, '${rp.code}', '${cat.code}');`);
        }
      }
      sqlLines.push('');
    }
  }

  // Save results
  fs.mkdirSync('data/reports', { recursive: true });
  fs.writeFileSync(`data/reports/all_rate_plans_${Date.now()}.json`, JSON.stringify(results, null, 2));
  fs.writeFileSync(`scripts/fix_ratebycat_discovered.sql`, 
    `-- Auto-discovered from Hotel.Tools Rate Calendar\n-- Date: ${new Date().toISOString()}\n-- Venues: ${ALL_VENUES.length}\n\n` + sqlLines.join('\n'));

  console.log(`\nSaved SQL: scripts/fix_ratebycat_discovered.sql`);
  console.log(`Saved JSON: data/reports/all_rate_plans_*.json`);

  await browser.close();
}
main().catch(console.error);
