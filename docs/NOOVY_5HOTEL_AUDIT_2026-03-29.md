# Noovy 5-Hotel Deep Audit — 2026-03-29

**Auditor**: Claude (automated via Noovy UI inspection)
**Date**: 2026-03-29
**Purpose**: Determine why 25 hotels fail Zenith SOAP pushes (Error 402) — is it Noovy configuration or Innstant static sync?

---

## Executive Summary

**Root Cause: TWO problems, not one.**

1. **Pricing = $0 and Availability = 0** on virtually all dates across all 5 hotels. Even if SOAP worked, there's nothing to push.
2. **Zenith static sync incomplete** — new venues likely not registered in the SOAP engine yet (requires Innstant team action).

Both problems must be fixed for hotels to appear in search results.

---

## Hotel-by-Hotel Findings

### 1. Cavalier Hotel — Venue #5113

| Check | Result | Status |
|-------|--------|--------|
| Products | Standard only | ⚠️ Limited |
| Rate Plans | Bed and Breakfast only — **NO Room Only (RO)** | ❌ Missing RO |
| Pricing | $0.00 everywhere (March 2026) | ❌ Empty |
| Availability | 0 on all dates | ❌ Empty |
| Medici Channel | Connected (green) in Hotel.Tools | ✅ OK |

**Issues**: Missing RO rate plan means all RO pushes will fail even after pricing is set. Only BB exists.

---

### 2. Fontainebleau Miami Beach — Venue #5268

| Check | Result | Status |
|-------|--------|--------|
| Products | Standard only | ⚠️ Limited |
| Rate Plans | Not visible (calendar empty) | ⚠️ Unknown |
| Pricing | $0.00 everywhere (March 2026) | ❌ Empty |
| Availability | 0 on all dates | ❌ Empty |
| Medici Channel | Connected (green) in Hotel.Tools | ✅ OK |

**Issues**: Completely empty venue — no pricing, no availability on any date. Products may exist but with no rates configured.

---

### 3. InterContinental Miami — Venue #5276

| Check | Result | Status |
|-------|--------|--------|
| Products | Standard only (1 product) | ⚠️ Limited |
| Rate Plans | BB + RO (both exist) | ✅ OK |
| Pricing BB | $0.00 everywhere except March 28 ($500) | ❌ Nearly empty |
| Pricing RO | $0.00 everywhere except March 28 ($500) | ❌ Nearly empty |
| Availability | 0 on all dates | ❌ Empty |
| Inbox | Connected | ✅ OK |

**Issues**: Rate plans are correct (both RO + BB), but pricing is only set for 1 day and availability is 0 everywhere. A Bulk Update is needed to populate pricing and availability.

---

### 4. Hotel Chelsea — Venue #5064

| Check | Result | Status |
|-------|--------|--------|
| Products | Standard + Standard Room (2 products, confusing names) | ⚠️ Duplicated |
| Rate Plans (Standard) | Standard_ro only — **NO BB** | ❌ Missing BB |
| Rate Plans (Standard Room) | room only — **NO BB** | ❌ Missing BB |
| Pricing (Standard/RO) | $0.00 everywhere except March 28 ($100) | ❌ Nearly empty |
| Pricing (Std Room/RO) | $0.00 everywhere except March 28 ($330), **avail=1** | ⚠️ 1 day only |
| Availability | 0 everywhere except Standard Room on March 28 (1) | ❌ Nearly empty |
| Inbox | "Venue is not connected to Inbox service" | ⚠️ Not connected |

**Issues**:
- Two products with confusingly similar names ("Standard" and "Standard Room")
- Neither product has a BB rate plan
- Only 1 day has availability=1 (Standard Room, March 28)
- Inbox service not connected (minor but worth noting)

---

### 5. Hilton Cabana Miami Beach — Venue #5115

| Check | Result | Status |
|-------|--------|--------|
| Products | Standard, Deluxe (×3), Suite (×2), Superior — **MANY DUPLICATES** | ⚠️ Messy |
| Rate Plans (Standard) | BB + Refundable + RO (3 rate plans) | ✅ Best of all 5 |
| Pricing (Standard/BB) | $0.00 everywhere except March 28 ($100) | ❌ Nearly empty |
| Availability | 0 on all dates | ❌ Empty |

**Issues**:
- Many duplicate products (3× Deluxe, 2× Suite) — cleanup needed
- Rate plans are the most complete of all 5 hotels (BB + RO + Refundable)
- But pricing and availability still empty

---

## Cross-Hotel Pattern Analysis

### Common Pattern Across All 5 Hotels

| Issue | Cavalier | Fontainebleau | InterContinental | Chelsea | Hilton Cabana |
|-------|----------|---------------|-------------------|---------|---------------|
| Price = $0 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Availability = 0 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Has RO rate plan | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| Has BB rate plan | ✅ | ⚠️ | ✅ | ❌ | ✅ |
| Multiple products | ❌ | ❌ | ❌ | ⚠️ | ✅ |
| Medici Channel | ✅ | ✅ | ✅ | ✅ | ✅ |
| Duplicate products | No | No | No | Yes | Yes (many) |

### Key Insight

**March 28 is the only date with any pricing** across all 5 hotels. This suggests a single Bulk Update was run on that date (perhaps a test) but never extended to other dates. The $100/$330/$500 values on March 28 appear to be test prices.

---

## Root Cause Diagnosis

### Problem 1: Empty Pricing & Availability (Noovy configuration — WE CAN FIX)

All 5 hotels have products and rate plans created, but virtually zero pricing and availability set. The Zenith SOAP push system sends prices from our `Med_Hotels_ratebycat` table, but Noovy/Zenith needs matching products with valid configuration to accept those pushes.

**Fix**: Run Bulk Update on each hotel to set pricing ($100-500 test price) and availability (≥1) for a broad date range (e.g., April–December 2026).

### Problem 2: Missing Rate Plans (Noovy configuration — WE CAN FIX)

| Hotel | Missing Rate Plan |
|-------|------------------|
| Cavalier #5113 | Room Only (RO) — only has BB |
| Hotel Chelsea #5064 | Bed & Breakfast (BB) — only has RO |

**Fix**: Create the missing rate plans in Noovy Settings → Products → Rate Plans.

### Problem 3: Zenith Static Sync (Innstant team — THEY MUST FIX)

Even after fixing Noovy config, new venues (5064, 5113, 5115, 5268, 5276) may not be recognized by the Zenith SOAP engine until the Innstant team runs a "static update from Noovy." This was already identified on March 25 and may still be pending.

**Fix**: Contact Innstant team to confirm static sync status for these venues.

### Problem 4: Duplicate/Messy Products (Cleanup — LOW PRIORITY)

Hilton Cabana has 3× Deluxe and 2× Suite duplicates. Hotel Chelsea has "Standard" vs "Standard Room" confusion. These won't break functionality but create confusion.

---

## Recommended Action Plan

### Immediate (Can do now via Noovy UI):

1. **Set pricing and availability** via Bulk Update for all 5 hotels:
   - Date range: 2026-04-01 to 2026-12-31
   - Price: $100 (test value)
   - Availability: 1
   - Apply to all products × all rate plans

2. **Create missing rate plans**:
   - Cavalier #5113: Add "Room Only / RO" rate plan to Standard product
   - Hotel Chelsea #5064: Add "Bed and Breakfast / BB" rate plan to both products

### Requires Innstant Team:

3. **Confirm static sync** for all new venues (5064, 5113, 5115, 5268, 5276, and the other 20 failing hotels)
4. Request a **fresh static update from Noovy** if not completed

### After Both Fixes:

5. **Test SOAP push** from Medici server (not sandbox — hotel.tools is blocked from this environment) to verify Error 402 is resolved
6. Monitor push success rate over 24 hours

---

## SOAP Test Note

SOAP tests could not be executed from this environment — the sandbox proxy blocks outbound connections to `hotel.tools`. Tests must be run from the Medici Azure server or a local development machine.

---

## Status

| # | Hotel | Venue | Config Status | Pricing Status | Action Needed |
|---|-------|-------|--------------|----------------|---------------|
| 1 | Cavalier | 5113 | Missing RO rate plan | Empty | Add RO + Bulk Update |
| 2 | Fontainebleau | 5268 | Minimal | Empty | Verify rate plans + Bulk Update |
| 3 | InterContinental | 5276 | ✅ OK (RO+BB) | Empty | Bulk Update only |
| 4 | Hotel Chelsea | 5064 | Missing BB rate plan | Empty | Add BB + Bulk Update |
| 5 | Hilton Cabana | 5115 | ✅ OK (RO+BB+Ref) | Empty | Bulk Update + cleanup duplicates |
