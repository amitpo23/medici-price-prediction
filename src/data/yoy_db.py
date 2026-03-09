"""Multi-year scan history loader for Year-over-Year price comparison.

Combines:
  - SalesOffice.Details + Orders  (2024–present, exact scan timestamps)
  - MED_SearchHotels              (2020–2023, historical search data)

Returns a unified DataFrame with schema:
  hotel_id, year, scan_date, checkin_date, category, board, price, source
"""
from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

logger = logging.getLogger(__name__)

BOARDS: dict[int, str] = {1: "RO", 2: "BB", 3: "HB", 4: "FB", 5: "AI", 6: "CB", 7: "BD"}
CATEGORIES: dict[int, str] = {1: "standard", 2: "superior", 3: "dormitory", 4: "deluxe", 12: "suite"}


def load_salesoffice_scan_history(hotel_ids: list[int]) -> pd.DataFrame:
    """Load all SalesOffice price scans (including soft-deleted historical records).

    Returns one row per (hotel, checkin_date, category, board, scan_date).
    Covers approximately 2024–present.
    """
    from src.data.trading_db import run_trading_query

    ids_str = ",".join(str(i) for i in hotel_ids)
    sql = f"""
        SELECT
            o.DestinationId                     AS hotel_id,
            LOWER(LTRIM(RTRIM(d.RoomCategory))) AS category,
            d.RoomBoard                         AS board_id,
            d.RoomPrice                         AS price,
            CAST(d.DateCreated AS DATE)         AS scan_date,
            CAST(o.DateFrom    AS DATE)         AS checkin_date,
            YEAR(d.DateCreated)                 AS year
        FROM [SalesOffice.Details] d
        JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
        WHERE o.DestinationId IN ({ids_str})
          AND d.RoomPrice > 0
          AND o.DateFrom IS NOT NULL
          AND d.DateCreated IS NOT NULL
    """
    try:
        df = run_trading_query(sql)
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.warning("SalesOffice YoY query failed: %s", e)
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Map board int → string
    df["board"] = df["board_id"].map(BOARDS).fillna("unknown")
    df["source"] = "salesoffice"

    cols = ["hotel_id", "year", "scan_date", "checkin_date", "category", "board", "price", "source"]
    df = df[cols].copy()
    df["scan_date"] = pd.to_datetime(df["scan_date"]).dt.date
    df["checkin_date"] = pd.to_datetime(df["checkin_date"]).dt.date

    logger.info("SalesOffice YoY: %d rows for %d hotels", len(df), df["hotel_id"].nunique())
    return df


def load_med_search_scan_history(hotel_ids: list[int]) -> pd.DataFrame:
    """Load MED_SearchHotels price history (2020–2023) for the given hotel IDs.

    MED_SearchHotels has 7M rows covering historical searches. Coverage for
    our 4 Miami hotels may be partial — returns empty DataFrame if no data found.
    """
    from src.data.trading_db import run_trading_query

    ids_str = ",".join(str(i) for i in hotel_ids)
    sql = f"""
        SELECT TOP 200000
            HotelId                             AS hotel_id,
            CategoryId                          AS category_id,
            BoardId                             AS board_id,
            Price                               AS price,
            CAST(RequestTime AS DATE)           AS scan_date,
            CAST(DateForm    AS DATE)           AS checkin_date,
            YEAR(RequestTime)                   AS year
        FROM MED_SearchHotels
        WHERE HotelId IN ({ids_str})
          AND Price > 0
          AND DateForm IS NOT NULL
          AND RequestTime IS NOT NULL
          AND DateForm >= RequestTime
        ORDER BY HotelId, DateForm, RequestTime
    """
    try:
        df = run_trading_query(sql)
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.warning("MED_SearchHotels YoY query failed: %s", e)
        return pd.DataFrame()

    if df.empty:
        logger.info("MED_SearchHotels: no data for hotels %s", hotel_ids)
        return pd.DataFrame()

    # Map category int → string, board int → string
    df["category"] = df["category_id"].map(CATEGORIES).fillna("unknown")
    df["board"] = df["board_id"].map(BOARDS).fillna("unknown")
    df["source"] = "med_search"

    cols = ["hotel_id", "year", "scan_date", "checkin_date", "category", "board", "price", "source"]
    df = df[cols].copy()
    df["scan_date"] = pd.to_datetime(df["scan_date"]).dt.date
    df["checkin_date"] = pd.to_datetime(df["checkin_date"]).dt.date

    logger.info("MED_SearchHotels YoY: %d rows for %d hotels", len(df), df["hotel_id"].nunique())
    return df


def load_unified_yoy_data(hotel_ids: list[int]) -> pd.DataFrame:
    """Load and merge multi-year scan history from all sources.

    Returns unified DataFrame:
        hotel_id, year, scan_date, checkin_date, category, board, price, source, T_days
    """
    so_df = load_salesoffice_scan_history(hotel_ids)
    med_df = load_med_search_scan_history(hotel_ids)

    parts = [df for df in [so_df, med_df] if not df.empty]
    if not parts:
        logger.warning("YoY: no data found for hotels %s", hotel_ids)
        return pd.DataFrame()

    df = pd.concat(parts, ignore_index=True)

    # Normalize category and board
    df["category"] = df["category"].astype(str).str.lower().str.strip()
    df["board"] = df["board"].astype(str).str.lower().str.strip()

    # Compute T
    df["scan_date"] = pd.to_datetime(df["scan_date"])
    df["checkin_date"] = pd.to_datetime(df["checkin_date"])
    df["T_days"] = (df["checkin_date"] - df["scan_date"]).dt.days

    # Filter valid T range
    df = df[(df["T_days"] >= 0) & (df["T_days"] <= 180)].copy()

    # Deduplicate: one price per (hotel, scan_date, checkin_date, category, board)
    df = df.sort_values("price")
    df = df.drop_duplicates(
        subset=["hotel_id", "scan_date", "checkin_date", "category", "board"],
        keep="first",
    )

    df["year"] = df["scan_date"].dt.year
    df = df.sort_values(["hotel_id", "checkin_date", "category", "board", "scan_date"])

    logger.info(
        "YoY unified: %d rows, %d hotels, years %s",
        len(df), df["hotel_id"].nunique(),
        sorted(df["year"].unique().tolist()),
    )
    return df
