# Knowaa Competitive Scan — 46 Hotels

> **Scan date:** 2026-04-24 08:00 UTC (scheduled) | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**

> ⚠️ **Note:** The 08:00 browser scan was blocked — Innstant B2B WebSocket server returned HTTP 400 from this cloud environment (IP restriction on `wss://b2b.innstant.travel/wss/`). Report uses the most recent valid scan (04:17 UTC, ~4h ago). No data loss — all 46 hotels confirmed.

## Summary

| Metric | Value | vs 03:12 UTC |
|--------|-------|-------------|
| Hotels scanned | 46 | - |
| Knowaa appears | **3 (7%)** | 0 |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 |
| Listed but not cheapest | 0 (0%) | 0 |
| Not listed (others have offers) | 28 (61%) | -5 |
| No refundable offers | 15 (33%) | +5 |

## A — Knowaa CHEAPEST (#1) — 3 hotels

| Hotel | VenueId | Knowaa $ | 2nd $ | 2nd Provider | Advantage |
|-------|---------|---------|-------|-------------|----------|
| citizenM Miami Brickell hotel | 5079 | **$177.23** | $187.86 | InnstantTravel | -$10.63 |
| Pullman Miami Airport | 5080 | **$133.45** | $141.46 | InnstantTravel | -$8.01 |
| DoubleTree by Hilton Miami Doral | 5082 | **$182.63** | $193.59 | InnstantTravel | -$10.96 |

## C — Knowaa NOT Listed (competitors active) — 28 hotels

| Hotel | VenueId | Cheapest $ | Provider | Categories | Boards |
|-------|---------|-----------|----------|------------|--------|
| Embassy Suites by Hilton Miami International Airport | 5081 | $143.36 | InnstantTravel | Standard, Suite | BB, RO |
| Iberostar Berkeley Shore Hotel | 5092 | $244.18 | InnstantTravel | Standard | RO |
| Eurostars Langford Hotel | 5098 | $192.12 | InnstantTravel | Deluxe | RO |
| Crystal Beach Suites Hotel | 5100 | $228.29 | InnstantTravel | Suite | RO |
| Notebook Miami Beach | 5102 | $65.07 | InnstantTravel | Standard | RO |
| Savoy Hotel | 5103 | $499.26 | InnstantTravel | Standard, Deluxe | RO, BB |
| MB Hotel, Trademark Collection by Wyndham | 5105 | $243.03 | goglobal | Standard | RO |
| Hampton Inn Miami Beach - Mid Beach | 5106 | $180.88 | InnstantTravel | Standard | RO |
| Freehand Miami | 5107 | $156.54 | InnstantTravel | Standard | RO |
| The Gabriel Miami South Beach, Curio Collection by Hilton | 5108 | $415.25 | InnstantTravel | Standard | BB |
| Hotel Riu Plaza Miami Beach | 5109 | $303.51 | InnstantTravel | Deluxe | RO, BB |
| Breakwater South Beach | 5110 | $227.88 | InnstantTravel | Superior | BB |
| Viajero Miami | 5111 | $122.21 | HyperGuestDirect⇄ | Deluxe | RO |
| Cavalier Hotel | 5113 | $238.35 | goglobal | Standard | RO |
| citizenM Miami South Beach | 5119 | $255.27 | InnstantTravel | Standard | RO |
| Grand Beach Hotel Miami | 5124 | $204.54 | InnstantTravel | Suite | RO |
| HOLIDAY INN EXPRESS HOTEL & SUITES MIAMI | 5130 | $114.92 | InnstantTravel | Standard | BB |
| Hôtel Gaythering | 5132 | $205.14 | InnstantTravel | Standard, Deluxe | BB |
| THE LANDON BAY HARBOR | 5138 | $194.90 | InnstantTravel | Deluxe | BB |
| The Gates Hotel South Beach - a DoubleTree by Hilton | 5140 | $164.73 | InnstantTravel | Standard | RO |
| Hotel Belleza | 5265 | $153.42 | InnstantTravel | Superior, Standard | RO |
| Dorchester Hotel | 5266 | $232.79 | InnstantTravel | Apartment, Suite | RO |
| Gale South Beach | 5267 | $306.13 | InnstantTravel | Standard | RO |
| Fontainebleau Miami Beach | 5268 | $341.31 | InnstantTravel | Deluxe, Standard | RO |
| Generator Miami | 5274 | $159.38 | InnstantTravel | Standard, Dormitory, Deluxe | RO |
| Miami International Airport Hotel | 5275 | $168.54 | InnstantTravel | Standard | RO |
| Gale Miami Hotel and Residences | 5278 | $202.51 | InnstantTravel | Standard, Suite | RO |
| Pod Times Square | 5305 | $121.94 | HyperGuestDirect⇄ | Standard, Dormitory | RO |

## D — No Refundable Offers — 15 hotels

| Hotel | VenueId |
|-------|--------|
| Hotel Chelsea | 5064 |
| The Grayson Hotel Miami Downtown | 5094 |
| Hyatt Centric South Beach Miami (City View) | 5097 |
| Atwell Suites Miami Brickell | 5101 |
| Sole Miami, A Noble House Resort | 5104 |
| Hilton Cabana Miami Beach | 5115 |
| Kimpton Hotel Palomar South Beach | 5116 |
| The Albion Hotel | 5117 |
| Hotel Croydon | 5131 |
| Kimpton Angler's Hotel | 5136 |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 |
| Metropole South Beach | 5141 |
| InterContinental Miami | 5276 |
| The Catalina Hotel & Beach Club | 5277 |
| Hilton Garden Inn Miami South Beach | 5279 |

## Trend vs 03:12 UTC Scan

| Metric | 03:12 | 04:17 | Change |
|--------|-------|-------|--------|
| Knowaa appears | 3 | 3 | 0 |
| Knowaa #1 | 3 | 3 | 0 |
| Not listed | 33 | 28 | -5 |
| No offers | 10 | 15 | +5 |

## WebSocket Scan Failure — Root Cause

The 08:00 UTC browser scan was attempted but could not complete:
- **Login**: ✅ Successful (fresh session: amit/Knowaa)
- **Hotel page nav**: ✅ Loaded via SPF
- **Room search**: ❌ `wss://b2b.innstant.travel/wss/` → HTTP 400 Bad Request (13 retries)
- **Root cause**: Innstant B2B WebSocket server rejects connections from this cloud IP
- **Impact**: All room offers appear empty — not a data issue, it's a network block
- **Resolution needed**: Run next scan from local machine with office IP, or configure WSS proxy/tunnel

---
_Generated by Knowaa Competitive Scanner (Claude agent) — 2026-04-24 08:33:00 UTC | Data from 2026-04-24 04:17:19 UTC_
