# Zenith Push Failure Analysis — 25 Hotels

**Date**: 2026-03-29
**Source**: SalesOffice.Log, ActionResultId=2 (Failed)

## Pattern
All 25 hotels have identical behavior:
- Push type: Availability (BookingLimit=1, Status=Open)
- All fail silently — Zenith returns failure with no error message
- Multiple rate plans and room types fail per hotel
- Retries every ~30 minutes, all fail

## Failing Hotels

| # | Venue | HotelId | Hotel | Fails | Notes |
|---|-------|---------|-------|-------|-------|
| 1 | 5064 | 32687 | Hotel Chelsea | 3 | |
| 2 | 5075 | 193899 | The Villa Casa Casuarina | 107 | |
| 3 | 5094 | 855865 | The Grayson Hotel | 26 | 1 success (Suite close) |
| 4 | 5113 | 66737 | Cavalier Hotel | 235 | |
| 5 | 5115 | 254198 | Hilton Cabana Miami Beach | 771 | Has 10 rates in DB |
| 6 | 5116 | 846428 | Kimpton Palomar South Beach | 95 | |
| 7 | 5119 | 854710 | citizenM Miami South Beach | 184 | Has 2 rates in DB |
| 8 | 5124 | 68833 | Grand Beach Hotel Miami | 114 | Has 3 rates in DB |
| 9 | 5130 | 67387 | Holiday Inn Express Miami | 110 | |
| 10 | 5131 | 286236 | Hotel Croydon | 12 | |
| 11 | 5132 | 277280 | Hotel Gaythering | 13 | |
| 12 | 5136 | 31226 | Kimpton Angler's Hotel | 189 | |
| 13 | 5138 | 851633 | THE LANDON BAY HARBOR | 40 | |
| 14 | 5139 | 851939 | SERENA Hotel Aventura | 212 | |
| 15 | 5140 | 301583 | The Gates Hotel South Beach | 3 | |
| 16 | 5265 | 414146 | Hotel Belleza | 2 | |
| 17 | 5266 | 6654 | Dorchester Hotel | 229 | |
| 18 | 5267 | 301645 | Gale South Beach | 190 | |
| 19 | 5268 | 19977 | Fontainebleau Miami Beach | 462 | Has 10 rates in DB |
| 20 | 5274 | 701659 | Generator Miami | 187 | Has 6 rates in DB |
| 21 | 5275 | 21842 | Miami Intl Airport Hotel | 91 | |
| 22 | 5276 | 6482 | InterContinental Miami | 342 | |
| 23 | 5277 | 87197 | The Catalina Hotel | 102 | |
| 24 | 5278 | 852725 | Gale Miami Hotel & Residences | 293 | Has 6 rates in DB |
| 25 | 5279 | 301640 | Hilton Garden Inn SB | 109 | Has 2 rates in DB |

**Total failures**: ~3,800+ push attempts

## Root Cause Hypothesis

These hotels are NOT set up properly in Noovy/Hotel.Tools. The availability push
(BookingLimit=1) requires the hotel to have:
1. Active venue in Noovy
2. Rooms configured with matching InvTypeCode
3. Rate plans configured with matching RatePlanCode
4. Pricing set for the dates being pushed

Hotels that WORK (like Pullman 5080, Breakwater 5110, Embassy 5081) have all 4.
These 25 hotels are missing one or more of these prerequisites.

## Required Action — Noovy Setup

For each hotel, in Noovy:
1. Verify the venue exists and is active
2. Check that rooms match the InvTypeCodes being pushed
3. Verify rate plans match the RatePlanCodes
4. Set pricing ($1000 fixed) for the push dates
5. After setup, the next push cycle should succeed
