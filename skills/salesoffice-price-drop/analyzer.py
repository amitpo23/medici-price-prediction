import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

try:
    import pyodbc
except Exception:
    pyodbc = None

PRICE_PATTERN = re.compile(
    r"DbRoomPrice:\s*(?P<old>[-+]?\d+(?:[\.,]\d+)?)\s*->\s*API\s*RoomPrice:\s*(?P<new>[-+]?\d+(?:[\.,]\d+)?)",
    re.IGNORECASE,
)

SQL_QUERY = """
SELECT
    l.Id,
    l.DateCreated,
    l.ActionId,
    l.ActionResultId,
    l.SalesOfficeOrderId,
    l.SalesOfficeDetailId,
    l.Message,
    d.HotelId,
    d.RoomCategory,
    d.RoomBoard
FROM [SalesOffice.Log] l
LEFT JOIN [SalesOffice.Details] d ON d.Id = l.SalesOfficeDetailId
WHERE l.ActionId IN (3, 6)
  AND l.Message LIKE '%DbRoomPrice:%-> API RoomPrice:%';
"""


@dataclass
class Config:
    input_csv: str | None
    connection_string: str | None
    scan_minutes: int
    out_dir: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="SalesOffice price-drop intelligence analyzer")
    parser.add_argument("--input-csv", help="Path to exported logs CSV")
    parser.add_argument("--connection-string", help="ODBC connection string to SQL Server")
    parser.add_argument("--scan-minutes", type=int, default=10, help="Scan window size in minutes")
    parser.add_argument("--out", default="report", help="Output directory")
    args = parser.parse_args()

    if not args.input_csv and not args.connection_string:
        raise SystemExit("Provide either --input-csv or --connection-string")
    if args.connection_string and pyodbc is None:
        raise SystemExit("pyodbc is required for --connection-string mode")

    return Config(
        input_csv=args.input_csv,
        connection_string=args.connection_string,
        scan_minutes=args.scan_minutes,
        out_dir=args.out,
    )


def load_data(cfg: Config) -> pd.DataFrame:
    if cfg.input_csv:
        return pd.read_csv(cfg.input_csv)

    conn = pyodbc.connect(cfg.connection_string)
    try:
        return pd.read_sql(SQL_QUERY, conn)
    finally:
        conn.close()


def to_float(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def enrich_price_fields(df: pd.DataFrame) -> pd.DataFrame:
    old_vals = []
    new_vals = []

    for msg in df.get("Message", pd.Series([], dtype=str)).fillna(""):
        match = PRICE_PATTERN.search(str(msg))
        if not match:
            old_vals.append(None)
            new_vals.append(None)
            continue
        old_vals.append(to_float(match.group("old")))
        new_vals.append(to_float(match.group("new")))

    df = df.copy()
    df["OldPrice"] = old_vals
    df["NewPrice"] = new_vals
    df = df.dropna(subset=["OldPrice", "NewPrice"])

    df["DropAmount"] = df["OldPrice"] - df["NewPrice"]
    df["IsPriceDrop"] = (df["DropAmount"] > 0).astype(int)

    if "DateCreated" in df.columns:
        df["DateCreated"] = pd.to_datetime(df["DateCreated"], errors="coerce")

    return df


def add_scan_windows(df: pd.DataFrame, scan_minutes: int) -> pd.DataFrame:
    df = df.copy()
    if "DateCreated" in df.columns:
        df["ScanWindow"] = df["DateCreated"].dt.floor(f"{scan_minutes}min")
    else:
        df["ScanWindow"] = pd.NaT
    return df


def safe_median(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.median())


def probability_next_drop(df_scan: pd.DataFrame) -> float:
    if df_scan.empty:
        return 0.0
    ordered = df_scan.sort_values("ScanWindow")
    if len(ordered) == 1:
        return float(ordered["DownwardRatePct"].iloc[-1] / 100.0)

    recent = ordered.tail(6)
    hist = ordered

    recent_p = recent["DownwardRatePct"].mean() / 100.0
    hist_p = hist["DownwardRatePct"].mean() / 100.0

    p = 0.7 * recent_p + 0.3 * hist_p
    return float(max(0.0, min(1.0, p)))


def build_reports(df: pd.DataFrame, scan_minutes: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    drop_events = df[df["IsPriceDrop"] == 1].copy()

    group_cols = [c for c in ["HotelId", "RoomCategory", "RoomBoard"] if c in drop_events.columns]
    if group_cols:
        by_hotel = (
            drop_events
            .groupby(group_cols, dropna=False)
            .agg(
                DropCount=("Id", "count"),
                AvgDropAmount=("DropAmount", "mean"),
                MaxDropAmount=("DropAmount", "max"),
                LowestObservedPrice=("NewPrice", "min"),
            )
            .reset_index()
            .sort_values(["DropCount", "MaxDropAmount"], ascending=[False, False])
        )
    else:
        by_hotel = pd.DataFrame(columns=["DropCount", "AvgDropAmount", "MaxDropAmount", "LowestObservedPrice"])

    by_scan = (
        df.groupby("ScanWindow", dropna=False)
        .agg(
            TotalPriceChanges=("Id", "count"),
            DownwardChanges=("IsPriceDrop", "sum"),
            LowestNewPriceInWindow=("NewPrice", "min"),
            MaxDropInWindow=("DropAmount", "max"),
        )
        .reset_index()
    )
    by_scan["DownwardRatePct"] = (100.0 * by_scan["DownwardChanges"] / by_scan["TotalPriceChanges"]).round(2)
    by_scan = by_scan.sort_values("ScanWindow", ascending=False)

    summary = {
        "generatedAtUtc": datetime.utcnow().isoformat() + "Z",
        "scanMinutes": scan_minutes,
        "totalPriceChanges": int(df.shape[0]),
        "downwardChanges": int(drop_events.shape[0]),
        "downwardRatePct": round(float((100.0 * drop_events.shape[0] / df.shape[0]) if df.shape[0] else 0.0), 2),
        "averageDropAmount": round(float(drop_events["DropAmount"].mean()), 4) if not drop_events.empty else 0.0,
        "medianDropAmount": round(float(safe_median(drop_events["DropAmount"])) if not drop_events.empty else 0.0, 4),
        "maxDropAmount": round(float(drop_events["DropAmount"].max()), 4) if not drop_events.empty else 0.0,
        "lowestObservedPrice": round(float(drop_events["NewPrice"].min()), 4) if not drop_events.empty else None,
        "hotelsWithDrops": int(drop_events["HotelId"].nunique()) if "HotelId" in drop_events.columns else None,
        "dropProbabilityNextScan": round(probability_next_drop(by_scan), 4),
    }

    return drop_events, by_scan, by_hotel, summary


def main() -> None:
    cfg = parse_args()
    os.makedirs(cfg.out_dir, exist_ok=True)

    raw = load_data(cfg)
    enriched = enrich_price_fields(raw)
    enriched = add_scan_windows(enriched, cfg.scan_minutes)

    drop_events, by_scan, by_hotel, summary = build_reports(enriched, cfg.scan_minutes)

    drop_events.to_csv(os.path.join(cfg.out_dir, "price_drop_events.csv"), index=False)
    by_scan.to_csv(os.path.join(cfg.out_dir, "price_drop_by_scan.csv"), index=False)
    by_hotel.to_csv(os.path.join(cfg.out_dir, "price_drop_by_hotel.csv"), index=False)

    with open(os.path.join(cfg.out_dir, "summary.json"), "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

