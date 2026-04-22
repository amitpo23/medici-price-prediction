# Medici-Hotels → Cloud Migration Guide

**From:** medici-price-prediction (pilot repo)
**To:** medici-hotels (10 launchd agents)
**Date:** 2026-04-22
**Status:** Pilot running. Same pattern ready to copy.

This is two things in one:
1. **Read path** — which SQL tables to query so your existing agents keep working without reading files from git.
2. **Write path** — how to move your own scanners off the MacBook into GitHub Actions, the exact same way we just did.

---

## Part 1 — What to read from now on

Your Mac-side agents currently read scan data from 3 places:
- `scan-reports/*.json` pulled via git
- `shared-reports/*.md` pulled via raw.githubusercontent.com
- `BrowserScanResults` direct SQL queries (some older code had broken column names)

**All three are now superseded by 3 shared SQL tables** on the same server you already use (`medici-sql-server.database.windows.net` / `medici-db`, login as before). No new credentials. No new endpoints.

### Table 1 — `[SalesOffice.BrowserScanResults]` *(existing, enriched)*

Same table as before, but **2 changes**:

| Change | What it means |
|--------|----------------|
| New column `CreatedBy NVARCHAR(100)` | `'local'` (Mac plist), `'BrowserScan@GHA-parallel'` (cloud parallel-run), `'BrowserScan@GHA'` (cloud post-cutover on 2026-04-25) |
| `RawJson` column now populated | Per-hotel JSON with full `offers` array (`{category, board, price, provider}`) |

**Update your queries** that used the old column names:

| Your code used (broken) | Use instead |
|---|---|
| `b.Category` | `b.CheapestCategory` (summary) or parse `RawJson` (detail) |
| `b.Board` | `b.CheapestBoard` or parse `RawJson` |
| `b.PricePerNight` | `b.CheapestOverall` or parse `RawJson[].price` |
| `b.ScanDate` | `b.ScanTimestamp` |

**During parallel run (through 2026-04-25):** the table has ~2× rows (both sources writing). If your consumer isn't aggregating and wants a single authoritative view, add:
```sql
WHERE CreatedBy NOT LIKE '%parallel%'
```

Post-cutover, drop that filter — all new rows are `'BrowserScan@GHA'`.

**Affected consumers in your repo** (we grepped):
- `skills/salesoffice-scanning/browser_reconcile.py` — uses broken column names, **needs update**
- `skills/salesoffice-scanning/compare_api_vs_browser.py` — uses broken column names, **needs update** (see Table 2 below for replacement path)
- `skills/salesoffice-scanning/scan_report.py`
- `skills/salesoffice-scanning/recurring_monitor.py`
- `skills/scan-reports-reader/sync.py` — reads files, can switch to SQL
- `skills/distribution-master/modules/scan_reports_reader.py` — same
- `skills/hotel-completion/analysis/multi_source_collector.py`
- `skills/commander/modules/report_readers.py`

### Table 2 — `[SalesOffice.PriceDriftReport]` *(NEW)*

**Replaces:** `scripts/compare_api_vs_browser.py` (ours) and any consumer of `scan-reports/compare_*.json`.

Daily at 02:00 UTC, cloud writes per-row drift detection between browser prices (what Innstant shows Knowaa LIVE) and API prices (what's in `SalesOffice.Details`).

**Schema:**
```
Id              BIGINT PK
RunTimestamp    DATETIME2
VenueId         INT
HotelId         INT
HotelName       NVARCHAR(200)
Category        NVARCHAR(50)    -- 'standard', 'deluxe', 'suite', 'other'
Board           NVARCHAR(50)    -- 'RO', 'BB', 'HB', 'FB', 'AI'
BrowserPrice    FLOAT           -- from BrowserScanResults.RawJson
ApiPrice        FLOAT           -- MIN from SalesOffice.Details
DiffUsd         FLOAT
DiffPct         FLOAT
BrowserProvider NVARCHAR(100)
ApiProvider     NVARCHAR(100)   -- always 'API'
Status          NVARCHAR(20)    -- MATCH | DRIFT | MISSING_API | MISSING_BROWSER
CreatedBy       NVARCHAR(100)   -- 'price-drift@GHA' (cloud) or 'local'
```

**Example queries:**
```sql
-- Where are we stale? (price drifted > 5% in last 24h)
SELECT VenueId, HotelName, Category, Board, BrowserPrice, ApiPrice, DiffPct
FROM [SalesOffice.PriceDriftReport]
WHERE Status = 'DRIFT' AND RunTimestamp > DATEADD(hour, -24, GETUTCDATE())
ORDER BY ABS(DiffPct) DESC;

-- Which venues are scan-blind? (API has data, browser doesn't see them)
SELECT DISTINCT VenueId, HotelName
FROM [SalesOffice.PriceDriftReport]
WHERE Status = 'MISSING_BROWSER' AND RunTimestamp > DATEADD(day, -1, GETUTCDATE());
```

### Table 3 — `[SalesOffice.KnowaaPerformanceDaily]` *(NEW)*

**Replaces:** `shared-reports/YYYY-MM-DD_knowaa_searchlog_report.{md,json}` — the Knowaa competitive scan output.

Daily at 02:00 UTC, cloud writes **one row per (ReportDate, HotelId)** summarizing Knowaa's performance in `SearchResultsSessionPollLog`. No more markdown parsing.

**Schema:**
```
Id                      BIGINT PK
ReportDate              DATE
WindowHours             INT             -- 24 or 48
HotelId                 INT             -- = Innstant_ZenithId (venue ID)
HotelName               NVARCHAR(200)
RoomCategory            NVARCHAR(50)    -- NULL at hotel-level (current granularity)
RoomBoard               NVARCHAR(50)    -- NULL at hotel-level
Sessions                INT
KnowaaSessions          INT             -- in how many sessions did we appear
KnowaaCoveragePct       FLOAT           -- = KnowaaSessions / Sessions
KnowaaNumber1Sessions   INT             -- in how many did we come in #1
KnowaaNumber1Pct        FLOAT           -- = KnowaaNumber1Sessions / KnowaaSessions
AvgGapUsd               FLOAT           -- avg $ above the cheapest competitor
CreatedBy               NVARCHAR(100)   -- 'knowaa-db@GHA'
InsertedAt              DATETIME2
```

**Example queries:**
```sql
-- Today's summary — hotels where Knowaa coverage dropped below 50%
SELECT HotelId, HotelName, Sessions, KnowaaCoveragePct, KnowaaNumber1Pct
FROM [SalesOffice.KnowaaPerformanceDaily]
WHERE ReportDate = CAST(GETUTCDATE() AS DATE)
  AND KnowaaCoveragePct < 50
ORDER BY Sessions DESC;

-- Trend — has Knowaa's #1 rate moved in the last 7 days?
SELECT ReportDate,
       SUM(KnowaaNumber1Sessions) * 100.0 / NULLIF(SUM(KnowaaSessions), 0) AS number_one_pct
FROM [SalesOffice.KnowaaPerformanceDaily]
WHERE ReportDate > DATEADD(day, -7, GETUTCDATE())
GROUP BY ReportDate ORDER BY ReportDate;
```

---

## Part 2 — How to migrate your own agents

Your 9 launchd agents (`com.medici.cancel-verifier`, `roomseller`, `mappingfixer`, `safety`, etc.) can follow the exact pattern we used for `browser-scan`. It's simple and zero-risk.

### The pattern (4 steps per agent, ~75 min each)

**Step 1 — Code changes (1 or 2 small commits)**
- Add a `CreatedBy NVARCHAR(100)` column to any table the agent writes to.
- The INSERT statement picks `CREATED_BY` env var, fallback `'local'`.
- Add a SIGTERM handler that closes open browsers/DB pools (critical for Playwright-based agents like `distribution-master` Noovy UI automation).
- Confirm the script doesn't require a `.env` file — use `if env_path.exists()` guard; rely on `os.environ` from GHA secrets.

**Step 2 — GHA workflow**

```yaml
name: <agent-name>
on:
  schedule:
    - cron: '<offset-from-local>'   # 30 min after local cadence to avoid collisions
  workflow_dispatch:

concurrency:
  group: <agent-name>
  cancel-in-progress: true

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: <based-on-job>
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5       # or setup-node
        with: {python-version: '3.12'}
      - name: Install ODBC 18
        run: |
          # ASCII-armored key — don't use --dearmor, it breaks on GHA without tty
          curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
            sudo tee /usr/share/keyrings/microsoft.asc > /dev/null
          echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.asc] \
            https://packages.microsoft.com/ubuntu/22.04/prod jammy main" | \
            sudo tee /etc/apt/sources.list.d/microsoft-prod.list
          sudo apt-get update
          ACCEPT_EULA=Y sudo apt-get install -y msodbcsql18
          pip install pyodbc
      - name: Run
        env:
          SOURCE_DB_SERVER: ${{ secrets.SOURCE_DB_SERVER }}
          SOURCE_DB_NAME:   ${{ secrets.SOURCE_DB_NAME }}
          SOURCE_DB_USER:   ${{ secrets.SOURCE_DB_USER }}
          SOURCE_DB_PASS:   ${{ secrets.SOURCE_DB_PASS }}
          CREATED_BY:       <agent>@GHA-parallel
        run: python3 skills/<agent>/<main>.py --flags
```

**Step 3 — GHA secrets**
`gh secret set SOURCE_DB_SERVER -b "medici-sql-server.database.windows.net"` etc. — 4 DB secrets + any agent-specific (Innstant creds, telegram token, etc.).

**SQL firewall already allows Azure services** — no firewall change needed.

**Step 4 — Parallel run → cutover**
- Let cloud + local run together for 3 days with `CreatedBy='<agent>@GHA-parallel'`.
- Build a simple parity check (we have `scripts/parity_check.py` as template).
- After 3 green days: `launchctl unload com.medici.<agent>.plist` and flip `CREATED_BY` to `<agent>@GHA`. Keep the plist on disk 90 days as rollback.

### Recommended migration order (easiest → hardest)

| # | Agent | Why | Expected effort |
|---|-------|-----|------------------|
| 1 | `cancel-verifier-daily` | Once a day, DB read + email, no external deps | 60 min |
| 2 | `reservation-health` | Once a day, DB read-only | 45 min |
| 3 | `mappingfixer` | 2x/day, DB-heavy. No browser | 90 min |
| 4 | `roomseller` | Every hour, DB + Zenith API. No browser | 90 min |
| 5 | `safety` | Every 20 min — frequent but lightweight | 75 min |
| 6 | `cancel-verifier` | Every 6h, moderate complexity | 75 min |
| 7 | `reservation-callback` | Every 5 min — needs care, highest frequency | 120 min |
| 8 | `distribution-master` | Playwright against Noovy UI — hardest | 180 min |
| 9 | `telegram-gateway` | Web server, not a scheduled job — keep local or move to App Service | separate evaluation |

Total rough estimate: **~15 hours** of engineering + parallel-run observation, spread over 1-2 weeks.

### What DOESN'T fit this pattern

- `telegram-gateway` — it's a persistent HTTP server, not a cron job. GHA schedules aren't right for it. Keep local or move to Azure App Service as a WebJob.
- Anything that needs persistent file state between runs (e.g. crawler cache). GHA runners are ephemeral — move state to blob storage or DB column first.

---

## Part 3 — Verification & contact

**Verify what you're reading is fresh:**
```sql
SELECT 'BrowserScanResults' AS t, MAX(ScanTimestamp) AS last_write, COUNT(*) AS rows_today
FROM [SalesOffice.BrowserScanResults] WHERE ScanTimestamp > DATEADD(day, -1, GETUTCDATE())
UNION ALL
SELECT 'PriceDriftReport', MAX(RunTimestamp), COUNT(*)
FROM [SalesOffice.PriceDriftReport] WHERE RunTimestamp > DATEADD(day, -1, GETUTCDATE())
UNION ALL
SELECT 'KnowaaPerformanceDaily', MAX(InsertedAt), COUNT(*)
FROM [SalesOffice.KnowaaPerformanceDaily] WHERE ReportDate >= DATEADD(day, -1, GETUTCDATE());
```

All three should show rows < 25h old after 2026-04-23 03:00 UTC (first nightly cycle of the daily-analytics workflow).

**Rollback insurance on our side:** local launchd plists stay on disk for 90 days post-cutover. `gh workflow disable <name>` restores the previous state in one command.

**Questions?** The working code lives at:
- `amitpo23/medici-price-prediction/.github/workflows/browser-scan.yml`
- `amitpo23/medici-price-prediction/.github/workflows/daily-analytics.yml`
- `amitpo23/medici-price-prediction/scripts/price_drift_check.py`
- `amitpo23/medici-price-prediction/scripts/knowaa_db_report.py`
- `amitpo23/medici-price-prediction/scripts/parity_check.py`

Copy-paste friendly. No new Azure infra required — GitHub Actions + Azure SQL is all you need.
