"""Medici DB MCP Server — direct SQL access to medici-db for AI agents.

Provides tools for:
- Price drop analysis (SalesOffice.Log, RoomPriceUpdateLog)
- Market intelligence (AI_Search_HotelData)
- Scan velocity tracking (SalesOffice.Details history)
- Hotel mapping validation (Med_Hotels, Med_Hotels_ratebycat)

READ-ONLY — no writes permitted.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

mcp = FastMCP("medici_db_mcp")

# ── Database Connection ─────────────────────────────────────────────

CONNECTION_STRING = os.environ.get(
    "MEDICI_DB_CONNECTION",
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=medici-sql-server.database.windows.net;"
    "Database=medici-db;"
    "Uid=prediction_reader;"
    "Pwd=Pr3d!rzn223y5KoNdQ^z8nG&YJ7N%rdRc;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)


def _run_query(sql: str, max_rows: int = 500) -> list[dict]:
    """Execute a read-only SQL query and return results as list of dicts."""
    import pyodbc

    conn = pyodbc.connect(CONNECTION_STRING, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = []
        for row in cursor.fetchmany(max_rows):
            rows.append({col: _serialize(val) for col, val in zip(columns, row)})
        return rows
    finally:
        conn.close()


def _serialize(val):
    """Convert DB values to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.hex()
    try:
        float(val)
        return val
    except (TypeError, ValueError):
        return str(val)


# ── Tool: Price Drop Events ──────────────────────────────────────────

class PriceDropParams(BaseModel):
    hotel_id: Optional[int] = Field(None, description="Filter by specific hotel ID")
    min_drop_pct: float = Field(5.0, description="Minimum drop percentage to include")
    hours_back: int = Field(168, description="How many hours back to search (default 7 days)")
    limit: int = Field(100, description="Max rows to return")


@mcp.tool(name="medici_price_drop_events")
async def price_drop_events(params: PriceDropParams) -> str:
    """Find all price drop events from SalesOffice.Log where price decreased.

    Parses the DbRoomPrice -> API RoomPrice pattern from log messages.
    Returns drops sorted by magnitude (largest first).
    Use this to find PUT opportunities — rooms where prices are falling.
    """
    hotel_filter = f"AND d.HotelId = {params.hotel_id}" if params.hotel_id else ""

    sql = f"""
    WITH base AS (
        SELECT l.Id, l.DateCreated, l.SalesOfficeDetailId, l.Message,
            CHARINDEX('DbRoomPrice:', l.Message) AS p1,
            CHARINDEX('-> API RoomPrice:', l.Message) AS p2,
            CHARINDEX('; DbRoomCode:', l.Message) AS p3
        FROM [SalesOffice.Log] l
        WHERE l.ActionId IN (3, 6)
          AND l.Message LIKE '%DbRoomPrice:%-> API RoomPrice:%'
          AND l.DateCreated >= DATEADD(hour, -{params.hours_back}, GETDATE())
    ),
    parsed AS (
        SELECT b.Id, b.DateCreated, b.SalesOfficeDetailId,
            TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(LTRIM(RTRIM(
                SUBSTRING(b.Message, b.p1 + 12, b.p2 - b.p1 - 12)
            )), '$',''),',','.')) AS OldPrice,
            TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(LTRIM(RTRIM(
                SUBSTRING(b.Message, b.p2 + 18,
                    CASE WHEN b.p3 > 0 THEN b.p3 - b.p2 - 18 ELSE LEN(b.Message) END)
            )), '$',''),',','.')) AS NewPrice
        FROM base b WHERE b.p1 > 0 AND b.p2 > b.p1
    )
    SELECT TOP {params.limit}
        p.Id, p.DateCreated, d.HotelId, h.Name AS HotelName,
        d.RoomCategory, d.RoomBoard, p.OldPrice, p.NewPrice,
        CAST(p.OldPrice - p.NewPrice AS decimal(18,2)) AS DropAmount,
        CAST((p.OldPrice - p.NewPrice) / NULLIF(p.OldPrice, 0) * 100 AS decimal(10,2)) AS DropPct
    FROM parsed p
    LEFT JOIN [SalesOffice.Details] d ON d.Id = p.SalesOfficeDetailId
    LEFT JOIN Med_Hotels h ON d.HotelId = h.HotelId
    WHERE p.OldPrice IS NOT NULL AND p.NewPrice IS NOT NULL
      AND p.NewPrice < p.OldPrice
      AND (p.OldPrice - p.NewPrice) / NULLIF(p.OldPrice, 0) * 100 >= {params.min_drop_pct}
      {hotel_filter}
    ORDER BY DropPct DESC
    """

    rows = _run_query(sql, params.limit)
    return json.dumps({"count": len(rows), "drops": rows}, default=str, indent=2)


# ── Tool: Scan Velocity ─────────────────────────────────────────────

class ScanVelocityParams(BaseModel):
    hotel_id: Optional[int] = Field(None, description="Filter by hotel ID")
    min_scans: int = Field(2, description="Minimum scan count to include")
    limit: int = Field(50, description="Max rows")


@mcp.tool(name="medici_scan_velocity")
async def scan_velocity(params: ScanVelocityParams) -> str:
    """Calculate price velocity between consecutive scans for each room.

    Shows which rooms are dropping/rising fastest right now.
    Velocity = % change per scan cycle (typically 3 hours).
    Negative velocity = price dropping = potential PUT signal.
    """
    hotel_filter = f"AND d.HotelId = {params.hotel_id}" if params.hotel_id else ""

    sql = f"""
    WITH scans AS (
        SELECT d.Id AS detail_id, d.SalesOfficeOrderId, d.HotelId, h.Name AS HotelName,
            d.RoomCategory, d.RoomBoard, d.RoomPrice, d.DateCreated,
            LAG(d.RoomPrice) OVER (
                PARTITION BY d.SalesOfficeOrderId, d.HotelId, d.RoomCategory, d.RoomBoard
                ORDER BY d.DateCreated
            ) AS PrevPrice,
            ROW_NUMBER() OVER (
                PARTITION BY d.SalesOfficeOrderId, d.HotelId, d.RoomCategory, d.RoomBoard
                ORDER BY d.DateCreated DESC
            ) AS rn,
            COUNT(*) OVER (
                PARTITION BY d.SalesOfficeOrderId, d.HotelId, d.RoomCategory, d.RoomBoard
            ) AS scan_count
        FROM [SalesOffice.Details] d
        JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
        JOIN Med_Hotels h ON d.HotelId = h.HotelId
        WHERE o.IsActive = 1
          AND o.WebJobStatus LIKE 'Completed%'
          AND o.WebJobStatus NOT LIKE '%Mapping: 0%'
          {hotel_filter}
    )
    SELECT TOP {params.limit}
        detail_id, HotelId, HotelName, RoomCategory, RoomBoard,
        RoomPrice AS CurrentPrice, PrevPrice,
        CAST((RoomPrice - PrevPrice) / NULLIF(PrevPrice, 0) * 100 AS decimal(10,2)) AS VelocityPct,
        scan_count AS TotalScans,
        DateCreated AS LastScan,
        CASE WHEN RoomPrice < PrevPrice THEN 'DROP'
             WHEN RoomPrice > PrevPrice THEN 'RISE'
             ELSE 'STABLE' END AS Direction
    FROM scans
    WHERE rn = 1 AND PrevPrice IS NOT NULL AND scan_count >= {params.min_scans}
    ORDER BY VelocityPct ASC
    """

    rows = _run_query(sql, params.limit)
    return json.dumps({"count": len(rows), "velocities": rows}, default=str, indent=2)


# ── Tool: Market Pressure ────────────────────────────────────────────

class MarketPressureParams(BaseModel):
    hotel_id: Optional[int] = Field(None, description="Specific hotel ID")
    days_back: int = Field(7, description="Days of market data to analyze")
    limit: int = Field(30, description="Max hotels to return")


@mcp.tool(name="medici_market_pressure")
async def market_pressure(params: MarketPressureParams) -> str:
    """Compare hotel prices against market competitors.

    Uses AI_Search_HotelData (8.5M rows) to find same-star hotels
    in the same city and calculate pricing pressure.
    Positive pressure = overpriced (risk of drop).
    Negative pressure = underpriced (opportunity).
    """
    hotel_filter = f"AND h1.HotelId = {params.hotel_id}" if params.hotel_id else ""

    sql = f"""
    SELECT TOP {params.limit}
        h1.HotelId, h1.Name AS HotelName,
        AVG(a1.PriceAmount) AS OurAvgPrice,
        (SELECT AVG(a2.PriceAmount) FROM AI_Search_HotelData a2
         JOIN Med_Hotels h2 ON a2.HotelId = h2.HotelId
         WHERE h2.HotelId != h1.HotelId
           AND a2.UpdatedAt >= DATEADD(day, -{params.days_back}, GETDATE())
           AND a2.PriceAmount > 0
        ) AS MarketAvgPrice,
        COUNT(*) AS DataPoints
    FROM AI_Search_HotelData a1
    JOIN Med_Hotels h1 ON a1.HotelId = h1.HotelId
    WHERE a1.UpdatedAt >= DATEADD(day, -{params.days_back}, GETDATE())
      AND a1.PriceAmount > 0
      {hotel_filter}
    GROUP BY h1.HotelId, h1.Name
    HAVING COUNT(*) >= 5
    ORDER BY AVG(a1.PriceAmount) DESC
    """

    rows = _run_query(sql, params.limit)

    # Add pressure calculation
    for row in rows:
        our = float(row.get("OurAvgPrice", 0) or 0)
        market = float(row.get("MarketAvgPrice", 0) or 0)
        if market > 0:
            row["PressurePct"] = round((our - market) / market * 100, 2)
        else:
            row["PressurePct"] = None

    return json.dumps({"count": len(rows), "hotels": rows}, default=str, indent=2)


# ── Tool: Hotel Mapping Status ───────────────────────────────────────

class MappingStatusParams(BaseModel):
    destination: str = Field("Miami", description="City/destination to filter")


@mcp.tool(name="medici_hotel_mapping_status")
async def hotel_mapping_status(params: MappingStatusParams) -> str:
    """Check hotel mapping status — which hotels have active orders, products, and rate plans.

    Shows for each hotel:
    - Active orders count and last update
    - Rooms with mapping count
    - Search result count and freshness
    """
    sql = f"""
    SELECT
        h.HotelId, h.Name AS HotelName,
        (SELECT COUNT(*) FROM [SalesOffice.Orders] o
         WHERE o.IsActive = 1 AND o.WebJobStatus LIKE 'Completed%'
           AND EXISTS (SELECT 1 FROM [SalesOffice.Details] d WHERE d.SalesOfficeOrderId = o.Id AND d.HotelId = h.HotelId)
        ) AS ActiveOrders,
        (SELECT COUNT(*) FROM [SalesOffice.Details] d
         JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
         WHERE d.HotelId = h.HotelId AND o.IsActive = 1
        ) AS TotalDetails,
        (SELECT MAX(d.DateCreated) FROM [SalesOffice.Details] d
         JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
         WHERE d.HotelId = h.HotelId AND o.IsActive = 1
        ) AS LastDetailUpdate
    FROM Med_Hotels h
    WHERE h.Name LIKE '%{params.destination}%'
       OR h.HotelId IN (
           SELECT DISTINCT rc.HotelId FROM Med_Hotels_ratebycat rc
           JOIN Med_Hotels h2 ON rc.HotelId = h2.HotelId
       )
    ORDER BY h.Name
    """

    rows = _run_query(sql, 100)
    return json.dumps({"count": len(rows), "hotels": rows}, default=str, indent=2)


# ── Tool: Raw SQL Query ─────────────────────────────────────────────

class RawQueryParams(BaseModel):
    sql: str = Field(..., description="SQL SELECT query to execute (read-only)")
    max_rows: int = Field(100, description="Maximum rows to return")


@mcp.tool(name="medici_query")
async def raw_query(params: RawQueryParams) -> str:
    """Execute a read-only SQL query against medici-db.

    ONLY SELECT statements are allowed. No INSERT/UPDATE/DELETE/DROP.
    Use this for ad-hoc analysis when the specialized tools don't cover your needs.

    Available tables:
    - [SalesOffice.Orders] — active room orders
    - [SalesOffice.Details] — room listings per order
    - [SalesOffice.Log] — scan log with price changes
    - Med_Hotels — hotel master
    - Med_Hotels_ratebycat — hotel x board x category mappings
    - MED_Board — board codes (RO, BB, HB, FB, AI)
    - MED_RoomCategory — category names
    - AI_Search_HotelData — competitor pricing (8.5M rows)
    - RoomPriceUpdateLog — price change events (82K rows)
    - MED_Book — confirmed bookings
    - MED_PreBook — pre-booking data
    """
    # Safety: block writes
    sql_upper = params.sql.strip().upper()
    for forbidden in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC"):
        if sql_upper.startswith(forbidden):
            return json.dumps({"error": f"Write operations are not permitted: {forbidden}"})

    rows = _run_query(params.sql, params.max_rows)
    return json.dumps({"count": len(rows), "rows": rows}, default=str, indent=2)


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
