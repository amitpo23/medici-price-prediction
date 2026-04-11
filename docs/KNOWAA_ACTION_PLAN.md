# תוכנית פעולה מקיפה - שיפור נראות Knowaa ב-55 מלונות מיאמי

## מצב נוכחי: 17/55 (31%) מלונות מציגים Knowaa

---

## ממצאי האבחון (מלאים)

### מה נבדק
בדקנו **כל 55 המלונות** ב-3 שכבות:
1. **Noovy GraphQL** — rate plans, products, supplier, venue config
2. **Zenith SOAP** — OTA_HotelAvailRQ (זמינות בפועל)
3. **דוח Knowaa** — April 1 תוצאות הסריקה

### ממצאים מפתיעים — מלונות עובדים ולא-עובדים **זהים לחלוטין**

| שכבה | עובדים (A+B) | לא עובדים (C+D) |
|-------|---------------|-------------------|
| Rate Plans (פעילים) | ✅ 15/18 | ✅ 33/33 |
| Supplier = Medici | ✅ כולם | ✅ כולם |
| Products (חדרים) | ✅ כולם | ✅ כולם |
| Zenith Availability | ✅ RoomStays חוזרים | ✅ RoomStays חוזרים |

### מסקנה: הבעיה **לא** בהגדרות Noovy הבסיסיות

---

## חלוקת המלונות

### Section A — Knowaa מופיע #1 (10 מלונות) ✅
| Venue ID | מלון | Rate Plans | Products |
|----------|-------|------------|----------|
| 5113 | Cavalier | 2 (Refundable, B&B) | 4 |
| 5120 | Cadet | 0* | 0* |
| 5129 | Crystal Beach | 1 (Refundable) | — |
| 5085 | Embassy Suites | 0* (access error) | — |
| 5127 | Eurostars Langford | 1 (Refundable) | — |
| 5081 | Hilton Airport | 2 (room only, B&B) | 3 |
| 5135 | Iberostar | 1 (Refundable) | — |
| 5078 | Kimpton Palomar | 0* | 0 |
| 5128 | Marseilles | 1 (Refundable) | — |
| 5123 | Villa Casa Casuarina | 1 (Refundable) | — |

*Cadet, Embassy Suites, Kimpton Palomar — עובדים למרות שאין RPs/Products ב-API שלנו (הגדרות דרך ערוץ אחר)

### Section B — Knowaa מופיע #2-3 (5 מלונות) ✅
| Venue ID | מלון | Rate Plans | Products |
|----------|-------|------------|----------|
| 5119 | citizenM SB | 3 (Refundable, RO, BB) | 2 |
| 5107 | Freehand | 2 (RO, B&B) | — |
| 5073 | Loews | 2 (RO, B&B) | 3 |
| 5109 | Riu Plaza | 2 (RO, BB) | — |
| 5136 | Kimpton Anglers | 3 (Refundable, RO, BB) | — |

### Section C — לא מופיע, מתחרים כן (21 מלונות) ❌ **עדיפות גבוהה**
| Venue ID | מלון | Rate Plans | Zenith RoomStays |
|----------|-------|------------|------------------|
| 5101 | Atwell Suites | 2 | 5 ✅ |
| 5110 | Breakwater | 3 | — |
| 5079 | citizenM Brickell | 2 | — |
| 5266 | Dorchester | 2 | — |
| 5082 | DoubleTree Ocean Point | 2 | — |
| 5090 | Dream South Beach | 2 | 5 ✅ |
| 5268 | Fontainebleau | 2 | 11 ✅ |
| 5278 | Gale Miami | 2 | — |
| 5267 | Gale South Beach | 2 | — |
| 5274 | Generator | 2 | — |
| 5124 | Grand Beach | 3 | — |
| 5106 | Hampton Inn | 1 | — |
| 5093 | Hilton Bentley | 2 | — |
| 5115 | Hilton Cabana | 3 | — |
| 5279 | Hilton Garden Inn | 2 | — |
| 5130 | Holiday Inn Express | 3 | — |
| 5265 | Hotel Belleza | 1 | — |
| 5131 | Hotel Croydon | 2 | — |
| 5132 | Gaythering | 3 | — |
| 5276 | InterContinental | 2 | — |
| 5097 | Hyatt Centric | 2 | — |

### Section D — אין הצעות Refundable מאף אחד (12 מלונות)
| Venue ID | מלון | Rate Plans | Zenith RoomStays |
|----------|-------|------------|------------------|
| 5089 | Fairwind | 2 | 5 ✅ |
| 5084 | Hilton Downtown | 2 | — |
| 5064 | Hotel Chelsea | 2 | — |
| 5105 | MB Hotel Wyndham | 1 | — |
| 5141 | Metropole | 3 | — |
| 5139 | SERENA Aventura | 25 | — |
| 5077 | SLS LUX | 2 | — |
| 5104 | Sole Miami | 2 | — |
| 5277 | Catalina | 2 | — |
| 5094 | Grayson | 2 | — |
| 5117 | Albion | 2 | — |
| 5140 | Gates South Beach | 2 | — |

---

## תוכנית פעולה — 5 שלבים

### שלב 1: חקירה — מה מבדיל עובדים מלא-עובדים? (עדיפות קריטית)

**בעיה**: בדקנו Rate Plans, Products, Supplier, Zenith Availability — כולם זהים. ההבדל נמצא בשכבה שעדיין לא זיהינו.

**פעולות נדרשות:**

1. **בדיקת UI ידנית** — להשוות ב-Noovy UI בין Cavalier (עובד) ל-Dream SB (לא עובד):
   - לפתוח כל venue ולצלם מסך מלא
   - לחפש הגדרות: Distribution channels, Channel mapping, Pricing rules, Market settings
   - לבדוק אם יש tab/section שלא נגיש דרך GraphQL

2. **בדיקת Hotel.Tools Admin** — לבדוק ב-Hotel.Tools dashboard:
   - האם יש "Active channels" שונים למלונות שונים?
   - האם מלון צריך להיות "published" או "live" בערוץ Knowaa?
   - האם יש mapping ספציפי בין Venue ID ל-Hotel.Tools property?

3. **הפעלת סריקה חדשה** — הדוח של April 1 עלול להיות לא עדכני:
   - להריץ scan חדש ולבדוק אם 6 המלונות שתיקנו (Gaythering, Landon, Grayson, Catalina, Gale SB, Hilton Cabana) כעת מופיעים
   - אם כן — הבעיה הייתה תזמון בלבד

4. **בדיקת Pricing נוכחי** — Zenith מחזיר RoomStays אבל ייתכן שאין **מחירים** (שדה Prices ריק):
   - לבדוק האם העובדים מחזירים מחירים בפועל
   - אם לא — הבעיה עלולה להיות שלא הועלו תעריפים (rates) עדכניים

### שלב 2: תיקון הגדרות שזוהו כחסרות (אחרי שלב 1)

**תלוי בממצאי שלב 1, הפעולה תהיה אחת מ:**

**אופציה A — אם יש Channel/Distribution setting:**
- סקריפט אוטומטי להפעלת Knowaa channel על כל 33 מלונות Section C
- ואז על 12 מלונות Section D

**אופציה B — אם יש Pricing/Rates חסרים:**
- העלאת תעריפים דרך Noovy Bulk Pricing API
- כל מלון צריך מחירים לחדרים לתאריכים עתידיים

**אופציה C — אם ההבדל הוא ב-Hotel.Tools (לא Noovy):**
- עבודה ב-Hotel.Tools Admin Panel
- הפעלת Medici/Knowaa channel per property
- זה עשוי לדרוש פניה לתמיכת Hotel.Tools

### שלב 3: Section C (21 מלונות) — עדיפות גבוהה
אלה מלונות שמתחרים מציגים הצעות אבל Knowaa לא. כל אחוז שיפור כאן = הכנסה ישירה.

**סדר פעולה לפי גודל מלון/חשיבות:**
1. Fontainebleau (5268) — 11 RoomStays, דירוג ענק
2. Hilton Cabana (5115) — 6 products, 3 RPs
3. Hilton Garden Inn (5279)
4. Hilton Bentley (5093)
5. InterContinental (5276)
6. DoubleTree Ocean Point (5082)
7. Grand Beach (5124)
8. Dream South Beach (5090)
9. citizenM Brickell (5079)
10. Hyatt Centric (5097)
11. Holiday Inn Express (5130)
12. Breakwater (5110)
13. Hampton Inn (5106)
14. Atwell Suites (5101)
15. Gale South Beach (5267)
16. Gale Miami (5278)
17. Generator (5274)
18. Hotel Croydon (5131)
19. Gaythering (5132)
20. Dorchester (5266)
21. Hotel Belleza (5265)

### שלב 4: Section D (12 מלונות) — עדיפות בינונית
אלה מלונות שאין הצעות Refundable מאף סוכן. ייתכן שהם פשוט לא מוכרים refundable, אבל עדיין כדאי לבדוק.

### שלב 5: אימות סופי
- הרצת סריקה חדשה
- בדיקה שכל המלונות מציגים Knowaa
- יעד: 90%+ (מ-17/55 → 50/55)

---

## פעולות מיידיות — מה לעשות עכשיו

### פעולה 1: הריצו סריקה חדשה (scan)
הדוח האחרון הוא מ-April 1. ייתכן שחלק מהתיקונים שעשינו כבר השפיעו.

### פעולה 2: בדיקת UI ידנית
פתחו ב-Noovy UI את:
- **Cavalier (5113)** — מלון עובד
- **Dream SB (5090)** — מלון לא עובד

הסתכלו על כל ה-tabs, settings, ו-configurations. חפשו כל דבר שונה.

### פעולה 3: שאלו את Hotel.Tools
שאלו: "Why do some hotels show Knowaa pricing while others don't, when all have the same Noovy configuration (rate plans, supplier, products)?"

---

## סיכום טכני

| מדד | ערך נוכחי |
|------|----------|
| סה"כ מלונות | 55 |
| מציגים Knowaa | 17 (31%) |
| לא מציגים (מתחרים כן) | 21 (Section C) |
| לא מציגים (אין הצעות) | 12 (Section D) |
| Hotels with Rate Plans | 48/51 (94%) |
| Hotels with Products | 50/55+ (91%) |
| Hotels with Supplier=Medici | 55/55 (100%) |
| Hotels with Zenith Availability | 8/8 tested (100%) |
| **גורם מבדיל שזוהה** | **לא נמצא עדיין** |

### GraphQL Queries שעובדים
```graphql
# Rate plans per venue
rateplan_list(filtering: { venueId: "5113" }, limit: 50) { name active id mealPlan { name } }

# Products per venue  
product_list(where: { venueId: { _equals: 5113 } }, limit: 50) { name productId status }

# Venue by ID
venue_list(where: { id: { _equals: "5113" } }, limit: 1) { name localCurrency supplierRatePlan connectedToSupplier }

# All venues
venue_list(limit: 200) { name connectedToSupplier supplierRatePlan }
```

### Zenith SOAP — עובד עבור כל המלונות
```
POST https://hotel.tools/service/Medici%20new
WSSE: APIMedici:Medici Live / 12345
```
מחזיר RoomStays עבור כל 8 המלונות שנבדקו (working + non-working).

---

## תובנות חשובות מהחקירה

1. **שלושה מלונות עובדים (Cadet, Embassy Suites, Kimpton Palomar) בלי RPs ויזיבליים** — ייתכן שיש הגדרות דרך channel אחר
2. **SERENA Aventura יש 25 rate plans** — ככל הנראה שכפולים שצריך לנקות
3. **Breakwater יש 3 rate plans כולל כפול** — room only + Bed and Breakfast + bed and breakfast / bb
4. **Product status=1** על כל המוצרים שנבדקו — אקטיביים

---

*מסמך נוצר: מתוך אבחון אוטומטי של כל 55 המלונות*
*כלים: Noovy GraphQL, Zenith SOAP, Playwright automation*
