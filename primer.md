# Medici Price Prediction — Session Primer

## Current State (2026-03-16)
- Production system live at medici-prediction-api.azurewebsites.net
- 19 Miami hotels being onboarded to SalesOffice pipeline
- 9/19 already appearing in Innstant B2B as Knowaa Global, 10 syncing
- All 19 configured: Products + Rate Plans + Medici Channel + Availability (19/09/2026 only)
- 340 tests passing, 17 sprints complete

## Active Work
- Hotel inventory completion: monitoring Innstant sync for remaining 10 hotels
- Availability set to 1 for test date 19/09/2026 only ($100 base price)
- After verification: reset availability back to 0

## Key Architecture
- FastAPI + 5 sub-routers under /api/v1/salesoffice
- Prediction: Forward Curve 50% + Historical 30% + ML 20%
- Read-only DB access enforced (never write to medici-db)
- 12 data sources, unified CacheManager

## Systems & Credentials
- Noovy/HT: Medici LIVE / zvi / karpad66
- Innstant B2B: Knowaa / Amit / porat10
- Azure: medici-prediction-rg

## Recent Decisions
- Availability=1 only for single test date, no commercial exposure
- Generator Miami was only hotel needing Product+RatePlan+Medici setup from scratch
- Medici channel in HT Marketplace = key for Innstant connectivity
