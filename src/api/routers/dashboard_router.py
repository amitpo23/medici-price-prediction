"""HTML dashboard endpoints — browser-facing pages with auto-refresh."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.api.routers._shared_state import (
    _get_cached_analysis,
    _is_scheduler_running,
    _loading_page,
)
from src.utils.cache_manager import cache as _cm
from src.api.routers._options_html_gen import _generate_html, _generate_options_async_html

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
            "scheduler_running": _is_scheduler_running(),
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
    """Fast async HTML shell for options that loads data after first paint."""
    return HTMLResponse(content=_generate_options_async_html(t_days=t_days, signal=signal))


@dashboard_router.get("/dashboard/path-forecast", response_class=HTMLResponse)
async def salesoffice_path_forecast_view():
    """Path Forecast dashboard — full price lifecycle with turning points and trades."""
    from src.analytics.path_forecast_page import generate_path_forecast_html
    return HTMLResponse(content=generate_path_forecast_html())


@dashboard_router.get("/dashboard/sources", response_class=HTMLResponse)
async def salesoffice_sources_view():
    """Source Comparison dashboard — per-source analysis without ensemble blending."""
    from src.analytics.sources_page import generate_sources_html
    return HTMLResponse(content=generate_sources_html())
