"""Accurate Hebrew calendar holidays using pyluach."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from pyluach import dates as hebrew_dates
from pyluach import hebrewcal


# Holidays that cause significant demand changes for Israeli hotels
HIGH_IMPACT = {
    "Rosh Hashana I", "Rosh Hashana II", "Yom Kippur",
    "Succos I", "Succos II", "Shmini Atzeres", "Simchas Torah",
    "Pesach I", "Pesach II", "Pesach VII", "Pesach VIII",
    "Shavuos I", "Shavuos II",
}

MEDIUM_IMPACT = {
    "Chanuka", "Purim", "Lag Ba'omer",
    "Tu B'Shvat", "Yom Ha'atzmaut", "Yom Hazikaron",
}


def _get_holiday_name(gregorian_date: date) -> str | None:
    """Get the Hebrew holiday name for a given Gregorian date."""
    try:
        heb = hebrew_dates.HebrewDate.from_pydate(gregorian_date)
        holiday = heb.holiday()
        return holiday if holiday else None
    except Exception:
        return None


def _get_year_holidays(year: int) -> list[dict]:
    """Get all holidays for a Gregorian year with their dates."""
    holidays = []
    current = date(year, 1, 1)
    end = date(year, 12, 31)

    while current <= end:
        name = _get_holiday_name(current)
        if name:
            holidays.append({"date": current, "holiday_name": name})
        current += timedelta(days=1)

    return holidays


def add_hebrew_holiday_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add accurate Hebrew holiday flags and proximity features."""
    df = df.copy()
    dt = pd.to_datetime(df[date_col])

    # Get all holidays in the date range
    years = dt.dt.year.unique()
    all_holidays = []
    for y in years:
        all_holidays.extend(_get_year_holidays(int(y)))

    holiday_dates = {h["date"]: h["holiday_name"] for h in all_holidays}
    high_impact_dates = {d for d, n in holiday_dates.items() if n in HIGH_IMPACT}
    medium_impact_dates = {d for d, n in holiday_dates.items() if n in MEDIUM_IMPACT}
    all_holiday_dates_sorted = sorted(holiday_dates.keys())

    # Binary flags
    df["is_holiday"] = dt.dt.date.isin(holiday_dates).astype(int)
    df["is_high_impact_holiday"] = dt.dt.date.isin(high_impact_dates).astype(int)
    df["is_medium_impact_holiday"] = dt.dt.date.isin(medium_impact_dates).astype(int)

    # Holiday eve (demand spikes the day before)
    eves = {d - timedelta(days=1) for d in high_impact_dates}
    df["is_holiday_eve"] = dt.dt.date.isin(eves).astype(int)

    # Days to next holiday
    def days_to_next(d):
        d_date = d.date() if hasattr(d, "date") else d
        for hd in all_holiday_dates_sorted:
            if hd >= d_date:
                return (hd - d_date).days
        return 365

    df["days_to_next_holiday"] = dt.apply(days_to_next)

    return df


def add_school_vacation_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Flag Israeli school vacation periods — major demand driver."""
    df = df.copy()
    dt = pd.to_datetime(df[date_col])

    # Summer vacation: July 1 - August 31
    df["is_summer_vacation"] = ((dt.dt.month == 7) | (dt.dt.month == 8)).astype(int)

    # Approximate Passover break: 2 weeks around Pesach (March-April)
    # Approximate Sukkot break: 1 week around Sukkot (September-October)
    # These overlap with the holiday flags above but represent the full school break

    # Chanuka break: late December
    df["is_chanuka_break"] = ((dt.dt.month == 12) & (dt.dt.day >= 20)).astype(int)

    return df
