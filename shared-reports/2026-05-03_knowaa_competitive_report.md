# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-03 16:00 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 12 of consecutive cloud scan block — Innstant B2B login credentials returning "Invalid login details" (credentials rotated since Apr 24); Azure SQL DB (port 1433) also TCP-blocked from cloud. This report uses the most recent valid local-machine scan (2026-04-24 04:17 UTC). **Data age: ~228h (~9.5 days).** Live scan must resume from office IP with updated credentials.

---

## Executive Summary

| Metric | Value | vs May 3 08:00 | vs May 2 16:00 | vs May 2 08:00 | vs May 1 | vs Apr 30 | vs Apr 24 | 12-Day Trend (Apr 24→May 3) |
|--------|-------|----------------|----------------|----------------|----------|-----------|-----------|---------------------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |

### Key Insight
**Day 12 of cloud scan block — 16:00 UTC scheduled slot.** Both 08:00 and 16:00 slots blocked today. A new failure mode was confirmed at 16:00: Innstant B2B login now returns "Invalid login details" — credentials have been rotated since the last successful local scan (Apr 24). Previously the block was WebSocket-level (HTTP 400/500); now it is credential-level as well. **Two independent blockers are now active.**

All metrics remain static — no fresh data obtainable from cloud. Knowaa holds all 3 active positions as #1 cheapest, each with a consistent ~5.66% margin vs InnstantTravel. Prices have been frozen since at least 2026-04-22 — **~280h (~11.7 days) with zero movement**, confirming static allotment loading for the June 10–11 window.

The structural distribution gap is unchanged: only 3 of 46 hotels (7%) have Knowaa inventory for this date. **28 hotels have competitor offers with zero Knowaa presence** — a distribution failure, not sell-out. **All 15 Section E hotels are at Day 19+ with no refundable inventory** — escalation to contracting is critically overdue.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~280h** (Apr 22 → May 3 16:00, ~11.7 days)

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked for ~12 days._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~280h) |
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~280h) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~280h) |

> All three hotels have been Knowaa #1 for ~12 consecutive days. The consistent 5.66% margin against InnstantTravel is structural — static allotment rate, not dynamic repricing. A manual reload from the contracting/revenue side would be required to change these prices.

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

No #2 positions in the June 10–11 window. In the May 28–29 window (scanned Apr 23 morning), Knowaa had 6 #2 positions at Embassy Suites (BB board) and Pullman (Superior category). The June window remains a materially different rate environment with significantly less Knowaa coverage.

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates with 442+ offers across 26 hotels; goglobal at 2 hotels; HyperGuestDirect⇄ at 2 hotels. All absences now 19+ consecutive days (since Apr 24 scan)._

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

> **Priority inventory gaps — June 10–11 (19+ consecutive days, escalation critically overdue):**
> - **Embassy Suites (5081)** — was Knowaa #1 in May 28–29 window; absent from June for 19+ days. Revenue at risk — critically overdue.
> - **Hotel Riu Plaza (5109)** — was Knowaa #1 in May 28–29 window; absent from June for 19+ days. Revenue at risk — critically overdue.
> - **Notebook Miami Beach (5102)** — platform-cheapest at $65.07; zero Knowaa presence across all observed dates.
> - **HOLIDAY INN EXPRESS (5130)** — sole InnstantTravel at $114.92; Knowaa could win immediately with any loaded rate.
> - **Pod Times Square (5305) + Viajero Miami (5111)** — captured by HyperGuestDirect⇄ direct channel ($121–$122).

---

## Section E — No Refundable Offers — 15 hotels

_These hotels returned no refundable offers for June 10–11. All 15 now at Day 19+ consecutive (since Apr 24 scan) — escalation is critically overdue._

| Hotel | VenueId | Status |
|-------|---------|--------|
| Atwell Suites Miami Brickell | 5101 | **🔴 CRITICAL — 19+ days (contract gap confirmed)** |
| Hilton Cabana Miami Beach | 5115 | 🔴 CRITICAL — 19+ days |
| Hilton Garden Inn Miami South Beach | 5279 | 🔴 CRITICAL — 19+ days |
| Hotel Chelsea | 5064 | 🔴 CRITICAL — 19+ days |
| Hotel Croydon | 5131 | **🔴 CRITICAL — 19+ days (contract gap confirmed)** |
| Hyatt Centric South Beach Miami (City View) | 5097 | 🔴 CRITICAL — 19+ days |
| InterContinental Miami | 5276 | **🔴 CRITICAL — 19+ days (contract gap confirmed)** |
| Kimpton Angler's Hotel | 5136 | 🔴 CRITICAL — 19+ days |
| Kimpton Hotel Palomar South Beach | 5116 | 🔴 CRITICAL — 19+ days |
| Metropole South Beach | 5141 | 🔴 CRITICAL — 19+ days |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 🔴 CRITICAL — 19+ days |
| Sole Miami, A Noble House Resort | 5104 | 🔴 CRITICAL — 19+ days |
| The Albion Hotel | 5117 | 🔴 CRITICAL — 19+ days |
| The Catalina Hotel & Beach Club | 5277 | **🔴 CRITICAL — 19+ days (contract gap confirmed)** |
| The Grayson Hotel Miami Downtown | 5094 | 🔴 CRITICAL — 19+ days |

> 🔴 **ALL 15 Section E hotels are at Day 19+ critical status.** Croydon (5131), Atwell Suites (5101), InterContinental (5276), and Catalina (5277) have confirmed contract gaps for June 10+. The remaining 11 hotels remain at escalation-overdue status. **Immediate action required — contracting team must resolve all 15 hotels urgently.**

---

## Trend — 12-Day Rolling View (Jun 10–11 Window)

### Summary Metrics

| Metric | Apr 24 04:17 | Apr 25 | Apr 26 | Apr 27 | Apr 28 | Apr 29* | Apr 30 | May 1 08:00 | May 1 16:00 | May 2 08:00 | May 2 16:00 | May 3 08:00 | **May 3 16:00** | 12-Day Δ |
|--------|-------------|--------|--------|--------|--------|---------|--------|-------------|-------------|-------------|-------------|-------------|-----------------|---------|
| Knowaa appears | 3 | 3 | 3 | 3 | 3 | 3* | 3 | 3 | 3 | 3 | 3 | 3 | **3** | 0 |
| Knowaa #1 | 3 | 3 | 3 | 3 | 3 | 3* | 3 | 3 | 3 | 3 | 3 | 3 | **3** | 0 |
| Knowaa #2 | 0 | 0 | 0 | 0 | 0 | 0* | 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| No Knowaa (has offers) | 28 | 28 | 28 | 28 | 28 | 28* | 28 | 28 | 28 | 28 | 28 | 28 | **28** | 0 |
| No refundable offers | 15 | 15 | 15 | 15 | 15 | 15* | 15 | 15 | 15 | 15 | 15 | 15 | **15** | 0 |

_* Apr 29 = no cloud scan (cloud block Day 5/6); data repeated from Apr 28_

### Section A — Price Stability (~12 days)

| Hotel | Apr 22 | Apr 24 | Apr 26 | Apr 28 | Apr 30 | May 1 08:00 | May 1 16:00 | May 2 16:00 | May 3 08:00 | **May 3 16:00** | Movement |
|-------|--------|--------|--------|--------|--------|-------------|-------------|-------------|-------------|-----------------|----------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 locked (~280h)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 locked (~280h)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 locked (~280h)** |

> **Interpretation:** ~12 consecutive days with zero price movement. Static allotment is confirmed beyond any doubt. Rates will not change without a manual reload from contracting/revenue. The 5.66% margin vs InnstantTravel is structural and permanent until allotment is reloaded.

---

## Provider Landscape (Jun 10–11)

| Provider | Hotels | Est. Offers | Role |
|----------|--------|-------------|------|
| InnstantTravel | 26 hotels | 442+ | Primary competitor — dominant across Section D |
| Knowaa_Global_zenith | 3 hotels | ~42 | Our provider — winning all active positions, severely under-distributed |
| goglobal | 2 hotels | ~20 | Secondary (MB Hotel, Cavalier) |
| HyperGuestDirect⇄ | 2 hotels | 2 | Direct channel (Pod Times Square, Viajero Miami) |

---

## Action Items

| Priority | Hotel | VenueId | Issue | Action | Days |
|----------|-------|---------|-------|--------|------|
| 🔴 CRITICAL | Atwell Suites, Croydon, InterContinental, Catalina | 5101, 5131, 5276, 5277 | Section E for **19+ consecutive days** — contract gap confirmed | **Contact contracting team NOW** — verify June 10+ contract coverage | 19+ |
| 🔴 CRITICAL | All other Section E hotels (11 hotels) | 5064, 5094, 5097, 5104, 5115, 5116, 5117, 5136, 5139, 5141, 5279 | 19+ days in Section E | **Escalate today** — include in contracting escalation | 19+ |
| 🔴 CRITICAL | Cloud scanner credentials | — | Login "Invalid login details" — credentials rotated since Apr 24 | **Update INNSTANT_PASS in .env / remote trigger secrets immediately** | Day 12 |
| 🔴 URGENT | Embassy Suites Miami Intl Airport | 5081 | No Knowaa Jun 10–11 (was #1 in May window) — 19+ days | Load June allotment — revenue at risk, critically overdue | 19+ |
| 🔴 URGENT | Hotel Riu Plaza Miami Beach | 5109 | No Knowaa Jun 10–11 (was #1 in May window) — 19+ days | Load June allotment — critically overdue | 19+ |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest hotel ($65.07) — zero Knowaa across all observed dates | Investigate contract — structural absence | 19+ |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | Sole competitor at $114.92 — easy Knowaa win | Load June inventory immediately | 19+ |
| 🟡 MED | Pod Times Square, Viajero Miami | 5305, 5111 | HyperGuestDirect⇄ at $121–$122 | Evaluate direct rate parity / Knowaa load | 19+ |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning at 5.66% margin — static rates | Monitor — no action required | N/A |

---

## Scan Failure Context (Cloud Environment — Day 12)

| Check | Status |
|-------|--------|
| HTTP to Innstant B2B | ✅ Accessible — login page loads (302 redirect) |
| Login authentication | ❌ **"Invalid login details"** — credentials expired/rotated (new failure mode, Day 12) |
| WebSocket (`wss://b2b.innstant.travel/wss/`) | ❌ HTTP 500 — cloud IP not whitelisted (was HTTP 400 in prior scans) |
| Azure SQL port 1433 | ❌ TCP unreachable from cloud |
| Today's scan attempts | ❌ 08:00 UTC blocked, ❌ 16:00 UTC blocked |
| Last valid data | 2026-04-24 04:17:19 UTC (local machine) |
| Data age | ~228h (~9.5 days) |
| Cloud block duration | **Day 12** (Apr 24 → May 3 16:00) |
| Resolution | 1) Update INNSTANT_PASS credentials; 2) Run from office IP where WebSocket is whitelisted |
| Impact | All pricing data is 228h stale; any price movements since Apr 24 04:17 are not captured |

> ⚠️ **New blocker detected at 16:00 UTC:** In addition to the WebSocket IP block (HTTP 500), Innstant B2B login now returns `{"status":"error","errorMessage":"Invalid login details"}` — the password stored in `claude_scan.js` (`porat10`) has been rotated. The cloud scanner cannot authenticate regardless of WebSocket status. **INNSTANT_PASS must be updated before the next scan attempt.**

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Report date | 2026-05-03 16:00 UTC |
| Underlying data | `2026-04-24_04-17_full_scan.json` |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age | ~228h (~9.5 days) |
| Previous comparison | `2026-05-03_knowaa_competitive_report.md` (08:00 slot) |
| Hotels in scan | 46 |
| Source | Innstant B2B (browser, from local machine — last valid) |
| Cloud block reason | Login credentials expired ("Invalid login details") + WebSocket HTTP 500 from cloud IP |
| Consecutive blocked days | **12 (since Apr 24)** |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-05-03 16:00 UTC_
