# MEMORY LOG — Medici Price Prediction

Last updated: 2026-03-12
Scope: Consolidated memory log of the current multi-turn working session (automation, mapping, validation, remediation, diagnostics).

## 1) Session Objective
Create and verify cross-system alignment between:
- B2BINNSTANT (search/offers/suppliers/prices)
- Noovy / Hotel.Tools (products, meal plans, room categories)
- Medici DB expected mapping (boards/categories per hotel)

Target outcome requested by user:
- Full compatibility validation by hotel/date
- Clear gap report (what is missing where)
- Practical remediation attempts

## 2) High-Level Outcome (Current)
- Full Innstant + Hotel.Tools + DB comparison pipeline is operational.
- Latest global status: 54 hotels total, 9 OK, 45 GAP.
- Main technical blocker: Hotel.Tools product creation API returns HTTP 500 during remediation attempts.
- Because of this backend blocker, automatic closure of all remaining Hotel.Tools gaps is currently blocked.

## 3) What Was Implemented During Session
### A. Innstant validation and evidence extraction
- Built and iterated Innstant automation to:
  - login
  - search per hotel (`searchQuery=hotel-<HotelId>`)
  - open room offers
  - expand more rooms
  - extract suppliers, min/max prices, boards, inferred room categories
- Added robust parsing and extraction logic for room/meal/supplier/price evidence.

### B. DB baseline and expected mapping
- Pulled expected boards/categories from DB mapping tables.
- Fixed schema assumptions and joins (Board/RoomCategory lookup columns).
- Produced baseline coverage files and cross-check inputs.

### C. Cross-system compare engine
- Built/updated comparison script to calculate per-hotel mismatches:
  - Missing in Hotel.Tools
  - Missing in Innstant
  - Supplier and price context
- Generated JSON + CSV reports for actionable gaps.

### D. Noovy/Hotel.Tools remediation attempts
- Ran reference clone process from reference venue across target venues.
- Executed focused (Top 10) and bulk remediation waves.
- Added stricter post-create verification to avoid false-positive “created” reporting.

### E. Deep diagnostics for create failures
- Built dedicated diagnostics script:
  - attempts creation per gap venue
  - captures request payload snippet + HTTP status + response snippet
- Result: 27/27 attempts failed with HTTP 500 (`Something went wrong, please try again`).

## 4) Key Reports Generated
### Main alignment reports
- data/reports/inventory_compare_innstant_hoteltools_1773330416799.json
- data/reports/inventory_compare_innstant_hoteltools_1773334223172.json
- data/reports/inventory_compare_innstant_hoteltools_1773336390979.json
- data/reports/inventory_compare_innstant_hoteltools_1773338342875.json

### Diagnostics and action lists
- data/reports/hoteltools_creation_diagnostics_1773344594407.json
- data/reports/hoteltools_creation_diagnostics_1773344594407.csv
- data/reports/hoteltools_gap_actions_1773338842841.csv

### Consolidated session summary reports
- data/reports/alignment_full_report_1773349431072.md
- data/reports/alignment_full_report_1773349431072.json

## 5) Current Quantitative Snapshot
Based on latest compare report used in this session:
- Total hotels: 54
- OK: 9
- GAP: 45

Gap composition highlights:
- Missing in Hotel.Tools (aggregated):
  - Boards: BB(11), RO(7)
  - Categories: Deluxe(26), Suite(26), Standard(7)
- Missing in Innstant vs expected (aggregated):
  - Boards: BB(27), RO(10)
  - Categories: Suite(36), Deluxe(28), Standard(8), Superior(1)

No-offer hotels on tested date window included:
- Dream South Beach
- Generator Miami
- Hilton Bentley Miami South Beach
- Hilton Cabana Miami Beach
- Kimpton Angler's Hotel

## 6) Root-Cause Notes (Blocking)
Observed during automated Noovy creation attempts:
- Requests include location + venue fields in payload.
- Backend still returns HTTP 500 for all tested gap venues in diagnostics batch.
- This indicates a server-side/permission/business-rule issue in Hotel.Tools, not only client-side selector automation.

## 7) Files/Code Updated During Session (Core)
- scripts/validate_innstant_inventory.js
- scripts/compare_innstant_hoteltools_inventory.js
- scripts/apply_noovy_reference_clone.js
- scripts/add_room_only_mealplan.js
- scripts/hoteltools_creation_diagnostics.js

## 8) Operational Next Steps
1. Resolve Hotel.Tools backend 500 on product create (vendor/platform side).
2. Re-run automated remediation on all remaining gap venues.
3. Re-run full compare and regenerate alignment report.
4. Confirm final closure target: all mapped boards/categories present in Noovy and represented in Innstant results for target dates.

## 9) Session Integrity Note
This memory log is generated from artifacts and context available in the current working session.
If you want, this file can be appended automatically after every major run (compare/diagnostics/remediation) to keep a continuous project memory trail.

## Run Snapshot — 2026-03-12T21:09:33.165Z
- Snapshot-Key: inventory_compare_innstant_hoteltools_1773338342875.json|hoteltools_creation_diagnostics_1773344594407.json|innstant_inventory_validation_1773328247079.json
- Compare report: data/reports/inventory_compare_innstant_hoteltools_1773338342875.json
- Diagnostics report: data/reports/hoteltools_creation_diagnostics_1773344594407.json
- Validation report: data/reports/innstant_inventory_validation_1773328247079.json
- Totals: total=54, ok=9, gap=45
- Diagnostics: attempted=27, success2xx=0, failed4xx5xx=27, exceptions=0
- Innstant validation: hotels=54, passed=3, failed=51

## Run Snapshot — 2026-03-13T06:28:37.170Z
- Snapshot-Key: inventory_compare_innstant_hoteltools_1773338342875.json|hoteltools_creation_diagnostics_1773382357728.json|innstant_inventory_validation_1773328247079.json
- Compare report: data/reports/inventory_compare_innstant_hoteltools_1773338342875.json
- Diagnostics report: data/reports/hoteltools_creation_diagnostics_1773382357728.json
- Validation report: data/reports/innstant_inventory_validation_1773328247079.json
- Totals: total=54, ok=9, gap=45
- Diagnostics: attempted=27, success2xx=0, failed4xx5xx=27, exceptions=0
- Innstant validation: hotels=54, passed=3, failed=51

## Run Snapshot — 2026-03-13T06:52:39.474Z
- Snapshot-Key: inventory_compare_innstant_hoteltools_1773384759321.json|hoteltools_creation_diagnostics_1773382357728.json|innstant_inventory_validation_1773328247079.json
- Compare report: data/reports/inventory_compare_innstant_hoteltools_1773384759321.json
- Diagnostics report: data/reports/hoteltools_creation_diagnostics_1773382357728.json
- Validation report: data/reports/innstant_inventory_validation_1773328247079.json
- Totals: total=54, ok=8, gap=46
- Diagnostics: attempted=27, success2xx=0, failed4xx5xx=27, exceptions=0
- Innstant validation: hotels=54, passed=3, failed=51

## Run Snapshot — 2026-03-26T15:30:00Z — Innstant Hotel Onboarding Response
- Snapshot-Key: noovy_bulk_pricing_28hotels|innstant_letter_response|all_rooms_all_rateplans
- Context: Innstant sent letter listing 30 hotels — 19 connected, 11 not flowing from Noovy, 3 MP were closed (now opened by Innstant). They asked us to verify rooms and dates are properly inserted in Noovy.
- Action taken: Bulk Update pricing via Noovy PMS for all 28 new hotels:
  - Rate: Fixed $1000
  - Date range: 01/08/26 – 10/08/26
  - Rooms: Select All (every room type per hotel)
  - Rate Plans: Select All (every rate plan per hotel — BB, RO, Refundable where applicable)
- Hotels completed (13/28 at session pause):
  1. Cavalier 5113 — Standard × (BB + Refundable)
  2. citizenM 5119 — Standard × (BB + Refundable + RO)
  3. Dorchester 5266 — Standard Room (Double/Twin) × (BB + Room Only)
  4. DoubleTree 5082 — Standard × (BB + Refundable)
  5. Fontainebleau 5268 — **5 room types** (Deluxe Bayview 2Q, Deluxe Bayview King, Oceanview 2Q, Oceanview King, Standard RO) × (BB + Room Only)
  6. Gale Miami 5278 — Standard × (BB + RO)
  7. Gale South Beach 5267 — Standard Room × (BB + RO)
  8. Generator 5274 — Standard × (BB + Room Only)
  9. Grand Beach 5124 — Standard × (BB + Refundable + RO)
  10. Hilton Cabana 5115 — Standard × (BB + Refundable + RO)
  11. Hilton Garden 5279 — Standard × (BB + Room Only)
  12. Hilton Airport 5083 — Standard × (BB + Room Only)
  13. Holiday Inn 5130 — Standard × (BB + Refundable + RO)
- Hotels remaining (15): Belleza 5265, Chelsea 5064, Croydon 5131, Gaythering 5132, InterContinental 5276, Kimpton Anglers 5136, Kimpton Palomar 5116, Loews 5073, Metropole 5141, Miami Airport 5275, Notebook 5102, SERENA 5139, Albion 5117, Catalina 5277, Gates 5140, Landon 5138, Villa Casa 5075
- Previous session (same day): Standard-only pricing was set for all 28 hotels (BB + RO separately). This session adds ALL room types and ALL rate plans.
- Key finding: Fontainebleau has 5 room types (most of any hotel). Most hotels have only Standard.
- Rate plan variations found: "bed and breakfast / bb", "Bed and Breakfast", "bed and brekfast" (typo), "room only / ro", "room only", "Refundable", "Standard_ro"
- Availability: NOT set (user explicitly requested no availability changes)
- Innstant static update: Pending — Innstant said they'll notify when complete
- Next steps after completing all 28: Wait for Innstant static sync, then re-test SOAP for all 30 hotels

## Run Snapshot — 2026-03-22T00:00:00Z
- Snapshot-Key: remediation_baseline_2.0.1|queue_request_models|override_history_window_fix
- App version: 2.0.1
- Git branch: main
- Git commit: 57ebbe1
- Baseline document: docs/REMEDIATION_BASELINE_2026-03-22.md
- Initial remediation slice completed:
  - Added typed request models for override and opportunity queue endpoints.
  - Replaced manual payload coercion on queue endpoints in `src/api/routers/analytics_router.py`.
  - Fixed override history day-window logic in `src/analytics/override_queue.py` to use `timedelta`.
  - Added regression coverage for API validation and month-boundary history filtering.
- Verification:
  - `pytest tests/unit/test_override_queue.py tests/integration/test_api_endpoints.py -q`
  - Result: 69 passed

## Run Snapshot — 2026-03-13T07:41:19.536Z
- Snapshot-Key: inventory_compare_innstant_hoteltools_1773384759321.json|hoteltools_creation_diagnostics_1773386713487.json|innstant_inventory_validation_1773328247079.json
- Compare report: data/reports/inventory_compare_innstant_hoteltools_1773384759321.json
- Diagnostics report: data/reports/hoteltools_creation_diagnostics_1773386713487.json
- Validation report: data/reports/innstant_inventory_validation_1773328247079.json
- Totals: total=54, ok=8, gap=46
- Diagnostics: attempted=27, success2xx=0, failed4xx5xx=24, exceptions=3
- Innstant validation: hotels=54, passed=3, failed=51

## Run Snapshot — 2026-03-14T00:00:00.000Z
- Snapshot-Key: hoteltools_creation_diagnostics_1773386713487.json|noovy_auth_probe_manual_20260314
- Source diagnostics: data/reports/hoteltools_creation_diagnostics_1773386713487.json
- Target venues extracted: 27 (from diagnostics source)
- Reference baseline: venue 2766 products export was previously successful in-session; current session auth then regressed
- Auth status (latest):
  - Noovy context returns `No Venue`
  - GraphQL product queries return `401 User is not authorized`
  - Hotel.Tools probe lands on login page (no active venue context)
- Operational impact:
  - Dry-run/apply remediation is blocked until venue-authorized session is restored
- Immediate next action:
  - Capture one successful manual `createProduct`/`updateProduct` mutation in active browser session, then resume automated dry-run and full apply across all 27 Miami venues

## Session Archive — 2026-03-14 (Full)

### Objective
- User requested end-to-end closure of Miami inventory gaps (room categories + meal boards) using execution-first approach.
- Required strategy pivot: learn from a known-good reference hotel instead of repeated blind create attempts.

### Timeline (Condensed)
1. Switched from legacy create trial-and-error to reference-learning approach.
2. Refactored clone flow to make reference venue configurable (default moved to 5110 via env).
3. Added and executed Noovy export flow from venue 2766 (successful milestone: 18 products exported).
4. Prepared full-target run for all 27 Miami venues from diagnostics source.
5. New blocker emerged: auth context degraded to `No Venue`; Noovy GraphQL returned `401`.
6. Paused apply path and moved to session-recovery flow (manual mutation capture window opened).
7. Added Claude Skill Memory policy to project context and synchronized memory log process.

### Code/Docs Updated In This Session
- `CLAUDE.md`
  - Added **Claude Skill Memory** section with canonical file, update triggers, entry minimum, and active context guardrails.
- `docs/MEMORY_LOG.md`
  - Added latest run snapshot and this full session archive entry.

### Evidence Paths
- `data/reports/hoteltools_creation_diagnostics_1773386713487.json`
- `data/reports/noovy_products_venue_2766_1773496659121.json`

### Confirmed Findings
- Legacy Hotel.Tools create path remains unstable for this workflow (500 history in diagnostics).
- Reference export from Noovy venue 2766 is valid and usable as baseline when auth context is healthy.
- Current blocking state for automation is authorization/session integrity (`No Venue`/`401`).

### Current Blocker
- Noovy/Hotel.Tools session does not expose authorized venue context; automated dry-run/apply cannot safely proceed.

### Next Explicit Step
- Restore venue-authorized session (manual successful create/update mutation capture), then run:
  1) full dry-run on 27 targets,
  2) controlled apply batch,
  3) post-apply verification report.
## Run Snapshot — 2026-03-14T15:08:19Z
- What changed: Added Claude Skill Memory policy, appended full session archive, prepared auth-recovery flow for Miami gap remediation
- Evidence: data/reports/hoteltools_creation_diagnostics_1773386713487.json; data/reports/noovy_products_venue_2766_1773496659121.json
- Blocker: Noovy auth context degraded to No Venue; GraphQL returns 401
- Next step: Restore venue-authorized session, rerun dry-run on 27 venues, then controlled apply and verification

## Run Snapshot — 2026-03-16T08:35:00Z
- What changed:
  - Added split-analysis profiles in analyzer: `all`, `internal_only`, `external_only`.
  - Added free-source connection + split PUT execution script.
  - Added rolling PUT table (CSV + Markdown) with explicit source provenance.
  - Added 6-hour scheduler script for continuous split execution.
- Evidence:
  - `DataAnalysisExpert/split_put_free_sources_20260316_103036.json`
  - `DataAnalysisExpert/put_split_table.csv`
  - `DataAnalysisExpert/put_split_table.md`
  - `docs/PUT_SPLIT_6H_RUNBOOK_2026-03-16.md`
- Current status:
  - Split calculations operational and isolated (no internal/external mixing).
  - Latest split result shows large strategy gap (internal PUT higher than external PUT).
- Blocker:
  - Partial external coverage in current run (e.g., flights NO_DATA, FRED unavailable) lowers external confidence.
- Next step:
  - Keep scheduler running every 6h, monitor table trend, and improve external source availability to raise external signal quality.

## Run Snapshot — 2026-03-22T00:00:00Z
- Snapshot-Key: mobile_ui_baseline_2.0.1|shared_mobile_shell|summary_pages_mobile_slice
- App version: 2.0.1
- Baseline document: docs/MOBILE_UI_BASELINE_2026-03-22.md
- Initial mobile slice completed:
  - Hardened shared responsive shell behavior in `src/templates/static/base.css`.
  - Preserved desktop home layout while improving phone behavior in `src/templates/landing.html`.
  - Improved mobile stacking and spacing in `src/templates/alerts.html`.
  - Added viewport meta and horizontal table overflow handling in `src/templates/health.html`.
- Verification:
  - `get_errors` on edited template/CSS files
  - Result: no errors found

## Run Snapshot — 2026-03-22T00:00:00Z
- Snapshot-Key: options_board_mobile_cards|desktop_table_preserved
- App version: 2.0.1
- What changed:
  - Added mobile card rendering mode to `src/templates/options_board.html`.
  - Kept desktop table rendering and pagination behavior intact.
  - Reused the same detail modal flow for both table rows and mobile cards.
- Verification:
  - `get_errors` on `src/templates/options_board.html`
  - Result: no errors found

## Run Snapshot — 2026-03-22T00:00:00Z
- Snapshot-Key: release_2.0.2|queue_validation_and_mobile_ui_rollup
- App version: 2.0.2
- Consolidated release scope:
  - Queue endpoint request validation hardening in `src/api/routers/analytics_router.py`
  - Rolling-window history fix in `src/analytics/override_queue.py`
  - Regression and integration coverage in `tests/unit/test_override_queue.py` and `tests/integration/test_api_endpoints.py`
  - Initial mobile shell and summary-page rollout in `src/templates/static/base.css`, `src/templates/landing.html`, `src/templates/alerts.html`, `src/templates/health.html`
  - Mobile card mode for `src/templates/options_board.html` with desktop table preserved
- Release documentation:
  - `CHANGELOG.md` updated with `2.0.2`
  - `docs/RELEASE_2.0.2_2026-03-22.md` added
