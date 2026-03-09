"""HTML dashboard endpoints — browser-facing pages with auto-refresh."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.api.routers._shared_state import (
    _scheduler_thread,
    _get_cached_analysis,
    _get_or_run_analysis,
    _loading_page,
    _extract_curve_points,
    _derive_option_signal,
    _extract_sources,
    _build_quality_summary,
    _build_option_levels,
    _build_put_path_insights,
)
from src.utils.cache_manager import cache as _cm
from src.api.routers._options_html_gen import _generate_html, _generate_options_html

logger = logging.getLogger(__name__)

dashboard_router = APIRouter()


@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def salesoffice_dashboard():
    """Full interactive HTML dashboard with Plotly charts."""
    analysis = _get_cached_analysis()
    if analysis is None:
        return HTMLResponse(content=_loading_page(
            "Analytics Dashboard", "/api/v1/salesoffice/dashboard"
        ))
    html = _generate_html(analysis)
    return HTMLResponse(content=html)


@dashboard_router.get("/home", response_class=HTMLResponse)
async def salesoffice_home():
    """Consolidated landing page — hub linking to all analytics pages."""
    from src.analytics.landing_page import generate_landing_html

    status_data = None
    try:
        from src.analytics.price_store import get_snapshot_count, load_latest_snapshot, init_db
        init_db()
        latest = load_latest_snapshot()
        status_data = {
            "total_rooms": len(latest) if not latest.empty else 0,
            "total_hotels": latest["hotel_id"].nunique() if not latest.empty else 0,
            "snapshots_collected": get_snapshot_count(),
            "scheduler_running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        }
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("Landing page status data unavailable: %s", exc)

    html = generate_landing_html(status_data)
    return HTMLResponse(content=html)


@dashboard_router.get("/info", response_class=HTMLResponse)
def salesoffice_info():
    """System information & documentation — how everything works."""
    from src.analytics.info_page import generate_info_html
    from src.analytics.data_sources import DATA_SOURCES

    db_stats = None
    try:
        from src.data.trading_db import run_trading_query
        df = run_trading_query("""
            SELECT t.name AS table_name, p.rows AS row_count,
                   SUM(a.total_pages) * 8 / 1024 AS size_mb
            FROM sys.tables t
            INNER JOIN sys.indexes i ON t.object_id = i.object_id
            INNER JOIN sys.partitions p ON i.object_id = p.object_id
                AND i.index_id = p.index_id
            INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE i.index_id <= 1
            GROUP BY t.name, p.rows
        """)
        db_stats = {
            "total_tables": len(df),
            "total_rows": int(df["row_count"].sum()),
            "total_size_mb": int(df["size_mb"].sum()),
        }
    except (OSError, ConnectionError, ValueError) as exc:
        logger.warning("DB stats query failed: %s", exc)

    html = generate_info_html(DATA_SOURCES, db_stats)
    return HTMLResponse(content=html)


@dashboard_router.get("/insights", response_class=HTMLResponse)
async def salesoffice_insights():
    """Price insights — when prices go up/down, days below/above today."""
    from src.analytics.insights_page import generate_insights_html

    analysis = _get_cached_analysis()
    if analysis is None:
        return HTMLResponse(content=_loading_page(
            "Price Insights", "/api/v1/salesoffice/insights"
        ))
    html = generate_insights_html(analysis)
    return HTMLResponse(content=html)


@dashboard_router.get("/yoy", response_class=HTMLResponse)
async def salesoffice_yoy():
    """Year-over-Year price comparison."""
    from src.analytics.yoy_page import generate_yoy_html

    cached = _cm.get_data("yoy")
    if cached is not None:
        return HTMLResponse(content=generate_yoy_html(cached))

    if _cm.is_loading("yoy"):
        return HTMLResponse(content=_loading_page(
            "Year-over-Year Price Comparison", "/api/v1/salesoffice/yoy"
        ))

    def _run_yoy():
        from src.data.yoy_db import load_unified_yoy_data
        from src.analytics.yoy_analysis import (
            build_scan_timeseries,
            build_t_year_pivot,
            build_yoy_comparison,
            build_calendar_spread,
        )
        from src.analytics.term_structure_engine import build_all_term_structures
        _cm.set_loading("yoy", True)
        try:
            HOTEL_IDS = [66814, 854881, 20702, 24982]
            raw = load_unified_yoy_data(HOTEL_IDS)
            if raw.empty:
                logger.warning("YoY: no data returned from DB")
                return
            ts = build_scan_timeseries(raw)
            ts_structures = build_all_term_structures(ts, HOTEL_IDS)
            result: dict = {}
            for hid in HOTEL_IDS:
                result[hid] = {
                    "pivot": build_t_year_pivot(ts, hid),
                    "comparison": build_yoy_comparison(ts, hid),
                    "spread": build_calendar_spread(ts, hid),
                    "term_structure": ts_structures.get(int(hid), {}),
                }
            _cm.set_data("yoy", result)
            logger.info("YoY cache populated for %d hotels", len(result))
        except (OSError, ConnectionError, ValueError) as exc:
            logger.error("YoY background load failed: %s", exc, exc_info=True)
        finally:
            _cm.set_loading("yoy", False)

    t = threading.Thread(target=_run_yoy, daemon=True)
    t.start()
    return HTMLResponse(content=_loading_page(
        "Year-over-Year Price Comparison", "/api/v1/salesoffice/yoy"
    ))


@dashboard_router.get("/options", response_class=HTMLResponse)
async def salesoffice_options_html():
    """Options trading signals + 6-month expiry-relative analytics."""
    from src.analytics.options_page import generate_options_html

    analysis = _get_cached_analysis()
    if analysis is None:
        return HTMLResponse(content=_loading_page(
            "Options Trading Signals", "/api/v1/salesoffice/options"
        ))

    expiry_data: dict = {}
    cached_expiry = _cm.get_data("options_expiry")
    if cached_expiry is not None:
        expiry_data = dict(cached_expiry)
    elif not _cm.is_loading("options_expiry"):
        def _run_options_expiry():
            from src.data.yoy_db import load_unified_yoy_data
            from src.analytics.options_engine import build_expiry_metrics
            _cm.set_loading("options_expiry", True)
            try:
                HOTEL_IDS = [66814, 854881, 20702, 24982]
                df = load_unified_yoy_data(HOTEL_IDS)
                if not df.empty:
                    summaries, rollups = build_expiry_metrics(df)
                    _cm.set_data("options_expiry", {
                        "summaries": summaries.to_dict("records") if not summaries.empty else [],
                        "rollups": rollups,
                    })
                    logger.info("Options expiry cache populated")
            except (OSError, ConnectionError, ValueError) as exc:
                logger.error("Options expiry load failed: %s", exc, exc_info=True)
            finally:
                _cm.set_loading("options_expiry", False)

        threading.Thread(target=_run_options_expiry, daemon=True).start()

    html = generate_options_html(analysis, expiry_data)
    return HTMLResponse(content=html)


@dashboard_router.get("/charts", response_class=HTMLResponse)
async def salesoffice_charts():
    """Chart Pack — 3-tab visual analysis."""
    from src.analytics.charts_page import generate_charts_html

    cached = _cm.get_data("charts")
    if cached is not None:
        return HTMLResponse(content=generate_charts_html(cached))

    if _cm.is_loading("charts"):
        return HTMLResponse(content=_loading_page(
            "Chart Pack", "/api/v1/salesoffice/charts"
        ))

    def _run_charts():
        from src.analytics.charts_engine import build_charts_cache
        _cm.set_loading("charts", True)
        try:
            HOTEL_IDS = [66814, 854881, 20702, 24982]
            result = build_charts_cache(HOTEL_IDS)
            if result:
                _cm.set_data("charts", result)
                logger.info("Charts cache populated")
        except (OSError, ConnectionError, ValueError) as exc:
            logger.error("Charts background load failed: %s", exc, exc_info=True)
        finally:
            _cm.set_loading("charts", False)

    t = threading.Thread(target=_run_charts, daemon=True)
    t.start()
    return HTMLResponse(content=_loading_page(
        "Chart Pack", "/api/v1/salesoffice/charts"
    ))


@dashboard_router.get("/accuracy", response_class=HTMLResponse)
async def salesoffice_accuracy():
    """Prediction Accuracy Tracker."""
    from src.analytics.accuracy_page import generate_accuracy_html

    cached = _cm.get_data("accuracy")
    if cached is not None:
        return HTMLResponse(content=generate_accuracy_html(cached))

    if _cm.is_loading("accuracy"):
        return HTMLResponse(content=_loading_page(
            "Prediction Accuracy Tracker", "/api/v1/salesoffice/accuracy"
        ))

    def _run_accuracy():
        from src.analytics.accuracy_engine import build_accuracy_data
        _cm.set_loading("accuracy", True)
        try:
            result = build_accuracy_data()
            if result:
                _cm.set_data("accuracy", result)
                logger.info("Accuracy cache populated")
        except (OSError, ConnectionError, ValueError) as exc:
            logger.error("Accuracy background load failed: %s", exc, exc_info=True)
        finally:
            _cm.set_loading("accuracy", False)

    threading.Thread(target=_run_accuracy, daemon=True).start()
    return HTMLResponse(content=_loading_page(
        "Prediction Accuracy Tracker", "/api/v1/salesoffice/accuracy"
    ))


@dashboard_router.get("/providers", response_class=HTMLResponse)
async def salesoffice_providers():
    """Provider Price Comparison."""
    from src.analytics.provider_page import generate_provider_html

    cached = _cm.get_data("provider")
    if cached is not None:
        return HTMLResponse(content=generate_provider_html(cached))

    if _cm.is_loading("provider"):
        return HTMLResponse(content=_loading_page(
            "Provider Price Comparison", "/api/v1/salesoffice/providers"
        ))

    def _run_providers():
        from src.analytics.provider_engine import build_provider_data
        _cm.set_loading("provider", True)
        try:
            result = build_provider_data(days_back=90)
            if result:
                _cm.set_data("provider", result)
                logger.info("Provider cache populated")
        except (OSError, ConnectionError, ValueError) as exc:
            logger.error("Provider background load failed: %s", exc, exc_info=True)
        finally:
            _cm.set_loading("provider", False)

    threading.Thread(target=_run_providers, daemon=True).start()
    return HTMLResponse(content=_loading_page(
        "Provider Price Comparison", "/api/v1/salesoffice/providers"
    ))


@dashboard_router.get("/alerts", response_class=HTMLResponse)
async def salesoffice_alerts():
    """Price Alert System — breach threshold monitoring."""
    from src.analytics.alerts_page import generate_alerts_html

    cached = _cm.get_data("charts")
    if cached is not None:
        return HTMLResponse(content=generate_alerts_html(cached))

    if _cm.is_loading("charts"):
        return HTMLResponse(content=_loading_page(
            "Price Alert System", "/api/v1/salesoffice/alerts"
        ))

    def _run_charts_for_alerts():
        from src.analytics.charts_engine import build_charts_cache
        _cm.set_loading("charts", True)
        try:
            HOTEL_IDS = [66814, 854881, 20702, 24982]
            result = build_charts_cache(HOTEL_IDS)
            if result:
                _cm.set_data("charts", result)
                logger.info("Charts cache populated (for alerts)")
        except (OSError, ConnectionError, ValueError) as exc:
            logger.error("Charts load for alerts failed: %s", exc, exc_info=True)
        finally:
            _cm.set_loading("charts", False)

    threading.Thread(target=_run_charts_for_alerts, daemon=True).start()
    return HTMLResponse(content=_loading_page(
        "Price Alert System", "/api/v1/salesoffice/alerts"
    ))


@dashboard_router.get("/freshness", response_class=HTMLResponse)
async def salesoffice_freshness():
    """Data Freshness Monitor."""
    from src.analytics.freshness_engine import build_freshness_data
    from src.analytics.freshness_page import generate_freshness_html

    try:
        data = build_freshness_data()
        return HTMLResponse(content=generate_freshness_html(data))
    except (ValueError, TypeError, KeyError, OSError) as e:
        logger.error("Freshness monitor failed: %s", e, exc_info=True)
        return HTMLResponse(content=_loading_page(
            "Data Freshness Monitor", "/api/v1/salesoffice/freshness"
        ))


@dashboard_router.get("/options/view", response_class=HTMLResponse)
async def salesoffice_options_view(
    t_days: int | None = None,
    signal: str | None = None,
):
    """Interactive HTML dashboard for Call/Put options."""
    import json

    analysis = _get_or_run_analysis()
    predictions = analysis.get("predictions", {})

    rows: list[dict] = []
    for detail_id, pred in predictions.items():
        curve_points = _extract_curve_points(pred, t_days)
        path_prices = [p["predicted_price"] for p in curve_points]

        current_price = float(pred.get("current_price", 0) or 0)
        predicted_checkin = float(pred.get("predicted_checkin_price", current_price) or current_price)

        if path_prices:
            expected_min_price = min(path_prices)
            expected_max_price = max(path_prices)

            price_range = max(expected_max_price - expected_min_price, 1.0)
            touch_band = max(price_range * 0.10, 1.0)
            touches_min = sum(1 for px in path_prices if abs(px - expected_min_price) <= touch_band)
            touches_max = sum(1 for px in path_prices if abs(px - expected_max_price) <= touch_band)

            changes_gt_20 = 0
            changes_lte_20 = 0
            for i in range(1, len(path_prices)):
                prev_px = path_prices[i - 1]
                if prev_px > 0:
                    delta = path_prices[i] - prev_px
                    if delta < -0.001:
                        changes_gt_20 += 1
                    else:
                        changes_lte_20 += 1
        else:
            expected_min_price = predicted_checkin
            expected_max_price = predicted_checkin
            touches_min = 1
            touches_max = 1
            changes_gt_20 = 0

        option_signal = _derive_option_signal(pred)
        sources = _extract_sources(pred, analysis)
        quality = _build_quality_summary(pred, sources)
        option_levels = _build_option_levels(pred, option_signal, quality)
        put_insights = _build_put_path_insights(
            curve_points, current_price, predicted_checkin,
            probability=pred.get("probability"),
        )
        scan = pred.get("scan_history") or {}

        signals_list = pred.get("signals") or []
        fc_sig = next((s for s in signals_list if s.get("source") == "forward_curve"), None)
        hist_sig = next((s for s in signals_list if s.get("source") == "historical_pattern"), None)
        ml_sig = next((s for s in signals_list if s.get("source") == "ml_forecast"), None)

        fc_pts = pred.get("forward_curve") or []
        ev_adj = sum(float(p.get("event_adj_pct", 0) or 0) for p in fc_pts)
        se_adj = sum(float(p.get("season_adj_pct", 0) or 0) for p in fc_pts)
        dm_adj = sum(float(p.get("demand_adj_pct", 0) or 0) for p in fc_pts)
        mo_adj = sum(float(p.get("momentum_adj_pct", 0) or 0) for p in fc_pts)

        rows.append({
            "detail_id": int(detail_id),
            "hotel_name": pred.get("hotel_name", ""),
            "category": pred.get("category", ""),
            "board": pred.get("board", ""),
            "date_from": pred.get("date_from", ""),
            "days_to_checkin": pred.get("days_to_checkin"),
            "option_signal": option_signal,
            "current_price": round(current_price, 2),
            "predicted_checkin_price": round(predicted_checkin, 2),
            "expected_change_pct": round(float(pred.get("expected_change_pct", 0) or 0), 2),
            "expected_min_price": round(float(expected_min_price), 2),
            "expected_max_price": round(float(expected_max_price), 2),
            "touches_min": touches_min,
            "touches_max": touches_max,
            "changes_gt_20": changes_gt_20,
            "quality_label": quality.get("label", ""),
            "quality_score": quality.get("score", 0),
            "level": option_levels.get("level_10", 0),
            "level_label": option_levels.get("label", ""),
            "sources_count": len(sources),
            "put_decline_count": put_insights.get("put_decline_count", 0),
            "put_total_decline": put_insights.get("put_total_decline_amount", 0),
            "put_largest_decline": put_insights.get("put_largest_single_decline", 0),
            "expected_future_drops": put_insights.get("expected_future_drops", 0),
            "expected_future_rises": put_insights.get("expected_future_rises", 0),
            "t_min_price": put_insights.get("t_min_price", 0),
            "t_max_price": put_insights.get("t_max_price", 0),
            "t_min_price_date": put_insights.get("t_min_price_date", ""),
            "t_max_price_date": put_insights.get("t_max_price_date", ""),
            "scan_snapshots": scan.get("scan_snapshots", 0),
            "first_scan_price": scan.get("first_scan_price"),
            "scan_price_change": scan.get("scan_price_change", 0),
            "scan_price_change_pct": scan.get("scan_price_change_pct", 0),
            "scan_actual_drops": scan.get("scan_actual_drops", 0),
            "scan_actual_rises": scan.get("scan_actual_rises", 0),
            "scan_total_drop_amount": scan.get("scan_total_drop_amount", 0),
            "scan_total_rise_amount": scan.get("scan_total_rise_amount", 0),
            "scan_trend": scan.get("scan_trend", "no_data"),
            "scan_price_series": scan.get("scan_price_series", []),
            "scan_max_single_drop": scan.get("scan_max_single_drop", 0),
            "scan_max_single_rise": scan.get("scan_max_single_rise", 0),
            "first_scan_date": scan.get("first_scan_date"),
            "latest_scan_date": scan.get("latest_scan_date"),
            "latest_scan_price": scan.get("latest_scan_price"),
            "scan_min_price": min((p.get("price", 0) for p in (scan.get("scan_price_series") or []) if p.get("price")), default=None),
            "scan_max_price": max((p.get("price", 0) for p in (scan.get("scan_price_series") or []) if p.get("price")), default=None),
            "market_avg_price": (pred.get("market_benchmark") or {}).get("market_avg_price", 0),
            "market_pressure": (pred.get("market_benchmark") or {}).get("pressure", 0),
            "market_competitor_hotels": (pred.get("market_benchmark") or {}).get("competitor_hotels", 0),
            "market_city": (pred.get("market_benchmark") or {}).get("city", ""),
            "market_stars": (pred.get("market_benchmark") or {}).get("stars", 0),
            "fc_price": round(float(fc_sig["predicted_price"]), 2) if fc_sig and fc_sig.get("predicted_price") else None,
            "fc_confidence": round(float(fc_sig.get("confidence", 0) or 0), 2) if fc_sig else 0,
            "fc_weight": round(float(fc_sig.get("weight", 0) or 0), 2) if fc_sig else 0,
            "hist_price": round(float(hist_sig["predicted_price"]), 2) if hist_sig and hist_sig.get("predicted_price") else None,
            "hist_confidence": round(float(hist_sig.get("confidence", 0) or 0), 2) if hist_sig else 0,
            "hist_weight": round(float(hist_sig.get("weight", 0) or 0), 2) if hist_sig else 0,
            "ml_price": round(float(ml_sig["predicted_price"]), 2) if ml_sig and ml_sig.get("predicted_price") else None,
            "event_adj_total": round(ev_adj, 2),
            "season_adj_total": round(se_adj, 2),
            "demand_adj_total": round(dm_adj, 2),
            "momentum_adj_total": round(mo_adj, 2),
            "fc_reasoning": (fc_sig.get("reasoning", "") if fc_sig else ""),
            "hist_reasoning": (hist_sig.get("reasoning", "") if hist_sig else ""),
            "ml_reasoning": (ml_sig.get("reasoning", "") if ml_sig else ""),
            "prediction_method": pred.get("prediction_method", ""),
            "explanation_factors": pred.get("explanation", {}).get("factors", []),
            "fc_series": [{"d": p["date"][-5:], "p": round(p["predicted_price"], 1),
                           "lo": round(float(p.get("lower_bound") or p["predicted_price"]), 1),
                           "hi": round(float(p.get("upper_bound") or p["predicted_price"]), 1)}
                          for p in curve_points],
            "fc_adj_series": [{"d": p["date"][-5:],
                               "ev": round(float(p.get("event_adj_pct", 0) or 0), 2),
                               "se": round(float(p.get("season_adj_pct", 0) or 0), 2),
                               "dm": round(float(p.get("demand_adj_pct", 0) or 0), 2),
                               "mo": round(float(p.get("momentum_adj_pct", 0) or 0), 2)}
                              for p in (pred.get("forward_curve") or [])[:len(curve_points)]],
            "momentum": pred.get("momentum", {}),
            "regime": pred.get("regime", {}),
            "yoy": pred.get("yoy_comparison", {}),
        })

    rows.sort(key=lambda x: (
        0 if x["option_signal"] in ("CALL", "PUT") else 1,
        -abs(float(x.get("expected_change_pct", 0))),
    ))

    if signal:
        sig_upper = signal.strip().upper()
        if sig_upper in ("CALL", "PUT", "NEUTRAL"):
            rows = [r for r in rows if r["option_signal"] == sig_upper]

    # Enrich rows with AI intelligence
    try:
        from src.analytics.ai_intelligence import detect_anomaly, assess_risk

        for r in rows:
            scan_prices_raw = r.get("scan_price_series", [])
            scan_prices = [
                p.get("price", 0) if isinstance(p, dict) else p
                for p in scan_prices_raw
            ] if scan_prices_raw else []

            anomaly = detect_anomaly(
                hotel_name=r.get("hotel_name", ""),
                current_price=r.get("current_price", 0),
                predicted_price=r.get("predicted_checkin_price", 0),
                change_pct=r.get("expected_change_pct", 0),
                scan_prices=scan_prices,
                regime="NORMAL",
            )
            risk = assess_risk(
                current_price=r.get("current_price", 0),
                predicted_price=r.get("predicted_checkin_price", 0),
                change_pct=r.get("expected_change_pct", 0),
                days_to_checkin=r.get("days_to_checkin", 0) or 0,
                scan_count=r.get("scan_snapshots", 0),
                regime="NORMAL",
                quality_score=r.get("quality_score", 0.5),
            )
            r["ai_anomaly"] = anomaly.to_dict()
            r["ai_risk"] = risk.to_dict()
            r["ai_conviction"] = ""
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.debug(f"AI enrichment for HTML skipped: {e}")

    html = _generate_options_html(rows, analysis, t_days)
    return HTMLResponse(content=html)
