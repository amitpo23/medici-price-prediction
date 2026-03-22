# Medici Hotels - Database Schema Documentation
Date: 02/22/2026 17:34:18

## Database Infrastructure

### Azure SQL Server Information:
- **Server Name**: medici-sql-dev.database.windows.net
- **Resource Group**: Medici-RG-Dev
- **Location**: East US
- **Status**: Active

### Databases:
1. **medici-db-dev-new** - Main production database
2. **medici-db-dev-copy** - Backup/test database
3. **master** - System database

### Connection Information:
- **Server**: medici-sql-dev.database.windows.net
- **Authentication**: SQL Server Authentication / Azure AD
- **Firewall**: Configured for Azure services

## Entity Framework Models Analysis

### Key Model Files Found:
### Entity Framework Models:
- BaseEF.cs
- CustomModel\BackOfficeOppLog.cs
- CustomModel\Book.cs
- CustomModel\Booking.cs
- CustomModel\BookingBackOffice.cs
- CustomModel\ChangePriceBookingResult.cs
- CustomModel\Chart.cs
- CustomModel\GraphResponse.cs
- CustomModel\InsertOpp.cs
- CustomModel\InsertOppResult.cs
- CustomModel\MedReservationCancelHotel.cs
- CustomModel\MedReservationModifyHotel.cs
- CustomModel\OpportunityBackOffice.cs
- CustomModel\OpportunityStatistics.cs
- CustomModel\OpResult.cs
- CustomModel\PreBook.cs
- CustomModel\PushRoom.cs
- CustomModel\QueueCheckStatus.cs
- CustomModel\ReservationBackOffice.cs
- CustomModel\ReservationDetails.cs
- CustomModel\ReservationInnstant.cs
- CustomModel\ReservationResponse.cs
- CustomModel\RoomChartValue.cs
- CustomModel\RoomGraphData.cs
- CustomModel\SalesOrderBackOffice.cs
- CustomModel\SalesRoomResponse.cs
- CustomModel\SnapshotCheckParameters.cs
- CustomModel\UpdateNameResult.cs
- Models11\BackOfficeOpt.cs
- Models11\BackOfficeOptLog.cs
- Models11\Basic.cs
- Models11\MedBoard.cs
- Models11\MedBook.cs
- Models11\MedBookCustomerMoreInfo.cs
- Models11\MedBookCustomerName.cs
- Models11\MedBookError.cs
- Models11\MedCancelBook.cs
- Models11\MedCancelBookError.cs
- Models11\MedCurrency.cs
- Models11\MedCustomerFname.cs
- Models11\MedCustomerLname.cs
- Models11\MedCustomersReservation.cs
- Models11\MedHotel.cs
- Models11\MedHotelRate.cs
- Models11\MedHotelsInstant.cs
- Models11\MedHotelsRatebycat.cs
- Models11\MedHotelsToPush.cs
- Models11\MedHotelsToSearch.cs
- Models11\MediciContext.cs
- Models11\MedLog.cs
- Models11\MedOPportunity.cs
- Models11\MedPreBook.cs
- Models11\MedReservation.cs
- Models11\MedReservationCancel.cs
- Models11\MedReservationCustomerMoreInfo.cs
- Models11\MedReservationCustomerName.cs
- Models11\MedReservationModify.cs
- Models11\MedReservationModifyCustomerMoreInfo.cs
- Models11\MedReservationModifyCustomerName.cs
- Models11\MedReservationNotificationLog.cs
- Models11\MedRoomBedding.cs
- Models11\MedRoomCategory.cs
- Models11\MedRoomConfirmation.cs
- Models11\MedSearchHotel.cs
- Models11\MedSource.cs
- Models11\MedUser.cs
- Models11\Queue.cs
- Models11\Tprice.cs

### Database Table Models (Models11):
- BackOfficeOpt.cs
- BackOfficeOptLog.cs
- Basic.cs
- MedBoard.cs
- MedBook.cs
- MedBookCustomerMoreInfo.cs
- MedBookCustomerName.cs
- MedBookError.cs
- MedCancelBook.cs
- MedCancelBookError.cs
- MedCurrency.cs
- MedCustomerFname.cs
- MedCustomerLname.cs
- MedCustomersReservation.cs
- MedHotel.cs
- MedHotelRate.cs
- MedHotelsInstant.cs
- MedHotelsRatebycat.cs
- MedHotelsToPush.cs
- MedHotelsToSearch.cs
- MediciContext.cs
- MedLog.cs
- MedOPportunity.cs
- MedPreBook.cs
- MedReservation.cs
- MedReservationCancel.cs
- MedReservationCustomerMoreInfo.cs
- MedReservationCustomerName.cs
- MedReservationModify.cs
- MedReservationModifyCustomerMoreInfo.cs
- MedReservationModifyCustomerName.cs
- MedReservationNotificationLog.cs
- MedRoomBedding.cs
- MedRoomCategory.cs
- MedRoomConfirmation.cs
- MedSearchHotel.cs
- MedSource.cs
- MedUser.cs
- Queue.cs
- Tprice.cs

### Custom Models:
- BackOfficeOppLog.cs
- Book.cs
- Booking.cs
- BookingBackOffice.cs
- ChangePriceBookingResult.cs
- Chart.cs
- GraphResponse.cs
- InsertOpp.cs
- InsertOppResult.cs
- MedReservationCancelHotel.cs
- MedReservationModifyHotel.cs
- OpportunityBackOffice.cs
- OpportunityStatistics.cs
- OpResult.cs
- PreBook.cs
- PushRoom.cs
- QueueCheckStatus.cs
- ReservationBackOffice.cs
- ReservationDetails.cs
- ReservationInnstant.cs
- ReservationResponse.cs
- RoomChartValue.cs
- RoomGraphData.cs
- SalesOrderBackOffice.cs
- SalesRoomResponse.cs
- SnapshotCheckParameters.cs
- UpdateNameResult.cs

## Configuration Details

### Connection Strings Location:
- **Backend/appsettings.json** - Main application configuration
- **Backend/appsettings.Development.json** - Development environment
- **Other services** - Each service has its own connection configuration

### Security:
- Managed Identity support available (oidc-msi-a550)
- Azure Key Vault integration (medici-keyvault)
- Connection strings stored securely

## Related Azure Resources:

### Storage:
- **Redis Cache**: medici-redis-dev (for session/caching)
- **Storage Account**: medicibackupstorage (for backups)

### Security:
- **Key Vault**: medici-keyvault
- **Managed Identity**: oidc-msi-a550

### Compute:
- **App Service Plans**: Multiple plans for different environments
- **Backend Application**: medici-backend-dev

---
Documentation Generated: 02/22/2026 17:34:19
Location: ..\database-documentation-2026-02-22-1734
