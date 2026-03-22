# Claude Code Continuation Prompt — Monitor ↔ Prediction Integration

## Context

We've built the full monitor bridge infrastructure. Now we need to **wire it into the live prediction pipeline**. Here's what exists:

### Already Built (DO NOT recreate)

1. **`src/services/monitor_bridge.py`** (~700 lines) — MonitorBridge class with:
   - `ingest_monitor_results(monitor_json)` → creates confidence_adjustments + market_signals in SQLite
   - `get_confidence_modifier(hotel_id=None)` → returns float -0.50 to 0.0
   - `get_market_signals()` → returns dict of normalized 0-1 signals: `demand_indicator`, `board_composition`, `market_dynamism`, `supply_volatility`, `price_execution_quality`
   - `check_health_and_alert()` → polls prediction engine freshness, dispatches alerts
   - `get_unified_status()` → combined health view

2. **`src/services/circuit_breaker.py`** (~310 lines) — CircuitBreaker with allow/record_success/record_failure, 3-state (CLOSED/OPEN/HALF_OPEN), threshold=3, cooldown=300s

3. **`src/api/routers/monitor_router.py`** (~150 lines) — 5 API endpoints under `/monitor/`

4. **`src/services/alert_dispatcher.py`** — AlertDispatcher with Log/Webhook/Telegram channels, SQLite dedup, `_check_escalation()`

5. **`tests/unit/test_monitor_bridge.py`** + **`tests/unit/test_circuit_breaker.py`** — Full unit tests

6. **`src/analytics/analyzer.py`** — Already has cancel_velocity enrichment (7d vs 365d rate comparison)

### What Needs Wiring (4 Tasks)

---

## Task 1: Wire MonitorBridge into Forward Curve Enrichments

**File**: `src/analytics/forward_curve.py`

The forward curve already applies enrichments (events, seasonality, demand, weather, competitors, cancellations). Add MonitorBridge signals as an additional enrichment step.

**What to do**:
1. After all existing enrichments are applied, add a new step:
   ```python
   # Monitor bridge confidence adjustment
   try:
       from src.services.monitor_bridge import MonitorBridge
       bridge = MonitorBridge()
       modifier = bridge.get_confidence_modifier(hotel_id=str(hotel_id))
       if modifier < 0:
           # Reduce confidence, not price. The modifier affects the signal confidence.
           result["confidence"] = max(0.1, result.get("confidence", 1.0) + modifier)
           result["monitor_adjustment"] = modifier
   except (ImportError, Exception):
       pass  # Monitor bridge is optional
   ```

2. Consume market signals for demand enrichment boost:
   ```python
   signals = bridge.get_market_signals()
   demand_signal = signals.get("demand_indicator", {}).get("value", 0)
   if demand_signal > 0.7:  # High demand from live bookings
       # Slight upward bias on forward curve
       enrichment_adjustments["live_demand"] = 0.02 * demand_signal
   ```

**Rules**:
- MonitorBridge is ALWAYS optional — wrap in try/except
- Never let monitor data override the core prediction, only adjust confidence
- Market signals adjust enrichments by max ±3%

---

## Task 2: Wire CircuitBreaker into Collector Registry

**File**: `src/collectors/` — find the base collector or registry that dispatches collectors

The circuit breaker exists but isn't used by any collector yet. Each collector's `collect()` method should check `circuit_breaker.allow(source_id)` before calling the data source.

**What to do**:
1. Find the base collector class or the collector registry (likely `src/collectors/base.py` or similar)
2. Add circuit breaker check at the entry point:
   ```python
   from src.services.circuit_breaker import circuit_breaker

   def collect(self):
       if not circuit_breaker.allow(self.source_id):
           logger.warning("Circuit breaker OPEN for %s, skipping", self.source_id)
           return self._get_cached_fallback()  # or raise CircuitBrokenError
       try:
           result = self._do_collect()
           circuit_breaker.record_success(self.source_id)
           return result
       except Exception as e:
           circuit_breaker.record_failure(self.source_id, str(e))
           raise
   ```

**Rules**:
- Each collector needs a stable `source_id` (use collector class name or config key)
- When circuit is open, return cached/fallback data, don't crash
- Log at WARNING level when circuit breaks

---

## Task 3: Integrate Market Signals into Options Engine

**File**: `src/analytics/options_engine.py`

The options engine generates CALL/PUT/NEUTRAL signals. Market signals from the monitor should influence signal confidence.

**What to do**:
1. When generating a signal, check market signals:
   - `demand_indicator > 0.7` → boost CALL confidence by 5%
   - `demand_indicator < 0.3` → boost PUT confidence by 5%
   - `supply_volatility > 0.5` → widen confidence interval
   - `board_composition` (BB ratio) significantly different from historical → flag as anomaly

2. Add to the signal output:
   ```python
   signal["market_context"] = {
       "demand_indicator": demand_signal,
       "supply_volatility": supply_signal,
       "board_composition": bb_ratio,
       "monitor_confidence_modifier": modifier,
   }
   ```

**Rules**:
- Market signals are optional enrichments, not core logic
- Max ±5% confidence adjustment from market signals
- Always include raw signal values in output for transparency

---

## Task 4: Add Monitor Ingest to Scheduled Scan

**File**: Find the scheduled scan runner (likely in `scripts/` or the main scan cycle)

The system_monitor.py output needs to be ingested into MonitorBridge on every scan cycle, not just via API call.

**What to do**:
1. Find where the price scan runs (every 3h cycle)
2. After scan completes, call MonitorBridge.check_health_and_alert()
3. If the monitor skill output JSON is available (saved to `medici-monitor-/skills/monitor/monitor-report/`), load the latest one and call `bridge.ingest_monitor_results(json_data)`

Alternative approach — just add a cron/scheduled call to the API:
```bash
# Every 30 min: health check
curl -X GET https://medici-predict.azurewebsites.net/api/v1/salesoffice/monitor/check

# Every 3h after monitor runs: ingest latest report
latest=$(ls -t monitor-report/monitor-*.json | head -1)
curl -X POST https://medici-predict.azurewebsites.net/api/v1/salesoffice/monitor/ingest \
  -H "Content-Type: application/json" \
  -d @"$latest"
```

---

## Testing

After each task, run the existing tests to verify nothing breaks:
```bash
cd /path/to/medici-price-prediction
python3 -m pytest tests/unit/test_monitor_bridge.py -v
python3 -m pytest tests/unit/test_circuit_breaker.py -v
python3 -m pytest tests/ -v --timeout=60
```

## Important Notes

- Read `CLAUDE.md` for project conventions
- The system is READ-ONLY for Azure SQL — never write to trading DB
- MonitorBridge uses SQLite at `data/monitor_bridge.db` — this is local only
- All new code needs: type hints, docstrings, logging, specific exception handling
- Forward curve weights (50/30/20) must not change
- Market signal influence must be capped and transparent
