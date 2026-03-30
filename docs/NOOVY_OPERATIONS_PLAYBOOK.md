# Noovy Operations Playbook — מדריך עבודה

## גישה לנובי

| שדה | ערך |
|-----|-----|
| URL | https://app.noovy.com |
| Account | Medici LIVE |
| Username | zvi |
| Password | karpad66 |

---

## 1. מתי מלון לא עובד ב-Zenith?

### תסמינים
- `Result=2` (Failed) ב-SalesOffice.Log
- Error 402 "Can not find product" ב-Zenith response
- ה-Monitor מנסה לדחוף availability/pricing ונכשל
- המלון לא מופיע ב-SalesOffice.Details (0 active details)

### צ'קליסט אבחון (בדוק לפי סדר)

```
□ 1. המלון קיים ופעיל בנובי?
     → Settings → Hotel → חפש לפי שם/מספר

□ 2. "Connected to Supplier" = Medici?
     → Settings → Hotel → Edit → שדה "Connected to Supplier"
     → חייב להיות "Medici". אם "None" → Zenith לא מזהה את המלון

□ 3. יש חדרים (Products) מוגדרים לכל סוגי החדרים?
     → Settings → Products → Tab "Rooms"
     → צריך: Standard, Deluxe, Suite, Superior (לפחות Standard + Deluxe)
     → InvTypeCode mapping: Standard→Stnd, Deluxe→DLX, Suite→Suite, Superior→SPR

□ 4. יש Rate Plans (RO + BB)?
     → Settings → Rate Plans → רואים לפחות RO?

□ 5. ה-Rate Plans מחוברים לכל ה-Products?
     → Rate Plans → עמודת Products → כל החדרים מופיעים?
     → **חשוב**: גם BB וגם RO צריכים את כל ה-Products

□ 6. יש PRICING מוגדר (≠ $0)?
     → Rates (/pricing-availability) → לוח שנה → בדוק שיש מחיר
     → אם $0.00: צריך Bulk Update עם מחיר

□ 7. יש AVAILABILITY > 0?
     → אותו לוח שנה → מספר ליד המחיר → 0 = סגור
     → אם 0: צריך Bulk Update עם availability=1
```

### סוגי כשלונות

| Error | סיבה | פתרון |
|-------|-------|--------|
| Result=2, שקט | Availability = 0 | Bulk Update → availability=1 |
| Error 402 "Can not find product" | Products חסרים או לא מחוברים ל-Rate Plans | צור Products + חבר ל-Rate Plans |
| NO_API (אין תוצאות) | "Connected to Supplier" ≠ Medici | Settings → Hotel → Edit → Medici |
| מחיר מנופח ($51K) | Runaway override loop | SOAP push מחיר נכון + safeguard בקוד |

---

## 2. הגדרת מלון חדש (מאפס) — 5 שלבים

### שלב א: יצירת Venue
1. Settings → Hotel → Hotel List → "New Hotel"
2. מלא שם, כתובת, timezone (America/New_York למיאמי)
3. שמור

### שלב ב: הגדרת "Connected to Supplier"
1. Settings → Hotel → לחץ Edit על המלון
2. מצא שדה **"Connected to Supplier"**
3. בחר **"Medici"**
4. שמור

**⚠️ בלי זה, Zenith לא יזהה את המלון כלל!**

### שלב ג: יצירת חדרים (Products)
1. Settings → Products → "New Product"
2. צור לפחות:
   - **Standard** (InvTypeCode: Stnd)
   - **Deluxe** (InvTypeCode: DLX)
   - **Suite** (InvTypeCode: Suite)
   - **Superior** (InvTypeCode: SPR)
3. לכל אחד: Base Price = $5000, Base Qty = 1

### שלב ד: יצירת Rate Plans
1. Settings → Rate Plans → "New Rate"
2. צור **RO** (Room Only):
   - Full Name: `room only / ro`
   - Short Name: `RO`
   - Currency: USD
   - Products: **בחר את כל החדרים**
   - Status: Enable
3. צור **BB** (Bed & Breakfast):
   - Full Name: `bed and breakfast / bb`
   - Short Name: `BB`
   - Products: **בחר את כל החדרים** (אותו דבר כמו RO!)
   - Status: Enable

### שלב ה: הגדרת Pricing + Availability
1. Rates → Bulk Update
2. Rooms: **Select All**
3. Rate Plans: **Select All**
4. Date Range: היום עד סוף השנה
5. Rate Update: Fixed → **$5000**
6. Availability Update: Fixed → **1**
7. Save

---

## 3. Bulk Update — תהליך מפורט

### מתי להשתמש
- מלון חדש שצריך pricing + availability
- שינוי מחיר בסיס לתקופה
- פתיחת/סגירת availability לתאריכים

### שלבים

```
1. בחר מלון ב-dropdown (sidebar למטה)
2. לחץ "Rates" בתפריט הצדדי
3. לחץ כפתור "Bulk Update"
4. ROOMS → Open → Select All → Close
5. RATE PLANS → Open → Select All → Close
6. DATE RANGE → לחץ על שדה תאריך
   → בחר תאריך התחלה
   → Navigate חודשים קדימה עם "Next month"
   → בחר תאריך סיום
7. RATE UPDATE → Fixed → הכנס סכום (5000)
8. AVAILABILITY UPDATE → Fixed → הכנס 1
9. Save
10. אישור: "Bulk update product successfully"
```

### אפשרויות Availability
| אפשרות | שימוש |
|---------|-------|
| Fixed | מספר חדרים קבוע (1 = חדר אחד פתוח) |
| Variable | שינוי יחסי (+/- מהקיים) |
| Reset | איפוס לברירת מחדל |
| No Availability | סגירה מלאה (0) |
| Close Sale | סגירת מכירות |
| Open Sale | פתיחת מכירות |

### אפשרויות Rate
| אפשרות | שימוש |
|---------|-------|
| Fixed | מחיר קבוע ($5000) |
| Variable | שינוי יחסי (+/- או %) |

---

## 4. תיקון Rate Plan Products

### מתי צריך
כש-Rate Plan חסר Products שצריכים להיות מחוברים.

### איך לזהות
1. Rate Plans page → עמודת Products
2. השווה RO vs BB — אם BB מציג פחות חדרים, צריך תיקון
3. השווה מול מה שקיים ב-Products page

### איך לתקן
1. לחץ על כפתור ⋮ (תפריט) בשורת ה-Rate Plan
2. Dialog "Edit Rate Plan" נפתח
3. גלול למטה ל-**Products**
4. לחץ "Open" ליד Products dropdown
5. בחר את כל החדרים שחסרים
6. Save
7. אישור: "Rate Plan changed"

---

## 5. תיקון Error 402 "Can not find product"

### אבחון
Error 402 מ-Zenith אומר שה-InvTypeCode שנשלח לא מתאים לשום Product ב-venue.

### בדיקה
```
1. בדוק ב-DB מה ה-InvTypeCodes שנשלחים:
   SELECT r.InvTypeCode, r.RatePlanCode FROM Med_Hotels_ratebycat r
   WHERE r.HotelId = [ID]

2. בנובי בדוק מה ה-Products שקיימים:
   Settings → Products → Rooms tab

3. השווה — אם InvTypeCode="DLX" נשלח
   אבל אין Product "Deluxe" בנובי → צריך ליצור
```

### תיקון
1. צור את ה-Product החסר (Settings → Products → New Product)
2. חבר אותו ל-Rate Plans (Rate Plans → Edit → Products)
3. Bulk Update pricing + availability
4. המתן ל-push cycle הבא

### דוגמה: Cavalier Hotel #5113
- **בעיה**: DB שולח InvTypeCode="DLX" אבל בנובי יש רק "Standard"
- **פתרון**: יצרנו Product "Deluxe", חיברנו ל-Rate Plans, הגדרנו Supplier=Medici
- **תוצאה**: ממתין לאימות אחרי push cycle

---

## 6. מחירים שגויים + Runaway Override

### איך לזהות
- מחיר חריג ב-SalesOffice.Details (למשל $51,177 במקום $140)
- מחירים שעולים כל 30 דקות ללא הגבלה

### סיבה
מערכת ה-override (PricePredictor) מכפילה מחירים — override על override.

### איך לתקן
1. **SOAP push ישיר** עם מחיר נכון (Bulk Update בנובי לא עוקף contracted rates)
2. **Safeguard בקוד**: `collector.py` מסנן מחירים > $10K, `override_rules.py` חוסם overrides > $10K

### מניעה
- Safeguard כבר קיים בקוד (Sprint 6)
- מחירים > $10,000 מסוננים אוטומטית

---

## 7. השוואת מלון עובד vs נכשל

### Pullman #5080 (עובד) vs Cavalier #5113 (נכשל)

| היבט | Pullman ✅ | Cavalier ❌ (לפני תיקון) |
|------|-----------|--------------------------|
| Products | 4: Standard, Deluxe, Suite, Superior | 1: Standard בלבד |
| Rate Plans | RO + BB → כל 4 Products | Ref + BB → Standard בלבד |
| Connected to Supplier | **Medici** | **None** |
| Push success ever | ✅ מאות | ❌ 0, 367 failures |
| Base Price | $500 | $100 |
| Availability | 1 | 0 |

---

## 8. מצב מלונות מיאמי (2026-03-30)

### עובדים תקין (24 מלונות)
Pullman, Breakwater, Embassy, Hilton Airport, Hilton Bentley, citizenM Brickell, DoubleTree, Atwell, Freehand, Hampton, Loews, Hyatt Centric, Hilton Downtown, Riu Plaza, Savoy, SLS Brickell, + עוד

### תוקנו pricing+availability, עדיין כושלים ב-Zenith (5)
| מלון | Zenith | Error | פעולה נדרשת |
|------|--------|-------|------------|
| Cavalier | 5113 | 402 | ✅ Products + Supplier תוקנו, ממתין לאימות |
| Hilton Cabana | 5115 | 402 | צריך Products + Supplier |
| Fontainebleau | 5268 | 402 | צריך Products + Supplier |
| InterContinental | 5276 | 402 | צריך Products + Supplier |
| Chelsea | 5064 | NO_API | צריך Supplier + בדיקה מעמיקה |

### צריך BB Rate Plan (6 מלונות)
Chelsea #5064, Croydon #5131, LANDON #5138, Gates #5140, Belleza #5265, Catalina #5277

---

## 9. Zenith SOAP — הגדרות

| הגדרה | ערך |
|--------|-----|
| URL | https://hotel.tools/service/Medici%20new |
| Username | APIMedici:Medici Live |
| Password | 12345 |
| Env var | ZENITH_SOAP_PASSWORD (default ב-Azure) |

**הסיסמה `12345` היא הנכונה** — מאושרת עם מלונות עובדים.

---

## 10. טיפים

1. **לוח השנה בנובי מראה רק חודש אחד** — השתמש בטאבים January-December
2. **Bulk Update לא מוצג?** — ודא שאתה בדף Rates (/pricing-availability)
3. **Rate Plan שינוי לא נשמר?** — ודא שלחצת Save ב-dialog (לא ב-X)
4. **Session נופלת?** — Noovy session timeout ~30 דקות. Login מחדש
5. **Hotel dropdown לא מוצא?** — הקלד חלק מהשם או מספר Zenith (#5268)
6. **Contracted rate עוקף Bulk Update?** — רק SOAP push ישיר דורס contracted rates
7. **בדוק "Connected to Supplier"** — זו הסיבה הנפוצה ביותר למלון שמעולם לא עבד
8. **Pullman #5080 הוא המודל** — תמיד השווה מלון בעייתי מול Pullman
