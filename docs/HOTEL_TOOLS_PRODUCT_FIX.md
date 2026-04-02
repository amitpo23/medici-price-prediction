# Hotel.Tools — Missing Products Fix Guide

## Status: 82 Products missing across 39 hotels

**Date:** 2026-04-02  
**Audit report:** `scripts/product_audit_report.json`  
**Fix script:** `scripts/fix_missing_products.js`

## The Problem

The SalesOffice WebJob pushes availability (BookingLimit=1) for all room types
mapped in `Med_Hotels_ratebycat`. When Zenith/Hotel.Tools doesn't have a matching
Product for that InvTypeCode, the push **fails silently** — the room never appears
for sale on Innstant.

**Since April 1:** ~4,000 failed push attempts, 34 of 50 hotels affected.  
**Root cause:** Products not created in Hotel.Tools for many room types.

## What Needs To Be Done

For each hotel below, create the listed Products in Hotel.Tools:
1. Login → https://hotel.tools (Medici LIVE / zvi / karpad66)
2. Switch venue context (top dropdown) to the hotel
3. Go to Products → New
4. Fill: Type=room, Title, Short Name, Base Price=$500, Currency=USD, Status=Active
5. **Set venue** in the form (select[name="venue"])
6. Save

## Complete Missing Products List

| Venue | Hotel | Missing Products |
|-------|-------|-----------------|
| 5073 | Loews Miami Beach | DLX (Deluxe) |
| 5075 | Villa Casa Casuarina | Suite |
| 5077 | SLS LUX Brickell | SPR (Superior) |
| 5079 | citizenM Brickell | DLX, SPR, Suite |
| 5080 | Pullman Miami Airport | APT (Apartment), EXEC (Executive) |
| 5081 | Embassy Suites | DLX, SPR, DRM (Dormitory) |
| 5083 | Hilton Miami Airport | DRM |
| 5084 | Hilton Downtown | DLX, SPR |
| 5089 | Fairwind Hotel | SPR, Suite |
| 5090 | Dream South Beach | DLX, SPR |
| 5092 | Iberostar Berkeley | SPR, APT |
| 5093 | Hilton Bentley SB | SPR, APT |
| 5095 | Cadet Hotel | DLX, SPR |
| 5096 | Marseilles Hotel | DLX, SPR, DRM |
| 5097 | Hyatt Centric SB | SPR, Suite |
| 5098 | Eurostars Langford | SPR, APT, DRM, EXEC |
| 5100 | Crystal Beach Suites | Stnd (Standard), DLX, SPR |
| 5101 | Atwell Suites Brickell | DLX, SPR |
| 5103 | Savoy Hotel | SPR |
| 5104 | Sole Miami | DLX, SPR |
| 5105 | MB Hotel | SPR |
| 5107 | Freehand Miami | DLX, DRM |
| 5108 | Gabriel South Beach | SPR |
| 5109 | Riu Plaza Miami Beach | SPR, Suite |
| 5110 | Breakwater South Beach | APT |
| 5115 | Hilton Cabana | DRM |
| 5117 | Albion Hotel | DLX, APT, DRM |
| 5124 | Grand Beach Hotel | Suite |
| 5130 | Holiday Inn Express | Suite |
| 5131 | Hotel Croydon | Suite |
| 5136 | Kimpton Anglers | DLX, APT, Suite |
| 5139 | SERENA Aventura | DLX, SPR, Suite |
| 5265 | Hotel Belleza | Stnd, SPR, DBL (Double) |
| 5266 | Dorchester Hotel | Stnd, Suite, APT, DBL |
| 5267 | Gale South Beach | 1QSR (Queen Standard) |
| 5268 | Fontainebleau | Stnd, DLX, Suite, APT, OV2Q (Ocean View) |
| 5274 | Generator Miami | DLX, SPR, Suite, DRM |
| 5276 | InterContinental Miami | DLX, Suite |
| 5278 | Gale Miami Hotel | Suite, APT |

**Total: 82 products across 39 venues**

## Most Common Missing Product: Superior (SPR) — 22 hotels

## Automation Script

`scripts/fix_missing_products.js` — Playwright-based, but currently blocked because
Hotel.Tools changed the venue select to `select2-hidden-accessible` which blocks
Playwright's `selectOption()`.

**Known fix needed:** The `setProductVenue()` function needs to use `page.evaluate()`
with jQuery select2 API instead of Playwright `selectOption`. The current JS evaluate
approach sets the value but the form POST still returns 500 "Something went wrong".

**The original script `create_products_26_venues.js` also fails now** with the same
select2 issue — confirmed on 2026-04-02.

## Manual Workaround

Create products one-by-one in the Hotel.Tools UI. Start with highest-impact:

### Priority 1 — Most room types missing (create these first)
1. **Fontainebleau (5268)** — 5 products: Stnd, DLX, Suite, APT, OV2Q
2. **Eurostars Langford (5098)** — 4 products: SPR, APT, DRM, EXEC
3. **Generator Miami (5274)** — 4 products: DLX, SPR, Suite, DRM
4. **Dorchester Hotel (5266)** — 4 products: Stnd, Suite, APT, DBL

### Priority 2 — Hotels with 3 missing
5. citizenM Brickell (5079) — DLX, SPR, Suite
6. Embassy Suites (5081) — DLX, SPR, DRM
7. Crystal Beach (5100) — Stnd, DLX, SPR
8. Hotel Belleza (5265) — Stnd, SPR, DBL
9. Marseilles (5096) — DLX, SPR, DRM
10. Kimpton Anglers (5136) — DLX, APT, Suite
11. SERENA Aventura (5139) — DLX, SPR, Suite
12. Albion Hotel (5117) — DLX, APT, DRM

### Priority 3 — Hotels with 2 missing
(remaining 16 hotels with 2 products each)

### Priority 4 — Hotels with 1 missing
(remaining 11 hotels with 1 product each)

## Also Fix: Hotel Gaythering $5,000 Price

Venue 5132 has a test price of $5,000 on standard/RO (RatePlan 12120).
Update to a realistic price (~$180) in Noovy Bulk Update.

## Verification After Fix

Run the audit script to verify:
```bash
python3 scripts/create_all_products.py
```

Expected result: 0 missing products.
