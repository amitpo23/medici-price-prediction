"""FRED economic indicators for Miami hotel market context.

Free API key required (fred.stlouisfed.org/docs/api/api_key.html).
Display only — not used in forward curve predictions.

Tracked series:
  hotel_employment   : IPUTN721110W200000000  FL hotel & motel employment (weekly, SA)
  lodging_cpi        : CUSR0000SEHB           CPI lodging away from home (US, monthly)
  fl_hospitality_jobs: FLLEIH                 FL leisure & hospitality employment (monthly)
"""
from __future__ import annotations

import logging

import requests

from config.settings import FRED_API_KEY

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

SERIES: dict[str, str] = {
    "hotel_employment": "IPUTN721110W200000000",
    "lodging_cpi": "CUSR0000SEHB",
    "fl_hospitality_jobs": "FLLEIH",
}

SERIES_LABELS: dict[str, str] = {
    "hotel_employment": "FL Hotel & Motel Employment",
    "lodging_cpi": "CPI: Lodging Away from Home (US)",
    "fl_hospitality_jobs": "FL Leisure & Hospitality Employment",
}


def get_fred_indicators() -> dict:
    """Fetch latest 13 observations for each tracked FRED series.

    Returns nested dict {series_name: {latest_value, latest_date, series_id, history, label}}.
    Returns empty dict if FRED_API_KEY is not set or all requests fail.
    """
    if not FRED_API_KEY:
        return {}

    result: dict = {}
    for name, series_id in SERIES.items():
        try:
            r = requests.get(
                FRED_BASE,
                params={
                    "series_id": series_id,
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 13,
                },
                timeout=10,
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            if not obs:
                continue

            latest = obs[0]
            result[name] = {
                "label": SERIES_LABELS.get(name, name),
                "series_id": series_id,
                "latest_value": float(latest["value"]) if latest["value"] != "." else None,
                "latest_date": latest["date"],
                "history": [
                    {
                        "date": o["date"],
                        "value": float(o["value"]) if o["value"] != "." else None,
                    }
                    for o in obs[:13]
                ],
            }
        except Exception as exc:
            logger.debug("FRED series %s unavailable: %s", series_id, exc)

    return result
