# 📚 מערכת הלוגים והתיעוד המלא - Medici Hotels

## 🎯 סקירה כללית

המערכת מתעדת פעילות ב-**3 מקומות**:
1. **בסיס נתונים** - טבלאות SQL עם היסטוריה מלאה
2. **קבצי לוג** - Winston logs במערכת הקבצים
3. **Slack Notifications** - התראות בזמן אמת

---

## 🗄️ חלק 1: טבלאות בבסיס הנתונים

### 📋 טבלאות מרכזיות שמצאנו:

#### 1. **MED_CancelBook** - ביטולים מוצלחים ✅
**תיאור:** מתעד כל ביטול שהושלם בהצלחה

**מבנה:**
- `Id` (int) - מזהה ייחודי
- `DateInsert` (datetime) - תאריך הביטול
- `PreBookId` (int) - מזהה הזמנה מקורי
- `contentBookingID` (nvarchar(50)) - מזהה supplier
- `RequestJson` (nvarchar(max)) - בקשת הביטול
- `ResponseJson` (nvarchar(max)) - תגובת ה-supplier
- `bookingdetailsJson` (nvarchar(max)) - פרטי ההזמנה
- `CancellationReason` (nvarchar(100)) - סיבת הביטול
- `CancellationDate` (datetime) - תאריך ביצוע

**סטטיסטיקות:**
- 📊 **4,614 רשומות** סה"כ
- 🕐 **אחרון:** 14 ינואר 2026, 05:48

**שימוש:**
```sql
-- ביטולים אחרונים
SELECT TOP 20 * 
FROM MED_CancelBook 
ORDER BY DateInsert DESC

-- ביטולים לפי תקופה
SELECT * FROM MED_CancelBook
WHERE DateInsert >= '2026-01-01'

-- ביטולים לפי סיבה
SELECT CancellationReason, COUNT(*) as Total
FROM MED_CancelBook
GROUP BY CancellationReason
```

---

#### 2. **MED_CancelBookError** - ביטולים שנכשלו ❌
**תיאור:** מתעד ביטולים שנכשלו + סיבת הכשל

**מבנה:**
- `Id` (int) - מזהה ייחודי
- `DateInsert` (datetime) - מתי נכשל
- `PreBookId` (int) - מזהה הזמנה
- `contentBookingID` (nvarchar) - מזהה supplier
- `Error` (nvarchar) - **הודעת השגיאה המלאה** ⚠️
- `RequestJson` (nvarchar) - מה ניסינו לשלוח
- `ResponseJson` (nvarchar) - מה קיבלנו בחזרה
- `UserId` (int) - מי ביצע

**סטטיסטיקות:**
- 📊 **29,619 רשומות שגיאה!**
- 🕐 **אחרון:** 14 ינואר 2026, 05:47

**דוגמאות שגיאות נפוצות:**
```sql
-- שגיאות נפוצות ביותר
SELECT TOP 10 
    Error, 
    COUNT(*) as ErrorCount
FROM MED_CancelBookError
WHERE DateInsert >= DATEADD(month, -1, GETDATE())
GROUP BY Error
ORDER BY ErrorCount DESC

-- ביטולים שנכשלו היום
SELECT * FROM MED_CancelBookError
WHERE CAST(DateInsert AS DATE) = CAST(GETDATE() AS DATE)
```

**⚠️ נקודה חשובה:** 29K שגיאות זה מספר גבוה! כדאי לנתח למה כל כך הרבה ביטולים נכשלים.

---

#### 3. **MED_OpportunitiesLog** - היסטוריית פעולות על הזדמנויות
**תיאור:** לוג מלא של כל פעולה על opportunity (הזמנה, ביטול, עדכון, מכירה)

**מבנה:**
- `Id` (int)
- `OpportunityId` (int) - מזהה ההזדמנות
- `ActionType` (nvarchar) - סוג הפעולה
- `RequestJson` (nvarchar) - פרטי הבקשה
- `ResponseJson` (nvarchar) - תגובה
- `DateTimeUTC` (datetime) - זמן UTC

**סטטיסטיקות:**
- 📊 **107,218 רשומות** סה"כ
- 🕐 **אחרון:** 1 אוגוסט 2024

**סוגי פעולות:**
- `AUTO_CANCELLED` - ביטול אוטומטי ע"י worker
- `CANCEL_FAILED` - ביטול שנכשל
- `ApiMedici.SearchHotels` - חיפוש מלונות
- `OPPORTUNITY_CREATED` - יצירת הזדמנות
- `OPPORTUNITY_SOLD` - מכירה

**שימוש:**
```sql
-- כל הביטולים האוטומטיים
SELECT * FROM MED_OpportunitiesLog
WHERE ActionType = 'AUTO_CANCELLED'
ORDER BY DateTimeUTC DESC

-- ביטולים שנכשלו
SELECT * FROM MED_OpportunitiesLog
WHERE ActionType = 'CANCEL_FAILED'
ORDER BY DateTimeUTC DESC

-- היסטוריה של opportunity ספציפי
SELECT * FROM MED_OpportunitiesLog
WHERE OpportunityId = 12345
ORDER BY DateTimeUTC DESC
```

---

#### 4. **MED_Log** - לוג מערכת כללי
**תיאור:** לוג כללי של אירועים במערכת

**מבנה:**
- `LogID` (int)
- `Date` (datetime)
- `Message` (nvarchar) - הודעה

**סטטיסטיקות:**
- 📊 **41,750 רשומות**
- 🕐 **אחרון:** 14 ינואר 2026

---

#### 5. **Med_ReservationCancel** - ביטולי הזמנות Zenith
**תיאור:** ביטולים שהגיעו מ-Zenith OTA

**מבנה:** 26 עמודות (טבלה גדולה!)
- מכילה פרטי ביטולים שהתקבלו מה-OTA
- מחוברת ל-Med_Reservation

**שימוש:**
```sql
SELECT COUNT(*) FROM Med_ReservationCancel
WHERE CancelDate >= DATEADD(month, -1, GETDATE())
```

---

#### 6. טבלאות נוספות שמצאנו:
- **BuyRoomLog** - לוג רכישות חדרים (4 עמודות)
- **RoomPriceUpdateLog** - לוג עדכוני מחירים (4 עמודות)
- **BackOfficeOptLog** - לוג back office (4 עמודות)
- **Med_ReservationNotificationLog** - התראות הזמנות (3 עמודות)
- **SearchResultsSessionPollLog** - חיפושים (32 עמודות!)
- **ManualSearchResultsSessionPollLog** - חיפושים ידניים (34 עמודות)
- **PreSearchResultsSessionPollLog** - pre-searches (4 עמודות)
- **SalesOffice.Log** - לוג SalesOffice (7 עמודות)
- **SalesOffice.LogActionsDictionary** - מילון פעולות (2 עמודות)
- **SalesOffice.LogActionsResultDictionary** - מילון תוצאות (2 עמודות)

---

## 📁 חלק 2: קבצי לוג (Winston Logger)

**מיקום:** `/workspaces/medici_web03012026/medici-backend-node/logs/`

### סוגי קבצי לוג:

#### 1. **application-{date}.log** - לוג ראשי
- כל אירועי המערכת
- Levels: info, warn, error
- פורמט: JSON

#### 2. **error-{date}.log** - שגיאות בלבד
- רק errors ו-warnings
- חשוב לניטור בעיות

#### 3. **http-{date}.log** - HTTP requests
- כל בקשות ה-API
- Response times
- Status codes

#### 4. **debug-{date}.log** - דיבאג
- פרטים טכניים מפורטים
- שימושי לפיתוח

#### 5. **exceptions.log** - Exceptions לא צפויים
- Uncaught exceptions
- Critical errors

#### 6. **rejections.log** - Promise rejections
- Unhandled promise rejections

### גישה לקבצי הלוג:

**דרך API:**
```bash
# רשימת קבצי לוג
GET /logs

# צפייה בקובץ ספציפי
GET /logs/application-2026-02-02.log?lines=100

# חיפוש
GET /logs/application-2026-02-02.log?search=cancel

# Tail (זרימה חיה)
GET /logs/tail/application-2026-02-02.log?lines=50

# חיפוש בכל הקבצים
GET /logs/search?query=cancel&days=7

# סטטיסטיקות
GET /logs/stats

# מחיקת לוגים ישנים
DELETE /logs/cleanup?days=30
```

**דרך מערכת הקבצים:**
```bash
# צפייה בלוגים
tail -f medici-backend-node/logs/application-2026-02-02.log

# חיפוש ביטולים
grep -i "cancel" medici-backend-node/logs/application-2026-02-02.log

# ספירת שגיאות
grep -c "error" medici-backend-node/logs/error-2026-02-02.log

# צפייה ב-50 שורות אחרונות
tail -50 medici-backend-node/logs/application-2026-02-02.log
```

---

## 🤖 חלק 3: Auto-Cancellation Worker

**קובץ:** `workers/auto-cancellation-worker.js`

### איך זה עובד?

#### 1. **Cron Schedule:**
- רץ כל שעה: `0 * * * *`
- בודק הזמנות שעומדות להתבטל

#### 2. **לוגיקה:**
```javascript
CANCELLATION_DEADLINE_HOURS = 48

// מחפש הזמנות:
// 1. IsActive = 1 (פעילות)
// 2. IsSale = 0 (לא נמכרו)
// 3. Check-in תוך 48 שעות
// 4. FreeCancelation = 1 (ניתן לביטול)
```

#### 3. **תהליך הביטול:**

**שלב 1:** ביטול מול ספק (InnstantAPI)
```javascript
const cancelResult = await innstantClient.cancelBooking({
  bookingId: purchase.SupplierBookingId,
  reason: 'Auto-cancellation - room not sold before deadline'
});
```

**שלב 2:** עדכון Opportunity
```sql
UPDATE [MED_ֹOֹֹpportunities]
SET IsActive = 0, Lastupdate = GETDATE()
WHERE OpportunityId = @opportunityId
```

**שלב 3:** רישום ב-MED_OpportunitiesLog
```sql
INSERT INTO MED_OpportunitiesLog 
(OpportunityId, ActionType, RequestJson, DateTimeUTC)
VALUES (@opportunityId, 'AUTO_CANCELLED', @details, GETUTCDATE())
```

**שלב 4:** התראת Slack
```javascript
await SlackService.sendCancellationNotification({
  type: 'auto-cancel',
  opportunityId, hotelName, roomName,
  checkIn, checkOut, purchasePrice, refundAmount
});
```

#### 4. **טיפול בכשלונות:**

אם הביטול נכשל:
1. לוג ב-MED_OpportunitiesLog עם `ActionType = 'CANCEL_FAILED'`
2. שליחת שגיאה ל-Slack
3. Logger.error עם פרטים

#### 5. **התראות מוקדמות:**
- 24 שעות לפני הביטול האוטומטי
- Slack notification לצוות
- רשימת חדרים שעומדים להתבטל

---

## 📊 חלק 4: API Endpoints לגישה ללוגים

### Routes מוגדרים:

**`/logs`** - ניהול לוגים
```javascript
GET    /logs                    // רשימת קבצים
GET    /logs/:filename          // צפייה בקובץ
GET    /logs/tail/:filename     // tail חי
GET    /logs/search             // חיפוש
GET    /logs/stats              // סטטיסטיקות
DELETE /logs/cleanup            // מחיקת ישנים
GET    /logs/stream/:filename   // WebSocket stream
```

**`/errors`** - ניהול שגיאות
```javascript
GET  /errors                 // שגיאות אחרונות
GET  /errors/stats           // סטטיסטיקות שגיאות
POST /errors/report          // דיווח שגיאה חדשה
```

**`/alerts`** - מערכת התראות
```javascript
GET  /alerts                 // התראות פעילות
POST /alerts/acknowledge     // אישור התראה
GET  /alerts/history         // היסטוריה
```

---

## 🔍 חלק 5: שאלות נפוצות וחיפושים

### איך למצוא ביטול ספציפי?

**לפי OpportunityId:**
```sql
-- טבלה ראשית
SELECT * FROM [MED_ֹOֹֹpportunities]
WHERE OpportunityId = 12345

-- לוג ביטולים מוצלחים
SELECT * FROM MED_CancelBook
WHERE PreBookId = 12345

-- לוג שגיאות
SELECT * FROM MED_CancelBookError
WHERE PreBookId = 12345

-- היסטוריה מלאה
SELECT * FROM MED_OpportunitiesLog
WHERE OpportunityId = 12345
ORDER BY DateTimeUTC DESC
```

**לפי תאריך:**
```sql
-- ביטולים היום
SELECT * FROM MED_CancelBook
WHERE CAST(DateInsert AS DATE) = CAST(GETDATE() AS DATE)

-- שגיאות השבוע
SELECT * FROM MED_CancelBookError
WHERE DateInsert >= DATEADD(day, -7, GETDATE())
```

**לפי מלון:**
```sql
SELECT 
  cb.*,
  h.name as HotelName
FROM MED_CancelBook cb
JOIN [MED_ֹOֹֹpportunities] o ON cb.PreBookId = o.OpportunityId
JOIN Med_Hotels h ON o.DestinationsId = h.HotelId
WHERE h.name LIKE '%Hilton%'
```

### איך למצוא ביטולים שנכשלו?

```sql
-- שגיאות אחרונות
SELECT TOP 50 * 
FROM MED_CancelBookError
ORDER BY DateInsert DESC

-- ביטולים שנכשלו אוטומטית
SELECT * FROM MED_OpportunitiesLog
WHERE ActionType = 'CANCEL_FAILED'
ORDER BY DateTimeUTC DESC

-- שגיאות לפי סוג
SELECT 
  SUBSTRING(Error, 1, 100) as ErrorType,
  COUNT(*) as Count
FROM MED_CancelBookError
WHERE DateInsert >= DATEADD(month, -1, GETDATE())
GROUP BY SUBSTRING(Error, 1, 100)
ORDER BY Count DESC
```

### איך לבדוק ביטולים אוטומטיים?

```sql
-- כל הביטולים האוטומטיים
SELECT * FROM MED_OpportunitiesLog
WHERE ActionType = 'AUTO_CANCELLED'
ORDER BY DateTimeUTC DESC

-- סטטיסטיקות חודשיות
SELECT 
  FORMAT(DateTimeUTC, 'yyyy-MM') as Month,
  COUNT(*) as AutoCancellations
FROM MED_OpportunitiesLog
WHERE ActionType = 'AUTO_CANCELLED'
GROUP BY FORMAT(DateTimeUTC, 'yyyy-MM')
ORDER BY Month DESC
```

---

## 📈 חלק 6: סטטיסטיקות ותובנות

### מצב נוכחי:

- ✅ **4,614 ביטולים מוצלחים**
- ❌ **29,619 ביטולים שנכשלו** (!)
- 📊 **107,218 פעולות על opportunities**
- 📝 **41,750 רשומות לוג כלליות**

### שיעור הצלחה:
```
Success Rate = 4,614 / (4,614 + 29,619) = 13.5%
Failure Rate = 86.5%
```

**⚠️ אזהרה:** שיעור כישלון גבוה מאוד! כדאי לחקור למה.

### סיבות אפשריות לכישלונות:
1. ❌ Timeout מול ספקים
2. ❌ Booking כבר מבוטל
3. ❌ אין אפשרות ביטול
4. ❌ שגיאות רשת
5. ❌ פרמטרים שגויים

---

## 🛠️ חלק 7: כלי עזר

### Script לניתוח לוגים:

**קובץ:** `scripts/analyze-cancellations.js`
```javascript
const { getPool } = require('../config/database');

async function analyzeCancellations() {
  const pool = await getPool();
  
  // Success vs Failure
  const success = await pool.request()
    .query('SELECT COUNT(*) as Total FROM MED_CancelBook');
  
  const failures = await pool.request()
    .query('SELECT COUNT(*) as Total FROM MED_CancelBookError');
  
  console.log('Cancellation Statistics:');
  console.log(`✅ Success: ${success.recordset[0].Total}`);
  console.log(`❌ Failures: ${failures.recordset[0].Total}`);
  console.log(`📊 Success Rate: ${(success / (success + failures) * 100).toFixed(2)}%`);
  
  // Top errors
  const topErrors = await pool.request().query(`
    SELECT TOP 10 
      SUBSTRING(Error, 1, 100) as ErrorType,
      COUNT(*) as Count
    FROM MED_CancelBookError
    WHERE DateInsert >= DATEADD(month, -1, GETDATE())
    GROUP BY SUBSTRING(Error, 1, 100)
    ORDER BY Count DESC
  `);
  
  console.log('\nTop 10 Errors (Last Month):');
  topErrors.recordset.forEach((row, i) => {
    console.log(`${i+1}. [${row.Count}x] ${row.ErrorType}`);
  });
}
```

---

## 🎯 סיכום - איפה מה נמצא?

| מה אני מחפש? | איפה למצוא? |
|-------------|------------|
| ביטול שהצליח | `MED_CancelBook` בבסיס נתונים |
| ביטול שנכשל | `MED_CancelBookError` בבסיס נתונים |
| היסטוריית opportunity | `MED_OpportunitiesLog` בבסיס נתונים |
| ביטול אוטומטי | `MED_OpportunitiesLog` WHERE ActionType='AUTO_CANCELLED' |
| לוגים בזמן אמת | `/logs/tail/application-{date}.log` |
| שגיאות אחרונות | `/logs/error-{date}.log` |
| HTTP requests | `/logs/http-{date}.log` |
| Worker status | `workers/auto-cancellation-worker.js` + logs |
| התראות Slack | SlackService + `/alerts` API |

---

## 🚀 המלצות

1. **נתח את 29K הכישלונות** - למה שיעור כישלון כל כך גבוה?
2. **צור Dashboard** - ויזואליזציה של ביטולים
3. **התראות פרואקטיביות** - Email/SMS על כישלונות
4. **Retry Mechanism** - ניסיון חוזר אוטומטי
5. **Data Retention** - מחיקת לוגים ישנים (>90 ימים)
6. **Performance Monitoring** - זמני תגובה של Cancellation API

---

**הכל מתועד! 📚✨**

