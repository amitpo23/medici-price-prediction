# Signal Logic Change — 2026-03-24

## Summary

Rewrote how CALL/PUT/NEUTRAL signals are computed. Changed from probability-based (% of days with movement) to forward-curve-based (actual predicted price change over T period).

## Before (v2.3.1 and earlier)

```
Input: p_up, p_down (% of historical days price moved up/down by >0.1%)

CALL High: p_up >= 70% AND acceleration >= 0
CALL Med:  p_up >= 60% AND acceleration >= 0
PUT High:  p_down >= 70% AND acceleration <= 0
PUT Med:   p_down >= 60% AND acceleration <= 0
NONE:      everything else
```

**Problem:** "75% of days the price went up" doesn't mean it will go up 30%. The direction frequency says nothing about the magnitude of the move.

## After (v2.3.2)

```
Input: forward_curve predicted prices over entire T period

1. Scan FC for min and max predicted prices
2. max_drop_pct = (current - FC_min) / current * 100
3. max_rise_pct = (FC_max - current) / current * 100

PUT:     max_drop_pct >= 5%   (price expected to fall ≥5% at some point)
CALL:    max_rise_pct >= 30%  (price expected to rise ≥30% at some point)
NEUTRAL: neither threshold met, OR insufficient data (<3 FC points)

Confidence:
  High: drop ≥10% (PUT) or rise ≥45% (CALL)
  Med:  drop 5-10% (PUT) or rise 30-45% (CALL)
  Low:  NEUTRAL / suppressed

Both signals possible: if both thresholds met, strongest wins.
```

## Thresholds

| Signal | Threshold | High Confidence | Rationale |
|--------|-----------|----------------|-----------|
| PUT | ≥5% drop | ≥10% drop | 5% = meaningful decline worth overriding |
| CALL | ≥30% rise | ≥45% rise | 30% = minimum margin for profitable buy |
| NEUTRAL | <5% drop AND <30% rise | — | Not enough movement to act on |

## What Stays the Same

- Market context adjustment (MonitorBridge demand/supply signals)
- Regime suppression (STALE → always NEUTRAL)
- Low quality suppression → NEUTRAL
- Momentum/velocity/acceleration still captured in output (for analytics)
- Output format unchanged — same fields, same API

## New Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `fc_max_drop_pct` | float | Largest predicted drop % from current price |
| `fc_max_rise_pct` | float | Largest predicted rise % from current price |
| `fc_points` | int | Number of FC price points used |

## Revert Points

| Tag | Description |
|-----|-------------|
| `v2.3.2-signal-logic-fix` | New FC-based signal logic |
| `v2.3.1-pre-signal-fix` | Old probability-based logic (revert here to restore) |

## Impact

Expect significantly different signal distribution:
- **More NEUTRAL** — many options won't hit 5% drop or 30% rise thresholds
- **Fewer false CALLs** — "75% days up" with 0.2% daily moves won't trigger
- **Fewer false PUTs** — small declines won't trigger unless ≥5%
- **Higher quality signals** — when CALL/PUT fires, it means real money opportunity

## Tests Updated

4 tests rewritten to use FC prices instead of probabilities:
- `test_call_high_signal` — FC peaks at +50% → CALL High
- `test_call_med_signal` — FC peaks at +35% → CALL Med
- `test_put_high_signal` — FC dips to -12% → PUT High
- `test_put_med_signal` — FC dips to -7% → PUT Med/High
- `test_none_signal_neutral` — FC range ±2.5% → NONE
