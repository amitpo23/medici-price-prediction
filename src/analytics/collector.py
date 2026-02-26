"""SalesOffice price collector — pulls room prices from medici-db.

Queries [SalesOffice.Details] joined with [SalesOffice.Orders] and Med_Hotels
for all active orders that have mapping (Completed + Mapping > 0).
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from src.analytics.price_store import init_db, save_snapshot

logger = logging.getLogger(__name__)

QUERY = """
SELECT
    d.Id            AS detail_id,
    d.SalesOfficeOrderId AS order_id,
    d.HotelId       AS hotel_id,
    h.Name           AS hotel_name,
    d.RoomCategory   AS room_category,
    d.RoomBoard      AS room_board,
    d.RoomPrice      AS room_price,
    d.RoomCode       AS room_code,
    o.DateFrom       AS date_from,
    o.DateTo         AS date_to,
    o.DestinationId  AS destination_id,
    d.IsProcessedCallback AS is_processed
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
JOIN Med_Hotels h ON d.HotelId = h.HotelId
WHERE o.IsActive = 1
  AND o.WebJobStatus LIKE 'Completed%'
  AND o.WebJobStatus NOT LIKE '%Mapping: 0%'
ORDER BY d.HotelId, o.DateFrom
"""


def collect_prices() -> pd.DataFrame:
    """Pull current prices from medici-db and store locally.

    Returns the collected DataFrame.
    """
    from src.data.trading_db import get_trading_engine

    init_db()

    engine = get_trading_engine()
    if engine is None:
        logger.error("Cannot connect to trading DB")
        return pd.DataFrame()

    logger.info("Collecting SalesOffice prices...")
    now = datetime.utcnow()

    try:
        df = pd.read_sql_query(QUERY, engine)
    except Exception as e:
        logger.error("Failed to query SalesOffice: %s", e)
        return pd.DataFrame()

    if df.empty:
        logger.warning("No mapped rooms found")
        return df

    # Convert dates to string for storage
    for col in ("date_from", "date_to"):
        if col in df.columns:
            df[col] = df[col].astype(str)

    count = save_snapshot(df, snapshot_ts=now)
    logger.info(
        "Collected %d rooms across %d hotels. Stored %d new rows. Snapshot: %s",
        len(df),
        df["hotel_id"].nunique(),
        count,
        now.strftime("%Y-%m-%d %H:%M"),
    )

    return df


HISTORY_QUERY = """
SELECT
    d.SalesOfficeOrderId AS order_id,
    o.DestinationId      AS hotel_id,
    h.name               AS hotel_name,
    o.DateFrom           AS date_from,
    o.DateTo             AS date_to,
    d.RoomCategory       AS room_category,
    d.RoomBoard          AS room_board,
    d.RoomPrice          AS room_price,
    d.DateCreated        AS scan_date
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
JOIN Med_Hotels h ON o.DestinationId = h.HotelId
WHERE o.DestinationId IN (
    SELECT DISTINCT o2.DestinationId
    FROM [SalesOffice.Orders] o2
    WHERE o2.IsActive = 1
      AND o2.WebJobStatus LIKE 'Completed%'
      AND o2.WebJobStatus NOT LIKE '%Mapping: 0%'
)
ORDER BY o.DestinationId, o.DateFrom, d.RoomCategory, d.DateCreated
"""


def load_historical_prices() -> pd.DataFrame:
    """Load ALL historical price records (incl soft-deleted) for active hotels.

    Returns DataFrame with columns: order_id, hotel_id, hotel_name, date_from,
    date_to, room_category, room_board, room_price, scan_date.
    """
    from src.data.trading_db import get_trading_engine

    engine = get_trading_engine()
    if engine is None:
        logger.error("Cannot connect to trading DB for historical data")
        return pd.DataFrame()

    logger.info("Loading historical price data from SalesOffice...")

    try:
        df = pd.read_sql_query(HISTORY_QUERY, engine)
    except Exception as e:
        logger.error("Failed to load historical prices: %s", e)
        return pd.DataFrame()

    if df.empty:
        logger.warning("No historical data found")
        return df

    for col in ("date_from", "date_to"):
        if col in df.columns:
            df[col] = df[col].astype(str)

    logger.info(
        "Loaded %d historical records across %d hotels, %d orders",
        len(df),
        df["hotel_id"].nunique(),
        df["order_id"].nunique(),
    )
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    df = collect_prices()
    if not df.empty:
        print(f"\nCollected {len(df)} rooms:")
        print(df.groupby(["hotel_id", "hotel_name"]).agg(
            rooms=("detail_id", "count"),
            min_price=("room_price", "min"),
            max_price=("room_price", "max"),
            avg_price=("room_price", "mean"),
        ).round(2))
