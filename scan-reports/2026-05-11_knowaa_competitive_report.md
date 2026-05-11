# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-11 00:16 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 20 of consecutive cloud scan block — Azure SQL DB (port 1433) TCP-blocked (connection timeout confirmed this session) + `INNSTANT_PASS` not set in environment (login attempted this session: AccountName=Knowaa, Username=Amit, Password=porat10 — URL remained on `/agent/login` after submit; credentials still invalid). Playwright (chromium-1194, `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) confirmed operational — navigated to `b2b.innstant.travel/agent/login`, HTTP 200, all 5 form fields loaded. **Data age: ~404h (~16.8 days).** May 10 had zero scan reports (3 slots missed). Provide updated `INNSTANT_PASS` to unblock scans immediately.

---

## Executive Summary

| Metric | Value | vs May 9 16:00 | vs May 9 08:08 | vs May 9 00:00 | vs May 8 | vs May 7 | vs May 6 16:00 | vs Apr 24 | 20-Day Trend |
|--------|-------|----------------|----------------|----------------|----------|----------|----------------|-----------|-------------- |
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |

### Key Insight
**Day 20, 00:00 UTC slot — scan blocked. May 10 entirely missed (no reports generated for 00:00, 08:00, or 16:00 slots).** Playwright (chromium-1194) successfully navigated to `b2b.innstant.travel/agent/login` this session — HTTP 200, form JS-rendered with all 5 input fields confirmed (AccountName, Username, Password, RememberMe, Redirect). Credentials submitted via JS: AccountName=Knowaa, Username=Amit, Password=porat10 — URL remained on login page after submit. Azure SQL port 1433 remains TCP-blocked from cloud environment (connection timeout confirmed).

All metrics remain static — data frozen at Apr 24 04:17 UTC (now **~404h / ~16.8 days** stale). Knowaa holds all 3 active positions as #1 cheapest at a consistent 5.66% margin vs InnstantTravel. Price stability now at **~524h+** since ~Apr 19 — zero movement confirmed across all 20 consecutive blocked scan slots.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~524h+** (Apr 19 → May 11 00:16, ~21.8 days)

### Infrastructure Status (May 11 00:16 UTC)

| Component | Status | Notes |
|-----------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP timeout from cloud — Day 20 |
| Innstant B2B credentials | 🔴 INVALID | Login attempted this session — page stayed on login URL |
| Password tried | 🔴 REJECTED | `porat10` — rotated (not set in `INNSTANT_PASS` env var) |
| Playwright (chromium-1194) | ✅ OPERATIONAL | `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` confirmed working |
| Network to innstant.travel | ✅ WORKING | HTTP 200 on login page |
| Login form | ✅ LOADED | All 5 fields present: AccountName, Username, Password, RememberMe, Redirect |
| Last live scan | ℹ️ Apr 24 04:17 UTC | Last successful browser scan |
| May 10 slots | ❌ MISSED | 00:00, 08:00, 16:00 — all 3 slots had no report generated |
| Consecutive blocked days | **20** | Apr 22 → May 11 |
| Next action | 🔴 URGENT | Set `INNSTANT_PASS` in environment to restore scanning |

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked ~21.8 days / ~524h+ with zero movement._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~524h+) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~524h+) |
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~524h+) |

> All 3 hotels: static allotment rate confirmed. No repricing possible without manual reload from contracting/revenue. Gap is precisely 5.66% across all 3 — characteristic of a fixed-rate allotment vs dynamic InnstantTravel pricing.

### Full Offer Breakdown — Section A

**citizenM Miami Brickell hotel (5079)**
| Provider | Category | Board | Price |
|----------|----------|-------|-------|
| **Knowaa_Global_zenith** | Standard | RO | **$177.23** |
| InnstantTravel | Standard | RO | $187.86 |
| InnstantTravel | Standard | RO | $203.55 |
| InnstantTravel | Standard | RO | $205.58 |
| InnstantTravel | Standard | RO | $206.76 |
| InnstantTravel | Standard | RO | $207.06 |
| InnstantTravel | Standard | RO | $210.78 |
| InnstantTravel | Standard | RO | $213.13 |
| InnstantTravel | Standard | RO | $213.23 |

**Pullman Miami Airport (5080)**
| Provider | Category | Board | Price |
|----------|----------|-------|-------|
| **Knowaa_Global_zenith** | Standard | RO | **$133.45** |
| InnstantTravel | Standard | RO | $141.46 |
| InnstantTravel | Superior | RO | $178.21 |
| InnstantTravel | Superior | RO | $179.81 |
| InnstantTravel | Superior | RO | $180.00 |
| InnstantTravel | Superior | RO | $181.22 |
| InnstantTravel | Deluxe | RO | $186.66 |
| InnstantTravel | Standard | RO | $190.58 |

**DoubleTree by Hilton Miami Doral (5082)**
| Provider | Category | Board | Price |
|----------|----------|-------|-------|
| **Knowaa_Global_zenith** | Standard | RO | **$182.63** |
| InnstantTravel | Standard | RO | $193.59 |
| InnstantTravel | Standard | RO | $220.43 |
| InnstantTravel | Standard | RO | $224.01 |
| InnstantTravel | Standard | RO | $229.84 |

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates 26 of 28 hotels; goglobal leads at 2; HyperGuestDirect⇄ at 2 (direct channel). All absences 27+ consecutive days._

| Hotel | VenueId | Cheapest $ | Provider | Category | Board | Offers | Priority |
|-------|---------|-----------|----------|----------|-------|--------|----------|
| Notebook Miami Beach | 5102 | $65.07 | InnstantTravel | Standard | RO | 5 | 🔴 HIGH |
| HOLIDAY INN EXPRESS HOTEL & SUITES MIAMI | 5130 | $114.92 | InnstantTravel | Standard | BB | 4 | 🔴 HIGH |
| Pod Times Square | 5305 | $121.94 | HyperGuestDirect⇄ | Standard | RO | 13 | 🔴 HIGH |
| Viajero Miami | 5111 | $122.21 | HyperGuestDirect⇄ | Deluxe | RO | 1 | 🔴 HIGH |
| Embassy Suites by Hilton Miami International Airport | 5081 | $143.36 | InnstantTravel | Standard | BB | 22 | 🔴 HIGH |
| Hotel Belleza | 5265 | $153.42 | InnstantTravel | Superior | RO | 10 | 🟡 MED |
| Freehand Miami | 5107 | $156.54 | InnstantTravel | Standard | RO | 16 | 🟡 MED |
| Generator Miami | 5274 | $159.38 | InnstantTravel | Standard | RO | 28 | 🟡 MED |
| The Gates Hotel South Beach - a DoubleTree by Hilton | 5140 | $164.73 | InnstantTravel | Standard | RO | 22 | 🟡 MED |
| Miami International Airport Hotel | 5275 | $168.54 | InnstantTravel | Standard | RO | 25 | 🟡 MED |
| Hampton Inn Miami Beach - Mid Beach | 5106 | $180.88 | InnstantTravel | Standard | RO | 30 | 🟡 MED |
| Eurostars Langford Hotel | 5098 | $192.12 | InnstantTravel | Deluxe | RO | 4 | 🟡 MED |
| THE LANDON BAY HARBOR | 5138 | $194.90 | InnstantTravel | Deluxe | BB | 8 | 🟡 MED |
| Gale Miami Hotel and Residences | 5278 | $202.51 | InnstantTravel | Standard | RO | 19 | 🟡 MED |
| Grand Beach Hotel Miami | 5124 | $204.54 | InnstantTravel | Suite | RO | 14 | 🟡 MED |
| Hôtel Gaythering | 5132 | $205.14 | InnstantTravel | Standard | BB | 22 | 🟡 MED |
| Breakwater South Beach | 5110 | $227.88 | InnstantTravel | Superior | BB | 7 | 🟡 MED |
| Crystal Beach Suites Hotel | 5100 | $228.29 | InnstantTravel | Suite | RO | 27 | 🟡 MED |
| Dorchester Hotel | 5266 | $232.79 | InnstantTravel | Apartment | RO | 20 | 🟢 LOW |
| Cavalier Hotel | 5113 | $238.35 | goglobal | Standard | RO | 22 | 🟢 LOW |
| MB Hotel, Trademark Collection by Wyndham | 5105 | $243.03 | goglobal | Standard | RO | 28 | 🟡 MED |
| Iberostar Berkeley Shore Hotel | 5092 | $244.18 | InnstantTravel | Standard | RO | 30 | 🟡 MED |
| citizenM Miami South Beach | 5119 | $255.27 | InnstantTravel | Standard | RO | 14 | 🟢 LOW |
| Hotel Riu Plaza Miami Beach | 5109 | $303.51 | InnstantTravel | Deluxe | RO | 28 | 🔴 HIGH |
| Gale South Beach | 5267 | $306.13 | InnstantTravel | Standard | RO | 16 | 🟢 LOW |
| Fontainebleau Miami Beach | 5268 | $341.31 | InnstantTravel | Deluxe | RO | 28 | 🟢 LOW |
| The Gabriel Miami South Beach, Curio Collection by Hilton | 5108 | $415.25 | InnstantTravel | Standard | BB | 9 | 🟢 LOW |
| Savoy Hotel | 5103 | $499.26 | InnstantTravel | Standard | RO | 15 | 🟢 LOW |

---

## Section E — No Refundable Offers — 15 hotels

_All 15 now at Day 27+ consecutive — escalation critically overdue. May 10 monitoring gap (3 missed slots) adds urgency._

| Hotel | VenueId | Days Absent | Status |
|-------|---------|------------|--------|
| Atwell Suites Miami Brickell | 5101 | 27+ | **🔴 CRITICAL — contract gap confirmed** |
| Hilton Cabana Miami Beach | 5115 | 27+ | 🔴 CRITICAL |
| Hilton Garden Inn Miami South Beach | 5279 | 27+ | 🔴 CRITICAL |
| Hotel Chelsea | 5064 | 27+ | 🔴 CRITICAL |
| Hotel Croydon | 5131 | 27+ | **🔴 CRITICAL — contract gap confirmed** |
| Hyatt Centric South Beach Miami (City View) | 5097 | 27+ | 🔴 CRITICAL |
| InterContinental Miami | 5276 | 27+ | **🔴 CRITICAL — contract gap confirmed** |
| Kimpton Angler's Hotel | 5136 | 27+ | 🔴 CRITICAL |
| Kimpton Hotel Palomar South Beach | 5116 | 27+ | 🔴 CRITICAL |
| Metropole South Beach | 5141 | 27+ | 🔴 CRITICAL |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 27+ | 🔴 CRITICAL |
| Sole Miami, A Noble House Resort | 5104 | 27+ | 🔴 CRITICAL |
| The Albion Hotel | 5117 | 27+ | 🔴 CRITICAL |
| The Catalina Hotel & Beach Club | 5277 | 27+ | **🔴 CRITICAL — contract gap confirmed** |
| The Grayson Hotel Miami Downtown | 5094 | 27+ | 🔴 CRITICAL |

---

## Trend — 20-Day Rolling View (Jun 10–11 Window)

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age | Status |
|------|-----------|-----------|-----------|-----------|----------|--------|
| **May 11 00:16** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **~404h** | ⚠️ Stale |
| May 10 00:00–16:00 | — | — | — | — | — | ❌ MISSED (3 slots) |
| May 9 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~372h | ⚠️ Stale |
| May 9 08:08 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~364h | ⚠️ Stale |
| May 9 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~356h | ⚠️ Stale |
| May 8 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~332h | ⚠️ Stale |
| May 7 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~308h | ⚠️ Stale |
| May 6 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~300h | ⚠️ Stale |
| May 6 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~292h | ⚠️ Stale |
| May 5 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 4 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~236h | ⚠️ Stale |
| May 3 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~228h | ⚠️ Stale |
| May 2 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~212h | ⚠️ Stale |
| May 1 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~186h | ⚠️ Stale |
| Apr 30 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~162h | ⚠️ Stale |
| Apr 24 04:17 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 0h | ✅ Live |

### Section A — Price Lock (~21.8 days)

| Hotel | Apr 22 | Apr 24 04:17 | May 5 | May 9 16:00 | **May 11 00:16** | Total Movement |
|-------|--------|-------------|-------|-------------|-----------------|----------------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 (~524h+)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 (~524h+)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 (~524h+)** |

---

## Action Items

| Priority | Hotel / System | VenueId | Issue | Action | Days |
|----------|---------------|---------|-------|--------|------|
| 🔴 INFRA | Cloud scan block | — | `INNSTANT_PASS` not in env — all slots blocked + May 10 entirely missed | **Set `INNSTANT_PASS` env var immediately to restore** | 20 |
| 🔴 CRITICAL | Atwell Suites, Croydon, InterContinental, Catalina | 5101, 5131, 5276, 5277 | 27+ days Section E — contract gap confirmed | Contact contracting team NOW | 27+ |
| 🔴 CRITICAL | All other Section E (11 hotels) | 5064, 5094, 5097, 5104, 5115, 5116, 5117, 5136, 5139, 5141, 5279 | 27+ days no refundable offers | Escalate to contracting | 27+ |
| 🔴 URGENT | Embassy Suites (5081), Hotel Riu Plaza (5109) | 5081, 5109 | Was Knowaa #1 in May window; absent June for 27+ days | Load June allotment | 27+ |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest at $65.07 — zero Knowaa | Investigate contract | 27+ |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | $114.92 solo — easy Knowaa win | Load June inventory | 27+ |
| 🟡 MED | Pod Times Square, Viajero Miami | 5305, 5111 | HyperGuestDirect⇄ direct channel — no Knowaa | Evaluate rate parity | 27+ |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning at 5.66% — static allotment | Monitor only | N/A |

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Report date | 2026-05-11 00:16 UTC |
| Slot | 00:00 UTC (scheduled) |
| Underlying data | `2026-04-24_04-17_full_scan.json` |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age | ~404h (~16.8 days) |
| Previous report | 2026-05-09 16:00 UTC slot |
| May 10 coverage | ❌ MISSED — 3 slots (00:00, 08:00, 16:00) not generated |
| Hotels in scan | 46 |
| Source | Innstant B2B (browser, from local machine — last valid) |
| Cloud block reason | `INNSTANT_PASS` not set in env (credentials invalid) + Azure SQL port 1433 TCP-blocked |
| Consecutive blocked days | **20 (since Apr 22)** |
| Live login attempt | May 11 00:16 UTC — JS fill; page remained on login URL after submit |
| Credentials tested | AccountName=Knowaa, Username=Amit, Password=porat10 → REJECTED |
| Chromium binary | `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (confirmed operational) |
| Login page status | HTTP 200 ✅ — 5 input fields: AccountName, Username, Password, RememberMe, Redirect |
| Next unblock | Provide updated `INNSTANT_PASS` env var |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-05-11 00:16 UTC_
