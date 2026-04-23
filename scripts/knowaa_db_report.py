#!/usr/bin/env python3
"""Knowaa SearchLog Report — daily DB-based competitive analysis.

Queries SearchResultsSessionPollLog to produce a full Knowaa performance
report (coverage, #1 win rate, price gap per hotel/category/board/day) and
saves markdown + JSON to shared-reports/ with a "searchlog" tag so it's
distinguishable from the browser-based Innstant scan reports.

Scheduled via ~/Library/LaunchAgents/com.medici.knowaa-db-report.plist
(once per day). Can also be run manually.

Usage:
    python3 scripts/knowaa_db_report.py [--hours 48]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "shared-reports"
SCAN_REPORTS_DIR = ROOT / "scan-reports"
REPORT_TAG = "knowaa_searchlog_report"


def _load_env() -> None:
    """Load .env values into os.environ (local dev). No-op on GHA /
    any environment where the file is absent — we expect env vars to be
    set by the runner's secrets injection there."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def _conn() -> pyodbc.Connection:
    _load_env()
    cs = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.environ['SOURCE_DB_SERVER']};"
        f"DATABASE={os.environ['SOURCE_DB_NAME']};"
        f"UID={os.environ['SOURCE_DB_USER']};"
        f"PWD={os.environ['SOURCE_DB_PASS']};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=20"
    )
    return pyodbc.connect(cs, autocommit=True, timeout=900)


def fetch_hotels() -> list[tuple[int, int, str]]:
    with _conn() as cn:
        cur = cn.cursor()
        cur.execute("""SELECT HotelId, Innstant_ZenithId, name FROM Med_Hotels
                       WHERE Innstant_ZenithId BETWEEN 5000 AND 5300 AND isActive=1
                       ORDER BY Innstant_ZenithId""")
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def scan_hotel(hid: int, hours: int) -> list[tuple]:
    """Return list of (date, category, board, min_price, knowaa_min) for each session."""
    sql = """
      SELECT
        CAST(RequestTime AS DATE) AS d,
        ISNULL(RoomCategory, '?') AS cat,
        ISNULL(RoomBoard, '?') AS brd,
        MIN(PriceAmount) AS min_price,
        MIN(CASE WHEN Providers LIKE '%Knowaa%' THEN PriceAmount END) AS knowaa_min
      FROM [SearchResultsSessionPollLog] WITH(NOLOCK)
      WHERE HotelId = ?
        AND RequestTime > DATEADD(hour, -?, GETUTCDATE())
        AND PriceAmount > 0
      GROUP BY CAST(RequestTime AS DATE),
               ISNULL(RoomCategory, '?'),
               ISNULL(RoomBoard, '?'),
               DATEDIFF(minute, '2026-01-01', RequestTime)
    """
    with _conn() as cn:
        cur = cn.cursor()
        cur.execute(sql, hid, hours)
        return cur.fetchall()


def build_report(hours: int) -> dict:
    hotels = fetch_hotels()
    print(f"Scanning {len(hotels)} Miami hotels (window: {hours}h)...", file=sys.stderr)

    per_hotel = {}
    per_cat_board = defaultdict(lambda: {"sessions": 0, "knowaa_in": 0, "knowaa_1": 0, "gap_sum": 0.0, "gap_n": 0})
    per_day = defaultdict(lambda: {"sessions": 0, "knowaa_in": 0, "knowaa_1": 0})
    total = {"sessions": 0, "knowaa_in": 0, "knowaa_1": 0}
    failures = []
    start = time.time()

    for i, (hid, zid, hname) in enumerate(hotels, 1):
        t0 = time.time()
        try:
            rows = scan_hotel(hid, hours)
        except pyodbc.Error as e:
            failures.append({"hid": hid, "zid": zid, "name": hname, "error": str(e)[:200]})
            print(f"  [{i:>2}/{len(hotels)}] {zid} FAIL: {str(e)[:80]}", file=sys.stderr)
            continue
        h = {"sessions": 0, "knowaa_in": 0, "knowaa_1": 0, "gap_sum": 0.0, "gap_n": 0}
        for d, cat, brd, min_p, knowaa_p in rows:
            h["sessions"] += 1
            total["sessions"] += 1
            day_key = str(d)
            per_day[day_key]["sessions"] += 1
            key = (cat, brd)
            per_cat_board[key]["sessions"] += 1
            if knowaa_p is not None:
                h["knowaa_in"] += 1
                total["knowaa_in"] += 1
                per_day[day_key]["knowaa_in"] += 1
                per_cat_board[key]["knowaa_in"] += 1
                if float(knowaa_p) <= float(min_p) + 0.01:
                    h["knowaa_1"] += 1
                    total["knowaa_1"] += 1
                    per_day[day_key]["knowaa_1"] += 1
                    per_cat_board[key]["knowaa_1"] += 1
                gap = float(knowaa_p) - float(min_p)
                h["gap_sum"] += gap
                h["gap_n"] += 1
                per_cat_board[key]["gap_sum"] += gap
                per_cat_board[key]["gap_n"] += 1
        per_hotel[hid] = {"zid": zid, "name": hname, **h}
        print(f"  [{i:>2}/{len(hotels)}] {zid} {hname[:30]:30s} "
              f"sess={h['sessions']:>4} K={h['knowaa_in']:>3} #1={h['knowaa_1']:>3} t={time.time()-t0:.1f}s",
              file=sys.stderr)

    scan_time = int(time.time() - start)
    print(f"\nScan done in {scan_time}s", file=sys.stderr)

    return {
        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source": "SearchResultsSessionPollLog",
        "window_hours": hours,
        "scan_duration_seconds": scan_time,
        "hotels_scanned": len(hotels),
        "hotels_failed": len(failures),
        "failures": failures,
        "totals": total,
        "per_hotel": list(per_hotel.values()),
        "per_cat_board": [
            {"category": k[0], "board": k[1], **v} for k, v in per_cat_board.items()
        ],
        "per_day": [{"date": k, **v} for k, v in sorted(per_day.items(), reverse=True)],
    }


def render_markdown(report: dict) -> str:
    t = report["totals"]
    lines = []
    lines.append(f"# Knowaa SearchLog Report — {report['generated_at_utc']}")
    lines.append("")
    lines.append(f"**Source:** `SearchResultsSessionPollLog` (DB-based) | "
                 f"**Window:** {report['window_hours']}h | "
                 f"**Hotels scanned:** {report['hotels_scanned']} | "
                 f"**Scan duration:** {report['scan_duration_seconds']}s")
    lines.append("")
    lines.append("> **How it works:** Each row in SearchResultsSessionPollLog = one offer from one provider in a search session. "
                 "A session is defined as (HotelId, RoomCategory, RoomBoard, RequestTime bucketed to minute). "
                 "For each session we check if Knowaa responded and whether it had the lowest price.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total search sessions | {t['sessions']:,} |")
    if t["sessions"]:
        k_pct = 100 * t["knowaa_in"] / t["sessions"]
        one_pct = 100 * t["knowaa_1"] / t["sessions"]
        lines.append(f"| Knowaa responded | **{t['knowaa_in']:,}** ({k_pct:.1f}%) |")
        lines.append(f"| Knowaa #1 (cheapest) | **{t['knowaa_1']:,}** ({one_pct:.1f}%) |")
        if t["knowaa_in"]:
            win_rate = 100 * t["knowaa_1"] / t["knowaa_in"]
            lines.append(f"| #1 rate when present | {win_rate:.1f}% |")
    lines.append("")

    # Per hotel
    lines.append("## Per Hotel (sorted by Knowaa activity)")
    lines.append("")
    lines.append("| Zenith | Hotel | Sessions | Knowaa % | #1 % | Avg Gap $ |")
    lines.append("|--------|-------|----------|----------|------|-----------|")
    ranked = sorted(report["per_hotel"],
                    key=lambda x: (-x["knowaa_in"], -x["sessions"]))
    for h in ranked:
        s = h["sessions"]
        if s == 0:
            continue
        k_pct = 100 * h["knowaa_in"] / s
        one_pct = 100 * h["knowaa_1"] / s
        avg_gap = h["gap_sum"] / h["gap_n"] if h["gap_n"] else 0
        gap_str = f"{avg_gap:+.2f}" if h["gap_n"] else "—"
        lines.append(f"| {h['zid']} | {h['name']} | {s} | {k_pct:.1f}% | {one_pct:.1f}% | {gap_str} |")
    # Hotels with 0 sessions
    zero = [h for h in report["per_hotel"] if h["sessions"] == 0]
    if zero:
        lines.append("")
        lines.append(f"### Hotels with 0 sessions in window ({len(zero)})")
        lines.append("")
        for h in zero:
            lines.append(f"- {h['zid']} — {h['name']}")
    lines.append("")

    # Per category/board
    lines.append("## Per Category × Board")
    lines.append("")
    lines.append("| Category | Board | Sessions | Knowaa % | #1 % | Avg Gap $ |")
    lines.append("|----------|-------|----------|----------|------|-----------|")
    for cb in sorted(report["per_cat_board"], key=lambda x: -x["sessions"]):
        s = cb["sessions"]
        if s < 5:
            continue
        k_pct = 100 * cb["knowaa_in"] / s
        one_pct = 100 * cb["knowaa_1"] / s
        avg_gap = cb["gap_sum"] / cb["gap_n"] if cb["gap_n"] else 0
        gap_str = f"{avg_gap:+.2f}" if cb["gap_n"] else "—"
        lines.append(f"| {cb['category']} | {cb['board']} | {s} | {k_pct:.1f}% | {one_pct:.1f}% | {gap_str} |")
    lines.append("")

    # Daily trend
    lines.append("## Daily Trend")
    lines.append("")
    lines.append("| Date | Sessions | Knowaa % | #1 % |")
    lines.append("|------|----------|----------|------|")
    for d in report["per_day"]:
        s = d["sessions"]
        k_pct = 100 * d["knowaa_in"] / s if s else 0
        one_pct = 100 * d["knowaa_1"] / s if s else 0
        lines.append(f"| {d['date']} | {s} | {k_pct:.1f}% | {one_pct:.1f}% |")
    lines.append("")

    # Failures
    if report["failures"]:
        lines.append("## Failures")
        lines.append("")
        for f in report["failures"]:
            lines.append(f"- {f['zid']} {f['name']} — {f['error']}")
        lines.append("")

    return "\n".join(lines)


def write_to_db(report: dict, created_by: str) -> int:
    """Upsert per-hotel aggregates into [SalesOffice.KnowaaPerformanceDaily].

    MERGE-based upsert (no DELETE needed) — matches on (ReportDate, HotelId,
    CreatedBy). Required because prediction_reader has a DB-wide DENY DELETE
    that blocks any DELETE regardless of per-table GRANT.

    Returns number of rows written.
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    hours = int(report.get("window_hours", 24))

    params = []
    for h in report.get("per_hotel", []):
        sessions = int(h.get("sessions", 0))
        k_in = int(h.get("knowaa_in", 0))
        k_1 = int(h.get("knowaa_1", 0))
        gap_n = int(h.get("gap_n", 0))
        gap_sum = float(h.get("gap_sum", 0.0))
        coverage_pct = round(k_in / sessions * 100, 2) if sessions else 0.0
        n1_pct = round(k_1 / k_in * 100, 2) if k_in else 0.0
        avg_gap = round(gap_sum / gap_n, 2) if gap_n else None
        params.append((
            date_str, hours,
            int(h.get("zid") or 0),
            (h.get("name") or "")[:200],
            None, None,   # RoomCategory, RoomBoard (hotel-level)
            sessions, k_in, coverage_pct, k_1, n1_pct, avg_gap,
            created_by,
        ))

    if not params:
        return 0

    with _conn() as cn:
        cur = cn.cursor()
        # Per-row upsert with MERGE — no table-wide DELETE needed.
        # Safe for any principal with SELECT+INSERT+UPDATE on the table.
        for p in params:
            cur.execute("""
                MERGE [SalesOffice.KnowaaPerformanceDaily] AS T
                USING (VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)) AS S
                      (ReportDate, WindowHours, HotelId, HotelName,
                       RoomCategory, RoomBoard,
                       Sessions, KnowaaSessions, KnowaaCoveragePct,
                       KnowaaNumber1Sessions, KnowaaNumber1Pct, AvgGapUsd, CreatedBy)
                ON  T.ReportDate = S.ReportDate
                AND T.HotelId    = S.HotelId
                AND T.CreatedBy  = S.CreatedBy
                AND ISNULL(T.RoomCategory,'') = ISNULL(S.RoomCategory,'')
                AND ISNULL(T.RoomBoard,'')    = ISNULL(S.RoomBoard,'')
                WHEN MATCHED THEN UPDATE SET
                    WindowHours           = S.WindowHours,
                    HotelName             = S.HotelName,
                    Sessions              = S.Sessions,
                    KnowaaSessions        = S.KnowaaSessions,
                    KnowaaCoveragePct     = S.KnowaaCoveragePct,
                    KnowaaNumber1Sessions = S.KnowaaNumber1Sessions,
                    KnowaaNumber1Pct      = S.KnowaaNumber1Pct,
                    AvgGapUsd             = S.AvgGapUsd,
                    InsertedAt            = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (ReportDate, WindowHours, HotelId, HotelName,
                            RoomCategory, RoomBoard,
                            Sessions, KnowaaSessions, KnowaaCoveragePct,
                            KnowaaNumber1Sessions, KnowaaNumber1Pct,
                            AvgGapUsd, CreatedBy)
                    VALUES (S.ReportDate, S.WindowHours, S.HotelId, S.HotelName,
                            S.RoomCategory, S.RoomBoard,
                            S.Sessions, S.KnowaaSessions, S.KnowaaCoveragePct,
                            S.KnowaaNumber1Sessions, S.KnowaaNumber1Pct,
                            S.AvgGapUsd, S.CreatedBy);
            """, *p)
        cn.commit()
        return len(params)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=int, default=48)
    p.add_argument("--outdir", type=Path, default=REPORTS_DIR)
    p.add_argument("--also-scan-reports", action="store_true", default=True,
                   help="Also copy to scan-reports/ (default: on)")
    # DB write flags (new — 2026-04-22)
    p.add_argument("--no-db", action="store_true",
                   help="Skip write to SalesOffice.KnowaaPerformanceDaily")
    # Cloud-mode flags (new) — GHA invokes with these set
    p.add_argument("--no-files", action="store_true",
                   help="Skip writing markdown/JSON report files to disk")
    p.add_argument("--no-push", action="store_true",
                   help="Skip git push (default behaviour for cloud runs)")
    args = p.parse_args()

    report = build_report(args.hours)
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # DB write (primary output shared with medici-hotels)
    if not args.no_db:
        try:
            created_by = os.environ.get("CREATED_BY", "local")
            n = write_to_db(report, created_by)
            print(f"Inserted {n} rows into [SalesOffice.KnowaaPerformanceDaily] (CreatedBy={created_by})",
                  file=sys.stderr)
        except pyodbc.Error as e:
            print(f"DB write failed: {str(e)[:200]}", file=sys.stderr)

    # File output (unchanged behavior unless --no-files)
    if not args.no_files:
        args.outdir.mkdir(parents=True, exist_ok=True)
        md_path = args.outdir / f"{date_str}_{REPORT_TAG}.md"
        json_path = args.outdir / f"{stamp}_{REPORT_TAG}.json"
        md_path.write_text(render_markdown(report))
        json_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"Wrote {md_path}", file=sys.stderr)
        print(f"Wrote {json_path}", file=sys.stderr)

        if args.also_scan_reports:
            SCAN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            md_copy = SCAN_REPORTS_DIR / f"{date_str}_{REPORT_TAG}.md"
            md_copy.write_text(render_markdown(report))
            print(f"Wrote {md_copy}", file=sys.stderr)

    # Git push — skipped when --no-push (cloud runs) or --no-files
    if not args.no_push and not args.no_files:
        try:
            import subprocess
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=ROOT, check=False)
            subprocess.run(["git", "add", "shared-reports/", "scan-reports/"], cwd=ROOT, check=False)
            subprocess.run(["git", "commit", "-m", f"chore: daily knowaa-searchlog report {date_str}"], cwd=ROOT, check=False)
            subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=False)
        except Exception as e:
            print(f"git push failed: {e}", file=sys.stderr)

    # Print markdown to stdout too (unless --no-files, to reduce GHA log noise)
    if not args.no_files:
        print(render_markdown(report))


if __name__ == "__main__":
    main()
