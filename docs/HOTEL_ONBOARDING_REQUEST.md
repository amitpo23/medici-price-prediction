# בקשה: הפעלת 11 מלונות חסרים ב-SalesOffice Pipeline

**תאריך:** 2026-03-16 (עדכון v2)
**מבקש:** צוות Prediction
**דחיפות:** גבוהה — 11 מלונות לא מקבלים סריקות

---

## ממצאי אבחון (מהמתכנת)

### בעיה #1: Innstant API מחזיר 0 חדרים (6 מלונות)

| מלון | ZenithId | בעיה |
|------|---------|------|
| Holiday Inn Express | 5130 | API מחזיר 0 חדרים |
| The Albion Hotel | 5117 | API מחזיר 0 חדרים |
| The Catalina Hotel | 5277 | API מחזיר 0 חדרים |
| Hotel Belleza | 5265 | API מחזיר 0 חדרים |
| Kimpton Angler's | 5136 | API מחזיר 0 חדרים |
| Notebook Miami Beach | 5102 | API מחזיר 0 חדרים |

**סיבות אפשריות:**
- ZenithId שגוי ב-Noovy/Innstant mapping
- המלון לא פעיל ב-Innstant system
- בעיית הרשאות ב-Innstant API

**פעולה נדרשת:** בדוק ב-Noovy/Innstant admin panel שה-venue mappings תקינים.

**ממצאים מבדיקת צוות Prediction (חקירה מעמיקה):**

**🔴 ממצא 1: ערוץ Innstant Travel מנותק בכל 6 המלונות!**
ב-HT Marketplace, ה-Medici channel מחובר ✅ אבל **Innstant Travel channel = Disconnected** בכל 6.
→ **פתרון:** הפעלו את ערוץ Innstant Travel בכל venue (Toggle Disabled→Enabled + Submit)

**🔴 ממצא 2: שני מלונות ממופים ל-Innstant IDs שגויים לחלוטין!**
| מלון שלנו | Innstant ID | מה שה-ID מצביע עליו בפועל |
|-----------|-----------|---------------------------|
| **Holiday Inn Express Miami** | 67387 | Holiday Inn ב-**Miami, Oklahoma** (לא פלורידה!) + status=2 |
| **Albion Hotel Miami Beach** | 855711 | Albion Hotel ב-**Cootamundra, Australia** (מדינה אחרת!) |
→ **פתרון:** צריך למצוא את ה-Innstant IDs הנכונים למלונות במיאמי ולעדכן ב-Med_Hotels

**✅ ממצא 3: 4 מלונות עם מיפוי Innstant נכון:**
- Catalina (#87197) — 1732 Collins Ave, Miami Beach ✅
- Hotel Belleza (#414146) — 2115 Washington Ave, Miami Beach ✅
- Kimpton Angler's (#31226) — Miami Beach ✅ (אבל Innstant Travel channel = Disabled)
- Notebook (#237547) — 216 43rd st, Miami Beach ✅

**SQL לאמת ולתקן:**
```sql
-- וודא ZenithId ב-Med_Hotels
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE HotelId IN (67387, 855711, 87197, 414146, 31226, 237547);

-- 67387 ו-855711 צריכים Innstant IDs חדשים!
-- Innstant Static Data API: https://static-data.innstant-servers.com/hotels/{ID}
-- API Key: $2y$10$yWot7dUYoc7.viH8vK1s0OG.D0n5uKm19Z84WznDiB.ESBnPOikr6
-- חפש את ה-IDs הנכונים עבור:
-- 1. Holiday Inn Express Hotel & Suites, Miami Beach, FL = ???
-- 2. The Albion Hotel, 1650 James Ave, Miami Beach, FL 33139 = ???
```

**🟡 ממצא 4: ערוץ Innstant Travel צריך להיות מופעל**
ב-HT Marketplace, לכל 6 ה-venues ערוץ "Innstant Travel" מופיע כ-Disconnected.
יש להפעיל אותו (Setup → Enable → Submit) בנוסף ל-Medici channel.
**Kimpton #5136** — יש credentials (INNstantTravel/api/innstantapi) אבל Disabled במפורש.

---

### בעיה #2: מיפוי מוצלח אבל אין Details (5 מלונות)

| מלון | API Rooms | Mapped | Details |
|------|----------|--------|---------|
| Dorchester Hotel | 2 | 1 | ❌ 0 |
| Fontainebleau Miami | 13 | 5 | ❌ 0 |
| Generator Miami | 4 | 2 | ❌ 0 |
| Hilton Garden Inn | 3 | 2 | ❌ 0 |
| Miami Airport Hotel | 5 | 2 | ❌ 0 |

**סיבה אפשרית:** Callback processor לא רץ — **2,544 callbacks לא מעובדים!**

**אבל שימו לב:** לפי ה-architecture, Details נוצרים ב-`AddSalesOfficeDetails()` **לפני** ה-Callback. אם יש Mapping > 0 אבל 0 Details, ייתכן ש:
1. `AddSalesOfficeDetails()` נכשל (exception?)
2. Details נוצרו אבל נמחקו אח"כ
3. ה-Details שייכים ל-HotelId אחר (DestinationId vs HotelId mismatch)

**פעולה נדרשת:**
1. בדוק ב-SalesOffice.Log אם יש שגיאות ליד ה-Orders של 5 המלונות
2. תקן/הפעל את ה-Callback processor (2,544 callbacks ממתינים)
3. בדוק ב-Details לפי DestinationId (לא רק HotelId):
```sql
-- חפש Details גם לפי DestinationId
SELECT d.Id, d.HotelId, d.RoomCategory, d.RoomBoard, d.RoomPrice, d.DateCreated,
       o.DestinationId, o.WebJobStatus
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.DestinationId IN (6654, 19977, 701659, 301640, 21842)
   OR d.HotelId IN (6654, 19977, 701659, 301640, 21842)
ORDER BY d.DateCreated DESC;

-- בדוק Logs לשגיאות
SELECT TOP 20 l.DateCreated, l.ActionId, l.Message
FROM [SalesOffice.Log] l
JOIN [SalesOffice.Details] d ON l.SalesOfficeDetailId = d.Id
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.DestinationId IN (6654, 19977, 701659, 301640, 21842)
ORDER BY l.DateCreated DESC;
```

---

## סיכום פעולות נדרשות

### עדיפות 1 (מיידי): הפעל Callback Processor
- 5 מלונות כבר ממופים בהצלחה אבל ה-callbacks לא מעובדים
- תיקון זה יפתור מיד את: Dorchester, Fontainebleau, Generator, Hilton Garden, Miami Airport

### עדיפות 2: תקן Innstant API עבור 6 מלונות
**2A: הפעל ערוץ Innstant Travel** ב-HT Marketplace לכל 6 venues (Setup → Enable → Submit)
**2B: תקן Innstant IDs שגויים:**
- Holiday Inn Express (67387) → מצביע על מלון ב-**Oklahoma**, לא Florida! צריך ID חדש
- Albion Hotel (855711) → מצביע על מלון ב-**Australia**! צריך ID חדש
**2C:** Catalina, Belleza, Kimpton, Notebook — מיפוי Innstant נכון, רק צריך להפעיל ערוץ

### עדיפות 3: אימות
אחרי תיקון, הריצו:
```sql
-- ודא שיש Details חדשים
SELECT d.HotelId, h.Name, COUNT(*) AS details_count, MAX(d.DateCreated) AS last_scan
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
WHERE d.HotelId IN (67387, 855711, 87197, 6654, 19977, 701659, 301640, 414146, 31226, 237547, 21842)
GROUP BY d.HotelId, h.Name
ORDER BY last_scan DESC;
```

---

## מצב Noovy/Hotel.Tools (הושלם ✅)

כל 19 המלונות מוגדרים בצד שלנו:
- Products (Room) ✅
- Rate Plans (RO/BB) ✅
- Medici Channel Connected ✅
- Availability=1 לתאריך 19/09/2026 (בדיקה) ✅

**Innstant B2B מראה 9 מלונות מ-Knowaa Global** (SLS Brickell, Savoy, Iberostar, Crystal Beach, Dream, Marseilles, Fairwind, Kimpton, Notebook)

---

## מצב מלא — 19 מלונות

### עובדים (8) — יש Orders + Details + Predictions:
| HotelId | שם | SO Rooms |
|---------|-----|---------|
| 852120 | SLS LUX Brickell | 535 |
| 64309 | Savoy Hotel | 236 |
| 173508 | Cadet Hotel | 86 |
| 64390 | Crystal Beach Suites | 72 |
| 383277 | Iberostar Berkeley Shore | 71 |
| 241025 | Dream South Beach | 64 |
| 6663 | Marseilles Hotel | 30 |
| 117491 | Fairwind Hotel | 20 |

### בעיה #2 — ממופים אבל אין Details (5):
| HotelId | שם | API Rooms | Mapped | פתרון |
|---------|-----|----------|--------|-------|
| 6654 | Dorchester Hotel | 2 | 1 | הפעל Callback |
| 19977 | Fontainebleau | 13 | 5 | הפעל Callback |
| 701659 | Generator Miami | 4 | 2 | הפעל Callback |
| 301640 | Hilton Garden Inn | 3 | 2 | הפעל Callback |
| 21842 | Miami Airport Hotel | 5 | 2 | הפעל Callback |

### בעיה #1 — API מחזיר 0 חדרים (6):
| HotelId | שם | ZenithId | פתרון |
|---------|-----|---------|-------|
| 67387 | Holiday Inn Express | 5130 | בדוק Innstant mapping |
| 855711 | Albion Hotel | 5117 | בדוק Innstant mapping |
| 87197 | Catalina Hotel | 5277 | בדוק Innstant mapping |
| 414146 | Hotel Belleza | 5265 | בדוק Innstant mapping |
| 31226 | Kimpton Angler's | 5136 | בדוק Innstant mapping* |
| 237547 | Notebook Miami Beach | 5102 | בדוק Innstant mapping* |

*Kimpton ו-Notebook מופיעים ב-Innstant B2B search עם Knowaa Global — ייתכן שהבעיה רק ב-API credentials של WebJob

---

## רשימת Noovy Venue IDs

| HotelId (Innstant) | שם | Noovy Venue ID |
|--------------------|----|---------------|
| 67387 | Holiday Inn Express | 5130 |
| 855711 | The Albion Hotel | 5117 |
| 87197 | The Catalina Hotel | 5277 |
| 6654 | Dorchester Hotel | 5266 |
| 19977 | Fontainebleau Miami Beach | 5268 |
| 701659 | Generator Miami | 5273 |
| 301640 | Hilton Garden Inn Miami SB | 5279 |
| 414146 | Hotel Belleza | 5265 |
| 31226 | Kimpton Angler's Hotel | 5136 |
| 237547 | Notebook Miami Beach | 5102 |
| 21842 | Miami International Airport Hotel | 5275 |

---

**צוות Prediction יאמת הצלחה דרך:**
- `GET /api/v1/salesoffice/hotel-readiness` → 19/19 ready
- `GET /api/v1/salesoffice/status` → total_hotels = 30+
- `GET /api/v1/salesoffice/options?all=true` → כל 19 עם predictions
