# Next-Scan Price Drop Prediction Skill

## Purpose
Predict which rooms will see a price DROP of ≥5% between the current scan and the next scan (typically 3 hours later). This is a **short-term PUT signal** — not about the final check-in price, but about the immediate next price movement.

## Why This Matters
Even if a room's long-term trend is upward (CALL), it may experience temporary dips between scans. These dips represent PUT opportunities — moments to buy at a lower price, even if the overall trajectory is upward.

## Data Sources

### Primary: Azure SQL (medici-db)
1. **RoomPriceUpdateLog** — every price change event with timestamp
   - `PreBookId`, `Price`, `DateInsert`
   - 82K+ rows, real-time updates

2. **AI_Search_HotelData** — competitor pricing (8.5M rows)
   - Same-star hotels in same city, recent prices
   - Market pressure indicator

3. **SalesOffice.Log** — detailed scan log
   - `DbRoomPrice: X -> API RoomPrice: Y` pattern
   - `ActionId = 3` (Detail Updated), `ActionId = 6` (Zenith Push)

4. **SalesOffice.Details** — current room state
   - `HotelId`, `RoomCategory`, `RoomBoard`, `RoomPrice`, `DateCreated`

### Secondary: Local SQLite (price_store.db)
- Hourly price snapshots with full history per detail_id
- Enables inter-scan velocity and acceleration calculation

## Detection Logic

### Feature Extraction (per room)
1. **Scan velocity** — price change rate over last 3, 6, 12 hours
2. **Scan acceleration** — is the drop speeding up or slowing down?
3. **Drop frequency** — how often does this room drop between scans?
4. **Market pressure** — are competitor prices falling? (from AI_Search)
5. **Day-of-week pattern** — some days have more drops (supply adjustments)
6. **Time-of-day pattern** — supplier price updates cluster at certain hours
7. **Category volatility** — Deluxe/Suite more volatile than Standard
8. **Recent drop streak** — 2+ consecutive drops = momentum

### Signal Rules
- **STRONG_PUT**: velocity < -5%/scan AND acceleration < 0 AND recent drop streak ≥2
- **PUT**: expected next-scan drop ≥5% based on features
- **WATCH**: drop probability 30-50% OR velocity trending negative
- **NEUTRAL**: no significant drop expected

### Probability Model
```
P(drop ≥ 5% in next scan) = f(
    velocity_3h,
    acceleration,
    drop_frequency,
    market_pressure,
    dow_pattern,
    category_volatility,
    recent_streak
)
```

Simple weighted scoring (no ML required):
- velocity_3h < -3%/scan: +30 points
- acceleration < 0: +15 points
- drop_frequency > 40%: +20 points
- market_pressure negative: +10 points
- consecutive drops ≥ 2: +15 points
- volatile category (Suite/Deluxe): +10 points

Total > 50: PUT signal
Total > 70: STRONG_PUT signal

## Output
```json
{
  "signal": "PUT",
  "strength": 7,
  "probability": 0.65,
  "expected_drop_pct": -7.2,
  "features": {
    "velocity_3h": -4.1,
    "acceleration": -0.8,
    "drop_frequency": 0.45,
    "market_pressure": -0.12,
    "recent_streak": 2
  }
}
```

## How to Run
```bash
python skills/next-scan-drop/predictor.py --connection-string "..." --out report
# OR
python skills/next-scan-drop/predictor.py --api-url "https://medici-prediction-api.azurewebsites.net"
```

## Integration
- Runs every scan cycle (3 hours) via scheduler
- Feeds into `/api/v1/salesoffice/options` as PUT signal source
- Alerts via Telegram/Webhook when STRONG_PUT detected
