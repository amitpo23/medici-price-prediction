-- Next-Scan Drop: Calculate inter-scan velocity for all active rooms
-- Groups consecutive scans per room and computes % change between each pair
-- Focuses on the LAST scan change (velocity_3h) and trend

WITH room_scans AS (
    SELECT
        d.Id AS detail_id,
        d.SalesOfficeOrderId AS order_id,
        d.HotelId AS hotel_id,
        h.Name AS hotel_name,
        d.RoomCategory AS category,
        d.RoomBoard AS board,
        d.RoomPrice AS price,
        d.DateCreated AS scan_date,
        ROW_NUMBER() OVER (
            PARTITION BY d.SalesOfficeOrderId, d.HotelId, d.RoomCategory, d.RoomBoard
            ORDER BY d.DateCreated DESC
        ) AS scan_rank
    FROM [SalesOffice.Details] d
    JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
    JOIN Med_Hotels h ON d.HotelId = h.HotelId
    WHERE o.IsActive = 1
      AND o.WebJobStatus LIKE 'Completed%'
      AND o.WebJobStatus NOT LIKE '%Mapping: 0%'
),
velocity AS (
    SELECT
        curr.detail_id,
        curr.hotel_id,
        curr.hotel_name,
        curr.category,
        curr.board,
        curr.price AS current_price,
        prev.price AS prev_price,
        curr.scan_date AS current_scan,
        prev.scan_date AS prev_scan,
        CASE WHEN prev.price > 0
             THEN CAST((curr.price - prev.price) / prev.price * 100 AS decimal(10,4))
             ELSE 0 END AS change_pct,
        CASE WHEN curr.price < prev.price THEN 1 ELSE 0 END AS is_drop,
        CASE WHEN prev.price > 0
             THEN CAST(prev.price - curr.price AS decimal(18,4))
             ELSE 0 END AS drop_amount
    FROM room_scans curr
    JOIN room_scans prev ON
        curr.order_id = prev.order_id
        AND curr.hotel_id = prev.hotel_id
        AND curr.category = prev.category
        AND curr.board = prev.board
        AND curr.scan_rank = prev.scan_rank - 1
    WHERE curr.scan_rank = 1  -- Most recent scan pair only
)
SELECT
    v.*,
    CASE
        WHEN v.change_pct <= -5.0 THEN 'STRONG_PUT'
        WHEN v.change_pct <= -2.0 THEN 'PUT'
        WHEN v.change_pct < 0 THEN 'WATCH'
        ELSE 'NEUTRAL'
    END AS next_scan_signal
FROM velocity v
WHERE v.is_drop = 1 OR v.change_pct <= -2.0
ORDER BY v.change_pct ASC;
