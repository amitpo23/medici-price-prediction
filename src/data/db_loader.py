"""Load hotel pricing and booking data from Azure SQL Database."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from config.settings import DATABASE_URL


def get_engine():
    """Create and return a SQLAlchemy engine for Azure SQL."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set in .env file")
    return create_engine(DATABASE_URL)


def load_table(table_name: str, columns: str = "*", limit: int | None = None) -> pd.DataFrame:
    """Load a table from the database into a DataFrame.

    Args:
        table_name: Name of the table.
        columns: Comma-separated column names or '*' for all.
        limit: Maximum number of rows to fetch. None for all.
    """
    engine = get_engine()
    query = f"SELECT {columns} FROM {table_name}"
    if limit:
        query += f" ORDER BY 1 OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
    return pd.read_sql(text(query), engine)


def load_bookings(limit: int | None = None) -> pd.DataFrame:
    """Load booking data with relevant pricing fields."""
    df = load_table("bookings", limit=limit)
    if df.empty:
        return df

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
    Adjust the table name and columns to match your DB schema.
    """
    engine = get_engine()
    query = "SELECT * FROM daily_prices WHERE 1=1"

    params = {}
    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date"

    df = pd.read_sql(text(query), engine, params=params)

    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

    return df


def discover_schema() -> dict:
    """Discover all tables and their columns in the database.

    Returns a dict of {table_name: [columns]}.
    """
    engine = get_engine()
    inspector = inspect(engine)

    schema = {}
    for table_name in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        schema[table_name] = columns

    return schema


def run_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """Run a custom SQL query and return results as DataFrame."""
    engine = get_engine()
    return pd.read_sql(text(query), engine, params=params or {})
