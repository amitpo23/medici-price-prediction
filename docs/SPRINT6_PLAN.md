# Sprint 6 — Full System Activation Plan

**Baseline tag**: `v2.7.0-pre-sprint6` (commit b752426)
**Baseline tests**: 1,433 passed, 0 failed
**Date**: 2026-03-29
**Goal**: Activate all 31 Miami hotels, fix prediction engine, make all dashboards work with live data

---

## Phase 0 — System Activation (CRITICAL)

Without this, nothing works. The Scheduler is stopped → no price scans → all dashboards empty.

| Task | Description | Status |
|------|------------|--------|
| 0.1 | Diagnose why Scheduler stopped and restart it | ⬜ |
| 0.2 | Verify Command Center loads with real data | ⬜ |
| 0.3 | Verify Unified Terminal loads with real data | ⬜ |
| 0.4 | Verify Home page shows Rooms/Hotels/Snapshots counts | ⬜ |

---

## Phase 1 — Hotel Activation (31 Miami Hotels)

### A1. Hotels with rates but no Orders (create Orders in SalesOffice)

| Task | Hotel | ZenithId | Rates | Extra work |
|------|-------|----------|-------|------------|
| A1.1 | Fontainebleau Miami Beach | 5268 | 10 | Orders only |
| A1.2 | citizenM Miami South Beach | 5119 | 2 | Orders + add SPR, DLX, Suite rates |
| A1.3 | Hilton Cabana Miami Beach | 5115 | 10 | Orders only |
| A1.4 | Grand Beach Hotel Miami | 5124 | 3 | Orders + add SPR, DLX rates |
| A1.5 | Gale Miami Hotel and Residences | 5278 | 6 | Orders + add SPR, DLX rates |
| A1.6 | Generator Miami | 5274 | 6 | Orders + add BB for SPR/DRM/DLX/Suite |
| A1.7 | Hilton Garden Inn Miami South Beach | 5279 | 2 | Orders + add SPR, DLX, Suite rates |

### A2. Hotels with no rates and no Orders (full Noovy setup + Orders)

| Task | Hotel | ZenithId |
|------|-------|----------|
| A2.1 | InterContinental Miami | 5276 |
| A2.2 | Miami International Airport Hotel | 5275 |
| A2.3 | Holiday Inn Express Miami | 5130 |
| A2.4 | Notebook Miami Beach | 5102 |
| A2.5 | Sole Miami, A Noble House Resort | 5104 |
| A2.6 | SERENA Hotel Aventura Miami | 5139 |
| A2.7 | The Grayson Hotel Miami Downtown | 5094 |

### A3. Hotels with Details but no rates (add rates in Noovy)

| Task | Hotel | ZenithId | Active Details |
|------|-------|----------|---------------|
| A3.1 | Loews Miami Beach Hotel | 5073 | 4 |
| A3.2 | Hyatt Centric South Beach Miami | 5097 | 2 |

### A4. Hotels with partial rates (complete in Noovy)

| Task | Hotel | ZenithId | Missing |
|------|-------|----------|---------|
| A4.1 | Hampton Inn Miami Beach - Mid Beach | 5106 | BB + SPR, DLX |
| A4.2 | citizenM Miami Brickell hotel | 5079 | BB for SPR, DLX, Suite |
| A4.3 | DoubleTree by Hilton Miami Doral | 5082 | SPR, DLX |

### A5. Cleanup

| Task | Description |
|------|------------|
| A5.1 | Hampton Inn duplicate (854875 + 826299 same ZenithId 5106) — deactivate old |
| A5.2 | Freehand Miami — $33,904 erroneous price — clean up |

---

## Phase 2 — Prediction Engine Accuracy

| Task | Description | Impact |
|------|------------|--------|
| B1 | Fix ML Signal — store price history per-room in SQLite, compute real lag/rolling features at inference | Ensemble becomes truly 3-signal |
| B2 | Fix Historical Signal — use compounding `(1+rate)^days - 1` instead of linear multiply, restore weight to 25-30% | Reactivate a disabled signal |
| B3 | Wire Meta-Learner — write outcomes to signal_accuracy, use get_weight_for_context() in _compute_weights() | Adaptive weights by context |
| B4 | Add cumulative enrichment cap — max ±0.5%/day total | Prevent extreme predictions |
| B5 | Fix Scaler leakage — fit() only on train data in forecaster.py:79 | Improve ML accuracy |
| B6 | Update documentation — CLAUDE.md 50/30/20 → 70/10/20, voters 11 → 14 | Accurate docs |

---

## Phase 3 — Dashboards, MCP, Code Quality

### C. Dashboard fixes

| Task | Description |
|------|------------|
| C1 | Remove duplicate route `/attribution/enrichments` (line 1651 vs 4293) |
| C2 | Fix rules_api.py AttributeError — `run_full_analysis` + `load_scan_history` don't exist |
| C3 | Wire Correlation + Meta-Learner panels in Unified Terminal |
| C4 | Build real walk-forward backtesting |

### D. MCP Tools

| Task | Description |
|------|------------|
| D1 | Renew BrightData token (HTTP 401) |
| D2 | Fix medici-db `price_drops` timeout |
| D3 | Integrate Kiwi flights → demand enrichment |
| D4 | Increase Playwright screenshot timeout 5s → 30s |

### E. Code Quality

| Task | Description |
|------|------------|
| E1 | 36 `except: pass` in prediction pipeline — add logger.warning |
| E2 | Migrate 2 inline SOAP blocks in analytics_router.py to zenith_push.py |
| E3 | Decompose compute_next_day_signals (complexity 37) into 3 helpers |
| E4 | Break up _run_collection_cycle God Function |
| E5 | Move MIN_VOTING_SOURCES to constants.py |

---

## Execution Order

```
Phase 0  →  Scheduler + UI verification (MUST DO FIRST)
  ↓
Phase 1  →  31 Miami hotels fully working (Noovy + SalesOffice)
  ↓
Phase 2  →  Accurate predictions (ML + Historical + Meta-Learner)
  ↓
Phase 3  →  Full dashboards + MCP tools + code quality
```

## Rollback

If anything breaks: `git checkout v2.7.0-pre-sprint6`

## Completion Tag

After all phases: tag `v3.0.0` with full documentation.
