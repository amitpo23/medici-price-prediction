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
        LTRIM(RTRIM(SUBSTRING(
            p.Message,
            p.p_old_start + LEN('DbRoomPrice:'),
            p.p_arrow - (p.p_old_start + LEN('DbRoomPrice:'))
        ))) AS OldPriceText,
        LTRIM(RTRIM(SUBSTRING(
            p.Message,
            p.p_arrow + LEN('-> API RoomPrice:'),
            CASE
                WHEN p.p_code > 0 THEN p.p_code - (p.p_arrow + LEN('-> API RoomPrice:'))
                WHEN p.p_first_semicolon_after_new > 0 THEN p.p_first_semicolon_after_new - (p.p_arrow + LEN('-> API RoomPrice:'))
                ELSE LEN(p.Message)
            END
        ))) AS NewPriceText,
        p.Message
    FROM positions p
    WHERE p.p_old_start > 0
      AND p.p_arrow > p.p_old_start
),
normalized AS (
    SELECT
        pa.*,
        TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(REPLACE(pa.OldPriceText, '$', ''), ',', '.'), ' ', '')) AS OldPrice,
        TRY_CONVERT(decimal(18,4), REPLACE(REPLACE(REPLACE(pa.NewPriceText, '$', ''), ',', '.'), ' ', '')) AS NewPrice
    FROM parsed pa
)
SELECT
    n.Id,
    n.DateCreated,
    n.ActionId,
    n.ActionResultId,
    n.SalesOfficeOrderId,
    n.SalesOfficeDetailId,
    d.HotelId,
    d.RoomCategory,
    d.RoomBoard,
    n.OldPrice,
    n.NewPrice,
    CAST(n.OldPrice - n.NewPrice AS decimal(18,4)) AS DropAmount,
    CASE WHEN n.NewPrice < n.OldPrice THEN 1 ELSE 0 END AS IsPriceDrop,
    n.Message
FROM normalized n
LEFT JOIN [SalesOffice.Details] d ON d.Id = n.SalesOfficeDetailId
WHERE n.OldPrice IS NOT NULL
  AND n.NewPrice IS NOT NULL
ORDER BY n.DateCreated DESC;

