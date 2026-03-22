# 01 - System Architecture / ארכיטקטורת מערכת

## Overview / סקירה כללית

Medici Hotels היא מערכת לניהול מלונות המתחברת ל-API חיצוניים (Innstant, GoGlobal) לחיפוש, הזמנה, ודחיפת מחירים/זמינות לערוץ Zenith. המערכת מורכבת ממספר רכיבים הפועלים על Azure App Service.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Azure App Service                            │
│                      medici-backend (East US 2)                     │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │   Backend    │  │   4 Continuous   │  │  Static Web App        │ │
│  │   Web API    │  │   WebJobs        │  │  (Control Panel)       │ │
│  └──────┬───────┘  └────────┬─────────┘  └────────────────────────┘ │
│         │                   │                                       │
└─────────┼───────────────────┼───────────────────────────────────────┘
          │                   │
          ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│  Azure SQL DB    │  │  External APIs   │
│  medici-db       │  │  - Innstant      │
│                  │  │  - GoGlobal      │
│                  │  │  - Zenith        │
└──────────────────┘  └──────────────────┘
```

---

## Components / רכיבים

### 1. Backend Web API (`Backend/`)
- **Type:** ASP.NET Core Web API
- **Purpose:** API ראשי למערכת - ניהול הזמנות, חיפושים, דשבורד
- **Key Features:**
  - SignalR Hub for real-time notifications
  - CORS enabled for all origins
  - Health Check endpoint
  - Swagger/OpenAPI documentation (dev only)
  - Basic Authentication via custom attribute
- **Entry Point:** [Backend/Program.cs](../Backend/Program.cs)
- **Controllers:** Located in `Backend/Controllers/`
- **Models:** Located in `Backend/Models/`

### 2. Azure WebJobs (4 Continuous)

| WebJob | Executable | Source Project | Function |
|--------|-----------|---------------|----------|
| **AutoCancellation** | `AutoCancellation.exe` | `MediciAutoCancellation/` (local) | ביטול אוטומטי של הזמנות |
| **AzureWebJob** | `AzureWebJob.exe` | OnlyNight project (NOT local) | עיבוד SalesOffice + עדכון מלונות |
| **BuyRoomWebJob** | `BuyRooms.exe` | `MediciBuyRooms/` (local) | רכישת חדרים מ-Opportunities |
| **LastPriceUpdate** | `LastPriceUpdate.exe` | `MediciUpdatePrices/` (local) | עדכון מחירים |

### 3. Shared Libraries

| Library | Purpose |
|---------|---------|
| `SharedLibrary/` | API wrappers (Innstant, GoGlobal, Medici), Repository, BuyRoomControl, PushRoomControl, Caching |
| `EFModel/` | Entity Framework models, BaseEF with all DB operations (~4173 lines) |
| `ApiInstant/` | Innstant API DTOs - Search, Book, PreBook, Content models |
| `ModelsLibrary/` | Shared model interfaces |
| `Extensions/` | SystemLog extension methods |
| `Notifications/` | Email/notification handling via SendGrid |
| `SlackLibrary/` | Slack integration for alerts |

### 4. Web Scraping Services

| Service | Purpose |
|---------|---------|
| `WebHotel/` | Web scraping for hotel data |
| `WebHotelLib/` | WebDriver processing library |
| `WebHotelRevise/` | Web hotel data revision/updates |
| `WebInnstant/` | Innstant-specific web scraping |
| `ProcessRevisedFile/` | Processing revised data files |

### 5. Agent & Other

| Service | Purpose |
|---------|---------|
| `MediciAgent/` | Agent service (details TBD) |

---

## Azure Infrastructure

### App Service
- **Name:** `medici-backend`
- **Location:** East US 2
- **Resource Group:** `Medici-RG`
- **Subscription:** `2da025cc-dfe5-450f-a18f-10549a3907e3`

### Azure SQL Database
- **Server:** `medici-sql-server.database.windows.net`
- **Database:** `medici-db`
- **Admin User:** `medici_sql_admin`

### Monitoring (created 2026-02-23)
- **Log Analytics Workspace:** `medici-monitor-law` (West Europe)
- **Action Group:** `medici-monitor-ag`
- **Workbook:** "Medici Ops Central Workbook"
- See [07-azure-monitoring.md](./07-azure-monitoring.md) for full details

---

## Data Flow Diagrams

### Flow 1: BuyRoom (Opportunity → Purchase → Push)
```
MED_Opportunities table
        │
        ▼
 GetNextOpportunityToBuy()      ← Stored Proc: MED_GetnextOֹֹpportunitiesTobuy
        │
        ▼
 SearchHotels (Innstant/GoGlobal)
        │
        ▼
 Filter by Category + Board + Bedding
        │
        ▼
 BuyRoom → PreBook → Book
        │
        ▼
 PushRoom → PushRates + PushAvailability to Zenith
```

### Flow 2: SalesOffice Processing (Order → Search → Map → Details)
```
SalesOffice.Orders table (WebJobStatus = NULL/In Progress)
        │
        ▼
 GetSalesOfficeOrdersList()
        │
        ▼
 GetInnstantHotelSearchData()   ← Innstant API search
        │
        ▼
 FilterByVenueId()              ← Match by Innstant_ZenithId
        │
        ▼
 GetRatePlanCodeAndInvTypeCode()
    └─ FindPushRatePlanCode()   ← Med_Hotels_ratebycat lookup
        │
        ▼
 AddSalesOfficeDetails()        ← Write to SalesOffice.Details
        │
        ▼
 UpdateWebJobStatus()           ← "Completed; Innstant Api Rooms: X; Rooms With Mapping: Y"
```

### Flow 3: Callback Processing (Details → Buy → Push)
```
SalesOffice.Details (IsProcessedCallback = false)
        │
        ▼
 ProcessCallBackCommitBySalesOffice()
        │
        ▼
 BuyRoom (via Innstant API)
        │
        ▼
 HandleSuccessInBuyRoom() / HandleFailInBuyRoom()
        │
        ▼
 CreateOpportunity() → AddToDbSalesOfficeBooking()
        │
        ▼
 PushRoom to Zenith channel
```

---

## External API Integrations

### 1. Innstant API (Source = 1)
- **Purpose:** Primary hotel search, prebook, book, cancellation
- **Endpoints:** Search → Poll → PreBook → Book → Cancel
- **Implementation:** `ApiInstant/ApiInstant.cs`, `SharedLibrary/ApiInnstant.cs`

### 2. GoGlobal API (Source = 2)
- **Purpose:** Secondary hotel search & booking
- **Implementation:** `ApiInstant/GoGlobal/`, `SharedLibrary/APIGoGlobal.cs`

### 3. Zenith Channel Manager
- **Purpose:** Push rates, availability, and restrictions to distribution channel
- **Implementation:** `ApiInstant/ApiInstantZenith.cs`
- **Operations:**
  - `PushRates` — Push room prices
  - `PushAvailabilityAndRestrictions` — Push room availability
- **Uses:** `HotelCode` (Innstant_ZenithId), `RatePlanCode`, `InvTypeCode`
