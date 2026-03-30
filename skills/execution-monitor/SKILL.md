# Execution Monitor Skill

## Purpose
Monitors that override (PUT) and opportunity (CALL) executions actually complete.
Runs automatically every collection cycle and can be triggered manually.

## What It Checks

### 1. Override Queue Health
- Pending items count — should be 0 between cycles
- Failed items — alerts if any
- Stuck items (pending > 1 hour) — alerts
- Done rate — % of submitted overrides that completed

### 2. PriceOverride DB Verification
- Active overrides count matches expectations
- No orphaned overrides (detail deleted but override active)
- Override prices within sane range ($1-$10K)

### 3. Opportunity Queue Health
- Pending opportunities count
- Failed opportunities
- BuyRoom WebJob pickup rate

## Endpoints
- `GET /api/v1/salesoffice/execution/health` — full health check
- `POST /api/v1/salesoffice/override/queue/process` — manually trigger pending overrides

## How to Use

### Check execution health
```bash
curl .../api/v1/salesoffice/execution/health
```

### Manually process stuck overrides
```bash
curl -X POST .../api/v1/salesoffice/override/queue/process
```

### From Terminal V2
- Override queue status shown in sidebar (OVERRIDE QUEUE panel)
- "Override All PUTs in View" button queues overrides
- Queue auto-processes every collection cycle (~1 hour)

## Architecture
```
User clicks "Override All PUTs"
  → POST /group/override → items added to SQLite override_queue
  → Next collection cycle: _process_override_queue() picks pending items
  → For each: write to Azure SQL PriceOverride + mark done
  → OR: POST /override/queue/process for immediate execution
```

## Guardrails
- Max $10K price check (runaway protection)
- Deduplication by detail_id (skip duplicates)
- mark_completed with success/failure tracking
- All errors logged, never silent
