# Zenith Product Gaps — 11 Hotels, 3,646 Failures (7 days)

**Date**: 2026-03-25
**Source**: Developer report — push failures from Medici prediction system
**Impact**: Rooms with correct prices in DB but NOT pushed to Zenith → customers don't see these rooms/prices

## Problem

`Med_Hotels_ratebycat` has InvTypeCode/RatePlanCode combinations that don't exist as products in Noovy/Zenith. Every push attempt returns Error 402: "Can not find product for availability update."

## Failures by Hotel

| # | Hotel | Venue | Failing ITC | RPC (RO) | RPC (BB) | Failures (7d) |
|---|-------|-------|-------------|----------|----------|---------------|
| 1 | Savoy Hotel | 5103 | DLX | 12071 | 13155 | 1,167 |
| 2 | Marseilles Hotel | 5096 | SPR, DLX | 12065 | - | 803 |
| 3 | Iberostar Berkeley Shore | 5092 | Stnd | 12061 | 13168 | 676 |
| 4 | Cadet Hotel | 5095 | SPR | 12064 | - | 369 |
| 5 | Breakwater South Beach | 5110 | APT | - | 12867 | 208 |
| 6 | The Grayson | 5094 | SPR | 12063 | - | 125 |
| 7 | Eurostars Langford | 5098 | EXEC | 12067 | 13159 | 100 |
| 8 | Hilton Miami Downtown | 5084 | DLX | 12048 | 13173 | 76 |
| 9 | Fairwind | 5089 | SPR, Suite | 12059 | - | 61 |
| 10 | SLS LUX Brickell | 5077 | SPR | 12035 | 13168 | 60 |
| 11 | Crystal Beach | 5100 | Stnd | 12069 | - | 1 |

## Fix Plan

| Hotel (Venue) | Missing Product | Board | Action |
|---------------|-----------------|-------|--------|
| Savoy (5103) | DLX (Deluxe) | RO + BB | Create Deluxe product |
| Marseilles (5096) | SPR (Superior) | RO | Create Superior product |
| Marseilles (5096) | DLX (Deluxe) | RO | Create Deluxe product |
| Iberostar (5092) | Stnd (Standard) | RO + BB | Check PMS code: "Stnd" vs "STD" |
| Cadet (5095) | SPR (Superior) | RO | Create Superior product |
| Breakwater (5110) | APT (Apartment) | BB | Create Apartment product |
| Grayson (5094) | SPR (Superior) | RO | Create Superior product |
| Eurostars (5098) | EXEC (Executive) | RO + BB | Create Executive product |
| Hilton Downtown (5084) | DLX (Deluxe) | RO + BB | Create Deluxe product |
| Fairwind (5089) | SPR (Superior) | RO | Create Superior product |
| Fairwind (5089) | Suite | RO | Check PMS code: "Suite" vs "SUT" |
| SLS LUX (5077) | SPR (Superior) | RO + BB | Create Superior product |
| Crystal Beach (5100) | Stnd (Standard) | RO | Check PMS code: "Stnd" vs "STD" |

## PMS Code Reference

Previous fixes (7 March): STD→Stnd, SUT→Suite for Pullman/SLS LUX/Savoy.

| Our System Sends | Noovy Might Have | Correct Code |
|------------------|------------------|--------------|
| Stnd | STD | Stnd |
| Suite | SUT | Suite |
| SPR | SUP | SPR |
| DLX | DLX | DLX |
| EXEC | EXEC | EXEC |
| APT | APT | APT |

## Status Tracking

| # | Hotel | Status | Notes |
|---|-------|--------|-------|
| 1 | Savoy (5103) | PENDING | |
| 2 | Marseilles (5096) | PENDING | |
| 3 | Iberostar (5092) | PENDING | |
| 4 | Cadet (5095) | PENDING | |
| 5 | Breakwater (5110) | PENDING | |
| 6 | Grayson (5094) | PENDING | |
| 7 | Eurostars (5098) | PENDING | |
| 8 | Hilton Downtown (5084) | PENDING | |
| 9 | Fairwind (5089) | PENDING | |
| 10 | SLS LUX (5077) | PENDING | |
| 11 | Crystal Beach (5100) | PENDING | |
