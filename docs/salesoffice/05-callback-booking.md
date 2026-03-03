# 05 – Callback, רכישה ודחיפה ל-Zenith

## סקירה

לאחר ש-Phase 1 (חיפוש ומיפוי) יוצר Details ב-`SalesOffice.Details`, Phase 2 מטפל ב-**Callback** – רכישת החדר בפועל מ-Innstant ודחיפתו ל-Zenith Channel Manager.

---

## מתי Callback רץ?

- `SalesOfficeCallbackService` מעבד Details עם `IsProcessedCallback = false`
- רץ באותו WebJob, לאחר שה-Details נכתבו
- כל Detail שטרם טופל → מועמד ל-BuyRoom

---

## זרימת Callback – Commit

```
ProcessCallBackCommitBySalesOffice()
│
├── 1. שליפת Details לא מטופלים
│      SELECT FROM [SalesOffice.Details] WHERE IsProcessedCallback = 0
│
├── 2. בדיקת מחיר
│      innstantPrice vs RoomPrice (מ-DB)
│      │
│      ├── מחיר Innstant > DB → HandleErrorInnstantRoomHigherPriceThanDb()
│      └── מחיר OK → המשך
│
├── 3. PreBook
│      PreBookAsync() → בדיקת זמינות ב-Innstant
│      │
│      ├── זמין → המשך
│      └── לא זמין → HandleErrorNoRoomInInnstantBasedOnHotelCategoryBoard()
│
├── 4. BuyRoom
│      BuyRoom() → הזמנה בפועל ב-Innstant
│      │
│      ├── הצליח → HandleSuccessInBuyRoom()
│      │            ├── CreateOpportunity()
│      │            ├── AddToDbSalesOfficeBooking()
│      │            └── Push to Zenith
│      │
│      └── נכשל → HandleFailInBuyRoom()
│
├── 5. עדכון Detail
│      IsProcessedCallback = true
│
└── 6. לוג
       SalesOfficeLogService.Log()
```

---

## שלבי Callback בפירוט

### 1. בחירת חדר מועמד
- `innstantRoomByCategoryAndRoomBoardWithLowestPrice` → בוחר את החדר עם **המחיר הנמוך ביותר** שמתאים ל-Category + Board

### 2. בדיקת מחיר
- משווה את מחיר Innstant למחיר שנשמר ב-`SalesOffice.Details`
- אם מחיר Innstant **גבוה יותר**: `HandleErrorInnstantRoomHigherPriceThanDb()`
  - נרשם בלוג
  - ה-Detail מסומן כטופל (עם שגיאה)

### 3. PreBook
```
ApiRequestInnstantService.PreBookAsync()
  → שולח בקשת PreBook ל-Innstant
  → מקבל אישור זמינות + מחיר סופי
```

### 4. BuyRoom (הזמנה בפועל)
```
ApiInnstantService.BuyRoom()
  │
  ├── CreateCustomer() → יצירת/שליפת לקוח
  ├── SetAdults() / SetAdultsAndChildrens() → הגדרת אורחים
  └── BookAsync() → שליחת הזמנה ל-Innstant API
```

**תוצאות BuyRoom:**
| תוצאה | Handler | פעולה |
|---|---|---|
| ✅ הצלחה | `HandleSuccessInBuyRoom()` | Opportunity + Booking + Push |
| ❌ חדר לא נמצא | `HandleErrorNoRoomInInnstant...()` | לוג + סימון |
| ❌ מחיר גבוה | `HandleErrorInnstantRoomHigher...()` | לוג + סימון |
| ❌ כשל כללי | `HandleFailInBuyRoom()` | לוג + סימון |
| ❌ Exception | `HandleTryCatchInMethod()` | לוג |

---

## HandleSuccessInBuyRoom – מה קורה בהצלחה?

```
HandleSuccessInBuyRoom()
│
├── 1. CreateOpportunity()
│      INSERT INTO MED_Opportunities
│      ├── PushHotelCode = HotelId
│      ├── PushRatePlanCode = מ-ratebycat
│      ├── PushInvTypeCode = מ-ratebycat
│      ├── PushPrice = מחיר
│      ├── DateForm / DateTo
│      └── PaxAdultsCount / PaxChildrenCount
│
├── 2. AddToDbSalesOfficeBooking()
│      INSERT INTO [SalesOffice.Bookings]
│      ├── SalesOfficeDetailId
│      ├── SalesOfficeOrderId
│      └── [פרטי הזמנה]
│
├── 3. Push to Zenith (via PushRoomControl)
│      ├── PushRates() → מחירים
│      └── PushAvailabilityAndRestrictions() → זמינות
│
└── 4. UpdateBookingStatus()
       עדכון סטטוס Booking ב-DB
```

---

## Push ל-Zenith – פרטים טכניים

### PushRoomControl (SharedLibrary)
```csharp
// PushRates – דחיפת מחירים
PushRates(
    zenithId,         // Innstant_ZenithId מ-Med_Hotels
    ratePlanCode,     // מ-ratebycat
    invTypeCode,      // מ-ratebycat
    price,            // מחיר
    dateFrom, dateTo, // תאריכים
    currency          // מטבע (USD)
)

// PushAvailabilityAndRestrictions – דחיפת זמינות
PushAvailabilityAndRestrictions(
    zenithId,
    ratePlanCode,
    invTypeCode,
    availability,     // מס' חדרים זמינים
    dateFrom, dateTo
)
```

### ApiInstantZenith
- מתקשר ל-Zenith Channel Manager API
- משתמש ב-XML format
- כתובות ראה `ApiInstant/ApiInstantZenith.cs`

---

## זרימת Callback – Cancel

```
ProcessCallBackCancelBySalesOffice()
│
├── 1. GetCancellation()
│      שליפת תנאי ביטול מ-Innstant
│      (penalty, deadline)
│
├── 2. BookCancel()
│      ביטול ההזמנה ב-Innstant API
│
├── 3. UpdateBookingStatus()
│      עדכון סטטוס ל-Cancelled
│
└── 4. Log()
```

---

## Opportunity → BuyRoomWebJob (תהליך מקביל)

ה-`CreateOpportunity()` כותב ל-`MED_Opportunities`. טבלה זו משרתת **גם** את `BuyRoomWebJob` (פרויקט MediciBuyRooms):

```
BuyRoomWebJob (MediciBuyRooms/MainLogic.cs)
│
├── while(true)
│   ├── GetNextOpportunityToBuy()
│   │   └── SP: MED_GetnextOppportunitiesTobuy
│   │
│   ├── Search → BookRooms → PushRoom
│   └── sleep
```

**ההבדל בין SalesOffice ל-BuyRoom:**
| | SalesOffice | BuyRoomWebJob |
|---|---|---|
| מקור | Control Panel Orders | MED_Opportunities (ידני/אחר) |
| חיפוש | לפי יעד+תאריכים | לפי Opportunity ספציפי |
| WebJob | AzureWebJob | BuyRoomWebJob |
| Code Location | OnlyNight (Azure only) | MediciBuyRooms (local) |

---

## לוגים (SalesOfficeLogService)

### UpdateWebJobStatus()
```sql
-- עדכון סטטוס ב-Orders
UPDATE [SalesOffice.Orders]
SET WebJobStatus = 'Completed; Innstant Api Rooms: 10; Rooms With Mapping: 3'
WHERE Id = @OrderId
```

### Log()
```sql
-- כתיבת שורת לוג
INSERT INTO [SalesOffice.Log]
(ActionId, ActionResultId, Message, DateCreated, ...)
VALUES (@actionId, @resultId, @message, GETDATE(), ...)
```

### UpdateExistLog()
```sql
-- עדכון לוג קיים (למשל הוספת תוצאה)
UPDATE [SalesOffice.Log] SET ... WHERE Id = @logId
```

---

## Error Handling Summary

```
┌──────────────────────────────────────────────┐
│           Error Handler Matrix               │
├──────────────────────┬───────────────────────┤
│ Error Type           │ Handler               │
├──────────────────────┼───────────────────────┤
│ Room not found       │ HandleErrorNoRoom...  │
│ Price too high       │ HandleErrorHigher...  │
│ BuyRoom failed       │ HandleFailInBuyRoom   │
│ BuyRoom succeeded    │ HandleSuccessInBuyRoom│
│ General exception    │ HandleTryCatchInMethod │
│ Cancel               │ ProcessCallBackCancel │
└──────────────────────┴───────────────────────┘
```

---

*ראה [06-troubleshooting-ops.md](06-troubleshooting-ops.md) לפתרון בעיות →*
