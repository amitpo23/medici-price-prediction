# Browser Price Check — Skill Definition

## Purpose
Scan Innstant B2B to verify **Knowaa_Global_zenith** competitive position:
1. Are we listed?
2. Are we the cheapest?
3. Who beats us and by how much?

**Schedule:** Every 8 hours | **Source of truth:** `SalesOffice.Orders` (NOT Details)

## Key Principles
- **Orders = what to scan** (hotels + dates configured for scanning)
- **Details = API scan results** (output of the other developer's scanner)
- **This skill = browser scan** (independent verification via Innstant B2B)
- **Filter: Refundable only** (skip Non-Refundable offers)
- **All room types** (Standard, Deluxe, Suite, Superior, Apartment)
- **All boards** (RO + BB)
- **Our provider name:** `Knowaa_Global_zenith`

---

## Pipeline Steps

### Step 0: Get Active Orders from DB
```sql
-- Via medici-db MCP — this defines WHAT to scan and WHEN
SELECT DISTINCT o.DestinationId AS InnstantId, h.name, h.Innstant_ZenithId AS VenueId,
       o.DateFrom, o.DateTo
FROM [SalesOffice.Orders] o
JOIN Med_Hotels h ON h.InnstantId = o.DestinationId
WHERE h.isActive = 1 AND h.Innstant_ZenithId >= 5000 AND o.IsActive = 1
ORDER BY h.name
```
This returns ~55 Miami hotels with their scan dates (currently Apr 20-21, 2026).

### Step 1: Navigate to Innstant B2B
- Already logged in as `amit (Knowaa)` — session persists
- If not logged in: account=`amit`, user=`amit`, password=`Knowaa2024!`

### Step 2: Scan Each Hotel
For each hotel from Step 0, navigate to hotel detail page:
```
URL: https://b2b.innstant.travel/hotel/{slug}-{InnstantId}?service=hotels&searchQuery=hotel-{InnstantId}&startDate={DateFrom}&endDate={DateTo}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=
```

Wait for `.search-result-item` selector (15s timeout), then extract:

```javascript
// CSS selectors:
// .search-result-item         = hotel card (contains category)
// .search-result-item-sub-section = individual room offer
// .provider-label             = supplier name (span)
// h4                          = price
// Skip if text contains "non-refundable" (case insensitive)
// Board: BB if text contains "BB" or "breakfast", else RO
// Category: first line of .small-4/.medium-3 text
```

### Step 3: Classify Results
For each hotel, determine:
- `knowaaPresent`: boolean — does Knowaa_Global_zenith appear?
- `knowaaIsCheapest`: boolean — is our price <= all others?
- `knowaaRank`: integer — position among all offers sorted by price
- `cheapestByProvider`: object — lowest price per provider
- `categories`: which room types available
- `boards`: which meal plans available

### Step 4: Save Report
Save to `scan-reports/YYYY-MM-DD_HH-MM_full_scan.md` with tables:
- **Section A:** Hotels where Knowaa is #1 (cheapest)
- **Section B:** Hotels where Knowaa is #2
- **Section C:** Hotels where Knowaa is #3+
- **Section D:** Hotels where Knowaa is NOT listed (others have offers)
- **Section E:** Hotels with NO refundable offers at all

### Step 5: Write JSON to scan-reports/
```json
{
  "scanDate": "2026-03-31",
  "scanTime": "07:20:00",
  "ordersDateFrom": "2026-04-20",
  "ordersDateTo": "2026-04-21",
  "source": "innstant_b2b_browser",
  "totalHotelsInOrders": 55,
  "results": [
    {
      "hotelId": 66737,
      "venueId": 5113,
      "name": "Cavalier Hotel",
      "knowaaPresent": true,
      "knowaaIsCheapest": false,
      "knowaaRank": 3,
      "knowaaPrice": 200.00,
      "cheapestPrice": 197.93,
      "cheapestProvider": "InnstantTravel",
      "categories": ["Standard", "Deluxe"],
      "boards": ["RO"],
      "providers": ["InnstantTravel", "Knowaa_Global_zenith", "goglobal"]
    }
  ]
}
```

### Step 6: Share Reports via GitHub (MANDATORY)
**After every scan**, copy reports to `shared-reports/` and push to GitHub:
```bash
cp scan-reports/YYYY-MM-DD_*.md shared-reports/
cp scan-reports/YYYY-MM-DD_*.json shared-reports/
git add shared-reports/ && git commit -m "chore: scan report YYYY-MM-DD" && git push
```
The partner project (medici-hotels, on a different machine) reads via GitHub raw URL:
```
https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/
```

### Step 7: Optional — Write to DB
```bash
python3 scripts/browser_to_db.py scan-reports/YYYY-MM-DD_HH-MM.json
```

---

## Schedule: Every 8 Hours
- Runs at 00:00, 08:00, 16:00 UTC
- Uses dates from current SalesOffice.Orders
- Batches: 3 × ~19 hotels (to avoid browser timeout)
- ~17 seconds per hotel = ~16 minutes total scan time

## Batch Execution
Split 55 hotels into 3 batches using `browser_run_code`:
```javascript
async (page) => {
  for (const hotel of batch) {
    await page.goto(hotelUrl);
    await page.waitForSelector('.search-result-item', {timeout: 15000});
    await page.waitForTimeout(2000);
    const data = await page.evaluate(extractFunction);
    results.push(data);
  }
  return results;
}
```

## Credentials
| System | Account | User | Password |
|--------|---------|------|----------|
| Innstant B2B | amit | amit | Knowaa2024! |
| medici-db | — | prediction_reader | (in MEDICI_DB_URL) |

## Benchmarks (from 2026-03-31 scan)
| Metric | Value |
|--------|-------|
| Hotels in Orders | 55 |
| Knowaa appears | 16 (29%) |
| Knowaa #1 | 7 (13%) |
| Knowaa #2 | 6 (11%) |
| Not listed | 24 (44%) |
| No refundable offers | 15 (27%) |
