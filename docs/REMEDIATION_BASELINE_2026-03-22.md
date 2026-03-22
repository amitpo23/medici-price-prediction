# Remediation Baseline

Date: 2026-03-22
Scope: Baseline snapshot before production-hardening remediation work.

## Version Context

- Application version: `2.0.1`
- Git branch: `main`
- Git commit: `57ebbe1`
- Primary app declaration: `src/api/main.py`
- Latest released change log entry: `CHANGELOG.md` section `[2.0.1] - 2026-03-09`

## Current System State

The system is a read-only pricing decision brain for hotel inventory. The prediction engine, router split, cache unification, structured logging, rate limiting, and startup validation are already in place. The business boundary is correct: the API recommends and queues actions, but does not write to the Medici trading database.

### Preserved Strengths

- Read-only SQL enforcement exists in `src/data/trading_db.py`.
- FastAPI app versioning and change tracking are explicit.
- SalesOffice router split is already completed.
- CacheManager centralizes major cache regions.
- Logging, correlation IDs, and rate limiting are deployed.
- Unit and integration test foundations exist and are usable for regression control.

## Verified Operational Weaknesses

### 1. Queue state is stored in local SQLite files

Affected modules:

- `src/analytics/override_queue.py`
- `src/analytics/opportunity_queue.py`
- `src/analytics/accuracy_tracker.py`
- `src/services/alert_dispatcher.py`
- `src/services/circuit_breaker.py`

Risk:

- Operational state is bound to local filesystem scope.
- Multi-instance deployment can split queue state.
- Restarts can interrupt queue-driven workflows.

### 2. API body validation is partially manual

Affected module:

- `src/api/routers/analytics_router.py`

Risk:

- Invalid payload types can surface as runtime exceptions.
- Some side-effect endpoints rely on manual coercion instead of request models.

### 3. Background job execution is fragmented

Affected modules:

- `src/api/main.py`
- `src/api/routers/dashboard_router.py`
- `src/api/routers/_shared_state.py`
- `src/services/scheduler.py`

Risk:

- Multiple ad-hoc threads are started from request and startup paths.
- Lifecycle control and observability are weaker than the prediction core.

### 4. Queue lifecycle is not lease-based

Affected modules:

- `src/analytics/override_queue.py`
- `src/analytics/opportunity_queue.py`

Risk:

- `picked` items can remain stuck indefinitely.
- No retry counter, reclaim path, or dead-letter semantics exist.

### 5. Collector resilience is still single-shot in key paths

Affected modules:

- `src/collectors/weather_collector.py`
- `src/collectors/events_collector.py`
- `src/collectors/cbs_collector.py`

Risk:

- Transient network failures can degrade data collection too aggressively.

## Remediation Starting Scope

The first execution slice is intentionally narrow:

1. Document the baseline state and version.
2. Fix an existing date-window bug in override history.
3. Replace manual request-body parsing for queue endpoints with typed FastAPI request models.
4. Add regression tests for validation and the date-window bug.

## Explicit Non-Goals For This Slice

- No change to prediction ensemble weights.
- No change to read-only trading DB enforcement.
- No queue storage migration yet.
- No background job framework rewrite yet.

## Worktree Note

Temporary `.fuse_hidden*` files were present under `data/` during baseline capture. They are treated as environment noise and not part of the remediation scope.