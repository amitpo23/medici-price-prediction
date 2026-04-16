# Knowaa SearchLog Report — 2026-04-16T19:18:27Z

**Source:** `SearchResultsSessionPollLog` (DB-based) | **Window:** 24h | **Hotels scanned:** 56 | **Scan duration:** 960s

> **How it works:** Each row in SearchResultsSessionPollLog = one offer from one provider in a search session. A session is defined as (HotelId, RoomCategory, RoomBoard, RequestTime bucketed to minute). For each session we check if Knowaa responded and whether it had the lowest price.

## Summary

| Metric | Value |
|--------|-------|
| Total search sessions | 952 |
| Knowaa responded | **442** (46.4%) |
| Knowaa #1 (cheapest) | **354** (37.2%) |
| #1 rate when present | 80.1% |

## Per Hotel (sorted by Knowaa activity)

| Zenith | Hotel | Sessions | Knowaa % | #1 % | Avg Gap $ |
|--------|-------|----------|----------|------|-----------|
| 5080 | Pullman Miami Airport | 213 | 73.7% | 59.2% | +0.21 |
| 5082 | DoubleTree by Hilton Miami Doral | 212 | 49.1% | 46.7% | +0.27 |
| 5081 | Embassy Suites by Hilton Miami International Airport | 171 | 46.8% | 25.1% | +6.29 |
| 5111 | Viajero Miami | 279 | 26.2% | 20.8% | +2.10 |
| 5109 | Hotel Riu Plaza Miami Beach | 57 | 29.8% | 29.8% | +0.00 |
| 5079 | citizenM Miami Brickell hotel | 15 | 73.3% | 73.3% | +0.00 |
| 5064 | Hotel Chelsea | 5 | 0.0% | 0.0% | — |

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
| standard | RO | 172 | 82.6% | 68.6% | +1.60 |
| standard | BB | 162 | 13.6% | 13.6% | +0.00 |
| suite | BB | 124 | 21.0% | 17.7% | +0.35 |
| suite | RO | 117 | 99.1% | 75.2% | +3.14 |
| deluxe | RO | 91 | 75.8% | 49.5% | +0.97 |
| deluxe | BB | 85 | 32.9% | 27.1% | +0.27 |
| superior | RO | 78 | 35.9% | 32.1% | +1.53 |
| superior | BB | 74 | 0.0% | 0.0% | — |
| dormitory | RO | 23 | 21.7% | 21.7% | +0.00 |
| deluxe | HB | 10 | 0.0% | 0.0% | — |
| standard | HB | 10 | 0.0% | 0.0% | — |

## Daily Trend

| Date | Sessions | Knowaa % | #1 % |
|------|----------|----------|------|
| 2026-04-16 | 952 | 46.4% | 37.2% |
