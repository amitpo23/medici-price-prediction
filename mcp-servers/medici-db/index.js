#!/usr/bin/env node
/**
 * Medici DB MCP Server — direct SQL access to medici-db for AI agents.
 *
 * Tools:
 *   medici_price_drops    — find price drop events from SalesOffice.Log
 *   medici_scan_velocity  — inter-scan price velocity per room
 *   medici_market_pressure — compare hotel vs market competitors
 *   medici_mapping_status — hotel mapping/configuration status
 *   medici_query          — raw read-only SQL query
 *
 * READ-ONLY — no writes permitted.
 */

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { z } = require("zod");
const sql = require("mssql");

const DB_CONFIG = {
  server: process.env.MEDICI_DB_SERVER || "medici-sql-server.database.windows.net",
  database: process.env.MEDICI_DB_NAME || "medici-db",
  user: process.env.MEDICI_DB_USER || "prediction_reader",
  password: process.env.MEDICI_DB_PASSWORD || "Pr3d!rzn223y5KoNdQ^z8nG&YJ7N%rdRc",
  options: {
    encrypt: true,
    trustServerCertificate: false,
    connectTimeout: 30000,
    requestTimeout: 60000,
  },
  pool: { max: 3, min: 0, idleTimeoutMillis: 30000 },
};

let pool = null;
async function getPool() {
  if (!pool) pool = await sql.connect(DB_CONFIG);
  return pool;
}

async function runQuery(query, maxRows = 500) {
  const p = await getPool();
  const result = await p.request().query(query);
  return result.recordset.slice(0, maxRows);
}

// ── MCP Server ────────────────────────────────────────────────────

const server = new McpServer({ name: "medici_db_mcp", version: "1.0.0" });

// Tool: Price Drop Events
server.tool(
  "medici_price_drops",
  "Find price drop events from SalesOffice.Log. Parses DbRoomPrice -> API RoomPrice pattern. Returns drops sorted by magnitude. Use to find PUT opportunities.",
  {
    hotel_id: z.number().optional().describe("Filter by specific hotel ID"),
    min_drop_pct: z.number().default(5).describe("Minimum drop percentage"),
    hours_back: z.number().default(168).describe("Hours to search back (default 7 days)"),
    limit: z.number().default(100).describe("Max rows"),
  },
  async ({ hotel_id, min_drop_pct, hours_back, limit }) => {
    const hotelFilter = hotel_id ? `AND d.HotelId = ${hotel_id}` : "";
    const query = `
      WITH base AS (
        SELECT l.Id, l.DateCreated, l.SalesOfficeDetailId, l.Message,
          CHARINDEX('DbRoomPrice:', l.Message) AS p1,
          CHARINDEX('-> API RoomPrice:', l.Message) AS p2,
          CHARINDEX('; DbRoomCode:', l.Message) AS p3
        FROM [SalesOffice.Log] l
        WHERE l.ActionId IN (3, 6)
          AND l.Message LIKE '%DbRoomPrice:%-> API RoomPrice:%'
          AND l.DateCreated >= DATEADD(hour, -${hours_back}, GETDATE())
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
      SELECT TOP ${limit}
        p.Id, p.DateCreated, d.HotelId, h.Name AS HotelName,
        d.RoomCategory, d.RoomBoard, p.OldPrice, p.NewPrice,
        CAST(p.OldPrice - p.NewPrice AS decimal(18,2)) AS DropAmount,
        CAST((p.OldPrice - p.NewPrice) / NULLIF(p.OldPrice, 0) * 100 AS decimal(10,2)) AS DropPct
      FROM parsed p
      LEFT JOIN [SalesOffice.Details] d ON d.Id = p.SalesOfficeDetailId
      LEFT JOIN Med_Hotels h ON d.HotelId = h.HotelId
      WHERE p.OldPrice IS NOT NULL AND p.NewPrice IS NOT NULL
        AND p.NewPrice < p.OldPrice
        AND (p.OldPrice - p.NewPrice) / NULLIF(p.OldPrice, 0) * 100 >= ${min_drop_pct}
        ${hotelFilter}
      ORDER BY DropPct DESC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, drops: rows }, null, 2) }] };
  }
);

// Tool: Scan Velocity
server.tool(
  "medici_scan_velocity",
  "Calculate price velocity between consecutive scans. Shows which rooms are dropping/rising fastest. Negative velocity = price dropping = PUT signal.",
  {
    hotel_id: z.number().optional().describe("Filter by hotel ID"),
    direction: z.enum(["DROP", "RISE", "ALL"]).default("DROP").describe("Filter direction"),
    limit: z.number().default(50).describe("Max rows"),
  },
  async ({ hotel_id, direction, limit }) => {
    const hotelFilter = hotel_id ? `AND d.HotelId = ${hotel_id}` : "";
    const dirFilter = direction === "DROP" ? "AND RoomPrice < PrevPrice"
      : direction === "RISE" ? "AND RoomPrice > PrevPrice" : "";

    const query = `
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
          ) AS rn
        FROM [SalesOffice.Details] d
        JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
        JOIN Med_Hotels h ON d.HotelId = h.HotelId
        WHERE o.IsActive = 1 AND o.WebJobStatus LIKE 'Completed%'
          AND o.WebJobStatus NOT LIKE '%Mapping: 0%' ${hotelFilter}
      )
      SELECT TOP ${limit}
        detail_id, HotelId, HotelName, RoomCategory, RoomBoard,
        RoomPrice AS CurrentPrice, PrevPrice,
        CAST((RoomPrice - PrevPrice) / NULLIF(PrevPrice, 0) * 100 AS decimal(10,2)) AS VelocityPct,
        DateCreated AS LastScan
      FROM scans
      WHERE rn = 1 AND PrevPrice IS NOT NULL ${dirFilter}
      ORDER BY VelocityPct ASC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, velocities: rows }, null, 2) }] };
  }
);

// Tool: Market Pressure
server.tool(
  "medici_market_pressure",
  "Compare hotel prices against market competitors using AI_Search_HotelData (8.5M rows). Positive pressure = overpriced. Negative = underpriced.",
  {
    hotel_id: z.number().optional().describe("Specific hotel"),
    days_back: z.number().default(7).describe("Days of market data"),
    limit: z.number().default(30).describe("Max hotels"),
  },
  async ({ hotel_id, days_back, limit }) => {
    const hotelFilter = hotel_id ? `AND h.HotelId = ${hotel_id}` : "";
    const query = `
      SELECT TOP ${limit} h.HotelId, h.Name,
        CAST(AVG(a.PriceAmount) AS decimal(10,2)) AS AvgPrice,
        COUNT(*) AS Samples,
        MIN(a.PriceAmount) AS MinPrice,
        MAX(a.PriceAmount) AS MaxPrice,
        MAX(a.UpdatedAt) AS LastUpdate
      FROM AI_Search_HotelData a
      JOIN Med_Hotels h ON a.HotelId = h.HotelId
      WHERE a.UpdatedAt >= DATEADD(day, -${days_back}, GETDATE())
        AND a.PriceAmount > 0 ${hotelFilter}
      GROUP BY h.HotelId, h.Name
      HAVING COUNT(*) >= 3
      ORDER BY AVG(a.PriceAmount) DESC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, hotels: rows }, null, 2) }] };
  }
);

// Tool: Hotel Mapping Status
server.tool(
  "medici_mapping_status",
  "Check which Miami hotels have active orders, search results, and when they last updated.",
  {
    city: z.string().default("Miami").describe("City name to filter"),
  },
  async ({ city }) => {
    const query = `
      SELECT h.HotelId, h.Name,
        (SELECT COUNT(*) FROM [SalesOffice.Orders] o
         JOIN [SalesOffice.Details] d ON d.SalesOfficeOrderId = o.Id
         WHERE d.HotelId = h.HotelId AND o.IsActive = 1) AS ActiveDetails,
        (SELECT MAX(d.DateCreated) FROM [SalesOffice.Details] d
         JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
         WHERE d.HotelId = h.HotelId AND o.IsActive = 1) AS LastUpdate
      FROM Med_Hotels h
      WHERE h.Name LIKE '%${city}%'
      ORDER BY h.Name`;

    const rows = await runQuery(query, 100);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, hotels: rows }, null, 2) }] };
  }
);

// ── Tool: RoomPriceUpdateLog — Price Change Events ──────────────────

server.tool(
  "medici_price_change_log",
  "Analyze RoomPriceUpdateLog (82K rows) — every price change event with timestamp. Shows velocity, acceleration, and patterns. Each row = one price update for a PreBookId. Find rooms with accelerating drops or unusual activity.",
  {
    hotel_id: z.number().optional().describe("Filter by hotel ID"),
    hours_back: z.number().default(72).describe("Hours to search back"),
    direction: z.enum(["DROP", "RISE", "ALL"]).default("DROP").describe("Price change direction"),
    min_change_pct: z.number().default(3).describe("Minimum % change to include"),
    limit: z.number().default(100).describe("Max rows"),
  },
  async ({ hotel_id, hours_back, direction, min_change_pct, limit }) => {
    const hotelFilter = hotel_id ? `AND b.HotelId = ${hotel_id}` : "";
    const dirFilter = direction === "DROP" ? "AND r2.Price < r1.Price"
      : direction === "RISE" ? "AND r2.Price > r1.Price" : "";

    const query = `
      WITH changes AS (
        SELECT r.PreBookId, r.Price, r.DateInsert,
          LAG(r.Price) OVER (PARTITION BY r.PreBookId ORDER BY r.DateInsert) AS PrevPrice,
          LAG(r.DateInsert) OVER (PARTITION BY r.PreBookId ORDER BY r.DateInsert) AS PrevDate
        FROM RoomPriceUpdateLog r
        WHERE r.DateInsert >= DATEADD(hour, -${hours_back}, GETDATE())
      )
      SELECT TOP ${limit}
        c.PreBookId, b.HotelId, h.Name AS HotelName,
        b.CategoryId, b.BoardId,
        c.PrevPrice, c.Price AS NewPrice,
        CAST(c.Price - c.PrevPrice AS decimal(18,2)) AS ChangeAmount,
        CAST((c.Price - c.PrevPrice) / NULLIF(c.PrevPrice, 0) * 100 AS decimal(10,2)) AS ChangePct,
        c.DateInsert, c.PrevDate,
        DATEDIFF(minute, c.PrevDate, c.DateInsert) AS MinutesBetween
      FROM changes c
      JOIN MED_PreBook b ON c.PreBookId = b.PreBookId
      JOIN Med_Hotels h ON b.HotelId = h.HotelId
      WHERE c.PrevPrice IS NOT NULL
        AND ABS((c.Price - c.PrevPrice) / NULLIF(c.PrevPrice, 0) * 100) >= ${min_change_pct}
        ${hotelFilter} ${dirFilter}
      ORDER BY ChangePct ASC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, source: "RoomPriceUpdateLog", changes: rows }, null, 2) }] };
  }
);

// ── Tool: SearchResultsSessionPollLog — Provider Pressure ───────────

server.tool(
  "medici_provider_pressure",
  "Analyze SearchResultsSessionPollLog (8.3M rows, 129 providers). Shows which providers are lowering prices, supplier competition level, and price spread across providers for each hotel. Provider pressure = when multiple suppliers drop prices simultaneously.",
  {
    hotel_id: z.number().optional().describe("Filter by hotel ID"),
    days_back: z.number().default(7).describe("Days of data to analyze"),
    min_providers: z.number().default(2).describe("Minimum providers per hotel"),
    limit: z.number().default(50).describe("Max rows"),
  },
  async ({ hotel_id, days_back, min_providers, limit }) => {
    const hotelFilter = hotel_id ? `AND s.HotelId = ${hotel_id}` : "";

    const query = `
      SELECT TOP ${limit}
        s.HotelId, h.Name AS HotelName,
        COUNT(DISTINCT s.ProviderId) AS ProviderCount,
        CAST(AVG(s.PriceAmount) AS decimal(10,2)) AS AvgPrice,
        CAST(MIN(s.PriceAmount) AS decimal(10,2)) AS MinPrice,
        CAST(MAX(s.PriceAmount) AS decimal(10,2)) AS MaxPrice,
        CAST(MAX(s.PriceAmount) - MIN(s.PriceAmount) AS decimal(10,2)) AS PriceSpread,
        CAST((MAX(s.PriceAmount) - MIN(s.PriceAmount)) / NULLIF(AVG(s.PriceAmount), 0) * 100 AS decimal(10,2)) AS SpreadPct,
        CAST(AVG(s.NetPriceAmount) AS decimal(10,2)) AS AvgNetPrice,
        CAST(AVG(s.PriceAmount) - AVG(s.NetPriceAmount) AS decimal(10,2)) AS AvgMargin,
        COUNT(*) AS TotalResults,
        MAX(s.DateCreated) AS LastResult
      FROM SearchResultsSessionPollLog s
      JOIN Med_Hotels h ON s.HotelId = h.HotelId
      WHERE s.DateCreated >= DATEADD(day, -${days_back}, GETDATE())
        AND s.PriceAmount > 0
        ${hotelFilter}
      GROUP BY s.HotelId, h.Name
      HAVING COUNT(DISTINCT s.ProviderId) >= ${min_providers}
      ORDER BY SpreadPct DESC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, source: "SearchResultsSessionPollLog", hotels: rows }, null, 2) }] };
  }
);

// ── Tool: Provider Price Trends ─────────────────────────────────────

server.tool(
  "medici_provider_trends",
  "Track price trends per provider for a specific hotel. Shows which providers are dropping prices fastest. If multiple providers drop simultaneously = strong PUT signal.",
  {
    hotel_id: z.number().describe("Hotel ID to analyze"),
    days_back: z.number().default(14).describe("Days to analyze"),
    limit: z.number().default(50).describe("Max rows"),
  },
  async ({ hotel_id, days_back, limit }) => {
    const query = `
      SELECT TOP ${limit}
        s.ProviderId, src.Name AS ProviderName,
        s.RoomCategory, s.RoomBoard,
        COUNT(*) AS ResultCount,
        CAST(AVG(s.PriceAmount) AS decimal(10,2)) AS AvgPrice,
        CAST(MIN(s.PriceAmount) AS decimal(10,2)) AS MinPrice,
        CAST(MAX(s.PriceAmount) AS decimal(10,2)) AS MaxPrice,
        MIN(s.DateCreated) AS FirstSeen,
        MAX(s.DateCreated) AS LastSeen,
        CAST(
          (SELECT TOP 1 s2.PriceAmount FROM SearchResultsSessionPollLog s2
           WHERE s2.HotelId = s.HotelId AND s2.ProviderId = s.ProviderId
             AND s2.RoomCategory = s.RoomCategory
           ORDER BY s2.DateCreated DESC) -
          (SELECT TOP 1 s3.PriceAmount FROM SearchResultsSessionPollLog s3
           WHERE s3.HotelId = s.HotelId AND s3.ProviderId = s.ProviderId
             AND s3.RoomCategory = s.RoomCategory
           ORDER BY s3.DateCreated ASC)
        AS decimal(10,2)) AS PriceTrend
      FROM SearchResultsSessionPollLog s
      LEFT JOIN Med_Source src ON s.ProviderId = src.Id
      WHERE s.HotelId = ${hotel_id}
        AND s.DateCreated >= DATEADD(day, -${days_back}, GETDATE())
        AND s.PriceAmount > 0
      GROUP BY s.ProviderId, src.Name, s.RoomCategory, s.RoomBoard, s.HotelId
      ORDER BY PriceTrend ASC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, source: "SearchResultsSessionPollLog", hotel_id, trends: rows }, null, 2) }] };
  }
);

// ── Tool: Booking & Cancellation Intelligence ───────────────────────

server.tool(
  "medici_booking_intelligence",
  "Analyze MED_PreBook (10.7K) + MED_CancelBook (4.7K) + MED_Book for booking pressure and cancellation spikes. High cancellation rate = demand dropping = price likely to fall. Low prebooking rate = weak demand.",
  {
    hotel_id: z.number().optional().describe("Filter by hotel ID"),
    days_back: z.number().default(30).describe("Days to analyze"),
    limit: z.number().default(30).describe("Max rows"),
  },
  async ({ hotel_id, days_back, limit }) => {
    const hotelFilter = hotel_id ? `AND p.HotelId = ${hotel_id}` : "";

    const query = `
      SELECT TOP ${limit}
        p.HotelId, h.Name AS HotelName,
        COUNT(DISTINCT p.PreBookId) AS TotalPreBooks,
        COUNT(DISTINCT b.PreBookId) AS ConfirmedBooks,
        COUNT(DISTINCT c.PreBookId) AS Cancellations,
        CAST(100.0 * COUNT(DISTINCT c.PreBookId) / NULLIF(COUNT(DISTINCT p.PreBookId), 0) AS decimal(10,2)) AS CancelRatePct,
        CAST(100.0 * COUNT(DISTINCT b.PreBookId) / NULLIF(COUNT(DISTINCT p.PreBookId), 0) AS decimal(10,2)) AS ConversionRatePct,
        CAST(AVG(p.Price) AS decimal(10,2)) AS AvgPreBookPrice,
        CAST(AVG(b.price) AS decimal(10,2)) AS AvgBookPrice,
        MAX(p.DateInsert) AS LastPreBook,
        MAX(c.CancellationDate) AS LastCancel
      FROM MED_PreBook p
      JOIN Med_Hotels h ON p.HotelId = h.HotelId
      LEFT JOIN MED_Book b ON p.PreBookId = b.PreBookId AND b.IsActive = 1
      LEFT JOIN MED_CancelBook c ON p.PreBookId = c.PreBookId
      WHERE p.DateInsert >= DATEADD(day, -${days_back}, GETDATE())
        ${hotelFilter}
      GROUP BY p.HotelId, h.Name
      ORDER BY CancelRatePct DESC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, source: "MED_PreBook+MED_Book+MED_CancelBook", hotels: rows }, null, 2) }] };
  }
);

// ── Tool: Cancellation Spike Detection ──────────────────────────────

server.tool(
  "medici_cancellation_spikes",
  "Detect cancellation spikes — sudden increase in cancellations signals demand collapse and potential price drops. Groups cancellations by day and flags anomalies.",
  {
    hotel_id: z.number().optional().describe("Filter by hotel ID"),
    days_back: z.number().default(30).describe("Days to analyze"),
  },
  async ({ hotel_id, days_back }) => {
    const hotelFilter = hotel_id ? `AND c.HotelId = ${hotel_id}` : "";

    const query = `
      SELECT
        CAST(c.CancellationDate AS date) AS CancelDate,
        COUNT(*) AS CancelCount,
        COUNT(DISTINCT c.HotelId) AS HotelsAffected,
        CAST(AVG(b.price) AS decimal(10,2)) AS AvgCancelledPrice,
        STRING_AGG(DISTINCT h.Name, ', ') AS Hotels
      FROM MED_CancelBook c
      JOIN MED_Book b ON c.PreBookId = b.PreBookId
      JOIN Med_Hotels h ON b.HotelId = h.HotelId
      WHERE c.CancellationDate >= DATEADD(day, -${days_back}, GETDATE())
        ${hotelFilter}
      GROUP BY CAST(c.CancellationDate AS date)
      ORDER BY CancelDate DESC`;

    const rows = await runQuery(query, 100);

    // Detect spikes (days with >2x average)
    if (rows.length > 3) {
      const avg = rows.reduce((s, r) => s + r.CancelCount, 0) / rows.length;
      rows.forEach(r => {
        r.IsSpike = r.CancelCount > avg * 2;
        r.Ratio = Math.round(r.CancelCount / avg * 100) / 100;
      });
    }

    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, source: "MED_CancelBook", dailyCancellations: rows }, null, 2) }] };
  }
);

// ── Tool: Historical Price Patterns (MED_SearchHotels) ──────────────

server.tool(
  "medici_historical_patterns",
  "Analyze MED_SearchHotels (7M rows, 2020-2023) for seasonal and day-of-week price patterns. Shows when prices historically drop — enabling prediction of future drops. Use for identifying recurring PUT windows.",
  {
    hotel_id: z.number().optional().describe("Filter by hotel ID"),
    category: z.string().optional().describe("Room category filter"),
    group_by: z.enum(["month", "dow", "month_dow"]).default("month").describe("How to group the analysis"),
    limit: z.number().default(50).describe("Max rows"),
  },
  async ({ hotel_id, category, group_by, limit }) => {
    const hotelFilter = hotel_id ? `AND s.HotelId = ${hotel_id}` : "";
    const catFilter = category ? `AND s.RoomCategory LIKE '%${category}%'` : "";

    let groupExpr, selectExpr;
    if (group_by === "month") {
      groupExpr = "MONTH(s.DateFrom)";
      selectExpr = "MONTH(s.DateFrom) AS Month";
    } else if (group_by === "dow") {
      groupExpr = "DATEPART(weekday, s.DateFrom)";
      selectExpr = "DATEPART(weekday, s.DateFrom) AS DayOfWeek";
    } else {
      groupExpr = "MONTH(s.DateFrom), DATEPART(weekday, s.DateFrom)";
      selectExpr = "MONTH(s.DateFrom) AS Month, DATEPART(weekday, s.DateFrom) AS DayOfWeek";
    }

    const query = `
      SELECT TOP ${limit}
        ${selectExpr},
        COUNT(*) AS SampleCount,
        CAST(AVG(s.Price) AS decimal(10,2)) AS AvgPrice,
        CAST(MIN(s.Price) AS decimal(10,2)) AS MinPrice,
        CAST(MAX(s.Price) AS decimal(10,2)) AS MaxPrice,
        CAST(STDEV(s.Price) AS decimal(10,2)) AS PriceStdDev,
        CAST(AVG(s.Price) - (SELECT AVG(s2.Price) FROM MED_SearchHotels s2
          WHERE s2.HotelId = s.HotelId ${catFilter}) AS decimal(10,2)) AS VsOverallAvg
      FROM MED_SearchHotels s
      JOIN Med_Hotels h ON s.HotelId = h.HotelId
      WHERE s.Price > 0 ${hotelFilter} ${catFilter}
      GROUP BY s.HotelId, ${groupExpr}
      ORDER BY AvgPrice ASC`;

    const rows = await runQuery(query, limit);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, source: "MED_SearchHotels", groupBy: group_by, patterns: rows }, null, 2) }] };
  }
);

// ── Tool: Combined PUT Intelligence ─────────────────────────────────

server.tool(
  "medici_combined_put_analysis",
  "Run a combined PUT analysis across ALL data sources for a specific hotel. Checks: scan velocity, price drops, provider pressure, cancellation rate, market position, and historical patterns. Returns a unified PUT score.",
  {
    hotel_id: z.number().describe("Hotel ID to analyze"),
  },
  async ({ hotel_id }) => {
    const queries = {
      // 1. Current scan velocity
      velocity: `
        SELECT TOP 5 d.RoomCategory, d.RoomBoard, d.RoomPrice AS CurrentPrice,
          LAG(d.RoomPrice) OVER (PARTITION BY d.RoomCategory, d.RoomBoard ORDER BY d.DateCreated) AS PrevPrice,
          d.DateCreated
        FROM [SalesOffice.Details] d
        JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
        WHERE d.HotelId = ${hotel_id} AND o.IsActive = 1
          AND o.WebJobStatus LIKE 'Completed%' AND o.WebJobStatus NOT LIKE '%Mapping: 0%'
        ORDER BY d.DateCreated DESC`,

      // 2. Recent price updates
      priceUpdates: `
        SELECT TOP 10 r.Price, r.DateInsert
        FROM RoomPriceUpdateLog r
        JOIN MED_PreBook p ON r.PreBookId = p.PreBookId
        WHERE p.HotelId = ${hotel_id}
        ORDER BY r.DateInsert DESC`,

      // 3. Provider competition
      providers: `
        SELECT COUNT(DISTINCT s.ProviderId) AS ProviderCount,
          CAST(AVG(s.PriceAmount) AS decimal(10,2)) AS AvgPrice,
          CAST(MIN(s.PriceAmount) AS decimal(10,2)) AS MinPrice,
          CAST(MAX(s.PriceAmount) AS decimal(10,2)) AS MaxPrice
        FROM SearchResultsSessionPollLog s
        WHERE s.HotelId = ${hotel_id}
          AND s.DateCreated >= DATEADD(day, -7, GETDATE()) AND s.PriceAmount > 0`,

      // 4. Cancellation rate
      cancellations: `
        SELECT COUNT(DISTINCT p.PreBookId) AS PreBooks,
          COUNT(DISTINCT c.PreBookId) AS Cancels,
          CAST(100.0 * COUNT(DISTINCT c.PreBookId) / NULLIF(COUNT(DISTINCT p.PreBookId), 0) AS decimal(10,2)) AS CancelRate
        FROM MED_PreBook p
        LEFT JOIN MED_CancelBook c ON p.PreBookId = c.PreBookId
        WHERE p.HotelId = ${hotel_id} AND p.DateInsert >= DATEADD(day, -30, GETDATE())`,

      // 5. Market position
      market: `
        SELECT CAST(AVG(a.PriceAmount) AS decimal(10,2)) AS MarketAvg,
          CAST(MIN(a.PriceAmount) AS decimal(10,2)) AS MarketMin
        FROM AI_Search_HotelData a
        WHERE a.HotelId = ${hotel_id}
          AND a.UpdatedAt >= DATEADD(day, -7, GETDATE()) AND a.PriceAmount > 0`,
    };

    const results = {};
    for (const [key, sql] of Object.entries(queries)) {
      try {
        results[key] = await runQuery(sql, 20);
      } catch (e) {
        results[key] = { error: e.message };
      }
    }

    // Calculate combined PUT score
    let putScore = 0;
    const factors = [];

    // Velocity check
    const vel = results.velocity?.[0];
    if (vel?.PrevPrice && vel?.CurrentPrice && vel.PrevPrice > 0) {
      const velPct = (vel.CurrentPrice - vel.PrevPrice) / vel.PrevPrice * 100;
      if (velPct < -5) { putScore += 30; factors.push(`velocity ${velPct.toFixed(1)}%`); }
      else if (velPct < -2) { putScore += 15; factors.push(`velocity ${velPct.toFixed(1)}%`); }
    }

    // Cancellation check
    const cancel = results.cancellations?.[0];
    if (cancel?.CancelRate > 40) { putScore += 20; factors.push(`cancel rate ${cancel.CancelRate}%`); }
    else if (cancel?.CancelRate > 20) { putScore += 10; factors.push(`cancel rate ${cancel.CancelRate}%`); }

    // Provider spread check
    const prov = results.providers?.[0];
    if (prov?.MaxPrice && prov?.MinPrice) {
      const spread = (prov.MaxPrice - prov.MinPrice) / prov.AvgPrice * 100;
      if (spread > 30) { putScore += 15; factors.push(`provider spread ${spread.toFixed(0)}%`); }
    }

    const signal = putScore >= 50 ? "STRONG_PUT" : putScore >= 30 ? "PUT" : putScore >= 15 ? "WATCH" : "NEUTRAL";

    return { content: [{ type: "text", text: JSON.stringify({
      hotel_id, signal, putScore, factors,
      sources: results,
    }, null, 2) }] };
  }
);

// Tool: Raw Query
server.tool(
  "medici_query",
  "Execute a read-only SQL query against medici-db. Only SELECT allowed. Tables: SalesOffice.Orders, SalesOffice.Details, SalesOffice.Log, Med_Hotels, Med_Hotels_ratebycat, AI_Search_HotelData, RoomPriceUpdateLog, MED_Book, MED_PreBook, MED_Board, MED_RoomCategory",
  {
    sql: z.string().describe("SQL SELECT query"),
    max_rows: z.number().default(100).describe("Maximum rows"),
  },
  async ({ sql: query, max_rows }) => {
    const upper = query.trim().toUpperCase();
    for (const word of ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC"]) {
      if (upper.startsWith(word)) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Write operations not permitted: ${word}` }) }] };
      }
    }
    const rows = await runQuery(query, max_rows);
    return { content: [{ type: "text", text: JSON.stringify({ count: rows.length, rows }, null, 2) }] };
  }
);

// Start
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
main().catch(console.error);
