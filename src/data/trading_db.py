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

    # Append connection timeout to the URL so pyodbc doesn't hang forever
    url = MEDICI_DB_URL
    sep = "&" if "?" in url else "?"
    if "timeout" not in url.lower() and "connect_timeout" not in url.lower():
        url = f"{url}{sep}connect_timeout=10"

    _engine = create_engine(
        url,
        pool_size=5,
        max_overflow=2,
        pool_timeout=15,
        pool_recycle=1800,
        pool_pre_ping=True,
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
# Market Benchmark (hotel vs same-star hotels in same city)
# ---------------------------------------------------------------------------

def load_market_benchmark(hotel_ids: list[int],
                          days_back: int = 60) -> dict[int, dict]:
    """Market benchmark: avg price of same-star hotels in same city.

    Uses AI_Search_HotelData (8.5M rows, 6K+ hotels, 323 cities) to compute
    how each hotel's pricing compares to similar hotels in the market.

    For each hotel_id, finds all OTHER hotels with the same CityName and Stars
    rating, then returns:
      - market_avg_price: average price across competitor hotels
      - our_avg_price: our hotel's average price in AI_Search
      - pressure: (market_avg - our_avg) / market_avg, clamped [-1, +1]
        Positive = market charges more (opportunity to raise)
        Negative = market charges less (risk of being overpriced)

    Returns dict: {hotel_id: {city, stars, market_avg_price, pressure, ...}}
    """
    if not hotel_ids:
        return {}

    placeholders = ",".join(str(int(h)) for h in hotel_ids)
    params: dict = {"days_back": -abs(days_back)}

    # Single CTE query: our hotel refs → our prices → market averages
    query = f"""
    WITH our_ref AS (
        SELECT DISTINCT HotelId, CityName, Stars
        FROM AI_Search_HotelData
        WHERE HotelId IN ({placeholders})
          AND Stars IS NOT NULL
          AND CityName IS NOT NULL
    ),
    our_prices AS (
        SELECT HotelId,
               AVG(PriceAmount) AS our_avg_price,
               COUNT(*) AS our_samples
        FROM AI_Search_HotelData
        WHERE HotelId IN ({placeholders})
          AND PriceAmount > 0
          AND UpdatedAt >= DATEADD(day, :days_back, GETDATE())
        GROUP BY HotelId
    ),
    market AS (
        SELECT r.HotelId       AS our_hotel_id,
               r.CityName,
               r.Stars,
               COUNT(DISTINCT a.HotelId) AS competitor_hotels,
               AVG(a.PriceAmount)        AS market_avg_price,
               MIN(a.PriceAmount)        AS market_min_price,
               MAX(a.PriceAmount)        AS market_max_price,
               COUNT(*)                  AS market_samples
        FROM our_ref r
        INNER JOIN AI_Search_HotelData a
            ON a.CityName = r.CityName
           AND a.Stars    = r.Stars
        WHERE a.HotelId NOT IN ({placeholders})
          AND a.PriceAmount > 0
          AND a.UpdatedAt >= DATEADD(day, :days_back, GETDATE())
        GROUP BY r.HotelId, r.CityName, r.Stars
    )
    SELECT m.our_hotel_id  AS hotel_id,
           m.CityName      AS city,
           m.Stars         AS stars,
           m.competitor_hotels,
           m.market_avg_price,
           m.market_min_price,
           m.market_max_price,
           m.market_samples,
           COALESCE(p.our_avg_price, 0) AS our_avg_price,
           COALESCE(p.our_samples, 0)   AS our_samples
    FROM market m
    LEFT JOIN our_prices p ON m.our_hotel_id = p.HotelId
    """

    try:
        df = run_trading_query(query, params)
    except Exception as exc:
        logger.warning("Market benchmark query failed: %s", exc)
        return {}

    if df.empty:
        return {}

    result: dict[int, dict] = {}
    for _, row in df.iterrows():
        hid = int(row["hotel_id"])
        market_avg = float(row["market_avg_price"] or 0)
        our_avg = float(row["our_avg_price"] or 0)

        # Pressure: positive = market more expensive (we can raise)
        #           negative = market cheaper (we're overpriced)
        pressure = 0.0
        if market_avg > 0 and our_avg > 0:
            pressure = max(-1.0, min(1.0, (market_avg - our_avg) / market_avg))

        result[hid] = {
            "city": row["city"],
            "stars": int(row["stars"]),
            "market_avg_price": round(market_avg, 2),
            "market_min_price": round(float(row["market_min_price"] or 0), 2),
            "market_max_price": round(float(row["market_max_price"] or 0), 2),
            "competitor_hotels": int(row["competitor_hotels"] or 0),
            "market_samples": int(row["market_samples"] or 0),
            "our_avg_price": round(our_avg, 2),
            "pressure": round(pressure, 4),
        }

    return result


# ---------------------------------------------------------------------------
# AI Search Hotel Data (8.5M rows — competitor/market pricing)
# ---------------------------------------------------------------------------

def load_ai_search_data(hotel_ids: list[int] | None = None,
                        days_back: int = 90) -> pd.DataFrame:
    """Load AI search hotel pricing data.

    This is the richest pricing table: 8.5M rows with prices across
    6,000+ hotels, 323 cities, room types, boards, and stars.
    """
    query = """
        SELECT Id, HotelId, HotelName, CityName, StayFrom, StayTo,
               CountryCode, PriceAmount, PriceAmountCurrency,
               CancellationType, RoomType, UpdatedAt, Board, Stars
        FROM AI_Search_HotelData
        WHERE UpdatedAt >= DATEADD(day, :days_back, GETDATE())
    """
    params = {"days_back": -abs(days_back)}
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" AND HotelId IN ({placeholders})"
    query += " ORDER BY UpdatedAt DESC"
    df = run_trading_query(query, params)
    return _convert_date_columns(df, ["StayFrom", "StayTo", "UpdatedAt"])


def load_ai_search_summary(hotel_ids: list[int] | None = None) -> pd.DataFrame:
    """Load aggregated AI search stats per hotel — lightweight summary."""
    query = """
        SELECT HotelId, HotelName, CityName, Stars,
               COUNT(*) AS search_count,
               AVG(PriceAmount) AS avg_price,
               MIN(PriceAmount) AS min_price,
               MAX(PriceAmount) AS max_price,
               MIN(UpdatedAt) AS first_seen,
               MAX(UpdatedAt) AS last_seen,
               COUNT(DISTINCT RoomType) AS room_types,
               COUNT(DISTINCT Board) AS boards
        FROM AI_Search_HotelData
    """
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" WHERE HotelId IN ({placeholders})"
    query += " GROUP BY HotelId, HotelName, CityName, Stars ORDER BY search_count DESC"
    return run_trading_query(query)


def load_ai_search_price_history(hotel_id: int, room_type: str | None = None,
                                  board: str | None = None) -> pd.DataFrame:
    """Load price time-series for a specific hotel from AI search data."""
    query = """
        SELECT StayFrom, StayTo, PriceAmount, RoomType, Board,
               CancellationType, UpdatedAt
        FROM AI_Search_HotelData
        WHERE HotelId = :hotel_id
    """
    params = {"hotel_id": hotel_id}
    if room_type:
        query += " AND RoomType = :room_type"
        params["room_type"] = room_type
    if board:
        query += " AND Board = :board"
        params["board"] = board
    query += " ORDER BY UpdatedAt"
    df = run_trading_query(query, params)
    return _convert_date_columns(df, ["StayFrom", "StayTo", "UpdatedAt"])


# ---------------------------------------------------------------------------
# Search Results Session Poll Log (8.3M rows — detailed search results)
# ---------------------------------------------------------------------------

def load_search_results(hotel_ids: list[int] | None = None,
                        days_back: int = 90) -> pd.DataFrame:
    """Load detailed search results with net/gross prices and providers.

    Excludes large JSON fields (RequestJson, ResponseJson) to keep queries fast.
    """
    query = """
        SELECT Id, RequestTime, DateInsert, PriceAmount, PriceAmountCurrency,
               NetPriceAmount, NetPriceCurrency, BarRateAmount,
               Confirmation, PaymentType, Providers,
               RoomName, RoomCategory, RoomBedding, RoomBoard,
               HotelId, PaxAdults, CancellationType,
               CancellationFrom, CancellationTo
        FROM SearchResultsSessionPollLog
        WHERE DateInsert >= DATEADD(day, :days_back, GETDATE())
    """
    params = {"days_back": -abs(days_back)}
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" AND HotelId IN ({placeholders})"
    query += " ORDER BY DateInsert DESC"
    df = run_trading_query(query, params)
    return _convert_date_columns(df, ["RequestTime", "DateInsert",
                                       "CancellationFrom", "CancellationTo"])


def load_search_results_summary(hotel_ids: list[int] | None = None) -> pd.DataFrame:
    """Aggregated search results stats per hotel."""
    query = """
        SELECT HotelId,
               COUNT(*) AS search_count,
               AVG(PriceAmount) AS avg_gross_price,
               AVG(NetPriceAmount) AS avg_net_price,
               MIN(PriceAmount) AS min_price,
               MAX(PriceAmount) AS max_price,
               AVG(PriceAmount - NetPriceAmount) AS avg_margin,
               COUNT(DISTINCT RoomCategory) AS categories,
               COUNT(DISTINCT RoomBoard) AS boards,
               COUNT(DISTINCT Providers) AS provider_combos,
               MIN(DateInsert) AS first_seen,
               MAX(DateInsert) AS last_seen
        FROM SearchResultsSessionPollLog
    """
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" WHERE HotelId IN ({placeholders})"
    query += " GROUP BY HotelId ORDER BY search_count DESC"
    return run_trading_query(query)


# ---------------------------------------------------------------------------
# MED_SearchHotels (7M rows — historical search data 2020-2023)
# ---------------------------------------------------------------------------

def load_med_search_hotels(hotel_ids: list[int] | None = None) -> pd.DataFrame:
    """Load historical search results (2020-2023 era).

    133 hotels, 3 providers — valuable for long-term pattern analysis.
    """
    query = """
        SELECT RequestTime, DateForm AS DateFrom, DateTo, NumberOfNights,
               HotelId, CategoryId, BeddingId, BoardId,
               PaxAdultsCount AS Adults, Price, CurrencyId,
               providerId, providerName, CancellationType, source
        FROM MED_SearchHotels
    """
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" WHERE HotelId IN ({placeholders})"
    query += " ORDER BY RequestTime DESC"
    return run_trading_query(query)


# ---------------------------------------------------------------------------
# Room Price Update Log (82K rows — every price change event)
# ---------------------------------------------------------------------------

def load_price_updates(days_back: int = 180) -> pd.DataFrame:
    """Load price change events — shows every time a room price was updated."""
    query = """
        SELECT r.Id, r.DateInsert, r.PreBookId, r.Price,
               b.HotelId, b.startDate AS DateFrom, b.endDate AS DateTo,
               b.source AS Source
        FROM RoomPriceUpdateLog r
        LEFT JOIN MED_Book b ON r.PreBookId = b.PreBookId
        WHERE r.DateInsert >= DATEADD(day, :days_back, GETDATE())
        ORDER BY r.DateInsert DESC
    """
    df = run_trading_query(query, {"days_back": -abs(days_back)})
    return _convert_date_columns(df, ["DateInsert", "DateFrom", "DateTo"])


def load_price_update_velocity(hotel_ids: list[int] | None = None) -> pd.DataFrame:
    """Compute price change velocity — how fast and how much prices move."""
    query = """
        SELECT b.HotelId,
               COUNT(r.Id) AS total_updates,
               COUNT(DISTINCT r.PreBookId) AS unique_rooms,
               AVG(r.Price) AS avg_price,
               ISNULL(STDEV(r.Price), 0) AS price_stdev,
               MIN(r.DateInsert) AS first_update,
               MAX(r.DateInsert) AS last_update
        FROM RoomPriceUpdateLog r
        LEFT JOIN MED_Book b ON r.PreBookId = b.PreBookId
        WHERE b.HotelId IS NOT NULL
    """
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" AND b.HotelId IN ({placeholders})"
    query += " GROUP BY b.HotelId ORDER BY total_updates DESC"
    return run_trading_query(query)


# ---------------------------------------------------------------------------
# PreBook data (10.7K rows — pre-booking with provider info)
# ---------------------------------------------------------------------------

def load_prebooks(hotel_ids: list[int] | None = None,
                  days_back: int = 180) -> pd.DataFrame:
    """Load pre-booking data with provider and pricing info."""
    query = """
        SELECT PreBookId, DateInsert, HotelId, DateForm AS DateFrom,
               DateTo, Price, CurrencyId, CategoryId, BoardId,
               PaxAdultsCount AS Adults, PaxChildrenCount AS Children,
               CancellationType, ProviderName, source AS Source,
               NumberOfNights
        FROM MED_PreBook
        WHERE DateInsert >= DATEADD(day, :days_back, GETDATE())
    """
    params = {"days_back": -abs(days_back)}
    if hotel_ids:
        placeholders = ",".join(str(int(h)) for h in hotel_ids)
        query += f" AND HotelId IN ({placeholders})"
    query += " ORDER BY DateInsert DESC"
    df = run_trading_query(query, params)
    return _convert_date_columns(df, ["DateInsert", "DateFrom", "DateTo"])


# ---------------------------------------------------------------------------
# Destinations & Hotel Geo (40K + 745K rows)
# ---------------------------------------------------------------------------

def load_destinations() -> pd.DataFrame:
    """Load all destinations with geo coordinates."""
    query = """
        SELECT Id, Name, Type, Latitude, Longitude, CountryId, SeoName
        FROM Destinations
        WHERE Latitude IS NOT NULL AND Longitude IS NOT NULL
    """
    return run_trading_query(query)


def load_hotels_with_geo() -> pd.DataFrame:
    """Load hotel metadata with lat/long from Med_Hotels_instant."""
    query = """
        SELECT h.HotelId, h.name AS Name, h.isActive AS IsActive,
               h.BoardId, h.CategoryId,
               i.stars AS Stars, i.countryName AS Country,
               i.countryIso AS CountryCode,
               i.Latitude, i.Longitude
        FROM Med_Hotels h
        LEFT JOIN Med_Hotels_instant i ON h.HotelId = i.HotelId
        WHERE h.isActive = 1
    """
    return run_trading_query(query)


def load_competitor_hotels(hotel_id: int, radius_km: float = 5.0,
                           stars: int | None = None) -> pd.DataFrame:
    """Find competitor hotels within radius using Haversine approx.

    Uses Med_Hotels_instant for lat/long, then filters by distance.
    """
    # First get our hotel's coordinates
    ref = run_trading_query(
        "SELECT Latitude, Longitude FROM Med_Hotels_instant WHERE HotelId = :hid",
        {"hid": hotel_id}
    )
    if ref.empty or ref.iloc[0]["Latitude"] is None:
        return pd.DataFrame()

    lat, lon = float(ref.iloc[0]["Latitude"]), float(ref.iloc[0]["Longitude"])
    # Rough bounding box (1 degree ~ 111 km)
    delta = radius_km / 111.0
    query = """
        SELECT i.HotelId, i.name AS Name, i.stars AS Stars,
               i.countryName AS Country, i.Latitude, i.Longitude
        FROM Med_Hotels_instant i
        WHERE i.isActive = 1
          AND i.Latitude BETWEEN :lat_min AND :lat_max
          AND i.Longitude BETWEEN :lon_min AND :lon_max
          AND i.HotelId != :hotel_id
    """
    params = {
        "lat_min": lat - delta, "lat_max": lat + delta,
        "lon_min": lon - delta, "lon_max": lon + delta,
        "hotel_id": hotel_id,
    }
    if stars is not None:
        query += " AND i.stars = :stars"
        params["stars"] = stars
    df = run_trading_query(query, params)
    if df.empty:
        return df

    # Drop rows with missing coordinates
    df = df.dropna(subset=["Latitude", "Longitude"])
    if df.empty:
        return df

    # Compute actual distance
    df["distance_km"] = df.apply(
        lambda r: _haversine(lat, lon, float(r["Latitude"]), float(r["Longitude"])),
        axis=1,
    )
    df = df[df["distance_km"] <= radius_km].sort_values("distance_km")
    return df


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# SalesOffice Log (1.2M rows — action/event logs)
# ---------------------------------------------------------------------------

def load_salesoffice_log(order_id: int | None = None,
                         days_back: int = 30) -> pd.DataFrame:
    """Load SalesOffice action logs."""
    query = """
        SELECT l.Id, l.SalesOfficeOrderId, l.SalesOfficeDetailId,
               l.DateCreated, l.Message, l.ActionId, l.ActionResultId,
               a.Name AS ActionName, r.Name AS ResultName
        FROM [SalesOffice.Log] l
        LEFT JOIN [SalesOffice.LogActionsDictionary] a ON l.ActionId = a.Id
        LEFT JOIN [SalesOffice.LogActionsResultDictionary] r ON l.ActionResultId = r.Id
        WHERE l.DateCreated >= DATEADD(day, :days_back, GETDATE())
    """
    params = {"days_back": -abs(days_back)}
    if order_id is not None:
        query += " AND l.SalesOfficeOrderId = :order_id"
        params["order_id"] = order_id
    query += " ORDER BY l.DateCreated DESC"
    df = run_trading_query(query, params)
    return _convert_date_columns(df, ["DateCreated"])


# ---------------------------------------------------------------------------
# Cancellation data (MED_CancelBook — 4.7K rows)
# ---------------------------------------------------------------------------

def load_cancellations(days_back: int = 365) -> pd.DataFrame:
    """Load booking cancellation history with reasons."""
    query = """
        SELECT c.Id, c.DateInsert, c.PreBookId, c.contentBookingID,
               c.CancellationReason, c.CancellationDate,
               b.HotelId, b.startDate AS DateFrom, b.endDate AS DateTo,
               b.price AS BuyPrice
        FROM MED_CancelBook c
        LEFT JOIN MED_Book b ON c.PreBookId = b.PreBookId
        WHERE c.DateInsert >= DATEADD(day, :days_back, GETDATE())
        ORDER BY c.DateInsert DESC
    """
    df = run_trading_query(query, {"days_back": -abs(days_back)})
    return _convert_date_columns(df, ["DateInsert", "CancellationDate",
                                       "DateFrom", "DateTo"])


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


# ---------------------------------------------------------------------------
# App Service structured logs (local JSONL files as data source)
# ---------------------------------------------------------------------------

def load_appservice_prediction_logs(days_back: int = 90) -> pd.DataFrame:
    """Load prediction events from App Service structured logs.

    These are written by prediction_logger.py every time the analyzer runs.
    Returns a DataFrame with hotel_id, current_price, predicted_price,
    date_from, days_to_checkin, enrichments, momentum, etc.
    """
    try:
        from src.analytics.prediction_logger import load_prediction_logs
        events = load_prediction_logs(days_back=days_back)
        if not events:
            return pd.DataFrame()
        df = pd.DataFrame(events)
        # Flatten enrichments into columns
        if "enrichments" in df.columns:
            enr = pd.json_normalize(df["enrichments"].apply(
                lambda x: x if isinstance(x, dict) else {}
            ))
            enr.columns = [f"enr_{c}" for c in enr.columns]
            df = pd.concat([df.drop(columns=["enrichments"]), enr], axis=1)
        # Flatten momentum into columns
        if "momentum" in df.columns:
            mom = pd.json_normalize(df["momentum"].apply(
                lambda x: x if isinstance(x, dict) else {}
            ))
            mom.columns = [f"mom_{c}" for c in mom.columns]
            df = pd.concat([df.drop(columns=["momentum"]), mom], axis=1)
        return df
    except Exception as e:
        logger.warning("Failed to load prediction logs: %s", e)
        return pd.DataFrame()


def load_appservice_price_logs(days_back: int = 90) -> pd.DataFrame:
    """Load price observation events from App Service structured logs."""
    try:
        from src.analytics.prediction_logger import load_price_logs
        events = load_price_logs(days_back=days_back)
        if not events:
            return pd.DataFrame()
        return pd.DataFrame(events)
    except Exception as e:
        logger.warning("Failed to load price logs: %s", e)
        return pd.DataFrame()


def load_appservice_price_change_logs(days_back: int = 90) -> pd.DataFrame:
    """Load price change events from App Service structured logs."""
    try:
        from src.analytics.prediction_logger import load_price_change_logs
        events = load_price_change_logs(days_back=days_back)
        if not events:
            return pd.DataFrame()
        return pd.DataFrame(events)
    except Exception as e:
        logger.warning("Failed to load price change logs: %s", e)
        return pd.DataFrame()

