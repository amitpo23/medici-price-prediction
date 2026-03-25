# Medici Prediction Engine — Complete Technical Guide

## What This Skill Does

This is the brain of Medici. It predicts hotel room prices along the T-timeline
(days to check-in) and generates CALL/PUT/NEUTRAL trading signals.

**Input**: 4,000+ room prices scanned every 3 hours from SalesOffice DB
**Output**: Per-room signal (CALL/PUT/NEUTRAL) with probability, enrichment breakdown, and price path

---

## Architecture Overview

```
Data Sources (12)
  ↓
Collection (every 3h) → SQLite snapshots
  ↓
Decay Curve (Bayesian smoothed from 7M+ historical observations)
  ↓
Forward Curve Walk (9 enrichments per day)
  ↓
Ensemble: FC 70% + Historical 10% + ML 20%
  ↓
14-Voter Consensus Engine (≥66% agreement, min 4 voters)
  ↓
Signal: CALL / PUT / NEUTRAL with probability %
  ↓
Rules Engine → Auto-Execute (Override for PUT, Opportunity for CALL)
```

---

## The Decay Curve — Foundation of Everything

### What It Is
A statistical model of how hotel room prices change as T (days to check-in) decreases.
Built from **two data sources**:
- SalesOffice.Details scans (36+ days, real-time)
- MED_SearchHotels archive (7M rows, 2020-2023)

### How It's Built

1. **Extract T-observations**: For each consecutive scan pair of the same room:
   ```
   daily_change_pct = (price_new - price_old) / price_old × 100 / gap_days
   T = days from scan midpoint to check-in date
   weight = 1.0 / (1.0 + 0.1 × gap_days)  # closer scans = more reliable
   ```

2. **Bin by T** (overlapping bins prevent data loss):
   ```
   T = 1-30:   bins of 5 days, step 1
   T = 31-60:  bins of 7 days, step 2
   T = 61-90:  bins of 10 days, step 3
   T = 91-180: bins of 14 days, step 7
   ```

3. **Bayesian smoothing** per bin:
   ```
   smoothed = (N × sample_mean + 5 × global_mean) / (N + 5)
   ```
   Few observations → trusts global average.
   Many observations → trusts local data.

4. **Probability distribution** per T:
   ```
   P(up)    = scans where price rose > 0.1%
   P(down)  = scans where price dropped > 0.1%
   P(stable) = everything else
   ```

### Why 7M Rows Matter
With only 36 days of SalesOffice data, the curve only saw one direction (prices rising
into Miami peak season). With 3 years of MED_SearchHotels, it sees full seasonal cycles:
- Feb peak (+9.9%/month average)
- Sep trough (-15.5%/month average)
- Event spikes (Art Basel, F1, Ultra)
- Post-event drops

---

## Forward Curve Walk — Price Path Prediction

Starting from current price, walk each day from T down to 1:

```python
for each day (T → 1):
    base = decay_curve.get_daily_change(t)     # from Bayesian curve

    # 9 Enrichment adjustments (daily %):
    + event_adj      # Miami events: Art Basel +5.7%, F1 +5.7%
    + season_adj     # Monthly: Feb +0.30%/day, Sep -0.47%/day
    + demand_adj     # Flights: HIGH +0.15%, LOW -0.15%
    + weather_adj    # Rain -0.05%, hurricane -0.15%, clear +0.02%
    + competitor_adj # AI_Search 8.5M rows: pressure × 0.20%
    + cancel_adj     # MED_CancelBook: -risk × 0.25%
    + provider_adj   # 129 OTA providers: pressure × 0.20%
    + momentum_adj   # Recent velocity × exp(-0.15 × day) × 0.3
    + offset_adj     # Room type premium/discount

    predicted_price *= (1 + total_daily_pct / 100)
```

**Confidence interval** (95%): accumulates volatility per day, bounds = price ± 1.96 × cumulative_std

---

## Ensemble — Three Signals Combined

| Signal | Weight | Source | What It Does |
|--------|--------|--------|-------------|
| Forward Curve | 70% | Decay curve walk | Projects price path based on historical T-behavior |
| Historical Pattern | 10% | Same-period last year | Compares to same month/DOW/lead-time bucket |
| ML (LightGBM) | 20% | Trained model | Direct price prediction from features |

### Dynamic Weight Scaling
```
effective_weight = base_weight × (0.5 + 0.5 × confidence)
```
High data density → full weight. Low density → half weight.

### Safety Clamps
```
Max prediction: current_price × 1.30  (+30%)
Min prediction: current_price × 0.70  (-30%)
Sanity blend triggered at: ±40% deviation from current
```

---

## 14-Voter Consensus Engine

### Rules
- NEUTRAL votes excluded from count
- Need ≥4 non-NEUTRAL voters
- Need ≥66% agreement for CALL or PUT
- Otherwise: NEUTRAL

### Voter Table

| # | Voter | When it votes CALL | When it votes PUT |
|---|-------|--------------------|-------------------|
| 1 | Forward Curve | FC change ≥ +15% | FC change ≤ -5% |
| 2 | Scan Velocity | velocity > +3%/day | velocity < -3%/day |
| 3 | Competitors | price ≤ -15% vs zone avg | price ≥ +10% vs zone avg |
| 4 | Events | upcoming event in T window | post-event period |
| 5 | Seasonality | season adj > +5% | season adj < -5% |
| 6 | Flight Demand | demand adj > +3% | demand adj < -3% |
| 7 | Weather | weather adj > +3% | weather adj < -5% |
| 8 | Peers | ≥66% peers rising | ≥66% peers falling |
| 9 | Booking Momentum | — | cancel adj < -2% |
| 10 | Historical | P(up) ≥ 65% | P(down) ≥ 65% |
| 11 | Official Benchmark | price ≤ -20% vs ADR | price ≥ +15% vs ADR |
| 12 | Scan Drop Risk | drop score ≤ -10 | drop score ≥ 50 |
| 13 | Provider Spread | pressure ≥ +0.1 | pressure ≤ -0.1 |
| 14 | Margin Erosion | margin ≥ +15% | margin ≤ -3% |

### Categories
- **Leading** (predict future): Events, Seasonality, Flights, Weather
- **Coincident** (current state): Velocity, Competitors, Peers, Scan Drop Risk, Provider Spread
- **Lagging** (confirmed patterns): FC, Booking Momentum, Historical, Benchmark, Margin Erosion

---

## Self-Correction Mechanisms

### 1. Accuracy Tracking
Every prediction is logged. When check-in passes, actual price is compared:
```
MAE  = mean(|actual - predicted|)
MAPE = mean(|error_pct|)
Directional = % of CALL/PUT signals that were correct
```

### 2. Data Quality Auto-Degrade
Each source has expected freshness (1h for SalesOffice, 24h for weather).
If `freshness < 0.5` → source weight automatically reduced.

### 3. Circuit Breaker
3 consecutive failures → source blocked → probe after 5 minutes → auto-recover.

### 4. Sanity Clamps
Prediction > 1.3× current → clamped. Prediction < 0.7× current → clamped.
Outlier predictions get confidence penalty (min 0.05 multiplier).

### 5. Scheduler Watchdog
Middleware checks every 60 seconds if scheduler is alive.
If dead → restarts automatically. Never goes more than 60s without detection.

---

## Data Sources

### Primary (Azure SQL — medici-db)
| Source | Rows | Used For |
|--------|------|----------|
| SalesOffice.Details | 4,000+ active | Current prices (scanned every 3h) |
| SalesOffice.Log | 1.2M+ | Price change audit trail (scan history) |
| MED_SearchHotels | 7M (2020-2023) | Decay curve foundation (3 years) |
| AI_Search_HotelData | 8.5M | Competitor pricing |
| SearchResultsPollLog | 8.3M, 129 providers | Provider pressure |
| RoomPriceUpdateLog | 82K+ | Price velocity/momentum |
| MED_Book | 10.7K | Active inventory (margin tracking) |
| MED_CancelBook | 4.7K | Cancellation demand signal |

### External APIs
| Source | Data | Status |
|--------|------|--------|
| Open-Meteo | Weather forecast | Connected |
| Ticketmaster/SeatGeek | Miami events | Connected (8 major hardcoded) |
| GMCVB | Official ADR by zone | Connected |
| Kiwi.com | Flight demand | NOT connected (collector off) |
| FRED | Hotel PPI, CPI | NOT connected (no API key) |

---

## How to Validate

### Quick Health Check
```bash
curl .../api/v1/salesoffice/status
# Check: scheduler_running=true, analysis_warming=false, last_state=success
```

### Voter Audit
```bash
curl .../api/v1/salesoffice/signal/consensus/{detail_id}
# Each vote should have a reason. "No " prefix = data missing.
```

### Price History
```bash
curl .../api/v1/salesoffice/scan-history/{detail_id}?days_back=60
# Should return price changes from SalesOffice.Log
```

### Signal Distribution
Check Command Center header: should see mix of CALL/PUT/NEUTRAL.
If 100% CALL or 100% PUT → something wrong with decay curve or clamps.

---

## Known Issues & Improvement Roadmap

### Current Gaps
1. **Kiwi flights collector off** → demand_adj always 0
2. **FRED no API key** → no macro context
3. **Cancellation adj always 0** → not flowing into FC enrichment
4. **ML model not trained** → 20% weight slot unused
5. **Accuracy scoring empty** → no retroactive learning yet

### Planned Improvements
1. **Per-zone seasonality** (South Beach vs Airport vs Downtown)
2. **Adaptive Bayesian K** based on data density
3. **Cross-hotel correlation** within zone+tier
4. **Backtesting framework** on historical data
5. **Voter accuracy tracking** → weight voters by their track record

---

## File Map

| File | Purpose |
|------|---------|
| `config/constants.py` | All thresholds, weights, caps |
| `src/analytics/forward_curve.py` | Decay curve + FC walk |
| `src/analytics/deep_predictor.py` | Ensemble combiner |
| `src/analytics/consensus_signal.py` | 14-voter engine |
| `src/analytics/momentum.py` | Velocity/acceleration |
| `src/analytics/collector.py` | Price collection + MED_SearchHotels merge |
| `src/analytics/analyzer.py` | Main analysis pipeline |
| `src/analytics/accuracy_tracker.py` | Prediction accuracy |
| `src/analytics/data_quality.py` | Source freshness monitoring |
| `src/services/circuit_breaker.py` | Failure detection |
| `src/api/middleware.py` | Scheduler watchdog |
| `docs/KNOWLEDGE_BASE.md` | Full system specification |
