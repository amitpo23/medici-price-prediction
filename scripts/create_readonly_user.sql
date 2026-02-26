-- =============================================================
-- Create read-only SQL user for Medici Price Prediction System
-- Run this on the medici-db Azure SQL Database
-- =============================================================

-- Step 1: Create the login on the MASTER database
-- Connect to the MASTER database first and run:
/*
CREATE LOGIN prediction_reader WITH PASSWORD = '<CHANGE-THIS-TO-A-STRONG-PASSWORD>';
*/

-- Step 2: Switch to the medici-db database and run the rest:

-- Create user mapped to the login
CREATE USER prediction_reader FOR LOGIN prediction_reader;

-- Grant read-only access to the database
ALTER ROLE db_datareader ADD MEMBER prediction_reader;

-- Grant SELECT on all tables the prediction system reads
-- (explicit grants for clarity and auditing)
GRANT SELECT ON dbo.MED_Book TO prediction_reader;
GRANT SELECT ON dbo.Med_Hotels TO prediction_reader;
GRANT SELECT ON dbo.MED_Opportunities TO prediction_reader;
GRANT SELECT ON dbo.BackOfficeOPT TO prediction_reader;
GRANT SELECT ON dbo.Med_Reservation TO prediction_reader;
GRANT SELECT ON dbo.MED_Board TO prediction_reader;
GRANT SELECT ON dbo.MED_RoomCategory TO prediction_reader;
GRANT SELECT ON dbo.Med_Source TO prediction_reader;
GRANT SELECT ON dbo.Med_Hotels_ratebycat TO prediction_reader;
GRANT SELECT ON dbo.tprice TO prediction_reader;

-- Explicitly DENY any write operations (defense in depth)
DENY INSERT, UPDATE, DELETE, ALTER, CREATE TABLE, DROP TABLE TO prediction_reader;

-- Verify: list permissions for the user
SELECT
    dp.name AS UserName,
    dp.type_desc AS UserType,
    p.permission_name,
    p.state_desc,
    OBJECT_NAME(p.major_id) AS ObjectName
FROM sys.database_permissions p
JOIN sys.database_principals dp ON p.grantee_principal_id = dp.principal_id
WHERE dp.name = 'prediction_reader'
ORDER BY p.permission_name;
