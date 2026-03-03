"""Quick script to query [SalesOffice.Orders] from medici-db."""
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load env from project .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MEDICI_DB_URL = os.getenv("MEDICI_DB_URL", "")
if not MEDICI_DB_URL:
    raise ValueError("MEDICI_DB_URL not set in .env")

engine = create_engine(MEDICI_DB_URL, echo=False)

with engine.connect() as conn:
    # Total count
    count_result = conn.execute(text("SELECT COUNT(*) AS total FROM [SalesOffice.Orders]"))
    total = count_result.scalar()
    print(f"Total records in [SalesOffice.Orders]: {total}")
    print("=" * 80)

    # Last 10 rows (most recent by some ordering - let's first get column names)
    cols_df = pd.read_sql(
        text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = 'SalesOffice.Orders' ORDER BY ORDINAL_POSITION"
        ),
        conn,
    )
    print(f"Columns ({len(cols_df)}):")
    for c in cols_df["COLUMN_NAME"]:
        print(f"  - {c}")
    print("=" * 80)

    # Sample: last 10 rows (order by Id DESC since that's the PK)
    sample_df = pd.read_sql(
        text("SELECT TOP 10 * FROM [SalesOffice.Orders] ORDER BY Id DESC"),
        conn,
    )
    print("Last 10 rows (ordered by OrderId DESC):")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 40)
    print(sample_df.to_string(index=False))

engine.dispose()
