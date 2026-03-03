# 02 – טבלאות מסד הנתונים (SalesOffice)

> Azure SQL: `medici-sql-server.database.windows.net` → Database: `medici-db`

---

## טבלאות ליבה של SalesOffice

### SalesOffice.Orders
הזמנות SalesOffice – כל שורה = בקשת חיפוש ליעד + טווח תאריכים.

| עמודה | טיפוס | תיאור |
|---|---|---|
| `Id` | int (PK, Identity) | מזהה ייחודי |
| `DateInsert` | datetime | תאריך יצירת ההזמנה |
| `DestinationType` | int | סוג יעד (עיר/אזור) |
| `DestinationId` | int | מזהה היעד ב-Innstant |
| `DateFrom` | date | תאריך Check-in |
| `DateTo` | date | תאריך Check-out |
| `UserId` | int | המשתמש שיצר את ההזמנה |
| `IsActive` | bit | האם ההזמנה פעילה |
| `WebJobStatus` | nvarchar(max) | סטטוס עיבוד |

**ערכי WebJobStatus:**
| ערך | משמעות |
|---|---|
| `NULL` | ממתין לעיבוד – WebJob יאסוף אותו |
| `'In Progress'` | WebJob מעבד כרגע |
| `'Completed; Innstant Api Rooms: X; Rooms With Mapping: Y'` | הושלם – X חדרים מ-API, Y מופו |

---

### SalesOffice.Details
חדרים ספציפיים שנמצאו ומופו – כל שורה = חדר אחד.

| עמודה | טיפוס | תיאור |
|---|---|---|
| `Id` | int (PK, Identity) | מזהה ייחודי |
| `DateCreated` | datetime | תאריך יצירה |
| `DateUpdated` | datetime | תאריך עדכון אחרון |
| `SalesOfficeOrderId` | int (FK → Orders.Id) | קשר ל-Order |
| `HotelId` | int (FK → Med_Hotels) | מזהה מלון ב-Medici |
| `RoomCategory` | int | קטגוריית חדר (1=Standard, 2=Superior, 4=Deluxe, 12=Suite) |
| `RoomBoard` | int | בסיס ארוחות (1=RO, 2=BB, 3=HB, 4=FB, 5=AI) |
| `RoomPrice` | decimal | מחיר החדר |
| `RoomCode` | nvarchar | קוד החדר ב-Innstant |
| `IsProcessedCallback` | bit | האם עבר Callback (רכישה) |

**IsProcessedCallback:**
- `0` (false) → ממתין לעיבוד Callback
- `1` (true) → נרכש או טופל

---

### SalesOffice.Bookings
הזמנות שהושלמו בהצלחה – BuyRoom הצליח.

| עמודה | טיפוס | תיאור |
|---|---|---|
| `Id` | int (PK, Identity) | מזהה ייחודי |
| `SalesOfficeDetailId` | int (FK → Details.Id) | קשר ל-Detail |
| `SalesOfficeOrderId` | int (FK → Orders.Id) | קשר ל-Order |
| *עמודות נוספות* | *משתנה* | *פרטי ההזמנה מ-Innstant* |

---

### SalesOffice.Log
לוג אירועים של כל הפעולות.

| עמודה | טיפוס | תיאור |
|---|---|---|
| `Id` | int (PK, Identity) | מזהה ייחודי |
| *ActionId* | int | FK ל-LogActionsDictionary |
| *ActionResultId* | int | FK ל-LogActionsResultDictionary |
| *Message* | nvarchar(max) | הודעת לוג |
| *DateCreated* | datetime | תאריך |

---

### SalesOffice.LogActionsDictionary
מילון פעולות ללוג.

### SalesOffice.LogActionsResultDictionary
מילון תוצאות פעולות ללוג.

---

## טבלאות תומכות (Medici Core)

### Med_Hotels
טבלת מלונות ראשית.

| עמודה חשובה | טיפוס | תיאור |
|---|---|---|
| `HotelId` | int (PK) | מזהה מלון |
| `Name` | nvarchar | שם המלון |
| `Innstant_ZenithId` | int | **VenueId ב-Zenith** – חייב >0 למיפוי |
| `isActive` | bit | **חייב =1 כדי שיימצא** |
| `InnstantHotelId` | int | מזהה ב-Innstant |
| `CityId` | int | עיר |

**תנאי סינון SalesOffice:**
```sql
WHERE Innstant_ZenithId > 0 AND isActive = 1
```

---

### Med_Hotels_ratebycat
טבלת מיפוי Board+Category → RatePlanCode + InvTypeCode.

| עמודה | טיפוס | תיאור |
|---|---|---|
| `Id` | int (PK, Identity) | מזהה ייחודי |
| `HotelId` | int (FK → Med_Hotels) | מזהה מלון |
| `BoardId` | int (FK → MED_Boards) | בסיס ארוחות |
| `CategoryId` | int (FK → MED_Room_Categories) | קטגוריית חדר |
| `RatePlanCode` | nvarchar | קוד RatePlan לדחיפה ל-Zenith |
| `InvTypeCode` | nvarchar | קוד InvType לדחיפה ל-Zenith |

**דוגמה:**
| Id | HotelId | BoardId | CategoryId | RatePlanCode | InvTypeCode |
|---|---|---|---|---|---|
| 852 | 20702 | 1 | 1 | 12045 | STD |
| 855 | 20702 | 1 | 12 | 12045 | SUI |
| 853 | 24982 | 1 | 1 | 12048 | STD |
| 854 | 24982 | 1 | 12 | 12048 | SUI |

---

### MED_Boards
רפרנס בסיסי ארוחות.

| BoardId | Description |
|---|---|
| 1 | Room Only (RO) |
| 2 | Bed & Breakfast (BB) |
| 3 | Half Board (HB) |
| 4 | Full Board (FB) |
| 5 | All Inclusive (AI) |
| 6 | Continental Breakfast (CB) |
| 7 | Bed (BD) |

---

### MED_Room_Categories
רפרנס קטגוריות חדרים.

| CategoryId | Description |
|---|---|
| 1 | Standard |
| 2 | Superior |
| 3 | Dormitory |
| 4 | Deluxe |
| 12 | Suite |

---

### MED_ֹOֹֹpportunities
הזדמנויות לרכישה – נוצרות ע"י SalesOffice Callback.

| עמודה חשובה | טיפוס | תיאור |
|---|---|---|
| `OpportunityId` | int (PK) | מזהה |
| `PushHotelCode` | int | מזהה מלון |
| `BoardId` | int | בסיס ארוחות |
| `CategoryId` | int | קטגוריית חדר |
| `DateForm` / `DateTo` | date | תאריכי שהייה |
| `PaxAdultsCount` | int | מס' מבוגרים |
| `PaxChildrenCount` | int | מס' ילדים |
| `PushBookingLimit` | int | מגבלת הזמנות |
| `PushRatePlanCode` | nvarchar | קוד RatePlan |
| `PushInvTypeCode` | nvarchar | קוד InvType |
| `PushPrice` | decimal | מחיר דחיפה |
| `PushCurrency` | nvarchar | מטבע |

---

## דיאגרמת קשרים

```
SalesOffice.Orders ──1:N──► SalesOffice.Details ──1:1──► SalesOffice.Bookings
       │                           │
       │                           │
       ▼                           ▼
SalesOffice.Log              Med_Hotels ──1:N──► Med_Hotels_ratebycat
                                   │
                                   ▼
                           MED_Opportunities
                                   │
                              ┌────┴────┐
                              ▼         ▼
                         MED_Boards  MED_Room_Categories
```

---

## Naming Convention

> **חשוב:** טבלאות SalesOffice משתמשות בנקודה (dot notation) כחלק מהשם:
> - `[SalesOffice.Orders]` ← צריך brackets בשאילתות SQL
> - `[SalesOffice.Details]`
> - `[SalesOffice.Bookings]`
> - `[SalesOffice.Log]`

**שגיאה נפוצה:**
```sql
-- ❌ לא יעבוד:
SELECT * FROM SalesOffice.Orders
-- ✅ נכון:
SELECT * FROM [SalesOffice.Orders]
```

---

*ראה [04-mapping-logic.md](04-mapping-logic.md) לפרטי FindPushRatePlanCode →*
