# 🏨 **Medici Hotels Booking Engine - API Documentation**
**Version:** 13.11.00  
**Last Updated:** February 23, 2026  
**Base URL:** `https://[your-domain]/api`

---

## 📋 **Table of Contents**
1. [Authentication](#authentication)
2. [API Overview](#api-overview)
3. [Swagger Interface](#swagger-interface)
4. [Authentication Endpoints](#auth-endpoints)
5. [Booking Management](#booking-management)
6. [Search & Availability](#search-availability)
7. [Reservation Management](#reservation-management)
8. [Sales & Revenue](#sales-revenue)
9. [Opportunity Management](#opportunity-management)
10. [Error Handling](#error-handling)
11. [Notifications](#notifications)
12. [Zenith Integration](#zenith-integration)
13. [Response Formats](#response-formats)
14. [Error Codes](#error-codes)
15. [Rate Limiting](#rate-limiting)

---

## 🔐 **authentication** {#authentication}

### **Authentication Methods**
- **Basic Authentication:** Header-based username:password (Base64 encoded)
- **Anonymous Access:** For specific Zenith API endpoints only

### **Authorization Header Format**
```http
Authorization: Basic [Base64-encoded-credentials]
```

**Example:**
```bash
# Credentials: user@example.com:password123
Authorization: Basic dXNlckBleGFtcGxlLmNvbTpwYXNzd29yZDEyMw==
```

---

## 📊 **API Overview** {#api-overview}

### **Base Configuration**
- **Protocol:** HTTPS (recommended) / HTTP
- **Content-Type:** `application/json` (default) / `text/xml` (Zenith endpoints)
- **CORS:** Enabled for all origins
- **Rate Limiting:** Basic throttling for security

### **Available Controllers**
| Controller | Purpose | Auth Required | Base Path |
|------------|---------|---------------|-----------|
| AuthController | User authentication | No | `/sign-in` |
| BookController | Booking management | Yes | `/Book/` |
| SearchController | Hotel search | Yes | `/Search/` |
| ReservationController | Reservation management | Yes | `/Reservation/` |
| SalesRoomController | Sales & revenue tracking | Yes | `/SalesRoom/` |
| OpportunityController | Opportunity management | Yes | `/Opportunity/` |
| ErrorsController | Error logs & monitoring | Yes | `/Errors/` |
| NotificationsController | Real-time notifications | No | `/api/Notifications/` |
| ZenithApiController | Zenith API integration | Mixed | `/ZenithApi/` |
| MiscController | Utility functions | No | `/Misc/` |

---

## 🌐 **Swagger Interface** {#swagger-interface}

### **Access Swagger UI**
**Development Environment Only:**
```
GET https://[your-domain]/swagger
```

### **OpenAPI Specification**
```
GET https://[your-domain]/swagger/v1/swagger.json
```

**Real-time API testing available through Swagger UI with:**
- Interactive endpoint testing
- Request/response examples
- Schema documentation
- Authentication testing

---

## 🔑 **Authentication Endpoints** {#auth-endpoints}

### **🔐 User Sign-In**
**Authenticate user and receive authorization token**

```http
POST /sign-in
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Success Response (200 OK):**
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "role": "admin"
  },
  "url": "/dashboards/finance",
  "authorization": "dXNlckBleGFtcGxlLmNvbTpwYXNzd29yZA=="
}
```

**Error Response (401 Unauthorized):**
```json
{
  "error": "Invalid credentials",
  "code": 401
}
```

**Rate Limiting:**
- Max 5 failed attempts per email
- 10-minute lockout after 5 failures

---

## 📖 **Booking Management** {#booking-management}

### **🏨 Get All Bookings**
```http
GET /Book/Bookings?force=false
Authorization: Basic [credentials]
```

**Parameters:**
- `force` (boolean, optional): Bypass cache, default: false

**Response:**
```json
{
  "bookings": [
    {
      "id": 123,
      "hotelId": 842332,
      "guestName": "John Doe",
      "checkIn": "2026-03-15",
      "checkOut": "2026-03-17",
      "status": "confirmed",
      "price": 450.00,
      "currency": "USD"
    }
  ],
  "total": 1
}
```

### **❌ Cancel Booking**
```http
DELETE /Book/CancelBooking?id=123
Authorization: Basic [credentials]
```

**Response:**
```json
{
  "success": true,
  "message": "Booking canceled successfully",
  "cancelationId": "CANC-789"
}
```

### **💰 Update Booking Price**
```http
POST /Book/UpdatePrice
Authorization: Basic [credentials]
Content-Type: application/json
```

**Request Body:**
```json
{
  "preBookId": 123,
  "pushPrice": 395.00
}
```

**Response:**
```json
{
  "result": [
    {
      "name": "Push Rates",
      "result": "Success"
    },
    {
      "name": "Push Availability And Restrictions", 
      "result": "Success"
    }
  ],
  "booking": [
    {
      "preBookId": 123,
      "pushPrice": 395.00
    }
  ]
}
```

### **📋 Get Canceled Bookings**
```http
GET /Book/Canceled?force=false
Authorization: Basic [credentials]
```

---

## 🔍 **Search & Availability** {#search-availability}

### **🏨 Search Hotels**
```http
POST /Search/Search
Authorization: Basic [credentials]
Content-Type: application/json
```

**Request Body:**
```json
{
  "dateFrom": "2026-03-15",
  "dateTo": "2026-03-17", 
  "hotelId": 842332
}
```

**Response:**
```json
{
  "results": [
    {
      "hotelId": 842332,
      "hotelName": "citizenM Miami Brickell",
      "dates": {
        "from": "2026-03-15",
        "to": "2026-03-17"
      },
      "price": {
        "amount": 450.00,
        "currency": "USD"
      },
      "cancellation": {
        "type": "fully-refundable",
        "deadline": "2026-03-14T18:00:00Z"
      },
      "availability": "available"
    }
  ],
  "query": {
    "dateFrom": "2026-03-15",
    "dateTo": "2026-03-17",
    "hotelId": 842332
  }
}
```

---

## 🏨 **Reservation Management** {#reservation-management}

### **📋 Get Reservation Logs**
```http
GET /Reservation/Log
Authorization: Basic [credentials]
```

### **📝 Get Reservation Details**
```http
GET /Reservation/GetDetails?soldId=123
Authorization: Basic [credentials]
```

**Response:**
```json
{
  "newOrder": {
    "id": 123,
    "hotelName": "citizenM Miami Brickell",
    "givenName": "John",
    "surname": "Doe",
    "email": "john.doe@example.com",
    "dateInsert": "2026-02-23T10:30:00"
  },
  "oldOrders": [
    {
      "id": 122,
      "source": "InnstantTravel",
      "preBookId": 456,
      "givenName": "John",
      "surname": "Doe"
    }
  ]
}
```

### **🔄 Get Reservation Modifications**
```http
GET /Reservation/ReservationModify?force=false
Authorization: Basic [credentials]
```

### **❌ Get Reservation Cancellations**
```http
GET /Reservation/ReservationCancel?force=false
Authorization: Basic [credentials]
```

---

## 💰 **Sales & Revenue** {#sales-revenue}

### **📊 Get All Sales**
```http
GET /SalesRoom/Sales?force=false
Authorization: Basic [credentials]
```

### **🏨 Get All Reservations**
```http
GET /SalesRoom/Reservations?force=false
Authorization: Basic [credentials]
```

### **💳 Get Purchased Items**
```http
GET /SalesRoom/Purchased?force=false
Authorization: Basic [credentials]
```

### **✅ Get Sold Items**
```http
GET /SalesRoom/Sold?force=false
Authorization: Basic [credentials]
```

### **📋 Get Sales Room Details**
```http
GET /SalesRoom/GetDetails?id=123
Authorization: Basic [credentials]
```

### **✏️ Update Name Success Status**
```http
POST /SalesRoom/UpdateNameSuccess
Authorization: Basic [credentials]
Content-Type: application/json
```

**Request Body:**
```json
{
  "id": 123,
  "result": 2
}
```

---

## 🎯 **Opportunity Management** {#opportunity-management}

### **➕ Insert New Opportunity**
```http
POST /Opportunity/InsertOpp
Authorization: Basic [credentials]
Content-Type: application/json
```

**Request Body:**
```json
{
  "hotelId": 842332,
  "startDateStr": "2026-03-15",
  "endDateStr": "2026-03-17",
  "categoryId": 1,
  "boardId": 1,
  "maxRooms": 10,
  "buyPrice": 200.00,
  "pushPrice": 450.00,
  "invTypeCode": "ROOM",
  "ratePlanCode": "STD",
  "reservationFullName": "John Doe"
}
```

**Response:**
```json
{
  "id": 456,
  "startDate": "2026-03-15T00:00:00",
  "endDate": "2026-03-17T00:00:00",
  "dateInsert": "2026-02-23T10:30:00",
  "roomToPurchase": 20
}
```

### **❌ Cancel Opportunity**
```http
GET /Opportunity/CancelOpp?oppId=456
Authorization: Basic [credentials]
```

### **📊 Get Opportunity Statistics**
```http
GET /Opportunity/Statistics?id=456
Authorization: Basic [credentials]
```

### **📋 Get Opportunity Logs**
```http
GET /Opportunity/Logs?id=456
Authorization: Basic [credentials]
```

---

## ⚠️ **Error Handling** {#error-handling}

### **📋 Get Booking Errors**
```http
GET /Errors/BookErrors
Authorization: Basic [credentials]
```

**Response:**
```json
{
  "errors": [
    {
      "id": 1,
      "preBookId": 123,
      "dateInsert": "2026-02-23T10:30:00",
      "error": "Payment processing failed",
      "code": "PAYMENT_ERROR",
      "requestJson": "{...}",
      "responseJson": "{...}"
    }
  ]
}
```

### **❌ Get Cancellation Errors**
```http
GET /Errors/CancelBookErrors
Authorization: Basic [credentials]
```

### **🔍 Get Specific Cancel Error**
```http
GET /Errors/GetCancelBookError?preBookId=123
Authorization: Basic [credentials]
```

---

## 🔔 **Notifications** {#notifications}

### **📨 Send Notification**
```http
POST /api/Notifications/SendNotification?msg=Hello
```

**Real-time notifications via SignalR Hub:**
```javascript
// JavaScript client example
const connection = new signalR.HubConnectionBuilder()
    .withUrl("https://[your-domain]/notifications")
    .build();

connection.on("Notify", function (message) {
    console.log("Notification:", message);
});
```

---

## 🔗 **Zenith Integration** {#zenith-integration}

### **🧪 Test Email (Zenith)**
```http
GET /ZenithApi/TestEmail
```

### **📱 Test SMS (Zenith)**
```http
GET /ZenithApi/TestSms
```

### **👋 Health Check (Zenith)**
```http
GET /ZenithApi/HelloZenith
```

**Response:**
```json
"ZenithApi Ok"
```

### **🏨 Reservation Webhook (Zenith)**
```http
POST /ZenithApi/reservation
Content-Type: text/xml
```

**XML Request Body (OTA Format):**
```xml
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
    <SOAP-ENV:Body>
        <OTA_HotelResNotifRQ>
            <!-- OTA Hotel Reservation Notification -->
        </OTA_HotelResNotifRQ>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

---

## 📜 **Response Formats** {#response-formats}

### **Standard Success Response**
```json
{
  "data": { /* response data */ },
  "success": true,
  "timestamp": "2026-02-23T10:30:00Z"
}
```

### **Standard Error Response**
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": { /* additional error context */ }
  },
  "success": false,
  "timestamp": "2026-02-23T10:30:00Z"
}
```

---

## 🚨 **Error Codes** {#error-codes}

| Code | HTTP Status | Description |
|------|-------------|-------------|
| 200 | 200 OK | Success |
| 400 | 400 Bad Request | Invalid request parameters |
| 401 | 401 Unauthorized | Authentication required |
| 402 | 402 Payment Required | XML parsing error (Zenith) |
| 448 | 400 Bad Request | System error (Zenith) |
| 404 | 404 Not Found | Resource not found |
| 500 | 500 Internal Server Error | Server error |

---

## ⏱️ **Rate Limiting** {#rate-limiting}

### **Authentication Endpoints**
- **Login attempts:** 5 per email per 10 minutes
- **Lockout duration:** 10 minutes after 5 failed attempts

### **General API Endpoints**
- **Rate limit:** 1000 requests per hour per IP
- **Burst limit:** 100 requests per minute

### **Zenith Webhook**
- **No rate limiting** (external system integration)

---

## 🧪 **Testing & Development**

### **Swagger UI (Development)**
```
https://[your-domain]/swagger
```

### **Health Check**
```http
GET /healthcheck
```

**Response:**
```
Healthy
```

### **Application Version**
```http
GET /Misc/Version
```

**Response:**
```json
{
  "version": "13.11.00"
}
```

---

## 📞 **Support & Contact**

### **Technical Support**
- **Email:** zvi.g@medicihotels.com
- **Slack:** #medici-api-support
- **Emergency:** +1-864-351-7711

### **API Status & Monitoring**
- **Health Check:** `/healthcheck`
- **Real-time notifications:** SignalR Hub
- **Error logs:** Available through Errors endpoints

---

## 🔒 **Security Considerations**

### **Best Practices**
1. **Always use HTTPS** in production
2. **Rotate credentials** regularly
3. **Monitor rate limits** to avoid blocking
4. **Log all API calls** for audit purposes
5. **Validate input data** before sending requests

### **Data Privacy**
- All personal data is encrypted
- GDPR compliant data handling
- Secure credential storage

---

## 🚀 **Getting Started Example**

### **1. Authenticate**
```bash
curl -X POST "https://[your-domain]/sign-in" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"yourpassword"}'
```

### **2. Get Bookings**
```bash
curl -X GET "https://[your-domain]/Book/Bookings" \
  -H "Authorization: Basic [your-base64-credentials]"
```

### **3. Search Hotels**
```bash
curl -X POST "https://[your-domain]/Search/Search" \
  -H "Authorization: Basic [your-base64-credentials]" \
  -H "Content-Type: application/json" \
  -d '{"dateFrom":"2026-03-15","dateTo":"2026-03-17","hotelId":842332}'
```

---

**📋 This documentation provides complete API coverage for third-party integration with the Medici Hotels Booking Engine system.**