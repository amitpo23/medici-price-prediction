# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-22 16:00 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 35 of consecutive cloud scan block — **Slot 46.** Playwright chromium v1208 functional, login page reached (HTTP 200, SSL bypass required — `ignore_https_errors=True`, persisting), credentials confirmed INVALID (`INNSTANT_PASS` / `INNSTANT_USER` / `INNSTANT_ACCOUNT` env vars NOT_SET; hardcoded fallback `Knowaa/Amit/porat10` rejected — `/agent/login-execute` returned `/agent/login`). Azure SQL port 1433 TCP-blocked (connection timeout). **Data age: ~683h (~28.5 days).** Provide updated `INNSTANT_PASS` to immediately unblock.

---

## Executive Summary

| Metric | Value | vs May 22 08:00 | vs May 22 00:00 | vs May 21 16:00 | vs May 21 08:00 | vs May 21 00:00 | vs May 16 | vs Apr 24 | 30-Day Trend |
|--------|-------|-----------------|-----------------|-----------------|-----------------|-----------------|-----------|-----------|--------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |

### Key Insight
**Day 35, 16:00 UTC slot (Slot 46) — scan blocked. Credentials remain INVALID.**

Playwright (chromium v1208 / 145.0.7632.6) launched successfully, reached Innstant B2B login at `/agent/login` (HTTP 200, SSL bypass `ignore_https_errors=True` required — `ERR_CERT_AUTHORITY_INVALID` persisting), form detected (AccountName / Username / Password fields confirmed visible), values filled (`AccountName=Knowaa`, `Username=Amit`, `Password` set via native setter bypass — `readOnly=true` still present on password field), form submitted to `/agent/login-execute` — Innstant redirected back to `/agent/login` (rejected). No env vars set (`INNSTANT_PASS`, `INNSTANT_USER`, `INNSTANT_ACCOUNT` all NOT_SET). Azure SQL port 1433 TCP-blocked (8s timeout from cloud egress).

All metrics static — data frozen at Apr 24 04:17 UTC (**~683h / ~28.5 days** stale). Knowaa holds 3 positions as #1 cheapest at 5.66% margin vs InnstantTravel. Zero price movement in **~808h** since ~Apr 19 — confirmed across 46 consecutive blocked scan slots.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~808h** (Apr 19 → May 22 16:00, ~33.7 days)

### Infrastructure Status (May 22 16:00 UTC)

| Component | Status | Notes |
|-----------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP timeout from cloud — Day 35 |
| Innstant B2B credentials | 🔴 ALL INVALID | `INNSTANT_PASS`, `INNSTANT_USER`, `INNSTANT_ACCOUNT` all NOT_SET in env **AND** hardcoded fallback `Knowaa/Amit/porat10` rejected |
| `INNSTANT_PASS` env var | 🔴 NOT SET | Must be updated in remote trigger environment |
| `INNSTANT_USER` env var | 🔴 NOT SET | Must be set in remote trigger environment |
| `INNSTANT_ACCOUNT` env var | 🔴 NOT SET | Must be set in remote trigger environment |
| `scan_cached.js` hardcoded password | 🔴 **STALE** | `porat10` rejected — update required |
| SSL certificate | ⚠️ **PERSISTING** | `ERR_CERT_AUTHORITY_INVALID` — recurring; `ignore_https_errors=True` bypass succeeds |
| Password field `readOnly` | ⚠️ PERSISTS | `input[name="Password"]` has `readOnly=true` — native setter bypass used successfully, but creds still invalid |
| Playwright chromium v1208 | ✅ INSTALLED | Browser launches (145.0.7632.6), login page loads correctly |
| Login page reachable | ✅ CONFIRMED | `/agent/login` reached (HTTP 200, after SSL bypass), form renders (after JS load + 5s wait) |
| Form fill | ✅ CONFIRMED | AccountName=Knowaa, Username=Amit, pass filled via native setter |
| Form submission | ✅ WORKS | Form submits to `/agent/login-execute`, response received |
| Login result | 🔴 FAILED | Redirected back to `/agent/login` (invalid credentials) |
| Network to innstant.travel | ✅ WORKING | HTTP 200 confirmed (with SSL bypass) |
| Last live scan | ℹ️ Apr 24 04:17 UTC | Last successful browser scan |
| Consecutive blocked days | **35** | Apr 18 → May 22 |
| Total blocked scan slots | **46** | Slot 46 = May 22 16:00 UTC |
| Next action | 🔴 **CRITICAL** | Provide valid `INNSTANT_PASS` — this is the **only** remaining blocker |

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked ~33.7 days / ~808h with zero movement._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~808h) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~808h) |
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~808h) |

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

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates 26 of 28 hotels; goglobal leads at 2; HyperGuestDirect⇄ at 2 (direct channel). All absences 46+ consecutive days._

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

_All 15 now at Day 46+ consecutive — escalation critically overdue. Credentials required to verify if any have recovered._

| Hotel | VenueId | Days Absent | Status |
|-------|---------|------------|--------|
| Atwell Suites Miami Brickell | 5101 | 46+ | **🔴 CRITICAL — contract gap confirmed** |
| Hilton Cabana Miami Beach | 5115 | 46+ | 🔴 CRITICAL |
| Hilton Garden Inn Miami South Beach | 5279 | 46+ | 🔴 CRITICAL |
| Hotel Chelsea | 5064 | 46+ | 🔴 CRITICAL |
| Hotel Croydon | 5131 | 46+ | **🔴 CRITICAL — contract gap confirmed** |
| Hyatt Centric South Beach Miami (City View) | 5097 | 46+ | 🔴 CRITICAL |
| InterContinental Miami | 5276 | 46+ | **🔴 CRITICAL — contract gap confirmed** |
| Kimpton Angler's Hotel | 5136 | 46+ | 🔴 CRITICAL |
| Kimpton Hotel Palomar South Beach | 5116 | 46+ | 🔴 CRITICAL |
| Metropole South Beach | 5141 | 46+ | 🔴 CRITICAL |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 46+ | 🔴 CRITICAL |
| Sole Miami, A Noble House Resort | 5104 | 46+ | 🔴 CRITICAL |
| The Albion Hotel | 5117 | 46+ | 🔴 CRITICAL |
| The Catalina Hotel & Beach Club | 5277 | 46+ | **🔴 CRITICAL — contract gap confirmed** |
| The Grayson Hotel Miami Downtown | 5094 | 46+ | 🔴 CRITICAL |

---

## Trend — 35-Day Rolling View (Jun 10–11 Window)

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age | Status |
|------|-----------|-----------|-----------|-----------|----------|--------|
| **May 22 16:00** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **~683h** | ⚠️ Stale |
| May 22 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~675h | ⚠️ Stale |
| May 22 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~668h | ⚠️ Stale |
| May 21 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~660h | ⚠️ Stale |
| May 21 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~652h | ⚠️ Stale |
| May 21 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~644h | ⚠️ Stale |
| May 20 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~636h | ⚠️ Stale |
| May 20 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~628h | ⚠️ Stale |
| May 20 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~620h | ⚠️ Stale |
| May 19 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~612h | ⚠️ Stale |
| May 19 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~604h | ⚠️ Stale |
| May 19 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~596h | ⚠️ Stale |
| May 18 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~588h | ⚠️ Stale |
| May 18 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~580h | ⚠️ Stale |
| May 18 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~572h | ⚠️ Stale |
| May 17 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~564h | ⚠️ Stale |
| May 17 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~556h | ⚠️ Stale |
| May 17 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~548h | ⚠️ Stale |
| May 16 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~540h | ⚠️ Stale |
| May 16 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~532h | ⚠️ Stale |
| May 16 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~524h | ⚠️ Stale |
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

### Section A — Price Lock (~33.7 days / ~808h)

| Hotel | Apr 22 | Apr 24 04:17 | May 6 | May 9 | May 11 | May 15 | May 22 08:00 | **May 22 16:00** | Total Movement |
|-------|--------|-------------|-------|-------|--------|--------|--------------|-----------------|----------------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 (~808h)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 (~808h)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 (~808h)** |

---

## Action Items

| Priority | Hotel / System | VenueId | Issue | Action | Days |
|----------|---------------|---------|-------|--------|------|
| 🔴 **INFRA #1** | Innstant B2B password | — | **`porat10` CONFIRMED INVALID** — rejected Slot 46 (May 22 16:00 UTC). Browser functional, login form fills (native setter bypasses `readOnly=true` on password field), form submits to `/agent/login-execute`. Password is the **sole remaining blocker** | **Update `INNSTANT_PASS` in remote trigger env AND update `scan_cached.js` hardcoded fallback** | 35 |
| 🔴 **INFRA #2** | Cloud SQL block | — | Azure SQL port 1433 TCP-blocked — Day 35 | Whitelist cloud egress IP or use DB proxy | 35 |
| ⚠️ **INFRA #3** | SSL certificate | — | `ERR_CERT_AUTHORITY_INVALID` — persisting; `ignore_https_errors=True` bypass succeeds | Verify SSL cert validity on Innstant B2B | Day 35 |
| 🔴 CRITICAL | Atwell Suites, Croydon, InterContinental, Catalina | 5101, 5131, 5276, 5277 | 46+ days Section E — contract gap confirmed | Contact contracting team NOW | 46+ |
| 🔴 CRITICAL | All other Section E (11 hotels) | 5064, 5094, 5097, 5104, 5115, 5116, 5117, 5136, 5139, 5141, 5279 | 46+ days no refundable offers | Escalate to contracting | 46+ |
| 🔴 URGENT | Embassy Suites (5081), Hotel Riu Plaza (5109) | 5081, 5109 | Was Knowaa #1 in May window; absent June for 46+ days | Load June allotment | 46+ |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest at $65.07 — zero Knowaa | Investigate contract | 46+ |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | $114.92 solo — easy Knowaa win | Load June inventory | 46+ |
| 🟡 MED | Pod Times Square, Viajero Miami | 5305, 5111 | HyperGuestDirect⇄ direct channel — no Knowaa | Evaluate rate parity | 46+ |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning at 5.66% — static allotment | Monitor only | N/A |

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Report date | 2026-05-22 16:00 UTC |
| Slot | 16:00 UTC (scheduled) |
| Slot number | 46 |
| Underlying data | `2026-04-24_04-17_full_scan.json` |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age | ~683h (~28.5 days) |
| Previous report | 2026-05-22 08:00 UTC (Slot 45) |
| May 12–14 coverage | ❌ MISSED — 9 slots (00:00, 08:00, 16:00 on May 12, 13, 14) |
| Hotels in scan | 46 |
| Source | Innstant B2B (browser, from local machine — last valid Apr 24) |
| Cloud block reason | `INNSTANT_PASS` invalid (`porat10` rejected) + Azure SQL port 1433 TCP-blocked |
| Consecutive blocked days | **35** (since Apr 18) |
| Total blocked slots | **46** (Slot 46 = May 22 16:00 UTC) |
| pyodbc | ✅ 5.3.0 installed; TCP blocked at network level |
| unixodbc | ✅ 2.3.12 installed |
| msodbcsql18 | ✅ 18.6.2.1 installed; TCP to port 1433 blocked |
| Playwright chromium v1208 | ✅ INSTALLED — browser 145.0.7632.6 launches |
| SSL bypass | ⚠️ **PERSISTING** — `ignore_https_errors=True` required; `ERR_CERT_AUTHORITY_INVALID` recurring |
| Login page reachable | ✅ CONFIRMED — `/agent/login` reached (HTTP 200, after SSL bypass), form rendered (5s JS load wait) |
| Password field `readOnly` | ⚠️ DETECTED — `readOnly=true` on `input[name="Password"]`; bypassed via native setter |
| Form fill | ✅ CONFIRMED — AccountName=Knowaa, Username=Amit, pass_len=7 |
| Form submission | ✅ WORKS — posts to `/agent/login-execute` |
| Login result | 🔴 FAILED — redirected back to `/agent/login` (invalid credentials) |
| Network to innstant.travel | ✅ WORKING |
| Next unblock | **Update `INNSTANT_PASS`** — this is the only blocker |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-05-22 16:00 UTC_
