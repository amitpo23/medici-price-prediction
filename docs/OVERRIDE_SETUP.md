# Override Execution — Setup Guide

## What This Does

The `/override/execute` endpoint allows the Medici prediction system to **push price overrides** to Zenith (the pricing engine) when a PUT signal is detected. The flow:

1. User clicks "Override" on a room in the Command Center
2. System writes a record to `SalesOffice.PriceOverride` (audit trail)
3. System sends SOAP request to Zenith to update the actual price

## Current State

- **Endpoint**: `POST /api/v1/salesoffice/override/execute`
- **Status**: Dry-run mode (safe — no actual changes)
- **Blocker**: DB user `prediction_reader` lacks write permissions to `PriceOverride` table

## Step 1: Grant DB Permissions

The system writes **only** to `SalesOffice.PriceOverride` — a dedicated table for overrides. It does NOT touch `Details`, `Orders`, or any other table.

### Option A: Azure Portal (Easiest)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **SQL databases** → **medici-db**
3. Click **Query editor** in the left menu
4. Login with admin credentials:
   - Server: `medici-sql-server.database.windows.net`
   - User: `medici_sql_admin`
   - Password: (ask admin)
5. Run:

```sql
GRANT INSERT, UPDATE ON [SalesOffice.PriceOverride] TO prediction_reader;
```

### Option B: sqlcmd (CLI)

```bash
sqlcmd -S medici-sql-server.database.windows.net \
       -d medici-db \
       -U medici_sql_admin \
       -P '<ADMIN_PASSWORD>' \
       -Q "GRANT INSERT, UPDATE ON [SalesOffice.PriceOverride] TO prediction_reader;"
```

### Option C: Azure Data Studio / SSMS

1. Connect to `medici-sql-server.database.windows.net`
2. Database: `medici-db`
3. Login: `medici_sql_admin`
4. Run the same GRANT statement

## Step 2: Enable Zenith Push (Optional)

By default, the endpoint runs in **dry-run mode** — it writes to the DB but does NOT send the SOAP request to Zenith. This is controlled by an environment variable.

To enable live pushes:

```bash
az webapp config appsettings set \
  --name medici-prediction-api \
  --resource-group medici-prediction-rg \
  --settings OVERRIDE_PUSH_ENABLED=true
```

To disable (revert to dry-run):

```bash
az webapp config appsettings set \
  --name medici-prediction-api \
  --resource-group medici-prediction-rg \
  --settings OVERRIDE_PUSH_ENABLED=false
```

## Step 3: Verify

After granting permissions, test with:

```bash
curl -X POST "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/override/execute" \
  -H "Content-Type: application/json" \
  -d '{"detail_id": 42236, "discount_usd": 1.0}'
```

Expected response (dry-run):

```json
{
  "action": "override_execute",
  "detail_id": 42236,
  "hotel_name": "Breakwater South Beach",
  "original_price": 193.95,
  "discount_usd": 1.0,
  "target_price": 192.95,
  "db_write": "success",
  "zenith_push": "dry_run — OVERRIDE_PUSH_ENABLED=false",
  "zenith_mapping": {
    "hotel_code": "5110",
    "rpc": "12078",
    "itc": "Stnd",
    "date": "2026-06-03"
  }
}
```

## Safety Mechanisms

| Mechanism | Description |
|-----------|-------------|
| `OVERRIDE_PUSH_ENABLED=false` | Default. No SOAP calls to Zenith |
| `SalesOffice.PriceOverride` only | Never writes to Details/Orders |
| `prediction_reader` permissions | Scoped GRANT — only INSERT/UPDATE on one table |
| Dry-run response | Returns full preview (SOAP XML, mapping) without executing |
| Override Queue | All overrides logged in SQLite `override_queue.db` for audit |

## Infrastructure Reference

| Resource | Value |
|----------|-------|
| SQL Server | `medici-sql-server.database.windows.net` |
| Database | `medici-db` |
| Resource Group (SQL) | `Medici-RG` |
| Admin User | `medici_sql_admin` |
| App User | `prediction_reader` |
| App Service | `medici-prediction-api` |
| Resource Group (App) | `medici-prediction-rg` |
| Override Table | `SalesOffice.PriceOverride` |
