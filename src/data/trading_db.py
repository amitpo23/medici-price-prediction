"""Read-only access to the Medici Hotels trading database (medici-db).

IMPORTANT: This module provides READ-ONLY access. No INSERT, UPDATE, or DELETE
operations are permitted. The prediction system is a decision brain only.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from config.settings import MEDICI_DB_URL


_engine: Engine | None = None


def get_trading_engine() -> Engine:
    """Create and return a read-only SQLAlchemy engine for medici-db."""
    global _engine
    if _engine is not None:
        return _engine

    if not MEDICI_DB_URL:
        raise ValueError("MEDICI_DB_URL must be set in .env file")

    _engine = create_engine(
        MEDICI_DB_URL,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800,
        echo=False,
    )

    @event.listens_for(_engine, "before_cursor_execute")
    def _block_writes(conn, cursor, statement, parameters, context, executemany):
        stmt_upper = statement.strip().upper()
        for forbidden in (
            "INSERT", "UPDATE", "DELETE", "DROP",
            "ALTER", "CREATE", "TRUNCATE", "EXEC",
        ):
            if stmt_upper.startswith(forbidden):
                raise PermissionError(
                    f"Write operation blocked: {forbidden}. "
                    "Prediction system has read-only access to medici-db."
                )

    return _engine


def run_trading_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """Run a SELECT query against medici-db. Returns DataFrame."""
    engine = get_trading_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


def _convert_date_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert specified columns to datetime."""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Booking data (MED_Book)
# ---------------------------------------------------------------------------

def load_active_bookings() -> pd.DataFrame:
    """Load all active (unsold) bookings from MED_Book.

    Price mapping:
      b.price         = actual cost paid to supplier (BuyPrice)
      o.PushPrice     = intended selling price (PushPrice)
      b.lastPrice     = last known push price before update
    """
    opp_table = _get_opportunities_table_name()
    query = f"""
        SELECT b.id AS Id, b.PreBookId, b.OpportunityId, b.HotelId,
               b.price AS BuyPrice,
               COALESCE(o.PushPrice, b.price) AS PushPrice,
               b.lastPrice AS LastPrice, b.IsActive, b.IsSold, b.SoldId,
               b.startDate AS DateFrom, b.endDate AS DateTo,
               b.CancellationTo, b.source AS Source,
               b.PaxAdultsCount AS Adults, b.PaxChildrenCount AS Children,
               b.DateInsert AS Created, b.contentBookingID AS ContentBookingId,
               h.name AS HotelName
        FROM MED_Book b
        LEFT JOIN Med_Hotels h ON b.HotelId = h.HotelId
        LEFT JOIN [{opp_table}] o ON b.OpportunityId = o.OpportunityId
        WHERE b.IsActive = 1
        ORDER BY b.DateInsert DESC
    """
    df = run_trading_query(query)
    return _convert_date_columns(df, ["DateFrom", "DateTo", "CancellationTo", "Created"])


def load_all_bookings(days_back: int = 180) -> pd.DataFrame:
    """Load booking history (active + sold + cancelled) for analysis."""
    opp_table = _get_opportunities_table_name()
    query = f"""
        SELECT b.id AS Id, b.PreBookId, b.OpportunityId, b.HotelId,
               b.price AS BuyPrice,
               COALESCE(o.PushPrice, b.price) AS PushPrice,
               b.lastPrice AS LastPrice, b.IsActive, b.IsSold, b.SoldId,
               b.startDate AS DateFrom, b.endDate AS DateTo,
               b.CancellationTo, b.source AS Source,
               b.PaxAdultsCount AS Adults, b.PaxChildrenCount AS Children,
               b.DateInsert AS Created,
               h.name AS HotelName
        FROM MED_Book b
        LEFT JOIN Med_Hotels h ON b.HotelId = h.HotelId
        LEFT JOIN [{opp_table}] o ON b.OpportunityId = o.OpportunityId
        WHERE b.DateInsert >= DATEADD(day, :days_back, GETDATE())
        ORDER BY b.DateInsert DESC
    """
    df = run_trading_query(query, {"days_back": -abs(days_back)})
    return _convert_date_columns(df, ["DateFrom", "DateTo", "CancellationTo", "Created"])


def load_booking_by_prebook_id(pre_book_id: int) -> pd.DataFrame:
    """Load a single booking by PreBookId."""
    opp_table = _get_opportunities_table_name()
    query = f"""
        SELECT b.id AS Id, b.PreBookId, b.OpportunityId, b.HotelId,
               b.price AS BuyPrice,
               COALESCE(o.PushPrice, b.price) AS PushPrice,
               b.lastPrice AS LastPrice, b.IsActive, b.IsSold, b.SoldId,
               b.startDate AS DateFrom, b.endDate AS DateTo,
               b.CancellationTo, b.source AS Source,
               b.PaxAdultsCount AS Adults, b.PaxChildrenCount AS Children,
               b.DateInsert AS Created, b.contentBookingID AS ContentBookingId,
               h.name AS HotelName
        FROM MED_Book b
        LEFT JOIN Med_Hotels h ON b.HotelId = h.HotelId
        LEFT JOIN [{opp_table}] o ON b.OpportunityId = o.OpportunityId
        WHERE b.PreBookId = :pre_book_id
    """
    df = run_trading_query(query, {"pre_book_id": pre_book_id})
    return _convert_date_columns(df, ["DateFrom", "DateTo", "CancellationTo", "Created"])


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def _get_opportunities_table_name() -> str:
    """Resolve the actual Opportunities table name (contains Hebrew nikud chars)."""
    try:
        df = run_trading_query(
            "SELECT name FROM sys.tables "
            "WHERE name LIKE N'%pportunit%' AND name NOT LIKE 'BAK%' AND name NOT LIKE '%Log'"
        )
        if not df.empty:
            return df.iloc[0]["name"]
    except Exception:
        pass
    return "MED_Opportunities"  # fallback


def load_opportunities(days_back: int = 90) -> pd.DataFrame:
    """Load opportunities from MED_Opportunities."""
    table_name = _get_opportunities_table_name()
    query = f"""
        SELECT OpportunityId, DateForm AS DateFrom, DateTo,
               NumberOfNights, BoardId, CategoryId,
               Price AS BuyPrice, PushPrice,
               DestinationsId AS HotelId,
               FreeCancelation AS FreeCancellation,
               PaxAdultsCount AS Adults, PaxChildrenCount AS Children,
               IsActive, IsSale AS IsSold, PreBookId,
               DateCreate AS Created
        FROM [{table_name}]
        WHERE DateForm >= DATEADD(day, :days_back, GETDATE())
        ORDER BY OpportunityId DESC
    """
    df = run_trading_query(query, {"days_back": -abs(days_back)})
    return _convert_date_columns(df, ["DateFrom", "DateTo", "Created"])


def load_backoffice_opportunities(days_back: int = 180) -> pd.DataFrame:
    """Load BackOffice opportunities with full history."""
    query = """
        SELECT id AS Id, HotelID AS HotelId,
               StartDate AS DateFrom, EndDate AS DateTo,
               BordID AS BoardId, CatrgoryID AS CategoryId,
               BuyPrice, PushPrice, MaxRooms, Status,
               invTypeCode AS InvTypeCode, ratePlanCode AS RatePlanCode,
               DateInsert AS Created
        FROM BackOfficeOPT
        WHERE StartDate >= DATEADD(day, :days_back, GETDATE())
        ORDER BY id DESC
    """
    df = run_trading_query(query, {"days_back": -abs(days_back)})
    return _convert_date_columns(df, ["DateFrom", "DateTo", "Created"])


# ---------------------------------------------------------------------------
# Reservations
# ---------------------------------------------------------------------------

def load_reservations(days_back: int = 90) -> pd.DataFrame:
    """Load guest reservations from Med_Reservation."""
    query = """
        SELECT Id, DateInsert AS Created, ResStatus AS Status,
               HotelCode, datefrom AS DateFrom, dateto AS DateTo,
               AmountAfterTax, AmountBeforeTax, CurrencyCode,
               RatePlanCode, MealPlanCodes, RoomTypeCode,
               AdultCount AS Adults, ChildrenCount AS Children,
               uniqueID AS UniqueId, Type, IsApproved, IsCanceled
        FROM Med_Reservation
        WHERE DateInsert >= DATEADD(day, :days_back, GETDATE())
        ORDER BY DateInsert DESC
    """
    df = run_trading_query(query, {"days_back": -abs(days_back)})
    return _convert_date_columns(df, ["Created", "DateFrom", "DateTo"])


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

def load_hotels() -> pd.DataFrame:
    """Load hotel reference data from Med_Hotels."""
    query = """
        SELECT HotelId, InnstantId, Innstant_ZenithId AS ZenithId,
               Goglobalid AS GoGlobalId, name AS Name,
               countryId AS CountryId, BoardId, CategoryId,
               isActive AS IsActive, RatePlanCode, InvTypeCode
        FROM Med_Hotels
        WHERE isActive = 1
    """
    return run_trading_query(query)


def load_reference_data() -> dict[str, pd.DataFrame]:
    """Load all reference/lookup tables."""
    return {
        "boards": run_trading_query(
            "SELECT BoardId, BoardCode, Description FROM MED_Board"
        ),
        "categories": run_trading_query(
            "SELECT CategoryId, Name, Description, PMS_Code FROM MED_RoomCategory"
        ),
        "sources": run_trading_query(
            "SELECT Id, Name, IsAcive AS IsActive FROM Med_Source"
        ),
        "rate_by_cat": run_trading_query(
            "SELECT HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode "
            "FROM Med_Hotels_ratebycat"
        ),
    }


def load_historical_prices() -> pd.DataFrame:
    """Load historical monthly pricing from tprice."""
    query = "SELECT price AS Price, month AS Month, HotelId FROM tprice ORDER BY HotelId, month"
    return run_trading_query(query)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_connection() -> bool:
    """Check if the trading DB is accessible."""
    try:
        run_trading_query("SELECT 1 AS ok")
        return True
    except Exception:
        return False
