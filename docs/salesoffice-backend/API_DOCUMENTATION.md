# Medici Hotels - API Documentation

> **ChatGPT API v1** (OpenAPI 3.0)  
> 17 Endpoints | 11 Schemas  
> Base URL: https://medici-backend.azurewebsites.net  
> Last Updated: January 13, 2026

---

## 🌐 API Overview

| Property | Value |
|----------|-------|
| API Title | ChatGPT API |
| Version | v1 |
| OpenAPI Version | 3.0.4 |
| Base URL | https://medici-backend.azurewebsites.net |
| Swagger UI | /swagger/index.html |
| Swagger JSON | /swagger/v1/swagger.json |
| Authentication | Basic Authentication |

---

## 📋 All Endpoints Summary

| Method | Endpoint | Description | Node.js Status |
|--------|----------|-------------|----------------|
| POST | `/api/auth/OnlyNightUsersTokenAPI` | Get authentication token | ⚠️ Different path |
| POST | `/api/hotels/GetInnstantSearchPrice` | Search Innstant prices | ❌ Missing |
| POST | `/api/hotels/GetRoomsActive` | Get active rooms | ⚠️ Different path |
| POST | `/api/hotels/GetRoomsSales` | Get room sales | ⚠️ Different path |
| POST | `/api/hotels/GetRoomsCancel` | Get cancelled rooms | ⚠️ Different path |
| POST | `/api/hotels/GetDashboardInfo` | Get dashboard info | ❌ Missing |
| POST | `/api/hotels/GetOpportunities` | Get opportunities | ⚠️ Different path |
| POST | `/api/hotels/InsertOpportunity` | Create opportunity | ⚠️ Different path |
| POST | `/api/hotels/UpdateRoomsActivePushPrice` | Update push price | ⚠️ Different path |
| DELETE | `/api/hotels/CancelRoomActive` | Cancel active room | ⚠️ Different path |
| POST | `/api/hotels/GetRoomArchiveData` | Get archive data | ❌ Missing |
| POST | `/api/hotels/GetOpportiunitiesByBackOfficeId` | Get by BackOffice ID | ❌ Missing |
| POST | `/api/hotels/GetOpportiunitiesHotelSearch` | Search opportunities | ❌ Missing |
| POST | `/api/hotels/ManualBook` | Manual booking | ❌ Missing |
| POST | `/api/hotels/PreBook` | Pre-booking | ❌ Missing |
| POST | `/api/hotels/Book` | Confirm booking | ❌ Missing |
| DELETE | `/api/hotels/CancelRoomDirectJson` | Cancel room (JSON) | ❌ Missing |

---

## 🔐 Authentication

### POST /api/auth/OnlyNightUsersTokenAPI

Get authentication token for API access.

**Request (multipart/form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| client_secret | string | Yes | API client secret |

---

## 📊 Data Schemas

### InsertOpp (Create Opportunity)

```typescript
interface InsertOpp {
  hotelId?: number;           // Hotel ID
  startDateStr: string;       // Min: 1, Max: 50 chars (required)
  endDateStr: string;         // Min: 1, Max: 50 chars (required)
  boardId: number;            // Min: 1 (required)
  categoryId: number;         // Min: 1 (required)
  buyPrice: number;           // Min: 1, Max: 10000 (required)
  pushPrice: number;          // Min: 1, Max: 10000 (required)
  maxRooms: number;           // Min: 1, Max: 30 (required)
  ratePlanCode?: string;      // Rate plan code
  invTypeCode?: string;       // Inventory type code
  reservationFullName?: string; // Max: 500 chars
  stars?: number;             // Hotel stars
  destinationId?: number;     // Destination ID
  locationRange?: number;     // Location range
  providerId?: number;        // Provider ID
  userId?: number;            // User ID
  paxAdults?: number;         // Number of adults
  paxChildren?: number[];     // Children ages array
}
```

### ApiInnstantSearchPrice (Search Request)

```typescript
interface ApiInnstantSearchPrice {
  dateFrom: string;           // Check-in date (required)
  dateTo: string;             // Check-out date (required)
  hotelName?: string;         // Hotel name filter
  city?: string;              // City filter
  pax?: Pax[];                // Passengers array
  stars?: number;             // Hotel stars filter
  limit?: number;             // Results limit
  showExtendedData?: boolean; // Show extended data
}
```

### Pax (Passenger Info)

```typescript
interface Pax {
  adults?: number;            // Number of adults
  children?: number[];        // Array of children ages
}
```

### RoomsActiveApiParams (Room Filters)

```typescript
interface RoomsActiveApiParams {
  startDate?: Date;           // Filter start date
  endDate?: Date;             // Filter end date
  hotelName?: string;         // Hotel name filter
  hotelStars?: number;        // Stars filter
  city?: string;              // City filter
  roomBoard?: string;         // Board type filter
  roomCategory?: string;      // Category filter
  provider?: string;          // Provider filter
}
```

### DashboardApiParams

```typescript
interface DashboardApiParams {
  hotelStars?: number;        // Hotel stars filter
  city?: string;              // City filter
  hotelName?: string;         // Hotel name filter
  reservationMonthDate?: Date; // Reservation month
  checkInMonthDate?: Date;    // Check-in month
  provider?: string;          // Provider filter
}
```

### RoomArchiveFilterDto (Archive Filters)

```typescript
interface RoomArchiveFilterDto {
  stayFrom?: Date;            // Stay from date
  stayTo?: Date;              // Stay to date
  hotelName?: string;         // Hotel name
  minPrice?: number;          // Minimum price
  maxPrice?: number;          // Maximum price
  city?: string;              // City
  roomBoard?: string;         // Board type
  roomCategory?: string;      // Room category
  minUpdatedAt?: Date;        // Min update date
  maxUpdatedAt?: Date;        // Max update date
  pageNumber?: number;        // Page number
  pageSize?: number;          // Page size
}
```

### ApiBooking (Price Update)

```typescript
interface ApiBooking {
  preBookId?: number;         // PreBook ID
  pushPrice?: number;         // New push price
}
```

### BookParams (Booking Request)

```typescript
interface BookParams {
  jsonRequest?: string;       // JSON request payload
}
```

### ManualBookParams

```typescript
interface ManualBookParams {
  opportiunityId?: number;    // Opportunity ID
  code?: string;              // Booking code
}
```

---

## 📡 Endpoint Details

### Room Management

| Endpoint | Description |
|----------|-------------|
| `POST /api/hotels/GetRoomsActive` | Get all active (purchased) rooms |
| `POST /api/hotels/GetRoomsSales` | Get sold rooms |
| `POST /api/hotels/GetRoomsCancel` | Get cancelled rooms |
| `DELETE /api/hotels/CancelRoomActive` | Cancel a room by prebookId |
| `POST /api/hotels/GetRoomArchiveData` | Get historical room data |

### Opportunity Management

| Endpoint | Description |
|----------|-------------|
| `POST /api/hotels/GetOpportunities` | List all opportunities |
| `POST /api/hotels/InsertOpportunity` | Create new opportunity |
| `POST /api/hotels/GetOpportiunitiesByBackOfficeId` | Get by BackOffice ID |
| `POST /api/hotels/GetOpportiunitiesHotelSearch` | Search opportunities |

### Booking Operations

| Endpoint | Description |
|----------|-------------|
| `POST /api/hotels/PreBook` | Create pre-booking |
| `POST /api/hotels/Book` | Confirm booking |
| `POST /api/hotels/ManualBook` | Manual booking by code |
| `DELETE /api/hotels/CancelRoomDirectJson` | Cancel with JSON |

### Price & Search

| Endpoint | Description |
|----------|-------------|
| `POST /api/hotels/GetInnstantSearchPrice` | Search Innstant API |
| `POST /api/hotels/UpdateRoomsActivePushPrice` | Update push price |
| `POST /api/hotels/GetDashboardInfo` | Dashboard statistics |

---

## 📝 Example Requests

### Create Opportunity

```http
POST /api/hotels/InsertOpportunity
Content-Type: application/json

{
  "hotelId": 12345,
  "startDateStr": "2024-03-01",
  "endDateStr": "2024-03-05",
  "boardId": 2,
  "categoryId": 1,
  "buyPrice": 100.00,
  "pushPrice": 150.00,
  "maxRooms": 5,
  "paxAdults": 2
}
```

### Search Innstant Prices

```http
POST /api/hotels/GetInnstantSearchPrice
Content-Type: application/json

{
  "dateFrom": "2024-03-01",
  "dateTo": "2024-03-05",
  "city": "Barcelona",
  "stars": 4,
  "pax": [{ "adults": 2, "children": [] }],
  "limit": 10
}
```

### Cancel Room

```http
DELETE /api/hotels/CancelRoomActive?prebookId=12345
```

### Update Push Price

```http
POST /api/hotels/UpdateRoomsActivePushPrice
Content-Type: application/json

{
  "preBookId": 12345,
  "pushPrice": 175.00
}
```

---

## 🔄 Node.js Backend Mapping

### Current Implementation vs Original API

| Original .NET Endpoint | Node.js Equivalent | Status |
|------------------------|-------------------|--------|
| `POST /api/auth/OnlyNightUsersTokenAPI` | `POST /sign-in` | ⚠️ Different |
| `POST /api/hotels/GetOpportunities` | `GET /Opportunity/Opportunities` | ⚠️ Different |
| `POST /api/hotels/InsertOpportunity` | `POST /Opportunity/InsertOpp` | ⚠️ Different |
| `POST /api/hotels/GetRoomsActive` | `GET /Book/Bookings` | ⚠️ Different |
| `POST /api/hotels/GetRoomsSales` | `GET /SalesRoom/Reservations` | ⚠️ Different |
| `POST /api/hotels/GetRoomsCancel` | `GET /Book/Canceled` | ⚠️ Different |
| `DELETE /api/hotels/CancelRoomActive` | `DELETE /Book/CancelBooking` | ⚠️ Different |
| `POST /api/hotels/UpdateRoomsActivePushPrice` | `POST /Book/UpdatePrice` | ⚠️ Different |
| `POST /api/hotels/GetInnstantSearchPrice` | ❌ | Missing |
| `POST /api/hotels/GetDashboardInfo` | ❌ | Missing |
| `POST /api/hotels/GetRoomArchiveData` | ❌ | Missing |
| `POST /api/hotels/PreBook` | ❌ | Missing |
| `POST /api/hotels/Book` | ❌ | Missing |
| `POST /api/hotels/ManualBook` | ❌ | Missing |

---

*Generated: January 13, 2026*

