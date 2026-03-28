# מדריך הגדרת מלונות — Noovy & Hotel.Tools
> מדריך עצמאי מלא: כל השלבים, כל הדוגמאות, כל הסקריפטים

**תאריך עדכון:** 2026-03-27
**גרסה:** 1.0
**כותב:** Claude Code (על בסיס עבודה אמיתית שבוצעה מרץ 2026)

---

## תוכן עניינים

1. [סקירת המערכת — 4 השכבות](#1-סקירת-המערכת--4-השכבות)
2. [התחברות לפלטפורמות](#2-התחברות-לפלטפורמות)
3. [שלב 1: יצירת מוצרים ב-Hotel.Tools / Noovy](#3-שלב-1-יצירת-מוצרים-ב-hoteltools--noovy)
4. [שלב 2: מיפוי בטבלת Med_Hotels_ratebycat](#4-שלב-2-מיפוי-בטבלת-med_hotels_ratebycat)
5. [שלב 3: אימות ב-Innstant](#5-שלב-3-אימות-ב-innstant)
6. [שלב 4: הזמנות SalesOffice](#6-שלב-4-הזמנות-salesoffice)
7. [סקריפטים אוטומטיים — מה כל אחד עושה](#7-סקריפטים-אוטומטיים--מה-כל-אחד-עושה)
8. [GraphQL API של Noovy — מדריך מלא](#8-graphql-api-של-noovy--מדריך-מלא)
9. [Zenith SOAP API — דחיפת מחירים](#9-zenith-soap-api--דחיפת-מחירים)
10. [פתרון בעיות נפוצות](#10-פתרון-בעיות-נפוצות)
11. [נספח: רשימת מלונות מיאמי](#11-נספח-רשימת-מלונות-מיאמי)

---

## 1. סקירת המערכת — 4 השכבות

כל מלון חייב לעבור 4 שכבות הגדרה לפני שהוא פעיל במערכת:

```
┌─────────────────────────────────────────────────────────────┐
│  שכבה 1: Noovy / Hotel.Tools                                │
│  יצירת מוצרים (חדרים + ארוחות) + קבלת RatePlanCode/InvTypeCode│
├─────────────────────────────────────────────────────────────┤
│  שכבה 2: Med_Hotels                                         │
│  הגדרת Innstant_ZenithId (VenueId) + isActive=1             │
├─────────────────────────────────────────────────────────────┤
│  שכבה 3: Med_Hotels_ratebycat                               │
│  מיפוי Board+Category → RatePlanCode + InvTypeCode          │
├─────────────────────────────────────────────────────────────┤
│  שכבה 4: SalesOffice.Orders                                 │
│  הפעלת סריקה — הזמנת חיפוש פעילה                           │
└─────────────────────────────────────────────────────────────┘
```

**אם חסרה שכבה אחת — המלון לא יעבוד:**
- חסר שכבה 1 → אין מוצרים ב-Zenith, Push ייכשל
- חסר שכבה 2 → המלון מסונן החוצה בזמן הסריקה
- חסר שכבה 3 → החדר נדלג ב-`FindPushRatePlanCode()`
- חסר שכבה 4 → אין סריקה בכלל

---

## 2. התחברות לפלטפורמות

### 2.1 Hotel.Tools (= Zenith Channel Manager)

**כתובת:** `https://hotel.tools/today-dashboard`

**שדות התחברות:**
| שדה | משתנה סביבה | תיאור |
|------|------------|--------|
| Account Name | `HOTEL_TOOLS_ACCOUNT_NAME` | שם החשבון |
| Agent Name | `HOTEL_TOOLS_AGENT_NAME` | שם המשתמש |
| Password | `HOTEL_TOOLS_PASSWORD` | סיסמה |

**תהליך התחברות ב-Playwright:**
```javascript
// scripts/_tmp_hoteltools_auth_probe.js
const page = await browser.newPage();
await page.goto('https://hotel.tools/today-dashboard');

// מילוי טופס התחברות
await page.getByRole('textbox', { name: /account/i }).fill(process.env.HOTEL_TOOLS_ACCOUNT_NAME);
await page.getByRole('textbox', { name: /agent|user/i }).fill(process.env.HOTEL_TOOLS_AGENT_NAME);
await page.getByRole('textbox', { name: /password/i }).fill(process.env.HOTEL_TOOLS_PASSWORD);
await page.getByRole('button', { name: /login/i }).click();

// המתנה לטעינת הדשבורד
await page.waitForURL('**/today-dashboard**', { timeout: 15000 });
```

**fallback למשתנים:**
```
HOTEL_TOOLS_ACCOUNT_NAME → NOOVY_ACCOUNT_NAME
HOTEL_TOOLS_AGENT_NAME → HOTEL_TOOLS_USERNAME → NOOVY_USERNAME
HOTEL_TOOLS_PASSWORD → NOOVY_PASSWORD
```

---

### 2.2 Noovy (= ממשק ניהול מוצרים)

**כתובת:** `https://app.noovy.com/bookings`

**שדות התחברות:** אותם credentials כמו Hotel.Tools (אותו חשבון)

**תהליך התחברות:**
```javascript
// scripts/export_noovy_venue_products.js
await page.goto('https://app.noovy.com/bookings');
await page.getByRole('textbox', { name: /account/i }).fill(accountName);
await page.getByRole('textbox', { name: /agent|user/i }).fill(username);
await page.getByRole('textbox', { name: /password/i }).fill(password);
await page.getByRole('button', { name: /login/i }).click();
await page.waitForURL('**/bookings**', { timeout: 15000 });
```

**אחרי התחברות, ה-Token נשמר ב-cookies ומשמש ל-GraphQL:**
```javascript
// שליפת Token מהדפדפן
const cookies = await context.cookies();
const tokenCookie = cookies.find(c => c.name === 'token');
```

---

### 2.3 Innstant (= פלטפורמת הפצה B2B)

**כתובת:** `https://b2b.innstant.travel/agent/login`

**שדות התחברות:**
| שדה | משתנה סביבה |
|------|------------|
| AccountName | `INNSTANT_ACCOUNT_NAME` |
| Username | `INNSTANT_USERNAME` |
| Password | `INNSTANT_PASSWORD` |

**תהליך התחברות:**
```javascript
// scripts/validate_innstant_inventory.js
await page.goto('https://b2b.innstant.travel/agent/login');
await page.fill('#AccountName', process.env.INNSTANT_ACCOUNT_NAME);
await page.fill('#Username', process.env.INNSTANT_USERNAME);
await page.fill('#Password', process.env.INNSTANT_PASSWORD);
await page.click('button[type="submit"]');
await page.waitForTimeout(4000); // חשוב - login processing
```

---

## 3. שלב 1: יצירת מוצרים ב-Hotel.Tools / Noovy

### 3.1 מהו "מוצר"?

מוצר (Product) הוא יחידה במערכת שמייצגת:
- **חדר** (room) — Standard, Deluxe, Superior, Suite
- **תוכנית ארוחות** (meal_plan) — RO, BB, HB, FB, AI

**כל Venue (מלון) צריך לפחות:**
- 1 מוצר חדר (Standard)
- 1-2 תוכניות ארוחות (RO + BB)

### 3.2 יצירה ידנית דרך הממשק

**ניווט:** Hotel.Tools → Products → + New Product

**טופס יצירת מוצר — 3 טאבים:**

#### טאב 1: General (כללי)
| שדה | Selector | דוגמה | חובה |
|------|----------|--------|------|
| Product Type | `#f-product-type` | `room` / `meal_plan` | ✅ |
| Title | `#f-title` | `Standard Room` | ✅ |
| Short Name | `#f-short-name` | `STD` | ✅ |
| Meal Plan Type | `#f-meal-plan-type` | `RO` / `BB` (רק ל-meal_plan) | ✅* |
| Base Price | `#f-base-price` | `100` | ✅ |
| Min Price | `#f-min-price` | `50` | |
| Real Price | `#f-real-price` | `120` | |
| Base Currency | `#f-base-currency` | `USD` | ✅ |
| Base Quantity | `#f-base-quantity` | `10` | |
| Max Occupancy | `#f-max-occupancy` | `2` | |
| Status | `#f-status` | `active` | ✅ |
| PMS Code | `#f-pms-code` | `STD` / `RO` | |
| Start Date | `#f-start-date` | `2025-01-01` | |
| End Date | `#f-end-date` | `2027-12-31` | |

#### טאב 2: Locations (מיקומים)
- בחירת Country → `US`
- בחירת Venue → לפי VenueId
- לחיצה על **Save Location**

#### טאב 3: Description (תיאור)
- אופציונלי — תיאור רב-שפתי

### 3.3 יצירה אוטומטית — שכפול מ-Venue מייחס

**הסקריפט:** `scripts/apply_noovy_reference_clone.js`

**עקרון:** לוקחים Venue שכבר מוגדר נכון (Reference), קוראים את כל המוצרים שלו, ומשכפלים אותם ל-Venues חדשים.

**הגדרות:**
```bash
# Venue מייחס (כבר מוגדר נכון)
REFERENCE_VENUE=5110  # ברירת מחדל, אפשר גם 2766

# יעדים
TARGET_VENUES=5064,5075,5082,5083,5113
```

**מצב DRY-RUN (ברירת מחדל — בטוח):**
```bash
npx playwright test scripts/apply_noovy_reference_clone.js
```

**מצב APPLY (מבצע בפועל):**
```bash
npx playwright test scripts/apply_noovy_reference_clone.js -- --apply
```

**מה הסקריפט עושה צעד אחר צעד:**

```
1. התחברות ל-Hotel.Tools
2. מעבר ל-Venue מייחס → קריאת כל המוצרים
3. לכל מוצר:
   a. כניסה לדף עריכה → שליפת כל השדות (Template)
   b. שמירת Template: { productType, title, shortName, mealPlanType, basePrice, ... }
4. לכל Venue יעד:
   a. הגדרת Venue Context
   b. בדיקה אם מוצר כבר קיים (לפי שם מנורמל)
   c. אם חסר → יצירת מוצר חדש מה-Template
   d. אימות שהמוצר נוצר בהצלחה
5. הפקת דוח JSON → data/reports/noovy_clone_batch1_*.json
```

**מבנה Template שנשלף:**
```javascript
{
  productType: 'room',            // או 'meal_plan'
  title: 'Standard Room',
  shortName: 'STD',
  mealPlanType: '',               // 'RO', 'BB' למוצרי meal_plan
  basePrice: '100',
  minPrice: '50',
  realPrice: '120',
  baseCurrency: 'USD',
  baseQuantity: '10',
  affectedBy: '',
  maxOccupancy: '2',
  startDate: '2025-01-01',
  endDate: '2027-12-31',
  exclusive: '',
  tags: '',
  productOrder: '1',
  roomsReserve: '',
  status: 'active',
  pmsCode: 'STD'
}
```

### 3.4 הוספת Room Only (RO) חסר

**הבעיה:** הרבה מלונות היו עם BB בלבד, בלי RO.

**הסקריפט:** `scripts/add_room_only_mealplan.js`

**מה עושה:**
1. מתחבר ל-Hotel.Tools
2. הולך ל-Venue 5077 (SLS Lux Brickell) — Reference
3. מוצא מוצר BB קיים → קורא את ה-Template שלו
4. יוצר Template חדש מבוסס BB אבל:
   - Title: `room only`
   - Short Name: `RO`
   - Meal Plan Type: `RO`
   - כל המחירים: `0`
   - PMS Code: `RO`
5. עובר על כל Venue יעד → בודק אם יש כבר RO → אם לא, יוצר

**פלט:**
```json
{
  "targets": ["5064", "5075", "5082"],
  "created": ["5064", "5082"],
  "skipped": [{"venue": "5075", "reason": "RO already exists"}],
  "errors": []
}
```

### 3.5 ייצוא מוצרים קיימים (לבדיקה)

**הסקריפט:** `scripts/export_noovy_venue_products.js`

**שימוש:** מייצא את כל המוצרים של Venue מסוים לקובץ JSON

**פלט:**
```json
{
  "venueId": 5110,
  "rooms": [
    { "productId": 12345, "name": "Standard Room", "shortName": "STD", "status": "active", "basePrice": 100 },
    { "productId": 12346, "name": "Deluxe Room", "shortName": "DLX", "status": "active", "basePrice": 200 }
  ],
  "mealPlans": [
    { "productId": 12347, "name": "Room Only", "shortName": "RO", "mealPlanType": "RO", "basePrice": 0 },
    { "productId": 12348, "name": "Bed & Breakfast", "shortName": "BB", "mealPlanType": "BB", "basePrice": 25 }
  ]
}
```

### 3.6 בדיקת פערים (Gap Analysis)

**הסקריפט:** `scripts/noovy_reference_gap_dryrun.js`

**מה עושה:**
1. שולף מוצרים מ-Venue מייחס (5110)
2. שולף מוצרים מכל Venue יעד
3. משווה לפי key מנורמל: `${productType}::${normalizedName}`
4. מציג מה חסר בכל Venue

**פלט דוגמה:**
```json
{
  "reference": { "venueId": 5110, "rooms": 5, "mealPlans": 3 },
  "targets": [
    {
      "venueId": 5064,
      "rooms": 3, "mealPlans": 1,
      "missingRooms": ["Deluxe Room", "Suite"],
      "missingMealPlans": ["BB", "HB"]
    }
  ]
}
```

---

## 4. שלב 2: מיפוי בטבלת Med_Hotels_ratebycat

### 4.1 מה הטבלה הזו?

`Med_Hotels_ratebycat` היא **הלב של המערכת** — היא אומרת:
> "למלון X, עם ארוחה Y וקטגוריית חדר Z, ה-RatePlanCode הוא ABC וה-InvTypeCode הוא DEF"

**בלי שורה בטבלה הזו — החדר יידלג לחלוטין!**

### 4.2 מבנה הטבלה

```sql
CREATE TABLE Med_Hotels_ratebycat (
    Id          INT PRIMARY KEY IDENTITY,
    HotelId     INT NOT NULL,      -- FK ל-Med_Hotels
    BoardId     INT NOT NULL,      -- FK ל-MED_Boards (1=RO, 2=BB, 3=HB, 4=FB, 5=AI)
    CategoryId  INT NOT NULL,      -- FK ל-MED_Room_Categories (1=Standard, 2=Superior, 4=Deluxe, 12=Suite)
    RatePlanCode VARCHAR(50),      -- קוד Rate Plan ב-Zenith/Noovy
    InvTypeCode  VARCHAR(50)       -- קוד סוג חדר ב-Zenith/Noovy
);
```

### 4.3 קודי Board (ארוחות)

| BoardId | קוד | שם |
|---------|------|------|
| 1 | RO | Room Only |
| 2 | BB | Bed & Breakfast |
| 3 | HB | Half Board |
| 4 | FB | Full Board |
| 5 | AI | All Inclusive |
| 6 | CB | Continental Breakfast |
| 7 | BD | Bed |

### 4.4 קודי Category (קטגוריות חדרים)

| CategoryId | שם | InvTypeCode טיפוסי |
|-----------|------|-------------------|
| 1 | Standard | STD / Stnd |
| 2 | Superior | SPR |
| 4 | Deluxe | DLX |
| 12 | Suite | Suite / SUI |

### 4.5 דוגמת מיפוי מלאה — Embassy Suites (HotelId=20702)

```sql
-- RatePlanCode ו-InvTypeCode מתקבלים מ-Noovy/Zenith
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES
(20702, 1, 1,  '12045', 'STD'),   -- RO + Standard
(20702, 1, 12, '12045', 'SUI'),   -- RO + Suite
(20702, 2, 1,  '13164', 'Stnd'),  -- BB + Standard
(20702, 2, 12, '13164', 'Suite'); -- BB + Suite
```

### 4.6 איך להשיג את ה-RatePlanCode וה-InvTypeCode?

**אפשרות 1: מ-Noovy GraphQL**
```javascript
// שליפת Rate Plans
const query = `
  query {
    product_list(
      filter: { venueId: 5110 }
      order: { productOrder: DESC }
    ) {
      productId
      name
      productType
      pmsCode      // ← זה ה-InvTypeCode
    }
  }
`;
```

**אפשרות 2: מ-Zenith OTA_HotelAvailRQ**
```xml
<!-- שאילתת זמינות מחזירה את הקודים -->
<OTA_HotelAvailRQ>
  <AvailRequestSegments>
    <AvailRequestSegment>
      <HotelSearchCriteria>
        <Criterion>
          <HotelRef HotelCode="5110"/>
        </Criterion>
      </HotelSearchCriteria>
    </AvailRequestSegment>
  </AvailRequestSegments>
</OTA_HotelAvailRQ>

<!-- התשובה מכילה: -->
<RoomStay>
  <RatePlans>
    <RatePlan RatePlanCode="12045"/>  <!-- ← RatePlanCode -->
  </RatePlans>
  <RoomTypes>
    <RoomType RoomTypeCode="STD"/>    <!-- ← InvTypeCode -->
  </RoomTypes>
</RoomStay>
```

**אפשרות 3: מתוך ממשק Hotel.Tools**
- Products → לחיצה על מוצר → הקוד מופיע ב-URL או בשדה PMS Code

### 4.7 הגדרת Med_Hotels

```sql
-- שלב 2: עדכון טבלת Med_Hotels
UPDATE Med_Hotels
SET Innstant_ZenithId = '5110',  -- VenueId מ-Noovy/Hotel.Tools
    isActive = 1                  -- הפעלת המלון
WHERE HotelId = 20702;
```

**⚠️ חשוב:** `Innstant_ZenithId` חייב להיות > 0, אחרת הסריקה מסננת את המלון!

---

## 5. שלב 3: אימות ב-Innstant

### 5.1 בדיקה ידנית

1. התחבר ל-`https://b2b.innstant.travel/agent/login`
2. חפש מלון: `https://b2b.innstant.travel/search/hotels?service=hotels&searchQuery=hotel-{hotelId}&startDate=2026-06-10&endDate=2026-06-11&account-country=US&adults=2`
3. לחץ "Show Rooms"
4. ודא שמופיעים חדרים עם ה-Board הנכון (RO, BB)

### 5.2 אימות אוטומטי

**הסקריפט:** `scripts/validate_innstant_inventory.js`

**מה עושה:**
1. שולף ציפיות מהמסד (Med_Hotels_ratebycat) — אילו Boards/Categories צריכים להיות
2. מתחבר ל-Innstant
3. לכל מלון:
   - מחפש את דף המלון
   - לוחץ "Show Rooms" + "Show more rooms" (עד 5 פעמים)
   - שולף Boards ו-Categories מהטקסט בדף
   - משווה מול הציפיות מהמסד
4. מפיק דוח pass/fail

**דוגמת פלט:**
```json
{
  "hotelId": 20702,
  "hotelName": "Embassy Suites Miami Airport",
  "status": "passed",
  "expectedBoards": ["RO", "BB"],
  "mealPlansFound": ["RO", "BB"],
  "missingBoards": [],
  "expectedCategories": ["Standard", "Suite"],
  "categoriesFound": ["Standard", "Suite"],
  "missingCategories": [],
  "roomLineCount": 15,
  "url": "https://b2b.innstant.travel/hotel/..."
}
```

### 5.3 השוואה שלושה צדדים

**הסקריפט:** `scripts/compare_innstant_hoteltools_inventory.js`

**הסקריפט הכי חשוב — משווה בין שלוש מערכות בבת אחת:**

```
Innstant (מה שהספקים מציעים)
    ↕ השוואה
Hotel.Tools (מה שהגדרנו)
    ↕ השוואה
Database (מה שצריך להיות)
```

**פלט:**
```json
{
  "hotelId": 66814,
  "hotelName": "Breakwater South Beach",
  "venueId": 2766,
  "innstantBoards": ["RO", "BB"],
  "hotelToolsBoards": ["RO", "BB"],
  "expectedBoards": ["RO", "BB"],
  "missingBoardsInHotelTools": [],
  "missingBoardsInInnstant": [],
  "innstantSuppliers": ["InnstantTravel", "HotelBeds", "Stuba", "WebBeds"],
  "innstantMinPrice": 89,
  "innstantMaxPrice": 245,
  "status": "ok"
}
```

**Action Items שהסקריפט מייצר:**
- `"Map HotelId to VenueID in Med_Hotels.Innstant_ZenithId"` — אם Venue לא ממופה
- `"Complete products in Hotel.Tools/Noovy"` — אם חסרים מוצרים
- `"Check Innstant availability/supplier contracts"` — אם ספקים לא מחזירים תוצאות
- `"No offers returned; verify date/rate/stop-sell"` — אם אין הצעות בכלל

---

## 6. שלב 4: הזמנות SalesOffice

### 6.1 יצירת הזמנת סריקה

לאחר שכל 3 השכבות הקודמות מוגדרות, יוצרים הזמנת סריקה:

```sql
INSERT INTO [SalesOffice.Orders] (DateFrom, DateTo, DestinationType, DestinationId)
VALUES ('2026-06-10', '2026-06-11', 'city', 'MIA');
```

### 6.2 מה קורה מאחורי הקלעים

```
WebJob (כל 5 דקות) מרים את ההזמנה
    ↓
חיפוש ב-Innstant API → מקבל רשימת חדרים
    ↓
סינון: רק מלונות עם Innstant_ZenithId > 0 ו-isActive = 1
    ↓
לכל חדר: FindPushRatePlanCode(hotelId, boardId, categoryId)
    ├→ נמצא → כותב ל-SalesOffice.Details
    └→ לא נמצא → דילוג (!)
    ↓
עדכון WebJobStatus: "Completed; Api: 16; Flat: 5; Map: 4; Miss: 1"
```

### 6.3 הפונקציה הקריטית: FindPushRatePlanCode

```csharp
// EFModel/BaseEF.cs - שורה 3026
async Task<(string?, string?)> FindPushRatePlanCode(int hotelId, int boardId, int categoryId)
{
    var result = await ctx.MedHotelsRatebycats
        .FirstOrDefaultAsync(i => i.HotelId == hotelId &&
                                  i.BoardId == boardId &&
                                  i.CategoryId == categoryId);

    if (result != null)
        return (result.RatePlanCode, result.InvTypeCode);  // ✅ עובר
    else
        return (null, null);  // ❌ נדלג!
}
```

### 6.4 הגדרת מחירים (Bulk Update)

**נתיב:** Hotel.Tools → Rates → Bulk Update

**הגדרות:**
- Room Types: בחירת סוגי חדרים
- Rate Plans: בחירת תוכניות מחיר
- Date Range: טווח תאריכים
- Rate Update Mode: `set` / `increase` / `decrease`
- Availability: `open` / `close` / number

**דוגמה שנעשתה:**
```
מלונות: 13 מלונות מיאמי
מחיר: Fixed $1000
תאריכים: 1-10 אוגוסט 2026
```

---

## 7. סקריפטים אוטומטיים — מה כל אחד עושה

### 7.1 סקריפטי ייצור (Production)

| סקריפט | תיאור | הרצה |
|--------|--------|------|
| `apply_noovy_reference_clone.js` | שכפול מוצרים מ-Venue מייחס ליעדים | `npx playwright test scripts/apply_noovy_reference_clone.js` |
| `add_room_only_mealplan.js` | הוספת RO חסר למלונות | `npx playwright test scripts/add_room_only_mealplan.js` |
| `export_noovy_venue_products.js` | ייצוא מוצרים של Venue לJSON | `npx playwright test scripts/export_noovy_venue_products.js` |
| `noovy_reference_gap_dryrun.js` | ניתוח פערים בין Reference ליעדים | `npx playwright test scripts/noovy_reference_gap_dryrun.js` |
| `capture_noovy_create_payload.js` | לכידת GraphQL payload בזמן יצירה ידנית | `npx playwright test scripts/capture_noovy_create_payload.js` |
| `compare_innstant_hoteltools_inventory.js` | השוואה שלושה-צדדית | `npx playwright test scripts/compare_innstant_hoteltools_inventory.js` |
| `validate_innstant_inventory.js` | אימות inventory ב-Innstant | `npx playwright test scripts/validate_innstant_inventory.js` |
| `hoteltools_creation_diagnostics.js` | דיאגנוסטיקה ליצירת מוצרים שנכשלו | `npx playwright test scripts/hoteltools_creation_diagnostics.js` |

### 7.2 סקריפטי חקירה (Probing — _tmp_ files)

42 סקריפטים שנכתבו תוך כדי חקירה. הקטגוריות:

**אימות:**
- `_tmp_noovy_auth_probe.js` — שליפת auth context מ-`__NEXT_DATA__`
- `_tmp_noovy_auth_storage_probe.js` — dump של localStorage, sessionStorage, cookies
- `_tmp_noovy_graphql_authheader_test.js` — בדיקת שיטות auth שונות (token, Bearer, authorization)

**GraphQL Schema:**
- `_tmp_noovy_introspection_fetch_noauth.js` — שליפת schema מלא בלי auth
- `_tmp_noovy_createProduct_signature.js` — חתימת createProduct/updateProduct mutations
- `_tmp_noovy_product_schema_probe.js` — שדות של Product type

**יצירת מוצרים:**
- `_tmp_noovy_create_via_graphql_smoke.js` — יצירה ישירה דרך GraphQL
- `_tmp_noovy_create_via_ui_smoke.js` — יצירה דרך מילוי טופס
- `_tmp_noovy_create_variant_locations.js` — ניסיונות יצירה עם variants שונים של location input

**ממשק:**
- `_tmp_noovy_new_product_probe.js` — ניתוח טופס מוצר חדש
- `_tmp_noovy_fields_probe.js` — שליפת HTML של שדות
- `_tmp_noovy_products_dom_probe.js` — ניתוח DOM של דף מוצרים

### 7.3 תוצרי הדוחות

כל הדוחות נשמרים ב-`data/reports/` עם timestamp:

```
data/reports/
  noovy_clone_batch1_1773384759321.json
  noovy_products_venue_5110_1773384759321.json
  noovy_reference_gap_dryrun_1773384759321.json
  noovy_create_payload_capture_1773384759321.json
  inventory_compare_innstant_hoteltools_1773384759321.json
  innstant_inventory_validation_1773384759321.json
  hoteltools_creation_diagnostics_1773384759321.json
  hoteltools_ro_fix_1773384759321.json
```

---

## 8. GraphQL API של Noovy — מדריך מלא

### 8.1 Endpoint

```
URL: https://app.noovy.com/graphql/api
Method: POST
Content-Type: application/json
```

### 8.2 אימות

**אפשרות 1: Cookie-based (מהדפדפן)**
```javascript
// בתוך page.evaluate() — הדפדפן שולח cookies אוטומטית
const response = await fetch('/graphql/api', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, variables })
});
```

**אפשרות 2: Header-based**
```javascript
const response = await fetch('https://app.noovy.com/graphql/api', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'authorization': `token ${authToken}`
  },
  body: JSON.stringify({ query, variables })
});
```

### 8.3 שאילתות (Queries)

#### שליפת מוצרים של Venue
```graphql
query {
  product_list(
    filter: { venueId: 5110, productType: "room" }
    order: { productOrder: DESC, productId: ASC }
  ) {
    productId
    venueId
    name
    shortName
    productType
    mealPlanType
    status
    pmsCode
    basePrice
    minPrice
    realPrice
    baseCurrency
    baseQuantity
    maxOccupancy
    productOrder
    affectedBy
    startDate
    endDate
    exclusive
  }
}
```

#### שליפת Venues מורשים
```graphql
query {
  allowedVenues {
    venueId
    name
  }
}
```

#### שליפת פרופיל משתמש
```graphql
query {
  getProfile {
    userId
    name
    permissions
  }
}
```

### 8.4 Mutations

#### יצירת מוצר
```graphql
mutation {
  createProduct(input: {
    venueId: 5110
    name: "Standard Room"
    shortName: "STD"
    productType: "room"
    basePrice: 100
    baseCurrency: "USD"
    status: "active"
    baseQuantity: 10
    maxOccupancy: 2
    pmsCode: "STD"
    locations: [{
      venueId: 5110
      countryCode: "US"
    }]
  }) {
    productId
    name
    status
  }
}
```

#### עדכון מוצר
```graphql
mutation {
  updateProduct(input: {
    productId: 12345
    basePrice: 150
    status: "active"
  }) {
    productId
    name
    basePrice
  }
}
```

#### שינוי סטטוס מוצר
```graphql
mutation {
  changeProductStatus(
    productId: 12345
    status: "inactive"
  ) {
    productId
    status
  }
}
```

### 8.5 Input Types (מהIntrospection)

```graphql
input productInputParameters {
  venueId: Int!
  name: String!
  shortName: String!
  productType: String!        # "room" | "meal_plan"
  mealPlanType: String        # "RO" | "BB" | "HB" | "FB" | "AI"
  basePrice: Float!
  minPrice: Float
  realPrice: Float
  baseCurrency: String!       # "USD"
  baseQuantity: Int
  maxOccupancy: Int
  status: String!             # "active" | "inactive"
  pmsCode: String
  affectedBy: String
  startDate: String
  endDate: String
  exclusive: Boolean
  tags: [String]
  productOrder: Int
  roomsReserve: Int
  descriptions: [productDescriptionInput]
  locations: [entityLocationInput]
  images: [String]
  metaObjects: [String]
}

input entityLocationInput {
  venueId: Int!
  countryCode: String!        # "US"
}

input productDescriptionInput {
  language: String!           # "en" | "he"
  title: String
  description: String
}
```

### 8.6 Introspection (שליפת Schema)

```graphql
# שליפת כל ה-schema
{
  __schema {
    types {
      name
      fields { name type { name kind } }
    }
    mutationType {
      fields { name args { name type { name } } }
    }
  }
}

# שליפת שדות של Input Type ספציפי
{
  __type(name: "productInputParameters") {
    inputFields {
      name
      type { name kind ofType { name } }
    }
  }
}
```

---

## 9. Zenith SOAP API — דחיפת מחירים

### 9.1 פרטי החיבור

```
URL: https://hotel.tools/service/Medici%20new
Username: APIMedici:Medici Live
Password: 12345
Protocol: SOAP/XML
```

### 9.2 פעולות נתמכות

| פעולה | סטטוס | שימוש |
|-------|--------|-------|
| OTA_HotelAvailRQ | ✅ | שליפת כל המוצרים של מלון |
| OTA_HotelAvailNotifRQ | ✅ | דחיפת זמינות (availability + restrictions) |
| OTA_HotelRateAmountNotifRQ | ✅ | דחיפת מחירים |
| OTA_HotelResNotifRQ | ✅ | קבלת הזמנות (callback) |
| OTA_HotelDescriptiveInfoRQ | ❌ | לא נתמך |
| OTA_ReadRQ | ❌ | לא נתמך |

### 9.3 דחיפת מחיר — דוגמה מלאה

**Python Implementation:** `src/utils/zenith_push.py`

```python
import requests

ZENITH_URL = "https://hotel.tools/service/Medici%20new"
ZENITH_USERNAME = "APIMedici:Medici Live"
ZENITH_PASSWORD = "12345"

def build_soap_envelope(hotel_code, inv_type_code, rate_plan_code, start, end, amount):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
  xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
  <SOAP-ENV:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>{ZENITH_USERNAME}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{ZENITH_PASSWORD}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05"
      Version="1.0" TimeStamp="{datetime.utcnow().isoformat()}">
      <RateAmountMessages HotelCode="{hotel_code}">
        <RateAmountMessage>
          <StatusApplicationControl
            InvTypeCode="{inv_type_code}"
            RatePlanCode="{rate_plan_code}"
            Start="{start}"
            End="{end}"/>
          <Rates>
            <Rate>
              <BaseByGuestAmts>
                <BaseByGuestAmt AgeQualifyingCode="10" AmountAfterTax="{amount}"/>
                <BaseByGuestAmt AgeQualifyingCode="8" AmountAfterTax="{amount}"/>
              </BaseByGuestAmts>
            </Rate>
          </Rates>
        </RateAmountMessage>
      </RateAmountMessages>
    </OTA_HotelRateAmountNotifRQ>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

def push_rate_to_zenith(hotel_code, inv_type_code, rate_plan_code, start, end, amount):
    """דחיפת מחיר ל-Zenith. מחזיר (success: bool, message: str)"""
    envelope = build_soap_envelope(hotel_code, inv_type_code, rate_plan_code, start, end, amount)
    response = requests.post(
        ZENITH_URL,
        data=envelope,
        headers={'Content-Type': 'text/xml; charset=utf-8'},
        timeout=30
    )
    success = response.status_code == 200 and 'Error' not in response.text
    return (success, response.text)
```

### 9.4 דחיפת זמינות

```xml
<OTA_HotelAvailNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" Version="1.0">
  <AvailStatusMessages HotelCode="5110">
    <AvailStatusMessage>
      <StatusApplicationControl
        InvTypeCode="STD"
        RatePlanCode="12045"
        Start="2026-06-10"
        End="2026-06-11"/>
      <LengthsOfStay>
        <LengthOfStay MinMaxMessageType="SetMinLOS" Time="1"/>
        <LengthOfStay MinMaxMessageType="SetMaxLOS" Time="30"/>
      </LengthsOfStay>
      <RestrictionStatus Status="Open" Restriction="Arrival"/>
      <RestrictionStatus Status="Open" Restriction="Departure"/>
    </AvailStatusMessage>
  </AvailStatusMessages>
</OTA_HotelAvailNotifRQ>
```

### 9.5 שגיאות נפוצות

```xml
<!-- מוצר לא נמצא -->
<Error Type="12" Code="402">
  Can not find product for availability update (HotelCode/InvTypeCode/RatePlanCode)
</Error>

<!-- הפתרון: לוודא שהקודים ב-ratebycat תואמים למה שב-Noovy -->
```

---

## 10. פתרון בעיות נפוצות

### בעיה: "Completed; Api: 16; Map: 0; Miss: 16"

**סיבה:** אין שורות ב-Med_Hotels_ratebycat למלון

**פתרון:**
```sql
-- בדיקה
SELECT * FROM Med_Hotels_ratebycat WHERE HotelId = 20702;

-- אם ריק, הוסף מיפויים:
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode)
VALUES (20702, 1, 1, '12045', 'STD');
```

---

### בעיה: מלון לא מופיע בסריקה בכלל

**סיבה:** `Innstant_ZenithId = 0` או `isActive = 0`

**פתרון:**
```sql
-- בדיקה
SELECT HotelId, Name, Innstant_ZenithId, isActive FROM Med_Hotels WHERE HotelId = 20702;

-- תיקון
UPDATE Med_Hotels SET Innstant_ZenithId = '5110', isActive = 1 WHERE HotelId = 20702;
```

---

### בעיה: Push ל-Zenith מחזיר Error 402

**סיבה:** ה-RatePlanCode או InvTypeCode לא תואמים למה שב-Noovy

**פתרון:**
1. הרץ `scripts/export_noovy_venue_products.js` — ראה מה באמת קיים ב-Noovy
2. השווה את ה-pmsCode עם ה-InvTypeCode בטבלה
3. עדכן את הטבלה בהתאם

---

### בעיה: Noovy מחזיר HTTP 500 ביצירת מוצר

**סיבה:** venue לא מוגדר, או שדה חובה חסר

**פתרון:**
1. הרץ `scripts/hoteltools_creation_diagnostics.js` — ראה מה בדיוק נכשל
2. ודא שה-Venue קיים ופעיל ב-Noovy
3. ודא שכל שדות החובה מסופקים (venueId, name, shortName, productType, basePrice, baseCurrency, status)

---

### בעיה: Innstant לא מציג חדרים למלון

**סיבות אפשריות:**
1. אין availability פתוח לתאריך הנבחר
2. ה-Rate Plan סגור (stop-sell)
3. ספקים לא חוזרים עם תוצאות
4. המלון לא ממופה נכון ב-Innstant

**פתרון:**
1. הרץ `scripts/validate_innstant_inventory.js` — ראה מה Innstant מחזיר
2. בדוק ב-Hotel.Tools → Rates → Bulk Update שהזמינות פתוחה
3. בדוק תאריך אחר

---

### בעיה: מוצר RO חסר

**פתרון אוטומטי:**
```bash
npx playwright test scripts/add_room_only_mealplan.js
```

---

## 11. נספח: רשימת מלונות מיאמי

### Venues מוגדרים (מרץ 2026)

| VenueId | HotelId | שם מלון | סטטוס |
|---------|---------|---------|--------|
| 2766 | 66814 | Breakwater South Beach | ✅ Reference |
| 5077 | - | SLS Lux Brickell | ✅ Reference |
| 5110 | - | Reference Venue | ✅ Reference |
| 5064 | - | Target Batch 1 | 🔄 |
| 5075 | - | Target Batch 1 | 🔄 |
| 5082 | - | DoubleTree Hilton Miami Doral | 🔄 |
| 5083 | - | Target Batch 1 | 🔄 |
| 5113 | - | Cavalier Hotel | 🔄 |
| 5115 | - | Target Batch 2 | 🔄 |
| 5116 | - | Target Batch 2 | 🔄 |
| 5117 | - | Target Batch 2 | 🔄 |
| 5119 | - | citizenM Miami South Beach | 🔄 |
| 5124 | - | Target Batch 2 | 🔄 |
| 5130 | - | Holiday Inn Express | 🔄 |
| 5131 | - | Target Batch 2 | 🔄 |
| 5132 | - | Target Batch 2 | 🔄 |
| 5136 | - | Target Batch 2 | 🔄 |
| 5138 | - | Target Batch 2 | 🔄 |
| 5139 | - | Target Batch 2 | 🔄 |
| 5140 | - | Target Batch 2 | 🔄 |
| 5141 | - | Target Batch 2 | 🔄 |
| 5266 | 6654 | Dorchester Hotel | 🔄 |
| 5268 | 19977 | Fontainebleau Miami Beach | 🔄 |
| 5274 | 701659 | Generator Miami | 🔄 |
| 5279 | 301640 | Hilton Garden Inn | 🔄 |

### 59 מלונות מיאמי ב-Pipeline

כולל: Atwell Suites, citizenM South Beach, Crystal Beach Suites, Dream South Beach, Embassy Suites, Hilton Downtown, ועוד 53 מלונות נוספים.

### סטטוס כללי (מרץ 2026)

| קטגוריה | כמות | מצב |
|---------|-------|------|
| A. פעיל לחלוטין | 11 | כל 4 שכבות מוגדרות |
| B. Push עצור | 14 | שכבות 1-3 OK, שכבה 4 לא פעילה |
| C. ממופה אבל חלקי | 2 | שכבות 1-3 OK, מעולם לא היה שכבה 4 |
| D. לא מוגדר | 31 | חסר שכבה 1 (Noovy) |
| E. בעיה | 1 | 2 InnstantIds → אותו VenueID |

---

## סיכום: הזרימה המלאה

```
                     ┌──────────────┐
                     │  התחלה       │
                     └──────┬───────┘
                            │
                    ┌───────▼────────┐
      שכבה 1       │  Hotel.Tools   │  יצירת מוצרים
                    │  / Noovy       │  (חדרים + ארוחות)
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
      שכבה 2       │  Med_Hotels    │  הגדרת VenueId
                    │  DB Update     │  + isActive=1
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
      שכבה 3       │  ratebycat     │  מיפוי Board+Category
                    │  DB Insert     │  → RatePlanCode+InvTypeCode
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
      אימות        │  Innstant      │  בדיקה שהחדרים
                    │  Validation    │  מופיעים בחיפוש
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
      שכבה 4       │  SalesOffice   │  הפעלת סריקה
                    │  Order         │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  WebJob Scan   │  → Details → Push
                    │  (אוטומטי)    │  → Zenith → Live!
                    └────────────────┘
```

---

> **הערה:** מדריך זה מבוסס על עבודה שבוצעה בפועל על 59 מלונות מיאמי במרץ 2026.
> כל הסקריפטים, ה-GraphQL queries, וה-SOAP XML נבדקו ועבדו בייצור.
