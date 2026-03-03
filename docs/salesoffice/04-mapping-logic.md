# 04 – לוגיקת מיפוי (Mapping Logic)

## הבעיה המרכזית

כשה-WebJob מחפש חדרים ב-Innstant API, הוא מקבל תוצאות גנריות. צריך **למפות** כל חדר למלון ספציפי של Medici כדי שאפשר יהיה לדחוף מחירים ל-Zenith.

המיפוי מתבצע בשני שלבים:
1. **FilterByVenueId** – מציאת המלון הנכון
2. **FindPushRatePlanCode** – מציאת קוד הדחיפה

---

## שלב 1: FilterByVenueId

### מה זה עושה?
מסנן את תוצאות החיפוש כדי לכלול **רק מלונות שממופים ל-Zenith**.

### תנאי סינון
```
Med_Hotels WHERE:
  - Innstant_ZenithId > 0    ← חייב VenueId תקין
  - isActive = 1              ← חייב להיות פעיל
```

### למה מלון לא ימופה?
| סיבה | שדה | בעיה |
|---|---|---|
| אין VenueId | `Innstant_ZenithId = 0` | המלון לא קושר ל-Zenith |
| מלון לא פעיל | `isActive = 0` | המלון מושבת |
| VenueId NULL | `Innstant_ZenithId IS NULL` | שדה ריק |

### איך לבדוק?
```sql
-- בדיקת מלון ספציפי
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE HotelId = 20702;

-- כל המלונות שלא ימופו (בעייתיים)
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE Innstant_ZenithId = 0 OR Innstant_ZenithId IS NULL OR isActive = 0;

-- כל המלונות שכן ימופו (תקינים)
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE Innstant_ZenithId > 0 AND isActive = 1;
```

---

## שלב 2: GetRatePlanCodeAndInvTypeCode → FindPushRatePlanCode

### מה זה עושה?
לכל חדר שעבר את שלב 1, מחפש את **קוד הדחיפה ל-Zenith**.

### קוד מקורי (BaseEF.cs)
```csharp
async Task<(string?, string?)> FindPushRatePlanCode(int hotelId, int boardId, int categoryId)
{
    using (var ctx = new MediciContext(ConnectionString))
    {
        var result = await ctx.MedHotelsRatebycats
            .FirstOrDefaultAsync(i => i.HotelId == hotelId &&
                                      i.BoardId == boardId &&
                                      i.CategoryId == categoryId)
            .ConfigureAwait(false);
        
        if (result != null)
        {
            return (result.RatePlanCode, result.InvTypeCode);  // ✅ נמצא מיפוי
        }
        else
        {
            return (null, null);  // ❌ אין מיפוי → החדר לא ייספר!
        }
    }
}
```

### מה קורה כש-`FindPushRatePlanCode` מחזיר `(null, null)`?
- החדר **לא נספר** ב-"Rooms With Mapping: Y"
- החדר **לא נכתב** ל-`SalesOffice.Details`
- ההזמנה מסתיימת עם `"Rooms With Mapping: 0"`
- **זו הסיבה השכיחה ביותר לכשל מיפוי!**

---

## טבלת ratebycat – הלב של המיפוי

### מבנה
```sql
SELECT Id, HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode
FROM Med_Hotels_ratebycat
WHERE HotelId = 20702;
```

### דוגמה – מלון 20702 (Embassy Suites, Miami)
| Id | HotelId | BoardId | CategoryId | RatePlanCode | InvTypeCode |
|---|---|---|---|---|---|
| 852 | 20702 | 1 (RO) | 1 (Standard) | 12045 | STD |
| 855 | 20702 | 1 (RO) | 12 (Suite) | 12045 | SUI |

### מה זה אומר?
- **חדר RO+Standard** → ידחף עם RatePlan=12045, InvType=STD
- **חדר RO+Suite** → ידחף עם RatePlan=12045, InvType=SUI
- **חדר BB+Standard** → ❌ אין שורה → לא ימופה!

---

## Board Reference

| BoardId | תיאור | קיצור |
|---|---|---|
| 1 | Room Only | RO |
| 2 | Bed & Breakfast | BB |
| 3 | Half Board | HB |
| 4 | Full Board | FB |
| 5 | All Inclusive | AI |
| 6 | Continental Breakfast | CB |
| 7 | Bed | BD |

## Category Reference

| CategoryId | תיאור | InvTypeCode מקובל |
|---|---|---|
| 1 | Standard | STD |
| 2 | Superior | SUP |
| 3 | Dormitory | DRM |
| 4 | Deluxe | DLX |
| 12 | Suite | SUI |

---

## תהליך המיפוי – Visualization

```
Innstant API Returns 10 rooms
          │
          ▼
  FilterByVenueId()
  ┌─────────────────────────────────┐
  │ Hotel has ZenithId>0 + Active?  │
  │   YES → 6 rooms pass           │
  │   NO  → 4 rooms filtered out   │
  └──────────┬──────────────────────┘
             │
             ▼
  GetRatePlanCodeAndInvTypeCode()
  ┌──────────────────────────────────┐
  │ For each room:                   │
  │   FindPushRatePlanCode(H,B,C)    │
  │     Has ratebycat row? → ✅ Map  │
  │     No ratebycat?      → ❌ Skip │
  └──────────┬───────────────────────┘
             │
             ▼
  Result:
    Innstant Api Rooms: 10
    Rooms With Mapping: 3
    (רק 3 מתוך 10 עברו את שני השלבים)
```

---

## WebJobStatus Parsing

הסטטוס הסופי נכתב בפורמט:
```
Completed; Innstant Api Rooms: X; Rooms With Mapping: Y
```

### פירוש:
| חלק | משמעות |
|---|---|
| `Innstant Api Rooms: X` | X חדרים הגיעו מ-Innstant API |
| `Rooms With Mapping: Y` | Y חדרים עברו מיפוי מלא (VenueId + ratebycat) |

### תרחישים:
| סטטוס | משמעות |
|---|---|
| `Rooms: 15; Mapping: 8` | יש 15 חדרים, 8 מופו → הכל תקין |
| `Rooms: 10; Mapping: 0` | יש 10 חדרים אבל **אף אחד לא מופה** → בעיה! |
| `Rooms: 0; Mapping: 0` | לא נמצאו חדרים ביעד → אולי תאריכים שגויים |

---

## בעיות נפוצות ופתרונות

### בעיה: "Rooms With Mapping: 0"

**צ'קליסט:**

1. **האם למלון יש ZenithId?**
   ```sql
   SELECT HotelId, Innstant_ZenithId, isActive FROM Med_Hotels WHERE HotelId = XXXXX;
   ```
   - אם `Innstant_ZenithId = 0` → עדכן: `UPDATE Med_Hotels SET Innstant_ZenithId = YYYY WHERE HotelId = XXXXX`

2. **האם המלון פעיל?**
   - אם `isActive = 0` → עדכן: `UPDATE Med_Hotels SET isActive = 1 WHERE HotelId = XXXXX`

3. **האם יש שורות ratebycat?**
   ```sql
   SELECT * FROM Med_Hotels_ratebycat WHERE HotelId = XXXXX;
   ```
   - אם ריק → הוסף שורות (ראה SQL Reference)

4. **האם ה-Board+Category מתאים?**
   - ייתכן שחדר BB+Deluxe נמצא אבל אין שורת ratebycat ל-Board=2+Category=4

### בעיה: מלון ממופה אבל חדרים ספציפיים לא

- בדוק אילו שילובי Board+Category יש בטבלת ratebycat
- הוסף שורות חסרות

---

## מיפוי Zenith VenueId – רפרנס

| HotelId | שם | Zenith VenueId | סטטוס |
|---|---|---|---|
| 20702 | Embassy Suites Miami | 5081 | ✅ פעיל |
| 24982 | Hilton Miami Downtown | 5084 | ✅ פעיל |
| 854881 | citizenM Miami Worldcenter | 5093 | ✅ פעיל |
| 20845 | DoubleTree Grand Biscayne | 5082 | ⬜ ממתין |
| 20706 | Hilton Miami Airport Blue Lagoon | 5083 | ⬜ ממתין |

> לרשימה מלאה ראה את גיליון ה-Excel של מיפוי Zenith.

---

*ראה [05-callback-booking.md](05-callback-booking.md) לתהליך הרכישה →*
