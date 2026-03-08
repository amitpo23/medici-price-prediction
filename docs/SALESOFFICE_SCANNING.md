# SalesOffice Scanning System — How Room Prices Are Collected

Complete documentation of the WebJob scanning pipeline that feeds our prediction system.

---

## Overview

A **WebJob runs every 10 minutes**, scanning all active orders against the Innstant API to find the cheapest available room prices. Results are written to `SalesOffice.Details` and pushed to Zenith (channel manager).

**This is the primary data source for our prediction system.** Every price we track, every forward curve we build, every signal we generate — originates from these scans.

---

## Pipeline: Step by Step

### Step 1: Load Orders
Every 10 minutes the WebJob activates, loads **all orders** from `SalesOffice.Orders`, and processes them **serially** (one by one).

### Step 2: Initial Filtering
For each order:
- **IsValidDateRange**: Only 1-night stays (`DateTo - DateFrom ≤ 1 day`)
- **IsActive**: If inactive → closes all rooms in Zenith (`BookingLimit=0`)

### Step 3: Innstant API Search
Calls `SearchHotels()` with:

| Parameter | Value |
|-----------|-------|
| DateFrom / DateTo | From the order |
| DestinationId | e.g., Miami |
| Adults | **2** (hardcoded) |
| Currency | **USD** (hardcoded) |
| Timeout | 30 seconds |
| Retries | Up to 5 (exponential backoff: 20s, 40s, 60s…) |

Returns a list of `ResultHotel` — each representing a specific room from a specific provider with a price.

### Step 4: Three Critical Filters

| Filter | What It Does | Why |
|--------|-------------|-----|
| `fully-refundable` | Only rooms with free cancellation | Avoid cancellation risk |
| `Not Knowaa_Global_zenith` | Excludes Medici's own provider | Prevent buying from yourself (loop) |
| `FilterByVenueId` | Only hotels where `InnstantZenithId ≠ 0` in `Med_Hotels` | Only hotels mapped to Zenith |

### Step 5: Flatten & Group — Cheapest Price Selection 🔑

`CreateFlattenedHotels()` does the magic:

1. **Flatten**: Each `ResultHotel` becomes individual rows: `(HotelId, Category, Board, Price, Code)`
2. **Group**: `GROUP BY {HotelId, RoomCategory, RoomBoard}`
3. **Min price**: `MinBy(RoomPrice)` — only the cheapest price survives

**Example:**
```
Expedia:     Standard/RO → $150  ← WINNER!
Booking.com: Standard/RO → $180
Hotels.com:  Standard/RO → $165
```

Only $150 is saved. **The provider name is NOT stored** — only the price, code, and room combination.

### Step 6: Remap to Zenith

`Remap()` performs an **INNER JOIN in memory** between search results and the `ratebycat` table:

```
Search Result (HotelId=100, category=standard, board=RO)
    × ratebycat (HotelId=100, RoomCategory=standard, RoomBoard=RO)
    = Match! → adds RatePlanCode + InvTypeCode + VenueId
```

**If there's no match → the room is dropped entirely.** This is why some room types (e.g., BB) may never appear in our data — they have no `ratebycat` mapping.

### Step 7: Sync to DB + Zenith (3 Operations)

| Operation | When | Zenith Push | Database |
|-----------|------|-------------|----------|
| **ADD** | New room not seen before | `BookingLimit=1` (open), `Price=price+$0.01` | `INSERT` into Details |
| **DELETE** | Room existed but no longer found | `BookingLimit=0` (closed), `Price=$1000` | `IsDeleted=true` |
| **UPDATE** | Room exists + price changed | `Price=new price` | Update `Price` + `Code` |

---

## Critical Details

### The $0.01 Markup
When a new room is added, Zenith receives `RoomPrice + $0.01`. This is the minimum markup — one cent above cost.

### No Provider Tracking
The system does **not** save which provider offered the cheapest price. Only the price itself, the booking code, and the room combination are stored. This means:
- We cannot analyze provider-level pricing trends
- We see only the market minimum at each scan
- Provider information from `SearchResultsSessionPollLog` (source #9) is the closest proxy

### Code = Innstant Booking ID
The `RoomCode` (e.g., `ABC123`) is the identifier needed to actually book the room through Innstant later. Each scan may return a different code for the same room.

### Price Accuracy = Scan Moment
The price is accurate **only at the moment of scanning**. It can change at the next scan (every 10 minutes). Each scan fully replaces/updates the data — there is no price history within SalesOffice itself.

### Zenith = SOAP Channel Manager
Zenith is a SOAP-based system that manages availability and rates. Medici pushes prices to Zenith so they appear on the sales website. Key SOAP operations:
- Set `BookingLimit` (0=closed, 1=open)
- Set `Price` (the rate to display)

---

## Data Schema: SalesOffice.Details

```
SalesOffice.Details:
├── SalesOfficeOrderId    FK → SalesOffice.Orders
├── HotelId               Innstant hotel ID
├── RoomCategory          standard, superior, deluxe, suite...
├── RoomBoard             RO (Room Only), BB, HB, AI...
├── RoomPrice             Cheapest price found (USD)
├── RoomCode              Innstant booking code
├── DateFrom              Check-in date
├── DateTo                Check-out date
├── DateCreated           When this row was first inserted
├── DateUpdated           Last price update timestamp (our scan history source!)
├── IsDeleted             true if room no longer available
├── IsProcessedCallback   true if room was actually booked
└── BookingStatus         Current booking state
```

---

## Implications for Our Prediction System

### What We See
- **Price = market minimum**: Always the cheapest fully-refundable rate from any provider
- **10-minute resolution**: Maximum granularity for price tracking
- **1-night stays only**: No multi-night rate optimization data
- **2-adult pricing**: Family/solo pricing may differ

### What We Don't See
- Which provider offered the price
- Non-refundable rates (often cheaper)
- Rates from unmapped hotels (no `ratebycat` entry)
- Rates for BB/HB if not in `ratebycat`
- The raw API response (only the MIN survives)

### How Our Scan History Works
Our `load_scan_history()` in `collector.py` queries `SalesOffice.Details` grouped by `DateCreated` timestamps:
- Each scan cycle creates rows with the same `DateCreated` timestamp
- We track price changes by comparing consecutive scans for the same `(OrderId, HotelId, Category, Board)` key
- `DateUpdated` tells us when the price last changed
- `IsDeleted` transitions tell us when rooms appear/disappear from the market

### Price Change Sensitivity
Since we see market minimums, a price "change" can mean:
1. **Same provider changed price** — actual market move
2. **Different provider became cheapest** — provider switching (invisible to us)
3. **Room sold out at cheapest provider** — supply-driven change

All three appear identical in our data. This is why our forward curve uses statistical smoothing rather than trying to decompose individual moves.

---

## Scanning Timeline Example

```
10:00  Scan #1: Standard/RO = $150 (from Expedia)
10:10  Scan #2: Standard/RO = $150 (no change → no UPDATE)
10:20  Scan #3: Standard/RO = $165 (Expedia sold out, Hotels.com now cheapest → UPDATE)
10:30  Scan #4: Standard/RO = $145 (new provider undercut → UPDATE)
10:40  Scan #5: Standard/RO not found (all sold out → DELETE, BookingLimit=0)
10:50  Scan #6: Standard/RO = $170 (back in stock → ADD, BookingLimit=1)
```

Our prediction system sees: $150, $150, $165, $145, [gap], $170 — and builds the forward curve from this price series.
