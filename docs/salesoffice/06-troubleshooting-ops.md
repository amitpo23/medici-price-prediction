# 06 – פתרון בעיות ותפעול (Troubleshooting & Operations)

---

## בעיות נפוצות

### 🔴 בעיה 1: "Rooms With Mapping: 0"

**סימפטום:** Order מסתיים עם `Completed; Innstant Api Rooms: X; Rooms With Mapping: 0`

**צ'קליסט אבחון:**

```
שלב 1: בדוק את המלון
─────────────────────
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE HotelId = XXXXX;

  ↓ ZenithId = 0?  → שלב 1A
  ↓ isActive = 0?  → שלב 1B
  ↓ שניהם תקינים? → שלב 2

שלב 1A: הגדר ZenithId
──────────────────────
UPDATE Med_Hotels
SET Innstant_ZenithId = [VENUE_ID_FROM_ZENITH]
WHERE HotelId = XXXXX;

שלב 1B: הפעל מלון
──────────────────
UPDATE Med_Hotels
SET isActive = 1
WHERE HotelId = XXXXX;

שלב 2: בדוק ratebycat
──────────────────────
SELECT * FROM Med_Hotels_ratebycat
WHERE HotelId = XXXXX;

  ↓ ריק? → שלב 2A
  ↓ חסר שילוב Board+Category? → שלב 2B
  ↓ הכל תקין? → שלב 3

שלב 2A: הוסף שורות ratebycat
─────────────────────────────
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES (XXXXX, 1, 1, 'RATE_CODE', 'STD');

שלב 2B: הוסף שילוב חסר
────────────────────────
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES (XXXXX, [BoardId], [CategoryId], 'RATE_CODE', 'INV_CODE');

שלב 3: בדוק שהתוצאות מתאימות
──────────────────────────────
  - האם ה-Board שמגיע מ-Innstant מתאים ל-BoardId ב-ratebycat?
  - האם ה-Category שמגיע מ-Innstant מתאים ל-CategoryId ב-ratebycat?
```

---

### 🔴 בעיה 2: Order "תקוע" ב-"In Progress"

**סימפטום:** Order נשאר עם `WebJobStatus = 'In Progress'` לזמן ארוך

**אבחון:**
```sql
-- מצא Orders תקועים (יותר מ-30 דקות)
SELECT Id, DateInsert, DestinationId, DateFrom, DateTo, WebJobStatus
FROM [SalesOffice.Orders]
WHERE WebJobStatus = 'In Progress'
  AND DateInsert < DATEADD(MINUTE, -30, GETDATE());
```

**פתרון:**
```sql
-- אפס סטטוס כדי שה-WebJob יעבד מחדש
UPDATE [SalesOffice.Orders]
SET WebJobStatus = NULL
WHERE Id = @OrderId;
```

---

### 🔴 בעיה 3: Order "Completed" אבל תיקנתי את המלון – איך לעבד מחדש?

**הסבר:** ה-WebJob **לא** מעבד מחדש Orders שכבר Completed.

**פתרון – Option A: אפס סטטוס**
```sql
-- אפס WebJobStatus כדי שיעובד מחדש
UPDATE [SalesOffice.Orders]
SET WebJobStatus = NULL
WHERE Id = @OrderId;
-- ה-WebJob יאסוף אותו בריצה הבאה (5 דקות)
```

**פתרון – Option B: צור Order חדש**
```sql
INSERT INTO [SalesOffice.Orders] (DateInsert, DestinationType, DestinationId, DateFrom, DateTo, UserId, IsActive, WebJobStatus)
SELECT GETDATE(), DestinationType, DestinationId, DateFrom, DateTo, UserId, 1, NULL
FROM [SalesOffice.Orders]
WHERE Id = @OriginalOrderId;
```

---

### 🔴 בעיה 4: WebJob לא רץ

**אבחון:**
1. בדוק סטטוס WebJob
```bash
curl https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob \
  -u "$medici-backend:DgFX5ZmRyla3i0T0iXid18zGfqrPRqZfvazrYwcart5xssLRh5wjGqW2hWZW"
```

2. בדוק לוגים
```bash
curl https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob/log
```

3. הפעל מחדש
```bash
# Start
curl -X POST https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob/start \
  -u "$medici-backend:DgFX5ZmRyla3i0T0iXid18zGfqrPRqZfvazrYwcart5xssLRh5wjGqW2hWZW"

# Stop + Start
curl -X POST https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob/stop \
  -u "$medici-backend:..."
curl -X POST https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob/start \
  -u "$medici-backend:..."
```

---

### 🟡 בעיה 5: Callback – "מחיר גבוה מ-DB"

**סימפטום:** Detail לא נרכש כי מחיר Innstant עלה

**אבחון:**
```sql
-- בדוק Details שלא עובדו
SELECT d.*, o.WebJobStatus
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE d.IsProcessedCallback = 0;
```

**פתרון:**
- ה-Handler `HandleErrorInnstantRoomHigherPriceThanDb()` מטפל אוטומטית
- ניתן ליצור Order חדש עם תאריכים מעודכנים

---

### 🟡 בעיה 6: חדר לא נמצא ב-Innstant (Category+Board)

**סימפטום:** `HandleErrorNoRoomInInnstantBasedOnHotelCategoryBoard()`

**סיבות אפשריות:**
- המלון לא זמין בתאריכים המבוקשים
- הקומבינציה Category+Board לא קיימת במלון
- Innstant API שינתה את המיפוי

---

## תהליכי תפעול שוטף

### הוספת מלון חדש למיפוי SalesOffice

```sql
-- 1. בדוק שהמלון קיים ב-Med_Hotels
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels WHERE HotelId = @NewHotelId;

-- 2. הגדר ZenithId (מגיליון Zenith)
UPDATE Med_Hotels
SET Innstant_ZenithId = @ZenithVenueId
WHERE HotelId = @NewHotelId;

-- 3. הפעל מלון
UPDATE Med_Hotels
SET isActive = 1
WHERE HotelId = @NewHotelId;

-- 4. הוסף שורות ratebycat (לפחות Standard)
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES
  (@NewHotelId, 1, 1, @RatePlanCode, 'STD'),   -- RO + Standard
  (@NewHotelId, 1, 12, @RatePlanCode, 'SUI');   -- RO + Suite (אם רלוונטי)

-- 5. אמת
SELECT * FROM Med_Hotels_ratebycat WHERE HotelId = @NewHotelId;
```

### בדיקת בריאות יומית

```sql
-- 1. Orders שממתינים לעיבוד
SELECT COUNT(*) AS PendingOrders
FROM [SalesOffice.Orders]
WHERE WebJobStatus IS NULL;

-- 2. Orders תקועים
SELECT COUNT(*) AS StuckOrders
FROM [SalesOffice.Orders]
WHERE WebJobStatus = 'In Progress'
  AND DateInsert < DATEADD(HOUR, -1, GETDATE());

-- 3. Details שלא עובדו
SELECT COUNT(*) AS UnprocessedDetails
FROM [SalesOffice.Details]
WHERE IsProcessedCallback = 0;

-- 4. סיכום יומי
SELECT
  CAST(DateInsert AS DATE) AS Day,
  COUNT(*) AS TotalOrders,
  SUM(CASE WHEN WebJobStatus LIKE 'Completed%' THEN 1 ELSE 0 END) AS CompletedOrders,
  SUM(CASE WHEN WebJobStatus IS NULL THEN 1 ELSE 0 END) AS PendingOrders,
  SUM(CASE WHEN WebJobStatus = 'In Progress' THEN 1 ELSE 0 END) AS InProgressOrders
FROM [SalesOffice.Orders]
WHERE DateInsert >= DATEADD(DAY, -7, GETDATE())
GROUP BY CAST(DateInsert AS DATE)
ORDER BY Day DESC;
```

### ניטור Azure

| משאב | מה לנטר |
|---|---|
| App Service `medici-backend` | CPU%, Memory%, HTTP 5xx |
| WebJob `AzureWebJob` | Status=Running, Errors in logs |
| SQL Database `medici-db` | DTU%, Failed queries |
| Log Analytics | SalesOffice-specific alerts |

---

## Backup לפני שינויים

**תמיד!** צור backup לפני עדכון נתונים:

```sql
-- Backup טבלת מלון ספציפי
SELECT * INTO BAK_Med_Hotels_[HOTEL]_[DATE]
FROM Med_Hotels WHERE HotelId = @HotelId;

-- Backup ratebycat ספציפי
SELECT * INTO BAK_ratebycat_[HOTEL]_[DATE]
FROM Med_Hotels_ratebycat WHERE HotelId = @HotelId;

-- Backup Orders
SELECT * INTO BAK_SalesOffice_Orders_[DATE]
FROM [SalesOffice.Orders] WHERE Id = @OrderId;
```

---

## Rollback Template

```sql
-- Rollback מלון
UPDATE Med_Hotels
SET Innstant_ZenithId = [ORIGINAL_VALUE],
    isActive = [ORIGINAL_VALUE]
WHERE HotelId = @HotelId;

-- Rollback ratebycat
DELETE FROM Med_Hotels_ratebycat WHERE Id IN (...);

-- Rollback Order
UPDATE [SalesOffice.Orders]
SET WebJobStatus = [ORIGINAL_VALUE]
WHERE Id = @OrderId;
```

---

*ראה [07-sql-reference.md](07-sql-reference.md) לשאילתות SQL מלאות →*
