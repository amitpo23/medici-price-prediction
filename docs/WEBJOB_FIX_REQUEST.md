# WebJob Fix — 10 מלונות עם WebJobStatus=nan

**תאריך:** 2026-03-17
**מבקש:** צוות Prediction
**דחיפות:** גבוהה — 10 מלונות לא נסרקים

---

## מצב נוכחי

ה-WebJob חזר לעבוד ✅ — 12 מלונות נסרקים באופן שוטף. אבל **10 מלונות תקועים עם WebJobStatus="nan"** — ה-WebJob אף פעם לא עיבד אותם.

### 12 מלונות שעובדים (סריקה פעילה):

| HotelId | שם | Details | סריקה אחרונה |
|---------|-----|---------|-------------|
| 66814 | Breakwater South Beach | 1,264 | 17/03 09:11 |
| 6805 | Pullman Miami Airport | 791 | 17/03 15:03 |
| 852120 | SLS LUX Brickell | 555 | 17/03 14:40 |
| 20702 | Embassy Suites Miami | 465 | 17/03 10:48 |
| 64309 | Savoy Hotel | 236 | 15/03 00:08 |
| 173508 | Cadet Hotel | 86 | 12/03 21:14 |
| 117491 | Fairwind Hotel | 82 | 17/03 13:52 |
| 333502 | Eurostars Langford | 77 | 17/03 13:21 |
| 64390 | Crystal Beach Suites | 75 | 17/03 11:50 |
| 383277 | Iberostar Berkeley Shore | 72 | 16/03 19:57 |
| 241025 | Dream South Beach | 65 | 16/03 19:29 |
| 6663 | Marseilles Hotel | 35 | 16/03 23:00 |

### 10 מלונות תקועים (WebJobStatus = "nan"):

| HotelId | שם | בעיה |
|---------|-----|------|
| 855711 | The Albion Hotel | WebJobStatus = "nan" |
| 87197 | The Catalina Hotel & Beach Club | WebJobStatus = "nan" |
| 6654 | Dorchester Hotel | WebJobStatus = "nan" |
| 19977 | Fontainebleau Miami Beach | WebJobStatus = "nan" |
| 701659 | Generator Miami | WebJobStatus = "nan" |
| 301640 | Hilton Garden Inn Miami SB | WebJobStatus = "nan" |
| 67387 | Holiday Inn Express Miami | WebJobStatus = "nan" |
| 414146 | Hotel Belleza | WebJobStatus = "nan" |
| 31226 | Kimpton Angler's Hotel | WebJobStatus = "nan" |
| 21842 | Miami Intl Airport Hotel | WebJobStatus = "nan" |

### מלון נוסף — Notebook Miami Beach:

| HotelId | שם | בעיה |
|---------|-----|------|
| 237547 | Notebook Miami Beach | WebJob Completed אבל **Innstant Api Rooms: 0; Mapping: 0** |

---

## פעולה נדרשת — פעולה אחת בלבד

### איפוס WebJobStatus ל-NULL עבור 10 המלונות

```sql
-- איפוס 10 מלונות תקועים כדי שה-WebJob יעבד אותם
UPDATE [SalesOffice.Orders]
SET WebJobStatus = NULL
WHERE DestinationId IN (855711, 87197, 6654, 19977, 701659, 301640, 67387, 414146, 31226, 21842)
  AND IsActive = 1
  AND (WebJobStatus = 'nan' OR WebJobStatus IS NULL OR WebJobStatus = '');
```

### אימות אחרי ביצוע

```sql
-- 1. ודא שה-WebJobStatus אופס
SELECT o.Id, o.DestinationId, h.Name, o.IsActive, o.WebJobStatus, o.DateFrom, o.DateTo
FROM [SalesOffice.Orders] o
JOIN Med_Hotels h ON o.DestinationId = h.HotelId
WHERE o.DestinationId IN (855711, 87197, 6654, 19977, 701659, 301640, 67387, 414146, 31226, 21842)
  AND o.IsActive = 1
ORDER BY h.Name;
```

```sql
-- 2. אחרי 10-15 דקות (זמן שה-WebJob יעבד), בדוק שנוצרו Details
SELECT d.HotelId, h.Name, COUNT(*) AS details_count, MAX(d.DateCreated) AS last_scan
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
WHERE d.HotelId IN (855711, 87197, 6654, 19977, 701659, 301640, 67387, 414146, 31226, 21842)
GROUP BY d.HotelId, h.Name
ORDER BY last_scan DESC;
```

```sql
-- 3. בדוק את ה-WebJobStatus אחרי שה-WebJob רץ
SELECT o.DestinationId, h.Name, o.WebJobStatus
FROM [SalesOffice.Orders] o
JOIN Med_Hotels h ON o.DestinationId = h.HotelId
WHERE o.DestinationId IN (855711, 87197, 6654, 19977, 701659, 301640, 67387, 414146, 31226, 21842)
  AND o.IsActive = 1
  AND o.WebJobStatus IS NOT NULL
ORDER BY h.Name;
```

---

## בעיה נפרדת — Notebook Miami Beach (237547)

ה-WebJob רץ אבל Innstant מחזיר 0 חדרים. הסיבות האפשריות:
1. **Innstant Hotel ID שגוי** — ID 237547 ב-Innstant מצביע על "Pierre" (שם ישן של המלון)
2. **Innstant destination mapping** — המלון לא ממופה ל-Miami Beach
3. **חסר ZenithId** — צריך לבדוק ב-Med_Hotels

```sql
-- בדוק את ה-mapping של Notebook
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE HotelId = 237547;

-- בדוק מה ה-WebJob מחזיר
SELECT TOP 5 o.Id, o.DestinationId, o.WebJobStatus, o.DateFrom, o.DateTo
FROM [SalesOffice.Orders] o
WHERE o.DestinationId = 237547
ORDER BY o.Id DESC;
```

---

## מה קורה אחרי התיקון

1. מריצים את ה-UPDATE SQL
2. ה-WebJob (רץ כל 5 דקות) מזהה Orders עם `WebJobStatus = NULL`
3. ה-WebJob שולח חיפוש ל-Innstant API לכל Order
4. תוצאות נכתבות ל-`SalesOffice.Details`
5. ה-Prediction System (collector כל 3 שעות) קורא את ה-Details החדשים
6. 10 מלונות מופיעים ב-Options Board עם predictions

**זמן צפוי:** 15-30 דקות אחרי ה-UPDATE עד ש-Details נוצרים. עוד 3 שעות עד שה-Prediction System אוסף אותם.

---

## סיכום מספרי

| סטטוס | כמות | פעולה |
|--------|------|-------|
| ✅ עובדים | 12 | אין צורך |
| ⚠️ WebJobStatus=nan | **10** | **UPDATE ל-NULL** |
| ⚠️ Mapping: 0 | 1 (Notebook) | בדיקת Innstant mapping |
| ❌ חסרים ב-DB | ~21 | ראה HOTEL_ONBOARDING_REQUEST.md |

**צוות Prediction יאמת הצלחה דרך:**
- `GET /api/v1/salesoffice/status` → total_hotels צריך לעלות מ-12 ל-22
- `GET /api/v1/salesoffice/hotel-readiness` → 22 ready מתוך 23
