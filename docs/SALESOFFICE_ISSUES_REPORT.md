# דוח בעיות SalesOffice — חקירה מעמיקה

**תאריך:** 2026-03-17
**דחיפות:** קריטית — OOM crashes + Orders לא מתעדכנים

---

## 5 בעיות שורש שנמצאו

### 1. OOM Crash — Worker נהרג (CRITICAL)
```
[2026-03-17 05:43:13] Worker (pid:1924) was sent SIGKILL! Perhaps out of memory?
Memory at crash: 1,305 MB
```
- App Service **B1 Basic** = 1.75 GB RAM, 1 core
- Analysis של 4,673 rooms צורך **1.3 GB** ולוקח **15 דקות**
- **3 crashes ביום אחד** (17/03) — restart cycles

**פתרון:**
```bash
# שדרג ל-S1 (לפחות)
az appservice plan update -g medici-prediction-rg -n [PLAN_NAME] --sku S1

# או P1 לביצועים טובים יותר
az appservice plan update -g medici-prediction-rg -n [PLAN_NAME] --sku P1V2
```

### 2. Always On כבוי (CRITICAL)
ה-App הולך לישון → cold start עם pip install כל פעם (2-5 דקות)

**פתרון:**
```bash
az webapp config set -g medici-prediction-rg -n medici-prediction-api --always-on true
```

### 3. SalesOffice.Orders לא מתעדכנים (5 ימים!)
- **Last Orders update: March 12** (RED in health check)
- ה-WebJob של medici-backend לא רץ/תקוע
- בלי Orders חדשים → אין סריקות חדשות → נתונים ישנים

**פתרון:** בדוק ותקן את ה-WebJob ב-medici-backend:
```bash
# בדוק סטטוס WebJob
az webapp webjob continuous list -g medici-prediction-rg -n medici-backend

# אם תקוע — restart
az webapp webjob continuous start -g medici-prediction-rg -n medici-backend -w AzureWebJob
```

### 4. Orders לא נסרקים מחדש
אחרי `WebJobStatus = 'Completed...'` — ה-WebJob **לא מעבד שוב**.
כל חדר נסרק רק **1-2 פעמים** (ממוצע 2.0 scans).

**פתרון — איפוס לסריקה מחדש:**
```sql
-- איפוס כל Orders הפעילים לסריקה מחדש
UPDATE [SalesOffice.Orders]
SET WebJobStatus = NULL
WHERE IsActive = 1
  AND WebJobStatus LIKE 'Completed%'
  AND DateFrom >= GETDATE();  -- רק תאריכים עתידיים

-- ה-WebJob יאסוף אותם בריצה הבאה (5 דקות)
```

### 5. מערכת OnlyNight — Order = לילה אחד בלבד
`IsValidDateRange()` דורש `DateTo - DateFrom ≤ 1 day`

**חשוב:** כדי לכסות 65 לילות צריך **65 Orders נפרדים**, לא Order אחד עם טווח.

---

## מצב Pullman Miami (דוגמה)

| מדד | ערך |
|-----|-----|
| Hotel ID | 6805 |
| Rows ב-system | **779** |
| תאריכים | **72** מתוך 77 (5 חסרים) |
| Categories | Standard, Deluxe, Suite, Superior (4) |
| Boards | RO, BB (2) |
| Scans/room | avg **2.0** (min 1, max 6) |

**5 תאריכים חסרים:** 15/06, 21/06, 24/06, 27/06, 29/06
**BB rates נעלמים ביוני** — כנראה המלון לא מציע BB לתאריכים מאוחרים

---

## Azure Logs — ציר זמן

```
02:07 UTC  App starts (instance E6)
02:10 UTC  Collection: 4,614 rooms, 22 hotels ✅
02:10 UTC  Analysis starts... (15 min)
02:25 UTC  Analysis complete
05:21 UTC  Collection: 4,673 rooms, 23 hotels ✅ (+1 hotel!)
05:21 UTC  Analysis starts... memory growing...
05:36 UTC  Analysis complete, memory=1,305 MB
05:43 UTC  ❌ SIGKILL — Out of Memory!
05:44 UTC  Restart, pip install...
05:45 UTC  Collection: 4,673 rooms ✅
05:45 UTC  Analysis starts again...
07:25 UTC  Another restart (instance AN)
```

---

## סדר עדיפויות לתיקון

1. **מיידי:** שדרג App Service plan (B1→S1/P1) + הפעל Always On
2. **מיידי:** בדוק למה WebJob ב-medici-backend תקוע (Orders מ-12/03)
3. **שוטף:** אפס WebJobStatus ל-NULL כדי לסרוק מחדש
4. **שוטף:** צור Orders חדשים ל-5 תאריכים חסרים של Pullman

---

## Health Check — מצב מקורות נתונים

| מקור | סטטוס | עדכון אחרון |
|------|-------|------------|
| SalesOffice.Details | 🟢 GREEN | 3 שעות |
| SalesOffice.Orders | 🔴 RED | **5 ימים** (12/03) |
| AI_Search_HotelData | 🔴 RED | 1 יום |
| Forward Curve | 🟢 | 1,176 tracks |
| Historical Patterns | 🟢 | 14,733 records |
| Flight Demand | ⚪ NO_DATA | — |
| Hotel Knowledge CSV | ⚠️ Missing | miami_hotels_tbo.csv not deployed |

---

## אימות צוות Prediction

```
GET /api/v1/salesoffice/status
GET /api/v1/salesoffice/hotel-readiness
GET /api/v1/salesoffice/options/view
```
