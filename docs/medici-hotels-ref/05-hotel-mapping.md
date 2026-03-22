# 05 - Hotel Mapping & Rate Plans / מיפוי מלונות ותוכניות מחיר

## Overview

כל מלון במערכת Medici חייב מיפוי תקין ל-Zenith Channel Manager. המיפוי מורכב מ-3 חלקים:
1. **Hotel → ZenithId** (בטבלת `Med_Hotels`)
2. **Hotel+Board+Category → RatePlanCode+InvTypeCode** (בטבלת `Med_Hotels_ratebycat`)
3. **isActive = True** (בטבלת `Med_Hotels`)

---

## Zenith Venue Mapping (Full Spreadsheet)

> Based on complete Zenith venue/hotel mapping spreadsheet comparison (2026-02-23)

| # | Zenith VenueId | Hotel Name | Innstant HotelId | Status |
|---|----------------|------------|-------------------|--------|
| 1 | 5029 | Ibis Styles | 838901 | ✅ Mapped |
| 2 | 5030 | Freehand Miami | 1004953 | ✅ Mapped |
| 3 | 5031 | Selina Gold Dust | 1023316 | ✅ Mapped |
| 4 | 5032 | Generator Miami | 1055975 | ✅ Mapped |
| 5 | 5033 | Life House Little Havana | 1088652 | ✅ Mapped |
| 6 | 5034 | citizenM Brickell | 854881 | ✅ Mapped |
| 7 | 5035 | Arlo Wynwood | 1010277 | ✅ Mapped |
| 8 | 5036 | Eurostars Langford | 261038 | ✅ Mapped |
| 9 | 5037 | Riviera Luxury Living | 885653 | ✅ Mapped |
| 10 | 5038 | Mondrian South Beach | 21024 | ✅ Mapped |
| 11 | 5039 | Novotel Miami Brickell | 338285 | ✅ Mapped |
| 12 | 5040 | Urbanica The Meridian | 371764 | ✅ Mapped |
| 13 | 5041 | Hampton Inn Hallandale | 826299 | ✅ Mapped |
| 14 | 5042 | Hyatt Regency Coral Gables | 24964 | ✅ Mapped |
| 15 | 5049 | Hotel AKA Brickell | 1107488 | ✅ Mapped |
| 16 | 5068 | Gabriel South Beach | 23413 | ✅ Mapped |
| 17 | 5069 | Crowne Plaza | 255124 | ✅ Mapped |
| 18 | 5070 | Hilton Cabana | 24969 | ✅ Mapped |
| 19 | 5071 | Hilton Aventura | 1099556 | ✅ Mapped |
| 20 | 5073 | SLS South Beach | 21049 | ✅ Mapped |
| 21 | 5074 | Nautilus by Arlo | 21021 | ✅ Mapped |
| 22 | 5075 | Residence Inn Aventura | 24998 | ✅ Mapped |
| 23 | 5076 | Residence Inn Sunny Isles | 364455 | ✅ Mapped |
| 24 | 5077 | Homewood Suites | 371704 | ✅ Mapped |
| 25 | 5078 | Courtyard Aventura | 24896 | ✅ Mapped |
| 26 | 5079 | Hampton Inn Aventura | 24942 | ✅ Mapped |
| 27 | 5080 | Holiday Inn Express Aventura | 388433 | ✅ Mapped |
| 28 | 5081 | Embassy Suites Doral | 20702 | ✅ **FIXED** 2026-02-23 |
| 29 | 5084 | Hilton Miami Downtown | 24982 | ✅ **FIXED** 2026-02-23 |

### Remaining (Deferred):
| Zenith VenueId | Hotel Name | Innstant HotelId | Status |
|----------------|------------|-------------------|--------|
| 5082 | DoubleTree Doral | 20845 | ⬜ Not yet mapped |
| 5083 | Hilton Miami Airport | 20706 | ⬜ Not yet mapped |
| 5106 | Hotel Continental | (conflict) | ⬜ Conflict - Hampton Inn hotels share VenueId |

---

## Rate Plan (ratebycat) Mapping

### How It Works:
```
FindPushRatePlanCode(hotelId, boardId, categoryId)
  │
  ├── Query: SELECT * FROM Med_Hotels_ratebycat
  │          WHERE HotelId = @hotelId 
  │          AND BoardId = @boardId 
  │          AND CategoryId = @categoryId
  │
  ├── If found: return (RatePlanCode, InvTypeCode)
  │     Example: ('12045', 'STD')
  │
  └── If NOT found: return (null, null)
        → This hotel/board/category has NO push mapping
        → Results in "Rooms With Mapping: 0" for that combo
```

### Current ratebycat Entries for Fixed Hotels:

#### Hotel 20702 (Embassy Suites Doral) — ZenithId 5081
| Id | HotelId | BoardId | CategoryId | RatePlanCode | InvTypeCode |
|----|---------|---------|------------|--------------|-------------|
| 852 | 20702 | 1 (RO) | 1 (Standard) | 12045 | STD |
| 855 | 20702 | 1 (RO) | 12 (Suite) | 12045 | SUI |

#### Hotel 24982 (Hilton Miami Downtown) — ZenithId 5084
| Id | HotelId | BoardId | CategoryId | RatePlanCode | InvTypeCode |
|----|---------|---------|------------|--------------|-------------|
| 853 | 24982 | 1 (RO) | 1 (Standard) | 12048 | STD |
| 854 | 24982 | 1 (RO) | 12 (Suite) | 12048 | SUI |

### Planned ratebycat for Deferred Hotels:

#### Hotel 20845 (DoubleTree Doral) — ZenithId 5082
| HotelId | BoardId | CategoryId | RatePlanCode | InvTypeCode |
|---------|---------|------------|--------------|-------------|
| 20845 | 1 (RO) | 1 (Standard) | 12046 | STD |
| 20845 | 1 (RO) | 4 (Deluxe) | 12046 | DLX |

#### Hotel 20706 (Hilton Miami Airport) — ZenithId 5083
| HotelId | BoardId | CategoryId | RatePlanCode | InvTypeCode |
|---------|---------|------------|--------------|-------------|
| 20706 | 1 (RO) | 4 (Deluxe) | 12047 | DLX |
| 20706 | 1 (RO) | 1 (Standard) | 12047 | STD |
| 20706 | 1 (RO) | 12 (Suite) | 12047 | SUI |

---

## Common InvTypeCode Values
| Code | Room Type |
|------|-----------|
| STD | Standard |
| DLX | Deluxe |
| SUI | Suite |
| SUP | Superior |
| DRM | Dormitory |

---

## Mapping Requirements for a Hotel to Work

### Checklist:
```
□ 1. Med_Hotels.HotelId exists with correct Innstant hotel code
□ 2. Med_Hotels.Innstant_ZenithId > 0 (maps to Zenith VenueId)
□ 3. Med_Hotels.isActive = True (1)
□ 4. Med_Hotels_ratebycat has rows for EACH board+category combo the hotel offers
□ 5. RatePlanCode matches what's configured in Zenith
□ 6. InvTypeCode matches room type in Zenith
```

### If any of these fail:
| Missing | Result |
|---------|--------|
| ZenithId = 0 | Hotel excluded by `FilterByVenueId()` — not searched |
| isActive = False | Hotel excluded by `FilterByVenueId()` — not searched |
| No ratebycat rows | "Rooms With Mapping: 0" — rooms found but can't push |
| Wrong RatePlanCode | Zenith push will fail with error |
| Wrong InvTypeCode | Room type mismatch in Zenith |

---

## 19 Hotels Batch Activated (2026-02-23)

The following hotels were activated (isActive set from 0 to 1) in a batch operation:

| HotelId | Hotel Name | ZenithId |
|---------|------------|----------|
| 21024 | Mondrian South Beach | 5038 |
| 261038 | Eurostars Langford | 5036 |
| 24964 | Hyatt Regency Coral Gables | 5042 |
| 1010277 | Arlo Wynwood | 5035 |
| 885653 | Riviera Luxury Living | 5037 |
| 371764 | Urbanica The Meridian | 5040 |
| 338285 | Novotel Miami Brickell | 5039 |
| 1004953 | Freehand Miami | 5030 |
| 1107488 | Hotel AKA Brickell | 5049 |
| 1023316 | Selina Gold Dust | 5031 |
| 1055975 | Generator Miami | 5032 |
| 1088652 | Life House Little Havana | 5033 |
| 838901 | Ibis Styles | 5029 |
| 23413 | Gabriel South Beach | 5068 |
| 255124 | Crowne Plaza | 5069 |
| 1099556 | Hilton Aventura | 5071 |
| 21049 | SLS South Beach | 5073 |
| 21021 | Nautilus by Arlo | 5074 |
| 24998 | Residence Inn Aventura | 5075 |

> Backup: `BAK_Med_Hotels_19inactive_20260223`
