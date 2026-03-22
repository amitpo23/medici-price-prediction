# 09 - Fixes & Changes Log / לוג שינויים ותיקונים

---

## Version 1.4 — 2026-02-24

**Status:** Monitoring Dashboard ADDED ✅

### Feature: Real-time Operations Monitoring Dashboard

**Files Added:**
- `Backend/Controllers/MonitoringController.cs` — Full monitoring API + embedded HTML dashboard
- `Backend/Models/MonitoringModels.cs` — DTO models for monitoring data

**Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET /Monitoring/Dashboard` | HTML dashboard — auto-refresh every 30s |
| `GET /Monitoring/api/status` | JSON API — full system status |

**Dashboard Monitors:**
- **Active Bookings** — total count, breakdown by hotel
- **Stuck Cancellations** — bookings where `IsActive=1 AND CancellationTo < NOW()` (RED alert)
- **Upcoming Cancellations** — within 48 hours
- **Push Operations** — active count, failed count with error details
- **Queue Status** — pending, processing, error items
- **SalesOffice Orders** — pending, in-progress, completed, failed
- **Booking Errors** — last 24h with details
- **Cancel Errors** — last 24h with details
- **BackOffice Errors** — last 24h with details
- **Opportunities** — active count, rooms bought today

**Features:**
- Auto-refresh every 30 seconds
- Color-coded KPI cards (green/yellow/red)
- Alert bar with sound notification for critical issues
- Hotel breakdown bar chart
- Tabbed error view (Cancel/Booking/Push/BackOffice/Queue)
- No external dependencies — fully self-contained HTML
- No authentication required (read-only)

**Database Tables Queried:**
`MED_Book`, `MED_CancelBook`, `MED_CancelBookError`, `MED_BookError`, `Med_HotelsToPush`, `Queue`, `BackOfficeOPT`, `BackOfficeOptLog`, `Med_Hotels`, `SalesOfficeOrders`

---

## Version 1.3 — 2026-02-24

**Status:** AutoCancellation cleanup APPLIED ✅

### Fix: One-time MED_Book cleanup (Option A)

**Database:** `medici-sql-server.database.windows.net/medici-db`  
**Table:** `MED_Book` (EF: `MedBooks`)  
**SQL:** `UPDATE MED_Book SET IsActive=0 WHERE IsActive=1 AND CancellationTo < DATEADD(MONTH, -1, GETDATE())`

| Metric | Value |
|--------|-------|
| Rows updated | **50** |
| Remaining stuck | **0** |
| Total active after | **107** |
| Date range | Apr 2025 – Dec 2025 |

**Key discovery:** The deployed WebJob uses Azure SQL (from `site/wwwroot/appsettings.json`), NOT the `194.113.211.244` server listed in the source code's `appsettings.json`.

**Rollback:** `UPDATE MED_Book SET IsActive=1 WHERE PreBookId IN (9377,9375,9422,...all 50 IDs)`

---

## Version 1.2 Snapshot — 2026-02-24

**Status:** Investigation complete, NO changes made yet.

### AutoCancellation WebJob Investigation

**Finding:** The `AutoCancellation` Continuous WebJob on `medici-backend` has ~30+ PreBookIds stuck in an infinite retry loop. Every run fails on all of them with "cannot cancel booking on Innstant" because the provider (RateHawk) no longer allows cancellation. Since `IsActive` is never set to `false` on failure, the same bookings are selected every run.

**See:** [10-autocancellation-investigation.md](./10-autocancellation-investigation.md)

**Proposed solutions (awaiting decision):**
- A: One-time SQL cleanup (`UPDATE MedBooks SET IsActive=0` for old entries)
- B: Code filter — skip `CancellationTo` older than 1 month in `GetBookIdsToCancel()`
- C: Combined A+B (recommended)
- D: Mark `IsActive=false` on API failure in `MainLogic.cs`

---

## Date: 2026-02-23

### Investigation: Hotel 20702 "Rooms With Mapping: 0"

**Issue:** Hotel 20702 (Embassy Suites by Hilton Miami - Doral) showed "Rooms With Mapping: 0" in SalesOffice processing.

**Root Cause Analysis:**
1. `Innstant_ZenithId = 0` → Hotel excluded by `FilterByVenueId()` — not even searched
2. `isActive = False` → Hotel inactive, excluded from all processing
3. **No `Med_Hotels_ratebycat` rows** → Even if searched, `FindPushRatePlanCode()` returns (null, null)

**Combined Effect:** The hotel was invisible to the SalesOffice WebJob on 3 independent levels.

---

### Fix 1: Hotel 20702 (Embassy Suites Doral)

**Before:**
| Field | Value |
|-------|-------|
| Innstant_ZenithId | 0 |
| isActive | False |
| ratebycat rows | 0 |

**After:**
| Field | Value |
|-------|-------|
| Innstant_ZenithId | 5081 |
| isActive | True |
| ratebycat rows | 2 |

**SQL Executed:**
```sql
-- Backup
SELECT * INTO BAK_Med_Hotels_20260223 FROM Med_Hotels
SELECT * INTO BAK_Med_Hotels_ratebycat_20260223 FROM Med_Hotels_ratebycat

-- Fix hotel
UPDATE Med_Hotels SET Innstant_ZenithId = 5081, isActive = 1 WHERE HotelId = 20702

-- Add ratebycat
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) 
VALUES (20702, 1, 1, '12045', 'STD')    -- Id=852

INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) 
VALUES (20702, 1, 12, '12045', 'SUI')   -- Id=855
```

**Rollback:** `ROLLBACK_Hotel20702_20260223.sql`

---

### Fix 2: Hotel 24982 (Hilton Miami Downtown)

**Before:**
| Field | Value |
|-------|-------|
| Innstant_ZenithId | 0 |
| isActive | False |
| ratebycat rows | 0 |

**After:**
| Field | Value |
|-------|-------|
| Innstant_ZenithId | 5084 |
| isActive | True |
| ratebycat rows | 2 |

**SQL Executed:**
```sql
-- Backup
SELECT * INTO BAK_Med_Hotels_24982_20260223 FROM Med_Hotels WHERE HotelId = 24982
SELECT * INTO BAK_ratebycat_24982_20260223 FROM Med_Hotels_ratebycat WHERE HotelId = 24982

-- Fix hotel
UPDATE Med_Hotels SET Innstant_ZenithId = 5084, isActive = 1 WHERE HotelId = 24982

-- Add ratebycat
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) 
VALUES (24982, 1, 1, '12048', 'STD')    -- Id=853

INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) 
VALUES (24982, 1, 12, '12048', 'SUI')   -- Id=854
```

**Rollback:** `ROLLBACK_Hotel24982_20260223.sql`

---

### Fix 3: 19 Hotels Batch Activation

**Issue:** 19 hotels had correct ZenithId but `isActive = False`

**SQL Executed:**
```sql
-- Backup
SELECT * INTO BAK_Med_Hotels_19inactive_20260223 
FROM Med_Hotels 
WHERE isActive = 0 
AND Innstant_ZenithId > 0 
AND HotelId IN (21024, 261038, 24964, 1010277, 885653, 371764, 338285, 
                1004953, 1107488, 1023316, 1055975, 1088652, 838901, 
                23413, 255124, 1099556, 21049, 21021, 24998)

-- Activate all
UPDATE Med_Hotels SET isActive = 1 
WHERE HotelId IN (21024, 261038, 24964, 1010277, 885653, 371764, 338285, 
                  1004953, 1107488, 1023316, 1055975, 1088652, 838901, 
                  23413, 255124, 1099556, 21049, 21021, 24998)
```

---

### Azure Monitoring Created

| Component | Details |
|-----------|---------|
| Log Analytics Workspace | `medici-monitor-law` (West Europe, 30d retention) |
| Action Group | `medici-monitor-ag` (email: amitporat1981@gmail.com) |
| Diagnostic Settings | webapp, SQL server, SQL database → Log Analytics |
| Metric Alerts | HTTP 5xx (>10, sev 1), SQL CPU (>80%, sev 2) |
| Log Alerts | 5xx spike, deadlocks, timeouts, blocks, errors, no-traffic |
| Workbook | "Medici Ops Central Workbook" |

---

### Deferred Work (Not Completed)

| Item | Details | Status |
|------|---------|--------|
| Hotel 20845 (DoubleTree Doral) | ZenithId=5082, RatePlan=12046 | ⬜ Deferred |
| Hotel 20706 (Hilton Airport) | ZenithId=5083, RatePlan=12047 | ⬜ Deferred |
| Hotel Continental | ZenithId=5106, mapping conflict | ⬜ Deferred |
| Reset WebJobStatus for fixed hotels | NULL out completed orders | ⬜ Offered, not done |
| B&B RatePlan mapping for Embassy | RatePlanCode=13170, BoardId=2 | ⬜ Not mapped yet |
| B&B RatePlan mapping for Hilton | RatePlanCode=13173, BoardId=2 | ⬜ Not mapped yet |
| Hotel 5080 Products | Empty in Zenith, same issue as 5081/5084 | ⬜ Needs Products in hotel.tools |

---

## Date: 2026-02-23 (Evening Session)

### Fix 4: Zenith Products Configuration - Embassy Suites (5081)

**Issue:** Hotel 5081 (Embassy Suites) had 247 push failures with zero successes, ever.
API returned `Error 402: Can not find product for availability update (5081/Stnd/12045)`.
`OTA_HotelAvailRQ` (Retrieve) returned `<RoomStays/>` = empty products.

**Root Cause:** Products (RoomType + RatePlan combinations) were not configured in hotel.tools UI.

**Fix Applied (in hotel.tools UI):**
- Added Product: Standard (Stnd) with 2 RatePlans:
  - 12045 (room only)
  - 13170 (bed and breakfast) ← NEW
- Added Product: Suite (Suite) with 2 RatePlans:
  - 12045 (room only)
  - 13170 (bed and breakfast) ← NEW

**Verification:**
```
OTA_HotelAvailRQ → 4 Products returned (was: 0)
OTA_HotelAvailNotifRQ → <Success/> (was: Error 402)
OTA_HotelRateAmountNotifRQ → <Success/> (was: Error 402)
```

---

### Fix 5: Zenith Products Configuration - Hilton Downtown (5084)

**Issue:** Hotel 5084 (Hilton Downtown) had 152 push failures with zero successes, ever.
Same error pattern as 5081.

**Fix Applied (in hotel.tools UI):**
- Added Product: Standard (Stnd) with 2 RatePlans:
  - 12048 (Refundable)
  - 13173 (bed and breakfast) ← NEW
- Added Product: Suite (Suite) with 2 RatePlans:
  - 12048 (Refundable)
  - 13173 (bed and breakfast) ← NEW

**Verification:**
```
OTA_HotelAvailRQ → 4 Products returned (was: 0)
OTA_HotelAvailNotifRQ → <Success/> (was: Error 402)
OTA_HotelRateAmountNotifRQ → <Success/> (was: Error 402)
```

---

### Full System Status After All Fixes (23/02/2026 End of Day)

| Hotel | ZenithId | Products | Push Avail | Push Rate | Status |
|-------|----------|----------|------------|-----------|--------|
| citizenM Miami | 5079 | 2 | ✅ | ✅ | Working (always was) |
| Breakwater South Beach | 5110 | 8 | ✅ | ✅ | Working (always was) |
| **Embassy Suites** | **5081** | **4** | **✅** | **✅** | **Fixed 23/02** |
| **Hilton Downtown** | **5084** | **4** | **✅** | **✅** | **Fixed 23/02** |

### New RatePlanCodes Discovered (Not Yet Mapped in DB)

| Hotel | ZenithId | RatePlanCode | Description | DB Status |
|-------|----------|-------------|-------------|-----------|
| Embassy | 5081 | 13170 | bed and breakfast | ❌ Not in ratebycat |
| Hilton | 5084 | 13173 | bed and breakfast | ❌ Not in ratebycat |
| citizenM | 5079 | 13169 | bed and breakfast | ❌ Not in ratebycat |
| Breakwater | 5110 | 12867 | Bed and Breakfast | ❌ Not in ratebycat |

To enable B&B pricing push, add rows to `Med_Hotels_ratebycat` with BoardId=2 (BB).

---

### Files Created During Session

| File | Location | Purpose |
|------|----------|---------|
| `check_orders.py` | Root | Query SalesOffice orders script |
| `check_orders_result.txt` | Root | Query results |
| `webjob-dlls/` | Root | Downloaded WebJob DLLs |
| `webjob-dlls/reflection.txt` | | .NET reflection output |
| `webjob-dlls/strings_services.txt` | | OnlyNight.Services.dll strings |
| `webjob-dlls/strings_filtered.txt` | | Filtered SalesOffice strings |
| `webjob-dlls/flow_strings.txt` | | RatePlan/Venue mapping strings |
| `webjob-dlls/data_strings.txt` | | OnlyNight.Data.dll strings |
| `webjob-dlls/models_strings.txt` | | OnlyNight.Models.dll strings |
| `webjob-dlls/sql_strings.txt` | | SQL operation strings |
| `ROLLBACK_Hotel20702_20260223.sql` | Root | Rollback script |
| `ROLLBACK_Hotel24982_20260223.sql` | Root | Rollback script |
| `docs/` | Root | This documentation folder |
