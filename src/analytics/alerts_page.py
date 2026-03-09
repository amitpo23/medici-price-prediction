"""Generate the Price Alert System HTML page.

Shows real-time alerts when contracts breach -5%/-10% thresholds.
Uses cached chart data (Tab 3 breach stats) plus live contract data.
"""
from __future__ import annotations

import json
from datetime import datetime

from src.utils.template_engine import render_template


HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_alerts_html(charts_data: dict) -> str:
    """Build the Price Alert System HTML page from cached chart data."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    tab3 = charts_data.get("tab3", {})

    # Collect alerts from Tab 3 breach data
    alerts = []
    hotel_summaries = {}

    for hid_str, breach_data in tab3.items():
        hid = int(hid_str)
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        breach_rates = breach_data.get("breach_rates", {})
        by_year = breach_rates.get("by_year", {})
        by_month = breach_rates.get("by_month", {})

        latest_year = max(by_year.keys()) if by_year else None
        if latest_year:
            stats = by_year[latest_year]
            pct_5 = stats.get("pct_5", 0)
            pct_10 = stats.get("pct_10", 0)
            n = stats.get("n", 0)

            severity = "normal"
            if pct_10 > 30:
                severity = "critical"
            elif pct_5 > 50:
                severity = "warning"
            elif pct_5 > 20:
                severity = "caution"

            hotel_summaries[hid] = {
                "hotel_name": hotel_name, "year": latest_year,
                "breach_5_pct": pct_5, "breach_10_pct": pct_10,
                "n_contracts": n, "severity": severity,
            }

            if pct_10 > 20:
                alerts.append({"type": "critical", "hotel": hotel_name,
                               "message": f"{pct_10:.0f}% of contracts breached -10% in {latest_year}"})
            if pct_5 > 40:
                alerts.append({"type": "warning", "hotel": hotel_name,
                               "message": f"{pct_5:.0f}% of contracts breached -5% in {latest_year}"})

        if by_month:
            for month in sorted(by_month.keys(), reverse=True)[:3]:
                mstats = by_month[month]
                if mstats.get("pct_10", 0) > 40:
                    alerts.append({"type": "critical", "hotel": hotel_name,
                                   "message": f"{mstats['pct_10']:.0f}% breached -10% in {month}"})

        threshold = breach_data.get("threshold_counts", {})
        by_year_th = threshold.get("by_year", {})
        if latest_year and latest_year in by_year_th:
            th = by_year_th[latest_year]
            if th.get("events_10", 0) > 10:
                alerts.append({"type": "info", "hotel": hotel_name,
                               "message": f"{th['events_10']} crossing events below -10% in {latest_year}"})

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a["type"], 99))

    # Monthly trend chart data
    monthly_labels: list[str] = []
    monthly_5: dict[str, dict] = {}
    for hid_str, breach_data in tab3.items():
        hid = int(hid_str)
        by_month = breach_data.get("breach_rates", {}).get("by_month", {})
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        monthly_5[hotel_name] = {}
        for month, mstats in sorted(by_month.items()):
            if month not in monthly_labels:
                monthly_labels.append(month)
            monthly_5[hotel_name][month] = mstats.get("pct_5", 0)
    monthly_labels.sort()

    colors = ["#6366f1", "#22c55e", "#eab308", "#ef4444"]
    chart_datasets_5 = []
    for i, (hotel_name, data) in enumerate(monthly_5.items()):
        chart_datasets_5.append({
            "label": hotel_name,
            "data": [data.get(m, 0) for m in monthly_labels],
            "borderColor": colors[i % len(colors)],
            "tension": 0.3, "fill": False,
        })

    return render_template(
        "alerts.html",
        active_page="alerts",
        now=now,
        alerts=alerts,
        n_alerts=len(alerts),
        n_critical=sum(1 for a in alerts if a["type"] == "critical"),
        n_hotels=len(hotel_summaries),
        hotel_summaries_list=list(hotel_summaries.values()),
        monthly_labels_json=json.dumps(monthly_labels),
        chart_datasets_json=json.dumps(chart_datasets_5),
    )
