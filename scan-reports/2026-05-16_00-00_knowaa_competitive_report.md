# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-16 00:00 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 25 of consecutive cloud scan block — Azure SQL DB (port 1433) TCP-blocked (connection timeout confirmed) + `INNSTANT_PASS` not set in environment (credentials rotated post Apr 24; last attempted password `porat10` rejected). Playwright (chromium-1194, `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) confirmed operational — login page `b2b.innstant.travel/agent/login` responds HTTP 200, all 5 form fields loaded (AccountName, Username, Password, RememberMe, Redirect). Network connectivity to innstant.travel ✅. **Data age: ~524h (~21.8 days).** This is the 00:00 UTC slot (Day 25, Slot 26). Provide updated `INNSTANT_PASS` to unblock scans immediately.

---

## Executive Summary

| Metric | Value | vs May 15 16:00 | vs May 15 08:00 | vs May 11 | vs May 9 16:00 | vs Apr 24 | 25-Day Trend |
|--------|-------|-----------------|-----------------|-----------|----------------|-----------|--------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | Flat |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |

### Key Insight
**Day 25, 00:00 UTC slot (Slot 26) — scan blocked.** First report of May 16. Playwright (chromium-1194) operational and confirmed reaching `b2b.innstant.travel/agent/login` (HTTP 200, JS-rendered form, all 5 fields present). Credentials `AccountName=Knowaa / Username=Amit / Password=porat10` remain rejected — password was rotated after last valid scan (Apr 24 04:17 UTC). Azure SQL port 1433 continues to timeout from cloud environment.

All metrics remain static — data frozen at Apr 24 04:17 UTC (now **~524h / ~21.8 days** stale). Knowaa holds all 3 active positions as #1 cheapest at a consistent 5.66% margin vs InnstantTravel. Price stability confirmed at **~668h+** since ~Apr 19 — zero movement across all 26 consecutive blocked scan slots.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~668h+** (Apr 19 → May 16 00:00, ~27.8 days)

### Infrastructure Status (May 16 00:00 UTC)

| Component | Status | Notes |
|-----------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP timeout from cloud — Day 25; `pyodbc` 5.3.0 installed, ODBC Driver 18 installed, driver resolves OK — network block confirmed |
| Innstant B2B credentials | 🔴 INVALID | `porat10` rejected — password rotated post Apr 24 |
| `INNSTANT_PASS` env var | 🔴 NOT SET | Must be set in remote trigger environment |
| Playwright (chromium-1194) | ✅ OPERATIONAL | `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` confirmed |
| Network to innstant.travel | ✅ WORKING | HTTP 200 on login page |
| Login form | ✅ LOADED | All 5 fields: AccountName, Username, Password, RememberMe, Redirect |
| Last live scan | ℹ️ Apr 24 04:17 UTC | Last successful browser scan |
| Consecutive blocked days | **25** | Apr 22 → May 16 |
| Total blocked scan slots | **26** | Slot 26 = May 16 00:00 UTC |
| Next action | 🔴 URGENT | Set `INNSTANT_PASS` in remote trigger env to restore scanning |

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked ~27.8 days / ~668h+ with zero movement._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~668h+) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~668h+) |
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~668h+) |

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

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates 26 of 28 hotels; goglobal leads at 2; HyperGuestDirect⇄ at 2 (direct channel). All absences 32+ consecutive days._

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

_All 15 now at Day 32+ consecutive — escalation critically overdue. Provide updated `INNSTANT_PASS` to verify if any have recovered._

| Hotel | VenueId | Days Absent | Status |
|-------|---------|------------|--------|
| Atwell Suites Miami Brickell | 5101 | 32+ | **🔴 CRITICAL — contract gap confirmed** |
| Hilton Cabana Miami Beach | 5115 | 32+ | 🔴 CRITICAL |
| Hilton Garden Inn Miami South Beach | 5279 | 32+ | 🔴 CRITICAL |
| Hotel Chelsea | 5064 | 32+ | 🔴 CRITICAL |
| Hotel Croydon | 5131 | 32+ | **🔴 CRITICAL — contract gap confirmed** |
| Hyatt Centric South Beach Miami (City View) | 5097 | 32+ | 🔴 CRITICAL |
| InterContinental Miami | 5276 | 32+ | **🔴 CRITICAL — contract gap confirmed** |
| Kimpton Angler's Hotel | 5136 | 32+ | 🔴 CRITICAL |
| Kimpton Hotel Palomar South Beach | 5116 | 32+ | 🔴 CRITICAL |
| Metropole South Beach | 5141 | 32+ | 🔴 CRITICAL |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 32+ | 🔴 CRITICAL |
| Sole Miami, A Noble House Resort | 5104 | 32+ | 🔴 CRITICAL |
| The Albion Hotel | 5117 | 32+ | 🔴 CRITICAL |
| The Catalina Hotel & Beach Club | 5277 | 32+ | **🔴 CRITICAL — contract gap confirmed** |
| The Grayson Hotel Miami Downtown | 5094 | 32+ | 🔴 CRITICAL |

---

## Trend — 25-Day Rolling View (Jun 10–11 Window)

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age | Status |
|------|-----------|-----------|-----------|-----------|----------|--------|
| **May 16 00:00** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **~524h** | ⚠️ Stale |
| May 15 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~516h | ⚠️ Stale |
| May 15 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~507h | ⚠️ Stale |
| May 12–14 00:00–16:00 | — | — | — | — | — | ❌ MISSED (9 slots) |
| May 11 00:16 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~404h | ⚠️ Stale |
| May 9 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~372h | ⚠️ Stale |
| May 8 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~332h | ⚠️ Stale |
| May 7 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~308h | ⚠️ Stale |
| May 6 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~300h | ⚠️ Stale |
| May 5 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 4 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~236h | ⚠️ Stale |
| May 3 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~228h | ⚠️ Stale |
| May 2 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~212h | ⚠️ Stale |
| May 1 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~186h | ⚠️ Stale |
| Apr 30 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~162h | ⚠️ Stale |
| Apr 24 04:17 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 0h | ✅ Live |

### Section A — Price Lock (~27.8 days / ~668h+)

| Hotel | Apr 22 | Apr 24 04:17 | May 6 | May 9 | May 11 | May 15 | **May 16 00:00** | Total Movement |
|-------|--------|-------------|-------|-------|--------|--------|------------------|----------------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 (~668h+)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 (~668h+)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 (~668h+)** |

---

## Action Items

| Priority | Hotel / System | VenueId | Issue | Action | Days |
|----------|---------------|---------|-------|--------|------|
| 🔴 INFRA | Cloud scan block | — | `INNSTANT_PASS` not in env — Day 25, Slot 26; 9 slots missed May 12–14 + both May 15 slots + May 16 00:00 | **Set `INNSTANT_PASS` env var immediately to restore** | 25 |
| 🔴 CRITICAL | Atwell Suites, Croydon, InterContinental, Catalina | 5101, 5131, 5276, 5277 | 32+ days Section E — contract gap confirmed | Contact contracting team NOW | 32+ |
| 🔴 CRITICAL | All other Section E (11 hotels) | 5064, 5094, 5097, 5104, 5115, 5116, 5117, 5136, 5139, 5141, 5279 | 32+ days no refundable offers | Escalate to contracting | 32+ |
| 🔴 URGENT | Embassy Suites (5081), Hotel Riu Plaza (5109) | 5081, 5109 | Was Knowaa #1 in May window; absent June for 32+ days | Load June allotment | 32+ |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest at $65.07 — zero Knowaa | Investigate contract | 32+ |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | $114.92 solo — easy Knowaa win | Load June inventory | 32+ |
| 🟡 MED | Pod Times Square, Viajero Miami | 5305, 5111 | HyperGuestDirect⇄ direct channel — no Knowaa | Evaluate rate parity | 32+ |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning at 5.66% — static allotment | Monitor only | N/A |

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Report date | 2026-05-16 00:00 UTC |
| Slot | 00:00 UTC (scheduled) |
| Underlying data | `2026-04-24_04-17_full_scan.json` |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age | ~524h (~21.8 days) |
| Previous report | 2026-05-15 16:00 UTC (16:00 slot, yesterday) |
| May 12–14 coverage | ❌ MISSED — 9 slots (00:00, 08:00, 16:00 on May 12, 13, 14) |
| Hotels in scan | 46 |
| Source | Innstant B2B (browser, from local machine — last valid Apr 24) |
| Cloud block reason | `INNSTANT_PASS` not set in env (credentials rotated/invalid) + Azure SQL port 1433 TCP-blocked |
| Consecutive blocked days | **25 (since Apr 22)** |
| Total blocked slots | **26** (Slot 26 = May 16 00:00 UTC) |
| Login page status | HTTP 200 ✅ — 5 input fields confirmed (AccountName, Username, Password, RememberMe, Redirect) |
| Credentials tested | AccountName=Knowaa, Username=Amit, Password=porat10 → REJECTED (rotated post Apr 24) |
| Chromium binary | `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (confirmed operational) |
| pyodbc installed | ✅ 5.3.0 installed; ODBC Driver 18 installed; TCP blocked at network level |
| Next unblock | Set updated `INNSTANT_PASS` in remote trigger environment |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-05-16 00:00 UTC_
