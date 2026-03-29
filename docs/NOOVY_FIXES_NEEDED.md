# Noovy Fixes Needed — Hotel Configuration Audit

**Date**: 2026-03-29
**Status**: Action required in Noovy UI (DB is read-only)

---

## A4. Hotels with Partial Rates in Med_Hotels_ratebycat

### 1. citizenM Miami Brickell (HotelId 854881, Zenith 5079)

**RatePlanCodes**: RO = `12043`, BB = `13169`

| Category | InvTypeCode | RO (Board 1) | BB (Board 2) | Action |
|----------|------------|---------------|--------------|--------|
| Standard (1) | Stnd | 12043 ✅ | 13169 ✅ | — |
| Superior (2) | SPR | 12043 ✅ | ❌ MISSING | **Add BB rate** (RatePlan 13169, InvType SPR) |
| Deluxe (4) | DLX | 12043 ✅ | ❌ MISSING | **Add BB rate** (RatePlan 13169, InvType DLX) |
| Suite (12) | Suite | 12043 ✅ | ❌ MISSING | **Add BB rate** (RatePlan 13169, InvType Suite) |

**Active scan details**: standard(RO $208, BB $254) — only 2 rooms scanning, likely because SPR/DLX/Suite have no availability set.

**Noovy action**: Add 3 BB rates for SPR, DLX, Suite using RatePlanCode `13169`.

---

### 2. DoubleTree by Hilton Miami Doral (HotelId 733781, Zenith 5082)

**RatePlanCodes**: RO = `12046`, BB = `13171`

| Category | InvTypeCode | RO (Board 1) | BB (Board 2) | Action |
|----------|------------|---------------|--------------|--------|
| Standard (1) | Stnd | 12046 ✅ | 13171 ✅ | — |
| Superior (2) | SPR | ❌ MISSING | ❌ MISSING | **Add both RO + BB rates** |
| Deluxe (4) | DLX | ❌ MISSING | ❌ MISSING | **Add both RO + BB rates** |
| Suite (12) | Suite | 12046 ✅ | 13171 ✅ | — |

**Active scan details**: standard(BB $237), suite(RO $257, BB $283) — 3 rooms scanning, no standard RO showing (may be price/availability issue).

**Noovy action**: Add 4 rates — SPR(RO 12046, BB 13171) + DLX(RO 12046, BB 13171).

---

### 3. Hampton Inn Miami Beach - Mid Beach (HotelId 854875, Zenith 5106)

**RatePlanCodes**: RO = `12074`, BB = **UNKNOWN** (no BB rate exists to reference)

| Category | InvTypeCode | RO (Board 1) | BB (Board 2) | Action |
|----------|------------|---------------|--------------|--------|
| Standard (1) | Stnd | 12074 ✅ | ❌ MISSING | **Add BB rate** (need to find/create BB RatePlanCode in Noovy) |
| Superior (2) | SPR | ❌ MISSING | ❌ MISSING | **Add both RO + BB rates** |
| Deluxe (4) | DLX | ❌ MISSING | ❌ MISSING | **Add both RO + BB rates** |

**Active scan details**: standard(RO $244) — only 1 room scanning.

**Noovy action**:
1. First, check in Noovy what the BB RatePlanCode is for Zenith 5106 (Hampton Inn). If no BB rate plan exists, create one.
2. Add BB for Standard, then add SPR(RO+BB) and DLX(RO+BB).
3. Total: 5 new rates needed (1 BB Stnd + 2 SPR + 2 DLX).

---

## A3. Hotels with Rates in ratebycat but Incomplete Coverage

### 4. Loews Miami Beach Hotel (HotelId 6661, Zenith 5073)

**RatePlanCodes**: RO = `12033`, BB = `12886`

| Category | InvTypeCode | RO (Board 1) | BB (Board 2) | Action |
|----------|------------|---------------|--------------|--------|
| Standard (1) | Stnd | 12033 ✅ | 12886 ✅ | — |
| Deluxe (4) | DLX | 12033 ✅ | ❌ MISSING | **Add BB rate** (RatePlan 12886, InvType DLX) |
| Suite (12) | Suite | 12033 ✅ | 12886 ✅ | — |

**Note**: User's original assessment said "NO rates in ratebycat" — this is outdated. Loews has 5 rates. Only DLX BB is missing.

**Active scan details**: standard(RO $342, BB $413), suite(RO $719, BB $996) — 4 rooms scanning. No DLX showing in scans (availability issue).

**Noovy action**: Add 1 BB rate for DLX using RatePlanCode `12886`.

---

### 5. Hyatt Centric South Beach Miami (HotelId 314212, Zenith 5097)

**RatePlanCodes**: RO = `12066`, BB = `13160`

| Category | InvTypeCode | RO (Board 1) | BB (Board 2) | Action |
|----------|------------|---------------|--------------|--------|
| Standard (1) | Stnd | 12066 ✅ | 13160 ✅ | — |
| Superior (2) | SPR | 12066 ✅ | ❌ MISSING | **Add BB rate** (RatePlan 13160, InvType SPR) |
| Deluxe (4) | DLX | 12066 ✅ | 13160 ✅ | — |
| Suite (12) | Suite | 12066 ✅ | 13160 ✅ | — |

**Note**: User's original assessment said "NO rates in ratebycat" — this is outdated. Hyatt has 7 rates. Only SPR BB is missing.

**Active scan details**: standard(BB $284), deluxe(BB $323) — only 2 rooms scanning, no RO rooms showing.

**Noovy action**: Add 1 BB rate for SPR using RatePlanCode `13160`.

---

## A5. Cleanup Tasks

### A5.1. Hampton Inn Duplicate (HotelId 826299)

| Field | HotelId 826299 | HotelId 854875 |
|-------|----------------|----------------|
| Name | Hampton Inn Miami Beach - Mid Beach, FL | Hampton Inn Miami Beach - Mid Beach |
| Zenith | 5106 | 5106 |
| isActive | true | true |
| Rates in ratebycat | 0 | 1 (Stnd RO) |
| Active details | 0 | 1 (standard RO $244) |

**Diagnosis**: HotelId 826299 is a duplicate entry with no rates and no scan results. It shares the same Zenith 5106 as 854875 which is the active entry.

**Action needed**: Deactivate HotelId 826299 in Med_Hotels (set `isActive = false`). This hotel has zero configuration and zero scan data — keeping it active is harmless but adds noise.

---

### A5.2. Freehand Miami (HotelId 6660, Zenith 5107) — Erroneous Price

| Detail | RoomCategory | RoomBoard | Price | Status |
|--------|-------------|-----------|-------|--------|
| Active | superior | RO | $106.45 | Normal |
| Active | superior | BB | **$40,447.90** | **ERRONEOUS** |

**Diagnosis**: The BB rate for the superior room is $40,448 — clearly a data error. The RO rate is $106, so BB should be in the $120-$160 range. This is likely a pricing error in Noovy where the price was entered incorrectly (possibly entered in cents instead of dollars, or a typo — 40448 vs 404.48 or 104.48).

**Ratebycat config** (8 rates, looks correct):
- Stnd: RO(12076) + BB(12865)
- SPR: RO(12076) + BB(12865)
- DRM: RO(12076)
- DLX: RO(12076)
- Suite: RO(12076) + BB(12865)

**Action needed**:
1. Check pricing in Noovy for Freehand (Zenith 5107), Superior room, BB rate plan (`12865`).
2. Correct the price — likely should be around $120-$160 (BB is typically $15-$70 above RO).
3. The scan picked up the bad price from the source, so the fix must be made at the rate plan level in Noovy/Zenith.

---

## Summary Checklist

| # | Hotel | Action | Items to Add |
|---|-------|--------|-------------|
| 1 | citizenM Brickell (854881) | Add BB rates | 3 rates: SPR+DLX+Suite BB (RatePlan 13169) |
| 2 | DoubleTree Doral (733781) | Add SPR+DLX | 4 rates: SPR(RO+BB) + DLX(RO+BB) |
| 3 | Hampton Inn (854875) | Add BB + SPR + DLX | 5 rates (need BB RatePlanCode from Noovy first) |
| 4 | Loews Miami Beach (6661) | Add DLX BB | 1 rate: DLX BB (RatePlan 12886) |
| 5 | Hyatt Centric (314212) | Add SPR BB | 1 rate: SPR BB (RatePlan 13160) |
| 6 | Hampton Inn dup (826299) | Deactivate | Set isActive = false |
| 7 | Freehand (6660) | Fix price | Correct Superior BB from $40,448 to ~$120-160 |

**Total new rates to add**: 14 rates across 5 hotels
**Total fixes**: 1 price correction + 1 deactivation
