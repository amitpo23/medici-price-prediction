# Med_Hotels_ratebycat — Mapping Fix for 28 Hotels

**Date**: 2026-03-26
**Problem**: 28 hotels have wrong RatePlanCode (12035/13168 from SLS LUX #5077). Each hotel has its own unique RPCs in Hotel.Tools.
**Impact**: All SOAP pushes fail with Error 402 — rooms not pushed to Zenith, not visible to customers.

---

## Correct RPC Mapping (from Hotel.Tools scan)

| # | Hotel | Venue | Correct RO RPC | Correct BB RPC | Current DB (wrong) | Products in HT |
|---|-------|-------|---------------|---------------|-------------------|----------------|
| 1 | Cavalier Hotel | 5113 | 12103 | 12866 | 12035/13168 | Standard |
| 2 | citizenM Miami South Beach | 5119 | 13551 | 13556 | 12035/13168 | Standard |
| 3 | Dorchester Hotel | 5266 | 13488 | 13561 | 12035/13168 | Standard |
| 4 | DoubleTree by Hilton Doral | 5082 | 12046 | 13171 | 12035/13168 | Standard, Suite |
| 5 | Fontainebleau Miami Beach | 5268 | 13489 | 13562 | 12035/13168 | Multiple (5 rooms) |
| 6 | Gale Miami Hotel | 5278 | 13567 | 13568 | 12035/13168 | Standard |
| 7 | Gale South Beach | 5267 | 13507 | 13539 | 12035/13168 | Standard |
| 8 | Generator Miami | 5274 | 13493 | 13563 | 12035/13168 | Standard |
| 9 | Grand Beach Hotel | 5124 | 13552 | 13557 | 12035/13168 | Standard |
| 10 | Hilton Cabana Miami Beach | 5115 | 13571 | 13572 | 12035/13168 | Standard |
| 11 | Hilton Garden Inn SB | 5279 | 13494 | 13564 | 12035/13168 | Standard |
| 12 | Hilton Miami Airport | 5083 | 12047 | 13172 | 12035/13168 | Deluxe, Standard, Suite |
| 13 | Holiday Inn Express Miami | 5130 | 13553 | 13558 | 12035/13168 | Standard |
| 14 | Hotel Belleza | 5265 | 13490 | *NONE* | 12035/13168 | Multiple |
| 15 | Hotel Chelsea | 5064 | 12109 | *NONE* | 12035/13168 | Standard |
| 16 | Hotel Croydon | 5131 | 12119 | *NONE* | 12035/13168 | Standard |
| 17 | Hotel Gaythering | 5132 | 13554 | 13559 | 12035/13168 | Standard |
| 18 | InterContinental Miami | 5276 | 13569 | 13570 | 12035/13168 | Standard |
| 19 | Kimpton Angler's Hotel | 5136 | 13491 | 13565 | 12035/13168 | Standard |
| 20 | Kimpton Palomar SB | 5116 | 13523 | 13536 | 12035/13168 | Standard |
| 21 | Loews Miami Beach | 5073 | 12033 | 12886 | 12033/- | Standard, Suite |
| 22 | Metropole South Beach | 5141 | 13555 | 13560 | 12035/13168 | Standard |
| 23 | Miami Airport Hotel | 5275 | 13492 | 13566 | 12035/13168 | Standard |
| 24 | Notebook Miami Beach | 5102 | 12070 | 13156 | 12070/13156 | Standard (already correct!) |
| 25 | SERENA Hotel Aventura | 5139 | 13522 | 13535 | 12035/13168 | Standard |
| 26 | The Albion Hotel | 5117 | 13486 | *NONE* | 12035/13168 | Standard |
| 27 | The Catalina Hotel | 5277 | 13487 | *NONE* | 12035/13168 | Standard |
| 28 | The Gates Hotel SB | 5140 | 12128 | *NONE* | 12035/13168 | Standard |
| 29 | THE LANDON BAY HARBOR | 5138 | 12126 | *NONE* | 12035/13168 | Standard |
| 30 | The Villa Casa Casuarina | 5075 | 13508 | 13538 | 12035/13168 | Standard |

---

## Hotels WITHOUT BB Rate Plan (7 hotels)

These hotels only have RO — need BB rate plan created in Hotel.Tools:
- 5064 Hotel Chelsea
- 5117 The Albion Hotel
- 5131 Hotel Croydon
- 5138 THE LANDON BAY HARBOR
- 5140 The Gates Hotel SB
- 5265 Hotel Belleza
- 5277 The Catalina Hotel

---

## Hotels with ONLY Standard product (most hotels)

Most hotels only have "Standard" linked to rate plans. Need Deluxe and Suite products created and linked.

**Hotels that already have multiple products:**
- 5082 DoubleTree: Standard, Suite
- 5083 Hilton Airport: Deluxe, Standard, Suite
- 5073 Loews: Standard, Suite
- 5268 Fontainebleau: 5 room types

---

## SQL Update Script

```sql
-- ============================================================
-- BACKUP FIRST
-- ============================================================
SELECT * INTO BAK_Med_Hotels_ratebycat_20260326
FROM Med_Hotels_ratebycat
WHERE HotelId IN (
    SELECT HotelId FROM Med_Hotels
    WHERE Innstant_ZenithId IN (5113,5119,5266,5082,5268,5278,5267,5274,5124,5115,5279,5083,5130,5265,5064,5131,5132,5276,5136,5116,5141,5275,5139,5117,5277,5140,5138,5075)
);

-- ============================================================
-- UPDATE RO Rate Plans (BoardId = 1)
-- ============================================================

-- Cavalier 5113: 12035 → 12103
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12103
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5113)
AND BoardId = 1;

-- citizenM SB 5119: 12035 → 13551
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13551
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5119)
AND BoardId = 1;

-- Dorchester 5266: 12035 → 13488
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13488
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5266)
AND BoardId = 1;

-- DoubleTree 5082: 12035 → 12046
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12046
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5082)
AND BoardId = 1;

-- Fontainebleau 5268: 12035 → 13489
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13489
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5268)
AND BoardId = 1;

-- Gale Miami 5278: 12035 → 13567
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13567
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5278)
AND BoardId = 1;

-- Gale SB 5267: 12035 → 13507
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13507
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5267)
AND BoardId = 1;

-- Generator 5274: 12035 → 13493
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13493
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5274)
AND BoardId = 1;

-- Grand Beach 5124: 12035 → 13552
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13552
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5124)
AND BoardId = 1;

-- Hilton Cabana 5115: 12035 → 13571
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13571
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5115)
AND BoardId = 1;

-- Hilton Garden 5279: 12035 → 13494
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13494
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5279)
AND BoardId = 1;

-- Hilton Airport 5083: 12035 → 12047
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12047
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5083)
AND BoardId = 1;

-- Holiday Inn 5130: 12035 → 13553
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13553
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5130)
AND BoardId = 1;

-- Belleza 5265: 12035 → 13490
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13490
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5265)
AND BoardId = 1;

-- Chelsea 5064: 12035 → 12109
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12109
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5064)
AND BoardId = 1;

-- Croydon 5131: 12035 → 12119
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12119
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5131)
AND BoardId = 1;

-- Gaythering 5132: 12035 → 13554
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13554
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5132)
AND BoardId = 1;

-- InterContinental 5276: 12035 → 13569
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13569
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5276)
AND BoardId = 1;

-- Kimpton Anglers 5136: 12035 → 13491
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13491
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5136)
AND BoardId = 1;

-- Kimpton Palomar 5116: 12035 → 13523
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13523
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5116)
AND BoardId = 1;

-- Metropole 5141: 12035 → 13555
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13555
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5141)
AND BoardId = 1;

-- Miami Airport 5275: 12035 → 13492
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13492
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5275)
AND BoardId = 1;

-- SERENA 5139: 12035 → 13522
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13522
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5139)
AND BoardId = 1;

-- Albion 5117: 12035 → 13486
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13486
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5117)
AND BoardId = 1;

-- Catalina 5277: 12035 → 13487
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13487
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5277)
AND BoardId = 1;

-- Gates 5140: 12035 → 12128
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12128
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5140)
AND BoardId = 1;

-- Landon 5138: 12035 → 12126
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12126
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5138)
AND BoardId = 1;

-- Villa Casa 5075: 12035 → 13508
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13508
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5075)
AND BoardId = 1;

-- ============================================================
-- UPDATE BB Rate Plans (BoardId = 2)
-- ============================================================

-- citizenM SB 5119: 13168 → 13556
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13556
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5119)
AND BoardId = 2;

-- Dorchester 5266: 13168 → 13561
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13561
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5266)
AND BoardId = 2;

-- DoubleTree 5082: 13168 → 13171
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13171
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5082)
AND BoardId = 2;

-- Fontainebleau 5268: 13168 → 13562
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13562
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5268)
AND BoardId = 2;

-- Gale Miami 5278: 13168 → 13568
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13568
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5278)
AND BoardId = 2;

-- Gale SB 5267: 13168 → 13539
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13539
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5267)
AND BoardId = 2;

-- Generator 5274: 13168 → 13563
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13563
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5274)
AND BoardId = 2;

-- Grand Beach 5124: 13168 → 13557
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13557
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5124)
AND BoardId = 2;

-- Hilton Cabana 5115: 13168 → 13572
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13572
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5115)
AND BoardId = 2;

-- Hilton Garden 5279: 13168 → 13564
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13564
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5279)
AND BoardId = 2;

-- Hilton Airport 5083: 13168 → 13172
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13172
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5083)
AND BoardId = 2;

-- Holiday Inn 5130: 13168 → 13558
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13558
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5130)
AND BoardId = 2;

-- Cavalier 5113: 13168 → 12866
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 12866
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5113)
AND BoardId = 2;

-- Gaythering 5132: 13168 → 13559
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13559
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5132)
AND BoardId = 2;

-- InterContinental 5276: 13168 → 13570
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13570
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5276)
AND BoardId = 2;

-- Kimpton Anglers 5136: 13168 → 13565
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13565
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5136)
AND BoardId = 2;

-- Kimpton Palomar 5116: 13168 → 13536
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13536
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5116)
AND BoardId = 2;

-- Metropole 5141: 13168 → 13560
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13560
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5141)
AND BoardId = 2;

-- Miami Airport 5275: 13168 → 13566
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13566
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5275)
AND BoardId = 2;

-- SERENA 5139: 13168 → 13535
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13535
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5139)
AND BoardId = 2;

-- Villa Casa 5075: 13168 → 13538
UPDATE Med_Hotels_ratebycat SET RatePlanCode = 13538
WHERE HotelId = (SELECT HotelId FROM Med_Hotels WHERE Innstant_ZenithId = 5075)
AND BoardId = 2;

-- ============================================================
-- DELETE BB rows for hotels WITHOUT BB rate plan (7 hotels)
-- These hotels only have RO in Hotel.Tools
-- ============================================================
DELETE FROM Med_Hotels_ratebycat
WHERE BoardId = 2
AND HotelId IN (
    SELECT HotelId FROM Med_Hotels
    WHERE Innstant_ZenithId IN (5064, 5117, 5131, 5138, 5140, 5265, 5277)
);

-- ============================================================
-- VERIFY
-- ============================================================
SELECT h.name, h.Innstant_ZenithId as venue, r.InvTypeCode, r.RatePlanCode,
    CASE r.BoardId WHEN 1 THEN 'RO' WHEN 2 THEN 'BB' END as Board
FROM Med_Hotels h
JOIN Med_Hotels_ratebycat r ON h.HotelId = r.HotelId
WHERE h.Innstant_ZenithId IN (5113,5119,5266,5082,5268,5278,5267,5274,5124,5115,5279,5083,5130,5265,5064,5131,5132,5276,5136,5116,5141,5275,5139,5117,5277,5140,5138,5075)
ORDER BY h.name, r.BoardId, r.InvTypeCode;
```

---

## Remaining Work After SQL Update

1. **Innstant static sync must complete** — until then, even correct RPCs will fail SOAP
2. **Create Deluxe/Suite products** in Hotel.Tools for hotels that only have Standard
3. **Create BB rate plans** in Hotel.Tools for the 7 hotels without BB
4. **Set availability + pricing** in Noovy for all hotels
