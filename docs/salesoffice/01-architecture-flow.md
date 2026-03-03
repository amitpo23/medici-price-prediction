# 01 – ארכיטקטורה וזרימת תהליך SalesOffice

## סקירה כללית

מערכת SalesOffice היא מנוע אוטומטי שמקבל הזמנות (Orders) מ-Control Panel, מחפש חדרי מלון ב-**Innstant API**, מבצע מיפוי למלונות של Medici, רוכש חדרים, ודוחף אותם ל-**Zenith Channel Manager**.

---

## שכבות המערכת

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTROL PANEL (UI)                          │
│  Medici-Control-Panel → יצירת Orders חדשים                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ INSERT INTO SalesOffice.Orders
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AZURE SQL DATABASE (medici-db)                │
│  SalesOffice.Orders │ SalesOffice.Details │ SalesOffice.Bookings│
│  SalesOffice.Log    │ Med_Hotels          │ Med_Hotels_ratebycat│
│  MED_Opportunities  │ MED_Boards          │ MED_Room_Categories │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              AZURE WEBJOB – AzureWebJob.exe                     │
│              (פרויקט OnlyNight – Continuous, Singleton)          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Timer Function: ProcessSalesOfficeOrders (5 min)   │        │
│  │                                                      │        │
│  │  SalesOfficeService.Run()                            │        │
│  │    ├── GetSalesOfficeOrdersList()                    │        │
│  │    ├── IsValidDateRange()                            │        │
│  │    ├── GetInnstantHotelSearchData()  ──► Innstant API│        │
│  │    ├── FilterByVenueId()                             │        │
│  │    ├── GetRatePlanCodeAndInvTypeCode()               │        │
│  │    ├── CreateFlattenedHotels()                       │        │
│  │    ├── AddSalesOfficeDetails()                       │        │
│  │    └── UpdateWebJobStatus()                          │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  SalesOfficeCallbackService                         │        │
│  │    ├── ProcessCallBackCommitBySalesOffice()          │        │
│  │    │     ├── BuyRoom() ──────────────► Innstant API  │        │
│  │    │     ├── CreateOpportunity()                     │        │
│  │    │     ├── AddToDbSalesOfficeBooking()             │        │
│  │    │     └── PushToZenith ──────────► Zenith CM      │        │
│  │    ├── ProcessCallBackCancelBySalesOffice()          │        │
│  │    ├── HandleErrorNoRoomInInnstant...()              │        │
│  │    ├── HandleErrorInnstantRoomHigherPrice...()       │        │
│  │    └── HandleFailInBuyRoom()                         │        │
│  └─────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────┐    ┌──────────────────────┐
│   INNSTANT API      │    │   ZENITH CHANNEL MGR │
│  - SearchHotels     │    │  - PushRates         │
│  - PreBook          │    │  - PushAvailability  │
│  - Book             │    │  - Via ApiInstantZenith│
│  - GetCancellation  │    │                      │
└─────────────────────┘    └──────────────────────┘
```

---

## זרימת התהליך – Phase 1: חיפוש ומיפוי

### שלב 1 – יצירת Order
- משתמש ב-Control Panel יוצר הזמנה חדשה
- נכתבת שורה ב-`SalesOffice.Orders` עם:
  - `DestinationType` + `DestinationId` (יעד – עיר/אזור)
  - `DateFrom` + `DateTo` (טווח תאריכים)
  - `WebJobStatus = NULL` (ממתין לעיבוד)

### שלב 2 – WebJob מזהה Order חדש
- `ProcessSalesOfficeOrders` רץ כל **5 דקות**
- `GetSalesOfficeOrdersList()` שולף Orders עם `WebJobStatus IS NULL OR WebJobStatus = 'In Progress'`
- WebJob מעדכן סטטוס ל-`'In Progress'`

### שלב 3 – אימות תאריכים
- `IsValidDateRange()` – בודק שטווח התאריכים תקין ועתידי

### שלב 4 – חיפוש ב-Innstant API
- `GetInnstantHotelSearchData()` → שולח בקשת חיפוש ליעד+תאריכים
- משתמש ב-`ApiRequestInnstantService`:
  - `SearchHotels()` → יוצר סשן חיפוש
  - `SearchResultsSession()` / `SearchResultsSessionPoll()` → Poll לתוצאות
  - `SearchResultsSessionHotelDetails()` → פרטי מלון

### שלב 5 – סינון לפי VenueId
- `FilterByVenueId()` → סורק רק מלונות שעומדים בתנאים:
  - `isActive = True` בטבלת `Med_Hotels`
  - `Innstant_ZenithId > 0` (= VenueId ב-Zenith)
- **מלונות בלי ZenithId או לא פעילים – ידלגו!**

### שלב 6 – מיפוי RatePlan
- `GetRatePlanCodeAndInvTypeCode()` → לכל חדר שנמצא:
  - קורא ל-`FindPushRatePlanCode(hotelId, boardId, categoryId)`
  - מחפש שורת התאמה ב-`Med_Hotels_ratebycat`
  - אם נמצא → `RatePlanCode` + `InvTypeCode` ✅
  - אם לא נמצא → `(null, null)` → **החדר לא ייספר ב-"Rooms With Mapping"** ❌

### שלב 7 – יצירת Details
- `CreateFlattenedHotels()` → מישור תוצאות לרשימה שטוחה
- `AddSalesOfficeDetails()` → כותב לטבלת `SalesOffice.Details`:
  - `HotelId`, `RoomCategory`, `RoomBoard`, `RoomPrice`, `RoomCode`
  - `IsProcessedCallback = false`

### שלב 8 – עדכון סטטוס
- `UpdateWebJobStatus()` → כותב ל-`WebJobStatus`:
  ```
  Completed; Innstant Api Rooms: X; Rooms With Mapping: Y
  ```
  - **X** = סה"כ חדרים שנמצאו ב-Innstant
  - **Y** = חדרים שמופו בהצלחה (יש להם ratebycat)

---

## זרימת התהליך – Phase 2: Callback (רכישה ודחיפה)

### שלב 9 – עיבוד Callback
- `ProcessCallBackCommitBySalesOffice()` → מעבד Details שלא טופלו:
  - סורק `SalesOffice.Details` עם `IsProcessedCallback = false`
  - בודק מחיר Innstant מול מחיר DB

### שלב 10 – BuyRoom
- `BuyRoom()` → קורא ל-Innstant API:
  - `PreBookAsync()` → אימות זמינות
  - `BookAsync()` → הזמנה בפועל
  - `CreateCustomer()` → יצירת לקוח (אם נדרש)

### שלב 11 – טיפול בשגיאות
| מקרה | Handler |
|---|---|
| חדר לא נמצא | `HandleErrorNoRoomInInnstantBasedOnHotelCategoryBoard()` |
| מחיר גבוה מ-DB | `HandleErrorInnstantRoomHigherPriceThanDb()` |
| כשל ברכישה | `HandleFailInBuyRoom()` |
| כשל כללי | `HandleTryCatchInMethod()` |

### שלב 12 – יצירת Opportunity
- `CreateOpportunity()` → כותב ל-`MED_Opportunities`:
  - כולל `PushRatePlanCode`, `PushInvTypeCode`, `PushHotelCode`, מחיר
  - זו ה-Opportunity ש-`BuyRoomWebJob` יכול לקלוט (אם מופעל)

### שלב 13 – שמירת Booking
- `AddToDbSalesOfficeBooking()` → כותב ל-`SalesOffice.Bookings`
- `UpdateBookingStatus()` → מעדכן סטטוס

### שלב 14 – Push ל-Zenith
- דרך `PushRoomControl`:
  - `PushRates()` → דחיפת מחירים
  - `PushAvailabilityAndRestrictions()` → דחיפת זמינות
  - משתמש ב-`ApiInstantZenith` → Zenith Channel Manager API

---

## זרימת תהליך ביטול

```
ProcessCallBackCancelBySalesOffice()
  ├── GetCancellation() → בדיקת תנאי ביטול
  ├── BookCancel() → ביטול ב-Innstant
  └── UpdateBookingStatus() → עדכון סטטוס ב-DB
```

---

## תפקודי Timer נוספים ב-WebJob

| Timer Function | תדירות | תיאור |
|---|---|---|
| `ProcessSalesOfficeOrders` | 5 דקות | **עיקרי** – עיבוד הזמנות SalesOffice |
| `ProcessPreSearchResultsSessionPollLog` | ? | ניטור סשנים של חיפוש |
| `UpdateAISearchHotelDataTable` | ? | עדכון טבלת חיפוש AI |
| `UpdateHotelsFromApi` | ? | עדכון נתוני מלונות מ-Innstant API |

---

## תלויות חיצוניות

| שירות | שימוש |
|---|---|
| **Innstant API** | חיפוש מלונות, PreBook, Book, Cancellation |
| **Zenith Channel Manager** | דחיפת מחירים וזמינות |
| **Azure SQL (medici-db)** | כל טבלאות SalesOffice + Med_Hotels |
| **Azure App Service** | hosting ל-WebJob |

---

*ראה [02-database-tables.md](02-database-tables.md) לפרטי טבלאות →*
