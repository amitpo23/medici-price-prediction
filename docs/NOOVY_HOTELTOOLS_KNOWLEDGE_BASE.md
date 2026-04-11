# מרכז ידע — Noovy & Hotel.Tools

> **מסמך אחיד ומעודכן** — מאחד את כל הידע שנצבר ממאות סקריפטים, 7 מסמכים קודמים, ו-15 סקריפטי חקירה.
> **עדכון אחרון:** אפריל 2026

---

## תוכן עניינים

1. [ארכיטקטורת המערכת](#1-ארכיטקטורת-המערכת)
2. [פרטי התחברות](#2-פרטי-התחברות)
3. [Noovy — ניהול מוצרים ותעריפים](#3-noovy--ניהול-מוצרים-ותעריפים)
4. [GraphQL API של Noovy](#4-graphql-api-של-noovy)
5. [Hotel.Tools / Zenith SOAP API](#5-hoteltools--zenith-soap-api)
6. [Innstant B2B — אימות](#6-innstant-b2b--אימות)
7. [Azure SQL — טבלאות קריטיות](#7-azure-sql--טבלאות-קריטיות)
8. [Playwright — אוטומציה](#8-playwright--אוטומציה)
9. [סקריפטים — רפרנס](#9-סקריפטים--רפרנס)
10. [תהליכי עבודה (Workflows)](#10-תהליכי-עבודה-workflows)
11. [פתרון בעיות](#11-פתרון-בעיות)
12. [ממצאי חקירת Knowaa](#12-ממצאי-חקירת-knowaa)
13. [רישום מלונות מיאמי](#13-רישום-מלונות-מיאמי)

---

## 1. ארכיטקטורת המערכת

### זרימת הנתונים — 4 שכבות

```
שכבה 1: Noovy / Hotel.Tools         ← מוצרים, תעריפים, זמינות
    ↓ (Zenith SOAP sync)
שכבה 2: Med_Hotels                   ← ZenithId + isActive
    ↓
שכבה 3: Med_Hotels_ratebycat         ← Board + Category → RatePlanCode + InvTypeCode
    ↓
שכבה 4: SalesOffice.Orders           ← סריקה פעילה (WebJob כל 5 דקות)
```

### מה כל שכבה עושה

| שכבה | מערכת | תפקיד | מי מגדיר |
|-------|-------|--------|----------|
| 1 | Noovy / Hotel.Tools | Products, Rate Plans, Pricing, Availability | אנחנו (ידנית או סקריפט) |
| 2 | Azure SQL — `Med_Hotels` | מיפוי Innstant HotelId ↔ Zenith VenueId | צוות Innstant + אנחנו |
| 3 | Azure SQL — `Med_Hotels_ratebycat` | Board+Category → RatePlanCode+InvTypeCode | אנחנו (INSERT ל-DB) |
| 4 | Azure SQL — `SalesOffice.Orders` | הזמנות סריקה פעילות | WebJob אוטומטי |

### הפונקציה הקריטית: FindPushRatePlanCode

```csharp
// EFModel/BaseEF.cs שורה 3026
// אם אין שורה ב-Med_Hotels_ratebycat — החדר נדלג!
async Task<(string?, string?)> FindPushRatePlanCode(int hotelId, int boardId, int categoryId)
{
    var result = await ctx.MedHotelsRatebycats
        .FirstOrDefaultAsync(i => i.HotelId == hotelId &&
                                  i.BoardId == boardId &&
                                  i.CategoryId == categoryId);
    if (result != null)
        return (result.RatePlanCode, result.InvTypeCode);  // ✅ Push יתבצע
    else
        return (null, null);  // ❌ ChIP נדלג!
}
```

### תהליך סריקת WebJob

```
WebJob (כל 5 דקות) → מרים הזמנה מ-SalesOffice.Orders
    → חיפוש ב-Innstant API (adults:2, children:[])
    → סינון: רק מלונות עם Innstant_ZenithId > 0 AND isActive = 1
    → לכל חדר: FindPushRatePlanCode(hotelId, boardId, categoryId)
        ├→ נמצא → כותב ל-SalesOffice.Details + Zenith Push
        └→ לא נמצא → דילוג
    → עדכון WebJobStatus: "Completed; Api: 16; Flat: 5; Map: 4; Miss: 1"
```

---

## 2. פרטי התחברות

### Noovy PMS

| שדה | ערך | משתנה סביבה |
|------|------|------------|
| כתובת | `https://app.noovy.com` | — |
| דף כניסה | `https://app.noovy.com/bookings` | — |
| Account Name | `Medici LIVE` | `NOOVY_ACCOUNT_NAME` |
| Username | `zvi` | `NOOVY_USERNAME` |
| Password | `karpad66` | `NOOVY_PASSWORD` |

**Auth**: Cookie-based. אחרי login, ה-token נשמר ב-cookies ומשרת גם את GraphQL.

### Hotel.Tools / Zenith Channel Manager

| שדה | ערך |
|------|------|
| כתובת | `https://hotel.tools` |
| Login | אותם credentials כמו Noovy (Medici LIVE / zvi / karpad66) |
| SOAP API URL | `https://hotel.tools/service/Medici%20new` |
| WSSE Username | `APIMedici:Medici Live` |
| WSSE Password | `12345` |

> ⚠️ **הערה**: בחלק מהמסמכים הישנים WSSE Password מופיע כ-`Medici Live`. הערך `12345` אומת כעובד בסקריפטים.

### B2B Innstant

| שדה | ערך | משתנה סביבה |
|------|------|------------|
| כתובת | `https://b2b.innstant.travel/agent/login` | — |
| Account Name | `Knowaa` | `INNSTANT_ACCOUNT_NAME` |
| Username | `Amit` | `INNSTANT_USERNAME` |
| Password | `porat10` | `INNSTANT_PASSWORD` |

### Azure SQL (Production — READ ONLY!)

| שדה | ערך |
|------|------|
| Server | `medici-sql-server.database.windows.net` |
| Database | `medici-db` |
| Driver | pyodbc + SQLAlchemy |

---

## 3. Noovy — ניהול מוצרים ותעריפים

### 3.1 מהו מוצר (Product)?

מוצר = יחידה שמייצגת חדר או תוכנית ארוחות:
- **חדר** (`room`): Standard, Deluxe, Superior, Suite
- **תוכנית ארוחות** (`meal_plan`): RO (Room Only), BB (Bed & Breakfast), HB, FB, AI

**כל Venue (מלון) צריך לפחות:**
- 1 מוצר חדר (Standard)
- 1-2 Rate Plans (RO, BB)
- מחירים > $0 לתאריכים עתידיים
- Availability ≥ 1

### 3.2 יצירה ידנית דרך UI

**נתיב:** Hotel.Tools → Products → + New Product

**טופס — 3 טאבים:**

#### טאב 1: General

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

#### טאב 2: Locations

- Country → `US`
- Venue → לפי VenueId
- **חובה ללחוץ Save Location!**

#### טאב 3: Description

- אופציונלי — תיאור רב-שפתי

### 3.3 Bulk Update — הכלי החשוב ביותר

**נתיב:** Rates (sidebar) → Bulk Update

**שלבים:**
1. בחר מלון ב-sidebar dropdown (Hotel)
2. לחץ **Rates** → **Bulk Update**
3. ROOMS → Open → Select All → Close
4. RATE PLANS → Open → Select All → Close
5. DATE RANGE → בחר תאריך התחלה → navigate חודשים → תאריך סיום
6. RATE UPDATE → Fixed → סכום (למשל $5000)
7. AVAILABILITY UPDATE → Fixed → 1
8. Save → "Bulk update product successfully"

**אפשרויות Availability:**

| אפשרות | שימוש |
|---------|-------|
| Fixed | מספר חדרים קבוע (1 = חדר אחד פתוח) |
| Variable | שינוי יחסי (+/- מהקיים) |
| No Availability | סגירה מלאה (0) |
| Close Sale | סגירת מכירות |
| Open Sale | פתיחת מכירות |

### 3.4 Rate Plans — תיקון Products חסרים

**מתי:** כש-Rate Plan מחובר רק לחלק מהחדרים (BB מציג פחות חדרים מ-RO)

**איך:**
1. Rate Plans page → כפתור ⋮ (תפריט) בשורת ה-Rate Plan
2. Dialog "Edit Rate Plan" נפתח
3. גלול ל-**Products** → Open → בחר חדרים חסרים → Save
4. אישור: "Rate Plan changed"

### 3.5 בחירת מלון — MUI Autocomplete dropdown

**ה-dropdown נמצא בתחתית ה-sidebar:**
- `role="combobox"`, `name='Hotel'`
- מכיל **723 מלונות** (כל חשבון Medici LIVE)
- **GOTCHA:** `MuiTooltip-tooltip` עלול לחסום clicks

**Workaround לבעיית Tooltip:**
```javascript
// הסתרת tooltips והפעלה ישירה
await page.evaluate(() => {
  document.querySelectorAll('.MuiTooltip-tooltip').forEach(t => t.style.display = 'none');
});
await page.evaluate(() => {
  const option = document.querySelector('[data-option-index="0"]');
  option?.click();
});
```

---

## 4. GraphQL API של Noovy

### 4.1 Endpoint

```
URL: https://app.noovy.com/graphql/api
Method: POST
Content-Type: application/json
```

### 4.2 אימות

**אפשרות 1: Cookie-based (מתוך Playwright — הדפדפן שולח cookies אוטומטית)**
```javascript
const response = await page.evaluate(async (query) => {
  const res = await fetch('/graphql/api', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  return res.json();
}, gqlQuery);
```

**אפשרות 2: Header-based**
```javascript
const response = await fetch('https://app.noovy.com/graphql/api', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'authorization': `token ${authToken}`
  },
  body: JSON.stringify({ query })
});
```

### 4.3 שדות שאומתו (Valid Fields)

| אובייקט | שדות |
|---------|-------|
| **Venue** | `name, id, connectedToSupplier, supplierRatePlan, localCurrency, active, type, phone, accountId` |
| **Product** | `name, productId, status, maxOccupancy, pmsCode, mealPlanType, shortName, venueId, basePrice, agentId, affectedBy, accountId` |
| **RatePlan** | `name, active, id, ratePlanOrderId, currency, venueId, shortName, affectedBy, isDefault, mealPlan{...}` |

### 4.4 סינטקס שליפה — שימו לב להבדלים!

```graphql
# Rate Plans — משתמש ב-filtering עם string
{
  rateplan_list(filtering: { venueId: "5113" }) {
    name active id isDefault
  }
}

# Products — משתמש ב-where עם int
{
  product_list(where: { venueId: { _equals: 5113 } }) {
    name productId status pmsCode shortName
  }
}

# Venues מורשים
{
  allowedVenues { venueId name }
}
```

### 4.5 Mutations — יצירת מוצר

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
    locations: [{            # ← חובה! בלי זה, היצירה נכשלת
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

> ⚡ **פריצת דרך חשובה:** ה-`locations` array הוא שדה חובה ביצירת מוצר. בלעדיו, ה-mutation מחזיר 500. זה לא מתועד ב-schema.

### 4.6 Input Type מלא (מ-Introspection)

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
  locations: [entityLocationInput]  # ← חובה בפועל!
  images: [String]
  metaObjects: [String]
}

input entityLocationInput {
  venueId: Int!
  countryCode: String!  # "US"
}
```

### 4.7 Introspection

```graphql
# שליפת כל ה-schema
{ __schema { types { name fields { name type { name kind } } } } }

# שליפת Input Type ספציפי
{ __type(name: "productInputParameters") { inputFields { name type { name kind ofType { name } } } } }
```

---

## 5. Hotel.Tools / Zenith SOAP API

### 5.1 פרטי חיבור

```
URL:      https://hotel.tools/service/Medici%20new
WSSE:     APIMedici:Medici Live / 12345
Protocol: SOAP 1.1 / XML
```

### 5.2 פעולות נתמכות

| פעולה | סטטוס | שימוש |
|-------|--------|-------|
| `OTA_HotelAvailRQ` | ✅ | שליפת מוצרים + זמינות של מלון |
| `OTA_HotelRateAmountNotifRQ` | ✅ | דחיפת מחירים |
| `OTA_HotelAvailNotifRQ` | ✅ | דחיפת זמינות + הגבלות |
| `OTA_HotelResNotifRQ` | ✅ | קבלת הזמנות (callback) |
| `OTA_HotelDescriptiveInfoRQ` | ❌ | לא נתמך |
| `OTA_ReadRQ` | ❌ | לא נתמך |

### 5.3 דחיפת מחיר

```xml
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
  <SOAP-ENV:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>APIMedici:Medici Live</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">12345</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" Version="1.0">
      <RateAmountMessages HotelCode="{venueId}">
        <RateAmountMessage>
          <StatusApplicationControl
            InvTypeCode="{STD|DLX|SUI|SUP}"
            RatePlanCode="{ratePlanCode}"
            Start="{YYYY-MM-DD}"
            End="{YYYY-MM-DD}"/>
          <Rates>
            <Rate>
              <BaseByGuestAmts>
                <BaseByGuestAmt AgeQualifyingCode="10" AmountAfterTax="{price}"/>
                <BaseByGuestAmt AgeQualifyingCode="8" AmountAfterTax="{price}"/>
              </BaseByGuestAmts>
            </Rate>
          </Rates>
        </RateAmountMessage>
      </RateAmountMessages>
    </OTA_HotelRateAmountNotifRQ>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

### 5.4 דחיפת זמינות

```xml
<OTA_HotelAvailNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" Version="1.0">
  <AvailStatusMessages HotelCode="{venueId}">
    <AvailStatusMessage>
      <StatusApplicationControl
        InvTypeCode="{STD|DLX|SUI|SUP}"
        RatePlanCode="{ratePlanCode}"
        Start="{YYYY-MM-DD}"
        End="{YYYY-MM-DD}"/>
      <LengthsOfStay>
        <LengthOfStay MinMaxMessageType="SetMinLOS" Time="1"/>
        <LengthOfStay MinMaxMessageType="SetMaxLOS" Time="30"/>
      </LengthsOfStay>
      <RestrictionStatus Status="Open" Restriction="Arrival"/>
      <RestrictionStatus Status="Open" Restriction="Departure"/>
      <BookingLimit>{count}</BookingLimit>
    </AvailStatusMessage>
  </AvailStatusMessages>
</OTA_HotelAvailNotifRQ>
```

### 5.5 שגיאות נפוצות

| Code | Message | סיבה | פתרון |
|------|---------|------|--------|
| 402 | Can not find product | HotelCode/InvTypeCode/RatePlanCode שגוי | ודא קודים תואמים ל-Noovy |
| 500 | Something went wrong | בעיית הרשאות / מוצר חסר | בדוק product קיים ב-Noovy |

### 5.6 Python Implementation

```python
# src/utils/zenith_push.py
import requests

ZENITH_URL = "https://hotel.tools/service/Medici%20new"
ZENITH_USERNAME = "APIMedici:Medici Live"
ZENITH_PASSWORD = "12345"

def push_rate_to_zenith(hotel_code, inv_type_code, rate_plan_code, start, end, amount):
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

---

## 6. Innstant B2B — אימות

### 6.1 חיפוש מלון

```
https://b2b.innstant.travel/hotel/{slug}-{hotelId}
  ?service=hotels
  &searchQuery=hotel-{hotelId}
  &startDate={YYYY-MM-DD}
  &endDate={YYYY-MM-DD}
  &account-country=US
  &onRequest=0
  &payAtTheHotel=1
  &adults=2
  &children=
```

**דוגמה:**
```
https://b2b.innstant.travel/hotel/embassy-suites-by-hilton-miami-international-airport-20702
  ?service=hotels&searchQuery=hotel-20702&startDate=2026-06-15&endDate=2026-06-16
  &account-country=US&onRequest=0&payAtTheHotel=1&adults=2&children=
```

### 6.2 סינון ספקים בתוצאות

| ספק | מקור | כמות טיפוסית |
|------|------|-------------|
| **InnstantTravel** | Innstant עצמם | 20-29 מ-30 |
| **goglobal** | GoGlobal aggregator | 2-10 |
| **Knowaa_Global_zenith** | הערוץ שלנו | 0-5 (כשעובד) |

### 6.3 ממצא קריטי: Pax Configuration

ה-SalesOffice WebJob **תמיד** מחפש עם `adults:2, children:[]`. הוא אף פעם לא שולח single/triple/family.

| מלון | 1 Adult | 2 Adults |
|------|---------|----------|
| Pullman | Knowaa ✅ 2 | Knowaa ❌ 0 |
| SLS LUX | ❌ 0 | Knowaa ✅ 5 |
| citizenM Brickell | Knowaa ✅ 1 | Knowaa ✅ 2 |
| Embassy Suites | Knowaa ✅ 3 | Knowaa ✅ 3 |

---

## 7. Azure SQL — טבלאות קריטיות

### 7.1 Med_Hotels

```sql
-- מלון חייב Innstant_ZenithId > 0 ו-isActive = 1 כדי להיסרק
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels WHERE Innstant_ZenithId > 0;
```

### 7.2 Med_Hotels_ratebycat — הלב של המערכת

```sql
CREATE TABLE Med_Hotels_ratebycat (
    Id           INT PRIMARY KEY IDENTITY,
    HotelId      INT NOT NULL,      -- FK ל-Med_Hotels
    BoardId      INT NOT NULL,      -- 1=RO, 2=BB, 3=HB, 4=FB, 5=AI
    CategoryId   INT NOT NULL,      -- 1=Standard, 2=Superior, 4=Deluxe, 12=Suite
    RatePlanCode VARCHAR(50),       -- קוד Rate Plan ב-Zenith/Noovy
    InvTypeCode  VARCHAR(50)        -- קוד סוג חדר ב-Zenith/Noovy
);
```

**בלי שורה בטבלה הזו — החדר יידלג לחלוטין!**

### 7.3 קודי Board (ארוחות)

| BoardId | קוד | שם |
|---------|------|------|
| 1 | RO | Room Only |
| 2 | BB | Bed & Breakfast |
| 3 | HB | Half Board |
| 4 | FB | Full Board |
| 5 | AI | All Inclusive |

### 7.4 קודי Category (קטגוריות חדרים)

| CategoryId | שם | InvTypeCode |
|-----------|------|-------------|
| 1 | Standard | STD / Stnd |
| 2 | Superior | SPR / SUP |
| 4 | Deluxe | DLX |
| 12 | Suite | Suite / SUI |

### 7.5 דוגמת מיפוי מלאה — Embassy Suites (HotelId=20702)

```sql
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES
(20702, 1, 1,  '12045', 'STD'),   -- RO + Standard
(20702, 1, 12, '12045', 'SUI'),   -- RO + Suite
(20702, 2, 1,  '13164', 'Stnd'),  -- BB + Standard
(20702, 2, 12, '13164', 'Suite'); -- BB + Suite
```

### 7.6 שאילתות שימושיות

```sql
-- בדיקת מלונות עם סריקות פעילות
SELECT o.DestinationId, COUNT(*) as orders, MAX(o.DateInsert) as last_order
FROM [SalesOffice.Orders] o WHERE o.IsActive = 1
GROUP BY o.DestinationId ORDER BY last_order DESC;

-- בדיקת מיפויים למלון ספציפי
SELECT r.HotelId, r.BoardId, r.CategoryId, r.RatePlanCode, r.InvTypeCode
FROM Med_Hotels_ratebycat r WHERE r.HotelId = 20702;

-- חיפוש ספק Knowaa בלוגים
SELECT PaxAdults, RoomBedding, COUNT(*) as cnt
FROM SearchResultsSessionPollLog
WHERE Providers LIKE '%Knowaa_Global_zenith%'
GROUP BY PaxAdults, RoomBedding;
```

---

## 8. Playwright — אוטומציה

### 8.1 הגדרות

**Config file:** `playwright.ops.config.ts`

```javascript
// הרצת סקריפט
npx playwright test scripts/<scriptname>.js --config=playwright.ops.config.ts

// הגדרות עיקריות:
// testMatch: scripts/**/*.js
// browser: chromium (headless)
// timeout: 600,000ms (10 דקות)
```

### 8.2 Login Template — Noovy

```javascript
const { test, expect } = require('@playwright/test');

test('noovy operation', async ({ page }) => {
  // Login
  await page.goto('https://app.noovy.com/bookings');
  await page.getByRole('textbox', { name: /account/i }).fill('Medici LIVE');
  await page.getByRole('textbox', { name: /agent|user/i }).fill('zvi');
  await page.getByRole('textbox', { name: /password/i }).fill('karpad66');
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForURL('**/bookings**', { timeout: 15000 });

  // שליפת token (אם צריך)
  const cookies = await page.context().cookies();
  const tokenCookie = cookies.find(c => c.name === 'token');

  // GraphQL מתוך הדפדפן
  const data = await page.evaluate(async () => {
    const res = await fetch('/graphql/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `{ allowedVenues { venueId name } }`
      })
    });
    return res.json();
  });
});
```

### 8.3 Login Template — Innstant

```javascript
await page.goto('https://b2b.innstant.travel/agent/login');
await page.fill('#AccountName', 'Knowaa');
await page.fill('#Username', 'Amit');
await page.fill('#Password', 'porat10');
await page.click('button[type="submit"]');
await page.waitForTimeout(4000); // חשוב — login processing
```

### 8.4 בחירת מלון ב-UI (MUI Autocomplete)

```javascript
// פתיחת ה-dropdown
const hotelCombo = page.getByRole('combobox', { name: 'Hotel' });
await hotelCombo.click();
await hotelCombo.fill('Cavalier');
await page.waitForTimeout(500);

// Workaround: tooltips חוסמים clicks
await page.evaluate(() => {
  document.querySelectorAll('.MuiTooltip-tooltip, .MuiTooltip-popper')
    .forEach(el => el.style.display = 'none');
});

// בחירה מהרשימה
const option = page.getByRole('option', { name: /Cavalier/i });
await option.click();
await page.waitForTimeout(2000); // טעינת dashboard
```

---

## 9. סקריפטים — רפרנס

### 9.1 סקריפטי ייצור (Production)

| סקריפט | תיאור | הרצה |
|--------|--------|------|
| `apply_noovy_reference_clone.js` | שכפול מוצרים מ-Venue מייחס ליעדים | DRY_RUN ברירת מחדל, `--apply` לביצוע |
| `add_room_only_mealplan.js` | הוספת RO חסר | בודק ויוצר RO בכל venue חסר |
| `export_noovy_venue_products.js` | ייצוא מוצרים ל-JSON | שימוש לבדיקה |
| `noovy_reference_gap_dryrun.js` | ניתוח פערים | משווה Reference ליעדים |
| `capture_noovy_create_payload.js` | לכידת GraphQL payload | Debug |
| `compare_innstant_hoteltools_inventory.js` | השוואה 3-צדדית | Innstant ↔ HT ↔ DB |
| `validate_innstant_inventory.js` | אימות inventory ב-Innstant | Pass/Fail per hotel |
| `hoteltools_creation_diagnostics.js` | דיאגנוסטיקה | מאבחן כשלי יצירה |

### 9.2 סקריפטי חקירה (tmp_ files) — מפתח

**הכי חשובים:**

| סקריפט | מה גילה |
|--------|---------|
| `tmp_ui_roomtype_v15.js` | **Marketplace זהה 100% לכל המלונות** — ruled out |
| `tmp_ui_roomtype_v9.js` | **כל שדות GQL + Rate Plan comparison ל-28 מלונות** |
| `tmp_noovy_create_v25.js` (בקירוב) | **פריצת דרך `locations` array ביצירת מוצר** |
| `tmp_noovy_introspection_fetch_noauth.js` | Schema מלא ללא auth |
| `tmp_ui_roomtype_v6-v8.js` | Venue Edit UI — אין טאבים נוספים |

### 9.3 דוחות

הדוחות נשמרים ב-`data/reports/` עם timestamp:
```
noovy_clone_batch1_*.json
noovy_products_venue_*_*.json
noovy_reference_gap_dryrun_*.json
inventory_compare_innstant_hoteltools_*.json
innstant_inventory_validation_*.json
```

---

## 10. תהליכי עבודה (Workflows)

### 10.1 הוספת מלון חדש — צ'קליסט 7 שלבים

- [ ] **1. Venue קיים?** בדוק ב-Noovy GraphQL: `allowedVenues`
- [ ] **2. connectedToSupplier?** בדוק: `venue { connectedToSupplier }` = true
- [ ] **3. Products?** בדוק: לפחות Standard Room + Board
- [ ] **4. Rate Plans?** בדוק: לפחות RO, רצוי גם BB
- [ ] **5. Rate Plans מחוברים ל-Products?** Rate Plans page → עמודת Products
- [ ] **6. Pricing > $0?** Rates → Calendar → ודא מחירים לתאריכים עתידיים
- [ ] **7. Availability ≥ 1?** Rates → Calendar → ודא availability פתוח

**אם חסר שלב, תקן ברצף מ-1 עד 7.**

### 10.2 הקמת מלון חדש מלאה — 5 שלבים

**שלב א: יצירת Products**
1. Settings → Products → New → Room: Standard, Deluxe, Suite, Superior
2. לכל Product: Base Price=100, Currency=USD, Status=Active

**שלב ב: יצירת Rate Plans**
1. Rate Plans page → New Rate Plan
2. שם: "Room Only" / "Bed and Breakfast"
3. חבר את כל ה-Products

**שלב ג: הפעלת Rate Plans**
1. לכל Rate Plan → Status: Enable

**שלב ד: מיפוי ב-DB**
```sql
-- עדכון Med_Hotels
UPDATE Med_Hotels SET Innstant_ZenithId = '{venueId}', isActive = 1 WHERE HotelId = {hotelId};

-- הוספת מיפויי ratebycat
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES
({hotelId}, 1, 1, '{rateplanRO}', 'Stnd'),
({hotelId}, 2, 1, '{rateplanBB}', 'Stnd');
```

**שלב ה: Pricing + Availability**
1. Rates → Bulk Update
2. Rooms: Select All | Rate Plans: Select All
3. Date Range: היום → סוף השנה
4. Rate: Fixed $5000 | Availability: Fixed 1
5. Save

### 10.3 Reference Clone — שכפול אוטומטי

```bash
# DRY-RUN (ברירת מחדל — בטוח)
REFERENCE_VENUE=5110 TARGET_VENUES=5064,5082 \
npx playwright test scripts/apply_noovy_reference_clone.js

# APPLY (מבצע בפועל)
npx playwright test scripts/apply_noovy_reference_clone.js -- --apply
```

**מה עושה:**
1. מתחבר → שולף מוצרים מ-Reference Venue
2. לכל Target: משווה → יוצר חסרים → מאמת

### 10.4 שלושה-צדדית — האימות הכי חשוב

```bash
npx playwright test scripts/compare_innstant_hoteltools_inventory.js
```

**משווה בין 3 מערכות:**
```
Innstant (מה שהספקים מציעים)  ←→  Hotel.Tools (מה שהגדרנו)  ←→  Database (מה שצריך להיות)
```

---

## 11. פתרון בעיות

### בעיה: "Completed; Api: 16; Map: 0; Miss: 16"

**סיבה:** אין שורות ב-`Med_Hotels_ratebycat` למלון
```sql
SELECT * FROM Med_Hotels_ratebycat WHERE HotelId = {hotelId};
-- אם ריק → הוסף מיפויים
```

### בעיה: מלון לא מופיע בסריקה בכלל

**סיבה:** `Innstant_ZenithId = 0` או `isActive = 0`
```sql
SELECT HotelId, Name, Innstant_ZenithId, isActive FROM Med_Hotels WHERE HotelId = {hotelId};
-- תקן: UPDATE Med_Hotels SET Innstant_ZenithId = '{venueId}', isActive = 1 WHERE HotelId = {hotelId};
```

### בעיה: Push ל-Zenith מחזיר Error 402

**סיבה:** RatePlanCode/InvTypeCode לא תואמים ל-Noovy
1. הרץ `export_noovy_venue_products.js` — ראה מה באמת קיים
2. השווה pmsCode עם InvTypeCode בטבלה
3. עדכן הטבלה בהתאם

### בעיה: HTTP 500 ביצירת מוצר

**סיבה:** חסר שדה `locations` ב-mutation
```graphql
# חובה לכלול:
locations: [{ venueId: {venueId}, countryCode: "US" }]
```

### בעיה: Innstant לא מציג חדרים

1. הרץ `validate_innstant_inventory.js`
2. בדוק Bulk Update → availability פתוח
3. בדוק תאריך אחר

### בעיה: Rate Plan חסר Products

Rate Plans page → ⋮ → Edit → Products → Open → בחר חדרים → Save

---

## 12. ממצאי חקירת Knowaa

### מצב נוכחי: 17/55 (31%) — יעד 90%+

### מה נבדק (15 סקריפטים) ונשלל:

| נבדק | שיטה | תוצאה |
|------|------|-------|
| שדות Venue ב-GraphQL | v9 — 28 מלונות | **זהה** — כולם active, connectedToSupplier=true |
| שדות Product ב-GraphQL | v9 — כל השדות | **אין דפוס מבדיל** |
| Venue Edit UI | v6-v8 — צילומי מסך | **זהה**, אין טאבים נוספים |
| Marketplace — Channels & Services | v15 — 6 מלונות | **"No data"** — זהה |
| Marketplace — OTAs | v15 — 6 מלונות | **12 OTAs זהים**, כולם "Set Up" |
| Marketplace — Pricing & Upselling | v15 — 6 מלונות | **9 כלים** — זהה |

### **מסקנה: הבעיה לא ב-Noovy — היא ב-Hotel.Tools/Zenith**

### סיגנלים חלקיים שנמצאו:

**1. isDefault חסר (4 מלונות — 19% מ-Section C):**
- Fontainebleau (5268), Gale SB (5267), Generator (5274), InterContinental (5276)
- כולם עם isDefault=false בכל ה-Rate Plans

**2. שגיאות כתיב בשמות Rate Plan:**
- Dream SB (5090): "bed and brekfast" (צ"ל breakfast)
- DoubleTree (5082): "bed and brekfast"

### המלצות לפעולה:

1. **תיקון isDefault** ל-4 מלונות (סיכון נמוך, כיסוי 19%)
2. **אסקלציה ל-Hotel.Tools** — לשאול מה מבדיל working מ-non-working
3. **בדיקת Zenith SOAP** — האם יש mapping ספציפי supplier-side

---

## 13. רישום מלונות מיאמי

### Section A — עובדים ב-Knowaa #1 (10 מלונות) ✅

| VenueId | מלון |
|---------|-------|
| 5113 | Cavalier Hotel |
| 5120 | Cadet Hotel |
| 5129 | Crystal Beach |
| 5085 | Embassy Suites |
| 5127 | Eurostars Langford |
| 5081 | Hilton Airport |
| 5135 | Iberostar Berkeley Shore |
| 5078 | Kimpton Palomar |
| 5128 | Marseilles |
| 5123 | Villa Casa Casuarina |

### Section B — Knowaa מופיע #2-3 (5 מלונות) ✅

| VenueId | מלון |
|---------|-------|
| 5119 | citizenM South Beach |
| 5107 | Freehand |
| 5073 | Loews |
| 5109 | Riu Plaza |
| 5136 | Kimpton Anglers |

### Section C — לא עובדים, מתחרים כן (21 מלונות) ❌

| VenueId | מלון | הערות |
|---------|-------|--------|
| 5268 | Fontainebleau | isDefault=false (4 מלונות) |
| 5267 | Gale South Beach | isDefault=false |
| 5274 | Generator | isDefault=false |
| 5276 | InterContinental | isDefault=false |
| 5101 | Atwell Suites | |
| 5110 | Breakwater | Reference Venue |
| 5079 | citizenM Brickell | חסר BB ל-SPR/DLX/Suite |
| 5266 | Dorchester | |
| 5082 | DoubleTree | חסר SPR+DLX (RO+BB), שגיאת כתיב |
| 5090 | Dream South Beach | שגיאת כתיב: "brekfast" |
| 5278 | Gale Miami | |
| 5124 | Grand Beach | |
| 5106 | Hampton Inn | חסר BB לגמרי |
| 5093 | Hilton Bentley | |
| 5115 | Hilton Cabana | duplicates בProducts |
| 5279 | Hilton Garden Inn | |
| 5130 | Holiday Inn Express | |
| 5265 | Hotel Belleza | |
| 5131 | Hotel Croydon | |
| 5132 | Gaythering | |
| 5097 | Hyatt Centric | חסר BB ל-SPR |

### Section D — אין Refundable מאף ספק (12 מלונות)

| VenueId | מלון |
|---------|-------|
| 5089 | Fairwind |
| 5084 | Hilton Downtown |
| 5064 | Hotel Chelsea |
| 5105 | MB Hotel Wyndham |
| 5141 | Metropole |
| 5139 | SERENA Aventura |
| 5077 | SLS LUX |
| 5104 | Sole Miami |
| 5277 | Catalina |
| 5094 | Grayson |
| 5117 | Albion |
| 5140 | Gates South Beach |

### Innstant HotelId ↔ Zenith VenueId — מיפוי מלא

| HotelId | מלון | VenueId |
|---------|-------|---------|
| 66814 | Breakwater South Beach | 2766 |
| 853382 | Atwell Suites Miami Brickell | 5101 |
| 854881 | citizenM Miami Brickell | 5079 |
| 173508 | Cadet Hotel | 5120 |
| 64390 | Crystal Beach Suites | 5129 |
| 241025 | Dream South Beach | 5090 |
| 20702 | Embassy Suites | 5085 |
| 333502 | Eurostars Langford | 5127 |
| 117491 | Fairwind Hotel | 5089 |
| 6660 | Freehand Miami | 5107 |
| 22034 | Hilton Bentley | 5093 |
| 24982 | Hilton Miami Downtown | 5084 |
| 24989 | Hotel Riu Plaza | 5109 |
| 314212 | Hyatt Centric SB | 5097 |
| 383277 | Iberostar Berkeley Shore | 5135 |
| 6663 | Marseilles Hotel | 5128 |
| 852120 | SLS LUX Brickell | 5077 |
| 88282 | Sole Miami | 5104 |
| 6654 | Dorchester Hotel | 5266 |
| 19977 | Fontainebleau | 5268 |
| 701659 | Generator Miami | 5274 |
| 301640 | Hilton Garden Inn | 5279 |
| 6661 | Loews Miami Beach | 5073 |
| 193899 | Villa Casa Casuarina | 5123 |

---

## נספח: מסמכים ישנים שהוחלפו

מסמך זה מאחד ומחליף את המסמכים הבאים:
- `NOOVY_HOTELTOOLS_SETUP_GUIDE.md` — מדריך הקמה (2026-03-27)
- `NOOVY_OPERATIONS_PLAYBOOK.md` — Playbook תפעולי
- `NOOVY_OPERATIONS_GUIDE.md` — מדריך תפעולי
- `NOOVY_FIXES_NEEDED.md` — תיקונים נדרשים (2026-03-29)
- `NOOVY_5HOTEL_AUDIT_2026-03-29.md` — ביקורת 5 מלונות
- `KNOWAA_DIAGNOSTIC_REPORT_2026-04-01.md` — דוח אבחון Knowaa
- `KNOWAA_ACTION_PLAN.md` — תוכנית פעולה

**המסמכים הישנים נשמרים לצורך היסטוריה אבל מסמך זה הוא ה-source of truth.**
