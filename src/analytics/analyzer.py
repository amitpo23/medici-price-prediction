"""SalesOffice price analyzer — algo-trading style price forecasting.

Models hotel room prices like futures contracts:
- T = days to check-in (time to expiration)
- Decay curve = empirical expected daily price change at each T
- Forward curve = predicted price path from now to check-in
- Momentum = velocity and acceleration from 3-hour scans
- Regime detection = is a room behaving normally or diverging?

For each room (Detail):
  - Walk the decay curve day-by-day (non-linear prediction)
  - Compute momentum from recent 3-hour scans
  - Detect regime (normal, trending, volatile, stale)
  - Confidence intervals from per-T historical volatility

For each hotel:
  - Aggregate room statistics
  - Price distribution analysis
  - Booking window analysis (days until check-in vs price)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.analytics.price_store import (
    load_all_snapshots,
    load_latest_snapshot,
    save_analysis_run,
)
from src.analytics.forward_curve import (
    DecayCurve,
    Enrichments,
    build_decay_curve,
    predict_forward_curve,
)
from src.analytics.momentum import compute_momentum
from src.analytics.regime import detect_regime
from src.analytics.deep_predictor import DeepPredictor
from src.analytics.historical_patterns import HistoricalPatternMiner
from src.analytics.miami_weather import get_weather_forecast
from src.analytics.xotelo_store import get_competitor_pressure

logger = logging.getLogger(__name__)

# Board and category labels (support both int IDs and string names from DB)
BOARDS = {1: "RO", 2: "BB", 3: "HB", 4: "FB", 5: "AI", 6: "CB", 7: "BD"}
CATEGORIES = {1: "Standard", 2: "Superior", 3: "Dormitory", 4: "Deluxe", 12: "Suite"}


def _safe_label(mapping: dict, value) -> str:
    """Get label from mapping, handling both int IDs and string names."""
    if value is None:
        return "Unknown"
    # Try as int first
    try:
        return mapping.get(int(value), str(value))
    except (ValueError, TypeError):
        # Already a string name — return as-is, capitalized
        return str(value).capitalize()


def _build_decay_curve() -> DecayCurve:
    """Build empirical decay curve from historical SalesOffice data.

    Analyzes all soft-deleted Detail records to learn expected daily
    price changes at each T (days to check-in). This replaces the old
    4-bucket model with a continuous T-indexed curve.
    """
    try:
        from src.analytics.collector import load_historical_prices
    except ImportError:
        logger.warning("Cannot import load_historical_prices")
        return DecayCurve()

    hist = load_historical_prices()
    return build_decay_curve(hist)


# Module-level cache for the decay curve (recomputed per analysis run)
_decay_curve: DecayCurve = DecayCurve()

# Module-level cache for flight demand data
_flight_demand_cache: dict = {}

# Module-level cache for events data
_events_cache: dict = {}

# Module-level cache for hotel knowledge data
_knowledge_cache: dict = {}

# Module-level cache for historical patterns (deep predictor)
_historical_patterns_cache: dict = {}


def _load_flight_demand() -> dict:
    """Load flight demand signal from stored Kiwi.com data.

    Returns demand summary dict with indicator (HIGH/MEDIUM/LOW)
    and per-date demand info for prediction adjustment.
    """
    try:
        from src.analytics.flights_store import get_demand_summary, init_flights_db
        init_flights_db()
        summary = get_demand_summary("Miami")
        if summary.get("indicator") == "NO_DATA":
            logger.info("No flight demand data available")
            return {"indicator": "NO_DATA"}
        logger.info(
            "Flight demand: %s (avg $%.0f, %d flights from %d origins)",
            summary["indicator"],
            summary.get("avg_flight_price", 0),
            summary.get("total_flights", 0),
            summary.get("origins_checked", 0),
        )
        return summary
    except Exception as e:
        logger.warning("Failed to load flight demand: %s", e)
        return {"indicator": "NO_DATA"}


def _load_events_data() -> dict:
    """Load events/conferences data for Miami.

    Seeds hardcoded major events and returns summary.
    """
    try:
        from src.analytics.events_store import (
            init_events_db, seed_major_events, get_events_summary,
        )
        init_events_db()
        seed_major_events()
        summary = get_events_summary()
        logger.info(
            "Events loaded: %d total, %d upcoming",
            summary.get("total_events", 0),
            summary.get("upcoming_events", 0),
        )
        return summary
    except Exception as e:
        logger.warning("Failed to load events data: %s", e)
        return {"total_events": 0, "upcoming_events": 0, "next_events": []}


def _load_hotel_knowledge() -> dict:
    """Load hotel knowledge base (competitive landscape from TBO data).

    Returns market summary and per-hotel profiles.
    """
    try:
        from src.analytics.hotel_knowledge import get_knowledge_summary
        summary = get_knowledge_summary()
        total = summary.get("market", {}).get("total_hotels", 0)
        logger.info("Hotel knowledge loaded: %d Miami market hotels", total)
        return summary
    except Exception as e:
        logger.warning("Failed to load hotel knowledge: %s", e)
        return {"market": {"status": "no_data"}, "our_hotels": []}


def _load_booking_benchmarks() -> dict:
    """Load booking behavior benchmarks from hotel-booking-dataset.

    Returns seasonality index, lead time model, city hotel benchmarks.
    """
    try:
        from src.analytics.booking_benchmarks import get_benchmarks_summary
        summary = get_benchmarks_summary()
        if summary.get("status") == "ok":
            logger.info(
                "Booking benchmarks loaded: %d bookings (%s)",
                summary.get("total_bookings", 0),
                summary.get("years", ""),
            )
        return summary
    except Exception as e:
        logger.warning("Failed to load booking benchmarks: %s", e)
        return {"status": "no_data"}


def _load_historical_patterns(hotel_ids: list[int] | None = None) -> dict:
    """Load deep historical patterns for prediction enrichment.

    Mines same-period, lead-time, DOW, event impacts, and monthly
    seasonality from all available historical data sources.

    Returns dict keyed by (hotel_id, category) tuples with pattern dicts.
    """
    global _historical_patterns_cache
    try:
        miner = HistoricalPatternMiner()
        miner.load_data()
        patterns = miner.mine_all(hotel_ids=hotel_ids)
        _historical_patterns_cache = patterns
        logger.info(
            "Historical patterns loaded: %d hotel+category combos",
            len(patterns),
        )
        return patterns
    except Exception as e:
        logger.warning("Failed to load historical patterns: %s", e)
        _historical_patterns_cache = {}
        return {}


def run_analysis() -> dict:
    """Run full analysis on all collected price data.

    Uses algo-trading style forward curve prediction:
    - Builds empirical decay curve from historical T-observations
    - Walks curve day-by-day per room with momentum + enrichments
    - Detects regimes (normal, trending, volatile)

    Returns a dict with analysis results for display/reporting.
    """
    global _decay_curve

    all_snapshots = load_all_snapshots()
    latest = load_latest_snapshot()

    if latest.empty:
        logger.warning("No data to analyze")
        return {"error": "No data collected yet"}

    n_snapshots = all_snapshots["snapshot_ts"].nunique()
    now = datetime.utcnow()

    # Build empirical decay curve from historical DB data
    try:
        _decay_curve = _build_decay_curve()
    except Exception as e:
        logger.warning("Failed to build decay curve, using defaults: %s", e)
        _decay_curve = DecayCurve()

    # Load flight demand signal (external enrichment)
    flight_demand = _load_flight_demand()
    _flight_demand_cache.update(flight_demand)

    # Load events/conferences data
    events_data = _load_events_data()
    _events_cache.update(events_data)

    # Load hotel knowledge base (competitive landscape)
    knowledge_data = _load_hotel_knowledge()
    _knowledge_cache.update(knowledge_data)

    # Load booking behavior benchmarks (seasonality, lead time model)
    benchmarks_data = _load_booking_benchmarks()

    # Load deep historical patterns for ensemble prediction
    hotel_ids = latest["hotel_id"].unique().tolist()
    historical_patterns = _load_historical_patterns(hotel_ids=[int(h) for h in hotel_ids])

    curve_summary = _decay_curve.to_summary()
    results = {
        "run_ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_snapshots": n_snapshots,
        "total_rooms": len(latest),
        "total_hotels": latest["hotel_id"].nunique(),
        "model_info": {
            "data_source": "forward_curve" if _decay_curve.total_tracks > 0 else "default",
            "total_tracks": curve_summary.get("total_tracks", 0),
            "total_observations": curve_summary.get("total_observations", 0),
            "global_mean_daily_pct": curve_summary.get("global_mean_daily_pct", 0),
            "curve_snapshot": curve_summary.get("curve_snapshot", []),
            "category_offsets": curve_summary.get("category_offsets", {}),
        },
        "flight_demand": flight_demand,
        "events": events_data,
        "knowledge": knowledge_data,
        "benchmarks": benchmarks_data,
        "historical_patterns_summary": {
            "loaded": bool(historical_patterns),
            "n_combos": len(historical_patterns),
            "avg_quality": round(
                np.mean([v.get("data_quality", 0) for v in historical_patterns.values()])
                if historical_patterns else 0, 2
            ),
        },
    }

    # ── 1. Hotel-level summary ──────────────────────────────────────
    hotel_summary = _analyze_hotels(latest, now)
    results["hotels"] = hotel_summary

    # ── 2. Room-level analysis ──────────────────────────────────────
    room_analysis = _analyze_rooms(all_snapshots, latest, now)
    results["rooms"] = room_analysis

    # ── 3. Price predictions ────────────────────────────────────────
    #   Load historical scan data from medici-db for scan_history tracking
    try:
        from src.analytics.collector import load_scan_history
        scan_history_df = load_scan_history()
    except Exception as e:
        logger.warning("Failed to load scan history from medici-db: %s", e)
        scan_history_df = pd.DataFrame()

    predictions = _predict_prices(all_snapshots, latest, now, scan_history_df)
    results["predictions"] = predictions

    # ── 4. Booking window analysis ──────────────────────────────────
    booking_window = _analyze_booking_window(latest, now)
    results["booking_window"] = booking_window

    # ── 5. Price change detection (if multiple snapshots) ───────────
    if n_snapshots > 1:
        changes = _detect_price_changes(all_snapshots)
        results["price_changes"] = changes
    else:
        results["price_changes"] = {
            "note": "Need 2+ snapshots to detect changes. Next snapshot in ~1 hour.",
            "changes": [],
        }

    # ── 6. Overall statistics ───────────────────────────────────────
    stats = _overall_statistics(latest, now)
    results["statistics"] = stats

    # Save run record
    model_tag = "forward_curve" if _decay_curve.total_tracks > 0 else "default"
    summary = (
        f"{len(latest)} rooms, {latest['hotel_id'].nunique()} hotels, "
        f"avg ${latest['room_price'].mean():.0f}, {n_snapshots} snapshots, model={model_tag}"
    )
    save_analysis_run(len(latest), latest["hotel_id"].nunique(), latest["room_price"].mean(), summary)

    return results


def _analyze_hotels(latest: pd.DataFrame, now: datetime) -> list[dict]:
    """Per-hotel summary statistics."""
    hotels = []
    for hotel_id, grp in latest.groupby("hotel_id"):
        date_from_vals = pd.to_datetime(grp["date_from"])
        days_to_checkin = (date_from_vals - pd.Timestamp(now)).dt.days

        hotels.append({
            "hotel_id": int(hotel_id),
            "hotel_name": grp["hotel_name"].iloc[0],
            "total_rooms": len(grp),
            "price_min": round(float(grp["room_price"].min()), 2),
            "price_max": round(float(grp["room_price"].max()), 2),
            "price_mean": round(float(grp["room_price"].mean()), 2),
            "price_median": round(float(grp["room_price"].median()), 2),
            "price_std": round(float(grp["room_price"].std()), 2) if len(grp) > 1 else 0,
            "categories": sorted(grp["room_category"].unique().tolist()),
            "boards": sorted(grp["room_board"].unique().tolist()),
            "date_range": f"{grp['date_from'].min()} → {grp['date_to'].max()}",
            "min_days_to_checkin": int(days_to_checkin.min()) if len(days_to_checkin) > 0 else 0,
            "max_days_to_checkin": int(days_to_checkin.max()) if len(days_to_checkin) > 0 else 0,
        })

    return sorted(hotels, key=lambda h: h["total_rooms"], reverse=True)


def _analyze_rooms(all_snapshots: pd.DataFrame, latest: pd.DataFrame, now: datetime) -> list[dict]:
    """Per-room detailed analysis."""
    rooms = []
    n_snapshots = all_snapshots["snapshot_ts"].nunique()

    for _, row in latest.iterrows():
        detail_id = int(row["detail_id"])
        date_from = pd.Timestamp(row["date_from"])
        days_to_checkin = (date_from - pd.Timestamp(now)).days

        room_info = {
            "detail_id": detail_id,
            "order_id": int(row["order_id"]),
            "hotel_id": int(row["hotel_id"]),
            "hotel_name": row["hotel_name"],
            "category": _safe_label(CATEGORIES, row["room_category"]),
            "board": _safe_label(BOARDS, row["room_board"]),
            "current_price": round(float(row["room_price"]), 2),
            "date_from": str(row["date_from"]),
            "date_to": str(row["date_to"]),
            "days_to_checkin": days_to_checkin,
            "is_processed": bool(row["is_processed"]),
        }

        # Price history from snapshots
        if n_snapshots > 1:
            history = all_snapshots[all_snapshots["detail_id"] == detail_id].copy()
            if len(history) > 1:
                prices = history["room_price"].values
                room_info["price_history"] = {
                    "snapshots": len(history),
                    "first_price": round(float(prices[0]), 2),
                    "last_price": round(float(prices[-1]), 2),
                    "change_abs": round(float(prices[-1] - prices[0]), 2),
                    "change_pct": round(float((prices[-1] - prices[0]) / prices[0] * 100), 2) if prices[0] > 0 else 0,
                    "volatility": round(float(np.std(prices)), 2),
                    "trend": "up" if prices[-1] > prices[0] else ("down" if prices[-1] < prices[0] else "stable"),
                }

        rooms.append(room_info)

    return rooms


def _build_enrichments(date_from, now: datetime, hotel_id: int | None = None,
                       *,
                       _shared: dict | None = None) -> Enrichments:
    """Build enrichments object from all external signals.

    Args:
        _shared: Pre-computed shared data (weather, seasonality, events, snapshot)
                 to avoid redundant I/O when called in a loop.
    """
    # Use pre-computed shared data if provided (batch optimization)
    if _shared is None:
        _shared = _compute_shared_enrichment_data()

    events_list = _shared.get("events_list", [])
    seasonality = _shared.get("seasonality", {})
    weather_signal = _shared.get("weather_signal", {})
    latest_snap = _shared.get("latest_snapshot")

    # Competitor pressure from Xotelo (no key required)
    competitor_pressure = 0.0
    if hotel_id:
        try:
            if latest_snap is not None and not latest_snap.empty and "room_price" in latest_snap.columns:
                hotel_snap = latest_snap[latest_snap["hotel_id"] == hotel_id]
                if not hotel_snap.empty:
                    our_adr = float(hotel_snap["room_price"].median())
                    competitor_pressure = get_competitor_pressure(hotel_id, our_adr)
        except Exception:
            pass

    return Enrichments(
        demand_indicator=_flight_demand_cache.get("indicator", "NO_DATA"),
        events=events_list,
        seasonality_index=seasonality,
        weather_signal=weather_signal,
        competitor_pressure=competitor_pressure,
    )


def _compute_shared_enrichment_data() -> dict:
    """Compute expensive enrichment data once (events, seasonality, weather, snapshot).

    Called once before a batch prediction loop instead of per-room.
    """
    # Map hotel_impact levels to multipliers
    impact_mults = {
        "extreme": 0.40, "very_high": 0.25, "high": 0.15,
        "moderate": 0.08, "low": 0.03,
    }

    # Collect upcoming events from cached events data
    events_list = []
    try:
        for ev in _events_cache.get("next_events", []):
            impact_level = ev.get("hotel_impact", "low")
            events_list.append({
                "start_date": ev.get("start_date", ""),
                "end_date": ev.get("end_date", ""),
                "multiplier": impact_mults.get(impact_level, 0),
                "name": ev.get("name", ""),
            })
    except Exception:
        pass

    # Seasonality index (from JSON file, read once)
    seasonality = {}
    try:
        from src.analytics.booking_benchmarks import get_seasonality_all
        seasonality = get_seasonality_all()
    except Exception:
        pass

    # Weather signal (Open-Meteo + NHC, single HTTP call)
    weather_signal: dict[str, float] = {}
    try:
        weather_signal = get_weather_forecast(days=14)
    except Exception:
        pass

    # Latest price snapshot (for competitor pressure computation)
    latest_snapshot = None
    try:
        latest_snapshot = load_latest_snapshot()
    except Exception:
        pass

    return {
        "events_list": events_list,
        "seasonality": seasonality,
        "weather_signal": weather_signal,
        "latest_snapshot": latest_snapshot,
    }


def _predict_prices(all_snapshots: pd.DataFrame, latest: pd.DataFrame,
                     now: datetime,
                     scan_history_df: pd.DataFrame | None = None) -> dict:
    """Predict daily prices until check-in using deep ensemble prediction.

    Combines 3 signals via weighted ensemble:
    1. Forward curve walk (decay curve day-by-day with momentum + enrichments)
    2. Historical pattern analysis (same-period, lead-time, DOW, events)
    3. ML forecast from Darts models (if available)

    Falls back to forward-curve-only if deep predictor fails for any room.
    """
    predictions = {}
    curve = _decay_curve

    # Initialize DeepPredictor with historical patterns and ML models dir
    try:
        from config.settings import MODELS_DIR
        ml_models_dir = MODELS_DIR
    except Exception:
        ml_models_dir = None

    deep_predictor = DeepPredictor(
        decay_curve=curve,
        historical_patterns=_historical_patterns_cache,
        ml_models_dir=ml_models_dir,
    )

    # Pre-compute shared enrichment data ONCE (weather API, seasonality JSON, etc.)
    # instead of making HTTP calls per-room (was 1143 HTTP calls → now 1)
    shared_data = _compute_shared_enrichment_data()

    # Pre-compute enrichments per hotel_id (only competitor pressure varies)
    unique_hotel_ids = latest["hotel_id"].unique()
    enrichments_by_hotel: dict[int, Enrichments] = {}
    for hid in unique_hotel_ids:
        enrichments_by_hotel[int(hid)] = _build_enrichments(
            None, now, hotel_id=int(hid), _shared=shared_data,
        )

    logger.info("Pre-computed enrichments for %d hotels (1 weather API call instead of %d)",
                len(unique_hotel_ids), len(latest))

    for _, row in latest.iterrows():
        detail_id = int(row["detail_id"])
        current_price = float(row["room_price"])
        hotel_id = int(row["hotel_id"])
        date_from = pd.Timestamp(row["date_from"])
        days_to_checkin = (date_from - pd.Timestamp(now)).days
        category = str(row["room_category"]).lower()
        board = str(row["room_board"]).lower() if row["room_board"] else "unknown"

        if days_to_checkin <= 0:
            continue

        # Compute momentum from 3-hour scan history
        expected_daily = curve.get_daily_change(days_to_checkin)
        vol_at_t = curve.get_volatility(days_to_checkin)
        mom = compute_momentum(detail_id, all_snapshots, expected_daily, vol_at_t)

        # Detect regime (normal, trending, volatile, stale)
        regime = detect_regime(
            detail_id, current_price, all_snapshots, curve, category, board,
        )

        # Use pre-computed enrichments for this hotel
        enrichments = enrichments_by_hotel.get(hotel_id, Enrichments())

        # Try deep ensemble prediction first
        try:
            deep_result = deep_predictor.predict(
                detail_id=detail_id,
                hotel_id=hotel_id,
                current_price=current_price,
                days_to_checkin=days_to_checkin,
                category=category,
                board=board,
                date_from=date_from,
                all_snapshots=all_snapshots,
                enrichments=enrichments,
                momentum_state=mom.to_dict(),
                regime_state=regime.to_dict(),
            )

            # Add fields that analyzer manages (labels, momentum, regime)
            deep_result["momentum"] = mom.to_dict()
            deep_result["regime"] = regime.to_dict()
            deep_result["hotel_name"] = row["hotel_name"]
            deep_result["hotel_id"] = hotel_id
            deep_result["category"] = _safe_label(CATEGORIES, row["room_category"])
            deep_result["board"] = _safe_label(BOARDS, row["room_board"])

            predictions[detail_id] = deep_result

        except Exception as e:
            logger.warning(
                "Deep predictor failed for detail %d, falling back to forward curve: %s",
                detail_id, e,
            )
            # Fallback: forward-curve-only prediction (original logic)
            predictions[detail_id] = _predict_forward_curve_only(
                row, detail_id, current_price, hotel_id, date_from,
                days_to_checkin, category, board, curve, mom, regime,
                enrichments, all_snapshots,
            )

        # Attach scan history for every prediction (from medici-db)
        predictions[detail_id]["scan_history"] = _build_scan_history(
            int(row["order_id"]), int(row["hotel_id"]),
            row["room_category"], row["room_board"],
            scan_history_df if scan_history_df is not None else pd.DataFrame(),
        )

    return predictions


def _build_scan_history(order_id: int, hotel_id: int,
                        room_category, room_board,
                        scan_history_df: pd.DataFrame) -> dict:
    """Build actual scan history for a room from medici-db historical data.

    Matches by (order_id, hotel_id, room_category, room_board) across all
    3-hourly scans since tracking started (Feb 23).

    Returns metrics about observed price behavior:
    - first/last scan price and dates
    - count of actual price drops and rises between consecutive scans
    - total actual decline/increase amounts
    - change from first scan to current price
    """
    _empty = {
        "scan_snapshots": 0,
        "first_scan_date": None,
        "first_scan_price": None,
        "latest_scan_date": None,
        "latest_scan_price": None,
        "scan_price_change": 0.0,
        "scan_price_change_pct": 0.0,
        "scan_actual_drops": 0,
        "scan_actual_rises": 0,
        "scan_actual_unchanged": 0,
        "scan_total_drop_amount": 0.0,
        "scan_total_rise_amount": 0.0,
        "scan_max_single_drop": 0.0,
        "scan_max_single_rise": 0.0,
        "scan_trend": "no_data",
    }

    if scan_history_df is None or scan_history_df.empty:
        return _empty

    # Match by natural key: same order + hotel + room type
    mask = (
        (scan_history_df["order_id"] == order_id)
        & (scan_history_df["hotel_id"] == hotel_id)
        & (scan_history_df["room_category"] == room_category)
        & (scan_history_df["room_board"] == room_board)
    )
    history = scan_history_df[mask].copy()

    if history.empty:
        return _empty

    # Aggregate per scan_date (take min price if multiple entries per scan)
    history["scan_date"] = pd.to_datetime(history["scan_date"], errors="coerce")
    agg = (
        history
        .groupby("scan_date")
        .agg(room_price=("room_price", "min"))
        .reset_index()
        .sort_values("scan_date")
    )

    if len(agg) < 1:
        return _empty

    prices = agg["room_price"].values.astype(float)
    scan_dates = agg["scan_date"].values

    first_price = float(prices[0])
    last_price = float(prices[-1])
    first_date = str(scan_dates[0])
    last_date = str(scan_dates[-1])

    drops = 0
    rises = 0
    unchanged = 0
    total_drop = 0.0
    total_rise = 0.0
    max_drop = 0.0
    max_rise = 0.0

    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff < -0.01:
            drops += 1
            amt = abs(diff)
            total_drop += amt
            if amt > max_drop:
                max_drop = amt
        elif diff > 0.01:
            rises += 1
            total_rise += diff
            if diff > max_rise:
                max_rise = diff
        else:
            unchanged += 1

    change = last_price - first_price
    change_pct = (change / first_price * 100) if first_price > 0 else 0.0

    if change < -0.5:
        trend = "down"
    elif change > 0.5:
        trend = "up"
    else:
        trend = "stable"

    # Build price series for charting (date -> price list)
    scan_price_series = [
        {"date": str(scan_dates[i])[:16], "price": round(float(prices[i]), 2)}
        for i in range(len(prices))
    ]

    return {
        "scan_snapshots": len(agg),
        "first_scan_date": first_date,
        "first_scan_price": round(first_price, 2),
        "latest_scan_date": last_date,
        "latest_scan_price": round(last_price, 2),
        "scan_price_change": round(change, 2),
        "scan_price_change_pct": round(change_pct, 2),
        "scan_actual_drops": drops,
        "scan_actual_rises": rises,
        "scan_actual_unchanged": unchanged,
        "scan_total_drop_amount": round(total_drop, 2),
        "scan_total_rise_amount": round(total_rise, 2),
        "scan_max_single_drop": round(max_drop, 2),
        "scan_max_single_rise": round(max_rise, 2),
        "scan_trend": trend,
        "scan_price_series": scan_price_series,
    }


def _predict_forward_curve_only(
    row,
    detail_id: int,
    current_price: float,
    hotel_id: int,
    date_from,
    days_to_checkin: int,
    category: str,
    board: str,
    curve: DecayCurve,
    mom,
    regime,
    enrichments: Enrichments,
    all_snapshots: pd.DataFrame,
) -> dict:
    """Fallback: original forward-curve-only prediction."""
    fwd = predict_forward_curve(
        detail_id=detail_id,
        hotel_id=hotel_id,
        current_price=current_price,
        current_t=days_to_checkin,
        category=category,
        board=board,
        curve=curve,
        momentum_state=mom.to_dict(),
        enrichments=enrichments,
    )

    cancel_prob = None
    try:
        from src.analytics.booking_benchmarks import get_cancel_probability
        cancel_prob = get_cancel_probability(days_to_checkin)
    except Exception:
        pass

    prob_info = curve.get_probabilities(days_to_checkin)
    final_price = fwd.points[-1].predicted_price if fwd.points else current_price
    cumulative_pct = fwd.points[-1].cumulative_change_pct if fwd.points else 0.0

    daily_predictions = []
    for pt in fwd.points:
        daily_predictions.append({
            "date": pt.date,
            "days_remaining": pt.t,
            "predicted_price": pt.predicted_price,
            "lower_bound": pt.lower_bound,
            "upper_bound": pt.upper_bound,
            "dow": pt.dow,
        })

    return {
        "hotel_name": row["hotel_name"],
        "hotel_id": hotel_id,
        "category": _safe_label(CATEGORIES, row["room_category"]),
        "board": _safe_label(BOARDS, row["room_board"]),
        "current_price": current_price,
        "date_from": str(row["date_from"]),
        "days_to_checkin": days_to_checkin,
        "predicted_checkin_price": round(final_price, 2),
        "expected_change_pct": round(cumulative_pct, 2),
        "probability": prob_info,
        "cancel_probability": round(cancel_prob, 3) if cancel_prob is not None else None,
        "model_type": "forward_curve" if curve.total_tracks > 0 else "default",
        "prediction_method": "forward_curve_only",
        "daily": daily_predictions,
        "momentum": mom.to_dict(),
        "regime": regime.to_dict(),
        "confidence_quality": fwd.confidence_quality,
        "forward_curve": [
            {
                "date": pt.date,
                "t": pt.t,
                "predicted_price": pt.predicted_price,
                "daily_change_pct": pt.daily_change_pct,
                "cumulative_change_pct": pt.cumulative_change_pct,
                "lower_bound": pt.lower_bound,
                "upper_bound": pt.upper_bound,
                "volatility_at_t": pt.volatility_at_t,
                "event_adj_pct": pt.event_adj_pct,
                "season_adj_pct": pt.season_adj_pct,
                "demand_adj_pct": pt.demand_adj_pct,
                "momentum_adj_pct": pt.momentum_adj_pct,
            }
            for pt in fwd.points
        ],
    }


def _analyze_booking_window(latest: pd.DataFrame, now: datetime) -> dict:
    """Analyze price vs days-to-checkin relationship."""
    latest = latest.copy()
    latest["days_to_checkin"] = (
        pd.to_datetime(latest["date_from"]) - pd.Timestamp(now)
    ).dt.days

    # Bucket by time windows
    buckets = [
        ("0-30 days", 0, 30),
        ("31-60 days", 31, 60),
        ("61-90 days", 61, 90),
        ("90+ days", 91, 999),
    ]

    window_analysis = []
    for label, low, high in buckets:
        mask = (latest["days_to_checkin"] >= low) & (latest["days_to_checkin"] <= high)
        subset = latest[mask]
        if len(subset) > 0:
            window_analysis.append({
                "window": label,
                "rooms": len(subset),
                "avg_price": round(float(subset["room_price"].mean()), 2),
                "min_price": round(float(subset["room_price"].min()), 2),
                "max_price": round(float(subset["room_price"].max()), 2),
            })

    # Price-days correlation
    corr = latest[["days_to_checkin", "room_price"]].corr().iloc[0, 1]

    return {
        "windows": window_analysis,
        "price_days_correlation": round(float(corr), 4) if not pd.isna(corr) else 0,
        "interpretation": (
            "Negative correlation = prices rise as check-in approaches"
            if corr < -0.1 else
            "Positive correlation = prices drop as check-in approaches"
            if corr > 0.1 else
            "No clear relationship between booking window and price"
        ),
    }


def _detect_price_changes(all_snapshots: pd.DataFrame) -> dict:
    """Detect significant price changes between snapshots."""
    snapshots_sorted = all_snapshots.sort_values(["detail_id", "snapshot_ts"])
    timestamps = sorted(snapshots_sorted["snapshot_ts"].unique())

    if len(timestamps) < 2:
        return {"changes": [], "note": "Need 2+ snapshots"}

    prev_ts = timestamps[-2]
    curr_ts = timestamps[-1]

    prev = snapshots_sorted[snapshots_sorted["snapshot_ts"] == prev_ts].set_index("detail_id")
    curr = snapshots_sorted[snapshots_sorted["snapshot_ts"] == curr_ts].set_index("detail_id")

    common = prev.index.intersection(curr.index)
    changes = []

    for detail_id in common:
        old_price = float(prev.loc[detail_id, "room_price"])
        new_price = float(curr.loc[detail_id, "room_price"])
        if old_price != new_price and old_price > 0:
            pct = (new_price - old_price) / old_price * 100
            changes.append({
                "detail_id": int(detail_id),
                "hotel_name": curr.loc[detail_id, "hotel_name"],
                "date_from": str(curr.loc[detail_id, "date_from"]),
                "old_price": round(old_price, 2),
                "new_price": round(new_price, 2),
                "change_abs": round(new_price - old_price, 2),
                "change_pct": round(pct, 2),
                "direction": "UP" if pct > 0 else "DOWN",
            })

    changes.sort(key=lambda c: abs(c["change_pct"]), reverse=True)

    return {
        "period": f"{prev_ts} → {curr_ts}",
        "total_changes": len(changes),
        "price_increases": sum(1 for c in changes if c["direction"] == "UP"),
        "price_decreases": sum(1 for c in changes if c["direction"] == "DOWN"),
        "biggest_change": changes[0] if changes else None,
        "changes": changes[:20],  # top 20
    }


def _overall_statistics(latest: pd.DataFrame, now: datetime) -> dict:
    """Overall portfolio statistics."""
    latest = latest.copy()
    latest["days_to_checkin"] = (
        pd.to_datetime(latest["date_from"]) - pd.Timestamp(now)
    ).dt.days

    prices = latest["room_price"]

    return {
        "total_rooms": len(latest),
        "total_hotels": latest["hotel_id"].nunique(),
        "price_mean": round(float(prices.mean()), 2),
        "price_median": round(float(prices.median()), 2),
        "price_std": round(float(prices.std()), 2),
        "price_min": round(float(prices.min()), 2),
        "price_max": round(float(prices.max()), 2),
        "price_q25": round(float(prices.quantile(0.25)), 2),
        "price_q75": round(float(prices.quantile(0.75)), 2),
        "total_inventory_value": round(float(prices.sum()), 2),
        "avg_days_to_checkin": round(float(latest["days_to_checkin"].mean()), 1),
        "nearest_checkin": str(latest.loc[latest["days_to_checkin"].idxmin(), "date_from"]) if len(latest) > 0 else "",
        "farthest_checkin": str(latest.loc[latest["days_to_checkin"].idxmax(), "date_from"]) if len(latest) > 0 else "",
        "by_category": {
            _safe_label(CATEGORIES, k): {
                "count": len(v),
                "avg_price": round(float(v["room_price"].mean()), 2),
            }
            for k, v in latest.groupby("room_category")
        },
        "by_board": {
            _safe_label(BOARDS, k): {
                "count": len(v),
                "avg_price": round(float(v["room_price"].mean()), 2),
            }
            for k, v in latest.groupby("room_board")
        },
    }
