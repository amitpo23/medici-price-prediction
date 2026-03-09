# Medici — Sprint Prompts for Claude Code

> Copy-paste each prompt into a **separate** Claude Code session.
> Each prompt is self-contained and references CLAUDE.md for project context.
> Execute sprints in order — later sprints depend on earlier ones.

---

## How to Use

1. Open Claude Code in the project root
2. Copy one sprint prompt (or a single task from it)
3. Paste and let Claude Code execute
4. Review the changes, run tests, commit
5. Move to next task/sprint

**Tip**: For large sprints, you can break them into individual tasks (each ### heading is a standalone task).

---

## Sprint Status Overview

| Sprint | Task | Status |
|--------|------|--------|
| 1.1 | Test Infrastructure | ✅ DONE |
| 1.2 | Critical Endpoint Tests | ✅ DONE (14 tests) |
| 1.3 | Unit Tests for Prediction Core | ✅ DONE (120+ tests) |
| 1.4 | Fix Bare Exception Handlers | ✅ DONE (81 fixed) |
| 1.5 | Startup Config Validation | ✅ DONE (23 tests) |
| 2.1 | Split Monolith Router | ✅ DONE (4,293→32 lines + 5 sub-routers) |
| 2.2 | Unify Cache Systems | ✅ DONE (CacheManager + 40 tests) |
| 2.3 | Extract HTML to Jinja2 | ✅ DONE (11 templates) |
| 2.4 | Standardize Collectors | ✅ DONE (auto-discovery, env toggle, 13 tests) |
| 2.5 | Extract Magic Numbers | ✅ DONE (config/constants.py, 30+ constants extracted) |
| 3.1 | API Pagination | ✅ DONE (paginate() + 4 endpoints, 16 tests) |
| 3.2 | Structured Logging | ✅ DONE (JSON logging, correlation IDs, 13 tests) |
| 3.3 | Rate Limiting & API Auth | ✅ DONE (slowapi, multi-key auth, CORS, 13 tests) |
| 3.4 | Health Check Dashboard | ✅ DONE (enhanced /health, HTML dashboard) |
| 4.1 | Prediction Feedback Loop | ✅ DONE (accuracy_tracker + 5 endpoints, 19 tests) |
| 4.2 | Real-Time Alert System | ✅ DONE (AlertDispatcher, 3 channels, 3 endpoints, 21 tests) |
| 4.3 | Data Quality Scoring | ✅ DONE (DataQualityScorer, 2 endpoints, 21 tests) |
| 4.4 | Scenario Analysis Engine | ✅ DONE (ScenarioEngine, 5 presets, 3 endpoints, 29 tests) |

**Total tests: 340 — All sprints complete!**

---

## ▶️ NEXT UP: Sprint 3 — Performance & Observability

### 3.1 — Add API Pagination

```
Read CLAUDE.md for project context.

Add pagination to all endpoints that return large datasets.

1. Create a shared pagination model in src/api/models/pagination.py:
   - PaginationParams: limit (default 100, max 1000), offset (default 0)
   - PaginatedResponse: items, total, limit, offset, has_more

2. Add pagination to these endpoints:
   - GET /options → limit/offset over the 2,850 room list
   - GET /data → paginate analysis results
   - GET /simple → paginate simplified view
   - GET /ai/metadata → already has limit param, standardize

3. For each endpoint:
   - Accept ?limit=100&offset=0 query params
   - Return PaginatedResponse with total count
   - Default to limit=100 if not specified
   - Cap limit at 1000

4. Add ?all=true escape hatch for backward compatibility (returns everything, but with warning header)

5. Update tests to verify pagination works correctly
6. Test edge cases: offset beyond total, limit=0, negative values

Don't break existing clients — if no pagination params are passed, return first 100 items with total count.
```

### 3.2 — Structured Logging

```
Read CLAUDE.md for project context.

Replace all 323 print/log statements with structured JSON logging.

1. Add python-json-logger to requirements.txt

2. Create src/utils/logging_config.py:
   - Configure JSON formatter for all loggers
   - Add correlation_id field (from X-Request-ID header)
   - Standard fields: timestamp, level, module, function, message, correlation_id
   - Set log level from env var: LOG_LEVEL (default INFO)

3. Create FastAPI middleware in src/api/middleware.py:
   - CorrelationIdMiddleware: extracts or generates X-Request-ID header
   - Stores correlation_id in contextvars for access across the request
   - Logs request start (method, path, params) and end (status, duration)

4. Replace ALL print() calls with logger.info/warning/error:
   - Search: grep -rn "print(" src/
   - Replace each with appropriate log level and structured message
   - Use f-strings or extra dict for structured data

5. Ensure every except block logs the exception with logger.error(..., exc_info=True)

6. Add to main.py startup: configure_logging()

7. Test: run the app and verify JSON output in logs
```

### 3.3 — Rate Limiting & API Auth

```
Read CLAUDE.md for project context.

Add proper rate limiting and improve API authentication.

1. Add slowapi to requirements.txt

2. Create src/api/middleware.py (or extend if exists):
   - Rate limiter: 100 requests/minute per IP for data endpoints
   - Rate limiter: 20 requests/minute per IP for AI endpoints (Claude API costs)
   - Rate limiter: 10 requests/minute for export endpoints
   - Return 429 Too Many Requests with Retry-After header

3. Improve API key validation:
   - Current: simple string comparison in analytics_dashboard.py
   - New: API key middleware that validates on all /api/ routes
   - Support multiple API keys (comma-separated in env var)
   - Log failed auth attempts with IP and attempted key prefix

4. Add CORS middleware:
   - Allow origins from env var: CORS_ORIGINS (comma-separated)
   - Default: allow same-origin only
   - Allow methods: GET, POST, PUT, DELETE
   - Allow headers: Authorization, Content-Type, X-Request-ID

5. Write tests for rate limiting and auth
```

### 3.4 — Health Check Dashboard

```
Read CLAUDE.md for project context.

Create a comprehensive health check endpoint that shows data source freshness and system status.

1. Enhance GET /health to return:
   {
     "status": "healthy" | "degraded" | "unhealthy",
     "uptime_seconds": 12345,
     "version": "2.0.0",
     "data_sources": {
       "salesoffice_db": { "status": "connected", "last_query": "2026-03-08T10:00:00Z", "latency_ms": 45 },
       "weather_api": { "status": "ok", "last_fetch": "...", "freshness": "fresh" },
       ...
     },
     "cache": { "analytics": { "size": 150, "hit_rate": 0.82 }, ... },
     "predictions": { "total_rooms": 2850, "last_scan": "...", "signals": { "CALL": 420, "PUT": 180, "NEUTRAL": 2250 } }
   }

2. Create a simple HTML health dashboard at GET /health/view:
   - Green/yellow/red status per data source
   - Last fetch timestamp
   - Auto-refresh every 60 seconds

3. Add alerting thresholds:
   - "degraded" if any source hasn't fetched in 2x expected interval
   - "unhealthy" if primary DB is unreachable or predictions are stale (>6 hours)

4. Write tests for health endpoint
```

---

## Sprint 4: New Capabilities (Weeks 7–10)

### 4.1 — Prediction Feedback Loop

```
Read CLAUDE.md for project context.

Implement closed-loop prediction accuracy tracking — this is the #1 missing capability.

1. Create new SQLite table via src/analytics/accuracy_tracker.py:
   - Table: prediction_log
   - Columns: id, room_id, hotel_id, prediction_ts, checkin_date, t_at_prediction,
     predicted_price, predicted_signal, predicted_confidence, actual_price, actual_signal,
     error_pct, error_abs, signal_correct (bool), scored_at

2. Hook into prediction pipeline:
   - After each prediction batch in deep_predictor.py, log predictions to prediction_log
   - Store: room_id, predicted_price, predicted_signal, t_at_prediction, timestamp

3. Create scoring job (runs daily):
   - For each prediction where checkin_date has passed:
   - Query actual price from SalesOffice DB (or latest price scan)
   - Compute: error_pct = (actual - predicted) / predicted
   - Determine: signal_correct = (predicted_signal matches actual direction)
   - Update prediction_log with actual values

4. Create accuracy API endpoints:
   - GET /api/v1/accuracy/summary?days=30 → MAE, MAPE, directional accuracy
   - GET /api/v1/accuracy/by-signal → precision/recall per CALL/PUT/NEUTRAL
   - GET /api/v1/accuracy/by-t-bucket → accuracy for T ranges: 1-7, 8-14, 15-30, 31-60, 61+
   - GET /api/v1/accuracy/by-hotel → per-hotel accuracy
   - GET /api/v1/accuracy/trend → rolling 7/30-day accuracy

5. Create HTML dashboard page: GET /accuracy/view
   - Charts: accuracy over time, by T-bucket, by signal type
   - Table: worst predictions (highest error)

6. Write tests for accuracy tracking
```

### 4.2 — Real-Time Alert System

```
Read CLAUDE.md for project context.

Implement push alerting on top of the existing Rules Engine.

1. Create src/services/alert_dispatcher.py:
   - AlertDispatcher class with channel support
   - Channel interface: send(alert_payload) → bool
   - WebhookChannel: HTTP POST to configurable URL
   - TelegramChannel: Telegram Bot API (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
   - LogChannel: always-on, logs all alerts to structured log

2. Create alert deduplication:
   - New SQLite table: alert_log (id, rule_id, timestamp, channel, payload_json, rooms_json, status)
   - Cooldown: don't re-fire same rule_id within ALERT_COOLDOWN_HOURS (default 4)

3. Hook into scan cycle:
   - In runner.py (or wherever price scans trigger), after scan completes:
   - Call rules engine evaluate_all()
   - For each triggered rule, dispatch alert via AlertDispatcher
   - Respect cooldown

4. Telegram message format:
   🔔 *Medici Alert: {rule_name}*
   Severity: {severity}
   Rooms: {count} rooms triggered
   Top signals: {room_id} → {signal} ({confidence})
   [View Dashboard]({dashboard_url})

5. API endpoints:
   - GET /api/v1/alerts/history?days=7 → alert log
   - POST /api/v1/alerts/test → fire test alert to all channels
   - GET /api/v1/alerts/stats → volume, top rules, false positive rate

6. Add to .env.example: ALERT_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALERT_COOLDOWN_HOURS

7. Write tests with mock channels
```

### 4.3 — Data Quality Scoring

```
Read CLAUDE.md for project context.

Implement data quality scoring for all data sources.

1. Create src/analytics/data_quality.py:
   - DataQualityScorer class
   - Per source: freshness_score (0-1), reliability_score (0-1), anomaly_flag (bool)
   - Freshness: exponential decay from last_successful_fetch / expected_interval
   - Reliability: rolling 30-day success rate (successful_fetches / expected_fetches)
   - Anomaly: flag when data deviates >3σ from rolling mean

2. New SQLite table: source_health
   - Columns: source_id, timestamp, freshness_score, reliability_score, anomaly_flag, weight_override, error_message

3. Auto weight adjustment:
   - When freshness_score < 0.5, reduce enrichment weight proportionally
   - Log all weight adjustments
   - Never reduce primary DB (SalesOffice) weight

4. API endpoints:
   - GET /api/v1/data-quality/status → all sources with scores
   - GET /api/v1/data-quality/history?source=weather&days=30

5. Hook into collector registry:
   - After each fetch, update source_health
   - On failure, record error and update reliability

6. Write tests
```

### 4.4 — Scenario Analysis Engine

```
Read CLAUDE.md for project context.

Implement what-if scenario analysis for the prediction engine.

1. Create src/analytics/scenario_engine.py:
   - ScenarioEngine class
   - run_scenario(overrides: dict) → ScenarioResult
   - Overrides: event_impact (0-200%), flight_delta (-50% to +50%), weather_severity (normal/storm/heatwave), competitor_delta (-20% to +20%), demand_multiplier (0.5-2.0), seasonal_override (peak/shoulder/off)

2. How it works:
   - Clone current forward curve state
   - Apply overrides to enrichment factors
   - Re-run ensemble with modified inputs
   - Return delta table: room_id, baseline_price, scenario_price, delta_$, delta_%, signal_changed

3. Preset scenarios:
   - "Art Basel Cancelled": event_impact=0, demand_multiplier=0.7
   - "Hurricane Warning": weather_severity=hurricane, demand_multiplier=0.5
   - "Peak Season Surge": demand_multiplier=1.5, competitor_delta=+15%
   - "Recession Impact": demand_multiplier=0.6, competitor_delta=-10%

4. API endpoints:
   - POST /api/v1/scenario/run → body: { overrides }, returns delta table
   - GET /api/v1/scenario/presets → list preset scenarios
   - POST /api/v1/scenario/compare → run multiple scenarios, return comparison

5. HTML dashboard: GET /scenario/view
   - Sliders for each factor
   - Real-time delta preview
   - Side-by-side comparison table

6. Write tests with known inputs/outputs
```

---

## Deferred / Optional Tasks

### 2.4 — Complete Collector Registry (80% done)

```
Read CLAUDE.md for project context.

The collector registry at src/collectors/registry.py exists but needs auto-discovery.

1. Add auto-discovery to CollectorRegistry:
   - Scan src/collectors/ for all classes extending BaseCollector
   - Auto-register them without hardcoded imports
   - Support enable/disable via env vars (COLLECTOR_{NAME}_ENABLED)

2. Update multi_source_loader.py to use registry.fetch_all()

3. Verify all collectors are properly detected and runnable

4. Write/update tests for auto-discovery

This is optional — the existing hardcoded registry works fine for now.
```

### 2.5 — Extract Magic Numbers

```
Read CLAUDE.md for project context.

Extract all hardcoded magic numbers into a central constants file.

1. Create config/constants.py with well-documented constants:

   # Prediction Engine
   ENSEMBLE_WEIGHT_FORWARD_CURVE = 0.50
   ENSEMBLE_WEIGHT_HISTORICAL = 0.30
   ENSEMBLE_WEIGHT_ML = 0.20
   BAYESIAN_K = 5
   MIN_VOLATILITY = 0.005
   OUTLIER_CAP = 0.10
   MAX_PREDICTION_HORIZON = 180
   PRICE_CLAMP_MIN = 0.40
   PRICE_CLAMP_MAX = 2.50

   # Signal Generation
   SIGNAL_THRESHOLD_HIGH = 0.70
   SIGNAL_THRESHOLD_MEDIUM = 0.60

   # Data Collection
   COLLECTION_INTERVAL = 3600
   DB_QUERY_TIMEOUT = 30
   API_TIMEOUT = 10

   # Enrichment Caps
   EVENT_IMPACT_MAX = 0.40
   DEMAND_IMPACT = 0.0015
   WEATHER_HURRICANE_IMPACT = -0.0015
   COMPETITOR_IMPACT_MAX = 0.0020
   CANCELLATION_IMPACT_MAX = -0.0025

2. Search and replace all magic numbers in the codebase with the constant names
3. Add imports to each file that uses them
4. Verify no behavior changes: run all tests

This is optional — can be done anytime as a cleanup task.
```

---

## Notes for Claude Code Usage

### General Tips
- **Always start** with `Read CLAUDE.md` — it gives Claude Code essential context
- **One sprint at a time** — don't try to do everything in one session
- **Commit after each task** — smaller commits are easier to review and revert
- **Run tests between tasks** — catch issues early

### If Claude Code Gets Confused
- Remind it: "Read CLAUDE.md for project context"
- Be specific: "Only modify src/analytics/forward_curve.py, don't touch other files"
- Set boundaries: "Don't refactor anything, just add the new function"

### Session Size Limits
- Large refactors should be done file-by-file across multiple sessions
- Each session: move one component, test, commit, start new session for next
