# Scan coverage gap — sales-order hotels

**Issue discovered 2026-04-23:**
`SalesOffice.BrowserScanResults` currently holds data for only **8 unique venues** in
the last 7 days:

```
5064, 5079, 5080, 5081, 5082, 5109, 5111, 5305
```

Meanwhile, `medici-hotels` has **40 active sales-order hotels** spanning venue IDs
5092–5141 and 5265–5279:

```
5092 5094 5097 5098 5100 5101 5102 5103 5104 5105 5106 5107 5108 5109 5110 5111
5113 5115 5116 5117 5119 5124 5130 5131 5132 5136 5138 5139 5140 5141
5265 5266 5267 5268 5274 5275 5276 5277 5278 5279
```

Overlap between scanned and sales-order: **2 venues** (5109, 5111) = **5% coverage.**

## Why this matters

`distribution-master` uses `BrowserScanResults.RawJson` as the ground-truth for
"is Knowaa visible in this hotel's Innstant results." Today it effectively has no
signal for 38/40 hotels we actually try to sell — so gap detection is a coin flip
for those rooms.

## Asks

1. **Add these 40 venue IDs to the scan rotation** (or increase scan breadth so every
   active sales-order hotel is scanned at least once per 24h).
2. If your scan runner already reads a config list — share where, we can PR the additions.
3. If coverage is throttled by cookie / session budget — let's discuss raising the
   per-scan hotel count (current ~8 → target 55+ to match the original Miami scope).

Happy to help identify the hotel slice from our side. Our SQL pulling the list is:

```sql
SELECT DISTINCT h.Innstant_ZenithId AS VenueId, h.InnstantId AS HotelId, h.Name
FROM [SalesOffice.Orders] o
JOIN Med_Hotels h ON h.HotelId = CAST(o.DestinationId AS INT)
WHERE o.IsActive=1 AND o.DestinationType='hotel' AND h.Innstant_ZenithId > 0
ORDER BY h.Innstant_ZenithId;
```

Thanks — this is the main blocker for gap analytics on the medici-hotels side.
