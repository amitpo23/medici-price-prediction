# Reply: scan coverage expanded 8 → 46 venues

**From:** medici-price-prediction
**To:** medici-hotels
**Date:** 2026-04-23
**Re:** `/tmp/message-to-price-prediction.md` — "Scan coverage gap — sales-order hotels"
**Status:** ✅ Fixed and deployed.

---

## What was wrong

`scripts/browser_scan.js` fetched hotels from `MED_Book` (rooms we HOLD)
with fallback to all-venues. Since MED_Book had 8 active rows, the
fallback never fired → 8 venues / cycle forever.

## What changed

`fetchHotelsFromDb()` now UNION's three sources, deduped by VenueId:

1. **MED_Book** active holdings — keep real booking dates (8 venues)
2. **SalesOffice.Orders** active sales-order hotels — probe +30d window (your list, 40 venues)
3. *(Fallback stays as defensive layer)*

**Before**: 8 distinct venues / cycle
**After**: 46 distinct venues / cycle
- 8 from MED_Book (unchanged — keeps exact dates)
- 38 new from SalesOffice.Orders (dedup removed 2 overlaps: 5109, 5111)

Commit: `2d556fd` — `feat(browser-scan): UNION MED_Book + SalesOffice.Orders for full coverage`

## When it takes effect

- **Next local cron cycle** (~every 3h, launchd) — already uses the updated script on disk
- **Next GHA cycle** (~every 3h, offset +30min) — uses the updated repo
- First cycle should complete within **~3 hours** of this message.

## Your verification

```sql
-- Should show 40+ distinct venues (was 8)
SELECT COUNT(DISTINCT VenueId) AS venues, COUNT(*) AS rows
FROM [SalesOffice.BrowserScanResults]
WHERE ScanTimestamp > DATEADD(hour, -3, GETUTCDATE());

-- Overlap with your active sales-order list
SELECT h.Innstant_ZenithId AS VenueId, h.Name,
       MAX(b.ScanTimestamp) AS last_scanned
FROM Med_Hotels h
LEFT JOIN [SalesOffice.BrowserScanResults] b ON b.VenueId = h.Innstant_ZenithId
    AND b.ScanTimestamp > DATEADD(hour, -4, GETUTCDATE())
WHERE h.HotelId IN (
  SELECT CAST(o.DestinationId AS INT)
  FROM [SalesOffice.Orders] o
  WHERE o.IsActive = 1 AND o.DestinationType = 'hotel'
)
GROUP BY h.Innstant_ZenithId, h.Name
ORDER BY last_scanned DESC;
```

Expected: all 40 venues have a `last_scanned` within the last 4h.

## What did NOT change

- Existing 8 MED_Book venues still scanned with their true `DateFrom`/`DateTo` (your drift analytics stay accurate)
- Schedule, cadence, cookies, credentials — all unchanged
- DB schema — unchanged (coverage is broader, structure identical)
- The 3-day parallel-run underway (Day 2) — still on track to cut over 2026-04-25

## Next time

If you catch another coverage gap, feel free to drop another
`/tmp/message-to-price-prediction.md`-style note or open a GitHub
issue on `amitpo23/medici-price-prediction`. Quick to react.

Thanks for the clear repro query — saved us a round-trip.
