"""SalesOffice Analytics Runner - collect, analyze, report on schedule.

Usage:
    # Run once (collect + analyze + report):
    python -m src.analytics.runner

    # Run with hourly scheduler:
    python -m src.analytics.runner --schedule

    # Collect only:
    python -m src.analytics.runner --collect-only

    # Analyze only (from existing snapshots):
    python -m src.analytics.runner --analyze-only
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from threading import Event, Thread

from src.analytics.collector import collect_prices
from src.analytics.analyzer import run_analysis
from src.analytics.report import generate_report
from src.analytics.price_store import init_db, get_snapshot_count

logger = logging.getLogger(__name__)

HOUR = 3600


def run_cycle() -> dict | None:
    """Run one full cycle: collect -> analyze -> report."""
    logger.info("=" * 60)
    logger.info("Starting analysis cycle at %s", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # Step 1: Collect
    logger.info("[1/3] Collecting prices from SalesOffice...")
    df = collect_prices()
    if df.empty:
        logger.warning("No data collected - skipping analysis")
        return None
    logger.info("  Collected %d rooms from %d hotels", len(df), df["hotel_id"].nunique())

    # Step 2: Analyze
    logger.info("[2/3] Running analysis...")
    analysis = run_analysis()
    if "error" in analysis:
        logger.error("  Analysis failed: %s", analysis["error"])
        return None

    stats = analysis.get("statistics", {})
    logger.info("  Stats: %d rooms, avg $%.0f, range $%.0f–$%.0f",
                stats.get("total_rooms", 0),
                stats.get("price_mean", 0),
                stats.get("price_min", 0),
                stats.get("price_max", 0))

    predictions = analysis.get("predictions", {})
    logger.info("  Predictions: %d rooms forecasted", len(predictions))

    # Step 3: Generate report
    logger.info("[3/3] Generating report...")
    report_path = generate_report(analysis)
    logger.info("  Report: %s", report_path)

    snapshots = get_snapshot_count()
    logger.info("Total snapshots in DB: %d", snapshots)
    logger.info("Cycle complete.\n")

    return analysis


def print_summary(analysis: dict) -> None:
    """Print a text summary to console."""
    stats = analysis.get("statistics", {})
    hotels = analysis.get("hotels", [])
    predictions = analysis.get("predictions", {})
    bw = analysis.get("booking_window", {})

    print("\n" + "=" * 70)
    print(f"  SALESOFFICE PRICE ANALYSIS - {analysis.get('run_ts', '')}")
    print("=" * 70)

    print(f"\n  Total Rooms: {stats.get('total_rooms', 0)} | Hotels: {stats.get('total_hotels', 0)}")
    print(f"  Price: ${stats.get('price_min', 0):,.0f} - ${stats.get('price_max', 0):,.0f} "
          f"(avg: ${stats.get('price_mean', 0):,.0f}, median: ${stats.get('price_median', 0):,.0f})")
    print(f"  Total Inventory Value: ${stats.get('total_inventory_value', 0):,.0f}")
    print(f"  Avg Days to Check-in: {stats.get('avg_days_to_checkin', 0):.0f}")

    print(f"\n  {'Hotel':<35} {'Rooms':>6} {'Min':>8} {'Avg':>8} {'Max':>8} {'Std':>8}")
    print("  " + "-" * 75)
    for h in hotels:
        print(f"  {h['hotel_name'][:35]:<35} {h['total_rooms']:>6} "
              f"${h['price_min']:>7,.0f} ${h['price_mean']:>7,.0f} "
              f"${h['price_max']:>7,.0f} ${h['price_std']:>7,.0f}")

    # Category breakdown
    by_cat = stats.get("by_category", {})
    if by_cat:
        print(f"\n  By Category:")
        for cat, info in by_cat.items():
            print(f"    {cat}: {info['count']} rooms, avg ${info['avg_price']:,.0f}")

    # Booking window
    windows = bw.get("windows", [])
    if windows:
        print(f"\n  Booking Window (correlation: {bw.get('price_days_correlation', 0)}):")
        for w in windows:
            print(f"    {w['window']}: {w['rooms']} rooms, avg ${w['avg_price']:,.0f} "
                  f"(${w['min_price']:,.0f}–${w['max_price']:,.0f})")

    # Predictions summary
    if predictions:
        increases = sum(1 for p in predictions.values() if p.get("expected_change_pct", 0) > 0)
        decreases = sum(1 for p in predictions.values() if p.get("expected_change_pct", 0) < 0)
        avg_change = sum(p.get("expected_change_pct", 0) for p in predictions.values()) / len(predictions)
        print(f"\n  Predictions ({len(predictions)} rooms):")
        print(f"    Expected increases: {increases} | Decreases: {decreases}")
        print(f"    Avg expected change: {avg_change:+.1f}%")

        # Top 5 biggest expected changes
        sorted_preds = sorted(predictions.values(), key=lambda p: abs(p.get("expected_change_pct", 0)), reverse=True)
        print(f"\n  Top 5 Expected Changes:")
        for p in sorted_preds[:5]:
            print(f"    {p['hotel_name'][:25]} | {p['category']}/{p['board']} | "
                  f"{p['date_from'][:10]} | ${p['current_price']:,.0f} -> ${p['predicted_checkin_price']:,.0f} "
                  f"({p['expected_change_pct']:+.1f}%)")

    # Price changes
    changes = analysis.get("price_changes", {})
    if changes.get("changes"):
        print(f"\n  Price Changes ({changes['total_changes']} detected):")
        for c in changes["changes"][:5]:
            print(f"    {c['hotel_name'][:25]} | {c['date_from'][:10]} | "
                  f"${c['old_price']:,.0f} -> ${c['new_price']:,.0f} ({c['change_pct']:+.1f}%)")
    elif changes.get("note"):
        print(f"\n  Price Changes: {changes['note']}")

    print("\n" + "=" * 70)


def run_scheduler(interval_seconds: int = HOUR) -> None:
    """Run collection + analysis on a schedule."""
    stop = Event()

    logger.info("Starting SalesOffice analytics scheduler (every %d seconds)", interval_seconds)

    def loop():
        while not stop.is_set():
            try:
                analysis = run_cycle()
                if analysis:
                    print_summary(analysis)
            except Exception as e:
                logger.error("Cycle failed: %s", e, exc_info=True)
            stop.wait(interval_seconds)

    thread = Thread(target=loop, daemon=True)
    thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        stop.set()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description="SalesOffice Price Analytics")
    parser.add_argument("--schedule", action="store_true", help="Run on hourly schedule")
    parser.add_argument("--interval", type=int, default=HOUR, help="Schedule interval in seconds")
    parser.add_argument("--collect-only", action="store_true", help="Only collect prices")
    parser.add_argument("--analyze-only", action="store_true", help="Only run analysis on existing data")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    init_db()

    if args.collect_only:
        df = collect_prices()
        if not df.empty:
            print(f"Collected {len(df)} rooms from {df['hotel_id'].nunique()} hotels")
        return

    if args.analyze_only:
        analysis = run_analysis()
        if "error" not in analysis:
            report_path = generate_report(analysis)
            print_summary(analysis)
            print(f"\nReport: {report_path}")
        else:
            print(f"Error: {analysis['error']}")
        return

    if args.schedule:
        run_scheduler(args.interval)
        return

    # Default: run once
    analysis = run_cycle()
    if analysis:
        print_summary(analysis)


if __name__ == "__main__":
    main()
