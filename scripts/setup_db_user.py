"""Create read-only SQL user for prediction system on Azure SQL.

Run with: python scripts/setup_db_user.py
Requires: Azure CLI logged in, pyodbc installed, ODBC Driver 17.
"""
import os
import struct
import subprocess
import secrets
import string

import pyodbc

SERVER = "medici-sql-server.database.windows.net"
DATABASE = "medici-db"
USER_HOME = os.path.expanduser("~")
TOKEN_PATH = os.path.join(USER_HOME, "azure_sql_token.txt")
PWD_PATH = os.path.join(USER_HOME, "prediction_reader_pwd.txt")

SQL_COPT_SS_ACCESS_TOKEN = 1256

TABLES_TO_GRANT = [
    "MED_Book",
    "Med_Hotels",
    "MED_Opportunities",
    "BackOfficeOPT",
    "Med_Reservation",
    "MED_Board",
    "MED_RoomCategory",
    "Med_Source",
    "Med_Hotels_ratebycat",
    "tprice",
]


def get_azure_token():
    """Get Azure AD access token for SQL via az CLI."""
    result = subprocess.run(
        ["az", "account", "get-access-token",
         "--resource", "https://database.windows.net/",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True,
    )
    if result.returncode != 0:
        # Try reading from file
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "r") as f:
                return f.read().strip()
        raise RuntimeError(f"az CLI failed: {result.stderr}")
    return result.stdout.strip()


def encode_token(token: str) -> bytes:
    """Encode token for ODBC connection."""
    token_bytes = token.encode("UTF-16-LE")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def connect(database: str, token_struct: bytes):
    """Connect to Azure SQL with Azure AD token."""
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE={database};"
    )
    conn = pyodbc.connect(
        conn_str,
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
    )
    conn.autocommit = True
    return conn


def generate_password() -> str:
    """Generate a strong password meeting Azure SQL requirements."""
    chars = string.ascii_letters + string.digits + "!@#%^&*"
    return "Pr3d!" + "".join(secrets.choice(chars) for _ in range(28))


def main():
    # 1. Get token
    print("Getting Azure AD token...")
    token = get_azure_token()
    token_struct = encode_token(token)
    print(f"  Token: {len(token)} chars")

    # 2. Connect to MASTER and create login
    print("\nConnecting to MASTER...")
    conn = connect("master", token_struct)
    cursor = conn.cursor()
    print("  Connected")

    cursor.execute(
        "SELECT name FROM sys.sql_logins WHERE name = 'prediction_reader'"
    )
    existing = cursor.fetchone()

    password = None
    if existing:
        print("  Login 'prediction_reader' already exists — skipping CREATE LOGIN")
        if os.path.exists(PWD_PATH):
            with open(PWD_PATH, "r") as f:
                password = f.read().strip()
            print(f"  Password loaded from {PWD_PATH}")
        else:
            print("  WARNING: No saved password found. You may need to reset it.")
    else:
        password = generate_password()
        cursor.execute(
            f"CREATE LOGIN prediction_reader WITH PASSWORD = '{password}'"
        )
        with open(PWD_PATH, "w") as f:
            f.write(password)
        print(f"  Login created: prediction_reader")
        print(f"  Password saved to {PWD_PATH}")

    cursor.close()
    conn.close()

    # 3. Connect to medici-db and create user + permissions
    print(f"\nConnecting to {DATABASE}...")
    conn = connect(DATABASE, token_struct)
    cursor = conn.cursor()
    print("  Connected")

    # Check if user exists
    cursor.execute(
        "SELECT name FROM sys.database_principals WHERE name = 'prediction_reader'"
    )
    user_exists = cursor.fetchone()

    if user_exists:
        print("  User 'prediction_reader' already exists — skipping CREATE USER")
    else:
        cursor.execute(
            "CREATE USER prediction_reader FOR LOGIN prediction_reader"
        )
        print("  User created: prediction_reader")

    # Grant db_datareader role
    try:
        cursor.execute(
            "ALTER ROLE db_datareader ADD MEMBER prediction_reader"
        )
        print("  Added to db_datareader role")
    except pyodbc.Error as e:
        if "already a member" in str(e).lower() or "15410" in str(e):
            print("  Already in db_datareader role")
        else:
            raise

    # Grant SELECT on specific tables
    for table in TABLES_TO_GRANT:
        try:
            cursor.execute(
                f"GRANT SELECT ON dbo.[{table}] TO prediction_reader"
            )
            print(f"  GRANT SELECT on {table}")
        except pyodbc.Error as e:
            print(f"  GRANT SELECT on {table} — {e}")

    # Deny write operations
    cursor.execute(
        "DENY INSERT, UPDATE, DELETE, ALTER, CREATE TABLE, DROP TABLE "
        "TO prediction_reader"
    )
    print("  DENY write operations applied")

    # Verify
    print("\n  Verifying permissions...")
    cursor.execute("""
        SELECT
            p.permission_name,
            p.state_desc,
            OBJECT_NAME(p.major_id) AS object_name
        FROM sys.database_permissions p
        JOIN sys.database_principals dp
            ON p.grantee_principal_id = dp.principal_id
        WHERE dp.name = 'prediction_reader'
        ORDER BY p.state_desc, p.permission_name
    """)
    for row in cursor.fetchall():
        print(f"    {row.state_desc:8s} {row.permission_name:20s} {row.object_name or '(database)'}")

    cursor.close()
    conn.close()

    # 4. Build connection string
    if password:
        from urllib.parse import quote_plus
        conn_string = (
            f"mssql+pyodbc://prediction_reader:{quote_plus(password)}"
            f"@{SERVER}/{DATABASE}"
            f"?driver=ODBC+Driver+17+for+SQL+Server"
            f"&Encrypt=yes&TrustServerCertificate=no"
        )
        print(f"\n{'='*60}")
        print("CONNECTION STRING (add to .env as MEDICI_DB_URL):")
        print(f"{'='*60}")
        print(conn_string)

        # Save to a file for convenience
        conn_str_path = os.path.join(USER_HOME, "prediction_conn_string.txt")
        with open(conn_str_path, "w") as f:
            f.write(conn_string)
        print(f"\nAlso saved to {conn_str_path}")
    else:
        print("\nNo password available — cannot build connection string.")
        print("Reset the password or check the saved password file.")

    print("\nDone!")


if __name__ == "__main__":
    main()
