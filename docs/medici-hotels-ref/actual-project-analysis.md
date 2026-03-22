# Actual Code Analysis - Medici Hotels
Generated: 02/22/2026 17:17:46

## Project Structure Overview
Total C# Files Found: 177
Total Projects/Directories: 23

## Projects Analysis

### ApiInstant
- **Files Count**: 41
- **Total Size**: 79377 bytes
- **Total Lines of Code**: 2060
- **Classes Found**: 62
- **Public Methods Found**: 7

**Files in Project**:
- AdultBook.cs (752 bytes)
- ApiInstant.cs (30912 bytes)
- ApiInstantZenith.cs (8487 bytes)
- Bedding.cs (623 bytes)
- Board.cs (668 bytes)
- Book.cs (835 bytes)
- BookingRequest.cs (689 bytes)
- BookRes.cs (709 bytes)
- BookResulte.cs (384 bytes)
- Cancellation.cs (2061 bytes)
- Category.cs (1124 bytes)
- Content.cs (720 bytes)
- ContentBook.cs (797 bytes)
- Currency.cs (453 bytes)
- Hotel.cs (1066 bytes)
- HotelBook.cs (972 bytes)
- InsertBook.cs (6905 bytes)
- InsertBookError.cs (1479 bytes)
- InsertPreBook.cs (7723 bytes)
- NetPriceInClientCurrency.cs (301 bytes)
- Options.cs (244 bytes)
- PaxBook.cs (485 bytes)
- Payment.cs (340 bytes)
- PaymentMethod.cs (411 bytes)
- PaymentMethodbook.cs (363 bytes)
- PaymentSettings.cs (310 bytes)
- PollHotel.cs (870 bytes)
- PreBook.cs (1677 bytes)
- PreBookRes.cs (533 bytes)
- PriceWithoutTax.cs (292 bytes)
- Reference.cs (464 bytes)
- Remarks.cs (239 bytes)
- ResultHotel.cs (1003 bytes)
- SearchCode.cs (283 bytes)
- SearchHotels.cs (1171 bytes)
- SearchHotelsResult.cs (358 bytes)
- SearchRequest.cs (550 bytes)
- ServiceBook.cs (662 bytes)
- Services.cs (932 bytes)
- Supplier.cs (242 bytes)
- TransactionFee.cs (288 bytes)


**Classes**:
- AdultBook
- ApiInstant
- ApiInstantZenith
- BarRate
- Bedding
- Board
- Book
- BookingRequest
- BookRes
- BookResulte
- Cancellation
- CancellationRes
- Category
- Client
- Contact
- Content
- ContentBook
- Currency
- Customer
- Dates
- Destination
- Error
- Filter
- Frame
- Hotel
- HotelBook
- InsertBook
- InsertBookError
- InsertPreBook
- Item
- Name
- NetPrice
- NetPriceInClientCurrency
- Options
- Pax
- PaxBook
- Payment
- PaymentMethod
- PaymentMethodbook
- PaymentSettings
- Penalty
- PollHotel
- preBook
- preBookRes
- Price
- PriceWithoutTax
- Provider
- Quantity
- Reference
- Remarks
- ResultHotel
- Room
- SearchCode
- SearchHotels
- SearchHotelsResult
- SearchRequest
- Service
- ServiceBook
- Services
- services
- Supplier
- TransactionFee

**Key Using Statements**:
- (TextReader reader = new StringReader(response.Content))
                        {
                            pushRatesRes.error = (ErrorZenith)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(response.Content))
                    {
                        pushRatesRes.envelope = (EnvelopeHotelRateAmountNotifRS)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(response.Content))
                {
                    availabilityAndRestrictionsRes.envelope = (EnvelopeHotelAvailNotifRS)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(response.Content))
                {
                    availabilityAndRestrictionsRes.error = (ErrorZenith)serializer.Deserialize(reader)
- ApiInstant.GoGlobal
- ApiInstant.Models
- Extensions
- JsonSerializer = System.Text.Json.JsonSerializer
- Newtonsoft.Json
- RestSharp
- static ApiInstant.Models.Zenith
- System
- System.Collections.Generic
- System.Diagnostics
- System.Linq
... and 8 more using statements

**Sample Methods**:
- ConvertBookRes
- ConvertInsertPreBook
- ConvertOffer
- ConvertPreBookRes
- ConvertRootBuyRoom
- preBookInnstant


---

### Attributes
- **Files Count**: 1
- **Total Size**: 1709 bytes
- **Total Lines of Code**: 44
- **Classes Found**: 1
- **Public Methods Found**: 2

**Files in Project**:
- BasicAuthenticationAttributeAction.cs (1709 bytes)


**Classes**:
- BasicAuthenticationAttributeAction

**Key Using Statements**:
- Microsoft.AspNetCore.Mvc
- Microsoft.AspNetCore.Mvc.Filters
- SharedLibrary
- SharedLibrary.Auth
- System.Web.Http.Results


**Sample Methods**:
- OnActionExecuted
- OnActionExecuting


---

### Auth
- **Files Count**: 1
- **Total Size**: 716 bytes
- **Total Lines of Code**: 21
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- UserAuthentication.cs (716 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- SharedLibrary.Models
- System
- System.Collections.Generic
- System.Linq
- System.Reflection.PortableExecutable
- System.Text
- System.Threading.Tasks


**Sample Methods**:



---

### Backend
- **Files Count**: 2
- **Total Size**: 2628 bytes
- **Total Lines of Code**: 99
- **Classes Found**: 1
- **Public Methods Found**: 0

**Files in Project**:
- BHealthCheck.cs (757 bytes)
- Program.cs (1871 bytes)


**Classes**:
- BHealthCheck

**Key Using Statements**:
- ApiInstant.Models
- Backend
- Backend.Attributes
- Backend.Hub
- EFModel.Models11
- Extensions
- IIS:
builder.Services.Configure<IISServerOptions>(options =>
{
    options.AllowSynchronousIO = true
- Microsoft.AspNetCore.Server.Kestrel.Core
- Microsoft.EntityFrameworkCore
- Microsoft.Extensions.Diagnostics.HealthChecks
- Notifications
- SharedLibrary


**Sample Methods**:



---

### Controllers
- **Files Count**: 10
- **Total Size**: 34632 bytes
- **Total Lines of Code**: 824
- **Classes Found**: 10
- **Public Methods Found**: 1

**Files in Project**:
- AuthController.cs (1933 bytes)
- BookController.cs (2555 bytes)
- ErrorsController.cs (1706 bytes)
- MiscController.cs (1080 bytes)
- NotificationsController.cs (707 bytes)
- OpportunityController.cs (3809 bytes)
- ReservationController.cs (1377 bytes)
- SalesRoomController.cs (2375 bytes)
- SearchController.cs (1267 bytes)
- ZenithApiController.cs (17823 bytes)


**Classes**:
- AuthController
- BookController
- ErrorsController
- MiscController
- NotificationsController
- OpportunityController
- ReservationController
- SalesRoomController
- SearchController
- ZenithApiController

**Key Using Statements**:
- (StreamReader r = new StreamReader("appsettings.json"))
            {
                string json = r.ReadToEnd()
- (var receiveStream = Request.Body)
            {
                using (var readStream = new StreamReader(receiveStream, Encoding.UTF8))
                {
                    return await readStream.ReadToEndAsync().ConfigureAwait(false)
- ApiInstant
- ApiInstant.Models
- Backend.Attributes
- Backend.Hub
- Backend.Models
- EFModel
- EFModel.CustomModel
- EFModel.Models11
- Extensions
- Microsoft.AspNetCore.Authorization
- Microsoft.AspNetCore.Components.Web
- Microsoft.AspNetCore.Mvc
- Microsoft.AspNetCore.SignalR
... and 15 more using statements

**Sample Methods**:
- ShowOppHome


---

### CustomModel
- **Files Count**: 27
- **Total Size**: 22341 bytes
- **Total Lines of Code**: 738
- **Classes Found**: 33
- **Public Methods Found**: 0

**Files in Project**:
- BackOfficeOppLog.cs (410 bytes)
- Book.cs (3469 bytes)
- Booking.cs (340 bytes)
- BookingBackOffice.cs (1489 bytes)
- ChangePriceBookingResult.cs (421 bytes)
- Chart.cs (542 bytes)
- GraphResponse.cs (482 bytes)
- InsertOpp.cs (1567 bytes)
- InsertOppResult.cs (443 bytes)
- MedReservationCancelHotel.cs (332 bytes)
- MedReservationModifyHotel.cs (332 bytes)
- OpportunityBackOffice.cs (930 bytes)
- OpportunityStatistics.cs (349 bytes)
- OpResult.cs (322 bytes)
- PreBook.cs (671 bytes)
- PushRoom.cs (1266 bytes)
- QueueCheckStatus.cs (243 bytes)
- ReservationBackOffice.cs (1607 bytes)
- ReservationDetails.cs (1254 bytes)
- ReservationInnstant.cs (1746 bytes)
- ReservationResponse.cs (496 bytes)
- RoomChartValue.cs (673 bytes)
- RoomGraphData.cs (317 bytes)
- SalesOrderBackOffice.cs (1544 bytes)
- SalesRoomResponse.cs (477 bytes)
- SnapshotCheckParameters.cs (329 bytes)
- UpdateNameResult.cs (290 bytes)


**Classes**:
- AdultBook
- BackOfficeOppLog
- BookBackOffice
- Booking
- BookingBackOffice
- ChangePriceBookingResult
- Chart
- Contact
- Customer
- DataContainer
- GraphResponse
- InsertOpp
- InsertOppResult
- MedReservationCancelHotel
- MedReservationModifyHotel
- Name
- OpportunityBackOffice
- OpportunityStatistics
- OpResult
- PushRoom
- ReservationBackOffice
- ReservationDetails
- ReservationInnstant
- ReservationResponse
- RoomChart
- RoomChartSeria
- RoomChartValue
- RoomGraphData
- SalesOrderBackOffice
- SalesRoomResponse
- SnapshotCheckParameters
- Source
- UpdateNameResult

**Key Using Statements**:
- EFModel.Models11
- System
- System.Collections.Generic
- System.ComponentModel.DataAnnotations
- System.Linq
- System.Reflection.PortableExecutable
- System.Text
- System.Threading.Tasks


**Sample Methods**:



---

### EFModel
- **Files Count**: 1
- **Total Size**: 194270 bytes
- **Total Lines of Code**: 4175
- **Classes Found**: 1
- **Public Methods Found**: 2

**Files in Project**:
- BaseEF.cs (194270 bytes)


**Classes**:
- BaseEF

**Key Using Statements**:
- (connection = new SqlConnection(ConnectionString))
                {
                    connection.Open()
- (SqlCommand command = connection.CreateCommand())
                            {

                                command.CommandText = "Med_InsertBookCustomerMoreInfo"
- (SqlCommand command = connection.CreateCommand())
                        {




                            var adultsLead = reservationInnstant.adults.Find(f => f.lead)
- (SqlCommand command = connection.CreateCommand())
                        {


                            command.CommandText = "MED_InsertReservationModifyCustomerName"
- (SqlCommand command = connection.CreateCommand())
                        {

                            command.CommandText = "MED_InsertBookCustomerName"
- (SqlCommand command = connection.CreateCommand())
                        {
                            command.CommandText = "MED_InsertReservationCustomerName"
- (SqlCommand command = connection.CreateCommand())
                        {
                            var adultsLead = reservationInnstant.adults.Find(f => f.lead)
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "GetFnameByOpportunityId"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_FindAvailableRoom"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_FindAvailableRoomCount"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_InsertBook"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_InsertBookError"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_InsertPreBook"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_InsertReservation"
- (SqlCommand command = connection.CreateCommand())
                    {

                        command.CommandText = "MED_InsertReservationCancel"
... and 105 more using statements

**Sample Methods**:
- GetAllPurchased
- GetAllSold


---

### Extensions
- **Files Count**: 1
- **Total Size**: 667 bytes
- **Total Lines of Code**: 23
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- SystemLog.cs (667 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- (StreamWriter sw = File.AppendText(currLogPath))
                {
                    sw.WriteLine($"{DateTime.Now} {message}")
- System.Diagnostics


**Sample Methods**:



---

### GoGlobal
- **Files Count**: 2
- **Total Size**: 36054 bytes
- **Total Lines of Code**: 848
- **Classes Found**: 34
- **Public Methods Found**: 1

**Files in Project**:
- ApiGoGlobal.cs (16723 bytes)
- GoglobalRequest.cs (19331 bytes)


**Classes**:
- ApiGoGlobal
- BodyGoglobal
- DebugError
- EnvelopeGoglobal
- ErrorBOOK
- GoBookingCodeBookingStatus
- Header
- HeaderBuyRoom
- Hotel
- Leader
- LeaderAMENDMENT
- Main
- MainAMENDMENT
- MainBookingDetails
- MainBookingStatus
- MainCancelRoom
- MakeRequestResponse
- Offer
- PersonAMENDMENT
- PersonName
- Preferences
- Room
- RoomAMENDMENT
- Rooms
- RoomsMainAMENDMENT
- RoomType
- RoomTypeAMENDMENT
- RootAMENDMENT
- RootBookingDetails
- RootBookingStatus
- RootBuyRoom
- RootCancelRoom
- SearchHotelsResponse
- Stats

**Key Using Statements**:
- (TextReader reader = new StringReader(response.Content))
                {

                    envelopeGoglobal = (EnvelopeGoglobal)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(response.Content))
            {
                envelopeGoglobal = (EnvelopeGoglobal)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(strBook))
                    {
                        rootBuyRoom = (RootCancelRoom)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(strBook))
                {

                    rootBuyRoom = (RootBuyRoom)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(strBook))
            {

                envelopeGoglobal = (EnvelopeGoglobal)serializer.Deserialize(reader)
- ApiInstant.Models
- Extensions
- RestSharp
- System
- System.Collections.Generic
- System.Diagnostics
- System.Linq
- System.Text
- System.Text.Json
- System.Threading.Tasks
... and 1 more using statements

**Sample Methods**:
- OfferToResultHotel


---

### Hub
- **Files Count**: 2
- **Total Size**: 383 bytes
- **Total Lines of Code**: 19
- **Classes Found**: 1
- **Public Methods Found**: 0

**Files in Project**:
- IMessageHubClient.cs (124 bytes)
- MessageHub.cs (259 bytes)


**Classes**:
- MessageHub

**Key Using Statements**:
- Microsoft.AspNetCore.SignalR


**Sample Methods**:



---

### MediciAutoCancellation
- **Files Count**: 2
- **Total Size**: 4381 bytes
- **Total Lines of Code**: 95
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- MainLogic.cs (3824 bytes)
- Program.cs (557 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- ApiInstant
- ApiInstant.Models
- Extensions
- MediciAutoCancellation
- Microsoft.Extensions.Configuration
- Notifications
- SharedLibrary
- System
- System.Collections.Generic
- System.Linq
- System.Text
- System.Threading.Tasks


**Sample Methods**:



---

### MediciBuyRooms
- **Files Count**: 2
- **Total Size**: 9017 bytes
- **Total Lines of Code**: 197
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- MainLogic.cs (8666 bytes)
- Program.cs (351 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- ApiInstant
- Azure.Core
- Extensions
- MediciBuyRooms
- Microsoft.Extensions.Configuration
- SharedLibrary
- System
- System.Collections.Generic
- System.Linq
- System.Text
- System.Threading.Tasks


**Sample Methods**:



---

### Models
- **Files Count**: 24
- **Total Size**: 62966 bytes
- **Total Lines of Code**: 1976
- **Classes Found**: 136
- **Public Methods Found**: 2

**Files in Project**:
- BookingCancel.cs (402 bytes)
- BookingCancelRes.cs (752 bytes)
- ContentBookingCancelRes.cs (528 bytes)
- OTA_HotelResNotifRQ.cs (30505 bytes)
- SearchHotelsResultsSession.cs (494 bytes)
- Zenith.cs (18404 bytes)
- Credentials.cs (345 bytes)
- SearchHotelRequest.cs (250 bytes)
- XmlActionResult.cs (2318 bytes)
- CellData.cs (237 bytes)
- ProblemReason.cs (405 bytes)
- ProblemRecord.cs (864 bytes)
- AppSettings.cs (615 bytes)
- AuthResponse.cs (468 bytes)
- LoginAttempt.cs (312 bytes)
- ReservationFullName.cs (278 bytes)
- VersionResponse.cs (273 bytes)
- WebsiteUser.cs (578 bytes)
- HotelToolsSearchRequest.cs (2129 bytes)
- HotelToolsSettings.cs (272 bytes)
- InnstantRecord.cs (850 bytes)
- InnstantSearchRequest.cs (424 bytes)
- ProblemReason.cs (401 bytes)
- ProblemRecord.cs (862 bytes)


**Classes**:
- AcceptedPayment
- AcceptedPayments
- Address
- AddressInfo
- AmountPercent
- AppSettings
- AuthResponse
- AvailabilityAndRestrictionsRes
- Base
- BaseByGuestAmt
- BaseByGuestAmts
- BasicPropertyInfo
- Body
- BodyError
- BodyHotelAvailNotifRS
- BodyHotelAvailRS
- BodyHotelRateAmountNotifRS
- BodyOTA_HotelRateAmountNotifRQ
- BodyRes
- BookingCancel
- BookingCancelRes
- BookingChannel
- Comment
- Comments
- Commission
- CommissionPayableAmount
- CompanyInfo
- CompanyName
- ConnectionStrings
- ContentBookingCancelRes
- Customer
- DepositPayments
- Envelope
- EnvelopeError
- EnvelopeHotelAvailNotifRS
- EnvelopeHotelAvailRS
- EnvelopeHotelRateAmountNotifRS
- EnvelopeOTAHotelRateAmountNotifRQ
- EnvelopeRes
- Envelopetest
- Error
- ErrorLogin
- ErrorNotif
- Errors
- ErrorsNotif
- ErrorZenith
- GetRoomsRes
- Guarantee
- GuaranteeAccepted
- GuaranteePayment
- GuaranteesAccepted
- GuestCount
- GuestCounts
- Header
- HotelReservation
- HotelReservationID
- HotelReservationIDs
- HotelReservations
- HotelToolsSearchRequest
- InnstantRecord
- InnstantSearchRequest
- LoginAttempt
- LoginCredentials
- OTA_HotelAvailNotifRS
- OTA_HotelAvailRS
- OTA_HotelRateAmountNotifRQ
- OTA_HotelRateAmountNotifRS
- OTAHotelAvailNotifRS
- OTAHotelResNotifRQ
- OTAHotelResNotifRS
- Password
- PaymentCard
- PersonName
- POS
- PriceXML
- Profile
- ProfileInfo
- Profiles
- PushAvailabilityAndRestrictionsResRequest
- PushRatesRequest
- PushRatesRes
- Rate
- RateAmountMessage
- RateAmountMessages
- RateDescription
- RatePlan
- RatePlans
- Rates
- RequestorID
- ReservationFullName
- ResGlobalInfo
- ResGuest
- ResGuestRPH
- ResGuestRPHs
- ResGuests
- Results
- RoomDescription
- RoomRate
- RoomRates
- RoomStay
- RoomStays
- RoomType
- RoomTypes
- SearchHotelRequest
- SearchHotelsResultsSession
- Security
- Service
- ServiceRPH
- ServiceRPHs
- Services
- SourceSwich
- SpecialRequest
- SpecialRequests
- StatusApplicationControl
- Tax
- Taxes
- Telephone
- TelephoneInfo
- ThreeDomainSecurity
- TimeSpanRoom
- Total
- TPAExtensions
- UniqueID
- UsernameToken
- VersionResponse
- VirtualCreditCard
- WebsiteUser
- XmlActionResult
- Zenith

**Key Using Statements**:
- (var writer = new StreamWriter(context.HttpContext.Response.Body))
                //{
                //    await writer.WriteAsync(this.objectToSerialize.ToString())
- Microsoft.AspNetCore.Mvc
- System
- System.Collections.Generic
- System.ComponentModel.DataAnnotations
- System.Linq
- System.Net.Http.Headers
- System.Reflection.PortableExecutable
- System.Runtime
- System.Text
- System.Threading.Tasks
- System.Xml.Serialization


**Sample Methods**:
- CellData
- HotelToolsSettings


---

### Models11
- **Files Count**: 40
- **Total Size**: 51752 bytes
- **Total Lines of Code**: 1785
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- BackOfficeOpt.cs (799 bytes)
- BackOfficeOptLog.cs (313 bytes)
- Basic.cs (503 bytes)
- MedBoard.cs (256 bytes)
- MedBook.cs (2216 bytes)
- MedBookCustomerMoreInfo.cs (724 bytes)
- MedBookCustomerName.cs (390 bytes)
- MedBookError.cs (474 bytes)
- MedCancelBook.cs (458 bytes)
- MedCancelBookError.cs (450 bytes)
- MedCurrency.cs (265 bytes)
- MedCustomerFname.cs (213 bytes)
- MedCustomerLname.cs (213 bytes)
- MedCustomersReservation.cs (630 bytes)
- MedHotel.cs (606 bytes)
- MedHotelRate.cs (247 bytes)
- MedHotelsInstant.cs (437 bytes)
- MedHotelsRatebycat.cs (402 bytes)
- MedHotelsToPush.cs (427 bytes)
- MedHotelsToSearch.cs (253 bytes)
- MediciContext.cs (27782 bytes)
- MedLog.cs (243 bytes)
- MedOPportunity.cs (1520 bytes)
- MedPreBook.cs (1777 bytes)
- MedReservation.cs (1334 bytes)
- MedReservationCancel.cs (1295 bytes)
- MedReservationCustomerMoreInfo.cs (778 bytes)
- MedReservationCustomerName.cs (449 bytes)
- MedReservationModify.cs (1295 bytes)
- MedReservationModifyCustomerMoreInfo.cs (786 bytes)
- MedReservationModifyCustomerName.cs (499 bytes)
- MedReservationNotificationLog.cs (284 bytes)
- MedRoomBedding.cs (259 bytes)
- MedRoomCategory.cs (305 bytes)
- MedRoomConfirmation.cs (269 bytes)
- MedSearchHotel.cs (1069 bytes)
- MedSource.cs (247 bytes)
- MedUser.cs (265 bytes)
- Queue.cs (779 bytes)
- Tprice.cs (241 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- Microsoft.EntityFrameworkCore
- System
- System.Collections.Generic


**Sample Methods**:



---

### ModelsLibrary
- **Files Count**: 1
- **Total Size**: 274 bytes
- **Total Lines of Code**: 14
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- IRollbackResponce.cs (274 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- System
- System.Collections.Generic
- System.Linq
- System.Text
- System.Threading.Tasks


**Sample Methods**:



---

### Notifications
- **Files Count**: 1
- **Total Size**: 2806 bytes
- **Total Lines of Code**: 82
- **Classes Found**: 1
- **Public Methods Found**: 0

**Files in Project**:
- BaseNotifications.cs (2806 bytes)


**Classes**:
- BaseNotifications

**Key Using Statements**:
- Extensions
- SendGrid
- SendGrid.Helpers.Mail
- Twilio
- Twilio.Rest.Api.V2010.Account


**Sample Methods**:



---

### ProcessRevisedFile
- **Files Count**: 2
- **Total Size**: 3069 bytes
- **Total Lines of Code**: 79
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- ProcessCommon.cs (2681 bytes)
- Program.cs (388 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- (var reader = new StreamReader(fileName))
            using (var csv = new CsvReader(reader, CultureInfo.InvariantCulture))
            {
                var records = csv.GetRecords<ProblemRecord>()
- ApiInstant
- ApiInstant.GoGlobal
- CsvHelper
- EFModel.CustomModel
- EFModel.Models11
- Extensions
- Microsoft.Extensions.Configuration
- ProcessRevisedFile
- ProcessRevisedFile.Models
- SharedLibrary
- System
- System.Collections.Generic
- System.Formats.Asn1
- System.Globalization
... and 4 more using statements

**Sample Methods**:



---

### SharedLibrary
- **Files Count**: 9
- **Total Size**: 84448 bytes
- **Total Lines of Code**: 1888
- **Classes Found**: 6
- **Public Methods Found**: 3

**Files in Project**:
- APIGoGlobal.cs (11078 bytes)
- ApiInnstant.cs (7639 bytes)
- ApiMedici.cs (4284 bytes)
- BuyRoomControl.cs (5958 bytes)
- Caching.cs (2538 bytes)
- Common.cs (2286 bytes)
- MachineUniqueId.cs (1227 bytes)
- PushRoomControl.cs (29059 bytes)
- Repository.cs (20379 bytes)


**Classes**:
- ApiMedici
- BuyRoomControl
- Common
- MachineUniqueId
- PushRoomControl
- Repository

**Key Using Statements**:
- (StreamReader r = new StreamReader("appsettings.json"))
            {
                string json = r.ReadToEnd()
- (TextReader reader = new StringReader(response.Content))
                {

                    envelopeGoglobal = (EnvelopeGoglobal)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(strBook))
                {
                    rootBookingStatus = (RootBookingStatus)serializer.Deserialize(reader)
- (TextReader reader = new StringReader(strBook))
                {
                    rootRootAMENDMENT = (RootAMENDMENT)serializer.Deserialize(reader)
- (var reader = new StreamReader(fileName))
                using (var csv = new CsvReader(reader, CultureInfo.InvariantCulture))
                {
                    var items = csv.GetRecords<CellData>().ToList()
- (var writer = new StreamWriter(fileName))
                using (var csv = new CsvWriter(writer, CultureInfo.InvariantCulture))
                {
                    csv.WriteRecords(data)
- ApiInstant
- ApiInstant.GoGlobal
- ApiInstant.Models
- Azure
- Azure.Core
- CsvHelper
- EFModel
- EFModel.CustomModel
- EFModel.Models11
... and 21 more using statements

**Sample Methods**:
- Basicvalidity
- ValidCancellation
- ValidDates


---

### SlackLibrary
- **Files Count**: 1
- **Total Size**: 987 bytes
- **Total Lines of Code**: 34
- **Classes Found**: 1
- **Public Methods Found**: 0

**Files in Project**:
- SlackCommon.cs (987 bytes)


**Classes**:
- SlackCommon

**Key Using Statements**:
- Extensions
- System.Text
- System.Text.Json


**Sample Methods**:



---

### WebHotel
- **Files Count**: 2
- **Total Size**: 8830 bytes
- **Total Lines of Code**: 231
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- Common.cs (3897 bytes)
- Program.cs (4933 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- ApiInstant
- ApiInstant.GoGlobal
- EFModel.CustomModel
- EFModel.Models11
- Extensions
- Microsoft.Extensions.Configuration
- ModelsLibrary.Models
- SharedLibrary
- SlackLibrary
- System
- System.Collections.Generic
- System.Linq
- System.Text
- System.Text.Json
- System.Threading.Tasks
... and 4 more using statements

**Sample Methods**:



---

### WebHotelLib
- **Files Count**: 1
- **Total Size**: 32054 bytes
- **Total Lines of Code**: 875
- **Classes Found**: 1
- **Public Methods Found**: 0

**Files in Project**:
- WebDriverProccessing.cs (32054 bytes)


**Classes**:
- WebDriverProccessing

**Key Using Statements**:
- Extensions
- HtmlAgilityPack
- ModelsLibrary.Models
- OpenQA.Selenium
- OpenQA.Selenium.Chrome
- OpenQA.Selenium.Edge
- OpenQA.Selenium.Firefox
- OpenQA.Selenium.Support.UI
- System
- System.Collections
- System.Collections.Generic
- System.ComponentModel.DataAnnotations
- System.Diagnostics
- System.Globalization
- System.Linq
... and 4 more using statements

**Sample Methods**:



---

### WebHotelRevise
- **Files Count**: 2
- **Total Size**: 18915 bytes
- **Total Lines of Code**: 349
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- Program.cs (844 bytes)
- ReviseCommon.cs (18071 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- (var writer = new StreamWriter(fileDir))
            using (var csv = new CsvWriter(writer, CultureInfo.InvariantCulture))
            {
                await csv.WriteRecordsAsync(problemRecords)
- ApiInstant
- ApiInstant.GoGlobal
- CsvHelper
- EFModel.CustomModel
- Extensions
- Microsoft.Extensions.Configuration
- ModelsLibrary.Models
- SharedLibrary
- SharedLibrary.Models
- System
- System.Collections.Generic
- System.Formats.Asn1
- System.Globalization
- System.Linq
... and 6 more using statements

**Sample Methods**:



---

### WebInnstant
- **Files Count**: 2
- **Total Size**: 2596 bytes
- **Total Lines of Code**: 71
- **Classes Found**: 0
- **Public Methods Found**: 0

**Files in Project**:
- Common.cs (1906 bytes)
- Program.cs (690 bytes)


**Classes**:
- No classes found

**Key Using Statements**:
- (var writer = new StreamWriter(fileDir))
            using (var csv = new CsvWriter(writer, CultureInfo.InvariantCulture))
            {
                await csv.WriteRecordsAsync(items)
- CsvHelper
- Extensions
- Microsoft.Extensions.Configuration
- System
- System.Collections.Generic
- System.Formats.Asn1
- System.Globalization
- System.Linq
- System.Text
- System.Threading.Tasks
- WebHotelLib
- WebHotelLib.Models
- WebInnstant


**Sample Methods**:



---

