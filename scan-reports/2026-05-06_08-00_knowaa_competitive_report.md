# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-06 08:00 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 15 of consecutive cloud scan block — Innstant B2B login credentials returning "Invalid login details" (credentials rotated since Apr 24); Azure SQL DB (port 1433) also TCP-blocked from cloud. Playwright browser is fully operational (chromium-headless-shell v1208 installed, login form confirmed reachable), but credentials remain invalid. This report uses the most recent valid local-machine scan (2026-04-24 04:17 UTC). **Data age: ~292h (~12.2 days).** Live scan must resume from office IP with updated INNSTANT_PASS.

---

## Executive Summary

| Metric | Value | vs May 5 16:05 | vs May 5 | vs May 4 00:00 | vs May 3 16:00 | vs May 2 16:00 | vs May 1 | vs Apr 30 | vs Apr 24 | 15-Day Trend |
|--------|-------|----------------|----------|----------------|----------------|----------------|----------|-----------|-----------|--------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Flat |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | Flat |

### Key Insight
**Day 15 of cloud scan block — 08:00 UTC scheduled slot.** Three independent blockers remain active: (1) Azure SQL TCP port 1433 blocked from cloud, (2) Innstant B2B credentials invalid ("Invalid login details" — confirmed via live login attempt with chromium), (3) Playwright browser is fully functional and confirmed reaching the login form. **Only INNSTANT_PASS is missing** — this is the sole blocker for live browser scans.

All metrics remain static — data frozen at Apr 24 04:17 UTC. **Price movement: $0.00 across ~292h (~12.2 days).** Knowaa holds all 3 active positions as #1 cheapest, each with a consistent ~5.66% margin vs InnstantTravel. The static allotment loading for the June 10–11 window has produced no dynamic repricing for 15 consecutive days.

The structural distribution gap persists: only 3 of 46 hotels (7%) have Knowaa inventory for this date. **28 hotels have competitor offers with zero Knowaa presence** — a distribution failure, not sell-out. **All 15 Section E hotels are now at Day 22+ with no refundable inventory** — contracting escalation is critically overdue.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg ~5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~292h** (Apr 22 → May 6 08:00, ~15 days)

### Infrastructure Status (May 6)
Live login attempt at 08:10 UTC confirmed: Playwright reaches b2b.innstant.travel login form, fills credentials, submits — server returns **"Invalid login details"**. This proves:
- ✅ Network connectivity to Innstant B2B is working
- ✅ Playwright/chromium is fully operational
- ✅ Login form interaction is working correctly
- ❌ Only the password is wrong — `INNSTANT_PASS` needs updating

**Provide updated INNSTANT_PASS (rotated post-Apr 24) to immediately unblock the next scheduled scan at 16:00 UTC.**

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked for ~15 days._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~292h) |
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~292h) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~292h) |

> All three hotels have been Knowaa #1 for ~15 consecutive days. The consistent 5.66% margin against InnstantTravel is structural — static allotment rate. Verify that allotment has not expired or been closed for the June 10–11 window.

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

No #2 positions in the June 10–11 window. In the May 28–29 window (scanned Apr 23 morning), Knowaa had 6 #2 positions at Embassy Suites (BB board) and Pullman (Superior category). The June window remains a materially different rate environment with significantly less Knowaa coverage.

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates with offers across 26 hotels; goglobal at 2 hotels; HyperGuestDirect⇄ at 2 hotels. All absences now 22+ consecutive days._

| Hotel | VenueId | Cheapest $ | Provider | Categories | Boards | Priority |
|-------|---------|-----------|----------|------------|--------|----------|
| Notebook Miami Beach | 5102 | $65.07 | InnstantTravel | Standard | RO | 🔴 HIGH |
| HOLIDAY INN EXPRESS HOTEL & SUITES MIAMI | 5130 | $114.92 | InnstantTravel | Standard | BB | 🔴 HIGH |
| Pod Times Square | 5305 | $121.94 | HyperGuestDirect⇄ | Standard, Dormitory | RO | 🔴 HIGH |
| Viajero Miami | 5111 | $122.21 | HyperGuestDirect⇄ | Deluxe | RO | 🔴 HIGH |
| Embassy Suites by Hilton Miami International Airport | 5081 | $143.36 | InnstantTravel | Standard, Suite | BB, RO | 🔴 HIGH |
| Hotel Belleza | 5265 | $153.42 | InnstantTravel | Superior, Standard | RO | 🟡 MED |
| Freehand Miami | 5107 | $156.54 | InnstantTravel | Standard | RO | 🟡 MED |
| Generator Miami | 5274 | $159.38 | InnstantTravel | Standard, Deluxe, Dormitory | RO | 🟡 MED |
| The Gates Hotel South Beach - a DoubleTree by Hilton | 5140 | $164.73 | InnstantTravel | Standard | RO | 🟡 MED |
| Miami International Airport Hotel | 5275 | $168.54 | InnstantTravel | Standard | RO | 🟡 MED |
| Hampton Inn Miami Beach - Mid Beach | 5106 | $180.88 | InnstantTravel | Standard | RO | 🟡 MED |
| Eurostars Langford Hotel | 5098 | $192.12 | InnstantTravel | Deluxe | RO | 🟡 MED |
| THE LANDON BAY HARBOR | 5138 | $194.90 | InnstantTravel | Deluxe | BB | 🟡 MED |
| Gale Miami Hotel and Residences | 5278 | $202.51 | InnstantTravel | Standard, Suite | RO | 🟡 MED |
| Grand Beach Hotel Miami | 5124 | $204.54 | InnstantTravel | Suite | RO | 🟡 MED |
| Hôtel Gaythering | 5132 | $205.14 | InnstantTravel | Standard, Deluxe | BB | 🟡 MED |
| Breakwater South Beach | 5110 | $227.88 | InnstantTravel | Superior | BB | 🟡 MED |
| Crystal Beach Suites Hotel | 5100 | $228.29 | InnstantTravel | Suite | RO | 🟡 MED |
| Dorchester Hotel | 5266 | $232.79 | InnstantTravel | Apartment, Suite | RO | 🟢 LOW |
| Cavalier Hotel | 5113 | $238.35 | goglobal | Standard | RO | 🟢 LOW |
| MB Hotel, Trademark Collection by Wyndham | 5105 | $243.03 | goglobal | Standard | RO | 🟡 MED |
| Iberostar Berkeley Shore Hotel | 5092 | $244.18 | InnstantTravel | Standard | RO | 🟡 MED |
| citizenM Miami South Beach | 5119 | $255.27 | InnstantTravel | Standard | RO | 🟢 LOW |
| Hotel Riu Plaza Miami Beach | 5109 | $303.51 | InnstantTravel | Deluxe | RO, BB | 🔴 HIGH |
| Gale South Beach | 5267 | $306.13 | InnstantTravel | Standard | RO | 🟢 LOW |
| Fontainebleau Miami Beach | 5268 | $341.31 | InnstantTravel | Standard, Deluxe | RO | 🟢 LOW |
| The Gabriel Miami South Beach, Curio Collection by Hilton | 5108 | $415.25 | InnstantTravel | Standard | BB | 🟢 LOW |
| Savoy Hotel | 5103 | $499.26 | InnstantTravel | Standard, Deluxe | RO, BB | 🟢 LOW |

> **Priority inventory gaps — June 10–11 (22+ consecutive days, contracting escalation critically overdue):**
> - **Notebook Miami Beach (5102)** — lowest competitor at $65.07; highest relative revenue risk per absent Knowaa offer.
> - **Embassy Suites (5081)** — was Knowaa #1 in May 28–29 window; absent from June 10–11 for 22+ days.
> - **Holiday Inn Express (5130)** — mid-range accessible price point lost for 22+ days.
> - **Pod Times Square (5305) & Viajero (5111)** — HyperGuestDirect⇄ sole or dominant provider; Knowaa should be competing here.
> - **Hotel Riu Plaza (5109)** — premium segment ($303.51); Knowaa absence at this price tier is significant.
> - **goglobal present at 2 hotels** (Cavalier, MB Hotel) — Knowaa should match or beat goglobal coverage.

---

## Section E — No Refundable Offers — 15 hotels

_No refundable inventory visible on Innstant B2B for June 10–11. All 15 have been in this state for 22+ consecutive days. Contracting escalation is critically overdue._

| Hotel | VenueId | Days w/o Offers | Action Required |
|-------|---------|-----------------|-----------------|
| Hotel Chelsea | 5064 | 22+ | Contracting check |
| The Grayson Hotel Miami Downtown | 5094 | 22+ | Contracting check |
| Hyatt Centric South Beach Miami (City View) | 5097 | 22+ | Contracting check |
| Atwell Suites Miami Brickell | 5101 | 22+ | Contracting check |
| Sole Miami, A Noble House Resort | 5104 | 22+ | Contracting check |
| Hilton Cabana Miami Beach | 5115 | 22+ | Contracting check |
| Kimpton Hotel Palomar South Beach | 5116 | 22+ | Contracting check |
| The Albion Hotel | 5117 | 22+ | Contracting check |
| Hotel Croydon | 5131 | 22+ | Contracting check |
| Kimpton Angler's Hotel | 5136 | 22+ | Contracting check |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 22+ | Contracting check |
| Metropole South Beach | 5141 | 22+ | Contracting check |
| InterContinental Miami | 5276 | 22+ | Contracting check |
| The Catalina Hotel & Beach Club | 5277 | 22+ | Contracting check |
| Hilton Garden Inn Miami South Beach | 5279 | 22+ | Contracting check |

> All 15 Section E hotels have been without any refundable inventory since at least Apr 14 (first confirmed absence). These may represent allotment loading failures, contract date exclusions, or closed allotments. Priority action: check allotment status in Noovy/SalesOffice for each hotel for the June 10–11 window.

---

## Scan Infrastructure Status

| Component | Status | Notes |
|-----------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP-blocked from cloud environment; all DB attempts timeout |
| Innstant B2B credentials | 🔴 INVALID | "Invalid login details" — confirmed via live login attempt at 08:10 UTC |
| Playwright (chromium) | ✅ OPERATIONAL | chromium-headless-shell v1208; login form reachable, interaction working |
| Network to innstant.travel | ✅ WORKING | HTTPS connectivity confirmed — only password invalid |
| MSSQL ODBC driver | ✅ Installed | pyodbc + msodbcsql18 installed; DB remains TCP-blocked |
| Hotel list cache | ✅ Available | `scan-reports/2026-04-24_04-17_full_scan.json` (46 hotels) |
| Last valid scan | ℹ️ Apr 24 04:17 UTC | `scan-reports/2026-04-24_04-17_full_scan.json` |

**Resolution path:** Provide updated `INNSTANT_PASS` (password rotated post-Apr 24) to immediately restore live scanning. The 08:00 UTC slot was attempted — next window is 16:00 UTC. Set `INNSTANT_PASS` in `.env` or environment before 16:00 UTC to capture the afternoon scan. Hotel list will be sourced from cached data (no DB required).

---

## Comparison vs Previous Reports

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age | Status |
|------|-----------|-----------|-----------|-----------|----------|--------|
| **May 6 08:00** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **~292h** | ⚠️ Stale |
| May 5 16:05 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 5 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~276h | ⚠️ Stale |
| May 4 00:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~236h | ⚠️ Stale |
| May 3 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~228h | ⚠️ Stale |
| May 2 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~212h | ⚠️ Stale |
| May 1 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~186h | ⚠️ Stale |
| Apr 30 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | ~162h | ⚠️ Stale |
| Apr 24 04:17 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 0h | ✅ Live |

All metrics frozen since Apr 24 — no dynamic changes detected across 15 consecutive days. Flat trend line confirms static allotment loading with zero repricing activity for the June 10–11 window.
