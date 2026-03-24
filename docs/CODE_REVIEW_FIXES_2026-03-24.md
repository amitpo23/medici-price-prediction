# Code Review Fixes — 2026-03-24

## Review Summary

Full code review was performed on the trading execution system (40+ commits from Command Center through Opportunity Rules). 3 critical issues found and fixed.

## Critical Fixes Applied

### 1. CALL Signal Validation on `/opportunity/execute`

**Problem:** The single opportunity execute endpoint did not validate that the option's signal is CALL/STRONG_CALL before purchasing. An API caller could buy any room — including PUT signals where the price is expected to drop.

**Fix:** Added signal validation after option lookup in `analytics_router.py`:
```python
opt_signal = target.get("option_signal", "")
if opt_signal not in ("CALL", "STRONG_CALL"):
    raise HTTPException(400, f"... signal is {opt_signal}, not CALL — buy rejected")
```

**File:** `src/api/routers/analytics_router.py`

### 2. SOAP Credentials Extracted to Environment Variables

**Problem:** Zenith SOAP username (`APIMedici:Medici Live`) and password (`12345`) were hardcoded in 3 locations in source code.

**Fix:** Created `src/utils/zenith_push.py` — single source of truth:
- `ZENITH_SOAP_URL` env var (default: `https://hotel.tools/service/Medici%20new`)
- `ZENITH_SOAP_USERNAME` env var (default: `APIMedici:Medici Live`)
- `ZENITH_SOAP_PASSWORD` env var (default: `12345`)
- `build_soap_envelope()` — shared SOAP XML builder
- `push_rate_to_zenith()` — shared push function
- `get_pyodbc_connection()` — shared DB connection builder

**Files:**
- Created: `src/utils/zenith_push.py`
- Modified: `src/analytics/override_rules.py` — replaced inline SOAP with shared utility

**Note:** `analytics_router.py` still has 2 inline SOAP blocks (execute and execute-bulk endpoints). These will be migrated to the shared utility in the next cleanup sprint.

### 3. Overly Broad Exception Handler

**Problem:** `except (pyodbc.Error, OSError, Exception)` on MED_Opportunities INSERT was equivalent to bare `except Exception` — swallowing all errors including programming bugs.

**Fix:** Removed `Exception` from the tuple, leaving `except (pyodbc.Error, OSError)`.

**File:** `src/analytics/opportunity_rules.py`

## Remaining Items from Review (Not Yet Fixed)

| # | Priority | Issue | Status |
|---|----------|-------|--------|
| 4 | Important | DB connection string parsing duplicated 5 times | `get_pyodbc_connection()` created but not yet used everywhere |
| 5 | Important | SOAP construction still inline in analytics_router.py (2 places) | Will migrate next sprint |
| 6 | Important | analytics_router.py at 3,877 lines — should split execution endpoints | Planned: `execution_router.py` |
| 7 | Important | Background thread uses daemon=True — can be killed mid-INSERT | Noted |
| 8 | Important | Silent exception on guest name fetch | Noted — non-critical |
| 9 | Suggestion | STRONG_PUT should match PUT rules | To discuss with product |
| 10 | Suggestion | No unit tests for execute functions | External dependency limitation |
| 11 | Suggestion | `datetime.utcnow()` deprecated in 3.12 | Low priority cleanup |

## Revert Points

| Tag | Description |
|-----|-------------|
| `v2.2.1-call-execute-verified` | Before code review fixes — last verified working state |
| `v2.1.3-pre-call-execute` | Before CALL execution — Override Rules only |
| `v2.1.2-pre-override-rules` | Before Override Rules — single + bulk execute only |
| `v2.1.1-pre-override-test` | Before override testing — Command Center only |
| `v2.1.0-ui-baseline` | Before Command Center — original 7 dashboards |
