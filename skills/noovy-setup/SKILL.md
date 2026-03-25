# Noovy Setup & Gap Remediation Skill

## Purpose
Diagnose and fix missing Noovy/Hotel.Tools configurations that prevent hotels from appearing in B2B Innstant search results via Knowaa_Global_zenith.

The skill performs 3 phases:
1. **Diagnose** — Query DB + Innstant to find gaps
2. **Plan** — Generate exact Noovy UI steps to fix each gap
3. **Execute** — Perform the fixes in Noovy via Playwright

## When to Use
- A hotel has SalesOffice orders but no Knowaa results in Innstant
- Onboarding new hotels to Noovy/Hotel.Tools
- Verifying existing hotel configurations are complete
- Setting availability/pricing for test dates across multiple hotels

## Prerequisites
- Noovy login: Account `Medici LIVE`, User `zvi`, Password `karpad66`
- Innstant login: Account `Knowaa`, Agent `Amit`, Password `porat10`
- Azure SQL access via `MEDICI_DB_URL` or `sqlcmd`
- Playwright MCP configured

## Phase 1: Diagnose — Find Gaps

### Step 1.1: Get Active Hotels from DB

Query SalesOffice to find which hotels have active scans:

```sql
SELECT DISTINCT
    d.HotelId,
    COUNT(*) as detail_count,
    MIN(d.RoomPrice) as min_price,
    MAX(d.RoomPrice) as max_price
FROM [SalesOffice.Details] d
WHERE d.IsDeleted = 0
GROUP BY d.HotelId
ORDER BY detail_count DESC
```

### Step 1.2: Get Zenith Mapping Status

Check which hotels have proper Zenith mapping:

```sql
SELECT
    h.HotelId,
    h.HotelName,
    h.Innstant_ZenithId,
    h.isActive,
    COUNT(r.Id) as ratebycat_count
FROM Med_Hotels h
LEFT JOIN Med_Hotels_ratebycat r ON h.HotelId = r.HotelId
WHERE h.HotelId IN ({hotel_ids_from_step_1})
GROUP BY h.HotelId, h.HotelName, h.Innstant_ZenithId, h.isActive
ORDER BY h.HotelName
```

### Step 1.3: Get Occupancy Breakdown

Check what bedding types exist per hotel:

```sql
SELECT
    d.HotelId,
    CASE
        WHEN d.RoomCode LIKE '%:single:%' THEN 'single'
        WHEN d.RoomCode LIKE '%:double:%' THEN 'double'
        WHEN d.RoomCode LIKE '%:twin:%' THEN 'twin'
        WHEN d.RoomCode LIKE '%:triple:%' THEN 'triple'
        WHEN d.RoomCode LIKE '%:quadruple:%' THEN 'quadruple'
        ELSE 'other'
    END as bedding,
    d.RoomCategory,
    d.RoomBoard,
    COUNT(*) as cnt
FROM [SalesOffice.Details] d
WHERE d.IsDeleted = 0
GROUP BY d.HotelId,
    CASE WHEN d.RoomCode LIKE '%:single:%' THEN 'single'
         WHEN d.RoomCode LIKE '%:double:%' THEN 'double'
         WHEN d.RoomCode LIKE '%:twin:%' THEN 'twin'
         WHEN d.RoomCode LIKE '%:triple:%' THEN 'triple'
         WHEN d.RoomCode LIKE '%:quadruple:%' THEN 'quadruple'
         ELSE 'other' END,
    d.RoomCategory, d.RoomBoard
ORDER BY d.HotelId, bedding
```

### Step 1.4: Check Knowaa Results in Innstant

For each hotel, search B2B Innstant and count Knowaa_Global_zenith results:

```
URL: https://b2b.innstant.travel/hotel/{slug}-{hotelId}?service=hotels&searchQuery=hotel-{hotelId}&startDate={date}&endDate={date+1}&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=
```

Count provider entries in results. Look for `Provider: Knowaa_Global_zenith`.

### Step 1.5: Generate Gap Report

For each hotel, classify the gap:

| Gap Type | Symptom | Root Cause |
|----------|---------|------------|
| **NO_VENUE** | Hotel not in Noovy at all | Need to create venue |
| **NO_PRODUCTS** | Venue exists, 0 products | Need to create products (Standard, Deluxe, Suite) |
| **NO_RATE_PLANS** | Products exist, no rate plans | Need to add RO/BB rate plans |
| **NO_CHANNEL** | Rate plans exist, Innstant not connected | Need to enable Innstant channel |
| **NO_AVAILABILITY** | Channel connected, 0 availability | Need to set availability via Bulk Update |
| **NO_MAPPING** | Innstant connected but ZenithId wrong | Need to fix Med_Hotels.Innstant_ZenithId |
| **CALLBACK_STUCK** | Mapping OK but 0 Details | Callback processor not running |

## Phase 2: Plan — Generate Fix Instructions

For each hotel with gaps, generate specific instructions:

### Fix: NO_AVAILABILITY (most common)

```
Hotel: {name} (Venue #{venue_id})
Action: Set availability and price for date range
Steps:
  1. Noovy → Select venue #{venue_id} from hotel dropdown
  2. Go to Rates (sidebar)
  3. Click Bulk Update
  4. ROOMS: Standard (or first available product)
  5. RATE PLANS: Bed and Breakfast (or first available)
  6. DATE RANGE: {start_date} to {end_date}
  7. RATE UPDATE: Fixed → ${price}
  8. AVAILABILITY UPDATE: Fixed → {count}
  9. Save
  10. Verify: "Bulk update product successfully"
```

### Fix: NO_CHANNEL

```
Hotel: {name} (Venue #{venue_id})
Action: Enable Innstant Travel channel
Steps:
  1. Hotel.Tools → Marketplace
  2. Find "Innstant Travel"
  3. Click Setup → Enable → Submit
  4. Verify status: Connected
```

### Fix: NO_PRODUCTS

```
Hotel: {name} (Venue #{venue_id})
Action: Create products and rate plans
Steps:
  1. Noovy → Settings → Products
  2. Click "Add Product"
  3. Name: "Standard" | Type: Room | Occupancy: 2
  4. Save
  5. Click "Add Rate Plan" on the product
  6. Name: "Room Only" | Code: RO
  7. Save
  8. Repeat for BB (Bed and Breakfast)
  9. Repeat for other categories if needed (Deluxe, Suite)
```

## Phase 3: Execute — Noovy Bulk Update via Playwright

### Automated Bulk Update Flow

For each hotel that needs availability:

```python
# Pseudocode for Playwright automation
for venue_id in venues_to_update:
    # 1. Switch venue
    navigate_to('https://app.noovy.com/pricing-availability/rateCalendar')
    click(hotel_dropdown)
    type(venue_name_or_id)
    select_venue()
    wait_for_calendar()

    # 2. Open Bulk Update
    click('Bulk Update')

    # 3. Set date range
    click(date_range_input)
    navigate_calendar_to(target_month)  # click Next month N times
    click(start_day)
    click(end_day)

    # 4. Set rate
    click(rate_update_dropdown)
    select('Fixed')
    type(price, in: rate_input)

    # 5. Set availability
    click(availability_dropdown)
    select('Fixed')
    type(count, in: availability_input)

    # 6. Save
    click('Save')
    wait_for('Bulk update product successfully')
```

### Noovy UI Element References

| Element | Selector / Approach |
|---------|-------------------|
| Hotel dropdown | Sidebar → bottom → combobox "Hotel" → click "Open" button |
| Rates page | Sidebar → link with `/pricing-availability` URL |
| Bulk Update button | `[data-test-id="pricing-availability-bulk-update-button"]` |
| Date range input | textbox with placeholder "DD/MM/YY – DD/MM/YY" |
| Next month | button "Next month" in date picker tooltip |
| Rate Update | combobox "RATE UPDATE" → options: No, Variable, Fixed |
| Price input | textbox after Rate Update = Fixed ($ prefix) |
| Availability Update | combobox "AVAILABILITY UPDATE" → options: No, Variable, Fixed, Reset, No Availability, Close Sale, Open Sale |
| Availability input | textbox after Availability Update = Fixed |
| Save button | button "Save" in dialog footer |
| Close dialog | `[data-test-id="rates-bulk-update-modal-close-button"]` |
| Success toast | alert containing "Bulk update product successfully" |

### Calendar Navigation

From current month to target month:
- March → August = 5 clicks on "Next month"
- Each click in date picker advances 1 month
- After reaching target month, click start day, then end day

### Switching Venues

To switch hotel in Noovy:
1. Click hotel name in sidebar (shows current venue name)
2. Or find the combobox labeled "Hotel" in the bottom of sidebar
3. Click "Open" or "Clear" to reset
4. Type hotel name → select from dropdown
5. Wait for page to reload with new venue data
6. Continue with Bulk Update

**Important**: The GraphQL API is venue-scoped. API calls only work for the currently selected venue. You cannot bulk-update multiple venues without switching between them.

## Noovy GraphQL API Reference

### Bulk Update Mutation

```graphql
mutation (
  $venueId: ID!
  $productIds: [ID!]!
  $rateIds: [ID]
  $weekdays: [dayOfWeekEnum]!
  $dateRanges: [bulkUpdateDateRange]!
  $changes: bulkUpdateChanges!
) {
  bulkUpdatePriceAndAvailability(
    venueId: $venueId
    productIds: $productIds
    rateIds: $rateIds
    weekdays: $weekdays
    dateRanges: $dateRanges
    changes: $changes
  ) {
    operationId
  }
}
```

Variables:
```json
{
  "venueId": "5113",
  "productIds": ["p.68c595033c719"],
  "rateIds": ["12866"],
  "weekdays": ["mon","tue","wed","thu","fri","sat","sun"],
  "dateRanges": [{"start": "2026-08-01", "end": "2026-08-10"}],
  "changes": {
    "price": {"operationType": "fixed", "amount": 1000},
    "availability": {"operationType": "fixed", "amount": 1}
  }
}
```

**Note**: `productIds` and `rateIds` are venue-specific. Get them from the `getPriceAndAvailability` query or the Bulk Update status query.

### Check Bulk Update Status

```graphql
query BulkUpdateStatusType($venueId: ID!) {
  bulkUpdateStatusType(venueId: $venueId) {
    status
    operationId
    rateIds
    productIds
    dateRanges { start end }
  }
}
```

### Endpoint

```
POST https://app.noovy.com/graphql/api
Cookie: token={session_token}; hotelId={venue_id}
Content-Type: application/json
```

## Gotchas

- [2026-03-25] Noovy GraphQL returns 403 "Operation not allowed" when productIds is empty; rule: Always include specific productIds and rateIds from the venue
- [2026-03-25] dayOfWeekEnum values are lowercase ("mon" not "MONDAY"); rule: Use lowercase weekday names
- [2026-03-25] changes.price requires "amount" field not "value"; rule: Use {operationType: "fixed", amount: X}
- [2026-03-25] Cannot query venues you haven't selected in the UI session; rule: Switch venue via UI before making API calls
- [2026-03-16] Hotel.Tools product creation API returns HTTP 500 for batch operations; rule: Create products manually through UI, not API
- [2026-03-16] Noovy auth degrades to "No Venue" after extended session; rule: Re-login if GraphQL returns 401
- [2026-03-16] Availability must be set to ≥1 for Innstant to show rooms; rule: Always set availability after configuring products/rates
- [2026-03-25] WebJob always searches adults:2 only; rule: Manual Innstant search needed to verify single/triple/family availability
