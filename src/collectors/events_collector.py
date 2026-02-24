"""Collect events data: Jewish holidays (Hebcal), conferences (PredictHQ), expos."""
from __future__ import annotations

from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from config.settings import PREDICTHQ_API_KEY

HEBCAL_URL = "https://www.hebcal.com/hebcal"


class EventsCollector(BaseCollector):
    """Collect events from Hebcal, PredictHQ, and Israeli expo sites."""

    name = "events"

    def is_available(self) -> bool:
        try:
            r = requests.get(HEBCAL_URL, params={
                "v": 1, "cfg": "json", "year": date.today().year,
                "maj": "on", "min": "on",
            }, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def collect(self, year: int | None = None, city: str | None = None, **kwargs) -> pd.DataFrame:
        """Collect events from all sources, merge and deduplicate."""
        year = year or date.today().year

        holidays = self._collect_hebcal_holidays(year)
        events = self._collect_predicthq_events(year, city)
        expos = self._collect_israeli_expos(year)

        parts = [df for df in [holidays, events, expos] if not df.empty]
        if not parts:
            return pd.DataFrame()

        combined = pd.concat(parts, ignore_index=True)
        combined = combined.drop_duplicates(subset=["name", "start_date"], keep="first")
        return combined

    def _collect_hebcal_holidays(self, year: int) -> pd.DataFrame:
        """Fetch Israeli/Jewish holidays from Hebcal REST API."""
        try:
            r = requests.get(HEBCAL_URL, params={
                "v": 1, "cfg": "json", "year": year,
                "maj": "on", "min": "on", "mod": "on",
                "nx": "on", "ss": "on",
            }, timeout=10)
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception:
            return pd.DataFrame()

        records = []
        for item in items:
            if item.get("category") not in ("holiday", "roshchodesh"):
                continue
            d = item.get("date", "")[:10]
            records.append({
                "event_id": f"hebcal_{item.get('title', '').replace(' ', '_')}_{d}",
                "name": item.get("title", ""),
                "start_date": d,
                "end_date": d,
                "city": "National",
                "country": "IL",
                "category": "holiday",
                "expected_attendance": None,
                "source": "hebcal",
            })

        df = pd.DataFrame(records)
        if not df.empty:
            df["start_date"] = pd.to_datetime(df["start_date"])
            df["end_date"] = pd.to_datetime(df["end_date"])
        return df

    def _collect_predicthq_events(self, year: int, city: str | None = None) -> pd.DataFrame:
        """Fetch conferences, festivals, sports from PredictHQ."""
        if not PREDICTHQ_API_KEY:
            return pd.DataFrame()

        try:
            headers = {"Authorization": f"Bearer {PREDICTHQ_API_KEY}"}
            params = {
                "country": "IL",
                "category": "conferences,expos,festivals,sports,performing-arts",
                "start.gte": f"{year}-01-01",
                "start.lte": f"{year}-12-31",
                "limit": 200,
                "sort": "start",
            }
            if city:
                params["q"] = city

            r = requests.get(
                "https://api.predicthq.com/v1/events/",
                headers=headers, params=params, timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception:
            return pd.DataFrame()

        records = []
        for ev in results:
            records.append({
                "event_id": f"phq_{ev.get('id', '')}",
                "name": ev.get("title", ""),
                "start_date": ev.get("start", "")[:10],
                "end_date": ev.get("end", ev.get("start", ""))[:10],
                "city": city or "Israel",
                "country": "IL",
                "category": ev.get("category", "other"),
                "expected_attendance": ev.get("phq_attendance"),
                "source": "predicthq",
            })

        df = pd.DataFrame(records)
        if not df.empty:
            df["start_date"] = pd.to_datetime(df["start_date"])
            df["end_date"] = pd.to_datetime(df["end_date"])
        return df

    def _collect_israeli_expos(self, year: int) -> pd.DataFrame:
        """Scrape Israeli expo/convention events from 10times.com."""
        try:
            url = "https://10times.com/israel/tradeshows"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            records = []
            for card in soup.select(".event-card, .listing-card")[:50]:
                name_el = card.select_one("h2, .event-name, a[title]")
                date_el = card.select_one(".date, time, .event-date")
                venue_el = card.select_one(".venue, .event-location")

                if not name_el:
                    continue

                records.append({
                    "event_id": f"10t_{name_el.text.strip()[:30].replace(' ', '_')}",
                    "name": name_el.text.strip(),
                    "start_date": date_el.text.strip() if date_el else "",
                    "end_date": date_el.text.strip() if date_el else "",
                    "city": venue_el.text.strip() if venue_el else "Israel",
                    "country": "IL",
                    "category": "conference",
                    "expected_attendance": None,
                    "source": "10times",
                })

            df = pd.DataFrame(records)
            if not df.empty:
                df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
                df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()
