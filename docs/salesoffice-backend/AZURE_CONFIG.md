# Medici Hotels - Azure App Service Configuration

> **medici-backend** | Production Environment  
> Last Updated: January 13, 2026

---

## 🌐 App Service Overview

| Property | Value |
|----------|-------|
| **Name** | medici-backend |
| **Type** | Web App (App Service) |
| **Status** | ✅ Running |
| **Default Domain** | medici-backend.azurewebsites.net |
| **URL** | https://medici-backend.azurewebsites.net |
| **Resource Group** | Medici-RG |
| **Location** | East US 2 |

### Hosting Configuration

| Property | Value |
|----------|-------|
| App Service Plan | MediciBackendS1Plan |
| SKU and Size | Standard (S1) |
| Instance Count | 1 |
| Operating System | Windows |
| Runtime Stack | .NET Core (Original) / Node.js (Replica) |

### Networking

| Property | Value |
|----------|-------|
| Virtual IP | 104.209.197.87 |
| Outbound IPs | 191.237.129.87, 191.237.129.130, 191.237.129.134, ... |

---

## 🔗 Connection Strings

### Production (Managed Identity)
```
Name: AZURE_SQL_CONNECTIONSTRING
Type: SQLAzure
Server: medici-sql-server.database.windows.net,1433
Database: medici-db
Authentication: ActiveDirectoryManagedIdentity
```

### Legacy SQL Connection
```
Name: SQLServerOLD
Server: tcp:medici-sql-server.database.windows.net,1433
Database: medici-db
User ID: medici2_sql_admin
Password: [STORED IN AZURE KEY VAULT]
```

---

## ⚙️ Application Settings

| Name | Value |
|------|-------|
| DIAGNOSTICS_AZUREBLOBRETENTIONINDAYS | 1 |
| WEBSITE_HTTPLOGGING_RETENTION_DAYS | 1 |
| WEBSITE_NODE_DEFAULT_VERSION | 6.9.1 |

---

## 📧 External Services Configuration

### SendGrid (Email)
| Property | Value |
|----------|-------|
| From Email | zvi.g@medicihotels.com |
| Recipients | zvi.g@medicihotels.com, shiranbr22@gmail.com, Gilifeldesh6@gmail.com |

### Twilio (SMS)
| Property | Value |
|----------|-------|
| From Number | +18643517711 |

### Slack Notifications
| Property | Value |
|----------|-------|
| Webhook URL | https://hooks.slack.com/services/T03RQ7Q1N4A/B04QS29NS4W/... |

---

## 🔄 WebJobs (Background Services)

| Name | Type | Status | Purpose |
|------|------|--------|---------|
| **BuyRoomWebJob** | Continuous | ✅ Running | Auto-purchase rooms from Innstant |
| **AutoCancellation** | Continuous | ✅ Running | Cancel unsold rooms before deadline |
| **LastPriceUpdate** | Continuous | ✅ Running | Push price updates to Zenith |
| **AzureWebJob** | Continuous | ✅ Running | General background tasks |

---

## 🌍 External API Integrations

### Innstant API (Room Supplier)

| Property | Value |
|----------|-------|
| Protocol | REST / JSON |
| Search URL | https://connect.mishor5.innstant-servers.com |
| Book URL | https://book.mishor5.innstant-servers.com |

**Headers:**
```
aether-access-token: [TOKEN]
aether-application-key: [KEY]
content-type: application/json
```

### Zenith API (Distribution Channel)

| Property | Value |
|----------|-------|
| Protocol | SOAP / XML (OTA Standard) |
| Service URL | https://hotel.tools/service/Medici%20new |
| Account Name | Medici LIVE |
| Agent Name | Zvi |

**Notifications Callback:**
```
https://bapi.medicihotels.com/
```

---

## 🔑 Environment Variables Required

For Node.js Backend replica, set these environment variables:

```env
# Database
DB_SERVER=medici-sql-server.database.windows.net
DB_DATABASE=medici-db
DB_USER=medici2_sql_admin
DB_PASSWORD=********
DB_PORT=1433

# JWT
JWT_SECRET=********

# Server
PORT=8080
NODE_ENV=production

# SendGrid
SENDGRID_API_KEY=********
SENDGRID_FROM_EMAIL=zvi.g@medicihotels.com

# Twilio
TWILIO_ACCOUNT_SID=********
TWILIO_AUTH_TOKEN=********
TWILIO_FROM_NUMBER=+18643517711

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/********

# Innstant API
INNSTANT_SEARCH_URL=https://connect.mishor5.innstant-servers.com
INNSTANT_BOOK_URL=https://book.mishor5.innstant-servers.com
INNSTANT_ACCESS_TOKEN=********
INNSTANT_APPLICATION_KEY=********

# Zenith API
ZENITH_SERVICE_URL=https://hotel.tools/service/Medici%20new
ZENITH_ACCOUNT_NAME=Medici LIVE
ZENITH_AGENT_NAME=Zvi
ZENITH_PASSWORD=********
ZENITH_CALLBACK_URL=https://bapi.medicihotels.com/
```

---

## 📡 Important URLs

| Service | URL |
|---------|-----|
| Backend API (Production) | https://medici-backend.azurewebsites.net |
| Backend API (Dev) | https://medici-backend-dev.azurewebsites.net |
| Frontend | https://admin.medicihotels.com |
| Innstant Search | https://connect.mishor5.innstant-servers.com |
| Innstant Book | https://book.mishor5.innstant-servers.com |
| Zenith | https://hotel.tools/service/Medici%20new |
| Notifications Callback | https://bapi.medicihotels.com/ |

---

## 🚀 Deployment

### Current Status
⚠️ CI/CD is NOT configured - Manual deployment only

### FTPS Deployment
```
Endpoint: ftps://waws-prod-bn1-001.ftp.azurewebsites.windows.net/site/wwwroot
Username: medici-backend\$medici-backend
```

### Recommended: GitHub Actions
```yaml
name: Deploy to Azure
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: azure/webapps-deploy@v2
        with:
          app-name: medici-backend
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

---

*Generated: January 13, 2026*

