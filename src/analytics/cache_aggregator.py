"""Cache Aggregator — Pulls data from Azure SQL into Analytical Cache.

Three refresh cycles:
  1. Startup: Reference data (hotels, categories, boards) — once
  2. Nightly: Aggregated market data + competitor matrix — once/day
  3. Every 3h: Price history for demand zones + daily signals — with scheduler

Data sources:
  - SalesOffice.Details + SalesOffice.Orders — current active prices (existing)
  - SalesOffice.PriceHistory — historical price changes with OldPrice/NewPrice/ChangePct
  - AI_Search_HotelData — competitor pricing and market benchmarks
  - Med_Hotels — hotel reference data

Uses the existing read-only engine from trading_db.py.
Does NOT modify any existing file.

Safety: This is a NEW file.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ── SQL Queries ──────────────────────────────────────────────────────

# Layer 1: Reference data
_SQL_HOTELS = """
SELECT DISTINCT
    d.HotelId       AS hotel_id,
    h.Name           AS hotel_name,
    ''               AS city,
    0                AS stars,
    NULL             AS latitude,
    NULL             AS longitude
FROM [SalesOffice.Details] d
JOIN Med_Hotels h ON d.HotelId = h.HotelId
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.IsActive = 1 AND d.IsDeleted = 0
"""

_SQL_CATEGORIES = """
SELECT DISTINCT
    ROW_NUMBER() OVER (ORDER BY LOWER(LTRIM(RTRIM(d.RoomCategory)))) AS category_id,
    LOWER(LTRIM(RTRIM(d.RoomCategory))) AS category_name
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.IsActive = 1 AND d.IsDeleted = 0
  AND d.RoomCategory IS NOT NULL AND d.RoomCategory != ''
"""

_SQL_BOARDS = """
SELECT DISTINCT
    ROW_NUMBER() OVER (ORDER BY LOWER(LTRIM(RTRIM(d.RoomBoard)))) AS board_id,
    LOWER(LTRIM(RTRIM(d.RoomBoard))) AS board_name
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.IsActive = 1 AND d.IsDeleted = 0
  AND d.RoomBoard IS NOT NULL AND d.RoomBoard != ''
"""

# Layer 2: Aggregated market data from PriceHistory
_SQL_MARKET_DAILY = """
SELECT
    HotelId         AS hotel_id,
    CAST(DateFrom AS DATE) AS date,
    RoomCategory    AS room_type,
    RoomBoard       AS board,
    AVG(NewPrice)   AS avg_price,
    MIN(NewPrice)   AS min_price,
    MAX(NewPrice)   AS max_price,
    COUNT(*)        AS observation_count
FROM [SalesOffice.PriceHistory]
WHERE ScanDate >= DATEADD(DAY, -:days_back, GETDATE())
  AND NewPrice > 0
GROUP BY HotelId, CAST(DateFrom AS DATE), RoomCategory, RoomBoard
ORDER BY HotelId, date
"""

# Layer 2: Competitor matrix from AI_Search_HotelData
_SQL_COMPETITOR_MATRIX = """
WITH our_hotels AS (
    SELECT DISTINCT d.HotelId, h.Name, a.CityName, a.Stars
    FROM [SalesOffice.Details] d
    JOIN Med_Hotels h ON d.HotelId = h.HotelId
    JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
    LEFT JOIN AI_Search_HotelData a ON a.HotelId = d.HotelId
    WHERE o.IsActive = 1 AND d.IsDeleted = 0
),
competitors AS (
    SELECT
        oh.HotelId        AS hotel_id,
        a.HotelId         AS competitor_hotel_id,
        0                 AS distance_km,
        a.Stars - oh.Stars AS star_diff,
        CASE WHEN AVG(a.PriceAmount) > 0
             THEN AVG(a.PriceAmount) / NULLIF(
                 (SELECT AVG(a2.PriceAmount) FROM AI_Search_HotelData a2 WHERE a2.HotelId = oh.HotelId), 0)
             ELSE 1.0
        END AS avg_price_ratio,
        0.0 AS market_pressure
    FROM our_hotels oh
    JOIN AI_Search_HotelData a ON a.CityName = oh.CityName
                               AND a.Stars = oh.Stars
                               AND a.HotelId != oh.HotelId
    GROUP BY oh.HotelId, a.HotelId, a.Stars, oh.Stars
)
SELECT hotel_id, competitor_hotel_id, distance_km, star_diff,
       avg_price_ratio, market_pressure
FROM competitors
"""

# Layer 3: Full price history for demand zone detection
_SQL_PRICE_HISTORY = """
SELECT
    HotelId          AS hotel_id,
    CAST(DateFrom AS DATE) AS date_from,
    RoomCategory     AS room_category,
    RoomBoard        AS room_board,
    NewPrice         AS room_price,
    OldPrice         AS old_price,
    PriceChange      AS price_change,
    ChangePct        AS change_pct,
    ScanDate         AS snapshot_ts
FROM [SalesOffice.PriceHistory]
WHERE HotelId = :hotel_id
  AND ScanDate >= DATEADD(DAY, -:days_back, GETDATE())
  AND NewPrice > 0
ORDER BY ScanDate ASC
"""

# Price history for ALL hotels (batch)
_SQL_PRICE_HISTORY_ALL = """
SELECT
    HotelId          AS hotel_id,
    CAST(DateFrom AS DATE) AS date_from,
    RoomCategory     AS room_category,
    RoomBoard        AS room_board,
    NewPrice         AS room_price,
    OldPrice         AS old_price,
    PriceChange      AS price_change,
    ChangePct        AS change_pct,
    ScanDate         AS snapshot_ts
FROM [SalesOffice.PriceHistory]
WHERE ScanDate >= DATEADD(DAY, -:days_back, GETDATE())
  AND NewPrice > 0
ORDER BY HotelId, ScanDate ASC
"""

# Volatility data from PriceHistory
_SQL_VOLATILITY = """
SELECT
    HotelId       AS hotel_id,
    RoomCategory  AS room_category,
    COUNT(*)      AS total_changes,
    AVG(ABS(PriceChange)) AS avg_volatility,
    STDEV(NewPrice)       AS price_std_dev,
    MIN(NewPrice)         AS all_time_min,
    MAX(NewPrice)         AS all_time_max,
    AVG(NewPrice)         AS avg_price
FROM [SalesOffice.PriceHistory]
WHERE ScanDate >= DATEADD(DAY, -:days_back, GETDATE())
  AND NewPrice > 0
GROUP BY HotelId, RoomCategory
ORDER BY avg_volatility DESC
"""

# Biggest price drops (trading opportunities)
_SQL_PRICE_DROPS = """
SELECT TOP 50
    HotelId, DateFrom, RoomCategory, RoomBoard,
    OldPrice, NewPrice, PriceChange, ChangePct, ScanDate
FROM [SalesOffice.PriceHistory]
WHERE PriceChange < -10
  AND ScanDate >= DATEADD(DAY, -:days_back, GETDATE())
ORDER BY PriceChange ASC
"""

# Price trend for specific hotel+date+room
_SQL_PRICE_TREND = """
SELECT
    ScanDate     AS snapshot_ts,
    OldPrice     AS old_price,
    NewPrice     AS room_price,
    PriceChange  AS price_change,
    ChangePct    AS change_pct
FROM [SalesOffice.PriceHistory]
WHERE HotelId = :hotel_id
  AND DateFrom = :date_from
  AND RoomCategory = :room_category
  AND RoomBoard = :room_board
ORDER BY ScanDate ASC
"""


# ── Aggregator Class ─────────────────────────────────────────────────


class CacheAggregator:
    """Pulls data from Azure SQL and populates the AnalyticalCache.

    Uses the existing read-only engine from trading_db.py.
    All queries are SELECT-only (enforced by trading_db.py event listener).
    """

    def __init__(self, cache=None):
        """Initialize with an AnalyticalCache instance.

        Args:
            cache: AnalyticalCache instance. If None, creates one with default path.
        """
        if cache is None:
            from src.analytics.analytical_cache import AnalyticalCache
            cache = AnalyticalCache()
        self.cache = cache
        self._engine = None

    def _get_engine(self):
        """Lazy-load the trading engine."""
        if self._engine is None:
            from src.data.trading_db import get_trading_engine
            self._engine = get_trading_engine()
        return self._engine

    def _run_query(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Execute a read-only query and return DataFrame."""
        from sqlalchemy import text
        engine = self._get_engine()
        try:
            with engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except Exception as e:
            logger.error("Query failed: %s — %s", type(e).__name__, str(e)[:200])
            return pd.DataFrame()

    # ── Layer 1: Reference Data (startup) ────────────────────────────

    def refresh_reference_data(self) -> dict:
        """Pull hotel, category, and board reference data from Azure SQL.

        Call once at startup or when hotels change.
        Returns: dict with counts {hotels, categories, boards}
        """
        result = {"hotels": 0, "categories": 0, "boards": 0}

        # Hotels
        df = self._run_query(_SQL_HOTELS)
        if not df.empty:
            hotels = df.to_dict("records")
            result["hotels"] = self.cache.upsert_hotels(hotels)
            logger.info("Refreshed %d hotels in reference cache", result["hotels"])

        # Categories
        df = self._run_query(_SQL_CATEGORIES)
        if not df.empty:
            cats = df.to_dict("records")
            result["categories"] = self.cache.upsert_categories(cats)

        # Boards
        df = self._run_query(_SQL_BOARDS)
        if not df.empty:
            boards = df.to_dict("records")
            result["boards"] = self.cache.upsert_boards(boards)

        logger.info("Reference data refresh: %s", result)
        return result

    # ── Layer 2: Market Aggregations (nightly) ───────────────────────

    def refresh_market_data(self, days_back: int = 90) -> dict:
        """Pull aggregated market data from PriceHistory.

        Call nightly to refresh market aggregations.
        Returns: dict with counts {market_daily, competitors}
        """
        result = {"market_daily": 0, "competitors": 0}

        # Market daily from PriceHistory
        df = self._run_query(_SQL_MARKET_DAILY, {"days_back": days_back})
        if not df.empty:
            # Convert date column to string
            if "date" in df.columns:
                df["date"] = df["date"].astype(str)
            rows = df.to_dict("records")
            result["market_daily"] = self.cache.upsert_market_daily(rows)
            logger.info("Refreshed %d market daily rows from PriceHistory", result["market_daily"])

        # Competitor matrix
        try:
            df = self._run_query(_SQL_COMPETITOR_MATRIX)
            if not df.empty:
                rows = df.to_dict("records")
                result["competitors"] = self.cache.upsert_competitor_matrix(rows)
                logger.info("Refreshed %d competitor pairs", result["competitors"])
        except Exception as e:
            logger.warning("Competitor matrix refresh failed: %s", e)

        return result

    # ── Layer 3: Price History for Analysis ──────────────────────────

    def get_price_history(self, hotel_id: int, days_back: int = 90) -> pd.DataFrame:
        """Get detailed price history for one hotel from PriceHistory table.

        Returns DataFrame ready for demand zone detection.
        """
        df = self._run_query(_SQL_PRICE_HISTORY, {
            "hotel_id": hotel_id,
            "days_back": days_back,
        })
        if not df.empty:
            logger.info("Loaded %d price history rows for hotel_id=%s", len(df), hotel_id)
        return df

    def get_all_price_history(self, days_back: int = 90) -> pd.DataFrame:
        """Get price history for ALL hotels from PriceHistory table.

        Returns DataFrame with hotel_id column for grouping.
        """
        df = self._run_query(_SQL_PRICE_HISTORY_ALL, {"days_back": days_back})
        if not df.empty:
            hotels = df["hotel_id"].nunique()
            logger.info("Loaded %d price history rows for %d hotels", len(df), hotels)
        return df

    def get_volatility_data(self, days_back: int = 90) -> pd.DataFrame:
        """Get per-hotel volatility from PriceHistory for trade setup sizing."""
        return self._run_query(_SQL_VOLATILITY, {"days_back": days_back})

    def get_price_drops(self, days_back: int = 3) -> pd.DataFrame:
        """Get biggest price drops — potential CALL opportunities."""
        return self._run_query(_SQL_PRICE_DROPS, {"days_back": days_back})

    def get_price_trend(self, hotel_id: int, date_from: str,
                        room_category: str, room_board: str) -> pd.DataFrame:
        """Get detailed price trend for a specific hotel+date+room combo."""
        return self._run_query(_SQL_PRICE_TREND, {
            "hotel_id": hotel_id,
            "date_from": date_from,
            "room_category": room_category,
            "room_board": room_board,
        })

    # ── Full Refresh Orchestration ───────────────────────────────────

    def full_refresh(self, days_back: int = 90) -> dict:
        """Run a complete refresh of all cache layers.

        Layer 1: Reference data
        Layer 2: Market aggregations + competitor matrix
        Layer 3 data is fetched on-demand by the signal generator.

        Returns: combined result dict
        """
        result = {}

        # Layer 1
        try:
            ref = self.refresh_reference_data()
            result.update({f"layer1_{k}": v for k, v in ref.items()})
        except Exception as e:
            logger.error("Layer 1 refresh failed: %s", e)

        # Layer 2
        try:
            market = self.refresh_market_data(days_back=days_back)
            result.update({f"layer2_{k}": v for k, v in market.items()})
        except Exception as e:
            logger.error("Layer 2 refresh failed: %s", e)

        logger.info("Full cache refresh complete: %s", result)
        return result

    # ── Analysis Pipeline ────────────────────────────────────────────

    def run_demand_zone_analysis(self, hotel_id: int, category: str = "",
                                  days_back: int = 90) -> dict:
        """Run demand zone detection for a hotel using PriceHistory.

        Pulls price history from Azure SQL → detects zones → saves to cache.
        Returns: {zones: count, breaks: count}
        """
        from src.analytics.demand_zones import detect_demand_zones, detect_structure_breaks

        df = self.get_price_history(hotel_id, days_back=days_back)
        if df.empty:
            return {"zones": 0, "breaks": 0}

        # Filter by category if specified
        if category and "room_category" in df.columns:
            mask = df["room_category"].str.lower().str.strip() == category.lower().strip()
            df = df[mask]

        # Detect zones
        zones = detect_demand_zones(df, hotel_id=hotel_id, category=category)

        # Detect structure breaks
        breaks = detect_structure_breaks(df, hotel_id=hotel_id, category=category,
                                          demand_zones=zones)

        # Save to cache
        zone_count = 0
        break_count = 0
        if zones:
            # Remove transient 'touches' field before saving
            for z in zones:
                z.pop("touches", None)
            zone_count = self.cache.save_demand_zones(zones)
        if breaks:
            break_count = self.cache.save_structure_breaks(breaks)

        logger.info(
            "Demand zone analysis for hotel_id=%s: %d zones, %d breaks",
            hotel_id, zone_count, break_count,
        )
        return {"zones": zone_count, "breaks": break_count}

    def run_all_demand_zones(self, days_back: int = 90) -> dict:
        """Run demand zone analysis for ALL hotels.

        Returns: {total_zones, total_breaks, hotels_analyzed}
        """
        df = self.get_all_price_history(days_back=days_back)
        if df.empty:
            return {"total_zones": 0, "total_breaks": 0, "hotels_analyzed": 0}

        from src.analytics.demand_zones import detect_demand_zones, detect_structure_breaks

        total_zones = 0
        total_breaks = 0
        hotels = df["hotel_id"].unique()

        for hotel_id in hotels:
            hotel_df = df[df["hotel_id"] == hotel_id].copy()
            zones = detect_demand_zones(hotel_df, hotel_id=int(hotel_id))
            breaks = detect_structure_breaks(hotel_df, hotel_id=int(hotel_id),
                                              demand_zones=zones)
            if zones:
                for z in zones:
                    z.pop("touches", None)
                total_zones += self.cache.save_demand_zones(zones)
            if breaks:
                total_breaks += self.cache.save_structure_breaks(breaks)

        result = {
            "total_zones": total_zones,
            "total_breaks": total_breaks,
            "hotels_analyzed": len(hotels),
        }
        logger.info("All demand zones: %s", result)
        return result
