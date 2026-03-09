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
| `GET /api/v1/salesoffice/options` | JSON | Options-style rows with min/max path, touch counts, $20 change counts, sources, and chart payload |
| `GET /api/v1/salesoffice/options/legend` | JSON | UI legend for `i/?` icon and source/quality interpretation |
| `GET /api/v1/salesoffice/options/detail/{detail_id}` | JSON | Trading chart data: FC series, scan series, signal weights, momentum, regime |
| `GET /api/v1/salesoffice/sources/audit` | JSON | Runtime audit of all configured data sources (active/degraded/planned) |
| `GET /api/v1/salesoffice/forward-curve/{detail_id}` | JSON | Day-by-day prediction for one room |
| `GET /api/v1/salesoffice/decay-curve` | JSON | The learned price change pattern |

### Options Endpoint Notes

`GET /api/v1/salesoffice/options` returns one row per room with:

- `option_signal`: `CALL` / `PUT` / `NEUTRAL`
- `expected_min_price`, `expected_max_price`
- `touches_expected_min`, `touches_expected_max`
- `count_price_changes_gt_20`, `count_price_changes_lte_20`
- PUT-focus path analytics across `T`:
	- `put_decline_count` (how many downward moves happened in the horizon)
	- `put_total_decline_amount` (total accumulated drop amount across all down-steps)
	- `put_largest_single_decline` (largest single step-down amount)
	- `put_first_decline_date`, `put_largest_decline_date`
	- `t_min_price`, `t_max_price` and `t_min_price_date`, `t_max_price_date`
	- `put_downside_from_now_to_t_min`, `put_rebound_from_t_min_to_checkin`
	- `put_decline_events` (step-by-step list: `from_date`, `to_date`, `from_price`, `to_price`, `drop_amount`)
- `sources`: per-signal model sources and reasoning
- `quality`: score + confidence summary
- `option_levels`: non-breaking 10-level strength (`CALL_L1..L10` / `PUT_L1..L10`, plus score)
- `info`: UI-ready info marker (`icon` = `i` / `?`) + tooltip text with source summary
- `chart`: labels + predicted / lower / upper series (for direct chart rendering)

Top-level metadata includes `source_validation` with basic checks for core sources.
Top-level metadata also includes `sources_audit_summary` for full-source runtime health snapshot.

Response envelope (top-level) includes:

- `run_ts`, `total_rows`, `t_days_requested`
- `source_validation`, `sources_audit_summary`, `data_sources`
- `rows` (list of room-level option rows)

`/api/v1/salesoffice/sources/audit` now explicitly reports:

- `trivago_statista` status based on local file `data/miami_benchmarks.json`
- `brightdata_mcp` status based on `.mcp.json` MCP server configuration

`GET /api/v1/salesoffice/options/legend` now includes compatibility + explicit scales:

- `legend_version`
- `scale`, `levels`, `call_levels`, `put_levels`
- `option_levels` (kept for backward compatibility)
- `info_icon_rules`, `quality_score_bands`, `source_fields`

`GET /api/v1/salesoffice/sources/audit` returns:

- `status` (`ok` / `degraded`)
- `summary`, `checks`, `source_validation`, `sources`

Note: `status = degraded` is an informational runtime state (for example missing external files), not an API failure.

Optional query parameters:

- `t_days` — analyze only the first T prediction days
- `include_chart` — include/remove chart payload per row
- `profile` — `full` (default) or `lite` (keeps existing schema, disables chart payload)
- `include_system_context` — include top-level `system_capabilities` snapshot (default: true)

Additional top-level additive fields:

- `profile_applied`
- `system_capabilities` (existing system/data coverage summary from forward-curve, historical patterns, events, flights, benchmarks)

### Inline Trading Charts (v1.1.0)

The HTML dashboard (`/options/view`) includes expandable trading chart panels per row:

1. **Click the ▼ button** in the ID column to expand a row
2. A chart panel appears below the row showing:
   - **Forward Curve** (blue line) with confidence band (shaded area)
   - **Adjusted Forward Curve** (orange line) when enrichment adjustments differ
   - **Actual scan prices** as colored dots (green = rise, red = drop)
   - **Current price** (dashed blue) and **predicted price** (dashed green) horizontal lines
   - **Min/Max markers** labeled on the chart
3. An **info panel** next to the chart shows signal weights, FC adjustments, momentum, regime

**Data is loaded lazily** — chart data is fetched via AJAX only when expanding a row, keeping the page fast.

### Detail Endpoint (v1.1.0)

`GET /api/v1/salesoffice/options/detail/{detail_id}` returns compact JSON for a single room:

```json
{
  "fc": [{"d": "03-08", "p": 330.1, "lo": 310, "hi": 350}],
  "scan": [{"d": "03-05", "p": 325.0}],
  "cp": 330.1, "pp": 825.25,
  "mn": 310.0, "mx": 860.0,
  "sig": "CALL", "chg": 150.0,
  "fcW": 0.5, "fcC": 0.85,
  "hiW": 0.3, "hiC": 0.7,
  "adj": {"comp": -0.02, "cancel": -0.01, "demand": 0.15},
  "mom": {"signal": "ACCELERATING_UP", "strength": 0.65},
  "reg": {"regime": "NORMAL", "z_score": 0.5},
  "drops": 2, "rises": 8, "scans": 10
}
```

### External Data
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/flights/demand` | JSON | Flight demand indicator |
| `GET /api/v1/salesoffice/events` | JSON | Events and conferences |
| `GET /api/v1/salesoffice/benchmarks` | JSON | Booking behavior benchmarks |
| `GET /api/v1/salesoffice/knowledge` | JSON | Hotel competitive landscape |

### Scenario Analysis (v2.0.0)
| Endpoint | Format | Description |
|----------|--------|-------------|
| `POST /api/v1/salesoffice/scenario/run` | JSON | Run what-if scenario with override factors |
| `GET /api/v1/salesoffice/scenario/presets` | JSON | List 5 preset scenarios |
| `POST /api/v1/salesoffice/scenario/compare` | JSON | Compare multiple scenarios side-by-side |

Override factors for `POST /scenario/run`:
- `event_impact` (0–200): percentage of normal event impact (0 = cancelled)
- `flight_delta` (-50 to +50): % change in flight demand
- `weather_severity`: normal / rain / storm / heatwave / hurricane / clear
- `competitor_delta` (-20 to +20): % competitor price change
- `demand_multiplier` (0.5–2.0): demand scaling factor
- `seasonal_override`: peak / shoulder / off

Example:
```json
POST /api/v1/salesoffice/scenario/run
{"demand_multiplier": 1.5, "competitor_delta": 15}
```

Returns delta table: baseline_price, scenario_price, delta_dollars, delta_pct, signal_changed for each room.

### Alerts & Monitoring (v2.0.0)
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/alerts/history?days=7` | JSON | Alert log with timestamps, severity, rooms |
| `POST /api/v1/salesoffice/alerts/test` | JSON | Fire test alert to all configured channels |
| `GET /api/v1/salesoffice/alerts/stats` | JSON | Alert volume, top rules, counts |
| `GET /api/v1/salesoffice/data-quality/status` | JSON | All sources with freshness/reliability scores |
| `GET /api/v1/salesoffice/data-quality/history?source=open_meteo&days=30` | JSON | Source health history |

### Prediction Accuracy (v2.0.0)
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /api/v1/salesoffice/accuracy/summary?days=30` | JSON | MAE, MAPE, directional accuracy |
| `GET /api/v1/salesoffice/accuracy/by-signal` | JSON | Precision/recall per CALL/PUT/NEUTRAL |
| `GET /api/v1/salesoffice/accuracy/by-t-bucket` | JSON | Accuracy for T ranges: 1-7, 8-14, 15-30, 31-60, 61+ |
| `GET /api/v1/salesoffice/accuracy/by-hotel` | JSON | Per-hotel accuracy breakdown |
| `GET /api/v1/salesoffice/accuracy/trend` | JSON | Rolling 7/30-day accuracy trend |

### System & Health
| Endpoint | Format | Description |
|----------|--------|-------------|
| `GET /health` | JSON | Health check with source status, cache metrics, prediction summary |
| `GET /health/view` | HTML | Health dashboard with green/yellow/red indicators |
| `GET /api/v1/salesoffice/status` | JSON | System health and snapshot count |
| `GET /api/v1/salesoffice/debug` | JSON | Debug info with error details |
| `GET /api/v1/salesoffice/export/csv/contracts` | CSV | Export all contracts |
| `GET /api/v1/salesoffice/export/csv/providers` | CSV | Export provider data |
| `GET /api/v1/salesoffice/export/summary` | JSON | Portfolio summary |

---

## Statista Ingestion (Local Pipeline)

To ingest Statista-derived Miami ADR data into the system:

```bash
python scripts/ingest_statista_data.py
```

Optional additional search path:

```bash
python scripts/ingest_statista_data.py --path ~/Downloads --path ~/Documents
```

Expected outputs after successful ingestion:

- `data/processed/statista_miami_monthly_adr.csv`
- `data/miami_benchmarks.json`

Then check runtime source status via:

```bash
GET /api/v1/salesoffice/sources/audit
```

---

## Bright Data OTA Ingestion (Airbnb, Booking, Expedia, ...)

To ingest OTA export files collected via Bright Data:

```bash
python scripts/ingest_brightdata_market_data.py
```

Optional additional search path:

```bash
python scripts/ingest_brightdata_market_data.py --path ~/Downloads --path ~/Documents
```

Expected outputs:

- `data/processed/brightdata_ota_rates.csv`
- `data/processed/brightdata_ota_summary.json`

How to verify Airbnb and other OTA data was loaded:

- Call `GET /api/v1/salesoffice/sources/audit`
- Check source `ota_brightdata_exports` evidence (`rows=...`, `platforms=airbnb,booking,...`)

---

## Pagination (v2.0.0)

Endpoints returning large datasets support pagination:

```
GET /api/v1/salesoffice/options?limit=100&offset=0
```

| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `limit` | 100 | 1000 | Number of items per page |
| `offset` | 0 | — | Items to skip |
| `all` | false | — | Return all items (escape hatch) |

Response includes pagination metadata:
```json
{
  "items": [...],
  "total": 2850,
  "limit": 100,
  "offset": 0,
  "has_more": true
}
```

Paginated endpoints: `/options`, `/data`, `/simple`, `/ai/metadata`

---

## API Authentication (v2.0.0)

If `API_KEYS` is set in the environment, all `/api/` endpoints require authentication:

```
GET /api/v1/salesoffice/options
Authorization: Bearer your-api-key
```

Or via query parameter:
```
GET /api/v1/salesoffice/options?api_key=your-api-key
```

Multiple API keys are supported (comma-separated in `API_KEYS` env var).

---

## Rate Limiting (v2.0.0)

| Endpoint Group | Limit |
|----------------|-------|
| Data endpoints | 100 requests/minute per IP |
| AI endpoints (`/ai/*`) | 20 requests/minute per IP |
| Export endpoints (`/export/*`) | 10 requests/minute per IP |

When rate limited, the API returns `429 Too Many Requests` with a `Retry-After` header.

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

**Q: How do I run a what-if scenario?**
A: Use `POST /scenario/run` with override factors (e.g., `{"demand_multiplier": 1.5}`). The engine applies adjustments to cached predictions without re-running the full pipeline. Use `GET /scenario/presets` to see 5 pre-built scenarios like "Art Basel Cancelled" or "Hurricane Warning".

**Q: How do I set up alerts?**
A: Configure `ALERT_WEBHOOK_URL` and/or `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in your environment. Alerts fire automatically during scan cycles when surge (>10% up, 5+ rooms) or drop events are detected. Use `POST /alerts/test` to verify your channels work. Check `GET /alerts/history` for recent alerts.

**Q: How accurate are the predictions?**
A: Check `GET /accuracy/summary?days=30` for MAE, MAPE, and directional accuracy. The system tracks every prediction and scores it against actual prices once check-in passes. Use `/accuracy/by-t-bucket` to see how accuracy varies by booking window.
