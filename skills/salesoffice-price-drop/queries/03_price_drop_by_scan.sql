WITH events AS (
    SELECT
        x.DateCreated,
        x.HotelId,
        x.RoomCategory,
        x.RoomBoard,
        x.OldPrice,
        x.NewPrice,
        CAST(x.OldPrice - x.NewPrice AS decimal(18,4)) AS DropAmount,
        CASE WHEN x.NewPrice < x.OldPrice THEN 1 ELSE 0 END AS IsPriceDrop
    FROM (
        SELECT
            l.DateCreated,
            d.HotelId,
            d.RoomCategory,
            d.RoomBoard,
            TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(SUBSTRING(
                l.Message,
                CHARINDEX('DbRoomPrice:', l.Message) + LEN('DbRoomPrice:'),
                CHARINDEX('-> API RoomPrice:', l.Message) - (CHARINDEX('DbRoomPrice:', l.Message) + LEN('DbRoomPrice:'))
            ))), '$', ''), ',', '.'), ' ', '')) AS OldPrice,
            TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(SUBSTRING(
                l.Message,
                CHARINDEX('-> API RoomPrice:', l.Message) + LEN('-> API RoomPrice:'),
                CASE
                    WHEN CHARINDEX('; DbRoomCode:', l.Message) > 0 THEN CHARINDEX('; DbRoomCode:', l.Message) - (CHARINDEX('-> API RoomPrice:', l.Message) + LEN('-> API RoomPrice:'))
                    ELSE LEN(l.Message)
                END
            ))), '$', ''), ',', '.'), ' ', '')) AS NewPrice
        FROM [SalesOffice.Log] l
        LEFT JOIN [SalesOffice.Details] d ON d.Id = l.SalesOfficeDetailId
        WHERE l.ActionId IN (3, 6)
          AND l.Message LIKE '%DbRoomPrice:%-> API RoomPrice:%'
    ) x
    WHERE x.OldPrice IS NOT NULL
      AND x.NewPrice IS NOT NULL
)
SELECT
    DATEADD(MINUTE, (DATEDIFF(MINUTE, '20000101', DateCreated) / 10) * 10, '20000101') AS ScanWindow,
    COUNT(*) AS TotalPriceChanges,
    SUM(CASE WHEN IsPriceDrop = 1 THEN 1 ELSE 0 END) AS DownwardChanges,
    CAST(100.0 * SUM(CASE WHEN IsPriceDrop = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS decimal(10,2)) AS DownwardRatePct,
    MIN(CASE WHEN IsPriceDrop = 1 THEN NewPrice END) AS LowestNewPriceInWindow,
    MAX(CASE WHEN IsPriceDrop = 1 THEN DropAmount END) AS MaxDropInWindow
FROM events
GROUP BY DATEADD(MINUTE, (DATEDIFF(MINUTE, '20000101', DateCreated) / 10) * 10, '20000101')
ORDER BY ScanWindow DESC;

