# Medici Hotels - Database Schema Documentation

> **64 Tables • 85 Stored Procedures**  
> Database: `medici-db` @ `medici-sql-server.database.windows.net`  
> Last Updated: January 13, 2026

---

## 📊 Tables Overview

| Category | Count | Purpose |
|----------|-------|---------|
| Core Booking | 7 | Room purchases, pre-books, cancellations |
| Opportunities | 4 | Purchase opportunities to monitor |
| Reservations | 7 | Incoming reservations from Zenith |
| Hotels | 8 | Hotel data, mappings, destinations |
| Lookup Tables | 8 | Board types, categories, currencies |
| Users & Auth | 7 | Users, roles, permissions |
| API & Tokens | 4 | API clients, tokens |
| Sales Office | 6 | Sales office operations |
| Logs | 6 | System and operation logs |
| Other | 7 | Queue, AI search, misc |

---

## 🏨 Core Booking Tables

### MED_Book
> **Purpose:** Stores all purchased room bookings. Main table for tracking room inventory.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | int | NO | Primary Key |
| `PreBookId` | int | NO | FK to MED_PreBook |
| `OpportunityId` | int | YES | FK to MED_Opportunities |
| `contentBookingID` | nvarchar(50) | YES | Supplier booking reference |
| `supplierReference` | nvarchar(50) | YES | Supplier confirmation code |
| `price` | float | YES | Purchase price |
| `servicesPrice` | float | YES | Services price |
| `startDate` | date | YES | Check-in date |
| `endDate` | date | YES | Check-out date |
| `HotelId` | int | YES | FK to Med_Hotels |
| `IsActive` | bit | YES | Is booking active |
| `IsSold` | bit | YES | Has been sold via Zenith |
| `SoldId` | int | YES | FK to Med_Reservation |
| `source` | int | YES | 1=Innstant, 2=GoGlobal |
| `CancellationType` | nvarchar(150) | YES | Cancellation policy type |
| `CancellationTo` | datetime | YES | Free cancellation deadline |
| `lastPrice` | float | YES | Last known market price |
| `RequestJson` | nvarchar(MAX) | YES | API request log |
| `ResponseJson` | nvarchar(MAX) | YES | API response log |

### MED_PreBook
> **Purpose:** Pre-booking records before final confirmation.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `PreBookId` | int | NO | Primary Key |
| `OpportunityId` | int | YES | FK to Opportunity |
| `HotelId` | int | YES | FK to Med_Hotels |
| `DateForm` | date | YES | Check-in date |
| `DateTo` | date | YES | Check-out date |
| `CategoryId` | int | YES | Room category |
| `BoardId` | int | YES | Board type |
| `Price` | float | YES | Quoted price |
| `Token` | nvarchar(MAX) | YES | API token for booking |
| `CancellationType` | nvarchar(150) | YES | Cancellation type |
| `CancellationTo` | datetime | YES | Free cancel deadline |
| `ProviderId` | int | YES | Provider ID |
| `source` | int | YES | 1=Innstant, 2=GoGlobal |

---

## 🎯 Opportunity Tables

### MED_Opportunities
> **Purpose:** Defines purchase opportunities - combinations of hotel/dates/board/category to monitor and buy.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `OpportunityId` | int | NO | Primary Key |
| `OpportunityMlId` | int | YES | Parent opportunity ID |
| `DestinationsId` | int | NO | FK to hotel/destination |
| `DateForm` | date | NO | Start date |
| `DateTo` | date | NO | End date |
| `BoardId` | int | YES | FK to MED_Board |
| `CategoryId` | int | YES | FK to MED_RoomCategory |
| `Price` | float | NO | Max purchase price |
| `PushPrice` | float | YES | Sell price to Zenith |
| `PushHotelCode` | int | YES | Zenith hotel code |
| `PushRatePlanCode` | nvarchar(50) | YES | Zenith rate plan |
| `PushInvTypeCode` | nvarchar(50) | YES | Zenith inventory type |
| `IsActive` | bit | YES | Is active for buying |
| `IsPush` | bit | YES | Has been pushed to Zenith |
| `IsSale` | bit | YES | Has been sold |
| `Lastupdate` | date | YES | Last processing time |
| `FreeCancelation` | bit | NO | Requires free cancellation |

---

## 📋 Reservation Tables

### Med_Reservation
> **Purpose:** Incoming reservations from Zenith (OTA_HotelResNotifRQ).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `Id` | int | NO | Primary Key |
| `ResStatus` | nvarchar(50) | YES | Commit/Modify/Cancel |
| `uniqueID` | nvarchar(50) | YES | Zenith booking reference |
| `HotelCode` | nvarchar(50) | YES | Zenith hotel code |
| `datefrom` | datetime | YES | Check-in date |
| `dateto` | datetime | YES | Check-out date |
| `AmountAfterTax` | float | YES | Total price |
| `CurrencyCode` | nvarchar(50) | YES | Currency |
| `RatePlanCode` | nvarchar(50) | YES | Rate plan |
| `RoomTypeCode` | nvarchar(50) | YES | Room type |
| `AdultCount` | int | YES | Number of adults |
| `ChildrenCount` | int | YES | Number of children |
| `IsApproved` | bit | YES | Has been matched to Book |
| `IsCanceled` | bit | YES | Is cancelled |
| `Comments` | nvarchar(MAX) | NO | Reservation comments |

---

## 🏢 Hotel Tables

### Med_Hotels
> **Purpose:** Main hotels table with mappings between Innstant, GoGlobal, and Zenith IDs.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `HotelId` | int | NO | Primary Key |
| `InnstantId` | int | NO | Innstant API hotel ID |
| `Innstant_ZenithId` | int | NO | Zenith hotel code |
| `Goglobalid` | int | YES | GoGlobal hotel ID |
| `name` | nvarchar(MAX) | YES | Hotel name |
| `countryId` | int | YES | Country ID |
| `BoardId` | int | YES | Default board type |
| `CategoryId` | int | YES | Default category |
| `isActive` | bit | YES | Is active |
| `RatePlanCode` | nvarchar(MAX) | YES | Zenith rate plan code |
| `InvTypeCode` | nvarchar(MAX) | YES | Zenith inventory type code |

### Med_HotelsToPush
> **Purpose:** Queue for rooms waiting to be pushed to Zenith.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | int | NO | Primary Key |
| `BookId` | int | NO | FK to MED_Book.PreBookId |
| `OpportunityId` | int | NO | FK to MED_Opportunities |
| `DateInsert` | datetime | NO | Queue time |
| `DatePush` | datetime | YES | Push completion time |
| `IsActive` | bit | NO | Pending (true) or done (false) |
| `Error` | nvarchar(MAX) | YES | Error message if failed |

---

## 📖 Lookup Tables

### MED_Board
> **Purpose:** Board (meal plan) types.

| BoardId | Code | Description |
|---------|------|-------------|
| 1 | RO | Room Only |
| 2 | BB | Bed & Breakfast |
| 3 | HB | Half Board |
| 4 | FB | Full Board |
| 5 | AI | All Inclusive |

### MED_RoomCategory
> **Purpose:** Room category types.

| CategoryId | Name | Description |
|------------|------|-------------|
| 1 | Standard | Standard room |
| 2 | Superior | Superior room |
| 3 | Suite | Suite |

### MED_RoomBedding
> **Purpose:** Bedding configuration types.

| BeddingId | Name | Description |
|-----------|------|-------------|
| 1 | Double | Double bed |
| 2 | Twin | Twin beds |

### Med_Source
> **Purpose:** Data/booking sources.

| Id | Name | Is Active |
|----|------|-----------|
| 1 | Innstant | true |
| 2 | GoGlobal | true |

---

## ⚙️ Stored Procedures

### Booking Operations

| Stored Procedure | Description |
|------------------|-------------|
| `MED_InsertPreBook` | Insert new pre-booking |
| `MED_InsertBook` | Insert confirmed booking |
| `MED_InsertBookCustomerName` | Insert customer name |
| `Med_InsertBookCustomerMoreInfo` | Insert customer details |
| `MED_InsertBookError` | Log booking error |
| `MED_InsertCancelBook` | Insert cancellation |
| `MED_InsertCancelBookError` | Log cancellation error |
| `MED_GetAllBook` | Get all bookings |
| `MED_GetAllBookBackOffice` | Get bookings for back office |
| `MED_GetBookingByPreBookId` | Get booking by PreBook ID |
| `MED_GetBookingIDByPreBookId` | Get booking ID |

### Opportunity Operations

| Stored Procedure | Description |
|------------------|-------------|
| `MED_InsertOpportunity` | Insert new opportunity |
| `MED_UpdateOpportunity` | Update opportunity |
| `MED_GetAllOpportunities` | Get all opportunities |
| `MED_GetAllOpportunitiesTobuy` | Get opportunities to purchase |
| `MED_GetnextOpportunitiesTobuy` | Get next opportunity for processing |
| `MED_GetAllOpportunitiesToUpdatePrice` | Get opportunities needing price update |
| `MED_SearchOpportunity` | Search opportunities |
| `InsertOpportunityBackOffice` | Insert from back office |
| `MED_DisabledOpTjOB` | Disable opportunity |
| `CancelOPT` | Cancel opportunity |

### Reservation Operations

| Stored Procedure | Description |
|------------------|-------------|
| `MED_InsertReservation` | Insert new reservation from Zenith |
| `MED_InsertReservationCancel` | Insert reservation cancellation |
| `MED_InsertReservationModify` | Insert reservation modification |
| `MED_InsertReservationCustomerName` | Insert customer name |
| `MED_InsertReservationCustomerMoreInfo` | Insert customer details |
| `MED_DoReservation` | Process reservation |
| `MED_ApprovedReservation` | Approve reservation |
| `MED_FindAvailableRoom` | Find available room for reservation |
| `MED_FindAvailableRoomCount` | Count available rooms |
| `MED_GetAllReservation` | Get all reservations |
| `MED_GetReservationByID` | Get reservation by ID |
| `MED_UpdateBookApprovedReservation` | Mark book as sold |
| `MED_UpdateReservationApprovedReservation` | Update reservation approval |
| `MED_UpdateOpportunitiesApprovedReservation` | Update opportunities after sale |

### Push to Zenith

| Stored Procedure | Description |
|------------------|-------------|
| `MED_GetAllHotelsToPush` | Get rooms queued for push |
| `MED_GetAllHotelsToPushCancel` | Get cancellations to push |
| `Med_UpdateHotelsToPush` | Mark push as complete |
| `Med_updateNewPrice` | Update push price |
| `Med_UpdateLastPrice` | Update last known price |

### Hotel Operations

| Stored Procedure | Description |
|------------------|-------------|
| `MED_GetAllHotels` | Get all hotels |
| `MED_GetAllHotelsNew` | Get new hotels |
| `MED_InsertHotel` | Insert hotel |
| `MED_InsertHotel_instant` | Insert Innstant hotel |
| `MED_GetHotelIdBysource` | Get hotel ID by source |
| `MED_GetHotelsToSearch` | Get hotels for search |
| `GetAllHotelsCountry` | Get hotels by country |
| `GetLastHotelid` | Get last hotel ID |
| `Med_Hotels_instant_Active` | Get active Innstant hotels |
| `updateHotelZenithId` | Update Zenith hotel ID |
| `MED_GetAllHotelBackOfficeRateInvCode` | Get rate/inv codes |

### Price Operations

| Stored Procedure | Description |
|------------------|-------------|
| `MED_GetHighPrice` | Get highest price |
| `MED_GetLowPrice` | Get lowest price |
| `MED_GetLastPrice` | Get last price |

### Lookup Data

| Stored Procedure | Description |
|------------------|-------------|
| `MED_GetAllBoard` | Get all board types |
| `MED_GetAllCategory` | Get all categories |
| `MED_GetAllBedding` | Get all bedding types |
| `MED_GetAllSource` | Get all sources |
| `MED_GetCustomerFNames` | Get first names |
| `MED_GetCustomerLNames` | Get last names |

### Auto Cancellation

| Stored Procedure | Description |
|------------------|-------------|
| `MED_AutoCancellation` | Run auto-cancellation process |

### Logging & Misc

| Stored Procedure | Description |
|------------------|-------------|
| `MED_InsertNewLog` | Insert general log |
| `MED_InsertNewReservationNotificationLog` | Log Zenith notification |
| `MED_GetAllLog` | Get all logs |
| `MED_GetAllUsers` | Get all users |
| `MED_InsertSearchHotels` | Insert search results |
| `MED_GetAllSearchHotels` | Get search history |
| `updateOpportunityIdlastupdate` | Update opportunity timestamp |
| `MED_BackOfficeOPT` | Back office operations |
| `MED_BackOfficeOptLog` | Log back office action |

---

## 🔗 Key Relationships

### Booking Flow

```
MED_Opportunities (defines what to buy)
        │
        ▼ OpportunityId
MED_PreBook (availability check result)
        │
        ▼ PreBookId
MED_Book (confirmed purchase)
        │
        ├──▶ Med_HotelsToPush (queue to update Zenith) via BookId
        │
        └──▶ Med_Reservation (incoming sale) via SoldId
```

### Hotel Mappings

```
Med_Hotels
    ├── InnstantId ──────────▶ Innstant API hotel ID
    ├── Goglobalid ──────────▶ GoGlobal API hotel ID  
    └── Innstant_ZenithId ───▶ Zenith hotel code (for push)
```

### Source Reference

```
source = 1 ──▶ Innstant
source = 2 ──▶ GoGlobal
```

---

## 📊 Entity Relationship Diagram

```
┌─────────────────────┐
│   MED_Opportunities │
├─────────────────────┤
│ OpportunityId (PK)  │───────────────────────┐
│ DestinationsId (FK) │◀──┐                   │
│ DateForm            │   │                   │
│ DateTo              │   │                   │
│ BoardId (FK)        │───┼──────────────┐    │
│ CategoryId (FK)     │───┼─────────┐    │    │
│ Price               │   │         │    │    │
│ PushPrice           │   │         │    │    │
│ IsActive            │   │         │    │    │
└─────────────────────┘   │         │    │    │
                          │         │    │    │
┌─────────────────────┐   │         │    │    │
│     Med_Hotels      │───┘         │    │    │
├─────────────────────┤             │    │    │
│ HotelId (PK)        │◀────────────┼────┼────┼─────┐
│ InnstantId          │             │    │    │     │
│ Innstant_ZenithId   │             │    │    │     │
│ Goglobalid          │             │    │    │     │
│ name                │             │    │    │     │
│ BoardId (FK)        │─────────────┘    │    │     │
│ CategoryId (FK)     │──────────────────┘    │     │
│ RatePlanCode        │                       │     │
│ InvTypeCode         │                       │     │
└─────────────────────┘                       │     │
                                              │     │
┌─────────────────────┐                       │     │
│    MED_PreBook      │◀──────────────────────┘     │
├─────────────────────┤                             │
│ PreBookId (PK)      │────────────────┐            │
│ OpportunityId (FK)  │                │            │
│ HotelId (FK)        │────────────────┼────────────┘
│ DateForm            │                │
│ DateTo              │                │
│ Price               │                │
│ Token               │                │
└─────────────────────┘                │
                                       │
┌─────────────────────┐                │
│      MED_Book       │◀───────────────┘
├─────────────────────┤
│ id (PK)             │────────────────────────────┐
│ PreBookId (FK)      │                            │
│ OpportunityId (FK)  │                            │
│ contentBookingID    │                            │
│ price               │                            │
│ startDate           │                            │
│ endDate             │                            │
│ HotelId (FK)        │                            │
│ IsSold              │                            │
│ SoldId (FK)         │─────────────────┐          │
└─────────────────────┘                 │          │
                                        │          │
┌─────────────────────┐                 │          │
│   Med_Reservation   │◀────────────────┘          │
├─────────────────────┤                            │
│ Id (PK)             │                            │
│ ResStatus           │                            │
│ uniqueID            │                            │
│ HotelCode           │                            │
│ datefrom            │                            │
│ dateto              │                            │
│ AmountAfterTax      │                            │
│ IsApproved          │                            │
│ IsCanceled          │                            │
└─────────────────────┘                            │
                                                   │
┌─────────────────────┐                            │
│  Med_HotelsToPush   │◀───────────────────────────┘
├─────────────────────┤
│ id (PK)             │
│ BookId (FK)         │
│ OpportunityId (FK)  │
│ DateInsert          │
│ DatePush            │
│ IsActive            │
│ Error               │
└─────────────────────┘
```

---

## 🔧 Common Queries

### Get Available Rooms for Sale
```sql
SELECT b.*, h.name as HotelName
FROM MED_Book b
JOIN Med_Hotels h ON b.HotelId = h.HotelId
WHERE b.IsActive = 1 
  AND b.IsSold = 0 
  AND b.IsCanceled = 0
  AND b.startDate >= GETDATE()
ORDER BY b.startDate
```

### Get Pending Opportunities
```sql
SELECT o.*, h.name as HotelName
FROM MED_Opportunities o
JOIN Med_Hotels h ON o.DestinationsId = h.HotelId
WHERE o.IsActive = 1
  AND o.DateForm >= GETDATE()
ORDER BY o.DateForm
```

### Get Rooms Waiting to Push to Zenith
```sql
SELECT hp.*, b.*, h.name as HotelName
FROM Med_HotelsToPush hp
JOIN MED_Book b ON hp.BookId = b.PreBookId
JOIN Med_Hotels h ON b.HotelId = h.HotelId
WHERE hp.IsActive = 1
ORDER BY hp.DateInsert
```

---

*Generated: January 13, 2026*

