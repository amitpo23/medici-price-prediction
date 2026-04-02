# Reservation Format Update — Required by Prediction System

**Date:** 2026-04-02
**From:** medici-price-prediction agent
**To:** medici-hotels agent (reservation-callback skill)

## What Changed

Every reservation shared between systems MUST include the full booking detail — not just summary fields.

## Complete Required Format

Based on real booking #1304985:

```json
{
  "BookingNumber": "1304985",
  "Source": "scraper",
  "ResStatus": "Commit",
  "BookingDate": "2026-04-02T01:42:27",
  "BookedBy": "Medici Live / API",
  "State": "FUTURE",
  "Status": "CONFIRMED",
  "MarketSegment": "Internet",
  "Manual": false,

  "HotelName": "Riu Plaza Miami Beach",
  "HotelCode": "5109",
  "DateFrom": "2026-05-21",
  "DateTo": "2026-05-24",
  "Nights": 3,
  "CheckIn": "15:00",
  "CheckOut": "11:00",

  "RoomTypeCode": "DLX",
  "RoomTypeName": "Deluxe (Unallocated)",
  "MealPlan": "RO",
  "RatePlanCode": "13150",
  "RatePlanName": "bed and brekfast",

  "AmountAfterTax": 1000.07,
  "CurrencyCode": "USD",
  "PaymentStatus": "Post Paid",
  "AmountPaid": 0.00,
  "AmountLeftToPay": 1000.07,

  "NightlyRates": [
    {"date": "2026-05-21", "amount": 257.82},
    {"date": "2026-05-22", "amount": 375.75},
    {"date": "2026-05-23", "amount": 366.50}
  ],

  "CancellationPolicy": "From 21 May 2026 00:00:00 Reservation becomes Non Refundable",
  "CancellationDeadline": "2026-05-21",
  "IsRefundable": false,

  "AdultCount": 2,
  "ChildrenCount": 0,
  "GuestFirstName": "Francisco E",
  "GuestLastName": "Romero",
  "GuestPrefix": "Mr",
  "GuestNationality": "United States",
  "GuestAge": 33,

  "BookerName": "Romero Francisco E",
  "BookerEmail": "support@splittytravel.com",
  "BookerPhone": "13478399680",
  "BookerAddress": "Israel, Tel Aviv, 8 Pinhas Sapir, Ness-Ziyonna - 7414001 Science Park",

  "Documents": [
    {
      "CreationDate": "2026-04-02T01:42:29",
      "Type": "Sales Order",
      "From": "Riu Plaza Miami Beach",
      "To": "mr Francisco E Romero [Customer]",
      "Reference": "4244333",
      "DueDate": "2026-05-21",
      "Amount": 1000.07,
      "LeftToPay": 1000.07,
      "Status": "Active",
      "PaymentMethod": "N/A"
    }
  ]
}
```

## Field Reference — Where to Find in Noovy

| Field | Location in Noovy Booking Page |
|-------|-------------------------------|
| BookingNumber | Header: "Booking Number: #1304985" |
| BookingDate | "Booking Date: 2 Apr 2026 01:42:27" |
| BookedBy | "Booked by: Medici Live / API" |
| State/Status | "State: FUTURE", "Status: CONFIRMED" |
| MarketSegment | "Market Segment: Internet" |
| HotelCode | From venue dropdown or URL (#5109) |
| HotelName | "Hotel: Riu Plaza Miami Beach" |
| DateFrom/DateTo | "Arrival Date / Departure Date" |
| Nights | "Nights: 3" |
| RoomTypeName | "Deluxe (Unallocated)" — room section header |
| MealPlan | "Meal Plan: Room Only (RO)" |
| RatePlanCode | "Rate Plan: 13150(bed and brekfast)" |
| AmountAfterTax | "Total Price: 1 000,07$" |
| PaymentStatus | "Post Paid" next to total price |
| AmountPaid/LeftToPay | From Totals section |
| NightlyRates | Per-night table at bottom: "21-May: 257.82, 22-May: 375.75, 23-May: 366.50" |
| CancellationPolicy | "Cancellation Terms:" section |
| CancellationDeadline | Parse date from cancellation text |
| Guest info | "Mr. Francisco E Romero", nationality, age |
| Booker info | "Booker" section: name, email, phone, address |
| Documents | "Documents" table: Sales Order with reference, amount |

## Why Each Field Matters

| Field | Used For |
|-------|----------|
| HotelCode | Exact venue matching (name matching is unreliable) |
| NightlyRates | Compare per-night vs forward curve predictions |
| CancellationPolicy | Determine if we can cancel and rebook cheaper |
| CancellationDeadline | Auto-cancel queue deadline monitoring |
| RatePlanCode | Match against Med_Hotels_ratebycat mapping |
| PaymentStatus | Know if committed or just reserved |
| BookerEmail | Identify OTA source (splittytravel = Splitty) |
| Documents | Track financial obligations |

## DB Changes Needed

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

## SOAP XML Source Mapping

```xml
<!-- HotelCode -->
<BasicPropertyInfo HotelCode="5109" HotelName="Riu Plaza Miami Beach"/>

<!-- NightlyRates from Rate elements -->
<Rate EffectiveDate="2026-05-21" ExpireDate="2026-05-22">
  <Base AmountAfterTax="257.82" CurrencyCode="USD"/>
</Rate>
<Rate EffectiveDate="2026-05-22" ExpireDate="2026-05-23">
  <Base AmountAfterTax="375.75" CurrencyCode="USD"/>
</Rate>
<Rate EffectiveDate="2026-05-23" ExpireDate="2026-05-24">
  <Base AmountAfterTax="366.50" CurrencyCode="USD"/>
</Rate>

<!-- CancelPenalties -->
<CancelPenalty>
  <Deadline AbsoluteDeadline="2026-05-21T00:00:00"/>
  <PenaltyDescription>
    <Text>From 21 May 2026 00:00:00 Reservation becomes Non Refundable</Text>
  </PenaltyDescription>
</CancelPenalty>

<!-- Guest -->
<Customer>
  <PersonName>
    <NamePrefix>Mr</NamePrefix>
    <GivenName>Francisco E</GivenName>
    <Surname>Romero</Surname>
  </PersonName>
  <Email>support@splittytravel.com</Email>
  <Telephone PhoneNumber="13478399680"/>
  <Address>
    <CityName>Tel Aviv</CityName>
    <CountryName>Israel</CountryName>
    <AddressLine>8 Pinhas Sapir, Ness-Ziyonna</AddressLine>
  </Address>
</Customer>
```
