"""Event impact features for hotel pricing."""
from __future__ import annotations

import pandas as pd
import numpy as np


# Impact weights by event category
CATEGORY_WEIGHTS = {
    "holiday": 3.0,
    "conference": 2.5,
    "conferences": 2.5,
    "expos": 2.0,
    "festival": 1.5,
    "festivals": 1.5,
    "sports": 1.5,
    "performing-arts": 1.0,
    "other": 0.5,
}


def add_event_features(
    df: pd.DataFrame,
    events_df: pd.DataFrame,
    date_col: str = "date",
    city_col: str = "city",
) -> pd.DataFrame:
    """Add event-derived features to pricing data."""
    df = df.copy()

    if events_df.empty:
        df["events_active_count"] = 0
        df["events_total_attendance"] = 0
        df["has_conference"] = 0
        df["has_festival"] = 0
        df["event_impact_score"] = 0.0
        df["days_to_next_event"] = 365
        return df

    events = events_df.copy()
    events["start_date"] = pd.to_datetime(events["start_date"])
    events["end_date"] = pd.to_datetime(events["end_date"])

    dt = pd.to_datetime(df[date_col])

    event_counts = []
    total_attendance = []
    has_conf = []
    has_fest = []
    impact_scores = []
    days_to_next = []

    for d in dt:
        # Active events on this date
        active = events[
            (events["start_date"] <= d) & (events["end_date"] >= d)
        ]

        # City-specific if available
        if city_col in df.columns and city_col in events.columns:
            pass  # Could filter by city here

        event_counts.append(len(active))
        attendance = active["expected_attendance"].fillna(0).sum() if not active.empty else 0
        total_attendance.append(attendance)

        cats = set(active["category"].values) if not active.empty else set()
        has_conf.append(int("conference" in cats or "conferences" in cats or "expos" in cats))
        has_fest.append(int("festival" in cats or "festivals" in cats))

        # Impact score: weighted sum of events
        score = 0.0
        if not active.empty:
            for _, ev in active.iterrows():
                weight = CATEGORY_WEIGHTS.get(ev.get("category", "other"), 0.5)
                att_factor = min((ev.get("expected_attendance") or 100) / 1000, 5.0)
                score += weight * att_factor
        impact_scores.append(score)

        # Days to next event
        future_events = events[events["start_date"] > d]
        if not future_events.empty:
            min_days = (future_events["start_date"] - d).dt.days.min()
            days_to_next.append(int(min_days))
        else:
            days_to_next.append(365)

    df["events_active_count"] = event_counts
    df["events_total_attendance"] = total_attendance
    df["has_conference"] = has_conf
    df["has_festival"] = has_fest
    df["event_impact_score"] = impact_scores
    df["days_to_next_event"] = days_to_next

    return df
