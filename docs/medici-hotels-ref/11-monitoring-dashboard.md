# 11 - Monitoring Dashboard / דשבורד ניטור בזמן אמת

> **Version:** 1.4  
> **Date:** 2026-02-24  
> **Status:** IMPLEMENTED ✅

---

## מטרה

מרכז בקרה אחד שנותן שיקוף מלא בזמן אמת על **כל** הפעולות במערכת:
- הזמנות פעילות ותקועות
- ביטולים שהצליחו ונכשלו
- Push operations ל-Zenith cockpit
- SalesOffice WebJob status
- Queue items ושגיאות
- BackOffice errors

**הבעיה שנפתרה:** לא היה שיקוף מרכזי על פעולות WebJobs. בעיות כמו 50 ביטולים תקועים (v1.3) או SalesOffice failures התגלו רק בעקבות אימייל שגיאה מ-Innstant.

---

## גישה

### Production (Azure)
```
https://medici-backend.azurewebsites.net/Monitoring/Dashboard
```

### API Endpoint (JSON)
```
https://medici-backend.azurewebsites.net/Monitoring/api/status
```

### Local Development
```
http://localhost:{port}/Monitoring/Dashboard
```

> **הערה:** הדשבורד לא דורש authentication (קריאה בלבד). ה-API מחזיר JSON סטנדרטי.

---

## קבצים

| File | Purpose |
|------|---------|
| `Backend/Controllers/MonitoringController.cs` | Controller — API + embedded HTML dashboard |
| `Backend/Models/MonitoringModels.cs` | DTO models for all monitoring data |

---

## מבנה הדשבורד

### 1. KPI Cards (שורה עליונה)

| Card | שדה | Status Color |
|------|------|-------------|
| חדרים פעילים | `TotalActiveBookings` | 🔵 Blue |
| ביטולים תקועים | `StuckCancellations` | 🔴 Red if > 0, 🟢 Green if 0 |
| ביטולים קרובים | `UpcomingCancellations` | 🟡 Yellow if > 5 |
| Push פעילים | `ActivePushOperations` | 🔵 Blue |
| Push נכשל | `FailedPushOperations` | 🔴 Red if > 0 |
| ביטולי הצלחה 24h | `CancelSuccessLast24h` | 🟢 Green |
| שגיאות ביטול 24h | `CancelErrorsLast24h` | 🟡 Yellow if > 0 |
| שגיאות הזמנה 24h | `BookingErrorsLast24h` | 🟡 Yellow if > 0 |
| שגיאות BackOffice 24h | `BackOfficeErrorsLast24h` | 🟡 Yellow if > 0 |
| Opportunities פעילים | `ActiveOpportunities` | 🔵 Blue |
| Queue ממתין | `QueuePending` | 🔴 Red if errors, 🟡 Yellow if pending |
| SalesOffice Pending | `SalesOfficePending` | 🔴 Red if failed |

### 2. Alert Bar

מופיע אוטומטית כאשר יש בעיות קריטיות:
- ביטולים תקועים > 0
- Push failures > 0
- SalesOffice failures > 0
- Queue errors > 0

כולל אפשרות **Sound Alert** — צפצוף כשנוסף ביטול תקוע חדש.

### 3. Stuck Cancellations Table

מציג את כל ההזמנות שתקועות (IsActive=1 AND CancellationTo < NOW):

| Column | Source |
|--------|--------|
| PreBookId | `MED_Book.PreBookId` |
| BookingId | `MED_Book.contentBookingID` |
| מלון | `MED_Book.HotelId` |
| מקור | Source 1=Innstant, 2=GoGlobal |
| תאריך ביטול | `MED_Book.CancellationTo` |
| ימים תקוע | `DATEDIFF(DAY, CancellationTo, NOW)` |
| שגיאות | Count from `MED_CancelBookError` |
| שגיאה אחרונה | Latest error text |

### 4. Hotel Breakdown Chart

תרשים בר אופקי — חדרים פעילים לפי מלון:
- 🔵 כחול = פעיל
- 🔴 אדום = תקוע
- 🟢 ירוק = נמכר

### 5. SalesOffice Monitor

| Badge | Meaning |
|-------|---------|
| Pending | `WebJobStatus IS NULL` |
| In Progress | `WebJobStatus = 'In Progress'` |
| Completed | `WebJobStatus LIKE 'Completed%'` |
| Failed | `WebJobStatus LIKE 'Failed%'` |

### 6. Error Tabs

5 טאבים לשגיאות לפי קטגוריה:
- **שגיאות ביטול** — `MED_CancelBookError` (25 אחרונות)
- **שגיאות הזמנה** — `MED_BookError` (25 אחרונות)
- **שגיאות Push** — `Med_HotelsToPush` where Error != 'CancelBook' (25 אחרונות)
- **שגיאות BackOffice** — `BackOfficeOptLog` (25 אחרונות)
- **שגיאות Queue** — `Queue` where Status='Error' (20 אחרונות)

---

## SQL Queries Reference

### Stuck Cancellations
```sql
SELECT b.PreBookId, b.contentBookingID, b.CancellationTo, b.source, b.HotelId, b.price,
       DATEDIFF(DAY, b.CancellationTo, GETDATE()) as DaysStuck,
       (SELECT COUNT(*) FROM MED_CancelBookError e WHERE e.PreBookId = b.PreBookId) as ErrorCount,
       (SELECT TOP 1 e.Error FROM MED_CancelBookError e WHERE e.PreBookId = b.PreBookId ORDER BY e.DateInsert DESC) as LastError
FROM MED_Book b
WHERE b.IsActive = 1 AND b.CancellationTo < GETDATE()
ORDER BY b.CancellationTo ASC
```

### Active Bookings Summary
```sql
SELECT 
    COUNT(*) as Total,
    SUM(CASE WHEN CancellationTo < GETDATE() THEN 1 ELSE 0 END) as Stuck,
    SUM(CASE WHEN CancellationTo >= GETDATE() AND CancellationTo <= DATEADD(DAY, 2, GETDATE()) THEN 1 ELSE 0 END) as Upcoming,
    SUM(CASE WHEN CancellationTo > DATEADD(DAY, 2, GETDATE()) OR CancellationTo IS NULL THEN 1 ELSE 0 END) as Future
FROM MED_Book WHERE IsActive = 1
```

### SalesOffice Status
```sql
SELECT 
    SUM(CASE WHEN WebJobStatus IS NULL THEN 1 ELSE 0 END) as Pending,
    SUM(CASE WHEN WebJobStatus = 'In Progress' THEN 1 ELSE 0 END) as InProgress,
    SUM(CASE WHEN WebJobStatus LIKE 'Completed%' THEN 1 ELSE 0 END) as Completed,
    SUM(CASE WHEN WebJobStatus LIKE 'Failed%' OR WebJobStatus = 'DateRangeError' THEN 1 ELSE 0 END) as Failed
FROM SalesOfficeOrders WHERE IsActive = 1
```

---

## Auto-Refresh

- ברירת מחדל: כל **30 שניות**
- כפתור `Auto 30s` מפעיל/מכבה
- כפתור `רענן` לרענון ידני מיידי
- כפתור `Sound` מפעיל/מכבה צפצוף על בעיות חדשות

---

## טכני

### Connection String
הדשבורד משתמש ב-`IConfiguration.GetConnectionString("SQLServer")` — קורא מאותו `appsettings.json` שה-Backend משתמש בו. ב-Production זה:
```
Server=medici-sql-server.database.windows.net; Database=medici-db; User Id=medici_sql_admin; Password=@Amit2025;
```

### ללא תלויות חיצוניות
ה-HTML dashboard הוא **self-contained** — אין CSS או JS חיצוניים. הכל embedded ב-Controller.

### SalesOffice Table Discovery
הקוד מנסה 3 שמות טבלה (`SalesOfficeOrders`, `[SalesOffice.Orders]`, `SalesOffice_Orders`) עם TRY/CATCH. אם הטבלה לא נמצאה, הסעיף מציג 0.

---

## Deploy

לאחר deploy ל-Azure App Service (`medici-backend`), הדשבורד יהיה זמין מיד ב:
```
https://medici-backend.azurewebsites.net/Monitoring/Dashboard
```

אין צורך בהגדרות נוספות — משתמש באותו connection string שכבר קיים ב-appsettings.json.

---

## המלצות לעתיד

1. **הוספת Authentication** — כרגע הדשבורד פתוח. מומלץ להוסיף token-based access
2. **SignalR Real-time** — במקום polling כל 30s, אפשר push updates דרך ה-MessageHub הקיים
3. **History/Trends** — גרף מגמות על כמות שגיאות לאורך זמן
4. **Notifications** — שליחת Slack/Email אוטומטית כשיש בעיה חדשה מהדשבורד
5. **Code-level fix** — Option B/C/D ל-AutoCancellation כדי למנוע הצטברות תקועים מחדש
