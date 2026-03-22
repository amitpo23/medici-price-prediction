# Estimated Database Tables Structure
Based on Entity Framework Models Analysis
## Table: BackOfficeOpt
**Columns:**
- Id (int)
- DateInsert (DateTime)

## Table: BackOfficeOptLog
**Columns:**
- Id (int)
- BackOfficeOptId (int)
- ErrorLog (string)
- DateCreate (DateTime)

## Table: Basic

## Table: MedBoard

## Table: MedBook
**Columns:**
- Id (int)
- PreBookId (int)

## Table: MedBookCustomerMoreInfo
**Columns:**
- Id (int)

## Table: MedBookCustomerName
**Columns:**
- Id (int)

## Table: MedBookError
**Columns:**
- Id (int)

## Table: MedCancelBook
**Columns:**
- Id (int)

## Table: MedCancelBookError
**Columns:**
- Id (int)

## Table: MedCurrency

## Table: MedCustomerFname
**Columns:**
- Id (int)
- Name (string)

## Table: MedCustomerLname
**Columns:**
- Id (int)
- Name (string)

## Table: MedCustomersReservation
**Columns:**
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

## Table: MedHotel
**Columns:**
- HotelId (int)
- InnstantId (int)
- InnstantZenithId (int)

## Table: MedHotelRate
**Columns:**
- BoardId (int)
- CategoryId (int)
- Rateid (int)

## Table: MedHotelsInstant
**Columns:**
- HotelId (int)

## Table: MedHotelsRatebycat
**Columns:**
- Id (int)
- HotelId (int)
- BoardId (int)
- CategoryId (int)
- RatePlanCode (string)
- InvTypeCode (string)

## Table: MedHotelsToPush
**Columns:**
- Id (int)
- DateInsert (DateTime)
- BookId (int)
- OpportunityId (int)
- IsActive (bool)

## Table: MedHotelsToSearch

## Table: MediciContext
**Columns:**
- ConnectionString (string)

## Table: MedLog
**Columns:**
- LogId (int)
- Date (DateTime)

## Table: MedOPportunity
**Columns:**
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

## Table: MedPreBook
**Columns:**
- PreBookId (int)

## Table: MedReservation
**Columns:**
- Id (int)
- Comments (string)

## Table: MedReservationCancel
**Columns:**
- Id (int)
- Comments (string)

## Table: MedReservationCustomerMoreInfo
**Columns:**
- Id (int)
- DateInsert (DateTime)

## Table: MedReservationCustomerName
**Columns:**
- Id (int)
- DateInsert (DateTime)

## Table: MedReservationModify
**Columns:**
- Id (int)
- Comments (string)

## Table: MedReservationModifyCustomerMoreInfo
**Columns:**
- Id (int)
- IsApproved (bool)

## Table: MedReservationModifyCustomerName
**Columns:**
- Id (int)
- IsApproved (bool)
- DateInsert (DateTime)

## Table: MedReservationNotificationLog
**Columns:**
- Id (int)
- RequestContent (string)
- DateInsert (DateTime)

## Table: MedRoomBedding

## Table: MedRoomCategory

## Table: MedRoomConfirmation

## Table: MedSearchHotel

## Table: MedSource
**Columns:**
- Id (int)
- Name (string)
- IsAcive (bool)

## Table: MedUser
**Columns:**
- Userid (int)
- Username (string)
- Password (string)

## Table: Queue
**Columns:**
- Id (int)
- CreatedOn (DateTime)
- PrebookId (int)
- Status (string)

## Table: Tprice


