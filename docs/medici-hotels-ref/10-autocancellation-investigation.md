# 10 - AutoCancellation WebJob Investigation / חקירת WebJob ביטולים אוטומטיים

## Date: 2026-02-24
## Version: 1.3 (Fix Applied)
## Status: RESOLVED ✅ — Option A executed on 2026-02-24

---

## Trigger

Email received from **Innstant Queue** (`support@travelcustomerservice.com`) about **Failed Cancellation**:

| Field | Value |
|-------|-------|
| Queue Item | #220841 |
| BookingID | **3597176** |
| Hotel | Sea Tower by Isrotel Design |
| Address | Tel Aviv 78 Hayarkon St, Tel Aviv |
| Mishor Hotel ID | 21106 |
| Provider | **RateHawk_v3 emerging travel (ID: 55361)** |
| Room | Standard Double room (full double bed) |
| Board | RO |
| Guests | Rocky BARTON |
| Dates | Dec 30, 2025 → Dec 31, 2025 |
| Status | Confirmed |
| Error | "Could not cancel the booking" |

---

## WebJob Identification

### Location & Configuration

| Property | Value |
|----------|-------|
| **Azure App Service** | `medici-backend` (East US 2) |
| **WebJob Name** | `AutoCancellation` |
| **Type** | Continuous (NOT triggered, NOT CRON) |
| **Executable** | `AutoCancellation.exe` |
| **Singleton** | `true` |
| **Uses SDK** | `false` |
| **Status** | Running ✅ |
| **Source Project** | `MediciAutoCancellation/` (in solution) |
| **Log URL** | `https://medici-backend.scm.azurewebsites.net/vfs/data/jobs/continuous/AutoCancellation/job_log.txt` |
| **API URL** | `https://medici-backend.scm.azurewebsites.net/api/continuouswebjobs/AutoCancellation` |
| **Kudu Dashboard** | `https://medici-backend.scm.azurewebsites.net/azurejobs/#/jobs/continuous/AutoCancellation` |

### Database (DIFFERENT from main Azure SQL!)

| Property | Value |
|----------|-------|
| **Server** | `194.113.211.244` |
| **Database** | `medici+++` |
| **User** | `sa` |
| **Password** | `CyPb0755med444` |
| **TrustServerCertificate** | True |

**⚠️ CORRECTION (v1.3):** Despite what `appsettings.json` in the source code says (`194.113.211.244/medici+++`), the **deployed** WebJob reads `appsettings.json` from `site/wwwroot/` of the App Service, which points to **Azure SQL** (`medici-sql-server.database.windows.net/medici-db`). The source `appsettings.json` is NOT deployed with the WebJob. The actual table is `MED_Book` (not `MedBooks` — EF maps `DbSet<MedBook> MedBooks` → `ToTable("MED_Book")`).

### Notification Channels

| Channel | Config |
|---------|--------|
| **Slack** | `hooks.slack.com/services/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` |
| **Email (SendGrid)** | From: `mediciprovider@gmail.com` / To: `zvi.g@medicihotels.com` |

---

## Code Flow

### Entry Point: `MediciAutoCancellation/Program.cs`

```
Program.Main()
  → Load appsettings.json
  → Set SendGrid keys
  → MainLogic.Process()
```

### Main Logic: `MediciAutoCancellation/MainLogic.cs` (81 lines)

```
Process()
  │
  ├── Repository.Instance.GetBookIdsToCancel()
  │     → BaseEF.GetBookIdsToCancel()
  │     → SQL: SELECT PreBookId FROM MedBooks 
  │            WHERE IsActive = 1 
  │              AND CancellationTo <= DATEADD(DAY, 2, GETDATE())
  │
  ├── If no results → log "Nothing to process" → END
  │
  ├── For each preBookId:
  │     │
  │     ├── CancelBooking_v2(preBookId, forceCancel=false)
  │     │     ├── Find active booking in MedBooks
  │     │     ├── Switch on Source:
  │     │     │     ├── Source=1 → ApiInnstant.BookCancel()
  │     │     │     │     ├── If "done" → InsertCancelBook() → Push availability to Zenith → Add to Queue
  │     │     │     │     └── If failed → MED_InsertCancelBookError()
  │     │     │     └── Source=2 → ApiGoGlobal.BookCancel()
  │     │     │           ├── If "done" → InsertCancelBook()
  │     │     │           └── If failed → MED_InsertCancelBookError()
  │     │     └── Return OpResult[]
  │     │
  │     ├── Check results for error strings:
  │     │     • "Could not cancel the booking"
  │     │     • "cannot cancel booking"
  │     │     • "Permission to booking force cancellation was denied"
  │     │
  │     └── If cancellation failed:
  │           ├── Log to auto_cancel.log
  │           └── Post to Slack
  │
  └── If ANY manual cancels needed:
        └── Send single email via SendGrid
            Subject: "Please cancel manually this rooms"
            Body: accumulated text of all failed preBookIds
```

### Key Database Table: `MedBooks`

Relevant columns:
- `PreBookId` (int) — Primary key for cancellation
- `ContentBookingId` (string) — Innstant/GoGlobal booking ID
- `IsActive` (bool) — Active booking flag
- `CancellationTo` (DateTime) — Free cancellation deadline
- `Source` (int) — 1=Innstant, 2=GoGlobal
- `OpportunityId` (int) — Link to SalesOffice opportunity

---

## Current Issue: Infinite Retry Loop

### Problem Description

~30+ PreBookIds keep failing on every run and are **never removed from the queue** because:

1. `GetBookIdsToCancel()` selects all `IsActive=true AND CancellationTo <= Now()+2days`
2. `CancelBooking_v2()` calls Innstant API → gets "cannot cancel booking on Innstant"
3. Error is logged to `MedCancelBookErrors` table
4. **But `IsActive` stays `true`** — booking is NOT deactivated on failure
5. Next run → same PreBookIds are selected again → same failures → infinite loop

### Observed Run History (from job_log.txt)

| Run Date | Instance | PreBookIds Attempted | Successes | Failures |
|----------|----------|---------------------|-----------|----------|
| 2026-02-17 09:14 | `3d6c1a` | ~30+ | 0 | ALL |
| 2026-02-19 08:03 | `3d6c1a` | ~30+ (same) | 0 | ALL |
| 2026-02-23 11:25 | `f9c9ae` | ~30+ (same) | 0 | ALL |

### Failing PreBookIds (all identical across runs)

```
9080, 9237, 9238, 9242, 9370, 9371, 9372, 9375, 9377, 9386,
9421, 9422, 9426, 9434, 9436, 9437, 9438, 9439, 9442, 9445,
9446, 9450, 9452, 9479, 9480, 9494, 9496, 9500, 9552, 9553,
9555, 9556, 9559 ...
(log truncated — "Reached maximum allowed output lines for this run")
```

### Error Pattern (identical for every PreBookId)

```
Find Booking: Success
ApiInnstant BookCancel: Error: cannot cancel booking on Innstant
MED_InsertCancelBookError: Success
PrebookId XXXX have to be canceled manually because of reason: 'Could not cancel the booking'
```

### Why They Can't Be Cancelled

These are old bookings where the **provider (RateHawk/Innstant) no longer allows API cancellation** — either the booking dates have passed, or the cancellation window has closed. The Innstant API correctly rejects the cancellation request.

---

## Timing Behavior

The WebJob is **Continuous** but the code runs once (no loop). It:
1. Starts when the App Service starts/restarts
2. Processes all pending cancellations
3. Finishes and stays "alive" (Azure reports "WebJob is still running" every ~12h)
4. Runs again only on next App Service restart

There is **no `settings.job`** file — only `job_log.txt`, `singleton.job.lock`, and `status_f9c9ae`.

---

## Proposed Solutions (NOT YET IMPLEMENTED)

### Option A: One-time SQL Cleanup (No Deploy)

```sql
-- Preview:
SELECT PreBookId, ContentBookingId, CancellationTo, StartDate
FROM MedBooks 
WHERE IsActive = 1 AND CancellationTo <= DATEADD(DAY, 2, GETDATE())
ORDER BY CancellationTo;

-- Execute:
UPDATE MedBooks 
SET IsActive = 0 
WHERE IsActive = 1 
  AND CancellationTo <= DATEADD(DAY, 2, GETDATE())
  AND CancellationTo < DATEADD(MONTH, -1, GETDATE());
```

### Option B: Query Filter — Skip entries older than 1 month (Deploy required)

In `BaseEF.GetBookIdsToCancel()`:
```csharp
var oneMonthAgo = DateTime.Now.AddMonths(-1);
return await ctx.MedBooks
    .Where(i => i.IsActive == true 
        && i.CancellationTo <= cancelationDay
        && i.CancellationTo >= oneMonthAgo)
    .Select(i => i.PreBookId).ToArrayAsync();
```

### Option C: Combined A + B (Recommended)

1. SQL cleanup now (immediate effect)
2. Deploy query filter (prevent future accumulation)

### Option D: Mark IsActive=false on Failure

In `MainLogic.cs`, after failed cancellation:
```csharp
await Repository.Instance.SetCancelStatus(preBookId).ConfigureAwait(false);
```

---

## Fix Applied — Option A (2026-02-24)

### SQL Executed

```sql
-- On: medici-sql-server.database.windows.net / medici-db
-- Table: MED_Book (EF name: MedBooks)
UPDATE MED_Book SET IsActive = 0 
WHERE IsActive = 1 
  AND CancellationTo < DATEADD(MONTH, -1, GETDATE());
```

### Results

| Metric | Value |
|--------|-------|
| **Rows updated** | 50 |
| **Remaining stuck** | 0 |
| **Total active bookings after** | 107 |
| **Date range cleaned** | Apr 2025 – Dec 2025 |
| **All Source** | 1 (Innstant/RateHawk) |

### Full List of Cleaned PreBookIds

```
9377, 9375, 9422, 9439, 9438, 9442, 9421, 9386, 9437, 9372,
9436, 9371, 9426, 9238, 9242, 9434, 9237, 9370, 9446, 9445,
9496, 9494, 9500, 9080, 9480, 9479, 9452, 9450, 9559, 9558,
9557, 9593, 9556, 9555, 9553, 9552, 9551, 9530, 9545, 9529,
9522, 9546, 9532, 9526, 9527, 9521, 9565, 9540, 9539, 9568
```

Notable: PB=9540 (BK=3597176) is the Sea Tower by Isrotel Design booking that triggered the investigation.

### Key Discovery During Fix

The `appsettings.json` in the source code (`MediciAutoCancellation/appsettings.json`) points to `194.113.211.244/medici+++`, but this file is **NOT deployed** to Azure. The WebJob's `Repository` class reads `appsettings.json` from `site/wwwroot/` which points to Azure SQL. The fix was applied to the correct database.

---

## Files Deployed on Azure (AutoCancellation folder)

| File | Size | Purpose |
|------|------|---------|
| `job_log.txt` | 423,726 bytes | Execution log |
| `singleton.job.lock` | 0 bytes | Singleton lock file |
| `status_f9c9ae` | 20 bytes | Current instance status |

Note: The actual `AutoCancellation.exe` and DLLs are in the parent App Service site deployment, not in the data/jobs folder.
