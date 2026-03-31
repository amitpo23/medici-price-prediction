# Agent API — Browser Price Scan Guide

## Overview
This document describes the automated browser scanning pipeline for hotel price verification. An AI agent uses Playwright MCP to scan Innstant B2B, captures live pricing, writes to DB, and compares against API data.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌─────────────┐
│ medici-db    │────>│ Agent scans  │────>│ scan-reports/  │────>│ BrowserScan │
│ (hotel list) │     │ Innstant B2B │     │ JSON + MD      │     │ Results DB  │
└─────────────┘     └──────────────┘     └───────────────┘     └─────────────┘
                                                                       │
                    ┌──────────────┐     ┌───────────────┐            │
                    │ SalesOffice  │────>│ compare_api_  │<───────────┘
                    │ .Details     │     │ vs_browser.py │
                    └──────────────┘     └───────────────┘
```

## Quick Start

### 1. Get Hotel List
```sql
-- Via medici-db MCP:
SELECT h.Id AS VenueId, h.Name, o.HotelId AS InnstantHotelId
FROM Med_Hotels h
JOIN SalesOffice.Orders o ON o.VenueId = h.Id
WHERE h.isActive = 1
GROUP BY h.Id, h.Name, o.HotelId
```

### 2. Scan Innstant B2B (Playwright MCP)
```
browser_navigate → https://b2b.innstant.travel
Login: account=amit, user=amit, password=Knowaa2024!
Search: Miami, dates: +30 days, 2 nights, 2 adults
For each hotel: capture offers (category, board, price, provider)
```

### 3. Save Results
Save JSON to `scan-reports/YYYY-MM-DD_HH-MM.json`

### 4. Write to DB
```bash
python3 scripts/browser_to_db.py scan-reports/YYYY-MM-DD_HH-MM.json
# Add --dry-run to preview without writing
```

### 5. Compare Prices
```bash
python3 scripts/compare_api_vs_browser.py
```

### 6. Verify
```sql
SELECT TOP 10 * FROM SalesOffice.BrowserScanResults ORDER BY ScanDate DESC
```

## Credentials

| System | Account | User | Password |
|--------|---------|------|----------|
| Innstant B2B | amit | amit | Knowaa2024! |
| Noovy PMS | Medici LIVE | zvi | karpad66 |
| medici-db | — | prediction_reader | (in MEDICI_DB_URL) |

## DB Schema: BrowserScanResults

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
| Currency | NVARCHAR(10) | Currency |
| Provider | NVARCHAR(100) | Supplier |
| Nights | INT | Number of nights |

## Hotel Venue IDs (28 New Miami Hotels)

| Hotel | VenueId | InnstantId |
|-------|---------|------------|
| Cavalier | 5113 | — |
| citizenM | 5119 | — |
| Dorchester | 5266 | — |
| DoubleTree | 5082 | — |
| Fontainebleau | 5268 | — |
| Gale Miami | 5278 | — |
| Gale South Beach | 5267 | — |
| Generator | 5274 | — |
| Grand Beach | 5124 | — |
| Hilton Cabana | 5115 | — |
| Hilton Garden | 5279 | — |
| Hilton Airport | 5083 | — |
| Holiday Inn | 5130 | — |
| Belleza | 5265 | — |
| Chelsea | 5064 | — |
| Croydon | 5131 | — |
| Gaythering | 5132 | — |
| InterContinental | 5276 | — |
| Kimpton Anglers | 5136 | — |
| Kimpton Palomar | 5116 | — |
| Loews | 5073 | — |
| Metropole | 5141 | — |
| Miami Airport | 5275 | — |
| SERENA | 5139 | — |
| Albion | 5117 | — |
| Catalina | 5277 | — |
| Gates | 5140 | — |
| Landon | 5138 | — |
| Villa Casa | 5075 | — |

## Comparison Output Example
```
======================================================================
BROWSER vs API PRICE COMPARISON
======================================================================
Browser offers: 156
API offers:     142
Matches (<5%):  118 (75.6%)
Discrepancies:  24 (avg 12.3% off)
Missing in API: 14

--- DISCREPANCIES (>5% difference) ---
  Fontainebleau                Deluxe       BB   Browser $  285.00 vs API $  245.00 (16.3% HIGHER)
  Hilton Cabana                Standard     RO   Browser $  142.00 vs API $  165.00 (13.9% LOWER)
```

## Troubleshooting
- **Innstant login fails**: Check if b2b.innstant.travel is accessible, credentials may have changed
- **No offers found**: Search date may be too close (use +30 days minimum)
- **DB write fails**: Ensure prediction_reader has INSERT permission on SalesOffice schema
- **Table doesn't exist**: browser_to_db.py auto-creates the table on first run
