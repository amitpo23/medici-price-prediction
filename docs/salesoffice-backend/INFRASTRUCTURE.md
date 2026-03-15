# Medici Hotels - Infrastructure & Deployment Guide

> **Production Environment**  
> ⚠️ CONFIDENTIAL - Contains passwords and API keys  
> Last Updated: January 13, 2026

---

## 🏗️ Architecture Overview

```
┌─────────────────────┐         ┌─────────────────────┐         ┌─────────────────────┐
│       Vercel        │         │    Azure App        │         │    Azure SQL        │
│     (Frontend)      │  HTTPS  │     Service         │   SQL   │     Database        │
│  Angular 16 + TS    │ ──────► │   (.NET Core)       │ ──────► │                     │
│                     │         │   [Node.js Replica] │         │                     │
│ admin.medicihotels  │         │ medici-backend      │         │ medici-sql-server   │
│        .com         │         │ .azurewebsites.net  │         │ .database.windows   │
└─────────────────────┘         └──────────┬──────────┘         └─────────────────────┘
                                           │
                                           │ REST/SOAP
                                           ▼
                                ┌─────────────────────┐
                                │   External APIs     │
                                │  • Innstant (REST)  │
                                │  • GoGlobal (REST)  │
                                │  • Zenith (SOAP)    │
                                │  • Slack (Webhook)  │
                                │  • SendGrid (Email) │
                                │  • Twilio (SMS)     │
                                └─────────────────────┘
```

---

## ☁️ Azure Infrastructure

### Resource Group

| Property | Value |
|----------|-------|
| Resource Group | Medici-RG |
| Subscription | Medici subscription |
| Subscription ID | 2da025cc-dfe5-450f-a18f-10549a3907e3 |
| Location | East US 2 |

### SQL Server & Database

| Property | Value |
|----------|-------|
| Server Name | medici-sql-server |
| Full Server URL | medici-sql-server.database.windows.net |
| Port | 1433 |
| Database Name | medici-db |

### App Service (Backend API)

| Property | Value |
|----------|-------|
| App Name | medici-backend |
| URL | https://medici-backend.azurewebsites.net |
| App Service Plan | MediciBackendS1Plan (S1: 1) |
| Runtime Stack | .NET Core (Original) / Node.js (Replica) |
| Operating System | Windows |
| Status | ✅ Running |

### WebJobs (Background Services)

| WebJob Name | Type | Status | Purpose |
|-------------|------|--------|---------|
| BuyRoomWebJob | Continuous | ✅ Running | Auto-purchase rooms from suppliers |
| AutoCancellation | Continuous | ✅ Running | Cancel unsold rooms before deadline |
| LastPriceUpdate | Continuous | ✅ Running | Update prices in Zenith |
| AzureWebJob | Continuous | ✅ Running | General purpose |

---

## ▲ Vercel Frontend

### Project Configuration

| Property | Value |
|----------|-------|
| Project Name | medici-web |
| Account | guyofiror (Pro) |
| Framework | Angular 16 + TypeScript |
| Production Branch | develop-azure |

### Domains

| Domain | Environment | Status |
|--------|-------------|--------|
| admin.medicihotels.com | Production | ✅ Active |
| medici-web.vercel.app | Production | ✅ Valid |

### GitHub Repository

| Property | Value |
|----------|-------|
| Organization | OnlyNight-LTD |
| Repository | medici_web |
| Full URL | github.com/OnlyNight-LTD/medici_web |
| Connected | January 12, 2024 |
| Auto Deploy | ✅ Enabled |

---

## 🌐 External API Integrations

### Innstant API (Room Supplier)

| Property | Value |
|----------|-------|
| Protocol | REST / JSON |
| Search URL | https://connect.mishor5.innstant-servers.com |
| Book URL | https://book.mishor5.innstant-servers.com |

**Headers:**
```
aether-access-token: $2y$10$QcGPkHG9Rk1VRTClz0HIsO3qQpm3JEU84QqfZadIVIoVHn5M7Tpnu
aether-application-key: $2y$10$zmUK0OGNeeTtiGcV/cpWsOrZY7VXbt0Bzp16VwPPQ8z46DNV6esum
content-type: application/json
```

### Zenith API (Distribution Channel)

| Property | Value |
|----------|-------|
| Protocol | SOAP / XML (OTA Standard) |
| Service URL | https://hotel.tools/service/Medici%20new |
| Account Name | Medici LIVE |
| Username | APIMedici:Medici Live |
| Password | 12345 |
| Agent Name | Zvi |
| Agent Password | karpad66 |

**Notifications Callback:**
```
https://bapi.medicihotels.com/
```

---

## 🔐 Credentials Reference

### Database Credentials

| Connection | User ID | Password | Type |
|------------|---------|----------|------|
| AZURE_SQL | Managed Identity | (automatic) | Production |
| SQLServerOLD | medici2_sql_admin | @Amit2025 | Legacy |
| SQLServerOLD2 | medici_sql_admin | @Amit2025 | Legacy |

### Connection Strings

**Production (Managed Identity):**
```
Data Source=medici-sql-server.database.windows.net,1433;
Initial Catalog=medici-db;
Authentication=ActiveDirectoryManagedIdentity
```

**Legacy (SQL Authentication):**
```
Server=tcp:medici-sql-server.database.windows.net,1433;
Initial Catalog=medici-db;
Persist Security Info=True;
User ID=medici2_sql_admin;
Password=@Amit2025;
MultipleActiveResultSets=True;
Encrypt=True;
TrustServerCertificate=False;
Connection Timeout=30;
Pooling=False
```

### API Credentials

| Service | Key/Token | Additional Info |
|---------|-----------|-----------------|
| SendGrid | SG.******************************** | Email notifications |
| Twilio SID | AC******************************** | SMS notifications |
| Twilio Token | ******************************** | From: +1864******* |
| Innstant Token | $2y$10$*************************** | Room supplier API |
| Zenith | APIMedici:******** / ***** | Distribution channel |
| Slack Webhook | ***************************** | Notifications |

**Note:** All credentials are stored securely in `.env` files and are not committed to Git.

---

## 🚀 Setting Up New Environment

### New Vercel Environment

1. Create new Vercel project or add environment to existing
2. Set Environment Variables:
   ```
   API_URL=https://your-new-backend.azurewebsites.net
   ```
3. Configure Branch: Point to appropriate Git branch
4. Deploy: Push to trigger deployment

### New Azure Environment

```bash
# 1. Create Resource Group
az group create --name Medici-RG-Dev --location eastus2

# 2. Create SQL Server
az sql server create --name medici-sql-dev --resource-group Medici-RG-Dev \
  --admin-user medici_admin --admin-password <PASSWORD>

# 3. Create Database
az sql db create --name medici-db-dev --server medici-sql-dev \
  --resource-group Medici-RG-Dev --service-objective S0

# 4. Create App Service
az webapp create --name medici-backend-dev --resource-group Medici-RG-Dev \
  --plan MediciBackendS1Plan --runtime "DOTNETCORE:7.0"

# 5. Configure Connection String
az webapp config connection-string set --name medici-backend-dev \
  --resource-group Medici-RG-Dev --connection-string-type SQLAzure \
  --settings SQLServer="Server=tcp:medici-sql-dev.database.windows.net..."
```

### For Node.js Replica

```bash
# Create App Service with Node.js runtime
az webapp create --name medici-backend-node-dev --resource-group Medici-RG-Dev \
  --plan MediciBackendS1Plan --runtime "NODE:18-lts"

# Set environment variables
az webapp config appsettings set --name medici-backend-node-dev \
  --resource-group Medici-RG-Dev \
  --settings DB_SERVER=medici-sql-dev.database.windows.net \
             DB_DATABASE=medici-db-dev \
             DB_USER=medici_admin \
             DB_PASSWORD=<PASSWORD> \
             NODE_ENV=development
```

---

## 📡 All URLs

| Service | URL |
|---------|-----|
| Frontend (Prod) | https://admin.medicihotels.com |
| Backend API | https://medici-backend.azurewebsites.net |
| SQL Server | medici-sql-server.database.windows.net:1433 |
| GitHub | github.com/OnlyNight-LTD/medici_web |
| Azure Portal | portal.azure.com |
| Vercel Dashboard | vercel.com/guyofiror/medici-web |
| Innstant Search | https://connect.mishor5.innstant-servers.com |
| Innstant Book | https://book.mishor5.innstant-servers.com |
| Zenith | https://hotel.tools/service/Medici%20new |
| Notifications Callback | https://bapi.medicihotels.com/ |

---

*Generated: January 13, 2026*

