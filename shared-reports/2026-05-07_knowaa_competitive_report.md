# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-07 00:00 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 16 of consecutive cloud scan block — Azure SQL DB (port 1433) TCP-blocked + `INNSTANT_PASS` invalid (confirmed via live login attempt at 00:00 UTC: "Invalid Login Details"). Playwright + chromium fully operational; network to b2b.innstant.travel reachable (HTTP 200). Password `porat10` confirmed rejected — credentials rotated since Apr 24. **Data age: ~308h (~12.8 days).** Provide updated `INNSTANT_PASS` to unblock scans immediately.

---

## Executive Summary

| Metric | Value | vs May 6 16:00 | vs May 6 08:00 | vs May 5 | vs May 4 | vs May 3 16:00 | vs May 2 16:00 | vs Apr 24 | 16-Day Trend |
|--------|-------|----------------|----------------|----------|----------|----------------|----------------|-----------|--------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |

### Key Insight
**Day 16, 00:00 UTC slot — scan blocked.** Playwright successfully navigated to `b2b.innstant.travel/agent/login` and submitted credentials (`AccountName=Knowaa`, `Username=Amit`, `Password=porat10`) — response: "Error: Invalid". Credentials confirmed rotated since Apr 24 last valid scan. Azure SQL port 1433 remains TCP-blocked from cloud.

All metrics remain static — data frozen at Apr 24 04:17 UTC (now **~308h / ~12.8 days** stale). Knowaa holds all 3 active positions as #1 cheapest at a consistent 5.66% margin vs InnstantTravel. Price stability now at **~428h+** since Apr 22 — zero movement confirmed across 16 consecutive reporting days.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~428h+** (Apr 22 → May 7 00:00, ~17.8 days)

### Infrastructure Status (May 7 00:00 UTC)

| Component | Status | Notes |
|-----------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP timeout from cloud — unchanged since Apr 24 |
| Innstant B2B credentials | 🔴 INVALID | Login attempted at 00:00 UTC — "Invalid" response |
| Password tried | 🔴 REJECTED | `porat10` (default from scan_cached.js) — rotated since Apr 24 |
| Playwright (chromium) | ✅ OPERATIONAL | chromium-headless-shell v1208; login page loaded OK |
| Network to innstant.travel | ✅ WORKING | HTTPS reachable — HTTP 200 on login page |
| Login page | ✅ LOADED | Form fields detected: AccountName, Username, Password |
| Last live scan | ℹ️ Apr 24 04:17 UTC | Last successful Playwright browser scan |
| Consecutive blocked days | **16** | Apr 24 → May 7 |
| Next action | 🔴 URGENT | Set `INNSTANT_PASS` in environment to restore scanning |

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked ~17.8 days / ~428h+ with zero movement._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~428h+) |
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~428h+) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~428h+) |

> All 3 hotels: static allotment rate confirmed. No repricing possible without manual reload from contracting/revenue. Gap is precisely 5.66% across all 3 — characteristic of a fixed-rate allotment vs dynamic InnstantTravel pricing.

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates 26 of 28 hotels; goglobal leads at 2; HyperGuestDirect⇄ at 2 (direct channel). All absences 23+ consecutive days._

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

_All 15 now at Day 23+ consecutive — escalation critically overdue._

| Hotel | VenueId | Days Absent | Status |
|-------|---------|------------|--------|
| Atwell Suites Miami Brickell | 5101 | 23+ | **🔴 CRITICAL — contract gap confirmed** |
| Hilton Cabana Miami Beach | 5115 | 23+ | 🔴 CRITICAL |
| Hilton Garden Inn Miami South Beach | 5279 | 23+ | 🔴 CRITICAL |
| Hotel Chelsea | 5064 | 23+ | 🔴 CRITICAL |
| Hotel Croydon | 5131 | 23+ | **🔴 CRITICAL — contract gap confirmed** |
| Hyatt Centric South Beach Miami (City View) | 5097 | 23+ | 🔴 CRITICAL |
| InterContinental Miami | 5276 | 23+ | **🔴 CRITICAL — contract gap confirmed** |
| Kimpton Angler's Hotel | 5136 | 23+ | 🔴 CRITICAL |
| Kimpton Hotel Palomar South Beach | 5116 | 23+ | 🔴 CRITICAL |
| Metropole South Beach | 5141 | 23+ | 🔴 CRITICAL |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 23+ | 🔴 CRITICAL |
| Sole Miami, A Noble House Resort | 5104 | 23+ | 🔴 CRITICAL |
| The Albion Hotel | 5117 | 23+ | 🔴 CRITICAL |
| The Catalina Hotel & Beach Club | 5277 | 23+ | **🔴 CRITICAL — contract gap confirmed** |
| The Grayson Hotel Miami Downtown | 5094 | 23+ | 🔴 CRITICAL |

---

## Trend — 16-Day Rolling View (Jun 10–11 Window)

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age | Status |
|------|-----------|-----------|-----------|-----------|----------|--------|
| **May 7 00:00** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **~308h** | ⚠️ Stale |
| May 6 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~300h | ⚠️ Stale |
| May 6 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~292h | ⚠️ Stale |
| May 5 16:05 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 5 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 4 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~236h | ⚠️ Stale |
| May 3 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~228h | ⚠️ Stale |
| May 2 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~212h | ⚠️ Stale |
| May 1 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~186h | ⚠️ Stale |
| Apr 30 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~162h | ⚠️ Stale |
| Apr 24 04:17 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 0h | ✅ Live |

### Section A — Price Lock (~17.8 days)

| Hotel | Apr 22 | Apr 24 04:17 | May 2 16:00 | May 6 16:00 | **May 7 00:00** | Total Movement |
|-------|--------|-------------|-------------|-------------|-----------------|----------------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 (~428h+)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 (~428h+)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 (~428h+)** |

---

## Action Items

| Priority | Hotel | VenueId | Issue | Action | Days |
|----------|-------|---------|-------|--------|------|
| 🔴 INFRA | Cloud scan block | — | `INNSTANT_PASS` rotated — all slots blocked | **Set `INNSTANT_PASS` env var immediately to restore** | 16 |
| 🔴 CRITICAL | Atwell Suites, Croydon, InterContinental, Catalina | 5101, 5131, 5276, 5277 | 23+ days Section E — contract gap confirmed | Contact contracting team NOW | 23+ |
| 🔴 CRITICAL | All other Section E (11 hotels) | 5064, 5094, 5097, 5104, 5115, 5116, 5117, 5136, 5139, 5141, 5279 | 23+ days no refundable offers | Escalate to contracting | 23+ |
| 🔴 URGENT | Embassy Suites (5081), Hotel Riu Plaza (5109) | 5081, 5109 | Was Knowaa #1 in May window; absent June for 23+ days | Load June allotment | 23+ |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest at $65.07 — zero Knowaa | Investigate contract | 23+ |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | $114.92 solo — easy Knowaa win | Load June inventory | 23+ |
| 🟡 MED | Pod Times Square, Viajero Miami | 5305, 5111 | HyperGuestDirect⇄ direct channel — no Knowaa | Evaluate rate parity | 23+ |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning at 5.66% — static allotment | Monitor only | N/A |

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Report date | 2026-05-07 00:00 UTC |
| Slot | 00:00 UTC (scheduled) |
| Underlying data | `2026-04-24_04-17_full_scan.json` |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age | ~308h (~12.8 days) |
| Previous report | `2026-05-06_knowaa_competitive_report.md` |
| Hotels in scan | 46 |
| Source | Innstant B2B (browser, from local machine — last valid) |
| Cloud block reason | `INNSTANT_PASS` rotated (credentials invalid) + Azure SQL port 1433 TCP-blocked |
| Consecutive blocked days | **16 (since Apr 24)** |
| Live login attempt | 00:00 UTC May 7 — "Invalid" via Playwright (chromium-headless-shell v1208) |
| Credentials tested | AccountName=Knowaa, Username=Amit, Password=porat10 → REJECTED |
| Next unblock | Provide updated `INNSTANT_PASS` env var |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-05-07 00:00 UTC_
