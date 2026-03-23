"""Shared state, caches, scheduler, and helper functions for SalesOffice analytics routers.

All module-level cache variables, locks, scheduler functions, and core
helper functions live here so that sub-routers can import them without
circular dependencies.

Cache state is managed by the unified CacheManager (src/utils/cache_manager.py).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from statistics import mean

from fastapi import Header, HTTPException

from config.settings import (
    CACHE_DIR,
    IS_PRODUCTION,
    MEDICI_DB_URL,
    SALESOFFICE_ALLOW_NON_PROD_SCHEDULER,
    SALESOFFICE_CACHE_PERSISTENCE_ENABLED,
    SALESOFFICE_COLLECTION_INTERVAL_SECONDS,
    SALESOFFICE_ON_DEMAND_WARMUP_ENABLED,
    SALESOFFICE_SCHEDULER_ENABLED,
)
from src.utils.cache_manager import cache as _cm

logger = logging.getLogger(__name__)

# ── Scheduler state ───────────────────────────────────────────────────
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_analysis_warming = threading.Event()  # set while background analysis is running
_analysis_rebuild_lock = threading.Lock()
_analysis_warmup_start_lock = threading.Lock()
_persist_state_lock = threading.Lock()
_persist_restore_lock = threading.Lock()
_persist_restore_attempted = False

COLLECTION_INTERVAL = SALESOFFICE_COLLECTION_INTERVAL_SECONDS
_last_event_refresh_date: list[str] = [""]  # tracks date of last API event refresh
_PERSISTED_CACHE_FILES = {
    "analytics": CACHE_DIR / "salesoffice_analytics_cache.json",
    "salesoffice_options": CACHE_DIR / "salesoffice_options_cache.json",
    "salesoffice_detail": CACHE_DIR / "salesoffice_detail_cache.json",
}


# ── Auth (reuse from integration) ────────────────────────────────────

def _optional_api_key(x_api_key: str = Header(default="")) -> str:
    from src.api.middleware import verify_api_key
    if not verify_api_key(x_api_key):
        logger.warning("Failed auth attempt with key prefix: %s...", x_api_key[:8] if x_api_key else "(empty)")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


def _salesoffice_scheduler_allowed() -> bool:
    return (
        SALESOFFICE_SCHEDULER_ENABLED
        and bool(MEDICI_DB_URL)
        and (IS_PRODUCTION or SALESOFFICE_ALLOW_NON_PROD_SCHEDULER)
    )


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def _persist_cache_region(region_name: str) -> None:
    if not SALESOFFICE_CACHE_PERSISTENCE_ENABLED:
        return

    path = _PERSISTED_CACHE_FILES.get(region_name)
    if path is None:
        return

    payload = {
        "saved_at": datetime.utcnow().isoformat(),
        "region": region_name,
        "entries": _cm.export_region(region_name),
    }
    _atomic_write_json(path, payload)


def _persist_salesoffice_state() -> None:
    if not SALESOFFICE_CACHE_PERSISTENCE_ENABLED:
        return

    with _persist_state_lock:
        for region_name in ("analytics", "salesoffice_options", "salesoffice_detail"):
            try:
                _persist_cache_region(region_name)
            except (OSError, TypeError, ValueError) as exc:
                logger.warning("Persisting %s cache failed: %s", region_name, exc)


def _restore_cache_region(region_name: str) -> int:
    if not SALESOFFICE_CACHE_PERSISTENCE_ENABLED:
        return 0

    path = _PERSISTED_CACHE_FILES.get(region_name)
    if path is None or not path.exists():
        return 0

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Restoring %s cache failed: %s", region_name, exc)
        return 0

    entries = payload.get("entries") if isinstance(payload, dict) else {}
    if not isinstance(entries, dict):
        return 0
    return _cm.import_region(region_name, entries, clear_existing=False)


def _restore_salesoffice_persisted_state() -> bool:
    global _persist_restore_attempted

    if _persist_restore_attempted or not SALESOFFICE_CACHE_PERSISTENCE_ENABLED:
        return _cm.has_data("analytics")

    with _persist_restore_lock:
        if _persist_restore_attempted:
            return _cm.has_data("analytics")

        restored_counts = {
            region_name: _restore_cache_region(region_name)
            for region_name in ("analytics", "salesoffice_options", "salesoffice_detail")
        }
        _persist_restore_attempted = True

    if any(restored_counts.values()):
        logger.info(
            "Restored persisted SalesOffice caches: analytics=%d options=%d detail=%d",
            restored_counts.get("analytics", 0),
            restored_counts.get("salesoffice_options", 0),
            restored_counts.get("salesoffice_detail", 0),
        )
    return _cm.has_data("analytics")


# ── Background scheduler ─────────────────────────────────────────────

def start_salesoffice_scheduler() -> None:
    """Start periodic price collection in background thread."""
    global _scheduler_thread

    if not _salesoffice_scheduler_allowed():
        logger.info(
            "SalesOffice scheduler disabled for environment (production_only=%s)",
            not SALESOFFICE_ALLOW_NON_PROD_SCHEDULER,
        )
        return

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.info("SalesOffice scheduler already running")
        return

    _scheduler_stop.clear()

    def _loop():
        logger.info("SalesOffice price collector started (every %ds)", COLLECTION_INTERVAL)
        while not _scheduler_stop.is_set():
            _analysis_warming.set()
            try:
                _run_collection_cycle()
            except (OSError, ConnectionError, ValueError) as e:
                logger.error("SalesOffice collection cycle failed: %s", e, exc_info=True)
            finally:
                _analysis_warming.clear()
            _scheduler_stop.wait(COLLECTION_INTERVAL)
        logger.info("SalesOffice price collector stopped")

    _scheduler_thread = threading.Thread(target=_loop, daemon=True, name="salesoffice-collector")
    _scheduler_thread.start()


def stop_salesoffice_scheduler() -> None:
    """Stop the background scheduler."""
    _scheduler_stop.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=5)


def _is_scheduler_running() -> bool:
    """Return whether the background scheduler thread is currently alive."""
    return _scheduler_thread is not None and _scheduler_thread.is_alive()


# ── Internal helpers ──────────────────────────────────────────────────

def _run_collection_cycle() -> dict | None:
    """Collect prices and run analysis. Cache the result."""
    from src.analytics.collector import collect_prices
    from src.analytics.analyzer import run_analysis
    from src.analytics.price_store import init_db

    init_db()

    logger.info("SalesOffice: collecting prices...")
    df = collect_prices()
    if df.empty:
        logger.warning("SalesOffice: no data collected")
        return None

    logger.info("SalesOffice: collected %d rooms, running analysis...", len(df))
    analysis = run_analysis()

    _cm.set_data("analytics", analysis)

    # Pre-compute signals in background (avoids 30s+ on first request)
    try:
        from src.analytics.options_engine import compute_next_day_signals
        signals = compute_next_day_signals(analysis)
        _cm.set_data("signals", signals)
        logger.info("SalesOffice: precomputed %d signals", len(signals))
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("SalesOffice signal precompute failed: %s", exc)
        _cm.set_data("signals", None)

    try:
        from src.api.routers.analytics_router import _prime_salesoffice_route_caches

        cache_stats = _prime_salesoffice_route_caches(analysis)
        logger.info(
            "SalesOffice: precomputed route caches — options=%d detail=%d",
            cache_stats.get("options", 0),
            cache_stats.get("details", 0),
        )
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("SalesOffice route precompute failed: %s", exc)

    _persist_salesoffice_state()

    # ── Override Rules: auto-match and execute ───────────────────────
    try:
        from src.analytics.override_rules import (
            init_rules_db,
            get_rules,
            match_rules,
            execute_matched_overrides,
        )
        from src.api.routers.analytics_router import _get_or_build_options_base_payload

        init_rules_db()
        active_rules = get_rules(active_only=True)

        if active_rules:
            logger.info("Override rules: %d active rules — running matcher", len(active_rules))
            options_payload = _get_or_build_options_base_payload(
                analysis, t_days=None, include_chart=False,
                profile="lite", source=None, source_only=False,
            )
            options_rows = options_payload.get("rows", [])
            if options_rows:
                matches = match_rules(options_rows)
                if matches:
                    result = execute_matched_overrides(matches)
                    logger.info(
                        "Override rules: executed %d/%d (success=%d failed=%d skipped=%d)",
                        result["success"], result["total"],
                        result["success"], result["failed"], result["skipped"],
                    )
                else:
                    logger.info("Override rules: no matches found")
            else:
                logger.warning("Override rules: options payload empty — skipping")
        else:
            logger.debug("Override rules: no active rules")
    except Exception as exc:
        logger.warning("Override rules execution failed (non-fatal): %s", exc)

    logger.info(
        "SalesOffice: analysis complete — %d rooms, %d hotels",
        analysis.get("statistics", {}).get("total_rooms", 0),
        analysis.get("statistics", {}).get("total_hotels", 0),
    )

    # Daily refreshes — run once per calendar day (not every hour)
    from datetime import date as _date
    today_str = _date.today().isoformat()
    if _last_event_refresh_date[0] != today_str:
        _last_event_refresh_date[0] = today_str

        # Score data quality for all sources
        try:
            from src.analytics.data_quality import DataQualityScorer
            scorer = DataQualityScorer()
            quality_result = scorer.score_all()
            logger.info(
                "Data quality scored: %d sources, avg freshness %.2f, %d anomalies",
                quality_result.get("total_sources", 0),
                quality_result.get("avg_freshness", 0),
                quality_result.get("anomaly_count", 0),
            )
        except (ImportError, OSError, ValueError) as exc:
            logger.warning("Data quality scoring failed: %s", exc)

        # Score predictions where check-in has passed
        try:
            from src.analytics.accuracy_tracker import score_predictions
            score_result = score_predictions()
            if score_result.get("scored", 0) > 0:
                logger.info("Prediction scoring: %d predictions scored", score_result["scored"])
        except (ImportError, OSError, ValueError) as exc:
            logger.warning("Prediction scoring failed: %s", exc)

        # Ticketmaster + SeatGeek events
        try:
            from src.analytics.miami_events_fetcher import refresh_api_events
            event_result = refresh_api_events(days_ahead=90)
            logger.info("API events refreshed: %s", event_result)
        except (ConnectionError, TimeoutError, ValueError) as exc:
            logger.warning("Event API refresh failed: %s", exc)

        # Evaluate alerts on analysis results
        try:
            from src.services.alert_dispatcher import AlertDispatcher
            dispatcher = AlertDispatcher()
            predictions = analysis.get("predictions", {}) if analysis else {}
            # Detect surge: rooms with >10% expected increase
            surge_rooms = [
                {"room_id": rid, "signal": "CALL",
                 "confidence": float(p.get("signals", [{}])[0].get("confidence", 0) if p.get("signals") else 0)}
                for rid, p in predictions.items()
                if float(p.get("expected_change_pct", 0) or 0) > 10
            ]
            if len(surge_rooms) >= 5:
                dispatcher.dispatch(
                    rule_id="surge_detected",
                    severity="high",
                    message=f"{len(surge_rooms)} rooms with >10% predicted surge",
                    rooms=surge_rooms[:20],
                )

            # Detect drop: rooms with >10% expected decrease
            drop_rooms = [
                {"room_id": rid, "signal": "PUT",
                 "confidence": float(p.get("signals", [{}])[0].get("confidence", 0) if p.get("signals") else 0)}
                for rid, p in predictions.items()
                if float(p.get("expected_change_pct", 0) or 0) < -10
            ]
            if len(drop_rooms) >= 5:
                dispatcher.dispatch(
                    rule_id="drop_detected",
                    severity="high",
                    message=f"{len(drop_rooms)} rooms with >10% predicted drop",
                    rooms=drop_rooms[:20],
                )
        except (ImportError, OSError, ValueError) as exc:
            logger.warning("Alert dispatch failed: %s", exc)

        # Xotelo competitor rates (free, no key)
        try:
            from src.analytics.xotelo_store import fetch_rates
            hotel_ids = [66814, 854881, 20702, 24982]
            xotelo_total = sum(fetch_rates(hid, days_ahead=60) for hid in hotel_ids)
            logger.info("Xotelo competitor rates refreshed: %d records", xotelo_total)
        except (AttributeError, ConnectionError, OSError, TimeoutError, TypeError, ValueError) as exc:
            logger.warning("Xotelo refresh failed: %s", exc)

        # Makcorps historical prices (needs API key)
        try:
            from src.analytics.makcorps_store import fetch_historical_prices
            from config.settings import MAKCORPS_API_KEY
            if MAKCORPS_API_KEY:
                hotel_ids = [66814, 854881, 20702, 24982]
                mc_total = sum(fetch_historical_prices(hid) for hid in hotel_ids)
                logger.info("Makcorps historical prices refreshed: %d records", mc_total)
        except (ImportError, ConnectionError, TimeoutError, ValueError) as exc:
            logger.warning("Makcorps refresh failed: %s", exc)

    return analysis


def _get_cached_analysis() -> dict | None:
    """Return cached analysis or None — never blocks."""
    data = _cm.get_data("analytics")
    if not data:
        _restore_salesoffice_persisted_state()
        data = _cm.get_data("analytics")
    return dict(data) if data else None


_signals_computing = threading.Event()


def _get_cached_signals() -> list[dict]:
    """Return cached next-day signals. Never blocks — returns [] if not ready.

    Signals are precomputed during the collection cycle. If the cache
    is cold (e.g. right after deploy), kicks off background computation
    and returns empty list immediately.
    """
    cached = _cm.get_data("signals")
    if cached is not None:
        return cached

    # Kick off background computation (non-blocking)
    if not _signals_computing.is_set():
        _signals_computing.set()

        def _compute():
            try:
                analysis = _get_cached_analysis()
                if analysis and analysis.get("predictions"):
                    from src.analytics.options_engine import compute_next_day_signals
                    signals = compute_next_day_signals(analysis)
                    _cm.set_data("signals", signals)
                    logger.info("Background: cached %d signals", len(signals))
            except Exception as exc:
                logger.warning("Background signal compute failed: %s", exc)
            finally:
                _signals_computing.clear()

        threading.Thread(target=_compute, daemon=True, name="signals-warmup").start()

    return []  # caller gets empty → shows "warming up"


def _rebuild_cached_analysis_from_snapshots() -> dict | None:
    """Rebuild analysis cache from existing SQLite snapshots without recollecting."""
    from src.analytics.analyzer import run_analysis
    from src.analytics.price_store import get_snapshot_count, init_db

    init_db()
    snapshot_count = get_snapshot_count()
    if snapshot_count <= 0:
        return None

    logger.info(
        "Analytics cache cold — rebuilding from %d existing snapshot(s)",
        snapshot_count,
    )
    analysis = run_analysis()
    if isinstance(analysis, dict) and not analysis.get("error"):
        _cm.set_data("analytics", analysis)
        try:
            from src.api.routers.analytics_router import _prime_salesoffice_route_caches

            _prime_salesoffice_route_caches(analysis)
        except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("SalesOffice route precompute from snapshots failed: %s", exc)
        _persist_salesoffice_state()
        logger.info("Analytics cache rebuilt from existing snapshots")
        return analysis
    return None


def _kickoff_analysis_warmup() -> dict[str, object]:
    """Ensure analytics warmup is running in the background and report state."""
    data = _cm.get_data("analytics")
    if not data:
        _restore_salesoffice_persisted_state()
        data = _cm.get_data("analytics")
    if data:
        return {
            "cache_ready": True,
            "analysis_warming": False,
            "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
            "started": False,
            "detail": "Analysis cache is already ready.",
            "retry_after": 0,
        }

    if not _salesoffice_scheduler_allowed():
        return {
            "cache_ready": False,
            "analysis_warming": False,
            "scheduler_running": False,
            "started": False,
            "detail": "Analysis cache is cold and SalesOffice scheduler is disabled outside production.",
            "retry_after": COLLECTION_INTERVAL,
        }

    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        logger.info("SalesOffice scheduler not running — restarting on demand")
        start_salesoffice_scheduler()

    if _analysis_warming.is_set():
        return {
            "cache_ready": False,
            "analysis_warming": True,
            "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
            "started": False,
            "detail": "Analysis is warming up in background. Retry in 30-60 seconds.",
            "retry_after": 30,
        }

    if not SALESOFFICE_ON_DEMAND_WARMUP_ENABLED:
        return {
            "cache_ready": False,
            "analysis_warming": False,
            "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
            "started": False,
            "detail": "Analysis cache is cold. On-demand warmup is disabled; wait for the scheduled 3-hour refresh.",
            "retry_after": COLLECTION_INTERVAL,
        }

    started = False
    with _analysis_warmup_start_lock:
        if not _analysis_warming.is_set():
            _analysis_warming.set()
            started = True

            def _background_warm() -> None:
                try:
                    rebuilt: dict | None = None
                    with _analysis_rebuild_lock:
                        rebuilt = _rebuild_cached_analysis_from_snapshots()
                    if rebuilt:
                        return
                    _run_collection_cycle()
                except (ConnectionError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    logger.error("Background warmup failed: %s", exc, exc_info=True)
                finally:
                    _analysis_warming.clear()

            threading.Thread(target=_background_warm, daemon=True, name="analysis-warmup").start()

    return {
        "cache_ready": False,
        "analysis_warming": True,
        "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "started": started,
        "detail": (
            "Analysis cache is cold. Warmup started — retry in 60 seconds."
            if started
            else "Analysis is warming up in background. Retry in 30-60 seconds."
        ),
        "retry_after": 60 if started else 30,
    }


def _get_or_run_analysis() -> dict:
    """Return cached analysis or signal that warmup is in progress.

    NEVER runs a synchronous collection cycle in the request path.
    The background scheduler (started at app boot) fills the cache.
    If the cache is still empty, return 503 so Azure gateway doesn't
    hit the 230-second timeout.
    """
    data = _get_cached_analysis()
    if data:
        return dict(data)

    warmup = _kickoff_analysis_warmup()
    raise HTTPException(
        status_code=503,
        detail=str(warmup["detail"]),
        headers={"Retry-After": str(warmup["retry_after"])},
    )


def _loading_page(title: str, redirect_url: str) -> str:
    """Return a self-refreshing loading page while analysis warms up."""
    from src.utils.template_engine import render_template
    return render_template("loading.html", title=title, redirect_url=redirect_url)


# ── Computation helpers (used by multiple routers) ────────────────────

def _extract_curve_points(pred: dict, t_days: int | None) -> list[dict]:
    points = pred.get("forward_curve") or []
    if not points:
        points = pred.get("daily") or []

    normalized = []
    for p in points:
        date = p.get("date")
        price = p.get("predicted_price")
        if date is None or price is None:
            continue
        normalized.append({
            "date": date,
            "predicted_price": float(price),
            "lower_bound": p.get("lower_bound"),
            "upper_bound": p.get("upper_bound"),
            "t": p.get("t", p.get("days_remaining")),
        })

    if t_days is not None and t_days > 0:
        return normalized[:t_days]
    return normalized


def _derive_option_signal(pred: dict) -> str:
    change_pct = float(pred.get("expected_change_pct", 0) or 0)
    probability = pred.get("probability", {}) or {}
    up = float(probability.get("up", 0) or 0)
    down = float(probability.get("down", 0) or 0)

    # Price-drop skill logic: if expected_min drops >5% below current at any
    # point before check-in, the contract has PUT characteristics regardless
    # of where the final predicted price lands.
    current_price = float(pred.get("current_price", 0) or 0)
    expected_min = float(pred.get("expected_min_price", 0) or 0)
    scan_history = pred.get("scan_history") or {}
    scan_drops = int(scan_history.get("scan_actual_drops", 0) or 0)
    scan_drop_pct = float(scan_history.get("scan_price_change_pct", 0) or 0)
    put_decline_count = int(pred.get("put_decline_count", 0) or 0)

    # PUT: expected min is ≥5% below current, OR scan history shows real drops
    if current_price > 0 and expected_min > 0:
        min_vs_current_pct = (expected_min - current_price) / current_price * 100
        if min_vs_current_pct <= -5.0:
            return "PUT"

    # PUT: scan history shows actual price drops with downward trend
    if scan_drops >= 2 and scan_drop_pct < -5.0:
        return "PUT"

    # PUT: forward curve predicts multiple decline events (>5 declines in path)
    if put_decline_count >= 5 and expected_min < current_price:
        return "PUT"

    # Original logic for remaining cases
    if change_pct >= 0.5 or up > down + 0.1:
        return "CALL"
    if change_pct <= -0.5 or down > up + 0.1:
        return "PUT"
    return "NEUTRAL"


def _extract_sources(pred: dict, analysis: dict) -> list[dict]:
    signals = pred.get("signals") or []
    if signals:
        return [
            {
                "source": s.get("source"),
                "predicted_price": s.get("predicted_price"),
                "weight": s.get("weight"),
                "confidence": s.get("confidence"),
                "reasoning": s.get("reasoning"),
            }
            for s in signals
        ]

    model_info = analysis.get("model_info", {})
    return [
        {
            "source": "forward_curve",
            "predicted_price": pred.get("predicted_checkin_price"),
            "weight": 1.0,
            "confidence": None,
            "reasoning": (
                f"Empirical decay curve from {model_info.get('total_tracks', 0)} tracks "
                f"and {model_info.get('total_observations', 0)} observations"
            ),
        }
    ]


def _build_quality_summary(pred: dict, sources: list[dict]) -> dict:
    quality = str(pred.get("confidence_quality", "medium") or "medium").lower()
    base_score_map = {"high": 0.85, "medium": 0.65, "low": 0.4}
    base_score = base_score_map.get(quality, 0.6)

    signal_conf_values = []
    for src in sources:
        conf = src.get("confidence")
        if isinstance(conf, (int, float)):
            signal_conf_values.append(float(conf))

    signal_confidence_mean = round(mean(signal_conf_values), 3) if signal_conf_values else None
    if signal_confidence_mean is not None:
        score = round((base_score * 0.6) + (signal_confidence_mean * 0.4), 3)
    else:
        score = round(base_score, 3)

    return {
        "label": quality.upper(),
        "score": score,
        "signals_count": len(sources),
        "signal_confidence_mean": signal_confidence_mean,
    }


def _build_option_levels(pred: dict, option_signal: str, quality: dict) -> dict:
    change_pct = float(pred.get("expected_change_pct", 0) or 0)
    probability = pred.get("probability", {}) or {}
    up = float(probability.get("up", 0) or 0)
    down = float(probability.get("down", 0) or 0)
    quality_score = float(quality.get("score", 0.6) or 0.6)

    prob_bias = up - down
    change_component = max(-1.0, min(1.0, change_pct / 12.0))
    probability_component = max(-1.0, min(1.0, prob_bias))

    base_score = (change_component * 0.65) + (probability_component * 0.35)
    weighted_score = base_score * max(0.2, min(1.0, quality_score))
    weighted_score = max(-1.0, min(1.0, weighted_score))

    abs_strength = abs(weighted_score)
    level_10 = int(round(abs_strength * 10))
    if level_10 == 0 and option_signal in ("CALL", "PUT"):
        level_10 = 1

    if option_signal == "CALL":
        direction = "CALL"
    elif option_signal == "PUT":
        direction = "PUT"
    else:
        direction = "NEUTRAL"
        level_10 = 0

    call_level = level_10 if direction == "CALL" else 0
    put_level = level_10 if direction == "PUT" else 0
    label = f"{direction}_L{level_10}" if direction != "NEUTRAL" else "NEUTRAL_L0"

    return {
        "direction": direction,
        "level_10": level_10,
        "label": label,
        "call_strength_level_10": call_level,
        "put_strength_level_10": put_level,
        "score": round(weighted_score, 4),
    }


def _build_row_chart(curve_points: list[dict]) -> dict:
    labels = [p["date"] for p in curve_points]
    predicted = [round(float(p["predicted_price"]), 2) for p in curve_points]
    lower = [round(float(p["lower_bound"]), 2) if p.get("lower_bound") is not None else None for p in curve_points]
    upper = [round(float(p["upper_bound"]), 2) if p.get("upper_bound") is not None else None for p in curve_points]
    return {
        "labels": labels,
        "series": {
            "predicted_price": predicted,
            "lower_bound": lower,
            "upper_bound": upper,
        },
    }


def _build_put_path_insights(
    curve_points: list[dict],
    current_price: float,
    predicted_checkin: float,
    probability: dict | None = None,
    include_decline_events: bool = True,
) -> dict:
    """Build put-side path insights: dips, declines, expected drops.

    Combines actual curve path analysis with probability-based expected drops.
    """
    horizon = len(curve_points) if curve_points else 0
    prob = probability or {}
    p_down = float(prob.get("down", 30.0) or 30.0) / 100.0
    p_up = float(prob.get("up", 30.0) or 30.0) / 100.0

    # Probability-based expected drops/rises over the horizon
    expected_future_drops = round(p_down * horizon, 1) if horizon > 0 else 0.0
    expected_future_rises = round(p_up * horizon, 1) if horizon > 0 else 0.0

    if not curve_points:
        base_price = round(float(predicted_checkin), 2)
        return {
            "t_min_price": base_price,
            "t_max_price": base_price,
            "t_min_price_date": None,
            "t_max_price_date": None,
            "put_decline_count": 0,
            "put_total_decline_amount": 0.0,
            "put_largest_single_decline": 0.0,
            "put_first_decline_date": None,
            "put_largest_decline_date": None,
            "put_downside_from_now_to_t_min": round(max(0.0, float(current_price) - base_price), 2),
            "put_rebound_from_t_min_to_checkin": 0.0,
            "put_decline_events": [],
            "expected_future_drops": expected_future_drops,
            "expected_future_rises": expected_future_rises,
        }

    prices = [float(p.get("predicted_price", predicted_checkin) or predicted_checkin) for p in curve_points]
    min_idx = min(range(len(prices)), key=lambda i: prices[i])
    max_idx = max(range(len(prices)), key=lambda i: prices[i])

    t_min_price = prices[min_idx]
    t_max_price = prices[max_idx]
    t_min_price_date = curve_points[min_idx].get("date")
    t_max_price_date = curve_points[max_idx].get("date")

    decline_events: list[dict] = []
    for i in range(1, len(prices)):
        prev_price = prices[i - 1]
        next_price = prices[i]
        drop_amount = prev_price - next_price

        if drop_amount > 0:
            drop_pct = round(drop_amount / prev_price * 100.0, 2) if prev_price > 0 else 0.0
            decline_events.append({
                "from_date": curve_points[i - 1].get("date"),
                "to_date": curve_points[i].get("date"),
                "from_price": round(prev_price, 2),
                "to_price": round(next_price, 2),
                "drop_amount": round(drop_amount, 2),
                "drop_pct": drop_pct,
            })

    total_decline = round(sum(float(e["drop_amount"]) for e in decline_events), 2)
    largest_decline_event = max(decline_events, key=lambda e: e["drop_amount"], default=None)

    # Use actual path dips if found; otherwise use probability-based estimate
    actual_decline_count = len(decline_events)
    effective_decline_count = max(actual_decline_count, round(expected_future_drops))

    return {
        "t_min_price": round(t_min_price, 2),
        "t_max_price": round(t_max_price, 2),
        "t_min_price_date": t_min_price_date,
        "t_max_price_date": t_max_price_date,
        "put_decline_count": effective_decline_count,
        "put_total_decline_amount": total_decline,
        "put_largest_single_decline": round(float(largest_decline_event["drop_amount"]), 2) if largest_decline_event else 0.0,
        "put_first_decline_date": decline_events[0]["to_date"] if decline_events else None,
        "put_largest_decline_date": largest_decline_event["to_date"] if largest_decline_event else None,
        "put_downside_from_now_to_t_min": round(max(0.0, float(current_price) - t_min_price), 2),
        "put_rebound_from_t_min_to_checkin": round(max(0.0, float(predicted_checkin) - t_min_price), 2),
        "put_decline_events": decline_events if include_decline_events else [],
        "expected_future_drops": expected_future_drops,
        "expected_future_rises": expected_future_rises,
    }


def _build_info_badge(option_signal: str, quality: dict, sources: list[dict]) -> dict:
    score = float(quality.get("score", 0) or 0)
    icon = "i"
    if score < 0.5:
        icon = "?"

    quality_label = quality.get("label", "UNKNOWN")
    sources_text = _build_sources_tooltip(sources)
    tooltip = (
        f"Signal: {option_signal} | Quality: {quality_label} ({score:.2f})"
        f" | Sources: {sources_text}"
    )

    return {
        "icon": icon,
        "label": "information",
        "tooltip": tooltip,
        "show_sources_on_click": True,
    }


def _build_sources_tooltip(sources: list[dict]) -> str:
    parts: list[str] = []
    for src in sources[:4]:
        name = src.get("source") or "unknown"
        weight = src.get("weight")
        confidence = src.get("confidence")

        text = f"{name}"
        if isinstance(weight, (int, float)):
            text += f" w={float(weight):.2f}"
        if isinstance(confidence, (int, float)):
            text += f" c={float(confidence):.2f}"
        parts.append(text)

    if len(sources) > 4:
        parts.append(f"+{len(sources) - 4} more")
    return "; ".join(parts) if parts else "none"


def _build_source_validation(analysis: dict) -> dict:
    model_info = analysis.get("model_info", {}) or {}
    hist = analysis.get("historical_patterns_summary", {}) or {}
    events = analysis.get("events", {}) or {}
    flights = analysis.get("flight_demand", {}) or {}
    benchmarks = analysis.get("benchmarks", {}) or {}

    checks = {
        "forward_curve_tracks": int(model_info.get("total_tracks", 0) or 0) > 0,
        "forward_curve_observations": int(model_info.get("total_observations", 0) or 0) > 0,
        "historical_patterns_loaded": bool(hist.get("loaded", False)),
        "events_loaded": int(events.get("upcoming_events", 0) or 0) >= 0,
        "flight_demand_loaded": bool(flights),
        "benchmarks_available": benchmarks.get("status") in ("ok", "partial", "no_data"),
    }

    return {
        "checked_at": analysis.get("run_ts"),
        "checks": checks,
        "passed_checks": sum(1 for v in checks.values() if v),
        "total_checks": len(checks),
    }


def _build_system_capabilities(analysis: dict, total_rows: int) -> dict:
    model_info = analysis.get("model_info", {}) or {}
    events = analysis.get("events", {}) or {}
    flight = analysis.get("flight_demand", {}) or {}
    benchmarks = analysis.get("benchmarks", {}) or {}
    patterns = analysis.get("historical_patterns_summary", {}) or {}

    core_modules = {
        "forward_curve": bool(model_info.get("total_tracks", 0)),
        "historical_patterns": bool(patterns.get("loaded", False)),
        "events_enrichment": bool(events.get("total_events", 0) or events.get("upcoming_events", 0)),
        "flight_demand": flight.get("indicator", "NO_DATA") != "NO_DATA",
        "benchmarks": benchmarks.get("status") == "ok",
        "options_signal_engine": total_rows > 0,
        "option_levels_1_to_10": True,
        "source_transparency": True,
        "chart_payload": True,
    }

    return {
        "as_of": analysis.get("run_ts"),
        "trading_stack": {
            "signals": ["CALL", "PUT", "NEUTRAL"],
            "option_levels": "L1-L10",
            "row_metrics": [
                "expected_min_price",
                "expected_max_price",
                "touches_expected_min",
                "touches_expected_max",
                "count_price_changes_gt_20",
                "count_price_changes_lte_20",
            ],
            "explainability": ["sources", "quality", "info", "source_validation", "sources_audit_summary"],
        },
        "data_coverage": {
            "total_prediction_rows": total_rows,
            "tracks": int(model_info.get("total_tracks", 0) or 0),
            "observations": int(model_info.get("total_observations", 0) or 0),
            "events_upcoming": int(events.get("upcoming_events", 0) or 0),
            "flight_indicator": flight.get("indicator", "NO_DATA"),
            "benchmarks_status": benchmarks.get("status", "no_data"),
            "historical_combos": int(patterns.get("n_combos", 0) or 0),
        },
        "core_modules": core_modules,
        "active_modules": sum(1 for v in core_modules.values() if v),
        "total_modules": len(core_modules),
    }


def _build_sources_audit(analysis: dict, summary_only: bool = False) -> dict:
    from src.analytics.data_sources import get_sources_summary

    registry = get_sources_summary()
    sources = registry.get("sources", [])

    model_info = analysis.get("model_info", {}) or {}
    flight_demand = analysis.get("flight_demand", {}) or {}
    events = analysis.get("events", {}) or {}
    knowledge = analysis.get("knowledge", {}) or {}
    benchmarks = analysis.get("benchmarks", {}) or {}
    hist = analysis.get("historical_patterns_summary", {}) or {}

    audited = []
    for src in sources:
        sid = src.get("id")
        runtime_status = "not_checked"
        evidence = "No runtime probe configured"

        if sid == "salesoffice":
            tracks = int(model_info.get("total_tracks", 0) or 0)
            runtime_status = "active" if tracks > 0 else "degraded"
            evidence = f"forward_curve_tracks={tracks}"
        elif sid == "kiwi_flights":
            indicator = flight_demand.get("indicator", "NO_DATA")
            runtime_status = "active" if indicator != "NO_DATA" else "degraded"
            evidence = f"indicator={indicator}"
        elif sid == "miami_events_hardcoded":
            total_events = int(events.get("total_events", 0) or 0)
            runtime_status = "active" if total_events > 0 else "degraded"
            evidence = f"total_events={total_events}"
        elif sid == "tbo_hotels":
            market = knowledge.get("market", {}) or {}
            total_hotels = int(market.get("total_hotels", 0) or 0)
            runtime_status = "active" if total_hotels > 0 else "degraded"
            evidence = f"market_hotels={total_hotels}"
        elif sid == "hotel_booking_dataset":
            status = benchmarks.get("status", "no_data")
            runtime_status = "active" if status == "ok" else "degraded"
            evidence = f"benchmarks_status={status}"
        elif sid == "trivago_statista":
            statista_info = _detect_statista_benchmark_file()
            runtime_status = "active" if statista_info["exists"] else "degraded"
            if statista_info["exists"]:
                evidence = (
                    f"file={statista_info['path']}, "
                    f"months={statista_info['months_count']}, "
                    f"source={statista_info['source_name']}"
                )
            else:
                evidence = f"file_missing={statista_info['path']}"
        elif sid == "brightdata_mcp":
            brightdata_info = _detect_brightdata_mcp()
            runtime_status = "active" if brightdata_info["configured"] else "degraded"
            if brightdata_info["configured"]:
                evidence = (
                    f"mcp_config={brightdata_info['path']}, "
                    f"has_server_key={brightdata_info['has_server_key']}"
                )
            else:
                evidence = f"mcp_not_configured={brightdata_info['path']}"
        elif sid == "ota_brightdata_exports":
            ota_info = _detect_brightdata_ota_outputs()
            runtime_status = "active" if ota_info["exists"] and ota_info["rows"] > 0 else "degraded"
            if ota_info["exists"]:
                evidence = (
                    f"file={ota_info['path']}, rows={ota_info['rows']}, "
                    f"platforms={','.join(ota_info['platforms']) or 'none'}"
                )
            else:
                evidence = f"file_missing={ota_info['path']}"
        elif src.get("status") == "planned":
            runtime_status = "planned"
            evidence = "Source is configured as planned"

        audited.append({
            "id": sid,
            "name": src.get("name"),
            "category": src.get("category"),
            "configured_status": src.get("status"),
            "runtime_status": runtime_status,
            "evidence": evidence,
            "update_freq": src.get("update_freq"),
            "url": src.get("url"),
        })

    active_runtime = sum(1 for s in audited if s["runtime_status"] == "active")
    degraded_runtime = sum(1 for s in audited if s["runtime_status"] == "degraded")
    planned_runtime = sum(1 for s in audited if s["runtime_status"] == "planned")

    summary = {
        "checked_at": analysis.get("run_ts"),
        "total_sources": len(audited),
        "runtime_active": active_runtime,
        "runtime_degraded": degraded_runtime,
        "runtime_planned": planned_runtime,
        "historical_patterns_loaded": bool(hist.get("loaded", False)),
    }

    status = "ok" if degraded_runtime == 0 else "degraded"
    checks = {
        "has_sources": len(audited) > 0,
        "has_active_runtime_source": active_runtime > 0,
        "historical_patterns_loaded": bool(hist.get("loaded", False)),
    }

    if summary_only:
        return summary

    return {
        "status": status,
        "summary": summary,
        "checks": checks,
        "source_validation": _build_source_validation(analysis),
        "sources": audited,
    }


def _detect_statista_benchmark_file() -> dict:
    workspace_root = Path(__file__).resolve().parents[3]
    benchmark_path = workspace_root / "data" / "miami_benchmarks.json"

    result = {
        "path": str(benchmark_path),
        "exists": benchmark_path.exists(),
        "months_count": 0,
        "source_name": None,
    }
    if not benchmark_path.exists():
        return result

    try:
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
        months_data = payload.get("monthly_adr") or payload.get("adr_by_month") or []
        if isinstance(months_data, dict):
            months_count = len(months_data)
        elif isinstance(months_data, list):
            months_count = len(months_data)
        else:
            months_count = 0

        result["months_count"] = months_count
        result["source_name"] = payload.get("source") or payload.get("data_source")
        return result
    except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
        logger.warning("Benchmark data detection failed: %s", exc)
        return result


def _detect_brightdata_mcp() -> dict:
    workspace_root = Path(__file__).resolve().parents[3]
    mcp_path = workspace_root / ".mcp.json"
    result = {
        "path": str(mcp_path),
        "configured": False,
        "has_server_key": False,
    }
    if not mcp_path.exists():
        return result

    try:
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        servers = payload.get("mcpServers", {}) if isinstance(payload, dict) else {}
        has_server = "brightdata" in servers
        result["configured"] = has_server
        result["has_server_key"] = has_server
        return result
    except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
        logger.warning("BrightData MCP config detection failed: %s", exc)
        return result


def _detect_brightdata_ota_outputs() -> dict:
    workspace_root = Path(__file__).resolve().parents[3]
    summary_path = workspace_root / "data" / "processed" / "brightdata_ota_summary.json"
    result = {
        "path": str(summary_path),
        "exists": summary_path.exists(),
        "rows": 0,
        "platforms": [],
    }
    if not summary_path.exists():
        return result

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        result["rows"] = int(payload.get("rows", 0) or 0)
        platforms = payload.get("platforms", {})
        if isinstance(platforms, dict):
            result["platforms"] = sorted([str(k) for k in platforms.keys()])
        return result
    except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
        logger.warning("BrightData OTA output detection failed: %s", exc)
        return result
