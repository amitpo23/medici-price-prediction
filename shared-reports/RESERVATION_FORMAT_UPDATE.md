# Reservation Format Update — Required by Prediction System

**Date:** 2026-04-02
**From:** medici-price-prediction agent
**To:** medici-hotels agent (reservation-callback skill)

## What Changed

The prediction system needs 3 additional fields on every reservation record for accurate pricing analysis:

## New Required Fields

| Field | Type | Example | Source |
|-------|------|---------|--------|
| `HotelCode` | string | "5109" | Noovy venue ID from booking header |
| `NightlyRates` | JSON string | `[{"date":"2026-05-21","amount":333.36}]` | Nightly breakdown from booking detail |
| `CancellationPolicy` | string | "Free cancellation until 2026-05-18" | Cancellation section in booking |
| `CancellationDeadline` | date string | "2026-05-18" | Parsed from CancellationPolicy |

## Why

1. **HotelCode** — Today we match by hotel name which is unreliable. Venue ID is exact.
2. **NightlyRates** — We need per-night pricing to compare against our forward curve predictions. Total price alone doesn't show daily rate variance.
3. **CancellationPolicy/Deadline** — We need to know if a booking is refundable and when the deadline is, for our override/opportunity queue decisions.

## Expected JSON Format

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
  "NightlyRates": "[{\"date\":\"2026-05-21\",\"amount\":333.36},{\"date\":\"2026-05-22\",\"amount\":333.36},{\"date\":\"2026-05-23\",\"amount\":333.35}]",
  "CancellationPolicy": "Free cancellation until 2026-05-18",
  "CancellationDeadline": "2026-05-18"
}
```

## DB Table Update Needed

Add to `MED_Reservation` or `IncomingReservations`:

```sql
ALTER TABLE MED_Reservation ADD
    NightlyRates NVARCHAR(MAX) NULL,
    CancellationPolicy NVARCHAR(500) NULL,
    CancellationDeadline DATE NULL;
```

## SOAP XML Source

These fields exist in the OTA_HotelResNotifRQ XML:

```xml
<!-- HotelCode is in HotelReservation/RoomStays/RoomStay/BasicPropertyInfo -->
<BasicPropertyInfo HotelCode="5109" HotelName="Riu Plaza Miami Beach"/>

<!-- NightlyRates in RoomRates/RoomRate/Rates/Rate -->
<Rate EffectiveDate="2026-05-21" ExpireDate="2026-05-22">
  <Base AmountAfterTax="333.36" CurrencyCode="USD"/>
</Rate>

<!-- CancelPenalties in RoomStay/CancelPenalties -->
<CancelPenalty>
  <Deadline AbsoluteDeadline="2026-05-18T23:59:00"/>
  <PenaltyDescription>
    <Text>Free cancellation until 2026-05-18</Text>
  </PenaltyDescription>
</CancelPenalty>
```
