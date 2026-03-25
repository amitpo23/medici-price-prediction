# Safety Map — Analytical Cache & Trading Layer

## Baseline: March 25, 2026
- **Commit**: `8cad823` (latest deployed)
- **Tests**: 773 pass / 27 fail (environment-only, not code bugs)
- **Status**: Production deployed, scheduler running, 167 snapshots collected

---

## 🔴 NO-TOUCH ZONE — Never modify these files

These files are deployed, tested, and working. ANY change risks breaking production.

### Core Prediction Engine
| File | Tests | Why |
|------|-------|-----|
| `src/analytics/forward_curve.py` | 120+ | Decay curve + walk forward — THE prediction core |
| `src/analytics/deep_predictor.py` | 40+ | Historical pattern analysis |
| `src/analytics/options_engine.py` | 30+ | Signal generation + packaging |
| `src/analytics/consensus_signal.py` | 25+ | 14-voter consensus — just deployed v2.6.0 |
| `src/analytics/momentum.py` | tested | Velocity/acceleration detection |
| `src/analytics/regime.py` | tested | Market structure detection |
| `src/analytics/path_forecast.py` | 15+ | Turning points + best trade |
| `src/analytics/portfolio_greeks.py` | 20+ | Theta/Delta/Vega/VaR |
| `src/analytics/seasonality.py` | tested | Monthly seasonality indices |

### Data Layer
| File | Why |
|------|-----|
| `src/data/trading_db.py` | Read-only guard — CRITICAL safety |
| `src/analytics/price_store.py` | SQLite snapshots — production data |
| `src/analytics/collector.py` | Price collection — running in production |
| `config/constants.py` | Ensemble weights, caps, thresholds — just tuned |
| `config/settings.py` | Cache config, intervals — production config |

### API Layer
| File | Why |
|------|-----|
| `src/api/main.py` | FastAPI entry point |
| `src/api/routers/_shared_state.py` | Scheduler + cache — just fixed watchdog |
| `src/api/routers/analytics_router.py` | 25 JSON endpoints |
| `src/api/routers/dashboard_router.py` | 12 HTML endpoints |
| `src/api/routers/market_router.py` | 18 market endpoints |
| `src/api/routers/ai_router.py` | 5 AI endpoints |

### UI Templates
| File | Why |
|------|-----|
| `src/templates/command_center.html` | Working 3-column trading dashboard |
| `src/templates/macro_terminal.html` | Working portfolio overview |
| `src/templates/terminal.html` | Working single-hotel view |

---

## 🟡 EXTEND-ONLY ZONE — Add new code, don't change existing

These files can be IMPORTED FROM but not modified:

| File | How to extend |
|------|---------------|
| `src/analytics/forward_curve.py` | Import `build_decay_curve()`, `walk_forward()` — call from NEW files |
| `src/analytics/path_forecast.py` | Import `PathForecast` — consume in NEW analysis |
| `src/analytics/consensus_signal.py` | Import voter results — add new voter via NEW file |
| `src/analytics/price_store.py` | Import `PriceStore` — read snapshots from NEW files |
| `src/utils/cache_manager.py` | Import `CacheManager` — add new cache regions |

---

## 🟢 SAFE CREATION ZONE — New files only

ALL new functionality goes in NEW files. Never modify existing files unless absolutely necessary (and document why).

### Phase 1: Analytical Cache
```
NEW: src/analytics/analytical_cache.py      — Cache DB manager
NEW: src/analytics/cache_aggregator.py       — Nightly aggregation job
NEW: tests/unit/test_analytical_cache.py     — Cache tests
```

### Phase 2: Daily Signals
```
NEW: src/analytics/daily_signals.py          — Per-day signal generation
NEW: tests/unit/test_daily_signals.py        — Signal tests
```

### Phase 3: Demand Zones & Structure
```
NEW: src/analytics/demand_zones.py           — Zone detection algorithm
NEW: src/analytics/structure_breaks.py       — BOS/CHOCH detection
NEW: tests/unit/test_demand_zones.py         — Zone tests
NEW: tests/unit/test_structure_breaks.py     — Structure tests
```

### Phase 4: Accuracy Dashboard
```
NEW: src/analytics/accuracy_dashboard.py     — Accuracy metrics exposure
NEW: tests/unit/test_accuracy_dashboard.py   — Accuracy tests
```

### Phase 5: Trading Execution Layer
```
NEW: src/analytics/trade_setup.py            — Stop/target/sizing/RR
NEW: src/analytics/trade_journal.py          — P&L tracking
NEW: src/analytics/trade_risk.py             — MAE/MFE/drawdown
NEW: tests/unit/test_trade_setup.py          — Setup tests
NEW: tests/unit/test_trade_journal.py        — Journal tests
NEW: tests/unit/test_trade_risk.py           — Risk tests
```

### UI Additions (extend, not replace)
```
NEW: src/templates/partials/signal_timeline.html  — Daily signal strip
NEW: src/templates/partials/demand_zones.html     — Zone panel
NEW: src/templates/partials/trade_setup.html      — Entry/stop/target panel
NEW: src/templates/partials/pnl_tracker.html      — Open P&L panel
NEW: src/templates/partials/greeks_panel.html     — Greeks dashboard
```

---

## 🔒 Integration Points — Minimal, controlled

When new code needs to connect to existing systems, use these controlled integration points:

### 1. Add new API endpoints
**WHERE**: `src/api/routers/analytics_router.py` (append only — add new endpoints at bottom)
**RULE**: Only add NEW @router.get() / @router.post() — never modify existing endpoints

### 2. Add new cache regions
**WHERE**: `config/settings.py` → CACHE_CONFIG dict
**RULE**: Only add new keys, never modify existing TTLs or sizes

### 3. Add scheduler tasks
**WHERE**: `src/api/routers/_shared_state.py` → `_run_collection_cycle()`
**RULE**: Add new function calls at END of cycle, wrapped in try/except

### 4. Add UI panels to Command Center
**WHERE**: `src/templates/command_center.html`
**RULE**: Add new panel divs in RIGHT column below existing panels. Use {% include %} for partials.

### 5. Add new voter to consensus
**WHERE**: Create `src/analytics/zone_voter.py`, register in `consensus_signal.py`
**RULE**: Add voter #15 to the VOTERS list — do NOT modify existing 14 voters

---

## 🔄 Rollback Strategy

### Before each phase:
```bash
git tag pre-phase-X  # Tag current state
git checkout -b phase-X  # Work on branch
```

### If something breaks:
```bash
git checkout main  # Return to safe state
git tag -d pre-phase-X  # Clean up if needed
```

### After phase is validated:
```bash
git checkout main
git merge phase-X
git tag post-phase-X
```

---

## ⚠️ Golden Rules

1. **NEW files first, integration last** — Build and test new functionality in isolation before connecting
2. **773 tests must pass** — Run `pytest tests/` after every integration point
3. **No import cycles** — New files import from existing, never the reverse
4. **No constants changes** — Ensemble weights, caps, thresholds stay frozen
5. **Command Center structure stays** — 3 columns, dark theme, Chart.js v4.4.7
6. **SQLite only** — Analytical cache is a separate .db file, never touch price_store or trading_db
7. **Deploy is separate** — Code is merged, tested, THEN deployed. Never deploy untested code.
