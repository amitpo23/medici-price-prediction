"""Alert Bridge — connects streaming_alerts to alert_dispatcher channels.

This module bridges the NEW streaming_alerts system with the EXISTING alert_dispatcher,
allowing generated alerts to be dispatched through configured channels (Log, Webhook, Telegram).

Usage:
    from src.analytics.alert_bridge import dispatch_streaming_alerts

    result = dispatch_streaming_alerts(current_analysis, previous_analysis)
    # result = {
    #   "total_alerts": 5,
    #   "dispatched": 3,
    #   "suppressed": 2,
    #   "channels": {"log": "sent", "webhook": "sent", "telegram": "failed"}
    # }
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def dispatch_streaming_alerts(
    analysis: dict,
    previous_analysis: dict | None = None,
) -> dict:
    """Generate streaming alerts and dispatch them through configured channels.

    Integrates streaming_alerts.generate_alerts() with alert_dispatcher.AlertDispatcher.

    Args:
        analysis: Current analysis predictions dict with "predictions" and "data_quality" keys.
        previous_analysis: Previous cycle's analysis for flip/change detection.

    Returns:
        Summary dict with structure:
        {
            "total_alerts": int,           # total generated
            "dispatched": int,             # successfully dispatched
            "suppressed": int,             # deduplicated/suppressed
            "by_type": dict,               # alert type distribution
            "by_severity": dict,           # severity distribution
            "dispatch_results": dict,      # per-channel results
            "error": str (optional),       # error message if dispatch failed
        }
    """
    try:
        from src.analytics.streaming_alerts import generate_alerts
        from src.services.alert_dispatcher import AlertDispatcher

        # Generate alerts from analysis
        alert_summary = generate_alerts(analysis, previous_analysis)

        # Initialize dispatcher
        dispatcher = AlertDispatcher()

        # Track dispatch results
        dispatch_results = {}
        dispatch_success_count = 0
        dispatch_failure_count = 0

        # Dispatch each new (non-suppressed) alert
        for alert in alert_summary.alerts:
            if alert.suppressed:
                continue

            # Construct rule_id for dispatcher tracking/deduplication
            rule_id = f"streaming_{alert.alert_type}_{alert.detail_id or 'system'}"

            # Build rooms data for dispatcher (relevant room info)
            rooms = []
            if alert.detail_id > 0:
                # Extract relevant room data from analysis
                predictions = analysis.get("predictions", {})
                pred = predictions.get(str(alert.detail_id), {})

                if pred:
                    rooms.append({
                        "detail_id": alert.detail_id,
                        "hotel_id": alert.hotel_id,
                        "hotel_name": alert.hotel_name,
                        "category": alert.category,
                        "signal": pred.get("option_signal", "NEUTRAL"),
                        "confidence": float(pred.get("option_confidence", 0) or 0),
                        "current_price": float(pred.get("current_price", 0) or 0),
                    })

            # Dispatch via AlertDispatcher
            dispatch_result = dispatcher.dispatch(
                rule_id=rule_id,
                severity=alert.severity,
                message=alert.message,
                rooms=rooms,
            )

            # Track results per alert
            dispatch_results[alert.alert_id] = dispatch_result

            if dispatch_result.get("dispatched"):
                dispatch_success_count += 1
            else:
                dispatch_failure_count += 1

            logger.info(
                "Dispatched alert %s (%s) — rule_id=%s, severity=%s, rooms=%d",
                alert.alert_id, alert.alert_type, rule_id, alert.severity,
                len(rooms),
            )

        return {
            "total_alerts": alert_summary.total_generated,
            "dispatched": dispatch_success_count,
            "suppressed": alert_summary.total_suppressed,
            "by_type": alert_summary.by_type,
            "by_severity": alert_summary.by_severity,
            "dispatch_results": dispatch_results,
            "timestamp": alert_summary.timestamp,
        }

    except ImportError as e:
        logger.error("Failed to import required modules: %s", e, exc_info=True)
        return {
            "error": f"Missing module: {e}",
            "total_alerts": 0,
            "dispatched": 0,
            "suppressed": 0,
        }
    except Exception as e:
        logger.error("Unexpected error in dispatch_streaming_alerts: %s", e, exc_info=True)
        return {
            "error": str(e),
            "total_alerts": 0,
            "dispatched": 0,
            "suppressed": 0,
        }


def get_recent_dispatch_log(
    hours_back: int = 24,
    alert_type: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    """Query recent dispatched alerts from the alert_dispatcher log.

    Args:
        hours_back: How far back to look (default 24).
        alert_type: Filter by type (optional).
        severity: Filter by severity (optional).

    Returns:
        List of dispatch log entries.
    """
    try:
        from src.services.alert_dispatcher import get_alert_history

        # Get full alert history
        history = get_alert_history(days=max(1, hours_back // 24 + 1))

        # Filter by alert type if specified
        if alert_type:
            history = [h for h in history if alert_type in h.get("rule_id", "")]

        # Filter by severity if specified
        if severity:
            history = [h for h in history if h.get("severity") == severity]

        return history[:200]  # Limit results

    except Exception as e:
        logger.error("Failed to query dispatch log: %s", e, exc_info=True)
        return []


def get_dispatch_stats() -> dict:
    """Get alert dispatch statistics (volume, channels, top rules).

    Returns:
        Dict with total alerts, last 24h count, top rules, channel distribution.
    """
    try:
        from src.services.alert_dispatcher import get_alert_stats

        return get_alert_stats()

    except Exception as e:
        logger.error("Failed to query dispatch stats: %s", e, exc_info=True)
        return {
            "total_alerts": 0,
            "error": str(e),
        }
