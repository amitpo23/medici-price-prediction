"""Generate the Provider Price Comparison HTML page.

Visualizes SearchResultsSessionPollLog data: provider rankings,
margin analysis, market share, and per-hotel best providers.
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


def generate_provider_html(data: dict) -> str:
    """Build the Provider Comparison HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if data.get("error"):
        return render_template("error.html", title="Provider Price Comparison", error=data["error"], now=now)

    rankings = data.get("provider_rankings", [])
    hotel_comparisons = data.get("hotel_comparisons", {})
    top_providers = rankings[:15]

    # Ranking rows data
    ranking_rows_data = []
    for p in top_providers:
        avg_price = p.get("avg_net_price") or p.get("avg_gross_price", 0)
        margin_str = f"{p['avg_margin_pct']:.1f}%" if p.get("avg_margin_pct") is not None else "N/A"
        ranking_rows_data.append({**p, "avg_price": avg_price, "margin_str": margin_str})

    # Chart data
    pie_labels = [p["provider_name"] for p in rankings[:10]]
    pie_values = [p["market_share_pct"] for p in rankings[:10]]
    other_share = 100 - sum(pie_values)
    if other_share > 0:
        pie_labels.append("Others")
        pie_values.append(round(other_share, 1))

    bar_labels = [p["provider_name"][:20] for p in top_providers[:10]]
    bar_gross = [p["avg_gross_price"] for p in top_providers[:10]]
    bar_net = [p.get("avg_net_price") or 0 for p in top_providers[:10]]

    # Per-hotel sections
    hotel_sections_data = []
    for hid, hdata in hotel_comparisons.items():
        providers = hdata.get("providers", [])[:10]
        if not providers:
            continue
        prov_list = []
        for p in providers:
            prov_list.append({**p, "avg_price": p.get("avg_net_price") or p.get("avg_gross_price", 0)})
        hotel_sections_data.append({
            "name": hdata.get("hotel_name", f"Hotel {hid}"),
            "total_results": hdata.get("total_results", 0),
            "providers": prov_list,
        })

    return render_template(
        "provider.html",
        active_page="providers",
        now=now,
        total_records=data.get("total_records", 0),
        unique_providers=data.get("unique_providers", 0),
        date_range=data.get("date_range", {}),
        source=data.get("source", ""),
        best_providers=data.get("best_providers", {}),
        ranking_rows_data=ranking_rows_data,
        hotel_sections_data=hotel_sections_data,
        pie_labels_json=json.dumps(pie_labels, default=str),
        pie_values_json=json.dumps(pie_values, default=str),
        bar_labels_json=json.dumps(bar_labels, default=str),
        bar_net_json=json.dumps(bar_net, default=str),
        bar_gross_json=json.dumps(bar_gross, default=str),
    )
