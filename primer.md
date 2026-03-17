# Medici Price Prediction — Session Primer

## Version: v2026.03.17-forecast-ui
**Tag:** `v2026.03.17-forecast-ui`
**Date:** 2026-03-17
**Tests:** 356 passed, 24.5% coverage
**Production:** medici-prediction-api.azurewebsites.net — HTTP 200, cache ready

## Current State
- **Azure:** B2 (3.5GB RAM, 2 cores), Always On = true — OOM fixed
- **Hotels:** 34 Miami hotels configured in Noovy with Products + RO + BB rate plans
  - Pullman Miami: full availability (all combos, until 12/2027)
  - Other 33: test availability on 15/10/2026 only
  - 8/34 confirmed in Innstant B2B, rest syncing (24h)
- **UI:** Options Board with 4 chart types in detail modal:
  1. Primary option chart (scans + forward curve + confidence band)
  2. Source comparison chart (multi-source overlay)
  3. Scan-only zoom (price/delta metric toggle)
  4. **NEW: Forecast candlestick** (historical candles + forecast with band, 7/14/30 day horizon)
- **Skills:** price-prediction (ARIMA/ETS/Prophet) + price-visualization (candlestick, trend bands)
- **API:** 90+ endpoints, 23 hotels in collection cycle, 4,673 rooms

## What Was Done (2026-03-17 sessions)

### Infrastructure
- Azure B1 → B2 upgrade (1.75GB → 3.5GB RAM) — fixes OOM crash at 1.3GB
- Always On enabled — no more cold starts
- Multiple deploys via `az webapp deploy --type zip`

### SalesOffice Investigation
- Root cause: OnlyNight = 1 order per night, WebJob doesn't rescan completed orders
- BB requires availability per product×rate plan combination in Noovy
- OOM crash kills analysis after 15 minutes (1.3GB on B1)
- Orders not updated since March 12 (WebJob stuck)
- Pullman has 779 rows across 72 dates (4 categories × 2 boards)

### Hotel Configuration (34 hotels)
- Added RO + BB rate plans to 16 hotels that only had "Refundable"
- Created products for Villa Casa Casuarina + Wyndham Garden Miami
- Set availability=1 for all 34 hotels (Oct 15 test date)
- Verified 8/34 visible in Innstant B2B from Knowaa Global

### UI Improvements
- Hotel filter dropdown, Board filter, Check-in date range
- Auto-refresh toggle (30s/60s/5m)
- PUT Analysis summary panel
- Forecast candlestick chart (4th chart in detail modal)
- Fetch timeout fix with AbortController
- Server-side search across all pages

### Documentation
- HOTEL_ONBOARDING_REQUEST.md — instructions for medici-web developer
- SALESOFFICE_ISSUES_REPORT.md — OOM, stale orders, scanning gaps
- Price-prediction + price-visualization skills installed

## Key Architecture
- FastAPI + 5 sub-routers under /api/v1/salesoffice
- Prediction: Forward Curve 50% + Historical 30% + ML 20%
- Charts: Canvas 2D API (no external library)
- Read-only DB access enforced via SQLAlchemy event listener
- Collector cycle: every 3 hours (10,800s)

## Systems & Credentials
- Noovy/HT: Medici LIVE / zvi / karpad66
- Innstant B2B: Knowaa / Amit / porat10
- Azure: medici-prediction-rg, medici-prediction-api, plan B2
- GitHub: amitpo23/medici-price-prediction

## Open Items
1. 26/34 hotels still syncing to Innstant — verify in 24h
2. 11 additional hotels from HOTEL_ONBOARDING_REQUEST.md pending medici-web developer
3. WebJob on medici-backend stuck since March 12 — needs investigation
4. Consider S1/P1 if B2 still OOMs with growing hotel count
