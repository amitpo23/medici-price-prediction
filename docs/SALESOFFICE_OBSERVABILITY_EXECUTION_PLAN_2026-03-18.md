# SalesOffice Observability Update — Execution Plan

**Date:** 2026-03-18  
**Scope:** Operational clarity only — no change to prediction weights, DB write behavior, or business logic.  
**Goal:** Improve confidence in the existing SalesOffice sync pipeline by exposing runtime health, clarifying cache-vs-DB status, adding collector filter tests, and aligning UI wording with the actual 3-hour collector cadence.

---

## Why this change

The current system is stable, but two operational gaps remain:

1. `/api/v1/salesoffice/status` reports local snapshot/cache state and scheduler flags, but it does not clearly expose the last successful DB-backed collection attempt.
2. Some user-facing text still says "hourly" while the configured SalesOffice prediction collector runs every 3 hours by default.
3. The collector SQL filters are critical to data quality, but there is no dedicated unit test file covering them.

---

## Change set

### 1. Add runtime collection metadata

**Files:**
- [src/analytics/collector.py](src/analytics/collector.py)
- [src/api/routers/analytics_router.py](src/api/routers/analytics_router.py)

**Planned result:**
- Track last collection attempt, completion, success/failure state, duration, row count, hotel count, and last error.
- Expose these values from `/api/v1/salesoffice/status`.
- Keep the endpoint read-only and lightweight.

### 2. Add collector filter tests

**Files:**
- [tests/unit/test_collector.py](tests/unit/test_collector.py)
- [tests/integration/test_api_endpoints.py](tests/integration/test_api_endpoints.py)

**Planned result:**
- Verify the collector query still filters on:
  - `IsActive = 1`
  - `WebJobStatus LIKE 'Completed%'`
  - `WebJobStatus NOT LIKE '%Mapping: 0%'`
- Verify status payload contains the new observability fields.

### 3. Align wording with actual cadence

**Files:**
- [src/api/routers/_options_html_gen.py](src/api/routers/_options_html_gen.py)
- [src/analytics/info_page.py](src/analytics/info_page.py)

**Planned result:**
- Replace ambiguous "hourly scan" wording with wording that matches the current prediction collector cadence.
- Clarify the distinction between SalesOffice scan data and the Medici prediction collector cache.

---

## Explicit non-goals

This execution will **not**:
- modify ensemble weights
- modify prediction formulas
- write to `medici-db`
- alter WebJob behavior
- alter scheduler interval
- alter hotel readiness rules

---

## Rollback point

### Safe rollback trigger

Rollback immediately if any of the following occurs:
- `/api/v1/salesoffice/status` returns non-200
- existing SalesOffice API integration tests fail
- new observability fields break frontend status usage
- collector unit tests expose a regression in query assumptions

### Rollback method

Revert only the files touched by this execution:
- [src/analytics/collector.py](src/analytics/collector.py)
- [src/api/routers/analytics_router.py](src/api/routers/analytics_router.py)
- [src/api/routers/_options_html_gen.py](src/api/routers/_options_html_gen.py)
- [src/analytics/info_page.py](src/analytics/info_page.py)
- [tests/unit/test_collector.py](tests/unit/test_collector.py)
- [tests/integration/test_api_endpoints.py](tests/integration/test_api_endpoints.py)

Operationally, rollback is low risk because this is observability/documentation/test work only.

---

## Validation plan

After implementation:

1. Run focused unit tests:
   - collector tests
   - shared state tests
2. Run focused integration tests:
   - SalesOffice API endpoint tests
3. Verify `/api/v1/salesoffice/status` still returns baseline fields plus runtime metadata.
4. Confirm wording updates are limited to documentation/UI hints only.

---

## Success criteria

Implementation is considered successful if:
- tests pass
- `/status` includes cache + collection runtime visibility
- query filters remain unchanged
- wording reflects the actual 3-hour prediction collection cadence
- no DB write path is introduced
