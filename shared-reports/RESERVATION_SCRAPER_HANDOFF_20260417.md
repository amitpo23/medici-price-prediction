# Reservation Scraper Handoff — price-prediction → medici-hotels

**Date:** 2026-04-17
**From:** medici-hotels team (reservation-callback skill)
**To:** medici-price-prediction team (scraper agent)
**Purpose:** Restart the Noovy reservation data feed. Current file `/Users/mymac/coding/medici-hotels/data/pending_reservations.json` last updated 2026-04-06 — 11 days stale.

---

## Context

Two spec documents already exchanged between the teams establish the format and the consumer-side fix:

- `medici-price-prediction/shared-reports/RESERVATION_FORMAT_UPDATE.md` (2026-04-02) — defines the JSON payload format
- `medici-price-prediction/shared-reports/CANCELLATION_ROOM_RELEASE_SPEC.md` (2026-04-17) — defines the consumer-side flow for cancellations

This handoff covers the **producer-side** plumbing: where the scraper must drop its output and how to trigger consumption.

---

## Exact instructions for the scraper agent

### 1. Output file path

Write the scraped reservations to **this exact absolute path**:

```
/Users/mymac/coding/medici-hotels/data/pending_reservations.json
```

Notes:
- Path is on the medici-hotels `coding/` tree — the running prod tree.
- The `data/` directory already exists.
- Overwrite the file on each run (do not append). Consumer loads the entire file each time.
- Write atomically: write to `pending_reservations.json.tmp` then rename to final name. Prevents consumer reading a half-written file.

### 2. File format

JSON array of reservation objects. Each object follows `RESERVATION_FORMAT_UPDATE.md` exactly. Required minimum fields:

```json
{
  "BookingNumber": "string (e.g., '1304985')",
  "Source": "scraper",
  "ResStatus": "Commit" | "Cancel",
  "HotelName": "string",
  "HotelCode": "string or null",
  "DateFrom": "YYYY-MM-DD",
  "DateTo": "YYYY-MM-DD",
  "AmountAfterTax": number,
  "CurrencyCode": "USD",
  "RoomTypeCode": "string (DLX, Stnd, etc.)",
  "MealPlan": "RO" | "BB" | "HB" | "FB" | "AI",
  "AdultCount": number,
  "ChildrenCount": number,
  "GuestFirstName": "string",
  "GuestLastName": "string",
  "BookerName": "string",
  "GuestsJson": [{"first_name": "...", "last_name": "..."}]
}
```

**Critical fields for the cancellation flow:**
- `ResStatus: "Cancel"` — required for any booking whose Noovy status is "cancelled", "canceled", or "no show"
- `BookingNumber` — must be unchanged from the original booking (same value for the initial "Commit" and the subsequent "Cancel" — they describe the same reservation's two states)

**Complete example** — see booking 1291361 in existing `pending_reservations.json` which correctly shows `"ResStatus": "Cancel"`.

### 3. Scraping cadence

Run every **30 minutes**. Reasoning:
- Shorter than Noovy typical cancellation → invoice window (hours)
- Longer than process_incoming's 5-minute cycle (consumer picks up fresh data on next run)

### 4. What to scrape from Noovy

Log into `https://hotel.tools/reservations` and extract ALL reservations from both tabs:
- **Future** tab — bookings that have not yet checked in
- **Past** tab — bookings within the last 90 days (needed to detect late cancellations)

Include every status — do not filter. The consumer decides how to process based on `ResStatus`.

### 5. Consumer-side trigger (MUST also be automated)

Writing the file alone is not enough. The consumer must be triggered to load it. Two options:

**Option A (preferred — no coordination needed):**
After writing the JSON, the scraper itself invokes:
```bash
python3 /Users/mymac/coding/medici-hotels/skills/reservation-callback/process_incoming.py \
    --connection-string "$MEDICI_DB_CONNECTION" \
    --from-json /Users/mymac/coding/medici-hotels/data/pending_reservations.json \
    --live
```
This loads the JSON into `SalesOffice.IncomingReservations` and processes each row.

**Option B (decoupled — requires medici-hotels team action):**
medici-hotels team adds a launchd plist that runs the above command every 5 minutes regardless of scraper state. Scraper just writes the file and forgets. If medici-hotels goes this route, they will notify via `shared-reports/`.

**Default assumption: Option A.** Scraper is responsible for triggering consumption.

### 6. Health check and monitoring

After each successful run, write a heartbeat file to:

```
/Users/mymac/coding/medici-hotels/skills/_shared/heartbeats/reservation-scraper.json
```

Format:
```json
{
  "agent": "reservation-scraper",
  "last_run": "2026-04-17T12:34:56Z",
  "status": "OK",
  "scraped": 42,
  "cancel_rows": 3,
  "commit_rows": 39
}
```

This plugs into the existing heartbeat monitor (`skills/_shared/heartbeat_monitor.py`) and allows safety-officer to detect staleness.

### 7. Error handling

- **hotel.tools login fails:** write status=`LOGIN_FAILED` to heartbeat, exit non-zero. Do NOT overwrite `pending_reservations.json` with an empty array (would wipe the last good snapshot).
- **DOM selectors don't match (zero rows found):** write status=`ZERO_ROWS` to heartbeat, exit 1. Same rule — do NOT overwrite the existing file if the result looks empty.
- **DB connection in consumer trigger fails:** log the error but leave `pending_reservations.json` in place so a later invocation can pick it up.

---

## Consumer-side gaps that still need fixing on our end

The medici-hotels team has separately documented these bugs that affect the cancellation flow even after your scraper is online:

- **Duplicate bail-out in `process_one`** (process_incoming.py:643-650) — existing Cancel rows are skipped instead of updating `Med_Reservation.IsCanceled`. Documented as Finding #11, Task C in `docs/risks/code-review-findings-20260417.md`.
- **Duplicate bail-out in `insert_into_incoming_table`** (process_incoming.py:772-778) — a Cancel JSON row for a booking whose initial Commit row is still in `IncomingReservations` gets skipped at insert time.
- **MED_Book release on cancel** — the spec in your `CANCELLATION_ROOM_RELEASE_SPEC.md` is being tracked as the consumer-side fix for room inventory reactivation.

These are being addressed in a separate sprint on medici-hotels side. Your scraper coming online is a **prerequisite** for testing those fixes end-to-end, so the earlier the better.

---

## Verification protocol

Once the scraper is running, validate end-to-end with these steps (producer + consumer side combined):

1. **Producer side:**
   - Scraper run completes without error
   - Heartbeat file updated within the last hour
   - `pending_reservations.json` exists, is valid JSON, contains >0 reservations

2. **Consumer side:**
   - `SalesOffice.IncomingReservations` has fresh rows from `Source='scraper'` within the last hour (query: `SELECT TOP 10 * FROM [SalesOffice.IncomingReservations] WHERE Source='scraper' ORDER BY Id DESC`)
   - For any Cancel row in the JSON with a matching existing `Med_Reservation`, check that `IsCanceled` eventually flips to 1 (requires Task C fix on medici-hotels side — coordinate)

3. **Daily reconciliation** (run once a day, optional):
   ```sql
   -- Any 'future' or 'in house' reservations in Med_Reservation that are past their end date but still IsCanceled=0 and have no corresponding Cancel in IncomingReservations?
   SELECT r.Id, r.uniqueID, r.dateto
   FROM Med_Reservation r
   LEFT JOIN [SalesOffice.IncomingReservations] i
     ON i.BookingNumber = r.uniqueID AND i.ResStatus = 'Cancel'
   WHERE r.IsCanceled = 0 AND r.dateto < GETDATE() AND i.Id IS NULL
   ORDER BY r.dateto DESC;
   ```
   Zero rows = scraper is capturing cancellations correctly.

---

## Questions / handoff protocol

If any of the above is unclear or conflicts with existing price-prediction infrastructure:

- Drop a response at `medici-price-prediction/shared-reports/RESERVATION_SCRAPER_QUESTIONS_20260417.md` — medici-hotels team will read it within 24h.
- Do **not** reply via DB tables or Slack — keep the paper trail in `shared-reports/` so both teams can diff and audit later.

---

## One-line summary for the agent

> Write JSON to `/Users/mymac/coding/medici-hotels/data/pending_reservations.json` every 30 min, include `ResStatus: "Commit" | "Cancel"` per `RESERVATION_FORMAT_UPDATE.md`, then invoke `process_incoming.py --from-json <path> --live`. Update heartbeat at `skills/_shared/heartbeats/reservation-scraper.json`. Do not overwrite on empty/failed scrapes.
