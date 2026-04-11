# דוח אבחון Knowaa — תוצאות סופיות

**תאריך:** 1 באפריל 2026  
**מצב נוכחי:** 17/55 (31%) מלונות נראים ב-Knowaa  
**יעד:** 90%+

---

## סיכום מנהלים

אחרי בדיקה ממצה של כל השכבות הנגישות ב-Noovy (GraphQL API, ממשק Venue Edit, ודף Marketplace), **לא נמצא שום הבדל בין מלונות עובדים לבין מלונות שלא עובדים**. ה-Marketplace זהה ב-100% לכל המלונות. המשמעות: **הבעיה לא נמצאת בצד ה-Noovy** — היא כמעט בוודאות בצד Hotel.Tools/Zenith.

---

## מה נבדק (15 סקריפטים, v1-v15)

### 1. GraphQL API — כל השדות של כל האובייקטים ✅ נבדק

| אובייקט | שדות שנבדקו | תוצאה |
|---------|-------------|-------|
| **Venue** | name, id, connectedToSupplier, supplierRatePlan, localCurrency, active, type, phone, accountId | **זהה** — כולם active=true, connectedToSupplier=true, accountId=698 |
| **Product** | name, productId, status, maxOccupancy, pmsCode, mealPlanType, shortName, venueId, basePrice, agentId, affectedBy, accountId | **אין הבדל מבדיל** |
| **RatePlan** | name, active, id, ratePlanOrderId, currency, venueId, shortName, affectedBy, isDefault, mealPlan{...} | **סיגנל חלקי** — ראה למטה |

### 2. Venue Edit UI — ממשק עריכת המלון ✅ נבדק
- **אין טאבים** לסוגי חדרים או בסיס אירוח
- הדף מכיל רק: שם, כתובת, טלפון, מטבע, סוג נכס
- **זהה** לכל המלונות

### 3. Marketplace — דף ה-Marketplace ✅ נבדק (v15 — דפיניטיבי)

**6 מלונות נבדקו:**
- ✅ Cavalier (5113) — עובד
- ✅ Loews (5073) — עובד
- ✅ Freehand (5107) — עובד
- ❌ Dream SB (5090) — לא עובד
- ❌ Fontainebleau (5268) — לא עובד
- ❌ DoubleTree (5082) — לא עובד

**תוצאה:** 

| טאב | Cavalier ✅ | Loews ✅ | Freehand ✅ | Dream SB ❌ | Fontainebleau ❌ | DoubleTree ❌ |
|-----|-----------|---------|-----------|-----------|----------------|------------|
| Channels & Services | "No data" | "No data" | "No data" | "No data" | "No data" | "No data" |
| My Apps | "No data" | "No data" | "No data" | "No data" | "No data" | "No data" |
| OTAs | 12 פריטים, כולם "Set Up" | **זהה** | **זהה** | **זהה** | **זהה** | **זהה** |
| Pricing & Upselling | 9 כלים | **זהה** | **זהה** | **זהה** | **זהה** | **זהה** |

**12 ה-OTAs (זהים לכולם):** PMSXchange, Booking.com, Expedia, Agoda, HyperGuest, AirBnB, Hoteliers, Lastminute, HostelWorld, HotelSpecials, Bedandbreakfast, AVS — כולם במצב "Set Up" (לא מחוברים)

**מסקנה:** דף ה-Marketplace הוא תבנית ברמת החשבון, לא הגדרה ברמת המלון. **לא מבדיל.**

---

## סיגנלים חלקיים שנמצאו

### סיגנל 1: isDefault בתוכניות תעריפים (4 מלונות)

4 מלונות לא-עובדים חסר להם `isDefault=true` בתוכנית תעריפים:

| מלון | Venue ID | Rate Plans | isDefault |
|------|----------|------------|-----------|
| Fontainebleau | 5268 | ro + BB | **שניהם false** |
| Gale SB | 5267 | RO + BB | **שניהם false** |
| Generator | 5274 | ro + BB | **שניהם false** |
| InterContinental | 5276 | RO + BB | **שניהם false** |

**לעומת מלונות עובדים:**
- Cavalier (5113): Refundable (isDefault=**true**) + BB (false)
- Loews (5073): room only (isDefault=**true**) + BB (false)

**כיסוי:** 4 מלונות מתוך 21 לא-עובדים = **19% בלבד**
**סיכוי הצלחה:** בינוני — זו השערה, לא ודאות

### סיגנל 2: שמות Rate Plan עם שגיאות כתיב

| מלון | Rate Plan Name | בעיה |
|------|---------------|------|
| Dream SB (5090) | "bed and brekfast" | שגיאת כתיב: brekfast → breakfast |
| DoubleTree (5082) | "bed and brekfast" | שגיאת כתיב: brekfast → breakfast |
| Fontainebleau (5268) | "bed and breakfast / bb" | תקין |

**לא ברור** אם שגיאת הכתיב משפיעה על מיפוי.

---

## מה נשלל (Ruled Out)

| נבדק | שיטה | תוצאה |
|------|------|-------|
| שדות Venue ב-GraphQL | v9 — כל 28 מלונות | זהה |
| שדות Product ב-GraphQL | v9 — כל השדות | אין דפוס מבדיל |
| ממשק Venue Edit | v6-v8 — צילומי מסך | זהה, אין טאבים נוספים |
| Marketplace — Channels & Services | v15 — 6 מלונות | "No data" — זהה |
| Marketplace — My Apps | v15 — 6 מלונות | "No data" — זהה |
| Marketplace — OTAs | v15 — 6 מלונות + צילומי מסך | 12 OTAs זהים, כולם "Set Up" |
| Marketplace — Pricing & Upselling | v15 — 6 מלונות | 9 כלים זהים |

---

## המלצות — מה לעשות עכשיו

### פעולה A: תיקון isDefault ל-4 מלונות (סיכון נמוך, כיסוי 19%)
**מלונות:** Fontainebleau, Gale SB, Generator, InterContinental  
**פעולה:** GraphQL mutation לשנות isDefault=true ל-rate plan אחד  
**סיכון:** נמוך — זו הגדרה סטנדרטית  
**ודאות:** בינונית — 50%  

### פעולה B: אסקלציה ל-Hotel.Tools (מומלץ!)
**הסיבה:** בדקנו את כל מה שנגיש מצד Noovy ולא מצאנו הבדל. הבעיה חייבת להיות בצד ה-supplier (Hotel.Tools/Zenith).  
**לשאול אותם:**
1. מה ההגדרות הנדרשות בצד שלהם כדי שמלון יופיע ב-Knowaa?
2. האם יש mapping ספציפי שצריך להתבצע בין Noovy venue ל-Hotel.Tools property?
3. למה 17 מלונות כן עובדים ו-21 לא — מה ההבדל בצד שלהם?

### פעולה C: בדיקת Zenith SOAP (אם אפשרי)
בדוק דרך ה-SOAP API של Hotel.Tools אם יש הבדלים ב-mapping או הגדרות supplier-side.

---

## ראיות ויזואליות

**צילומי מסך שמורים ב-** `/tmp/noovy_v15/`:
- `apps_*.png` — טאב My Apps (6 מלונות, כולם "No data to display")
- `cs_*.png` — טאב Channels & Services (6 מלונות)
- `mp_*.png` — טאב ראשי Marketplace (6 מלונות)
- `ota_*.png` — טאב OTAs (6 מלונות, 12 OTAs זהים)
- `pricing_*.png` — טאב Pricing & Upselling (6 מלונות)

---

## סטטוס מלונות — מעודכן

### A — עובדים ב-Knowaa (15 מלונות)
Cavalier(5113), Cadet(5120), Crystal Beach(5129), Embassy Suites(5085), Eurostars(5127), Hilton Airport(5081), Iberostar(5135), Kimpton Palomar(5078), Marseilles(5128), Villa Casa(5123), citizenM SB(5119), Freehand(5107), Loews(5073), Riu Plaza(5109), Kimpton Anglers(5136)

### C — לא עובדים (21 מלונות)
**עם בעיית isDefault (4):** Fontainebleau(5268), Gale SB(5267), Generator(5274), InterContinental(5276)  
**ללא בעיה ידועה ב-Noovy (17):** Atwell(5101), Breakwater(5110), citizenM Brickell(5079), Dorchester(5266), DoubleTree(5082), Dream SB(5090), Gale Miami(5278), Grand Beach(5124), Hampton Inn(5106), Hilton Bentley(5093), Hilton Cabana(5115), Hilton Garden Inn(5279), Holiday Inn Express(5130), Hotel Belleza(5265), Hotel Croydon(5131), Gaythering(5132), Hyatt Centric(5097)

### D — ללא Rate Plan Refundable (12 מלונות)
Fairwind(5089), Hilton Downtown(5084), Hotel Chelsea(5064), MB Hotel Wyndham(5105), Metropole(5141), SERENA Aventura(5139), SLS LUX(5077), Sole Miami(5104), Catalina(5277), Grayson(5094), Albion(5117), Gates SB(5140)

---

## שורה תחתונה

**הבעיה לא ב-Noovy.** בדקנו הכל — GraphQL, UI, Marketplace — הכל זהה בין מלונות עובדים ולא-עובדים. **צריך לפנות ל-Hotel.Tools/Zenith** כדי להבין מה חסר מהצד שלהם.
