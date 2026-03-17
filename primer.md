# Medici Price Prediction — Session Primer

## Current State (2026-03-17)
- Production system live at medici-prediction-api.azurewebsites.net
- 34 Miami hotels configured in Noovy with Products + Rate Plans (RO + BB) + Availability
- Pullman Miami: full availability (all combos, until 12/2027)
- Other 33 hotels: test availability on 15/10/2026 only
- OOM crash issue (1.3GB on B1 tier) — needs S1/P1 upgrade
- 356 tests passing

## What Was Done This Session
- Investigated SalesOffice low result count (Pullman)
  - Root cause: OnlyNight system = 1 order per night, WebJob doesn't rescan
  - BB requires availability per product×rate plan combination
  - OOM crash (1.3GB RAM) kills analysis after 15 minutes
  - Orders not updated since March 12 (WebJob stuck)
- Added RO + BB rate plans to 16 hotels that only had "Refundable"
- Created products for Villa Casa Casuarina + Wyndham Garden
- Set availability=1 for all 34 hotels (Oct 15 test date)
- Added hotel-readiness endpoint + UI improvements (filters, auto-refresh, PUT panel)
- Installed price-prediction + price-visualization skills
- Multiple deploys to Azure via CLI

## Next Steps — DO IN NEXT SESSION
1. **Integrate price-prediction into Options Board UI**
   - Add forecast tab in Chart & Analysis detail modal
   - Candlestick chart option alongside existing price chart
   - Confidence bands on forward curve visualization
   - DO NOT change existing functionality — ADD alongside it
2. **Fix OOM** — upgrade Azure plan or optimize analysis
3. **Enable Always On** on Azure
4. **Verify 34 hotels appear in Innstant B2B** (after sync)

## Key Architecture
- FastAPI + 5 sub-routers under /api/v1/salesoffice
- Prediction: Forward Curve 50% + Historical 30% + ML 20%
- Read-only DB access enforced
- Skills: price-prediction (ARIMA/ETS), price-visualization (plotly candlestick)

## Systems & Credentials
- Noovy/HT: Medici LIVE / zvi / karpad66
- Innstant B2B: Knowaa / Amit / porat10
- Azure: medici-prediction-rg, medici-prediction-api
