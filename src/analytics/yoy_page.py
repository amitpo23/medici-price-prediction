"""Generate the Year-over-Year price comparison page.

4 tabs:
  Tab 1: Decay Curve by Year — T × Year heatmap of avg daily % change
  Tab 2: YoY Comparison     — current year vs prior years, z-score alerts + industry benchmark
  Tab 3: Calendar Spread    — avg price per (check-in month, T, year)
  Tab 4: External Benchmarks — Hotel Booking Demand & TBO Hotels dataset context
"""
from __future__ import annotations

import json
from datetime import datetime

from src.analytics.yoy_analysis import _safe_color, _safe_price_color

# Maps our T-bucket values → lead-time bucket keys in booking_benchmarks.json
_T_TO_LEAD: dict[int, str] = {
    1: "0-7d", 3: "0-7d", 5: "0-7d", 7: "0-7d",
    10: "8-30d", 14: "8-30d", 21: "8-30d", 30: "8-30d",
    45: "31-60d", 60: "31-60d",
    90: "61-90d",
}

# Month names → seasonality index keys
_MONTH_TO_SEASON_KEY: dict[str, str] = {
    "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
    "May": "May", "Jun": "June", "Jul": "July", "Aug": "August",
    "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December",
}

# ── Embedded benchmark data (avoids runtime file dependency on Azure) ─────────

# Source 1: Miami market ADR by month — Kayak / STR / CoStar (2023-2024)
# Seasonality index = monthly_adr / annual_avg_adr (annual avg $236.67 per Kayak)
_BENCHMARKS: dict = {
    "source": "Miami market benchmarks (Kayak/STR/CoStar/HVS/GMCVB/CBRE/Newmark) — compiled 2026-03",
    "annual_avg_adr": 222.12,  # STR/CoStar full-year 2024

    # Miami-specific seasonality (inverted vs Europe — peak = Jan-Feb-Dec, trough = Sep)
    # Derived from Kayak 2023-2024 monthly ADR / annual avg $236.67
    "seasonality_index": {
        "January": 1.056, "February": 1.099, "March": 1.014, "April": 0.972,
        "May": 0.930, "June": 0.887, "July": 0.908, "August": 0.887,
        "September": 0.845, "October": 0.866, "November": 0.930, "December": 1.099,
    },

    # Monthly ADR by source (USD, all-hotel Miami metro average — Kayak 2023-2024)
    "monthly_adr_kayak": {
        "January": 250, "February": 260, "March": 240, "April": 230,
        "May": 220, "June": 210, "July": 215, "August": 210,
        "September": 200, "October": 205, "November": 220, "December": 260,
    },

    # STR spot readings 2024 (professional hotel-only benchmark — Miami-Dade)
    "str_spot_2024": {
        "February": {"adr": 326.27, "occupancy_pct": 78.1, "revpar": 254.73,
                     "note": "Miami Beach submarket; occ +0.3%, ADR -1.5% YoY"},
        "March":   {"adr": 284.14, "occupancy_pct": 83.5, "revpar": 237.25,
                    "note": "Highest in Top 25 US markets; occ +2.3%, ADR -0.6% YoY"},
        "October": {"adr": 245.28, "revpar": 179.72, "note": "event-driven: Taylor Swift + Adobe MAX; ADR +29.9% YoY"},
        "Q3_avg":  {"adr": 169.70, "occupancy_pct": 67.2, "revpar": 114.08, "note": "Off-season Q3 2024"},
    },

    # Annual market KPIs (STR/CoStar — Miami-Dade County)
    "annual_market": {
        "2019": {"occupancy_pct": 75.0, "adr": 215.29, "revpar": 154.21,
                 "note": "Pre-pandemic baseline; #3 ADR nationally"},
        "2020": {"occupancy_pct": 48.8, "adr": 187.01, "revpar": None,
                 "note": "COVID collapse (Dec 2020 snapshot)"},
        "2021": {"occupancy_pct": 72.0, "adr": 223.49, "revpar": None,
                 "note": "Fast recovery; ADR +14.7% vs 2019; 24.2M visitors"},
        "2022": {"occupancy_pct": 72.1, "adr": 253.11, "revpar": 182.55,
                 "revpar_yoy_pct": 23.1, "adr_yoy_pct": 14.0,
                 "note": "Post-pandemic peak; ADR +30% vs 2019; #3 ADR, #3 RevPAR nationally"},
        "2023": {"occupancy_pct": 71.9, "adr": 209.98, "revpar": 159.22,
                 "revpar_yoy_pct": -6.7, "adr_yoy_pct": -6.0, "occ_yoy_pct": -0.2,
                 "note": "Normalization year; 16-month RevPAR decline began"},
        "2024": {"occupancy_pct": 73.9, "adr": 222.12, "revpar": 164.10,
                 "revpar_yoy_pct": 3.1, "adr_yoy_pct": 0.4, "occ_yoy_pct": 2.7,
                 "total_rooms": 67973, "visitors": 28.23,
                 "note": "Recovery; #4 occ, #3 ADR in Top 25; record 28.2M visitors"},
        "2025F": {"occupancy_pct": 74.0, "adr": 223.45, "revpar": 165.41,
                  "revpar_yoy_pct": 0.8, "adr_yoy_pct": 0.6, "occ_yoy_pct": 0.2,
                  "note": "CBRE forecast; Q1 led Top 25 markets in RevPAR & occupancy"},
    },

    # 2025 actual monthly data (STR/CoStar press releases)
    "str_monthly_2025": {
        "January":  {"occupancy_pct": 79.4, "adr": 256.99, "revpar": 203.95,
                     "occ_yoy": 1.0, "adr_yoy": 2.1, "revpar_yoy": 3.1},
        "February": {"occupancy_pct": 85.8, "adr": 305.06, "revpar": 261.61,
                     "occ_yoy": 2.3, "adr_yoy": 4.6, "revpar_yoy": 7.0},
        "March":    {"occupancy_pct": 83.2, "adr": 284.25, "revpar": 236.40,
                     "occ_yoy": -0.4, "adr_yoy": 0.0, "revpar_yoy": -0.4,
                     "note": "#1 occupancy in all Top 25 US markets"},
    },

    # Submarket performance (HVS / STR 2019 baseline)
    "submarket_2019": {
        "Miami Beach":        {"occupancy_pct": 79.6, "adr": 332.42, "revpar": 264.61},
        "Downtown/Brickell":  {"occupancy_pct": 77.5, "adr": 215.29, "revpar": 166.85},
        "Airport":            {"occupancy_pct": 83.0, "adr": 129.54, "revpar": 107.52},
    },

    # South Florida comparative (Matthews 3Q24 trailing 12 months)
    "south_florida_t12_3q24": {
        "Miami":         {"occupancy_pct": 73.3, "adr": 220.31, "revpar": 161.37, "rooms": 67481},
        "Fort Lauderdale":{"occupancy_pct": 72.2, "adr": 180.32, "revpar": 132.57, "rooms": 39502},
        "Palm Beach":    {"occupancy_pct": 67.1, "adr": 252.10, "revpar": 169.24, "rooms": 19533},
    },

    # Market segmentation — chain scale share of Miami market (Matthews 3Q24)
    "chain_scale_share": {
        "Luxury": 0.20, "Upper Upscale": 0.23, "Upscale": 0.24,
        "Upper Midscale": 0.15, "Midscale": 0.06, "Economy": 0.12,
    },

    # HVS long-run RevPAR series (Miami-Hialeah)
    "hvs_annual_revpar": {
        "2008": 114.32, "2009": 91.32,  "2010": 101.40, "2011": 116.14,
        "2012": 124.18, "2013": 135.24, "2014": 144.83, "2015": 152.74,
        "2016": 143.59, "2017": 144.65, "2018": 148.99, "2019": 154.21,
    },

    # Supply pipeline (Matthews 3Q24)
    "supply_pipeline": {
        "total_rooms_2024": 67973,
        "under_construction": 3600,
        "under_construction_properties": 21,
        "new_2023": 423,
        "new_2024_scheduled": 1200,
        "new_2025_scheduled": 1200,
        "new_2026_planned": 5000,
        "total_pipeline_rooms": 10564,
        "total_pipeline_projects": 60,
    },

    # ── Hotel Booking Demand dataset — European hotels 2015-2017, 117,429 rows ──
    # Source: kagglehub jessemostipak/hotel-booking-demand (full CSV analysis)
    # Note: directional signals only — Miami absolute ADR is ~2× higher

    # Lead-time ADR + cancel rate (computed from full CSV, adr > 0 & < 5000)
    "lead_time_buckets": {
        "0-7d":    {"cancel_rate": 0.11, "avg_adr": 97.23,  "median_adr": 89.0,  "bookings": 12839},
        "8-30d":   {"cancel_rate": 0.28, "avg_adr": 109.91, "median_adr": 99.0,  "bookings": 18651},
        "31-60d":  {"cancel_rate": 0.37, "avg_adr": 107.18, "median_adr": 96.0,  "bookings": 16819},
        "61-90d":  {"cancel_rate": 0.40, "avg_adr": 107.43, "median_adr": 98.0,  "bookings": 12487},
        "91-180d": {"cancel_rate": 0.45, "avg_adr": 109.66, "median_adr": 100.3, "bookings": 26311},
        "181-365d":{"cancel_rate": 0.56, "avg_adr": 95.61,  "median_adr": 90.0,  "bookings": 21424},
        "365d+":   {"cancel_rate": 0.68, "avg_adr": 79.29,  "median_adr": 67.0,  "bookings": 3129},
    },

    # Market segment (sorted by volume)
    "market_segment_adr": {
        "Online TA": 117.96, "Direct": 117.69, "Aviation": 102.74,
        "Offline TA/TO": 88.35, "Groups": 80.51, "Corporate": 70.45,
    },
    "market_segment_cancel": {
        "Online TA": 0.37, "Direct": 0.15, "Aviation": 0.22,
        "Offline TA/TO": 0.35, "Groups": 0.62, "Corporate": 0.19,
    },
    "market_segment_bookings": {
        "Online TA": 56110, "Offline TA/TO": 23886, "Groups": 19558,
        "Direct": 12366, "Corporate": 5213, "Aviation": 231,
    },

    # Customer type
    "customer_type_cancel": {
        "Transient": 0.41, "Transient-Party": 0.26, "Contract": 0.31, "Group": 0.08,
    },
    "customer_type_adr": {
        "Transient": 108.71, "Transient-Party": 87.67, "Contract": 88.07, "Group": 88.55,
    },

    # Hotel type (City vs Resort)
    "hotel_type": {
        "City Hotel":   {"cancel_rate": 0.42, "avg_adr": 106.87, "bookings": 78121},
        "Resort Hotel": {"cancel_rate": 0.28, "avg_adr":  96.77, "bookings": 39308},
    },

    # European monthly ADR (opposite seasonality to Miami — peak = Jul-Aug)
    "european_monthly_adr": {
        "January": 71.91, "February": 74.95, "March": 81.41, "April": 101.63,
        "May": 110.38, "June": 117.97, "July": 128.51, "August": 141.81,
        "September": 106.64, "October": 89.77, "November": 75.50, "December": 83.78,
    },

    "weekend_premium_pct": 4.3,  # +4.3% weekend vs weekday ADR (directly from CSV)

    # ── Miami International Airport (MIA) passenger statistics ───────
    # Source: official MIA press releases / miamidade.gov / ACI rankings
    "mia_annual_passengers": {
        "2019": {"total_m": 45.92, "note": "Pre-pandemic baseline"},
        "2020": {"total_m": 18.66, "note": "COVID collapse -59.4%"},
        "2021": {"total_m": 37.30, "note": "Recovery +99.9% YoY"},
        "2022": {"total_m": 50.68, "domestic_m": 29.3,  "international_m": 21.3,
                 "note": "Record at the time; #1 US intl passengers"},
        "2023": {"total_m": 52.34, "domestic_m": 29.1,  "international_m": 23.24,
                 "note": "+3.3% YoY; 96 carriers"},
        "2024": {"total_m": 55.93, "domestic_m": 30.76, "international_m": 25.17,
                 "note": "+6.8% YoY; +22% vs 2019; #10 US, #1 US intl pax"},
        "2025": {"total_m": 55.30, "domestic_m": 30.5,  "international_m": 24.8,
                 "note": "-1.1% YoY; slight softening"},
    },
    "mia_annual_cargo_tons_m": {
        "2019": 2.30, "2020": 2.32, "2021": 2.70,
        "2022": 2.70, "2023": 2.78, "2024": 3.008,
    },
    "mia_annual_operations": {
        "2019": 416000, "2020": 252000, "2021": 387973,
        "2022": 472400, "2023": 461792, "2024": 485448,
    },
    "mia_rankings_2024": {
        "us_rank_total_pax": 10,
        "us_rank_intl_pax": 1,
        "us_rank_intl_cargo": 1,
        "us_rank_total_cargo": 3,
        "global_rank_total_pax": 27,
        "global_rank_intl_freight": 5,
    },

    # ── Miami Airbnb / Short-term Rental (STR) market ─────────────────
    # Source: Airbtics Nov 2024 - Oct 2025 (insideairbnb.com blocked, Airbtics proxy)
    "airbnb_miami": {
        "active_listings_city": 7263,
        "active_listings_metro": 22409,  # AirDNA broader Miami-Dade count
        "median_occupancy_pct": 69.0,
        "adr": 197.0,
        "revpar": 136.0,  # computed: 69% × $197
        "avg_annual_revenue": 47000,
        "avg_monthly_revenue": 3956,
        "international_guest_pct": 24.27,
        "yoy_revenue_change_pct": 25.28,
        "peak_month": "February",
        "trough_month": "September",
        "monthly_revenue": {
            "November": 3455, "December": 4261, "January": 3843,
            "February": 4485, "March": 4329, "April": 4099,
            "May": 3861, "June": 3774, "July": 3917,
            "August": 3914, "September": 3106, "October": 4406,
        },
        "neighborhoods": {
            "Brickell":      {"listings": 1304, "annual_rev": 70612, "occupancy_pct": 75, "adr": 250},
            "Downtown Miami":{"listings": 1141, "annual_rev": 60334, "occupancy_pct": 67, "adr": 241},
            "Coconut Grove": {"listings": 705,  "annual_rev": 57245, "occupancy_pct": 75, "adr": 204},
            "Wynwood":       {"listings": 469,  "occupancy_pct": None, "adr": 188},
            "Little Havana": {"listings": 234,  "occupancy_pct": None, "adr": 134},
        },
        "property_type": {
            "Entire home": 4831, "Condo": 1535, "Private room": 792,
            "Shared room": 79, "Hotel room": 26,
        },
        "bedroom_distribution": {
            "Studio": 623, "1 bed": 2838, "2 bed": 1764,
            "3 bed": 681, "4 bed": 274, "5+ bed": 186,
        },
        # Inside Airbnb listings.csv columns (schema from public docs — CSV itself 403 blocked)
        "insideairbnb_columns": [
            "id", "name", "host_id", "host_name", "neighbourhood_group", "neighbourhood",
            "latitude", "longitude", "room_type", "price", "minimum_nights",
            "number_of_reviews", "last_review", "reviews_per_month",
            "calculated_host_listings_count", "availability_365",
            "number_of_reviews_ltm", "license",
        ],
    },
}

# Source 2: TBO Hotels Dataset — Miami area supply (2978 hotels, metadata only)
_TBO_STATS: dict = {
    "total": 2978,
    "ratings": {
        "ThreeStar": 1333, "FourStar": 591, "TwoStar": 514,
        "All": 439, "FiveStar": 69, "OneStar": 32,
    },
    "cities": {
        "Miami": 953, "Miami Beach": 599, "Fort Lauderdale": 590,
        "Miami South Beach": 279, "Hollywood Beach/Fort Lauderdale": 221,
        "Miami Beach - Sunny Isles": 93, "Pompano Beach/Fort Lauderdale": 70,
        "Lauderdale-by-the-Sea": 47,
    },
}

HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_yoy_html(yoy_data: dict) -> str:
    """Build the full YoY HTML page from pre-computed analysis dicts."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if not yoy_data:
        return _empty_page(now)

    tab1 = _build_decay_tab(yoy_data)
    tab2 = _build_yoy_comparison_tab(yoy_data, _BENCHMARKS)
    tab3 = _build_calendar_spread_tab(yoy_data)
    tab4 = _build_external_benchmarks_tab(_BENCHMARKS, _TBO_STATS)
    term_data = {hid: data.get("term_structure", {}) for hid, data in yoy_data.items()}
    tab5 = _build_term_structure_tab(term_data)

    return _wrap_page(now, tab1, tab2, tab3, tab4, tab5)


# ── Tab 1: Decay Curve by Year ────────────────────────────────────────

def _build_decay_tab(yoy_data: dict) -> str:
    html = """
    <div class="explainer">
        <strong>How to read:</strong> Each cell shows the average daily % price change at that T (days to check-in) for that year.
        <span class="savings">Green</span> = prices were falling at that lead time (buy opportunity).
        <span class="premium">Red</span> = prices were rising (sell / hold signal).
        Darker = stronger signal. Cells with fewer than 3 observations show <em>—</em>.
    </div>"""

    for hotel_id, data in yoy_data.items():
        pivot = data.get("pivot", {})
        if not pivot or not pivot.get("rows"):
            continue

        hotel_name = HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}")
        years = pivot["years"]
        rows = pivot["rows"]

        # Column headers
        year_headers = "".join(f"<th>{y}</th>" for y in years)
        current_yr = max(years) if years else 2025

        table_rows = ""
        for row in rows:
            T = row["T"]
            yr_cells = ""
            for yr in years:
                cell = row["years"].get(yr)
                if cell is None:
                    yr_cells += '<td class="empty-cell">—</td>'
                else:
                    avg = cell["avg"]
                    n = cell["n"]
                    bg = _safe_color(avg)
                    sign = "+" if avg >= 0 else ""
                    yr_cells += f'<td style="background:{bg}" title="{n} obs">{sign}{avg:.3f}%<span class="n-obs">{n}</span></td>'

            # Delta vs last year
            delta = row.get("delta_vs_ly")
            delta_html = "—"
            if delta is not None:
                bg = _safe_color(delta, scale=0.3)
                sign = "+" if delta >= 0 else ""
                delta_cls = "premium" if delta > 0 else "savings"
                delta_html = f'<span class="{delta_cls}">{sign}{delta:.3f}%</span>'

            table_rows += f"""<tr>
                <td class="t-cell">{row["label"]}</td>
                {yr_cells}
                <td>{delta_html}</td>
            </tr>"""

        html += f"""
        <h3 class="hotel-header">{hotel_name}</h3>
        <div class="table-wrap">
        <table class="heatmap-table">
            <thead><tr>
                <th>T</th>
                {year_headers}
                <th>Δ vs LY</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
        </div>"""

    return html


# ── Tab 2: YoY Comparison ─────────────────────────────────────────────

def _benchmark_adr(T: int, month_name: str, benchmarks: dict) -> float | None:
    """Compute seasonally-adjusted industry benchmark ADR for a given T and month."""
    if not benchmarks:
        return None
    bucket = _T_TO_LEAD.get(T)
    if not bucket:
        return None
    lead_data = benchmarks.get("lead_time_buckets", {}).get(bucket, {})
    base_adr = lead_data.get("avg_adr")
    if not base_adr:
        return None
    season_key = _MONTH_TO_SEASON_KEY.get(month_name)
    season_factor = benchmarks.get("seasonality_index", {}).get(season_key, 1.0) if season_key else 1.0
    return round(base_adr * season_factor, 2)


def _build_yoy_comparison_tab(yoy_data: dict, benchmarks: dict) -> str:
    has_benchmarks = bool(benchmarks)
    benchmark_note = (
        ' Industry ADR from <em>Hotel Booking Demand dataset (2015–2017, 117K bookings)</em>, '
        'seasonally adjusted by month. Use as directional context only — not Miami-specific.'
        if has_benchmarks else ""
    )
    html = f"""
    <div class="explainer">
        <strong>How to read:</strong> For each room category, check-in month, and T (days to check-in),
        this compares the average price this year vs. last year.
        <span class="alert-warning-pill">Warning</span> (Z &gt; 2.5) means this year's price is significantly
        above the historical pattern. <span class="savings">Green</span> = cheaper than last year.
        <span class="premium">Red</span> = more expensive than last year.{benchmark_note}
    </div>"""

    for hotel_id, data in yoy_data.items():
        comparison = data.get("comparison", [])
        if not comparison:
            continue

        hotel_name = HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}")
        html += f'<h3 class="hotel-header">{hotel_name}</h3>'

        # Group by category
        by_cat: dict[str, list[dict]] = {}
        for row in comparison:
            cat = row["category"]
            by_cat.setdefault(cat, []).append(row)

        for cat, rows in sorted(by_cat.items()):
            warnings = sum(1 for r in rows if r["alert"] == "warning")
            watches = sum(1 for r in rows if r["alert"] == "watch")
            uid = f"yoy_{hotel_id}_{cat}"

            table_rows = ""
            for r in rows:
                alert = r.get("alert", "normal")
                row_cls = "row-warning" if alert == "warning" else "row-watch" if alert == "watch" else ""

                yoy_pct = r.get("yoy_pct")
                yoy_html = "—"
                if yoy_pct is not None:
                    cls = "premium" if yoy_pct > 0 else "savings"
                    yoy_html = f'<span class="{cls}">{yoy_pct:+.1f}%</span>'

                zscore = r.get("zscore")
                z_html = "—"
                if zscore is not None:
                    zcls = "z-warning" if abs(zscore) > 2.5 else "z-watch" if abs(zscore) > 1.5 else "z-normal"
                    z_html = f'<span class="{zcls}">{zscore:+.2f}</span>'

                curr_price = r.get("current_avg_price")
                last_price = r.get("last_year_avg_price")
                curr_html = f"${curr_price:,.0f}" if curr_price else "—"
                last_html = f"${last_price:,.0f}" if last_price else "—"

                # Industry benchmark ADR (seasonally adjusted)
                bench_adr = _benchmark_adr(r["T_bucket"], r["checkin_month_name"], benchmarks)
                bench_html = "—"
                if bench_adr and curr_price:
                    pct_vs_bench = (curr_price - bench_adr) / bench_adr * 100
                    sign = "+" if pct_vs_bench >= 0 else ""
                    b_cls = "premium" if pct_vs_bench > 5 else "savings" if pct_vs_bench < -5 else ""
                    bench_html = (
                        f'<span title="Industry ADR: ${bench_adr:,.0f}">'
                        f'${bench_adr:,.0f} '
                        f'<span class="{b_cls}" style="font-size:0.8em">({sign}{pct_vs_bench:.0f}%)</span>'
                        f'</span>'
                    )
                elif bench_adr:
                    bench_html = f"${bench_adr:,.0f}"

                bench_col = f"<td>{bench_html}</td>" if has_benchmarks else ""
                table_rows += f"""<tr class="{row_cls}">
                    <td>{r["checkin_month_name"]}</td>
                    <td>{r["T_bucket"]}d</td>
                    <td>{last_html} <span class="n-obs">n={r["last_year_n"]}</span></td>
                    <td>{curr_html} <span class="n-obs">n={r["current_n"]}</span></td>
                    <td>{yoy_html}</td>
                    {bench_col}
                    <td>{z_html}</td>
                    <td>{"⚠" if alert == "warning" else "👁" if alert == "watch" else "✓"}</td>
                </tr>"""

            alert_summary = ""
            if warnings:
                alert_summary += f'<span class="alert-warning-pill">{warnings} warnings</span> '
            if watches:
                alert_summary += f'<span class="alert-watch-pill">{watches} watches</span>'

            bench_th = "<th>Industry ADR</th>" if has_benchmarks else ""
            html += f"""
            <div class="comp-row">
                <div class="comp-row-header" onclick="toggle('{uid}')">
                    <span class="comp-room">{cat.title()}</span>
                    <span>{len(rows)} data points</span>
                    <span>{alert_summary}</span>
                    <span class="comp-toggle" id="arrow_{uid}">&#9654;</span>
                </div>
                <div class="comp-detail" id="{uid}" style="display:none">
                    <table class="comp-table">
                        <thead><tr>
                            <th>Month</th><th>T</th>
                            <th>{rows[0].get("last_year", "LY")} Avg</th>
                            <th>{rows[0].get("current_year", "CY")} Avg</th>
                            <th>YoY %</th>{bench_th}
                            <th>Z-Score</th><th>Flag</th>
                        </tr></thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>"""

    return html


# ── Tab 3: Calendar Spread ────────────────────────────────────────────

def _build_calendar_spread_tab(yoy_data: dict) -> str:
    html = """
    <div class="explainer">
        <strong>How to read:</strong> For each check-in month and T (days to check-in),
        this shows the average price across different years. Cells are colored relative to
        the most recent year — <span class="savings">green</span> = cheaper than this year's price,
        <span class="premium">red</span> = more expensive. Blank = no data for that combination.
    </div>"""

    for hotel_id, data in yoy_data.items():
        spread = data.get("spread", {})
        if not spread or not spread.get("months"):
            continue

        hotel_name = HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}")
        years = spread["years"]
        months = spread["months"]

        html += f'<h3 class="hotel-header">{hotel_name}</h3>'

        year_headers = "".join(f"<th>{y}</th>" for y in years)
        current_yr = max(years) if years else 2025

        for month_name, month_data in months.items():
            rows = month_data.get("rows", [])
            if not rows:
                continue

            table_rows = ""
            for row in rows:
                yr_prices = row["years"]
                ref_price = yr_prices.get(current_yr)

                yr_cells = ""
                for yr in years:
                    price = yr_prices.get(yr)
                    if price is None:
                        yr_cells += '<td class="empty-cell">—</td>'
                    else:
                        bg = _safe_price_color(price, ref_price) if yr != current_yr else "transparent"
                        yr_cells += f'<td style="background:{bg}">${price:,.0f}</td>'

                table_rows += f'<tr><td class="t-cell">{row["label"]}</td>{yr_cells}</tr>'

            html += f"""
            <div class="spread-section">
                <div class="spread-header" onclick="toggleSpread('{hotel_id}_{month_name}')">
                    <span class="month-label">Check-in: {month_name}</span>
                    <span class="comp-toggle" id="arrow_{hotel_id}_{month_name}">&#9654;</span>
                </div>
                <div id="spread_{hotel_id}_{month_name}" style="display:none">
                    <table class="heatmap-table">
                        <thead><tr><th>T</th>{year_headers}</tr></thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>"""

    return html


# ── Tab 4: External Benchmarks ────────────────────────────────────────

def _build_external_benchmarks_tab(benchmarks: dict, tbo_stats: dict) -> str:
    """Build the External Benchmarks panel — Miami-specific market data."""

    if not benchmarks:
        return '<p class="no-data">Benchmark data not available.</p>'

    # ── Section 1: Miami ADR by Month ────────────────────────────────
    season = benchmarks.get("seasonality_index", {})
    kayak_adr = benchmarks.get("monthly_adr_kayak", {})
    annual_avg = benchmarks.get("annual_avg_adr", 236.67)

    season_rows = ""
    for month, idx in season.items():
        adr = kayak_adr.get(month, 0)
        bar_w = min(int(idx * 70), 100)
        bar_cls = "bar-high" if idx >= 1.05 else "bar-mid" if idx >= 0.95 else "bar-low"
        label = "Peak" if idx >= 1.05 else "Average" if idx >= 0.95 else "Low"
        season_rows += (
            f'<tr><td class="bm-month">{month[:3]}</td>'
            f'<td>${adr:,.0f}</td>'
            f'<td class="bm-idx">{idx:.3f}</td>'
            f'<td><div class="bar-bg"><div class="bar-fill {bar_cls}" style="width:{bar_w}%"></div></div></td>'
            f'<td class="bm-note">{label}</td></tr>'
        )

    # ── Section 2: Annual KPIs (STR/CoStar) ──────────────────────────
    annual = benchmarks.get("annual_market", {})
    annual_rows = ""
    for yr in sorted(annual.keys()):
        d = annual[yr]
        occ = d.get("occupancy_pct")
        adr = d.get("adr")
        revpar = d.get("revpar") or d.get("revpar_approx")
        yoy = d.get("revpar_yoy_pct")
        yoy_str = f'{yoy:+.1f}%' if yoy is not None else "—"
        yoy_color = "var(--green)" if (yoy or 0) >= 0 else "var(--red)"
        note = d.get("note", "")
        annual_rows += (
            f'<tr><td class="bm-month">{yr}</td>'
            f'<td>{f"{occ:.1f}%" if occ else "—"}</td>'
            f'<td>{f"${adr:.2f}" if adr else "—"}</td>'
            f'<td>{f"${revpar:.2f}" if revpar else "—"}</td>'
            f'<td style="color:{yoy_color};font-weight:600">{yoy_str}</td>'
            f'<td class="bm-note">{note}</td></tr>'
        )

    # ── Section 2b: 2025 actual monthly data ─────────────────────────
    m2025 = benchmarks.get("str_monthly_2025", {})
    m2025_rows = ""
    for month, d in m2025.items():
        occ = d.get("occupancy_pct", 0)
        adr = d.get("adr", 0)
        revpar = d.get("revpar", 0)
        occ_yoy = d.get("occ_yoy", 0)
        adr_yoy = d.get("adr_yoy", 0)
        revpar_yoy = d.get("revpar_yoy", 0)
        note = d.get("note", "")
        def _yc(v: float) -> str:
            return "var(--green)" if v >= 0 else "var(--red)"
        m2025_rows += (
            f'<tr><td class="bm-month">{month}</td>'
            f'<td>{occ:.1f}% <small style="color:{_yc(occ_yoy)}">({occ_yoy:+.1f}%)</small></td>'
            f'<td>${adr:.2f} <small style="color:{_yc(adr_yoy)}">({adr_yoy:+.1f}%)</small></td>'
            f'<td>${revpar:.2f} <small style="color:{_yc(revpar_yoy)}">({revpar_yoy:+.1f}%)</small></td>'
            f'<td class="bm-note">{note}</td></tr>'
        )

    # ── Section 3: STR Spot Readings 2024 ────────────────────────────
    str_spots = benchmarks.get("str_spot_2024", {})
    str_rows = ""
    for period, d in str_spots.items():
        if not isinstance(d, dict):
            continue
        adr = d.get("adr", "—")
        occ = d.get("occupancy_pct", "—")
        revpar = d.get("revpar", "—")
        note = d.get("note", "")
        str_rows += (
            f'<tr><td class="bm-month">{period.replace("_", " ")}</td>'
            f'<td>${adr if isinstance(adr, str) else f"{adr:.2f}"}</td>'
            f'<td>{f"{occ:.1f}%" if isinstance(occ, (int, float)) else occ}</td>'
            f'<td>${revpar if isinstance(revpar, str) else f"{revpar:.2f}"}</td>'
            f'<td class="bm-note">{note}</td></tr>'
        )

    # ── Section 3b: Submarket comparison ─────────────────────────────
    submarket = benchmarks.get("submarket_2019", {})
    sub_rows = "".join(
        f'<tr><td class="bm-month">{sm}</td>'
        f'<td>{d.get("occupancy_pct",0):.1f}%</td>'
        f'<td>${d.get("adr",0):.2f}</td>'
        f'<td>${d.get("revpar",0):.2f}</td></tr>'
        for sm, d in submarket.items()
    )

    # ── Section 3c: South Florida comparison ─────────────────────────
    sf = benchmarks.get("south_florida_t12_3q24", {})
    sf_rows = "".join(
        f'<tr><td class="bm-month">{mkt}</td>'
        f'<td>{d.get("occupancy_pct",0):.1f}%</td>'
        f'<td>${d.get("adr",0):.2f}</td>'
        f'<td>${d.get("revpar",0):.2f}</td>'
        f'<td>{d.get("rooms",0):,}</td></tr>'
        for mkt, d in sf.items()
    )

    # ── Section 3d: Chain scale share ────────────────────────────────
    chain_scale = benchmarks.get("chain_scale_share", {})
    scale_order = ["Luxury", "Upper Upscale", "Upscale", "Upper Midscale", "Midscale", "Economy"]
    scale_rows = ""
    for seg in scale_order:
        share = chain_scale.get(seg, 0)
        bar_w = int(share * 300)
        scale_rows += (
            f'<tr><td class="bm-month">{seg}</td>'
            f'<td>{share * 100:.0f}%</td>'
            f'<td><div class="bar-bg"><div class="bar-fill bar-mid" style="width:{bar_w}%"></div></div></td></tr>'
        )

    # ── Section 4: HVS Long-run RevPAR ───────────────────────────────
    hvs = benchmarks.get("hvs_annual_revpar", {})
    hvs_rows = ""
    prev = None
    for yr in sorted(hvs.keys()):
        val = hvs[yr]
        chg = f'{(val - prev) / prev * 100:+.1f}%' if prev else "—"
        chg_color = "var(--green)" if prev and val >= prev else "var(--red)"
        hvs_rows += (
            f'<tr><td class="bm-month">{yr}</td>'
            f'<td>${val:.2f}</td>'
            f'<td style="color:{chg_color}">{chg}</td></tr>'
        )
        prev = val

    # ── Section 5: Lead-time benchmarks (proxy) ──────────────────────
    lead_rows = ""
    for bucket, bdata in benchmarks.get("lead_time_buckets", {}).items():
        adr = bdata.get("avg_adr", 0)
        median_adr = bdata.get("median_adr", 0)
        cancel = bdata.get("cancel_rate", 0)
        n = bdata.get("bookings", 0)
        cancel_color = "var(--red)" if cancel >= 0.5 else "var(--yellow)" if cancel >= 0.35 else "var(--green)"
        lead_rows += (
            f'<tr><td class="bm-month">{bucket}</td>'
            f'<td>${adr:,.2f}</td>'
            f'<td>${median_adr:,.1f}</td>'
            f'<td style="color:{cancel_color}">{cancel * 100:.0f}%</td>'
            f'<td class="bm-note">{n:,}</td></tr>'
        )

    # ── Section 5b: Market segment (proxy) ───────────────────────────
    seg_adr = benchmarks.get("market_segment_adr", {})
    seg_cancel = benchmarks.get("market_segment_cancel", {})
    seg_bookings = benchmarks.get("market_segment_bookings", {})
    seg_rows = ""
    for seg in sorted(seg_adr, key=lambda s: -seg_bookings.get(s, 0)):
        adr = seg_adr.get(seg, 0)
        cancel = seg_cancel.get(seg, 0)
        n = seg_bookings.get(seg, 0)
        cancel_color = "var(--red)" if cancel >= 0.5 else "var(--yellow)" if cancel >= 0.3 else "var(--green)"
        seg_rows += (
            f'<tr><td class="bm-month">{seg}</td>'
            f'<td>${adr:.2f}</td>'
            f'<td style="color:{cancel_color}">{cancel * 100:.0f}%</td>'
            f'<td class="bm-note">{n:,}</td></tr>'
        )

    # ── Section 5c: Customer type (proxy) ────────────────────────────
    ct_cancel = benchmarks.get("customer_type_cancel", {})
    ct_adr = benchmarks.get("customer_type_adr", {})
    ct_rows = "".join(
        f'<tr><td class="bm-month">{ct}</td>'
        f'<td>${ct_adr.get(ct, 0):.2f}</td>'
        f'<td style="color:{"var(--red)" if ct_cancel.get(ct,0)>=0.35 else "var(--green)"}">{ct_cancel.get(ct,0)*100:.0f}%</td></tr>'
        for ct in ct_cancel
    )

    # ── Section 5d: European monthly ADR (opposite seasonality) ──────
    eu_adr = benchmarks.get("european_monthly_adr", {})
    miami_adr = benchmarks.get("monthly_adr_kayak", {})
    eu_rows = ""
    months_order = ["January","February","March","April","May","June",
                    "July","August","September","October","November","December"]
    for m in months_order:
        eu = eu_adr.get(m, 0)
        miami = miami_adr.get(m, 0)
        diff = "Peak EU" if eu >= 120 else "Low EU" if eu <= 80 else ""
        eu_rows += (
            f'<tr><td class="bm-month">{m[:3]}</td>'
            f'<td>${eu:.2f}</td>'
            f'<td>${miami:.0f}</td>'
            f'<td class="bm-note">{diff}</td></tr>'
        )

    # ── Section 5e: Airbnb STR market ────────────────────────────────
    airbnb = benchmarks.get("airbnb_miami", {})
    airbnb_occ = airbnb.get("median_occupancy_pct", 0)
    airbnb_adr = airbnb.get("adr", 0)
    airbnb_revpar = airbnb.get("revpar", 0)
    airbnb_listings = airbnb.get("active_listings_city", 0)
    airbnb_monthly = airbnb.get("monthly_revenue", {})
    airbnb_nbhd = airbnb.get("neighborhoods", {})
    def _airbnb_nbhd_row(nb: str, d: dict) -> str:
        occ_str = f'{d["occupancy_pct"]:.0f}%' if d.get("occupancy_pct") else "—"
        rev_str = f'${d["annual_rev"]:,}' if d.get("annual_rev") else "—"
        return (
            f'<tr><td class="bm-month">{nb}</td>'
            f'<td>{d.get("listings", 0):,}</td>'
            f'<td>{occ_str}</td>'
            f'<td>${d.get("adr", 0):.0f}</td>'
            f'<td>{rev_str}</td></tr>'
        )
    airbnb_nbhd_rows = "".join(_airbnb_nbhd_row(nb, d) for nb, d in airbnb_nbhd.items())
    airbnb_monthly_rows = "".join(
        f'<tr><td class="bm-month">{m[:3]}</td><td>${rev:,}</td></tr>'
        for m, rev in airbnb_monthly.items()
    )
    airbnb_prop_rows = "".join(
        f'<tr><td class="bm-month">{pt}</td><td>{cnt:,}</td>'
        f'<td><div class="bar-bg"><div class="bar-fill bar-mid" style="width:{min(int(cnt/airbnb_listings*180),100)}%"></div></div></td></tr>'
        for pt, cnt in airbnb.get("property_type", {}).items()
    )

    # ── Section 6: Miami Airport (MIA) statistics ────────────────────
    mia_pax = benchmarks.get("mia_annual_passengers", {})
    mia_cargo = benchmarks.get("mia_annual_cargo_tons_m", {})
    mia_ops = benchmarks.get("mia_annual_operations", {})
    mia_rows = ""
    prev_pax = None
    for yr in sorted(mia_pax.keys()):
        d = mia_pax[yr]
        total = d.get("total_m", 0)
        dom = d.get("domestic_m")
        intl = d.get("international_m")
        note = d.get("note", "")
        yoy_str = ""
        if prev_pax:
            yoy = (total - prev_pax) / prev_pax * 100
            col = "var(--green)" if yoy >= 0 else "var(--red)"
            yoy_str = f'<span style="color:{col}">({yoy:+.1f}%)</span>'
        cargo = mia_cargo.get(yr, 0)
        ops = mia_ops.get(yr, 0)
        mia_rows += (
            f'<tr><td class="bm-month">{yr}</td>'
            f'<td>{total:.2f}M {yoy_str}</td>'
            f'<td>{f"{dom:.1f}M" if dom else "—"}</td>'
            f'<td>{f"{intl:.2f}M" if intl else "—"}</td>'
            f'<td>{f"{cargo:.2f}M t" if cargo else "—"}</td>'
            f'<td>{f"{ops:,}" if ops else "—"}</td>'
            f'<td class="bm-note">{note}</td></tr>'
        )
        prev_pax = total

    # ── Section 7: TBO supply ─────────────────────────────────────────
    tbo_html = ""
    if tbo_stats:
        total = tbo_stats.get("total", 0)
        ratings = tbo_stats.get("ratings", {})
        cities = tbo_stats.get("cities", {})
        rating_rows = "".join(
            f'<tr><td class="bm-month">{r}</td><td>{n:,}</td>'
            f'<td><div class="bar-bg"><div class="bar-fill bar-mid" '
            f'style="width:{min(int(n / total * 200), 100)}%"></div></div></td></tr>'
            for r, n in sorted(ratings.items(), key=lambda x: -x[1])
        )
        city_rows = "".join(
            f'<tr><td class="bm-month">{c}</td><td>{n:,}</td></tr>'
            for c, n in sorted(cities.items(), key=lambda x: -x[1])
        )
        tbo_html = f"""
        <div class="bm-grid">
            <div class="bm-panel">
                <h4 class="bm-panel-title">Hotel Supply by Star Rating</h4>
                <p class="bm-desc">Miami-area hotel supply composition — TBO dataset (Kaggle), {total:,} properties.</p>
                <table class="bm-table">
                    <thead><tr><th>Rating</th><th>Hotels</th><th>Share</th></tr></thead>
                    <tbody>{rating_rows}</tbody>
                </table>
            </div>
            <div class="bm-panel">
                <h4 class="bm-panel-title">Supply by Sub-market</h4>
                <p class="bm-desc">Geographic distribution of Miami-area hotel inventory.</p>
                <table class="bm-table">
                    <thead><tr><th>Area</th><th>Hotels</th></tr></thead>
                    <tbody>{city_rows}</tbody>
                </table>
            </div>
        </div>"""

    return f"""
    <div class="explainer">
        <strong>Miami Market Benchmarks</strong> — compiled from Kayak, STR/CoStar, HVS, GMCVB, CBRE, and Newmark datasets.
        Full-year 2024 ADR: <strong>${annual_avg:,.2f}</strong> (STR/CoStar, Miami-Dade county-wide).
        Peak: <span class="premium">Feb 2025 $305 ADR, 85.8% occ</span>.
        Trough: <span class="savings">Sep ($200 ADR)</span>.
        2024 visitors: <strong>28.2M (record)</strong>.
    </div>

    <h3 class="hotel-header">&#9312; Miami ADR by Month — Seasonality</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: Kayak (via 30secondcity.com)</span>
        <span class="bm-badge">Miami metro · all hotel classes · 2023-2024</span>
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Monthly ADR + Seasonality Index</h4>
            <p class="bm-desc">Index = monthly ADR / annual avg ($236.67). Miami peak = winter (Jan-Feb-Dec, snowbird season) — opposite of Europe.
            Sep is cheapest month (-15% vs avg). Feb &amp; Dec both index at 1.099.</p>
            <table class="bm-table">
                <thead><tr><th>Month</th><th>Avg ADR</th><th>Index</th><th>Demand</th><th></th></tr></thead>
                <tbody>{season_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9313; Full Historical Series — STR / CoStar (2019-2025F)</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: STR / CoStar · CBRE · GMCVB</span>
        <span class="bm-badge">Miami-Dade hotel market</span>
        <span class="bm-badge">2019 – 2025 forecast</span>
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Annual Occupancy / ADR / RevPAR</h4>
            <p class="bm-desc">2022 was the post-pandemic peak (ADR +30% vs 2019). 2023 normalization (-6.7% RevPAR).
            2024 recovery. 2025 CBRE forecast +0.8% RevPAR; Q1 2025 led all Top 25 US markets.</p>
            <table class="bm-table">
                <thead><tr><th>Year</th><th>Occ</th><th>ADR</th><th>RevPAR</th><th>RevPAR YoY</th><th>Note</th></tr></thead>
                <tbody>{annual_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">2025 Monthly Actuals (STR)</h4>
            <p class="bm-desc">Jan-Mar 2025 actual performance. Feb 2025: $305 ADR (+4.6% YoY), 85.8% occ (+2.3% YoY) — strongest month.
            March 2025 was #1 in all Top 25 US markets by occupancy.</p>
            <table class="bm-table">
                <thead><tr><th>Month</th><th>Occupancy</th><th>ADR</th><th>RevPAR</th><th>Note</th></tr></thead>
                <tbody>{m2025_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9314; Submarket &amp; Regional Comparison</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: STR / HVS · Matthews 3Q24</span>
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Miami Submnarkets — 2019 Baseline</h4>
            <p class="bm-desc">Miami Beach commands 47% ADR premium vs county-wide. Airport has highest occupancy but lowest ADR (transit/commercial demand).
            Downtown/Brickell is fastest-growing submarket for new supply.</p>
            <table class="bm-table">
                <thead><tr><th>Submarket</th><th>Occupancy</th><th>ADR</th><th>RevPAR</th></tr></thead>
                <tbody>{sub_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">South Florida Markets — Trailing 12M (3Q24)</h4>
            <p class="bm-desc">Miami leads South Florida in both ADR ($220) and occupancy (73.3%).
            Palm Beach has higher ADR ($252) but lower occupancy (67.1%).
            CBRE 2025: Miami RevPAR +21.7% above 2019 levels.</p>
            <table class="bm-table">
                <thead><tr><th>Market</th><th>Occ</th><th>ADR</th><th>RevPAR</th><th>Rooms</th></tr></thead>
                <tbody>{sf_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9315; Market Structure &amp; Long-run Trend</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: Matthews 3Q24 · HVS Hotel Valuation Index</span>
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Chain Scale Market Share (Miami)</h4>
            <p class="bm-desc">Miami skews heavily premium: 43% Upscale/Upper Upscale/Luxury combined.
            Pipeline is even more luxury-heavy — Grand Hyatt Miami Beach (800 rooms, 2026), Virgin Hotels Brickell (250), Baccarat (249).</p>
            <table class="bm-table">
                <thead><tr><th>Segment</th><th>Share</th><th></th></tr></thead>
                <tbody>{scale_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">Long-run RevPAR — HVS (2008–2019)</h4>
            <p class="bm-desc">Structural uptrend from $91 (GFC trough 2009) to $154 (2019 pre-pandemic peak).
            2022 surpassed $180. 2025 tracking toward $165-172.</p>
            <table class="bm-table">
                <thead><tr><th>Year</th><th>RevPAR</th><th>YoY</th></tr></thead>
                <tbody>{hvs_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9316; Hotel Booking Demand — Full Dataset Analysis</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: kagglehub jessemostipak/hotel-booking-demand</span>
        <span class="bm-badge">117,429 bookings · European hotels · 2015-2017</span>
        <span class="bm-badge" style="background:rgba(234,179,8,0.15);color:var(--yellow);">&#9888; Proxy — directional signals only, Miami ADR ≈ 2× higher</span>
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Lead Time → ADR + Cancel Rate</h4>
            <p class="bm-desc">Cancel rate rises sharply with lead time: 11% at 0-7d vs 68% at 365d+.
            ADR peaks 8-30d out then declines for very early bookers.
            Weekend premium: +4.3% over weekday ADR.</p>
            <table class="bm-table">
                <thead><tr><th>Lead Time</th><th>Avg ADR</th><th>Median ADR</th><th>Cancel %</th><th>Bookings</th></tr></thead>
                <tbody>{lead_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">Market Segment Performance</h4>
            <p class="bm-desc">Online TA dominates volume (48%) and commands highest ADR ($118). Groups have 62% cancel rate — highest risk.
            Direct bookings have lowest cancel rate (15%).</p>
            <table class="bm-table">
                <thead><tr><th>Segment</th><th>Avg ADR</th><th>Cancel %</th><th>Bookings</th></tr></thead>
                <tbody>{seg_rows}</tbody>
            </table>
        </div>
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Customer Type</h4>
            <p class="bm-desc">Transient (individual) = 75% of volume, highest ADR ($109) but 41% cancel rate.
            Groups = lowest cancel (8%) but lowest ADR ($89).</p>
            <table class="bm-table">
                <thead><tr><th>Type</th><th>Avg ADR</th><th>Cancel %</th></tr></thead>
                <tbody>{ct_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">European vs Miami Seasonality (Month ADR)</h4>
            <p class="bm-desc">Europe peaks Jul-Aug. Miami peaks Jan-Feb-Dec. Completely inverted.
            Sep is low season for both but for opposite reasons: hurricanes (Miami) vs school term (EU).</p>
            <table class="bm-table">
                <thead><tr><th>Month</th><th>EU ADR</th><th>Miami ADR</th><th></th></tr></thead>
                <tbody>{eu_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9317; Miami Airbnb / Short-term Rental (STR) Market</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: Airbtics · Inside Airbnb · AirDNA</span>
        <span class="bm-badge">7,263 active listings (city) · 22,409 (Miami-Dade metro)</span>
        <span class="bm-badge">Nov 2024 – Oct 2025</span>
    </div>
    <div class="explainer" style="margin-bottom:12px">
        Hotel vs STR comparison — Miami proper:
        Hotels: ADR $222 · Occ 73.9% · RevPAR $164 &nbsp;|&nbsp;
        Airbnb: ADR <strong>${airbnb_adr:.0f}</strong> · Occ <strong>{airbnb_occ:.0f}%</strong> · RevPAR <strong>${airbnb_revpar:.0f}</strong>.
        Hotels command <strong>+{(222-airbnb_adr)/airbnb_adr*100:.0f}%</strong> ADR premium over STR.
    </div>
    <div class="bm-grid">
        <div class="bm-panel">
            <h4 class="bm-panel-title">Top Neighborhoods (Airbnb)</h4>
            <p class="bm-desc">Brickell is the top performer: $250 ADR, 75% occ, $70K annual revenue.
            Downtown Miami follows at $241 ADR. STR ADR in premium neighborhoods approaches hotel rates.</p>
            <table class="bm-table">
                <thead><tr><th>Neighborhood</th><th>Listings</th><th>Occ</th><th>ADR</th><th>Annual Rev</th></tr></thead>
                <tbody>{airbnb_nbhd_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">Monthly Revenue Seasonality</h4>
            <p class="bm-desc">Airbnb peak = Feb ($4,485/mo). Trough = Sep ($3,106). Pattern mirrors hotels.
            Relatively stable year-round (+25.3% YoY revenue growth). {airbnb_listings:,} active listings.
            International guests: {airbnb.get("international_guest_pct", 0):.1f}% of bookings.</p>
            <table class="bm-table">
                <thead><tr><th>Month</th><th>Avg Monthly Revenue</th></tr></thead>
                <tbody>{airbnb_monthly_rows}</tbody>
            </table>
        </div>
        <div class="bm-panel">
            <h4 class="bm-panel-title">Property Type Distribution</h4>
            <p class="bm-desc">67% entire homes, 21% condos. Condo inventory directly competes with hotel suites.
            Only 26 hotel rooms listed on Airbnb (hotels primarily on OTAs).</p>
            <table class="bm-table">
                <thead><tr><th>Type</th><th>Listings</th><th>Share</th></tr></thead>
                <tbody>{airbnb_prop_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9318; Miami International Airport (MIA) Traffic</h3>
    <div class="bm-meta">
        <span class="bm-badge">Source: MIA official press releases · miami-airport.com · ACI rankings</span>
        <span class="bm-badge">#1 US intl passengers · #1 US intl cargo · #10 US total pax (2024)</span>
    </div>
    <div class="bm-grid">
        <div class="bm-panel" style="grid-column:1/-1">
            <h4 class="bm-panel-title">Annual Passengers / Cargo / Operations 2019–2025</h4>
            <p class="bm-desc">MIA is the primary demand driver for Airport-submarket hotels.
            2024: record 55.9M passengers (+22% vs 2019), 3.0M cargo tons (record), 485K flight ops.
            Airport ADR historically ~$130 — lowest of Miami submnarkets but highest occupancy (~83%).
            MIA handles 90% of Florida air trade and 40% of combined air+sea trade.</p>
            <table class="bm-table">
                <thead><tr><th>Year</th><th>Total Pax</th><th>Domestic</th><th>International</th><th>Cargo (tons)</th><th>Operations</th><th>Note</th></tr></thead>
                <tbody>{mia_rows}</tbody>
            </table>
        </div>
    </div>

    <h3 class="hotel-header" style="margin-top:32px">&#9319; Miami Hotel Supply — TBO Dataset</h3>
    {tbo_html}
    """


# ── Tab 5: Term Structure ─────────────────────────────────────────────

def _build_term_structure_tab(term_data: dict) -> str:
    """Build Term Structure tab with 6 Chart.js charts + client-side filtering."""
    # Filter to hotels that actually have data
    available = {hid: hdata for hid, hdata in term_data.items() if hdata and hdata.get("combos")}

    if not available:
        return (
            '<div class="no-data" style="padding:60px;text-align:center;">'
            'Term structure data is loading — please refresh in ~30 seconds.</div>'
        )

    # Build hotel dropdown
    hotel_opts = "".join(
        f'<option value="{hid}">{HOTEL_NAMES.get(int(hid), f"Hotel {hid}")}</option>'
        for hid in sorted(available)
    )

    # First hotel's combos for initial combo dropdown
    first_hid = next(iter(sorted(available)))
    first_combos = available[first_hid].get("combos", [])
    combo_opts = "".join(f'<option value="{c}">{c}</option>' for c in first_combos)

    # Serialize all data to JSON (embedded in page, drives all charts client-side)
    # Convert int keys to str for JSON compatibility
    serializable = {str(hid): hdata for hid, hdata in available.items()}
    json_data = json.dumps(serializable, default=str)

    html = (
        '<div class="explainer">'
        '<strong>How to read:</strong> Select a hotel and room/board combination. '
        'All 6 charts update instantly — no page reload. '
        '<span style="color:#6366f1;font-weight:600;">Indigo = 2023</span> &nbsp;'
        '<span style="color:#06b6d4;font-weight:600;">Cyan = 2024</span> &nbsp;'
        '<span style="color:#22c55e;font-weight:600;">Green = 2025</span>. '
        'Only clean observations (n&ge;3 per T-bucket) are plotted.</div>'

        '<div class="ts-filters">'
        f'<label class="ts-label">Hotel<select id="ts-hotel" onchange="tsHotelChange()">{hotel_opts}</select></label>'
        f'<label class="ts-label">Room / Board<select id="ts-combo" onchange="tsRender()">{combo_opts}</select></label>'
        '</div>'

        '<div class="ts-grid">'

        # Chart 1
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9312; Avg Daily &Delta;% by T</div>'
        '<div class="ts-panel-desc">Average daily price change at each lead time. Where 2025 diverges from 2023/2024 marks the structural shift point.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-delta"></canvas></div>'
        '</div>'

        # Chart 2
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9313; Cumulative Path (base&nbsp;=&nbsp;100 at T=90)</div>'
        '<div class="ts-panel-desc">Compounded price path from 90 days out to expiry. Flat then spike = last-minute squeeze. Linear = steady pressure.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-cumul"></canvas></div>'
        '</div>'

        # Chart 3
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9314; Realized Volatility by T</div>'
        '<div class="ts-panel-desc">Std dev of daily % changes. If 2025 spikes earlier than prior years, instability moved forward in the booking window.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-vol"></canvas></div>'
        '</div>'

        # Chart 4
        '<div class="ts-panel">'
        '<div class="ts-panel-title">&#9315; % Days with Positive &Delta;%</div>'
        '<div class="ts-panel-desc">Fraction of days where price rose. At T=7: if 2025 &gt; 70% vs 2023 &lt; 55% — abnormal upward pressure confirmed.</div>'
        '<div class="ts-canvas-wrap"><canvas id="ch-pctup"></canvas></div>'
        '</div>'

        # Chart 5 — full width
        '<div class="ts-panel ts-panel--full">'
        '<div class="ts-panel-title">&#9316; Min Rel-to-Expiry Distribution</div>'
        '<div class="ts-panel-desc">For each completed contract: minimum of (price&minus;S_exp)/S_exp&times;100. '
        'Shows whether large pre-expiry discounts (&minus;10%) still exist or have disappeared.</div>'
        '<div class="ts-canvas-wrap ts-canvas-wrap--bar"><canvas id="ch-minrel"></canvas></div>'
        '</div>'

        # Chart 6 — heatmap, full width
        '<div class="ts-panel ts-panel--full">'
        '<div class="ts-panel-title">&#9317; Heatmap &mdash; Avg Daily &Delta;% (T &times; Year)</div>'
        '<div class="ts-panel-desc">Same data as Chart &#9312; as a color matrix. '
        '<span class="savings">Green</span> = prices falling (buy opportunity). '
        '<span class="premium">Red</span> = prices rising. Hot zones jump out immediately.</div>'
        '<div id="ch-heatmap" class="table-wrap"></div>'
        '</div>'

        '</div>'  # end .ts-grid
    )

    # JavaScript — string concatenation avoids f-string brace conflicts with JS objects
    js = (
        '<script>\n'
        '(function() {\n'
        'const TS_DATA = ' + json_data + ';\n'
        'const YEAR_COLORS = {"2023":"#6366f1","2024":"#06b6d4","2025":"#22c55e"};\n'
        'const YEARS = ["2023","2024","2025"];\n'
        'const CHART_OPTS = {\n'
        '  responsive: true, maintainAspectRatio: false,\n'
        '  plugins: { legend: { labels: { color: "#e4e7ec", padding: 14 } },\n'
        '             tooltip: { mode: "index", intersect: false } },\n'
        '};\n'
        'const AXIS_X = { reverse: true,\n'
        '  title: { display: true, text: "T (days to check-in)", color: "#8b90a0" },\n'
        '  ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } };\n'
        'function yAxis(label) {\n'
        '  return { title: { display: true, text: label, color: "#8b90a0" },\n'
        '           ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } }; }\n'
        'let _ch = {};\n'
        '\n'
        'window.tsHotelChange = function() {\n'
        '  const hotel = document.getElementById("ts-hotel").value;\n'
        '  const combos = (TS_DATA[hotel] || {}).combos || [];\n'
        '  const sel = document.getElementById("ts-combo");\n'
        '  sel.innerHTML = combos.map(c => `<option value="${c}">${c}</option>`).join("");\n'
        '  window.tsRender();\n'
        '};\n'
        '\n'
        'window.tsRender = function() {\n'
        '  const hotel = document.getElementById("ts-hotel").value;\n'
        '  const combo = document.getElementById("ts-combo").value;\n'
        '  const hdata = TS_DATA[hotel];\n'
        '  if (!hdata) return;\n'
        '  const d = (hdata.data || {})[combo];\n'
        '  if (!d) return;\n'
        '  const T = d.t_values;\n'
        '  _line("ch-delta", T, d.avg_delta, "Avg Daily \\u0394%");\n'
        '  _line("ch-cumul", T, d.cumulative, "Normalized Price");\n'
        '  _line("ch-vol",   T, d.volatility, "Std Dev \\u0394%");\n'
        '  _line("ch-pctup", T, d.pct_up, "% Days Positive");\n'
        '  _bar("ch-minrel", d.min_rel_hist);\n'
        '  _heatmap("ch-heatmap", d.heatmap);\n'
        '};\n'
        '\n'
        'function _line(id, tVals, yearData, yLabel) {\n'
        '  if (_ch[id]) { _ch[id].destroy(); }\n'
        '  const ctx = document.getElementById(id);\n'
        '  if (!ctx) return;\n'
        '  _ch[id] = new Chart(ctx, {\n'
        '    type: "line",\n'
        '    data: { labels: tVals,\n'
        '      datasets: YEARS.map(yr => ({\n'
        '        label: yr, data: (yearData || {})[yr] || [],\n'
        '        borderColor: YEAR_COLORS[yr], backgroundColor: "transparent",\n'
        '        tension: 0.3, pointRadius: 4, pointHoverRadius: 6,\n'
        '        spanGaps: true, borderWidth: 2 })) },\n'
        '    options: { ...CHART_OPTS, scales: { x: AXIS_X, y: yAxis(yLabel) } }\n'
        '  });\n'
        '}\n'
        '\n'
        'function _bar(id, histData) {\n'
        '  if (_ch[id]) { _ch[id].destroy(); }\n'
        '  const ctx = document.getElementById(id);\n'
        '  if (!ctx || !histData) return;\n'
        '  _ch[id] = new Chart(ctx, {\n'
        '    type: "bar",\n'
        '    data: { labels: histData.buckets || [],\n'
        '      datasets: YEARS.map(yr => ({\n'
        '        label: yr, data: histData[yr] || [],\n'
        '        backgroundColor: YEAR_COLORS[yr] + "99",\n'
        '        borderColor: YEAR_COLORS[yr], borderWidth: 1 })) },\n'
        '    options: { ...CHART_OPTS,\n'
        '      scales: {\n'
        '        x: { title: { display: true, text: "Min Rel-to-Expiry", color: "#8b90a0" },\n'
        '             ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } },\n'
        '        y: { title: { display: true, text: "# Contracts", color: "#8b90a0" },\n'
        '             ticks: { color: "#8b90a0" }, grid: { color: "#2d3140" } } } }\n'
        '  });\n'
        '}\n'
        '\n'
        'function _heatmap(id, hmData) {\n'
        '  const el = document.getElementById(id);\n'
        '  if (!el || !hmData) return;\n'
        '  const tVals = hmData.t_values || [];\n'
        '  const yrs = hmData.years || [];\n'
        '  const matrix = hmData.matrix || {};\n'
        '  let h = \'<table class="heatmap-table"><thead><tr><th>T</th>\';\n'
        '  yrs.forEach(yr => h += `<th>${yr}</th>`);\n'
        '  h += "</tr></thead><tbody>";\n'
        '  tVals.forEach((T, ti) => {\n'
        '    h += `<tr><td class="t-cell">${T}d</td>`;\n'
        '    yrs.forEach(yr => {\n'
        '      const v = (matrix[yr] || [])[ti];\n'
        '      if (v === null || v === undefined) {\n'
        '        h += \'<td class="empty-cell">&mdash;</td>\';\n'
        '      } else {\n'
        '        const alpha = Math.min(0.15 + Math.abs(v) / 0.5 * 0.55, 0.70);\n'
        '        const bg = v < 0\n'
        '          ? `rgba(34,197,94,${alpha.toFixed(2)})`\n'
        '          : `rgba(239,68,68,${alpha.toFixed(2)})`;\n'
        '        h += `<td style="background:${bg}">${v > 0 ? "+" : ""}${v.toFixed(3)}%</td>`;\n'
        '      }\n'
        '    });\n'
        '    h += "</tr>";\n'
        '  });\n'
        '  h += "</tbody></table>";\n'
        '  el.innerHTML = h;\n'
        '}\n'
        '\n'
        'document.addEventListener("DOMContentLoaded", function() {\n'
        '  if (document.getElementById("ch-delta")) window.tsRender();\n'
        '});\n'
        '})();\n'
        '</script>\n'
    )

    return html + js


# ── Page wrapper ──────────────────────────────────────────────────────

def _empty_page(now: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>YoY Comparison</title></head>
<body style="background:#0f1117;color:#e4e7ec;font-family:sans-serif;padding:40px;text-align:center;">
<h1>No YoY Data Available</h1>
<p>The historical data query is still loading. Please try again in a moment.</p>
<p style="color:#8b90a0;font-size:0.85em;">Generated {now}</p>
</body></html>"""


def _wrap_page(now: str, tab1: str, tab2: str, tab3: str, tab4: str, tab5: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medici — Year-over-Year Price Comparison</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{
    --bg:#0f1117; --surface:#1a1d27; --surface2:#232733;
    --border:#2d3140; --text:#e4e7ec; --text-dim:#8b90a0;
    --accent:#6366f1; --accent2:#818cf8;
    --green:#22c55e; --red:#ef4444; --yellow:#eab308; --cyan:#06b6d4;
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}}
.container{{max-width:1400px;margin:0 auto;padding:0 24px;}}
.header{{background:linear-gradient(135deg,#1e1b4b,#312e81);padding:32px 0;border-bottom:1px solid var(--border);}}
.header h1{{font-size:2em;font-weight:700;background:linear-gradient(135deg,#c7d2fe,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
.header p{{color:var(--text-dim);margin-top:6px;}}
.nav-links{{display:flex;gap:16px;padding:10px 0;}}
.nav-links a{{color:var(--text-dim);text-decoration:none;font-size:0.85em;}}
.nav-links a:hover{{color:var(--accent2);}}

/* Tabs */
.tab-bar{{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;}}
.tab-bar .container{{display:flex;}}
.tab-btn{{padding:14px 24px;background:none;border:none;border-bottom:3px solid transparent;color:var(--text-dim);font-size:0.95em;font-weight:500;cursor:pointer;transition:all 0.2s;font-family:inherit;}}
.tab-btn:hover{{color:var(--text);background:var(--surface2);}}
.tab-btn.active{{color:var(--accent2);border-bottom-color:var(--accent2);background:rgba(99,102,241,0.08);}}
.tab-content{{display:none;padding:24px 0;}}
.tab-content.active{{display:block;}}

/* Hotel headers */
.hotel-header{{font-size:1.2em;font-weight:700;color:var(--accent2);margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--border);}}
.hotel-header:first-child{{margin-top:0;}}

/* Explainer */
.explainer{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin:0 0 20px;font-size:0.9em;color:var(--text-dim);}}
.explainer strong{{color:var(--text);}}

/* Heatmap table */
.table-wrap{{overflow-x:auto;margin-bottom:20px;}}
.heatmap-table{{width:100%;border-collapse:collapse;font-size:0.85em;}}
.heatmap-table th{{background:var(--surface2);padding:10px 12px;text-align:center;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);border-right:1px solid var(--border);white-space:nowrap;}}
.heatmap-table td{{padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);border-right:1px solid var(--border);font-size:0.88em;color:var(--text);position:relative;}}
.heatmap-table tbody tr:hover td{{filter:brightness(1.2);}}
.t-cell{{font-weight:600;color:var(--accent2);text-align:right;background:var(--surface)!important;}}
.empty-cell{{color:var(--text-dim);}}
.n-obs{{display:block;font-size:0.7em;color:var(--text-dim);}}

/* Comparison rows (Tab 2) */
.comp-row{{background:var(--surface);border:1px solid var(--border);border-radius:8px;margin:4px 0;}}
.comp-row-header{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;cursor:pointer;font-size:0.9em;gap:16px;flex-wrap:wrap;}}
.comp-row-header:hover{{background:var(--surface2);}}
.comp-room{{font-weight:600;min-width:100px;}}
.comp-toggle{{color:var(--text-dim);transition:transform 0.2s;}}
.comp-toggle.open{{transform:rotate(90deg);}}
.comp-detail{{padding:0 16px 16px;overflow-x:auto;}}
.comp-table{{width:100%;border-collapse:collapse;font-size:0.85em;}}
.comp-table th{{background:var(--surface2);padding:8px 10px;text-align:left;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);}}
.comp-table td{{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text-dim);}}
.comp-table .row-warning td{{background:rgba(239,68,68,0.06);}}
.comp-table .row-watch td{{background:rgba(234,179,8,0.06);}}

/* Alert pills */
.alert-warning-pill{{background:rgba(239,68,68,0.15);color:var(--red);padding:2px 8px;border-radius:10px;font-size:0.78em;font-weight:600;}}
.alert-watch-pill{{background:rgba(234,179,8,0.15);color:var(--yellow);padding:2px 8px;border-radius:10px;font-size:0.78em;font-weight:600;}}

/* Z-score colors */
.z-warning{{color:var(--red);font-weight:700;}}
.z-watch{{color:var(--yellow);font-weight:600;}}
.z-normal{{color:var(--green);}}

/* Calendar spread (Tab 3) */
.spread-section{{background:var(--surface);border:1px solid var(--border);border-radius:8px;margin:6px 0;}}
.spread-header{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;cursor:pointer;}}
.spread-header:hover{{background:var(--surface2);}}
.month-label{{font-weight:600;color:var(--text);}}

/* Shared */
.savings{{color:var(--green);font-weight:600;}}
.premium{{color:var(--red);font-weight:600;}}
.footer{{text-align:center;padding:32px 0;color:var(--text-dim);font-size:0.85em;border-top:1px solid var(--border);margin-top:24px;}}

/* External Benchmarks (Tab 4) */
.bm-meta{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;}}
.bm-badge{{background:rgba(99,102,241,0.15);color:var(--accent2);border:1px solid rgba(99,102,241,0.3);border-radius:20px;padding:4px 12px;font-size:0.8em;font-weight:600;}}
.bm-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;margin-bottom:24px;}}
.bm-panel{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;}}
.bm-panel-title{{font-size:1em;font-weight:700;color:var(--text);margin-bottom:6px;}}
.bm-desc{{font-size:0.82em;color:var(--text-dim);margin-bottom:12px;line-height:1.4;}}
.bm-table{{width:100%;border-collapse:collapse;font-size:0.83em;}}
.bm-table th{{background:var(--surface2);padding:7px 10px;text-align:left;font-weight:600;color:var(--text);border-bottom:2px solid var(--border);}}
.bm-table td{{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text-dim);}}
.bm-month{{font-weight:600;color:var(--text);white-space:nowrap;}}
.bm-idx,.bm-note{{white-space:nowrap;}}
.bar-bg{{background:var(--surface2);border-radius:4px;height:10px;width:120px;overflow:hidden;}}
.bar-fill{{height:100%;border-radius:4px;}}
.bar-high{{background:var(--red);}}
.bar-mid{{background:var(--cyan);}}
.bar-low{{background:var(--text-dim);}}
.no-data{{color:var(--text-dim);font-style:italic;padding:20px 0;}}

/* Term Structure (Tab 5) */
.ts-filters{{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-radius:10px;margin-bottom:20px;}}
.ts-label{{font-size:0.85em;color:var(--text-dim);display:flex;flex-direction:column;gap:4px;}}
.ts-label select{{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:0.9em;font-family:inherit;cursor:pointer;min-width:200px;}}
.ts-label select:focus{{outline:none;border-color:var(--accent);}}
.ts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
@media(max-width:900px){{.ts-grid{{grid-template-columns:1fr;}}}}
.ts-panel{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;}}
.ts-panel--full{{grid-column:1/-1;}}
.ts-panel-title{{font-size:0.95em;font-weight:700;color:var(--accent2);margin-bottom:4px;}}
.ts-panel-desc{{font-size:0.8em;color:var(--text-dim);margin-bottom:12px;line-height:1.4;}}
.ts-canvas-wrap{{height:280px;position:relative;}}
.ts-canvas-wrap--bar{{height:260px;}}
</style>
</head>
<body>

<div class="header">
<div class="container">
    <h1>Year-over-Year Price Comparison</h1>
    <p>Calendar spread analysis &mdash; how prices behave at each T across multiple years</p>
    <div class="nav-links">
        <a href="/api/v1/salesoffice/insights">Insights</a>
        <a href="/api/v1/salesoffice/options">Options</a>
        <a href="/api/v1/salesoffice/dashboard">Dashboard</a>
        <a href="/api/v1/salesoffice/info">Documentation</a>
    </div>
</div>
</div>

<div class="tab-bar">
<div class="container">
    <button class="tab-btn active" onclick="switchTab('decay',this)">Decay Curve by Year</button>
    <button class="tab-btn" onclick="switchTab('yoy',this)">YoY Comparison</button>
    <button class="tab-btn" onclick="switchTab('spread',this)">Calendar Spread</button>
    <button class="tab-btn" onclick="switchTab('benchmarks',this)">External Benchmarks</button>
    <button class="tab-btn" onclick="switchTab('ts',this)">Term Structure</button>
</div>
</div>

<div class="container">
    <div id="tab-decay" class="tab-content active">{tab1}</div>
    <div id="tab-yoy" class="tab-content">{tab2}</div>
    <div id="tab-spread" class="tab-content">{tab3}</div>
    <div id="tab-benchmarks" class="tab-content">{tab4}</div>
    <div id="tab-ts" class="tab-content">{tab5}</div>
</div>

<div class="footer">
    <p>Medici Price Prediction Engine &mdash; Generated {now}</p>
</div>

<script>
function switchTab(name, btn) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    btn.classList.add('active');
    if (name === 'ts' && typeof tsRender === 'function') {{ tsRender(); }}
}}
function toggle(id) {{
    const el = document.getElementById(id);
    const arrow = document.getElementById('arrow_' + id);
    if (!el) return;
    if (el.style.display === 'none') {{
        el.style.display = 'block';
        if (arrow) arrow.classList.add('open');
    }} else {{
        el.style.display = 'none';
        if (arrow) arrow.classList.remove('open');
    }}
}}
function toggleSpread(id) {{
    const el = document.getElementById('spread_' + id);
    const arrow = document.getElementById('arrow_' + id);
    if (!el) return;
    if (el.style.display === 'none') {{
        el.style.display = 'block';
        if (arrow) arrow.classList.add('open');
    }} else {{
        el.style.display = 'none';
        if (arrow) arrow.classList.remove('open');
    }}
}}
</script>
</body>
</html>"""
