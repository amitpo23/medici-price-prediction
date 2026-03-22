# 07 - Azure Monitoring Setup / הגדרות ניטור

## Overview

Azure monitoring infrastructure created on 2026-02-23 for `Medici-RG` resource group.

---

## Components

### 1. Log Analytics Workspace
| Property | Value |
|----------|-------|
| **Name** | `medici-monitor-law` |
| **Location** | West Europe |
| **Retention** | 30 days |
| **Resource ID** | `/subscriptions/2da025cc-dfe5-450f-a18f-10549a3907e3/resourceGroups/Medici-RG/providers/Microsoft.OperationalInsights/workspaces/medici-monitor-law` |

### 2. Action Group
| Property | Value |
|----------|-------|
| **Name** | `medici-monitor-ag` |
| **Short Name** | `medialrt` |
| **Resource ID** | `/subscriptions/2DA025CC-DFE5-450F-A18F-10549A3907E3/resourceGroups/Medici-RG/providers/microsoft.insights/actionGroups/medici-monitor-ag` |
| **Test Email** | `amitporat1981@gmail.com` |

### 3. Workbook
| Property | Value |
|----------|-------|
| **Name** | "Medici Ops Central Workbook" |
| **ID** | `4f7e2f6e-2bfb-49e7-b35f-92e7b9b4d2a1` |
| **Panels** | HTTP Status Distribution, SQL Diagnostic Events, 5xx Errors |

---

## Diagnostic Settings

### Web App (medici-backend)
**Setting Name:** `medici-webapp-diag`  
**Target:** Log Analytics workspace

| Log Category | Enabled |
|-------------|---------|
| AppServiceHTTPLogs | ✅ |
| AppServiceConsoleLogs | ✅ |
| AppServiceAppLogs | ✅ |
| AppServiceAuditLogs | ✅ |
| AppServicePlatformLogs | ✅ |
| AllMetrics | ✅ |

### SQL Server (medici-sql-server)
**Setting Name:** `medici-sqlserver-diag`

| Log Category | Enabled |
|-------------|---------|
| SQLSecurityAuditEvents | ✅ |
| DevOpsOperationsAudit | ✅ |
| AllMetrics | ✅ |

### SQL Database (medici-db)
**Setting Name:** `medici-sqldb-diag`

| Log Category | Enabled |
|-------------|---------|
| AutomaticTuning | ✅ |
| QueryStoreRuntimeStatistics | ✅ |
| QueryStoreWaitStatistics | ✅ |
| Errors | ✅ |
| DatabaseWaitStatistics | ✅ |
| Timeouts | ✅ |
| Blocks | ✅ |
| Deadlocks | ✅ |
| SQLInsights | ✅ |

| Metric Category | Enabled |
|-----------------|---------|
| Basic | ✅ |
| InstanceAndAppAdvanced | ✅ |
| WorkloadManagement | ✅ |

---

## Alerts

### Metric Alerts (Azure Monitor)
| Alert Name | Resource | Condition | Severity | Window | Frequency |
|-----------|----------|-----------|----------|--------|-----------|
| `medici-webapp-http5xx` | medici-backend | Http5xx count > 10 | 1 (Critical) | 5m | 1m |
| `medici-sqldb-cpu-high` | medici-db | CPU % avg > 80 | 2 (Warning) | 5m | 1m |

### Log Alerts (Scheduled Query)
| Alert Name | Query | Threshold | Severity |
|-----------|-------|-----------|----------|
| `medici-logalert-http5xx-spike` | AppServiceHTTPLogs \| ScStatus 500-599 | > 20 | 1 |
| `medici-logalert-sql-deadlocks` | AzureDiagnostics \| Category == 'Deadlocks' | > 0 | 1 |
| `medici-logalert-sql-timeouts` | AzureDiagnostics \| Category == 'Timeouts' | > 5 | 2 |
| `medici-logalert-sql-blocks` | AzureDiagnostics \| Category == 'Blocks' | > 3 | 2 |
| `medici-logalert-sql-errors` | AzureDiagnostics \| Category == 'Errors' | > 5 | 2 |
| `medici-logalert-no-http-traffic` | AppServiceHTTPLogs count | < 1 | 3 |

All alerts → Action Group `medici-monitor-ag`  
All log alerts: evaluation-frequency=5m, window=10m, auto-mitigate=true

---

## Useful KQL Queries

### HTTP Status Distribution (1h)
```kql
union isfuzzy=true AppServiceHTTPLogs 
| where TimeGenerated > ago(1h) 
| summarize Requests=count() by Status=tostring(ScStatus) 
| order by Requests desc
```

### SQL Diagnostic Events (1h)
```kql
union isfuzzy=true AzureDiagnostics 
| where TimeGenerated > ago(1h) 
| where Category in ("Deadlocks","Timeouts","Blocks","Errors") 
| summarize Count=count() by Category 
| order by Count desc
```

### 5xx Errors (15m)
```kql
union isfuzzy=true AppServiceHTTPLogs 
| where TimeGenerated > ago(15m) 
| where toint(ScStatus) between (500 .. 599) 
| summarize Errors5xx=count()
```

### WebJob Activity
```kql
AppServiceConsoleLogs
| where TimeGenerated > ago(1h)
| where ResultDescription has "SalesOffice" or ResultDescription has "BuyRoom"
| project TimeGenerated, ResultDescription
| order by TimeGenerated desc
```

---

## Verification Commands

```powershell
# List all alerts
az monitor scheduled-query list -g Medici-RG --query "[].{name:name,severity:severity,enabled:enabled}" -o table
az monitor metrics alert list -g Medici-RG --query "[].{name:name,severity:severity,enabled:enabled}" -o table

# Check workbook
az resource show --ids /subscriptions/2da025cc-dfe5-450f-a18f-10549a3907e3/resourceGroups/Medici-RG/providers/Microsoft.Insights/workbooks/4f7e2f6e-2bfb-49e7-b35f-92e7b9b4d2a1 --query "{name:name,displayName:properties.displayName}" -o json

# Test action group
az monitor action-group test-notifications create -g Medici-RG --action-group medici-monitor-ag --alert-type logalertv2 --add-action email testReceiver amitporat1981@gmail.com usecommonalertschema -o json

# Run KQL query
az monitor log-analytics query -w <workspace-id> --analytics-query "<KQL>" -o table
```
