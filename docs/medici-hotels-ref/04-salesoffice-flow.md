# 04 - SalesOffice Processing Flow / תהליך עיבוד SalesOffice

## Overview

SalesOffice הוא המנגנון המרכזי לעיבוד הזמנות מלונות. ההזמנות נכנסות לטבלת `SalesOffice.Orders` ומעובדות על ידי ה-WebJob `AzureWebJob` (פרויקט OnlyNight) כל 5 דקות.

---

## End-to-End Flow

```
                              ┌─────────────────────┐
                              │  Control Panel /     │
                              │  External System     │
                              │  Creates Order       │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ SalesOffice.Orders   │
                              │ WebJobStatus = NULL  │
                              │ IsActive = 1         │
                              └──────────┬──────────┘
                                         │
                               Every 5 minutes
                                         │
                                         ▼
                    ┌────────────────────────────────────┐
                    │   AzureWebJob.Functions             │
                    │   .ProcessSalesOfficeOrders.Run()   │
                    └──────────────┬─────────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────────┐
                    │   SalesOfficeService.Run()          │
                    │   (OnlyNight.Services)              │
                    └──────────────┬─────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
   ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
   │ 1. Get       │   │ 2. Search        │   │ 3. Map Rooms     │
   │ Orders List  │   │ Innstant API     │   │ to Rate Plans    │
   │              │   │                  │   │                  │
   │ GetSalesOff- │   │ GetInnstant-     │   │ GetRatePlanCode- │
   │ iceOrders-   │   │ HotelSearchData()│   │ AndInvTypeCode() │
   │ List()       │   │                  │   │                  │
   └──────┬───────┘   └───────┬──────────┘   └───────┬──────────┘
          │                   │                       │
          │                   ▼                       ▼
          │         ┌──────────────────┐   ┌──────────────────┐
          │         │ FilterByVenueId()│   │ FindPushRate-    │
          │         │ (match ZenithId) │   │ PlanCode()       │
          │         └──────────────────┘   │ (ratebycat tbl)  │
          │                                └──────────────────┘
          │
          ▼
   ┌──────────────────────────────────────────────┐
   │ 4. Write Results                              │
   │                                               │
   │  AddSalesOfficeDetails()     → SalesOffice.Details  │
   │  UpdateWebJobStatus()        → SalesOffice.Orders   │
   │  "Completed; Innstant Api Rooms: X;                  │
   │   Rooms With Mapping: Y"                             │
   └──────────────────────────────────────────────┘
```

---

## Step-by-Step Detailed Flow

### Step 1: Get Pending Orders
```
Method: SalesOfficeService.GetSalesOfficeOrdersList()
Query:  SELECT * FROM [SalesOffice.Orders] 
        WHERE IsActive = 1 
        AND (WebJobStatus IS NULL OR WebJobStatus = 'In Progress')
Result: List of SalesOfficeOrders to process
```

### Step 2: Validate Dates
```
Method: SalesOfficeService.IsValidDateRange()
Check:  DateFrom < DateTo AND DateFrom >= Today
Skip:   Orders with invalid date ranges
```

### Step 3: Search Innstant API
```
Method: SalesOfficeService.GetInnstantHotelSearchData()
Action: 
  1. Build search request with DateFrom, DateTo, DestinationId
  2. Call Innstant API SearchHotels
  3. Poll for results (SearchResultsSessionPoll)
  4. Get hotel details (SearchResultsSessionHotelDetails)
  5. Return list of available hotels with rooms
```

### Step 4: Filter by VenueId (ZenithId)
```
Method: SalesOfficeService.FilterByVenueId()
Action:
  1. Get all Med_Hotels where Innstant_ZenithId > 0 AND isActive = True
  2. For each hotel in Innstant API results:
     a. Match hotel.code to Med_Hotels.HotelId
     b. Verify hotel has Innstant_ZenithId (VenueId) > 0
     c. Keep only matching hotels
  3. Return filtered list

⚠️ CRITICAL: If hotel has ZenithId=0 or isActive=False → EXCLUDED HERE
```

### Step 5: Get Rate Plan Mapping
```
Method: SalesOfficeService.GetRatePlanCodeAndInvTypeCode()
  └── Calls: BaseEF.FindPushRatePlanCode(hotelId, boardId, categoryId)

Action:
  1. For each room in filtered results:
     a. Look up Med_Hotels_ratebycat WHERE:
        - HotelId = room's hotel ID
        - BoardId = room's board type (1=RO, 2=BB, etc.)
        - CategoryId = room's category (1=Std, 4=DLX, 12=Suite)
     b. If found: RatePlanCode + InvTypeCode → "Mapped Room"
     c. If NOT found: returns (null, null) → "Room With NO Mapping"
  
  2. Count results:
     - Total rooms from API = "Innstant Api Rooms: X"
     - Rooms with ratebycat match = "Rooms With Mapping: Y"

⚠️ ROOT CAUSE of "Rooms With Mapping: 0":
  - Missing rows in Med_Hotels_ratebycat for that hotel/board/category combo
  - Hotel has ZenithId = 0 (already filtered out in Step 4)
```

### Step 6: Create Flattened Hotels & Add Details
```
Method: SalesOfficeService.CreateFlattenedHotels()
  └── SalesOfficeService.AddSalesOfficeDetails()

Action:
  1. For each mapped room:
     a. Create SalesOfficeDetails record
     b. INSERT INTO [SalesOffice.Details] with:
        - SalesOfficeOrderId → link to order
        - HotelId
        - RoomCategory, RoomBoard, RoomPrice, RoomCode
        - IsProcessedCallback = false
```

### Step 7: Update WebJob Status
```
Method: SalesOfficeLogService.UpdateWebJobStatus()

Action:
  1. Build status string:
     "Completed; Innstant Api Rooms: {totalApiRooms}; Rooms With Mapping: {mappedRooms}"
  
  2. UPDATE [SalesOffice.Orders] 
     SET WebJobStatus = {status_string}
     WHERE Id = {orderId}

Examples:
  - "Completed; Innstant Api Rooms: 14; Rooms With Mapping: 0"    ← PROBLEM
  - "Completed; Innstant Api Rooms: 22; Rooms With Mapping: 12"   ← OK
  - "Completed; Innstant Api Rooms: 0; Rooms With Mapping: 0"     ← No results from API
```

---

## Callback Processing (Phase 2)

After Details are created with `IsProcessedCallback = false`, the callback service processes them:

```
SalesOfficeCallbackService.ProcessCallBackCommitBySalesOffice()
  │
  ├── Get Details WHERE IsProcessedCallback = false
  │
  ├── For each detail:
  │     ├── Search Innstant API for current price
  │     ├── Compare DB price vs API price
  │     │
  │     ├── If NO room found in Innstant:
  │     │     └── HandleErrorNoRoomInInnstantBasedOnHotelCategoryBoard()
  │     │
  │     ├── If API price > DB price:
  │     │     └── HandleErrorInnstantRoomHigherPriceThanDb()
  │     │
  │     ├── If everything OK:
  │     │     ├── ApiInnstantService.BuyRoom()  ← PreBook → Book
  │     │     │
  │     │     ├── On Success:
  │     │     │     ├── HandleSuccessInBuyRoom()
  │     │     │     ├── CreateOpportunity()
  │     │     │     ├── AddToDbSalesOfficeBooking()
  │     │     │     └── PushRoom() to Zenith
  │     │     │
  │     │     └── On Failure:
  │     │           └── HandleFailInBuyRoom()
  │     │
  │     └── UpdateBookingStatus()
  │
  └── Log results
```

### Cancel Callback:
```
SalesOfficeCallbackService.ProcessCallBackCancelBySalesOffice()
  └── Cancel existing booking via Innstant API
```

---

## Re-Processing Behavior

### ❓ Will the WebJob re-process orders after hotel fixes?

**NO.** Orders with `WebJobStatus = 'Completed; ...'` will NOT be automatically re-processed.

### How to Trigger Re-Processing:

**Option A:** Reset WebJobStatus to NULL
```sql
UPDATE [SalesOffice.Orders] 
SET WebJobStatus = NULL 
WHERE Id IN (/* order IDs for fixed hotels */)
```

**Option B:** Create new orders for the same destinations/dates

### Important: The WebJob only picks up orders where:
```sql
WebJobStatus IS NULL OR WebJobStatus = 'In Progress'
```

---

## Troubleshooting Guide

### Problem: "Rooms With Mapping: 0"
**Root Cause:** Missing `Med_Hotels_ratebycat` rows for the hotel's room types
**Fix:**
1. Identify hotel ID and board/category combos
2. INSERT appropriate row(s) into `Med_Hotels_ratebycat`
3. Reset `WebJobStatus = NULL` for affected orders
4. Wait 5 minutes for next WebJob run

### Problem: "Innstant Api Rooms: 0"
**Root Cause:** Hotel not found in Innstant API search (dates unavailable, hotel inactive in Innstant)
**Check:**
1. Is the hotel still available on Innstant for those dates?
2. Is `isActive = True` in `Med_Hotels`?
3. Is the destination correct?

### Problem: Hotel not appearing at all
**Root Cause:** `FilterByVenueId()` excluded it
**Check:**
1. `Innstant_ZenithId` must be > 0
2. `isActive` must be True (1)
3. Hotel must exist in `Med_Hotels`
