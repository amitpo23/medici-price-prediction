# Browser-Scan Migration Notice → medici-hotels consumers

**Sender:** medici-price-prediction
**Date:** 2026-04-22
**Phase:** Day 1 of 3-day parallel-run (cutover ETA 2026-04-25)
**Impact:** Low (additive schema, no breaking changes) — action required only if you filter BrowserScanResults by source.

---

## TL;DR

`browser-scan` is migrating from the CEO's MacBook (launchd, local) to GitHub Actions (cloud). During the next 3 days both sources write in parallel, then we cut over to cloud-only.

- **Same table, same server, same schema** — no connection changes.
- **New column** on `[SalesOffice.BrowserScanResults]`: `CreatedBy NVARCHAR(100)` (default `'local'`).
- **Scan reports** (markdown/JSON) from the cloud side no longer land in git — they're in GHA artifacts (30d retention).

---

## Where data is written

### `[SalesOffice.BrowserScanResults]` (Azure SQL `medici-sql-server.database.windows.net` / `medici-db`)

| Phase | Cadence | `CreatedBy` value |
|-------|---------|-------------------|
| **Now (Day 0–3, parallel)** | Local: every 3h on the hour. GHA: every 3h offset +30min. | `'local'` or `'BrowserScan@GHA-parallel'` |
| **After cutover (~2026-04-25)** | GHA only, every 3h. Local plist unloaded. | `'BrowserScan@GHA'` |
| **Historical rows (pre-2026-04-22)** | Before migration | All backfilled to `'local'` |

Schema change (applied 2026-04-22 ~10:45 UTC):
```sql
ALTER TABLE [SalesOffice.BrowserScanResults]
ADD CreatedBy NVARCHAR(100) NULL
CONSTRAINT DF_BrowserScanResults_CreatedBy DEFAULT 'local';

UPDATE [SalesOffice.BrowserScanResults]
SET CreatedBy = 'local' WHERE CreatedBy IS NULL;  -- 6,174 rows
```

### Where scan **reports** (JSON + Markdown) live

| Source | Location | Retention |
|--------|----------|-----------|
| Local plist | `scan-reports/*.json`, `shared-reports/*.md` (git-pushed to `main`) | Permanent |
| GHA run | `gh run download <run-id>` → workflow artifacts `scan-reports-<run_id>` | 30 days |

⚠ If your agent reads scan reports from the GitHub raw URL (`https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/...`), you'll still see reports from the local plist until cutover. After cutover, only the artifact channel will produce fresh reports — let me know if you need them pushed back to git post-cutover.

---

## What you may need to change

### If you read `BrowserScanResults` for reconciliation

**During parallel (Days 1–3):** the table has ~2× rows (both sources). To get a single authoritative snapshot:

```sql
SELECT ...
FROM [SalesOffice.BrowserScanResults]
WHERE CreatedBy NOT LIKE '%parallel%'   -- excludes GHA-parallel rows
  AND DateCreated > DATEADD(day, -1, GETDATE())
```

**After cutover:** drop the filter — all rows will be `'BrowserScan@GHA'` or historical `'local'`.

Known consumers I grepped (all manual, not scheduled — low parallel-run risk):
- `medici-hotels/skills/salesoffice-scanning/browser_reconcile.py`
- `medici-hotels/skills/salesoffice-scanning/compare_api_vs_browser.py`
- `medici-hotels/scripts/browser_to_db.py`

If any of these runs automatically / on schedule, add the `CreatedBy NOT LIKE '%parallel%'` filter before Day 1.

### If you watch git commits from `github-actions[bot]`

The old workflow auto-pushed `chore: automated browser-price-check scan` commits (10 per day). **That stopped as of 2026-04-22.** The new workflow uploads artifacts instead. Local plist still commits, but only every 3h.

---

## Verification you can run

```sh
# Connect to Azure SQL, run:
SELECT CreatedBy, COUNT(*) AS rows, COUNT(DISTINCT VenueId) AS venues
FROM [SalesOffice.BrowserScanResults]
WHERE DateCreated > DATEADD(hour, -6, GETDATE())
GROUP BY CreatedBy;
```

Expected during parallel phase: two rows in output, counts within ±10%.

Or from medici-price-prediction repo:
```sh
python3 scripts/parity_check.py --window-hours 4
```

---

## Contact / escalation

- Migration owner: CEO / Claude session
- Plan: `/Users/mymac/.claude/plans/sparkling-purring-wind.md`
- Rollback: `gh workflow disable browser-scan.yml` (one command, reversible)

No action required if your agent only aggregates by venue (the `CreatedBy` column is additive, queries ignoring it keep working — you just get 2× rows temporarily).
