# 03 - WebJobs & OnlyNight Project / שירותי WebJob

## Overview

Azure App Service `medici-backend` runs **4 Continuous WebJobs**. All run continuously alongside the main web API.

---

## WebJob Inventory

| # | WebJob Name | Executable | SDK | Source Project | Status |
|---|-------------|-----------|-----|---------------|--------|
| 1 | `AutoCancellation` | `AutoCancellation.exe` | No | `MediciAutoCancellation/` (local) | Running |
| 2 | **`AzureWebJob`** | `AzureWebJob.exe` | **Yes** (WebJobs SDK) | **OnlyNight project (NOT local)** | Running, Singleton |
| 3 | `BuyRoomWebJob` | `BuyRooms.exe` | No | `MediciBuyRooms/` (local) | Running |
| 4 | `LastPriceUpdate` | `LastPriceUpdate.exe` | No | `MediciUpdatePrices/` (local) | Running |

**Note:** No triggered WebJobs exist.

---

## 1. AutoCancellation WebJob

### Source: `MediciAutoCancellation/MainLogic.cs`
### Purpose: ביטול אוטומטי של הזמנות שתקופת הביטול שלהן עברה

### Flow:
```
Process()
  │
  ├── GetBookIdsToCancel()         ← Get bookings past cancellation date
  │
  ├── For each preBookId:
  │     ├── CancelBooking_v2()     ← Cancel via API
  │     ├── If manual cancel needed:
  │     │     ├── Log to Slack
  │     │     └── Queue for email
  │     └── Continue to next
  │
  └── If manual cancels:
        └── SendEmail() via SendGrid  ← "Please cancel manually these rooms"
```

### Configuration: `MediciAutoCancellation/appsettings.json`
- SendGridApiKey
- FromEmail / ToEmail
- SQLServer connection string
- SlackChannel

---

## 2. AzureWebJob (OnlyNight Project) ⭐ CRITICAL

### THIS IS THE MAIN SALESOFFICE PROCESSOR

### Source: **OnlyNight** separate project — NOT available in local `medici-hotels` solution
### Deployed directly to Azure as `AzureWebJob.exe`
### Settings: `{"is_singleton": true}` — only one instance runs at a time
### Schedule: Every 5 minutes (timer-triggered)

### Deployed DLLs:
| DLL | Size | Purpose |
|-----|------|---------|
| `AzureWebJob.dll` | 13 KB | Entry point — 4 timer functions |
| `OnlyNight.Services.dll` | ~large | All business logic |
| `OnlyNight.Data.dll` | ~medium | EF DbContext with SalesOffice tables |
| `OnlyNight.Models.dll` | ~medium | DTOs and model classes |
| `OnlyNight.Entities.dll` | ~medium | Entity classes |
| `OnlyNight.Notifications.dll` | small | Notification handling |
| `OnlyNight.Logging.dll` | small | Logging |

### 4 Timer Functions (in AzureWebJob.dll):

```csharp
namespace AzureWebJob.Functions
{
    // 1. Process SalesOffice orders — THE MAIN ONE
    class ProcessSalesOfficeOrders { async Task Run(TimerInfo timer) { ... } }
    
    // 2. Process pre-search session poll logs
    class ProcessPreSearchResultsSessionPollLog { async Task Run(TimerInfo timer) { ... } }
    
    // 3. Update AI Search hotel data
    class UpdateAISearchHotelDataTable { async Task Run(TimerInfo timer) { ... } }
    
    // 4. Update hotels from Innstant API
    class UpdateHotelsFromApi { async Task Run(TimerInfo timer) { ... } }
}
```

### OnlyNight.Services Namespace Structure:
```
OnlyNight.Services.Services/
  ├── BaseEF                          ← DB operations (includes FindPushRatePlanCode)
  ├── Repository                      ← Data access layer
  ├── ApiInnstantService              ← Innstant API integration
  │     ├── BuyRoom()
  │     ├── CreateCustomer()
  │     ├── SetAdults()
  │     └── SetAdultsAndChildrens()
  ├── ApiRequestInnstantService       ← HTTP requests to Innstant
  │     ├── SearchHotels()
  │     ├── SearchResultsSession()
  │     ├── SearchResultsSessionPoll()
  │     ├── SearchResultsSessionCommon()
  │     ├── SearchResultsSessionHotelDetails()
  │     ├── PreBookAsync()
  │     ├── BookAsync()
  │     ├── BookCancel()
  │     ├── GetCancellation()
  │     ├── GetUserCreditCard()
  │     ├── GetBookingDetailsJsonAsync()
  │     ├── GetAetherAccessTokenByUserId()
  │     └── PopulateCancellationDetails()
  │
  └── WebJob/
        ├── SalesOfficeService          ← ⭐ MAIN PROCESSING
        │     ├── Run()                 ← Entry point
        │     ├── GetSalesOfficeOrdersList()
        │     ├── GetAvailableToProceedDetails()
        │     ├── PrepareDetailsToDelete()
        │     ├── IsValidDateRange()
        │     ├── GetRatePlanCodeAndInvTypeCode()
        │     ├── GetInnstantHotelSearchData()
        │     ├── FilterByVenueId()
        │     ├── CreateFlattenedHotels()
        │     ├── AddSalesOfficeDetails()
        │     ├── UpdateSalesOfficeDetails()
        │     ├── DeleteSalesOfficeDetails()
        │     └── UpdateSalesOfficeDetailAsync()
        │
        ├── SalesOfficeCallbackService  ← CALLBACK/BUY PROCESSING
        │     ├── ProcessCallBackCommitBySalesOffice()
        │     ├── ProcessCallBackCancelBySalesOffice()
        │     ├── HandleErrorNoRoomInInnstantBasedOnHotelCategoryBoard()
        │     ├── HandleErrorInnstantRoomHigherPriceThanDb()
        │     ├── HandleFailInBuyRoom()
        │     ├── HandleSuccessInBuyRoom()
        │     ├── HandleTryCatchInMethod()
        │     ├── CreateOpportunity()
        │     ├── AddToDbSalesOfficeBooking()
        │     └── UpdateBookingStatus()
        │
        ├── SalesOfficeLogService       ← LOGGING
        │     ├── UpdateWebJobStatus()  ← Writes "Completed; ..." to Orders
        │     ├── Log()
        │     └── UpdateExistLog()
        │
        ├── SalesOfficeOrdersService    ← ORDERS CRUD
        │     ├── GetSalesOfficeOrders()
        │     ├── InsertSalesOfficeOrder()
        │     └── DeleteSalesOfficeOrders()
        │
        ├── SalesOfficeDetailsService   ← DETAILS CRUD
        │     └── GetSalesOfficeDetails()
        │
        ├── SalesOfficeBookingsService  ← BOOKINGS CRUD
        │     └── GetSalesOfficeBookings()
        │
        └── UpdateHotelsFromApiService  ← HOTEL SYNC
              └── CopyDataFromHotelInnstantToHotel()
```

### OnlyNight.Models:
```csharp
class SalesOfficeOrders       { string WebJobStatus; ... }
class SalesOfficeDetailsClass { int SalesOfficeDetailId; int SalesOfficeOrderId; ... }
class SalesOfficeBookingsClass { int SalesOfficeDetailId; int SalesOfficeOrderId; bool completed; ... }
class SalesOfficeOrdersDto
class SalesOfficeBookingsDto
class WebJobSalesOfficeDetailsDto
class SalesOfficeOrderInsert
class DeleteSalesOfficeOrder
class SalesOfficeDetails
class SalesOfficeLogActions
class SalesOfficeLogActionsResult
```

### OnlyNight.Data (DbContext):
```csharp
// DbSets:
DbSet<SalesOfficeOrders>  SalesOfficeOrders   → [SalesOffice.Orders]
DbSet<SalesOfficeDetails> SalesOfficeDetails   → [SalesOffice.Details]
DbSet<SalesOfficeBookings> SalesOfficeBookings → [SalesOffice.Bookings]
DbSet<SalesOfficeLogs>    SalesOfficeLogs      → [SalesOffice.Log]
```

### Reverse Engineering Files:
Binary analysis results saved at: `webjob-dlls/`
- `reflection.txt` — .NET reflection output (types & methods)
- `strings_services.txt` — All extracted strings from OnlyNight.Services.dll
- `flow_strings.txt` — RatePlan/VenueId related strings
- `data_strings.txt` — DbContext property strings from OnlyNight.Data.dll
- `models_strings.txt` — Model property strings from OnlyNight.Models.dll
- `sql_strings.txt` — SQL/Update operation strings

---

## 3. BuyRoomWebJob

### Source: `MediciBuyRooms/MainLogic.cs`
### Purpose: רכישת חדרים מתוך טבלת Opportunities

### Flow:
```
Process()
  │
  ├── GetAllSources()                ← Get active API sources (Innstant=1, GoGlobal=2)
  ├── GetCategories() + GetBoards()  ← Reference data
  │
  └── while(true):                   ← INFINITE LOOP
        │
        ├── GetNextOpportunityToBuy() ← Stored Proc: MED_GetnextOֹֹpportunitiesTobuy
        │
        ├── If opportunity found:
        │     ├── For each source:
        │     │     ├── GetHotelIdBySource()
        │     │     └── ApiMedici.SearchHotels()
        │     │
        │     ├── Filter by Category + Board + Bedding ("Double")
        │     │
        │     ├── If results found:
        │     │     ├── Sort by price ascending
        │     │     ├── For each room:
        │     │     │     ├── BuyRoom() → validates cancellation + dates
        │     │     │     ├── Source 1: ApiInnstant.BuyRoom() → PreBook → Book
        │     │     │     └── Source 2: APIGoGlobal.BuyRoom()
        │     │     │
        │     │     └── PushRoom() → PushRates + PushAvailability to Zenith
        │     │
        │     └── If no results:
        │           └── Log to MED_BackOfficeOptLog
        │
        └── If no opportunity:
              └── Sleep 200 seconds
```

### Key Method: `BuyRoomControl.BookRooms()`
1. Combine results from all sources
2. Filter by category + board + bedding (case-insensitive)
3. Validate cancellation policy (penalty=0, cancellation before departure)
4. Sort by price ascending (cheapest first)
5. For each, create Opportunity → PreBook → Book → Push

---

## 4. LastPriceUpdate WebJob

### Source: `MediciUpdatePrices/`
### Purpose: עדכון מחירי Push אחרון

---

## Kudu Access (for WebJob management)

```
Base URL: https://medici-backend.scm.azurewebsites.net
User:     $medici-backend
Password: DgFX5ZmRyla3i0T0iXid18zGfqrPRqZfvazrYwcart5xssLRh5wjGqW2hWZW

# List WebJobs
GET /api/continuouswebjobs

# View WebJob status
GET /api/continuouswebjobs/{name}

# View function status files
GET /api/vfs/data/jobs/continuous/AzureWebJob/AzureWebJob.Functions.ProcessSalesOfficeOrders.Run.status

# List deployed DLLs
GET /api/vfs/site/wwwroot/app_data/jobs/continuous/AzureWebJob/
```
