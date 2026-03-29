"""Options trading engine — treats hotel room contracts as options with expiry = check-in.

Two main outputs:
  1. compute_next_day_signals(analysis)  → ex-ante CALL/PUT/NONE signal per active contract
  2. build_expiry_metrics(df)            → ex-post breach/drawdown analytics for last 6M
"""
from __future__ import annotations

import math
import logging
from datetime import timedelta

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


# ── Section A: Ex-ante next-day signals ──────────────────────────────

def compute_next_day_signals(analysis: dict) -> list[dict]:
    """Compute CALL/PUT/NONE recommendation for each active contract.

    Uses existing analysis["predictions"] — no additional DB queries needed.
    P_up/P_down come from the decay-curve probability distribution already stored
    in each prediction's "probability" dict (values are 0–100 scale).

    Returns a list of signal dicts, sorted by (hotel_id, checkin_date, T desc).
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        return []

    # Pre-load MED_Book buy prices for margin erosion voter
    med_book_prices: dict[int, float] = {}  # hotel_id -> avg buy price
    try:
        from src.data.trading_db import load_active_bookings
        mb_df = load_active_bookings()
        if not mb_df.empty and "HotelId" in mb_df.columns and "BuyPrice" in mb_df.columns:
            for _, row in mb_df.groupby("HotelId")["BuyPrice"].mean().items():
                med_book_prices[int(_)] = float(row)
    except (ImportError, OSError, ConnectionError, ValueError):
        pass  # MED_Book data optional

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
                    zone_prices = []
                    for _, other_pred in predictions.items():
                        other_hid = int(other_pred.get("hotel_id", 0) or 0)
                        if other_hid == int(hotel_id_val):
                            continue  # skip self
                        other_seg = HOTEL_SEGMENTS.get(other_hid, {})
                        # Compare within same zone AND same tier
                        if other_seg.get("zone") == zone and other_seg.get("tier") == tier:
                            other_cp = float(other_pred.get("current_price", 0) or 0)
                            if other_cp > 0:
                                zone_prices.append(other_cp)
                            # Collect peer direction for consensus voter
                            other_change = float(other_pred.get("expected_change_pct", 0) or 0)
                            if other_change > 0:
                                peer_directions.append({"direction": "up"})
                            elif other_change < 0:
                                peer_directions.append({"direction": "down"})
                    if zone_prices:
                        zone_avg = sum(zone_prices) / len(zone_prices)
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
                from datetime import datetime, timedelta
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
