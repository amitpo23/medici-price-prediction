# Medici Price Prediction — Session Primer

## Current State (2026-03-26)

### Production
- **Azure B2**, Always On, 22 hotels, ~4,000 rooms
- **Deploy zip:** 623 files (2.5MB)
- **Tests:** 1,387 passed + 2 skipped, 44.5% coverage
- **All endpoints 200** — status, home, options, dashboard, trading, consensus, health
- **Branch:** main (Phase 1-4 + TD-1 + TD-2 complete)
- **Latest commit:** `de16f9d`

### Session 2026-03-26 — Production Stabilization + Innstant Onboarding
- Fixed `/status` and `/home` 500 errors (SQLite path not writable on Azure)
- Sprint TD-1: removed 3,503 lines dead legacy HTML from `_options_html_gen.py`
- Sprint TD-2: enabled 76 collector tests (kaggle OSError fix)
- Pushed Phase 4 Advanced Analytics to GitHub
- Updated SKILL.md with Phase 1+2 documentation
- **Innstant Hotel Onboarding Response** — Responding to Innstant letter about 30 hotels:
  - Set pricing (Fixed $1000, Aug 1-10) for ALL room types × ALL rate plans on 13/28 hotels
  - Checked each hotel's room types via Bulk Update (Select All rooms + Select All rate plans)
  - Found Fontainebleau has 5 room types, most others have only Standard
  - Rate plan variations: bb, Bed and Breakfast, bed and brekfast, ro, room only, Refundable
  - 15 hotels remaining: Belleza, Chelsea, Croydon, Gaythering, InterContinental, Kimpton Anglers, Kimpton Palomar, Loews, Metropole, Miami Airport, Notebook, SERENA, Albion, Catalina, Gates, Landon, Villa Casa
  - Availability NOT set (per user instruction)
  - Innstant static sync still pending

### Phase 1 — Analytical Cache + Trading Layer (2026-03-25)

**Status:** COMPLETE — All 4 phases built, tested, integrated, and merged to main.

#### What Was Built (branch: `phase-1-analytical-cache`)

8 new files, 256 new tests (Phase 1: 217 + Phase 2: 39):

| File | Lines | Tests | What It Does |
|------|-------|-------|-------------|
| `src/analytics/analytical_cache.py` | ~1,080 | 62 | 3-layer SQLite cache with 13 tables |
| `src/analytics/daily_signals.py` | ~200 | 35 | Per-day CALL/PUT/NEUTRAL from forward curve |
| `src/analytics/demand_zones.py` | ~350 | 30 | ICT/SMC support/resistance + BOS + CHOCH |
| `src/analytics/trade_setup.py` | ~560 | 51 | Stop-loss, take-profit, Kelly sizing, RR |
| `src/analytics/cache_aggregator.py` | ~800 | 39 | Azure SQL → SQLite pipeline (all tables) |
| `docs/SAFETY_MAP.md` | ~150 | — | NO-TOUCH / EXTEND-ONLY / SAFE zones |
| `src/api/routers/trading_router.py` | ~320 | 39 | 12 API endpoints: signals, zones, setups, search, rebuy, cache |
| `tests/unit/test_trading_router.py` | ~400 | — | Tests for trading_router + scheduler integration |

#### Modified Files (Phase 2 Integration)
| File | What Changed |
|------|-------------|
| `src/api/routers/_shared_state.py` | Added `_get_analytical_cache()`, `_get_cache_aggregator()`, `_refresh_analytical_cache_daily()`, `_refresh_analytical_cache_signals()` — wired into scheduler cycle |
| `src/api/analytics_dashboard.py` | Added `trading_router` import + `router.include_router(trading_router)` |

#### Files to NEVER Delete
All 8 files above are NEW and must be preserved.

---

## Analytical Cache Architecture

### 3 Layers in SQLite (`data/analytical_cache.db`)

```
Layer 1 — Reference (startup, once)
├── ref_hotels          — hotel_id, name, city, stars
├── ref_categories      — room categories
└── ref_boards          — board types (BB, HB, etc.)

Layer 2 — Market Intelligence (nightly refresh)
├── agg_market_daily    — avg/min/max prices per hotel+date+room (from PriceHistory)
├── agg_competitor_matrix — hotel vs competitor pricing relationships
├── agg_search_daily    — 3 price points: sell/net/bar from SearchResultsSessionPollLog
├── agg_margin_spread   — sell vs net vs bar spread (profit signal)
├── agg_search_volume   — search count trends (demand indicator)
├── rebuy_signals       — cancellation rebuy events from MED_CancelBook
└── price_overrides     — human pricing decisions from SalesOffice.PriceOverride

Layer 3 — Real-Time Signals (every 3h with scheduler)
├── daily_signals       — per-day CALL/PUT/NEUTRAL with confidence
├── demand_zones        — support/resistance levels with touch_count + strength
├── structure_breaks    — BOS (Break of Structure) + CHOCH (Change of Character)
├── trade_setups        — entry/stop/target/RR/position_size per room
└── trade_journal       — P&L tracking with MAE/MFE
```

### Azure SQL Data Sources

| Table | Rows | What It Gives Us | Used In |
|-------|------|------------------|---------|
| `SalesOffice.PriceHistory` | ~8.5M | OldPrice/NewPrice/ChangePct per scan | agg_market_daily, demand_zones, volatility |
| `SearchResultsSessionPollLog` | 8.4M | 3 price points: PriceAmount, NetPriceAmount, BarRateAmount + provider + cancellation | agg_search_daily, margin_spread, arbitrage |
| `MED_CancelBook` | 4,697 | Cancellation reasons — "Last Price Update Job" = rebuy signal | rebuy_signals |
| `MED_PreBook` | 10,791 | Provider who gave best price, cancellation window, payment type | provider intelligence |
| `SalesOffice.PriceOverride` | 866 | Manual price changes (human intelligence signal) | price_overrides |
| `SalesOffice.MappingMisses` | 208 | Unmapped rooms (market gaps) | market gap analysis |
| `SalesOffice.Details` + `Orders` | ~50K active | Current active room prices + check-in dates | ref data, forward curve |
| `AI_Search_HotelData` | 8.5M | Competitor pricing from 323 cities | competitor_matrix |
| `Med_Hotels` | 23 | Hotel reference (name, ID) | ref_hotels |
| `MED_Book` | ~50K | Booking records (cost paid to supplier) | med_book predictions |

---

## How Each Module Works

### 1. `analytical_cache.py` — AnalyticalCache class

**Purpose:** SQLite database manager for all 13 tables.

**Key Methods:**
```python
cache = AnalyticalCache()                    # or AnalyticalCache(db_path=Path(...))

# Layer 1
cache.upsert_hotels(hotels: list[dict])      → int  # count upserted
cache.get_hotels()                            → list[dict]
cache.get_hotel(hotel_id)                     → dict | None

# Layer 2 — Market
cache.upsert_market_daily(rows)              → int
cache.get_market_daily(hotel_id, days_back=90) → list[dict]
cache.upsert_competitor_matrix(rows)          → int
cache.get_competitors(hotel_id)               → list[dict]

# Layer 2 — Search Intelligence (3 price points)
cache.save_search_daily(rows)                → int   # sell/net/bar prices
cache.get_search_daily(hotel_id, days_back=30) → list[dict]
cache.save_margin_spread(rows)               → int   # profit spread
cache.save_search_volume(rows)               → int   # demand indicator

# Layer 2 — Trading Intelligence
cache.save_rebuy_signals(rows)               → int   # cancellation rebuys
cache.get_rebuy_activity(hotel_id=0)         → list[dict]
cache.save_price_overrides(rows)             → int   # human decisions
cache.get_price_override_signals(hotel_id)   → list[dict]

# Layer 3 — Signals
cache.save_daily_signals(signals)            → int
cache.get_daily_signals(detail_id, days_forward=30) → list[dict]
cache.get_hotel_daily_signals(hotel_id, signal_date) → list[dict]

# Layer 3 — Zones
cache.save_demand_zones(zones)               → int
cache.get_demand_zones(hotel_id, category=None, active_only=True) → list[dict]

# Layer 3 — Trade Setups
cache.save_trade_setups(setups)              → int
cache.get_trade_setups(hotel_id=None, signal=None, min_rr=0) → list[dict]
cache.get_trade_setup(detail_id)             → dict | None

# Layer 3 — Trade Journal
cache.log_trade(trade: dict)                 → int  # trade_id
cache.get_trade_journal(hotel_id=None, days_back=90) → list[dict]
cache.get_trade_stats()                      → dict  # win_rate, profit_factor, etc.

# Layer 3 — Structure Breaks
cache.save_structure_breaks(breaks)          → int
cache.get_structure_breaks(hotel_id, days_back=30) → list[dict]

# Metadata
cache.get_freshness()                        → dict  # {table: {count, latest}}
cache.clear_layer(layer: int)                → None  # 1, 2, or 3
```

**Verification:**
```bash
pytest tests/unit/test_analytical_cache.py -v --override-ini="addopts="
# Expects: 62 passed (including search, rebuy, override tests)
```

### 2. `daily_signals.py` — Per-Day Signal Generation

**Purpose:** Convert forward curve points to per-day CALL/PUT/NEUTRAL signals.

**Thresholds:** `≥+0.5%` → CALL, `≤-0.5%` → PUT, else NEUTRAL

**Key Functions:**
```python
from src.analytics.daily_signals import generate_daily_signals, summarize_signals

signals = generate_daily_signals(
    forward_curve_points,     # list[dict] with date, t, predicted_price, daily_change_pct
    detail_id=100,
    hotel_id=1,
    enrichments=None,         # optional overrides like {"event_adj_pct": 0.05}
)
# Returns: list[dict] with signal_date, t_value, predicted_price, daily_change_pct,
#          signal ("CALL"/"PUT"/"NEUTRAL"), confidence (0-1), enrichments

summary = summarize_signals(signals)
# Returns: {total, calls, puts, neutrals, trend, next_7_days: {signals, calls, puts}}
```

**Confidence formula:** Based on 3 factors:
- Magnitude of daily change (higher = more confident)
- Enrichment agreement (same direction = boost, opposite = penalty)
- T-proximity (closer to check-in = more confident)

**Verification:**
```bash
pytest tests/unit/test_daily_signals.py -v --override-ini="addopts="
# Expects: 35 passed
```

### 3. `demand_zones.py` — ICT/SMC Zone Detection

**Purpose:** Detect support/resistance zones from price history reversals.

**Key Functions:**
```python
from src.analytics.demand_zones import detect_demand_zones, detect_structure_breaks

zones = detect_demand_zones(
    price_history_df,          # DataFrame with room_price, snapshot_ts columns
    hotel_id=1,
    category="standard",       # optional filter
)
# Returns: list[dict] with zone_id, hotel_id, category, zone_type (SUPPORT/RESISTANCE),
#          price_lower, price_upper, touch_count, strength, first_touch, last_touch

breaks = detect_structure_breaks(
    price_history_df,
    hotel_id=1,
    category="standard",
    demand_zones=zones,        # optional — will mark zones as broken
)
# Returns: list[dict] with break_id, break_type (BOS/CHOCH), direction (BULLISH/BEARISH),
#          break_price, previous_level, significance
```

**Zone detection algorithm:**
1. Find local min/max reversals (requires `MIN_REVERSAL_PCT` = 1% swing)
2. Cluster reversals within `ZONE_TOLERANCE_PCT` = 3% price range
3. Require `MIN_TOUCHES` = 2+ touches to form a zone
4. Strength is recency-weighted (14-day half-life exponential decay)

**BOS/CHOCH detection:**
- BOS: Price breaks above previous swing high (bullish) or below swing low (bearish)
- CHOCH: HH→LH transition (bearish) or LL→HL transition (bullish)

**Verification:**
```bash
pytest tests/unit/test_demand_zones.py -v --override-ini="addopts="
# Expects: 30 passed
```

### 4. `trade_setup.py` — Trade Setup Calculator

**Purpose:** For each CALL/PUT signal, compute complete trade setup with entry/stop/target/RR/sizing.

**Key Functions:**
```python
from src.analytics.trade_setup import compute_trade_setup, batch_compute_setups, TradeSetup

setup = compute_trade_setup(
    detail_id=100, hotel_id=1,
    current_price=200.0,
    signal="CALL",               # or "PUT"
    confidence=0.75,
    sigma_1d=2.0,                # daily volatility %
    t_value=14,                  # days to check-in
    path_forecast=None,          # optional: {"best_sell_price": 230}
    demand_zones=None,           # optional: list of zone dicts
    turning_points=None,         # optional: list of TP dicts
    win_rate=0.60,               # optional: for Kelly sizing
    avg_win_pct=3.0,             # optional: for Kelly sizing
    avg_loss_pct=2.0,            # optional: for Kelly sizing
    max_risk_usd=100.0,
)
# Returns: TradeSetup dataclass

# Batch version:
setups = batch_compute_setups(options, demand_zones_by_hotel, trade_stats, max_risk_usd)
```

**Stop-loss priority:** demand_zone → turning_point → volatility (2× σ × √holding_days)
**Take-profit priority:** path_forecast → demand_zone → RR-based (1.5× stop distance)
**Position sizing:** Kelly criterion (half-Kelly) if stats available, else simple max-risk
**Quality rating:** high (RR≥2.0, conf≥0.70) → medium (RR≥1.5, conf≥0.50) → low → skip

**Constants:**
- `STOP_VOL_MULTIPLIER` = 2.0
- `MIN_STOP_DISTANCE_PCT` = 1.5%
- `MAX_STOP_DISTANCE_PCT` = 15.0%
- `MIN_RISK_REWARD` = 1.0
- `DEFAULT_MAX_RISK_USD` = $100
- `KELLY_FRACTION` = 0.5 (half-Kelly)

**Verification:**
```bash
pytest tests/unit/test_trade_setup.py -v --override-ini="addopts="
# Expects: 51 passed
```

### 5. `cache_aggregator.py` — Azure SQL → Cache Pipeline

**Purpose:** Pull data from ALL Azure SQL tables into the analytical cache.

**Key Class:**
```python
from src.analytics.cache_aggregator import CacheAggregator

agg = CacheAggregator()                        # uses default cache
agg = CacheAggregator(cache=my_cache)           # or provide one

# Full refresh (all layers)
result = agg.full_refresh(days_back=90)
# Returns: {layer1_hotels, layer2_market_daily, layer2_competitors,
#           layer2_search_daily, layer2_margin_spread, layer2_search_volume,
#           layer2_rebuy_signals, layer2_price_overrides}

# Individual refreshes
agg.refresh_reference_data()                    # Layer 1
agg.refresh_market_data(days_back=90)           # Layer 2 market
agg.refresh_search_intelligence(days_back=30)   # Layer 2 search results
agg.refresh_trading_signals(days_back=30)       # Layer 2 rebuy+overrides

# Raw data queries (returns DataFrame)
agg.get_price_history(hotel_id, days_back=90)   # PriceHistory for one hotel
agg.get_all_price_history(days_back=90)         # PriceHistory all hotels
agg.get_volatility_data(days_back=90)           # STDEV per hotel+room
agg.get_price_drops(days_back=3)                # Biggest drops (CALL opportunities)
agg.get_price_trend(hotel_id, date_from, room_category, room_board)

# SearchResultsSessionPollLog queries
agg.get_search_results_daily(days_back=30)      # 3 price points aggregated
agg.get_provider_prices(hotel_id, days_back=7)  # Who gives best price?
agg.get_margin_spread(days_back=30)             # Sell vs net vs bar spread
agg.get_search_volume(days_back=30)             # Demand indicator
agg.get_arbitrage_opportunities(days_back=3)    # >15% margin opportunities

# Trading intelligence
agg.get_cancel_book()                           # Full cancellation history
agg.get_rebuy_signals(days_back=30)             # "Last Price Update" rebuys
agg.get_prebook_data(days_back=30)              # Provider pricing intel
agg.get_price_overrides()                       # Human pricing decisions
agg.get_mapping_misses()                        # Unmapped rooms (market gaps)

# Analysis pipelines
agg.run_demand_zone_analysis(hotel_id, category="", days_back=90)
agg.run_all_demand_zones(days_back=90)
```

**SQL Tables Used:**
- `SalesOffice.PriceHistory` — price changes (OldPrice, NewPrice, ChangePct, ScanDate)
- `SearchResultsSessionPollLog` — 8.4M search results (PriceAmount, NetPriceAmount, BarRateAmount)
- `MED_CancelBook` + `MED_Book` — cancellation rebuys
- `MED_PreBook` — pre-booking provider data
- `SalesOffice.PriceOverride` + `SalesOffice.Details` + `SalesOffice.Orders` — human overrides
- `SalesOffice.MappingMisses` — unmapped rooms
- `AI_Search_HotelData` — competitor matrix

**DB Access:** Uses `trading_db.get_trading_engine()` with read-only enforcement. User: `prediction_reader`.

**Verification:**
```bash
pytest tests/unit/test_cache_aggregator.py -v --override-ini="addopts="
# Expects: 39 passed
```

### 6. `docs/SAFETY_MAP.md` — Safety Architecture

Defines NO-TOUCH (red), EXTEND-ONLY (yellow), and SAFE CREATION (green) zones.
**Golden Rules:**
1. New files first — never modify existing files unless extending
2. All existing tests must pass after every change
3. No import cycles between new and existing code
4. No changes to `config/constants.py` ensemble weights

---

## How to Verify Everything Works

```bash
# Run ALL new tests (should be 217 passed)
pytest tests/unit/test_analytical_cache.py \
       tests/unit/test_daily_signals.py \
       tests/unit/test_trade_setup.py \
       tests/unit/test_demand_zones.py \
       tests/unit/test_cache_aggregator.py \
       -v --override-ini="addopts="

# Run ALL unit tests (skip env-dependent ones)
pytest tests/unit/ --override-ini="addopts=" -q \
  --ignore=tests/unit/test_api_analytics.py \
  --ignore=tests/unit/test_api_market.py \
  --ignore=tests/unit/test_dashboard_router.py \
  --ignore=tests/unit/test_rate_limiting.py \
  --ignore=tests/unit/test_scenario_engine.py \
  --ignore=tests/unit/test_analytics_router_source_modes.py \
  --ignore=tests/unit/test_collectors.py \
  --ignore=tests/unit/test_pagination.py \
  --ignore=tests/unit/test_shared_state.py

# Compile check all new files
python -m py_compile src/analytics/analytical_cache.py
python -m py_compile src/analytics/daily_signals.py
python -m py_compile src/analytics/demand_zones.py
python -m py_compile src/analytics/trade_setup.py
python -m py_compile src/analytics/cache_aggregator.py
```

---

## Smart Caching & Query Reduction Strategy

**Problem:** Azure SQL has 8.5M+ row tables. Without caching, every analysis run queries the same data repeatedly, overloading the DB and slowing everything down.

**Solution:** 3-tier caching — query once, reuse many times:

### Tier 1: Static Reference (query ONCE at startup, reuse forever)
```
ref_hotels, ref_categories, ref_boards
→ Query Azure SQL once → save to SQLite → never query again until restart
→ Estimated: 23 hotels + ~30 categories + ~10 boards = ~63 rows total
→ Refresh trigger: app restart or manual /api/cache/refresh
```

### Tier 2: Aggregated Intelligence (query ONCE nightly, reuse all day)
```
agg_market_daily        → Pre-aggregated from 8.5M PriceHistory → ~50K rows
agg_search_daily        → Pre-aggregated from 8.4M SearchResults → ~20K rows
agg_margin_spread       → Sell vs net vs bar spread per hotel+day → ~5K rows
agg_search_volume       → Search count trends → ~5K rows
agg_competitor_matrix   → Hotel vs competitor relationships → ~200 rows
rebuy_signals           → Cancellation rebuys → ~100 rows
price_overrides         → Human decisions → ~866 rows
```
**Key insight:** Instead of querying 8.5M rows every time, we query ONCE at night, aggregate (GROUP BY hotel+date+room), and store ~50K pre-computed rows in SQLite. Every subsequent request reads from local SQLite in <10ms instead of hitting Azure SQL.

### Tier 3: Computed Signals (recalculate every 3h, cached in SQLite)
```
daily_signals      → Derived from forward_curve + enrichments (no Azure query needed)
demand_zones       → Derived from Tier 2 market data (no extra Azure query)
trade_setups       → Derived from signals + zones (pure computation)
structure_breaks   → Derived from zones + price data (pure computation)
trade_journal      → Write-once from trade execution (no query)
```
**Key insight:** Layer 3 NEVER touches Azure SQL directly. It reads from the pre-cached Layer 2 data in SQLite. This means the 3-hourly signal refresh is pure local computation.

### Query Budget Per Day

| When | What | Azure SQL Queries | Rows Scanned |
|------|------|-------------------|-------------|
| Startup | Reference data | 3 | ~100 |
| Night (1am) | Market aggregation | 2 | ~8.5M (once!) |
| Night (1am) | Search intelligence | 3 | ~8.4M (once!) |
| Night (1am) | Trading signals | 2 | ~15K |
| Every 3h | Price collection | 1 | ~4K (existing) |
| Every 3h | Signal generation | **0** | **0** — reads from SQLite |
| On-demand | Specific hotel drill-down | 1 | ~5K max |
| **TOTAL per day** | | **~19 queries** | **~17M rows (compressed to ~80K cached)** |

**Before:** Every API request → Azure SQL query → 8.5M rows scanned
**After:** Night batch → SQLite cache → all day local reads in milliseconds

### Data Deduplication Rules
- PriceHistory rows with same hotel+date+room+board: keep the LATEST ScanDate only
- SearchResults with same hotel+date+room: aggregate (AVG, MIN, MAX, COUNT)
- Competitor matrix: one row per hotel pair, overwrite on refresh
- Demand zones: deterministic zone_id (hash of hotel+category+type+price), upsert

### When to Re-Query Azure SQL
- **Forced refresh:** `POST /api/cache/refresh` — full Layer 1+2 rebuild
- **Stale data alert:** If `cache.get_freshness()` shows any table older than 25 hours
- **New hotel added:** Triggers Layer 1 refresh
- **Manual override:** After human price override, refresh that hotel's data only

### Learning & Pattern Memory
The `trade_journal` table accumulates trade outcomes over time. After 20+ trades:
- `get_trade_stats()` returns win_rate, profit_factor, avg_win_pct, avg_loss_pct
- Kelly criterion automatically uses these stats for position sizing
- The system gets smarter with every trade — no manual tuning needed
- Demand zone strength decays with a 14-day half-life, so stale zones fade automatically
- Rebuy signals are deduplicated by (hotel_id, reason) — same pattern isn't counted twice

---

## Phase 2 Integration — COMPLETED (2026-03-25)

### Step 1: Scheduler Integration ✅ DONE
Wired into `_shared_state.py._run_collection_cycle()`:
- **Daily (once per calendar day):** `_refresh_analytical_cache_daily()` → calls `aggregator.full_refresh(90)` — refreshes Layer 1 (reference) + Layer 2 (market + search + trading)
- **Every cycle (3h):** `_refresh_analytical_cache_signals(analysis)` → generates daily signals from forward curve, runs demand zone detection, computes trade setups

Singleton helpers:
```python
_get_analytical_cache()      # → AnalyticalCache singleton
_get_cache_aggregator()      # → CacheAggregator with shared cache
_refresh_analytical_cache_daily()    # → Layer 1+2 refresh from Azure SQL
_refresh_analytical_cache_signals(analysis)  # → Layer 3 signals+zones+setups
```

### Step 2: Trading API Endpoints ✅ DONE
All in `src/api/routers/trading_router.py`, prefix `/api/v1/salesoffice/trading/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/trading/signals?detail_id=X` | GET | Daily CALL/PUT/NEUTRAL timeline |
| `/trading/signals/summary?detail_id=X` | GET | Signal counts + avg confidence + dominant |
| `/trading/zones?hotel_id=X` | GET | Demand (SUPPORT/RESISTANCE) zones |
| `/trading/breaks?hotel_id=X` | GET | Structure breaks (BOS/CHOCH) |
| `/trading/setups?hotel_id=X&signal=CALL&min_rr=1.5` | GET | Trade setups with entry/stop/target/RR |
| `/trading/search-intel?hotel_id=X` | GET | 3 price points (sell/net/bar) per day |
| `/trading/rebuy?hotel_id=X` | GET | Rebuy signals from cancellation book |
| `/trading/overrides?hotel_id=X` | GET | Human price override history |
| `/trading/cache/freshness` | GET | Cache layer status (13 tables) |
| `/trading/cache/refresh?layer=all` | POST | Trigger manual refresh (all/daily/signals) |
| `/trading/hotel/{hotel_id}` | GET | Combined overview: zones+breaks+rebuy+overrides+search+sentiment |

### Step 3: Command Center UI Panels ✅ DONE
Added 3 trading intelligence panels to the right column of `src/templates/command_center.html`:
- **Trading Intel** (`#panel-trading-intel`) — signal summary (CALL/PUT/NEUTRAL counts, avg confidence, dominant signal) + rebuy indicators
- **Demand Zones** (`#panel-demand-zones`) — support/resistance zones with strength + touch count + structure breaks (BOS/CHOCH)
- **Trade Setup** (`#panel-trade-setup`) — entry/stop/target/RR/quality/size card for selected option

JS functions: `loadTradingIntel()`, `loadDemandZones()`, `loadTradeSetup()`, `loadTradingPanels()` — all hooked into `selectOption()` flow.

### Step 4: Enrichment Feed ✅ DONE
Extended forward curve with 3 new enrichment signals from analytical cache:
- **demand_zone_proximity** — ±0.10%/day when price near SUPPORT (bullish) or RESISTANCE (bearish)
- **rebuy_signal_strength** — +0.12%/day max CALL boost when rebuy pattern detected in MED_CancelBook
- **search_volume_trend** — ±0.08%/day based on normalized search volume (0.5 = neutral)

Modified files:
- `config/constants.py` — 3 new constants (DEMAND_ZONE_IMPACT_MAX, REBUY_SIGNAL_IMPACT_MAX, SEARCH_VOLUME_IMPACT_MAX)
- `src/analytics/forward_curve.py` — 3 new Enrichments fields + 3 getter methods + 3 ForwardPoint fields + prediction loop integration
- `src/analytics/analyzer.py` — `_build_enrichments()` populates new fields from analytical_cache data

---

## Previous Sessions

### Session 2026-03-24 — v2.6.0 Release
1. MCP medici-db fix (prediction_readonly → prediction_reader)
2. Voter data enrichment — Events + Peers connected
3. FRED Collector (BaseCollector, SQLite, 5 FRED series)
4. Active Rooms Selector — MED_Book prediction
5. Command Center polish (Term Structure, Source Breakdown, category headers)

### Session 2026-03-20 — 2026-03-21
- Collector fix, signals cache, path forecast, source attribution
- Override Queue (38 tests), Opportunity Queue (40 tests)
- Trading Terminal, Path Forecast, Source Comparison dashboards

---

## Production URLs
- Command Center: `/api/v1/salesoffice/dashboard/command-center`
- Trading Terminal: `/api/v1/salesoffice/dashboard/terminal`
- Options board: `/api/v1/salesoffice/options/view`
- Override Queue: `/api/v1/salesoffice/dashboard/override-queue`
- Opportunity Queue: `/api/v1/salesoffice/dashboard/opportunity-queue`
