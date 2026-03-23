# Opportunity (CALL) Execution System

## Overview

The opportunity system buys rooms when CALL signals are detected — buying at current price and pushing at a 30% markup for profit.

**WARNING: This system spends real money. Every executed opportunity purchases a hotel room.**

**Version:** v2.2.1 | **Verified:** 2026-03-23 | **Tag:** `v2.2.1-call-execute-verified`

## Endpoints

### Single Opportunity
```
POST /api/v1/salesoffice/opportunity/execute
Body: { "detail_id": 42748 }
→ Auto-computes: buy_price = current, push_price = buy * 1.30
```

### Rules CRUD
```
POST   /opportunity/rules          — Create rule
GET    /opportunity/rules          — List rules
GET    /opportunity/rules/{id}     — Detail + execution log
PUT    /opportunity/rules/{id}     — Pause/resume (?action=pause|resume)
DELETE /opportunity/rules/{id}     — Delete
POST   /opportunity/rules/trigger  — Manual trigger (match + execute)
```

### Create Rule Example
```json
{
  "name": "Eurostars CALLs +30%",
  "signal": "CALL",
  "hotel_id": 333502,
  "push_markup_pct": 30,
  "category": "standard",
  "board": "ro",
  "min_T": 14,
  "max_T": 90
}
```

## Safety Guardrails

| Guardrail | Value | Why |
|-----------|-------|-----|
| Signal type | CALL/STRONG_CALL only | Never buy on PUT/NEUTRAL |
| Min margin | **30%** (push >= 130% of buy) | Ensure profitable trade |
| Max rooms per opp | **1** | Limit exposure |
| Daily budget | **$2,000** (configurable via env var) | Cap daily spend |
| Kill switch | `OPPORTUNITY_EXECUTE_ENABLED` env var | Must be `true` to execute |
| Duplicate check | No active opp for same hotel+date (Status IN 0,1) | Prevent double buy |
| Max rules | 50 | Prevent runaway |
| Max trigger batch | 20 | Budget protection |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPPORTUNITY_EXECUTE_ENABLED` | `false` | Must be `true` to write to BackOfficeOPT + MED_Opportunities |
| `OPPORTUNITY_DAILY_BUDGET` | `2000` | Max $ spend per day (changeable) |

### Enable/Disable

```bash
# Enable (CAUTION — real money)
az webapp config appsettings set --name medici-prediction-api --resource-group medici-prediction-rg \
  --settings OPPORTUNITY_EXECUTE_ENABLED=true

# Disable (safe)
az webapp config appsettings set --name medici-prediction-api --resource-group medici-prediction-rg \
  --settings OPPORTUNITY_EXECUTE_ENABLED=false

# Change daily budget
az webapp config appsettings set --name medici-prediction-api --resource-group medici-prediction-rg \
  --settings OPPORTUNITY_DAILY_BUDGET=5000
```

## Execution Flow

```
1. CALL signal detected (price expected to rise)
2. Rule matches: hotel, category, board, T range
3. Safety checks:
   a. Daily budget: spent + buy_price <= $2,000
   b. Kill switch: OPPORTUNITY_EXECUTE_ENABLED = true
   c. Duplicate: no existing BackOfficeOPT with same hotel+date (Status IN 0,1)
   d. Mapping: ratebycat exists (BoardId, CategoryId, RatePlanCode, InvTypeCode)
4. INSERT BackOfficeOPT (opportunity header)
5. INSERT MED_Opportunities (1 row for 1-night stay)
6. Log execution to SQLite
7. BuyRoom WebJob picks up Status=1 → purchases from Innstant → pushes to Zenith
```

## Database Tables Written (Verified SQL)

### BackOfficeOPT (1 row per opportunity)
```sql
INSERT INTO BackOfficeOPT
  (HotelID, StartDate, EndDate, BordID, CatrgoryID,
   BuyPrice, PushPrice, MaxRooms, Status, DateInsert,
   invTypeCode, ratePlanCode, CountryId, ReservationFirstName)
VALUES
  (@hotel_id, @start_date, @end_date, @board_id, @category_id,
   @buy_price, @push_price, 1, 1, GETDATE(),
   @inv_type_code, @rate_plan_code, 1, 'PricePredictor')
```
Note: `CatrgoryID` (typo) and `HotelID` (uppercase D) match actual DB column names.
Note: `Status=1` — BuyRoom WebJob looks for Status=1.
Note: `EndDate = StartDate + 1 day` (checkout next day).

### MED_Opportunities (1 row per night)
**Table name has hidden Unicode chars:** `MED_ֹOֹֹpportunities` — resolved at runtime via `sys.tables`.

```sql
INSERT INTO [MED_ֹOֹֹpportunities]
  (DestinationsType, DestinationsId, DateForm, DateTo,
   NumberOfNights, Price, Operator, Currency,
   FreeCancelation, CountryCode, PaxAdultsCount, PaxChildrenCount,
   OpportunityMlId, DateCreate, BoardId, CategoryId,
   PushHotelCode, PushBookingLimit, PushInvTypeCode, PushRatePlanCode,
   PushPrice, PushCurrency, IsActive, IsPush, IsSale,
   ReservationFirstName)
VALUES
  ('hotel', @hotel_id, @start_date, @end_date,
   1, @buy_price, 'LTE', 'USD',
   1, 'IL', 2, 0,
   @opp_id, GETDATE(), @board_id, @category_id,
   @hotel_id, 1, @inv_type_code, @rate_plan_code,
   @push_price, 'USD', 1, 0, 0,
   'PricePredictor')
```

## DB Permissions Required

```sql
GRANT INSERT, SELECT ON [dbo].[BackOfficeOPT] TO [prediction_reader];
GRANT INSERT, SELECT ON [dbo].[MED_ֹOֹֹpportunities] TO [prediction_reader];
-- Note: If DENY INSERT exists at DATABASE level, REVOKE it first
```

## Logging (3 Layers)

1. **Opportunity Rule Log** (SQLite `data/opportunity_rules.db`) — every execution with rule_id, buy/push price, profit, opp_id, db_write status
2. **Azure SQL** — BackOfficeOPT + MED_Opportunities rows (permanent record)
3. **Application Logs** — structured JSON with timestamps, correlation IDs

## Auto-Execution

After every collection cycle (every 3 hours), active opportunity rules are matched against fresh CALL signals. Matched opportunities are executed automatically if:
- `OPPORTUNITY_EXECUTE_ENABLED=true`
- Within daily budget ($2,000 default)
- No duplicate exists
- Valid ratebycat mapping

## Comparison: PUT vs CALL

| | PUT (Override) | CALL (Opportunity) |
|---|---|---|
| Signal | PUT/STRONG_PUT | CALL/STRONG_CALL |
| Action | Reduce displayed price in Zenith | Buy room + push markup price |
| Writes to | SalesOffice.PriceOverride | BackOfficeOPT + MED_Opportunities |
| External action | Zenith SOAP push (immediate) | BuyRoom WebJob purchases (async) |
| Risk | Low (price display only) | **High (real money)** |
| Reversible | Yes (next scan resets) | No (room is purchased) |
| Budget limit | No | $2,000/day |
| Margin | N/A (discount $0.01-$10) | Min 30% markup |
| Kill switch | `OVERRIDE_PUSH_ENABLED` | `OPPORTUNITY_EXECUTE_ENABLED` |

## Verified Test Results (2026-03-23)

| Test | Detail | Hotel | Buy | Push | Result |
|------|--------|-------|-----|------|--------|
| Single execute | 42748 | Freehand Miami | $93.43 | $121.46 | **SUCCESS** — BackOfficeOPT + MED_Opportunities created |
| Duplicate check | 42878 | Viajero Miami | $108.53 | — | **SKIPPED** — existing opp #3869 |
| Budget check | (tested) | — | — | — | **Enforced** — $2,000/day cap |
| CALL rule trigger | 86 matches | Eurostars | — | — | **MATCHED** — 86 CALL signals found |
| PUT signal rejected | (tested) | — | — | — | **REJECTED** — CALL/STRONG_CALL only |

## Known Issues (Resolved)

| Issue | Fix | Date |
|-------|-----|------|
| `Invalid column name 'Name'` in BackOfficeOPT | Removed — column doesn't exist | 2026-03-23 |
| `SCOPE_IDENTITY() returns None` | Added `@@IDENTITY` fallback | 2026-03-23 |
| MED_Opportunities INSERT silent failure | Unicode table name — resolved via `sys.tables` lookup | 2026-03-23 |
| `NumberOfNights` NULL | Added `NumberOfNights=1` | 2026-03-23 |
| `Price` NULL | Added `Price=buy_price` | 2026-03-23 |
| `Operator` NULL | Added full C# BaseEF.cs column set (26 columns) | 2026-03-23 |
| `CatrgoryID` typo | Matched actual DB column name (not a bug) | 2026-03-23 |
| `Status=0` vs `Status=1` | Changed to Status=1 (BuyRoom WebJob requirement) | 2026-03-23 |
| `EndDate = StartDate` | Changed to StartDate + 1 day (checkout) | 2026-03-23 |
| BAK_Opportunities matched | Added `NOT LIKE 'BAK%'` filter | 2026-03-23 |
| BoardCode case mismatch | Added LOWER() on both sides of JOIN | 2026-03-23 |
