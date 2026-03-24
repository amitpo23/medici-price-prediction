# Medici Arbitrage Signal Model

## Philosophy

Hotel rooms are financial options. We trade arbitrage on the T period — buying when the price dips and selling when it peaks. We don't wait for check-in. We scan every 3 hours and look for opportunities to:

- **Buy low** (CALL): price is expected to rise → buy now at current price, push at higher price later
- **Sell high** (PUT): price is expected to drop → override price down now, buy back cheaper later

The signal system identifies **when** during the T period these opportunities occur, based on multiple independent data sources voting together.

## Core Principle: Independent Source Voting

Every data source is an independent witness. No source gets more weight than another. Each votes CALL / PUT / NEUTRAL independently. The signal is determined by **consensus**.

```
10 sources, each votes independently (100% weight each)

Probability = agreeing_sources / voting_sources × 100%

≥66% agreement → Signal (CALL or PUT)
<66% agreement → NEUTRAL (no consensus, don't trade)
```

### Example

```
Source              Vote    Reason
─────────────────────────────────────────────────
Forward Curve       CALL    FC predicts +15% in T=30-45
Scan Velocity       CALL    Last 3 scans: +2%, +1.5%, +3%
Competitor Prices   PUT     Zone avg dropped 4%
Events Calendar     CALL    Ultra Music Festival in T=20
Seasonality Index   CALL    April historically +8%
Flight Demand       CALL    MIA arrivals up 12%
Weather Forecast    —       Neutral (clear, normal)
Peer Hotels         CALL    5/6 peers rising
Booking Momentum    PUT     Cancellations up 15%
Historical Pattern  CALL    Same month last year +22%
─────────────────────────────────────────────────
Result: 6 CALL / 2 PUT / 1 Neutral
Voting sources: 8 (excluding neutral)
Probability: 6/8 = 75% CALL
Signal: CALL with 75% probability
```

## The 10 Sources

### 1. Forward Curve (FC)
**What:** Bayesian-smoothed price prediction for each day in T
**Data:** SalesOffice.Details scan history → decay curve → enriched FC
**Vote logic:**
- FC shows price dip ≥5% from current → PUT
- FC shows price rise ≥30% from current → CALL
- Neither → NEUTRAL

### 2. Scan Velocity (Recent Price Movement)
**What:** Direction and speed of price changes in last 3-5 scans
**Data:** RoomPriceUpdateLog (82K+ events), SalesOffice.Details scan history
**Vote logic:**
- Last 3 scans all down, total drop ≥3% → PUT
- Last 3 scans all up, total rise ≥3% → CALL
- Mixed or flat → NEUTRAL

### 3. Competitor Prices (Market Pressure)
**What:** Are similar hotels in the same zone raising or lowering prices?
**Data:** AI_Search_HotelData (8.5M records), hotel_segments.py peer groups
**Vote logic:**
- Zone average dropped ≥3% in last scan → PUT
- Zone average rose ≥3% in last scan → CALL
- Stable → NEUTRAL

### 4. Events Calendar
**What:** Upcoming events that drive demand (concerts, conferences, sports, holidays)
**Data:** Hebcal (Jewish holidays), hardcoded Miami events, PredictHQ (future)
**Vote logic:**
- Major event within T window → CALL (demand spike)
- Event just ended within T window → PUT (demand drop)
- No significant events → NEUTRAL

### 5. Seasonality Index
**What:** Historical monthly/weekly price patterns
**Data:** Historical scan data, Miami tourism statistics
**Vote logic:**
- Current month historically shows ≥5% rise → CALL
- Current month historically shows ≥5% drop → PUT
- Flat or insufficient history → NEUTRAL

### 6. Flight Demand
**What:** Incoming flight bookings to Miami as demand proxy
**Data:** Kiwi.com MCP tool (real-time flight prices/availability)
**Vote logic:**
- Flight prices to Miami up ≥10% = high demand → CALL
- Flight prices down ≥10% = low demand → PUT
- Normal → NEUTRAL

### 7. Weather Forecast
**What:** Weather impact on tourism demand
**Data:** Open-Meteo (free, no API key)
**Vote logic:**
- Hurricane warning in T window → PUT
- Extended rain (5+ days) in T window → PUT
- Perfect weather, peak season → CALL
- Normal conditions → NEUTRAL

### 8. Peer Hotel Behavior
**What:** What are similar hotels (same zone + tier) doing?
**Data:** hotel_segments.py peer groups + current prices from analysis cache
**Vote logic:**
- Majority of peers (≥66%) prices rising → CALL
- Majority of peers (≥66%) prices falling → PUT
- Mixed → NEUTRAL

### 9. Booking Momentum (Cancellations & Bookings)
**What:** Net booking trend — are more rooms being booked or cancelled?
**Data:** MED_Book, MED_CancelBook tables
**Vote logic:**
- Net bookings positive, cancellation rate dropping → CALL
- Cancellation spike, net bookings negative → PUT
- Normal → NEUTRAL

### 10. Historical Pattern (Same Period Last Year)
**What:** What did this exact hotel + date range do last year?
**Data:** SalesOffice scan history (if available), YoY analysis
**Vote logic:**
- Same period last year price rose ≥10% → CALL
- Same period last year price dropped ≥10% → PUT
- No data or flat → NEUTRAL

## Probability Calculation

```python
def calculate_signal(votes: dict) -> dict:
    """
    votes = {
        "forward_curve": "CALL",
        "scan_velocity": "CALL",
        "competitors": "PUT",
        "events": "CALL",
        "seasonality": "NEUTRAL",
        ...
    }
    """
    call_count = sum(1 for v in votes.values() if v == "CALL")
    put_count = sum(1 for v in votes.values() if v == "PUT")
    voting_count = call_count + put_count  # NEUTRAL doesn't count

    if voting_count == 0:
        return {"signal": "NEUTRAL", "probability": 0, "consensus": "no_data"}

    call_pct = call_count / voting_count * 100
    put_pct = put_count / voting_count * 100

    if call_pct >= 66:
        return {"signal": "CALL", "probability": round(call_pct, 1), "sources_agree": call_count, "sources_disagree": put_count}
    elif put_pct >= 66:
        return {"signal": "PUT", "probability": round(put_pct, 1), "sources_agree": put_count, "sources_disagree": call_count}
    else:
        return {"signal": "NEUTRAL", "probability": 0, "consensus": "split", "call_pct": round(call_pct, 1), "put_pct": round(put_pct, 1)}
```

## Timing: When in T?

The signal isn't just CALL/PUT — it identifies **when** the opportunity occurs:

```
Option: Breakwater South Beach, T=60

Day   Price    Signal   Source Agreement
──────────────────────────────────────────
T=60  $200     —        (today)
T=55  $195     PUT 70%  Velocity↓ + Competitors↓ + Peers↓ + Seasonality↓ + FC↓
T=45  $185     PUT 80%  ← Best BUY point (lowest predicted)
T=35  $210     —        Transition
T=25  $245     CALL 75% Events↑ + Demand↑ + FC↑ + Seasonality↑ + Peers↑
T=15  $270     CALL 90% ← Best SELL point (highest predicted)
T=5   $255     —        Last-minute volatility
```

**Arbitrage trade:**
- Buy at T=45 ($185) → CALL signal, 80% PUT agreement said "price will drop"
- Sell at T=15 ($270) → PUT signal, 90% CALL agreement said "price peaked"
- Profit: $85 per room per night (46%)

## Command Center Visualization

### Signal Panel (Right Column)
```
┌─────────────────────────────────┐
│ SIGNAL: CALL  87.5%             │
│                                 │
│ Sources (7/8 agree):            │
│ ✓ Forward Curve      CALL      │
│ ✓ Scan Velocity      CALL      │
│ ✗ Competitors        PUT       │
│ ✓ Events             CALL      │
│ ✓ Seasonality        CALL      │
│ ✓ Flight Demand      CALL      │
│ — Weather            NEUTRAL   │
│ ✓ Peers              CALL      │
│ ✓ Booking Momentum   CALL      │
│ — Historical         NEUTRAL   │
│                                 │
│ Probability: 87.5%              │
│ Agreement: 7 CALL / 1 PUT      │
└─────────────────────────────────┘
```

### T-Timeline Chart (Center Column)
A chart showing predicted price over T with:
- **Green zones** = CALL periods (buy opportunities)
- **Red zones** = PUT periods (sell opportunities)
- **Gray zones** = NEUTRAL (no signal)
- **Markers** for best buy point and best sell point
- **Source agreement bars** under each day showing how many sources agree

### Source Breakdown Chart (Tab in Center)
Stacked bar chart per source per day:
- X-axis: days in T
- Y-axis: source votes
- Green bars = CALL votes
- Red bars = PUT votes
- Shows where consensus builds and breaks

## Future: Weighted Sources

Currently all sources have equal weight. In the future, we may add:
- **Backtesting weight** — sources that were historically more accurate get higher weight
- **Recency weight** — recent data slightly more important
- **Data quality weight** — sources with more data points get slight edge

This will be based on prediction accuracy tracking (already built — `accuracy_tracker.py`).

## Implementation Plan

1. **Build `src/analytics/consensus_signal.py`** — the 10-source voting engine
2. **Connect each source** — implement vote logic per source
3. **Replace `compute_next_day_signals`** — use consensus instead of single-source
4. **Add T-timeline endpoint** — predicted price + per-day source votes
5. **Update Command Center** — source agreement panel, T-timeline chart, source breakdown chart
6. **Test with real data** — compare old vs new signals on historical options
7. **Deploy and monitor** — track signal accuracy over time

## Revert

If the new model produces worse signals:
- `v2.3.1-pre-signal-fix` — old probability-based signals
- `v2.3.2-signal-logic-fix` — current FC-based (intermediate)
