"""Options trading engine — treats hotel room contracts as options with expiry = check-in.

Two main outputs:
  1. compute_next_day_signals(analysis)  → ex-ante CALL/PUT/NONE signal per active contract
  2. build_expiry_metrics(df)            → ex-post breach/drawdown analytics for last 6M
"""
from __future__ import annotations

import math
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Contract key columns (uniquely identify a comparable room product)
CONTRACT_KEY = ["hotel_id", "checkin_date", "category", "board"]

from config.constants import SIGNAL_THRESHOLD_HIGH, SIGNAL_THRESHOLD_MEDIUM

# Thresholds
P_THRESHOLD_HIGH = SIGNAL_THRESHOLD_HIGH   # High-confidence signal
P_THRESHOLD_MED  = SIGNAL_THRESHOLD_MEDIUM   # Medium-confidence signal
BREACH_THRESHOLDS = (-5.0, -10.0)


# ── Math helpers ──────────────────────────────────────────────────────

def _normal_cdf(x: float) -> float:
    """Normal CDF using math.erf — no scipy required."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _count_crossings(values: np.ndarray, threshold: float) -> int:
    """Count entry events — transitions from ABOVE threshold to AT/BELOW threshold.

    Chronological order assumed (T descending = earliest scan first).
    An 'event' = one crossing, not consecutive days below the same threshold.
    """
    if len(values) < 1:
        return 0
    below = values <= threshold
    if len(values) == 1:
        return int(below[0])
    # Transitions: False → True  (above → below)
    transitions = int(np.sum(np.diff(below.astype(np.int8)) > 0))
    # If the very first observation is already below threshold, count that as an event
    first_below = int(below[0])
    return transitions + first_below


# ── AI_Search competitor & historical data ───────────────────────────

def _load_competitor_zone_averages(predictions: dict) -> dict[int, float]:
    """Load zone average prices from cached AI_Search data (nightly refresh).

    Reads from analytical_cache SQLite (populated by nightly _refresh_ai_search_cache).
    Falls back to prediction-based averages if cache unavailable.
    Returns {hotel_id: zone_avg_price} for each hotel in predictions.
    """
    try:
        from config.hotel_segments import HOTEL_SEGMENTS
    except ImportError:
        return {}

    # Try reading from analytical cache (nightly refresh)
    try:
        from src.analytics.analytical_cache import AnalyticalCache
        import json as _json
        cache = AnalyticalCache()
        with cache._get_conn() as c:
            row = c.execute(
                "SELECT status FROM trade_journal WHERE id = 999999"
            ).fetchone()
        if row and row[0]:
            cached = _json.loads(row[0])
            zone_averages = cached.get("zone_averages", {})
            if zone_averages:
                result: dict[int, float] = {}
                for pred in predictions.values():
                    hid = pred.get("hotel_id")
                    if not hid:
                        continue
                    seg = HOTEL_SEGMENTS.get(int(hid))
                    if seg and seg["zone"] in zone_averages:
                        result[int(hid)] = zone_averages[seg["zone"]]
                if result:
                    logger.info("AI_Search competitor: loaded from cache for %d hotels", len(result))
                    return result
    except Exception as exc:
        logger.debug("AI_Search cache read failed, using fallback: %s", exc)

    # Fallback: return empty (prediction-based will be used in compute_next_day_signals)
    return {}

    # --- Original AI_Search direct query (disabled — too heavy for B2) ---
    # Collect unique checkin dates from predictions
    checkin_dates: set[str] = set()
    hotel_ids_in_preds: set[int] = set()
    for pred in predictions.values():
        date_from = pred.get("date_from", "")
        if isinstance(date_from, str) and len(date_from) >= 10:
            checkin_dates.add(date_from[:10])
        elif hasattr(date_from, "strftime"):
            checkin_dates.add(date_from.strftime("%Y-%m-%d"))
        hid = pred.get("hotel_id")
        if hid:
            hotel_ids_in_preds.add(int(hid))

    if not checkin_dates:
        return {}

    # Build SQL: query AI_Search for Miami hotels, matching StayFrom dates, last 3 days
    # Use TOP to prevent huge result sets and set query timeout
    date_list = ", ".join(f"'{d}'" for d in sorted(checkin_dates))
    sql = f"""
        SELECT TOP 500 HotelId, AVG(PriceAmount) as avg_price
        FROM AI_Search_HotelData
        WHERE CityName = 'Miami'
          AND StayFrom IN ({date_list})
          AND UpdatedAt > DATEADD(day, -3, GETUTCDATE())
          AND PriceAmount > 0 AND PriceAmount < 10000
        GROUP BY HotelId
    """

    try:
        conn = get_pyodbc_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
    except Exception as exc:
        logger.warning("AI_Search competitor query failed (non-fatal): %s", exc)
        return {}

    if not rows:
        logger.debug("AI_Search competitor query returned 0 rows")
        return {}

    # Map external hotel_id -> avg_price
    external_prices: dict[int, float] = {}
    for row in rows:
        try:
            external_prices[int(row[0])] = float(row[1])
        except (TypeError, ValueError):
            continue

    logger.info("AI_Search competitor prices loaded for %d hotels", len(external_prices))

    # Group external prices by zone
    zone_price_sums: dict[str, float] = {}
    zone_price_counts: dict[str, int] = {}
    for hid, price in external_prices.items():
        seg = HOTEL_SEGMENTS.get(hid)
        if seg:
            zone = seg["zone"]
        else:
            # External hotels not in our segments — skip (we only have zone mapping for ours)
            # But AI_Search has 6013 hotels — we can still count them if they match Miami
            # For now, only use hotels we can map to a zone
            continue
        zone_price_sums[zone] = zone_price_sums.get(zone, 0.0) + price
        zone_price_counts[zone] = zone_price_counts.get(zone, 0) + 1

    # Also include ALL external Miami hotels in a global "miami" average as fallback
    all_prices = [p for p in external_prices.values() if p > 0]
    miami_avg = sum(all_prices) / len(all_prices) if all_prices else 0.0

    zone_averages: dict[str, float] = {}
    for zone in zone_price_sums:
        count = zone_price_counts[zone]
        if count >= 2:  # Need at least 2 hotels for meaningful average
            zone_averages[zone] = zone_price_sums[zone] / count

    # Map each hotel_id in predictions to its zone average
    result: dict[int, float] = {}
    for hid in hotel_ids_in_preds:
        seg = HOTEL_SEGMENTS.get(hid)
        if not seg:
            continue
        zone = seg["zone"]
        if zone in zone_averages:
            result[hid] = zone_averages[zone]
        elif miami_avg > 0:
            # Fallback to city-wide average if zone has too few hotels in AI_Search
            result[hid] = miami_avg

    logger.info("AI_Search zone averages: %s (miami_avg=%.0f)", {z: round(v) for z, v in zone_averages.items()}, miami_avg)
    return result


def _load_historical_comparisons(predictions: dict) -> dict[str, dict]:
    """Load historical price comparisons from AI_Search_HotelData (same period last year).

    For each unique (hotel_id, room_type, checkin_month) combo, queries AI_Search
    for the same hotel, same room type, same month last year.

    Returns {detail_id: {"yoy_avg": float, "yoy_samples": int, "yoy_change_pct": float}}

    Reads YoY data from analytical_cache (populated by nightly _refresh_ai_search_cache).
    """
    # Try reading from cache
    try:
        from src.analytics.analytical_cache import AnalyticalCache
        import json as _json
        cache = AnalyticalCache()
        with cache._get_conn() as c:
            row = c.execute(
                "SELECT status FROM trade_journal WHERE id = 999999"
            ).fetchone()
        if row and row[0]:
            cached = _json.loads(row[0])
            yoy_prices = cached.get("yoy_hotel_prices", {})
            if yoy_prices:
                result: dict[str, dict] = {}
                for detail_id, pred in predictions.items():
                    hid = str(pred.get("hotel_id", ""))
                    if hid in yoy_prices:
                        yoy_avg = yoy_prices[hid]
                        current = float(pred.get("current_price", 0) or 0)
                        yoy_change = ((current - yoy_avg) / yoy_avg * 100) if yoy_avg > 0 and current > 0 else 0
                        result[str(detail_id)] = {
                            "yoy_avg": round(yoy_avg, 2),
                            "yoy_samples": 0,
                            "yoy_change_pct": round(yoy_change, 1),
                        }
                if result:
                    logger.info("AI_Search historical: loaded from cache for %d details", len(result))
                    return result
    except Exception as exc:
        logger.debug("AI_Search historical cache read failed: %s", exc)

    return {}
    try:
        from src.utils.zenith_push import get_pyodbc_connection
    except ImportError as exc:
        logger.debug("AI_Search historical loading skipped (import): %s", exc)
        return {}

    # Collect unique (hotel_id, category, month) combos + map detail_ids
    combos: dict[tuple, list[str]] = {}  # (hotel_id, category, month, year-1) -> [detail_ids]
    for detail_id, pred in predictions.items():
        hid = pred.get("hotel_id")
        cat = pred.get("category", "")
        date_from = pred.get("date_from", "")
        if not hid or not cat or not date_from:
            continue
        try:
            if isinstance(date_from, str):
                checkin = datetime.strptime(date_from[:10], "%Y-%m-%d")
            elif hasattr(date_from, "month"):
                checkin = date_from
            else:
                continue
            month = checkin.month
            last_year = checkin.year - 1
        except (ValueError, AttributeError):
            continue
        key = (int(hid), cat, month, last_year)
        combos.setdefault(key, []).append(str(detail_id))

    if not combos:
        return {}

    # Build a UNION ALL query for each unique (hotel_id, month, year) combo
    # But to avoid massive queries, batch by hotel_id
    hotel_month_groups: dict[int, list[tuple]] = {}
    for key in combos:
        hid = key[0]
        hotel_month_groups.setdefault(hid, []).append(key)

    try:
        conn = get_pyodbc_connection()
        cursor = conn.cursor()
    except (OSError, ConnectionError, ValueError, Exception) as exc:
        logger.warning("AI_Search historical query connection failed: %s", exc)
        return {}

    result: dict[str, dict] = {}
    query_count = 0

    try:
        for hid, keys in hotel_month_groups.items():
            # Build one query per hotel with all month/year combos
            # Use UNION for each month/year pair
            for key in keys:
                _, cat, month, year = key
                sql = """
                    SELECT TOP 50 RoomType, AVG(PriceAmount) as avg_price, COUNT(*) as samples
                    FROM AI_Search_HotelData
                    WHERE HotelId = ? AND MONTH(StayFrom) = ? AND YEAR(StayFrom) = ?
                      AND RoomType LIKE ? AND PriceAmount > 0
                    GROUP BY RoomType
                """
                # Use category as a LIKE pattern (room types may not match exactly)
                cat_pattern = f"%{cat[:20]}%" if cat else "%"
                cursor.execute(sql, (hid, month, year, cat_pattern))
                rows = cursor.fetchall()
                query_count += 1

                if rows:
                    # Take the first matching room type average
                    yoy_avg = float(rows[0][1])
                    yoy_samples = int(rows[0][2])
                    for did in combos[key]:
                        # Find current price for this detail
                        pred = predictions.get(did) or predictions.get(int(did))
                        current_price = float((pred or {}).get("current_price", 0) or 0)
                        yoy_change_pct = 0.0
                        if yoy_avg > 0 and current_price > 0:
                            yoy_change_pct = ((current_price - yoy_avg) / yoy_avg) * 100
                        result[str(did)] = {
                            "yoy_avg": round(yoy_avg, 2),
                            "yoy_samples": yoy_samples,
                            "yoy_change_pct": round(yoy_change_pct, 1),
                        }
        conn.close()
    except (OSError, ConnectionError, ValueError, Exception) as exc:
        logger.warning("AI_Search historical query failed after %d queries: %s", query_count, exc)
        try:
            conn.close()
        except Exception:
            pass

    logger.info("AI_Search historical comparisons loaded for %d details (%d queries)", len(result), query_count)
    return result


# ── Section A: Ex-ante next-day signals ──────────────────────────────

def compute_next_day_signals(analysis: dict) -> list[dict]:
    """Compute CALL/PUT/NONE recommendation for each active contract.

    Pre-loads bulk data from AI_Search_HotelData (competitor zone averages, YoY
    historical comparisons) and MED_Book buy prices, then runs consensus voters
    per detail.

    Returns a list of signal dicts, sorted by (hotel_id, checkin_date, T desc).
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        return []

    # Pre-load AI_Search competitor zone averages (one query for all dates)
    ai_search_zone_avgs: dict[int, float] = {}
    try:
        ai_search_zone_avgs = _load_competitor_zone_averages(predictions)
    except Exception as exc:
        logger.warning("AI_Search competitor loading failed: %s", exc)

    # Pre-load AI_Search historical YoY comparisons
    ai_search_historical: dict[str, dict] = {}
    try:
        ai_search_historical = _load_historical_comparisons(predictions)
    except Exception as exc:
        logger.warning("AI_Search historical loading failed: %s", exc)

    # Pre-load MED_Book buy prices for margin erosion voter
    med_book_prices: dict[int, float] = {}  # hotel_id -> avg buy price
    try:
        from src.data.trading_db import load_active_bookings
        mb_df = load_active_bookings()
        if not mb_df.empty and "HotelId" in mb_df.columns and "BuyPrice" in mb_df.columns:
            for _, row in mb_df.groupby("HotelId")["BuyPrice"].mean().items():
                med_book_prices[int(_)] = float(row)
            logger.info("MED_Book buy prices loaded for %d hotels", len(med_book_prices))
        else:
            logger.debug("MED_Book: no active bookings found (empty=%s, cols=%s)",
                         mb_df.empty if mb_df is not None else "None",
                         list(mb_df.columns) if mb_df is not None and not mb_df.empty else "N/A")
    except (ImportError, OSError, ConnectionError, ValueError) as exc:
        logger.debug("MED_Book buy price loading failed: %s", exc)

    signals: list[dict] = []

    for detail_id, pred in predictions.items():
        try:
            prob = pred.get("probability") or {}
            p_up   = float(prob.get("up",   0)) / 100.0
            p_down = float(prob.get("down", 0)) / 100.0

            regime_info = pred.get("regime") or {}
            regime = regime_info.get("regime", "NORMAL")

            momentum = pred.get("momentum") or {}
            accel    = float(momentum.get("acceleration", 0) or 0)
            vel_24h  = float(momentum.get("velocity_24h", 0) or 0)
            mom_sig  = momentum.get("signal", "N/A")

            quality = pred.get("confidence_quality", "low")

            # σ_1d from forward curve first point (if available)
            fc = pred.get("forward_curve") or []
            sigma_1d = float(fc[0].get("volatility_at_t", 0)) if fc else 0.0

            exp_return = float(pred.get("expected_change_pct", 0) or 0)

            current_price = float(pred.get("current_price", 0) or 0)

            # FC metrics kept for output (max_drop_pct, max_rise_pct, fc_points)
            fc_prices = [float(pt.get("predicted_price", 0)) for pt in fc if pt.get("predicted_price")]
            max_drop_pct = 0.0
            max_rise_pct = 0.0
            if fc_prices and current_price > 0:
                fc_min = min(fc_prices)
                fc_max = max(fc_prices)
                max_drop_pct = ((current_price - fc_min) / current_price) * 100
                max_rise_pct = ((fc_max - current_price) / current_price) * 100

            # --- Consensus signal from 14 independent voters ---
            # Get zone context for competitor/benchmark voting
            zone_avg = 0.0
            official_adr = 0.0
            peer_directions = []
            hotel_id_val = pred.get("hotel_id", 0)
            try:
                from config.hotel_segments import get_hotel_segment, HOTEL_SEGMENTS
                seg = get_hotel_segment(int(hotel_id_val)) if hotel_id_val else None
                if seg:
                    zone = seg["zone"]
                    tier = seg["tier"]

                    # Prefer AI_Search zone average (real market data from 129 providers)
                    ai_zone_avg = ai_search_zone_avgs.get(int(hotel_id_val), 0.0)
                    if ai_zone_avg > 0:
                        zone_avg = ai_zone_avg
                    else:
                        # Fallback: compute from other predictions in same zone
                        zone_prices = []
                        for _, other_pred in predictions.items():
                            other_hid = int(other_pred.get("hotel_id", 0) or 0)
                            if other_hid == int(hotel_id_val):
                                continue
                            other_seg = HOTEL_SEGMENTS.get(other_hid, {})
                            if other_seg.get("zone") != zone:
                                continue
                            other_cp = float(other_pred.get("current_price", 0) or 0)
                            if other_cp > 0:
                                zone_prices.append(other_cp)
                        if zone_prices:
                            zone_avg = sum(zone_prices) / len(zone_prices)

                    # Collect peer directions (one vote per hotel, not per room)
                    tier_directions = []
                    zone_directions = []
                    seen_hotels = set()
                    for _, other_pred in predictions.items():
                        other_hid = int(other_pred.get("hotel_id", 0) or 0)
                        if other_hid == int(hotel_id_val):
                            continue
                        other_seg = HOTEL_SEGMENTS.get(other_hid, {})
                        if other_seg.get("zone") != zone:
                            continue
                        other_change = float(other_pred.get("expected_change_pct", 0) or 0)
                        if other_hid not in seen_hotels and other_change != 0:
                            seen_hotels.add(other_hid)
                            direction = {"direction": "up" if other_change > 0 else "down"}
                            zone_directions.append(direction)
                            if other_seg.get("tier") == tier:
                                tier_directions.append(direction)
                    # Prefer same zone+tier peers; fall back to zone-only
                    peer_directions = tier_directions if tier_directions else zone_directions
            except (ImportError, ValueError, TypeError) as exc:
                logger.debug("Hotel segments lookup failed: %s", exc)

            # Get official ADR for this zone from GMCVB benchmarks
            try:
                from src.collectors.gmcvb_collector import get_official_adr
                if seg:
                    official_adr = get_official_adr(seg["zone"])
            except ImportError as exc:
                logger.debug("GMCVB collector not available: %s", exc)

            # Build events list for consensus voter
            events_for_voter = []
            try:
                from src.analytics.events_store import MIAMI_MAJOR_EVENTS
                date_from_str = pred.get("date_from", "")
                if date_from_str:
                    if isinstance(date_from_str, str):
                        checkin = datetime.strptime(date_from_str[:10], "%Y-%m-%d").date()
                    elif hasattr(date_from_str, 'date'):
                        checkin = date_from_str.date()
                    else:
                        checkin = date_from_str
                    for ev in MIAMI_MAJOR_EVENTS:
                        ev_start = datetime.strptime(ev["start"], "%Y-%m-%d").date()
                        ev_end = datetime.strptime(ev["end"], "%Y-%m-%d").date()
                        if ev_start <= checkin <= ev_end + timedelta(days=3):
                            events_for_voter.append({"name": ev["name"], "status": "upcoming"})
                        elif ev_end < checkin <= ev_end + timedelta(days=7):
                            events_for_voter.append({"name": ev["name"], "status": "past"})
            except (ImportError, ValueError, TypeError) as exc:
                logger.debug("Events lookup for consensus voter failed: %s", exc)

            # MED_Book buy price for margin erosion voter
            buy_price = med_book_prices.get(int(hotel_id_val), 0.0) if hotel_id_val else 0.0

            from src.analytics.consensus_signal import compute_consensus_signal
            consensus = compute_consensus_signal(
                pred, zone_avg=zone_avg, official_adr=official_adr,
                events=events_for_voter or None,
                peer_prices=peer_directions or None,
                med_book_buy_price=buy_price,
            )

            rec = consensus["signal"]
            if rec == "NEUTRAL":
                rec = "NONE"  # Keep backward compat with existing UI
            conf_pct = consensus["probability"]
            if conf_pct >= 90:
                conf = "High"
            elif conf_pct >= 66:
                conf = "Med"
            else:
                conf = "Low"

            # Regime/quality suppression
            suppress = (regime in ("STALE",)) or (quality == "low") or (current_price <= 0)
            if suppress:
                rec, conf = "NONE", "Low"

            # --- Market signal adjustment (from MonitorBridge) ---
            market_ctx = {}
            try:
                from src.services.monitor_bridge import MonitorBridge
                bridge = MonitorBridge()
                mkt = bridge.get_market_signals()
                demand_val = mkt.get("demand_indicator", {}).get("value", 0)
                vol_val = mkt.get("supply_volatility", {}).get("value", 0)
                bb_val = mkt.get("board_composition", {}).get("value", 0)
                monitor_mod = bridge.get_confidence_modifier(
                    hotel_id=str(pred.get("hotel_id", ""))
                )
                market_ctx = {
                    "demand_indicator": round(demand_val, 3),
                    "supply_volatility": round(vol_val, 3),
                    "board_composition": round(bb_val, 3),
                    "monitor_confidence_modifier": round(monitor_mod, 3),
                }

                # Adjust confidence level based on market signals (max ±1 tier)
                if not suppress and conf != "Low":
                    if demand_val > 0.7 and rec == "CALL" and conf == "Med":
                        conf = "High"  # Strong live demand supports CALL
                    elif demand_val < 0.3 and rec == "PUT" and conf == "Med":
                        conf = "High"  # Weak live demand supports PUT
                    if vol_val > 0.5 and conf == "High":
                        conf = "Med"   # High supply volatility → reduce certainty

                # Downgrade if monitor flags system issues
                if monitor_mod <= -0.30 and conf == "High":
                    conf = "Med"
                elif monitor_mod <= -0.40:
                    conf = "Low"
            except (ImportError, OSError, Exception):
                pass  # Monitor bridge is optional

            # AI_Search historical YoY comparison for this detail
            yoy_data = ai_search_historical.get(str(detail_id), {})

            signals.append({
                "detail_id":        str(detail_id),
                "hotel_id":         pred.get("hotel_id"),
                "hotel_name":       pred.get("hotel_name", ""),
                "checkin_date":     pred.get("date_from", ""),
                "T":                pred.get("days_to_checkin", 0),
                "category":         pred.get("category", ""),
                "board":            pred.get("board", ""),
                "S_t":              pred.get("current_price", 0),
                "expected_return_1d": round(exp_return, 3),
                "sigma_1d":         round(sigma_1d, 4),
                "P_up":             round(p_up * 100, 1),
                "P_down":           round(p_down * 100, 1),
                "velocity_24h":     round(vel_24h, 4),
                "acceleration":     round(accel, 4),
                "momentum_signal":  mom_sig,
                "regime":           regime,
                "quality":          quality,
                "recommendation":   rec,
                "confidence":       conf,
                "consensus_probability":    consensus.get("probability", 0),
                "consensus_sources_agree":  consensus.get("sources_agree", 0),
                "consensus_sources_voting": consensus.get("sources_voting", 0),
                "consensus_by_category":    consensus.get("by_category", {}),
                "fc_max_drop_pct":  round(max_drop_pct, 1),
                "fc_max_rise_pct":  round(max_rise_pct, 1),
                "fc_points":        len(fc_prices),
                "market_context":   market_ctx,
                "ai_search_zone_avg": round(zone_avg, 2) if ai_search_zone_avgs.get(int(hotel_id_val), 0) > 0 else None,
                "ai_search_yoy":    yoy_data if yoy_data else None,
            })
        except (KeyError, ValueError, TypeError, AttributeError, ZeroDivisionError) as exc:
            logger.debug("options signal failed for %s: %s", detail_id, exc)
            continue

    # Sort: hotel, checkin_date, T descending (highest T = farthest out = first)
    signals.sort(key=lambda s: (
        s.get("hotel_id") or 0,
        s.get("checkin_date") or "",
        -(s.get("T") or 0),
    ))
    return signals


# ── Section B: Ex-post expiry-relative metrics ────────────────────────

def build_expiry_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Compute 6-month expiry-relative analytics from unified YoY DataFrame.

    For each completed contract (check-in date in last 6 months):
    - S_exp = price at minimum T_days (settlement price)
    - rel_to_expiry = (price - S_exp) / S_exp * 100
    - Count days and events below -5% and -10% thresholds

    Returns:
        (contract_summaries_df, hotel_rollups_dict)
    """
    if df.empty:
        return pd.DataFrame(), {}

    today = pd.Timestamp.today().normalize()
    six_months_ago = today - timedelta(days=180)

    # Ensure datetime types
    df = df.copy()
    df["checkin_date"] = pd.to_datetime(df["checkin_date"])
    df["scan_date"]    = pd.to_datetime(df["scan_date"])

    # Completed contracts in last 6 months
    completed = df[
        (df["checkin_date"] < today) &
        (df["checkin_date"] >= six_months_ago)
    ].copy()

    if completed.empty:
        logger.info("Options: no completed contracts in last 6 months")
        return pd.DataFrame(), {}

    # Settlement price: price at min(T_days) per contract
    settlement = (
        completed.sort_values("T_days")
        .groupby(CONTRACT_KEY, as_index=False)
        .first()[CONTRACT_KEY + ["price", "T_days"]]
        .rename(columns={"price": "S_exp", "T_days": "settlement_T"})
    )
    settlement["settlement_fallback"] = settlement["settlement_T"] > 3

    # Merge settlement back
    merged = completed.merge(
        settlement[CONTRACT_KEY + ["S_exp", "settlement_fallback"]],
        on=CONTRACT_KEY, how="inner",
    )

    # Filter out bad settlements (S_exp = 0 or missing)
    merged = merged[merged["S_exp"] > 0].copy()

    # Relative to expiry
    merged["rel_to_expiry"] = (merged["price"] - merged["S_exp"]) / merged["S_exp"] * 100.0

    # Per-contract summaries
    summaries: list[dict] = []

    for key, group in merged.groupby(CONTRACT_KEY):
        hotel_id, checkin_date, category, board = key
        rel = group["rel_to_expiry"]

        # Sort chronologically: T descending (far → near = time forward)
        rel_chrono = group.sort_values("T_days", ascending=False)["rel_to_expiry"].values

        days_below_5  = int((rel <= BREACH_THRESHOLDS[0]).sum())
        days_below_10 = int((rel <= BREACH_THRESHOLDS[1]).sum())
        events_below_5  = _count_crossings(rel_chrono, BREACH_THRESHOLDS[0])
        events_below_10 = _count_crossings(rel_chrono, BREACH_THRESHOLDS[1])

        s_exp_val = group["S_exp"].iloc[0]
        fallback  = bool(group["settlement_fallback"].iloc[0])

        summaries.append({
            "hotel_id":           int(hotel_id),
            "checkin_date":       str(checkin_date.date()) if hasattr(checkin_date, "date") else str(checkin_date),
            "category":           category,
            "board":              board,
            "S_exp":              round(float(s_exp_val), 2),
            "min_rel":            round(float(rel.min()), 2),
            "max_rel":            round(float(rel.max()), 2),
            "n_scans":            int(len(group)),
            "days_below_5":       days_below_5,
            "days_below_10":      days_below_10,
            "events_below_5":     events_below_5,
            "events_below_10":    events_below_10,
            "settlement_fallback": fallback,
        })

    if not summaries:
        return pd.DataFrame(), {}

    summary_df = pd.DataFrame(summaries)

    # Hotel-level rollups
    rollups: dict[int, dict] = {}
    for hid, hgroup in summary_df.groupby("hotel_id"):
        n = len(hgroup)
        cnt_5  = int((hgroup["min_rel"] <= -5.0).sum())
        cnt_10 = int((hgroup["min_rel"] <= -10.0).sum())
        min_rel_vals = hgroup["min_rel"].dropna()

        rollups[int(hid)] = {
            "total_contracts":    n,
            "pct_below_5":        round(cnt_5  / n * 100, 1) if n else 0,
            "pct_below_10":       round(cnt_10 / n * 100, 1) if n else 0,
            "total_events_5":     int(hgroup["events_below_5"].sum()),
            "total_events_10":    int(hgroup["events_below_10"].sum()),
            "avg_days_below_5":   round(float(hgroup["days_below_5"].mean()), 1),
            "avg_days_below_10":  round(float(hgroup["days_below_10"].mean()), 1),
            "median_min_rel":     round(float(min_rel_vals.median()), 2) if len(min_rel_vals) else None,
            "p10_min_rel":        round(float(np.percentile(min_rel_vals, 10)), 2) if len(min_rel_vals) >= 5 else None,
            "p90_min_rel":        round(float(np.percentile(min_rel_vals, 90)), 2) if len(min_rel_vals) >= 5 else None,
        }

    logger.info(
        "Options expiry metrics: %d contracts, %d hotels, 6M window",
        len(summary_df), len(rollups),
    )
    return summary_df, rollups
