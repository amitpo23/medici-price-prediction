# Knowaa Competitive Scan — 55 Hotels

**Scan:** 2026-04-02 08:03 UTC | **Source:** Innstant B2B (data from 00:37 scan — live scan unavailable in this environment)
**Search dates:** 2026-04-20 → 2026-04-21 (1 night, 2 adults) | **Filter:** Refundable only
**Provider:** `Knowaa_Global_zenith` | **Account:** Knowaa/Amit

> ⚠️ **Note:** Live browser scan could not be executed in this trigger environment (network proxy blocks Innstant B2B access; Azure SQL unreachable). This report uses the most recent scan data (00:37 UTC, 7.5 hours ago). No pricing changes expected — same search window (Apr 20–21). For a fresh live scan, run via GitHub Actions or local `node scripts/browser_scan.js`.

---

## Summary

| Metric | 2026-04-02 00:37 | 2026-04-01 13:41 | 2026-04-01 08:16 | Δ vs yesterday |
|--------|-----------------|-----------------|-----------------|----------------|
| Hotels scanned | 55 | 55 | 55 | = |
| Hotels w/ refundable offers | **42** | 45 | 45 | **(-3)** |
| Knowaa appears | **15 (27%)** | 16 (29%) | 15 (27%) | **(-1)** |
| Knowaa #1 (cheapest) | **8 (15%)** | 9 (16%) | 8 (15%) | **(-1)** |
| Knowaa #2 | **4 (7%)** | 3 (5%) | 4 (7%) | (+1) |
| Knowaa #3+ | **3 (5%)** | 4 (7%) | 3 (5%) | (-1) |
| Has offers, NO Knowaa | **27 (49%)** | 29 (53%) | 30 (55%) | **(-2 vs yesterday)** |
| No refundable offers | **13 (24%)** | 10 (18%) | 10 (18%) | **(+3)** |

**Overall trajectory vs yesterday: MIXED** — Lost 1 #1 position (Eurostars Langford dropped out); +3 hotels moved to no-offer (E); Knowaa absent from 27 hotels.

---

## Section A — Knowaa is #1 (Cheapest) — 8 hotels

| Hotel | Venue | Room Types | Boards | Knowaa $ | 2nd Best $ | 2nd Provider | Lead |
|-------|-------|-----------|--------|----------|-----------|-------------|------|
| Cavalier Hotel | 5113 | Standard, Deluxe | RO | **$100.04** | $106.04 | InnstantTravel | **-$6.00** |
| Embassy Suites by Hilton Miami International Airport | 5081 | Standard, Suite | RO, BB | **$135.42** | $136.22 | InnstantTravel | -$0.80 |
| Hilton Miami Airport | 5083 | Standard | RO | **$214.75** | $214.75 | InnstantTravel | -$0.00 |
| Hotel Riu Plaza Miami Beach | 5109 | Deluxe | RO, BB | **$287.41** | $287.41 | goglobal | -$0.00 |
| Hyatt Centric South Beach Miami (City View) | 5097 | Standard | RO | **$260.32** | $275.94 | InnstantTravel | **-$15.62** |
| Iberostar Berkeley Shore Hotel | 5092 | Standard | RO | **$224.34** | $225.49 | InnstantTravel | -$1.15 |
| Kimpton Hotel Palomar South Beach | 5116 | Standard | RO | **$180.56** | $183.13 | InnstantTravel | -$2.57 |
| Marseilles Hotel | 5096 | Standard | RO | **$195.02** | $195.56 | InnstantTravel | -$0.54 |

**Average lead where #1: -$3.34** | **Hyatt Centric** newly entered #1 position (+$15.62 lead vs competition).

---

## Section B — Knowaa is #2 — 4 hotels

| Hotel | Venue | Room Types | Boards | Knowaa $ | Cheapest $ | Cheaper Provider | Gap | Action |
|-------|-------|-----------|--------|----------|-----------|-----------------|-----|--------|
| Cadet Hotel | 5095 | Standard, Superior, Suite | RO | $223.45 | $223.44 | InnstantTravel | **+$0.01** | Drop $0.02 → #1 |
| Crystal Beach Suites Hotel | 5100 | Suite | RO | $167.16 | $167.15 | InnstantTravel | **+$0.01** | Drop $0.02 → #1 |
| Freehand Miami | 5107 | Superior, Standard | RO | $104.79 | $104.54 | InnstantTravel | +$0.25 | Drop $0.26 → #1 |
| The Villa Casa Casuarina | 5075 | Standard | RO | $1,923.92 | $1,923.91 | InnstantTravel | **+$0.01** | Drop $0.02 → #1 |

> **Note:** The Villa Casa Casuarina dropped from #1 (13:41 scan at $1,556.65) to #2 (price increased to $1,923.92 while InnstantTravel came in at $1,923.91). Cadet and Crystal remain $0.01 behind since Apr 1 morning — pricing drift not corrected.

---

## Section C — Knowaa is #3 or Lower — 3 hotels

| Hotel | Venue | Rank | Room Types | Boards | Knowaa $ | Cheapest $ | Cheapest Provider | Gap | Action |
|-------|-------|------|-----------|--------|----------|-----------|------------------|-----|--------|
| citizenM Miami South Beach | 5119 | #3 | Standard | RO | $175.71 | $175.70 | InnstantTravel | +$0.01 | Drop $0.02 → #1 |
| Loews Miami Beach Hotel | 5073 | #3 | Standard | RO | $342.38 | $342.37 | InnstantTravel | +$0.01 | Drop $0.02 → #1 |
| Kimpton Angler's Hotel | 5136 | #25 | Deluxe, Standard | RO | $394.67 | $373.37 | InnstantTravel | **+$21.30** | ⚠️ Review Noovy rate |

> **Kimpton Angler's** remains severely overpriced at rank #25 (+$21.30 vs market). This has persisted across multiple scans — Noovy rate review is urgent.
> **citizenM SB** and **Loews** remain $0.01 behind — quick wins with a $0.02 price reduction.

---

## Section D — Has Offers but NO Knowaa — 27 hotels

| # | Hotel | Venue | Cheapest $ | Lead Provider | Boards | Categories |
|---|-------|-------|-----------|-------------|--------|------------|
| 1 | Notebook Miami Beach | 5102 | $82.07 | InnstantTravel | RO | Standard |
| 2 | The Albion Hotel | 5117 | $103.49 | InnstantTravel | RO | Dormitory, Standard, Deluxe, Apartment |
| 3 | HOLIDAY INN EXPRESS HOTEL & SUITES MIAMI | 5130 | $125.19 | InnstantTravel | BB | Standard |
| 4 | Generator Miami | 5274 | $136.38 | InnstantTravel | RO | Deluxe, Standard |
| 5 | Dorchester Hotel | 5266 | $145.36 | InnstantTravel | RO | Standard, Apartment |
| 6 | The Gates Hotel South Beach - a DoubleTree by Hilton | 5140 | $151.52 | InnstantTravel | RO | Standard |
| 7 | Pullman Miami Airport | 5080 | $157.07 | InnstantTravel | RO | Superior |
| 8 | Gale Miami Hotel and Residences | 5278 | $160.47 | InnstantTravel | RO | Standard |
| 9 | Hilton Cabana Miami Beach | 5115 | $163.66 | InnstantTravel | RO | Standard, Deluxe |
| 10 | Breakwater South Beach | 5110 | $164.97 | InnstantTravel | BB | Superior |
| 11 | Hilton Garden Inn Miami South Beach | 5279 | $172.84 | InnstantTravel | RO | Standard |
| 12 | Hotel Belleza | 5265 | $174.11 | InnstantTravel | RO | Standard |
| 13 | Dream South Beach | 5090 | $181.66 | InnstantTravel | RO | Standard |
| 14 | Hôtel Gaythering | 5132 | $183.88 | InnstantTravel | BB | Standard, Deluxe |
| 15 | THE LANDON BAY HARBOR | 5138 | $185.85 | InnstantTravel | BB, RO | Deluxe, Standard |
| 16 | Miami International Airport Hotel | 5275 | $189.42 | InnstantTravel | RO | Standard |
| 17 | Grand Beach Hotel Miami | 5124 | $203.96 | InnstantTravel | RO | Suite |
| 18 | DoubleTree by Hilton Miami Doral | 5082 | $211.21 | InnstantTravel | RO | Standard |
| 19 | Atwell Suites Miami Brickell | 5101 | $229.02 | InnstantTravel | BB | Suite |
| 20 | citizenM Miami Brickell hotel | 5079 | $230.70 | InnstantTravel | RO | Standard |
| 21 | Hampton Inn Miami Beach - Mid Beach | 5106 | $236.28 | InnstantTravel | RO | Deluxe, Standard |
| 22 | Gale South Beach | 5267 | $240.99 | InnstantTravel | RO | Standard |
| 23 | InterContinental Miami | 5276 | $283.43 | InnstantTravel | RO | Standard |
| 24 | The Gabriel Miami South Beach, Curio Collection by Hilton | 5108 | $308.83 | InnstantTravel | BB | Standard |
| 25 | Savoy Hotel | 5103 | $382.00 | InnstantTravel | RO | Deluxe, Standard |
| 26 | Hilton Bentley Miami South Beach | 5093 | $433.59 | InnstantTravel | RO | Standard |
| 27 | Fontainebleau Miami Beach | 5268 | $546.35 | InnstantTravel | RO | Deluxe, Standard |

> **DoubleTree by Hilton Miami Doral** (5082) dropped from Section C (#19 by $0.01) to Section D (Knowaa no longer appearing). This is a regression — Knowaa was visible in the 13:41 scan.
> InnstantTravel dominates all 27 hotels. Knowaa is absent — Noovy availability/sync not active for these properties.

---

## Section E — No Refundable Offers — 13 hotels

| # | Hotel | Venue | Notes |
|---|-------|-------|-------|
| 1 | Eurostars Langford Hotel | 5098 | **NEW** — was Knowaa #1 ($142.71) in Apr 1 13:41 scan |
| 2 | FAIRWIND HOTEL & SUITES SOUTH BEACH | 5089 | **NEW** — was in Section D in Apr 1 13:41 scan |
| 3 | Hilton Miami Downtown | 5084 | No refundable offers from any provider (persistent) |
| 4 | Hotel Chelsea | 5064 | No refundable offers from any provider (persistent) |
| 5 | Hotel Croydon | 5131 | No refundable offers from any provider (persistent) |
| 6 | MB Hotel, Trademark Collection by Wyndham | 5105 | No refundable offers from any provider (persistent) |
| 7 | Metropole South Beach | 5141 | No refundable offers from any provider (persistent) |
| 8 | SERENA Hotel Aventura Miami, Tapestry Collection by Hilton | 5139 | No refundable offers from any provider (persistent) |
| 9 | SLS LUX Brickell | 5077 | No refundable offers from any provider (persistent) |
| 10 | Sole Miami, A Noble House Resort | 5104 | No refundable offers from any provider (persistent) |
| 11 | The Catalina Hotel & Beach Club | 5277 | No refundable offers from any provider (persistent) |
| 12 | The Grayson Hotel Miami Downtown | 5094 | No refundable offers from any provider (persistent) |
| 13 | Viajero Miami | 5111 | **NEW** — was in Section D (HyperGuestDirect $117.65) in Apr 1 13:41 scan |

> **3 new hotels in Section E vs Apr 1 13:41:** Eurostars Langford (was Knowaa #1), FAIRWIND (was D), Viajero Miami (was D). Refundable inventory may have been exhausted for the Apr 20–21 date.

---

## Trend Analysis — Apr 1 13:41 → Apr 2 00:37

### Position Changes

| Hotel | Apr 1 13:41 | Apr 2 00:37 | Change |
|-------|------------|------------|--------|
| **Eurostars Langford Hotel** | #1 ($142.71) | **Section E** | ⬇️ Lost — no refundable offers |
| **The Villa Casa Casuarina** | #1 ($1,556.65) | **#2 ($1,923.92)** | ⬇️ Price rose $367; InnstantTravel undercut by $0.01 |
| **Hyatt Centric South Beach Miami** | Section D ($263.06) | **#1 ($260.32)** | ⬆️ Gained #1 — entered market cheaper |
| **DoubleTree by Hilton Miami Doral** | #19 ($211.22, +$0.01) | **Section D** | ⬇️ Lost — Knowaa no longer appearing |
| **FAIRWIND HOTEL & SUITES** | Section D ($94.70) | **Section E** | ⬇️ Lost — no refundable offers |
| **Viajero Miami** | Section D ($117.65, HyperGuestDirect) | **Section E** | ⬇️ Lost — no refundable offers |
| **Kimpton Angler's Hotel** | #26 (+$21.30) | **#25 (+$21.30)** | → Unchanged — still severely overpriced |
| Crystal Beach Suites Hotel | #2 ($188.05, +$0.01) | #2 ($167.16, +$0.01) | → Persistent #2, repriced but still behind |

### Net Position Summary
- **Gained #1:** Hyatt Centric South Beach (+1)
- **Lost #1:** Eurostars Langford (→ E), The Villa Casa Casuarina (→ #2) (-2)
- **Net #1 change: -1** (9 → 8)
- **Net Knowaa listed: -1** (16 → 15)
- **Section E grew: +3** (10 → 13) — inventory exhaustion for Apr 20–21

---

## Provider Landscape

| Provider | Hotels Present | Δ vs Apr 1 | Notes |
|----------|--------------|-----------|-------|
| InnstantTravel | 42 / 55 (76%) | -3 | Dominant across all categories |
| **Knowaa_Global_zenith** | **15 / 55 (27%)** | **-1** | Present in 15 hotels |
| goglobal | ~9 / 55 (16%) | ≈ | Strong in luxury — Riu Plaza, Villa Casa |
| HyperGuestDirect⇄ | 0 / 55 (0%) | -1 | Viajero Miami dropped to no-offer |

---

## Key Actions Required

| Priority | Hotel | Venue | Issue | Recommended Action |
|----------|-------|-------|-------|-------------------|
| 🔴 CRITICAL | Kimpton Angler's Hotel | 5136 | Rank #25 (+$21.30) — 3rd scan unchanged | **Reprice in Noovy to ≤$373** |
| 🔴 HIGH | DoubleTree by Hilton Miami Doral | 5082 | Knowaa disappeared (was #19 by $0.01) | Check Noovy availability / Innstant sync |
| 🟡 MED | The Villa Casa Casuarina | 5075 | Fell from #1 → #2 (+$0.01); price jumped $367 | Review rate — drop $0.02 → #1 |
| 🟡 MED | Cadet Hotel | 5095 | #2 by $0.01 (since Apr 1 morning) | Drop $0.02 → #1 (persistent quick win) |
| 🟡 MED | Crystal Beach Suites Hotel | 5100 | #2 by $0.01 (since Apr 1 morning) | Drop $0.02 → #1 (persistent quick win) |
| 🟡 MED | Freehand Miami | 5107 | #2 by $0.25 | Drop $0.26 → #1 |
| 🟡 MED | citizenM Miami South Beach | 5119 | #3 by $0.01 | Drop $0.02 → #1 |
| 🟡 MED | Loews Miami Beach Hotel | 5073 | #3 by $0.01 | Drop $0.02 → #1 |
| 🔵 LOW | 27 hotels in Section D | various | Knowaa absent | Activate Noovy availability for these properties |

> **Quick wins (7 hotels):** A small price reduction on Cadet, Crystal Beach, Freehand, Villa Casa Casuarina, citizenM SB, and Loews would bring Knowaa to **#1 in 14 hotels (25%)** vs current 8 (15%).

---

## Historical Trend (Apr 20–21 search window)

| Metric | Mar 31 07:10 | Apr 1 08:16 | Apr 1 13:41 | Apr 2 00:37 | Trend |
|--------|-------------|------------|------------|------------|-------|
| Knowaa #1 | n/a | 8 | 9 | **8** | ↑↓ (volatile) |
| Knowaa listed | n/a | 15 | 16 | **15** | ↑↓ |
| Hotels w/ offers | n/a | 45 | 45 | **42** | ↓ (-3, inventory tightening) |
| Section E (no offers) | n/a | 10 | 10 | **13** | ↓ inventory shrinking |

> Apr 20–21 inventory appears to be tightening — 3 additional hotels lost all refundable offers overnight. Knowaa's position count (8) matches the Apr 1 morning baseline.

---

*Knowaa Competitive Scanner — 2026-04-02 08:03 UTC*
*Data: Innstant B2B scan (00:37 UTC) | Search: Apr 20–21 2026 | Filter: Refundable only*
*Compared against: 2026-04-01 13:41 UTC scan*
