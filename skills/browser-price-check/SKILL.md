# Browser Price Check — Skill Definition

## Purpose
Scan Innstant B2B to verify **Knowaa_Global_zenith** competitive position:
1. Are we listed?
2. Are we the cheapest?
3. Who beats us and by how much?

**Schedule:** Every 8 hours via Claude Remote Trigger
**Source of truth:** `SalesOffice.Orders` (NOT Details)

## Key Principles
- **Orders = what to scan** (hotels + dates configured for scanning)
- **Details = API scan results** (output of the other developer's scanner)
- **This skill = browser scan** (independent verification via Innstant B2B)
- **Filter: Refundable only** (skip Non-Refundable offers)
- **All room types** (Standard, Deluxe, Suite, Superior, Apartment)
- **All boards** (RO + BB)
- **Our provider name:** `Knowaa_Global_zenith`

## Resilience
- **Browser crash recovery:** If browser/page closes mid-scan, auto-relaunches and retries up to 3 times per hotel
- **Graceful skip:** After 3 failed attempts, marks hotel as `error: scan_failed` and continues to next hotel
- **No full crash:** A single hotel failure never kills the entire 55-hotel scan

---

## How To Run

### Automated (Primary — Remote Trigger)
Claude Remote Trigger runs every 8 hours from the local machine.

| Setting | Value |
|---------|-------|
| Trigger ID | `trig_01CAWRdQb2m57Y8MLHcb5mKg` |
| Schedule | `0 */8 * * *` (00:00, 08:00, 16:00 UTC) |
| Model | claude-sonnet-4-6 |

### Local Script
```bash
# Full scan (DB + git push)
node scripts/browser_scan.js

# Dry run (no DB, no push)
node scripts/browser_scan.js --dry-run

# Scan + push, skip DB
node scripts/browser_scan.js --no-db

# npm shortcuts
npm run scan
npm run scan:dry
npm run scan:no-db
```

### Cross-Agent Report Access
Other agents fetch the latest report via GitHub raw URL:
```bash
curl -s https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/2026-04-01_full_55_hotels_report.md
```

---

## Pipeline Steps (inside browser_scan.js)

### Step 0: Get Active Orders from DB
```sql
SELECT DISTINCT o.DestinationId AS InnstantId, h.name, h.Innstant_ZenithId AS VenueId,
       o.DateFrom, o.DateTo
FROM [SalesOffice].[Orders] o
JOIN Med_Hotels h ON h.InnstantId = o.DestinationId
WHERE h.isActive = 1 AND h.Innstant_ZenithId >= 5000 AND o.IsActive = 1
ORDER BY h.name
```

### Step 1: Login to Innstant B2B
- Credentials from env vars: `INNSTANT_USER`, `INNSTANT_PASS`, `INNSTANT_ACCOUNT`
- Auto-detects if already logged in

### Step 2: Scan Each Hotel
URL pattern: `https://b2b.innstant.travel/hotel/{slug}-{InnstantId}?...`
- Extracts via CSS selectors: `.search-result-item`, `.provider-label`, `h4` (price)
- Skips non-refundable offers
- ~8 seconds per hotel, ~16 minutes total for 55 hotels
- **Crash recovery:** if browser dies mid-scan, relaunches + retries up to 3 times per hotel

### Step 3: Classify & Report
- JSON report → `scan-reports/` + `shared-reports/`
- Markdown report → same directories
- Sections: A (#1), B (listed not cheapest), C (not listed), D (no offers)

### Step 4: Write to DB
- Table: `SalesOffice.BrowserScanResults`
- User: `agent_scanner` (env: `SCAN_DB_USER`, `SCAN_DB_PASS`)
- Includes `IsKnowaa` bit + `KnowaaRank` columns

### Step 5: Git Push
- Commits `shared-reports/` + `scan-reports/` → pushes to GitHub
- Partner project reads via: `https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/`

---

## Environment Variables

| Variable | Default | Required |
|----------|---------|----------|
| `INNSTANT_USER` | amit | Yes |
| `INNSTANT_PASS` | — | Yes |
| `INNSTANT_ACCOUNT` | amit | No |
| `SOURCE_DB_SERVER` | medici-sql-server.database.windows.net | No |
| `SOURCE_DB_NAME` | medici-db | No |
| `SOURCE_DB_USER` | prediction_reader | No |
| `SOURCE_DB_PASS` | — | Yes |
| `SCAN_DB_SERVER` | (same as SOURCE) | No |
| `SCAN_DB_NAME` | (same as SOURCE) | No |
| `SCAN_DB_USER` | agent_scanner | No |
| `SCAN_DB_PASS` | — | For DB write |

---

## Benchmarks (2026-04-01)
| Metric | Value |
|--------|-------|
| Hotels in Orders | 55 |
| Knowaa appears | 17 (31%) |
| Knowaa #1 | 10 (18%) |
| Not listed | 21 (38%) |
| No refundable offers | 12 (22%) |
| Scan time | ~16 minutes |
