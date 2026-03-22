# Release 2.0.2 — 2026-03-22

## Summary

This release consolidates two implementation tracks completed in the current session:

1. Queue/API hardening for SalesOffice override and opportunity workflows.
2. Initial mobile usability rollout for shared UI shell and key operator views.

The release remains within the existing system boundary:

- No trading execution was added.
- No read-only database protections were changed.
- No ensemble weights or prediction logic were changed.

## Version Context

- Previous application version: `2.0.1`
- New application version: `2.0.2`
- Release date: `2026-03-22`

## Included Work

### 1. Queue/API Hardening

Files:

- `src/api/routers/analytics_router.py`
- `src/analytics/override_queue.py`
- `tests/unit/test_override_queue.py`
- `tests/integration/test_api_endpoints.py`

What changed:

- Added typed request models for override queue endpoints.
- Added typed request models for opportunity queue endpoints.
- Removed manual payload coercion from queue API entrypoints.
- Fixed override history filtering so `days=N` behaves as a true rolling window.
- Added regression test coverage for the month-boundary bug.
- Added integration coverage for invalid queue request payloads.

Why it matters:

- Invalid request data is now rejected at the API boundary instead of failing later in business logic.
- Override history analytics now produce correct results across month changes.
- Queue-facing API behavior is more predictable and easier to maintain.

Validation:

- `pytest tests/unit/test_override_queue.py tests/integration/test_api_endpoints.py -q`
- Result: `69 passed`

### 2. Mobile UI Initial Rollout

Files:

- `src/templates/static/base.css`
- `src/templates/landing.html`
- `src/templates/alerts.html`
- `src/templates/health.html`
- `src/templates/options_board.html`

What changed:

- Improved shared mobile shell behavior in the base stylesheet.
- Increased touch-target usability in navigation.
- Added consistent horizontal overflow handling for wide tables.
- Tightened spacing and stacking behavior on summary pages.
- Preserved desktop landing-page structure while improving phone behavior.
- Added mobile card rendering to the options board.
- Kept desktop table rendering, pagination, and detail modal behavior intact.

Why it matters:

- Key operator pages are now usable on narrow screens without forcing a desktop redesign.
- Desktop workflows remain visually stable.
- The options board now supports a phone-friendly reading mode without replacing the existing table workflow.

Validation:

- Static template/CSS validation via editor diagnostics
- Result: `no errors found`

## Documentation Added In This Release

- `docs/REMEDIATION_BASELINE_2026-03-22.md`
- `docs/MOBILE_UI_BASELINE_2026-03-22.md`
- `docs/RELEASE_2.0.2_2026-03-22.md`

## Explicit Non-Changes

- No change to read-only enforcement in `src/data/trading_db.py`
- No queue storage migration
- No scheduler/framework rewrite
- No prediction-weight changes
- No desktop main-screen redesign

## Release Outcome

Release `2.0.2` formalizes the backend queue validation improvements and the first mobile UI rollout as a single patch release with preserved desktop behavior.