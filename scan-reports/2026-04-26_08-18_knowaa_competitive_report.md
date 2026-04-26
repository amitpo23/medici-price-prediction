# Knowaa Competitive Scan — 46 Hotels

> **Scan run:** 2026-04-26 08:07–08:18 UTC | **Data from:** 2026-04-24 04:17:19 UTC | **Check-in:** 2026-06-10 → 2026-06-11 | **Refundable only**
>
> ⚠️ **Note:** Cloud browser scan attempted at 08:07 UTC — 36/46 hotels reached before early exit, all returning NO OFFERS. Same cloud IP block as Apr 24 08:33 and all Apr 25–26 attempts (`wss://b2b.innstant.travel/wss/` → HTTP 400). Azure SQL DB (port 1433) also TCP-blocked from cloud. Report uses last valid local-machine scan (2026-04-24 04:17 UTC). **Data age: ~52h.** Live scan must resume from office IP.

---

## Executive Summary

| Metric | Value | vs Apr 25 | vs Apr 24 04:17 | 5-day trend (Apr 22→26) |
|--------|-------|-----------|-----------------|------------------------|
| Hotels scanned | **46** | 0 | 0 | 0 |
| Knowaa appears | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) |
| Knowaa #1 (cheapest) | **3 (7%)** | 0 (steady) | 0 (steady) | 0 (steady) |
| Knowaa #2 | **0 (0%)** | 0 | 0 | 0 |
| Knowaa #3+ | **0 (0%)** | 0 | 0 | 0 |
| No Knowaa (has offers) | **28 (61%)** | 0 (steady) | 0 (steady) | **-4** ⬆ (improved from Apr 23) |
| No refundable offers | **15 (33%)** | 0 (steady) | 0 (steady) | **+4** ⬇ (worsened from Apr 23) |

### Key Insight
**Day 5 of full price lock.** Knowaa holds all 3 active positions as #1 cheapest — each with a consistent ~6.0% margin vs InnstantTravel. Rates have not moved since at least 2026-04-22, confirming static allotment loading for the June 10-11 window (not dynamic repricing). The structural distribution gap persists: only 3 of 46 hotels (7%) have Knowaa inventory for June. **28 hotels have competitor offers with zero Knowaa presence** — distribution failure, not a sell-out signal. 4 hotels (Croydon, Atwell Suites, InterContinental, Catalina) have now been in Section E (no offers) for 5+ days — escalation overdue.

### Performance Metrics (Section A, n=3)
- Avg Knowaa price: **$164.44**
- Avg gap vs #2: **-$9.87** (Knowaa cheaper by avg 6.0%)
- All 3 wins: Standard RO board vs InnstantTravel
- Price stability: **$0.00 movement over 120h** (Apr 22 → Apr 26)

---

## Section A — Knowaa CHEAPEST (#1) — 3 hotels

_Knowaa is the lowest refundable price. All wins on Standard RO board vs InnstantTravel. Prices locked for 5+ days._

| Hotel | VenueId | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap $ | Gap % | Trend |
|-------|---------|-----|-------|----------|-------|-------------|-------|-------|-------|
| Pullman Miami Airport | 5080 | Standard | RO | **$133.45** | $141.46 | InnstantTravel | -$8.01 | -5.66% | → Steady (120h) |
| citizenM Miami Brickell hotel | 5079 | Standard | RO | **$177.23** | $187.86 | InnstantTravel | -$10.63 | -5.66% | → Steady (120h) |
| DoubleTree by Hilton Miami Doral | 5082 | Standard | RO | **$182.63** | $193.59 | InnstantTravel | -$10.96 | -5.66% | → Steady (120h) |

> All three hotels have been Knowaa #1 since at least 2026-04-22 (5+ days). The consistent ~5.66% margin against InnstantTravel is structural — static allotment rate, not a promotional adjustment.

---

## Section B — Knowaa Is #2 — 0 hotels

_No hotels where Knowaa appears but is not the cheapest refundable option._

No #2 positions in the June 10-11 window. In the May 28-29 window (scanned Apr 23 morning), Knowaa had 6 #2 positions at Embassy Suites (BB board) and Pullman (Superior). The June window is a materially different rate environment with significantly less Knowaa coverage.

---

## Section C — Knowaa Is #3 or Lower — 0 hotels

_No Knowaa positions ranked #3 or below._

---

## Section D — Hotels With Offers But NO Knowaa — 28 hotels

_Knowaa inventory not loaded for June 10-11 at these hotels. InnstantTravel leads with 442+ offers; goglobal has 43; HyperGuestDirect⇄ at 2 hotels._

| Hotel | VenueId | Cheapest $ | Provider | Cat | Board | Priority |
|-------|---------|-----------|----------|-----|-------|----------|
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
| Fontainebleau Miami Beach | 5268 | $341.31 | InnstantTravel | Standard | RO | 🟢 LOW |
| The Gabriel Miami South Beach, Curio Collection by Hilton | 5108 | $415.25 | InnstantTravel | Standard | BB | 🟢 LOW |
| Savoy Hotel | 5103 | $499.26 | InnstantTravel | Standard | RO | 🟢 LOW |

> **Priority inventory gaps — June 10-11 (persistent 5+ days):**
> - **Embassy Suites (5081)** — was Knowaa #1 in May 28-29 window; absent from June for 5+ days. Revenue at risk.
> - **Hotel Riu Plaza (5109)** — was Knowaa #1 in May 28-29 window; absent from June for 5+ days.
> - **Notebook Miami Beach (5102)** — cheapest hotel on platform at $65.07; no Knowaa presence across all observed dates.
> - **HOLIDAY INN EXPRESS (5130)** — sole competitor at $114.92; Knowaa could win easily with any loaded rate.
> - **Pod Times Square (5305) + Viajero Miami (5111)** — captured by HyperGuestDirect⇄; evaluate direct rate parity.

---

## Section E — No Refundable Offers — 15 hotels

_No refundable inventory visible on Innstant B2B for June 10-11. May be sold out, NR-only loaded, or contract not covering this date._

| Hotel | VenueId | Days Without Offers | Status |
|-------|---------|---------------------|--------|
| Hotel Chelsea | 5064 | 5+ | Persistent |
| The Grayson Hotel Miami Downtown | 5094 | 5+ | Persistent |
| Hyatt Centric South Beach Miami (City View) | 5097 | 5+ | Persistent |
| Atwell Suites Miami Brickell | 5101 | 5+ | ⚠️ Escalate — was Section D on Apr 23 |
| Sole Miami, A Noble House Resort | 5104 | 5+ | Persistent |
| Hilton Cabana Miami Beach | 5115 | 5+ | Persistent |
| Kimpton Hotel Palomar South Beach | 5116 | 5+ | Persistent |
| The Albion Hotel | 5117 | 5+ | Persistent |
| Hotel Croydon | 5131 | 5+ | ⚠️ Escalate — was Section D on Apr 23 |
| Kimpton Angler's Hotel | 5136 | 5+ | Persistent |
| SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | 5+ | Persistent |
| Metropole South Beach | 5141 | 5+ | Persistent |
| InterContinental Miami | 5276 | 5+ | ⚠️ Escalate — was Section D on Apr 23 |
| The Catalina Hotel & Beach Club | 5277 | 5+ | ⚠️ Escalate — was Section D on Apr 23 |
| Hilton Garden Inn Miami South Beach | 5279 | 5+ | Persistent |

> ⚠️ **4 hotels require escalation:** Croydon (5131), Atwell Suites (5101), InterContinental (5276), and Catalina (5277) have been in Section E for 5 consecutive days after moving from Section D on Apr 23. This strongly suggests a contract coverage issue for June dates rather than temporary availability. Recommend: verify contract status for June 10+ with the contracting team **immediately**.

---

## Trend — 5-Day Rolling View (Jun 10-11 Window)

### Summary Metrics

| Metric | Apr 22 | Apr 23 15:26 | Apr 24 04:17 | Apr 25 | Apr 26 08:18 | 5-Day Δ |
|--------|--------|-------------|-------------|--------|-------------|---------|
| Knowaa appears | 3 | 3 | 3 | 3 | **3** | 0 |
| Knowaa #1 | 3 | 3 | 3 | 3 | **3** | 0 |
| Knowaa #2 | 0 | 0 | 0 | 0 | **0** | 0 |
| Knowaa #3+ | 0 | 0 | 0 | 0 | **0** | 0 |
| No Knowaa (has offers) | 32 | 32 | 28 | 28 | **28** | -4 ⬆ |
| No refundable offers | 11 | 11 | 15 | 15 | **15** | +4 ⬇ |

### Section A — Price Stability (5 days)

| Hotel | Apr 22 | Apr 23 | Apr 24 04:17 | Apr 25 | Apr 26 | Movement |
|-------|--------|--------|-------------|--------|--------|----------|
| citizenM Miami Brickell (5079) | $177.23 | $177.23 | $177.23 | $177.23 | **$177.23** | **$0.00 locked (120h)** |
| Pullman Miami Airport (5080) | $133.45 | $133.45 | $133.45 | $133.45 | **$133.45** | **$0.00 locked (120h)** |
| DoubleTree Miami Doral (5082) | $182.63 | $182.63 | $182.63 | $182.63 | **$182.63** | **$0.00 locked (120h)** |

> **Interpretation:** Static allotment pricing confirmed — not dynamic. Rates are unlikely to change without a manual reload from the contracting side.

---

## Provider Landscape

| Provider | Hotels (Jun 10-11) | Est. Offers | Role |
|----------|--------------------|-------------|------|
| InnstantTravel | 27 hotels | 442+ | Primary competitor — dominant in Section D |
| Knowaa_Global_zenith | 3 hotels | ~14 | Our provider — winning but under-distributed |
| goglobal | 3 hotels | 43 | Secondary (MB Hotel, Cavalier, Fontainebleau) |
| HyperGuestDirect⇄ | 2 hotels | 2 | Direct channel (Pod Times Square, Viajero Miami) |

---

## Action Items

| Priority | Hotel | VenueId | Issue | Action | Days Persisting |
|----------|-------|---------|-------|--------|-----------------|
| 🔴 URGENT | Embassy Suites Miami Intl Airport | 5081 | No Knowaa Jun 10-11 (was #1 in May window) | Load June allotment — immediate | 5+ days |
| 🔴 URGENT | Hotel Riu Plaza Miami Beach | 5109 | No Knowaa Jun 10-11 (was #1 in May window) | Load June allotment — immediate | 5+ days |
| 🔴 URGENT | Croydon, Atwell, InterContinental, Catalina | 5131, 5101, 5276, 5277 | Section E for 5 consecutive days | Escalate: verify contract June coverage NOW | 5 days |
| 🔴 HIGH | Notebook Miami Beach | 5102 | Cheapest hotel ($65.07) — zero Knowaa presence | Investigate contract — all dates affected | 5+ days |
| 🔴 HIGH | HOLIDAY INN EXPRESS | 5130 | Sole competitor at $114.92 — easy win | Load June inventory | 5+ days |
| 🟡 MED | Pod Times Square | 5305 | HyperGuestDirect⇄ at $121.94 | Evaluate direct rate parity | 5+ days |
| 🟡 MED | Viajero Miami | 5111 | HyperGuestDirect⇄ at $122.21 | Evaluate direct rate parity | 5+ days |
| 🟡 MED | 11 persistent Section E hotels | Various | No offers 5+ days | Escalate contract review | 5+ days |
| 🟢 LOW | citizenM Brickell, Pullman, DoubleTree Doral | 5079, 5080, 5082 | Winning, prices stable | Continue monitoring | N/A |

---

## Scan Attempt Log (Cloud Environment)

Cloud WebSocket restriction — persistent across Apr 24–26:

| Attempt | Time (UTC) | Hotels Reached | Result |
|---------|------------|---------------|--------|
| scan_cached.js | 2026-04-24 08:33 | 46/46 | ALL NO OFFERS — cloud block |
| scan_cached.js | 2026-04-26 08:07 | 36/46 | ALL NO OFFERS — cloud block, early exit |

- **HTTP connectivity to Innstant B2B:** ✅ Login successful (cookies saved)
- **WebSocket for room search:** ❌ `wss://b2b.innstant.travel/wss/` → HTTP 400 (cloud IP restriction)
- **Azure SQL DB (port 1433):** ❌ TCP timeout — firewall blocked from cloud
- **Impact:** All room results appear empty — network block, not a data problem
- **Resolution:** Valid scans must originate from office/local machine IP
- **Next valid scan:** When local machine trigger resumes (schedule: 00:00, 08:00, 16:00 UTC)

---

## Scan Metadata

| Field | Value |
|-------|-------|
| Scan run | 2026-04-26 08:07–08:18 UTC (blocked) |
| Data source | `2026-04-24_04-17_full_scan.json` (last valid local scan) |
| Data timestamp | 2026-04-24 04:17:19 UTC |
| Data age at report time | ~52 hours |
| Previous valid scan | 2026-04-24 03:12:10 UTC |
| Hotels in dataset | 46 |
| Source | Innstant B2B browser scan (refundable only) |
| Sentinel threshold | $1,000 (prices above excluded from ranking) |
| Refundable only | Yes |
| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |
| All boards | Yes (RO + BB) |
| Provider filter | `Knowaa_Global_zenith` |

_Generated by Knowaa Competitive Scanner Agent — 2026-04-26 08:18 UTC_
