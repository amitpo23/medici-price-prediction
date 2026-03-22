# Complete Database Deep Documentation - Medici Hotels
Generated: 02/22/2026 17:44:10

## Database Infrastructure Complete Overview

### Azure SQL Configuration:
- **Primary Server**: medici-sql-dev.database.windows.net
- **Resource Group**: Medici-RG-Dev
- **Location**: East US
- **Subscription**: Medici subscription
- **Status**: Production Active

### Database Instances:
1. **medici-db-dev-new** - Main Production Database
2. **medici-db-dev-copy** - Backup/Development Database  
3. **master** - System Database

## Entity Framework Models Complete Analysis

### Database Context Analysis (BaseEF.cs):
**File Size**: 194270 bytes
**Lines of Code**: 4175

## Database Tables Complete Structure

### Table 1: BackOfficeOpt
**Columns (2):**
  - Id (int)
  - DateInsert (DateTime)

**File Info**: 799 bytes, 37 lines

---

### Table 2: BackOfficeOptLog
**Columns (4):**
  - Id (int)
  - BackOfficeOptId (int)
  - ErrorLog (string)
  - DateCreate (DateTime)

**File Info**: 313 bytes, 15 lines

---

### Table 3: Basic

**File Info**: 503 bytes, 25 lines

---

### Table 4: MedBoard

**File Info**: 256 bytes, 13 lines

---

### Table 5: MedBook
**Columns (2):**
  - Id (int)
  - PreBookId (int)

**File Info**: 2216 bytes, 95 lines

---

### Table 6: MedBookCustomerMoreInfo
**Columns (1):**
  - Id (int)

**File Info**: 724 bytes, 33 lines

---

### Table 7: MedBookCustomerName
**Columns (1):**
  - Id (int)

**File Info**: 390 bytes, 19 lines

---

### Table 8: MedBookError
**Columns (1):**
  - Id (int)

**File Info**: 474 bytes, 23 lines

---

### Table 9: MedCancelBook
**Columns (1):**
  - Id (int)

**File Info**: 458 bytes, 21 lines

---

### Table 10: MedCancelBookError
**Columns (1):**
  - Id (int)

**File Info**: 450 bytes, 21 lines

---

### Table 11: MedCurrency

**File Info**: 265 bytes, 13 lines

---

### Table 12: MedCustomerFname
**Columns (2):**
  - Id (int)
  - Name (string)

**File Info**: 213 bytes, 11 lines

---

### Table 13: MedCustomerLname
**Columns (2):**
  - Id (int)
  - Name (string)

**File Info**: 213 bytes, 11 lines

---

### Table 14: MedCustomersReservation
**Columns (10):**
  - ReservationId (int)
  - Lead (bool)
  - Titel (string)
  - FirstName (string)
  - LastName (string)
  - Email (string)
  - Phone (string)
  - Address (string)
  - Country (string)
  - City (string)

**File Info**: 630 bytes, 27 lines

---

### Table 15: MedHotel
**Columns (3):**
  - HotelId (int)
  - InnstantId (int)
  - InnstantZenithId (int)

**File Info**: 606 bytes, 29 lines

---

### Table 16: MedHotelRate
**Columns (3):**
  - BoardId (int)
  - CategoryId (int)
  - Rateid (int)

**File Info**: 247 bytes, 13 lines

---

### Table 17: MedHotelsInstant
**Columns (1):**
  - HotelId (int)

**File Info**: 437 bytes, 21 lines

---

### Table 18: MedHotelsRatebycat
**Columns (6):**
  - Id (int)
  - HotelId (int)
  - BoardId (int)
  - CategoryId (int)
  - RatePlanCode (string)
  - InvTypeCode (string)

**File Info**: 402 bytes, 19 lines

---

### Table 19: MedHotelsToPush
**Columns (5):**
  - Id (int)
  - DateInsert (DateTime)
  - BookId (int)
  - OpportunityId (int)
  - IsActive (bool)

**File Info**: 427 bytes, 21 lines

---

### Table 20: MedHotelsToSearch

**File Info**: 253 bytes, 13 lines

---

### Table 21: MediciContext
**Columns (1):**
  - ConnectionString (string)

**File Info**: 27782 bytes, 686 lines

---

### Table 22: MedLog
**Columns (2):**
  - LogId (int)
  - Date (DateTime)

**File Info**: 243 bytes, 13 lines

---

### Table 23: MedOPportunity
**Columns (13):**
  - OpportunityId (int)
  - DestinationsType (string)
  - DestinationsId (int)
  - DateForm (DateTime)
  - DateTo (DateTime)
  - NumberOfNights (int)
  - Price (double)
  - Operator (string)
  - Currency (string)
  - FreeCancelation (bool)
  - CountryCode (string)
  - PaxAdultsCount (int)
  - PaxChildrenCount (int)

**File Info**: 1520 bytes, 65 lines

---

### Table 24: MedPreBook
**Columns (1):**
  - PreBookId (int)

**File Info**: 1777 bytes, 77 lines

---

### Table 25: MedReservation
**Columns (2):**
  - Id (int)
  - Comments (string)

**File Info**: 1334 bytes, 59 lines

---

### Table 26: MedReservationCancel
**Columns (2):**
  - Id (int)
  - Comments (string)

**File Info**: 1295 bytes, 57 lines

---

### Table 27: MedReservationCustomerMoreInfo
**Columns (2):**
  - Id (int)
  - DateInsert (DateTime)

**File Info**: 778 bytes, 35 lines

---

### Table 28: MedReservationCustomerName
**Columns (2):**
  - Id (int)
  - DateInsert (DateTime)

**File Info**: 449 bytes, 21 lines

---

### Table 29: MedReservationModify
**Columns (2):**
  - Id (int)
  - Comments (string)

**File Info**: 1295 bytes, 57 lines

---

### Table 30: MedReservationModifyCustomerMoreInfo
**Columns (2):**
  - Id (int)
  - IsApproved (bool)

**File Info**: 786 bytes, 35 lines

---

### Table 31: MedReservationModifyCustomerName
**Columns (3):**
  - Id (int)
  - IsApproved (bool)
  - DateInsert (DateTime)

**File Info**: 499 bytes, 23 lines

---

### Table 32: MedReservationNotificationLog
**Columns (3):**
  - Id (int)
  - RequestContent (string)
  - DateInsert (DateTime)

**File Info**: 284 bytes, 13 lines

---

### Table 33: MedRoomBedding

**File Info**: 259 bytes, 13 lines

---

### Table 34: MedRoomCategory

**File Info**: 305 bytes, 15 lines

---

### Table 35: MedRoomConfirmation

**File Info**: 269 bytes, 13 lines

---

### Table 36: MedSearchHotel

**File Info**: 1069 bytes, 47 lines

---

### Table 37: MedSource
**Columns (3):**
  - Id (int)
  - Name (string)
  - IsAcive (bool)

**File Info**: 247 bytes, 13 lines

---

### Table 38: MedUser
**Columns (3):**
  - Userid (int)
  - Username (string)
  - Password (string)

**File Info**: 265 bytes, 13 lines

---

### Table 39: Queue
**Columns (4):**
  - Id (int)
  - CreatedOn (DateTime)
  - PrebookId (int)
  - Status (string)

**File Info**: 779 bytes, 37 lines

---

### Table 40: Tprice

**File Info**: 241 bytes, 13 lines

---

**Total Tables Analyzed**: 40

## Custom Database Models
- **BackOfficeOppLog** (BackOfficeOppLog.cs)
  Size: 410 bytes
- **Book** (Book.cs)
  Size: 3469 bytes
- **Booking** (Booking.cs)
  Size: 340 bytes
- **BookingBackOffice** (BookingBackOffice.cs)
  Size: 1489 bytes
- **ChangePriceBookingResult** (ChangePriceBookingResult.cs)
  Size: 421 bytes
- **Chart** (Chart.cs)
  Size: 542 bytes
- **GraphResponse** (GraphResponse.cs)
  Size: 482 bytes
- **InsertOpp** (InsertOpp.cs)
  Size: 1567 bytes
- **InsertOppResult** (InsertOppResult.cs)
  Size: 443 bytes
- **MedReservationCancelHotel** (MedReservationCancelHotel.cs)
  Size: 332 bytes
- **MedReservationModifyHotel** (MedReservationModifyHotel.cs)
  Size: 332 bytes
- **OpportunityBackOffice** (OpportunityBackOffice.cs)
  Size: 930 bytes
- **OpportunityStatistics** (OpportunityStatistics.cs)
  Size: 349 bytes
- **OpResult** (OpResult.cs)
  Size: 322 bytes
- **PreBook** (PreBook.cs)
  Size: 671 bytes
- **PushRoom** (PushRoom.cs)
  Size: 1266 bytes
- **QueueCheckStatus** (QueueCheckStatus.cs)
  Size: 243 bytes
- **ReservationBackOffice** (ReservationBackOffice.cs)
  Size: 1607 bytes
- **ReservationDetails** (ReservationDetails.cs)
  Size: 1254 bytes
- **ReservationInnstant** (ReservationInnstant.cs)
  Size: 1746 bytes
- **ReservationResponse** (ReservationResponse.cs)
  Size: 496 bytes
- **RoomChartValue** (RoomChartValue.cs)
  Size: 673 bytes
- **RoomGraphData** (RoomGraphData.cs)
  Size: 317 bytes
- **SalesOrderBackOffice** (SalesOrderBackOffice.cs)
  Size: 1544 bytes
- **SalesRoomResponse** (SalesRoomResponse.cs)
  Size: 477 bytes
- **SnapshotCheckParameters** (SnapshotCheckParameters.cs)
  Size: 329 bytes
- **UpdateNameResult** (UpdateNameResult.cs)
  Size: 290 bytes

Total Custom Models: 27

