"""Write browser scan results from JSON to SalesOffice.BrowserScanResults table.

Usage:
    python3 scripts/browser_to_db.py scan-reports/2026-03-30_14-30.json
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pyodbc

logger = logging.getLogger(__name__)

# DB connection — same as prediction system
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=medici-sql-server.database.windows.net;"
    "DATABASE=medici-db;"
    "UID=prediction_reader;"
    "PWD=Pr3d!rzn223y5KoNdQ^z8nG&YJ7N%rdRc;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=15;"
)

CREATE_TABLE_SQL = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'BrowserScanResults' AND schema_id = SCHEMA_ID('SalesOffice'))
BEGIN
    CREATE TABLE SalesOffice.BrowserScanResults (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ScanDate DATETIME NOT NULL,
        CheckInDate DATE NOT NULL,
        CheckOutDate DATE NOT NULL,
        VenueId INT NULL,
        HotelId INT NULL,
        HotelName NVARCHAR(200) NULL,
        Category NVARCHAR(100) NULL,
        Board NVARCHAR(50) NULL,
        Price DECIMAL(10,2) NULL,
        PricePerNight DECIMAL(10,2) NULL,
        Currency NVARCHAR(10) NULL,
        Provider NVARCHAR(100) NULL,
        Nights INT NULL,
        CreatedAt DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_BrowserScanResults_ScanDate ON SalesOffice.BrowserScanResults(ScanDate);
    CREATE INDEX IX_BrowserScanResults_VenueId ON SalesOffice.BrowserScanResults(VenueId);
    PRINT 'Created SalesOffice.BrowserScanResults table';
END
"""

INSERT_SQL = """
INSERT INTO SalesOffice.BrowserScanResults
    (ScanDate, CheckInDate, CheckOutDate, VenueId, HotelId, HotelName, Category, Board, Price, PricePerNight, Currency, Provider, Nights)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def load_scan_report(filepath: str) -> dict:
    """Load and validate a scan report JSON file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Scan report not found: {filepath}")

    with open(path) as f:
        data = json.load(f)

    required_keys = ["scanDate", "searchDates", "hotels"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key '{key}' in scan report")

    return data


def write_to_db(data: dict, dry_run: bool = False) -> int:
    """Write scan results to database. Returns number of rows inserted."""
    scan_date = datetime.fromisoformat(f"{data['scanDate']}T{data.get('scanTime', '00:00:00')}")
    check_in = data["searchDates"]["checkIn"]
    check_out = data["searchDates"]["checkOut"]

    rows = []
    for hotel in data.get("hotels", []):
        venue_id = hotel.get("venueId")
        hotel_id = hotel.get("hotelId")
        hotel_name = hotel.get("name", "")

        for offer in hotel.get("offers", []):
            nights = offer.get("nights", 1)
            price = offer.get("price")
            price_per_night = round(price / nights, 2) if price and nights else None

            rows.append((
                scan_date,
                check_in,
                check_out,
                venue_id,
                hotel_id,
                hotel_name,
                offer.get("category"),
                offer.get("board"),
                price,
                price_per_night,
                offer.get("currency", "USD"),
                offer.get("provider"),
                nights,
            ))

    if not rows:
        logger.warning("No offers found in scan report")
        return 0

    if dry_run:
        print(f"[DRY RUN] Would insert {len(rows)} rows")
        for row in rows[:3]:
            print(f"  {row[5]} | {row[6]} | {row[7]} | ${row[8]} | {row[11]}")
        if len(rows) > 3:
            print(f"  ... and {len(rows) - 3} more")
        return len(rows)

    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()

    # Insert rows
    inserted = 0
    for row in rows:
        try:
            cursor.execute(INSERT_SQL, row)
            inserted += 1
        except pyodbc.Error as e:
            logger.error(f"Failed to insert row for {row[5]}: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Inserted {inserted}/{len(rows)} rows into SalesOffice.BrowserScanResults")
    return inserted


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/browser_to_db.py <scan-report.json> [--dry-run]")
        sys.exit(1)

    filepath = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    data = load_scan_report(filepath)
    hotel_count = len(data.get("hotels", []))
    offer_count = sum(len(h.get("offers", [])) for h in data.get("hotels", []))

    print(f"Loaded scan report: {data['scanDate']}")
    print(f"  Hotels: {hotel_count}, Offers: {offer_count}")
    print(f"  Dates: {data['searchDates']['checkIn']} → {data['searchDates']['checkOut']}")

    count = write_to_db(data, dry_run=dry_run)
    print(f"Done. {count} rows {'would be ' if dry_run else ''}written.")


if __name__ == "__main__":
    main()
