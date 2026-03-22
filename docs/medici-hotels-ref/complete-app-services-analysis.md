# Complete App Services Deep Documentation
Generated: 02/22/2026 17:44:10

## App Service Infrastructure Overview

### Azure App Service Plans:
Based on Azure resource analysis:
- **amitporat1981_asp_2805** (Canada Central)
- **amitporat1981_asp_2806** (Canada Central)
- **amitporat1981_asp_2807** (Canada Central) 
- **ASP-MediciRGDev-899a** (East US 2)
- **MediciBackendS1Plan** (East US 2)

### App Service Applications:
- **medici-backend-dev** (Development Environment)
- **medici-backend** (Production Environment)

## Backend Application Complete Analysis

### Backend Application Structure

**Program.cs Analysis:**
- File Size: 1871 bytes
- Lines of Code: 76
- Contains Service Registration: Yes
- Contains Middleware Configuration: Yes
- API Controllers Enabled: Yes

**Application Configuration (appsettings.json):**

**Connection Strings:**
- SQLServer
  Connection: Data Source = W00048\SQLEXPRESS; Initial Catalog = medici; Integrated Security = True; Multiple Active Result Sets=True; TrustServerCertificate=true;

**Logging Configuration:**
- Default Level: Information

**Additional Configuration Sections:**
- SendGridApiKey
- SendGridEmailFrom
- SendGridEmailRecipients
- TwilioAccountSid
- TwilioAuthToken
- FromNumber
- ClientAppVersion
- SlackChannel

**API Controllers Analysis:**
Total Controllers Found: 10

### Controller: AuthController
- File Size: 1933 bytes
- Lines of Code: 53
- GET Endpoints: 0
- POST Endpoints: 0
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 0

---
### Controller: BookController
- File Size: 2555 bytes
- Lines of Code: 75
- GET Endpoints: 3
- POST Endpoints: 1
- PUT Endpoints: 0
- DELETE Endpoints: 2
- Total Endpoints: 6
**Routes:**
  - [controller]

---
### Controller: ErrorsController
- File Size: 1706 bytes
- Lines of Code: 51
- GET Endpoints: 4
- POST Endpoints: 0
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 4
**Routes:**
  - [controller]

---
### Controller: MiscController
- File Size: 1080 bytes
- Lines of Code: 39
- GET Endpoints: 1
- POST Endpoints: 0
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 1
**Routes:**
  - [controller]

---
### Controller: NotificationsController
- File Size: 707 bytes
- Lines of Code: 24
- GET Endpoints: 0
- POST Endpoints: 1
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 1
**Routes:**
  - api/[controller]

---
### Controller: OpportunityController
- File Size: 3809 bytes
- Lines of Code: 109
- GET Endpoints: 10
- POST Endpoints: 1
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 11
**Routes:**
  - [controller]

---
### Controller: ReservationController
- File Size: 1377 bytes
- Lines of Code: 40
- GET Endpoints: 4
- POST Endpoints: 0
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 4
**Routes:**
  - [controller]

---
### Controller: SalesRoomController
- File Size: 2375 bytes
- Lines of Code: 68
- GET Endpoints: 5
- POST Endpoints: 1
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 6
**Routes:**
  - [controller]

---
### Controller: SearchController
- File Size: 1267 bytes
- Lines of Code: 35
- GET Endpoints: 0
- POST Endpoints: 1
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 1
**Routes:**
  - [controller]

---
### Controller: ZenithApiController
- File Size: 17823 bytes
- Lines of Code: 330
- GET Endpoints: 0
- POST Endpoints: 0
- PUT Endpoints: 0
- DELETE Endpoints: 0
- Total Endpoints: 0

---

