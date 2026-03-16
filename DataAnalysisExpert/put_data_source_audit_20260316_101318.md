# PUT Data Source Audit — Markdown Summary

- Generated at: 2026-03-16 08:08:30 UTC
- Analysis run_ts: 2026-03-16 08:05:43
- Source JSON: DataAnalysisExpert/put_data_source_audit_20260316_100830.json

## PUT Snapshot

- Total predictions: 4511
- PUT count: 544
- CALL count: 3967
- NEUTRAL count: 0
- PUT rate: 12.06%

## Freshness Overview

- Overall status: red
- Green: 5 | Yellow: 2 | Red: 2 | Unknown: 5
- Checked at: 2026-03-16 08:05 UTC

## Prediction Engine Inputs (Observed)

- prediction_method_counts: {'deep_ensemble': 4511}
- model_type_counts: {'deep_ensemble': 4511}
- signal_source_counts: {'forward_curve': 4511, 'historical_pattern': 4511}
- source_inputs_presence keys: ['demand_indicator', 'events_count', 'event_names', 'weather_days', 'competitor_pressure', 'price_velocity', 'cancellation_risk', 'provider_pressure']

## Source Status Table

| Source | Registry Status | Freshness | Last Updated | Priority | Action | ETA |
|---|---|---|---|---|---|---|
| SalesOffice DB | active | green, red | 2026-03-16 08:05 UTC; 2026-03-12 13:25 UTC | P1 | Investigate stale critical source and trigger refresh | Today |
| AI Search Hotel Data | active | red | 2026-03-15 00:02 UTC | P1 | Investigate stale critical source and trigger refresh | Today |
| Search Results Session Poll Log | active | green | 2026-03-16 06:49 UTC | P3 | No action required | Monitor |
| Room Price Update Log | active | green | 2026-03-16 06:50 UTC | P3 | No action required | Monitor |
| MED PreBook Data | active | yellow | 2026-03-12 10:39 UTC | P2 | Schedule refresh / verify ingestion lag | Today |
| SalesOffice Action Log | active | green | 2026-03-16 08:05 UTC | P3 | No action required | Monitor |
| Kiwi.com Flights | active | unknown | None | P2 | Wire freshness signal for this source | Today |
| Open-Meteo Weather | active | unknown | None | P2 | Wire freshness signal for this source | Today |
| SeatGeek Events | active | unknown | None | P2 | Wire freshness signal for this source | Today |
| TBO Hotels Dataset (Kaggle) | active | unknown | N/A | P2 | Wire freshness signal for this source | Today |
| Hotel Booking Demand (GitHub) | active | unknown | N/A | P2 | Wire freshness signal for this source | Today |
| Trivago ADR (via Statista) | active | unknown | N/A | P2 | Wire freshness signal for this source | Today |

## Today Priority Plan

1. P1: Resolve all red freshness sources before business-critical PUT monitoring.
2. P2: Eliminate unknown freshness for Flights/Weather/Events caches.
3. P2: Re-run audit after refresh and compare PUT rate delta.
4. P3: Keep daily scheduled audit artifact for trend tracking.