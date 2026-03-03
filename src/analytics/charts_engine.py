"""Charts engine — contract path, market benchmark, and breach statistics.

Three chart groups:
  Tab 1: Room/Contract Path (single contract deep dive) — Charts 1-4
  Tab 2: 3-Year Term Structure (aggregate) — Charts 5-9 (reuses term_structure_engine)
  Tab 3: Expiry-Relative Opportunity Stats (6 months) — Charts 10-12
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

T_BUCKETS = [90, 60, 45, 30, 21, 14, 10, 7, 5, 3, 1]
T_WINDOW = 3
YEARS = ["2023", "2024", "2025"]
CONTRACT_KEY = ["hotel_id", "checkin_date", "category", "board"]
BREACH_THRESHOLDS = (-5.0, -10.0)
BUCKET_LABELS = ["<-20%", "-20 to -10%", "-10 to -5%", "-5 to 0%", "0 to +5%", ">+5%"]
BUCKET_EDGES = [-999, -20, -10, -5, 0, 5, 999]

HOTEL_IDS = [66814, 854881, 20702, 24982]
HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


# ── Top-level cache builder (Tab 2 + Tab 3, background thread) ───────────


def build_charts_cache(hotel_ids: list[int]) -> dict:
    """Build all pre-cacheable chart data (Tabs 2 & 3).

    Tab 1 is on-demand (AJAX) and not included here.

    Returns:
        {
            "tab2": {hotel_id: {"combos": [...], "data": {"cat|board": {...}}}},
            "tab3": {hotel_id: {...}},
            "contracts_index": {hotel_id: [...]},
            "filter_options": {"categories": [...], "boards": [...], "years": [...]},
        }
    """
    from src.analytics.term_structure_engine import build_all_term_structures
    from src.analytics.yoy_analysis import build_scan_timeseries
    from src.data.yoy_db import load_unified_yoy_data

    logger.info("Charts cache: loading unified YoY data for %d hotels", len(hotel_ids))
    raw = load_unified_yoy_data(hotel_ids)
    if raw.empty:
        logger.warning("Charts cache: no data returned")
        return {}

    ts = build_scan_timeseries(raw)
    tab2 = build_all_term_structures(ts, hotel_ids)
    tab3 = _build_tab3_data(raw, hotel_ids)
    contracts_index = _build_contracts_index(raw, hotel_ids)

    categories = sorted(raw["category"].dropna().unique().tolist())
    boards = sorted(raw["board"].dropna().unique().tolist())
    years = sorted(str(y) for y in raw["year"].dropna().unique().tolist())

    logger.info(
        "Charts cache built: tab2=%d hotels, tab3=%d hotels, contracts=%d hotels",
        len(tab2), len(tab3), len(contracts_index),
    )
    return {
        "tab2": tab2,
        "tab3": tab3,
        "contracts_index": contracts_index,
        "filter_options": {"categories": categories, "boards": boards, "years": years},
    }


# ── Tab 1: Contract path (on-demand per AJAX) ────────────────────────────


def build_contract_path(
    hotel_id: int,
    checkin_date: str,
    category: str,
    board: str,
    market_radius_km: float = 5.0,
    market_stars: int | None = None,
) -> dict:
    """Build Charts 1-4 data for a single contract.

    Returns JSON-serializable dict with chart1..chart4 datasets + meta.
    """
    from src.data.yoy_db import load_unified_yoy_data

    raw = load_unified_yoy_data([hotel_id])
    if raw.empty:
        return _empty_contract()

    checkin_dt = pd.to_datetime(checkin_date)
    sub = raw[
        (raw["hotel_id"] == hotel_id)
        & (raw["checkin_date"] == checkin_dt)
        & (raw["category"] == category.lower().strip())
        & (raw["board"] == board.lower().strip())
    ].copy()

    if sub.empty:
        return _empty_contract()

    # Filter out invalid prices and NaN
    sub = sub[sub["price"].notna() & (sub["price"] > 0)].copy()
    if sub.empty:
        return _empty_contract()

    sub = sub.sort_values("scan_date")

    # Settlement price: price at smallest T_days (closest to check-in)
    s_exp_row = sub.loc[sub["T_days"].idxmin()]
    s_exp = float(s_exp_row["price"])

    # Chart 1: Realized Price Path (scan_date, price)
    chart1 = {
        "scan_dates": [d.strftime("%Y-%m-%d") for d in sub["scan_date"]],
        "prices": [round(float(p), 2) for p in sub["price"]],
    }

    # Chart 2: T-space path (T_days descending, price)
    t_sorted = sub.sort_values("T_days", ascending=False)
    chart2 = {
        "T_values": [int(t) for t in t_sorted["T_days"]],
        "prices": [round(float(p), 2) for p in t_sorted["price"]],
    }

    # Chart 3: Relative-to-expiry (T_days, rel %)
    if s_exp > 0:
        t_sorted = t_sorted.copy()
        t_sorted["rel_pct"] = (t_sorted["price"] - s_exp) / s_exp * 100.0
        chart3 = {
            "T_values": [int(t) for t in t_sorted["T_days"]],
            "rel_pct": [round(float(r), 2) for r in t_sorted["rel_pct"]],
            "S_exp": round(s_exp, 2),
            "thresholds": [-10, -5, 5, 10],
        }
    else:
        chart3 = {"T_values": [], "rel_pct": [], "S_exp": 0, "thresholds": [-10, -5, 5, 10]}

    # Chart 4: Market premium path
    chart4 = _build_chart4_market_premium(
        hotel_id, checkin_date, t_sorted, market_radius_km, market_stars,
    )

    meta = {
        "hotel_name": HOTEL_NAMES.get(hotel_id, f"Hotel {hotel_id}"),
        "hotel_id": hotel_id,
        "checkin_date": checkin_date,
        "category": category,
        "board": board,
        "S_exp": round(s_exp, 2),
        "n_scans": len(sub),
        "first_scan": sub["scan_date"].min().strftime("%Y-%m-%d"),
        "last_scan": sub["scan_date"].max().strftime("%Y-%m-%d"),
        "min_price": round(float(sub["price"].min()), 2),
        "max_price": round(float(sub["price"].max()), 2),
    }

    return {
        "chart1_realized_path": chart1,
        "chart2_t_space_path": chart2,
        "chart3_rel_expiry": chart3,
        "chart4_market_premium": chart4,
        "contract_meta": meta,
    }


def _empty_contract() -> dict:
    """Return fallback data when no records match the requested contract."""
    return {
        "chart1_realized_path": {"scan_dates": [], "prices": []},
        "chart2_t_space_path": {"T_values": [], "prices": []},
        "chart3_rel_expiry": {"T_values": [], "rel_pct": [], "S_exp": 0, "thresholds": [-10, -5, 5, 10]},
        "chart4_market_premium": {"T_values": [], "premium_pct": [], "market_avg": [], "our_price": [], "percentile": [], "no_market_data": True},
        "contract_meta": {},
    }


def _build_chart4_market_premium(
    hotel_id: int,
    checkin_date: str,
    contract_df: pd.DataFrame,
    radius_km: float,
    stars: int | None,
) -> dict:
    """Build Chart 4: premium vs market benchmark at each T."""
    market = _build_market_benchmark(hotel_id, checkin_date, radius_km, stars)

    if market.empty or contract_df.empty:
        t_vals = [int(t) for t in contract_df["T_days"]] if not contract_df.empty else []
        prices = [round(float(p), 2) for p in contract_df["price"]] if not contract_df.empty else []
        n = len(t_vals)
        return {
            "T_values": t_vals,
            "premium_pct": [None] * n,
            "market_avg": [None] * n,
            "our_price": prices,
            "percentile": [None] * n,
            "no_market_data": True,
        }

    # Merge contract data with market on scan_date
    contract = contract_df[["scan_date", "T_days", "price"]].copy()
    contract["scan_date_d"] = pd.to_datetime(contract["scan_date"]).dt.date

    market["scan_date_d"] = pd.to_datetime(market["scan_date"]).dt.date

    merged = contract.merge(market, on="scan_date_d", how="left", suffixes=("", "_mkt"))

    t_vals = []
    premium_pct = []
    market_avg_list = []
    our_price_list = []
    percentile_list = []

    for _, row in merged.sort_values("T_days", ascending=False).iterrows():
        t_vals.append(int(row["T_days"]))
        our_price_list.append(round(float(row["price"]), 2))

        if pd.notna(row.get("market_avg")) and row["market_avg"] > 0:
            prem = (row["price"] - row["market_avg"]) / row["market_avg"] * 100.0
            premium_pct.append(round(float(prem), 2))
            market_avg_list.append(round(float(row["market_avg"]), 2))
            percentile_list.append(round(float(row.get("percentile", 50)), 1))
        else:
            premium_pct.append(None)
            market_avg_list.append(None)
            percentile_list.append(None)

    return {
        "T_values": t_vals,
        "premium_pct": premium_pct,
        "market_avg": market_avg_list,
        "our_price": our_price_list,
        "percentile": percentile_list,
        "no_market_data": False,
    }


def _build_market_benchmark(
    hotel_id: int,
    checkin_date: str,
    radius_km: float = 5.0,
    stars: int | None = None,
) -> pd.DataFrame:
    """Build comparable market pricing per scan_date.

    Returns DataFrame: scan_date, market_avg, market_median, market_p25, market_p75, n_competitors, percentile.
    """
    from src.data.trading_db import load_competitor_hotels, run_trading_query

    competitors = load_competitor_hotels(hotel_id, radius_km, stars)
    if competitors.empty:
        logger.info("No competitors found for hotel %d within %.1f km", hotel_id, radius_km)
        return pd.DataFrame()

    comp_ids = competitors["HotelId"].tolist()
    ids_csv = ",".join(str(int(h)) for h in comp_ids)

    checkin_dt = pd.to_datetime(checkin_date)
    # Query AI_Search_HotelData for competitor prices around this checkin date
    sql = f"""
        SELECT
            HotelId,
            PriceAmount,
            CAST(UpdatedAt AS DATE) AS scan_date
        FROM AI_Search_HotelData
        WHERE HotelId IN ({ids_csv})
          AND StayFrom >= :checkin_start AND StayFrom <= :checkin_end
          AND PriceAmount > 0
        ORDER BY UpdatedAt
    """
    params = {
        "checkin_start": (checkin_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        "checkin_end": (checkin_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
    }

    try:
        raw = run_trading_query(sql, params)
    except Exception as e:
        logger.warning("Market benchmark query failed: %s", e)
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    # Aggregate per scan_date
    agg = raw.groupby("scan_date").agg(
        market_avg=("PriceAmount", "mean"),
        market_median=("PriceAmount", "median"),
        market_p25=("PriceAmount", lambda x: float(np.percentile(x, 25))),
        market_p75=("PriceAmount", lambda x: float(np.percentile(x, 75))),
        n_competitors=("HotelId", "nunique"),
    ).reset_index()

    # Compute percentile of our hotel's price vs market at each scan_date
    # (will be merged later in _build_chart4)
    # For now store raw data — percentile computed during merge
    agg["percentile"] = 50.0  # default, overridden in merge

    return agg


# ── Tab 3: Breach/opportunity stats ──────────────────────────────────────


def _build_tab3_data(raw: pd.DataFrame, hotel_ids: list[int]) -> dict:
    """Build Charts 10-12 data: breach rates, min_rel distributions, threshold counts.

    Scoped to last 6 months of check-in dates.
    """
    # Year-aware contract key: same hotel+checkin+cat+board in different years
    # are separate contracts with different settlement prices
    tab3_contract_key = ["hotel_id", "checkin_date", "category", "board", "year"]

    result: dict = {}

    if raw.empty:
        return result

    # Ensure year column exists
    if "year" not in raw.columns:
        raw = raw.copy()
        raw["year"] = raw["scan_date"].dt.year

    # Filter to last 6 months of check-in dates
    max_checkin = raw["checkin_date"].max()
    six_months_ago = max_checkin - pd.Timedelta(days=180)
    recent = raw[raw["checkin_date"] >= six_months_ago].copy()

    if recent.empty:
        return result

    for hid in hotel_ids:
        sub = recent[recent["hotel_id"] == hid]
        if sub.empty:
            continue

        # Filter to valid prices before computing settlement
        sub = sub[sub["price"] > 0].copy()
        if sub.empty:
            continue

        # Compute settlement price per contract (price at min T_days)
        settlement = (
            sub.sort_values("T_days")
            .groupby(tab3_contract_key, as_index=False)
            .first()[tab3_contract_key + ["price"]]
            .rename(columns={"price": "S_exp"})
        )

        merged = sub.merge(settlement, on=tab3_contract_key, how="inner")
        merged = merged[merged["S_exp"] > 0].copy()

        if merged.empty:
            continue

        merged["rel"] = (merged["price"] - merged["S_exp"]) / merged["S_exp"] * 100.0

        # Add year/month columns for grouping (needed for Charts 10-12)
        merged["year_str"] = merged["checkin_date"].dt.year.astype(str)
        merged["month_str"] = merged["checkin_date"].dt.strftime("%Y-%m")

        # Min rel per contract (year-aware)
        min_per = (
            merged.groupby(tab3_contract_key)["rel"]
            .min()
            .reset_index()
            .rename(columns={"rel": "min_rel"})
        )
        min_per["year_str"] = min_per["checkin_date"].dt.year.astype(str)
        min_per["month_str"] = min_per["checkin_date"].dt.strftime("%Y-%m")

        # Chart 10: min_rel distribution histogram by year
        min_rel_dist = {}
        for yr in YEARS:
            yr_vals = min_per[min_per["year_str"] == yr]["min_rel"].values
            if len(yr_vals) > 0:
                bins = np.histogram(yr_vals, bins=BUCKET_EDGES)[0].tolist()
                min_rel_dist[yr] = [int(x) for x in bins]
            else:
                min_rel_dist[yr] = [0] * len(BUCKET_LABELS)

        # Chart 11: breach rates by year and by month
        breach_by_year: dict = {}
        for yr in YEARS:
            yr_data = min_per[min_per["year_str"] == yr]
            n = len(yr_data)
            if n > 0:
                pct_5 = round(float((yr_data["min_rel"] <= -5).mean() * 100), 1)
                pct_10 = round(float((yr_data["min_rel"] <= -10).mean() * 100), 1)
            else:
                pct_5, pct_10 = 0.0, 0.0
            breach_by_year[yr] = {"pct_5": pct_5, "pct_10": pct_10, "n": n}

        breach_by_month: dict = {}
        for month_key, group in min_per.groupby("month_str"):
            n = len(group)
            pct_5 = round(float((group["min_rel"] <= -5).mean() * 100), 1)
            pct_10 = round(float((group["min_rel"] <= -10).mean() * 100), 1)
            breach_by_month[month_key] = {"pct_5": pct_5, "pct_10": pct_10, "n": n}

        # Chart 12: threshold breach counts (days + crossing events)
        threshold_by_year = _compute_threshold_counts(merged, "year_str", YEARS)
        months_list = sorted(merged["month_str"].unique().tolist())
        threshold_by_month = _compute_threshold_counts(merged, "month_str", months_list)

        result[int(hid)] = {
            "min_rel_dist": {"buckets": BUCKET_LABELS, **min_rel_dist},
            "breach_rates": {"by_year": breach_by_year, "by_month": breach_by_month},
            "threshold_counts": {"by_year": threshold_by_year, "by_month": threshold_by_month},
        }

    return result


def _compute_threshold_counts(df: pd.DataFrame, group_col: str, keys: list[str]) -> dict:
    """Compute scan-days below and crossing events for -5% and -10% thresholds."""
    # Year-aware contract key for consistent grouping
    tab3_contract_key = ["hotel_id", "checkin_date", "category", "board", "year"]

    result: dict = {}
    for key in keys:
        sub = df[df[group_col] == key]
        scans_5 = int((sub["rel"] <= -5).sum())
        scans_10 = int((sub["rel"] <= -10).sum())

        # Crossing events: transitions from above to below threshold
        events_5 = 0
        events_10 = 0
        # Use only columns that exist in the dataframe
        grp_cols = [c for c in tab3_contract_key if c in sub.columns]
        if grp_cols:
            for _, contract_group in sub.groupby(grp_cols):
                sorted_g = contract_group.sort_values("T_days", ascending=False)
                rels = sorted_g["rel"].values
                for i in range(1, len(rels)):
                    if rels[i] <= -5 and rels[i - 1] > -5:
                        events_5 += 1
                    if rels[i] <= -10 and rels[i - 1] > -10:
                        events_10 += 1

        result[key] = {
            "days_5": scans_5, "days_10": scans_10,
            "events_5": events_5, "events_10": events_10,
        }
    return result


# ── Contract index builder ────────────────────────────────────────────────


def _build_contracts_index(raw: pd.DataFrame, hotel_ids: list[int]) -> dict:
    """Build contract selector dropdown data for Tab 1.

    Returns: {hotel_id: [{"checkin_date": ..., "category": ..., ...}, ...]}
    """
    result: dict = {}

    if raw.empty:
        return result

    for hid in hotel_ids:
        sub = raw[raw["hotel_id"] == hid]
        if sub.empty:
            continue

        contracts = (
            sub.groupby(CONTRACT_KEY)
            .agg(
                n_scans=("price", "count"),
                first_scan=("scan_date", "min"),
                last_scan=("scan_date", "max"),
                min_price=("price", "min"),
                max_price=("price", "max"),
            )
            .reset_index()
        )

        # Only include contracts with enough data points
        contracts = contracts[contracts["n_scans"] >= 3].copy()
        contracts = contracts.sort_values("checkin_date", ascending=False).head(200)

        entries = []
        for _, row in contracts.iterrows():
            # checkin_date, first_scan, last_scan are already datetime from groupby
            checkin_str = row["checkin_date"].strftime("%Y-%m-%d") if hasattr(row["checkin_date"], "strftime") else str(row["checkin_date"])[:10]
            first_str = row["first_scan"].strftime("%Y-%m-%d") if hasattr(row["first_scan"], "strftime") else str(row["first_scan"])[:10]
            last_str = row["last_scan"].strftime("%Y-%m-%d") if hasattr(row["last_scan"], "strftime") else str(row["last_scan"])[:10]
            entries.append({
                "checkin_date": checkin_str,
                "category": str(row["category"]),
                "board": str(row["board"]),
                "n_scans": int(row["n_scans"]),
                "date_range": f"{first_str} to {last_str}",
                "price_range": f"${row['min_price']:.0f}-${row['max_price']:.0f}",
            })

        if entries:
            result[int(hid)] = entries

    return result
