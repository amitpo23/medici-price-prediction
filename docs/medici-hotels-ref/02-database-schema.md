# 02 - Database Schema / מבנה מסד נתונים

## Connection Details
```
Server:   medici-sql-server.database.windows.net
Database: medici-db
User:     medici_sql_admin
Password: @Amit2025
Encrypt:  True
```

---

## Core Tables

### Med_Hotels
> טבלת המלונות הראשית

| Column | Type | Description |
|--------|------|-------------|
| `HotelId` | int (PK) | מזהה מלון ייחודי מ-Innstant |
| `Name` | nvarchar | שם המלון |
| `Innstant_ZenithId` | int | מזהה ב-Zenith Channel Manager |
| `isActive` | bit | האם המלון פעיל (חייב להיות 1 לעיבוד) |
| `Rating` | int | דירוג כוכבים |
| `City` | nvarchar | עיר |
| `Country` | nvarchar | מדינה |
| `Address` | nvarchar | כתובת |
| `latitude` | float | קואורדינטות |
| `longitude` | float | קואורדינטות |

**Critical Fields for SalesOffice Processing:**
- `Innstant_ZenithId` — MUST be > 0 for `FilterByVenueId()` to find the hotel
- `isActive` — MUST be True (1) for hotel to be included in searches

---

### Med_Hotels_ratebycat
> טבלת מיפוי RatePlanCode/InvTypeCode לפי מלון, לוח, וקטגוריה

| Column | Type | Description |
|--------|------|-------------|
| `Id` | int (PK, Identity) | מזהה שורה |
| `HotelId` | int (FK → Med_Hotels) | מזהה מלון |
| `BoardId` | int (FK → Med_Board) | מזהה לוח (1=RO, 2=BB...) |
| `CategoryId` | int (FK → Med_RoomCategories) | מזהה קטגוריה (1=Std, 4=DLX, 12=Suite) |
| `RatePlanCode` | nvarchar | קוד תוכנית מחיר (e.g., '12045') |
| `InvTypeCode` | nvarchar | קוד סוג מלאי (e.g., 'STD', 'DLX', 'SUI') |

**Critical:** `FindPushRatePlanCode(hotelId, boardId, categoryId)` queries this table.  
If no matching row → returns `(null, null)` → "Rooms With Mapping: 0"

---

### SalesOffice Schema

#### SalesOffice.Orders
> הזמנות SalesOffice לעיבוד

| Column | Type | Description |
|--------|------|-------------|
| `Id` | int (PK, Identity) | מזהה הזמנה |
| `DateInsert` | datetime | תאריך הכנסה |
| `DestinationType` | nvarchar | סוג יעד |
| `DestinationId` | int | מזהה יעד (city/area) |
| `DateFrom` | date | תאריך כניסה |
| `DateTo` | date | תאריך יציאה |
| `UserId` | int | מזהה משתמש |
| `IsActive` | bit | האם ההזמנה פעילה |
| `WebJobStatus` | nvarchar(MAX) | סטטוס עיבוד WebJob |

**WebJobStatus Values:**
- `NULL` — ממתין לעיבוד
- `"In Progress"` — בעיבוד
- `"Completed; Innstant Api Rooms: X; Rooms With Mapping: Y"` — הושלם

#### SalesOffice.Details
> פרטי חדרים שנמצאו עבור כל הזמנה

| Column | Type | Description |
|--------|------|-------------|
| `Id` | int (PK, Identity) | מזהה |
| `DateCreated` | datetime | תאריך יצירה |
| `DateUpdated` | datetime | תאריך עדכון |
| `SalesOfficeOrderId` | int (FK → Orders) | מזהה הזמנה |
| `HotelId` | int | מזהה מלון |
| `RoomCategory` | nvarchar | קטגוריית חדר |
| `RoomBoard` | nvarchar | סוג לוח |
| `RoomPrice` | decimal | מחיר חדר |
| `RoomCode` | nvarchar | קוד חדר |
| `IsProcessedCallback` | bit | האם עובד כ-callback |

#### SalesOffice.Bookings
> הזמנות שבוצעו דרך SalesOffice

| Column | Type | Description |
|--------|------|-------------|
| `Id` | int (PK) | מזהה |
| `SalesOfficeDetailId` | int (FK → Details) | מזהה פרט |
| `SalesOfficeOrderId` | int (FK → Orders) | מזהה הזמנה |
| `WebJobStatus` | nvarchar | סטטוס |

#### SalesOffice.Log
> לוג פעולות SalesOffice

#### SalesOffice.LogActionsDictionary
> מילון פעולות לוג

#### SalesOffice.LogActionsResultDictionary  
> מילון תוצאות פעולות לוג

---

### MED_ֹOֹֹpportunities
> הזדמנויות לרכישת חדרים (שימו לב: תווים עבריים בשם הטבלה)

| Column | Type | Description |
|--------|------|-------------|
| `OpportunityId` | int (PK, Identity) | מזהה הזדמנות |
| `DateForm` | datetime | תאריך כניסה |
| `DateTo` | datetime | תאריך יציאה |
| `DestinationsId` | int | מזהה מלון |
| `PaxAdultsCount` | int | מספר מבוגרים |
| `PaxChildrenCount` | int | מספר ילדים |
| `BoardId` | int | מזהה לוח |
| `CategoryId` | int | מזהה קטגוריה |
| `PushHotelCode` | int | קוד מלון ל-Push |
| `PushRatePlanCode` | nvarchar | קוד תוכנית מחיר |
| `PushInvTypeCode` | nvarchar | קוד סוג מלאי |
| `PushBookingLimit` | int | מגבלת הזמנות |
| `PushPrice` | float | מחיר ל-Push |
| `PushCurrency` | nvarchar | מטבע |
| `PreBookId` | int | מזהה PreBook |

**Accessed by:** BuyRoomWebJob via stored proc `MED_GetnextOֹֹpportunitiesTobuy`

---

### Reference Tables

#### Med_Board
| BoardId | BoardCode | Description |
|---------|-----------|-------------|
| 1 | RO | Room Only |
| 2 | BB | Bed & Breakfast |
| 3 | HB | Half Board |
| 4 | FB | Full Board |
| 5 | AI | All Inclusive |
| 6 | CB | Continental Breakfast |
| 7 | BD | Bed & Dinner |

#### Med_RoomCategories
| CategoryId | Name |
|------------|------|
| 1 | Standard |
| 2 | Superior |
| 3 | Dormitory |
| 4 | Deluxe |
| 12 | Suite |

#### Med_Sources
| Id | Description |
|----|-------------|
| 1 | Innstant |
| 2 | GoGlobal |

---

### Booking Tables

#### Med_Books
> הזמנות שבוצעו

| Column | Description |
|--------|-------------|
| `HotelId` | מלון |
| `OpportunityId` | הזדמנות |
| `IsSold` | האם נמכר |
| `SoldId` | מזהה מכירה |
| `IsActive` | פעיל |
| `ContentBookingId` | מזהה הזמנה אצל ספק |
| `DateInsert` | תאריך |
| `StartDate` | כניסה |
| `EndDate` | יציאה |
| `CancellationTo` | ביטול עד |
| `Providers` | ספקים |
| `ReferenceAgency` | רפרנס |
| `ReferenceVoucherEmail` | רפרנס ווצ'ר |
| `SupplierReference` | רפרנס ספק |
| `NumberOfNights` | מספר לילות |
| `StatusChangeName` | שינוי סטטוס |

#### Med_Reservations
> הזמנות מכירה

#### Med_ReservationCustomerNames
> שמות לקוחות בהזמנות

---

### Backup Tables (Created 2026-02-23)
| Backup Table | Original |
|-------------|----------|
| `BAK_Med_Hotels_20260223` | Med_Hotels (full) |
| `BAK_Med_Hotels_ratebycat_20260223` | Med_Hotels_ratebycat (full) |
| `BAK_SalesOffice_Orders_20260223` | SalesOffice.Orders (full) |
| `BAK_Opportunities_20260223` | MED_ֹOֹֹpportunities (full) |
| `BAK_Med_Hotels_24982_20260223` | Med_Hotels (hotel 24982 only) |
| `BAK_ratebycat_24982_20260223` | Med_Hotels_ratebycat (hotel 24982 only) |
| `BAK_Med_Hotels_19inactive_20260223` | Med_Hotels (19 inactive hotels) |

---

## Stored Procedures (Notable)
| Procedure | Purpose |
|-----------|---------|
| `MED_GetnextOֹֹpportunitiesTobuy` | מחזיר הזדמנות הבאה לרכישה |
| `MED_BackOfficeOptLog` | כתיבת לוג BackOffice |
| ~90 additional stored procedures | Various operations |

**Note:** There are NO stored procedures for SalesOffice operations — all SalesOffice processing is application-side in the OnlyNight project.
