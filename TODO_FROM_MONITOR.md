# Pending Tasks from MediciMonitor

**Created:** 2026-03-23 by Claude Code (medici-monitor session)
**Priority:** High

---

## 1. Activate Monitor Ingestion Bridge

The MediciMonitor now has a full SystemMonitor service that runs 13 health checks every 30 minutes. The prediction project already has a `POST /monitor/ingest` endpoint and `MonitorBridge` class ready.

**What's needed on prediction side:**
- Verify `src/services/monitor_bridge.py` and `src/api/routers/monitor_router.py` are working
- Test the ingest endpoint: `POST /api/v1/salesoffice/monitor/ingest` with sample monitor JSON
- Ensure confidence adjustments are applied when monitor data arrives

**Monitor API to pull from:**
```
GET https://medici-monitor-dashboard.azurewebsites.net/api/monitor/full
GET https://medici-monitor-dashboard.azurewebsites.net/api/monitor/status
GET https://medici-monitor-dashboard.azurewebsites.net/api/monitor/trend?hours=24
GET https://medici-monitor-dashboard.azurewebsites.net/api/status
GET https://medici-monitor-dashboard.azurewebsites.net/api/alerts
```

## 2. Set Up Scheduled Monitor Polling

The prediction service should periodically pull monitor data and apply it to confidence adjustments.

**Implementation:**
- Add a scheduled task (every 30 min) in `_shared_state.py` or a new background task
- Fetch `GET /api/monitor/full` from the monitor
- Pass the result to `MonitorBridge.ingest_monitor_results()`
- Log the applied confidence adjustments

**Example code:**
```python
import httpx

MONITOR_URL = "https://medici-monitor-dashboard.azurewebsites.net"

async def poll_monitor():
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{MONITOR_URL}/api/monitor/full")
            if resp.status_code == 200:
                monitor_bridge.ingest_monitor_results(resp.json())
                logger.info("Monitor data ingested successfully")
    except Exception as e:
        logger.warning(f"Monitor poll failed: {e}")
```

## 3. Bidirectional Health Status

The monitor already exposes prediction health via:
- `GET /api/monitor/check/booking_sales` — tracks booking/sales metrics

**Prediction should expose back:**
- Current signal distribution (CALL/PUT/NEUTRAL counts)
- Prediction confidence average
- Active confidence adjustments from monitor data
- Last successful prediction run timestamp

This is already partially done via `/monitor/status` — verify it returns useful data.

## 4. Alert Cross-Reference

When the monitor detects issues (WebJob stale, Zenith down, mapping gaps), the prediction system should:
1. Reduce confidence for affected hotels (already implemented in MonitorBridge)
2. Show a banner/warning in the trading dashboard
3. Optionally pause CALL signals for affected hotels

**Check:** Does `src/templates/options_board.html` show any monitor-based warnings?

## 5. Telegram Integration

The MediciMonitor Telegram bot sends reports every 3 hours. Consider:
- Adding prediction summary to the monitor's Telegram reports
- The monitor bot can call `/api/v1/salesoffice/ai/brief` and include it in reports
- This requires the monitor to know the prediction API URL

**Prediction API URL:** https://medici-prediction-api.azurewebsites.net

---

## Connection Details

| System | URL | Purpose |
|--------|-----|---------|
| Monitor Dashboard | https://medici-monitor-dashboard.azurewebsites.net | Booking engine health |
| Monitor API (full scan) | /api/monitor/full | 13-check system scan |
| Monitor API (status) | /api/status | Live booking status |
| Monitor API (alerts) | /api/alerts | Active alerts |
| Prediction API | https://medici-prediction-api.azurewebsites.net | Price signals |
| Prediction Monitor Ingest | POST /api/v1/salesoffice/monitor/ingest | Receive monitor data |
| Shared DB | Azure SQL medici-db | Both projects read from same DB |
