"""Generate the system information & documentation page.

Provides a comprehensive, user-friendly HTML page explaining:
- How the prediction engine works
- What each data source provides
- How to read all numbers and metrics
- Glossary of terms
- API reference with live links
"""
from __future__ import annotations

from datetime import datetime

from src.utils.template_engine import render_template

# ── Static content data ──────────────────────────────────────────────

_HOW_IT_WORKS = [
    {"title": "Data Collection (every 3 hours)",
     "desc": "The system queries the SalesOffice database for all active hotel room prices. Each scan records the <strong>room price, category, board type, and check-in date</strong>. This creates a time-series of price observations for every room."},
    {"title": "Build the Decay Curve (from historical data)",
     "desc": 'Using <strong>all historical scan pairs</strong> (consecutive observations of the same room), the system calculates how prices typically change at each value of T (days to check-in). For example: "At T=30, prices typically drop 0.05% per day. At T=7, prices typically rise 0.3% per day." This is smoothed using <strong>Bayesian shrinkage</strong> to handle sparse data.'},
    {"title": "Walk the Forward Curve (day-by-day prediction)",
     "desc": "Starting from today's price, the system <strong>walks forward day by day</strong> along the decay curve, applying the expected daily percentage change at each T value. This is <strong>non-linear</strong> — the predicted path curves based on how hotel prices actually behave at different lead times."},
    {"title": "Apply Enrichments (events, seasonality, demand)",
     "desc": "The curve walk is adjusted by external factors: <strong>events</strong> (like Art Basel or F1 Miami, spread over a ramp-peak-taper window), <strong>seasonality</strong> (monthly adjustment from 117K historical bookings), and <strong>flight demand</strong> (price signals from Kiwi.com flights to Miami)."},
    {"title": "Compute Momentum (real-time signals)",
     "desc": 'From the last few 3-hour scans, the system computes <strong>velocity</strong> (how fast the price is changing over 3h, 24h, and 72h windows) and <strong>acceleration</strong> (is the change speeding up or slowing down?). It compares this to what the decay curve expects — if the room is moving faster than expected, it generates a signal.'},
    {"title": "Detect Regime (is this room behaving normally?)",
     "desc": 'The system compares actual price behavior to the expected path and computes a <strong>z-score</strong> (how many standard deviations away from expected). This classifies each room into a regime: <strong>NORMAL</strong>, <strong>TRENDING UP/DOWN</strong>, <strong>VOLATILE</strong>, or <strong>STALE</strong>.'},
    {"title": "Generate Report & Confidence Intervals",
     "desc": "The final output includes the <strong>predicted price for each day</strong> until check-in, with <strong>80% and 95% confidence bands</strong>. These bands are computed from the historical volatility at each T value — wider bands mean more uncertainty."},
]

_PREDICTION_CARDS = [
    {"title": 'Decay Curve — "How prices typically move"',
     "content": """<p>The decay curve is the <strong>heart of the prediction engine</strong>. It shows the expected daily percentage price change at each T (days to check-in).</p>
    <p><strong>How to read it:</strong></p>
    <ul>
        <li><strong>Negative values</strong> (e.g., -0.05% at T=60) mean prices typically <em>decrease</em> at that lead time</li>
        <li><strong>Positive values</strong> (e.g., +0.3% at T=5) mean prices typically <em>increase</em> as check-in nears</li>
        <li><strong>Volatility</strong> shows how much prices vary — high volatility = less predictable</li>
        <li><strong>Density</strong> shows how much data backs this estimate — "dense" = many observations, "sparse" = few, "extrapolated" = estimated</li>
    </ul>
    <div class="formula">Smoothed daily change = (N * empirical_mean + K * global_mean) / (N + K)
    where K=5 (Bayesian prior strength), N = number of observations at that T</div>
    <p>This means: with few observations, the estimate is pulled toward the global average. With many observations, it trusts the local data more.</p>"""},
    {"title": 'Forward Curve — "Where the price is heading"',
     "content": """<p>The forward curve walks day-by-day from today's price to check-in, applying the decay curve at each step:</p>
    <div class="formula">Day 1: price_1 = current_price * (1 + daily_change_at_T / 100)
    Day 2: price_2 = price_1 * (1 + daily_change_at_T-1 / 100)
    ... and so on until check-in</div>
    <p><strong>How to read the forward curve chart:</strong></p>
    <ul>
        <li><strong>The line</strong> is the predicted price path</li>
        <li><strong>The shaded band</strong> is the confidence interval (80% inner, 95% outer)</li>
        <li><strong>Wider bands</strong> = more uncertainty (further into the future or higher volatility)</li>
        <li><strong>If current price is above the predicted line</strong>, the room is <em>overpriced</em> vs. history</li>
        <li><strong>If current price is below the predicted line</strong>, the room is <em>underpriced</em> vs. history</li>
    </ul>"""},
    {"title": 'Confidence Intervals — "How sure are we?"',
     "content": """<p>Every prediction comes with <strong>80% and 95% confidence bands</strong>:</p>
    <ul>
        <li><strong>80% band</strong>: We expect the actual price to fall within this range 80% of the time</li>
        <li><strong>95% band</strong>: We expect the actual price to fall within this range 95% of the time</li>
        <li><strong>Confidence quality</strong>: rated "high" (many observations, low volatility), "medium", or "low" (sparse data, high volatility)</li>
    </ul>
    <div class="formula">Upper bound = predicted_price * (1 + z * cumulative_volatility / 100)
    Lower bound = predicted_price * (1 - z * cumulative_volatility / 100)
    where z=1.28 for 80%, z=1.96 for 95%</div>"""},
    {"title": "Category & Board Offsets",
     "content": """<p>Different room types and meal plans have different price dynamics:</p>
    <ul>
        <li><strong>Category offset</strong>: How much faster/slower this room type changes vs. average (e.g., suites may change +0.02% faster per day than standard rooms)</li>
        <li><strong>Board offset</strong>: Meal plan impact (RO = room only, BB = bed & breakfast, HB = half board, FB = full board, AI = all inclusive)</li>
    </ul>
    <p>These offsets are <strong>added to the base decay curve</strong> to get the room-specific expected change.</p>"""},
]

_SIGNAL_CARDS = [
    {"title": 'Momentum — "How fast is the price moving?"',
     "content": """<p>Momentum tracks the <strong>speed of price changes</strong> from recent 3-hour scans:</p>
    <ul>
        <li><strong>Velocity 3h</strong>: Price change in the last 3-hour scan window (raw speed)</li>
        <li><strong>Velocity 24h</strong>: Price change rate over 24 hours, annualized to daily (smoothed speed)</li>
        <li><strong>Velocity 72h</strong>: Price change rate over 72 hours (trend speed)</li>
        <li><strong>Acceleration</strong>: Is the velocity <em>increasing or decreasing</em>? Positive = prices accelerating upward</li>
        <li><strong>Momentum vs. Expected</strong>: How does actual velocity compare to what the decay curve predicts?</li>
    </ul>
    <p><strong>Signal types:</strong></p>
    <ul>
        <li><strong>ACCELERATING_UP</strong> — Price rising much faster than expected (momentum &gt; 2x volatility)</li>
        <li><strong>ACCELERATING_DOWN</strong> — Price falling much faster than expected</li>
        <li><strong>ACCELERATING</strong> — Acceleration is high (price changes speeding up)</li>
        <li><strong>DECELERATING</strong> — Acceleration is negative (price changes slowing down)</li>
        <li><strong>NORMAL</strong> — Price moving as expected</li>
        <li><strong>INSUFFICIENT_DATA</strong> — Not enough scans to compute</li>
    </ul>"""},
    {"title": 'Regime Detection — "Is this room behaving normally?"',
     "content": """<p>Regime detection classifies each room's behavior using a <strong>z-score</strong> (standard deviations from expected):</p>
    <ul>
        <li><strong>NORMAL</strong> (z-score between -2 and +2) — Room is following the expected path</li>
        <li><strong>TRENDING_UP</strong> (z-score &gt; +2) — Room is significantly above expected price. Consider selling at this price level.</li>
        <li><strong>TRENDING_DOWN</strong> (z-score &lt; -2) — Room is significantly below expected price. Potential buying opportunity.</li>
        <li><strong>VOLATILE</strong> (recent volatility &gt; 2x expected) — Room is swinging wildly. Prediction reliability is reduced.</li>
        <li><strong>STALE</strong> (no price changes in 16+ scans) — Price hasn't moved. May indicate data issue or no availability.</li>
    </ul>
    <p><strong>Alert levels:</strong></p>
    <ul>
        <li><strong>None</strong> — Everything normal</li>
        <li><strong>Watch</strong> (|z-score| &gt; 1.5) — Worth monitoring</li>
        <li><strong>Warning</strong> (|z-score| &gt; 2.5) — Significant divergence, action may be needed</li>
    </ul>"""},
    {"title": 'Market Data — "Where do we stand vs. the market?"',
     "content": """<p>With <strong>8.5 million search results</strong>, the system benchmarks your hotel prices against the broader market:</p>
    <ul>
        <li><strong>Average Market Price</strong>: What competitors in the same city are charging</li>
        <li><strong>Price Percentile</strong>: Where your price sits vs. all room options (e.g., 30th percentile = cheaper than 70% of options)</li>
        <li><strong>Net vs. Gross Margin</strong>: From 8.3M search results — the difference between what you charge and what you pay (your profit margin)</li>
        <li><strong>Provider Comparison</strong>: Prices from 129 different providers — which provider gives the best rate?</li>
        <li><strong>Price Velocity</strong>: How fast prices are changing across all hotels — is the market moving?</li>
    </ul>"""},
]

_GLOSSARY = [
    {"term": "T (Time to Check-in)", "definition": 'Number of days between the scan date (now) and the check-in date. Like "time to expiration" in options trading. T=30 means check-in is 30 days away.'},
    {"term": "Decay Curve", "definition": "The empirical curve showing expected daily price change at each T value. Built from thousands of historical scan-pair observations with Bayesian smoothing."},
    {"term": "Forward Curve", "definition": "The predicted price path from today to check-in. Generated by walking the decay curve day-by-day with multiplicative compounding."},
    {"term": "Scan / Snapshot", "definition": "A single observation of all room prices at a point in time. The system takes a scan every 3 hours, recording prices for all monitored rooms."},
    {"term": "Momentum", "definition": "The velocity (speed) and acceleration of price changes from recent scans. Computed over 3h, 24h, and 72h windows and compared to expected movement."},
    {"term": "Regime", "definition": "The behavioral classification of a room: NORMAL, TRENDING_UP, TRENDING_DOWN, VOLATILE, or STALE. Based on z-score divergence from expected price path."},
    {"term": "Z-Score", "definition": "How many standard deviations the actual price is from the expected price. Z=0 is exactly on target. Z=+2 means the price is 2 standard deviations above expected (unusually high)."},
    {"term": "Bayesian Shrinkage", "definition": 'A statistical technique that blends sparse local data with a global average. Prevents wild estimates when we have few observations. K=5 means 5 "virtual" observations pull toward the mean.'},
    {"term": "Volatility", "definition": "How much prices vary at a given T value. High volatility = prices swing a lot = wider confidence bands = less certainty in predictions. Minimum floor: 0.5% daily."},
    {"term": "Confidence Band (80% / 95%)", "definition": "The range where we expect the actual future price to fall. 80% band: 4 out of 5 times. 95% band: 19 out of 20 times. Wider = less certain."},
    {"term": "Board Type", "definition": "Meal plan included with the room. RO = Room Only, BB = Bed & Breakfast, HB = Half Board (dinner), FB = Full Board (all meals), AI = All Inclusive."},
    {"term": "Room Category", "definition": "The type of room: Standard, Superior, Deluxe, Suite. Each category has its own price dynamics and offset from the base decay curve."},
    {"term": "Enrichment", "definition": "External data layered onto the base prediction: events (Art Basel, F1), seasonality (monthly pattern), and flight demand (Kiwi.com). Each adds/subtracts a daily % adjustment."},
    {"term": "Gross vs. Net Price", "definition": "Gross = what the customer pays. Net = what you pay the supplier. The difference is your margin. Tracked from 8.3M search results across 129 providers."},
    {"term": "SalesOffice", "definition": "The scanning system that searches hotel availability across multiple providers every 3 hours. It creates Orders (what to scan) and Details (what it found)."},
    {"term": "Price Velocity", "definition": "How fast prices are changing per unit time. Computed from the RoomPriceUpdateLog (82K events). High velocity = market is moving fast."},
]


def _build_api_groups(n_sources: int, total_rows: int) -> list[dict]:
    """Build API reference table groups."""
    base = "/api/v1/salesoffice"
    link = lambda path, text=None: f'<a href="{base}{path}">{text or path}</a>'

    return [
        {"title": "Core Analytics", "columns": ["Endpoint", "Description", "Returns"], "rows": [
            [link("/dashboard"), "Interactive HTML dashboard with charts and predictions", "HTML page with Plotly charts"],
            [link("/data"), "Raw analysis JSON — all predictions, statistics, model info", "Full analysis object"],
            [link("/status"), "System health: snapshots, rooms, hotels, scheduler status", "Status summary"],
            [link("/simple"), "Simplified human-readable analysis", "Simplified JSON"],
            [link("/decay-curve"), "Empirical term structure — expected daily change at each T", "Curve points + category offsets"],
            ["/forward-curve/&lt;detail_id&gt;", "Full forward curve for a specific room with momentum & regime", "Predicted price path + signals"],
            [link("/backtest"), "Backtest prediction accuracy against historical data", "Accuracy metrics"],
        ]},
        {"title": "Enrichment Data", "columns": ["Endpoint", "Description", "Returns"], "rows": [
            [link("/events"), "Miami events calendar — Art Basel, Ultra, F1, etc.", "Event list with impact scores"],
            [link("/flights/demand"), "Flight demand indicator — prices from 5 US cities to Miami", "Flight price data"],
            [link("/knowledge"), "Hotel knowledge base — all 4 hotels", "Hotel profiles + competitor analysis"],
            [link("/benchmarks"), "Booking benchmarks from 117K historical bookings", "Seasonality, ADR, lead time models"],
            [link("/data-sources"), f"List of all {n_sources} data sources with status", "Source registry"],
        ]},
        {"title": "Market Intelligence (28M rows)", "columns": ["Endpoint", "Description", "Data Size"], "rows": [
            [link("/market/db-overview"), "Full database overview — all tables with row counts & sizes", f"72 tables, {total_rows:,} rows"],
            ["/market/search-data?hotel_id=X&days_back=N", "Raw AI search price data for a hotel", "8.5M rows total"],
            [link("/market/search-summary"), "Aggregated market stats per hotel — avg price, min, max, room types", "6,013 hotels"],
            [link("/market/search-results"), "Provider-level pricing — net vs gross, margins, 129 providers", "8.3M rows total"],
            [link("/market/price-updates"), "Every price change event tracked", "82K events"],
            [link("/market/price-velocity"), "Price change speed per hotel — avg, stdev, update frequency", "Per hotel aggregation"],
            ["/market/competitors/&lt;hotel_id&gt;?radius_km=N", "Find competitor hotels within radius using geo coordinates", "745K hotels with lat/long"],
            [link("/market/prebooks"), "Pre-booking data with provider and pricing", "10.7K prebooks"],
            [link("/market/cancellations"), "Cancellation history with reasons", "4.7K cancellations"],
            [link("/market/hotels-geo"), "Hotel metadata with coordinates, stars, country", "745K hotels"],
        ]},
        {"title": "Documentation", "columns": ["Endpoint", "Description"], "rows": [
            [link("/info"), "This page — system information, documentation, and glossary"],
        ]},
    ]


def generate_info_html(data_sources: list[dict], db_stats: dict | None = None) -> str:
    """Generate the full info/documentation HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    active_sources = [s for s in data_sources if s["status"] == "active"]
    planned_sources = [s for s in data_sources if s["status"] == "planned"]

    total_rows = db_stats.get("total_rows", 0) if db_stats else 0
    total_tables = db_stats.get("total_tables", 0) if db_stats else 0
    total_size_mb = db_stats.get("total_size_mb", 0) if db_stats else 0

    return render_template(
        "info.html",
        now=now,
        total_rows=total_rows,
        total_tables=total_tables,
        total_size_mb=total_size_mb,
        n_active=len(active_sources),
        n_total_sources=len(data_sources),
        active_sources=active_sources,
        planned_sources=planned_sources,
        how_it_works_steps=_HOW_IT_WORKS,
        prediction_cards=_PREDICTION_CARDS,
        signal_cards=_SIGNAL_CARDS,
        glossary_terms=_GLOSSARY,
        api_groups=_build_api_groups(len(data_sources), total_rows),
    )
