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
  user: process.env.MEDICI_DB_USER || "prediction_readonly",
  password: process.env.MEDICI_DB_PASSWORD || "Medici2025!",
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
