# 03 – WebJob AzureWebJob ופרויקט OnlyNight

## סקירה

ה-WebJob **AzureWebJob** הוא Continuous WebJob שרץ על Azure App Service `medici-backend`. הוא מבוסס על פרויקט C# בשם **OnlyNight** שהקוד שלו **לא נמצא ב-repo המקומי** – הוא נפרס ישירות ל-Azure.

> **שימו לב:** כל המידע בדף זה נוצר מ-**reverse engineering** של קבצי DLL שהורדו מ-Azure Kudu.

---

## פרטי Deployment

| פרמטר | ערך |
|---|---|
| App Service | `medici-backend` |
| Region | East US 2 |
| Resource Group | `Medici-RG` |
| WebJob Name | `AzureWebJob` |
| Executable | `AzureWebJob.exe` |
| Type | Continuous |
| Mode | Singleton (=מופע אחד בלבד) |
| Using SDK | True (Azure WebJobs SDK) |

### גישה דרך Kudu
```
https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob
```

---

## מבנה DLLים

```
AzureWebJob/
├── AzureWebJob.dll          (13KB)  ← Entry point + Timer Functions
├── OnlyNight.Services.dll   (55KB+) ← כל הלוגיקה העסקית
├── OnlyNight.Models.dll     (10KB+) ← Models/DTOs
├── OnlyNight.Data.dll       (8KB+)  ← DbContext + Data Access
└── [dependencies...]
```

---

## AzureWebJob.dll – Timer Functions

4 פונקציות Timer שרצות במחזוריות:

### 1. ProcessSalesOfficeOrders ⭐ (עיקרי)
- **תדירות:** כל 5 דקות
- **תפקיד:** עיבוד הזמנות SalesOffice חדשות
- **Entry Point:** `SalesOfficeService.Run()`

### 2. ProcessPreSearchResultsSessionPollLog
- **תפקיד:** ניטור ולוג של סשני חיפוש Innstant

### 3. UpdateAISearchHotelDataTable
- **תפקיד:** עדכון טבלת נתונים לחיפוש AI

### 4. UpdateHotelsFromApi
- **תפקיד:** עדכון נתוני מלונות מ-Innstant
- **משתמש ב:** `CopyDataFromHotelInnstantToHotel()`

---

## OnlyNight.Services.dll – שירותים

### Namespace: `OnlyNight.Services.Services.WebJob`

#### SalesOfficeService (עיבוד הליבה)
| מתודה | תיאור |
|---|---|
| `Run()` | נקודת כניסה ראשית – אורכסטרציה של כל התהליך |
| `GetSalesOfficeOrdersList()` | שליפת Orders עם `WebJobStatus IS NULL OR 'In Progress'` |
| `GetAvailableToProceedDetails()` | שליפת Details זמינים להמשך עיבוד |
| `PrepareDetailsToDelete()` | זיהוי Details שצריך למחוק |
| `IsValidDateRange()` | אימות טווח תאריכים |
| `GetInnstantHotelSearchData()` | חיפוש מלונות ב-Innstant API |
| `FilterByVenueId()` | סינון לפי ZenithId ו-isActive |
| `GetRatePlanCodeAndInvTypeCode()` | שליפת קודי מיפוי RatePlan |
| `CreateFlattenedHotels()` | מישור תוצאות לרשימה שטוחה |
| `AddSalesOfficeDetails()` | כתיבה ל-Details |
| `UpdateSalesOfficeDetails()` | עדכון Details קיימים |
| `DeleteSalesOfficeDetails()` | מחיקת Details |

#### SalesOfficeCallbackService (רכישה ודחיפה)
| מתודה | תיאור |
|---|---|
| `ProcessCallBackCommitBySalesOffice()` | עיבוד Commit – BuyRoom + Push |
| `ProcessCallBackCancelBySalesOffice()` | עיבוד ביטול |
| `HandleErrorNoRoomInInnstantBasedOnHotelCategoryBoard()` | טיפול בשגיאת חדר חסר |
| `HandleErrorInnstantRoomHigherPriceThanDb()` | טיפול במחיר גבוה מ-DB |
| `HandleFailInBuyRoom()` | טיפול בכשל BuyRoom |
| `HandleSuccessInBuyRoom()` | טיפול בהצלחת BuyRoom |
| `HandleTryCatchInMethod()` | טיפול בשגיאות כלליות |
| `CreateOpportunity()` | יצירת Opportunity ב-MED_Opportunities |
| `AddToDbSalesOfficeBooking()` | שמירת Booking ב-DB |
| `UpdateBookingStatus()` | עדכון סטטוס Booking |

#### SalesOfficeLogService (לוגים)
| מתודה | תיאור |
|---|---|
| `UpdateWebJobStatus()` | עדכון WebJobStatus ב-Orders |
| `Log()` | כתיבת שורת לוג |
| `UpdateExistLog()` | עדכון לוג קיים |

#### SalesOfficeOrdersService (CRUD)
| מתודה | תיאור |
|---|---|
| `GetSalesOfficeOrders()` | שליפת Orders |
| `InsertSalesOfficeOrder()` | הוספת Order חדש |
| `DeleteSalesOfficeOrders()` | מחיקת Orders |

#### SalesOfficeDetailsService (CRUD)
| מתודה | תיאור |
|---|---|
| `GetSalesOfficeDetails()` | שליפת Details |

#### SalesOfficeBookingsService (CRUD)
| מתודה | תיאור |
|---|---|
| `GetSalesOfficeBookings()` | שליפת Bookings |

---

### Namespace: `OnlyNight.Services.Services`

#### ApiInnstantService (תקשורת Innstant)
| מתודה | תיאור |
|---|---|
| `BuyRoom()` | רכישת חדר ב-Innstant |
| `SetAdults()` | הגדרת מבוגרים בבקשה |
| `SetAdultsAndChildrens()` | הגדרת מבוגרים+ילדים |
| `CreateCustomer()` | יצירת לקוח ב-Innstant |
| `GetInnstantSearchPrice()` | שליפת מחיר חיפוש |

#### ApiRequestInnstantService (HTTP Level)
| מתודה | תיאור |
|---|---|
| `SearchHotels()` | שליחת חיפוש מלונות |
| `SearchResultsSession()` | שליפת תוצאות סשן |
| `SearchResultsSessionPoll()` | Poll לתוצאות |
| `SearchResultsSessionCommon()` | לוגיקה משותפת |
| `SearchResultsSessionHotelDetails()` | פרטי מלון |
| `PreBookAsync()` | Pre-Book (בדיקת זמינות) |
| `BookAsync()` | Book (הזמנה בפועל) |
| `BookCancel()` | ביטול הזמנה |
| `GetCancellation()` | שליפת תנאי ביטול |
| `PopulateCancellationDetails()` | מילוי פרטי ביטול |
| `GetBookingDetailsJsonAsync()` | שליפת פרטי הזמנה |
| `GetUserCreditCard()` | שליפת כרטיס אשראי |
| `GetAetherAccessTokenByUserId()` | שליפת token |

#### UpdateHotelsFromApiService
| מתודה | תיאור |
|---|---|
| `CopyDataFromHotelInnstantToHotel()` | סנכרון נתוני מלון מ-Innstant ל-DB |

#### BaseEF (OnlyNight version)
| מתודה | תיאור |
|---|---|
| `FindPushRatePlanCode()` | חיפוש RatePlan בטבלת ratebycat |
| `GetMedHotelsInnstant()` | שליפת מלונות Innstant |

#### Repository
| מתודה | תיאור |
|---|---|
| `GetMedHotelsInnstant()` | Wrapper ל-BaseEF |

---

## OnlyNight.Models.dll – מודלים

### SalesOfficeOrders
```
Properties:
  - Id, DateInsert, DestinationType, DestinationId
  - DateFrom, DateTo, UserId, IsActive
  - WebJobStatus ← הפרמטר המרכזי לזיהוי סטטוס
```

### SalesOfficeDetailsClass
```
Properties:
  - Id, DateCreated, DateUpdated
  - SalesOfficeOrderId (FK)
  - HotelId, RoomCategory, RoomBoard, RoomPrice, RoomCode
  - IsProcessedCallback
```

### SalesOfficeBookingsClass
```
Properties:
  - Id, SalesOfficeDetailId (FK), SalesOfficeOrderId (FK)
  - [additional booking details]
```

### DTOs
| DTO | שימוש |
|---|---|
| `SalesOfficeOrdersDto` | העברת נתוני Order |
| `SalesOfficeBookingsDto` | העברת נתוני Booking |
| `WebJobSalesOfficeDetailsDto` | העברת Details ל-WebJob |
| `SalesOfficeOrderInsert` | בקשת יצירת Order |

---

## OnlyNight.Data.dll – DbContext

```csharp
// DbSets identified:
DbSet<SalesOfficeOrders> SalesOfficeOrders
DbSet<SalesOfficeDetailsClass> SalesOfficeDetails
DbSet<SalesOfficeBookingsClass> SalesOfficeBookings
DbSet<SalesOfficeLog> SalesOfficeLogs
```

---

## משתנים פנימיים (מ-DLL analysis)

| משתנה | תיאור |
|---|---|
| `_apiInnstantService` | שירות Innstant API |
| `_apiRequestInnstantService` | שירות HTTP Innstant |
| `_innstantStaticDataUrl` | URL לנתונים סטטיים |
| `_salesOfficeLogService` | שירות לוגים |
| `_salesOfficeService` | שירות ראשי |
| `innstantSearchType` | סוג חיפוש (InnstantServersHotelsDestination / Response) |
| `innstantRoomByCategoryAndRoomBoardWithLowestPrice` | חדר עם מחיר נמוך ביותר |
| `innstantRoomCandidateToBuy` | חדר מועמד לרכישה |
| `preBookInnstant` | תוצאת PreBook |
| `innstantBookRoomResult` | תוצאת BuyRoom |

---

## ניטור WebJob

### דרך Kudu API
```bash
# סטטוס WebJob
curl https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob \
  -u $medici-backend:DgFX5ZmRyla3i0T0iXid18zGfqrPRqZfvazrYwcart5xssLRh5wjGqW2hWZW

# לוגים
curl https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AzureWebJob/log
```

### WebJobs שנוספים באותו App Service
| WebJob | Executable | תיאור |
|---|---|---|
| AutoCancellation | AutoCancellation.exe | ביטולים אוטומטיים |
| **AzureWebJob** | **AzureWebJob.exe** | **SalesOffice + עוד** |
| BuyRoomWebJob | BuyRooms.exe | רכישת חדרים (Opportunities) |
| LastPriceUpdate | LastPriceUpdate.exe | עדכון מחירים |

---

*ראה [04-mapping-logic.md](04-mapping-logic.md) לפרטי מיפוי →*
