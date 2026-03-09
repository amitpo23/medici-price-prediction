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
    """Log a text summary of the analysis results."""
    stats = analysis.get("statistics", {})
    hotels = analysis.get("hotels", [])
    predictions = analysis.get("predictions", {})
    bw = analysis.get("booking_window", {})

    logger.info("SALESOFFICE PRICE ANALYSIS - %s", analysis.get("run_ts", ""))
    logger.info(
        "Rooms: %d | Hotels: %d | Price: $%s–$%s (avg $%s) | Inventory: $%s",
        stats.get("total_rooms", 0),
        stats.get("total_hotels", 0),
        f"{stats.get('price_min', 0):,.0f}",
        f"{stats.get('price_max', 0):,.0f}",
        f"{stats.get('price_mean', 0):,.0f}",
        f"{stats.get('total_inventory_value', 0):,.0f}",
    )

    for h in hotels:
        logger.info(
            "  %s: %d rooms, $%s–$%s (avg $%s)",
            h["hotel_name"][:35], h["total_rooms"],
            f"{h['price_min']:,.0f}", f"{h['price_max']:,.0f}", f"{h['price_mean']:,.0f}",
        )

    by_cat = stats.get("by_category", {})
    if by_cat:
        for cat, info in by_cat.items():
            logger.info("  Category %s: %d rooms, avg $%s", cat, info["count"], f"{info['avg_price']:,.0f}")

    windows = bw.get("windows", [])
    if windows:
        logger.info("Booking window correlation: %s", bw.get("price_days_correlation", 0))
        for w in windows:
            logger.info("  %s: %d rooms, avg $%s", w["window"], w["rooms"], f"{w['avg_price']:,.0f}")

    if predictions:
        increases = sum(1 for p in predictions.values() if p.get("expected_change_pct", 0) > 0)
        decreases = sum(1 for p in predictions.values() if p.get("expected_change_pct", 0) < 0)
        avg_change = sum(p.get("expected_change_pct", 0) for p in predictions.values()) / len(predictions)
        logger.info(
            "Predictions: %d rooms, %d increases, %d decreases, avg change %+.1f%%",
            len(predictions), increases, decreases, avg_change,
        )

        sorted_preds = sorted(predictions.values(), key=lambda p: abs(p.get("expected_change_pct", 0)), reverse=True)
        for p in sorted_preds[:5]:
            logger.info(
                "  Top change: %s | $%s -> $%s (%+.1f%%)",
                p["hotel_name"][:25],
                f"{p['current_price']:,.0f}",
                f"{p['predicted_checkin_price']:,.0f}",
                p["expected_change_pct"],
            )

    changes = analysis.get("price_changes", {})
    if changes.get("changes"):
        logger.info("Price changes: %d detected", changes["total_changes"])
        for c in changes["changes"][:5]:
            logger.info(
                "  %s | %s | $%s -> $%s (%+.1f%%)",
                c["hotel_name"][:25], c["date_from"][:10],
                f"{c['old_price']:,.0f}", f"{c['new_price']:,.0f}", c["change_pct"],
            )
    elif changes.get("note"):
        logger.info("Price changes: %s", changes["note"])


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
            except (OSError, ConnectionError, ValueError, RuntimeError) as e:
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

    from src.utils.logging_config import configure_logging
    configure_logging()

    init_db()

    if args.collect_only:
        df = collect_prices()
        if not df.empty:
            logger.info("Collected %d rooms from %d hotels", len(df), df["hotel_id"].nunique())
        return

    if args.analyze_only:
        analysis = run_analysis()
        if "error" not in analysis:
            report_path = generate_report(analysis)
            print_summary(analysis)
            logger.info("Report: %s", report_path)
        else:
            logger.error("Analysis error: %s", analysis["error"])
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
