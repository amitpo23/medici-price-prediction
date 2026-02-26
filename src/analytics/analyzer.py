"""SalesOffice price analyzer — statistical analysis + price forecasting.

For each room (Detail):
  - Track price changes over time (from hourly snapshots)
  - Calculate volatility, trend, days until check-in
  - Predict daily price until check-in date
  - Flag rooms with significant price movement

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


def _build_historical_model() -> dict:
    """Build price change model from real historical data in SalesOffice.

    Analyzes all soft-deleted Detail records to learn:
    - Expected TOTAL price change by booking window bucket
    - Per-category volatility
    - Probability of price moving up/down/stable

    Uses track-level total changes (first price -> last price) instead of
    consecutive scan diffs, which produces much more stable predictions.

    Returns model parameters dict or empty dict if not enough data.
    """
    try:
        from src.analytics.collector import load_historical_prices
    except ImportError:
        logger.warning("Cannot import load_historical_prices")
        return {}

    hist = load_historical_prices()
    if hist.empty or len(hist) < 50:
        logger.info("Not enough historical data for model (%d rows)", len(hist))
        return {}

    logger.info("Building prediction model from %d historical records...", len(hist))

    hist["scan_date"] = pd.to_datetime(hist["scan_date"])
    hist["date_from_dt"] = pd.to_datetime(hist["date_from"])
    hist["room_price"] = pd.to_numeric(hist["room_price"], errors="coerce")
    hist = hist.dropna(subset=["room_price", "scan_date", "date_from_dt"])

    # Compute per-track total changes (first -> last observation)
    tracks = hist.groupby(["order_id", "hotel_id", "room_category", "room_board"])

    track_stats = []
    for _key, grp in tracks:
        grp = grp.sort_values("scan_date")
        if len(grp) < 2:
            continue

        first = grp.iloc[0]
        last = grp.iloc[-1]
        first_price = float(first["room_price"])
        last_price = float(last["room_price"])
        if first_price <= 0:
            continue

        days_tracked = (last["scan_date"] - first["scan_date"]).total_seconds() / 86400
        if days_tracked < 0.5:
            continue

        date_from = first["date_from_dt"]
        days_to_checkin_start = (date_from - first["scan_date"]).days
        total_pct = (last_price - first_price) / first_price * 100

        # Cap extreme outliers
        total_pct = max(-50.0, min(50.0, total_pct))

        # Also compute daily rate for this track
        daily_rate = total_pct / days_tracked

        track_stats.append({
            "days_to_checkin": days_to_checkin_start,
            "total_pct": total_pct,
            "daily_rate": daily_rate,
            "days_tracked": days_tracked,
            "category": str(first["room_category"]),
            "scans": len(grp),
        })

    if len(track_stats) < 10:
        logger.info("Not enough tracks for model (%d)", len(track_stats))
        return {}

    ts_df = pd.DataFrame(track_stats)

    # Compute expected total change and volatility by booking window
    buckets = [
        ("0-30", 0, 30),
        ("31-60", 31, 60),
        ("61-90", 61, 90),
        ("90+", 91, 9999),
    ]

    window_stats = {}
    for label, lo, hi in buckets:
        mask = (ts_df["days_to_checkin"] >= lo) & (ts_df["days_to_checkin"] <= hi)
        subset = ts_df[mask]
        if len(subset) >= 3:
            vals = subset["total_pct"]
            up_count = (vals > 1).sum()
            down_count = (vals < -1).sum()
            stable_count = len(vals) - up_count - down_count

            window_stats[label] = {
                "avg_total_pct": round(float(vals.mean()), 2),
                "median_total_pct": round(float(vals.median()), 2),
                "std_total_pct": round(float(vals.std()), 2) if len(vals) > 1 else 5.0,
                "avg_daily_rate": round(float(subset["daily_rate"].mean()), 4),
                "tracks": len(subset),
                "avg_days_tracked": round(float(subset["days_tracked"].mean()), 1),
                "up_pct": round(up_count / len(subset) * 100, 1),
                "down_pct": round(down_count / len(subset) * 100, 1),
                "stable_pct": round(stable_count / len(subset) * 100, 1),
            }

    # Per-category stats
    category_stats = {}
    for cat, grp in ts_df.groupby("category"):
        if len(grp) >= 5:
            category_stats[str(cat)] = {
                "avg_total_pct": round(float(grp["total_pct"].mean()), 2),
                "median_total_pct": round(float(grp["total_pct"].median()), 2),
                "std_total_pct": round(float(grp["total_pct"].std()), 2) if len(grp) > 1 else 5.0,
                "tracks": len(grp),
            }

    overall_avg = float(ts_df["total_pct"].mean())
    overall_median = float(ts_df["total_pct"].median())
    overall_std = float(ts_df["total_pct"].std())

    model = {
        "total_tracks": len(track_stats),
        "window_stats": window_stats,
        "category_stats": category_stats,
        "overall_avg_total_pct": round(overall_avg, 2),
        "overall_median_total_pct": round(overall_median, 2),
        "overall_std_total_pct": round(overall_std, 2),
        "data_source": "historical",
    }

    logger.info(
        "Model built: %d tracks, avg total change %.2f%%, median %.2f%%, windows: %s",
        len(track_stats), overall_avg, overall_median, list(window_stats.keys()),
    )
    return model


# Module-level cache for the historical model (recomputed per analysis run)
_historical_model: dict = {}


def run_analysis() -> dict:
    """Run full analysis on all collected price data.

    Returns a dict with analysis results for display/reporting.
    """
    global _historical_model

    all_snapshots = load_all_snapshots()
    latest = load_latest_snapshot()

    if latest.empty:
        logger.warning("No data to analyze")
        return {"error": "No data collected yet"}

    n_snapshots = all_snapshots["snapshot_ts"].nunique()
    now = datetime.utcnow()

    # Build data-driven model from historical DB data
    try:
        _historical_model = _build_historical_model()
    except Exception as e:
        logger.warning("Failed to build historical model, using defaults: %s", e)
        _historical_model = {}

    results = {
        "run_ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_snapshots": n_snapshots,
        "total_rooms": len(latest),
        "total_hotels": latest["hotel_id"].nunique(),
        "model_info": {
            "data_source": _historical_model.get("data_source", "assumptions"),
            "total_tracks": _historical_model.get("total_tracks", 0),
            "overall_avg_total_pct": _historical_model.get("overall_avg_total_pct", 0),
            "overall_median_total_pct": _historical_model.get("overall_median_total_pct", 0),
        },
    }

    # ── 1. Hotel-level summary ──────────────────────────────────────
    hotel_summary = _analyze_hotels(latest, now)
    results["hotels"] = hotel_summary

    # ── 2. Room-level analysis ──────────────────────────────────────
    room_analysis = _analyze_rooms(all_snapshots, latest, now)
    results["rooms"] = room_analysis

    # ── 3. Price predictions ────────────────────────────────────────
    predictions = _predict_prices(all_snapshots, latest, now)
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
    model_tag = "historical" if _historical_model else "assumptions"
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


def _get_expected_change(days_to_checkin: int, category: str) -> tuple[float, float]:
    """Get expected total % change and std for a room until check-in.

    Uses historical track-level data if available.
    Returns (expected_total_pct, std_total_pct).
    """
    model = _historical_model

    # Default: prices are approximately stable (based on analysis of 232 tracks)
    default_change = -0.5
    default_std = 8.0

    # Determine bucket
    if days_to_checkin <= 30:
        bucket = "0-30"
    elif days_to_checkin <= 60:
        bucket = "31-60"
    elif days_to_checkin <= 90:
        bucket = "61-90"
    else:
        bucket = "90+"

    if model and "window_stats" in model:
        ws = model["window_stats"].get(bucket, {})
        # Use median (more robust than mean for skewed data)
        base_pct = ws.get("median_total_pct", default_change)
        std = ws.get("std_total_pct", default_std)

        # Blend with category-specific stats
        cat_key = str(category).lower()
        cat_stats = model.get("category_stats", {})
        if cat_key in cat_stats:
            cat_pct = cat_stats[cat_key]["median_total_pct"]
            cat_std = cat_stats[cat_key]["std_total_pct"]
            # 60% window, 40% category
            base_pct = base_pct * 0.6 + cat_pct * 0.4
            std = (std + cat_std) / 2

        # Scale by actual days relative to bucket's typical tracking period
        avg_tracked = ws.get("avg_days_tracked", 20)
        if avg_tracked > 0:
            scale = min(days_to_checkin / avg_tracked, 2.0)
            base_pct = base_pct * scale
            std = std * scale ** 0.5

        return base_pct, std

    return default_change, default_std


def _predict_prices(all_snapshots: pd.DataFrame, latest: pd.DataFrame, now: datetime) -> dict:
    """Predict daily prices until check-in for each room.

    Strategy (data-driven, track-level):
    - Computes expected TOTAL change from historical track analysis
    - Distributes change linearly across prediction period
    - Adjusts with observed trend from local snapshots
    - Confidence intervals from historical std
    - Probabilities of up/down/stable from historical data
    """
    predictions = {}
    n_snapshots = all_snapshots["snapshot_ts"].nunique()
    model = _historical_model

    for _, row in latest.iterrows():
        detail_id = int(row["detail_id"])
        current_price = float(row["room_price"])
        date_from = pd.Timestamp(row["date_from"])
        days_to_checkin = (date_from - pd.Timestamp(now)).days
        category = str(row["room_category"]).lower()

        if days_to_checkin <= 0:
            continue

        dates = pd.date_range(start=now.date(), end=date_from, freq="D")
        total_days = len(dates) - 1
        if total_days < 1:
            total_days = 1

        # Get expected total change from historical model
        expected_total_pct, total_std = _get_expected_change(days_to_checkin, category)

        # Observed trend from local snapshots (blend in if available)
        if n_snapshots > 1:
            history = all_snapshots[all_snapshots["detail_id"] == detail_id]
            if len(history) > 1:
                prices = history["room_price"].values
                timestamps = pd.to_datetime(history["snapshot_ts"])
                days_span = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds() / 86400
                if days_span > 0.5 and prices[0] > 0:
                    observed_pct = (prices[-1] - prices[0]) / prices[0] * 100
                    # Project observed rate to full period
                    projected_observed = observed_pct / days_span * days_to_checkin
                    projected_observed = max(-30, min(30, projected_observed))
                    # Blend: 70% historical, 30% observed
                    expected_total_pct = expected_total_pct * 0.7 + projected_observed * 0.3

        # Cap total expected change at reasonable bounds
        expected_total_pct = max(-40, min(40, expected_total_pct))

        # Compute daily step (linear distribution of total change)
        daily_step_pct = expected_total_pct / total_days

        # Get probability info
        prob_info = {"up": 30, "down": 30, "stable": 40}
        if model and "window_stats" in model:
            bucket = "0-30" if days_to_checkin <= 30 else ("31-60" if days_to_checkin <= 60 else ("61-90" if days_to_checkin <= 90 else "90+"))
            ws = model["window_stats"].get(bucket, {})
            if ws:
                prob_info = {
                    "up": ws.get("up_pct", 30),
                    "down": ws.get("down_pct", 30),
                    "stable": ws.get("stable_pct", 40),
                }

        daily_predictions = []
        for i, date in enumerate(dates):
            days_remaining = (date_from - pd.Timestamp(date)).days
            if days_remaining <= 0:
                days_remaining = 1

            # Linear interpolation from current to predicted final price
            progress = i / total_days
            predicted_pct = expected_total_pct * progress
            predicted = current_price * (1 + predicted_pct / 100)

            # Confidence interval widens over time
            uncertainty_pct = total_std * (progress ** 0.5)
            uncertainty = current_price * uncertainty_pct / 100

            dow = date.dayofweek
            daily_predictions.append({
                "date": date.strftime("%Y-%m-%d"),
                "days_remaining": days_remaining,
                "predicted_price": round(predicted, 2),
                "lower_bound": round(predicted - abs(uncertainty), 2),
                "upper_bound": round(predicted + abs(uncertainty), 2),
                "dow": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dow],
            })

        final_price = daily_predictions[-1]["predicted_price"] if daily_predictions else current_price

        predictions[detail_id] = {
            "hotel_name": row["hotel_name"],
            "hotel_id": int(row["hotel_id"]),
            "category": _safe_label(CATEGORIES, row["room_category"]),
            "board": _safe_label(BOARDS, row["room_board"]),
            "current_price": current_price,
            "date_from": str(row["date_from"]),
            "days_to_checkin": days_to_checkin,
            "predicted_checkin_price": round(final_price, 2),
            "expected_change_pct": round(expected_total_pct, 2),
            "probability": prob_info,
            "model_type": "historical" if model else "default",
            "daily": daily_predictions,
        }

    return predictions


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
