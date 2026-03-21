# Claude Code Prompt — Group Actions Deploy & Verify

Copy-paste this entire prompt to Claude Code:

---

## Context

Three new files were added to the Medici Price Prediction system for **Group Actions** — bulk CALL/PUT execution with flexible filtering. These files are already written and all tests pass (57 new tests). Your job is to **verify, commit, deploy, and validate**.

### New/Modified Files

1. **`src/analytics/group_actions.py`** (NEW — 430 lines)
   - `GroupFilter` dataclass: signal, hotel_id, hotel_ids, category, board, confidence, min_T, max_T, min_price, max_price
   - `filter_signals()` — applies GroupFilter to signal list
   - `preview_group_action()` — dry-run preview
   - `execute_group_override()` — bulk PUT overrides → override_queue.db
   - `execute_group_opportunity()` — bulk CALL opportunities → opportunity_queue.db
   - Safety cap: MAX_GROUP_SIZE = 200, MIN_T_DAYS = 1
   - Batch IDs: `GRP-OVR-{timestamp}-{uuid}` and `GRP-OPP-{timestamp}-{uuid}`

2. **`src/api/routers/analytics_router.py`** (MODIFIED — 3 new endpoints added before Hotel Readiness Diagnostic section)
   - `POST /api/v1/salesoffice/group/preview` — dry-run showing matched rooms, per-hotel breakdown, total value
   - `POST /api/v1/salesoffice/group/override` — bulk PUT overrides with discount_usd param
   - `POST /api/v1/salesoffice/group/opportunity` — bulk CALL opportunities with max_rooms param
   - All endpoints accept query params: signal, hotel_id, hotel_ids (comma-separated), category, board, confidence, min_T, max_T, min_price, max_price

3. **`tests/unit/test_group_actions.py`** (NEW — 57 tests)
   - TestGroupFilter (10 tests): describe(), defaults
   - TestExpandSignal (5 tests): CALL→{CALL,STRONG_CALL}, PUT→{PUT,STRONG_PUT}
   - TestFilterSignals (15 tests): each filter dimension, combined, case-insensitive, edge cases
   - TestPreviewGroupAction (7 tests): hotel breakdown, value, limits
   - TestExecuteGroupOverride (8 tests): queuing, validation errors, hotel breakdown, batch_id
   - TestExecuteGroupOpportunity (6 tests): queuing, force CALL filter, strong variants
   - TestGroupActionResult (1 test): to_dict serialization
   - TestEdgeCases (5 tests): missing fields, None values, T boundary

## Tasks

### 1. Verify Tests Pass
```bash
python3 -m pytest tests/unit/test_group_actions.py -v -o "addopts="
```
Expected: 57 passed, 0 failed.

### 2. Verify Compilation
```bash
python3 -m py_compile src/analytics/group_actions.py
python3 -m py_compile src/api/routers/analytics_router.py
python3 -m py_compile tests/unit/test_group_actions.py
```

### 3. Run Full Test Suite (Check No Regressions)
```bash
python3 -m pytest tests/unit/ -v -o "addopts=" --ignore=tests/unit/test_rate_limiting.py --ignore=tests/unit/test_analytics_router_source_modes.py
```
Note: test_rate_limiting.py and test_analytics_router_source_modes.py have pre-existing httpx dependency issues — ignore them.
Expected: 621+ passed (existing) + 57 new = 678+ total. 19 pre-existing failures are known.

### 4. Commit
```bash
git add src/analytics/group_actions.py src/api/routers/analytics_router.py tests/unit/test_group_actions.py
git commit -m "feat: Group Actions — bulk CALL/PUT execution with flexible filtering

- GroupFilter: signal, hotel_id, hotel_ids, category, board, confidence, T range, price range
- preview_group_action(): dry-run with hotel breakdown and value summary
- execute_group_override(): bulk PUT → override_queue.db with batch tracking
- execute_group_opportunity(): bulk CALL → opportunity_queue.db with batch tracking
- 3 API endpoints: POST /group/preview, /group/override, /group/opportunity
- Safety: MAX_GROUP_SIZE=200, MIN_T_DAYS=1, skip reasons capped at 10
- 57 unit tests all passing"
```

### 5. Deploy
```bash
python3 scripts/build_deploy.py
```
Or whatever your standard deploy command is. If `build_deploy.py` doesn't exist, use:
```bash
az webapp deploy --resource-group <rg> --name medici-prediction-api --src-path <zip>
```

### 6. Validate on Production
After deploy, test the 3 new endpoints:

```bash
# Preview all signals
curl -X POST "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/group/preview" -H "X-API-Key: YOUR_KEY"

# Preview PUT signals for a specific hotel
curl -X POST "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/group/preview?signal=PUT&hotel_id=173508"

# Preview CALL signals with confidence=High
curl -X POST "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/group/preview?signal=CALL&confidence=High"

# Preview with T range filter
curl -X POST "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/group/preview?min_T=7&max_T=30"
```

⚠️ **Do NOT run /group/override or /group/opportunity in production until you've verified the preview returns correct data.**

### 7. Update primer.md
Add to the "Completed" section:
```
- **Group Actions**: Bulk CALL/PUT execution with GroupFilter (signal, hotel, category, board, confidence, T, price).
  3 API endpoints: /group/preview, /group/override, /group/opportunity. 57 tests.
```

## Critical Rules — DO NOT BREAK
1. **Read-only database**: group_actions.py only writes to SQLite queues, never to Azure SQL
2. **Decision Brain boundary**: system queues recommendations, external skills execute
3. **CALL/PUT definitions preserved**: CALL = P_up ≥ 70% (High) or ≥ 60% + acceleration (Med), PUT = P_down ≥ 70% (High) or ≥ 60% + negative acceleration (Med)
4. **Ensemble weights**: 50/30/20 (FC/Historical/ML) — do NOT modify
5. **Existing code untouched**: only additions, no modifications to existing logic
