# Medici Price Prediction — Roadmap V2

**Created:** 2026-03-20
**Status:** All original sprints (1.1–4.4) COMPLETE. This document defines the next phase.

---

## System Identity — PRESERVED Principles

These rules are **immutable** and apply to every new sprint:

1. **Decision Brain ONLY** — The system NEVER executes trades, changes prices, or writes to SalesOffice/Azure SQL. It reads and recommends. Execution happens via external skills (insert-opp, price-override) reading SQLite queues.

2. **Read-Only Database** — `src/data/trading_db.py` SQLAlchemy event listener blocks INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/EXEC. Never disable.

3. **Claude AI Fallback** — Every AI feature works without an API key via rule-based fallback. Claude API is never a hard dependency.

4. **Ensemble Weights** — 50% Forward Curve / 30% Historical / 20% ML. Don't change without A/B testing evidence.

5. **4-Layer Architecture** — Data Collection → Prediction Engine → AI Intelligence → API & Dashboard. Keep layers clean.

---

## CALL/PUT Signal Definitions — PRESERVED

### What CALL Means (Buy Opportunity)
```
A room contract is a CALL when the prediction engine expects the price to RISE
before check-in, creating a buy opportunity NOW at a lower price.

Trigger conditions:
  - P_up ≥ 70% → CALL with High confidence
  - P_up ≥ 60% + positive acceleration → CALL with Medium confidence
  - Regime NOT in (STALE, VOLATILE)
  - Data quality NOT "low"

Execution via Opportunity Queue:
  - push_price = buy_price + $50 (FIXED_MARKUP_USD)
  - Eligibility: predicted_price - buy_price ≥ $50 (MIN_PROFIT_USD)
  - Queue states: pending → picked → done/failed
  - External insert-opp skill creates BackOfficeOPT + MED_Opportunities in Azure SQL
  - BuyRoom WebJob executes the actual purchase
```

### What PUT Means (Price Override / Protect)
```
A room contract is a PUT when the prediction engine expects the price to DROP,
and the current price should be overridden downward to stay competitive.

Trigger conditions:
  - P_down ≥ 70% → PUT with High confidence
  - P_down ≥ 60% + negative acceleration → PUT with Medium confidence
  - Regime NOT in (STALE, VOLATILE)
  - Data quality NOT "low"

Execution via Override Queue:
  - target_price = current_price - discount_usd
  - Guardrails: MAX_DISCOUNT_USD = $10, MIN_TARGET_PRICE_USD = $50
  - Queue states: pending → picked → done/failed
  - External price-override skill pushes to Zenith
```

### What NONE Means (Hold / No Action)
```
No clear directional signal. Reasons:
  - Neither P_up nor P_down reaches 60% threshold
  - Regime is STALE or VOLATILE (unreliable data)
  - Data quality is "low" (fewer than 7 observations)
  - Acceleration conflicts with probability direction
```

### Market Context Modifiers (MonitorBridge)
```
Confidence can shift ±1 tier based on live market signals:
  - demand_indicator > 0.7 + CALL → Med upgrades to High
  - demand_indicator < 0.3 + PUT → Med upgrades to High
  - supply_volatility > 0.5 + High → downgrades to Med
  - monitor_confidence_modifier ≤ -0.30 + High → downgrades to Med
  - monitor_confidence_modifier ≤ -0.40 → downgrades to Low
```

### Signal Suppression Rules
```
Signals are suppressed (forced to NONE) when:
  - regime ∈ {STALE, VOLATILE}
  - confidence_quality = "low"
  - Data density < 7 observations (DATA_DENSITY_MEDIUM)
```

---

## Supporting Engine Definitions — PRESERVED

### Momentum Detection
```
Velocity: 3h, 24h, 72h rates from price scan history
Acceleration: velocity_24h - velocity_72h
Signals: ACCELERATING_UP | ACCELERATING_DOWN | NORMAL | INSUFFICIENT_DATA
Threshold: |momentum_vs_expected| > 2 × volatility
```

### Regime Detection
```
Regimes: NORMAL | TRENDING_UP | TRENDING_DOWN | VOLATILE | STALE
Z-score: (actual_change - expected_change) / (std × √days)
  - |z| > 2.0 → TRENDING_UP/DOWN
  - |z| > 3.0 → warning alert level
  - Scan volatility > 2× expected → VOLATILE
  - Price unchanged across 16+ scans → STALE
```

### Rules Engine Pipeline (11 rule types)
```
Order: hold_until_drop → exclude_category → exclude_board → price_ceiling →
       target_price → max_rooms → markup_pct/fixed → price_floor →
       auto_close_threshold → preferred_category
Actions: ACCEPT / REJECT / MODIFY / HOLD
```

### Forward Curve
```
Bayesian-smoothed decay curve: T → expected daily % change
Enrichments: events (+0.03–0.40%), seasonality (×3.0 multiplier),
  demand (±0.15%), weather (-0.15% to +0.02%), competitors (±0.20%),
  cancellations (-0.25% max), provider (±0.20%)
Confidence: 95% CI bands (Z=1.96), adjusted by data density
```

---

## Completed Sprints (v1) — Reference

| Sprint | What | Status |
|--------|------|--------|
| 1.1 | Test infrastructure (pytest, conftest, GitHub Actions) | ✅ |
| 1.2 | Integration tests — 26 tests | ✅ |
| 1.3 | Unit tests — 504+ tests | ✅ |
| 1.4 | Exception handling — 81 bare except fixed | ✅ |
| 1.5 | Config validation — `config_validator.py` | ✅ |
| 2.1 | Router split — monolith → 5 sub-routers | ✅ |
| 2.2 | Unified CacheManager — 8→1, 47 tests | ✅ |
| 2.3 | Jinja2 template extraction — 11 page generators | ✅ |
| 2.4 | Collector registry auto-discovery | ✅ |
| 2.5 | Constants extraction — 30+ magic numbers | ✅ |
| 3.1 | API pagination | ✅ |
| 3.2 | Structured JSON logging + correlation IDs | ✅ |
| 3.3 | Rate limiting + API auth + CORS | ✅ |
| 3.4 | Health check dashboard | ✅ |
| 4.1 | Prediction accuracy tracker | ✅ |
| 4.2 | Real-time alert system | ✅ |
| 4.3 | Data quality scoring | ✅ |
| 4.4 | Scenario analysis engine | ✅ |

**Bonus features (not planned, delivered):**
- Path Forecast Engine + dashboard
- Raw Source Analyzer + dashboard
- Forward Curve raw mode
- Trading Terminal (dark-themed decision dashboard)
- Opportunity Queue (CALL execution)
- Override Queue (PUT execution)
- MonitorBridge market context integration

---

## Phase 2: Tech Debt Cleanup

### Sprint TD-1: Remaining Jinja2 Extraction
**Goal:** Move all remaining inline HTML generators to `render_template()`

| File | Lines | Status |
|------|-------|--------|
| `src/analytics/terminal_page.py` | 772 | HTML inline |
| `src/analytics/alerts_page.py` | 121 | HTML inline |
| `src/api/routers/_options_html_gen.py` | 3,500+ | HTML inline |

**Deliverables:**
- Extract each to `src/templates/{name}.html`
- Use `render_template(name, **context)` pattern from `template_engine.py`
- Zero behavior change — output HTML must be identical
- Unit tests for each template render

### Sprint TD-2: Collector Test Coverage
**Goal:** Unit tests for all collectors in `src/collectors/`

| Collector | File | Tests |
|-----------|------|-------|
| Weather | `weather_collector.py` | 0 → 8+ |
| Market | `market_collector.py` | 0 → 8+ |
| Events | `events_collector.py` | 0 → 8+ |
| Trading | `trading_collector.py` | 0 → 8+ |
| CBS | `cbs_collector.py` | 0 → 6+ |
| BrightData | `brightdata_collector.py` | 0 → 6+ |
| Registry | `registry.py` | 0 → 10+ |

**Pattern:** Mock external APIs, test parsing logic, test error handling, test `COLLECTOR_{NAME}_ENABLED` toggle.

---

## Phase 3: Trading System Enhancements

### Sprint 5.1: Portfolio Greeks & VaR
**Goal:** Calculate options-style Greeks for hotel room contracts

**New file:** `src/analytics/portfolio_greeks.py`

```
Greeks definitions (hotel room context):

Theta (Time Decay):
  - How much value a room contract loses per day as check-in approaches
  - θ = ΔP/Δt from forward curve daily step
  - Negative when expected price rises (holding cost)
  - Positive when expected price falls (time is your friend)

Delta (Price Sensitivity):
  - Portfolio value change for $1 change in room price
  - δ = ∂V/∂S where V = predicted_price - current_price
  - For CALL positions: delta ≈ P_up (probability of profit)
  - For PUT overrides: delta ≈ -P_down

Vega (Volatility Sensitivity):
  - How much the prediction changes if volatility shifts by 1%
  - ν = ∂V/∂σ from forward curve volatility per T
  - High vega = uncertain prediction, more scenario-sensitive

Portfolio VaR (Value at Risk):
  - Maximum expected loss at 95% confidence over 1 day
  - VaR = Σ(position_value × σ_1d × 1.645) across all positions
  - Uses per-room σ from forward curve

Portfolio CVaR (Conditional VaR):
  - Expected loss GIVEN we exceed VaR threshold
  - CVaR = E[Loss | Loss > VaR]
```

**API Endpoints:**
- `GET /api/v1/salesoffice/greeks` — Portfolio-level Greeks summary
- `GET /api/v1/salesoffice/greeks/{hotel_id}` — Per-hotel Greeks
- `GET /api/v1/salesoffice/greeks/var` — VaR/CVaR calculation

**Dashboard:** New panel in Trading Terminal showing Greeks gauges

**Constants** (add to `config/constants.py`):
```python
VAR_CONFIDENCE = 0.95
VAR_HORIZON_DAYS = 1
GREEKS_MIN_DATA_POINTS = 5
```

### Sprint 5.2: Position Tracking & PnL
**Goal:** Track what was bought/overridden and calculate profit/loss

**New file:** `src/analytics/position_tracker.py`

```
Position model:
  - entry_price (what we paid / pushed)
  - entry_date (when)
  - current_price (latest scan)
  - predicted_exit_price (forward curve at T=0)
  - unrealized_pnl = current_price - entry_price
  - realized_pnl = exit_price - entry_price (after check-in)
  - status: OPEN / CLOSED / EXPIRED

Data source: opportunity_queue.db (CALL) + override_queue.db (PUT)
  - status=done → position opened
  - Check-in passed → position closed, scored

Position limits (guardrails):
  - MAX_EXPOSURE_PER_HOTEL = configurable
  - MAX_TOTAL_POSITIONS = configurable
  - CONCENTRATION_WARNING = 30% in single hotel
```

**API Endpoints:**
- `GET /api/v1/salesoffice/positions` — All open positions
- `GET /api/v1/salesoffice/positions/pnl` — PnL summary (realized + unrealized)
- `GET /api/v1/salesoffice/positions/{hotel_id}` — Per-hotel positions

**Dashboard:** PnL dashboard with daily/cumulative charts

### Sprint 5.3: Attribution Analysis
**Goal:** Decompose what drives prediction accuracy and PnL

**New file:** `src/analytics/attribution.py`

```
Attribution factors:
  1. Forward Curve contribution (50% weight impact)
  2. Historical Pattern contribution (30% weight impact)
  3. ML Model contribution (20% weight impact)
  4. Event enrichment impact (Art Basel, holidays, etc.)
  5. Seasonality impact
  6. Demand (flights) impact
  7. Weather impact
  8. Momentum timing benefit
  9. Regime detection benefit (avoided bad signals)

Method: Shapley-style decomposition
  - Run prediction with/without each factor
  - Delta = factor's marginal contribution to final price
  - Aggregate over all scored predictions

Rolling windows: 7-day, 30-day, 90-day attribution
```

**API Endpoints:**
- `GET /api/v1/salesoffice/attribution` — Factor attribution summary
- `GET /api/v1/salesoffice/attribution/{hotel_id}` — Per-hotel attribution
- `GET /api/v1/salesoffice/attribution/signals` — CALL vs PUT success breakdown

### Sprint 5.4: Execution Quality & Slippage
**Goal:** Track how well execution matches predictions

**New file:** `src/analytics/execution_quality.py`

```
Metrics:
  - Slippage: |predicted_price - actual_execution_price|
  - Fill rate: % of queued opportunities that became done
  - Rejection rate: % failed
  - Timing score: Did we execute at optimal T?
  - Price improvement: actual vs predicted at queue time

Data source: opportunity_queue.db + override_queue.db
  - Compare predicted_price at queue time vs actual outcome
  - Track time from pending → done (execution latency)
```

**API Endpoints:**
- `GET /api/v1/salesoffice/execution/quality` — Execution metrics
- `GET /api/v1/salesoffice/execution/slippage` — Slippage analysis

---

## Phase 4: Advanced Analytics

### Sprint 6.1: Cross-Hotel Correlation Matrix
**Goal:** Understand price co-movement across Miami hotels

**New file:** `src/analytics/correlation.py`

```
Correlation types:
  - Hotel-to-hotel: Do prices move together?
  - Category-to-category: Standard vs Deluxe dynamics
  - Board-to-board: RO vs BB co-movement
  - Seasonal patterns: Do all hotels peak together?

Method: Rolling Pearson correlation on daily % changes
Window: 30-day rolling
Output: N×N correlation matrix + heatmap
```

**API:** `GET /api/v1/salesoffice/correlation`
**Dashboard:** Interactive heatmap in Trading Terminal

### Sprint 6.2: Adaptive Signal Weighting
**Goal:** Learn which signals perform best in which conditions

**New file:** `src/analytics/meta_learner.py`

```
Approach:
  - Track signal accuracy by: regime, T-range, hotel, season
  - Adjust 50/30/20 weights dynamically per context
  - Consensus scoring: how many sub-signals agree?
  - Guardrail: weights stay within ±20% of base (30/50 → 50/70 max range)

NOT changing the base constants — this is a dynamic overlay.
config/constants.py remains the source of truth for defaults.
```

### Sprint 6.3: Real-Time Streaming Alerts
**Goal:** Proactive alerts on live price movements

**New file:** `src/analytics/streaming_alerts.py`

```
Alert types:
  - BAND_BREACH: Price exits confidence band
  - REGIME_CHANGE: Room transitions to different regime
  - MOMENTUM_SHIFT: Acceleration reverses direction
  - STALE_DATA: Source hasn't updated in expected interval
  - MODEL_DEGRADATION: Rolling accuracy drops below threshold
  - SIGNAL_FLIP: CALL → PUT or PUT → CALL
```

### Sprint 6.4: Audit Trail & Compliance
**Goal:** Complete decision trail for every signal and action

**New file:** `src/analytics/audit_trail.py`

```
Logged events:
  - Every CALL/PUT signal generated (with all inputs)
  - Every queue insertion (opportunity + override)
  - Every rule application and result
  - Every parameter change
  - Every manual override

Storage: SQLite audit_trail.db
Retention: 365 days
API: GET /api/v1/salesoffice/audit?from=&to=&hotel_id=
```

---

## Implementation Priority

| Priority | Sprint | Impact | Effort | Dependency |
|----------|--------|--------|--------|------------|
| 1 | TD-1 | Low (cleanup) | Low | None |
| 2 | TD-2 | Medium (reliability) | Medium | None |
| 3 | 5.1 | **High** (risk visibility) | Medium | None |
| 4 | 5.2 | **High** (PnL tracking) | High | 5.1 |
| 5 | 5.3 | **High** (learning) | Medium | 5.2 |
| 6 | 5.4 | Medium (execution) | Medium | 5.2 |
| 7 | 6.1 | Medium (diversification) | Medium | None |
| 8 | 6.2 | High (accuracy) | High | 5.3 |
| 9 | 6.3 | Medium (monitoring) | Medium | None |
| 10 | 6.4 | Medium (compliance) | Low | None |

---

## Key Numbers (Current)

- **23 hotels**, **4,047 rooms** in production
- **90+ API endpoints** across 5 sub-routers
- **504+ unit tests**, **26 integration tests**
- **12 active data sources**
- **~32,000 lines** of Python code
- Deployed on **Azure App Service B2** (Always On)
