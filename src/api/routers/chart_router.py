"""Chart API Router — Trading Chart indicator endpoints.

Serves indicator time series and BUY/SELL signals for the TradingView-style chart.
Does NOT modify any existing endpoints.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.analytics.chart_indicators import (
    INDICATOR_DEFS,
    build_indicator,
    compute_consensus,
    consensus_to_dict,
    get_active_indicators,
    indicator_to_dict,
)
from src.api.routers._shared_state import (
    _get_cached_analysis,
    _optional_api_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chart"])


@router.get("/chart/indicators/{option_id}")
async def chart_indicators(
    option_id: str,
    request: Request,
    api_key: str = _optional_api_key,
):
    """Return all 20 indicator time series for a specific option."""
    try:
        analysis = _get_cached_analysis()
        if not analysis:
            raise HTTPException(503, "Analysis not ready")

        # Find the option
        option = None
        for opt in analysis.get("options", []):
            if str(opt.get("id")) == option_id or opt.get("option_id") == option_id:
                option = opt
                break

        if not option:
            raise HTTPException(404, f"Option {option_id} not found")

        current_price = option.get("current_price", 0) or option.get("price", 0)
        fc_price = option.get("fc_price") or option.get("predicted_price")
        T = option.get("T", 30)
        hotel = option.get("hotel", "")
        check_in = option.get("check_in", "")

        # Build indicators from available data
        indicators = {}

        # Price Scan — from scan history in option
        scan_history = option.get("scan_history", [])
        if scan_history:
            indicators["price_scan"] = build_indicator(
                "price_scan", scan_history, T, current_price, fc_price)

        # Forward Curve — from FC points in option
        fc_points = option.get("fc_points", [])
        if fc_points:
            indicators["forward_curve"] = build_indicator(
                "forward_curve", fc_points, T, current_price, fc_price)

        # Historical T — from historical patterns
        hist_points = option.get("historical_prices", [])
        if hist_points:
            indicators["historical_t"] = build_indicator(
                "historical_t", hist_points, T, current_price, fc_price)

        # YoY Price
        yoy_points = option.get("yoy_prices", [])
        if yoy_points:
            indicators["yoy_price"] = build_indicator(
                "yoy_price", yoy_points, T, current_price, fc_price)

        # Macro indicators from yfinance collector
        try:
            from src.collectors.yfinance_collector import YFinanceCollector
            yfc = YFinanceCollector()
            for sym_key, sym_name in [("jets_etf", "JETS"), ("vix", "^VIX")]:
                series = yfc.get_indicator_series(sym_name, days_back=180)
                if series:
                    indicators[sym_key] = build_indicator(
                        sym_key, series, T, current_price, fc_price)
            reits_series = yfc.get_reits_avg_series(180)
            if reits_series:
                indicators["hotel_reits"] = build_indicator(
                    "hotel_reits", reits_series, T, current_price, fc_price)
        except Exception as exc:
            logger.debug("yfinance indicators unavailable: %s", exc)

        # Hotel PPI from FRED
        try:
            from src.collectors.fred_collector import get_hotel_ppi_trend, fetch_fred_series
            ppi_data = fetch_fred_series("PCU721110721110", months_back=12)
            if ppi_data:
                ppi_series = [{"t": p["date"], "v": p["value"]} for p in ppi_data]
                indicators["hotel_ppi"] = build_indicator(
                    "hotel_ppi", ppi_series, T, current_price, fc_price)
        except Exception as exc:
            logger.debug("FRED PPI unavailable: %s", exc)

        # Airbnb
        try:
            from src.collectors.airbnb_collector import AirbnbCollector
            ac = AirbnbCollector()
            airbnb_series = ac.get_indicator_series("Miami Beach")
            if airbnb_series:
                indicators["airbnb_avg"] = build_indicator(
                    "airbnb_avg", airbnb_series, T, current_price, fc_price)
        except Exception as exc:
            logger.debug("Airbnb indicator unavailable: %s", exc)

        # BTS Flights
        try:
            from src.collectors.bts_collector import BTSCollector
            bc = BTSCollector()
            bts_series = bc.get_indicator_series()
            if bts_series:
                indicators["bts_flights"] = build_indicator(
                    "bts_flights", bts_series, T, current_price, fc_price)
        except Exception as exc:
            logger.debug("BTS flights indicator unavailable: %s", exc)

        # Enrichment indicators (events, seasonality) from option metadata
        events_impact = option.get("events_impact", [])
        if events_impact:
            indicators["events"] = build_indicator(
                "events", events_impact, T, current_price, fc_price)

        seasonality_data = option.get("seasonality_data", [])
        if seasonality_data:
            indicators["seasonality"] = build_indicator(
                "seasonality", seasonality_data, T, current_price, fc_price)

        # Margin %
        buy_price = option.get("buy_price") or option.get("cost_price")
        if buy_price and current_price and buy_price > 0:
            margin_pct = (current_price - buy_price) / buy_price * 100
            indicators["margin"] = build_indicator(
                "margin", [{"t": check_in, "v": round(margin_pct, 1)}],
                T, current_price, fc_price)

        # Compute consensus
        consensus = compute_consensus(indicators, T)

        return JSONResponse({
            "option_id": option_id,
            "hotel": hotel,
            "check_in": check_in,
            "T": T,
            "current_price": current_price,
            "indicators": {k: indicator_to_dict(v) for k, v in indicators.items()},
            "consensus": consensus_to_dict(consensus),
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("chart_indicators error: %s", exc, exc_info=True)
        raise HTTPException(500, f"Chart indicators error: {exc}")


@router.get("/chart/signals/{option_id}")
async def chart_signals(
    option_id: str,
    request: Request,
    api_key: str = _optional_api_key,
):
    """Return BUY/SELL signal history for an option."""
    try:
        # For now, return current consensus as a single signal point
        # Future: compute historical signals from stored scan data
        resp = await chart_indicators(option_id, request, api_key)
        data = resp.body.decode() if hasattr(resp, 'body') else "{}"
        import json
        parsed = json.loads(data)
        consensus = parsed.get("consensus", {})

        return JSONResponse({
            "option_id": option_id,
            "signals": [{
                "t": parsed.get("check_in", ""),
                "type": consensus.get("signal", "NEUTRAL"),
                "confidence": consensus.get("score", 0.5),
                "agreeing": consensus.get("votes_buy", 0) if consensus.get("signal") == "BUY"
                           else consensus.get("votes_sell", 0),
                "total": consensus.get("total_votes", 0),
            }]
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("chart_signals error: %s", exc, exc_info=True)
        raise HTTPException(500, f"Chart signals error: {exc}")


@router.get("/dashboard/trading-chart", response_class=HTMLResponse)
async def trading_chart_page(request: Request):
    """Serve the TradingView-style trading chart dashboard."""
    try:
        from src.analytics.chart_indicators import INDICATOR_DEFS
        from pathlib import Path

        template_path = Path(__file__).parent.parent.parent / "templates" / "trading_chart.html"
        if template_path.exists():
            return HTMLResponse(template_path.read_text())

        # Fallback: minimal page that loads chart via JS
        return HTMLResponse(f"""
        <html><head><title>Trading Chart — Loading...</title></head>
        <body style="background:#0a0a0a;color:#fff;font-family:monospace;padding:40px;">
        <h1>Trading Chart</h1>
        <p>Template not found. Create: src/templates/trading_chart.html</p>
        </body></html>
        """)
    except Exception as exc:
        logger.error("trading_chart_page error: %s", exc)
        return HTMLResponse(f"<h1>Error: {exc}</h1>", status_code=500)
