# SalesOffice – תיעוד מלא

> תיעוד עצמאי ומקיף של מערכת **SalesOffice** – מערכת ניהול הזמנות אוטומטית שמחפשת חדרים ב-Innstant API, משייכת אותם למלונות ב-Medici, ומבצעת רכישה ודחיפה ל-Zenith Channel Manager.

---

## 📂 מבנה התיקייה

| קובץ | תיאור |
|---|---|
| [01-architecture-flow.md](01-architecture-flow.md) | ארכיטקטורה כללית וזרימת התהליך מקצה לקצה |
| [02-database-tables.md](02-database-tables.md) | טבלאות מסד הנתונים – סכמה, עמודות וקשרים |
| [03-webjob-onlynight.md](03-webjob-onlynight.md) | WebJob AzureWebJob ופרויקט OnlyNight – שירותים ומתודות |
| [04-mapping-logic.md](04-mapping-logic.md) | לוגיקת מיפוי – FilterByVenueId, FindPushRatePlanCode, ratebycat |
| [05-callback-booking.md](05-callback-booking.md) | עיבוד Callback – BuyRoom, יצירת Opportunity, דחיפה ל-Zenith |
| [06-troubleshooting-ops.md](06-troubleshooting-ops.md) | פתרון בעיות ותפעול שוטף |
| [07-sql-reference.md](07-sql-reference.md) | שאילתות SQL שימושיות |

---

## 🔑 מושגי יסוד

| מונח | הסבר |
|---|---|
| **SalesOffice Order** | הזמנה ביעד + טווח תאריכים שנשלחת מ-Control Panel |
| **SalesOffice Detail** | חדר ספציפי שנמצא ב-Innstant ומופה למלון ב-Medici |
| **Callback** | תהליך הרכישה – BuyRoom מ-Innstant ו-Push ל-Zenith |
| **WebJobStatus** | סטטוס עיבוד ב-Orders: `null`=המתנה, `In Progress`=מעובד, `Completed;...`=הושלם |
| **Innstant_ZenithId** | מזהה VenueId ב-Zenith – חייב להיות >0 במלון כדי שימופה |
| **RatePlanCode / InvTypeCode** | קודי מיפוי בטבלת ratebycat – חיוניים לדחיפה ל-Zenith |
| **FindPushRatePlanCode** | מתודה שמחפשת את קוד הדחיפה לפי HotelId+BoardId+CategoryId |

---

## 🏗️ ארכיטקטורה בקצרה

```
Control Panel               Azure WebJob                  Innstant API
    │                      (AzureWebJob.exe)                    │
    │  Insert Order         ┌──────────────┐                    │
    ├─────────────────────►│ SalesOffice   │   Search Hotels    │
    │                      │ Service.Run() ├──────────────────►│
    │                      │               │◄──────────────────┤
    │                      │ FilterByVenueId│   Results         │
    │                      │ GetRatePlan...│                    │
    │                      │ AddDetails    │                    │
    │                      └──────┬───────┘                    │
    │                             │                             │
    │                      ┌──────▼───────┐                    │
    │                      │ Callback     │   BuyRoom          │
    │                      │ Service      ├──────────────────►│
    │                      │              │◄──────────────────┤
    │                      │ CreateOpp    │                    │
    │                      │ PushToZenith │──────► Zenith CM   │
    │                      └──────────────┘                    │
```

---

## ⚡ תהליך בקצרה

1. **יצירת הזמנה** – מ-Control Panel נכתבת שורה ל-`SalesOffice.Orders`
2. **WebJob רץ כל 5 דקות** – `ProcessSalesOfficeOrders` → `SalesOfficeService.Run()`
3. **חיפוש ב-Innstant** – `GetInnstantHotelSearchData()` עם יעד + תאריכים
4. **סינון לפי VenueId** – `FilterByVenueId()` *מסנן רק מלונות עם ZenithId>0 + isActive*
5. **מיפוי ratebycat** – `GetRatePlanCodeAndInvTypeCode()` → `FindPushRatePlanCode()`
6. **יצירת Details** – `AddSalesOfficeDetails()` כותב חדרים ממופים
7. **עדכון סטטוס** – `UpdateWebJobStatus("Completed; Innstant Api Rooms: X; Rooms With Mapping: Y")`
8. **Callback** – `ProcessCallBackCommitBySalesOffice()` → BuyRoom → CreateOpportunity → PushToZenith
9. **Booking** – `AddToDbSalesOfficeBooking()` שומר הזמנה מושלמת

---

## 🔗 פרויקטים קשורים

| פרויקט | מיקום | תפקיד |
|---|---|---|
| **OnlyNight** | Azure WebJob (לא נמצא מקומי) | הלוגיקה העיקרית של SalesOffice |
| **EFModel** | `medici-hotels/EFModel/` | `FindPushRatePlanCode()` ב-BaseEF.cs |
| **SharedLibrary** | `medici-hotels/SharedLibrary/` | `BuyRoomControl`, `PushRoomControl`, `Repository` |
| **MediciBuyRooms** | `medici-hotels/MediciBuyRooms/` | תהליך קנייה מקביל (דרך Opportunities) |
| **Medici-Control-Panel** | repo נפרד | ממשק המשתמש ליצירת Orders |

---

*עדכון אחרון: פברואר 2025*
