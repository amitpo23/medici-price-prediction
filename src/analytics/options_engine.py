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

            # --- Decision rules ---
            suppress = (regime in ("STALE", "VOLATILE")) or (quality == "low")

            if suppress:
                rec, conf = "NONE", "Low"
            elif p_up >= P_THRESHOLD_HIGH and accel >= 0:
                rec, conf = "CALL", "High"
            elif p_up >= P_THRESHOLD_MED and accel >= 0:
                rec, conf = "CALL", "Med"
            elif p_down >= P_THRESHOLD_HIGH and accel <= 0:
                rec, conf = "PUT", "High"
            elif p_down >= P_THRESHOLD_MED and accel <= 0:
                rec, conf = "PUT", "Med"
            else:
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
