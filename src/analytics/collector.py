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
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.error("Failed to query SalesOffice: %s", e, exc_info=True)
        return pd.DataFrame()

    if df.empty:
        logger.warning("No mapped rooms found")
        return df

    # Convert dates to string for storage
    for col in ("date_from", "date_to"):
        if col in df.columns:
            df[col] = df[col].astype(str)

    count = save_snapshot(df, snapshot_ts=now)

    # Log price observations to structured event log (training data source)
    try:
        from src.analytics.prediction_logger import log_price_snapshot
        log_price_snapshot(df, snapshot_ts=now)
    except (ImportError, FileNotFoundError, OSError, ValueError) as e:
        logger.warning("Failed to log price snapshot: %s", e)

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
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.error("Failed to load historical prices: %s", e, exc_info=True)
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


SCAN_HISTORY_QUERY = """
SELECT
    d.SalesOfficeOrderId AS order_id,
    d.HotelId            AS hotel_id,
    d.RoomCategory       AS room_category,
    d.RoomBoard          AS room_board,
    d.RoomPrice          AS room_price,
    d.DateCreated        AS scan_date
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.IsActive = 1
  AND o.WebJobStatus LIKE 'Completed%%'
  AND o.WebJobStatus NOT LIKE '%%Mapping: 0%%'
ORDER BY d.SalesOfficeOrderId, d.HotelId, d.RoomCategory, d.RoomBoard, d.DateCreated
"""


def load_scan_history() -> pd.DataFrame:
    """Load all historical scan records from medici-db for scan_history analysis.

    Each row = one room result from one scan.  Matching key for tracking a room
    across scans: (order_id, hotel_id, room_category, room_board).
    Multiple scans are distinguished by scan_date (DateCreated).

    Returns DataFrame with columns: order_id, hotel_id, room_category,
    room_board, room_price, scan_date.
    """
    from src.data.trading_db import get_trading_engine

    engine = get_trading_engine()
    if engine is None:
        logger.error("Cannot connect to trading DB for scan history")
        return pd.DataFrame()

    logger.info("Loading scan history from medici-db [SalesOffice.Details]...")

    try:
        df = pd.read_sql_query(SCAN_HISTORY_QUERY, engine)
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.error("Failed to load scan history: %s", e, exc_info=True)
        return pd.DataFrame()

    if df.empty:
        logger.warning("No scan history found")
        return df

    n_scans = df["scan_date"].nunique() if "scan_date" in df.columns else 0
    logger.info(
        "Loaded %d scan records, %d unique scan dates, %d orders",
        len(df), n_scans, df["order_id"].nunique(),
    )
    return df


if __name__ == "__main__":
    from src.utils.logging_config import configure_logging
    configure_logging()
    df = collect_prices()
    if not df.empty:
        summary = df.groupby(["hotel_id", "hotel_name"]).agg(
            rooms=("detail_id", "count"),
            min_price=("room_price", "min"),
            max_price=("room_price", "max"),
            avg_price=("room_price", "mean"),
        ).round(2)
        logger.info("Collected %d rooms:\n%s", len(df), summary)
