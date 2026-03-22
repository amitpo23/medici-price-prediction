# 06 - Codebase Reference / תיעוד קוד

## Solution Structure

**Solution file:** `Backend.sln`  
**Framework:** .NET (ASP.NET Core + Console Apps)

---

## Project Dependency Map

```
Backend.csproj (Web API)
  ├── SharedLibrary
  ├── EFModel
  ├── ApiInstant
  ├── Extensions
  ├── Notifications
  └── ModelsLibrary

MediciBuyRooms.csproj (WebJob)
  ├── SharedLibrary
  ├── ApiInstant
  └── Extensions

MediciAutoCancellation.csproj (WebJob)
  ├── SharedLibrary
  ├── Notifications
  └── Extensions

MediciUpdatePrices.csproj (WebJob)
  └── (TBD)

SharedLibrary.csproj
  ├── EFModel
  ├── ApiInstant
  ├── Extensions
  ├── WebHotelLib
  └── SlackLibrary

EFModel.csproj
  └── Microsoft.EntityFrameworkCore
```

---

## Key Classes & Methods

### 1. BaseEF (`EFModel/BaseEF.cs`) — ~4173 lines
> Central data access layer — ALL database operations

#### Critical Methods:

| Method | Line | Purpose |
|--------|------|---------|
| `FindPushRatePlanCode(hotelId, boardId, categoryId)` | ~3026 | Look up RatePlanCode + InvTypeCode from ratebycat |
| `GetPushRoomByOpportunityId(opportunityId)` | ~3047 | Get PushRoom object for opportunity |
| `GetPushRoom(bookingId)` | ~3100 | Get PushRoom by booking |
| `GetNextOpportunityToBuy()` | ~3880 | Execute SP `MED_GetnextOֹֹpportunitiesTobuy` |
| `GetAllSource()` | ~3873 | Get active API sources |
| `GetAllReservations()` | ~3897 | Get all bookings for back office |
| `FindAvailableRoomCount(...)` | varies | Count available rooms for push |
| `SearchOpportunity(resultHotel)` | varies | Search/create opportunity |
| `InsertPreBook(...)` | varies | Insert prebook record |
| `InsertBook(...)` | varies | Insert booking record |
| `CancelBooking_v2(preBookId, ...)` | varies | Cancel booking |
| `InsertLog(message)` | varies | Insert log entry |
| `MED_BackOfficeOptLog(...)` | varies | Back office log |

#### FindPushRatePlanCode — THE MAPPING METHOD:
```csharp
async Task<(string?, string?)> FindPushRatePlanCode(int hotelId, int boardId, int categoryId)
{
    using (var ctx = new MediciContext(ConnectionString))
    {
        var result = await ctx.MedHotelsRatebycats
            .FirstOrDefaultAsync(i => i.HotelId == hotelId &&
                                      i.BoardId == boardId &&
                                      i.CategoryId == categoryId);
        if (result != null)
            return (result.RatePlanCode, result.InvTypeCode);
        else
            return (null, null);   // ← causes "Rooms With Mapping: 0"
    }
}
```

#### GetPushRoomByOpportunityId — BUILDS PUSHROOM OBJECT:
```csharp
// Joins: MedOPportunities + MedBoards + MedRoomCategories + MedHotels
// Then calls FindPushRatePlanCode() to override RatePlanCode/InvTypeCode
// if a ratebycat mapping exists
```

---

### 2. MainLogic (`MediciBuyRooms/MainLogic.cs`) — 185 lines
> BuyRoomWebJob main processing loop

| Method | Purpose |
|--------|---------|
| `Process(waitAfterBuy)` | Main loop — while(true) get opportunity → search → buy → push |
| `Tests()` | Test method for search |
| `GetAllSources()` | Get active API source IDs |

#### Process Flow:
```csharp
while (true)
{
    var opportunity = await Repository.Instance.GetNextOpportunityToBuy();
    if (opportunity != null)
    {
        // 1. Search each source (Innstant, GoGlobal)
        // 2. Filter by Category + Board + Bedding
        // 3. BookRooms() → PreBook → Book
        // 4. PushRoom() to Zenith
        // 5. Wait 2 seconds
        // 6. UpdateOpportunityIdlastUpdate()
    }
    else
    {
        // Sleep 200 seconds
    }
}
```

---

### 3. BuyRoomControl (`SharedLibrary/BuyRoomControl.cs`) — 165 lines
> Room purchase logic and validation

| Method | Purpose |
|--------|---------|
| `BuyRoom(resultHotel)` | Validate and create opportunity |
| `Basicvalidity(resultHotel, dates)` | Check cancellation + dates |
| `ValidDates(dates)` | Date validation (currently always returns true) |
| `ValidCancellation(cancellation, dates)` | Check cancellation penalty = 0, date before tomorrow |
| `BookRooms(list, hotelId, from, to, category, board, bedding)` | Main booking orchestration |

#### BookRooms Logic:
```
1. Combine results from all sources
2. Filter: category + board + bedding (case-insensitive)
3. Filter: Basicvalidity (cancellation + dates)
4. Sort by price ascending
5. For each room:
   a. BuyRoom() → SearchOpportunity()
   b. Source 1: ApiInnstant.BuyRoom() → PreBook → Book
   c. Source 2: APIGoGlobal.BuyRoom()
6. Return (count, message)
```

#### Validation Rules:
- `ValidCancellation`: penalty amount = 0 AND cancellation from-date ≤ tomorrow
- `ValidDates`: Always returns true (validation commented out)
- `minDaysForCancellation = 6` (not currently used)
- `minDaysTobuy = 14` (not currently used)

---

### 4. PushRoomControl (`SharedLibrary/PushRoomControl.cs`) — 575 lines
> Push rates and availability to Zenith

| Method | Purpose |
|--------|---------|
| `PushRates(room)` | Push price to Zenith via `ApiInstantZenith.PushRates()` |
| `PushAvailabilityAndRestrictions(room)` | Push room count + availability status |
| `PushRoom(hotelId)` | Orchestrate full push for a hotel |

#### PushRates Parameters:
```csharp
pushRatesRequest.HotelCode = room.Innstant_ZenithId.ToString();  // VenueId
pushRatesRequest.InvTypeCode = room.PushInvTypeCode;              // STD, DLX, SUI
pushRatesRequest.RatePlanCodeor = room.PushRatePlanCode;          // e.g., '12045'
pushRatesRequest.AmountAfterTax = room.PushPrice.ToString();
pushRatesRequest.Start = room.DateForm.ToString("yyyy-MM-dd");
pushRatesRequest.End = room.DateForm.ToString("yyyy-MM-dd");
```

---

### 5. ApiInnstant (`SharedLibrary/ApiInnstant.cs`) — 162 lines
> Innstant-specific booking operations

| Method | Purpose |
|--------|---------|
| `CreateCustomer(firstName)` | Create customer object with random names |
| `BuyRoom(searchHotels, room, opportunityId, hotelId, from, to)` | Full buy flow: PreBook → Book |

#### BuyRoom Flow:
```
1. preBookInnstant() → Create prebook request from search results
2. ApiMedici.PreBook() → Call Innstant API for prebook
3. If prebook done:
   a. InsertPreBook() → Save to DB
   b. CreateCustomer() → Generate customer (random names from DB)
   c. new Book() → Create book request
   d. ApiMedici.Book() → Call Innstant API for booking
   e. If confirmed:
      - InsertBook() → Save to DB
      - Record success
   f. If error:
      - InsertBookError() → Save error
```

---

### 6. ApiMedici (`SharedLibrary/ApiMedici.cs`) — 76 lines
> Unified API facade for multiple sources

| Method | Purpose |
|--------|---------|
| `PreBook(preBook)` | Route to appropriate source for prebook |
| `Book(book, insertPreBook, source)` | Route booking: Source 1→Innstant, Source 2→GoGlobal |
| `SearchHotels(from, to, hotelId, type, source, currencies, adults)` | Route search: Source 1→Innstant, Source 2→GoGlobal |

---

### 7. Repository (`SharedLibrary/Repository.cs`) — 481 lines
> Singleton repository pattern wrapping BaseEF

- **Pattern:** Thread-safe Singleton with lazy initialization
- **Connection:** Reads from `appsettings.json` (ConnectionStrings.SQLServer)
- **Delegates:** All calls forwarded to `BaseEF` instance

#### Notable Methods:
| Method | Delegates To |
|--------|-------------|
| `GetNextOpportunityToBuy()` | `BaseEF.GetNextOpportunityToBuy()` |
| `InsertPreBook()` | `BaseEF.InsertPreBook()` |
| `InsertBook()` | `BaseEF.InsertBook()` |
| `SearchOpportunity()` | `BaseEF.SearchOpportunity()` |
| `CancelBooking_v2()` | `BaseEF.CancelBooking_v2()` |
| `GetPushRoom()` | `BaseEF.GetPushRoom()` |
| `FindAvailableRoomCount()` | `BaseEF.FindAvailableRoomCount()` |
| `InsertLog()` | `BaseEF.InsertLog()` |
| `PublishToSlack()` | Slack integration |

---

### 8. MediciAutoCancellation (`MediciAutoCancellation/MainLogic.cs`) — 81 lines
> Auto-cancel bookings past cancellation deadline

| Method | Purpose |
|--------|---------|
| `Process()` | Get bookings to cancel, attempt cancel, email failures |

#### Flow:
```
1. GetBookIdsToCancel()
2. For each: CancelBooking_v2()
3. If manual cancel needed:
   a. Log to Slack
   b. Accumulate text
4. SendEmail() via SendGrid for manual cancels
```

#### Config Properties:
- `SendGridApiKey`
- `FromEmail`, `ToEmail`

---

### 9. ApiInstant Namespace (`ApiInstant/`)
> Innstant API Data Transfer Objects

| Class | Purpose |
|-------|---------|
| `ApiInstant` | Main API client (SearchHotels, PreBook, Book, Cancel) |
| `ApiInstantZenith` | Zenith channel manager API (PushRates, PushAvailability) |
| `SearchHotels` / `SearchRequest` | Search DTOs |
| `PollHotel` / `ResultHotel` | Search results |
| `PreBook` / `preBookRes` | Prebook flow |
| `Book` / `BookRes` / `BookResulte` | Booking flow |
| `InsertBook` / `InsertPreBook` | DB insertion models |
| `PushRatesRequest` etc. | Push to Zenith DTOs |
| `Cancellation` | Cancellation policy |
| `Hotel` / `HotelBook` / `ContentBook` | Hotel data |

---

### 10. Backend Web API (`Backend/`)

| Component | Path | Purpose |
|-----------|------|---------|
| `Program.cs` | Backend/ | App startup, SignalR, CORS, DI |
| Controllers/ | Backend/Controllers/ | API endpoints |
| Hub/ | Backend/Hub/ | SignalR hub for real-time |
| Attributes/ | Backend/Attributes/ | Basic auth attribute |
| BHealthCheck.cs | Backend/ | Health check implementation |

---

## Configuration Files

### appsettings.json Pattern:
```json
{
  "ConnectionStrings": {
    "SQLServer": "Server=tcp:medici-sql-server.database.windows.net,1433;..."
  },
  "SlackChannel": "...",
  "SendGridApiKey": "...",
  "FromEmail": "...",
  "ToEmail": "..."
}
```

Projects with appsettings:
- `Backend/appsettings.json` + `appsettings.Development.json`
- `MediciAutoCancellation/appsettings.json`
- `MediciBuyRooms/appsettings.json` + `appsettings.Development.json`
- `ProcessRevisedFile/appsettings.json`
- `WebHotel/appsettings.json`
- `WebHotelRevise/appsettings.json`
