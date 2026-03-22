# Complete Database Relations & Foreign Keys Analysis
Generated: 02/22/2026 18:05:32

## Database Relationship Overview

### Entity Framework Relationships Analysis

### Table Relationships Mapping:
Total Model Files Analyzed: 40

**Table: BackOfficeOpt**
**Foreign Keys:**
  - Id → References: 
  - CountryId → References: Country
  - HotelId → References: Hotel
  - BordId → References: Bord
  - CatrgoryId → References: Catrgory

---
**Table: BackOfficeOptLog**
**Foreign Keys:**
  - Id → References: 
  - BackOfficeOptId → References: BackOfficeOpt

---
**Table: Basic**

---
**Table: MedBoard**
**Foreign Keys:**
  - BoardId → References: Board

---
**Table: MedBook**
**Foreign Keys:**
  - Id → References: 
  - PreBookId → References: PreBook
  - OpportunityId → References: Opportunity
  - CurrencyId → References: Currency
  - SourceHotelId → References: SourceHotel
  - HotelId → References: Hotel
  - ItemId → References: Item
  - ServicesCurrencyId → References: ServicesCurrency
  - SoldId → References: Sold

---
**Table: MedBookCustomerMoreInfo**
**Foreign Keys:**
  - Id → References: 
  - PreBookId → References: PreBook

---
**Table: MedBookCustomerName**
**Foreign Keys:**
  - Id → References: 
  - PreBookId → References: PreBook

---
**Table: MedBookError**
**Foreign Keys:**
  - Id → References: 
  - PreBookId → References: PreBook

---
**Table: MedCancelBook**
**Foreign Keys:**
  - Id → References: 
  - PreBookId → References: PreBook

---
**Table: MedCancelBookError**
**Foreign Keys:**
  - Id → References: 
  - PreBookId → References: PreBook

---
**Table: MedCurrency**
**Foreign Keys:**
  - CurrencyId → References: Currency

---
**Table: MedCustomerFname**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedCustomerLname**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedCustomersReservation**
**Foreign Keys:**
  - ReservationId → References: Reservation

---
**Table: MedHotel**
**Foreign Keys:**
  - HotelId → References: Hotel
  - InnstantId → References: Innstant
  - InnstantZenithId → References: InnstantZenith
  - CountryId → References: Country
  - BoardId → References: Board
  - CategoryId → References: Category

---
**Table: MedHotelRate**
**Foreign Keys:**
  - BoardId → References: Board
  - CategoryId → References: Category

---
**Table: MedHotelsInstant**
**Foreign Keys:**
  - HotelId → References: Hotel
  - InnstantZenithId → References: InnstantZenith

---
**Table: MedHotelsRatebycat**
**Foreign Keys:**
  - Id → References: 
  - HotelId → References: Hotel
  - BoardId → References: Board
  - CategoryId → References: Category

---
**Table: MedHotelsToPush**
**Foreign Keys:**
  - Id → References: 
  - BookId → References: Book
  - OpportunityId → References: Opportunity

---
**Table: MedHotelsToSearch**
**Foreign Keys:**
  - HotelId → References: Hotel

---
**Table: MediciContext**

---
**Table: MedLog**
**Foreign Keys:**
  - LogId → References: Log

---
**Table: MedOPportunity**
**Foreign Keys:**
  - OpportunityId → References: Opportunity
  - OpportunityMlId → References: OpportunityMl
  - DestinationsId → References: Destinations
  - BoardId → References: Board
  - CategoryId → References: Category
  - PreBookId → References: PreBook

---
**Table: MedPreBook**
**Foreign Keys:**
  - PreBookId → References: PreBook
  - SourceHotelId → References: SourceHotel
  - HotelId → References: Hotel
  - CategoryId → References: Category
  - BeddingId → References: Bedding
  - BoardId → References: Board
  - CurrencyId → References: Currency
  - ProviderId → References: Provider
  - OpportunityId → References: Opportunity

---
**Table: MedReservation**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedReservationCancel**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedReservationCustomerMoreInfo**
**Foreign Keys:**
  - Id → References: 
  - ReservationId → References: Reservation

---
**Table: MedReservationCustomerName**
**Foreign Keys:**
  - Id → References: 
  - ReservationId → References: Reservation

---
**Table: MedReservationModify**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedReservationModifyCustomerMoreInfo**
**Foreign Keys:**
  - Id → References: 
  - ReservationId → References: Reservation

---
**Table: MedReservationModifyCustomerName**
**Foreign Keys:**
  - Id → References: 
  - ReservationId → References: Reservation

---
**Table: MedReservationNotificationLog**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedRoomBedding**
**Foreign Keys:**
  - BeddingId → References: Bedding

---
**Table: MedRoomCategory**
**Foreign Keys:**
  - CategoryId → References: Category

---
**Table: MedRoomConfirmation**
**Foreign Keys:**
  - ConfirmationId → References: Confirmation

---
**Table: MedSearchHotel**
**Foreign Keys:**
  - SourceHotelId → References: SourceHotel
  - HotelId → References: Hotel
  - CategoryId → References: Category
  - BeddingId → References: Bedding
  - BoardId → References: Board
  - CurrencyId → References: Currency
  - ProviderId → References: Provider

---
**Table: MedSource**
**Foreign Keys:**
  - Id → References: 

---
**Table: MedUser**

---
**Table: Queue**
**Foreign Keys:**
  - Id → References: 
  - PrebookId → References: Prebook
  - HotelId → References: Hotel

---
**Table: Tprice**
**Foreign Keys:**
  - HotelId → References: Hotel

---

### Relationship Summary:
- **Total Tables Analyzed**: 40
- **Total Relationships Found**: 92
- **Relationship Types**: Foreign Keys, Navigation Properties, Collections

### Common Relationship Patterns:
- **User/Customer Relationships**: MedCustomersReservation → Customer data management
- **Booking Relationships**: MedBook → Core booking entities
- **Hotel Relationships**: MedHotel → Hotel and room management
- **Reservation Relationships**: Various Med*Reservation* → Reservation lifecycle
- **Error/Log Relationships**: *Error, *Log → Audit and error tracking

