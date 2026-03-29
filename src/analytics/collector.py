"""SalesOffice price collector — pulls room prices from medici-db.

Queries [SalesOffice.Details] joined with [SalesOffice.Orders] and Med_Hotels
for all active orders that have mapping (Completed + Mapping > 0).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import pandas as pd

from config.settings import MEDICI_DB_URL
from src.analytics.price_store import init_db, save_snapshot

logger = logging.getLogger(__name__)

_collection_runtime_lock = threading.Lock()
_collection_runtime: dict[str, object] = {
    "db_configured": bool(MEDICI_DB_URL),
    "last_state": "never_run",
    "last_attempt_ts": None,
    "last_started_ts": None,
    "last_completed_ts": None,
    "last_successful_db_query_ts": None,
    "last_duration_ms": None,
    "last_rows_collected": 0,
    "last_hotels_collected": 0,
    "last_snapshot_rows_saved": 0,
    "last_error": None,
    "last_failure_ts": None,
}


def _update_collection_runtime(**updates: object) -> None:
    with _collection_runtime_lock:
        _collection_runtime.update(updates)


def get_collection_runtime_status() -> dict[str, object]:
    """Return a snapshot of the latest SalesOffice collection runtime metadata."""
    with _collection_runtime_lock:
        runtime = dict(_collection_runtime)
    runtime["db_configured"] = bool(MEDICI_DB_URL)
    return runtime

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
  AND d.IsDeleted = 0
ORDER BY d.HotelId, o.DateFrom
"""


def collect_prices() -> pd.DataFrame:
    """Pull current prices from medici-db and store locally.

    Returns the collected DataFrame.
    """
    from src.data.trading_db import get_trading_engine

    init_db()

    started_at = datetime.utcnow()
    started_ts = started_at.isoformat()
    started_perf = time.perf_counter()
    _update_collection_runtime(
        last_state="running",
        last_attempt_ts=started_ts,
        last_started_ts=started_ts,
        last_completed_ts=None,
        last_error=None,
    )

    def _finish_collection(
        *,
        state: str,
        rows_collected: int = 0,
        hotels_collected: int = 0,
        snapshot_rows_saved: int = 0,
        error: str | None = None,
        successful_query: bool = False,
    ) -> None:
        finished_ts = datetime.utcnow().isoformat()
        duration_ms = int((time.perf_counter() - started_perf) * 1000)
        payload: dict[str, object] = {
            "last_state": state,
            "last_completed_ts": finished_ts,
            "last_duration_ms": duration_ms,
            "last_rows_collected": int(rows_collected),
            "last_hotels_collected": int(hotels_collected),
            "last_snapshot_rows_saved": int(snapshot_rows_saved),
            "last_error": error,
        }
        if successful_query:
            payload["last_successful_db_query_ts"] = finished_ts
        if error:
            payload["last_failure_ts"] = finished_ts
        _update_collection_runtime(**payload)

    try:
        engine = get_trading_engine()
    except ValueError as e:
        logger.error("Cannot connect to trading DB: %s", e)
        _finish_collection(state="failed", error=str(e))
        return pd.DataFrame()

    if engine is None:
        logger.error("Cannot connect to trading DB")
        _finish_collection(state="failed", error="Trading DB engine unavailable")
        return pd.DataFrame()

    logger.info("Collecting SalesOffice prices...")
    now = started_at

    try:
        df = pd.read_sql_query(QUERY, engine)
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.error("Failed to query SalesOffice: %s", e, exc_info=True)
        _finish_collection(state="failed", error=str(e))
        return pd.DataFrame()

    if df.empty:
        logger.warning("No mapped rooms found")
        _finish_collection(state="empty", successful_query=True)
        return df

    # Filter out extreme price outliers (runaway override protection)
    MAX_SANE_PRICE = 10_000.0
    if "room_price" in df.columns:
        outliers = df[df["room_price"] > MAX_SANE_PRICE]
        if len(outliers) > 0:
            logger.warning(
                "Filtered %d outlier prices (>$%s): %s",
                len(outliers), f"{MAX_SANE_PRICE:,.0f}",
                ", ".join(
                    f"{r.get('hotel_name', '?')} ${r['room_price']:,.0f}"
                    for _, r in outliers.head(5).iterrows()
                ),
            )
            df = df[df["room_price"] <= MAX_SANE_PRICE]

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

    _finish_collection(
        state="success",
        rows_collected=len(df),
        hotels_collected=df["hotel_id"].nunique(),
        snapshot_rows_saved=count,
        successful_query=True,
    )

    return df


def collect_med_book_predictions() -> pd.DataFrame:
    """Collect active MED_Book rooms for prediction pipeline.

    Returns DataFrame with same schema as SalesOffice collection for direct merging.
    """
    try:
        from src.data.trading_db import load_med_book_for_prediction
        df = load_med_book_for_prediction()
        if not df.empty:
            logger.info("MED_Book: loaded %d active rooms for prediction", len(df))
        return df
    except (ImportError, OSError, ConnectionError, ValueError) as exc:
        logger.warning("MED_Book collection failed: %s", exc)
        return pd.DataFrame()


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
)
ORDER BY o.DestinationId, o.DateFrom, d.RoomCategory, d.DateCreated
"""


def load_historical_prices() -> pd.DataFrame:
    """Load ALL historical price records (incl soft-deleted) for active hotels.

    Combines two sources:
    1. SalesOffice history (recent ~36 days of scan data)
    2. MED_SearchHotels (2020-2023, up to 500k rows for tracked hotels)

    Returns DataFrame with columns: order_id, hotel_id, hotel_name, date_from,
    date_to, room_category, room_board, room_price, scan_date.
    """
    from src.data.trading_db import get_trading_engine

    engine = get_trading_engine()
    if engine is None:
        logger.error("Cannot connect to trading DB for historical data")
        return pd.DataFrame()

    # --- Source 1: SalesOffice history ---
    logger.info("Loading historical price data from SalesOffice...")
    so_df = pd.DataFrame()
    try:
        so_df = pd.read_sql_query(HISTORY_QUERY, engine)
    except (OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.error("Failed to load SalesOffice history: %s", e, exc_info=True)

    so_count = len(so_df)
    logger.info("SalesOffice history: %d rows", so_count)

    # --- Source 2: MED_SearchHotels (2020-2023) ---
    search_df = pd.DataFrame()
    try:
        from config.hotel_segments import HOTEL_SEGMENTS
        from src.data.trading_db import load_med_search_hotels

        tracked_ids = list(HOTEL_SEGMENTS.keys())
        # Disabled: MED_SearchHotels loading moved to nightly cache refresh
        # to avoid heavy Azure SQL query during startup/analysis cycle.
        # raw = load_med_search_hotels(hotel_ids=tracked_ids, limit=50_000)
        raw = pd.DataFrame()  # Empty — will be populated by cache_aggregator nightly

        if not raw.empty:
            # Map MED_SearchHotels columns to unified schema
            search_df = pd.DataFrame({
                "order_id": (
                    raw["RequestTime"].astype(str) + "_" + raw["HotelId"].astype(str)
                ).apply(lambda x: abs(hash(x)) % (10**10)),
                "hotel_id": raw["HotelId"],
                "hotel_name": None,  # not available in search data
                "date_from": raw["DateFrom"],
                "date_to": None,     # not reliably available
                "room_category": raw["CategoryId"],
                "room_board": raw["BoardId"],
                "room_price": raw["Price"],
                "scan_date": raw["RequestTime"],
            })
            # Drop rows with missing price or hotel
            search_df = search_df.dropna(subset=["room_price", "hotel_id"])
            logger.info(
                "MED_SearchHotels: %d rows loaded for %d tracked hotels",
                len(search_df),
                search_df["hotel_id"].nunique(),
            )
    except (ImportError, OSError, ConnectionError, TimeoutError, ValueError) as e:
        logger.warning("MED_SearchHotels load failed (fallback to SalesOffice only): %s", e)

    # --- Combine both sources ---
    frames = [f for f in (so_df, search_df) if not f.empty]
    if not frames:
        logger.warning("No historical data found from any source")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    for col in ("date_from", "date_to"):
        if col in df.columns:
            df[col] = df[col].astype(str)

    logger.info(
        "Combined historical data: %d rows (%d SalesOffice + %d MED_SearchHotels), %d hotels",
        len(df),
        so_count,
        len(search_df),
        df["hotel_id"].nunique(),
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
