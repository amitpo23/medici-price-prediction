"""Export engine — CSV downloads and summary report generation.

Provides:
- CSV export of key datasets (contracts, prices, provider data)
- Weekly summary digest (plain text / JSON)
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)

HOTEL_IDS = [66814, 854881, 20702, 24982]
HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def export_contracts_csv(hotel_ids: list[int] | None = None) -> str:
    """Export contract price history as CSV string."""
    from src.data.yoy_db import load_unified_yoy_data

    hids = hotel_ids or HOTEL_IDS
    raw = load_unified_yoy_data(hids)
    if raw.empty:
        return "No data available"

    raw = raw[raw["price"].notna() & (raw["price"] > 0)].copy()

    # Select and format columns
    cols = ["hotel_id", "checkin_date", "category", "board", "scan_date", "T_days", "price", "source"]
    available = [c for c in cols if c in raw.columns]
    export_df = raw[available].copy()

    # Add hotel name
    export_df["hotel_name"] = export_df["hotel_id"].map(HOTEL_NAMES)

    # Sort for readability
    export_df = export_df.sort_values(["hotel_id", "checkin_date", "scan_date"])

    # Format dates
    for col in ["checkin_date", "scan_date"]:
        if col in export_df.columns:
            export_df[col] = pd.to_datetime(export_df[col]).dt.strftime("%Y-%m-%d")

    buf = io.StringIO()
    export_df.to_csv(buf, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return buf.getvalue()


def export_providers_csv(hotel_ids: list[int] | None = None, days_back: int = 90) -> str:
    """Export provider pricing data as CSV string."""
    from src.data.trading_db import load_search_results

    hids = hotel_ids or HOTEL_IDS
    raw = load_search_results(hotel_ids=hids, days_back=days_back)
    if raw.empty:
        return "No data available"

    cols = [
        "HotelId", "DateInsert", "PriceAmount", "PriceAmountCurrency",
        "NetPriceAmount", "Providers", "RoomName", "RoomCategory",
        "RoomBoard", "CancellationType",
    ]
    available = [c for c in cols if c in raw.columns]
    export_df = raw[available].copy()

    # Add hotel name
    export_df["HotelName"] = export_df["HotelId"].map(HOTEL_NAMES)

    export_df = export_df.sort_values(["HotelId", "DateInsert"])

    for col in ["DateInsert"]:
        if col in export_df.columns:
            export_df[col] = pd.to_datetime(export_df[col]).dt.strftime("%Y-%m-%d %H:%M")

    buf = io.StringIO()
    export_df.to_csv(buf, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return buf.getvalue()


def generate_weekly_summary() -> dict:
    """Generate weekly summary digest with key metrics."""
    now = datetime.now(timezone.utc)
    summary = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "period": "Last 7 days",
        "hotels": {},
        "alerts": [],
    }

    try:
        from src.data.yoy_db import load_unified_yoy_data
        raw = load_unified_yoy_data(HOTEL_IDS)
        if raw.empty:
            summary["error"] = "No data available"
            return summary

        raw = raw[raw["price"].notna() & (raw["price"] > 0)].copy()

        # Last 7 days of scans
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
        recent = raw[raw["scan_date"] >= cutoff]

        for hid in HOTEL_IDS:
            sub = recent[recent["hotel_id"] == hid]
            if sub.empty:
                continue

            hotel_summary = {
                "hotel_name": HOTEL_NAMES.get(hid, f"Hotel {hid}"),
                "scans_7d": len(sub),
                "avg_price": round(float(sub["price"].mean()), 2),
                "min_price": round(float(sub["price"].min()), 2),
                "max_price": round(float(sub["price"].max()), 2),
                "unique_contracts": sub.groupby(["checkin_date", "category", "board"]).ngroups,
            }

            # Price trend
            if len(sub) > 1:
                first_avg = sub.nsmallest(len(sub) // 2, "scan_date")["price"].mean()
                last_avg = sub.nlargest(len(sub) // 2, "scan_date")["price"].mean()
                trend_pct = (last_avg - first_avg) / first_avg * 100
                hotel_summary["trend_pct"] = round(float(trend_pct), 2)
                hotel_summary["trend"] = "up" if trend_pct > 1 else ("down" if trend_pct < -1 else "stable")

                # Generate alerts
                if trend_pct < -5:
                    summary["alerts"].append({
                        "type": "price_drop",
                        "hotel": HOTEL_NAMES.get(hid),
                        "message": f"Prices dropped {abs(trend_pct):.1f}% this week",
                        "severity": "warning",
                    })
                if trend_pct < -10:
                    summary["alerts"].append({
                        "type": "price_crash",
                        "hotel": HOTEL_NAMES.get(hid),
                        "message": f"Prices crashed {abs(trend_pct):.1f}% — immediate attention needed",
                        "severity": "critical",
                    })

            summary["hotels"][int(hid)] = hotel_summary

    except Exception as e:
        logger.error("Weekly summary generation failed: %s", e, exc_info=True)
        summary["error"] = str(e)

    return summary


def generate_summary_text(summary: dict) -> str:
    """Convert weekly summary dict to plain text email format."""
    lines = [
        "=" * 60,
        "MEDICI PRICE PREDICTION — WEEKLY SUMMARY",
        f"Generated: {summary.get('generated_at', 'N/A')}",
        f"Period: {summary.get('period', 'N/A')}",
        "=" * 60,
        "",
    ]

    # Alerts first
    alerts = summary.get("alerts", [])
    if alerts:
        lines.append("!! ALERTS !!")
        lines.append("-" * 40)
        for a in alerts:
            severity = a.get("severity", "info").upper()
            lines.append(f"  [{severity}] {a.get('hotel', 'Unknown')}: {a.get('message', '')}")
        lines.append("")

    # Hotel summaries
    lines.append("HOTEL PERFORMANCE")
    lines.append("-" * 40)
    for hid, data in summary.get("hotels", {}).items():
        name = data.get("hotel_name", f"Hotel {hid}")
        lines.append(f"\n  {name}")
        lines.append(f"    Scans (7d):     {data.get('scans_7d', 0)}")
        lines.append(f"    Avg Price:      ${data.get('avg_price', 0):.2f}")
        lines.append(f"    Price Range:    ${data.get('min_price', 0):.2f} - ${data.get('max_price', 0):.2f}")
        lines.append(f"    Contracts:      {data.get('unique_contracts', 0)}")
        trend = data.get("trend_pct")
        if trend is not None:
            arrow = "^" if trend > 0 else ("v" if trend < 0 else "=")
            lines.append(f"    Trend:          {arrow} {trend:+.1f}%")

    lines.append("")
    lines.append("=" * 60)
    lines.append("Medici Price Prediction | medici-prediction-api.azurewebsites.net")

    return "\n".join(lines)
