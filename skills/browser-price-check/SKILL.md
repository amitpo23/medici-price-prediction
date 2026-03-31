# Browser Price Check — Skill Definition

## Purpose
Scan Innstant B2B portal via browser automation (Playwright MCP) to capture live hotel pricing, then compare against our API/DB prices to find discrepancies.

## Pipeline Steps

### Step 0: Query Hotels from DB
```
Use medici-db MCP to get active hotels:
SELECT h.Id, h.Name, h.Innstant_ZenithId, o.HotelId AS InnstantHotelId
FROM Med_Hotels h
JOIN SalesOffice.Orders o ON o.VenueId = h.Id
WHERE h.isActive = 1
GROUP BY h.Id, h.Name, h.Innstant_ZenithId, o.HotelId
```

### Step 1: Navigate to Innstant B2B
1. `browser_navigate` → https://b2b.innstant.travel
2. Login: account=`amit`, user=`amit`, password=`Knowaa2024!`
3. Set search: Miami, check-in = tomorrow+30d, check-out = +2 nights, 2 adults

### Step 2: Scan Each Hotel
For each hotel from Step 0:
1. Search by hotel name or Innstant HotelId
2. `browser_snapshot` → capture room offers
3. Extract: room category, board (RO/BB), price, provider, currency
4. Record timestamp

### Step 3: Save Results
Save to `scan-reports/` as:
- `scan-reports/YYYY-MM-DD_HH-MM.json` — structured data
- `scan-reports/YYYY-MM-DD_HH-MM.md` — human-readable markdown

JSON structure:
```json
{
  "scanDate": "2026-03-30",
  "scanTime": "14:30:00",
  "searchDates": { "checkIn": "2026-05-01", "checkOut": "2026-05-03" },
  "source": "innstant_b2b_browser",
  "hotels": [
    {
      "hotelId": 6805,
      "venueId": 5080,
      "name": "Pullman Miami Airport",
      "offers": [
        {
          "category": "Standard",
          "board": "RO",
          "price": 145.00,
          "currency": "USD",
          "provider": "Knowaa_Global_zenith",
          "nights": 2
        }
      ]
    }
  ]
}
```

### Step 4: Write to DB
Run `python3 scripts/browser_to_db.py scan-reports/YYYY-MM-DD_HH-MM.json`

This writes each offer to `SalesOffice.BrowserScanResults`:
| Column | Type | Description |
|--------|------|-------------|
| Id | int (identity) | Auto PK |
| ScanDate | datetime | When scan was performed |
| CheckInDate | date | Search check-in date |
| CheckOutDate | date | Search check-out date |
| VenueId | int | Noovy venue ID |
| HotelId | int | Innstant hotel ID |
| HotelName | nvarchar(200) | Hotel name |
| Category | nvarchar(100) | Room category (Standard, Deluxe, etc.) |
| Board | nvarchar(50) | Meal plan (RO, BB) |
| Price | decimal(10,2) | Total price |
| PricePerNight | decimal(10,2) | Price / nights |
| Currency | nvarchar(10) | Currency code |
| Provider | nvarchar(100) | OTA/supplier name |
| Nights | int | Number of nights |

### Step 5: Compare API vs Browser
Run `python3 scripts/compare_api_vs_browser.py`

Compares latest browser scan against:
- SalesOffice.Details (our current API prices)
- Forward curve predictions
- Outputs discrepancy report

### Step 6: Verify
```sql
SELECT TOP 10 * FROM SalesOffice.BrowserScanResults ORDER BY ScanDate DESC
```

## Credentials
- Innstant B2B: account=`amit`, user=`amit`, password=`Knowaa2024!`
- DB: Uses `prediction_reader` credentials from MEDICI_DB_URL

## When to Use
- Daily price verification
- Before/after Zenith push cycles
- When investigating price discrepancies
- Validating Innstant static data sync
