# Medici Price Prediction — Session Primer

## Current State (2026-03-28)

### Production
- **Azure B2**, Always On, 22 hotels, ~4,000 rooms
- **Deploy zip:** 276 files
- **Tests:** 1,469 passed + 2 skipped, 44.9% coverage
- **All endpoints 200** — status, home, options, dashboard, trading, consensus, health, terminal-v2
- **Branch:** main (Phase 1-4 + TD-1 + TD-2 + Terminal V2 complete)
- **Version:** v2.7.0

### Session 2026-03-27/28 — Terminal V2 (Unified Trading Dashboard)

**Goal:** Replace 9 separate dashboards with a single Bloomberg/TWS-style trading terminal.

**What Was Built:**
- `src/templates/terminal_v2.html` — 51,767 chars, full Bloomberg-style terminal
- `src/analytics/terminal_v2_page.py` — thin page generator
- Route: `/dashboard/terminal-v2`
- `tests/unit/test_terminal_v2_page.py` — 6 unit tests

**Terminal V2 Features:**
- **Signal Table** — 500 rooms, 13 columns: Hotel, Cat/Board, Check-in, T, Price, Signal, Cons%, Δ24h, Sparkline, ↑/↓, Rate/d, Direction, Target
- **3 Chart Panels** — Price (Scan History + Forward Curve + Confidence Band), Velocity (rate of change bars), Voter Timeline (14 agents)
- **14 Voter Toggles** — FC, Velocity, Events, Competitors, Seasonality, Flights, Weather, Peers, Bookings, Historical, Benchmark, ScanDrop, Provider, Margin + Consensus bar
- **HeatMap Mode** — Hotel × T-bucket matrix (10 hotels × 5 buckets), clickable to filter
- **Filter Strip** — Signal (All/CALL/PUT), Hotel, Zone, T Range, Category, Board, Search, Reset — all client-side
- **Right Sidebar** — Alerts, Override Queue (399 pending), Opportunity Queue (4 pending), Rules, Selected Info
- **Execution Actions:**
  - Override Selected (single PUT → `/override/request`)
  - Buy Selected (single CALL → `/opportunity/request`)
  - Override All PUTs in View (bulk → `/group/override`)
  - Buy All CALLs in View (bulk → `/group/opportunity`)
  - Trigger Rules Now (both override + opportunity rules)
- **Two-Stage Loading** — lite profile for fast table, full profile in background for sparklines
- **Auto-Refresh** — 60s table, 30s alerts
- **Keyboard Navigation** — ↑/↓ arrows
- **Dark Bloomberg Theme** — monospace font, sharp corners, data-dense

**Production Verified:** 40+ browser tests, 0 console errors, all execution endpoints returning 200 OK.

**URL:** https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/dashboard/terminal-v2

**17 commits** — 1 spec, 1 plan, 1 feature, 14 production fixes (field mapping, API endpoints, chart dates, queue format, bulk actions)

**Dashboards Replaced (Phase 3 pending):**
- Command Center (`/dashboard/command-center`)
- Unified Terminal (`/dashboard/unified-terminal`)
- Macro Terminal (`/dashboard/macro`)
- Trading Terminal (`/dashboard/terminal`)
- Options Board (`/options/view`)
- Charts Page (`/charts`)
- Path Forecast (`/dashboard/path-forecast`)
- Override Queue (`/dashboard/override-queue`)
- Opportunity Queue (`/dashboard/opportunity-queue`)

### Previous Sessions Summary

**v2.6.2 (2026-03-26):**
- Production stability fixes — MED_SearchHotels OOM, unified terminal timeout
- Sprint TD-1: removed 3,503 lines dead HTML
- Sprint TD-2: 76 collector tests enabled
- Innstant hotel onboarding — 13/28 completed

**v2.6.0-v2.6.1 (2026-03-24-26):**
- Phase 4 dashboards, Unified Trading Terminal
- MCP medici-db fix, voter enrichment, FRED collector
- Command Center enhancements, Knowledge Base

**v2.5.0 and earlier:** See CLAUDE.md for full sprint history.

---

## Next Session — Planned

- **Terminal V2 Phase 2:** Voter overlays as icons on price chart, synced crosshair, sidebar collapse
- **Terminal V2 Phase 3:** Redirect old dashboards → terminal-v2, remove old templates after 30 days
- **Complete remaining 15 hotels** — Noovy pricing for Innstant onboarding
- **FRED API key** — get key from fred.stlouisfed.org, set in Azure App Service
- **MED_Book integration** — wire collect_med_book_predictions() into main collection cycle
