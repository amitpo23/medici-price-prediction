"""
Price Drift Check — daily.

Compares browser-scan prices (from BrowserScanResults.RawJson) against
SalesOffice.Details API prices for the same venue + category + board,
and writes per-row drift results to [SalesOffice.PriceDriftReport].

Runs daily from GitHub Actions at 02:00 UTC. Replaces the older
scripts/compare_api_vs_browser.py which queried columns that no longer
exist in the BrowserScanResults schema.

Usage:
    python3 scripts/price_drift_check.py
    python3 scripts/price_drift_check.py --window-hours 6
    python3 scripts/price_drift_check.py --dry-run   # no DB write

Env:
    SCAN_DB_SERVER / SCAN_DB_NAME / SCAN_DB_USER / SCAN_DB_PASS
    CREATED_BY (default 'local')
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_reporter import RunReporter  # vendored from medici-hotels skills/_shared/


DRIFT_PCT_THRESHOLD = 5.0  # > 5% = DRIFT status


def get_conn_str() -> str:
    server = os.environ.get("SCAN_DB_SERVER", os.environ.get(
        "SOURCE_DB_SERVER", "medici-sql-server.database.windows.net"))
    database = os.environ.get("SCAN_DB_NAME",
                               os.environ.get("SOURCE_DB_NAME", "medici-db"))
    user = os.environ.get("SCAN_DB_USER",
                           os.environ.get("SOURCE_DB_USER", ""))
    password = os.environ.get("SCAN_DB_PASS",
                               os.environ.get("SOURCE_DB_PASS", ""))
    return (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER=tcp:{server},1433;DATABASE={database};"
        f"UID={user};PWD={password};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


@dataclass
class Offer:
    venue_id: int
    hotel_id: int
    hotel_name: str
    category: str
    board: str
    price: float
    provider: str


def load_browser_offers(cursor, window_hours: int) -> list[Offer]:
    """Unpack BrowserScanResults.RawJson into per-offer rows.

    We pick the MOST RECENT row per VenueId (based on ScanTimestamp) within
    the window, then expand its .offers array. This gives one Offer per
    (venue, category, board, provider) in the freshest scan.
    """
    cursor.execute("""
        ;WITH Latest AS (
            SELECT VenueId,
                   MAX(ScanTimestamp) AS MaxTs
            FROM [SalesOffice.BrowserScanResults]
            WHERE ScanTimestamp >= DATEADD(HOUR, -?, SYSUTCDATETIME())
              AND RawJson IS NOT NULL
            GROUP BY VenueId
        )
        SELECT b.VenueId, b.HotelId, b.HotelName, b.RawJson
        FROM [SalesOffice.BrowserScanResults] b
        JOIN Latest l
          ON b.VenueId = l.VenueId AND b.ScanTimestamp = l.MaxTs
        WHERE b.RawJson IS NOT NULL
    """, window_hours)

    out: list[Offer] = []
    for vid, hid, hname, raw_json in cursor.fetchall():
        try:
            doc = json.loads(raw_json)
        except (TypeError, json.JSONDecodeError):
            continue
        for off in doc.get("offers", []):
            price = off.get("price")
            if price is None:
                continue
            out.append(Offer(
                venue_id=int(vid),
                hotel_id=int(hid) if hid is not None else 0,
                hotel_name=hname or doc.get("name", ""),
                category=(off.get("category") or "").strip().lower(),
                board=(off.get("board") or "").strip().upper(),
                price=float(price),
                provider=off.get("provider") or "",
            ))
    return out


def load_api_prices(cursor, venue_ids: list[int]) -> dict[tuple[int, str, str], Offer]:
    """Per (VenueId, RoomCategory, RoomBoard), return the LOWEST active
    RoomPrice from SalesOffice.Details. No time filter — the WebJob keeps
    Details fresh by overwriting in-place, and different hotels refresh
    on different cycles (some are 48h stale). Best-available snapshot."""
    if not venue_ids:
        return {}
    venue_csv = ",".join(str(v) for v in venue_ids)

    cursor.execute(f"""
        SELECT HotelId, Innstant_ZenithId
        FROM Med_Hotels
        WHERE Innstant_ZenithId IN ({venue_csv})
    """)
    hotel_to_venue = {int(hid): int(vid) for hid, vid in cursor.fetchall()}

    cursor.execute(f"""
        SELECT d.HotelId, d.RoomCategory, d.RoomBoard, MIN(d.RoomPrice) AS MinPrice
        FROM [SalesOffice.Details] d
        JOIN Med_Hotels h ON h.HotelId = d.HotelId
        WHERE h.Innstant_ZenithId IN ({venue_csv})
          AND d.IsDeleted = 0
          AND d.RoomPrice IS NOT NULL
          AND d.RoomPrice > 0
        GROUP BY d.HotelId, d.RoomCategory, d.RoomBoard
    """)
    result: dict[tuple[int, str, str], Offer] = {}
    for hid, cat, board, min_price in cursor.fetchall():
        venue = hotel_to_venue.get(int(hid))
        if venue is None or min_price is None:
            continue
        key = (venue, (cat or "").strip().lower(), (board or "").strip().upper())
        result[key] = Offer(
            venue_id=venue, hotel_id=int(hid), hotel_name="",
            category=key[1], board=key[2], price=float(min_price), provider="API",
        )
    return result


def classify(browser_price: Optional[float], api_price: Optional[float]) -> tuple[str, float, float]:
    """Return (Status, DiffUsd, DiffPct)."""
    if browser_price is None and api_price is None:
        return ("NO_DATA", 0.0, 0.0)
    if browser_price is None:
        return ("MISSING_BROWSER", api_price or 0.0, 100.0)
    if api_price is None or api_price == 0:
        return ("MISSING_API", browser_price, 100.0)
    diff = browser_price - api_price
    pct = abs(diff) / api_price * 100.0
    return ("DRIFT" if pct > DRIFT_PCT_THRESHOLD else "MATCH", diff, pct)


def compare_and_build_rows(browser: list[Offer], api: dict) -> list[dict]:
    """Pair each browser offer with its best-match API entry. Also emits
    MISSING_BROWSER rows for API entries with no browser counterpart."""
    rows: list[dict] = []
    seen_api_keys: set[tuple[int, str, str]] = set()

    for b in browser:
        key = (b.venue_id, b.category, b.board)
        a = api.get(key)
        status, diff_usd, diff_pct = classify(b.price, a.price if a else None)
        if a:
            seen_api_keys.add(key)
        rows.append({
            "VenueId": b.venue_id, "HotelId": b.hotel_id, "HotelName": b.hotel_name,
            "Category": b.category, "Board": b.board,
            "BrowserPrice": b.price,
            "ApiPrice": a.price if a else None,
            "DiffUsd": diff_usd, "DiffPct": diff_pct,
            "BrowserProvider": b.provider,
            "ApiProvider": a.provider if a else None,
            "Status": status,
        })

    # API-only keys (browser didn't see them)
    for key, a in api.items():
        if key in seen_api_keys:
            continue
        rows.append({
            "VenueId": a.venue_id, "HotelId": a.hotel_id, "HotelName": a.hotel_name,
            "Category": a.category, "Board": a.board,
            "BrowserPrice": None, "ApiPrice": a.price,
            "DiffUsd": -a.price, "DiffPct": 100.0,
            "BrowserProvider": None, "ApiProvider": a.provider,
            "Status": "MISSING_BROWSER",
        })
    return rows


def write_rows(conn, rows: list[dict], created_by: str) -> int:
    if not rows:
        return 0
    c = conn.cursor()
    c.fast_executemany = True
    params = [(
        r["VenueId"], r["HotelId"], r["HotelName"][:200] if r["HotelName"] else None,
        r["Category"], r["Board"],
        r["BrowserPrice"], r["ApiPrice"], r["DiffUsd"], r["DiffPct"],
        r["BrowserProvider"][:100] if r["BrowserProvider"] else None,
        r["ApiProvider"][:100] if r["ApiProvider"] else None,
        r["Status"], created_by,
    ) for r in rows]
    c.executemany("""
        INSERT INTO [SalesOffice.PriceDriftReport]
          (VenueId, HotelId, HotelName, Category, Board,
           BrowserPrice, ApiPrice, DiffUsd, DiffPct,
           BrowserProvider, ApiProvider, Status, CreatedBy)
        VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?)
    """, params)
    conn.commit()
    return len(params)


def summarize(rows: list[dict]) -> None:
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["Status"]] = by_status.get(r["Status"], 0) + 1
    total = sum(by_status.values()) or 1
    print(f"\n  ─── Price Drift Summary ({len(rows)} rows) ───")
    for status in ("MATCH", "DRIFT", "MISSING_API", "MISSING_BROWSER", "NO_DATA"):
        n = by_status.get(status, 0)
        print(f"    {status:17s} {n:5d} ({n/total*100:5.1f}%)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--window-hours", type=int, default=6,
                    help="How far back to look for browser scans (default: 6h).")
    p.add_argument("--dry-run", action="store_true",
                    help="Compute and print summary, don't write to DB.")
    args = p.parse_args()

    created_by = os.environ.get("CREATED_BY", "local")
    print(f"  Price drift check — window {args.window_hours}h, CreatedBy={created_by}")

    conn = pyodbc.connect(get_conn_str(), timeout=30)
    try:
        with RunReporter(
            conn,
            agent_name="price-drift",
            created_by=created_by,
            summary={"window_hours": args.window_hours},
        ) as reporter:
            cur = conn.cursor()
            browser = load_browser_offers(cur, args.window_hours)
            if not browser:
                print("  No recent browser offers — nothing to compare.")
                reporter.summary["status"] = "no_data"
                return 0
            venue_ids = sorted({o.venue_id for o in browser})
            api = load_api_prices(cur, venue_ids)
            rows = compare_and_build_rows(browser, api)
            summarize(rows)

            # Capture summary metrics for AgentRunLog
            by_status: dict[str, int] = {}
            for r in rows:
                by_status[r["Status"]] = by_status.get(r["Status"], 0) + 1
            reporter.summary.update({
                "venues_compared": len(venue_ids),
                "rows_total": len(rows),
                "match": by_status.get("MATCH", 0),
                "drift": by_status.get("DRIFT", 0),
                "missing_api": by_status.get("MISSING_API", 0),
                "missing_browser": by_status.get("MISSING_BROWSER", 0),
            })

            if args.dry_run:
                print("\n  [DRY RUN] skipping DB write.")
                reporter.summary["dry_run"] = True
                return 0
            inserted = write_rows(conn, rows, created_by)
            reporter.summary["inserted"] = inserted
            print(f"\n  ✓ Inserted {inserted} rows into [SalesOffice.PriceDriftReport]")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
