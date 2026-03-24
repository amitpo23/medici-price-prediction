# Session Handoff — 2026-03-24

## Current Version: v2.5.0-arbitrage-complete

## What Was Built This Session

### Infrastructure
1. **Command Center** (`/dashboard/command-center`) — 3-column trading dashboard
2. **Hotel Segmentation** (`config/hotel_segments.py`) — 4 zones, 4 tiers, peer comparison
3. **GMCVB Benchmarks** (`src/collectors/gmcvb_collector.py`) — official ADR per zone
4. **FRED Collector** (`src/collectors/fred_collector.py`) — Hotel PPI (needs API key)

### Execution System
5. **Override Execute** — PUT → SalesOffice.PriceOverride + Zenith SOAP push
6. **Override Rules** — persistent PUT rules, auto-execute after scan
7. **Opportunity Execute** — CALL → BackOfficeOPT + MED_Opportunities
8. **Opportunity Rules** — persistent CALL rules, 30% margin, $2000/day budget

### Signal Engine
9. **Consensus Signal** (`src/analytics/consensus_signal.py`) — 11 independent voters
10. **Arbitrage Engine** (`src/analytics/arbitrage_engine.py`) — T-timeline, buy/sell points
11. **Scan History endpoint** (`/scan-history/{detail_id}`) — real price data from DB

### Kill Switches (both OFF)
- `OVERRIDE_PUSH_ENABLED=false`
- `OPPORTUNITY_EXECUTE_ENABLED=false`

## Critical Issue: No Real Data Connection

**The entire signal engine, charts, and arbitrage scoring are based on theoretical forward curve — NOT real scan data.**

### Why
- MCP medici-db tool used wrong credentials (`prediction_readonly`)
- Fixed credentials in `mcp-servers/medici-db/server.py` to `prediction_reader`
- **Needs Claude Code session restart to take effect**

### After Restart — First Priority
1. Verify MCP medici-db works: `mcp__medici-db__medici_query` should return data
2. Query `SalesOffice.Log` for real price changes (1.38M rows)
3. Query `RoomPriceUpdateLog` for price updates (86K rows)
4. Fix charts to show real EKG-like price movements
5. Fix consensus voters to use real velocity/momentum from scan data
6. Recalibrate signal thresholds based on real data distribution

### Tables with Real Price History
| Table | Rows | What |
|-------|------|------|
| `SalesOffice.Log` | 1,383,428 | Every action including price changes ("DbRoomPrice: X -> API RoomPrice: Y") |
| `RoomPriceUpdateLog` | 86,199 | Every price update with timestamp |
| `AI_Search_HotelData` | 8,549,466 | Market prices from 129 providers |
| `SearchResultsSessionPollLog` | 8,392,099 | Search results with net/gross prices |
| `SalesOffice.Details` | 7,456 | Current snapshot only (not history) |

### SalesOffice Scan Cycle
- WebJob runs **every 5 minutes** (not 3 hours)
- Updates `SalesOffice.Details` with new prices
- Logs changes to `SalesOffice.Log` (ActionId=3 = Detail Updated, ActionId=6 = Zenith Push)
- Price pattern: "DbRoomPrice: 195.02 -> API RoomPrice: 193.95"
- Real prices change ~10 times per day per room — EKG pattern, not smooth curve

## Test Results Verified
- Override: Breakwater $193.95 → $192.95 verified in Hotel.Tools ✅
- Opportunity: Freehand $93.43 → BackOfficeOPT + MED_Opportunities created ✅
- Override Rules: 787 executions on Breakwater ✅
- Consensus: 11 voters working, calibrated (MIN_VOTING=4) ✅
- 810 unit tests passing ✅

## Git Tags (Revert Points)
| Tag | What |
|-----|------|
| `v2.5.0-arbitrage-complete` | Current — full system |
| `v2.4.4-calibrated` | After voter calibration |
| `v2.3.2-signal-logic-fix` | FC-based signals |
| `v2.3.1-pre-signal-fix` | Old probability-based |
| `v2.2.2-code-review-fixes` | After code review |
| `v2.1.0-ui-baseline` | Before Command Center |

## Documentation
| Doc | Content |
|-----|---------|
| `docs/ARBITRAGE_SIGNAL_MODEL.md` | Full arbitrage philosophy + 11 sources |
| `docs/VOTER_CALIBRATION_GUIDE.md` | All thresholds + how to tune |
| `docs/SIGNAL_LOGIC_CHANGE_2026-03-24.md` | Before/after signal logic |
| `docs/OVERRIDE_EXECUTION.md` | PUT execution system |
| `docs/OPPORTUNITY_EXECUTION.md` | CALL execution system |
| `docs/CODE_REVIEW_FIXES_2026-03-24.md` | 3 critical fixes |
| `docs/DATA_SOURCES_AUDIT.md` | 10 external data sources |
