"""Source Attribution Engine — isolate and score each prediction source independently.

Runs 4 parallel analysis tracks:
  Track 1: Forward Curve ONLY (100%) — no historical, no ML
  Track 2: Historical Patterns ONLY (100%) — no FC, no ML
  Track 3: ML Model ONLY (100%) — no FC, no historical
  Track 4: Ensemble (50/30/20) — the production pipeline

For each track, computes:
  - Predicted price per room
  - CALL/PUT signal (same thresholds as production)
  - Accuracy vs. actual (when actuals are available from prediction_log)
  - IC (Information Coefficient) — correlation between prediction and outcome
  - Hit rate — % of correct signal directions
  - MAPE — Mean Absolute Percentage Error

Additionally provides enrichment-level attribution:
  - FC+Events vs FC alone → event contribution
  - FC+Seasonality vs FC alone → seasonality contribution
  - etc. for each enrichment source

This module is READ-ONLY — it never modifies predictions or signals.
It only analyzes and scores existing data.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class SourceTrack:
    """One isolated prediction source running at 100% weight."""
    source: str                     # "forward_curve", "historical", "ml", "ensemble"
    label: str                      # Display name
    weight_pct: int                 # 100 for isolated, actual for ensemble
    total_rooms: int = 0
    rooms_with_signal: int = 0      # Rooms where this source produced a prediction
    coverage_pct: float = 0.0       # rooms_with_signal / total_rooms
    avg_predicted_price: float = 0.0
    avg_confidence: float = 0.0
    calls: int = 0
    puts: int = 0
    neutrals: int = 0
    # Accuracy (only when actuals available)
    scored_rooms: int = 0
    hit_rate: float = 0.0           # % of correct signal direction
    mape: float = 0.0              # Mean Absolute Percentage Error
    ic: float = 0.0                # Information Coefficient
    avg_error_pct: float = 0.0
    # Per-hotel breakdown
    hotel_breakdown: list[dict] = field(default_factory=list)
    # Sample predictions
    sample_predictions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnrichmentAttribution:
    """Contribution of a single enrichment source."""
    enrichment: str                 # "events", "seasonality", "demand", etc.
    label: str
    avg_daily_impact_pct: float     # Average daily adjustment %
    max_daily_impact_pct: float     # Max observed daily adjustment %
    rooms_affected: int             # Rooms where this enrichment != 0
    rooms_total: int
    coverage_pct: float             # rooms_affected / rooms_total
    avg_price_impact_usd: float     # Absolute $ impact on final price
    direction: str                  # "positive", "negative", "mixed"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AttributionReport:
    """Full attribution report across all sources and enrichments."""
    timestamp: str
    total_rooms: int
    source_tracks: list[SourceTrack]
    enrichment_attribution: list[EnrichmentAttribution]
    # Cross-source comparison
    agreement_rate: float           # % of rooms where all sources agree on direction
    divergence_rooms: list[dict]    # Rooms where sources disagree

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── Signal thresholds (same as options_engine.py) ────────────────────

SIGNAL_THRESHOLD_HIGH = 0.70
SIGNAL_THRESHOLD_MEDIUM = 0.60


def _derive_signal(p_up: float, p_down: float, acceleration: float = 0.0) -> tuple[str, str]:
    """Derive CALL/PUT/NONE signal from probabilities.

    Returns (recommendation, confidence).
    Uses same logic as options_engine.py.
    """
    if p_up >= SIGNAL_THRESHOLD_HIGH and acceleration >= 0:
        return "CALL", "High"
    elif p_up >= SIGNAL_THRESHOLD_MEDIUM and acceleration >= 0:
        return "CALL", "Med"
    elif p_down >= SIGNAL_THRESHOLD_HIGH and acceleration <= 0:
        return "PUT", "High"
    elif p_down >= SIGNAL_THRESHOLD_MEDIUM and acceleration <= 0:
        return "PUT", "Med"
    return "NONE", "Low"


# ── Core: Extract isolated predictions ───────────────────────────────

def extract_source_predictions(analysis: dict) -> dict[str, list[dict]]:
    """Extract per-source predictions from the analysis cache.

    The DeepPredictor already stores individual signal prices in each prediction:
      - fc_price, fc_confidence, fc_weight → Forward Curve
      - hist_price, hist_confidence, hist_weight → Historical
      - ml_price, ml_confidence, ml_weight → ML
      - predicted_checkin_price → Ensemble

    This function extracts these into 4 separate prediction lists.
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        logger.warning("source_attribution: no predictions in analysis cache")
        return {"forward_curve": [], "historical": [], "ml": [], "ensemble": []}

    tracks: dict[str, list[dict]] = {
        "forward_curve": [],
        "historical": [],
        "ml": [],
        "ensemble": [],
    }

    for detail_id_str, pred in predictions.items():
        detail_id = pred.get("detail_id", detail_id_str)
        hotel_id = pred.get("hotel_id", 0)
        hotel_name = pred.get("hotel_name", "")
        category = pred.get("category", "")
        board = pred.get("board", "")
        current_price = float(pred.get("current_price", 0) or 0)
        days_to_checkin = int(pred.get("days_to_checkin", 0) or 0)
        checkin_date = pred.get("date_from", "")

        if current_price <= 0:
            continue

        # Ensemble (production)
        ensemble_price = float(pred.get("predicted_checkin_price", 0) or 0)
        if ensemble_price > 0:
            # Extract probabilities from forward curve
            prob = pred.get("probability", {})
            p_up = float(prob.get("up", 0) or 0) / 100.0 if float(prob.get("up", 0) or 0) > 1 else float(prob.get("up", 0) or 0)
            p_down = float(prob.get("down", 0) or 0) / 100.0 if float(prob.get("down", 0) or 0) > 1 else float(prob.get("down", 0) or 0)
            acceleration = float(pred.get("acceleration", 0) or 0)

            rec, conf = _derive_signal(p_up, p_down, acceleration)
            tracks["ensemble"].append({
                "detail_id": detail_id,
                "hotel_id": hotel_id,
                "hotel_name": hotel_name,
                "category": category,
                "board": board,
                "current_price": current_price,
                "predicted_price": ensemble_price,
                "change_pct": _safe_pct(ensemble_price, current_price),
                "confidence": float(pred.get("confidence_score", 0.5) or 0.5),
                "signal": rec,
                "signal_confidence": conf,
                "days_to_checkin": days_to_checkin,
                "checkin_date": checkin_date,
            })

        # Forward Curve isolated (100%)
        fc_price = float(pred.get("fc_price", 0) or 0)
        fc_confidence = float(pred.get("fc_confidence", 0) or 0)
        if fc_price > 0:
            fc_change = _safe_pct(fc_price, current_price)
            fc_p_up = max(0, fc_change / 100) if fc_change > 0 else 0
            fc_p_down = max(0, -fc_change / 100) if fc_change < 0 else 0
            fc_rec, fc_conf = _derive_signal(fc_p_up, fc_p_down)
            tracks["forward_curve"].append({
                "detail_id": detail_id,
                "hotel_id": hotel_id,
                "hotel_name": hotel_name,
                "category": category,
                "board": board,
                "current_price": current_price,
                "predicted_price": fc_price,
                "change_pct": fc_change,
                "confidence": fc_confidence,
                "signal": fc_rec,
                "signal_confidence": fc_conf,
                "days_to_checkin": days_to_checkin,
                "checkin_date": checkin_date,
            })

        # Historical isolated (100%)
        hist_price = float(pred.get("hist_price", 0) or 0)
        hist_confidence = float(pred.get("hist_confidence", 0) or 0)
        if hist_price > 0:
            hist_change = _safe_pct(hist_price, current_price)
            hist_p_up = max(0, hist_change / 100) if hist_change > 0 else 0
            hist_p_down = max(0, -hist_change / 100) if hist_change < 0 else 0
            hist_rec, hist_conf = _derive_signal(hist_p_up, hist_p_down)
            tracks["historical"].append({
                "detail_id": detail_id,
                "hotel_id": hotel_id,
                "hotel_name": hotel_name,
                "category": category,
                "board": board,
                "current_price": current_price,
                "predicted_price": hist_price,
                "change_pct": hist_change,
                "confidence": hist_confidence,
                "signal": hist_rec,
                "signal_confidence": hist_conf,
                "days_to_checkin": days_to_checkin,
                "checkin_date": checkin_date,
            })

        # ML isolated (100%)
        ml_price = float(pred.get("ml_price", 0) or 0)
        ml_confidence = float(pred.get("ml_confidence", 0) or 0)
        if ml_price > 0:
            ml_change = _safe_pct(ml_price, current_price)
            ml_p_up = max(0, ml_change / 100) if ml_change > 0 else 0
            ml_p_down = max(0, -ml_change / 100) if ml_change < 0 else 0
            ml_rec, ml_conf = _derive_signal(ml_p_up, ml_p_down)
            tracks["ml"].append({
                "detail_id": detail_id,
                "hotel_id": hotel_id,
                "hotel_name": hotel_name,
                "category": category,
                "board": board,
                "current_price": current_price,
                "predicted_price": ml_price,
                "change_pct": ml_change,
                "confidence": ml_confidence,
                "signal": ml_rec,
                "signal_confidence": ml_conf,
                "days_to_checkin": days_to_checkin,
                "checkin_date": checkin_date,
            })

    return tracks


# ── Core: Build SourceTrack from predictions ─────────────────────────

def build_source_track(
    source: str,
    label: str,
    weight_pct: int,
    predictions: list[dict],
    total_rooms: int,
    actuals: dict[str, float] | None = None,
) -> SourceTrack:
    """Build a SourceTrack from a list of isolated predictions.

    Args:
        source: Source identifier
        label: Display label
        weight_pct: Weight percentage (100 for isolated, actual for ensemble)
        predictions: List of prediction dicts from extract_source_predictions
        total_rooms: Total rooms in the analysis
        actuals: Optional dict of detail_id → actual_price for accuracy scoring
    """
    track = SourceTrack(
        source=source,
        label=label,
        weight_pct=weight_pct,
        total_rooms=total_rooms,
        rooms_with_signal=len(predictions),
        coverage_pct=round(len(predictions) / max(total_rooms, 1) * 100, 1),
    )

    if not predictions:
        return track

    # Aggregate metrics
    prices = [p["predicted_price"] for p in predictions]
    confidences = [p["confidence"] for p in predictions]
    track.avg_predicted_price = round(sum(prices) / len(prices), 2)
    track.avg_confidence = round(sum(confidences) / len(confidences), 3)

    # Signal counts
    for p in predictions:
        sig = (p.get("signal") or "NONE").upper()
        if sig in ("CALL", "STRONG_CALL"):
            track.calls += 1
        elif sig in ("PUT", "STRONG_PUT"):
            track.puts += 1
        else:
            track.neutrals += 1

    # Per-hotel breakdown
    hotel_data: dict[int, dict] = {}
    for p in predictions:
        hid = int(p.get("hotel_id", 0))
        hname = p.get("hotel_name", "")
        if hid not in hotel_data:
            hotel_data[hid] = {
                "hotel_id": hid,
                "hotel_name": hname,
                "rooms": 0,
                "calls": 0,
                "puts": 0,
                "avg_price": 0.0,
                "avg_change_pct": 0.0,
                "_prices": [],
                "_changes": [],
            }
        hotel_data[hid]["rooms"] += 1
        sig = (p.get("signal") or "NONE").upper()
        if sig in ("CALL", "STRONG_CALL"):
            hotel_data[hid]["calls"] += 1
        elif sig in ("PUT", "STRONG_PUT"):
            hotel_data[hid]["puts"] += 1
        hotel_data[hid]["_prices"].append(p["predicted_price"])
        hotel_data[hid]["_changes"].append(p.get("change_pct", 0))

    for hd in hotel_data.values():
        hd["avg_price"] = round(sum(hd["_prices"]) / len(hd["_prices"]), 2)
        hd["avg_change_pct"] = round(sum(hd["_changes"]) / len(hd["_changes"]), 2)
        del hd["_prices"]
        del hd["_changes"]

    track.hotel_breakdown = sorted(
        hotel_data.values(), key=lambda h: h["rooms"], reverse=True
    )

    # Accuracy scoring (if actuals provided)
    if actuals:
        scored = []
        hits = 0
        errors_pct = []
        pred_changes = []
        actual_changes = []

        for p in predictions:
            did = str(p.get("detail_id", ""))
            if did not in actuals:
                continue
            actual_price = actuals[did]
            if actual_price <= 0:
                continue

            predicted_price = p["predicted_price"]
            current_price = p["current_price"]
            error_pct = abs(predicted_price - actual_price) / actual_price * 100

            # Signal hit: predicted direction matches actual
            pred_direction = "up" if predicted_price > current_price else "down"
            actual_direction = "up" if actual_price > current_price else "down"
            is_hit = pred_direction == actual_direction
            if is_hit:
                hits += 1

            scored.append(did)
            errors_pct.append(error_pct)
            pred_changes.append(_safe_pct(predicted_price, current_price))
            actual_changes.append(_safe_pct(actual_price, current_price))

        track.scored_rooms = len(scored)
        if scored:
            track.hit_rate = round(hits / len(scored) * 100, 1)
            track.mape = round(sum(errors_pct) / len(errors_pct), 2)
            track.avg_error_pct = round(
                sum(e for e in errors_pct) / len(errors_pct), 2
            )
            # IC: Pearson correlation between predicted and actual changes
            track.ic = _pearson_correlation(pred_changes, actual_changes)

    # Sample predictions (top 20 by absolute change)
    sorted_preds = sorted(predictions, key=lambda p: abs(p.get("change_pct", 0)), reverse=True)
    track.sample_predictions = sorted_preds[:20]

    return track


# ── Core: Enrichment Attribution ─────────────────────────────────────

def compute_enrichment_attribution(analysis: dict) -> list[EnrichmentAttribution]:
    """Compute per-enrichment contribution from forward curve data.

    Each prediction's forward_curve points contain daily enrichment adjustments:
      event_adj_pct, season_adj_pct, demand_adj_pct,
      weather_adj_pct, competitor_adj_pct, momentum_adj_pct
    """
    predictions = analysis.get("predictions", {})
    if not predictions:
        return []

    enrichment_names = [
        ("event_adj_pct", "events", "Events (Art Basel, Ultra, Holidays)"),
        ("season_adj_pct", "seasonality", "Seasonality (Monthly Patterns)"),
        ("demand_adj_pct", "demand", "Demand (Flight Data)"),
        ("weather_adj_pct", "weather", "Weather (Rain, Hurricanes)"),
        ("competitor_adj_pct", "competitor", "Competitor Pressure"),
        ("momentum_adj_pct", "momentum", "Price Momentum"),
    ]

    # Also check for cancellation and provider from enrichments
    enrichment_keys_extended = enrichment_names + [
        ("cancel_adj_pct", "cancellation", "Cancellation Risk"),
        ("provider_adj_pct", "provider", "Provider Pressure"),
    ]

    stats: dict[str, dict] = {}
    for _, key, label in enrichment_keys_extended:
        stats[key] = {
            "label": label,
            "daily_impacts": [],
            "rooms_affected": 0,
            "total_rooms": 0,
            "price_impacts_usd": [],
        }

    for pred in predictions.values():
        fc_points = pred.get("forward_curve", [])
        current_price = float(pred.get("current_price", 0) or 0)
        if not fc_points or current_price <= 0:
            continue

        for field_name, key, _ in enrichment_keys_extended:
            stats[key]["total_rooms"] += 1

            # Collect daily adjustments from forward curve points
            daily_adjs = []
            for pt in fc_points:
                adj = float(pt.get(field_name, 0) or 0)
                daily_adjs.append(adj)

            if daily_adjs:
                avg_daily = sum(daily_adjs) / len(daily_adjs)
                max_daily = max(abs(a) for a in daily_adjs) if daily_adjs else 0

                if abs(avg_daily) > 0.0001:  # Non-zero contribution
                    stats[key]["rooms_affected"] += 1
                    stats[key]["daily_impacts"].append(avg_daily)

                    # Estimate USD impact: compound daily adjustments
                    cumulative_pct = sum(daily_adjs)
                    usd_impact = current_price * cumulative_pct / 100
                    stats[key]["price_impacts_usd"].append(usd_impact)

    result = []
    for key, s in stats.items():
        if s["total_rooms"] == 0:
            continue

        daily = s["daily_impacts"]
        usd_impacts = s["price_impacts_usd"]
        avg_daily = sum(daily) / len(daily) if daily else 0
        max_daily = max((abs(d) for d in daily), default=0)
        avg_usd = sum(usd_impacts) / len(usd_impacts) if usd_impacts else 0

        # Determine direction
        positives = sum(1 for d in daily if d > 0)
        negatives = sum(1 for d in daily if d < 0)
        if positives > 0 and negatives == 0:
            direction = "positive"
        elif negatives > 0 and positives == 0:
            direction = "negative"
        else:
            direction = "mixed"

        result.append(EnrichmentAttribution(
            enrichment=key,
            label=s["label"],
            avg_daily_impact_pct=round(avg_daily, 4),
            max_daily_impact_pct=round(max_daily, 4),
            rooms_affected=s["rooms_affected"],
            rooms_total=s["total_rooms"],
            coverage_pct=round(s["rooms_affected"] / max(s["total_rooms"], 1) * 100, 1),
            avg_price_impact_usd=round(avg_usd, 2),
            direction=direction,
        ))

    # Sort by absolute impact
    result.sort(key=lambda e: abs(e.avg_daily_impact_pct), reverse=True)
    return result


# ── Core: Cross-source agreement ─────────────────────────────────────

def compute_agreement(tracks: dict[str, list[dict]]) -> tuple[float, list[dict]]:
    """Compute agreement rate across sources and find divergence rooms.

    Returns:
        (agreement_rate, divergence_rooms)
    """
    # Build lookup by detail_id
    fc_signals = {str(p["detail_id"]): p for p in tracks.get("forward_curve", [])}
    hist_signals = {str(p["detail_id"]): p for p in tracks.get("historical", [])}
    ml_signals = {str(p["detail_id"]): p for p in tracks.get("ml", [])}

    # Only count rooms where at least 2 sources produced predictions
    common_ids = set()
    for did in fc_signals:
        sources_present = 1
        if did in hist_signals:
            sources_present += 1
        if did in ml_signals:
            sources_present += 1
        if sources_present >= 2:
            common_ids.add(did)

    if not common_ids:
        return 0.0, []

    agreements = 0
    divergences = []

    for did in common_ids:
        directions = {}
        if did in fc_signals:
            directions["forward_curve"] = _signal_direction(fc_signals[did].get("signal", "NONE"))
        if did in hist_signals:
            directions["historical"] = _signal_direction(hist_signals[did].get("signal", "NONE"))
        if did in ml_signals:
            directions["ml"] = _signal_direction(ml_signals[did].get("signal", "NONE"))

        unique_dirs = set(directions.values())
        if len(unique_dirs) == 1:
            agreements += 1
        else:
            # Build divergence detail
            div_room = {"detail_id": did}
            if did in fc_signals:
                div_room["hotel_name"] = fc_signals[did].get("hotel_name", "")
                div_room["current_price"] = fc_signals[did].get("current_price", 0)
            for src, direction in directions.items():
                sig_data = (fc_signals if src == "forward_curve" else hist_signals if src == "historical" else ml_signals).get(did, {})
                div_room[f"{src}_signal"] = sig_data.get("signal", "")
                div_room[f"{src}_price"] = sig_data.get("predicted_price", 0)
                div_room[f"{src}_change"] = sig_data.get("change_pct", 0)

            divergences.append(div_room)

    agreement_rate = round(agreements / len(common_ids) * 100, 1) if common_ids else 0.0

    # Sort divergences by price spread (biggest disagreement first)
    for d in divergences:
        prices = [d.get(f"{s}_price", 0) for s in ("forward_curve", "historical", "ml") if d.get(f"{s}_price")]
        d["price_spread"] = round(max(prices) - min(prices), 2) if len(prices) >= 2 else 0
    divergences.sort(key=lambda d: d.get("price_spread", 0), reverse=True)

    return agreement_rate, divergences[:50]  # Cap at 50


# ── Main: Build full attribution report ──────────────────────────────

def build_attribution_report(
    analysis: dict,
    actuals: dict[str, float] | None = None,
) -> AttributionReport:
    """Build complete source attribution report.

    Args:
        analysis: Full analysis cache from run_analysis()
        actuals: Optional {detail_id: actual_price} for accuracy scoring

    Returns:
        AttributionReport with all 4 tracks, enrichment attribution, and agreement.
    """
    predictions = analysis.get("predictions", {})
    total_rooms = len(predictions)

    # Extract isolated predictions
    tracks = extract_source_predictions(analysis)

    # Build source tracks
    source_tracks = [
        build_source_track(
            "forward_curve", "Forward Curve (100%)", 100,
            tracks["forward_curve"], total_rooms, actuals,
        ),
        build_source_track(
            "historical", "Historical Patterns (100%)", 100,
            tracks["historical"], total_rooms, actuals,
        ),
        build_source_track(
            "ml", "ML Model (100%)", 100,
            tracks["ml"], total_rooms, actuals,
        ),
        build_source_track(
            "ensemble", "Ensemble (50/30/20)", -1,  # -1 = mixed weights
            tracks["ensemble"], total_rooms, actuals,
        ),
    ]

    # Enrichment attribution
    enrichment_attribution = compute_enrichment_attribution(analysis)

    # Cross-source agreement
    agreement_rate, divergence_rooms = compute_agreement(tracks)

    return AttributionReport(
        timestamp=datetime.utcnow().isoformat() + "Z",
        total_rooms=total_rooms,
        source_tracks=source_tracks,
        enrichment_attribution=enrichment_attribution,
        agreement_rate=agreement_rate,
        divergence_rooms=divergence_rooms,
    )


# ── Helpers ──────────────────────────────────────────────────────────

def _safe_pct(predicted: float, current: float) -> float:
    """Calculate percentage change safely."""
    if current <= 0:
        return 0.0
    return round((predicted - current) / current * 100, 2)


def _signal_direction(signal: str) -> str:
    """Normalize signal to direction: up/down/neutral."""
    s = (signal or "").upper()
    if s in ("CALL", "STRONG_CALL"):
        return "up"
    elif s in ("PUT", "STRONG_PUT"):
        return "down"
    return "neutral"


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient (IC)."""
    n = len(x)
    if n < 3:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    denom = math.sqrt(var_x * var_y)
    if denom < 1e-10:
        return 0.0

    return round(cov / denom, 4)
