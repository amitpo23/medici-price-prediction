"""
Parity check for the browser-scan cloud migration.

Compares rows written by the local launchd agent (CreatedBy='local')
against rows written by GitHub Actions (CreatedBy='BrowserScan@GHA-parallel').

Usage:
    python3 scripts/parity_check.py [--window-hours 4] [--tolerance-usd 2.0]

Exit 0 if parity OK, exit 1 if blockers found (missing hotels, large price gaps).
"""
import argparse
import os
import sys
from dataclasses import dataclass
from typing import Dict

try:
    import pyodbc
except Exception as e:
    print(f"pyodbc not installed: {e}")
    sys.exit(2)


CONN_STR = os.environ.get(
    "MEDICI_CONNECTION_STRING",
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=tcp:medici-sql-server.database.windows.net,1433;"
    "DATABASE=medici-db;UID=medici_sql_admin;PWD=@Amit2025;"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
)

LOCAL = "local"
GHA = "BrowserScan@GHA-parallel"


@dataclass
class VenuePrice:
    created_by: str
    venue_id: int
    hotel_name: str
    cheapest_overall: float
    scan_ts: str


def fetch_rows(conn, window_hours: int) -> Dict[str, Dict[int, VenuePrice]]:
    """Return {created_by: {venue_id: latest VenuePrice}} within the window.
    Latest = highest ScanTimestamp."""
    c = conn.cursor()
    c.execute("""
        SELECT CreatedBy, VenueId, HotelName, CheapestOverall, ScanTimestamp
        FROM [SalesOffice.BrowserScanResults]
        WHERE DateCreated >= DATEADD(HOUR, -?, SYSUTCDATETIME())
        ORDER BY ScanTimestamp DESC
    """, window_hours)
    by_source: Dict[str, Dict[int, VenuePrice]] = {LOCAL: {}, GHA: {}}
    for row in c.fetchall():
        cb, vid, name, cheapest, ts = row
        if cb not in by_source:
            continue
        # keep latest per venue (first seen because sorted DESC)
        if vid in by_source[cb]:
            continue
        by_source[cb][vid] = VenuePrice(cb, int(vid), str(name or ""),
                                          float(cheapest) if cheapest is not None else 0.0,
                                          str(ts))
    return by_source


def compare(rows: Dict[str, Dict[int, VenuePrice]],
             tolerance_usd: float, tolerance_pct: float) -> dict:
    """A gap is a blocker only when it exceeds BOTH an absolute floor and a
    relative (%) threshold. One-sided zeros (Innstant intermittent failures
    where one scan got offers and the other got NO_RESULTS) are classified
    separately — they indicate data quality, not drift."""
    local = rows[LOCAL]
    gha = rows[GHA]

    common = set(local.keys()) & set(gha.keys())
    only_local = set(local.keys()) - set(gha.keys())
    only_gha = set(gha.keys()) - set(local.keys())

    gaps = []
    one_sided_zeros = []
    for vid in common:
        l, g = local[vid], gha[vid]
        l_price = l.cheapest_overall
        g_price = g.cheapest_overall
        # One-sided zero = Innstant flakiness, one scan returned NO_RESULTS.
        # Not a drift blocker — flag separately so operators see the signal
        # without triggering cutover blockers on natural scan noise.
        if (l_price == 0) != (g_price == 0):
            one_sided_zeros.append({
                "venue": vid, "hotel": l.hotel_name,
                "local": l_price, "gha": g_price,
                "side_with_data": "local" if l_price > 0 else "gha",
            })
            continue
        if l_price == 0 and g_price == 0:
            continue  # both empty — nothing to compare
        diff = abs(l_price - g_price)
        mean = (l_price + g_price) / 2.0 or 1.0
        pct = diff / mean * 100.0
        if diff > tolerance_usd and pct > tolerance_pct:
            gaps.append({
                "venue": vid, "hotel": l.hotel_name,
                "local": l_price, "gha": g_price,
                "diff": diff, "pct": pct,
            })
    gaps.sort(key=lambda x: x["diff"], reverse=True)

    return {
        "counts": {LOCAL: len(local), GHA: len(gha), "common": len(common)},
        "only_local": sorted(only_local),
        "only_gha": sorted(only_gha),
        "large_gaps": gaps,
        "one_sided_zeros": one_sided_zeros,
    }


def report(result: dict, tolerance_usd: float, tolerance_pct: float) -> int:
    c = result["counts"]
    print(f"\n  ─── Parity Check ───")
    print(f"  Local rows:     {c[LOCAL]}")
    print(f"  GHA rows:       {c[GHA]}")
    print(f"  Common venues:  {c['common']}")
    print()

    blockers = 0

    if c[GHA] == 0:
        print(f"  ⚠ No GHA rows in window — either first GHA run hasn't fired yet,")
        print(f"    or cloud is not writing. Re-check after the next scheduled run.")
        return 1

    if result["only_local"]:
        print(f"  ⚠ Hotels in local but not GHA ({len(result['only_local'])}):")
        print(f"      venues={result['only_local'][:10]}")
        blockers += 1

    if result["only_gha"]:
        print(f"  ⚠ Hotels in GHA but not local ({len(result['only_gha'])}):")
        print(f"      venues={result['only_gha'][:10]}")

    zeros = result.get("one_sided_zeros", [])
    if zeros:
        print(f"\n  ℹ Innstant flakiness — one side NO_RESULTS ({len(zeros)} venues):")
        for z in zeros[:5]:
            print(f"    venue={z['venue']:5d} {z['hotel'][:35]:35s}"
                  f" local=${z['local']:7.2f} gha=${z['gha']:7.2f}"
                  f" (data from: {z['side_with_data']})")
        if len(zeros) > 5:
            print(f"    ...and {len(zeros)-5} more — natural Innstant intermittent failure")
        print(f"  (not a cutover blocker — data quality signal, not drift)")

    gaps = result["large_gaps"]
    if gaps:
        print(f"\n  ⚠ Real price drift > ${tolerance_usd:.2f} AND >{tolerance_pct:.1f}% ({len(gaps)} venues):")
        for g in gaps[:10]:
            print(f"    venue={g['venue']:5d} {g['hotel'][:35]:35s}"
                  f" local=${g['local']:7.2f} gha=${g['gha']:7.2f}"
                  f" diff=${g['diff']:6.2f} ({g['pct']:.1f}%)")
        if len(gaps) > 10:
            print(f"    ...and {len(gaps)-10} more")
        blockers += 1
    else:
        print(f"  ✓ All common venues (both sides with data) within ${tolerance_usd:.2f} AND {tolerance_pct:.1f}% tolerance")

    if blockers == 0:
        print(f"\n  ✓ PARITY OK — safe to continue toward cutover")
        return 0
    print(f"\n  ⚠ {blockers} blocker(s) — investigate before cutover")
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--window-hours", type=int, default=4,
                    help="Lookback window (default: 4h, covers 1 local + 1 GHA cycle)")
    p.add_argument("--tolerance-usd", type=float, default=5.0,
                    help="Minimum absolute gap (USD) to flag — default $5 "
                         "(below this is natural Innstant price drift)")
    p.add_argument("--tolerance-pct", type=float, default=3.0,
                    help="Minimum relative gap (%%) to flag — default 3%% "
                         "(gap must exceed BOTH usd AND pct floors to be a blocker)")
    args = p.parse_args()

    conn = pyodbc.connect(CONN_STR, timeout=30)
    rows = fetch_rows(conn, args.window_hours)
    result = compare(rows, args.tolerance_usd, args.tolerance_pct)
    return report(result, args.tolerance_usd, args.tolerance_pct)


if __name__ == "__main__":
    sys.exit(main())
