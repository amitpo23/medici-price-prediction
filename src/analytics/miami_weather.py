"""Miami weather signal: Open-Meteo forecast + NHC hurricane detection.

No API key required. Provides:
- Daily weather-based demand adjustments (heavy rain, clear sky)
- Hurricane proximity detection during Atlantic hurricane season (Jun-Nov)

Adjustments (% per day):
  Heavy rain (>20mm):   -0.05%/day  (leisure demand drops)
  Clear sky (wcode<3):  +0.02%/day  (beach/pool demand rises)
  Hurricane nearby:     -0.15%/day  (override, applied regardless of weather code)
"""
from __future__ import annotations

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

MIAMI_LAT = 25.7617
MIAMI_LON = -80.1918
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NHC_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
HURRICANE_SEASON_MONTHS = {6, 7, 8, 9, 10, 11}


def get_weather_forecast(days: int = 14) -> dict[str, float]:
    """Return {date_str: daily_adj_pct} for the next N days.

    Only dates with non-zero adjustments are included.
    Returns empty dict if API is unavailable.
    """
    hurricane_adj = _check_hurricane_proximity()
    adjustments: dict[str, float] = {}

    try:
        r = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": MIAMI_LAT,
                "longitude": MIAMI_LON,
                "daily": "precipitation_sum,weather_code",
                "timezone": "America/New_York",
                "forecast_days": min(days, 16),  # Open-Meteo max is 16 days
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()["daily"]

        for d, precip, wcode in zip(
            data["time"],
            data["precipitation_sum"],
            data["weather_code"],
        ):
            adj = hurricane_adj  # start with hurricane base (0 or -0.15)
            if precip and precip > 20:
                adj -= 0.05   # heavy rain hurts leisure demand
            elif wcode is not None and wcode < 3:
                adj += 0.02   # clear sky → beach/pool demand lift

            if adj != 0.0:
                adjustments[d] = round(adj, 4)

        logger.debug("Weather forecast: %d days with adjustments (hurricane_adj=%.2f)", len(adjustments), hurricane_adj)

    except Exception as exc:
        logger.debug("Weather forecast unavailable: %s", exc)

    return adjustments


def _check_hurricane_proximity() -> float:
    """Return -0.15 if an active hurricane is within ~500 km of Miami, else 0.0.

    Only called during Atlantic hurricane season (Jun-Nov).
    Uses NHC CurrentStorms.json (free, no key, real-time).
    """
    if date.today().month not in HURRICANE_SEASON_MONTHS:
        return 0.0

    try:
        r = requests.get(NHC_URL, timeout=5)
        r.raise_for_status()
        storms = r.json().get("activeStorms", [])
        for storm in storms:
            lat = storm.get("latitudeNumeric", 0) or 0
            lon = storm.get("longitudeNumeric", 0) or 0
            # ~5 degrees ≈ 550 km — rough proximity check
            if abs(lat - MIAMI_LAT) < 5 and abs(lon - MIAMI_LON) < 5:
                logger.warning("Hurricane proximity detected: %s at (%.1f, %.1f)", storm.get("name", "?"), lat, lon)
                return -0.15
    except Exception as exc:
        logger.debug("NHC check unavailable: %s", exc)

    return 0.0
