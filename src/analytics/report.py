"""SalesOffice report generator — HTML reports with interactive charts.

Generates a self-contained HTML report with:
  - Portfolio overview dashboard
  - Per-hotel price analysis
  - Per-room price predictions with charts
  - Booking window analysis
  - Price change alerts
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_report(analysis: dict) -> Path:
    """Generate an HTML report from analysis results.

    Returns the path to the generated report.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    report_path = REPORTS_DIR / f"salesoffice_report_{ts}.html"

    stats = analysis.get("statistics", {})
    hotels = analysis.get("hotels", [])
    predictions = analysis.get("predictions", {})
    booking_window = analysis.get("booking_window", {})
    price_changes = analysis.get("price_changes", {})
    model_info = analysis.get("model_info", {})
    flight_demand = analysis.get("flight_demand", {})

    # Build chart data
    hotel_chart_data = _build_hotel_chart_data(hotels)
    prediction_chart_data = _build_prediction_charts(predictions)
    booking_window_chart = _build_booking_window_chart(booking_window)
    category_chart = _build_category_chart(stats)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SalesOffice Price Analysis — {analysis.get('run_ts', '')}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
  .header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid #334155; margin-bottom: 30px; }}
  .header h1 {{ font-size: 2em; color: #38bdf8; }}
  .header p {{ color: #94a3b8; margin-top: 8px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; }}
  .card h3 {{ color: #38bdf8; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
  .card .value {{ font-size: 2.2em; font-weight: 700; color: #f1f5f9; }}
  .card .sub {{ color: #94a3b8; font-size: 0.85em; margin-top: 4px; }}
  .section {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; margin-bottom: 24px; }}
  .section h2 {{ color: #38bdf8; margin-bottom: 16px; font-size: 1.3em; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #334155; color: #cbd5e1; padding: 10px 12px; text-align: left; font-size: 0.85em; text-transform: uppercase; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #334155; }}
  .chart {{ width: 100%; min-height: 400px; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }}
  .tag-up {{ background: #dc262622; color: #f87171; }}
  .tag-down {{ background: #16a34a22; color: #4ade80; }}
  .tag-stable {{ background: #38bdf822; color: #38bdf8; }}
  .alert {{ background: #7c2d1244; border: 1px solid #dc2626; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .alert-title {{ color: #f87171; font-weight: 700; }}
</style>
</head>
<body>

<div class="header">
  <h1>SalesOffice Price Analysis</h1>
  <p>Generated: {analysis.get('run_ts', '')} UTC &middot; {analysis.get('total_snapshots', 0)} snapshot(s) collected</p>
  <p style="margin-top: 4px; font-size: 0.85em; color: #64748b;">Model: {model_info.get('data_source', 'N/A')} &middot; {model_info.get('total_tracks', 0)} historical tracks &middot; Avg change: {model_info.get('overall_avg_total_pct', 0):+.1f}%</p>
</div>

<!-- KPI Cards -->
<div class="grid">
  <div class="card">
    <h3>Total Rooms</h3>
    <div class="value">{stats.get('total_rooms', 0)}</div>
    <div class="sub">{stats.get('total_hotels', 0)} hotels</div>
  </div>
  <div class="card">
    <h3>Avg Price</h3>
    <div class="value">${stats.get('price_mean', 0):,.0f}</div>
    <div class="sub">Median: ${stats.get('price_median', 0):,.0f}</div>
  </div>
  <div class="card">
    <h3>Price Range</h3>
    <div class="value">${stats.get('price_min', 0):,.0f} — ${stats.get('price_max', 0):,.0f}</div>
    <div class="sub">Std: ${stats.get('price_std', 0):,.0f}</div>
  </div>
  <div class="card">
    <h3>Total Inventory</h3>
    <div class="value">${stats.get('total_inventory_value', 0):,.0f}</div>
    <div class="sub">Avg {stats.get('avg_days_to_checkin', 0):.0f} days to check-in</div>
  </div>
</div>

{_build_flight_demand_section(flight_demand)}

<!-- Hotel Price Distribution -->
<div class="section">
  <h2>Price Distribution by Hotel</h2>
  <div id="hotel-chart" class="chart"></div>
</div>

<!-- Hotel Summary Table -->
<div class="section">
  <h2>Hotels Summary</h2>
  <table>
    <tr><th>Hotel</th><th>Rooms</th><th>Min</th><th>Avg</th><th>Max</th><th>Std</th><th>Date Range</th><th>Days to Check-in</th></tr>
    {''.join(_hotel_row(h) for h in hotels)}
  </table>
</div>

<!-- Booking Window Analysis -->
<div class="section">
  <h2>Booking Window Analysis</h2>
  <p style="color: #94a3b8; margin-bottom: 16px;">
    Price-Days Correlation: <strong>{booking_window.get('price_days_correlation', 0)}</strong>
    — {booking_window.get('interpretation', '')}
  </p>
  <div id="booking-window-chart" class="chart"></div>
</div>

<!-- Category & Board Breakdown -->
<div class="section">
  <h2>Price by Category & Board</h2>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
    <div id="category-chart" class="chart"></div>
    <div id="board-chart" class="chart"></div>
  </div>
</div>

<!-- Price Predictions -->
<div class="section">
  <h2>Price Predictions (Sample — Top Hotels)</h2>
  {_build_prediction_section(predictions, hotels)}
</div>

<!-- Price Changes -->
<div class="section">
  <h2>Price Changes</h2>
  {_build_changes_section(price_changes)}
</div>

<script>
const darkLayout = {{
  paper_bgcolor: '#1e293b',
  plot_bgcolor: '#1e293b',
  font: {{ color: '#e2e8f0', family: '-apple-system, sans-serif' }},
  margin: {{ l: 60, r: 30, t: 40, b: 60 }},
  xaxis: {{ gridcolor: '#334155', zerolinecolor: '#475569' }},
  yaxis: {{ gridcolor: '#334155', zerolinecolor: '#475569' }},
}};

// Hotel chart
{hotel_chart_data}

// Booking window chart
{booking_window_chart}

// Category chart
{category_chart}

// Prediction charts
{prediction_chart_data}
</script>

</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    logger.info("Report generated: %s", report_path)

    # Also save as "latest"
    latest_path = REPORTS_DIR / "latest_report.html"
    latest_path.write_text(html, encoding="utf-8")

    return report_path


def _build_flight_demand_section(demand: dict) -> str:
    """Build the flight demand indicator section for the dashboard."""
    indicator = demand.get("indicator", "NO_DATA")

    if indicator == "NO_DATA":
        return """
<div class="section">
  <h2>Flight Demand Indicator</h2>
  <p style="color: #94a3b8;">No flight demand data collected yet. Run Kiwi flight search to populate.</p>
</div>"""

    # Color and icon by indicator
    colors = {"HIGH": "#f87171", "MEDIUM": "#fbbf24", "LOW": "#4ade80"}
    icons = {"HIGH": "&#9650;", "MEDIUM": "&#9644;", "LOW": "&#9660;"}
    color = colors.get(indicator, "#94a3b8")
    icon = icons.get(indicator, "?")

    avg_price = demand.get("avg_flight_price", 0)
    min_price = demand.get("min_flight_price", 0)
    total_flights = demand.get("total_flights", 0)
    origins = demand.get("origins_checked", 0)
    last_collected = demand.get("last_collected", "N/A")

    # Build per-origin table rows
    origin_rows = ""
    for item in demand.get("by_origin", []):
        origin_rows += (
            f"<tr>"
            f"<td>{item['origin']}</td>"
            f"<td>{item['flight_date']}</td>"
            f"<td>{item['num_flights']}</td>"
            f"<td>${item['min_price']:,.0f}</td>"
            f"<td>${item['avg_price']:,.0f}</td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <h2>Flight Demand Indicator <span style="color: {color}; font-size: 0.8em;">{icon} {indicator}</span></h2>
  <div class="grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 16px;">
    <div class="card" style="text-align: center;">
      <h3>Demand Level</h3>
      <div class="value" style="color: {color};">{indicator}</div>
      <div class="sub">Based on flight prices to Miami</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Avg Flight Price</h3>
      <div class="value">${avg_price:,.0f}</div>
      <div class="sub">Cheapest: ${min_price:,.0f}</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Flights Available</h3>
      <div class="value">{total_flights}</div>
      <div class="sub">From {origins} cities</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Last Updated</h3>
      <div class="value" style="font-size: 1em;">{last_collected}</div>
      <div class="sub">Via Kiwi.com</div>
    </div>
  </div>
  <table>
    <tr><th>Origin</th><th>Flight Date</th><th>Flights</th><th>Min Price</th><th>Avg Price</th></tr>
    {origin_rows}
  </table>
</div>"""


def _hotel_row(h: dict) -> str:
    return (
        f"<tr>"
        f"<td><strong>{h['hotel_name']}</strong><br><small>ID: {h['hotel_id']}</small></td>"
        f"<td>{h['total_rooms']}</td>"
        f"<td>${h['price_min']:,.0f}</td>"
        f"<td>${h['price_mean']:,.0f}</td>"
        f"<td>${h['price_max']:,.0f}</td>"
        f"<td>${h['price_std']:,.0f}</td>"
        f"<td>{h['date_range']}</td>"
        f"<td>{h['min_days_to_checkin']}–{h['max_days_to_checkin']} days</td>"
        f"</tr>"
    )


def _build_hotel_chart_data(hotels: list[dict]) -> str:
    if not hotels:
        return "// No hotel data"

    traces = []
    for h in hotels:
        traces.append({
            "type": "bar",
            "name": h["hotel_name"],
            "x": ["Min", "Avg", "Median", "Max"],
            "y": [h["price_min"], h["price_mean"], h["price_median"], h["price_max"]],
        })

    return f"""
Plotly.newPlot('hotel-chart', {json.dumps(traces)}, {{
  ...darkLayout,
  barmode: 'group',
  title: 'Price Distribution by Hotel',
  yaxis: {{ ...darkLayout.yaxis, title: 'Price ($)' }},
}});
"""


def _build_booking_window_chart(bw: dict) -> str:
    windows = bw.get("windows", [])
    if not windows:
        return "// No booking window data"

    return f"""
Plotly.newPlot('booking-window-chart', [{{
  type: 'bar',
  x: {json.dumps([w['window'] for w in windows])},
  y: {json.dumps([w['avg_price'] for w in windows])},
  text: {json.dumps([f"${w['avg_price']:.0f} ({w['rooms']} rooms)" for w in windows])},
  textposition: 'outside',
  marker: {{ color: ['#38bdf8', '#818cf8', '#a78bfa', '#c084fc'] }},
}}], {{
  ...darkLayout,
  title: 'Average Price by Booking Window',
  yaxis: {{ ...darkLayout.yaxis, title: 'Avg Price ($)' }},
}});
"""


def _build_category_chart(stats: dict) -> str:
    by_cat = stats.get("by_category", {})
    by_board = stats.get("by_board", {})

    cat_js = "// No category data"
    if by_cat:
        cat_js = f"""
Plotly.newPlot('category-chart', [{{
  type: 'bar',
  x: {json.dumps(list(by_cat.keys()))},
  y: {json.dumps([v['avg_price'] for v in by_cat.values()])},
  text: {json.dumps([f"{v['count']} rooms" for v in by_cat.values()])},
  textposition: 'outside',
  marker: {{ color: '#38bdf8' }},
}}], {{
  ...darkLayout,
  title: 'Avg Price by Room Category',
  yaxis: {{ ...darkLayout.yaxis, title: 'Price ($)' }},
}});
"""

    board_js = "// No board data"
    if by_board:
        board_js = f"""
Plotly.newPlot('board-chart', [{{
  type: 'bar',
  x: {json.dumps(list(by_board.keys()))},
  y: {json.dumps([v['avg_price'] for v in by_board.values()])},
  text: {json.dumps([f"{v['count']} rooms" for v in by_board.values()])},
  textposition: 'outside',
  marker: {{ color: '#818cf8' }},
}}], {{
  ...darkLayout,
  title: 'Avg Price by Board Type',
  yaxis: {{ ...darkLayout.yaxis, title: 'Price ($)' }},
}});
"""
    return cat_js + "\n" + board_js


def _build_prediction_charts(predictions: dict) -> str:
    """Build Plotly charts for top predictions (one chart per hotel)."""
    if not predictions:
        return "// No predictions"

    # Group predictions by hotel
    by_hotel: dict[int, list] = {}
    for detail_id, pred in predictions.items():
        hid = pred["hotel_id"]
        if hid not in by_hotel:
            by_hotel[hid] = []
        by_hotel[hid].append((detail_id, pred))

    js_parts = []
    for i, (hotel_id, preds) in enumerate(list(by_hotel.items())[:4]):  # top 4 hotels
        div_id = f"pred-chart-{hotel_id}"
        traces = []

        # Show up to 10 rooms per hotel
        for detail_id, pred in preds[:10]:
            daily = pred.get("daily", [])
            if not daily:
                continue
            dates = [d["date"] for d in daily]
            prices = [d["predicted_price"] for d in daily]
            upper = [d["upper_bound"] for d in daily]
            lower = [d["lower_bound"] for d in daily]

            label = f"{pred['category']} {pred['board']} ({pred['date_from'][:10]})"

            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": label,
                "x": dates,
                "y": prices,
            })

        hotel_name = preds[0][1]["hotel_name"] if preds else str(hotel_id)
        js_parts.append(f"""
Plotly.newPlot('{div_id}', {json.dumps(traces)}, {{
  ...darkLayout,
  title: '{hotel_name} — Price Predictions',
  xaxis: {{ ...darkLayout.xaxis, title: 'Date' }},
  yaxis: {{ ...darkLayout.yaxis, title: 'Predicted Price ($)' }},
  showlegend: true,
  legend: {{ font: {{ size: 10 }} }},
}});
""")

    return "\n".join(js_parts)


def _build_prediction_section(predictions: dict, hotels: list) -> str:
    """Build HTML section with prediction charts and summary table."""
    if not predictions:
        return "<p style='color: #94a3b8;'>No predictions available yet.</p>"

    # Group by hotel
    by_hotel: dict[int, list] = {}
    for detail_id, pred in predictions.items():
        hid = pred["hotel_id"]
        if hid not in by_hotel:
            by_hotel[hid] = []
        by_hotel[hid].append(pred)

    html_parts = []
    for hotel_id, preds in list(by_hotel.items())[:4]:
        hotel_name = preds[0]["hotel_name"]
        div_id = f"pred-chart-{hotel_id}"

        # Summary table for this hotel
        rows = ""
        for p in sorted(preds, key=lambda x: x["date_from"])[:15]:
            change_class = "tag-up" if p["expected_change_pct"] > 1 else ("tag-down" if p["expected_change_pct"] < -1 else "tag-stable")
            change_label = f"+{p['expected_change_pct']}%" if p["expected_change_pct"] > 0 else f"{p['expected_change_pct']}%"
            prob = p.get("probability", {})
            prob_html = ""
            if prob:
                prob_html = (
                    f"<small style='color: #94a3b8;'>"
                    f"<span style='color: #f87171;'>&#9650;{prob.get('up', 0):.0f}%</span> "
                    f"<span style='color: #4ade80;'>&#9660;{prob.get('down', 0):.0f}%</span> "
                    f"<span style='color: #38bdf8;'>&#9644;{prob.get('stable', 0):.0f}%</span>"
                    f"</small>"
                )
            rows += (
                f"<tr>"
                f"<td>{p['category']} / {p['board']}</td>"
                f"<td>{p['date_from'][:10]}</td>"
                f"<td>{p['days_to_checkin']}d</td>"
                f"<td>${p['current_price']:,.0f}</td>"
                f"<td>${p['predicted_checkin_price']:,.0f}</td>"
                f"<td><span class='tag {change_class}'>{change_label}</span></td>"
                f"<td>{prob_html}</td>"
                f"</tr>"
            )

        html_parts.append(f"""
        <h3 style="color: #f1f5f9; margin: 20px 0 10px;">{hotel_name} ({len(preds)} rooms)</h3>
        <div id="{div_id}" class="chart"></div>
        <table style="margin-top: 16px;">
          <tr><th>Room</th><th>Check-in</th><th>Days</th><th>Current</th><th>Predicted</th><th>Change</th><th>Probability</th></tr>
          {rows}
        </table>
        """)

    return "\n".join(html_parts)


def _build_changes_section(changes: dict) -> str:
    if not changes or not changes.get("changes"):
        note = changes.get("note", "No price changes detected yet. Collecting more snapshots...")
        return f"<p style='color: #94a3b8;'>{note}</p>"

    html = f"""
    <p style="color: #94a3b8; margin-bottom: 12px;">
      Period: {changes['period']} &middot;
      {changes['total_changes']} changes ({changes['price_increases']} up, {changes['price_decreases']} down)
    </p>
    <table>
      <tr><th>Hotel</th><th>Date</th><th>Old Price</th><th>New Price</th><th>Change</th></tr>
    """
    for c in changes.get("changes", [])[:20]:
        tag = "tag-up" if c["direction"] == "UP" else "tag-down"
        html += (
            f"<tr>"
            f"<td>{c['hotel_name']}</td>"
            f"<td>{c['date_from'][:10]}</td>"
            f"<td>${c['old_price']:,.0f}</td>"
            f"<td>${c['new_price']:,.0f}</td>"
            f"<td><span class='tag {tag}'>{c['change_pct']:+.1f}%</span></td>"
            f"</tr>"
        )
    html += "</table>"
    return html
