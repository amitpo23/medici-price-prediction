"""Load hotel pricing and booking data from Supabase."""

import pandas as pd
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY


def get_client() -> Client:
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .env file"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_table(table_name: str, columns: str = "*", limit: int | None = None) -> pd.DataFrame:
    """Load a table from Supabase into a DataFrame.

    Args:
        table_name: Name of the Supabase table.
        columns: Comma-separated column names or '*' for all.
        limit: Maximum number of rows to fetch. None for all.
    """
    client = get_client()
    query = client.table(table_name).select(columns)
    if limit:
        query = query.limit(limit)
    response = query.execute()
    return pd.DataFrame(response.data)


def load_bookings(limit: int | None = None) -> pd.DataFrame:
    """Load booking data with relevant pricing fields."""
    df = load_table("bookings", limit=limit)
    if df.empty:
        return df

    # Parse dates
    date_cols = [c for c in df.columns if "date" in c.lower() or "created" in c.lower()]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def load_rooms(limit: int | None = None) -> pd.DataFrame:
    """Load room inventory and pricing data."""
    return load_table("rooms", limit=limit)


def load_rates(limit: int | None = None) -> pd.DataFrame:
    """Load rate/pricing history."""
    df = load_table("rates", limit=limit)
    if df.empty:
        return df

    date_cols = [c for c in df.columns if "date" in c.lower()]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def load_daily_pricing(
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Load daily pricing data, optionally filtered by date range.

    This is the main function for feeding data into the forecasting model.
    Adjust the table name and columns to match your Supabase schema.
    """
    client = get_client()
    query = client.table("daily_prices").select("*")

    if start_date:
        query = query.gte("date", start_date)
    if end_date:
        query = query.lte("date", end_date)

    query = query.order("date")
    response = query.execute()
    df = pd.DataFrame(response.data)

    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

    return df


def discover_schema() -> dict:
    """Discover available tables and their columns.

    Useful for initial exploration when you're not sure about the schema.
    Returns a dict of {table_name: [columns]}.
    """
    client = get_client()
    # Try common hotel-related table names
    tables_to_try = [
        "bookings", "rooms", "rates", "daily_prices", "hotels",
        "reservations", "guests", "room_types", "pricing",
        "availability", "revenue", "competitors",
    ]
    schema = {}
    for table in tables_to_try:
        try:
            response = client.table(table).select("*").limit(1).execute()
            if response.data:
                schema[table] = list(response.data[0].keys())
            else:
                schema[table] = ["(empty table)"]
        except Exception:
            continue  # Table doesn't exist

    return schema
