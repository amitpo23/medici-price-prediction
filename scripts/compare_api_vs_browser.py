"""Compare latest browser scan prices against API/DB prices.

Finds discrepancies between what Innstant B2B shows in browser
vs what our SalesOffice.Details has from API scans.

Usage:
    python3 scripts/compare_api_vs_browser.py [--date 2026-03-30]
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pyodbc

logger = logging.getLogger(__name__)

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=medici-sql-server.database.windows.net;"
    "DATABASE=medici-db;"
    "UID=prediction_reader;"
    "PWD=Pr3d!rzn223y5KoNdQ^z8nG&YJ7N%rdRc;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=15;"
)

BROWSER_QUERY = """
SELECT
    b.VenueId, b.HotelId, b.HotelName, b.Category, b.Board,
    b.PricePerNight AS BrowserPrice, b.Provider, b.CheckInDate, b.Nights
FROM SalesOffice.BrowserScanResults b
WHERE b.ScanDate = (SELECT MAX(ScanDate) FROM SalesOffice.BrowserScanResults)
ORDER BY b.HotelName, b.Category, b.Board
"""

API_QUERY = """
SELECT
    d.VenueId, d.HotelId, d.HotelName, d.Category, d.Board,
    d.Price AS ApiPrice, d.Provider, d.DateFrom
FROM SalesOffice.Details d
WHERE d.IsDeleted = 0
  AND d.VenueId IN ({venue_ids})
  AND d.DateFrom >= ?
  AND d.DateFrom <= ?
ORDER BY d.HotelName, d.Category, d.Board
"""


def fetch_browser_data(cursor) -> list[dict]:
    """Get latest browser scan results."""
    try:
        cursor.execute(BROWSER_QUERY)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except pyodbc.Error as e:
        logger.warning(f"BrowserScanResults table may not exist yet: {e}")
        return []


def fetch_api_data(cursor, venue_ids: list[int], check_in: str, check_out: str) -> list[dict]:
    """Get API scan results for same venues and dates."""
    if not venue_ids:
        return []

    placeholders = ",".join(str(v) for v in venue_ids)
    query = API_QUERY.format(venue_ids=placeholders)
    cursor.execute(query, check_in, check_out)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def compare(browser_data: list[dict], api_data: list[dict]) -> dict:
    """Compare browser vs API prices and generate discrepancy report."""
    # Build API lookup: (VenueId, Category, Board) -> best price
    api_lookup = {}
    for row in api_data:
        key = (row["VenueId"], str(row.get("Category", "")).lower(), str(row.get("Board", "")).lower())
        existing = api_lookup.get(key)
        if existing is None or (row["ApiPrice"] and row["ApiPrice"] < existing["ApiPrice"]):
            api_lookup[key] = row

    matches = []
    missing_in_api = []
    discrepancies = []

    for brow in browser_data:
        key = (brow["VenueId"], str(brow.get("Category", "")).lower(), str(brow.get("Board", "")).lower())
        api_row = api_lookup.get(key)

        if not api_row:
            missing_in_api.append(brow)
            continue

        browser_price = float(brow.get("BrowserPrice") or 0)
        api_price = float(api_row.get("ApiPrice") or 0)

        if api_price == 0:
            missing_in_api.append(brow)
            continue

        diff_pct = abs(browser_price - api_price) / api_price * 100 if api_price else 0

        entry = {
            "hotel": brow["HotelName"],
            "venueId": brow["VenueId"],
            "category": brow["Category"],
            "board": brow["Board"],
            "browserPrice": browser_price,
            "apiPrice": api_price,
            "diffPct": round(diff_pct, 1),
            "browserProvider": brow.get("Provider"),
            "apiProvider": api_row.get("Provider"),
        }

        if diff_pct > 5:
            discrepancies.append(entry)
        else:
            matches.append(entry)

    return {
        "scanDate": str(browser_data[0]["CheckInDate"]) if browser_data else None,
        "totalBrowserOffers": len(browser_data),
        "totalApiOffers": len(api_data),
        "matches": len(matches),
        "discrepancies": discrepancies,
        "missingInApi": missing_in_api,
        "summary": {
            "matchRate": round(len(matches) / max(len(browser_data), 1) * 100, 1),
            "discrepancyCount": len(discrepancies),
            "missingCount": len(missing_in_api),
            "avgDiscrepancyPct": round(
                sum(d["diffPct"] for d in discrepancies) / max(len(discrepancies), 1), 1
            ),
        },
    }


def print_report(report: dict):
    """Print human-readable comparison report."""
    print("=" * 70)
    print("BROWSER vs API PRICE COMPARISON")
    print("=" * 70)
    s = report["summary"]
    print(f"Browser offers: {report['totalBrowserOffers']}")
    print(f"API offers:     {report['totalApiOffers']}")
    print(f"Matches (<5%):  {report['matches']} ({s['matchRate']}%)")
    print(f"Discrepancies:  {s['discrepancyCount']} (avg {s['avgDiscrepancyPct']}% off)")
    print(f"Missing in API: {s['missingCount']}")
    print()

    if report["discrepancies"]:
        print("--- DISCREPANCIES (>5% difference) ---")
        for d in sorted(report["discrepancies"], key=lambda x: -x["diffPct"]):
            direction = "HIGHER" if d["browserPrice"] > d["apiPrice"] else "LOWER"
            print(
                f"  {d['hotel'][:30]:<30} {d['category']:<12} {d['board']:<4} "
                f"Browser ${d['browserPrice']:>8.2f} vs API ${d['apiPrice']:>8.2f} "
                f"({d['diffPct']:>5.1f}% {direction})"
            )
        print()

    if report["missingInApi"][:10]:
        print("--- MISSING IN API (first 10) ---")
        for m in report["missingInApi"][:10]:
            print(f"  {m['HotelName'][:30]:<30} {m['Category']:<12} {m['Board']:<4} ${float(m.get('BrowserPrice') or 0):>8.2f}")
        if len(report["missingInApi"]) > 10:
            print(f"  ... and {len(report['missingInApi']) - 10} more")


def main():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    # Get browser data
    browser_data = fetch_browser_data(cursor)
    if not browser_data:
        print("No browser scan results found. Run a browser scan first.")
        print("Use the browser-price-check skill or scan Innstant B2B manually.")
        cursor.close()
        conn.close()
        return

    # Get venue IDs and date range from browser data
    venue_ids = list(set(r["VenueId"] for r in browser_data if r["VenueId"]))
    check_in = str(browser_data[0].get("CheckInDate", ""))
    nights = browser_data[0].get("Nights", 2)
    check_in_dt = datetime.strptime(check_in[:10], "%Y-%m-%d") if check_in else datetime.now()
    check_out = str((check_in_dt + timedelta(days=nights)).date())

    # Get API data for same venues and dates
    api_data = fetch_api_data(cursor, venue_ids, check_in, check_out)

    cursor.close()
    conn.close()

    # Compare
    report = compare(browser_data, api_data)
    print_report(report)

    # Save report
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    report_path = Path(f"scan-reports/compare_{timestamp}.json")
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
