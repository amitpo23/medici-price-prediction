# Medici Hotels - תיעוד מערכת מלא

## System Documentation Index

> **Last Updated:** 2026-02-24  
> **Author:** Auto-generated documentation from full system audit  
> **Version:** 1.4

---

## Table of Contents

| # | Document | Description |
|---|----------|-------------|
| 1 | [System Architecture](./01-system-architecture.md) | סקירת ארכיטקטורה כללית, רכיבים, ותשתית Azure |
| 2 | [Database Schema](./02-database-schema.md) | מבנה טבלאות, עמודות, וקשרים |
| 3 | [WebJobs & OnlyNight Project](./03-webjobs-onlynight.md) | תיעוד 4 ה-WebJobs ופרויקט OnlyNight |
| 4 | [SalesOffice Processing Flow](./04-salesoffice-flow.md) | תהליך עיבוד הזמנות SalesOffice מקצה לקצה |
| 5 | [Hotel Mapping & Rate Plans](./05-hotel-mapping.md) | מיפוי מלונות, Zenith IDs, RatePlanCodes |
| 6 | [Codebase Reference](./06-codebase-reference.md) | תיעוד קוד - פרויקטים, מחלקות, ומתודות עיקריות |
| 7 | [Azure Monitoring Setup](./07-azure-monitoring.md) | ניטור, alerts, workbook, Log Analytics |
| 8 | [Operations Runbook](./08-operations-runbook.md) | מדריך תפעולי - תיקונים, בדיקות, rollbacks |
| 8b | [Investigation: 82 Details](./08-investigation-82-details.md) | חקירה למה רק 82 עדכוני מחיר → **נפתר** ✅ |
| 9 | [Fixes & Changes Log](./09-fixes-changelog.md) | לוג שינויים ותיקונים שבוצעו |
| 9b | [Zenith API Research](./09-zenith-api-research.md) | מחקר מלא על Zenith API - פעולות, שגיאות, בדיקות |
| 10 | [AutoCancellation Investigation](./10-autocancellation-investigation.md) | חקירת WebJob ביטולים — 50 הזמנות תקועות → **נפתר** ✅ |
| 11 | [Monitoring Dashboard](./11-monitoring-dashboard.md) | דשבורד ניטור בזמן אמת — כל הפעולות, WebJobs, שגיאות, SalesOffice |

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 1.0 | 2026-02-23 | Initial documentation — architecture, DB, WebJobs, SalesOffice flow, mapping, monitoring |
| 1.1 | 2026-02-24 | Added investigation resolution (82 Details), Zenith API research, fixes changelog |
| 1.2 | 2026-02-24 | Snapshot before AutoCancellation fix — added doc 10 with full investigation |
| 1.3 | 2026-02-24 | Option A applied — 50 stuck bookings cleaned from MED_Book |
| **1.4** | **2026-02-24** | **Real-time Monitoring Dashboard — /Monitoring/Dashboard** |

---

## Quick Reference

### Connection Details
| Resource | Value |
|----------|-------|
| **Azure SQL Server** | `medici-sql-server.database.windows.net` |
| **Database** | `medici-db` |
| **SQL User** | `medici_sql_admin` |
| **App Service** | `medici-backend` (East US 2) |
| **Resource Group** | `Medici-RG` |
| **Subscription** | `2da025cc-dfe5-450f-a18f-10549a3907e3` |
| **Log Analytics** | `medici-monitor-law` (West Europe) |

### Key API Sources
| Source ID | Provider | Description |
|-----------|----------|-------------|
| 1 | Innstant API | Primary hotel search & booking |
| 2 | GoGlobal | Secondary hotel search & booking |

### Board Reference
| ID | Code | Description |
|----|------|-------------|
| 1 | RO | Room Only |
| 2 | BB | Bed & Breakfast |
| 3 | HB | Half Board |
| 4 | FB | Full Board |
| 5 | AI | All Inclusive |
| 6 | CB | Continental Breakfast |
| 7 | BD | Bed & Dinner |

### Category Reference
| ID | Name |
|----|------|
| 1 | Standard |
| 2 | Superior |
| 3 | Dormitory |
| 4 | Deluxe |
| 12 | Suite |
