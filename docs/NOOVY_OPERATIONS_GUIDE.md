# Noovy & Hotel.Tools — Operations Guide

Complete operational guide for managing hotel inventory through Noovy, Hotel.Tools, and B2B Innstant.

---

## 1. System Overview

```
Noovy (PMS)                    Hotel.Tools (Channel Manager)         B2B Innstant (Distribution)
app.noovy.com                  hotel.tools                           b2b.innstant.travel
    │                              │                                      │
    │ Products, Rates,             │ Zenith SOAP API                     │ Knowaa_Global_zenith
    │ Availability                 │ OTA_HotelRateAmountNotifRQ          │ (our supplier)
    │                              │ OTA_HotelAvailNotifRQ               │
    ▼                              ▼                                      ▼
┌─────────┐    Sync    ┌──────────────┐    Push    ┌──────────────────────┐
│  Noovy  │ ────────── │  Hotel.Tools │ ────────── │  Innstant Search     │
│  (PMS)  │            │  (Zenith CM) │            │  Results             │
└─────────┘            └──────────────┘            └──────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │   SalesOffice DB   │
                    │  (Azure SQL)       │
                    │  medici-db         │
                    └────────────────────┘
```

**Flow**: Noovy → Hotel.Tools → Innstant → SalesOffice scans → Medici Prediction

---

## 2. Credentials

### Noovy (PMS)
- **URL**: https://app.noovy.com
- **Account**: `Medici LIVE`
- **User**: `zvi`
- **Password**: `karpad66`

### Hotel.Tools / Zenith (Channel Manager)
- **URL**: https://hotel.tools
- **Same credentials as Noovy** (single sign-on via HotelRunner)
- **SOAP API**: https://hotel.tools/service/Medici%20new
- **SOAP Auth**: WS-Security UsernameToken
  - Username: `APIMedici:Medici Live`
  - Password: `Medici Live`

### B2B Innstant (Distribution)
- **URL**: https://b2b.innstant.travel
- **Account**: `Knowaa`
- **Agent**: `Amit`
- **Password**: `porat10`
- Shows as "amit (Knowaa)" when logged in

### Azure SQL (Medici DB)
- **Server**: `medici-sql-server.database.windows.net`
- **Database**: `medici-db`
- **Resource Group**: `Medici-RG`
- **Read user**: `prediction_reader`
- **Admin user**: `medici_sql_admin`

---

## 3. Hotel Inventory — Full List

### 30 Hotels with Noovy Venue IDs

| # | Hotel Name | Innstant HotelId | Zenith VenueId |
|---|------------|------------------|----------------|
| 1 | Cavalier Hotel | 66737 | 5113 |
| 2 | citizenM Miami South Beach | 854710 | 5119 |
| 3 | Dorchester Hotel | 6654 | 5266 |
| 4 | DoubleTree by Hilton Miami Doral | 733781 | 5082 |
| 5 | Fontainebleau Miami Beach | 19977 | 5268 |
| 6 | Gale Miami Hotel and Residences | 852725 | 5278 |
| 7 | Gale South Beach | 301645 | 5267 |
| 8 | Generator Miami | 701659 | 5274 |
| 9 | Grand Beach Hotel Miami | 68833 | 5124 |
| 10 | Hilton Cabana Miami Beach | 254198 | 5115 |
| 11 | Hilton Garden Inn Miami South Beach | 301640 | 5279 |
| 12 | Hilton Miami Airport | 20706 | 5083 |
| 13 | Holiday Inn Express Hotel & Suites | 67387 | 5130 |
| 14 | Hotel Belleza | 414146 | 5265 |
| 15 | Hotel Chelsea | 32687 | 5064 |
| 16 | Hotel Croydon | 286236 | 5131 |
| 17 | Hotel Gaythering | 277280 | 5132 |
| 18 | InterContinental Miami | 6482 | 5276 |
| 19 | Kimpton Angler's Hotel | 31226 | 5136 |
| 20 | Kimpton Hotel Palomar South Beach | 846428 | 5116 |
| 21 | Loews Miami Beach Hotel | 6661 | 5073 |
| 22 | Metropole South Beach | 31433 | 5141 |
| 23 | Miami International Airport Hotel | 21842 | 5275 |
| 24 | Notebook Miami Beach | 237547 | 5102 |
| 25 | SERENA Hotel Aventura Miami | 851939 | 5139 |
| 26 | The Albion Hotel | 855711 | 5117 |
| 27 | The Catalina Hotel & Beach Club | 87197 | 5277 |
| 28 | The Gates Hotel South Beach | 301583 | 5140 |
| 29 | The Landon Bay Harbor | 851633 | 5138 |
| 30 | The Villa Casa Casuarina | 193899 | 5075 |

### 23 Hotels Already in SalesOffice Scans

These hotels already have active scans and price data:

| Hotel | HotelId | Active Details |
|-------|---------|----------------|
| Atwell Suites Miami Brickell | 853382 | 102 |
| Breakwater South Beach | 66814 | 494 |
| Cadet Hotel | 173508 | 87 |
| citizenM Miami Brickell hotel | 854881 | 153 |
| Crystal Beach Suites Hotel | 64390 | 60 |
| Dream South Beach | 241025 | 169 |
| Embassy Suites by Hilton | 20702 | 290 |
| Eurostars Langford Hotel | 333502 | 88 |
| FAIRWIND HOTEL & SUITES | 117491 | 1 |
| Freehand Miami | 6660 | 196 |
| Hilton Bentley Miami SB | 22034 | 258 |
| Hilton Miami Downtown | 24982 | 231 |
| Hotel Riu Plaza Miami Beach | 24989 | 264 |
| Hyatt Centric South Beach | 314212 | 162 |
| Iberostar Berkeley Shore | 383277 | 72 |
| Marseilles Hotel | 6663 | 89 |
| Pullman Miami Airport | 6805 | 595 |
| Savoy Hotel | 64309 | 196 |
| SLS LUX Brickell | 852120 | 312 |
| Sole Miami | 88282 | 37 |
| The Gabriel Miami SB | 848677 | 67 |
| The Grayson Hotel | 855865 | 54 |
| Viajero Miami | 31709 | 57 |

---

## 4. Noovy — Setting Availability & Pricing

### 4.1 Login

1. Go to https://app.noovy.com
2. Account Name: `Medici LIVE`
3. User Name: `zvi`
4. Password: `karpad66`
5. Click Login

### 4.2 Select Hotel (Venue)

1. After login, expand the sidebar (click hamburger icon top-left)
2. At the bottom of the sidebar, find the **Hotel** dropdown
3. Click "Open" button next to it
4. Type hotel name or scroll to find it (e.g., "Cavalier Hotel #5113")
5. Click to select → dashboard loads for that venue

### 4.3 Bulk Update — Set Price + Availability

This is the fastest way to set availability and pricing for a date range.

1. Click **Rates** in the sidebar (opens `/pricing-availability/rateCalendar`)
2. Wait for calendar to load (shows current month)
3. Click **Bulk Update** button (top right)
4. In the dialog:

| Field | Setting |
|-------|---------|
| ROOMS | Standard (pre-selected, or choose specific room) |
| RATE PLANS | Bed and Breakfast (or Room Only) |
| DATE RANGE | Click → navigate to target month → click start date → click end date |
| Days of the Week | Leave all selected (Sun-Sat) |
| RATE UPDATE | Select **Fixed** → enter price (e.g., `1000`) |
| AVAILABILITY UPDATE | Select **Fixed** → enter count (e.g., `1`) |

5. Click **Save**
6. Wait for green toast: **"Bulk update product successfully"**
7. Switch to target month tab to verify (e.g., click "August")

### 4.4 Calendar Navigation in Bulk Update

The date picker shows 2 months side by side. To reach future months:
- Click the **`>`** (Next month) button in the date picker header
- Each click advances by 1 month
- From March 2026, click 5 times to reach August 2026

### 4.5 Verify Changes

After Bulk Update:
1. Click the target month tab (e.g., "August") in the calendar
2. Each day cell shows: `availability | occupancy%` on top, `$ price` below
3. Verify the cells show your updated values

---

## 5. Hotel.Tools — Channel Management

### 5.1 Access

Hotel.Tools is the Zenith Channel Manager layer. Access via:
- Direct: https://hotel.tools (login with Noovy credentials)
- Or via Noovy sidebar → Settings → Channels

### 5.2 Verify Innstant Channel is Connected

1. In Hotel.Tools, go to **Marketplace**
2. Find **Innstant Travel** in the channel list
3. Status should be: **Connected** (green)
4. If Disconnected: Click Setup → Enable → Submit

### 5.3 Verify Products Exist

Each hotel needs at least one Product with a Rate Plan:

1. In Hotel.Tools, go to **Products** (or via Noovy: Settings → Products)
2. Verify products exist (e.g., "Standard", "Deluxe", "Suite", "Superior")
3. Each product should have at least one Rate Plan (e.g., "Room Only / RO", "Bed and Breakfast / BB")
4. If missing: Create Product → Add Rate Plan → Link to Innstant channel

### 5.4 Product ↔ Rate Plan ↔ InvTypeCode Mapping

| Category | InvTypeCode | boardId | Rate Plan |
|----------|-------------|---------|-----------|
| Standard | STD or Stnd | 1 = RO | Room Only |
| Standard | STD or Stnd | 2 = BB | Bed and Breakfast |
| Superior | SUP | 1 = RO | Room Only |
| Deluxe | DLX | 1 = RO | Room Only |
| Suite | SUI | 1 = RO | Room Only |

These codes are stored in `Med_Hotels_ratebycat` table and used for Zenith SOAP pushes.

---

## 6. B2B Innstant — Verification

### 6.1 Search for a Hotel

1. Go to https://b2b.innstant.travel (logged in as amit/Knowaa)
2. In the search box, type hotel name (e.g., "Pullman Miami")
3. Select from dropdown
4. Set dates, rooms (e.g., 1 Adult or 2 Adults), Customer Country: United States
5. Click **Submit**
6. Wait for results to load (~10 seconds)

### 6.2 Direct URL Pattern

For faster testing, use direct URLs:

```
https://b2b.innstant.travel/hotel/{slug}-{hotelId}?service=hotels&searchQuery=hotel-{hotelId}&startDate={YYYY-MM-DD}&endDate={YYYY-MM-DD}&account-country=US&onRequest=0&payAtTheHotel=1&adults={N}&children=
```

Examples:
```
# Pullman, 1 Adult, Jun 15-16
https://b2b.innstant.travel/hotel/pullman-miami-airport-6805?service=hotels&searchQuery=hotel-6805&startDate=2026-06-15&endDate=2026-06-16&account-country=US&onRequest=0&payAtTheHotel=1&adults=1&children=

# Embassy Suites, 2 Adults, Jun 15-16
https://b2b.innstant.travel/hotel/embassy-suites-by-hilton-miami-international-airport-20702?service=hotels&searchQuery=hotel-20702&startDate=2026-06-15&endDate=2026-06-16&account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=

# Breakwater, 2 Adults + 1 child age 7
...&adults=2&children=7
```

### 6.3 Filter by Provider

In the results page, look for **"Provider: Knowaa_Global_zenith"** next to each room offer. This is our Zenith channel.

Other providers you'll see:
- **InnstantTravel** — Innstant's own inventory (dominant, 20-29 out of 30 results)
- **goglobal** — GoGlobal aggregator (2-10 results)
- **Knowaa_Global_zenith** — Our Zenith/Noovy channel (0-5 results, when available)

### 6.4 Pax Configuration Findings (March 2026)

| Hotel | 1 Adult | 2 Adults | 2+Child |
|-------|---------|----------|---------|
| Pullman | Knowaa: ✅ 2 | Knowaa: ❌ 0 | ❌ 0 total |
| SLS LUX | ❌ 0 total | Knowaa: ✅ 5 | — |
| citizenM Brickell | Knowaa: ✅ 1 | Knowaa: ✅ 2 | — |
| Eurostars | Knowaa: ✅ 1 | Knowaa: ✅ 1 | — |
| Freehand | Knowaa: ✅ 1 | Knowaa: ✅ 1 | — |
| Dream SB | Knowaa: ❌ | Knowaa: ❌ | — |
| Breakwater | Knowaa: ❌ | Knowaa: ❌ | — |
| Embassy Suites | Knowaa: ✅ 3 | Knowaa: ✅ 3 | — |
| Hilton Bentley | Knowaa: ❌ | Knowaa: ❌ | — |
| Hilton Downtown | Knowaa: ❌ | Knowaa: ❌ | — |
| Savoy | ❌ 0 total | ❌ 0 total | — |

**Key insight**: The SalesOffice WebJob ALWAYS searches with `adults:2, children:[]`. It never sends single/triple/family searches.

---

## 7. Zenith SOAP API

### 7.1 Push Price (OTA_HotelRateAmountNotifRQ)

Used by the override system to push price changes.

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>APIMedici:Medici Live</wsse:Username>
        <wsse:Password>Medici Live</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05">
      <RateAmountMessages HotelCode="{zenith_hotel_code}">
        <RateAmountMessage>
          <StatusApplicationControl
            Start="{YYYY-MM-DD}"
            End="{YYYY-MM-DD}"
            InvTypeCode="{STD|DLX|SUI|SUP}"
            RatePlanCode="{rate_plan_code}" />
          <Rates>
            <Rate>
              <BaseByGuestAmts>
                <BaseByGuestAmt AmountAfterTax="{price}" CurrencyCode="USD" />
              </BaseByGuestAmts>
            </Rate>
          </Rates>
        </RateAmountMessage>
      </RateAmountMessages>
    </OTA_HotelRateAmountNotifRQ>
  </soap:Body>
</soap:Envelope>
```

### 7.2 Push Availability (OTA_HotelAvailNotifRQ)

```xml
<OTA_HotelAvailNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05">
  <AvailStatusMessages HotelCode="{zenith_hotel_code}">
    <AvailStatusMessage>
      <StatusApplicationControl
        Start="{YYYY-MM-DD}"
        End="{YYYY-MM-DD}"
        InvTypeCode="{STD|DLX|SUI|SUP}"
        RatePlanCode="{rate_plan_code}" />
      <LengthsOfStay>
        <LengthOfStay Time="1" MinMaxMessageType="SetMinLOS" />
      </LengthsOfStay>
      <BookingLimit>{count}</BookingLimit>
    </AvailStatusMessage>
  </AvailStatusMessages>
</OTA_HotelAvailNotifRQ>
```

### 7.3 Common Error Codes

| Code | Message | Cause |
|------|---------|-------|
| 402 | Can not find product | Wrong HotelCode, InvTypeCode, or RatePlanCode |
| 500 | Something went wrong | Server-side error, usually permissions or missing product |

---

## 8. SalesOffice Database — Key Queries

### Check which hotels have active orders

```sql
SELECT o.DestinationId, COUNT(*) as orders, MAX(o.DateInsert) as last_order
FROM [SalesOffice.Orders] o
WHERE o.IsActive = 1
GROUP BY o.DestinationId
ORDER BY last_order DESC
```

### Check occupancy types per hotel

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
    COUNT(*) as cnt
FROM [SalesOffice.Details] d
WHERE d.IsDeleted = 0
GROUP BY d.HotelId,
    CASE WHEN d.RoomCode LIKE '%:single:%' THEN 'single'
         WHEN d.RoomCode LIKE '%:double:%' THEN 'double'
         WHEN d.RoomCode LIKE '%:twin:%' THEN 'twin'
         WHEN d.RoomCode LIKE '%:triple:%' THEN 'triple'
         WHEN d.RoomCode LIKE '%:quadruple:%' THEN 'quadruple'
         ELSE 'other' END
ORDER BY d.HotelId, bedding
```

### Check Knowaa results in search logs

```sql
SELECT
    PaxAdults, RoomBedding, COUNT(*) as cnt, COUNT(DISTINCT HotelId) as hotels
FROM SearchResultsSessionPollLog
WHERE Providers LIKE '%Knowaa_Global_zenith%'
    AND DateInsert > '2026-03-01'
GROUP BY PaxAdults, RoomBedding
ORDER BY cnt DESC
```

### Check what pax the WebJob sends

```sql
SELECT TOP 5 CAST(RequestJson AS NVARCHAR(MAX)) as req
FROM SearchResultsSessionPollLog
WHERE HotelId = 6805 AND DateInsert > '2026-03-23'
```

### Check Zenith mapping

```sql
SELECT h.HotelId, h.HotelName, h.Innstant_ZenithId, h.isActive,
       r.BoardId, r.CategoryId, r.RatePlanCode, r.InvTypeCode
FROM Med_Hotels h
LEFT JOIN Med_Hotels_ratebycat r ON h.HotelId = r.HotelId
WHERE h.HotelId = @hotelId
```

---

## 9. Troubleshooting Guide

### Hotel not appearing in Innstant search

1. **Check Noovy**: Is availability > 0 for the target date?
   → Rates → Calendar → navigate to target month → verify availability shows ≥1

2. **Check Hotel.Tools**: Is Innstant channel Connected?
   → Marketplace → Innstant Travel → should show "Connected"

3. **Check Products**: Does the hotel have products with rate plans?
   → Products → verify at least 1 product with 1 rate plan exists

4. **Check Availability**: Is availability pushed to Innstant?
   → Set availability=1 via Bulk Update for a test date
   → Wait 5-15 minutes for sync
   → Search in Innstant

5. **Check ZenithId**: Is the mapping correct?
   ```sql
   SELECT HotelId, HotelName, Innstant_ZenithId, isActive
   FROM Med_Hotels WHERE HotelId = @id
   ```
   → Innstant_ZenithId should match the Innstant hotel ID
   → isActive must be 1

### Knowaa not appearing as provider

Even when a hotel appears in Innstant, Knowaa_Global_zenith might not be listed:
- **Other providers** (InnstantTravel, goglobal) aggregate from many sources
- **Knowaa** only shows our Zenith inventory
- If Knowaa missing: check if products/rates/availability are properly configured in Noovy

### Price override not working

1. Check DB permissions: `GRANT INSERT, UPDATE ON [SalesOffice.PriceOverride] TO prediction_reader`
2. Check env var: `OVERRIDE_PUSH_ENABLED=true` (default is false = dry-run)
3. Check Zenith mapping: `Med_Hotels_ratebycat` must have RatePlanCode + InvTypeCode for the hotel/board/category
4. Check Zenith response: look for Error Code 402 = wrong product mapping

### "Operation not allowed" in Noovy GraphQL

The Noovy GraphQL API requires the venue to be active in the session:
- You must select the venue through the UI first
- API calls are scoped to the active venue
- Cannot bulk-update multiple venues in a single API session

---

## 10. Common Operations Playbook

### A. Onboard a New Hotel

1. **In Noovy**: Create venue → Add Products (Standard, Deluxe, Suite as needed) → Add Rate Plans (RO, BB)
2. **In Hotel.Tools**: Enable Innstant Travel channel for the venue
3. **In Noovy**: Set availability=1 and a price for test dates via Bulk Update
4. **In Innstant**: Search for the hotel → verify Knowaa_Global_zenith appears
5. **In Azure SQL**: Verify Med_Hotels mapping (HotelId, Innstant_ZenithId, isActive=1)
6. **In Azure SQL**: Verify Med_Hotels_ratebycat has rows for each board+category

### B. Set Availability for Multiple Dates

1. Login to Noovy → Select hotel
2. Go to Rates → Click Bulk Update
3. Set DATE RANGE, RATE UPDATE = Fixed $X, AVAILABILITY UPDATE = Fixed Y
4. Save → verify "Bulk update product successfully"
5. Repeat for each hotel (must switch venue in sidebar)

### C. Verify End-to-End Flow

1. Set availability in Noovy (Bulk Update, availability=1, price=$X)
2. Wait 5-15 minutes
3. Search in Innstant with same dates
4. Look for Knowaa_Global_zenith in results
5. Verify price matches what was set in Noovy

### D. Reset Test Availability

After testing, always set availability back to 0:
1. Noovy → Rates → Bulk Update
2. AVAILABILITY UPDATE = **No Availability** (or Fixed = 0)
3. Save
4. This prevents accidental real bookings at test prices

---

## 11. Known Issues & Blockers

### Noovy API Limitation
- GraphQL API is venue-scoped; cannot bulk-update across venues without switching
- No public REST API for multi-venue operations
- UI automation is the only way to handle 30+ venues efficiently

### Hotel.Tools Product Creation
- HTTP 500 errors on product creation API for some venues (27 out of 27 in diagnostic batch)
- Backend/permission issue — not a client-side problem
- Workaround: Create products manually through the UI

### WebJob Pax Configuration
- SalesOffice WebJob always searches with `adults:2, children:[]`
- No single/triple/family searches are ever sent
- To get pricing for other occupancies, manual Innstant searches are needed

### ZenithId Mismatches
- Holiday Inn Express (67387) → mapped to Oklahoma hotel, not Miami
- The Albion Hotel (855711) → mapped to Australian hotel, not Miami
- Fix: Update Innstant_ZenithId in Med_Hotels to correct hotel IDs

### Callback Processor
- 2,544 unprocessed callbacks identified (2026-03-16)
- Hotels with correct mapping but 0 Details = callback processor not running
- Affects: Dorchester, Fontainebleau, Generator Miami, Hilton Garden Inn, Miami Airport Hotel

---

## 12. Environment Variables (Medici Prediction API)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OVERRIDE_PUSH_ENABLED` | `false` | Enable/disable Zenith price push |
| `OPPORTUNITY_EXECUTE_ENABLED` | `false` | Enable/disable opportunity execution |
| `MEDICI_DB_URL` | — | Azure SQL connection string |
| `ZENITH_SOAP_URL` | `https://hotel.tools/service/Medici%20new` | Zenith SOAP endpoint |
| `ZENITH_SOAP_USERNAME` | `APIMedici:Medici Live` | SOAP auth username |
| `ZENITH_SOAP_PASSWORD` | `Medici Live` | SOAP auth password |

---

## 13. File References

| File | Purpose |
|------|---------|
| `docs/OVERRIDE_SETUP.md` | Override execution setup for second developer |
| `docs/OVERRIDE_EXECUTION.md` | Full override system documentation |
| `docs/HOTEL_ONBOARDING_REQUEST.md` | 11-hotel onboarding investigation |
| `docs/medici-hotels-ref/05-hotel-mapping.md` | Zenith mapping guide |
| `docs/medici-hotels-ref/09-zenith-api-research.md` | Full Zenith API research |
| `skills/price-override/SKILL.md` | Price override skill with gotchas |
| `skills/insert-opp/SKILL.md` | Opportunity insertion skill with gotchas |
| `src/utils/zenith_push.py` | Shared Zenith SOAP utilities |
| `src/analytics/override_queue.py` | Override queue (SQLite) |
| `src/analytics/opportunity_queue.py` | Opportunity queue (SQLite) |
