# SalesOffice Price Drop Intelligence Skill

## Purpose
Analyze `SalesOfficeLogService` logs and detect price drops across scans.

## What this skill gives you
- Total number of price changes
- Count of downward price changes only
- All places where price decreased (hotel/category/board/order/detail)
- Drop magnitude statistics (avg/median/max)
- How many downward changes happen per scan window
- Lowest observed price in the selected period
- Short-term probability estimate for a drop in the next scan window

## Required data source
Primary table: `[SalesOffice.Log]`

Optional enrichments:
- `[SalesOffice.Details]` for hotel/category/board
- `[SalesOffice.Orders]` for order context

## Known action codes (from current system docs)
- `ActionId = 3` => Detail Updated
- `ActionId = 6` => Zenith Push - Update Rate

The log message pattern usually contains:
`DbRoomPrice: X -> API RoomPrice: Y; DbRoomCode: ...`

## How to run
### Option A: SQL first + Python report
1. Run `queries/01_extract_price_changes.sql` and export results to CSV.
2. Run:
```powershell
python analyzer.py --input-csv price_changes.csv --scan-minutes 10 --out report
```

### Option B: Direct DB connection
```powershell
python analyzer.py --connection-string "Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;TrustServerCertificate=yes;Uid=...;Pwd=..." --scan-minutes 10 --out report
```

## Output files
- `report/price_drop_events.csv`
- `report/price_drop_by_scan.csv`
- `report/price_drop_by_hotel.csv`
- `report/summary.json`

## Suggested usage in another system
- Schedule every 10 minutes after SalesOffice scan cycle
- Persist `summary.json` snapshots for trend tracking
- Trigger alert if drop rate spikes or if new minimum price is reached

