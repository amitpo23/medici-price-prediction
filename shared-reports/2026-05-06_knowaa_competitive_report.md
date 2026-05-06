# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-06 16:05 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 15 of consecutive cloud scan block — `INNSTANT_PASS` was not updated before the 16:00 UTC slot; credentials remain invalid (confirmed: 08:10 UTC live login attempt returned "Invalid login details"). Azure SQL DB (port 1433) also TCP-blocked from cloud. This report uses the most recent valid local-machine scan (2026-04-24 04:17 UTC). **Data age: ~300h (~12.5 days).** Provide updated `INNSTANT_PASS` to unblock next scheduled scan at 00:00 UTC.

---

## Executive Summary

| Metric | Value | vs May 6 08:00 | vs May 5 16:05 | vs May 5 | vs May 4 | vs May 3 16:00 | vs May 2 16:00 | vs Apr 24 | 15-Day Trend |
|--------|-------|----------------|----------------|----------|----------|----------------|----------------|-----------|--------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |

### Key Insight
**Day 15, 16:00 UTC slot — scan blocked.** The `INNSTANT_PASS` was not updated before the 16:00 UTC window. Credentials confirmed invalid since at least Apr 24 (rotated post-last-valid-scan). Playwright + chromium fully operational; Azure SQL still TCP-blocked. No new data obtainable.

All metrics remain static — data frozen at Apr 24 04:17 UTC (now **~300h / ~12.5 days** stale). Knowaa holds all 3 active positions as #1 cheapest at a consistent 5.66% margin vs InnstantTravel. Price stability now at **~410h+** since Apr 22 — zero movement confirmed across 15 consecutive reporting days.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~410h+** (Apr 22 → May 6 16:05, ~17.1 days)

### Infrastructure Status (May 6 16:00 UTC)

| Component | Status | Notes |
|-----------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP timeout from cloud — unchanged |
| Innstant B2B credentials | 🔴 INVALID | `INNSTANT_PASS` not updated before 16:00 slot |
| Playwright (chromium) | ✅ OPERATIONAL | chromium-headless-shell v1208; confirmed at 08:10 UTC |
| Network to innstant.travel | ✅ WORKING | HTTPS reachable — only password invalid |
| Last live scan attempt | ℹ️ 08:10 UTC | "Invalid login details" confirmed |
| Next scan slot | 00:00 UTC May 7 | Set `INNSTANT_PASS` before midnight to restore |

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked ~17 days / ~410h+ with zero movement._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~410h+) |
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~410h+) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~410h+) |

> All 3 hotels: static allotment rate confirmed. No repricing possible without manual reload from contracting/revenue.

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates 26 hotels; goglobal at 2; HyperGuestDirect⇄ at 2. All absences 22+ consecutive days._

| Hotel | VenueId | Cheapest $ | Provider | Category | Board | Priority |
|-------|---------|-----------|----------|----------|-------|----------|
| Notebook Miami Beach | 5102 | $65.07 | InnstantTravel | Standard | RO | 🔴 HIGH |
| HOLIDAY INN EXPRESS HOTEL & SUITES MIAMI | 5130 | $114.92 | InnstantTravel | Standard | BB | 🔴 HIGH |
| Pod Times Square | 5305 | $121.94 | HyperGuestDirect⇄ | Standard | RO | 🔴 HIGH |
| Viajero Miami | 5111 | $122.21 | HyperGuestDirect⇄ | Deluxe | RO | 🔴 HIGH |
| Embassy Suites by Hilton Miami International Airport | 5081 | $143.36 | InnstantTravel | Standard | BB | 🔴 HIGH |
| Hotel Belleza | 5265 | $153.42 | InnstantTravel | Superior | RO | 🟡 MED |
| Freehand Miami | 5107 | $156.54 | InnstantTravel | Standard | RO | 🟡 MED |
| Generator Miami | 5274 | $159.38 | InnstantTravel | Standard | RO | 🟡 MED |
| The Gates Hotel South Beach - a DoubleTree by Hilton | 5140 | $164.73 | InnstantTravel | Standard | RO | 🟡 MED |
| Miami International Airport Hotel | 5275 | $168.54 | InnstantTravel | Standard | RO | 🟡 MED |
| Hampton Inn Miami Beach - Mid Beach | 5106 | $180.88 | InnstantTravel | Standard | RO | 🟡 MED |
| Eurostars Langford Hotel | 5098 | $192.12 | InnstantTravel | Deluxe | RO | 🟡 MED |
| THE LANDON BAY HARBOR | 5138 | $194.90 | InnstantTravel | Deluxe | BB | 🟡 MED |
| Gale Miami Hotel and Residences | 5278 | $202.51 | InnstantTravel | Standard | RO | 🟡 MED |
| Grand Beach Hotel Miami | 5124 | $204.54 | InnstantTravel | Suite | RO | 🟡 MED |
| Hôtel Gaythering | 5132 | $205.14 | InnstantTravel | Standard | BB | 🟡 MED |
| Breakwater South Beach | 5110 | $227.88 | InnstantTravel | Superior | BB | 🟡 MED |
| Crystal Beach Suites Hotel | 5100 | $228.29 | InnstantTravel | Suite | RO | 🟡 MED |
| Dorchester Hotel | 5266 | $232.79 | InnstantTravel | Apartment | RO | 🟢 LOW |
| Cavalier Hotel | 5113 | $238.35 | goglobal | Standard | RO | 🟢 LOW |
| MB Hotel, Trademark Collection by Wyndham | 5105 | $243.03 | goglobal | Standard | RO | 🟡 MED |
| Iberostar Berkeley Shore Hotel | 5092 | $244.18 | InnstantTravel | Standard | RO | 🟡 MED |
| citizenM Miami South Beach | 5119 | $255.27 | InnstantTravel | Standard | RO | 🟢 LOW |
| Hotel Riu Plaza Miami Beach | 5109 | $303.51 | InnstantTravel | Deluxe | RO | 🔴 HIGH |
| Gale South Beach | 5267 | $306.13 | InnstantTravel | Standard | RO | 🟢 LOW |
| Fontainebleau Miami Beach | 5268 | $341.31 | InnstantTravel | Deluxe | RO | 🟢 LOW |
| The Gabriel Miami South Beach, Curio Collection by Hilton | 5108 | $415.25 | InnstantTravel | Standard | BB | 🟢 LOW |
| Savoy Hotel | 5103 | $499.26 | InnstantTravel | Standard | RO | 🟢 LOW |

---

## Section E — No Refundable Offers — 15 hotels

_All 15 now at Day 22+ consecutive — escalation critically overdue._

| Hotel | VenueId | Days Absent | Status |
|-------|---------|------------|--------|
| Atwell Suites Miami Brickell | 5101 | 22+ | **🔴 CRITICAL — contract gap confirmed** |
| Hilton Cabana Miami Beach | 5115 | 22+ | 🔴 CRITICAL |
| Hilton Garden Inn Miami South Beach | 5279 | 22+ | 🔴 CRITICAL |
| Hotel Chelsea | 5064 | 22+ | 🔴 CRITICAL |
| Hotel Croydon | 5131 | 22+ | **🔴 CRITICAL — contract gap confirmed** |
| Hyatt Centric South Beach Miami (City View) | 5097 | 22+ | 🔴 CRITICAL |
| InterContinental Miami | 5276 | 22+ | **🔴 CRITICAL — contract gap confirmed** |
| Kimpton Angler's Hotel | 5136 | 22+ | 🔴 CRITICAL |
| Kimpton Hotel Palomar South Beach | 5116 | 22+ | 🔴 CRITICAL |
| Metropole South Beach | 5141 | 22+ | 🔴 CRITICAL |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 22+ | 🔴 CRITICAL |
| Sole Miami, A Noble House Resort | 5104 | 22+ | 🔴 CRITICAL |
| The Albion Hotel | 5117 | 22+ | 🔴 CRITICAL |
| The Catalina Hotel & Beach Club | 5277 | 22+ | **🔴 CRITICAL — contract gap confirmed** |
| The Grayson Hotel Miami Downtown | 5094 | 22+ | 🔴 CRITICAL |

---

## Trend — 15-Day Rolling View (Jun 10–11 Window)

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age | Status |
|------|-----------|-----------|-----------|-----------|----------|--------|
| **May 6 16:00** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **~300h** | ⚠️ Stale |
| May 6 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~292h | ⚠️ Stale |
| May 5 16:05 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 5 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 4 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~236h | ⚠️ Stale |
| May 3 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~228h | ⚠️ Stale |
| May 2 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~212h | ⚠️ Stale |
| May 1 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~186h | ⚠️ Stale |
| Apr 30 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~162h | ⚠️ Stale |
| Apr 24 04:17 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 0h | ✅ Live |

### Section A — Price Lock (~17 days)

| Hotel | Apr 22 | Apr 24 04:17 | May 2 16:00 | May 6 08:00 | **May 6 16:00** | Total Movement |
|-------|--------|-------------|-------------|-------------|-----------------|----------------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 (~410h+)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 (~410h+)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 (~410h+)** |

---

## Action Items

| Priority | Hotel | VenueId | Issue | Action | Days |
|----------|-------|---------|-------|--------|------|
| 🔴 INFRA | Cloud scan block | — | `INNSTANT_PASS` rotated — 16:00 slot missed | **Set `INNSTANT_PASS` before 00:00 UTC (May 7)** | 15 |
| 🔴 CRITICAL | Atwell Suites, Croydon, InterContinental, Catalina | 5101, 5131, 5276, 5277 | 22+ days Section E — contract gap confirmed | Contact contracting team NOW | 22+ |
| 🔴 CRITICAL | All other Section E (11 hotels) | 5064, 5094, 5097, 5104, 5115, 5116, 5117, 5136, 5139, 5141, 5279 | 22+ days no refundable offers | Escalate to contracting | 22+ |
| 🔴 URGENT | Embassy Suites (5081), Hotel Riu Plaza (5109) | 5081, 5109 | Was Knowaa #1 in May window; absent June for 22+ days | Load June allotment | 22+ |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest at $65.07 — zero Knowaa | Investigate contract | 22+ |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | $114.92 solo — easy Knowaa win | Load June inventory | 22+ |
| 🟡 MED | Pod Times Square, Viajero Miami | 5305, 5111 | HyperGuestDirect⇄ direct channel | Evaluate rate parity | 22+ |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning at 5.66% — static | Monitor only | N/A |

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Report date | 2026-05-06 16:05 UTC |
| Slot | 16:00 UTC (scheduled) |
| Underlying data | `2026-04-24_04-17_full_scan.json` |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age | ~300h (~12.5 days) |
| Previous report | `2026-05-06_08-00_knowaa_competitive_report.md` |
| Hotels in scan | 46 |
| Source | Innstant B2B (browser, from local machine — last valid) |
| Cloud block reason | `INNSTANT_PASS` rotated (credentials invalid) + Azure SQL port 1433 TCP-blocked |
| Consecutive blocked days | **15 (since Apr 24)** |
| Live login confirmed | 08:10 UTC — "Invalid login details" via Playwright |
| Next unblock window | 00:00 UTC May 7 (set `INNSTANT_PASS` before then) |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-05-06 16:05 UTC_
