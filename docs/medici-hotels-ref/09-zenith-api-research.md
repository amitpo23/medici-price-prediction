# מחקר מלא - Zenith API (hotel.tools)

## תאריך: 23/02/2026  
## עדכון אחרון: 24/02/2026

---

## 1. סיכום מנהלים

### ✅ הבעיה תוקנה! (23/02/2026)

**בעיה מקורית:** המלונות 5081 (Embassy) ו-5084 (Hilton) לא היו להם Products מוגדרים ב-hotel.tools, כך שכל Push נכשל.

**פתרון:** הוגדרו Products (Standard + Suite) עם RatePlans בממשק hotel.tools.

**תוצאה:** כל 4 המלונות (5079, 5081, 5084, 5110) עובדים עכשיו מקצה לקצה.

### מצב לפני התיקון (23/02 בוקר)

```
קריאה: OTA_HotelAvailRQ ← HotelCode="5081"
תוצאה: <RoomStays/> ← ריק! אפס פרודוקטים

קריאה: OTA_HotelAvailRQ ← HotelCode="5084"
תוצאה: <RoomStays/> ← ריק! אפס פרודוקטים
```

### מצב אחרי התיקון (23/02 ערב)

```
קריאה: OTA_HotelAvailRQ ← HotelCode="5081"
תוצאה: 4 פרודוקטים (Stnd/12045, Stnd/13170, Suite/12045, Suite/13170)

קריאה: OTA_HotelAvailRQ ← HotelCode="5084"
תוצאה: 4 פרודוקטים (Stnd/12048, Stnd/13173, Suite/12048, Suite/13173)

Push Availability → <Success/> ✅
Push Rate → <Success/> ✅
```

### מלונות שעבדו מההתחלה

```
קריאה: OTA_HotelAvailRQ ← HotelCode="5079" (citizenM - עובד)
תוצאה: 2 פרודוקטים (Stnd/12043, Stnd/13169)

קריאה: OTA_HotelAvailRQ ← HotelCode="5110" (Breakwater - עובד)
תוצאה: 8 פרודוקטים (DLX/Stnd/Suite/SPR × 12078/12867)
```

---

## 2. יכולות ה-API של זניט (נבדקו בפועל)

### פעולות נתמכות

| פעולה OTA | נתמך | תיאור | שימוש |
|---|:---:|---|---|
| `OTA_HotelAvailNotifRQ` | ✅ | Push Availability & Restrictions | שליחת זמינות וסטטוס חדר |
| `OTA_HotelRateAmountNotifRQ` | ✅ | Push Rates | שליחת מחירים |
| `OTA_HotelAvailRQ` | ✅ | **Retrieve Products** | **שליפת כל הפרודוקטים של מלון** |
| `OTA_HotelResNotifRQ` | ✅ | Reservation Callback | קבלת הזמנות (Commit/Modify/Cancel) |

### פעולות שאינן נתמכות

| פעולה OTA | נתמך | תגובת API |
|---|:---:|---|
| `OTA_HotelDescriptiveInfoRQ` | ❌ | `Unsupported request ()` |
| `OTA_ReadRQ` | ❌ | `Unsupported request ()` |
| `OTA_HotelRatePlanRQ` | ❌ | `Unsupported request ()` |
| `OTA_HotelInvCountNotifRQ` | לא נבדק | - |

### מבנה שגיאות

```xml
<!-- שגיאת פרודוקט לא נמצא -->
<Errors>
  <Error Type="12" Code="402">Can not find product for availability update (HotelCode/InvTypeCode/RatePlanCode)</Error>
</Errors>

<!-- שגיאת בקשה לא נתמכת -->
<error http-code="0"><message><![CDATA[Unsupported request ()]]></message></error>
```

---

## 3. פעולת Retrieve (שליפה) - OTA_HotelAvailRQ

### זוהי הפעולה החשובה ביותר! מאפשרת לבדוק מה מוגדר בזניט.

### SOAP Request Template

```xml
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Header>
    <wsse:Security soap:mustUnderstand="1" 
      xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" 
      xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <wsse:UsernameToken>
        <wsse:Username>APIMedici:Medici Live</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">12345</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <OTA_HotelAvailRQ xmlns="http://www.opentravel.org/OTA/2003/05" 
      Version="1.0" EchoToken="unique-id">
      <AvailRequestSegments>
        <AvailRequestSegment>
          <HotelSearchCriteria>
            <Criterion>
              <HotelRef HotelCode="XXXX"/>   <!-- הכנס HotelCode כאן -->
            </Criterion>
          </HotelSearchCriteria>
        </AvailRequestSegment>
      </AvailRequestSegments>
    </OTA_HotelAvailRQ>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

### תגובה - פרודוקטים קיימים (דוגמה מ-5079 citizenM)

```xml
<OTA_HotelAvailRS>
  <RoomStays>
    <RoomStay>
      <RoomTypes>
        <RoomType RoomTypeCode="Stnd">
          <RoomDescription Name="Standard (Stnd)"><Text/></RoomDescription>
        </RoomType>
      </RoomTypes>
      <RatePlans>
        <RatePlan RatePlanCode="12043">
          <RatePlanDescription Name="room only"/>
        </RatePlan>
      </RatePlans>
    </RoomStay>
    <!-- RoomStay נוסף לכל שילוב RoomType + RatePlan -->
  </RoomStays>
  <Success/>
</OTA_HotelAvailRS>
```

### תגובה - אין פרודוקטים (דוגמה מ-5081 Embassy)

```xml
<OTA_HotelAvailRS>
  <RoomStays/>   <!-- ריק! -->
  <Success/>
</OTA_HotelAvailRS>
```

### PowerShell Script לבדיקה

```powershell
# בדיקת פרודוקטים של מלון בזניט
function Test-ZenithProducts {
    param([string]$HotelCode)
    
    $b = "<SOAP-ENV:Envelope xmlns:SOAP-ENV=`"http://schemas.xmlsoap.org/soap/envelope/`"><SOAP-ENV:Header><wsse:Security soap:mustUnderstand=`"1`" xmlns:wsse=`"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd`" xmlns:soap=`"http://schemas.xmlsoap.org/soap/envelope/`"><wsse:UsernameToken><wsse:Username>APIMedici:Medici Live</wsse:Username><wsse:Password Type=`"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText`">12345</wsse:Password></wsse:UsernameToken></wsse:Security></SOAP-ENV:Header><SOAP-ENV:Body><OTA_HotelAvailRQ xmlns=`"http://www.opentravel.org/OTA/2003/05`" Version=`"1.0`" EchoToken=`"check$HotelCode`"><AvailRequestSegments><AvailRequestSegment><HotelSearchCriteria><Criterion><HotelRef HotelCode=`"$HotelCode`"/></Criterion></HotelSearchCriteria></AvailRequestSegment></AvailRequestSegments></OTA_HotelAvailRQ></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    
    $r = Invoke-WebRequest -Uri "https://hotel.tools/service/Medici%20new" -Method POST -ContentType "text/xml" -Body $b -UseBasicParsing
    
    [xml]$xml = $r.Content
    $ns = @{ota = "http://www.opentravel.org/OTA/2003/05"; soap = "http://schemas.xmlsoap.org/soap/envelope/"}
    $roomStays = $xml.SelectNodes("//ota:RoomStay", (New-Object System.Xml.XmlNamespaceManager($xml.NameTable)).Tap({$_.AddNamespace("ota","http://www.opentravel.org/OTA/2003/05")}))
    
    Write-Host "Hotel $HotelCode - Response:"
    Write-Host $r.Content
}

# שימוש:
Test-ZenithProducts -HotelCode "5081"
```

---

## 4. טבלת השוואה מלאה - מלונות SalesOffice

### מיפוי Med_Hotels_ratebycat ← DB

| מלון | HotelId | ZenithId | CategoryId | BoardId | RatePlanCode | InvTypeCode | סטטוס Push |
|---|---|---|---|---|---|---|---|
| **citizenM Miami** | 854881 | 5079 | 1 (Standard) | 1 (RO) | 12043 | Stnd | ✅ עובד |
| **Breakwater** | 66814 | 5110 | 1 (Standard) | 1 (RO) | 12078 | Stnd | ✅ עובד |
| **Breakwater** | 66814 | 5110 | 2 (Superior) | 1 (RO) | 12078 | SPR | ✅ עובד |
| **Breakwater** | 66814 | 5110 | 4 (Deluxe) | 1 (RO) | 12078 | DLX | ✅ עובד |
| **Breakwater** | 66814 | 5110 | 12 (Suite) | 1 (RO) | 12078 | Suite | ✅ עובד |
| **Embassy Suites** | 20702 | 5081 | 1 (Standard) | 1 (RO) | 12045 | Stnd | ✅ **תוקן 23/02** |
| **Embassy Suites** | 20702 | 5081 | 12 (Suite) | 1 (RO) | 12045 | Suite | ✅ **תוקן 23/02** |
| **Hilton Downtown** | 24982 | 5084 | 1 (Standard) | 1 (RO) | 12048 | Stnd | ✅ **תוקן 23/02** |
| **Hilton Downtown** | 24982 | 5084 | 12 (Suite) | 1 (RO) | 12048 | Suite | ✅ **תוקן 23/02** |

### פרודוקטים בפועל בזניט (OTA_HotelAvailRQ)

| ZenithId | מלון | RoomTypeCode | RatePlanCode | RatePlan Name | סטטוס |
|---|---|---|---|---|---|
| **5079** | citizenM | Stnd | 12043 | room only | ✅ מוגדר |
| **5079** | citizenM | Stnd | 13169 | bed and breakfast | ✅ מוגדר |
| **5110** | Breakwater | DLX | 12078 | room only | ✅ מוגדר |
| **5110** | Breakwater | DLX | 12867 | Bed and Breakfast | ✅ מוגדר |
| **5110** | Breakwater | Stnd | 12078 | room only | ✅ מוגדר |
| **5110** | Breakwater | Stnd | 12867 | Bed and Breakfast | ✅ מוגדר |
| **5110** | Breakwater | Suite | 12078 | room only | ✅ מוגדר |
| **5110** | Breakwater | Suite | 12867 | Bed and Breakfast | ✅ מוגדר |
| **5110** | Breakwater | SPR | 12078 | room only | ✅ מוגדר |
| **5110** | Breakwater | SPR | 12867 | Bed and Breakfast | ✅ מוגדר |
| **5081** | Embassy | Stnd | 12045 | room only | ✅ **תוקן 23/02** |
| **5081** | Embassy | Stnd | 13170 | bed and breakfast | ✅ **חדש 23/02** |
| **5081** | Embassy | Suite | 12045 | room only | ✅ **תוקן 23/02** |
| **5081** | Embassy | Suite | 13170 | bed and breakfast | ✅ **חדש 23/02** |
| **5084** | Hilton | Stnd | 12048 | Refundable | ✅ **תוקן 23/02** |
| **5084** | Hilton | Stnd | 13173 | bed and breakfast | ✅ **חדש 23/02** |
| **5084** | Hilton | Suite | 12048 | Refundable | ✅ **תוקן 23/02** |
| **5084** | Hilton | Suite | 13173 | bed and breakfast | ✅ **חדש 23/02** |

### ניתוח פער (Gap Analysis)

| מלון | DB: RatePlanCode | DB: InvTypeCode | Zenith: Products | סטטוס |
|---|---|---|---|---|
| **Embassy (5081)** | 12045 | Stnd, Suite | Stnd+Suite × 12045+13170 = 4 | ✅ **תוקן 23/02** |
| **Hilton (5084)** | 12048 | Stnd, Suite | Stnd+Suite × 12048+13173 = 4 | ✅ **תוקן 23/02** |
| citizenM (5079) | 12043 | Stnd | Stnd/12043, Stnd/13169 | ✅ תקין |
| Breakwater (5110) | 12078 | Stnd,SPR,DLX,Suite | 4 types × 2 plans = 8 | ✅ תקין |

> **הערה:** RatePlanCodes חדשים 13170 (Embassy B&B) ו-13173 (Hilton B&B) עדיין לא ממופים ב-`Med_Hotels_ratebycat`.

---

## 5. מה צריך לעשות כדי לתקן

### שלב 1: הגדרת Products בזניט (hotel.tools)
צריך להיכנס לממשק הניהול של hotel.tools ולהגדיר עבור כל מלון כושל:

**Embassy Suites (5081):**
- Product 1: RoomType=Stnd, RatePlan=12045 (room only)
- Product 2: RoomType=Suite, RatePlan=12045 (room only)

**Hilton Downtown (5084):**
- Product 1: RoomType=Stnd, RatePlan=12048 (room only)
- Product 2: RoomType=Suite, RatePlan=12048 (room only)

### שלב 2: אימות (Verification)
לאחר ההגדרה, הריצו את בדיקת ה-Retrieve:

```powershell
# בדיקה שהפרודוקטים הוגדרו
$b = '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Header><wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><wsse:UsernameToken><wsse:Username>APIMedici:Medici Live</wsse:Username><wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">12345</wsse:Password></wsse:UsernameToken></wsse:Security></SOAP-ENV:Header><SOAP-ENV:Body><OTA_HotelAvailRQ xmlns="http://www.opentravel.org/OTA/2003/05" Version="1.0" EchoToken="verify"><AvailRequestSegments><AvailRequestSegment><HotelSearchCriteria><Criterion><HotelRef HotelCode="5081"/></Criterion></HotelSearchCriteria></AvailRequestSegment></AvailRequestSegments></OTA_HotelAvailRQ></SOAP-ENV:Body></SOAP-ENV:Envelope>'

$r = Invoke-WebRequest -Uri "https://hotel.tools/service/Medici%20new" -Method POST -ContentType "text/xml" -Body $b -UseBasicParsing
Write-Host $r.Content
# צפוי: <RoomStays> עם Products ← ולא <RoomStays/> ריק
```

### שלב 3: בדיקת Push ידנית

```powershell
# בדיקת Push Availability
$b = '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Header><wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><wsse:UsernameToken><wsse:Username>APIMedici:Medici Live</wsse:Username><wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">12345</wsse:Password></wsse:UsernameToken></wsse:Security></SOAP-ENV:Header><SOAP-ENV:Body><OTA_HotelAvailNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" Version="1.0" TimeStamp="2026-02-23T10:00:00" EchoToken="pushtest"><AvailStatusMessages HotelCode="5081"><AvailStatusMessage BookingLimit="1"><StatusApplicationControl Start="2026-07-01" End="2026-07-01" InvTypeCode="Stnd" RatePlanCode="12045"/><RestrictionStatus Status="Open" /></AvailStatusMessage></AvailStatusMessages></OTA_HotelAvailNotifRQ></SOAP-ENV:Body></SOAP-ENV:Envelope>'

$r = Invoke-WebRequest -Uri "https://hotel.tools/service/Medici%20new" -Method POST -ContentType "text/xml" -Body $b -UseBasicParsing
Write-Host $r.Content
# צפוי: <Success/> ← במקום שגיאה 402
```

---

## 6. מדריך הקמת מלון חדש בזניט

### תהליך מלא - צ'קליסט

#### א. דרישות מקדימות
- [ ] HotelCode בזניט (מתקבל מצוות hotel.tools)
- [ ] Products מוגדרים בממשק hotel.tools (RoomType + RatePlan)
- [ ] RatePlanCode שהוקצה למלון

#### ב. הגדרה בזניט (hotel.tools UI)
1. יצירת מלון עם HotelCode
2. הגדרת חדרים (RoomTypes): Stnd, Suite, DLX, SPR וכו'
3. הגדרת תעריפים (RatePlans): room only, B&B וכו' → מתקבל RatePlanCode
4. יצירת Products = שילוב RoomType + RatePlan

#### ג. אימות API
```powershell
# ודאו שהפרודוקטים חוזרים:
# OTA_HotelAvailRQ → צפוי <RoomStays> עם Products
```

#### ד. הגדרה ב-DB (medici-db)

1. **Med_Hotels** - הוספת מלון:
```sql
-- בדקו שהמלון קיים:
SELECT * FROM Med_Hotels WHERE HotelId = @HotelId

-- עדכנו Innstant_ZenithId:
UPDATE Med_Hotels 
SET Innstant_ZenithId = @ZenithHotelCode 
WHERE HotelId = @HotelId
```

2. **Med_Hotels_ratebycat** - מיפוי חדרים:
```sql
-- הוסיפו שורה לכל שילוב Category + Board:
INSERT INTO Med_Hotels_ratebycat (HotelId, CategoryId, BoardId, RatePlanCode, InvTypeCode)
VALUES (@HotelId, @CategoryId, @BoardId, @RatePlanCode, @InvTypeCode)

-- דוגמאות CategoryId:
-- 1 = Standard, 2 = Superior, 4 = Deluxe, 12 = Suite

-- דוגמאות BoardId:
-- 1 = Room Only (RO)

-- InvTypeCode חייב להתאים ל-RoomTypeCode בזניט:
-- Stnd, Suite, DLX, SPR
```

3. **SalesOffice.Orders** - יצירת הזמנות:
   - ה-WebJob מעבד אוטומטית Orders ← Details ← Push לזניט
   - DestinationId = HotelId מ-Med_Hotels

#### ה. בדיקה סופית
```powershell
# 1. ודאו Retrieve מחזיר Products
# 2. Push Availability → צפוי <Success/>
# 3. Push Rates → צפוי <Success/>
# 4. בדקו SalesOffice.Log → ActionId=5, ActionResultId=1 (Success)
```

---

## 7. פרטי חיבור API

| פרמטר | ערך |
|---|---|
| **URL** | `https://hotel.tools/service/Medici%20new` |
| **Method** | POST |
| **Content-Type** | text/xml |
| **Auth Type** | WSSE (WS-Security) |
| **Username** | `APIMedici:Medici Live` |
| **Password** | `12345` |
| **Protocol** | SOAP 1.1 |
| **OTA Version** | 1.0 |
| **Namespace** | `http://www.opentravel.org/OTA/2003/05` |

---

## 8. הודעות שגיאה ידועות

| קוד שגיאה | Type | הודעה | משמעות | פתרון |
|---|---|---|---|---|
| 402 | 12 | `Can not find product for availability update (HotelCode/InvTypeCode/RatePlanCode)` | שילוב הפרודוקט לא קיים בזניט | הגדרת Product בממשק hotel.tools |
| 402 | 12 | `Can not find product for rate update (HotelCode/InvTypeCode/RatePlanCode)` | שילוב הפרודוקט לא קיים בזניט | הגדרת Product בממשק hotel.tools |
| 0 | - | `Unsupported request ()` | סוג הבקשה OTA לא נתמך | השתמש רק בפעולות נתמכות |
| 448 | 3 | `System Error` | שגיאה פנימית | בדיקת Payload |

---

## 9. לוגים ומעקב

### SalesOffice.Log (טבלת `[SalesOffice.Log]`)
- **ActionId=5**: Push to HotelConnect (Zenith)
- **ActionResultId=1**: Success
- **ActionResultId=2**: Failed
- **Message**: מכיל את ה-Request JSON payload (לא את ה-Error response!)

### Med_Log (טבלת `MED_Log`)
- מכיל שגיאות מ-PushRoomControl.cs (הזרימה הכללית)
- **כולל את הודעת השגיאה מזניט**: `"PushRates HotelsToPushId:X error:Can not find product..."`
- ⚠️ הזרימה של SalesOffice WebJob **לא כותבת** את שגיאת זניט ל-Med_Log

### חסרון: שגיאת זניט לא נשמרת ב-SalesOffice.Log
ב-SalesOffice WebJob, כשה-Push נכשל, ה-Log מכיל רק את ה-Request שנשלח (JSON):
```json
{
  "HotelCode": "5081",
  "BookingLimit": "1",
  "InvTypeCode": "Stnd",
  "RatePlanCodeor": "12045",
  "Start": "2026-07-01",
  "End": "2026-07-01",
  "Status": "Open"
}
```
**המלצה**: לעדכן את ה-WebJob כך שישמור גם את הודעת השגיאה מזניט ב-Message.

---

## 10. סטטיסטיקת כשלונות (לפני התיקון - נכון ל-23/02/2026 בוקר)

| מלון | ZenithId | Total Push Failures | Total Successes | שגיאת זניט |
|---|---|---|---|---|
| Embassy Suites | 5081 | 247 | 0 | Can not find product (5081/Stnd/12045) |
| Hilton Downtown | 5084 | 152 | 0 | Can not find product (5084/Stnd/12048) |
| citizenM | 5079 | 0 | פועל תקין | - |
| Breakwater | 5110 | 0 | פועל תקין | - |

> **✅ תוקן 23/02/2026 ערב:** לאחר הגדרת Products ב-hotel.tools, כל 4 המלונות עובדים.

---

## 11. גם מלון 5080 נכשל!

בבדיקה נוספת, גם HotelCode **5080** חוזר ריק מזניט ורושם שגיאות ב-Med_Log:
```
Can not find product for rate update (5080/DLX/12044)
Can not find product for rate update (5080/Stnd/12044)
Can not find product for availability update (5080/Stnd/12044)
```

---

## 12. סיכום תוצאות הבדיקות

### בדיקות שבוצעו בפועל (23/02/2026)

| # | בדיקה | HotelCode | תוצאה |
|---|---|---|---|
| 1 | OTA_HotelAvailNotifRQ (Push Avail) | 5081 | ❌ `Error 402: Can not find product` |
| 2 | OTA_HotelAvailNotifRQ (Push Avail) | 5084 | ❌ `Error 402: Can not find product` |
| 3 | OTA_HotelAvailNotifRQ (Push Avail) | 5079 | ✅ `<Success/>` |
| 4 | OTA_HotelRateAmountNotifRQ (Push Rate) | 5081 | ❌ `Error 402: Can not find product` |
| 5 | OTA_HotelAvailRQ (Retrieve) | 5079 | ✅ 2 products returned |
| 6 | OTA_HotelAvailRQ (Retrieve) | 5110 | ✅ 8 products returned |
| 7 | OTA_HotelAvailRQ (Retrieve) | 5081 | ⚠️ `<RoomStays/>` empty |
| 8 | OTA_HotelAvailRQ (Retrieve) | 5084 | ⚠️ `<RoomStays/>` empty |
| 9 | OTA_HotelAvailRQ (Retrieve) | 5080 | ⚠️ `<RoomStays/>` empty |
| 10 | OTA_HotelDescriptiveInfoRQ | 5081 | ❌ `Unsupported request` |
| 11 | OTA_ReadRQ | 5079 | ❌ `Unsupported request` |
| 12 | OTA_HotelRatePlanRQ | 5079 | ❌ `Unsupported request` |

### בדיקות נוספות - אחרי תיקון Products ב-hotel.tools (23/02/2026 ערב)

| # | בדיקה | HotelCode | תוצאה |
|---|---|---|---|
| 13 | OTA_HotelAvailRQ (Retrieve) | 5081 | ✅ **4 products** (Stnd+Suite × 12045+13170) |
| 14 | OTA_HotelAvailRQ (Retrieve) | 5084 | ✅ **4 products** (Stnd+Suite × 12048+13173) |
| 15 | OTA_HotelAvailNotifRQ (Push Avail) | 5081 | ✅ **`<Success/>`** |
| 16 | OTA_HotelAvailNotifRQ (Push Avail) | 5084 | ✅ **`<Success/>`** |
| 17 | OTA_HotelRateAmountNotifRQ (Push Rate) | 5081 | ✅ **`<Success/>`** |
| 18 | OTA_HotelRateAmountNotifRQ (Push Rate) | 5084 | ✅ **`<Success/>`** |
