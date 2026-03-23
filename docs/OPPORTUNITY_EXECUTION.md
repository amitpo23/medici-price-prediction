# Opportunity (CALL) Execution System

## Overview

The opportunity system buys rooms when CALL signals are detected — buying at current price and pushing at a markup for profit.

**WARNING: This system spends real money. Every executed opportunity purchases a hotel room.**

## Endpoints

### Single Opportunity
```
POST /api/v1/salesoffice/opportunity/execute
Body: { "detail_id": 39923 }
→ Auto-computes: buy_price = current, push_price = buy * 1.30
```

### Rules CRUD
```
POST   /opportunity/rules          — Create rule
GET    /opportunity/rules          — List rules
GET    /opportunity/rules/{id}     — Detail + execution log
PUT    /opportunity/rules/{id}     — Pause/resume (?action=pause|resume)
DELETE /opportunity/rules/{id}     — Delete
POST   /opportunity/rules/trigger  — Manual trigger
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
| Min margin | **30%** (push ≥ 130% of buy) | Ensure profitable trade |
| Max rooms per opp | **1** | Limit exposure |
| Daily budget | **$2,000** (configurable) | Cap daily spend |
| Kill switch | `OPPORTUNITY_EXECUTE_ENABLED` env var | Must be `true` to execute |
| Duplicate check | No active opp for same hotel+date+board+category | Prevent double buy |
| Max rules | 50 | Prevent runaway |
| Max trigger batch | 20 | Budget protection |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPPORTUNITY_EXECUTE_ENABLED` | `false` | Must be `true` to write to BackOfficeOPT |
| `OPPORTUNITY_DAILY_BUDGET` | `2000` | Max $ spend per day |

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
1. Rule matches CALL signals (hotel, category, board, T range)
2. For each match:
   a. Check daily budget (spent + buy_price ≤ $2,000)
   b. Check OPPORTUNITY_EXECUTE_ENABLED = true
   c. Check no duplicate (same hotel+date+board+category)
   d. Get BoardId, CategoryId, RatePlanCode from DB
   e. INSERT BackOfficeOPT (1 row — the opportunity header)
   f. INSERT MED_Opportunities (1 row per night, MaxRooms=1)
   g. Log execution with opp_id
3. BuyRoom WebJob picks up → purchases from Innstant → pushes to Zenith
```

## Database Tables Written

### BackOfficeOPT (1 row per opportunity)
```sql
INSERT INTO BackOfficeOPT
(HotelId, StartDate, EndDate, BordId, CategoryId, BuyPrice, PushPrice, MaxRooms, Status, DateInsert, [Name])
VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, GETDATE(), 'PricePredictor Auto')
```

### MED_Opportunities (1 row per room per night)
```sql
INSERT INTO MED_Opportunities
(OpportunityId, HotelId, CategoryId, BoardId, [Date], BuyPrice, PushPrice, MaxRooms, Status)
VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
```

## DB Permissions Required

```sql
GRANT INSERT ON [dbo].[BackOfficeOPT] TO [prediction_reader];
GRANT INSERT ON [dbo].[MED_Opportunities] TO [prediction_reader];
GRANT SELECT ON [dbo].[BackOfficeOPT] TO [prediction_reader];
GRANT SELECT ON [dbo].[MED_Opportunities] TO [prediction_reader];
```

## Logging (3 Layers)

1. **Opportunity Rule Log** (SQLite) — every matched opportunity with rule_id, buy/push price, db_write, opp_id
2. **Azure SQL** — BackOfficeOPT + MED_Opportunities rows
3. **App Logs** — structured JSON with timestamps

## Auto-Execution

After every collection cycle (every 3 hours), active opportunity rules are matched against fresh signals. Matched opportunities are executed automatically (if `OPPORTUNITY_EXECUTE_ENABLED=true` and within daily budget).

## Comparison: PUT vs CALL

| | PUT (Override) | CALL (Opportunity) |
|---|---|---|
| Signal | PUT/STRONG_PUT | CALL/STRONG_CALL |
| Action | Reduce displayed price | Buy room + push price |
| Writes to | SalesOffice.PriceOverride | BackOfficeOPT + MED_Opportunities |
| External action | Zenith SOAP push | BuyRoom WebJob buys |
| Risk | Low (price display only) | **High (real money)** |
| Reversible | Yes (next scan resets) | No (room is purchased) |
| Budget limit | No | $2,000/day |
| Margin | N/A | Min 30% |
