# Knowaa SearchLog Report — 2026-04-18T16:29:03Z

**Source:** `SearchResultsSessionPollLog` (DB-based) | **Window:** 24h | **Hotels scanned:** 56 | **Scan duration:** 920s

> **How it works:** Each row in SearchResultsSessionPollLog = one offer from one provider in a search session. A session is defined as (HotelId, RoomCategory, RoomBoard, RequestTime bucketed to minute). For each session we check if Knowaa responded and whether it had the lowest price.

## Summary

| Metric | Value |
|--------|-------|
| Total search sessions | 560 |
| Knowaa responded | **262** (46.8%) |
| Knowaa #1 (cheapest) | **241** (43.0%) |
| #1 rate when present | 92.0% |

## Per Hotel (sorted by Knowaa activity)

| Zenith | Hotel | Sessions | Knowaa % | #1 % | Avg Gap $ |
|--------|-------|----------|----------|------|-----------|
| 5080 | Pullman Miami Airport | 128 | 75.0% | 74.2% | +0.01 |
| 5082 | DoubleTree by Hilton Miami Doral | 134 | 49.3% | 47.8% | +0.08 |
| 5081 | Embassy Suites by Hilton Miami International Airport | 94 | 48.9% | 35.1% | +1.41 |
| 5111 | Viajero Miami | 158 | 24.1% | 20.9% | +1.06 |
| 5109 | Hotel Riu Plaza Miami Beach | 34 | 29.4% | 29.4% | +0.00 |
| 5079 | citizenM Miami Brickell hotel | 9 | 66.7% | 66.7% | +0.00 |
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
| standard | RO | 108 | 83.3% | 75.9% | +0.29 |
| standard | BB | 99 | 16.2% | 16.2% | +0.00 |
| suite | BB | 73 | 21.9% | 20.5% | +0.07 |
| suite | RO | 71 | 98.6% | 85.9% | +0.64 |
| deluxe | RO | 51 | 78.4% | 72.5% | +0.98 |
| deluxe | BB | 48 | 33.3% | 33.3% | +0.00 |
| superior | RO | 43 | 27.9% | 27.9% | +0.00 |
| superior | BB | 42 | 0.0% | 0.0% | — |
| dormitory | RO | 13 | 15.4% | 15.4% | +0.00 |
| deluxe | HB | 6 | 0.0% | 0.0% | — |
| standard | HB | 6 | 0.0% | 0.0% | — |

## Daily Trend

| Date | Sessions | Knowaa % | #1 % |
|------|----------|----------|------|
| 2026-04-18 | 363 | 45.7% | 41.0% |
| 2026-04-17 | 197 | 48.7% | 46.7% |
