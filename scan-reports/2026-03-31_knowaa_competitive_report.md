# Knowaa Competitive Position Report — Innstant B2B

**Scan:** 2026-03-31 | **Dates:** Apr 20-21, 2026 (1 night) | **Filter:** Refundable only | **All room types + All boards**

---

## Hotels Where Knowaa IS Listed (6/16)

### 1. Loews Miami Beach Hotel (Venue 5073)
| Category | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Knowaa Rank | Status |
|----------|-------|----------|------------|-------------------|-------------|--------|
| Standard | RO | **$342.00** | $342.00 | **Knowaa_Global_zenith** | **#1** | **CHEAPEST** |

### 2. citizenM Miami South Beach (Venue 5119)
| Category | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Knowaa Rank | Status |
|----------|-------|----------|------------|-------------------|-------------|--------|
| Standard | RO | $175.70 | $175.70 | InnstantTravel (tie) | **#2** | MATCH |

### 3. Hilton Miami Airport (Venue 5083)
| Category | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Knowaa Rank | Status |
|----------|-------|----------|------------|-------------------|-------------|--------|
| Standard | RO | $216.54 | $216.53 | goglobal | **#2** | +$0.01 |

### 4. Kimpton Hotel Palomar South Beach (Venue 5116)
| Category | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Knowaa Rank | Status |
|----------|-------|----------|------------|-------------------|-------------|--------|
| Standard | RO | $181.03 | $181.02 | goglobal | **#2** | +$0.01 |

### 5. Cavalier Hotel (Venue 5113)
| Category | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Knowaa Rank | Status |
|----------|-------|----------|------------|-------------------|-------------|--------|
| Standard | RO | $200.00 | $197.93 | InnstantTravel | #3 | +$2.07 |

### 6. The Villa Casa Casuarina (Venue 5075)
| Category | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Knowaa Rank | Status |
|----------|-------|----------|------------|-------------------|-------------|--------|
| Standard | RO | $1,554.68 | $1,482.50 | goglobal (Suite BB) | #4 | +$72.18 |
| Standard | RO | $5,000.00 | — | — | — | TEST PRICE - REMOVE |

---

## Hotels Where Knowaa is NOT Listed (10/16)

| # | Hotel | VenueId | InnstantId | Categories Found | Boards | Cheapest $ | Cheapest Provider | Providers Present |
|---|-------|---------|------------|-----------------|--------|------------|-------------------|-------------------|
| 7 | Fontainebleau Miami Beach | 5268 | 19977 | Deluxe, Standard | RO | $538.46 | goglobal | goglobal, InnstantTravel |
| 8 | Gale Miami Hotel & Residences | 5278 | 852725 | Standard | RO | $160.47 | InnstantTravel | InnstantTravel, goglobal |
| 9 | Gale South Beach | 5267 | 301645 | Standard | RO | $240.99 | InnstantTravel | InnstantTravel, goglobal |
| 10 | Generator Miami | 5274 | 701659 | Deluxe, Standard | RO | $154.12 | InnstantTravel | InnstantTravel, goglobal |
| 11 | Grand Beach Hotel | 5124 | 68833 | Suite | RO | $206.96 | InnstantTravel | InnstantTravel, goglobal |
| 12 | InterContinental Miami | 5276 | 6482 | Standard | RO | $287.56 | goglobal | goglobal, InnstantTravel |
| 13 | Pullman Miami Airport | 5080 | 6805 | Superior | RO | $176.91 | InnstantTravel | InnstantTravel, goglobal |
| 14 | SERENA Hotel Aventura | 5139 | 851939 | — | — | — | — | **NO REFUNDABLE OFFERS** |
| 15 | Hilton Miami Downtown | 5084 | 24982 | — | — | — | — | **NO REFUNDABLE OFFERS** |
| 16 | DoubleTree Doral (only RO) | 5082 | 733781 | Standard | RO | $211.21 | InnstantTravel | InnstantTravel, Knowaa (#19), goglobal |

---

## Observation: Missing BB (Breakfast) Offers

**Across ALL 16 hotels, almost no BB offers were found in Refundable.** Only Villa Casa had Suite BB from goglobal/InnstantTravel. This means:
- Either BB rates are Non-Refundable only
- Or BB rates are not being pushed by any provider including us

---

## Category/Board Breakdown Per Hotel

| Hotel | Standard RO | Standard BB | Deluxe RO | Deluxe BB | Suite RO | Suite BB | Superior RO |
|-------|-------------|------------|-----------|-----------|----------|----------|-------------|
| Cavalier | 24 offers | 0 | 2 offers | 0 | 0 | 0 | 0 |
| citizenM SB | 14 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| DoubleTree | 21 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| Fontainebleau | 3 offers | 0 | 24 offers | 0 | 0 | 0 | 0 |
| Gale Miami | 30 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| Generator | 1 offer | 0 | 21 offers | 0 | 0 | 0 | 0 |
| Hilton Airport | 23 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| InterContinental | 27 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| Loews | 29 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| Villa Casa | 7 offers | 0 | 0 | 0 | 0 | 6 offers | 0 |
| Pullman | 0 | 0 | 0 | 0 | 0 | 0 | 22 offers |
| Grand Beach | 0 | 0 | 0 | 0 | 8 offers | 0 | 0 |
| Kimpton Palomar | 25 offers | 0 | 0 | 0 | 0 | 0 | 0 |
| Gale South Beach | 18 offers | 0 | 0 | 0 | 0 | 0 | 0 |

---

## Action Items for Dev Team

1. **CRITICAL: Knowaa not appearing in 10/16 hotels** — likely Noovy availability=0 or Innstant static sync incomplete
2. **No BB offers anywhere** — verify BB rate plans are properly configured and pushed
3. **Villa Casa $5,000** — test price leaked to production, must be corrected in Noovy
4. **Competitive position is good** — where we appear, we're #1-#3 in price ranking
5. **Run this scan again after fixing availability** to confirm improvement
