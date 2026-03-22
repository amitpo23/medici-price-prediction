# Complete API Schemas & Endpoints Documentation
Generated: 02/22/2026 17:53:45

## API Overview
- Framework: ASP.NET Core Web API
- Response Format: JSON REST API
- Base URL: Based on controller routing

## API Controllers Analysis

### Controller: Auth
**Endpoints Summary:**
- GET endpoints: 0
- POST endpoints: 0
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 0

---

### Controller: Book
**Endpoints Summary:**
- GET endpoints: 3
- POST endpoints: 1
- PUT endpoints: 0
- DELETE endpoints: 2
- Total: 6

**Routes:**
- [controller]

---

### Controller: Errors
**Endpoints Summary:**
- GET endpoints: 4
- POST endpoints: 0
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 4

**Routes:**
- [controller]

---

### Controller: Misc
**Endpoints Summary:**
- GET endpoints: 1
- POST endpoints: 0
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 1

**Routes:**
- [controller]

---

### Controller: Notifications
**Endpoints Summary:**
- GET endpoints: 0
- POST endpoints: 1
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 1

**Routes:**
- api/[controller]

---

### Controller: Opportunity
**Endpoints Summary:**
- GET endpoints: 10
- POST endpoints: 1
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 11

**Routes:**
- [controller]

**API Actions:**
- ShowOppHome

---

### Controller: Reservation
**Endpoints Summary:**
- GET endpoints: 4
- POST endpoints: 0
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 4

**Routes:**
- [controller]

---

### Controller: SalesRoom
**Endpoints Summary:**
- GET endpoints: 5
- POST endpoints: 1
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 6

**Routes:**
- [controller]

---

### Controller: Search
**Endpoints Summary:**
- GET endpoints: 0
- POST endpoints: 1
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 1

**Routes:**
- [controller]

---

### Controller: ZenithApi
**Endpoints Summary:**
- GET endpoints: 0
- POST endpoints: 0
- PUT endpoints: 0
- DELETE endpoints: 0
- Total: 0

---

## Data Model Schemas

### Model: BackOfficeOpt
**Properties (2):**
- Id : int
- DateInsert : DateTime


### Model: BackOfficeOptLog
**Properties (4):**
- Id : int
- BackOfficeOptId : int
- ErrorLog : string
- DateCreate : DateTime


### Model: Basic


### Model: MedBoard


### Model: MedBook
**Properties (2):**
- Id : int
- PreBookId : int


### Model: MedBookCustomerMoreInfo
**Properties (1):**
- Id : int


### Model: MedBookCustomerName
**Properties (1):**
- Id : int


### Model: MedBookError
**Properties (1):**
- Id : int


### Model: MedCancelBook
**Properties (1):**
- Id : int


### Model: MedCancelBookError
**Properties (1):**
- Id : int


