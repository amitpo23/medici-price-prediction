# Voter Calibration Guide

## How the Consensus Engine Works

11 independent sources each vote CALL / PUT / NEUTRAL.
Only non-NEUTRAL votes count. Probability = agreeing / voting × 100%.
≥66% agreement + minimum voters = signal.

## Where to Change Settings

All voter thresholds are in ONE file:
```
src/analytics/consensus_signal.py
```

Each voter function has clearly marked thresholds at the top of its logic.

## Current Thresholds (v2.4.3)

### Global Settings

| Setting | Value | Location | Description |
|---------|-------|----------|-------------|
| `SIGNAL_THRESHOLD` | 66.0% | Line ~20 | Min agreement % for signal |
| `MIN_VOTING_SOURCES` | 4 | Line ~21 | Min non-NEUTRAL voters required |

### Per-Voter Thresholds

#### 1. Forward Curve (Lagging)
```python
# vote_forward_curve()
FC_DROP_PCT = 5.0     # ≥5% drop from current → PUT
FC_RISE_PCT = 30.0    # ≥30% rise from current → CALL
```
**How to adjust:**
- Lower FC_DROP_PCT = more PUT signals (e.g., 3.0 = trigger PUT on smaller drops)
- Lower FC_RISE_PCT = more CALL signals (e.g., 20.0 = trigger CALL on smaller rises)
- Higher = fewer signals, more selective

#### 2. Scan Velocity (Coincident)
```python
# vote_scan_velocity()
VELOCITY_THRESHOLD = 0.03  # ±3% velocity → signal
```
**How to adjust:**
- Lower = more sensitive to small price movements
- Higher = only reacts to big moves
- Also checks acceleration direction (accel ≥ 0 for CALL, ≤ 0 for PUT)

#### 3. Competitors (Coincident)
```python
# vote_competitors()
COMP_BELOW_PCT = -15.0   # Price ≤15% below tier avg → CALL
COMP_ABOVE_PCT = 10.0    # Price ≥10% above tier avg → PUT
COMPARE_MODE = "tier"     # "tier" = same zone+tier, "zone" = whole zone
```
**How to adjust:**
- `COMPARE_MODE = "tier"` → Freehand vs Viajero (both budget)
- `COMPARE_MODE = "zone"` → Freehand vs everything in South Beach
- Wider BELOW/ABOVE range = fewer signals
- Narrower = more signals

#### 4. Events Calendar (Leading)
```python
# vote_events()
EVENT_IMPACT_MIN = "medium"  # Minimum event impact level
```
**How to adjust:**
- `"high"` = only major events (Art Basel, Ultra, F1)
- `"medium"` = includes conferences, holidays
- `"low"` = every event triggers signal

#### 5. Seasonality Index (Leading)
```python
# vote_seasonality()
SEASON_THRESHOLD = 0.05  # ±5% seasonal enrichment → signal
```
**How to adjust:**
- Higher = only strong seasonal effects trigger (e.g., 0.08 = 8%)
- Lower = more sensitive (e.g., 0.02 = 2%)
- Based on `season_adj_pct` from forward curve enrichment

#### 6. Flight Demand (Leading)
```python
# vote_flight_demand()
DEMAND_THRESHOLD = 0.03  # ±3% demand enrichment → signal
```
**How to adjust:**
- Higher = only significant demand shifts trigger
- Lower = more sensitive to small demand changes

#### 7. Weather Forecast (Leading)
```python
# vote_weather()
WEATHER_NEG_THRESHOLD = -0.05  # ≤-5% weather impact → PUT
WEATHER_POS_THRESHOLD = 0.03   # ≥3% weather boost → CALL
```
**How to adjust:**
- `WEATHER_NEG_THRESHOLD` closer to 0 = more PUT from bad weather
- `WEATHER_POS_THRESHOLD` higher = less CALL from good weather

#### 8. Peer Hotel Behavior (Coincident)
```python
# vote_peers()
PEER_AGREEMENT = 0.66  # 66% of peers must agree on direction
```
**How to adjust:**
- Higher (0.80) = needs 80% of peers moving same direction
- Lower (0.50) = simple majority of peers

#### 9. Booking Momentum (Lagging)
```python
# vote_booking_momentum()
CANCEL_THRESHOLD = -0.03  # ≤-3% cancellation impact → PUT
```
**How to adjust:**
- More negative = only high cancellation spikes trigger PUT
- Less negative = more sensitive to cancellations

#### 10. Historical Pattern (Lagging)
```python
# vote_historical()
HISTORICAL_THRESHOLD = 65.0  # ≥65% historical direction → signal
```
**How to adjust:**
- Higher (75.0) = only strong historical patterns trigger
- Lower (55.0) = weaker patterns also trigger

#### 11. Official Market Benchmark (Lagging)
```python
# vote_official_benchmark()
BENCH_BELOW_PCT = -20.0  # Price ≤20% below official ADR → CALL
BENCH_ABOVE_PCT = 15.0   # Price ≥15% above official ADR → PUT
```
**How to adjust:**
- Wider range = fewer signals (price must deviate more)
- Narrower range = more signals

## Calibration Changes Log

### v2.4.4 (Current)

| Voter | Before | After | Why |
|-------|--------|-------|-----|
| Competitors | zone avg (all tiers) | **same tier avg** | Freehand vs Viajero, not vs Hilton Bentley |
| Competitors below | -15% | -15% | Unchanged |
| Competitors above | +10% | +10% | Unchanged |
| Seasonality | 2% | **5%** | 2% is noise, not signal |
| Flight demand | 1% | **3%** | 1% is noise |
| Weather negative | -3% | **-5%** | Only significant weather events |
| Weather positive | 1% | **3%** | Normal clear weather shouldn't trigger |
| MIN_VOTING_SOURCES | none | **4** | Prevents signal from 3/4 votes when 7 are neutral |

### v2.4.3 (Before calibration)
All original thresholds as first implemented.

## How to Tune

### Step 1: Check current distribution
```bash
curl -s ".../options?limit=500&profile=lite" | python3 -c "
import sys,json;d=json.load(sys.stdin)
rows=d.get('rows',[])
calls=sum(1 for r in rows if r.get('option_signal') in ('CALL','STRONG_CALL'))
puts=sum(1 for r in rows if r.get('option_signal') in ('PUT','STRONG_PUT'))
nones=len(rows)-calls-puts
print(f'CALL: {calls} ({calls/len(rows)*100:.0f}%)')
print(f'PUT: {puts} ({puts/len(rows)*100:.0f}%)')
print(f'NEUTRAL: {nones} ({nones/len(rows)*100:.0f}%)')
"
```

### Step 2: Check individual voter behavior
```bash
curl -s ".../signal/consensus/42236" | python3 -c "
import sys,json;d=json.load(sys.stdin)
for v in d.get('votes',[]):
    print(f'{v[\"source\"]:25s} {v[\"vote\"]:8s} {v[\"reason\"][:60]}')
"
```

### Step 3: Change threshold in consensus_signal.py

### Step 4: Run tests
```bash
python3 -m pytest tests/unit/test_consensus_signal.py -v
```

### Step 5: Deploy and check distribution again

### Target Distribution
A healthy distribution for Miami hotels should be roughly:
- **CALL: 5-15%** — clear buy opportunities
- **PUT: 5-15%** — clear sell opportunities
- **NEUTRAL: 70-90%** — no action, wait for signal

If CALL > 30% or PUT > 30%, thresholds are too loose.
If NEUTRAL > 95%, thresholds are too tight.

## Revert Points

| Tag | Description |
|-----|-------------|
| `v2.4.4-calibrated` | After calibration (current) |
| `v2.4.3-pre-calibration` | Before calibration (98% CALL) |
| `v2.4.2-consensus-engine-live` | Consensus engine first deploy |
| `v2.3.2-signal-logic-fix` | FC-based signals (before consensus) |
| `v2.3.1-pre-signal-fix` | Original probability-based signals |
