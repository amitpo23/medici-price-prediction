# Medici Knowledge Base — System Architecture, Algorithm & Self-Audit

> Complete technical specification of the Medici Price Prediction engine.
> Covers: data sources, prediction algorithm, 14-voter consensus, accuracy measurement,
> self-correction mechanisms, known gaps, and improvement roadmap.
>
> Last updated: 2026-03-25

---

## 1. System Overview

Medici treats hotel rooms as **financial derivatives**. Each room has:
- **S(t)**: Current market price at time t
- **T**: Days until check-in (expiry)
- **Signal**: CALL (price will rise), PUT (price will drop), NEUTRAL

The system **never executes trades** — it generates signals and recommendations.
The operator (or rules engine) decides whether to act.

**Scale**: 4,058 rooms, 23 hotels, 12 data sources, 14 consensus voters, scan every 3 hours.

---

## 2. Data Sources — Complete Inventory

### 2.1 Azure SQL (medici-db) — Primary

| Table | Rows | Purpose | Scan Frequency |
|-------|------|---------|----------------|
| SalesOffice.Details | ~4,058 active | Current room prices per scan | Every 3h |
| SalesOffice.Orders | ~100s active | Search requests, date ranges | Real-time |
| SalesOffice.Log | 1.2M+ | **Price change audit trail** — `DbRoomPrice: X -> API RoomPrice: Y` | Every scan |
| RoomPriceUpdateLog | 82K+ | Every price update event with timestamp | Continuous |
| AI_Search_HotelData | 8.5M | Competitor OTA pricing (Booking, Expedia) | 60-day window |
| SearchResultsPollLog | 8.3M, 129 providers | Per-provider per-room pricing | 7-day window |
| MED_Book | 10.7K | Active purchased inventory (buy price, last market price) | Continuous |
| MED_PreBook | 10.7K | Pre-booking pipeline | Continuous |
| MED_CancelBook | 4.7K | Cancellation events — demand signal | Continuous |
| MED_SearchHotels | 7M (2020-2023) | 3-year historical archive | Static |
| Med_Hotels | 23+ | Hotel master data, ZenithId, zone/tier | Reference |
| Med_Hotels_ratebycat | Variable | Zenith rate plan mappings | Reference |

### 2.2 Local SQLite — Snapshots & Execution

| Database | Tables | Purpose |
|----------|--------|---------|
| salesoffice_prices.db | price_snapshots, analysis_runs | Hourly price snapshots (UNIQUE: snapshot_ts + detail_id) |
| prediction_tracker.db | prediction_log | Every prediction vs actual — accuracy feedback loop |
| override_queue.db | override_requests, override_rules | PUT signal execution queue |
| opportunity_queue.db | opportunity_queue, opportunity_rules | CALL signal execution queue |
| fred_data.db | fred_observations | FRED macroeconomic indicators |

### 2.3 External APIs

| Source | Data | Freshness | Status |
|--------|------|-----------|--------|
| Open-Meteo | Weather forecast (rain, clear, hurricane) | Daily | ✅ Connected |
| Ticketmaster/SeatGeek | Miami events (8 major + dynamic) | Weekly | ✅ Connected (hardcoded) |
| GMCVB | Official ADR/RevPAR by zone | Weekly | ✅ Connected |
| Kiwi.com Flights | Miami inbound demand | Daily | ⚠️ Collector not active (demand_adj = 0) |
| FRED | Hotel PPI, Lodging CPI, Employment | Monthly | ❌ Missing API key |
| BrightData | Live OTA scraping | On-demand | ✅ MCP configured |

### 2.4 Data Freshness Monitoring

Each source has an expected interval. Freshness score = `exp(-age / expected_interval)`:

| Source | Expected Interval | Protected | Notes |
|--------|------------------|-----------|-------|
| salesoffice | 1 hour | ✅ Yes | Weight never reduced |
| ai_search_hotel_data | 4 hours | No | Auto weight reduction if stale |
| search_results_poll_log | 4 hours | No | |
| room_price_update_log | 4 hours | No | |
| med_prebook | 24 hours | No | |
| cancellation_data | 24 hours | No | |
| kiwi_flights | 24 hours | No | Currently stale (collector off) |
| open_meteo | 24 hours | No | |
| fred | 720 hours (monthly) | No | No API key |

**Auto-degradation**: If `freshness < 0.5` and source NOT protected → weight_override = freshness value.

---

## 3. Prediction Algorithm — Mathematical Specification

### 3.1 Overview: Three-Signal Ensemble

```
Final Price = FC_Price × 0.50 + Historical_Price × 0.30 + ML_Price × 0.20
(weights adjusted dynamically by confidence)
```

### 3.2 Signal 1: Forward Curve (50% weight)

#### Step 1: Decay Curve Construction

**Input**: All historical SalesOffice.Details scans (including IsDeleted=1).

**Process**:
1. Group by (order_id, hotel_id, room_category, room_board)
2. For consecutive scan pairs, compute daily price change:
   ```
   daily_pct = (price_new - price_old) / price_old × 100 / gap_days
   Cap: max(-10%, min(+10%, daily_pct))
   ```
3. Assign to T-bucket at scan midpoint: `T = max(1, (checkin_date - midpoint_date).days)`
4. Weight by scan proximity: `weight = 1.0 / (1.0 + 0.1 × gap_days)`

**Binning** (overlapping to prevent data loss):
```
T = 1-30:   bin_width=5,  step=1
T = 31-60:  bin_width=7,  step=2
T = 61-90:  bin_width=10, step=3
T = 91-180: bin_width=14, step=7
```

**Bayesian Smoothing** per bin:
```
shrunk_mean = (N × sample_mean + K × global_mean) / (N + K)
K = 5 (prior strength)
```
When N is small (few observations), the estimate pulls toward the global mean.
When N is large, it trusts the local data.

**Probability Distribution** per T:
```
P(up)    = count(daily_pct > +0.1%) / total × 100
P(down)  = count(daily_pct < -0.1%) / total × 100
P(stable) = 100 - P(up) - P(down)
```

#### Step 2: Price Walk (Forward Projection)

Starting from `current_price`, walk each day from T down to 1:

```
For each day i (T → 1):
    base_change = decay_curve.get_daily_change(t)     # Core T-dependent drift

    # 9 Enrichment Adjustments (daily %):
    event_adj     = impact_multiplier × 100 / impact_days  # Ramp 3d before, taper 2d after
    season_adj    = (month_index - 1.0) × 3.0              # Feb peak +9.9%, Sep trough -15.5%
    demand_adj    = ±0.15%                                  # HIGH/LOW flight demand
    weather_adj   = per-date forecast signal                # Rain -0.05%, hurricane -0.15%
    competitor_adj = pressure × 0.20                        # AI_Search benchmark (-1 to +1)
    cancel_adj    = -cancel_risk × 0.25                     # Max -0.25%/day
    provider_adj  = pressure × 0.20                         # SearchResultsPollLog (-1 to +1)
    momentum_adj  = momentum_vs_expected × exp(-0.15 × i) × 0.3  # ~5-day half-life
    offset_adj    = category_offset + board_offset          # Room type premium/discount

    total_daily_pct = sum(all adjustments above)
    predicted_price *= (1.0 + total_daily_pct / 100.0)

    # Confidence interval (95%):
    cumulative_variance += (volatility_at_t / 100 × predicted_price)²
    lower = predicted_price - 1.96 × sqrt(cumulative_variance)
    upper = predicted_price + 1.96 × sqrt(cumulative_variance)
```

**Output**: 65+ daily price points with bounds, enrichment decomposition per day.

### 3.3 Signal 2: Historical Patterns (30% weight)

1. Look up same calendar month from prior year: `same_period[month].avg_price`
2. Adjust by lead-time bucket:
   ```
   Buckets: 0-7d, 8-14d, 15-30d, 31-60d, 60+d
   predicted = base_price × (1 + bucket.avg_daily_change × T / 100)
   ```
3. Adjust by day-of-week pattern: `predicted *= (1 + dow_index / 100)`
4. **Sanity clamp**: If ratio > 2.0× or < 0.5× current:
   ```
   predicted = predicted × 0.20 + current × 0.80
   confidence *= 0.30
   ```

### 3.4 Signal 3: ML Forecast (20% weight)

LightGBM direct prediction model:
- **Features**: day_of_week, month, is_weekend, price lags (1,3,7,14,28 days), rolling stats, velocity, cancel rate
- **Sanity clamp**: `[current × 0.50, current × 2.00]`
- **Fallback**: If model not trained, weight redistributed to FC (66%) + Historical (34%)

### 3.5 Ensemble Combination

**Dynamic Weight Scaling**:
```
effective_weight = base_weight × (0.5 + 0.5 × confidence)
```
High confidence (1.0) → full weight. Low confidence (0.0) → half weight.

**Per-Signal Sanity Check** (before combining):
```
ratio = predicted / current
if ratio > 2.0 or ratio < 0.5:
    penalty = max(0.05, 1.0 / (1.0 + |log₂(ratio)|))
    confidence *= penalty
```
Example: ratio 3.0× → penalty 0.37, ratio 4.0× → penalty 0.29

**Final Price**:
```
ensemble = Σ(signal_price × normalized_weight)
Hard clamp: [current × 0.40, current × 2.50]
```

### 3.6 Data Density → Confidence Mapping

| Observations | Density | Confidence |
|-------------|---------|------------|
| ≥15 | High | 0.80 |
| ≥7 | Medium | 0.60 |
| <7 | Low | 0.40 |
| Extrapolated | — | 0.20 |

---

## 4. Momentum Engine

**Input**: Price snapshots from 3-hour scan cycles.

**Velocity** (normalized to 3-hour rates):
```
hourly_rates = scan_pct_changes / time_diff_hours × 3
velocity_3h  = latest rate
velocity_24h = mean(rates in last 24h) × 8  (daily)
velocity_72h = mean(rates in last 72h) × 8  (daily)
```

**Acceleration**: `velocity_24h - velocity_72h` (positive = speeding up)

**Momentum vs Expected**: `observed_daily_rate - decay_curve_rate_at_T`

**Signal Classification**:
- `|momentum_vs_expected| > 2 × volatility` → ACCELERATING_UP/DOWN (strength up to 1.0)
- `|acceleration| > volatility` → ACCELERATING/DECELERATING (strength up to 0.5)
- Otherwise → NORMAL

**Integration into FC**: Momentum decays exponentially in the price walk:
```
contribution = momentum × exp(-0.15 × day_index) × 0.3
Half-life ≈ ln(2) / 0.15 ≈ 4.6 days
```

---

## 5. Consensus Signal Engine — 14 Voters

### 5.1 Voting Rules

```
NEUTRAL votes excluded from count
voting_count = CALL_votes + PUT_votes
Minimum voters: 4 non-NEUTRAL required
Agreement threshold: ≥66% for signal
Otherwise: NEUTRAL
```

### 5.2 Voter Specifications

| # | Voter | Category | CALL Threshold | PUT Threshold | Data Source |
|---|-------|----------|---------------|--------------|-------------|
| 1 | Forward Curve | Lagging | change ≥ +30% | change ≤ -5% | FC[0].change_pct |
| 2 | Scan Velocity | Coincident | velocity > +3% | velocity < -3% | momentum.velocity_24h |
| 3 | Competitors | Coincident | ≤ -15% vs zone | ≥ +10% vs zone | Zone avg (same tier) |
| 4 | Events | Leading | "upcoming" event | "past" event | MIAMI_MAJOR_EVENTS |
| 5 | Seasonality | Leading | adj > +5% | adj < -5% | FC season_adj_pct |
| 6 | Flight Demand | Leading | adj > +3% | adj < -3% | FC demand_adj_pct |
| 7 | Weather | Leading | adj > +3% | adj < -5% | FC weather_adj_pct |
| 8 | Peers | Coincident | ≥66% peers up | ≥66% peers down | Same zone+tier directions |
| 9 | Booking Momentum | Lagging | — | cancel_adj < -2% | FC cancellation_adj_pct |
| 10 | Historical | Lagging | P(up) ≥ 65% | P(down) ≥ 65% | probability.up/down |
| 11 | Official Benchmark | Lagging | ≤ -20% vs ADR | ≥ +15% vs ADR | GMCVB zone ADR |
| 12 | Scan Drop Risk | Coincident | score ≤ -10 | score ≥ 50 | scan_history patterns |
| 13 | Provider Spread | Coincident | pressure ≥ +0.1 | pressure ≤ -0.1 | SearchResultsPollLog |
| 14 | Margin Erosion | Lagging | margin ≥ +15% | margin ≤ -3% | MED_Book buy prices |

### 5.3 Voter Categories

- **Leading (Predict)**: Events, Seasonality, Flights, Weather — predict future demand
- **Coincident (Now)**: Velocity, Competitors, Peers, Scan Drop Risk, Provider Spread — current state
- **Lagging (History)**: FC, Booking Momentum, Historical, Benchmark, Margin Erosion — confirmed patterns

### 5.4 Scan Drop Risk Scoring Model

Based on `next-scan-drop` skill predictor:
```
score += 30 if drop_frequency > 60%
score += 15 if drop_frequency > 40%
score += 25 if trend == "down"
score -= 15 if trend == "up"
score += 20 if max_single_drop > $20
score += 10 if max_single_drop > $10
score += 15 if all_drops_no_rises
score += 10 if drops > 2× rises

PUT if score ≥ 50
CALL if score ≤ -10
```

---

## 6. Accuracy Measurement & Self-Correction

### 6.1 Prediction Logging

Every prediction stored at generation time:
```
prediction_log: room_id, hotel_id, prediction_ts, checkin_date,
                t_at_prediction, predicted_price, predicted_signal,
                predicted_confidence, actual_price, error_pct,
                signal_correct, scored_at
```

### 6.2 Scoring (retroactive)

When checkin_date passes, system looks up actual price from price_snapshots:
```
error_pct = (actual - predicted) / predicted × 100
signal_correct = 1 if actual direction matches predicted signal
```

### 6.3 Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| MAE | mean(\|actual - predicted\|) | < $30 |
| MAPE | mean(\|error_pct\|) | < 10% |
| Directional Accuracy | correct_signals / total | > 65% |
| Within 5% | \|error\| ≤ 5% / total | > 50% |
| Within 10% | \|error\| ≤ 10% / total | > 75% |
| Bias | mean(error_pct) | Near 0 |

### 6.4 Breakdown Dimensions

- **By T-bucket**: 1-7d, 8-14d, 15-30d, 31-60d, 61+d
- **By signal**: CALL precision/recall, PUT precision/recall
- **By hotel**: Per-hotel MAPE and directional accuracy
- **By trend**: Rolling 7-day and 30-day windows

### 6.5 Self-Correction Mechanisms

| Mechanism | Trigger | Action |
|-----------|---------|--------|
| Data Quality Auto-Degrade | freshness < 0.5 | Reduce source weight to freshness value |
| Circuit Breaker | 3 consecutive failures | Block source, alert, probe after 5 min |
| Sanity Clamp | prediction > 2.5× or < 0.4× current | Hard clamp to bounds |
| Outlier Blend | ratio > 2.0× or < 0.5× | Blend 20% prediction + 80% current |
| Confidence Penalty | outlier detection | confidence *= penalty (min 0.05) |
| Voter Calibration | NEUTRAL > 95% or CALL+PUT > 30% | Adjust voter thresholds |

### 6.6 Circuit Breaker Detail

```
States: CLOSED → OPEN (after 3 failures) → HALF_OPEN (after 5 min) → CLOSED (probe OK)
                                            → OPEN (probe fails)
```

Per-source tracking: `circuit_state` table (source_id, state, failure_count, timestamps).
Events audit log: `circuit_events` table.

---

## 7. Known Gaps & Honest Assessment

### 7.1 Data Gaps (as of 2026-03-25)

| Issue | Impact | Fix |
|-------|--------|-----|
| **Flight demand always 0** | demand_adj never contributes to FC | Enable Kiwi collector |
| **FRED not connected** | No macro context (PPI, CPI) | Set FRED_API_KEY env var |
| **Cancellation adj always 0** | Voter #9 always NEUTRAL | Wire cancel data into enrichment |
| **Scan Drop Risk — few scans** | Most rooms have 1 snapshot | Will resolve with more scan cycles |
| **Margin Erosion — sparse** | Only 93 MED_Book rooms have future stays | Inherent limitation |
| **Scheduler dies** | Stops collecting after a few cycles | Need watchdog/recovery |
| **ML model not trained** | 20% weight slot unused | Train on accumulated snapshots |

### 7.2 Algorithm Limitations

| Limitation | Impact | Severity |
|------------|--------|----------|
| Bayesian K=5 fixed | Same smoothing regardless of data quality | Low |
| Category offsets need ≥10 obs | New room types get no offset | Medium |
| Event windows fixed (3d before, 2d after) | No per-event customization | Low |
| Seasonality is global (all hotels) | Zone differences ignored | Medium |
| Momentum half-life ~5 days | May be too short for slow-moving rooms | Low |
| FC change_pct threshold 30% for CALL | Very high — few rooms trigger | Medium |
| No cross-hotel correlation | Hotels in same zone may move together | Medium |

### 7.3 Voter Connectivity Audit (2026-03-25)

| # | Voter | Real Data? | Issue |
|---|-------|-----------|-------|
| 1 | Forward Curve | ✅ 65 FC points | Working |
| 2 | Scan Velocity | ✅ velocity_24h=28.2 | Working |
| 3 | Competitors | ✅ zone_avg=$302 | Working |
| 4 | Events | ✅ Miami Swim Week detected | Working |
| 5 | Seasonality | ✅ season_adj=4.2% | Working |
| 6 | Flight Demand | ⚠️ demand_adj=0.0 always | **Kiwi collector off** |
| 7 | Weather | ✅ weather_adj=0.02 | Working (light data) |
| 8 | Peers | ✅ 464/505 peers | Working |
| 9 | Booking Momentum | ⚠️ cancel_adj=0.0 always | **Cancel data not flowing to enrichment** |
| 10 | Historical | ✅ up=32% down=43% | Working |
| 11 | Official Benchmark | ✅ -13.7% vs ADR | Working |
| 12 | Scan Drop Risk | ⚠️ "Only 1 scans" | **Needs more cycles** |
| 13 | Provider Spread | ✅ pressure=-1.0 | Working |
| 14 | Margin Erosion | ⚠️ only for MED_Book rooms | Working (93 rooms) |

**Effective voters with real data: 10 of 14** (71%)

---

## 8. Improvement Roadmap

### 8.1 Critical Fixes (Now)

| Fix | Impact | Effort |
|-----|--------|--------|
| Fix scheduler watchdog | Continuous scanning | 1 hour |
| Wire cancellation data into FC enrichment | Voter #9 activated | 2 hours |
| Enable Kiwi flights collector | Voter #6 activated | 1 hour (config) |
| Set FRED_API_KEY | Macro context | 5 min (env var) |

### 8.2 Algorithm Improvements (Short-term)

| Improvement | Current | Proposed | Impact |
|-------------|---------|----------|--------|
| **Adaptive Bayesian K** | K=5 fixed | K = max(2, 10 - data_density) | Better smoothing for sparse data |
| **Per-zone seasonality** | Global monthly | Zone-specific (SB vs Airport vs Downtown) | More accurate seasonal signal |
| **Lower FC CALL threshold** | 30% | 15% (or adaptive by T) | More CALL signals for long-T rooms |
| **Cross-hotel correlation** | Independent | Correlation matrix within zone+tier | Catch zone-wide movements |
| **Momentum half-life by tier** | 5 days for all | Budget 3d, Mid 5d, Premium 7d | Better momentum decay |
| **Event-specific windows** | 3d before, 2d after | Art Basel 7d/5d, F1 5d/3d | More accurate event impact |

### 8.3 New Data Sources (Medium-term)

| Source | Value | Effort |
|--------|-------|--------|
| **MED_Book lastPrice tracking** | Real-time market price for owned rooms | Medium |
| **SalesOffice.Log parsed timeline** | Full price history per room (already in endpoint) | Done |
| **Provider velocity** (not just pressure) | Which OTAs are dropping fastest | Medium |
| **AirDNA/CoStar** | Airbnb/VRBO competitive data | Paid API |
| **Google Trends** | Miami hotel search interest | Free API |

### 8.4 Self-Validation Enhancements

| Enhancement | Purpose |
|-------------|---------|
| **Backtesting framework** | Run predictions on historical data, measure accuracy before deploy |
| **A/B testing** | Compare old vs new algorithm on same data |
| **Voter accuracy tracking** | Which voters are most accurate? Weight them accordingly |
| **Anomaly detection on predictions** | Flag predictions that are statistical outliers |
| **Confidence calibration** | Are 80% confidence predictions actually right 80% of the time? |

---

## 9. How to Validate the System

### 9.1 Quick Health Check

```bash
# Status
curl https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/status

# Key fields to verify:
# - scheduler_running: true
# - analysis_warming: false
# - snapshots_collected: increasing
# - collection_runtime.last_state: success
```

### 9.2 Voter Verification

```bash
# Check all 14 voters for a specific room
curl https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/signal/consensus/{detail_id}

# Each vote should have a reason — if reason starts with "No " → data missing
```

### 9.3 Scan History Verification

```bash
# Check that Log-based scan history works
curl https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/scan-history/{detail_id}?days_back=60

# Should return price_history array with old_price → new_price per scan
```

### 9.4 Accuracy Check

```bash
# Check prediction accuracy
curl https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/accuracy/summary

# Check per-hotel accuracy
curl https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/accuracy/by-hotel
```

### 9.5 Data Quality Check

```bash
# Check all source freshness
curl https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/data-quality

# Each source should have freshness > 0.5
# Protected: salesoffice (weight never reduced)
```

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **T** | Days until check-in (expiry). T=1 means tomorrow. |
| **S(t)** | Room price at time t. |
| **Forward Curve (FC)** | Bayesian-smoothed predicted price path from now to check-in. |
| **Decay Curve** | Historical average daily % change at each T-value. |
| **Enrichment** | External factor adjustment applied to FC (events, weather, etc.) |
| **Ensemble** | Weighted combination of FC + Historical + ML predictions. |
| **Momentum** | Rate of price change relative to expected (from decay curve). |
| **Regime** | Market state: NORMAL, TRENDING_UP, TRENDING_DOWN, VOLATILE, STALE. |
| **Consensus** | 14-voter majority vote (≥66% agreement required). |
| **Circuit Breaker** | Safety mechanism that blocks a failing data source. |
| **Override** | Price pushed to Zenith below SalesOffice price (PUT action). |
| **Opportunity** | Room purchased at market price for resale (CALL action). |
| **Scan** | One collection cycle — pulls all 4,058 prices from SalesOffice DB. |
| **Snapshot** | One frozen copy of all prices at a point in time. |
