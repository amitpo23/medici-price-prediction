# חקירה: למה רק 82 עדכוני מחיר (Details) נשלחו לזניט?

**תאריך:** 23.02.2026  
**בעיה:** מתוך מאות Orders עם Mapping, רק ~82 Details פעילים → רק ~82 עדכוני מחיר בפועל לזניט

---

## 🔍 ממצא מרכזי: הסיבה האמיתית

### ה-Push של Availability לזניט **נכשל** עבור מלונות 20702 ו-24982

הזרימה ב-WebJob היא:
```
Order → Search Innstant API → Find Rooms With Mapping → Push Availability to Zenith → Create Detail
```

**אם ה-Push נכשל → Detail לא נוצר כלל.**

---

## 📊 עדויות מטבלת SalesOffice.Log

### Action Types:
| ActionId | Name | תיאור |
|----------|------|--------|
| 1 | AddRecordToDb | יצירת Detail חדש |
| 2 | DeleteItemFromDb | מחיקת Detail |
| 3 | UpdateRecordInDb | עדכון Detail קיים |
| 4 | DeleteDataFromHotelConnect | מחיקה מזניט |
| 5 | PushDataToHotelConnect | Push Availability לזניט |
| 6 | UpdateRateInHotelConnect | עדכון מחיר בזניט |

### Result Types:
| ResultId | Name |
|----------|------|
| 1 | Success |
| 2 | **Failed** |
| 3 | InProgress |

### לוג היום (23.02.2026) לפי מלון:

| מלון | Action | Result | כמות |
|------|--------|--------|------|
| **20702** (Embassy) | PushDataToHotelConnect | **FAILED** | **247** |
| **24982** (Hilton) | PushDataToHotelConnect | **FAILED** | **152** |
| 66814 (Breakwater) | AddRecordToDb | Success | 12 |
| 66814 | DeleteItemFromDb | Success | 16 |
| 66814 | UpdateRecordInDb | Success | 59 |
| 66814 | DeleteDataFromHotelConnect | Success | 16 |
| 66814 | PushDataToHotelConnect | **Success** | 12 |
| 66814 | UpdateRateInHotelConnect | Success | 10 |
| 854881 (citizenM) | UpdateRecordInDb | Success | 511 |
| 854881 | UpdateRateInHotelConnect | Success | 13 |

### לוג כל הזמנים:
- **20702**: סה"כ היסטורי: **247 Push FAILED** — אף פעם לא הצליח. אפס Details אי פעם.
- **24982**: סה"כ היסטורי: **152 Push FAILED** — אף פעם לא הצליח. אפס Details אי פעם.
- **854881**: 213 AddRecord(✓), 17,148 Update(✓), 213 Push(✓), 313 UpdateRate(✓) — עובד מושלם
- **66814**: 3,365 AddRecord(✓), 71,767 Update(✓), 3,365 Push(✓), 3,083 UpdateRate(✓) — עובד מושלם

---

## 🏨 פירוט לפי מלון

### 854881 - citizenM Miami Brickell (ZenithId: 5079) ✅ עובד
- **73 Orders** עם Mapping → **73 Details פעילים** (יחס 1:1 מושלם)
- Mapping: 1 ערך ב-ratebycat: `standard:RO` (CategoryId=1, BoardId=1, RatePlanCode=12043, InvTypeCode=Stnd)
- Details נוצרו ב-17.02, מתעדכנים כל מחזור (DateUpdated = 23.02)
- מחירים: $137-$539, ממוצע $266

### 66814 - Breakwater South Beach (ZenithId: 5110) ✅ עובד
- **9 Orders** פעילים → **12 Details פעילים** (Details מנוהלים עם יצירה+מחיקה יומית)
- Mapping: 4 ערכים ב-ratebycat: Stnd, SPR, DLX, Suite (RatePlanCode=12078)
- Details פעילים: superior(6), deluxe(3), suite(3) — **"standard" לא נוצר** (ייתכן שאין חדר standard ב-API)
- מחירים: $159-$596, ממוצע $357

### 20702 - Embassy Suites (ZenithId: 5081) ❌ נכשל
- **74 Orders** עם Mapping → **0 Details** (אף פעם!)
- Mapping: 2 ערכים ב-ratebycat: Stnd + Suite (RatePlanCode=12045)
- **כל 247 ניסיונות Push לזניט נכשלו** (ActionId=5, ActionResultId=2)
- SalesOfficeDetailId=0 בכל הלוגים → Detail מעולם לא נוצר
- ה-Push שנכשל שולח: `HotelCode=5081, InvTypeCode=Stnd/Suite, RatePlanCode=12045`

### 24982 - Hilton Miami Downtown (ZenithId: 5084) ❌ נכשל
- **48 Orders** עם Mapping → **0 Details** (אף פעם!)
- Mapping: 2 ערכים ב-ratebycat: Stnd + Suite (RatePlanCode=12048)
- **כל 152 ניסיונות Push לזניט נכשלו**
- ה-Push שנכשל שולח: `HotelCode=5084, InvTypeCode=Stnd/Suite, RatePlanCode=12048`

---

## ⚠️ מלונות נוספים עם אותה בעיה (Push תמיד נכשל)

| HotelId | ZenithId | Pushes Failed | Details Ever |
|---------|----------|---------------|--------------|
| 6661 | ? | 41,515 | 0 |
| 6805 | ? | 16,819 | 0 |
| 852120 | ? | 6,494 | 0 |

מלונות אלו **מעולם** לא הצליחו לבצע Push לזניט.

---

## 🎯 אבחנה: למה ה-Push נכשל?

ה-Push נשלח דרך SOAP API ל: `https://hotel.tools/service/Medici%20new`

### השערות (דורשות בדיקה בזניט):

1. **המלונות 5081/5084 לא מוגדרים נכון בזניט**
   - ייתכן שה-HotelCode לא קיים או לא פעיל בזניט
   - ייתכן שה-RatePlanCode (12045/12048) לא מוגדר עבור המלונות הללו

2. **InvTypeCode לא תואם**
   - ב-ratebycat: `Stnd` ו-`Suite`
   - ייתכן שבזניט ה-InvTypeCode שונה

3. **RatePlanCode לא תואם**
   - 12045 (Embassy), 12048 (Hilton) — ייתכן שקודים אלו לא קיימים בזניט

4. **הרשאות חסרות**
   - ייתכן שה-API User אין לו הרשאה עבור המלונות הללו

### השוואה עם מלונות שעובדים:
| | 66814 (עובד) | 854881 (עובד) | 20702 (נכשל) | 24982 (נכשל) |
|---|---|---|---|---|
| ZenithId | 5110 | 5079 | 5081 | 5084 |
| RatePlanCode | 12078 | 12043 | 12045 | 12048 |
| InvTypeCode | Stnd/SPR/DLX/Suite | Stnd | Stnd/Suite | Stnd/Suite |

---

## 📝 סיכום: למה רק 82 Details?

```
854881: 73 Details (Zenith push עובד → Details נוצרים ומתעדכנים)
 66814: 9 Details  (Zenith push עובד → Details נוצרים/נמחקים/נוצרים מחדש)
   Other hotels: ~4 Details (6660, 24989, 826068)
---
Total: ~86 Details פעילים

20702: 0 Details  (Zenith push נכשל → Detail מעולם לא נוצר)
24982: 0 Details  (Zenith push נכשל → Detail מעולם לא נוצר)
```

**התשובה: ה-WebJob מצליח לחפש ולמצוא חדרים עם Mapping ("Rooms With Mapping: 1"), אבל כשהוא מנסה לעדכן Availability בזניט, הקריאה נכשלת עבור 20702 ו-24982. בגלל הכשלון הזה, Details לא נוצרים → עדכוני מחיר לא נשלחים.**

---

## 🔧 צעדים הבאים (מ-23/02 - הושלמו)

1. ~~**בדוק בזניט (hotel.tools)**: האם מלונות 5081 ו-5084 קיימים ופעילים?~~ ✅
2. ~~**בדוק RatePlanCode**: האם 12045 ו-12048 מוגדרים נכון עבור המלונות הללו?~~ ✅
3. ~~**בדוק InvTypeCode**: האם Stnd/Suite מוגדרים כ-Room Types בזניט עבור המלונות הללו?~~ ✅
4. ~~**בדוק logs של hotel.tools**: האם יש error ספציפי שחוזר מה-API?~~ ✅
5. ~~**נסה Push ידני**: שלח SOAP request ישירות ל-hotel.tools עבור HotelCode=5081 ובדוק את ה-response/error~~ ✅

---

## ✅ פתרון (בוצע 23/02/2026)

### שלב 1: חקירה - מה אמר ה-API?

בדיקת `OTA_HotelAvailRQ` (Retrieve Products) גילתה שמלונות 5081 ו-5084 מחזירים `<RoomStays/>` ריק.
השוואה למלונות עובדים (5079, 5110) שמחזירים Products מלאים.

שגיאת ה-Push הספציפית:
```
Error Type="12" Code="402": Can not find product for availability update (5081/Stnd/12045)
Error Type="12" Code="402": Can not find product for rate update (5081/Stnd/12045)
```

### שלב 2: סיבה - חסרים Products ב-hotel.tools

המלונות היו מוגדרים בזניט (קיבלו HotelCode) אבל **לא הוגדרו להם Products** (שילובי RoomType + RatePlan).
בממשק hotel.tools, לשונית Products הייתה ריקה.

### שלב 3: תיקון - הגדרת Products ב-hotel.tools UI

תאריך ביצוע: **23/02/2026**

**Embassy Suites (5081)** - הוגדרו 2 Products:
- Standard: RoomTypeCode=Stnd
- Suite: RoomTypeCode=Suite

כל Product קיבל 2 RatePlans:
- RatePlanCode **12045** - room only
- RatePlanCode **13170** - bed and breakfast (חדש!)

**Hilton Downtown (5084)** - הוגדרו 2 Products:
- Standard: RoomTypeCode=Stnd
- Suite: RoomTypeCode=Suite

כל Product קיבל 2 RatePlans:
- RatePlanCode **12048** - Refundable
- RatePlanCode **13173** - bed and breakfast (חדש!)

### שלב 4: אימות - בדיקות API ישירות

**Retrieve (OTA_HotelAvailRQ):**

| מלון | לפני | אחרי |
|------|-------|-------|
| 5081 Embassy | `<RoomStays/>` ריק | **4 Products** (Stnd+Suite × 12045+13170) |
| 5084 Hilton | `<RoomStays/>` ריק | **4 Products** (Stnd+Suite × 12048+13173) |

**Push Availability (OTA_HotelAvailNotifRQ):**

| מלון | לפני | אחרי |
|------|-------|-------|
| 5081 Embassy | `Error 402` | **`<Success/>`** ✅ |
| 5084 Hilton | `Error 402` | **`<Success/>`** ✅ |

**Push Rate (OTA_HotelRateAmountNotifRQ):**

| מלון | לפני | אחרי |
|------|-------|-------|
| 5081 Embassy | `Error 402` | **`<Success/>`** ✅ |
| 5084 Hilton | `Error 402` | **`<Success/>`** ✅ |

### ⚠️ RatePlanCodes חדשים (B&B) - טרם מומפו

נוספו RatePlanCodes חדשים בזניט שעוד **לא ממופים** ב-`Med_Hotels_ratebycat`:

| מלון | RatePlanCode | תיאור | סטטוס ב-DB |
|------|-------------|--------|------------|
| 5081 Embassy | **13170** | bed and breakfast | ❌ לא ממופה |
| 5084 Hilton | **13173** | bed and breakfast | ❌ לא ממופה |

כדי שגם מחירי B&B יידחפו, צריך להוסיף שורות ל-`Med_Hotels_ratebycat`:
```sql
-- Embassy B&B mapping (BoardId=2 for BB)
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES (20702, 2, 1, '13170', 'Stnd'),
       (20702, 2, 12, '13170', 'Suite')

-- Hilton B&B mapping
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES (24982, 2, 1, '13173', 'Stnd'),
       (24982, 2, 12, '13173', 'Suite')
```

### מצב נוכחי - סיכום סופי (24/02/2026)

| מלון | ZenithId | Products | Push Avail | Push Rate | סטטוס |
|------|----------|----------|------------|-----------|-------|
| citizenM | 5079 | 2 | ✅ | ✅ | עובד (מאז ההתחלה) |
| Breakwater | 5110 | 8 | ✅ | ✅ | עובד (מאז ההתחלה) |
| **Embassy** | **5081** | **4** | **✅** | **✅** | **תוקן 23/02** |
| **Hilton** | **5084** | **4** | **✅** | **✅** | **תוקן 23/02** |

**ה-WebJob הבא שירוץ יצליח לדחוף מחירים וזמינות ל-4 מלונות במקום 2.**
