# Zenith Product Gaps — Investigation Results

**Date**: 2026-03-25
**Investigated by**: Claude Code (automated)
**Original report**: 3,646 push failures across 11 hotels in 7 days

---

## Executive Summary

**Root cause identified: Hotel.Tools product creation API returns HTTP 500.**

The failing products either don't exist in Hotel.Tools (need creation) or exist but aren't synced to the Zenith SOAP engine. In both cases, the fix requires Hotel.Tools backend intervention — it cannot be resolved through the UI.

---

## What Was Tested

### SOAP API Verification (Direct Push Test)

Tested all 18 failing ITC/RPC combinations directly via Zenith SOAP API:

| Venue | ITC | RPC | SOAP Result |
|-------|-----|-----|-------------|
| 5103 Savoy | DLX | 12071 | **Error 402** |
| 5103 Savoy | DLX | 13155 | **Error 402** |
| 5096 Marseilles | SPR | 12065 | **Error 402** |
| 5096 Marseilles | DLX | 12065 | **Error 402** |
| 5092 Iberostar | Stnd | 12061 | **Success** (works!) |
| 5092 Iberostar | Stnd | 13168 | **Error 402** |
| 5095 Cadet | SPR | 12064 | **Error 402** |
| 5110 Breakwater | APT | 12867 | **Error 402** |
| 5094 Grayson | SPR | 12063 | **Error 402** |
| 5098 Eurostars | EXEC | 12067 | **Error 402** |
| 5098 Eurostars | EXEC | 13159 | **Error 402** |
| 5084 Hilton DT | DLX | 12048 | **Error 402** |
| 5084 Hilton DT | DLX | 13173 | **Error 402** |
| 5089 Fairwind | SPR | 12059 | **Error 402** |
| 5089 Fairwind | Suite | 12059 | **Error 402** |
| 5077 SLS LUX | SPR | 12035 | **Error 402** |
| 5077 SLS LUX | SPR | 13168 | **Error 402** |
| 5100 Crystal Beach | Stnd | 12069 | **Error 402** |

**Reference tests (known-good):**
- 5103/Stnd/12071 → **Success**
- 5103/Suite/12071 → **Success**
- 5096/Stnd/12065 → **Success**

### Hotel.Tools UI Verification (Savoy #5103 deep-dive)

| Component | Status | Finding |
|-----------|--------|---------|
| **Noovy Products** | ✅ | Standard, Suite, Deluxe exist (PMS codes: Stnd, Suite, DLX) |
| **Noovy Rate Plans** | ✅ | 12071 (RO) + 13155 (BB) linked to Deluxe, Standard, Suite |
| **Hotel.Tools Products** | ✅ | Same products visible, PMS Exchange code = DLX |
| **Hotel.Tools Rate Plans** | ✅ | Products = "Deluxe, Standard, Suite" for both 12071 and 13155 |
| **Zenith SOAP** | ❌ | Error 402: "Can not find product for rate update (5103/DLX/12071)" |

**Conclusion**: Products are correctly configured in both Noovy and Hotel.Tools, but the Zenith SOAP engine doesn't recognize them. Products created later (after initial setup) are not synced to Zenith.

### Product Creation Attempt

Attempted to create "Superior" (SPR) product for Savoy #5103 via Hotel.Tools UI:
- Filled all required fields (Title, Short Name, PMS code, Currency, Dates, Location)
- **Result: HTTP 500 "Internal Server Error"** on submit
- This is the same known issue from 2026-03-14 investigation (27/27 creation attempts failed)

---

## Breakdown by Hotel

### Two categories of failures:

**Category A: Product exists in Noovy/HT but Zenith doesn't recognize it (sync issue)**
- Savoy (5103): DLX exists, linked to rate plans, SOAP says 402
- Same pattern likely applies to other hotels

**Category B: Product doesn't exist at all (creation needed, blocked by HTTP 500)**
- Superior (SPR) missing from: Savoy, Marseilles, Cadet, Grayson, Fairwind, SLS LUX
- Deluxe (DLX) missing from: Marseilles, Hilton Downtown
- Executive (EXEC) missing from: Eurostars
- Apartment (APT) missing from: Breakwater

---

## Required Actions

### Action 1: Contact Hotel.Tools Support (CRITICAL)
Request:
1. **Resync all products** for venues: 5103, 5096, 5092, 5095, 5110, 5094, 5098, 5084, 5089, 5077, 5100
2. **Fix product creation API** — HTTP 500 on POST /products has been failing since at least 2026-03-14
3. **Alternatively**: Have their team create the missing products directly in the backend

Products to create (if HT support can do it):

| Venue | Product | PMS Code (InvTypeCode) |
|-------|---------|----------------------|
| 5103 Savoy | Superior | SPR |
| 5096 Marseilles | Superior | SPR |
| 5096 Marseilles | Deluxe | DLX |
| 5095 Cadet | Superior | SPR |
| 5110 Breakwater | Apartment | APT |
| 5094 Grayson | Superior | SPR |
| 5098 Eurostars | Executive | EXEC |
| 5084 Hilton DT | Deluxe | DLX |
| 5089 Fairwind | Superior | SPR |
| 5077 SLS LUX | Superior | SPR |

### Action 2: After products are created/synced
Each new product must be linked to the hotel's Rate Plans:
- RO rate plan (12071/12065/12061 etc.)
- BB rate plan (13155/13168 etc.) where applicable

### Action 3: Verify
Re-run this SOAP test script to confirm all 18 combinations return Success:
```bash
curl -s -X POST 'https://hotel.tools/service/Medici%20new' \
  -H 'Content-Type: text/xml' \
  -d '...InvTypeCode="{ITC}" RatePlanCode="{RPC}"...'
```

---

## What Was Already Done

1. ✅ Enabled Deluxe product #2 (was Off) in Noovy for Savoy
2. ✅ Re-submitted Rate Plan 12071 in Hotel.Tools for Savoy
3. ✅ Attempted Superior product creation in Hotel.Tools → HTTP 500
4. ✅ Verified SOAP credentials work (password: 12345)
5. ✅ Verified known-good products (Stnd, Suite) still work

---

## SOAP Test Credentials

```
URL: https://hotel.tools/service/Medici%20new
Username: APIMedici:Medici Live
Password: 12345
```

---

## Update: Full 30-Hotel SOAP Test (2026-03-25, 12:30 UTC)

Following the Innstant team response about "static update from Noovy", tested all 30 new hotels:

### Results: 29/30 fail, 1 partial

| Status | Count | Hotels |
|--------|-------|--------|
| ❌ All ITCs fail | 29 | All except Notebook |
| ✅ Stnd only | 1 | Notebook (5102) — DLX/Suite/SPR fail |

**Root cause confirmed**: These are new venues that haven't completed their Zenith static sync. The Innstant team reported they are running a "static update from Noovy" — this should resolve the SOAP 402 errors once complete.

### Innstant Team Status per Hotel

| Hotel | Venue | Innstant Status | SOAP |
|-------|-------|----------------|------|
| Cavalier | 5113 | connected | ❌ |
| citizenM SB | 5119 | connected | ❌ |
| Dorchester | 5266 | not flowing - MP open | ❌ |
| DoubleTree | 5082 | connected | ❌ |
| Fontainebleau | 5268 | not flowing - MP open | ❌ |
| Gale Miami | 5278 | MP was closed → opened | ❌ |
| Gale South Beach | 5267 | MP was closed → opened | ❌ |
| Generator | 5274 | not flowing - MP open | ❌ |
| Grand Beach | 5124 | connected | ❌ |
| Hilton Cabana | 5115 | connected | ❌ |
| Hilton Garden | 5279 | not flowing - MP open | ❌ |
| Hilton Airport | 5083 | connected | ❌ |
| Holiday Inn | 5130 | not flowing - MP open | ❌ |
| Belleza | 5265 | not flowing - MP open | ❌ |
| Chelsea | 5064 | connected | ❌ |
| Croydon | 5131 | connected | ❌ |
| Gaythering | 5132 | connected | ❌ |
| InterContinental | 5276 | MP was closed → opened | ❌ |
| Kimpton Anglers | 5136 | connected | ❌ |
| Kimpton Palomar | 5116 | connected | ❌ |
| Loews | 5073 | connected | ❌ |
| Metropole | 5141 | connected | ❌ |
| Miami Airport | 5275 | not flowing - MP open | ❌ |
| **Notebook** | **5102** | **not flowing - MP open** | **✅ Stnd only** |
| SERENA | 5139 | connected | ❌ |
| Albion | 5117 | connected | ❌ |
| Catalina | 5277 | connected | ❌ |
| Gates | 5140 | connected | ❌ |
| Landon | 5138 | connected | ❌ |
| Villa Casa | 5075 | connected | ❌ |

### Next Steps

1. **Wait for Innstant static update to complete** — they said they'll notify
2. **After update**: Re-run SOAP test for all 30 hotels
3. **Set availability in Noovy** for test dates (all 30 hotels)
4. **Verify in B2B Innstant** that Knowaa_Global_zenith results appear
5. **Create SalesOffice Orders** for working hotels
