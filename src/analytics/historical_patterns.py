"""Historical pattern mining — deep analysis of past price behavior.

Mines all available historical data to find patterns:
  - Same-period analysis (what happened last year this month?)
  - Lead-time behavior (how prices change in final days before check-in)
  - Day-of-week patterns (are Friday check-ins more expensive?)
  - Event impact measurement (actual price uplift during events)
  - Hotel-specific monthly seasonality index

Called once per analysis run, results cached and passed to DeepPredictor.
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Events with their date ranges for impact measurement
MIAMI_EVENTS = [
    {"name": "Miami International Boat Show", "month": 2},
    {"name": "South Beach Wine & Food Festival", "month": 2},
    {"name": "Miami Open Tennis", "month": 3},
    {"name": "Ultra Music Festival", "month": 3},
    {"name": "F1 Miami Grand Prix", "month": 5},
    {"name": "Miami Swim Week", "month": 5},
    {"name": "Florida SuperCon", "month": 7},
    {"name": "Art Basel Miami Beach", "month": 12},
]


class HistoricalPatternMiner:
    """Mines historical price data for reusable patterns."""

    def __init__(self):
        self._historical_df = None   # SalesOffice Details history
        self._tprice_df = None       # Monthly tprice table
        self._bookings_df = None     # Booking history (buy/push/sold)
        self._seasonality = None     # Benchmark monthly index
        self._loaded = False

    def load_data(self) -> None:
        """Load all historical data sources. Call once per analysis run."""
        # 1. SalesOffice historical prices
        try:
            from src.analytics.collector import load_historical_prices
            self._historical_df = load_historical_prices()
            if not self._historical_df.empty:
                self._historical_df["scan_date"] = pd.to_datetime(
                    self._historical_df["scan_date"], errors="coerce"
                )
                self._historical_df["date_from_dt"] = pd.to_datetime(
                    self._historical_df["date_from"], errors="coerce"
                )
                self._historical_df["room_price"] = pd.to_numeric(
                    self._historical_df["room_price"], errors="coerce"
                )
                self._historical_df = self._historical_df.dropna(
                    subset=["room_price", "scan_date"]
                )
                logger.info(
                    "Historical patterns: loaded %d SalesOffice records",
                    len(self._historical_df),
                )
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.warning("Failed to load SalesOffice history: %s", e)
            self._historical_df = pd.DataFrame()

        # 2. Monthly tprice table
        try:
            from src.data.trading_db import load_historical_prices as load_tprice
            self._tprice_df = load_tprice()
            if not self._tprice_df.empty:
                logger.info(
                    "Historical patterns: loaded %d tprice records",
                    len(self._tprice_df),
                )
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.warning("Failed to load tprice: %s", e)
            self._tprice_df = pd.DataFrame()

        # 3. Booking history
        try:
            from src.data.trading_db import load_all_bookings
            self._bookings_df = load_all_bookings(days_back=365)
            if not self._bookings_df.empty:
                logger.info(
                    "Historical patterns: loaded %d booking records",
                    len(self._bookings_df),
                )
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.warning("Failed to load bookings: %s", e)
            self._bookings_df = pd.DataFrame()

        # 4. Benchmark seasonality index (always available as fallback)
        try:
            from src.analytics.booking_benchmarks import get_seasonality_all
            self._seasonality = get_seasonality_all()
        except (ImportError, KeyError, ValueError, TypeError) as e:
            logger.warning("Failed to load seasonality benchmarks: %s", e)
            self._seasonality = {}

        self._loaded = True

    def mine_same_period(
        self,
        hotel_id: int,
        category: str,
        target_month: int,
    ) -> dict:
        """Find prices for same hotel+category in same calendar month.

        Answers: "What did prices look like last year this month?"

        Priority:
        1. SalesOffice historical (same hotel, same category, same month of date_from)
        2. tprice table (same hotel, same month)
        3. Booking benchmarks seasonality-adjusted estimate
        """
        result = {
            "avg_price": None,
            "median_price": None,
            "price_range": None,
            "n_observations": 0,
            "data_source": "none",
            "monthly_seasonality": self._get_benchmark_seasonality(target_month),
        }

        # Try SalesOffice historical first
        if self._historical_df is not None and not self._historical_df.empty:
            hist = self._historical_df
            mask = (
                (hist["hotel_id"] == hotel_id)
                & (hist["room_category"].astype(str).str.lower() == str(category).lower())
                & (hist["date_from_dt"].dt.month == target_month)
            )
            subset = hist[mask]

            if len(subset) >= 3:
                prices = subset["room_price"].values
                result.update({
                    "avg_price": round(float(np.mean(prices)), 2),
                    "median_price": round(float(np.median(prices)), 2),
                    "price_range": (round(float(np.min(prices)), 2), round(float(np.max(prices)), 2)),
                    "n_observations": len(subset),
                    "data_source": "salesoffice_history",
                })
                return result

            # Try same hotel, any category
            mask_hotel = (
                (hist["hotel_id"] == hotel_id)
                & (hist["date_from_dt"].dt.month == target_month)
            )
            subset_hotel = hist[mask_hotel]
            if len(subset_hotel) >= 3:
                prices = subset_hotel["room_price"].values
                result.update({
                    "avg_price": round(float(np.mean(prices)), 2),
                    "median_price": round(float(np.median(prices)), 2),
                    "price_range": (round(float(np.min(prices)), 2), round(float(np.max(prices)), 2)),
                    "n_observations": len(subset_hotel),
                    "data_source": "salesoffice_history_hotel_level",
                })
                return result

        # Try tprice table
        if self._tprice_df is not None and not self._tprice_df.empty:
            tp = self._tprice_df
            mask = (tp["HotelId"] == hotel_id) & (tp["Month"] == target_month)
            subset = tp[mask]
            if not subset.empty:
                price = float(subset.iloc[0]["Price"])
                result.update({
                    "avg_price": round(price, 2),
                    "median_price": round(price, 2),
                    "price_range": (round(price * 0.85, 2), round(price * 1.15, 2)),
                    "n_observations": 1,
                    "data_source": "tprice_monthly",
                })
                return result

        return result

    def mine_lead_time_behavior(
        self,
        hotel_id: int,
        category: str,
    ) -> list[dict]:
        """Analyze how prices change in final days before check-in.

        Answers: "Do prices rise or fall in the last 7/14/30 days?"

        Uses same T-observation logic as forward_curve._extract_t_observations()
        but groups into coarser lead-time buckets.
        """
        if self._historical_df is None or self._historical_df.empty:
            return []

        hist = self._historical_df
        mask = (hist["hotel_id"] == hotel_id)
        if category:
            cat_mask = hist["room_category"].astype(str).str.lower() == str(category).lower()
            if cat_mask.sum() >= 10:
                mask = mask & cat_mask

        subset = hist[mask]
        if len(subset) < 10:
            return []

        # Extract T-observations (same logic as forward_curve)
        observations = self._extract_t_observations(subset)
        if len(observations) < 5:
            return []

        obs_df = pd.DataFrame(observations)

        # Group into lead-time buckets
        buckets = [
            ("0-7d", 0, 7),
            ("8-14d", 8, 14),
            ("15-30d", 15, 30),
            ("31-60d", 31, 60),
            ("60+d", 61, 999),
        ]

        results = []
        for label, t_min, t_max in buckets:
            bucket_mask = (obs_df["t"] >= t_min) & (obs_df["t"] <= t_max)
            bucket = obs_df[bucket_mask]

            if len(bucket) < 3:
                continue

            daily_pcts = bucket["daily_pct"].values
            results.append({
                "bucket": label,
                "avg_daily_change_pct": round(float(np.mean(daily_pcts)), 4),
                "median_daily_change_pct": round(float(np.median(daily_pcts)), 4),
                "volatility_pct": round(float(np.std(daily_pcts)), 4),
                "direction_bias": round(float(np.mean(daily_pcts > 0) - np.mean(daily_pcts < 0)), 3),
                "n_observations": len(bucket),
            })

        return results

    def mine_day_of_week(
        self,
        hotel_id: int,
        category: str,
    ) -> dict:
        """Compute price patterns by check-in day of week.

        Answers: "Are Friday check-ins more expensive than Tuesday?"
        """
        if self._historical_df is None or self._historical_df.empty:
            return {}

        hist = self._historical_df
        mask = (hist["hotel_id"] == hotel_id) & hist["date_from_dt"].notna()
        if category:
            cat_mask = hist["room_category"].astype(str).str.lower() == str(category).lower()
            if cat_mask.sum() >= 10:
                mask = mask & cat_mask

        subset = hist[mask].copy()
        if len(subset) < 14:
            return {}

        subset["dow"] = subset["date_from_dt"].dt.dayofweek
        overall_mean = subset["room_price"].mean()
        if overall_mean <= 0:
            return {}

        dow_means = subset.groupby("dow")["room_price"].mean()
        dow_index = {}
        for dow in range(7):
            if dow in dow_means.index:
                pct_offset = (dow_means[dow] - overall_mean) / overall_mean * 100
                dow_index[dow] = round(float(pct_offset), 2)

        weekend_prices = subset[subset["dow"].isin([4, 5])]["room_price"]
        weekday_prices = subset[~subset["dow"].isin([4, 5])]["room_price"]

        weekend_premium = 0.0
        if len(weekend_prices) > 0 and len(weekday_prices) > 0 and weekday_prices.mean() > 0:
            weekend_premium = round(
                float((weekend_prices.mean() - weekday_prices.mean()) / weekday_prices.mean() * 100), 2
            )

        return {
            "dow_index": dow_index,
            "weekend_premium_pct": weekend_premium,
            "n_observations": len(subset),
        }

    def mine_event_impacts(
        self,
        hotel_id: int,
    ) -> list[dict]:
        """Measure actual price impact during events from historical data.

        Answers: "How much did prices actually jump during Art Basel?"

        Compares event-period prices to same-month baseline (non-event dates).
        Falls back to hardcoded multipliers when insufficient data.
        """
        if self._historical_df is None or self._historical_df.empty:
            return []

        hist = self._historical_df
        hotel_data = hist[hist["hotel_id"] == hotel_id]
        if len(hotel_data) < 20:
            return []

        results = []
        for event in MIAMI_EVENTS:
            event_month = event["month"]

            # Get prices in event month
            month_mask = hotel_data["date_from_dt"].dt.month == event_month
            month_prices = hotel_data[month_mask]["room_price"]

            if len(month_prices) < 5:
                continue

            # Baseline: adjacent months (month-1 and month+1)
            adj_months = [(event_month - 1) if event_month > 1 else 12,
                          (event_month + 1) if event_month < 12 else 1]
            baseline_mask = hotel_data["date_from_dt"].dt.month.isin(adj_months)
            baseline_prices = hotel_data[baseline_mask]["room_price"]

            if len(baseline_prices) < 5:
                continue

            event_avg = float(month_prices.mean())
            baseline_avg = float(baseline_prices.mean())

            if baseline_avg <= 0:
                continue

            uplift_pct = (event_avg - baseline_avg) / baseline_avg * 100
            confidence = min(len(month_prices) / 30, 1.0)

            results.append({
                "event_name": event["name"],
                "event_month": event_month,
                "measured_uplift_pct": round(uplift_pct, 2),
                "event_avg_price": round(event_avg, 2),
                "baseline_avg_price": round(baseline_avg, 2),
                "n_event_observations": len(month_prices),
                "n_baseline_observations": len(baseline_prices),
                "confidence": round(confidence, 2),
            })

        return results

    def mine_monthly_price_index(
        self,
        hotel_id: int,
        category: str | None = None,
    ) -> dict[int, float]:
        """Compute hotel-specific monthly seasonality index.

        Answers: "What's the price pattern across months for THIS hotel?"

        Index = month_avg / annual_avg (1.0 = average month).
        Falls back to booking benchmarks if insufficient hotel data.
        """
        monthly_prices = {}

        # Try SalesOffice historical
        if self._historical_df is not None and not self._historical_df.empty:
            hist = self._historical_df
            mask = (hist["hotel_id"] == hotel_id) & hist["date_from_dt"].notna()
            if category:
                cat_mask = hist["room_category"].astype(str).str.lower() == str(category).lower()
                if cat_mask.sum() >= 10:
                    mask = mask & cat_mask

            subset = hist[mask].copy()
            if len(subset) >= 30:
                subset["month"] = subset["date_from_dt"].dt.month
                monthly_means = subset.groupby("month")["room_price"].mean()
                annual_mean = subset["room_price"].mean()

                if annual_mean > 0 and len(monthly_means) >= 4:
                    for month, avg in monthly_means.items():
                        monthly_prices[int(month)] = round(float(avg / annual_mean), 3)

        # Try tprice if SalesOffice insufficient
        if not monthly_prices and self._tprice_df is not None and not self._tprice_df.empty:
            tp = self._tprice_df[self._tprice_df["HotelId"] == hotel_id]
            if len(tp) >= 4:
                annual_mean = tp["Price"].mean()
                if annual_mean > 0:
                    for _, row in tp.iterrows():
                        monthly_prices[int(row["Month"])] = round(
                            float(row["Price"] / annual_mean), 3
                        )

        # Fallback to booking benchmarks
        if not monthly_prices and self._seasonality:
            month_names = [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ]
            for m in range(1, 13):
                idx = self._seasonality.get(month_names[m], 1.0)
                monthly_prices[m] = round(float(idx), 3)

        return monthly_prices

    def mine_all(
        self,
        hotel_ids: list[int] | None = None,
    ) -> dict:
        """Mine all patterns for all hotel+category combinations.

        Returns dict keyed by (hotel_id, category_str) with all mined patterns.
        """
        if not self._loaded:
            self.load_data()

        # Discover hotel+category combos from historical data
        combos = set()
        if self._historical_df is not None and not self._historical_df.empty:
            for _, row in self._historical_df[["hotel_id", "room_category"]].drop_duplicates().iterrows():
                hid = int(row["hotel_id"])
                if hotel_ids and hid not in hotel_ids:
                    continue
                combos.add((hid, str(row["room_category"]).lower()))

        if not combos:
            logger.info("No historical data to mine patterns from")
            return {}

        contexts = {}
        for hotel_id, category in combos:
            try:
                context = {
                    "hotel_id": hotel_id,
                    "category": category,
                    "same_period": {},
                    "lead_time": self.mine_lead_time_behavior(hotel_id, category),
                    "day_of_week": self.mine_day_of_week(hotel_id, category),
                    "event_impacts": self.mine_event_impacts(hotel_id),
                    "monthly_index": self.mine_monthly_price_index(hotel_id, category),
                    "data_quality": self.get_data_quality_score(hotel_id, category),
                }

                # Mine same-period for each month (1-12)
                for month in range(1, 13):
                    sp = self.mine_same_period(hotel_id, category, month)
                    if sp["n_observations"] > 0:
                        context["same_period"][month] = sp

                contexts[(hotel_id, category)] = context
            except (ValueError, TypeError, ZeroDivisionError, KeyError) as e:
                logger.warning(
                    "Failed to mine patterns for hotel=%d cat=%s: %s",
                    hotel_id, category, e,
                )

        logger.info("Mined patterns for %d hotel+category combinations", len(contexts))
        return contexts

    def get_data_quality_score(
        self,
        hotel_id: int,
        category: str,
    ) -> float:
        """0-1 score of how much historical data we have for this hotel+category.

        Based on: number of tracks, time span covered, number of months represented.
        """
        if self._historical_df is None or self._historical_df.empty:
            return 0.0

        hist = self._historical_df
        mask = (
            (hist["hotel_id"] == hotel_id)
            & (hist["room_category"].astype(str).str.lower() == str(category).lower())
        )
        subset = hist[mask]

        if len(subset) < 5:
            return 0.0

        n_records = len(subset)
        n_orders = subset["order_id"].nunique()
        n_months = subset["date_from_dt"].dt.month.nunique() if "date_from_dt" in subset.columns else 0

        # Score components (each 0-1)
        records_score = min(n_records / 100, 1.0)
        orders_score = min(n_orders / 20, 1.0)
        months_score = min(n_months / 8, 1.0)

        # Weighted average
        score = records_score * 0.4 + orders_score * 0.3 + months_score * 0.3
        return round(float(score), 2)

    def get_summary(self) -> dict:
        """Summary of loaded data for API/logging."""
        return {
            "salesoffice_records": len(self._historical_df) if self._historical_df is not None else 0,
            "tprice_records": len(self._tprice_df) if self._tprice_df is not None else 0,
            "booking_records": len(self._bookings_df) if self._bookings_df is not None else 0,
            "has_seasonality_benchmarks": bool(self._seasonality),
            "loaded": self._loaded,
        }

    # ── Private helpers ──────────────────────────────────────────────

    def _extract_t_observations(self, df: pd.DataFrame) -> list[dict]:
        """Extract T-observations from historical scan pairs.

        Same logic as forward_curve._extract_t_observations() but simplified
        for pattern mining (no weight computation needed).
        """
        observations = []
        tracks = df.groupby(["order_id", "hotel_id", "room_category", "room_board"])

        for key, grp in tracks:
            grp = grp.sort_values("scan_date")
            if len(grp) < 2:
                continue

            date_from = grp.iloc[0].get("date_from_dt")
            if pd.isna(date_from):
                continue

            prices = grp["room_price"].values
            dates = grp["scan_date"].values

            for i in range(1, len(grp)):
                price_prev = float(prices[i - 1])
                price_curr = float(prices[i])
                if price_prev <= 0:
                    continue

                scan_prev = pd.Timestamp(dates[i - 1])
                scan_curr = pd.Timestamp(dates[i])
                gap_days = (scan_curr - scan_prev).total_seconds() / 86400

                if gap_days < 0.1:
                    continue

                pct_change = (price_curr - price_prev) / price_prev * 100
                daily_pct = pct_change / gap_days
                daily_pct = max(-10.0, min(10.0, daily_pct))

                midpoint = scan_prev + (scan_curr - scan_prev) / 2
                t = max(1, int((date_from - midpoint).total_seconds() / 86400))

                observations.append({"t": t, "daily_pct": daily_pct})

        return observations

    def _get_benchmark_seasonality(self, month: int) -> float:
        """Get booking benchmark seasonality index for a month."""
        if not self._seasonality:
            return 1.0
        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        return float(self._seasonality.get(month_names[month], 1.0))
