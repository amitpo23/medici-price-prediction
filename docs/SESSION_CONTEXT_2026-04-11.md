# Session Context — Browser Price Check & Reservation Format
**Date:** 2026-04-11
**Project:** medici-price-prediction
**Focus:** Browser scanning automation, reservation format update, cross-project sharing

---

## 1. Primary Goals

### A. Browser Price Check Skill
Automated scanning of Innstant B2B (b2b.innstant.travel) to track **Knowaa_Global_zenith** competitive position:
- Does Knowaa appear for each hotel?
- Is Knowaa the cheapest offer?
- Per-category, per-board tracking (Refundable only)

### B. Reliable Scheduling
Run scans every 8 hours automatically, even when laptop is idle.

### C. Cross-Project Sharing
Share scan results with partner agent (medici-hotels) running on a different machine.

### D. Availability Cleanup
Close old availability for 55 hotels (15/04–30/10, except 20/04) in both Noovy and Hotel.Tools.

### E. Reservation Format Update
Extend reservation-callback skill with NightlyRates, CancellationPolicy, CancellationDeadline, HotelCode fields.

---

## 2. Key Accounts & URLs

| System | URL | Credentials |
|--------|-----|-------------|
| Innstant B2B | b2b.innstant.travel | amit (Knowaa) / Knowaa2024! |
| Noovy PMS | app.noovy.com | Medici LIVE / zvi / karpad66 |
| Hotel.Tools | hotel.tools | Medici Live / Zvi |
| Azure SQL | medici-sql-server.database.windows.net | prediction_reader (read-only) |
| GitHub reports | raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/ | public |

---

## 3. Source of Truth: SalesOffice.Orders

**CRITICAL:** Always use `SalesOffice.Orders` (configured scans), NOT `SalesOffice.Details` (partner's API results).

```sql
SELECT DISTINCT
  o.DestinationId AS InnstantId,
  h.name,
  h.Innstant_ZenithId AS VenueId,
  o.DateFrom,
  o.DateTo
FROM [SalesOffice.Orders] o
JOIN Med_Hotels h ON h.InnstantId = o.DestinationId
WHERE h.isActive = 1
  AND h.Innstant_ZenithId >= 5000
  AND o.IsActive = 1
```

**Growth over session:**
- 2026-03-31: 55 hotels
- 2026-04-09: 110 hotels
- 2026-04-10: 165 hotels (55 new, mostly outside Miami, mostly without Knowaa)

---

## 4. Skill: browser-price-check

### Files
- [skills/browser-price-check/SKILL.md](skills/browser-price-check/SKILL.md)
- [scripts/browser_scan.js](scripts/browser_scan.js) — 24KB main scanner
- [scan-reports/](scan-reports/) — historical scans
- [shared-reports/](shared-reports/) — partner-accessible reports

### Flow
1. Query SalesOffice.Orders for active hotel scans
2. Login to Innstant B2B once
3. For each hotel: search by InnstantId + dates
4. Extract offers: category, board (BB/RO), provider, price
5. Skip `non-refundable` items
6. Calculate Knowaa rank per category
7. Write markdown + JSON report
8. Commit + push to GitHub

### Key Extract Function
```javascript
const EXTRACT_FN = () => {
    const items = document.querySelectorAll('.search-result-item');
    const offers = [];
    items.forEach(item => {
        const catEl = item.querySelector('.small-4,.medium-3');
        const cat = catEl ? catEl.textContent.trim().split('\n')[0].trim() : '?';
        item.querySelectorAll('.search-result-item-sub-section').forEach(section => {
            const text = section.textContent || '';
            if (/non-refundable/i.test(text)) return;
            const provLabel = section.querySelector('.provider-label');
            const provider = provLabel ? provLabel.textContent.trim() : '?';
            const priceEl = section.querySelector('h4');
            const price = priceEl ? parseFloat(priceEl.textContent.replace(/[$,\s]/g, '')) : null;
            const board = /BB|breakfast/i.test(text) ? 'BB' : 'RO';
            if (price) offers.push({ cat, board, price, provider });
        });
    });
    return offers;
};
```

### Git Push with Retry
```javascript
try {
    execSync('git pull --rebase origin main', { cwd });
    execSync(`git add shared-reports/ scan-reports/`, { cwd });
    execSync(`git commit -m "${msg}"`, { cwd });
    execSync('git push origin main', { cwd });
} catch (err) {
    try {
        execSync('git pull --rebase origin main', { cwd });
        execSync('git push origin main', { cwd });
    } catch (err2) {
        log(`WARNING: git push failed after retry: ${err2.message}`);
    }
}
```

---

## 5. Scheduling: launchd (not cron)

**Why not cron:** macOS cron requires Full Disk Access; fails silently otherwise.

### Agent File
`/Users/mymac/Library/LaunchAgents/com.medici.browser-scan.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.medici.browser-scan</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/mymac/.nvm/versions/node/v22.22.0/bin/node</string>
        <string>/Users/mymac/Desktop/coding/medici-price-prediction/scripts/browser_scan.js</string>
        <string>--no-db</string>
    </array>
    <key>StartInterval</key>
    <integer>28800</integer>
    <key>StandardOutPath</key>
    <string>/tmp/browser_scan.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/browser_scan_error.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

### Commands
```bash
launchctl load ~/Library/LaunchAgents/com.medici.browser-scan.plist
launchctl list | grep medici
tail -f /tmp/browser_scan.log
```

**Runs every 28,800 seconds (8h). RunAtLoad triggers immediate execution.**

---

## 6. Cross-Project Sharing

### Problem
Partner agent (medici-hotels) runs on a different machine — cannot read local files.

### Solution
Commit reports to GitHub; partner reads via raw URL:
```
https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/
```

### Partner Skill
[skills/scan-reports-reader/SKILL.md](skills/scan-reports-reader/SKILL.md) — reads from GitHub raw URL.

---

## 7. Reservation Format Update

### Source
Real booking #1304985 — Riu Plaza Miami Beach, Francisco E Romero, $1000.07 × 3 nights.

### New Required Fields (MUST be populated)
| Field | Example | Where in Noovy |
|-------|---------|----------------|
| HotelCode | "5109" | Header next to hotel name |
| NightlyRates | JSON array per-night | Booking detail → nightly price table |
| CancellationPolicy | "Free cancellation until 2026-05-18" | Cancellation Policy section |
| CancellationDeadline | "2026-05-18" | Parsed from CancellationPolicy text |

### Full JSON Example
```json
{
  "BookingNumber": "1304985",
  "Source": "scraper",
  "ResStatus": "Commit",
  "HotelName": "Riu Plaza Miami Beach",
  "HotelCode": "5109",
  "DateFrom": "2026-05-21",
  "DateTo": "2026-05-24",
  "AmountAfterTax": 1000.07,
  "CurrencyCode": "USD",
  "RoomTypeCode": "DLX",
  "MealPlan": "RO",
  "AdultCount": 2,
  "ChildrenCount": 0,
  "GuestFirstName": "Francisco E",
  "GuestLastName": "Romero",
  "NightlyRates": [
    {"date": "2026-05-21", "amount": 257.82},
    {"date": "2026-05-22", "amount": 375.75},
    {"date": "2026-05-23", "amount": 366.50}
  ],
  "CancellationPolicy": "From 21 May 2026 00:00:00 Reservation becomes Non Refundable",
  "CancellationDeadline": "2026-05-21"
}
```

### Files Updated
- `/Users/mymac/Desktop/coding/medici-hotels/skills/reservation-callback/SKILL.md`
- [shared-reports/RESERVATION_FORMAT_UPDATE.md](shared-reports/RESERVATION_FORMAT_UPDATE.md)

### DB Migration Needed
```sql
ALTER TABLE MED_Reservation ADD
    NightlyRates NVARCHAR(MAX) NULL,
    CancellationPolicy NVARCHAR(500) NULL,
    CancellationDeadline DATE NULL,
    BookerEmail NVARCHAR(200) NULL,
    BookerPhone NVARCHAR(50) NULL,
    BookerAddress NVARCHAR(500) NULL,
    PaymentStatus NVARCHAR(50) NULL,
    AmountPaid DECIMAL(10,2) NULL,
    AmountLeftToPay DECIMAL(10,2) NULL,
    MarketSegment NVARCHAR(100) NULL,
    RatePlanName NVARCHAR(100) NULL;
```

---

## 8. Availability Reset Task

### Goal
Close availability for 55 hotels:
- **Dates:** 15/04/2026 – 30/10/2026 (except 20/04)
- **Value:** Fixed availability = 0 (NOT "No availability")
- **Systems:** Noovy AND Hotel.Tools

### Why "Fixed = 0" not "No availability"
User explicit feedback: "למה אתה לא עושה רק fixed avalibily?"
- Fixed=0 preserves the configuration
- "No availability" deletes it

### Results
- **Noovy:** 37/55 completed (18 failed due to browser crash)
- **Hotel.Tools:** 49/55 completed (6 failed due to missing products)

### Browser Crash Recovery
```bash
pkill -9 chromium
rm -f ~/.cache/ms-playwright/chromium*/chrome-*/SingletonLock
```

---

## 9. Knowaa Tracking Timeline

| Date | Total Hotels | Knowaa Present | #1 Rank | Notes |
|------|-------------|----------------|---------|-------|
| 2026-03-31 | 55 | 16 (29%) | 7 | Baseline |
| 2026-04-05 | 55 | 1 (2%) | 0 | **Channel issue** |
| 2026-04-06 | 55 | 1 (2%) | 0 | Still broken |
| 2026-04-09 | 110 | 35 (32%) | ~15 | **Recovered** |
| 2026-04-10 22:13 | 165 | 11 (7%) | 2 (1%) | 55 new hotels, mostly without Knowaa |

**Interpretation:** The 55 new hotels added to SalesOffice.Orders on 10/04 are likely outside Miami and not yet pushed to Innstant via Zenith/Noovy → Knowaa coverage percentage dropped.

---

## 10. Errors & Fixes

| Problem | Fix |
|---------|-----|
| Browser crashes during scan | `pkill -9 chromium && rm SingletonLock` |
| Cron doesn't run on macOS | Replaced with launchd agent |
| Git push rejected | `git pull --rebase` before push + retry logic |
| Merge conflicts on scan reports | `git checkout --theirs` |
| Unstaged `.claude-memory.md` blocks rebase | `git checkout -- .claude-memory.md` |
| Daterangepicker `setValue` doesn't work | Click input first, then `picker.setStartDate()` |
| `moment` undefined in browser context | Use `picker.startDate.clone()` instead |
| Wrong availability type | Changed from "No availability" to "Fixed=0" |
| Partner can't read local files | Switched to GitHub raw URL |
| Remote trigger has no browser | Abandoned — use local launchd |
| Wrong data source | SalesOffice.Orders (NOT Details) |

---

## 11. Files Created/Modified

### Created
- `skills/browser-price-check/SKILL.md`
- `scripts/browser_scan.js`
- `/Users/mymac/Library/LaunchAgents/com.medici.browser-scan.plist`
- `shared-reports/RESERVATION_FORMAT_UPDATE.md`
- `scan-reports/YYYY-MM-DD/` (recurring)
- `skills/scan-reports-reader/SKILL.md` (partner project)
- `docs/SESSION_CONTEXT_2026-04-11.md` (this file)

### Modified
- `/Users/mymac/Desktop/coding/medici-hotels/skills/reservation-callback/SKILL.md` — added NightlyRates, CancellationPolicy, CancellationDeadline, HotelCode
- `src/api/main.py` — version 2.2.0 → 2.7.0
- `.claude/projects/.../memory/MEMORY.md` — added browser-price-check info, 55-hotel baseline

---

## 12. User Preferences (from this session)

- **Always use SalesOffice.Orders**, never SalesOffice.Details
- **Knowaa_Global_zenith** is our provider — track presence + ranking
- **Refundable only** — skip non-refundable
- **Fixed availability = 0**, not "No availability"
- **GitHub raw URL** for cross-project sharing
- **launchd** for macOS scheduling (cron unreliable)
- **Hebrew communication**, English code/docs
- **Full detailed reports** — both markdown + JSON
- **FULL AUTONOMY** — never ask for confirmation

---

## 13. Next Steps

### Immediate
- Next scheduled scan runs every 8h via launchd
- Investigate: why do the 55 new hotels lack Knowaa coverage?
  - Likely: outside Miami, not yet pushed via Zenith/Noovy
  - Check `Med_Hotels.InnstantId` vs `Innstant_ZenithId` mappings

### Pending
- Complete 18 Noovy hotels that failed (browser crash)
- Complete 6 Hotel.Tools hotels that failed (no products)
- Verify partner's reservation-callback skill picks up new JSON format from GitHub
- DB migration for new MED_Reservation fields (NightlyRates, CancellationPolicy, etc.)

---

## 14. Key Commands Reference

```bash
# Manual scan
node /Users/mymac/Desktop/coding/medici-price-prediction/scripts/browser_scan.js --no-db

# View scheduler
launchctl list | grep medici

# Reload scheduler
launchctl unload ~/Library/LaunchAgents/com.medici.browser-scan.plist
launchctl load ~/Library/LaunchAgents/com.medici.browser-scan.plist

# View logs
tail -f /tmp/browser_scan.log
tail -f /tmp/browser_scan_error.log

# Kill stuck browser
pkill -9 chromium
rm -f ~/.cache/ms-playwright/chromium*/chrome-*/SingletonLock
```

---

**End of session context.**
