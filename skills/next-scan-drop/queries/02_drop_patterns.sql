-- Next-Scan Drop: Historical drop patterns per room
-- Calculates drop frequency, streaks, and avg drop size
-- Used to predict likelihood of drop in next scan

WITH room_scans AS (
    SELECT
        d.SalesOfficeOrderId AS order_id,
        d.HotelId AS hotel_id,
        h.Name AS hotel_name,
        d.RoomCategory AS category,
        d.RoomBoard AS board,
        d.RoomPrice AS price,
        d.DateCreated AS scan_date,
        LAG(d.RoomPrice) OVER (
            PARTITION BY d.SalesOfficeOrderId, d.HotelId, d.RoomCategory, d.RoomBoard
            ORDER BY d.DateCreated
        ) AS prev_price
    FROM [SalesOffice.Details] d
    JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
    JOIN Med_Hotels h ON d.HotelId = h.HotelId
    WHERE o.IsActive = 1
      AND o.WebJobStatus LIKE 'Completed%'
      AND o.WebJobStatus NOT LIKE '%Mapping: 0%'
),
changes AS (
    SELECT
        rs.*,
        CASE WHEN prev_price IS NOT NULL AND prev_price > 0
             THEN CAST((price - prev_price) / prev_price * 100 AS decimal(10,4))
             ELSE NULL END AS change_pct,
        CASE WHEN price < prev_price THEN 1 ELSE 0 END AS is_drop
    FROM room_scans rs
    WHERE prev_price IS NOT NULL
)
SELECT
    hotel_id,
    hotel_name,
    category,
    board,
    COUNT(*) AS total_scan_pairs,
    SUM(is_drop) AS total_drops,
    CAST(100.0 * SUM(is_drop) / NULLIF(COUNT(*), 0) AS decimal(10,2)) AS drop_frequency_pct,
    MIN(CASE WHEN is_drop = 1 THEN change_pct END) AS max_drop_pct,
    AVG(CASE WHEN is_drop = 1 THEN change_pct END) AS avg_drop_pct,
    SUM(CASE WHEN change_pct <= -5.0 THEN 1 ELSE 0 END) AS drops_over_5pct,
    SUM(CASE WHEN change_pct <= -10.0 THEN 1 ELSE 0 END) AS drops_over_10pct,
    MIN(price) AS lowest_price_seen,
    MAX(scan_date) AS last_scan
FROM changes
GROUP BY hotel_id, hotel_name, category, board
HAVING SUM(is_drop) > 0
ORDER BY drop_frequency_pct DESC, total_drops DESC;
