# Scan Reports Reader — Skill Definition

## Purpose
Read Knowaa competitive scan reports from the medici-price-prediction project.
These reports show where Knowaa_Global_zenith appears on Innstant B2B, whether we're the cheapest, and where we're missing.

## How Reports Are Generated
An automated Node.js script (`scripts/browser_scan.js`) scans all ~55 Knowaa hotels on Innstant B2B every 8 hours. It runs via:
- **GitHub Actions** — `.github/workflows/browser-scan.yml` (cron: every 8h)
- **Local crontab** — `node scripts/browser_scan.js` (backup)

Reports are pushed to `shared-reports/` on GitHub after every scan.

---

## How To Fetch Reports

### Option 1: GitHub Raw URL (Fastest)

**Latest Markdown report:**
```bash
# Auto-detect latest report filename
LATEST=$(curl -s https://api.github.com/repos/amitpo23/medici-price-prediction/contents/shared-reports | \
  python3 -c "import sys,json; files=[f['name'] for f in json.load(sys.stdin) if f['name'].endswith('_hotels_report.md')]; print(sorted(files)[-1] if files else '')")
curl -s "https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/$LATEST"
```

**Latest JSON report:**
```bash
LATEST=$(curl -s https://api.github.com/repos/amitpo23/medici-price-prediction/contents/shared-reports | \
  python3 -c "import sys,json; files=[f['name'] for f in json.load(sys.stdin) if f['name'].endswith('_full_scan.json')]; print(sorted(files)[-1] if files else '')")
curl -s "https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/$LATEST"
```

**Specific date report:**
```bash
curl -s https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/2026-04-01_full_55_hotels_report.md
```

**List all available reports:**
```bash
curl -s https://api.github.com/repos/amitpo23/medici-price-prediction/contents/shared-reports | \
  python3 -c "import sys,json; [print(f['name']) for f in json.load(sys.stdin)]"
```

### Option 2: Database Query (Structured)

Scan results are also written to `SalesOffice.BrowserScanResults`:
```sql
-- Latest scan summary per hotel
SELECT HotelName, VenueId, Provider, Price, IsKnowaa, KnowaaRank, ScanDate
FROM SalesOffice.BrowserScanResults
WHERE ScanDate = (SELECT MAX(ScanDate) FROM SalesOffice.BrowserScanResults)
ORDER BY HotelName, Price

-- Knowaa competitive position over time
SELECT CAST(ScanDate AS DATE) AS ScanDay,
       COUNT(DISTINCT CASE WHEN IsKnowaa = 1 THEN VenueId END) AS KnowaaHotels,
       COUNT(DISTINCT CASE WHEN IsKnowaa = 1 AND KnowaaRank = 1 THEN VenueId END) AS KnowaaFirst,
       COUNT(DISTINCT VenueId) AS TotalHotels
FROM SalesOffice.BrowserScanResults
GROUP BY CAST(ScanDate AS DATE)
ORDER BY ScanDay DESC

-- Connection: UID=agent_scanner; PWD=Ag3ntSc@n2026Med1c1!
```

---

## Report Structure

### Markdown Report (5 sections)

| Section | Description |
|---------|-------------|
| **Summary** | Totals: scanned, Knowaa appears, #1, not listed, no offers |
| **A** | Hotels where Knowaa is #1 (cheapest) — with gap to 2nd |
| **B** | Hotels where Knowaa listed but not cheapest — with rank + gap |
| **C** | Hotels with offers from others but NOT from Knowaa |
| **D** | Hotels with no refundable offers at all |

### JSON Report Schema
```json
{
  "scanDate": "2026-04-01",
  "scanTime": "06:31:00",
  "searchDates": { "checkIn": "2026-04-20", "checkOut": "2026-04-21" },
  "source": "innstant_b2b_browser",
  "totalHotelsScanned": 55,
  "summary": {
    "knowaaAppears": 17,
    "knowaaFirst": 10,
    "notListed": 21,
    "noOffers": 12
  },
  "hotels": [
    {
      "hotelId": 66737,
      "venueId": 5113,
      "name": "Cavalier Hotel",
      "knowaaPresent": true,
      "knowaaIsCheapest": true,
      "knowaaRank": 1,
      "knowaaPrice": 100.03,
      "cheapestPrice": 100.03,
      "cheapestProvider": "Knowaa_Global_zenith",
      "categories": ["Standard", "Deluxe"],
      "boards": ["RO"],
      "providers": ["Knowaa_Global_zenith", "InnstantTravel", "goglobal"],
      "offers": [
        { "category": "Standard", "board": "RO", "price": 100.03, "provider": "Knowaa_Global_zenith" }
      ]
    }
  ]
}
```

---

## Schedule
New reports are pushed approximately every 8 hours by GitHub Actions.
File naming: `YYYY-MM-DD_HH-MM_full_scan.json` / `YYYY-MM-DD_full_NN_hotels_report.md`

## When To Use
- When asked about Knowaa competitive position
- When checking if we appear on Innstant for a specific hotel
- When comparing our prices vs competitors
- When investigating why a hotel has no Knowaa offers
- Before/after price pushes to verify visibility
- When tracking competitive position trends over time
