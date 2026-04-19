# Knowaa SearchLog Report — 2026-04-19T00:17:31Z

**Source:** `SearchResultsSessionPollLog` (DB-based) | **Window:** 24h | **Hotels scanned:** 56 | **Scan duration:** 1050s

> **How it works:** Each row in SearchResultsSessionPollLog = one offer from one provider in a search session. A session is defined as (HotelId, RoomCategory, RoomBoard, RequestTime bucketed to minute). For each session we check if Knowaa responded and whether it had the lowest price.

## Summary

| Metric | Value |
|--------|-------|
| Total search sessions | 746 |
| Knowaa responded | **338** (45.3%) |
| Knowaa #1 (cheapest) | **297** (39.8%) |
| #1 rate when present | 87.9% |

## Per Hotel (sorted by Knowaa activity)

| Zenith | Hotel | Sessions | Knowaa % | #1 % | Avg Gap $ |
|--------|-------|----------|----------|------|-----------|
| 5080 | Pullman Miami Airport | 164 | 73.2% | 72.0% | +0.36 |
| 5082 | DoubleTree by Hilton Miami Doral | 186 | 48.4% | 44.6% | +0.24 |
| 5081 | Embassy Suites by Hilton Miami International Airport | 132 | 47.7% | 29.5% | +3.46 |
| 5111 | Viajero Miami | 220 | 23.2% | 19.5% | +1.03 |
| 5109 | Hotel Riu Plaza Miami Beach | 34 | 29.4% | 29.4% | +0.00 |
| 5079 | citizenM Miami Brickell hotel | 7 | 57.1% | 57.1% | +0.00 |
| 5064 | Hotel Chelsea | 3 | 0.0% | 0.0% | — |

### Hotels with 0 sessions in window (49)

- 5073 — Loews Miami Beach Hotel
- 5075 — The Villa Casa Casuarina
- 5077 — SLS LUX Brickell
- 5083 — Hilton Miami Airport
- 5084 — Hilton Miami Downtown
- 5089 — FAIRWIND HOTEL & SUITES SOUTH BEACH
- 5090 — Dream South Beach
- 5092 — Iberostar Berkeley Shore Hotel
- 5093 — Hilton Bentley Miami South Beach
- 5094 — The Grayson Hotel Miami Downtown
- 5095 — Cadet Hotel
- 5096 — Marseilles Hotel
- 5097 — Hyatt Centric South Beach Miami (City View)
- 5098 — Eurostars Langford Hotel
- 5100 — Crystal Beach Suites Hotel
- 5101 — Atwell Suites Miami Brickell
- 5102 — Notebook Miami Beach
- 5103 — Savoy Hotel
- 5104 — Sole Miami, A Noble House Resort
- 5105 — MB Hotel, Trademark Collection by Wyndham
- 5106 — Hampton Inn Miami Beach - Mid Beach, FL
- 5106 — Hampton Inn Miami Beach - Mid Beach
- 5107 — Freehand Miami
- 5108 — The Gabriel Miami South Beach, Curio Collection by Hilton
- 5110 — Breakwater South Beach
- 5113 — Cavalier Hotel
- 5115 — Hilton Cabana Miami Beach
- 5116 — Kimpton Hotel Palomar South Beach
- 5117 — The Albion Hotel
- 5119 — citizenM Miami South Beach
- 5124 — Grand Beach Hotel Miami
- 5130 — HOLIDAY INN EXPRESS HOTEL & SUITES MIAMI
- 5131 — Hotel Croydon
- 5132 — Hôtel Gaythering
- 5136 — Kimpton Angler's Hotel
- 5138 — THE LANDON BAY HARBOR
- 5139 — SERENA Hotel Aventura Miami, Tapestry Collection by Hilton
- 5140 — The Gates Hotel South Beach - a DoubleTree by Hilton
- 5141 — Metropole South Beach
- 5265 — Hotel Belleza
- 5266 — Dorchester Hotel
- 5267 — Gale South Beach
- 5268 — Fontainebleau Miami Beach
- 5274 — Generator Miami
- 5275 — Miami International Airport Hotel
- 5276 — InterContinental Miami
- 5277 — The Catalina Hotel & Beach Club
- 5278 — Gale Miami Hotel and Residences
- 5279 — Hilton Garden Inn Miami South Beach

## Per Category × Board

| Category | Board | Sessions | Knowaa % | #1 % | Avg Gap $ |
|----------|-------|----------|----------|------|-----------|
| standard | RO | 145 | 83.4% | 69.0% | +0.97 |
| standard | BB | 136 | 14.0% | 14.0% | +0.00 |
| suite | BB | 102 | 19.6% | 19.6% | +0.00 |
| suite | RO | 92 | 98.9% | 83.7% | +1.37 |
| deluxe | RO | 64 | 76.6% | 68.8% | +1.46 |
| deluxe | BB | 62 | 33.9% | 32.3% | +1.07 |
| superior | BB | 56 | 0.0% | 0.0% | — |
| superior | RO | 56 | 26.8% | 26.8% | +0.00 |
| dormitory | RO | 21 | 9.5% | 9.5% | +0.00 |
| deluxe | HB | 6 | 0.0% | 0.0% | — |
| standard | HB | 6 | 0.0% | 0.0% | — |

## Daily Trend

| Date | Sessions | Knowaa % | #1 % |
|------|----------|----------|------|
| 2026-04-19 | 16 | 62.5% | 62.5% |
| 2026-04-18 | 730 | 44.9% | 39.3% |
