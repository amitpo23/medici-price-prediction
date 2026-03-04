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
