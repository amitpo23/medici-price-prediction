# Cancellation → Room Release Specification

**Date:** 2026-04-17
**Priority:** CRITICAL — rooms stuck as `IsSold=1` after guest cancellation
**Owner:** medici-hotels (process_incoming.py)
**Requester:** medici-price-prediction (analytics detected the gap)

---

## Problem

When a guest cancels a booking via Noovy, the system correctly records:
- `MED_Reservation.IsCanceled = 1` ✅
- `SalesOffice.IncomingReservations.ResStatus = "Cancel"` ✅

But it does **NOT** release the room back to active inventory:
- `MED_Book.IsSold` stays `1` ❌
- `MED_Book.SoldId` still points to cancelled reservation ❌
- Room is **stuck** — cannot be resold, does not appear in scans, excluded from signals

## Impact

- Every cancelled booking = one room permanently lost from inventory
- Revenue loss: room cannot be resold to another guest
- Signal blindness: prediction engine skips sold rooms
- Accumulative: problem grows with every cancellation

---

## Current Flow (as-is)

```
Guest cancels on Noovy
    ↓
Zenith sends callback (ResStatus="Cancel")
    ↓
SalesOffice.IncomingReservations row created (IsProcessed=0)
    ↓
process_incoming.py picks it up
    ↓
Creates MED_Reservation with IsCanceled=1
    ↓
STOPS HERE — MED_Book not updated ← THE GAP
```

## Required Flow (to-be)

```
Guest cancels on Noovy
    ↓
Zenith sends callback (ResStatus="Cancel")
    ↓
SalesOffice.IncomingReservations row created (IsProcessed=0)
    ↓
process_incoming.py picks it up
    ↓
Creates MED_Reservation with IsCanceled=1
    ↓
NEW: Finds MED_Book row via SoldId
    ↓
NEW: UPDATE MED_Book SET IsSold=0, SoldId=NULL
    ↓
Room is back in active inventory (IsActive=1, IsSold=0)
    ↓
Room re-enters scan cycle, signals, and sale pipeline
```

---

## Implementation

### Where to add code

**File:** `skills/reservation-callback/process_incoming.py`
**Location:** Inside `process_one()` function, after the MED_Reservation INSERT, when `ResStatus = "Cancel"`

### New function to add

```python
def release_active_room_on_cancel(conn, reservation_id, booking_number):
    """Release room back to active inventory when guest cancels.
    
    When a guest cancels a booking, find the MED_Book row that was
    sold to this reservation (via SoldId) and reset it to unsold,
    so the room returns to the scan/signal/sale cycle.
    
    Args:
        conn: DB connection
        reservation_id: MED_Reservation.Id of the cancelled booking
        booking_number: for logging
    """
    cursor = conn.cursor()
    
    # Step 1: Find the sold room linked to this reservation
    cursor.execute("""
        SELECT id, SourceHotelId, startDate, endDate, BuyPrice
        FROM MED_Book
        WHERE SoldId = ? AND IsActive = 1 AND IsSold = 1
    """, reservation_id)
    row = cursor.fetchone()
    
    if not row:
        logger.info(f"[CANCEL] Booking #{booking_number}: no active sold room found for reservation {reservation_id}")
        return False
    
    book_id, hotel_id, start_date, end_date, buy_price = row
    
    # Step 2: Release the room
    cursor.execute("""
        UPDATE MED_Book
        SET IsSold = 0, SoldId = NULL
        WHERE id = ? AND IsActive = 1
    """, book_id)
    
    logger.info(
        f"[CANCEL] Booking #{booking_number}: RELEASED room MED_Book.id={book_id} "
        f"(hotel={hotel_id}, {start_date}-{end_date}, bought at ${buy_price}). "
        f"Room is back in active inventory."
    )
    
    conn.commit()
    return True
```

### Where to call it

Inside `process_one()`, after the MED_Reservation INSERT:

```python
# Existing code: Insert MED_Reservation
reservation_id = insert_med_reservation(conn, incoming, is_cancelled=is_cancelled)

# NEW: If cancellation, release the room
if is_cancelled and reservation_id:
    released = release_active_room_on_cancel(conn, reservation_id, booking_number)
    if released:
        logger.info(f"[CANCEL] Booking #{booking_number}: room released back to inventory")
    else:
        logger.warning(f"[CANCEL] Booking #{booking_number}: cancellation recorded but no room to release")
```

---

## DB Tables Reference

### MED_Book (Active Room Inventory)

| Column | Type | Relevant Values |
|--------|------|-----------------|
| `id` | int | PK |
| `IsSold` | bit | `0` = available, `1` = sold to guest |
| `SoldId` | int | FK → `MED_Reservation.Id` (NULL when unsold) |
| `IsActive` | bit | `1` = in inventory, `0` = cancelled/expired |
| `SourceHotelId` | int | Hotel reference |
| `startDate` | date | Check-in |
| `endDate` | date | Check-out |
| `BuyPrice` | decimal | What we paid for the room |
| `CancellationTo` | datetime | Deadline for free cancellation |

### MED_Reservation (Guest Bookings)

| Column | Type | Relevant Values |
|--------|------|-----------------|
| `Id` | int | PK |
| `BookingNumber` | nvarchar | Noovy booking reference |
| `IsCanceled` | bit | `0` = active, `1` = cancelled |
| `ResStatus` | nvarchar | `"Commit"` or `"Cancel"` |
| `HotelCode` | nvarchar | Hotel reference |
| `DateFrom` | date | Check-in |
| `DateTo` | date | Check-out |

### Relationship

```
MED_Book.SoldId  →  MED_Reservation.Id
```

When `MED_Reservation.IsCanceled = 1` AND `MED_Book.SoldId = MED_Reservation.Id`:
→ `MED_Book.IsSold` should be `0` (room released)

---

## Verification Query

After implementing, run this to find stuck rooms (should return 0 rows):

```sql
-- Rooms that are sold to cancelled reservations (stuck rooms)
SELECT 
    b.id AS book_id,
    b.SourceHotelId,
    b.startDate,
    b.endDate,
    b.BuyPrice,
    b.IsSold,
    r.BookingNumber,
    r.IsCanceled,
    r.ResStatus
FROM MED_Book b
JOIN MED_Reservation r ON b.SoldId = r.Id
WHERE b.IsActive = 1
  AND b.IsSold = 1
  AND r.IsCanceled = 1
```

If this returns rows → those rooms are currently stuck. Fix with:

```sql
-- One-time fix for existing stuck rooms
UPDATE b
SET b.IsSold = 0, b.SoldId = NULL
FROM MED_Book b
JOIN MED_Reservation r ON b.SoldId = r.Id
WHERE b.IsActive = 1
  AND b.IsSold = 1
  AND r.IsCanceled = 1
```

---

## Edge Cases

| Scenario | How to handle |
|----------|---------------|
| Cancellation arrives but room already auto-cancelled (IsActive=0) | Skip — room already out of inventory |
| Cancellation arrives but SoldId is NULL | Log warning — room was never linked |
| Cancellation arrives twice (duplicate callback) | Idempotent — IsSold already 0, no-op |
| Partial cancellation (1 of 2 nights) | Out of scope — treat as full cancel for now |
| No-show (guest didn't arrive) | Same as cancel — `ResStatus="Cancel"`, release room |

## Testing

1. Find an existing cancelled booking: `SELECT TOP 1 * FROM MED_Reservation WHERE IsCanceled=1`
2. Check if its room is stuck: `SELECT * FROM MED_Book WHERE SoldId = <reservation_id>`
3. If `IsSold=1` → confirm the bug exists
4. Apply the fix
5. Verify `IsSold=0` and room appears in next scan cycle

---

## Summary for medici-hotels agent

**Add one function** (`release_active_room_on_cancel`) to `process_incoming.py` and **call it when ResStatus="Cancel"**. This closes the loop: sell room → guest cancels → room released → back to sale.

**One-time SQL fix** needed for rooms already stuck as IsSold=1 with cancelled reservations.

**Verification query** provided to confirm fix works.
