# Claude Code Prompt — Source Attribution Engine Deploy

---

## Context

A new **Source Attribution Engine** was added to Medici Price Prediction. It isolates each prediction source (Forward Curve, Historical, ML) and runs them independently at 100% weight, then compares against the production ensemble (50/30/20). It also breaks down enrichment contributions (events, seasonality, demand, weather, competitors, momentum, cancellations, provider).

**This is a READ-ONLY analytical module.** It never modifies predictions or signals — only scores and compares.

### New Files

1. **`src/analytics/source_attribution.py`** (NEW — ~430 lines)
   - `SourceTrack` dataclass: per-source isolated metrics (coverage, hit rate, MAPE, IC, hotel breakdown)
   - `EnrichmentAttribution` dataclass: per-enrichment contribution (daily impact %, USD impact, direction)
   - `AttributionReport` dataclass: full report with 4 tracks + enrichments + agreement
   - `extract_source_predictions(analysis)` → pulls fc_price, hist_price, ml_price from each prediction
   - `build_source_track(source, label, weight, predictions, total, actuals)` → builds isolated track
   - `compute_enrichment_attribution(analysis)` → extracts event/season/demand/weather/competitor/momentum from forward curve points
   - `compute_agreement(tracks)` → cross-source agreement rate + divergence rooms
   - `build_attribution_report(analysis, actuals)` → orchestrates full report
   - `_derive_signal(p_up, p_down, acceleration)` → same CALL/PUT logic as options_engine.py
   - `_pearson_correlation(x, y)` → IC calculation

2. **`src/api/routers/analytics_router.py`** (MODIFIED — 5 new endpoints)
   - `GET /attribution` — Full report: 4 tracks + enrichments + agreement
   - `GET /attribution/sources` — Sources only: FC vs Historical vs ML vs Ensemble
   - `GET /attribution/enrichments` — Per-enrichment breakdown
   - `GET /attribution/agreement` — Cross-source agreement + divergence rooms
   - `GET /attribution/hotel/{hotel_id}` — Per-hotel source comparison

3. **`tests/unit/test_source_attribution.py`** (NEW — 53 tests)
   - TestDeriveSignal (7): CALL/PUT/NONE logic, acceleration blocking
   - TestSafePct (4): percentage calculation edge cases
   - TestSignalDirection (5): normalization
   - TestPearsonCorrelation (5): IC calculation, edge cases
   - TestExtractSourcePredictions (7): 4-track extraction, missing sources, field validation
   - TestBuildSourceTrack (6): metrics, hotel breakdown, accuracy scoring, sample cap
   - TestEnrichmentAttribution (6): forward curve points, direction, sorting
   - TestComputeAgreement (6): full agreement, divergence, partial coverage
   - TestBuildAttributionReport (5): full report, serialization, actuals
   - TestSerialization (2): to_dict roundtrip

## Tasks

### 1. Verify Tests Pass
```bash
python3 -m pytest tests/unit/test_source_attribution.py -v -o "addopts="
```
Expected: 53 passed.

### 2. Verify Compilation
```bash
python3 -m py_compile src/analytics/source_attribution.py
python3 -m py_compile src/api/routers/analytics_router.py
```

### 3. Full Test Suite
```bash
python3 -m pytest tests/unit/ -v -o "addopts=" --ignore=tests/unit/test_rate_limiting.py --ignore=tests/unit/test_analytics_router_source_modes.py -q
```
Expected: 673+ passed. 20 pre-existing failures.

### 4. Commit
```bash
git add src/analytics/source_attribution.py src/api/routers/analytics_router.py tests/unit/test_source_attribution.py
git commit -m "feat: Source Attribution Engine — isolate FC/Historical/ML at 100% + enrichment breakdown

- 4 parallel analysis tracks: FC alone, Historical alone, ML alone, Ensemble (50/30/20)
- Per-source: coverage, hit rate, MAPE, IC (Information Coefficient), hotel breakdown
- Per-enrichment: events, seasonality, demand, weather, competitor, momentum contribution
- Cross-source agreement rate + divergence room detection
- 5 API endpoints: /attribution, /attribution/sources, /attribution/enrichments, /attribution/agreement, /attribution/hotel/{id}
- 53 unit tests all passing, zero regressions"
```

### 5. Deploy
```bash
python3 scripts/build_deploy.py
```

### 6. Validate on Production
```bash
# Full attribution report
curl -s "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/attribution" | python3 -m json.tool | head -50

# Sources comparison — THIS IS THE KEY VIEW
curl -s "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/attribution/sources" | python3 -m json.tool

# Enrichment breakdown
curl -s "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/attribution/enrichments" | python3 -m json.tool

# Agreement
curl -s "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/attribution/agreement" | python3 -m json.tool

# Per-hotel (Cadet = 173508)
curl -s "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/attribution/hotel/173508" | python3 -m json.tool
```

### 7. What to Look For in the Data

**Sources endpoint (`/attribution/sources`):**
- `coverage_pct` — FC should be ~100%, Historical maybe 60-80%, ML maybe 30-50%
- `calls` vs `puts` — do sources agree on direction?
- `avg_predicted_price` — how different are the predictions?

**Enrichments endpoint (`/attribution/enrichments`):**
- `avg_daily_impact_pct` — seasonality should be the biggest contributor
- `rooms_affected` — demand (flights) might have low coverage
- `direction` — weather should typically be "mixed" or "negative"

**Agreement endpoint (`/attribution/agreement`):**
- `agreement_rate_pct` — above 70% = sources mostly agree = good
- `divergence_rooms` — sorted by price_spread, biggest disagreements first

### 8. Update primer.md
Add:
```
- **Source Attribution Engine**: 4 isolated tracks (FC/Historical/ML/Ensemble), enrichment decomposition, cross-source agreement.
  5 API endpoints: /attribution, /attribution/sources, /attribution/enrichments, /attribution/agreement, /attribution/hotel/{id}. 53 tests.
```

## Critical Rules — DO NOT BREAK
1. This module is READ-ONLY — it never modifies predictions, signals, or caches
2. CALL/PUT signal logic mirrors options_engine.py exactly (same thresholds)
3. Ensemble weights 50/30/20 are not changed — only read and compared against isolated 100% tracks
4. All existing endpoints and logic remain untouched
