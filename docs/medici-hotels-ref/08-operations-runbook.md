# 08 - Operations Runbook / מדריך תפעולי

## Quick Reference

### Connection Strings
```
SQL: Server=tcp:medici-sql-server.database.windows.net,1433;Database=medici-db;User Id=medici_sql_admin;Password=@Amit2025;Encrypt=True;TrustServerCertificate=False;
```

### Kudu Access
```
URL:  https://medici-backend.scm.azurewebsites.net
User: $medici-backend
Pass: DgFX5ZmRyla3i0T0iXid18zGfqrPRqZfvazrYwcart5xssLRh5wjGqW2hWZW
```

---

## Common Operations

### 1. Add a New Hotel Mapping

#### Step 1: Find the Hotel in Med_Hotels
```sql
SELECT HotelId, Name, Innstant_ZenithId, isActive 
FROM Med_Hotels 
WHERE HotelId = @hotelId
-- OR
WHERE Name LIKE '%hotel name%'
```

#### Step 2: Create Backup
```sql
SELECT * INTO BAK_Med_Hotels_{hotelId}_{date} FROM Med_Hotels WHERE HotelId = @hotelId
SELECT * INTO BAK_ratebycat_{hotelId}_{date} FROM Med_Hotels_ratebycat WHERE HotelId = @hotelId
```

#### Step 3: Update Hotel (if needed)
```sql
UPDATE Med_Hotels 
SET Innstant_ZenithId = @zenithId, isActive = 1 
WHERE HotelId = @hotelId
```

#### Step 4: Add ratebycat Rows
```sql
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) 
VALUES 
  (@hotelId, 1, 1, '@ratePlanCode', 'STD'),  -- RO + Standard
  (@hotelId, 1, 12, '@ratePlanCode', 'SUI')   -- RO + Suite
-- Add more rows for each board/category combo
```

#### Step 5: Verify
```sql
SELECT * FROM Med_Hotels WHERE HotelId = @hotelId
SELECT * FROM Med_Hotels_ratebycat WHERE HotelId = @hotelId
```

---

### 2. Re-Process SalesOffice Orders for a Hotel

#### Step 1: Find affected orders
```sql
SELECT o.Id, o.DateInsert, o.DateFrom, o.DateTo, o.WebJobStatus
FROM [SalesOffice.Orders] o
WHERE o.DestinationId IN (
    SELECT HotelId FROM Med_Hotels WHERE HotelId = @hotelId
)
AND o.WebJobStatus LIKE 'Completed%Mapping: 0%'
ORDER BY o.DateInsert DESC
```

#### Step 2: Reset WebJobStatus
```sql
-- Create backup first!
SELECT * INTO BAK_SalesOffice_Orders_reset_{date}
FROM [SalesOffice.Orders] 
WHERE Id IN (@orderIds)

-- Reset
UPDATE [SalesOffice.Orders] 
SET WebJobStatus = NULL 
WHERE Id IN (@orderIds)
```

#### Step 3: Wait for WebJob
The `AzureWebJob.Functions.ProcessSalesOfficeOrders` runs every 5 minutes. Check status after:
```sql
SELECT Id, WebJobStatus 
FROM [SalesOffice.Orders] 
WHERE Id IN (@orderIds)
```

---

### 3. Check WebJob Health

#### Via Azure CLI:
```powershell
# List all WebJobs
az webapp webjob continuous list -g Medici-RG -n medici-backend -o table

# Check specific WebJob
az webapp webjob continuous show -g Medici-RG -n medici-backend --webjob-name AzureWebJob -o json
```

#### Via Kudu API:
```powershell
$cred = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('$medici-backend:DgFX5ZmRyla3i0T0iXid18zGfqrPRqZfvazrYwcart5xssLRh5wjGqW2hWZW'))

# Check ProcessSalesOfficeOrders last run
Invoke-RestMethod -Uri "https://medici-backend.scm.azurewebsites.net/api/vfs/data/jobs/continuous/AzureWebJob/AzureWebJob.Functions.ProcessSalesOfficeOrders.Run.status" -Headers @{Authorization="Basic $cred"} | ConvertTo-Json
```

#### Expected Status Response:
```json
{
  "Last": "2026-02-23T11:25:03.4311652+00:00",
  "Next": "2026-02-23T11:30:00+00:00",
  "LastUpdated": "2026-02-23T11:25:03.4311652+00:00"
}
```

---

### 4. Rollback Hotel Changes

#### Rollback Hotel 20702:
```sql
-- File: ROLLBACK_Hotel20702_20260223.sql

-- Delete added ratebycat rows
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 20702 AND Id IN (852, 855)

-- Restore original hotel data
UPDATE Med_Hotels 
SET Innstant_ZenithId = 0, isActive = 0 
WHERE HotelId = 20702

-- Verify
SELECT * FROM Med_Hotels WHERE HotelId = 20702
SELECT * FROM Med_Hotels_ratebycat WHERE HotelId = 20702
```

#### Rollback Hotel 24982:
```sql
-- File: ROLLBACK_Hotel24982_20260223.sql

DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 24982 AND Id IN (853, 854)

UPDATE Med_Hotels 
SET Innstant_ZenithId = 0, isActive = 0 
WHERE HotelId = 24982
```

#### Rollback 19 Hotels:
```sql
-- Restore from backup
UPDATE mh 
SET mh.isActive = bak.isActive 
FROM Med_Hotels mh 
JOIN BAK_Med_Hotels_19inactive_20260223 bak ON mh.HotelId = bak.HotelId
```

---

### 5. Check SalesOffice Order Statistics

```sql
-- Overall stats
SELECT 
  COUNT(*) AS TotalOrders,
  SUM(CASE WHEN WebJobStatus IS NULL THEN 1 ELSE 0 END) AS Pending,
  SUM(CASE WHEN WebJobStatus = 'In Progress' THEN 1 ELSE 0 END) AS InProgress,
  SUM(CASE WHEN WebJobStatus LIKE 'Completed%' THEN 1 ELSE 0 END) AS Completed
FROM [SalesOffice.Orders]
WHERE IsActive = 1

-- Orders with mapping problems
SELECT o.Id, o.DateInsert, o.DateFrom, o.DateTo, o.WebJobStatus
FROM [SalesOffice.Orders] o
WHERE o.WebJobStatus LIKE '%Mapping: 0%'
ORDER BY o.DateInsert DESC

-- Orders with good mapping
SELECT o.Id, o.WebJobStatus
FROM [SalesOffice.Orders] o
WHERE o.WebJobStatus LIKE '%Mapping: [1-9]%'
ORDER BY o.DateInsert DESC
```

---

### 6. Check Hotel Mapping Completeness

```sql
-- Hotels with ZenithId but no ratebycat
SELECT h.HotelId, h.Name, h.Innstant_ZenithId, h.isActive
FROM Med_Hotels h
WHERE h.Innstant_ZenithId > 0
AND h.isActive = 1
AND NOT EXISTS (
    SELECT 1 FROM Med_Hotels_ratebycat r WHERE r.HotelId = h.HotelId
)

-- Hotels with ratebycat entries
SELECT h.HotelId, h.Name, h.Innstant_ZenithId,
       r.BoardId, r.CategoryId, r.RatePlanCode, r.InvTypeCode
FROM Med_Hotels h
JOIN Med_Hotels_ratebycat r ON h.HotelId = r.HotelId
WHERE h.Innstant_ZenithId > 0
ORDER BY h.HotelId, r.BoardId, r.CategoryId

-- Active hotels without ZenithId
SELECT HotelId, Name, Innstant_ZenithId, isActive
FROM Med_Hotels
WHERE isActive = 1 AND (Innstant_ZenithId IS NULL OR Innstant_ZenithId = 0)
```

---

### 7. Monitor Opportunities

```sql
-- Pending opportunities
SELECT TOP 10 * FROM [MED_ֹOֹֹpportunities] 
ORDER BY OpportunityId DESC

-- Today's opportunities
SELECT * FROM [MED_ֹOֹֹpportunities]
WHERE CAST(DateForm AS DATE) >= CAST(GETDATE() AS DATE)
ORDER BY OpportunityId DESC
```

---

### 8. Restart a WebJob

```powershell
# Stop
az webapp webjob continuous stop -g Medici-RG -n medici-backend --webjob-name AzureWebJob

# Start
az webapp webjob continuous start -g Medici-RG -n medici-backend --webjob-name AzureWebJob
```

---

## Backup Tables Registry

| Table | Date | Purpose |
|-------|------|---------|
| `BAK_Med_Hotels_20260223` | 2026-02-23 | Full Med_Hotels backup |
| `BAK_Med_Hotels_ratebycat_20260223` | 2026-02-23 | Full ratebycat backup |
| `BAK_SalesOffice_Orders_20260223` | 2026-02-23 | Full SalesOffice.Orders backup |
| `BAK_Opportunities_20260223` | 2026-02-23 | Full Opportunities backup |
| `BAK_Med_Hotels_24982_20260223` | 2026-02-23 | Hotel 24982 specific backup |
| `BAK_ratebycat_24982_20260223` | 2026-02-23 | Hotel 24982 ratebycat backup |
| `BAK_Med_Hotels_19inactive_20260223` | 2026-02-23 | 19 inactive hotels backup |

---

## Emergency Contacts / Escalation

- **Email:** amitporat1981@gmail.com (via Action Group)
- **Slack:** Configured via SlackLibrary
- **Azure Portal:** https://portal.azure.com → Medici-RG
