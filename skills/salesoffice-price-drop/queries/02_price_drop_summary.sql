WITH base_logs AS (
    SELECT
        l.Id,
        l.DateCreated,
        l.ActionId,
        l.ActionResultId,
        l.Message,
        l.SalesOfficeOrderId,
        l.SalesOfficeDetailId
    FROM [SalesOffice.Log] l
    WHERE l.ActionId IN (3, 6)
      AND l.Message LIKE '%DbRoomPrice:%-> API RoomPrice:%'
),
positions AS (
    SELECT
        b.*,
        CHARINDEX('DbRoomPrice:', b.Message) AS p_old_start,
        CHARINDEX('-> API RoomPrice:', b.Message) AS p_arrow,
        CHARINDEX('; DbRoomCode:', b.Message) AS p_code,
        CHARINDEX(';', b.Message, CHARINDEX('-> API RoomPrice:', b.Message) + LEN('-> API RoomPrice:')) AS p_first_semicolon_after_new
    FROM base_logs b
),
parsed AS (
    SELECT
        p.Id,
        p.DateCreated,
        p.ActionId,
        p.ActionResultId,
        p.SalesOfficeOrderId,
        p.SalesOfficeDetailId,
        TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(SUBSTRING(
            p.Message,
            p.p_old_start + LEN('DbRoomPrice:'),
            p.p_arrow - (p.p_old_start + LEN('DbRoomPrice:'))
        ))), '$', ''), ',', '.'), ' ', '')) AS OldPrice,
        TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(SUBSTRING(
            p.Message,
            p.p_arrow + LEN('-> API RoomPrice:'),
            CASE
                WHEN p.p_code > 0 THEN p.p_code - (p.p_arrow + LEN('-> API RoomPrice:'))
                WHEN p.p_first_semicolon_after_new > 0 THEN p.p_first_semicolon_after_new - (p.p_arrow + LEN('-> API RoomPrice:'))
                ELSE LEN(p.Message)
            END
        ))), '$', ''), ',', '.'), ' ', '')) AS NewPrice
    FROM positions p
    WHERE p.p_old_start > 0
      AND p.p_arrow > p.p_old_start
),
events AS (
    SELECT
        p.*,
        d.HotelId,
        d.RoomCategory,
        d.RoomBoard,
        CAST(p.OldPrice - p.NewPrice AS decimal(18,4)) AS DropAmount,
        CASE WHEN p.NewPrice < p.OldPrice THEN 1 ELSE 0 END AS IsPriceDrop
    FROM parsed p
    LEFT JOIN [SalesOffice.Details] d ON d.Id = p.SalesOfficeDetailId
    WHERE p.OldPrice IS NOT NULL
      AND p.NewPrice IS NOT NULL
)
SELECT
    COUNT(*) AS TotalPriceChanges,
    SUM(CASE WHEN IsPriceDrop = 1 THEN 1 ELSE 0 END) AS DownwardChanges,
    CAST(100.0 * SUM(CASE WHEN IsPriceDrop = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS decimal(10,2)) AS DownwardRatePct,
    MIN(CASE WHEN IsPriceDrop = 1 THEN NewPrice END) AS LowestObservedPrice,
    MAX(CASE WHEN IsPriceDrop = 1 THEN DropAmount END) AS MaxDropAmount,
    AVG(CASE WHEN IsPriceDrop = 1 THEN DropAmount END) AS AvgDropAmount,
    COUNT(DISTINCT CASE WHEN IsPriceDrop = 1 THEN HotelId END) AS HotelsWithDrops
FROM events;

