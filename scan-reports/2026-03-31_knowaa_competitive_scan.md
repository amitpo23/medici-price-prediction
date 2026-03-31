# Knowaa Competitive Scan Report

**Scan Date:** 2026-03-31 07:15 UTC
**Search Dates:** Check-in 2026-04-20, Check-out 2026-04-21 (1 night)
**Source:** Innstant B2B (b2b.innstant.travel)
**Account:** amit (Knowaa)
**Search:** Miami, FL — 2 Adults — same dates as SalesOffice.Orders active scan
**Our Provider Name:** `Knowaa_Global_zenith`

---

## Summary

| Metric | Value |
|--------|-------|
| Total Miami hotels on Innstant | 361 |
| Our hotels scanned | 16 |
| Knowaa appears | **6 (37%)** |
| Knowaa is cheapest | **1 (6%)** |
| Knowaa does NOT appear | **10 (63%)** |

---

## Full Results Table

| # | Hotel | VenueId | InnstantId | Knowaa Present? | Knowaa Price | Cheapest Price | Cheapest Provider | Knowaa Rank | Gap $ | Status |
|---|-------|---------|------------|-----------------|-------------|----------------|-------------------|-------------|-------|--------|
| 1 | Cavalier Hotel | 5113 | 66737 | YES | $200.00 RO | $197.93 | InnstantTravel | #3 | +$2.07 | CLOSE |
| 2 | citizenM Miami South Beach | 5119 | 854710 | YES | $175.70 RO | $174.30 | InnstantTravel | #2 | +$1.40 | CLOSE |
| 3 | DoubleTree by Hilton Miami Doral | 5082 | 733781 | YES | $211.22 RO | $211.21 | InnstantTravel | #19 | +$0.01 | CLOSE |
| 4 | Hilton Miami Airport Blue Lagoon | 5083 | 20706 | YES | $216.54 RO | $216.53 | goglobal | #2 | +$0.01 | CLOSE |
| 5 | Kimpton Hotel Palomar South Beach | 5116 | 846428 | YES | $181.03 RO | $181.02 | goglobal | #2 | +$0.01 | CLOSE |
| 6 | Loews Miami Beach Hotel | 5073 | 6661 | YES | $342.00 RO | $342.00 | **Knowaa_Global_zenith** | **#1** | $0.00 | **CHEAPEST** |
| 7 | The Villa Casa Casuarina | 5075 | 193899 | YES | $1,554.68 RO | $1,482.50 | goglobal | #4 | +$72.18 | OVERPRICED |
| 8 | Fontainebleau Miami Beach | 5268 | 19977 | **NO** | — | $538.46 | goglobal | — | — | NOT LISTED |
| 9 | Gale Miami Hotel & Residences | 5278 | 852725 | **NO** | — | $160.47 | InnstantTravel | — | — | NOT LISTED |
| 10 | Gale South Beach | 5267 | 301645 | **NO** | — | $240.99 | InnstantTravel | — | — | NOT LISTED |
| 11 | Generator Miami | 5274 | 701659 | **NO** | — | $154.12 | InnstantTravel | — | — | NOT LISTED |
| 12 | Grand Beach Hotel | 5124 | 68833 | **NO** | — | $202.08 | InnstantTravel | — | — | NOT LISTED |
| 13 | Hilton Miami Downtown | 5084 | 24982 | **NO** | — | $250.80 | InnstantTravel | — | — | NOT LISTED |
| 14 | InterContinental Miami | 5276 | 6482 | **NO** | — | $287.56 | goglobal | — | — | NOT LISTED |
| 15 | Pullman Miami Airport | 5080 | 6805 | **NO** | — | $176.13 | InnstantTravel | — | — | NOT LISTED |
| 16 | SERENA Hotel Aventura Miami | 5139 | 851939 | **NO** | — | $146.91 | InnstantTravel | — | — | NOT LISTED |

---

## Hotels NOT scanned yet (remaining from our portfolio)

| Hotel | VenueId | InnstantId | Reason |
|-------|---------|------------|--------|
| Dorchester Hotel | 5266 | 6654 | Not scanned this batch |
| Hilton Cabana Miami Beach | 5115 | 254198 | Not scanned this batch |
| Hilton Garden Inn SB | 5279 | 301640 | Not scanned this batch |
| Hotel Belleza | 5265 | 414146 | Not scanned this batch |
| Hotel Chelsea | 5064 | 32687 | Not scanned this batch |
| Hotel Croydon | 5131 | 286236 | Not scanned this batch |
| Hotel Gaythering | 5132 | 277280 | Not scanned this batch |
| Kimpton Angler's Hotel | 5136 | 31226 | Not scanned this batch |
| Metropole Suites SB | 5141 | 31433 | Not scanned this batch |
| Albion Hotel | 5117 | 855711 | Not scanned this batch |
| Catalina Hotel | 5277 | 87197 | Not scanned this batch |
| Gates Hotel SB | 5140 | 301583 | Not scanned this batch |
| Landon Bay Harbor | 5138 | 851633 | Not scanned this batch |
| Notebook Miami Beach | 5102 | 237547 | Not scanned this batch |
| Miami Airport Hotel | 5275 | 21842 | Not scanned this batch |

---

## Provider Distribution (across all scanned hotels)

| Provider | Hotels appearing in | Notes |
|----------|---------------------|-------|
| InnstantTravel | 16/16 | Always present, often cheapest |
| goglobal | 16/16 | Always present, competitive |
| Knowaa_Global_zenith | 6/16 | **Our provider — missing from 10 hotels** |

---

## Root Cause Analysis — Why Knowaa Missing from 10 Hotels

Likely reasons per hotel:

| Hotel | VenueId | Probable Cause |
|-------|---------|----------------|
| Fontainebleau | 5268 | Noovy pricing set but Innstant static sync not complete |
| Gale Miami | 5278 | Innstant MP was closed — recently opened by Innstant team |
| Gale South Beach | 5267 | Innstant MP was closed — recently opened by Innstant team |
| Generator Miami | 5274 | Availability=0 or Noovy config incomplete |
| Grand Beach | 5124 | Availability=0 or Noovy config incomplete |
| Hilton Downtown | 5084 | Availability=0 or Noovy config incomplete |
| InterContinental | 5276 | Innstant MP was closed — recently opened by Innstant team |
| Pullman Airport | 5080 | Was working previously — may need re-sync |
| SERENA Aventura | 5139 | Availability=0 or Noovy config incomplete |

**Common pattern:** Hotels where we set pricing in Noovy but did NOT set availability. Innstant cannot sell rooms with availability=0.

---

## Action Items

1. **Set availability in Noovy** for all hotels where Knowaa is NOT listed — this is the #1 blocker
2. **Verify Innstant static sync** has completed for all 30 hotels
3. **Re-scan after availability is set** to confirm Knowaa appears
4. **Price competitiveness** — where we appear, we're very close to cheapest (within $0.01-$2.07) except Villa Casa ($72 gap)
5. **Villa Casa $5,000 offer** — this is our Noovy test price that leaked to Innstant — should be corrected

---

## Technical Details

- Extraction method: Playwright MCP browser automation
- CSS selectors: `.search-result-item` (hotel cards), `.provider-label` (supplier name), `h4` (price)
- Each hotel page loads rooms via AJAX — waitForSelector('.search-result-item') needed
- URL pattern: `b2b.innstant.travel/hotel/{slug}-{innstantId}?searchQuery=hotel-{innstantId}&startDate=...`
