"""Next-Scan Price Drop Predictor.

Predicts which rooms will see a ≥5% price drop in the NEXT scan cycle.
Uses scan velocity, acceleration, drop frequency, market pressure, and
pattern features to score each room's drop probability.

Unlike the standard options signal (which looks at check-in date),
this skill focuses on the immediate next scan — finding short-term
PUT opportunities even in uptrending rooms.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── SQL Queries ────────────────────────────────────────────────────────

SCAN_VELOCITY_QUERY = """
SELECT
    d.Id AS detail_id,
    d.HotelId AS hotel_id,
    h.Name AS hotel_name,
    d.RoomCategory AS category,
    d.RoomBoard AS board,
    d.RoomPrice AS current_price,
    d.DateCreated AS last_scan_date,
    o.DateFrom AS checkin_date,
    DATEDIFF(day, GETDATE(), o.DateFrom) AS days_to_checkin
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
JOIN Med_Hotels h ON d.HotelId = h.HotelId
WHERE o.IsActive = 1
  AND o.WebJobStatus LIKE 'Completed%%'
  AND o.WebJobStatus NOT LIKE '%%Mapping: 0%%'
"""

PRICE_HISTORY_QUERY = """
SELECT
    d.Id AS detail_id,
    d.HotelId AS hotel_id,
    d.RoomCategory AS category,
    d.RoomBoard AS board,
    d.RoomPrice AS price,
    d.DateCreated AS scan_date
FROM [SalesOffice.Details] d
JOIN [SalesOffice.Orders] o ON d.SalesOfficeOrderId = o.Id
WHERE o.IsActive = 1
  AND o.WebJobStatus LIKE 'Completed%%'
  AND o.WebJobStatus NOT LIKE '%%Mapping: 0%%'
ORDER BY d.Id, d.DateCreated
"""

MARKET_PRESSURE_QUERY = """
SELECT
    h.HotelId,
    AVG(a.PriceAmount) AS market_avg_price,
    MIN(a.PriceAmount) AS market_min_price,
    COUNT(*) AS market_samples
FROM AI_Search_HotelData a
JOIN Med_Hotels h ON a.HotelId = h.HotelId
WHERE a.UpdatedAt >= DATEADD(day, -7, GETDATE())
  AND a.PriceAmount > 0
GROUP BY h.HotelId
"""


# ── Feature Extraction ────────────────────────────────────────────────

@dataclass
class RoomFeatures:
    detail_id: int
    hotel_id: int
    hotel_name: str
    category: str
    board: str
    current_price: float
    days_to_checkin: int

    # Scan velocity features
    velocity_3h: float = 0.0        # % change in last scan
    velocity_6h: float = 0.0        # % change over 2 scans
    velocity_12h: float = 0.0       # % change over 4 scans
    acceleration: float = 0.0       # velocity trend (speeding up/slowing)

    # Pattern features
    drop_frequency: float = 0.0     # % of scans that were drops
    consecutive_drops: int = 0      # current streak of consecutive drops
    total_drops: int = 0
    total_scans: int = 0
    max_single_drop_pct: float = 0.0

    # Market features
    market_pressure: float = 0.0    # our price vs market avg

    # Derived
    score: float = 0.0
    probability: float = 0.0
    signal: str = "NEUTRAL"
    strength: int = 0
    expected_drop_pct: float = 0.0


def extract_scan_features(detail_id: int, prices: list[tuple[float, str]]) -> dict:
    """Extract velocity, acceleration, and pattern features from scan history."""
    if len(prices) < 2:
        return {}

    # Sort by date ascending
    sorted_prices = sorted(prices, key=lambda x: x[1])
    price_values = [p[0] for p in sorted_prices]

    # Velocity: % change between consecutive scans
    changes = []
    for i in range(1, len(price_values)):
        if price_values[i - 1] > 0:
            pct = (price_values[i] - price_values[i - 1]) / price_values[i - 1] * 100
            changes.append(pct)

    if not changes:
        return {}

    velocity_3h = changes[-1]  # Last scan change
    velocity_6h = sum(changes[-2:]) / min(2, len(changes)) if len(changes) >= 2 else velocity_3h
    velocity_12h = sum(changes[-4:]) / min(4, len(changes)) if len(changes) >= 4 else velocity_6h

    # Acceleration: is velocity getting more negative?
    if len(changes) >= 2:
        acceleration = changes[-1] - changes[-2]
    else:
        acceleration = 0.0

    # Drop frequency
    drops = [c for c in changes if c < 0]
    drop_frequency = len(drops) / len(changes) if changes else 0

    # Consecutive drops (recent streak)
    consecutive = 0
    for c in reversed(changes):
        if c < 0:
            consecutive += 1
        else:
            break

    # Max single drop
    max_drop = abs(min(changes)) if changes else 0

    return {
        "velocity_3h": round(velocity_3h, 4),
        "velocity_6h": round(velocity_6h, 4),
        "velocity_12h": round(velocity_12h, 4),
        "acceleration": round(acceleration, 4),
        "drop_frequency": round(drop_frequency, 4),
        "consecutive_drops": consecutive,
        "total_drops": len(drops),
        "total_scans": len(changes),
        "max_single_drop_pct": round(max_drop, 4),
    }


def score_drop_probability(features: RoomFeatures) -> tuple[float, str, int]:
    """Score the probability of a ≥5% drop in the next scan.

    Returns (probability, signal, strength).
    """
    points = 0.0

    # Velocity signals (strongest indicator)
    if features.velocity_3h < -5.0:
        points += 35
    elif features.velocity_3h < -3.0:
        points += 25
    elif features.velocity_3h < -1.0:
        points += 10

    # Acceleration (drop speeding up)
    if features.acceleration < -2.0:
        points += 20
    elif features.acceleration < 0:
        points += 10

    # Drop frequency (historically volatile)
    if features.drop_frequency > 0.5:
        points += 20
    elif features.drop_frequency > 0.3:
        points += 10

    # Consecutive drops (momentum)
    if features.consecutive_drops >= 3:
        points += 20
    elif features.consecutive_drops >= 2:
        points += 15
    elif features.consecutive_drops >= 1:
        points += 5

    # Market pressure
    if features.market_pressure < -0.1:
        points += 10
    elif features.market_pressure < -0.05:
        points += 5

    # Category volatility (Suite/Deluxe more volatile)
    cat = str(features.category).lower()
    if "suite" in cat or "deluxe" in cat:
        points += 5

    # Max historical drop (has shown ability to drop big)
    if features.max_single_drop_pct > 10:
        points += 10
    elif features.max_single_drop_pct > 5:
        points += 5

    # Normalize to probability
    probability = min(1.0, max(0.0, points / 100.0))

    # Signal classification
    if points >= 70:
        signal = "STRONG_PUT"
        strength = min(10, int(points / 10))
    elif points >= 50:
        signal = "PUT"
        strength = min(7, int(points / 12))
    elif points >= 30:
        signal = "WATCH"
        strength = min(4, int(points / 15))
    else:
        signal = "NEUTRAL"
        strength = 0

    return probability, signal, strength


# ── Data Loading ───────────────────────────────────────────────────────

def load_from_api(api_url: str) -> list[RoomFeatures]:
    """Load data from the prediction API and compute features."""
    import urllib.request

    url = f"{api_url.rstrip('/')}/api/v1/salesoffice/options?all=true&profile=lite"
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = json.loads(resp.read())

    rows = data.get("rows", [])
    features_list = []

    for r in rows:
        scan = r.get("scan_history") or {}
        snapshots = scan.get("scan_snapshots", 0) or 0

        rf = RoomFeatures(
            detail_id=r.get("detail_id", 0),
            hotel_id=r.get("hotel_id", 0),
            hotel_name=r.get("hotel_name", ""),
            category=r.get("category", ""),
            board=r.get("board", ""),
            current_price=float(r.get("current_price", 0) or 0),
            days_to_checkin=int(r.get("days_to_checkin", 0) or 0),
        )

        # Extract features from scan history
        rf.total_scans = snapshots
        rf.total_drops = int(scan.get("scan_actual_drops", 0) or 0)
        rf.max_single_drop_pct = abs(float(scan.get("scan_max_single_drop", 0) or 0))

        if rf.current_price > 0 and rf.total_scans >= 1:
            first_price = float(scan.get("first_scan_price", 0) or 0)
            latest_price = float(scan.get("latest_scan_price", 0) or 0)
            change_pct = float(scan.get("scan_price_change_pct", 0) or 0)

            # Approximate velocity from available data
            if rf.total_scans >= 2 and first_price > 0:
                avg_change_per_scan = change_pct / max(1, rf.total_scans - 1)
                rf.velocity_3h = avg_change_per_scan
                rf.velocity_6h = avg_change_per_scan
                rf.velocity_12h = avg_change_per_scan

            # Drop frequency
            rises = int(scan.get("scan_actual_rises", 0) or 0)
            total_moves = rf.total_drops + rises
            if total_moves > 0:
                rf.drop_frequency = rf.total_drops / total_moves

            # Trend as acceleration proxy
            trend = scan.get("scan_trend", "stable")
            if trend == "down":
                rf.acceleration = -1.0
                rf.consecutive_drops = max(1, rf.total_drops)
            elif trend == "up":
                rf.acceleration = 1.0
                rf.consecutive_drops = 0

            # Max drop as percentage
            if rf.current_price > 0:
                rf.max_single_drop_pct = abs(float(scan.get("scan_max_single_drop", 0) or 0)) / rf.current_price * 100

        # Forward curve decline events as additional signal
        put_decline = int(r.get("put_decline_count", 0) or 0)
        exp_min = float(r.get("expected_min_price", 0) or 0)
        if rf.current_price > 0 and exp_min > 0:
            min_vs_current = (exp_min - rf.current_price) / rf.current_price * 100
            if min_vs_current < -5:
                rf.market_pressure = min_vs_current / 100  # Normalize

        # Score
        rf.probability, rf.signal, rf.strength = score_drop_probability(rf)
        if rf.velocity_3h < 0:
            rf.expected_drop_pct = rf.velocity_3h  # Simplistic but directional

        features_list.append(rf)

    return features_list


def load_from_db(connection_string: str) -> list[RoomFeatures]:
    """Load data directly from Azure SQL and compute features."""
    import pyodbc

    conn = pyodbc.connect(connection_string)
    try:
        # Load current state
        current_df = pd.read_sql(SCAN_VELOCITY_QUERY, conn)

        # Load price history for velocity calculation
        history_df = pd.read_sql(PRICE_HISTORY_QUERY, conn)

        # Load market pressure
        try:
            market_df = pd.read_sql(MARKET_PRESSURE_QUERY, conn)
            market_map = dict(zip(market_df["HotelId"], market_df["market_avg_price"]))
        except Exception:
            market_map = {}
    finally:
        conn.close()

    # Build price history per detail_id
    price_history = {}
    for _, row in history_df.iterrows():
        did = row["detail_id"]
        if did not in price_history:
            price_history[did] = []
        price_history[did].append((float(row["price"]), str(row["scan_date"])))

    features_list = []
    for _, row in current_df.iterrows():
        did = int(row["detail_id"])
        rf = RoomFeatures(
            detail_id=did,
            hotel_id=int(row["hotel_id"]),
            hotel_name=str(row["hotel_name"]),
            category=str(row.get("category", "")),
            board=str(row.get("board", "")),
            current_price=float(row["current_price"]),
            days_to_checkin=int(row.get("days_to_checkin", 0)),
        )

        # Extract features from price history
        if did in price_history:
            feats = extract_scan_features(did, price_history[did])
            for k, v in feats.items():
                setattr(rf, k, v)

        # Market pressure
        market_avg = market_map.get(rf.hotel_id, 0)
        if market_avg > 0 and rf.current_price > 0:
            rf.market_pressure = (rf.current_price - market_avg) / market_avg

        # Score
        rf.probability, rf.signal, rf.strength = score_drop_probability(rf)
        rf.expected_drop_pct = rf.velocity_3h if rf.velocity_3h < 0 else 0.0

        features_list.append(rf)

    return features_list


# ── Report Generation ──────────────────────────────────────────────────

def generate_report(features: list[RoomFeatures], out_dir: str) -> dict:
    """Generate trading signals report."""
    os.makedirs(out_dir, exist_ok=True)

    # Sort by signal strength descending
    features.sort(key=lambda f: (-f.strength, -f.probability, f.expected_drop_pct))

    # Summary
    total = len(features)
    strong_put = sum(1 for f in features if f.signal == "STRONG_PUT")
    put = sum(1 for f in features if f.signal == "PUT")
    watch = sum(1 for f in features if f.signal == "WATCH")
    neutral = sum(1 for f in features if f.signal == "NEUTRAL")

    summary = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "totalRooms": total,
        "signalCounts": {
            "STRONG_PUT": strong_put,
            "PUT": put,
            "WATCH": watch,
            "NEUTRAL": neutral,
        },
        "putRate": round((strong_put + put) / total * 100, 1) if total else 0,
        "description": "Next-scan price drop prediction. PUT = expected ≥5% drop in the next 3-hour scan cycle.",
    }

    # Top signals
    top_signals = []
    for f in features[:100]:
        if f.signal in ("STRONG_PUT", "PUT", "WATCH"):
            top_signals.append({
                "detailId": f.detail_id,
                "hotelId": f.hotel_id,
                "hotelName": f.hotel_name,
                "category": f.category,
                "board": f.board,
                "currentPrice": round(f.current_price, 2),
                "signal": f.signal,
                "strength": f.strength,
                "probability": round(f.probability, 3),
                "expectedDropPct": round(f.expected_drop_pct, 2),
                "features": {
                    "velocity3h": round(f.velocity_3h, 3),
                    "acceleration": round(f.acceleration, 3),
                    "dropFrequency": round(f.drop_frequency, 3),
                    "consecutiveDrops": f.consecutive_drops,
                    "maxSingleDropPct": round(f.max_single_drop_pct, 2),
                    "marketPressure": round(f.market_pressure, 4),
                    "totalScans": f.total_scans,
                    "totalDrops": f.total_drops,
                },
                "daysToCheckin": f.days_to_checkin,
            })

    summary["topSignals"] = top_signals

    # Save
    with open(os.path.join(out_dir, "next_scan_signals.json"), "w") as fp:
        json.dump(summary, fp, indent=2, ensure_ascii=False)

    # CSV for all PUT signals
    put_rows = [f for f in features if f.signal in ("STRONG_PUT", "PUT")]
    if put_rows:
        df = pd.DataFrame([{
            "detail_id": f.detail_id, "hotel_id": f.hotel_id, "hotel": f.hotel_name,
            "category": f.category, "board": f.board, "price": f.current_price,
            "signal": f.signal, "strength": f.strength, "probability": f.probability,
            "velocity_3h": f.velocity_3h, "acceleration": f.acceleration,
            "drop_freq": f.drop_frequency, "consec_drops": f.consecutive_drops,
            "expected_drop_pct": f.expected_drop_pct, "days_to_checkin": f.days_to_checkin,
        } for f in put_rows])
        df.to_csv(os.path.join(out_dir, "next_scan_put_signals.csv"), index=False)

    return summary


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Next-scan price drop predictor")
    parser.add_argument("--api-url", help="Prediction API URL")
    parser.add_argument("--connection-string", help="ODBC connection string")
    parser.add_argument("--out", default="report", help="Output directory")
    args = parser.parse_args()

    if args.api_url:
        features = load_from_api(args.api_url)
    elif args.connection_string:
        features = load_from_db(args.connection_string)
    else:
        raise SystemExit("Provide --api-url or --connection-string")

    summary = generate_report(features, args.out)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
