# Medici Price Prediction — Usage Guide

How to use and understand the analysis system.

---

## Quick Start

### View Simplified Analysis (Recommended)

**JSON format** — for apps and dashboards:
```
GET /api/v1/salesoffice/simple
```

**Plain text** — for quick reading in terminal or email:
```
GET /api/v1/salesoffice/simple/text
```

### View Full Dashboard
Open in browser:
```
GET /api/v1/salesoffice/dashboard
```

### Check System Status
```
GET /api/v1/salesoffice/status
```

---

## Understanding the Simplified Output

The simplified analysis has 4 sections:

### 1. Summary
A one-paragraph overview of your portfolio:
```
"You have 45 rooms across 3 hotels. Average price: $850.
12 rooms have price predictions. 3 rooms need attention.
Predictions based on 500 historical price tracks."
```

### 2. Predictions (per room)
Each room shows:

| Field | Meaning |
|-------|---------|
| `current_price` | Latest observed price from SalesOffice |
| `predicted_price` | Expected price at check-in date |
| `expected_change_pct` | How much the price is expected to change (%) |
| `trend` | RISING / FALLING / STABLE |
| `status` | NORMAL / WATCH / WARNING |
| `confidence` | HIGH / MEDIUM / LOW — how reliable the prediction is |
| `direction` | Plain text explanation (e.g., "Price expected to increase ~$60 by check-in") |
| `days_to_checkin` | How many days until check-in |

### 3. Attention Items
Rooms that need your action. Each item has:

| Field | Meaning |
|-------|---------|
| `reason` | What's happening (e.g., "Price DROPPING: $1200 -> $1050 (-12.5%)") |
| `action` | What to do (e.g., "Consider repricing or cancellation") |
| `urgency` | HIGH / MEDIUM / LOW |

### 4. Market Overview
Portfolio-level numbers: total rooms, average price, price range, breakdown by category and board type.

---

## Reading Predictions

### Trend
- **RISING** — Price is going up. Good if you're selling; buy opportunities may be disappearing.
- **FALLING** — Price is going down. Consider repricing. New buy opportunities may appear.
- **STABLE** — Price is flat. No immediate action needed.

### Status
- **NORMAL** — Room is behaving as expected based on historical patterns.
- **WATCH** — Room is slightly diverging from expected behavior. Keep an eye on it.
- **WARNING** — Room is behaving unusually (volatile, dropping fast, or stale data). Take action.

### Confidence
- **HIGH** — Prediction is backed by many similar historical observations. Reliable.
- **MEDIUM** — Some historical data available. Reasonably reliable.
- **LOW** — Limited historical data for this T value. Take prediction with caution.

---

## When to Act

### Immediate Action Required
- Urgency: **HIGH**
- Room dropping >10% with check-in approaching
- Cancel deadline within 5 days and position unprofitable

### Review Soon
- Urgency: **MEDIUM**
- Volatile pricing (swinging up and down)
- Price trending below expectations
- Accelerating price drops

### Monitor
- Urgency: **LOW**
- Slight divergence from expected pattern
- Stale prices (possible data issue, not necessarily a problem)

---

## API Endpoints Reference

### Simplified (Human-Readable)
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/simple` | JSON | Simplified 4-section analysis |
| `GET /api/v1/salesoffice/simple/text` | Text | Plain text report |

### Full Detail
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/dashboard` | HTML | Interactive visual dashboard |
| `GET /api/v1/salesoffice/data` | JSON | Full raw analysis data |
| `GET /api/v1/salesoffice/forward-curve/{detail_id}` | JSON | Day-by-day prediction for one room |
| `GET /api/v1/salesoffice/decay-curve` | JSON | The learned price change pattern |

### External Data
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/flights/demand` | JSON | Flight demand indicator |
| `GET /api/v1/salesoffice/events` | JSON | Events and conferences |
| `GET /api/v1/salesoffice/benchmarks` | JSON | Booking behavior benchmarks |
| `GET /api/v1/salesoffice/knowledge` | JSON | Hotel competitive landscape |

### System
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/status` | JSON | System health and snapshot count |
| `GET /api/v1/salesoffice/debug` | JSON | Debug info with error details |

---

## FAQ

**Q: Why is confidence LOW?**
A: The system doesn't have enough historical price observations for rooms at this number of days before check-in. As more price snapshots are collected, confidence will improve.

**Q: What does VOLATILE mean?**
A: The room's price is swinging up and down more than expected between 3-hour scans. This could mean the supplier is actively adjusting prices, or there's unusual market activity.

**Q: What does STALE mean?**
A: The price hasn't changed across 16+ scans (48+ hours). This is unusual — it could mean the data feed isn't updating, or the supplier genuinely hasn't changed the price.

**Q: How often are predictions updated?**
A: The system collects new prices every hour and re-runs the analysis. Predictions are always based on the latest available data.

**Q: What if there's no historical data?**
A: The system falls back to a default model that assumes prices are approximately stable (~0.01% daily decrease). Predictions will be less accurate until enough data is collected.

**Q: How many snapshots are needed for good predictions?**
A: The system starts producing predictions with 2+ snapshots, but quality improves significantly with 50+ historical price tracks. Momentum detection needs 2+ snapshots; regime detection needs 4+.

**Q: Can I trust the predicted check-in price?**
A: Use the confidence level and interval. HIGH confidence with a narrow range = reliable. LOW confidence with a wide range = take it as a rough estimate. The predicted price is the most likely value, but the actual price could be anywhere within the confidence interval.

**Q: What's the difference between `/simple` and `/data`?**
A: `/simple` is human-readable with plain language (RISING/FALLING/STABLE). `/data` is the full technical output with momentum velocities, Z-scores, and regime classifications — useful for debugging or building custom analysis.
