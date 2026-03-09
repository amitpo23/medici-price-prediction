"""Generate the Prediction Accuracy Tracker HTML page.

Shows backtest results: predicted vs actual settlement prices,
accuracy metrics per hotel and T-bucket, scatter plots.
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


def generate_accuracy_html(data: dict) -> str:
    """Build the Prediction Accuracy Tracker HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if data.get("error"):
        return render_template("error.html", title="Prediction Accuracy Tracker", error=data["error"], now=now)

    overall = data.get("overall", {})
    hotels = data.get("hotels", {})
    yoy = data.get("yoy_accuracy", {})
    sources = data.get("sources_used", {})

    # KPI calculations
    overall_by_t = overall.get("by_T", {})
    best_t, best_within5 = None, 0
    for t_val, stats in overall_by_t.items():
        w5 = stats.get("within_5", 0)
        if w5 > best_within5:
            best_within5 = w5
            best_t = t_val

    avg_mape = sum(s.get("mape", 0) for s in overall_by_t.values()) / len(overall_by_t) if overall_by_t else 0

    # Build hotel card data
    hotel_cards_data = []
    for hid, hdata in hotels.items():
        acc_by_t = hdata.get("accuracy_by_T", {})
        if not acc_by_t:
            continue
        rows = []
        for t_val in sorted(acc_by_t.keys()):
            s = acc_by_t[t_val]
            rows.append({
                "t_val": t_val,
                "n_observations": s["n_observations"],
                "mape": s["mape"],
                "mape_cls": "green" if s["mape"] < 5 else ("yellow" if s["mape"] < 10 else "red"),
                "direction_accuracy_pct": s["direction_accuracy_pct"],
                "dir_cls": "green" if s["direction_accuracy_pct"] > 60 else ("yellow" if s["direction_accuracy_pct"] > 45 else "red"),
                "within_5pct": s["within_5pct"],
                "within_10pct": s["within_10pct"],
                "mean_actual_change_pct": s["mean_actual_change_pct"],
                "price_went_down_pct": s["price_went_down_pct"],
                "price_went_up_pct": s["price_went_up_pct"],
            })
        hotel_cards_data.append({"name": hdata.get("hotel_name", f"Hotel {hid}"), "rows": rows})

    # YoY data
    yoy_rows_data = [{"year": y, **yoy[y]} for y in sorted(yoy.keys())]

    # Chart data
    t_bar_labels, t_bar_mape, t_bar_within5 = [], [], []
    for t_val in sorted(overall_by_t.keys()):
        s = overall_by_t[t_val]
        t_bar_labels.append(f"T-{t_val}")
        t_bar_mape.append(s.get("mape", 0))
        t_bar_within5.append(s.get("within_5", 0))

    return render_template(
        "accuracy.html",
        active_page="accuracy",
        now=now,
        total_contracts=data.get("total_contracts", 0),
        total_obs=data.get("total_observations", 0),
        avg_mape=avg_mape,
        best_within5=best_within5,
        best_t=best_t,
        hotel_cards_data=hotel_cards_data,
        yoy_rows_data=yoy_rows_data,
        scatter_data_json=json.dumps(overall.get("scatter", []), default=str),
        t_bar_labels_json=json.dumps(t_bar_labels),
        t_bar_mape_json=json.dumps(t_bar_mape),
        t_bar_within5_json=json.dumps(t_bar_within5),
        sources_text=", ".join(f"{k}: {v:,}" for k, v in sources.items()),
    )
