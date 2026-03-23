# Override Execution System

## Overview

The override system allows the Medici prediction engine to push price reductions to Zenith/Noovy when PUT signals are detected. It operates as a **write-through** system: DB record + Zenith SOAP push in one call.

## Endpoints

### Single Override
```
POST /api/v1/salesoffice/override/execute
Body: { "detail_id": 42236, "discount_usd": 1.0 }
```

### Bulk Override
```
POST /api/v1/salesoffice/override/execute-bulk?signal=PUT&hotel_id=66814&discount_usd=1.0&max_items=50
```

**Bulk Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| signal | string | PUT | PUT, STRONG_PUT | Only PUT signals allowed |
| hotel_id | int | null | any | Specific hotel or all |
| category | string | null | standard, deluxe, suite, superior | Room category filter |
| board | string | null | ro, bb | Board type filter |
| min_T | int | 7 | 0-999 | Min days to check-in |
| max_T | int | 120 | 0-999 | Max days to check-in |
| discount_usd | float | 1.0 | 0.01-10.0 | Price reduction per room |
| max_items | int | 50 | 1-200 | Max overrides per call |

## Safety Guardrails

### Hard Limits (cannot be overridden)

| Guardrail | Value | Enforced By |
|-----------|-------|-------------|
| Signal type | PUT/STRONG_PUT only | API validation |
| Max discount | $10.00 per room | API validation |
| Min target price | $50.00 | API validation |
| Max deviation from DB price | 50% | DB query check |
| Max items per bulk call | 200 | API validation |
| Push delay between rooms | 200ms | Code |
| Zenith push kill switch | `OVERRIDE_PUSH_ENABLED` env var | Azure App Settings |

### What It Can Do
- Write to `[dbo].[SalesOffice.PriceOverride]` (INSERT + UPDATE)
- Push prices to Zenith via SOAP API
- Read from any SalesOffice table (SELECT)

### What It Cannot Do
- Override CALL or NEUTRAL signals
- Discount more than $10 per room
- Push target price below $50
- Deviate more than 50% from original DB price
- Process more than 200 rooms per call
- Delete rows from PriceOverride (DENY DELETE on DB)
- Modify SalesOffice.Details, Orders, or any other table
- Push to Zenith when `OVERRIDE_PUSH_ENABLED=false`

## Execution Flow

```
1. Filter: select PUT signals matching hotel/category/board/T criteria
2. For each matched option:
   a. Query Azure SQL: get detail + Zenith mapping (RPC, ITC, ZenithId)
   b. Validate: price range, deviation, mapping exists
   c. Write: INSERT into SalesOffice.PriceOverride (deactivate old, create new)
   d. Push: SOAP OTA_HotelRateAmountNotifRQ to Zenith (if enabled)
   e. Wait: 200ms before next push
3. Return: summary with success/failed/skipped counts
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OVERRIDE_PUSH_ENABLED` | `false` | Must be `true` to push to Zenith. When `false`, writes to DB only (dry run). |
| `MEDICI_DB_URL` | (required) | Azure SQL connection string |

### Enable/Disable Zenith Push

```bash
# Enable live pushes
az webapp config appsettings set --name medici-prediction-api --resource-group medici-prediction-rg --settings OVERRIDE_PUSH_ENABLED=true

# Disable (safe mode)
az webapp config appsettings set --name medici-prediction-api --resource-group medici-prediction-rg --settings OVERRIDE_PUSH_ENABLED=false
```

## Database

### Table: `[dbo].[SalesOffice.PriceOverride]`

| Column | Type | Description |
|--------|------|-------------|
| Id | INT (PK) | Auto-increment |
| DetailId | INT | SalesOffice.Details.Id |
| OriginalPrice | DECIMAL | Price before override |
| OverridePrice | DECIMAL | New target price |
| CreatedBy | NVARCHAR | Always 'PricePredictor' |
| IsActive | BIT | 1=active, 0=deactivated |
| PushStatus | NVARCHAR | null/success/failed |
| PushedAt | DATETIME | When pushed to Zenith |
| CreatedAt | DATETIME | When record created |

### Permissions

```
prediction_reader:
  SELECT on [dbo].[SalesOffice.PriceOverride]  ✓
  INSERT on [dbo].[SalesOffice.PriceOverride]  ✓
  UPDATE on [dbo].[SalesOffice.PriceOverride]  ✓
  DELETE on [dbo].[SalesOffice.PriceOverride]  ✗ (DENY)
  ALTER  on DATABASE                            ✗ (DENY)
  All other tables: SELECT only (db_datareader)
```

## Zenith SOAP Integration

**Endpoint:** `https://hotel.tools/service/Medici%20new`
**Auth:** Username/Password in SOAP header (WS-Security)
**Message:** `OTA_HotelRateAmountNotifRQ`
**Mapping:** hotel_code (Innstant_ZenithId) + RatePlanCode + InvTypeCode from `Med_Hotels_ratebycat`

## Usage Examples

```bash
# Dry run: all PUTs for Breakwater South Beach
curl -X POST ".../override/execute-bulk?signal=PUT&hotel_id=66814&discount_usd=1.0"

# Dry run: all PUTs, Standard rooms only, T=30-90
curl -X POST ".../override/execute-bulk?signal=PUT&category=standard&min_T=30&max_T=90&discount_usd=1.5"

# Dry run: all PUTs for Pullman, RO board, max 100
curl -X POST ".../override/execute-bulk?signal=PUT&hotel_id=6805&board=ro&max_items=100&discount_usd=2.0"

# Single override
curl -X POST ".../override/execute" -H "Content-Type: application/json" -d '{"detail_id":42236,"discount_usd":1.0}'
```

## Verified Test Results (2026-03-23)

| Test | Input | Expected | Result |
|------|-------|----------|--------|
| CALL signal on override | signal=CALL | Reject | **Rejected** ✓ |
| Discount $15 | discount_usd=15 | Reject (>$10) | **Rejected** ✓ |
| max_items=300 | max_items=300 | Reject (>200) | **Rejected** ✓ |
| Negative discount | discount_usd=-5 | Reject | **Rejected** ✓ |
| Non-existent detail | detail_id=99999999 | Reject | **Rejected** ✓ |
| Override CALL detail | detail on CALL signal | Reject | **Rejected** ✓ |
| Valid PUT bulk (dry run) | Breakwater, 3 items | DB write, no push | **3 db_only** ✓ |
| Valid PUT single (live) | detail 42236, -$1 | DB + Zenith push | **$192.95 in Hotel.Tools** ✓ |
