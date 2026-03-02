"""Kaggle Hotel Booking Demand dataset loader and pattern extractor.

Source: Antonio, Almeida & Nunes (2019), 119,390 bookings from 2 Portuguese hotels.
Data file: data/kaggle_hotel_bookings.csv (downloaded via GitHub TidyTuesday mirror).
Download URL: https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2020/2020-02-11/hotels.csv

Key columns:
  lead_time              : days between booking date and arrival date
  adr                    : Average Daily Rate (price paid at booking, EUR)
  is_canceled            : 0=stayed, 1=canceled
  arrival_date_year/month/day_of_month : check-in date
  market_segment         : Direct, Online TA, Offline TA/TO, Groups, Corporate...
  hotel                  : Resort Hotel | City Hotel

Miami calibration: European base ADR is ~$104. Miami 2024 ADR is $222.12.
All ADR values can be scaled by MIAMI_SCALE_FACTOR = 222.12 / 104.11 = 2.134
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

CSV_PATH = DATA_DIR / "kaggle_hotel_bookings.csv"
DB_PATH  = DATA_DIR / "salesoffice_prices.db"
CSV_URL  = (
    "https://raw.githubusercontent.com/rfordatascience/tidytuesday/"
    "master/data/2020/2020-02-11/hotels.csv"
)

MIAMI_SCALE_FACTOR = 222.12 / 104.11   # 2.134x — scales European ADR to Miami

# Lead-time bucket definitions
LEAD_BUCKETS = [
    ("0-7d",    0,   7),
    ("8-30d",   8,  30),
    ("31-60d", 31,  60),
    ("61-90d", 61,  90),
    ("91-180d", 91, 180),
    ("181-365d",181, 365),
    ("366+d",  366, 9999),
]

_df_cache: pd.DataFrame | None = None


def download_if_missing() -> bool:
    """Download the Kaggle dataset CSV if not present. Returns True if file exists."""
    if CSV_PATH.exists():
        return True
    try:
        import requests
        logger.info("Downloading Kaggle hotel bookings dataset from GitHub mirror...")
        r = requests.get(CSV_URL, timeout=60)
        r.raise_for_status()
        CSV_PATH.write_bytes(r.content)
        logger.info("Downloaded %s (%.1f MB)", CSV_PATH.name, len(r.content) / 1_048_576)
        return True
    except Exception as exc:
        logger.warning("Failed to download Kaggle dataset: %s", exc)
        return False


def _load() -> pd.DataFrame | None:
    """Load and cache the CSV. Returns None if unavailable."""
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    if not CSV_PATH.exists():
        download_if_missing()
    if not CSV_PATH.exists():
        return None
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
        # Build arrival date
        df["arrival_date"] = pd.to_datetime(
            df["arrival_date_year"].astype(str) + "-"
            + df["arrival_date_month"] + "-"
            + df["arrival_date_day_of_month"].astype(str),
            errors="coerce",
        )
        df["dow"] = df["arrival_date"].dt.day_name()
        # Filter out extreme outliers in ADR
        df = df[(df["adr"] >= 0) & (df["adr"] < 2000)].copy()
        _df_cache = df
        logger.info("Kaggle hotel bookings loaded: %d rows", len(df))
        return df
    except Exception as exc:
        logger.warning("Failed to load Kaggle dataset: %s", exc)
        return None


def get_lead_time_curves(miami_scale: bool = True) -> dict:
    """Compute lead-time price + cancel curves.

    Returns dict with ADR and cancel rate per lead-time bucket.
    If miami_scale=True, ADR values are scaled to Miami market (~$222 base).
    """
    df = _load()
    if df is None:
        return {}

    result = {}
    for label, lo, hi in LEAD_BUCKETS:
        mask = (df["lead_time"] >= lo) & (df["lead_time"] <= hi)
        sub_all = df[mask]
        sub_stayed = sub_all[sub_all["is_canceled"] == 0]

        avg_adr = float(sub_stayed["adr"].mean()) if not sub_stayed.empty else 0
        if miami_scale:
            avg_adr = round(avg_adr * MIAMI_SCALE_FACTOR, 2)

        result[label] = {
            "avg_adr": avg_adr,
            "cancel_rate": round(float(sub_all["is_canceled"].mean()), 4) if len(sub_all) > 0 else 0,
            "bookings": len(sub_all),
            "stayed": len(sub_stayed),
        }
    return result


def get_dow_premiums() -> dict[str, float]:
    """Day-of-week ADR premium ratios relative to weekly average.

    Returns {day_name: ratio} where 1.0 = average.
    """
    df = _load()
    if df is None:
        return {}

    stayed = df[df["is_canceled"] == 0]
    avg = stayed["adr"].mean()
    if avg <= 0:
        return {}

    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        d: round(float(stayed[stayed["dow"] == d]["adr"].mean() / avg), 4)
        for d in dow_order
        if d in stayed["dow"].values
    }


def get_market_segment_patterns() -> dict:
    """ADR and cancel rates by market segment, Miami-scaled."""
    df = _load()
    if df is None:
        return {}

    result = {}
    for seg, grp in df.groupby("market_segment"):
        stayed = grp[grp["is_canceled"] == 0]
        avg_adr = float(stayed["adr"].mean()) * MIAMI_SCALE_FACTOR if not stayed.empty else 0
        result[str(seg)] = {
            "avg_adr": round(avg_adr, 2),
            "cancel_rate": round(float(grp["is_canceled"].mean()), 4),
            "total_bookings": len(grp),
        }
    return result


def get_monthly_seasonality() -> dict[str, float]:
    """Monthly ADR seasonality index relative to annual average (European — directional only).

    Returns {month_name: index} where 1.0 = annual average.
    NOTE: European seasonality pattern is INVERTED vs Miami. Use Miami STR data for
    seasonality adjustments. This is kept for academic comparison only.
    """
    df = _load()
    if df is None:
        return {}

    stayed = df[df["is_canceled"] == 0]
    annual_avg = stayed["adr"].mean()
    if annual_avg <= 0:
        return {}

    monthly = stayed.groupby("arrival_date_month")["adr"].mean()
    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    return {
        m: round(float(monthly.get(m, annual_avg)) / annual_avg, 4)
        for m in month_order
        if m in monthly.index
    }


def get_summary() -> dict:
    """Full summary of Kaggle dataset patterns for API/dashboard."""
    df = _load()
    if df is None:
        return {"status": "unavailable", "csv_path": str(CSV_PATH)}

    return {
        "status": "ok",
        "source": "Kaggle Hotel Booking Demand (Antonio et al., 2019)",
        "file": CSV_PATH.name,
        "total_bookings": len(df),
        "cancel_rate": round(float(df["is_canceled"].mean()), 4),
        "years": sorted(df["arrival_date_year"].dropna().unique().tolist()),
        "miami_scale_factor": round(MIAMI_SCALE_FACTOR, 4),
        "lead_time_curves": get_lead_time_curves(miami_scale=True),
        "dow_premiums": get_dow_premiums(),
        "market_segments": get_market_segment_patterns(),
        "note": "ADR values scaled from European base ($104) to Miami ($222) using 2.13x factor",
    }
