# Session Context — 2026-04-02 to 2026-04-11

Comprehensive log of work done across multiple sessions on Medici Price Prediction.

---

## Table of Contents
1. [Initial Analysis — Hotel Onboarding Issues](#1-initial-analysis)
2. [Security Audit & Hardening](#2-security-audit--hardening)
3. [Hotel.Tools / Noovy Product Investigation](#3-hoteltools--noovy-product-investigation)
4. [Best Buy / Best Sell Features](#4-best-buy--best-sell-features)
5. [UI Integration in Command Center](#5-ui-integration-in-command-center)
6. [Execution Dashboard](#6-execution-dashboard)
7. [Agent Health Check (medici-hotels)](#7-agent-health-check-medici-hotels)
8. [CI/CD Fixes](#8-cicd-fixes)
9. [Knowaa Competitive Intelligence](#9-knowaa-competitive-intelligence)
10. [Open Items](#10-open-items)
11. [Current Session Snapshot](#11-current-session-snapshot)

---

## 1. Initial Analysis

### Starting state (2026-04-02 scan)
- 55 Miami hotels, 120 active Details, check-in 20/04/2026
- **43 working (78%)**, 8 Api=0, 3 Failed, 1 Stuck
- 120 active Details across the portfolio
- Rate limit options dashboard scan report

### Problems identified
| Category | Count | Hotels |
|----------|-------|--------|
| Working OK | 43 | Most |
| Api=0 (no results) | 8 | Chelsea, Villa Casa, Fairwind, Viajero, Croydon, Gates, Metropole, Miami Airport |
| Failed | 3 | Hampton Inn, Albion, Landon |
| Stuck | 1 | Notebook Miami Beach |

### Gap analysis findings
- **Hampton Inn 5106**: Duplicate in `Med_Hotels` — InnstantId 826299 (scans) vs 854875 (has ratebycat). Mapping broken.
- **Chelsea, Albion, Gates, Croydon, Metropole**: Missing ratebycat mappings — only have 1-2 rows vs Pullman's 17
- **Gaythering $5,000**: Placeholder price leaked from Noovy Bulk Update to scan output
- **Villa Casa, Fairwind**: Regression — had Api results recently, now Api=0
- **Chelsea + 4 others**: Api=0 every scan since 27/03 (Hotel.Tools side issue)

### Key finding: "Hotels stopped working" was a mislabel
**The hotels never fully worked.** Data from `SalesOffice.Log` since April 1:
- Price scan (ActionId=3): 7,264 OK / 0 fail
- Availability push open (ActionId=5): 799 OK / **3,661 fail**
- Availability push close (ActionId=4): 656 OK / 314 fail
- Rate push (ActionId=6): 671 OK / 106 fail

**Root cause**: Only some InvTypeCodes have Products in Noovy. Push attempts for unconfigured room types fail silently. Appears as "hotel stopped working" when really it's a partial configuration issue.

---

## 2. Security Audit & Hardening

### Tags
- `v3.0.1-pre-security` — rollback point before fixes
- `v3.0.1-security` — after all hardening

### CRITICAL findings (all fixed in code)
| # | Issue | Files |
|---|-------|-------|
| 1 | Hardcoded Zenith SOAP password `12345` as default | `src/utils/zenith_push.py:18`, `skills/price-override/override_push.py:63` |
| 2 | Unauthenticated `/train`, `/predict`, `/diag/*` endpoints | `src/api/main.py` (17 endpoints) |
| 3 | Unauthenticated AI endpoints — free Claude API abuse | `src/api/routers/ai_router.py` (5 endpoints) |
| 4 | SOAP `soap_preview` leaks WSSE credentials in dry-run response | `analytics_router.py:2746` |
| 5 | Traceback leaked in API responses | `analytics_router.py:1099`, `monitor_router.py` (3x) |
| 6 | SQL injection via f-string | `src/data/db_loader.py:25` |
| 7 | Pickle RCE via unprotected `/train` endpoint | `deep_predictor.py:492`, `forecaster.py:400` |

### Fixes committed (7 commits)
1. `security: remove hardcoded Zenith SOAP credentials — require env vars`
2. `security: add API key auth to all unprotected endpoints in main.py`
3. `security: add API key auth to all 5 AI endpoints`
4. `security: remove SOAP credential leak + traceback from API responses`
5. `security: fix SQL injection in db_loader — add table/column allowlist`
6. `security: add security headers, API key warning, stop logging key prefix`
7. `security: update .gitignore — exclude credential-bearing temp files`

### Security headers added
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=31536000 (production only)
```

### Test result: 1397 passed, 0 failed

### Still outstanding (not code)
**9 passwords exposed in Git history** — require rotation on the servers:
- `Pr3d!rzn223y5KoNdQ^z8nG&YJ7N%rdRc` (prediction_reader)
- `@Amit2025` (medici_sql_admin)
- `Ag3ntSc@n2026Med1c1!` (agent_scanner)
- `karpad66` (Noovy zvi)
- `porat10` (Innstant Amit)
- `12345` (Zenith SOAP)
- `DgFX5ZmRyla...` ($medici-backend deploy)
- Innstant API tokens (Aether)
- `CyPb0755med444` (AutoCancellation)

---

## 3. Hotel.Tools / Noovy Product Investigation

### Audit result (2026-04-02)
- **55 venues scanned**
- **183 Products required**
- **101 existing**
- **82 missing** across 39 venues

### Investigation journey
1. **First attempt** — Python Playwright script via Hotel.Tools UI → all submits returned **500 "Something went wrong"**
2. **Root cause found**: Hotel.Tools select2 widgets incompatible with JS `val().trigger('change')`. Form submit works only via the UI's own jQuery flow.
3. **Dead ends**: Native submit, XHR with PJAX headers, form interceptors — all rejected by server
4. **Key insight** — `locations` require `states[location][ID]=added` field that only the UI wizard sets. `disabled` attribute on selects in view mode means they're not sent via FormData.
5. **Pivot to Noovy UI** (app.noovy.com) — completely different form with MUI components
6. **Noovy form works cleanly**:
   - Products page → `+ New Product` button
   - Product Type = Room (MUI Select)
   - Name, Short Name, BasePrice, Basic Occupancy
   - Currency = US Dollar (autocomplete with `Open` button)
   - Locations tab — auto-filled with current venue
   - Click Save

### Script created
**`scripts/noovy_create_products.py`** — automated via Playwright Python

### Result of full run
| Metric | Count |
|--------|-------|
| Venues processed | 38 |
| Products **created** | **5** |
| Products **already existed** | **75** |
| Errors | 0 |

**The 5 actually created:**
- SLS LUX Brickell (5077) — Superior
- InterContinental Miami (5276) — Deluxe, Suite
- Gale Miami Hotel (5278) — Suite, Apartment

### Meta-finding
**The audit overcounted by 75**. Most "missing" Products were already in Noovy — the Hotel.Tools audit saw a different view. **75 Products that appeared missing were actually already there.**

**Real conclusion**: The availability push failures are NOT due to missing Products. They're because the **SalesOffice WebJob** tries to push only a subset of ITC codes per hotel, ignoring others. This is a WebJob-side logic bug, not a Noovy config issue.

### Verification: All 55 hotels connected to Medici supplier ✅
Automated Playwright scan confirmed `Connected to Supplier = Medici` on all 55.

---

## 4. Best Buy / Best Sell Features

### Best Buy
**Purpose**: Identify rooms priced BELOW market — buy opportunities

**Composite score formula**:
```
composite = (ADR gap × 0.25)
          + (Zone avg gap × 0.25)
          + (CALL signal strength × 0.20)
          + (Velocity positive × 0.15)
          + (Consensus probability × 0.15)
```

**Labels**:
- `STRONG BUY` ≥ 0.45
- `BUY` ≥ 0.30
- `WATCH` ≥ 0.20
- `AVOID` < 0.20

**Files**:
- `src/analytics/best_buy.py` — calculation logic
- `GET /api/v1/salesoffice/best-buy?top=N` — JSON API
- `GET /dashboard/best-buy` — standalone dark-theme dashboard
- `.claude/agents/best-buy-price-analyzer.md` — Claude agent

### Best Sell
**Purpose**: Identify overpriced rooms that should be repriced down — PUT opportunities

**Formula** (inverted):
```
composite = (ADR overpricing × 0.25)
          + (Zone avg overpricing × 0.25)
          + (PUT signal strength × 0.20)
          + (Velocity negative × 0.15)
          + (Consensus probability × 0.15)
```

**Labels**:
- `STRONG SELL` ≥ 0.45
- `SELL` ≥ 0.30
- `OVERPRICED` ≥ 0.20
- `FAIR PRICE` < 0.20

**Files**:
- `src/analytics/best_sell.py`
- `GET /api/v1/salesoffice/best-sell?top=N`
- `GET /dashboard/best-sell`
- `.claude/agents/best-sell-price-analyzer.md`

### Zone ADR benchmarks (GMCVB official)
```
South Beach:  $380
Mid-Beach:    $420
Downtown:     $280
Brickell:     $280
Airport:      $150
Sunny Isles:  $300
```

### Scheduled scan
**`scripts/run_best_buy.sh`** — cron every 2 hours, saves JSON to `scan-reports/best-buy-*.json`, logs STRONG BUY alerts.

```
0 */2 * * * /Users/mymac/Desktop/coding/medici-price-prediction/scripts/run_best_buy.sh
```

---

## 5. UI Integration in Command Center

### Command Center layout (18+ panels, 3 columns)

**Left column:**
- Filters (hotel, signal, board, category, T, price)
- Mini Heatmap
- Options Table
- Bulk Actions (override/opportunity)

**Center column:**
- Price Chart (forward curve + actual scans)
- Secondary tabs: Enrichments / Historical T / Term Structure
- Option detail bar (selected option)
- **NEW:** Embedded tabs — Correlation / Alerts / Audit / Execution

**Right column:**
- Signal Summary
- **NEW:** Best Buy / Best Sell (toggle buttons)
- Source Consensus
- Accuracy & Context
- Arbitrage Opportunity
- Alerts & Risk
- Override History
- Override Rules
- Opportunity Rules
- Trading Intelligence
- Demand Zones
- Trade Setup
- Execution Queue

**Everything in ONE page** — no navigation needed.

### URL
```
https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/dashboard/command-center
```

---

## 11. Current Session Snapshot

### Environment
- Date: 2026-04-11
- OS: macOS
- Workspace root: `/Users/mymac/Desktop/coding/medici-price-prediction`
- Active shell observed: `zsh`
- Repeated activation command: `source /Users/mymac/Desktop/coding/medici-price-prediction/venv/bin/activate`

### Current repo context
- Repository: `medici-price-prediction`
- Role: Decision Brain for hotel room pricing
- Core behavior: produces CALL/PUT/NEUTRAL recommendations with confidence levels
- Safety boundary: does not execute trades or directly change prices

### Architecture reminder
1. Data collection from multiple sources
2. Prediction engine using weighted ensemble
3. AI intelligence for anomaly detection, risk assessment, and Q&A
4. API and dashboard delivery through FastAPI and HTML/JSON endpoints

### Critical constraints carried in context
- Database access must remain read-only
- AI features must preserve rule-based fallback behavior
- Existing ensemble weights and pricing logic conventions must be preserved unless intentionally changed

### Source tree summary
- `src/api/` for FastAPI app entrypoints, routers, models, and dashboard endpoints
- `src/analytics/` for prediction and analytics logic
- `src/collectors/` for source integrations
- `src/data/` for DB loaders and schemas
- `src/features/` for feature engineering
- `src/models/` for ML definitions
- `src/rules/` for rules engine logic
- `src/services/` for service-layer code
- `src/utils/` for shared helpers such as cache and config validation

### Workspace snapshot
Top-level areas visible in the current session:

- `build_deploy.py`
- `build_zip.py`
- `CHANGELOG.md`
- `CLAUDE.md`
- `README.md`
- `package.json`
- `pyproject.toml`
- `config/`
- `data/`
- `docs/`
- `mcp-servers/`
- `notebooks/`
- `scripts/`
- `src/`
- `tests/`
- `tasks/`
- `skills/`
- `prompts/`
- `scan-reports/`
- `shared-reports/`

### Memory state
- User memory: no saved user preferences yet
- Session memory: empty
- Repository memory files:
  - `/memories/repo/agent-guide-noovy-hoteltools.md`
  - `/memories/repo/noovy-help-knowledge-base.md`
  - `/memories/repo/noovy-zenith-session.md`
  - `/memories/repo/terminal-architecture.md`

### Terminal snapshot
- Most terminals are `zsh` sessions repeatedly activating the workspace virtualenv
- Observed working directories:
  - `/Users/mymac/Desktop/coding/medici-price-prediction`
  - `/Users/mymac/Desktop/coding/medici-price-prediction/mcp-servers/medici-db`
- An additional `node` terminal was used to run `claude` from the workspace root

### Related context sources
- `CLAUDE.md`
- `primer.md`
- `README.md`
- `docs/MEMORY_LOG.md`
- `.claude/rules/*.md`
- `.claude/skills/*/SKILL.md`

### Notes
- This section is a compact snapshot of the visible VS Code session state on 2026-04-11
- Repetitive terminal entries were summarized instead of copied line-by-line
- This file now serves as the combined historical context for 2026-04-02 through 2026-04-11

---

## 6. Execution Dashboard

**File**: `src/api/routers/dashboard_router.py::dashboard_execution()`
**URL**: `/api/v1/salesoffice/dashboard/execution`

### Displays
**KPI cards (4):**
- Total Overrides (30 days)
- Total Opportunities (30 days)
- Success Rate
- Budget Today ($2,000)

**Tables:**
- Recent Overrides (PUT actions) — date, hotel, room, original → override, discount
- Recent Opportunities (CALL actions) — date, hotel, room, buy → sell target, margin
- Top 5 Best Buy
- Top 5 Best Sell

### Real state of execution (2026-04-03 check)
| Metric | Value |
|--------|-------|
| Total Overrides | 1,203 |
| **Pushed to Zenith** | **0** |
| Rolled back | 1 |
| Not pushed | 1,202 |
| Active | 275 |

**`OVERRIDE_PUSH_ENABLED=false`** — kill switch keeps everything in dry-run. 1,203 overrides written to DB but **none pushed**. All overrides use default $1.00 discount.

---

## 7. Agent Health Check (medici-hotels)

### Full check (2026-04-10 12:55)
25 agents total. Status:

**✅ 19 working:**
| Agent | Last run | Status |
|-------|----------|--------|
| שמעון (Safety Officer) | 12:50 | 87/87 rooms safe, WebJob 3min ago |
| אמיר (SOM Critical) | 12:55 | OK |
| אמיר (SOM Full) | 12:00 | OK |
| אריה (Control Room) | 12:00 | 23/25 agents OK |
| דני (Coordinator) | 12:30 | ⚠️ DNS error (medici-monitor-) |
| יוסי (Room Seller) | 12:27 | 8 updated, 77 skipped |
| גבי (Autofix) | 12:50 | Alert: Viajero Miami BB |
| מיכאל (Mapping Fixer) | 10:00 | OK |
| יעל (Monitor) | 12:30 | WebJob OK, 1849 overrides / 0 pushed |
| שרה (Reservation Scraper) | 12:30 | OK |
| נתן (Rebuy) | 12:20 | Found 4, Fixed 4 |
| Smart Runner, Advisor, Validator, Learning Coord, Market Position | 12:25-12:50 | OK |
| Safety Wall | 07:05 | 78 fail / 900 ok (8.7% fail) |

**❌ 2 broken** (fixed during session):
1. **רוני (Mission)** — missing `--connection-string` argument
2. **שרה (process_incoming)** — same issue

### Fix applied
```bash
# Updated cron entries with --connection-string
# Both agents verified working manually on 2026-04-10 18:44
```

---

## 8. CI/CD Fixes

### Failing workflows
1. **Deploy to Azure App Service** — failed every push with `No credentials found`
2. **Browser Price Check Scan** — failed on `git push` due to race condition

### Fix 1: Disabled auto-deploy
**`.github/workflows/deploy-azure.yml`** — removed `push` trigger. Only `workflow_dispatch` remains.

Manual deploy still works: `python3 build_deploy.py --deploy`

### Fix 2: Retry with rebase
**`.github/workflows/browser-scan.yml`** — added 3 retry attempts with `git pull --rebase` between each:

```yaml
for i in 1 2 3; do
  git pull --rebase origin main || true
  if git push; then
    echo "Push succeeded on attempt $i"
    exit 0
  fi
  sleep 5
done
```

### Commit
`fix(ci): disable auto-deploy + add retry/rebase to browser-scan push`

---

## 9. Knowaa Competitive Intelligence

### How it works
**Tool**: `browser-price-check` (GitHub Actions workflow)
**Schedule**: Every 8 hours (00:00, 08:00, 16:00 UTC)
**Reports location**: `/Users/mymac/Desktop/coding/medici-price-prediction/scan-reports/`

### Report types
| File pattern | Purpose |
|--------------|---------|
| `*_knowaa_competitive_report.md` | Concise competitive analysis |
| `*_full_165_hotels_report.md` | Full 165-hotel report |
| `*_full_scan.json` | Raw scan data |
| `shared-reports/` | Shared copies |

### Latest report (2026-04-10 16:00 UTC)
| Metric | Current | Previous | Δ |
|--------|---------|----------|---|
| Total Hotels | 55 | 55 | 0 |
| Knowaa present | 27 (49%) | 29 (52%) | -2 |
| **Knowaa #1** | **13 (24%)** | **18 (32%)** | **-5 ▼** |
| Knowaa #2 | 5 | 2 | +3 |
| Knowaa #3+ | 9 | 9 | 0 |
| No Knowaa | 24 | 22 | -2 |

**Trend: Knowaa visibility dropping.** Down from 18 to 13 hotels where we're #1.

### Anomaly detected
**SLS LUX Brickell** listed at **$13,016** — runaway override. Currently ranked #6 with a +1594% markup vs cheapest (InnstantTravel at $768). Needs immediate fix.

---

## 10. Open Items

### High priority
1. **SLS LUX Brickell $13,016 runaway** — override escaped the $10K safeguard somehow. Check `PriceOverride` table for detail_id and rollback.
2. **Knowaa visibility trend declining** — 18 → 13 #1 positions in recent scans. Investigate if push failures correlate with drop.
3. **9 passwords in Git history** — rotate on servers:
   - Azure SQL (prediction_reader, agent_scanner, admin)
   - Noovy (zvi / karpad66)
   - Innstant (Amit / porat10)
   - Zenith SOAP (12345)
   - Azure WebJob deploy credential
   - Aether API tokens
4. **Gaythering $5,000** placeholder — fix RO/Standard price in Noovy bulk update

### Medium priority
5. **`OVERRIDE_PUSH_ENABLED=false`** — 1,203 overrides queued but zero pushed. Decision needed: enable push with real discounts (not $1), or continue dry-run only.
6. **Hampton Inn 5106 duplicate** in Med_Hotels — requires DB write (we have read-only)
7. **Safety Wall 8.7% failure rate** — 78 failed pushes out of 978 attempts per run. Root cause?
8. **דני Coordinator DNS error** — `medici-monitor-.azurewebsites.net` URL seems wrong

### Lower priority
9. **2 workflows still pending first clean run** — verify browser-scan retry fix works on next 16:00 UTC run
10. **Runaway override safeguard** — currently filters >$10K in `collector.py:146`. SLS at $13,016 suggests the safeguard has a bypass somewhere

---

## Key URLs

### Dashboards (production)
Base: `https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice`

| Dashboard | Path |
|-----------|------|
| **Command Center (primary)** | `/dashboard/command-center` |
| Best Buy | `/dashboard/best-buy` |
| Best Sell | `/dashboard/best-sell` |
| Execution | `/dashboard/execution` |
| Unified Terminal | `/dashboard/unified-terminal` |
| Terminal V2 | `/dashboard/terminal-v2` |
| Macro Terminal | `/dashboard/macro` |
| Trading Analysis | `/dashboard/trading-analysis` |
| Override Queue | `/dashboard/override-queue` |
| Opportunity Queue | `/dashboard/opportunity-queue` |
| Correlation | `/dashboard/correlation` |
| Streaming Alerts | `/dashboard/streaming-alerts` |
| Audit Trail | `/dashboard/audit-trail` |
| Options Board | `/options/view` |
| Health | `/health/view` |

### JSON APIs
| Endpoint | Purpose |
|----------|---------|
| `/best-buy?top=N` | Best Buy opportunities |
| `/best-sell?top=N` | Overpriced rooms |
| `/override/history?days=30` | Override execution history |
| `/opportunity/history?days=30` | Opportunity execution history |
| `/execution/health` | Full execution health check |
| `/options?all=true` | All current room options |
| `/data?all=true` | Raw pricing data |
| `/forward-curve` | Forward curve predictions |
| `/market/official-benchmarks` | GMCVB ADR benchmarks |
| `/signal/consensus/{id}` | Consensus signal per option |
| `/signal/arbitrage/{id}` | Arbitrage analysis |

---

## Commits during session (newest first)

```
fix(ci): disable auto-deploy + add retry/rebase to browser-scan push
feat: Execution Dashboard — overrides, opportunities, PnL, budget
feat: integrate Correlation, Alerts, Audit, Execution into Command Center
feat: integrate Best Buy/Sell panel into Command Center
feat: Best Sell dashboard + agent — overpriced room detection
chore: add best-buy cron scan every 2 hours
feat: Best Buy dashboard + Noovy product automation
docs: complete Hotel.Tools product gap analysis + fix guide
security: update .gitignore — exclude credential-bearing temp files
security: add security headers, API key warning, stop logging key prefix
security: fix SQL injection in db_loader — add table/column allowlist
security: remove SOAP credential leak + traceback from API responses
security: add API key auth to all 5 AI endpoints
security: add API key auth to all unprotected endpoints in main.py
security: remove hardcoded Zenith SOAP credentials — require env vars
```

---

## Agents (Claude Code)

### Created during session
1. **`best-buy-price-analyzer`** — finds optimal buy opportunities
2. **`best-sell-price-analyzer`** — finds overpriced rooms (PUT signals)

### Locations
- `.claude/agents/best-buy-price-analyzer.md`
- `.claude/agents/best-sell-price-analyzer.md`
- Agent memory: `.claude/agent-memory/best-buy-price-analyzer/`

---

## File map — created/modified during session

### New files
- `src/analytics/best_buy.py`
- `src/analytics/best_sell.py`
- `scripts/noovy_create_products.py`
- `scripts/create_all_products.py`
- `scripts/fix_missing_products.js`
- `scripts/run_best_buy.sh`
- `scripts/product_audit_report.json`
- `scripts/noovy_create_report.json`
- `docs/HOTEL_TOOLS_PRODUCT_FIX.md`
- `docs/superpowers/plans/2026-04-02-security-hardening.md`
- `.claude/agents/best-buy-price-analyzer.md`
- `.claude/agents/best-sell-price-analyzer.md`

### Modified files
- `src/api/main.py` (added auth to 17 endpoints)
- `src/api/middleware.py` (security headers, CSRF warning)
- `src/api/routers/analytics_router.py` (best-buy, best-sell endpoints + auth fixes)
- `src/api/routers/ai_router.py` (auth on 5 endpoints)
- `src/api/routers/dashboard_router.py` (best-buy, best-sell, execution pages)
- `src/api/routers/monitor_router.py` (sanitized error messages)
- `src/api/routers/_shared_state.py` (API key log fix)
- `src/data/db_loader.py` (SQL injection fix)
- `src/utils/zenith_push.py` (removed hardcoded password)
- `skills/price-override/override_push.py` (env vars)
- `src/templates/command_center.html` (Best Buy/Sell panel + embedded tabs)
- `.github/workflows/deploy-azure.yml` (disabled auto)
- `.github/workflows/browser-scan.yml` (retry with rebase)
- `.gitignore` (exclude credentials)

---

*Generated: 2026-04-11*
*Session count: Multiple (2026-04-02 to 2026-04-11)*
