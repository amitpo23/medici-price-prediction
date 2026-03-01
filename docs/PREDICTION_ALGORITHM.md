# Medici Price Prediction Algorithm

How the system predicts hotel room prices, step by step.

---

## Overview

The system models hotel room prices like financial futures contracts. Each room has a **check-in date** and a **current price**. The algorithm predicts how the price will change each day between now and check-in.

**Key concept: T = days to check-in.** When T is large (e.g., 90 days away), prices tend to be lower. As T decreases (check-in approaches), prices typically increase. The algorithm learns this pattern from historical data.

---

## Step 1: Data Collection

**What it does:** Collects current room prices from the SalesOffice database every hour.

**How it works:**
1. Connects to the Medici trading database (read-only)
2. Queries `SalesOffice.Details` for all active room listings
3. Stores each snapshot in a local SQLite database with a timestamp
4. Over time, builds a history of price changes per room

**Example:**
```
Snapshot at 10:00 AM: Room #1234 = $800
Snapshot at 1:00 PM:  Room #1234 = $815  (+$15)
Snapshot at 4:00 PM:  Room #1234 = $815  (no change)
```

**Key files:** `src/analytics/collector.py`, `src/analytics/price_store.py`

---

## Step 2: Building the Decay Curve

**What it does:** Learns the "typical daily price change" at each T (days to check-in) from historical data.

**How it works:**

1. **Extract observations:** For each historical room, takes pairs of consecutive price scans and computes the daily rate of price change:
   ```
   Room was $800 at T=45, then $810 at T=43 (2 days later)
   Daily change = ($810 - $800) / $800 / 2 days = +0.625%/day
   This observation is assigned to T=44 (midpoint)
   ```

2. **Group by T:** All observations at similar T values are grouped using overlapping bins:
   - T = 1-30: bins of width 5, step 1
   - T = 31-60: bins of width 7, step 2
   - T = 61-90: bins of width 10, step 3
   - T = 91-180: bins of width 14, step 7

3. **Smooth with Bayesian shrinkage:** Prevents overreacting to small samples. The formula blends the local average with the global average:
   ```
   smoothed_value = (N * local_mean + K * global_mean) / (N + K)
   ```
   Where K=5 (prior strength). With many observations, local data dominates. With few observations, it falls back toward the global average.

4. **Result:** A curve mapping each T to:
   - Expected daily price change (%)
   - Volatility (standard deviation of changes)
   - Probability of price going up/down/stable

**Example decay curve:**
```
T=1   (tomorrow):    +0.45%/day  (prices tend to spike right before check-in)
T=7   (next week):   +0.15%/day  (moderate upward pressure)
T=30  (next month):  +0.02%/day  (mostly stable)
T=90  (3 months):    -0.01%/day  (slight downward drift)
```

**Key parameters:**
- `_BAYESIAN_K = 5` — How much to trust global average vs local data
- `_MIN_VOL = 0.5` — Minimum volatility floor (%)
- Outlier cap: Daily changes capped at +/-10%

**Key file:** `src/analytics/forward_curve.py` → `build_decay_curve()`

---

## Step 3: Forward Curve Walk (Price Prediction)

**What it does:** Starting from today's price, walks day-by-day to check-in, applying the expected change at each T.

**How it works:**

For each day from now to check-in:
```
predicted_price = current_price

For each day (T counting down from current_T to 1):
    1. base_change    = decay_curve[T]           (e.g., +0.15%)
    2. category_adj   = category_offset           (e.g., Suites: +0.05%)
    3. board_adj      = board_offset              (e.g., All-Inclusive: +0.02%)
    4. momentum_adj   = recent_momentum * decay   (e.g., +0.10%, decays over 7 days)
    5. event_adj      = event_impact              (e.g., Art Basel: +0.30%)
    6. season_adj     = seasonal_index            (e.g., August peak: +0.04%)
    7. demand_adj     = flight_demand_signal      (e.g., HIGH demand: +0.02%)

    total_change = base + category + board + momentum + event + season + demand
    predicted_price *= (1 + total_change / 100)
```

**Example:**
```
Room #1234: Current price $800, check-in in 14 days

Day 1 (T=14): base +0.10%, momentum +0.05%, event +0.20% = +0.35%
  → $800 * 1.0035 = $802.80

Day 2 (T=13): base +0.12%, momentum +0.04% = +0.16%
  → $802.80 * 1.0016 = $804.08

... (continues for 14 days)

Day 14 (T=0): Final predicted price = $845.20 (+5.7%)
```

**Adjustments explained:**
- **Category offset:** Suites and Deluxe rooms may have different price patterns than Standard rooms
- **Board offset:** All-Inclusive prices behave differently from Room-Only
- **Momentum:** If the room has been rising faster than expected in recent scans, that momentum carries forward (but decays with a ~7-day half-life)
- **Events:** Major events (Art Basel, conferences) push prices up during their impact window (3 days before to 2 days after)
- **Seasonality:** Monthly index from historical booking data (e.g., August = 1.37x average, January = 0.70x)
- **Demand:** Flight search volume to Miami indicates general demand level

**Confidence intervals:**
The algorithm also computes price bands showing the range of likely prices:
```
Day 7:  Predicted $820, Range [$790 - $850] (95% confidence)
Day 14: Predicted $845, Range [$770 - $920] (95% confidence — wider because further out)
```
These are computed by accumulating the per-T volatility from the decay curve.

**Key file:** `src/analytics/forward_curve.py` → `predict_forward_curve()`

---

## Step 4: Momentum Detection

**What it does:** Measures how fast and in which direction a room's price is currently moving, using the 3-hour scan intervals.

**How it works:**

1. **Velocity calculation:** Computes price change rates at three time scales:
   - **3h velocity:** Latest scan-to-scan change rate
   - **24h velocity:** Average daily rate over the last 24 hours
   - **72h velocity:** Average daily rate over the last 3 days

2. **Acceleration:** Is the price speeding up or slowing down?
   ```
   acceleration = velocity_24h - velocity_72h
   ```
   Positive acceleration = price is rising faster than before.

3. **Compare to expected:** The momentum is compared against what the decay curve predicts:
   ```
   momentum_vs_expected = observed_daily_rate - curve_expected_rate
   ```
   If a room is rising +1%/day but the curve says +0.1%/day, the excess momentum is +0.9%.

4. **Signal classification:**
   - `ACCELERATING_UP` — Price rising much faster than expected (>2 sigma)
   - `ACCELERATING_DOWN` — Price falling much faster than expected (>2 sigma)
   - `NORMAL` — Behaving as expected
   - `INSUFFICIENT_DATA` — Not enough scans yet

**Example:**
```
Room #5678 over the last 72 hours:
  3h ago:  $950 → $960  (velocity: +1.05%/3h)
  24h avg: +0.8%/day
  72h avg: +0.3%/day
  Acceleration: +0.5%/day (speeding up)
  Expected at T=20: +0.1%/day
  Momentum vs expected: +0.7%/day
  Signal: ACCELERATING_UP (strength: 0.65)
```

**Key file:** `src/analytics/momentum.py` → `compute_momentum()`

---

## Step 5: Regime Detection

**What it does:** Identifies when a room's price behavior deviates significantly from what's expected — a warning that something unusual is happening.

**How it works:**

1. Compare **actual** cumulative price change to **expected** change over the observation period
2. Compute a Z-score (how many standard deviations from expected):
   ```
   z_score = (actual_change - expected_change) / (volatility * sqrt(days))
   ```
3. Classify the regime:

| Regime | Z-Score | Meaning |
|--------|---------|---------|
| NORMAL | \|z\| < 2.0 | Price tracking within expected range |
| TRENDING_UP | z > 2.0 | Price significantly above expected — unusual demand |
| TRENDING_DOWN | z < -2.0 | Price significantly below expected — weak demand |
| VOLATILE | High scan variance | Large price swings between scans |
| STALE | No movement, 16+ scans | Price hasn't changed — possible data issue |

**Example:**
```
Room #9012: First seen at $500, now $420 after 10 days
  Expected change: -0.1%/day * 10 = -1% → expected $495
  Actual change: -16% → $420
  Volatility: 1.5%/day, sqrt(10) = 3.16
  Z-score: (-16% - (-1%)) / (1.5% * 3.16) = -3.16

  Regime: TRENDING_DOWN (warning)
  Description: "Price -15.0% below expected (-3.2 sigma)"
```

**Key file:** `src/analytics/regime.py` → `detect_regime()`

---

## Step 6: Trading Recommendations

**What it does:** Based on predictions, momentum, and market context, recommends actions for each room.

### For Buy Opportunities (new rooms to purchase):

**Decision: BUY or PASS**

```
margin = (predicted_market_price - buy_price) / buy_price

BUY if:
  - margin >= 15% (minimum required profit margin)
  - sell_probability >= 40% (estimated chance of selling the room)

STRONG BUY if:
  - margin >= 22.5% (1.5x minimum)
  - sell_probability >= 65%
  - market_upside >= 10%

PASS if:
  - margin < 15%, OR
  - sell_probability < 40%
```

**Sell probability** is estimated by combining:
- Price margin (higher margin = more pricing flexibility)
- Occupancy forecast (high occupancy = more demand)
- Seasonal factors (holidays and weekends boost demand)
- Hotel's historical sell-through rate
- Competitive positioning vs competitor prices
- Confidence interval risk (if lower bound shows a loss)

### For Existing Bookings:

**Decision: HOLD, REPRICE, CONSIDER_CANCEL, or ALERT**

```
REPRICE if:
  - Market price is 10%+ above our push price → reprice up
  - Market price is 10%+ below our push price → reprice down

CONSIDER_CANCEL if:
  - Market well below push price AND margin thin (<5%)
  - Cancel deadline approaching AND unprofitable at market price

ALERT if:
  - Cancel deadline within 5 days with thin margin
  - Check-in within 7 days AND unprofitable

HOLD (default):
  - Position is healthy, margin adequate, market aligned
```

**Key parameters:**
- `MIN_MARGIN_BUY = 15%` — Minimum profit margin to recommend buying
- `MIN_SELL_PROBABILITY = 40%` — Minimum estimated sell chance
- `REPRICE_THRESHOLD = 10%` — Market-vs-push gap to trigger repricing
- `CANCEL_RISK_DAYS = 5` — Days before cancel deadline = high urgency
- `LOW_MARGIN_ALERT = 5%` — Below this margin = alert

**Key file:** `src/models/recommender.py` → `TradingRecommender`

---

## Step 7: Deep Historical Analysis (Ensemble Prediction)

**What it does:** Combines 3 independent prediction signals into a weighted ensemble, with year-over-year comparison and human-readable explanations.

### Signal 1: Forward Curve (weight: ~50%)
The existing decay curve walk from Steps 2-3 above.

### Signal 2: Historical Patterns (weight: ~30%)
Mines all available historical data for:

1. **Same-period analysis:** What was the average price for this hotel + room category in the same calendar month last year?
2. **Lead-time behavior:** How do prices typically change in the final days before check-in? (Buckets: 0-7d, 8-14d, 15-30d, 31-60d, 60+d)
3. **Day-of-week patterns:** Are Friday check-ins more expensive than Monday?
4. **Event impact measurement:** Actual price uplift during past events (not hardcoded multipliers)
5. **Hotel-specific monthly seasonality:** Per-hotel monthly price index, falling back to generic benchmarks

### Signal 3: ML Forecast (weight: ~20%)
If a trained Darts model exists for the hotel (XGBoost/LightGBM/NBEATS), its prediction is included.

### Dynamic Weighting
Weights are adjusted based on data quality:
- High-confidence signals get more weight
- Low-data signals get reduced weight
- If only the forward curve is available, it gets 100%

### Output
```
Predicted price: $860 (+7.5% from current $800)

Signals:
  Forward curve: $855 (weight: 50%, confidence: high)
  Historical pattern: $870 (weight: 35%, confidence: medium)
  ML forecast: $850 (weight: 15%, confidence: medium)

Year-over-year: April avg last year was $780 (+2.6% YoY)

Why:
  - Historical pattern: +5% (Last April, similar rooms averaged $840)
  - Lead-time effect: +3% (Prices typically rise 3% in final 45 days)
  - Miami Open Tennis: +2% (Event starts 5 days before check-in)
  - Momentum: upward (Price rising faster than expected)
```

**Key files:** `src/analytics/historical_patterns.py`, `src/analytics/deep_predictor.py`

---

## Step 8: Backtest Validation

**What it does:** Validates prediction quality against actual outcomes using walk-forward methodology.

**How it works:**
1. For each historical price track with 3+ scans, the last scan = "actual" check-in price
2. Earlier scans are used as prediction points
3. For each test point, the decay curve is rebuilt from data BEFORE that point (no data leakage)
4. Compare predicted price vs actual price

**Metrics:**
- MAPE (Mean Absolute Percentage Error) — lower is better
- RMSE (Root Mean Squared Error %) — penalizes large errors
- Breakdown: by hotel, by room category, by lead-time bucket

**Quality assessment:**
| MAPE | Rating |
|------|--------|
| < 5% | Excellent |
| 5-10% | Good |
| 10-20% | Fair |
| > 20% | Poor |

**Key file:** `src/analytics/backtest.py`

---

## Full Pipeline Summary

```
1. COLLECT        Every hour, snapshot all room prices from SalesOffice DB
                   ↓
2. DECAY CURVE     Learn "expected daily change" at each T from history
                   ↓
3. MINE PATTERNS   Same-period, lead-time, DOW, event impacts, seasonality
                   ↓
4. FORWARD CURVE   Walk day-by-day: base + category + momentum + events + season
                   ↓
5. DEEP ENSEMBLE   Combine: forward curve (50%) + historical (30%) + ML (20%)
                   ↓
6. MOMENTUM        Measure 3h/24h/72h price velocity from recent scans
                   ↓
7. REGIME          Detect abnormal behavior (trending, volatile, stale)
                   ↓
8. RECOMMEND       BUY/PASS for opportunities, HOLD/REPRICE/CANCEL for bookings
                   ↓
9. EXPLAIN         YoY comparison + "why" factors + confidence statement
                   ↓
10. REPORT         Simplified analysis with attention items + explanations
```

---

## Data Sources

| Source | What It Provides | Update Frequency |
|--------|-----------------|-----------------|
| SalesOffice DB | Room prices, bookings | Every hour (live scan) |
| Historical price tracks | Decay curve + same-period patterns | Built on each analysis run |
| Monthly tprice table | Hotel-specific monthly pricing | Built on each analysis run |
| Booking history | Sell-through rates, outcomes | Built on each analysis run |
| Kiwi.com flights | Demand indicator (HIGH/MEDIUM/LOW) | On demand |
| Events database | Conference/event impact multipliers | On demand |
| Booking benchmarks | Seasonality index, cancellation model | Static dataset |
| Hotel knowledge (TBO) | Competitive landscape | Static dataset |
| Darts ML models | XGBoost/LightGBM forecasts | When trained |

---

## API Endpoints

| Endpoint | What It Returns |
|----------|----------------|
| `GET /api/v1/salesoffice/simple` | Simplified JSON (summary, predictions with explanations, attention items) |
| `GET /api/v1/salesoffice/simple/text` | Plain text report |
| `GET /api/v1/salesoffice/forward-curve/{id}` | Detailed prediction for one room (all signals, YoY, explanation) |
| `GET /api/v1/salesoffice/backtest` | Prediction quality validation (MAPE, RMSE by hotel/category/T) |
| `GET /api/v1/salesoffice/data` | Full raw analysis JSON |
| `GET /api/v1/salesoffice/dashboard` | Interactive HTML dashboard |
