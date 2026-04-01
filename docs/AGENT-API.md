# Browser Price Scan — Documentation

## Overview

Automated browser scanning pipeline for hotel price verification on Innstant B2B.
Checks **Knowaa_Global_zenith** competitive position across 55 Miami hotels.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ SalesOffice     │     │ Claude Remote    │     │ shared-reports/  │
│ .Orders (DB)    │────>│ Trigger Agent    │────>│ (GitHub repo)    │
│ 55 active hotels│     │ every 8 hours    │     │ JSON + Markdown  │
└─────────────────┘     └─────────────────┘     └────────┬─────────┘
                               │                          │
                        ┌──────▼──────┐          ┌────────▼──────────────┐
                        │ Playwright  │          │ Other agents fetch:   │
                        │ MCP scans   │          │ curl -s raw.github... │
                        │ Innstant B2B│          │ /shared-reports/...md │
                        └─────────────┘          └───────────────────────┘
```

## Scanning Methods

### 1. Remote Trigger (Primary — Active)

Claude Code Remote Trigger runs every 8 hours from the local machine.

| Setting | Value |
|---------|-------|
| Trigger ID | `trig_01CAWRdQb2m57Y8MLHcb5mKg` |
| Schedule | `0 */8 * * *` (00:00, 08:00, 16:00 UTC) |
| Model | claude-sonnet-4-6 |
| Tools | Bash, Read, Write, Edit, Glob, Grep |
| Source | `https://github.com/amitpo23/medici-price-prediction` |
| Status | **Active** |

The agent:
1. Queries `SalesOffice.Orders` for active hotels
2. Scans Innstant B2B via Playwright MCP
3. Generates Markdown + JSON reports in `scan-reports/` + `shared-reports/`
4. Compares with previous scan for trends
5. Commits and pushes to GitHub

### 2. Standalone Node.js Script (Backup)

```bash
# Full scan (DB write + git push)
node scripts/browser_scan.js

# Dry run (no DB, no push)
node scripts/browser_scan.js --dry-run

# npm shortcuts
npm run scan
npm run scan:dry
```

**Status:** Works locally but requires DB credentials in `.env`. GitHub Actions workflow (`.github/workflows/browser-scan.yml`) exists but **fails** because `prediction_reader` lacks SELECT permission on `[SalesOffice.Orders]`.

### 3. Manual Playwright MCP Scan

Run interactively in Claude Code using Playwright MCP tools to scan Innstant B2B.

---

## Report Distribution

### Output Files

| File | Location | Purpose |
|------|----------|---------|
| `scan-reports/YYYY-MM-DD_full_NN_hotels_report.md` | Local + GitHub | Full Markdown report |
| `scan-reports/YYYY-MM-DD_HH-MM_full_scan.json` | Local + GitHub | Structured JSON data |
| `shared-reports/YYYY-MM-DD_full_NN_hotels_report.md` | Local + GitHub | **Cross-agent access point** |
| `shared-reports/YYYY-MM-DD_HH-MM_full_scan.json` | Local + GitHub | Cross-agent JSON |

### Cross-Agent Access

Other agents (e.g. `medici-hotels`) fetch the latest report via GitHub raw URL:

```bash
curl -s https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/2026-04-01_full_55_hotels_report.md
```

The URL pattern:
```
https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/{YYYY-MM-DD}_full_{N}_hotels_report.md
```

### Report Sections

| Section | Content |
|---------|---------|
| **A** | Knowaa is CHEAPEST (#1) — hotels where we beat all competitors |
| **B** | Knowaa listed but not cheapest — rank #2+ with gap amount |
| **C** | Knowaa NOT listed — competitors have offers, we don't |
| **D** | No refundable offers — no provider has refundable rooms |

---

## Scan Configuration

| Parameter | Value |
|-----------|-------|
| Hotels source | `SalesOffice.Orders` (IsActive=1, Innstant_ZenithId >= 5000) |
| Filter | Refundable only (skip Non-Refundable) |
| Room types | All (Standard, Deluxe, Suite, Superior, Apartment) |
| Boards | All (RO + BB) |
| Our provider name | `Knowaa_Global_zenith` |
| Batch size | 19 hotels per batch |
| Hotel timeout | 15 seconds |

## Innstant B2B Access

| Field | Value |
|-------|-------|
| URL | https://b2b.innstant.travel |
| Account | knowaa |
| Username | Amit |
| Password | porat10 |

Hotel page URL pattern:
```
https://b2b.innstant.travel/hotel/{slug}-{InnstantId}?service=hotels&searchQuery=hotel-{InnstantId}&startDate={DateFrom}&endDate={DateTo}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=
```

---

## Benchmarks

| Date | Hotels | Knowaa Appears | Knowaa #1 | Not Listed | No Offers |
|------|--------|---------------|-----------|------------|-----------|
| 2026-04-01 | 55 | 17 (31%) | 10 (18%) | 21 (38%) | 12 (22%) |
| 2026-03-31 | 55 | 16 (29%) | 7 (13%) | 24 (44%) | 15 (27%) |

---

## DB Schema: BrowserScanResults

Written by `scripts/browser_scan.js` (Step 6) when `--no-db` is not set.

| Column | Type | Description |
|--------|------|-------------|
| Id | INT IDENTITY | Primary key |
| ScanDate | DATETIME | When scan ran |
| CheckInDate | DATE | Search check-in |
| CheckOutDate | DATE | Search check-out |
| VenueId | INT | Noovy venue ID |
| HotelId | INT | Innstant hotel ID |
| HotelName | NVARCHAR(200) | Hotel name |
| Category | NVARCHAR(100) | Room category |
| Board | NVARCHAR(50) | Meal plan (RO/BB) |
| Price | DECIMAL(10,2) | Total price |
| PricePerNight | DECIMAL(10,2) | Per-night price |
| Currency | NVARCHAR(10) | Currency (USD) |
| Provider | NVARCHAR(100) | Supplier name |
| IsKnowaa | BIT | 1 if Knowaa provider |
| KnowaaRank | INT | Our rank (1=cheapest) |
| Nights | INT | Number of nights |
| CreatedAt | DATETIME | Row insert time |

DB user for writes: `agent_scanner` (env: `SCAN_DB_USER`, `SCAN_DB_PASS`)

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

## Known Issues

1. **GitHub Actions fails** — `prediction_reader` user lacks SELECT permission on `[SalesOffice.Orders]`. Fix: GRANT SELECT or use a different DB user in `SOURCE_DB_USER` secret.
2. **GitHub raw URL cache** — GitHub caches raw files for up to 5 minutes. After a push, the new report may take a few minutes to be available.
3. **Scan time** — Full 55-hotel scan takes ~16 minutes with Playwright.

## Troubleshooting

- **Innstant login fails**: Check credentials, b2b.innstant.travel may be down
- **No offers found**: Search date may be too close (use +30 days minimum)
- **DB write fails**: Ensure `agent_scanner` has INSERT permission on `SalesOffice.BrowserScanResults`
- **Report not updating on GitHub**: Check that the Remote Trigger is enabled and the machine is on
