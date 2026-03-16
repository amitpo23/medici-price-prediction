# PUT Split Monitoring Runbook (Internal vs External)

## Goal
Run two separate PUT calculations every 6 hours, without mixing data sources:
1. `internal_only` (Azure SQL / internal sources)
2. `external_only` (external free sources)

Update a shared PUT table each run, including source provenance.

## What Was Implemented
- Added split enrichment profiles in analyzer:
  - `all` (default)
  - `internal_only`
  - `external_only`
- Added free-source connector + split execution script:
  - `DataAnalysisExpert/connect_free_sources_and_split_put.py`
- Added 6-hour scheduler script:
  - `DataAnalysisExpert/run_split_put_every_6h.py`
- Added rolling PUT table outputs:
  - `DataAnalysisExpert/put_split_table.csv`
  - `DataAnalysisExpert/put_split_table.md`

## Source Provenance in PUT Table
Each row in the PUT table contains:
- `internal_sources`:
  - SalesOffice.Details
  - SalesOffice.Orders
  - AI_Search_HotelData
  - SearchResultsSessionPollLog
  - RoomPriceUpdateLog
  - MED_Book / MED_CancelBook
- `external_sources_connected`:
  - dynamically populated from connected free external sources in that run

## Commands
### One-time split run
```powershell
$env:PYTHONPATH='.'
& "C:/Users/97250/Desktop/booking engine/medici-price-prediction/.venv/Scripts/python.exe" "DataAnalysisExpert/connect_free_sources_and_split_put.py"
```

### Start 6-hour continuous scheduler
```powershell
$env:PYTHONPATH='.'
& "C:/Users/97250/Desktop/booking engine/medici-price-prediction/.venv/Scripts/python.exe" "DataAnalysisExpert/run_split_put_every_6h.py"
```

## Artifacts Produced
- Per-run report JSON:
  - `DataAnalysisExpert/split_put_free_sources_YYYYMMDD_HHMMSS.json`
- Rolling table:
  - `DataAnalysisExpert/put_split_table.csv`
  - `DataAnalysisExpert/put_split_table.md`
- Scheduler log:
  - `DataAnalysisExpert/split_put_scheduler.log`

## Operational Notes
- If external sources are partially unavailable (e.g., no flights data), `external_only` still runs but will reflect lower coverage.
- Internal and external calculations are intentionally isolated in the model enrichment layer.
- Existing default behavior (`all`) remains unchanged for current API consumers.
