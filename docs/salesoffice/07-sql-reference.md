# 07 – SQL Reference (שאילתות שימושיות)

> כל השאילתות עובדות על: `medici-sql-server.database.windows.net` → `medici-db`
> 
> **חשוב:** טבלאות SalesOffice משתמשות בנקודה בשם → חייבים brackets: `[SalesOffice.Orders]`

---

## 📋 שאילתות Orders

### כל ה-Orders (אחרונים ראשון)
```sql
SELECT TOP 50 Id, DateInsert, DestinationType, DestinationId,
       DateFrom, DateTo, UserId, IsActive, WebJobStatus
FROM [SalesOffice.Orders]
ORDER BY Id DESC;
```

### Orders ממתינים לעיבוד
```sql
SELECT *
FROM [SalesOffice.Orders]
WHERE WebJobStatus IS NULL AND IsActive = 1
ORDER BY DateInsert;
```

### Orders בעיבוד (In Progress)
```sql
SELECT *
FROM [SalesOffice.Orders]
WHERE WebJobStatus = 'In Progress';
```

### Orders שהושלמו עם 0 מיפויים
```sql
SELECT *
FROM [SalesOffice.Orders]
WHERE WebJobStatus LIKE '%Rooms With Mapping: 0%'
ORDER BY DateInsert DESC;
```

### Orders שהושלמו בהצלחה (יש מיפויים)
```sql
SELECT *
FROM [SalesOffice.Orders]
WHERE WebJobStatus LIKE 'Completed%'
  AND WebJobStatus NOT LIKE '%Rooms With Mapping: 0%'
ORDER BY DateInsert DESC;
```

### Orders תקועים (In Progress > 30 דקות)
```sql
SELECT Id, DateInsert, WebJobStatus,
       DATEDIFF(MINUTE, DateInsert, GETDATE()) AS MinutesElapsed
FROM [SalesOffice.Orders]
WHERE WebJobStatus = 'In Progress'
  AND DateInsert < DATEADD(MINUTE, -30, GETDATE());
```

### אפס Order לעיבוד מחדש
```sql
UPDATE [SalesOffice.Orders]
SET WebJobStatus = NULL
WHERE Id = @OrderId;
```

### אפס כל ה-Orders של יעד ספציפי
```sql
UPDATE [SalesOffice.Orders]
SET WebJobStatus = NULL
WHERE DestinationId = @DestId
  AND WebJobStatus LIKE 'Completed%Mapping: 0%';
```

---

## 📋 שאילתות Details

### Details של Order ספציפי
```sql
SELECT d.Id, d.DateCreated, d.HotelId, h.Name AS HotelName,
       d.RoomCategory, d.RoomBoard, d.RoomPrice, d.RoomCode,
       d.IsProcessedCallback
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
WHERE d.SalesOfficeOrderId = @OrderId
ORDER BY d.HotelId, d.RoomCategory;
```

### Details שלא עובדו (Callback)
```sql
SELECT d.*, h.Name AS HotelName, h.Innstant_ZenithId
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
WHERE d.IsProcessedCallback = 0
ORDER BY d.DateCreated DESC;
```

### סיכום Details לפי מלון
```sql
SELECT d.HotelId, h.Name, h.Innstant_ZenithId,
       COUNT(*) AS TotalDetails,
       SUM(CASE WHEN d.IsProcessedCallback = 1 THEN 1 ELSE 0 END) AS Processed,
       SUM(CASE WHEN d.IsProcessedCallback = 0 THEN 1 ELSE 0 END) AS Pending
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
GROUP BY d.HotelId, h.Name, h.Innstant_ZenithId
ORDER BY TotalDetails DESC;
```

---

## 📋 שאילתות Bookings

### כל ה-Bookings (אחרונים)
```sql
SELECT TOP 50 *
FROM [SalesOffice.Bookings]
ORDER BY Id DESC;
```

### Bookings עם פרטי Order ו-Detail
```sql
SELECT b.*, d.HotelId, h.Name AS HotelName,
       d.RoomCategory, d.RoomBoard, d.RoomPrice,
       o.DestinationId, o.DateFrom, o.DateTo
FROM [SalesOffice.Bookings] b
JOIN [SalesOffice.Details] d ON b.SalesOfficeDetailId = d.Id
JOIN [SalesOffice.Orders] o ON b.SalesOfficeOrderId = o.Id
JOIN Med_Hotels h ON d.HotelId = h.HotelId
ORDER BY b.Id DESC;
```

---

## 📋 שאילתות Log

### לוגים אחרונים
```sql
SELECT TOP 100 *
FROM [SalesOffice.Log]
ORDER BY Id DESC;
```

### לוגים של Order ספציפי
```sql
SELECT l.*
FROM [SalesOffice.Log] l
WHERE l.Message LIKE '%OrderId: ' + CAST(@OrderId AS VARCHAR) + '%'
ORDER BY l.Id;
```

---

## 📋 שאילתות Med_Hotels (מיפוי)

### מלון ספציפי – סטטוס מלא
```sql
SELECT h.HotelId, h.Name, h.Innstant_ZenithId, h.isActive,
       h.InnstantHotelId, h.CityId
FROM Med_Hotels h
WHERE h.HotelId = @HotelId;
```

### כל המלונות הממופים ל-Zenith
```sql
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE Innstant_ZenithId > 0
ORDER BY Innstant_ZenithId;
```

### מלונות פעילים אבל בלי ZenithId (צריכים מיפוי)
```sql
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE isActive = 1 AND (Innstant_ZenithId = 0 OR Innstant_ZenithId IS NULL);
```

### מלונות עם ZenithId אבל לא פעילים
```sql
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE Innstant_ZenithId > 0 AND isActive = 0;
```

---

## 📋 שאילתות Med_Hotels_ratebycat

### ratebycat של מלון ספציפי (עם שמות)
```sql
SELECT r.Id, r.HotelId, h.Name AS HotelName,
       r.BoardId, b.Description AS BoardName,
       r.CategoryId, c.Description AS CategoryName,
       r.RatePlanCode, r.InvTypeCode
FROM Med_Hotels_ratebycat r
JOIN Med_Hotels h ON r.HotelId = h.HotelId
JOIN MED_Boards b ON r.BoardId = b.BoardId
JOIN MED_Room_Categories c ON r.CategoryId = c.CategoryId
WHERE r.HotelId = @HotelId;
```

### מלונות בלי ratebycat (ממופים אבל חסר RatePlan)
```sql
SELECT h.HotelId, h.Name, h.Innstant_ZenithId
FROM Med_Hotels h
WHERE h.Innstant_ZenithId > 0
  AND h.isActive = 1
  AND NOT EXISTS (
    SELECT 1 FROM Med_Hotels_ratebycat r WHERE r.HotelId = h.HotelId
  );
```

### הוספת שורת ratebycat
```sql
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES (@HotelId, @BoardId, @CategoryId, @RatePlanCode, @InvTypeCode);
```

---

## 📋 שאילתות MED_Opportunities

### Opportunities אחרונות
```sql
SELECT TOP 50 OpportunityId, PushHotelCode, BoardId, CategoryId,
       DateForm, DateTo, PaxAdultsCount, PushRatePlanCode,
       PushInvTypeCode, PushPrice, PushCurrency
FROM [MED_ֹOֹֹpportunities]
ORDER BY OpportunityId DESC;
```

### Opportunities של מלון ספציפי
```sql
SELECT *
FROM [MED_ֹOֹֹpportunities]
WHERE PushHotelCode = @HotelId
ORDER BY OpportunityId DESC;
```

---

## 📋 שאילתות דיאגנוסטיות

### סיכום מלא – Order + Details + Bookings
```sql
SELECT
  o.Id AS OrderId,
  o.DateInsert,
  o.DestinationId,
  o.DateFrom,
  o.DateTo,
  o.WebJobStatus,
  COUNT(DISTINCT d.Id) AS TotalDetails,
  SUM(CASE WHEN d.IsProcessedCallback = 1 THEN 1 ELSE 0 END) AS ProcessedDetails,
  COUNT(DISTINCT b.Id) AS TotalBookings
FROM [SalesOffice.Orders] o
LEFT JOIN [SalesOffice.Details] d ON o.Id = d.SalesOfficeOrderId
LEFT JOIN [SalesOffice.Bookings] b ON o.Id = b.SalesOfficeOrderId
GROUP BY o.Id, o.DateInsert, o.DestinationId, o.DateFrom, o.DateTo, o.WebJobStatus
ORDER BY o.Id DESC;
```

### בדיקת מוכנות מלון ל-SalesOffice
```sql
-- בדיקה מקיפה של מלון ספציפי
DECLARE @HotelId INT = 20702;

SELECT 'Hotel Status' AS [Check],
       HotelId, Name, Innstant_ZenithId, isActive,
       CASE
         WHEN Innstant_ZenithId > 0 AND isActive = 1 THEN '✅ OK'
         WHEN Innstant_ZenithId = 0 THEN '❌ Missing ZenithId'
         WHEN isActive = 0 THEN '❌ Not Active'
         ELSE '❌ Problem'
       END AS Status
FROM Med_Hotels WHERE HotelId = @HotelId;

SELECT 'RatePlan Mapping' AS [Check],
       r.Id, r.BoardId, b.Description AS Board,
       r.CategoryId, c.Description AS Category,
       r.RatePlanCode, r.InvTypeCode
FROM Med_Hotels_ratebycat r
JOIN MED_Boards b ON r.BoardId = b.BoardId
JOIN MED_Room_Categories c ON r.CategoryId = c.CategoryId
WHERE r.HotelId = @HotelId;

SELECT 'Recent Orders' AS [Check],
       o.Id, o.DateFrom, o.DateTo, o.WebJobStatus
FROM [SalesOffice.Orders] o
JOIN [SalesOffice.Details] d ON o.Id = d.SalesOfficeOrderId
WHERE d.HotelId = @HotelId
ORDER BY o.Id DESC;
```

### ספירת חדרים לפי מלון ב-Orders
```sql
SELECT d.HotelId, h.Name, h.Innstant_ZenithId,
       COUNT(*) AS RoomCount,
       MIN(d.RoomPrice) AS MinPrice,
       MAX(d.RoomPrice) AS MaxPrice,
       AVG(d.RoomPrice) AS AvgPrice
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
GROUP BY d.HotelId, h.Name, h.Innstant_ZenithId
ORDER BY RoomCount DESC;
```

---

## 📋 Backup & Rollback

### יצירת Backup לפני שינוי
```sql
-- Backup מלון
SELECT * INTO BAK_Med_Hotels_XXXXX_YYYYMMDD
FROM Med_Hotels WHERE HotelId = XXXXX;

-- Backup ratebycat
SELECT * INTO BAK_ratebycat_XXXXX_YYYYMMDD
FROM Med_Hotels_ratebycat WHERE HotelId = XXXXX;

-- Backup Orders
SELECT * INTO BAK_SalesOffice_Orders_YYYYMMDD
FROM [SalesOffice.Orders] WHERE Id IN (...);
```

### Rollback
```sql
-- שחזור מלון (דוגמה)
UPDATE h
SET h.Innstant_ZenithId = b.Innstant_ZenithId,
    h.isActive = b.isActive
FROM Med_Hotels h
JOIN BAK_Med_Hotels_XXXXX_YYYYMMDD b ON h.HotelId = b.HotelId;

-- מחיקת ratebycat שנוספו
DELETE FROM Med_Hotels_ratebycat WHERE Id IN (...);
```

---

## 📋 Reference Tables

### Board IDs
```sql
SELECT * FROM MED_Boards ORDER BY BoardId;
-- 1=RO, 2=BB, 3=HB, 4=FB, 5=AI, 6=CB, 7=BD
```

### Category IDs
```sql
SELECT * FROM MED_Room_Categories ORDER BY CategoryId;
-- 1=Standard, 2=Superior, 3=Dormitory, 4=Deluxe, 12=Suite
```

---

*סוף.*
