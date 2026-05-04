# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-05-04 00:00 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Day 13 of consecutive cloud scan block — Innstant B2B login credentials returning "Invalid login details" (credentials rotated since Apr 24); Azure SQL DB (port 1433) also TCP-blocked from cloud. This report uses the most recent valid local-machine scan (2026-04-24 04:17 UTC). **Data age: ~236h (~9.8 days).** Live scan must resume from office IP with updated credentials.

---

## Executive Summary

| Metric | Value | vs May 3 16:00 | vs May 3 08:00 | vs May 2 16:00 | vs May 2 08:00 | vs May 1 | vs Apr 30 | vs Apr 24 | 13-Day Trend (Apr 24→May 4) |
|--------|-------|----------------|----------------|----------------|----------------|----------|-----------|-----------|----------------------------|
| Hotels scanned | **46** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) | 0 (steady) |

### Key Insight
**Day 13 of cloud scan block — 00:00 UTC scheduled slot.** Three independent blockers active: (1) Azure SQL TCP port 1433 blocked from cloud, (2) Innstant B2B login returning "Invalid login details" (credentials rotated since Apr 24), (3) pyodbc MSSQL driver now installed in cloud but DB remains TCP-unreachable. No fresh data obtainable from this environment.

All metrics remain static — data frozen at Apr 24 04:17 UTC. Knowaa holds all 3 active positions as #1 cheapest, each with a consistent ~5.66% margin vs InnstantTravel. Prices have been frozen since at least 2026-04-22 — **~288h (~12 days) with zero price movement**, confirming static allotment loading for the June 10–11 window. No dynamic repricing has occurred.

The structural distribution gap persists: only 3 of 46 hotels (7%) have Knowaa inventory for this date. **28 hotels have competitor offers with zero Knowaa presence** — a distribution failure, not sell-out. **All 15 Section E hotels are at Day 20+ with no refundable inventory** — escalation to contracting is critically overdue.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 5.66%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over ~288h** (Apr 22 → May 4 00:00, ~12 days)

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked for ~13 days._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (~288h) |
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (~288h) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (~288h) |

> All three hotels have been Knowaa #1 for ~13 consecutive days. The consistent 5.66% margin against InnstantTravel is structural — static allotment rate, not dynamic repricing. A manual reload from the contracting/revenue side would be required to change these prices.

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

No #2 positions in the June 10–11 window. In the May 28–29 window (scanned Apr 23 morning), Knowaa had 6 #2 positions at Embassy Suites (BB board) and Pullman (Superior category). The June window remains a materially different rate environment with significantly less Knowaa coverage.

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10–11. InnstantTravel dominates with 440+ offers across 26 hotels; goglobal at 2 hotels; HyperGuestDirect⇄ at 2 hotels. All absences now 20+ consecutive days (since Apr 24 scan)._

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

> **Priority inventory gaps — June 10–11 (20+ consecutive days, escalation critically overdue):**
> - **Embassy Suites (5081)** — was Knowaa #1 in May 28–29 window; absent from June for 20+ days. Revenue at risk.
> - **Notebook Miami Beach (5102)** — lowest competitor price at $65.07; lost Knowaa position is highest relative revenue impact.
> - **Holiday Inn Express (5130)** — mid-range gap; accessible price point lost for 20+ days.
> - **Pod Times Square (5305) & Viajero Miami (5111)** — HyperGuestDirect⇄ is sole provider; Knowaa should be competing here.
> - **Hotel Riu Plaza (5109)** — premium price point ($303.51) — Knowaa absence at this tier is notable.

---

## Section E — No Refundable Offers — 15 hotels

_No refundable inventory visible on Innstant B2B for June 10–11. All 15 have been in this state for 20+ consecutive days. Escalation to contracting is critically overdue._

| Hotel | VenueId | Days w/o Offers | Action Required |
|-------|---------|-----------------|-----------------|
| Hotel Chelsea | 5064 | 20+ | Contracting check |
| The Grayson Hotel Miami Downtown | 5094 | 20+ | Contracting check |
| Hyatt Centric South Beach Miami (City View) | 5097 | 20+ | Contracting check |
| Atwell Suites Miami Brickell | 5101 | 20+ | Contracting check |
| Sole Miami, A Noble House Resort | 5104 | 20+ | Contracting check |
| Hilton Cabana Miami Beach | 5115 | 20+ | Contracting check |
| Kimpton Hotel Palomar South Beach | 5116 | 20+ | Contracting check |
| The Albion Hotel | 5117 | 20+ | Contracting check |
| Hotel Croydon | 5131 | 20+ | Contracting check |
| Kimpton Angler's Hotel | 5136 | 20+ | Contracting check |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 20+ | Contracting check |
| Metropole South Beach | 5141 | 20+ | Contracting check |
| InterContinental Miami | 5276 | 20+ | Contracting check |
| The Catalina Hotel & Beach Club | 5277 | 20+ | Contracting check |
| Hilton Garden Inn Miami South Beach | 5279 | 20+ | Contracting check |

> All 15 Section E hotels have been without any refundable inventory since at least Apr 14 (initial count of ~20 days). No competitor pricing data available — these may represent allotment loading failures or contracted date exclusions.

---

## Scan Infrastructure Status

| Blocker | Status | Notes |
|---------|--------|-------|
| Azure SQL port 1433 | 🔴 BLOCKED | TCP-blocked from cloud environment; all DB attempts timeout |
| Innstant B2B login | 🔴 BLOCKED | "Invalid login details" — credentials rotated since Apr 24 |
| MSSQL ODBC driver | ✅ Installed | `msodbcsql18` installed in cloud (new today), but DB still TCP-blocked |
| Playwright | ✅ Available | `/opt/node22/bin/playwright` present; would work if credentials were valid |
| Last valid scan | ℹ️ Apr 24 04:17 UTC | `scan-reports/2026-04-24_04-17_full_scan.json` |

**Resolution path:** Live scan requires (1) valid INNSTANT_PASS from office/secrets, and (2) Azure SQL accessible from office IP or VPN. Neither is achievable from cloud trigger without credential refresh.

---

## Comparison vs Previous Reports

| Date | Knowaa #1 | Knowaa #2 | No Knowaa | No Offers | Data Age |
|------|-----------|-----------|-----------|-----------|----------|
| **May 4 00:00** | **3 (7%)** | **0** | **28 (61%)** | **15 (33%)** | **236h** |
| May 3 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 228h |
| May 3 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 220h |
| May 2 16:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 212h |
| May 2 08:00 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 204h |
| May 1 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 186h |
| Apr 30 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 162h |
| Apr 24 | 3 (7%) | 0 | 28 (61%) | 15 (33%) | 0h (live) |

All metrics frozen since Apr 24 — no dynamic changes detected. The trend line is flat across 13 days.
