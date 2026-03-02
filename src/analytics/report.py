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
    events_data = analysis.get("events", {})
    knowledge_data = analysis.get("knowledge", {})
    benchmarks_data = analysis.get("benchmarks", {})

    # Build chart data
    hotel_chart_data = _build_hotel_chart_data(hotels)
    prediction_chart_data = _build_prediction_charts(predictions)
    booking_window_chart = _build_booking_window_chart(booking_window)
    category_chart = _build_category_chart(stats)
    seasonality_chart = _build_seasonality_chart(benchmarks_data)

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
  <p style="margin-top: 4px; font-size: 0.85em; color: #64748b;">Model: {model_info.get('data_source', 'N/A')} &middot; {model_info.get('total_tracks', 0)} tracks / {model_info.get('total_observations', 0)} T-observations &middot; Mean daily: {model_info.get('global_mean_daily_pct', 0):+.4f}%/day</p>
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

{_build_trading_signals_section(predictions, model_info)}

{_build_flight_demand_section(flight_demand)}

{_build_events_section(events_data)}

{_build_data_sources_section()}

{_build_knowledge_section(knowledge_data)}

{_build_benchmarks_section(benchmarks_data)}

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

<!-- Forward Curve Predictions -->
<div class="section">
  <h2>Forward Curve Predictions</h2>
  <p style="color: #94a3b8; margin-bottom: 16px;">Algo-trading style: decay curve walked day-by-day with momentum + enrichments. Non-linear paths with per-T confidence intervals.</p>
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

// Seasonality chart
{seasonality_chart}

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


def _build_trading_signals_section(predictions: dict, model_info: dict) -> str:
    """Build the trading signals dashboard section — momentum, regime, curve quality."""
    if not predictions:
        return ""

    # Collect all momentum signals and regimes
    signals = []
    regime_alerts = []
    for detail_id, pred in predictions.items():
        mom = pred.get("momentum", {})
        regime = pred.get("regime", {})
        signal = mom.get("signal", "NORMAL")
        strength = mom.get("strength", 0)
        alert = regime.get("alert_level", "none")

        if signal not in ("NORMAL", "INSUFFICIENT_DATA"):
            signals.append({
                "hotel": pred["hotel_name"],
                "room": f"{pred['category']} / {pred['board']}",
                "checkin": pred["date_from"][:10],
                "t": pred["days_to_checkin"],
                "signal": signal,
                "strength": strength,
                "velocity_24h": mom.get("velocity_24h", 0),
            })

        if alert != "none":
            regime_alerts.append({
                "hotel": pred["hotel_name"],
                "room": f"{pred['category']} / {pred['board']}",
                "checkin": pred["date_from"][:10],
                "regime": regime.get("regime", ""),
                "z_score": regime.get("z_score", 0),
                "divergence": regime.get("divergence_pct", 0),
                "alert": alert,
                "desc": regime.get("description", ""),
            })

    # Count by signal type
    total_rooms = len(predictions)
    active_signals = len(signals)
    active_alerts = len(regime_alerts)

    # Curve quality from model_info
    curve_snapshot = model_info.get("curve_snapshot", [])
    cat_offsets = model_info.get("category_offsets", {})

    # Signal rows
    signal_rows = ""
    sig_colors = {
        "ACCELERATING_UP": "#f87171", "ACCELERATING_DOWN": "#4ade80",
        "ACCELERATING": "#fbbf24", "DECELERATING": "#818cf8",
    }
    for s in sorted(signals, key=lambda x: -x["strength"])[:10]:
        sc = sig_colors.get(s["signal"], "#94a3b8")
        signal_rows += (
            f"<tr>"
            f"<td>{s['hotel']}</td>"
            f"<td>{s['room']}</td>"
            f"<td>T-{s['t']}</td>"
            f"<td><span class='tag' style='background: {sc}22; color: {sc};'>{s['signal'].replace('_', ' ')}</span></td>"
            f"<td>{s['strength']:.0%}</td>"
            f"<td>{s['velocity_24h']:+.3f}%/day</td>"
            f"</tr>"
        )

    # Regime alert rows
    alert_rows = ""
    alert_colors = {"watch": "#fbbf24", "warning": "#f87171"}
    for a in sorted(regime_alerts, key=lambda x: abs(x["z_score"]), reverse=True)[:10]:
        ac = alert_colors.get(a["alert"], "#94a3b8")
        alert_rows += (
            f"<tr>"
            f"<td>{a['hotel']}</td>"
            f"<td>{a['room']}</td>"
            f"<td><span class='tag' style='background: {ac}22; color: {ac};'>{a['regime'].replace('_', ' ')}</span></td>"
            f"<td>{a['z_score']:+.1f} sigma</td>"
            f"<td>{a['divergence']:+.1f}%</td>"
            f"<td><small>{a['desc']}</small></td>"
            f"</tr>"
        )

    # Decay curve snapshot table
    curve_rows = ""
    for cp in curve_snapshot:
        d = cp.get("density", "")
        d_color = "#4ade80" if d == "high" else ("#fbbf24" if d == "medium" else "#f87171")
        curve_rows += (
            f"<tr>"
            f"<td>T-{cp['t']}</td>"
            f"<td>{cp['expected_daily_pct']:+.4f}%</td>"
            f"<td>{cp['volatility']:.4f}%</td>"
            f"<td><span style='color: {d_color};'>{d}</span></td>"
            f"</tr>"
        )

    # Category offsets
    offset_pills = " ".join(
        f"<span class='tag' style='background: #334155; color: #cbd5e1;'>{cat}: {off:+.4f}%/d</span>"
        for cat, off in cat_offsets.items()
    )

    return f"""
<div class="section">
  <h2>Trading Signals <span style="color: #fbbf24; font-size: 0.7em;">{active_signals} active signals, {active_alerts} regime alerts</span></h2>
  <div class="grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 16px;">
    <div class="card" style="text-align: center;">
      <h3>Rooms Tracked</h3>
      <div class="value">{total_rooms}</div>
      <div class="sub">Forward curve predictions</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Active Signals</h3>
      <div class="value" style="color: #fbbf24;">{active_signals}</div>
      <div class="sub">Momentum divergences</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Regime Alerts</h3>
      <div class="value" style="color: {'#f87171' if active_alerts > 0 else '#4ade80'};">{active_alerts}</div>
      <div class="sub">Rooms off expected path</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Model</h3>
      <div class="value" style="font-size: 1em;">Forward Curve</div>
      <div class="sub">{model_info.get('total_tracks', 0)} tracks, {model_info.get('total_observations', 0)} obs</div>
    </div>
  </div>

  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
    <div>
      <h3 style="color: #f1f5f9; margin-bottom: 8px;">Momentum Signals</h3>
      {f'<table><tr><th>Hotel</th><th>Room</th><th>T</th><th>Signal</th><th>Strength</th><th>Velocity</th></tr>{signal_rows}</table>' if signal_rows else '<p style="color: #64748b;">All rooms tracking normally -- no divergent momentum detected.</p>'}
    </div>
    <div>
      <h3 style="color: #f1f5f9; margin-bottom: 8px;">Regime Alerts</h3>
      {f'<table><tr><th>Hotel</th><th>Room</th><th>Regime</th><th>Z-Score</th><th>Divergence</th><th>Details</th></tr>{alert_rows}</table>' if alert_rows else '<p style="color: #64748b;">All rooms in NORMAL regime -- no anomalies detected.</p>'}
    </div>
  </div>

  <h3 style="color: #f1f5f9; margin: 16px 0 8px;">Decay Curve Term Structure</h3>
  <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
    <table>
      <tr><th>T (days to check-in)</th><th>Expected Daily Change</th><th>Daily Volatility</th><th>Data Density</th></tr>
      {curve_rows}
    </table>
    <div>
      <h3 style="color: #f1f5f9; margin-bottom: 8px;">Category Offsets</h3>
      <div style="line-height: 2;">{offset_pills if offset_pills else '<span style="color: #64748b;">No category offsets computed</span>'}</div>
    </div>
  </div>
</div>"""


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


def _build_events_section(events: dict) -> str:
    """Build the events and conferences section for the dashboard."""
    total = events.get("total_events", 0)
    upcoming = events.get("upcoming_events", 0)
    next_events = events.get("next_events", [])

    if total == 0:
        return """
<div class="section">
  <h2>Events & Conferences</h2>
  <p style="color: #94a3b8;">No events data loaded yet.</p>
</div>"""

    # Impact colors
    impact_colors = {
        "extreme": "#f87171",
        "very_high": "#fb923c",
        "high": "#fbbf24",
        "moderate": "#38bdf8",
        "low": "#94a3b8",
    }

    rows = ""
    for ev in next_events:
        impact = ev.get("hotel_impact", "low")
        color = impact_colors.get(impact, "#94a3b8")
        attendance = ev.get("expected_attendance", 0)
        rows += (
            f"<tr>"
            f"<td><strong>{ev['name']}</strong></td>"
            f"<td>{ev['start_date']} → {ev['end_date']}</td>"
            f"<td>{ev.get('category', '')}</td>"
            f"<td>{attendance:,}</td>"
            f"<td><span class='tag' style='background: {color}22; color: {color};'>{impact.upper()}</span></td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <h2>Events & Conferences <span style="color: #fbbf24; font-size: 0.7em;">{upcoming} upcoming</span></h2>
  <div class="grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 16px;">
    <div class="card" style="text-align: center;">
      <h3>Total Events</h3>
      <div class="value">{total}</div>
      <div class="sub">In Miami area</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Upcoming</h3>
      <div class="value" style="color: #fbbf24;">{upcoming}</div>
      <div class="sub">Events ahead</div>
    </div>
  </div>
  <table>
    <tr><th>Event</th><th>Dates</th><th>Category</th><th>Est. Attendance</th><th>Hotel Impact</th></tr>
    {rows}
  </table>
</div>"""


def _build_data_sources_section() -> str:
    """Build the data sources overview section."""
    try:
        from src.analytics.data_sources import DATA_SOURCES
    except ImportError:
        return ""

    active = [s for s in DATA_SOURCES if s["status"] == "active"]
    planned = [s for s in DATA_SOURCES if s["status"] == "planned"]

    rows = ""
    for s in DATA_SOURCES:
        status_color = "#4ade80" if s["status"] == "active" else "#94a3b8"
        status_icon = "&#9679;" if s["status"] == "active" else "&#9675;"
        rows += (
            f"<tr>"
            f"<td><span style='color: {status_color};'>{status_icon}</span> {s['name']}</td>"
            f"<td>{s['category']}</td>"
            f"<td>{s['access']}</td>"
            f"<td>{s['cost']}</td>"
            f"<td><small>{s['metrics']}</small></td>"
            f"<td>{s['update_freq']}</td>"
            f"</tr>"
        )

    return f"""
<div class="section">
  <h2>Data Sources <span style="color: #4ade80; font-size: 0.7em;">{len(active)} active</span> <span style="color: #94a3b8; font-size: 0.7em;">{len(planned)} planned</span></h2>
  <table>
    <tr><th>Source</th><th>Category</th><th>Access</th><th>Cost</th><th>Metrics</th><th>Frequency</th></tr>
    {rows}
  </table>
</div>"""


def _build_knowledge_section(knowledge: dict) -> str:
    """Build the hotel knowledge base / competitive landscape section."""
    if not knowledge or knowledge.get("market", {}).get("status") == "no_data":
        return """
<div class="section">
  <h2>Market Intelligence</h2>
  <p style="color: #94a3b8;">Hotel knowledge base not loaded. Add data/miami_hotels_tbo.csv to enable.</p>
</div>"""

    market = knowledge.get("market", {})
    our_hotels = knowledge.get("our_hotels", [])
    total_hotels = market.get("total_hotels", 0)
    ratings = market.get("rating_distribution", {})
    sub_markets = market.get("sub_markets", {})

    # Rating breakdown row
    rating_html = " &middot; ".join(
        f"<span style='color: #38bdf8;'>{k}</span>: {v}"
        for k, v in sorted(ratings.items(), key=lambda x: -x[1])
    )

    # Sub-market pills
    sub_html = " ".join(
        f"<span class='tag' style='background: #334155; color: #cbd5e1; margin: 2px;'>{k}: {v}</span>"
        for k, v in sorted(sub_markets.items(), key=lambda x: -x[1])
    )

    # Per-hotel competitive cards
    hotel_cards = ""
    for profile in our_hotels:
        name = profile.get("name", "Unknown")
        sub = profile.get("sub_market", "")
        nearby = profile.get("nearby_hotels", 0)
        rating_mix = profile.get("nearby_rating_mix", {})
        closest = profile.get("closest_competitors", [])

        amenities = profile.get("facilities", {}).get("amenities", {})
        amenity_tags = " ".join(
            f"<span class='tag' style='background: #16a34a22; color: #4ade80; margin: 1px;'>{a.replace('_', ' ')}</span>"
            for a in list(amenities.keys())[:10]
        )

        comp_rows = ""
        for c in closest[:5]:
            comp_rows += (
                f"<tr>"
                f"<td>{c['name'][:40]}</td>"
                f"<td>{c['rating']}</td>"
                f"<td>{c['distance_km']:.1f} km</td>"
                f"</tr>"
            )

        mix_html = ", ".join(f"{k}: {v}" for k, v in sorted(rating_mix.items(), key=lambda x: -x[1])[:4])

        hotel_cards += f"""
        <div style="background: #0f172a; border: 1px solid #475569; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
          <h3 style="color: #f1f5f9; margin-bottom: 8px;">{name} <span style="color: #94a3b8; font-size: 0.7em;">({sub})</span></h3>
          <p style="color: #94a3b8; font-size: 0.85em; margin-bottom: 8px;">
            <strong>{nearby}</strong> competitors within 2km &middot; {mix_html}
          </p>
          <div style="margin-bottom: 8px;">{amenity_tags}</div>
          {"<table><tr><th>Closest Competitor</th><th>Rating</th><th>Distance</th></tr>" + comp_rows + "</table>" if comp_rows else ""}
        </div>
        """

    return f"""
<div class="section">
  <h2>Market Intelligence <span style="color: #4ade80; font-size: 0.7em;">{total_hotels} hotels in Miami metro</span></h2>
  <div class="grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 16px;">
    <div class="card">
      <h3>Rating Distribution</h3>
      <div style="font-size: 0.9em; color: #cbd5e1; line-height: 1.8;">{rating_html}</div>
    </div>
    <div class="card">
      <h3>Sub-Markets</h3>
      <div style="line-height: 2;">{sub_html}</div>
    </div>
  </div>
  <h3 style="color: #f1f5f9; margin-bottom: 12px;">Our Hotels — Competitive Position</h3>
  {hotel_cards}
  <p style="color: #64748b; font-size: 0.8em; margin-top: 8px;">Source: TBO Hotels Dataset (Kaggle) — {total_hotels} unique hotels in Miami metro area</p>
</div>"""


def _build_benchmarks_section(benchmarks: dict) -> str:
    """Build the booking benchmarks section with seasonality chart."""
    if not benchmarks or benchmarks.get("status") == "no_data":
        return """
<div class="section">
  <h2>Booking Benchmarks</h2>
  <p style="color: #94a3b8;">Benchmarks data not loaded. Add data/booking_benchmarks.json to enable.</p>
</div>"""

    seasonality = benchmarks.get("seasonality", {})
    city = benchmarks.get("city_hotel", {})
    lead_time = benchmarks.get("lead_time_buckets", {})
    total = benchmarks.get("total_bookings", 0)
    weekend_prem = benchmarks.get("weekend_premium_pct", 0)

    # Lead time table
    lt_rows = ""
    for bucket, data in lead_time.items():
        cancel_pct = data.get("cancel_rate", 0) * 100
        bar_color = "#f87171" if cancel_pct > 40 else ("#fbbf24" if cancel_pct > 25 else "#4ade80")
        lt_rows += (
            f"<tr>"
            f"<td>{bucket}</td>"
            f"<td>${data.get('avg_adr', 0):,.0f}</td>"
            f"<td><span style='color: {bar_color};'>{cancel_pct:.1f}%</span></td>"
            f"<td>{data.get('bookings', 0):,}</td>"
            f"</tr>"
        )

    # Market segments
    segments = benchmarks.get("market_segments", {})
    seg_rows = ""
    for seg in sorted(segments, key=lambda s: segments[s].get("avg_adr", 0), reverse=True):
        data = segments[seg]
        if data.get("avg_adr", 0) > 0:
            seg_rows += (
                f"<tr>"
                f"<td>{seg}</td>"
                f"<td>${data.get('avg_adr', 0):,.0f}</td>"
                f"<td>{data.get('cancel_rate', 0)*100:.0f}%</td>"
                f"</tr>"
            )

    return f"""
<div class="section">
  <h2>Booking Benchmarks <span style="color: #94a3b8; font-size: 0.7em;">from {total:,} bookings</span></h2>
  <div class="grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 16px;">
    <div class="card" style="text-align: center;">
      <h3>City Hotel ADR</h3>
      <div class="value">${city.get('avg_adr', 0):,.0f}</div>
      <div class="sub">Median: ${city.get('median_adr', 0):,.0f}</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Cancel Rate</h3>
      <div class="value" style="color: #fbbf24;">{city.get('cancel_rate', 0)*100:.0f}%</div>
      <div class="sub">City Hotels</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Avg Lead Time</h3>
      <div class="value">{city.get('avg_lead_time_days', 0):.0f}d</div>
      <div class="sub">Booking to check-in</div>
    </div>
    <div class="card" style="text-align: center;">
      <h3>Weekend Premium</h3>
      <div class="value">+{weekend_prem:.1f}%</div>
      <div class="sub">vs. weekday-only stays</div>
    </div>
  </div>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
    <div id="seasonality-chart" class="chart" style="min-height: 300px;"></div>
    <div>
      <h3 style="color: #f1f5f9; margin-bottom: 8px;">Lead Time vs Cancellation Risk</h3>
      <table>
        <tr><th>Lead Time</th><th>Avg ADR</th><th>Cancel Rate</th><th>Bookings</th></tr>
        {lt_rows}
      </table>
      <h3 style="color: #f1f5f9; margin: 16px 0 8px;">Market Segments</h3>
      <table>
        <tr><th>Segment</th><th>Avg ADR</th><th>Cancel</th></tr>
        {seg_rows}
      </table>
    </div>
  </div>
  <p style="color: #64748b; font-size: 0.8em; margin-top: 8px;">Source: hotel-booking-dataset (GitHub mpolinowski) &mdash; {total:,} bookings, 2015-2017</p>
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


def _build_seasonality_chart(benchmarks: dict) -> str:
    """Build Plotly seasonality chart from booking benchmarks."""
    if not benchmarks or benchmarks.get("status") == "no_data":
        return "// No seasonality data"

    seasonality = benchmarks.get("seasonality_index", {})
    if not seasonality:
        return "// No seasonality data"

    months = list(seasonality.keys())
    values = list(seasonality.values())
    # Miami range: 0.845 (Sep trough) to 1.099 (Feb/Dec peak)
    # Red = peak (>= 1.05), Green = trough (<= 0.90), Blue = mid-range
    colors = ["#f87171" if v >= 1.05 else ("#4ade80" if v <= 0.90 else "#38bdf8") for v in values]

    return f"""
Plotly.newPlot('seasonality-chart', [{{
  type: 'bar',
  x: {json.dumps(months)},
  y: {json.dumps(values)},
  text: {json.dumps([f"{v:.2f}x" for v in values])},
  textposition: 'outside',
  marker: {{ color: {json.dumps(colors)} }},
}}], {{
  ...darkLayout,
  title: 'ADR Seasonality Index — Miami (1.0 = annual avg, peak=Feb/Dec, trough=Sep)',
  yaxis: {{ ...darkLayout.yaxis, title: 'Index', range: [0.6, 1.3] }},
  shapes: [{{ type: 'line', x0: -0.5, x1: 11.5, y0: 1.0, y1: 1.0, line: {{ color: '#94a3b8', dash: 'dash' }} }}],
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
    """Build Plotly forward curve charts with confidence bands (one per hotel)."""
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
    for i, (hotel_id, preds) in enumerate(list(by_hotel.items())[:4]):
        div_id = f"pred-chart-{hotel_id}"
        traces = []

        # Show up to 6 rooms per hotel (with confidence bands)
        for detail_id, pred in preds[:6]:
            daily = pred.get("daily", [])
            if not daily:
                continue
            dates = [d["date"] for d in daily]
            prices = [d["predicted_price"] for d in daily]
            upper = [d["upper_bound"] for d in daily]
            lower = [d["lower_bound"] for d in daily]

            label = f"{pred['category']} {pred['board']} ({pred['date_from'][:10]})"
            mom = pred.get("momentum", {})
            signal = mom.get("signal", "")
            signal_tag = f" [{signal}]" if signal and signal != "NORMAL" and signal != "INSUFFICIENT_DATA" else ""

            # Confidence band (filled area)
            traces.append({
                "type": "scatter",
                "x": dates + dates[::-1],
                "y": upper + lower[::-1],
                "fill": "toself",
                "fillcolor": "rgba(56, 189, 248, 0.08)",
                "line": {"color": "transparent"},
                "showlegend": False,
                "hoverinfo": "skip",
            })

            # Main prediction line
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": label + signal_tag,
                "x": dates,
                "y": prices,
                "line": {"width": 2},
            })

            # Starting price marker
            traces.append({
                "type": "scatter",
                "mode": "markers",
                "x": [dates[0]],
                "y": [pred["current_price"]],
                "marker": {"size": 8, "symbol": "diamond"},
                "showlegend": False,
                "hovertext": f"Current: ${pred['current_price']:.0f}",
            })

        hotel_name = preds[0][1]["hotel_name"] if preds else str(hotel_id)
        js_parts.append(f"""
Plotly.newPlot('{div_id}', {json.dumps(traces)}, {{
  ...darkLayout,
  title: '{hotel_name} -- Forward Curve',
  xaxis: {{ ...darkLayout.xaxis, title: 'Date (T countdown to check-in)' }},
  yaxis: {{ ...darkLayout.yaxis, title: 'Predicted Price ($)' }},
  showlegend: true,
  legend: {{ font: {{ size: 10 }} }},
}});
""")

    return "\n".join(js_parts)


def _build_prediction_section(predictions: dict, hotels: list) -> str:
    """Build HTML section with forward curve charts and summary table."""
    if not predictions:
        return "<p style='color: #94a3b8;'>No predictions available yet.</p>"

    # Group by hotel
    by_hotel: dict[int, list] = {}
    for detail_id, pred in predictions.items():
        hid = pred["hotel_id"]
        if hid not in by_hotel:
            by_hotel[hid] = []
        by_hotel[hid].append(pred)

    # Momentum signal colors
    signal_colors = {
        "ACCELERATING_UP": "#f87171",
        "ACCELERATING_DOWN": "#4ade80",
        "ACCELERATING": "#fbbf24",
        "DECELERATING": "#818cf8",
        "NORMAL": "#64748b",
        "INSUFFICIENT_DATA": "#475569",
    }
    # Regime alert colors
    regime_colors = {
        "NORMAL": "#64748b",
        "TRENDING_UP": "#f87171",
        "TRENDING_DOWN": "#4ade80",
        "VOLATILE": "#fbbf24",
        "STALE": "#94a3b8",
    }

    html_parts = []
    for hotel_id, preds in list(by_hotel.items())[:4]:
        hotel_name = preds[0]["hotel_name"]
        div_id = f"pred-chart-{hotel_id}"

        rows = ""
        for p in sorted(preds, key=lambda x: x["date_from"])[:15]:
            change_class = "tag-up" if p["expected_change_pct"] > 1 else ("tag-down" if p["expected_change_pct"] < -1 else "tag-stable")
            change_label = f"+{p['expected_change_pct']}%" if p["expected_change_pct"] > 0 else f"{p['expected_change_pct']}%"

            # Momentum badge
            mom = p.get("momentum", {})
            signal = mom.get("signal", "INSUFFICIENT_DATA")
            strength = mom.get("strength", 0)
            sig_color = signal_colors.get(signal, "#475569")
            mom_html = f"<span class='tag' style='background: {sig_color}22; color: {sig_color};'>{signal.replace('_', ' ')}</span>"
            if strength > 0.3:
                mom_html += f" <small style='color: {sig_color};'>({strength:.0%})</small>"

            # Regime badge
            regime = p.get("regime", {})
            reg_name = regime.get("regime", "NORMAL")
            alert = regime.get("alert_level", "none")
            reg_color = regime_colors.get(reg_name, "#64748b")
            reg_html = ""
            if alert != "none":
                reg_html = f"<span class='tag' style='background: {reg_color}22; color: {reg_color};'>{reg_name.replace('_', ' ')}</span>"

            # Confidence quality
            quality = p.get("confidence_quality", "")
            q_color = "#4ade80" if quality == "high" else ("#fbbf24" if quality == "medium" else "#f87171")

            rows += (
                f"<tr>"
                f"<td>{p['category']} / {p['board']}</td>"
                f"<td>{p['date_from'][:10]}</td>"
                f"<td>T-{p['days_to_checkin']}</td>"
                f"<td>${p['current_price']:,.0f}</td>"
                f"<td>${p['predicted_checkin_price']:,.0f}</td>"
                f"<td><span class='tag {change_class}'>{change_label}</span></td>"
                f"<td>{mom_html}</td>"
                f"<td>{reg_html}</td>"
                f"</tr>"
            )

        html_parts.append(f"""
        <h3 style="color: #f1f5f9; margin: 20px 0 10px;">{hotel_name} ({len(preds)} rooms)</h3>
        <div id="{div_id}" class="chart"></div>
        <table style="margin-top: 16px;">
          <tr><th>Room</th><th>Check-in</th><th>T</th><th>Current</th><th>Predicted</th><th>Change</th><th>Momentum</th><th>Regime</th></tr>
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
