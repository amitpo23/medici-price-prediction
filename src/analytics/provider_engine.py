"""Provider price comparison engine — analyze 8.3M SearchResultsSessionPollLog records.

Compares gross/net prices across 129 providers to identify:
- Which providers offer the lowest net prices
- Provider margin analysis (gross - net spread)
- Provider market share and availability
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

HOTEL_IDS = [66814, 854881, 20702, 24982]
HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def build_provider_data(hotel_ids: list[int] | None = None, days_back: int = 90) -> dict:
    """Build provider comparison data from SearchResultsSessionPollLog.

    Returns structured dict with provider rankings, margins, and market share.
    """
    from src.data.trading_db import load_search_results

    hids = hotel_ids or HOTEL_IDS
    raw = load_search_results(hotel_ids=hids, days_back=days_back)
    if raw.empty:
        return {"error": "No search results data available", "providers": []}

    # Parse provider names from Providers column (JSON or comma-separated)
    raw["provider_name"] = raw["Providers"].apply(_parse_provider)
    raw = raw[raw["provider_name"] != "unknown"].copy()

    # Filter valid prices
    raw = raw[raw["PriceAmount"].notna() & (raw["PriceAmount"] > 0)].copy()
    if raw.empty:
        return {"error": "No valid price data", "providers": []}

    # Compute net margin where available
    raw["margin"] = np.where(
        raw["NetPriceAmount"].notna() & (raw["NetPriceAmount"] > 0),
        raw["PriceAmount"] - raw["NetPriceAmount"],
        np.nan,
    )
    raw["margin_pct"] = np.where(
        raw["PriceAmount"] > 0,
        raw["margin"] / raw["PriceAmount"] * 100,
        np.nan,
    )

    # Provider-level aggregation
    provider_stats = _compute_provider_stats(raw)

    # Per-hotel provider comparison
    hotel_comparisons = {}
    for hid in hids:
        sub = raw[raw["HotelId"] == hid]
        if sub.empty:
            continue
        hotel_comparisons[int(hid)] = {
            "hotel_name": HOTEL_NAMES.get(hid, f"Hotel {hid}"),
            "providers": _compute_provider_stats(sub),
            "total_results": len(sub),
        }

    # Best provider per hotel (lowest avg net price)
    best_providers = {}
    for hid, data in hotel_comparisons.items():
        providers = data.get("providers", [])
        if providers:
            best = min(providers, key=lambda p: p.get("avg_net_price") or p.get("avg_gross_price", 999999))
            best_providers[hid] = {
                "hotel_name": HOTEL_NAMES.get(hid, f"Hotel {hid}"),
                "provider": best["provider_name"],
                "avg_price": best.get("avg_net_price") or best.get("avg_gross_price"),
            }

    # Room category breakdown
    category_stats = _compute_category_stats(raw)

    return {
        "provider_rankings": provider_stats,
        "hotel_comparisons": hotel_comparisons,
        "best_providers": best_providers,
        "category_breakdown": category_stats,
        "total_records": len(raw),
        "unique_providers": raw["provider_name"].nunique(),
        "date_range": {
            "from": raw["DateInsert"].min().strftime("%Y-%m-%d") if (not raw.empty and pd.notna(raw["DateInsert"].min())) else None,
            "to": raw["DateInsert"].max().strftime("%Y-%m-%d") if (not raw.empty and pd.notna(raw["DateInsert"].max())) else None,
        },
        "source": "SearchResultsSessionPollLog (8.3M rows, 129 providers)",
    }


def _parse_provider(providers_val) -> str:
    """Extract provider name from Providers column."""
    if pd.isna(providers_val):
        return "unknown"
    s = str(providers_val).strip()
    if not s:
        return "unknown"

    # Try JSON parse
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list) and parsed:
            return str(parsed[0]).strip()
        if isinstance(parsed, dict):
            return parsed.get("name", parsed.get("Name", str(parsed)))
        return str(parsed).strip()
    except (json.JSONDecodeError, TypeError):
        pass

    # Comma-separated
    if "," in s:
        return s.split(",")[0].strip()

    return s[:50]


def _compute_provider_stats(df: pd.DataFrame) -> list[dict]:
    """Compute stats per provider."""
    groups = df.groupby("provider_name")
    stats = []

    for provider, group in groups:
        n = len(group)
        if n < 5:
            continue

        avg_gross = round(float(group["PriceAmount"].mean()), 2)
        avg_net = None
        avg_margin = None
        avg_margin_pct = None

        net_valid = group[group["NetPriceAmount"].notna() & (group["NetPriceAmount"] > 0)]
        if len(net_valid) > 0:
            avg_net = round(float(net_valid["NetPriceAmount"].mean()), 2)
            margin_vals = net_valid["margin_pct"].dropna()
            if len(margin_vals) > 0:
                avg_margin = round(float(net_valid["margin"].mean()), 2)
                avg_margin_pct = round(float(margin_vals.mean()), 2)

        categories = group["RoomCategory"].nunique() if "RoomCategory" in group.columns else 0

        stats.append({
            "provider_name": str(provider),
            "total_results": n,
            "avg_gross_price": avg_gross,
            "avg_net_price": avg_net,
            "min_price": round(float(group["PriceAmount"].min()), 2),
            "max_price": round(float(group["PriceAmount"].max()), 2),
            "avg_margin": avg_margin,
            "avg_margin_pct": avg_margin_pct,
            "room_categories": int(categories),
            "market_share_pct": round(n / len(df) * 100, 1),
        })

    stats.sort(key=lambda x: x.get("avg_net_price") or x["avg_gross_price"])
    return stats


def _compute_category_stats(df: pd.DataFrame) -> list[dict]:
    """Compute price stats per room category."""
    if "RoomCategory" not in df.columns:
        return []

    stats = []
    for cat, group in df.groupby("RoomCategory"):
        if len(group) < 10:
            continue
        stats.append({
            "category": str(cat),
            "count": len(group),
            "avg_gross": round(float(group["PriceAmount"].mean()), 2),
            "avg_net": round(float(group["NetPriceAmount"].mean()), 2) if group["NetPriceAmount"].notna().any() else None,
            "providers": group["provider_name"].nunique(),
        })

    stats.sort(key=lambda x: x["count"], reverse=True)
    return stats[:20]
