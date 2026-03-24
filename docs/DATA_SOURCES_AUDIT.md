# Data Sources Audit — 2026-03-24

## MCP medici-db Fix

**Problem:** MCP server used `prediction_readonly` (wrong user, login fails).
**Fix:** Updated `mcp-servers/medici-db/server.py` to use `prediction_reader` (same user as production).
**Status:** Will take effect on next Claude Code session restart.

## Current Access Status

### Working Now

| Source | Type | Auth | Data |
|--------|------|------|------|
| Open-Meteo | REST API | None | Weather forecast + historical, any location |
| Hebcal | REST API | None | Jewish holidays, Torah portions |
| Kiwi.com Flights | MCP tool | Built-in | Real-time flight prices Miami <-> anywhere |
| Web Search | Built-in | None | Google/Bing/Yandex |
| Web Fetch | Built-in | None | Scrape any public URL |
| Playwright | MCP tool | None | Browser automation (Hotel.Tools, Noovy, Innstant) |
| SQLite (local) | File | None | Price snapshots, rules, queues, audit logs |
| Azure CLI | CLI | Authenticated | App Service management, settings |

### Fixed (Next Session)

| Source | Type | Fix |
|--------|------|-----|
| Azure SQL (medici-db) MCP | MCP tool | Updated credentials to `prediction_reader` |

### Needs Setup

| Source | What's Needed | Impact |
|--------|--------------|--------|
| BrightData | Token in .mcp.json (exists) — needs activation | Live OTA prices (Airbnb, Booking, Expedia) |
| Kaggle | KAGGLE_USERNAME + KAGGLE_KEY | Historical hotel datasets for ML |
| PredictHQ | API key | Event forecasting Miami |
| FRED | API key (free) | National hotel PPI indices |

## New External Data Sources Found

### 1. GMCVB Miami & Miami Beach — Official Hotel Metrics
**URL:** https://www.miamiandbeaches.com/gmcvb-partners/research-statistics-reporting
**Data:** Weekly hotel performance (Occupancy, ADR, RevPAR, Demand) by area
**Format:** Tableau dashboard (interactive), PDF reports
**Access:** Free, public
**Frequency:** Weekly
**Latest data (Mar 14, 2026):** Occupancy 87.3%, ADR $315.14, RevPAR $275.04

### 2. FRED — Hotel Producer Price Index
**URL:** https://fred.stlouisfed.org
**Series:**
- `PCU721110721110` — Hotels PPI (monthly, Dec 2003-present)
- `PCU721110721110103` — Luxury Hotels Guestroom Rental PPI (monthly, Jun 1993-present)
- `FLLEIH` — Florida Leisure & Hospitality Employment (monthly)
**Access:** Free API with key (https://fred.stlouisfed.org/docs/api/fred/)

### 3. Florida Dept of Revenue — Hotel Tax Collections
**URL:** https://floridarevenue.com/dataPortal/Pages/TaxResearch.aspx
**Data:** Local tax receipts by county (includes Miami-Dade tourist development tax)
**Format:** Excel/CSV downloads
**Access:** Free, public

### 4. AirDNA / AirROI — Short-Term Rental Data
**URL:** https://www.airdna.co/vacation-rental-data/app/us/florida/miami-beach/overview
**Data:** Airbnb/VRBO occupancy, ADR, revenue by neighborhood
**Miami Beach:** 9,813 listings, 50% occupancy, $358 daily rate
**API:** https://www.airroi.com/api/documentation/ (paid)

### 5. CoStar/STR — Industry Standard Hotel Data
**URL:** https://str.com / https://www.costar.com/products/str-benchmark
**Data:** Hotel performance by chain scale (Luxury/Upscale/Midscale/Economy)
**Access:** Paid subscription
**Note:** This is THE industry standard. Most hotel data in news comes from STR.

### 6. HVS Hotel Valuation Index — Miami-Hialeah
**URL:** https://hvi.hvs.com/market/united-states/Miami_-_Hialeah
**Data:** Hotel valuation, supply/demand, pipeline, market trends
**Access:** Free summary, detailed reports paid

### 7. Newmark Hotel nSights — Miami Market Report
**URL:** https://nmrk.imgix.net/uploads/documents/hotel-nsights/Newmark_VA_Hotel-Nsights-Report_Miami_FL.PDF
**Data:** Market overview, supply pipeline, performance rankings
**Format:** PDF, quarterly

### 8. CBRE Hotels — South Florida Forecast
**URL:** https://www.cbre.com/press-releases/cbre-hotels-forecasts-steady-2025-growth-in-south-florida
**Data:** ADR/RevPAR/Occupancy forecasts, urban vs resort comparison
**Note:** Forecasts +2.5% ADR for 2025 in Miami

### 9. Matthews Real Estate — South Florida Hospitality Report
**URL:** https://www.matthews.com/market_insights/3q24-south-florida-hospitality-market-report
**Data:** Quarterly market report, investment cap rates, supply/demand

### 10. Miami-Dade Tourist Tax Data
**URL:** https://www.miamidade.gov/global/service.page?Mduid_service=ser1499797928395868
**Tax rates:** Miami Beach 7%, Surfside/Bal Harbour 4%, rest of county 6%
**Data:** Monthly tax returns filed by all hotels
**Contact:** 786-336-1040

## Key Market Numbers (as of March 2026)

| Metric | Value | Source |
|--------|-------|--------|
| Miami-Dade Occupancy (week Mar 14) | **87.3%** | GMCVB |
| Miami-Dade ADR (week Mar 14) | **$315.14** | GMCVB |
| Miami-Dade RevPAR (week Mar 14) | **$275.04** | GMCVB |
| Miami-Dade ADR (Jan 2026) | **$287.84** (+12.4% YoY) | Hospitality Net |
| Miami Beach Airbnb ADR | **$358** | AirDNA |
| Miami Beach Airbnb Occupancy | **50%** | AirDNA |
| Hotel PPI Luxury (Feb 2026) | Index from FRED | FRED PCU721110721110103 |

## Integration Recommendations

### Immediate (can build now)
1. **FRED API collector** — Free, already have Python library (`fredapi`). Add PPI series as market benchmark.
2. **GMCVB PDF scraper** — Monthly PDF with ADR/Occupancy/RevPAR. WebFetch + parse.
3. **Web search enrichment** — Periodic search for "Miami hotel occupancy" to capture latest news/reports.

### Medium-term (needs API key)
4. **PredictHQ events** — Better than hardcoded events list
5. **BrightData OTA scraping** — Live Booking.com/Expedia prices for our hotels
6. **AirROI API** — Short-term rental market data as competing supply indicator

### Long-term (needs subscription)
7. **STR/CoStar** — Industry gold standard, but expensive
8. **AirDNA full access** — Detailed neighborhood-level vacation rental data
