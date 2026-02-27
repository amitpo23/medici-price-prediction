"""Hotel Knowledge Base — competitive landscape from TBO Hotels dataset.

Provides structured market intelligence for each SalesOffice hotel:
- Nearby competitors (within configurable radius)
- Sub-market size and rating distribution
- Hotel facilities and amenities
- Coordinates for geo-analysis

Data source: TBO Hotels dataset (Kaggle raj713335/tbo-hotels-dataset)
Filtered to Miami metro area (~1,816 unique hotels).
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Path to extracted Miami hotels CSV
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_MIAMI_CSV = _DATA_DIR / "miami_hotels_tbo.csv"

# Our SalesOffice hotels with known TBO codes and coordinates
SALESOFFICE_HOTELS = {
    66814: {
        "name": "Breakwater South Beach",
        "tbo_code": 1153760,
        "rating": "ThreeStar",
        "lat": 25.779887,
        "lon": -80.130707,
        "sub_market": "South Beach",
        "address": "940 Ocean Drive Miami Beach",
    },
    854881: {
        "name": "citizenM Miami Brickell",
        "tbo_code": None,  # Not in TBO dataset (newer chain)
        "rating": "FourStar",
        "lat": 25.7617,  # Approximate Brickell location
        "lon": -80.1918,
        "sub_market": "Brickell",
        "address": "Brickell, Miami",
    },
    20702: {
        "name": "Embassy Suites by Hilton Miami International Airport",
        "tbo_code": 1097638,
        "rating": "ThreeStar",
        "lat": 25.8075,
        "lon": -80.26178,
        "sub_market": "Airport",
        "address": "3974 NW South River Drive, Miami, FL 33142",
    },
    24982: {
        "name": "Hilton Miami Downtown",
        "tbo_code": 1045957,
        "rating": "FourStar",
        "lat": 25.79077,
        "lon": -80.18904,
        "sub_market": "Downtown",
        "address": "1601 Biscayne Blvd, Miami, FL 33132",
    },
}

# Cache loaded data
_miami_df: pd.DataFrame | None = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two coordinates."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _load_miami_data() -> pd.DataFrame:
    """Load and cache Miami hotels TBO data."""
    global _miami_df
    if _miami_df is not None:
        return _miami_df

    if not _MIAMI_CSV.exists():
        logger.warning("Miami hotels CSV not found at %s", _MIAMI_CSV)
        _miami_df = pd.DataFrame()
        return _miami_df

    df = pd.read_csv(_MIAMI_CSV, encoding="utf-8")
    # Clean whitespace
    for col in ["cityName", "HotelName", "HotelRating", "Address"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Parse coordinates
    if "Map" in df.columns:
        def _parse_map(val):
            s = str(val)
            if "|" in s:
                parts = s.split("|")
                try:
                    return float(parts[0].strip()), float(parts[1].strip())
                except (ValueError, IndexError):
                    pass
            return None, None

        df["lat"], df["lon"] = zip(*df["Map"].apply(_parse_map))

    _miami_df = df
    logger.info("Loaded %d Miami hotel records (%d unique)", len(df), df["HotelCode"].nunique())
    return _miami_df


def get_market_summary() -> dict:
    """Overall Miami hotel market summary."""
    df = _load_miami_data()
    if df.empty:
        return {"status": "no_data", "total_hotels": 0}

    unique = df.drop_duplicates("HotelCode")
    rating_dist = unique["HotelRating"].value_counts().to_dict()

    # Sub-markets
    sub_markets = {}
    market_patterns = {
        "South Beach": "South Beach",
        "Miami Beach": "Miami Beach",
        "Downtown/Brickell": "Miami,   Florida",
        "Fort Lauderdale": "Lauderdale",
        "Airport/Doral": "Doral",
        "Bal Harbour": "Bal Harbour",
        "Coral Gables": "Coral Gables",
        "Key Biscayne": "Key Biscayne",
    }
    for label, pattern in market_patterns.items():
        sub = df[df["cityName"].str.contains(pattern, case=False, na=False)]
        sub_markets[label] = sub["HotelCode"].nunique()

    return {
        "status": "ok",
        "data_source": "TBO Hotels (Kaggle)",
        "total_hotels": int(unique.shape[0]),
        "total_records": len(df),
        "rating_distribution": {k: int(v) for k, v in rating_dist.items()},
        "sub_markets": sub_markets,
    }


def get_competitors(hotel_id: int, radius_km: float = 2.0, limit: int = 20) -> dict:
    """Find competitor hotels within radius of a SalesOffice hotel.

    Args:
        hotel_id: SalesOffice hotel ID (e.g. 66814)
        radius_km: Search radius in km (default 2.0)
        limit: Max competitors to return

    Returns:
        Dict with competitor list and market composition.
    """
    df = _load_miami_data()
    hotel_info = SALESOFFICE_HOTELS.get(hotel_id)

    if hotel_info is None:
        return {"error": f"Unknown hotel_id {hotel_id}"}
    if df.empty:
        return {"hotel": hotel_info["name"], "competitors": [], "status": "no_data"}

    lat, lon = hotel_info["lat"], hotel_info["lon"]
    has_coords = df.dropna(subset=["lat", "lon"]).copy()

    if has_coords.empty:
        return {"hotel": hotel_info["name"], "competitors": [], "status": "no_coords"}

    has_coords["dist_km"] = has_coords.apply(
        lambda r: _haversine_km(lat, lon, r["lat"], r["lon"]), axis=1
    )
    within = has_coords[has_coords["dist_km"] <= radius_km].copy()
    # Remove self (by TBO code if known)
    if hotel_info["tbo_code"]:
        within = within[within["HotelCode"] != hotel_info["tbo_code"]]

    within = within.drop_duplicates("HotelCode").sort_values("dist_km")

    rating_counts = within["HotelRating"].value_counts().to_dict()
    competitors = []
    for _, row in within.head(limit).iterrows():
        comp = {
            "name": row["HotelName"],
            "tbo_code": int(row["HotelCode"]),
            "rating": row["HotelRating"],
            "distance_km": round(row["dist_km"], 2),
            "city": row["cityName"],
        }
        if pd.notna(row.get("Address")):
            comp["address"] = str(row["Address"])[:100]
        competitors.append(comp)

    return {
        "hotel": hotel_info["name"],
        "hotel_id": hotel_id,
        "sub_market": hotel_info["sub_market"],
        "radius_km": radius_km,
        "total_within_radius": len(within),
        "rating_breakdown": {k: int(v) for k, v in rating_counts.items()},
        "competitors": competitors,
    }


def get_hotel_profile(hotel_id: int) -> dict:
    """Detailed profile for a SalesOffice hotel from TBO data.

    Includes facilities, coordinates, address, and nearby market.
    """
    df = _load_miami_data()
    hotel_info = SALESOFFICE_HOTELS.get(hotel_id)

    if hotel_info is None:
        return {"error": f"Unknown hotel_id {hotel_id}"}

    profile = {
        "hotel_id": hotel_id,
        "name": hotel_info["name"],
        "rating": hotel_info["rating"],
        "sub_market": hotel_info["sub_market"],
        "coordinates": {"lat": hotel_info["lat"], "lon": hotel_info["lon"]},
        "address": hotel_info["address"],
    }

    # Try to find in TBO data for facilities
    if hotel_info["tbo_code"] and not df.empty:
        tbo_row = df[df["HotelCode"] == hotel_info["tbo_code"]]
        if not tbo_row.empty:
            row = tbo_row.iloc[0]
            facilities_raw = str(row.get("HotelFacilities", ""))
            if facilities_raw and facilities_raw != "nan":
                # Parse facility keywords
                facilities = _parse_facilities(facilities_raw)
                profile["facilities"] = facilities
                profile["facilities_raw"] = facilities_raw[:500]

            desc = str(row.get("Description", ""))
            if desc and desc != "nan":
                profile["description"] = desc[:500]

            profile["tbo_code"] = int(row["HotelCode"])

    # Competitive position
    comps = get_competitors(hotel_id, radius_km=2.0, limit=5)
    profile["nearby_hotels"] = comps.get("total_within_radius", 0)
    profile["nearby_rating_mix"] = comps.get("rating_breakdown", {})
    profile["closest_competitors"] = comps.get("competitors", [])[:5]

    return profile


def _parse_facilities(raw: str) -> dict:
    """Parse TBO facilities string into categorized amenities."""
    raw_lower = raw.lower()

    categories = {
        "pool": any(kw in raw_lower for kw in ["pool", "swimming"]),
        "fitness": any(kw in raw_lower for kw in ["fitness", "gym"]),
        "wifi": "wifi" in raw_lower or "internet" in raw_lower,
        "parking": "parking" in raw_lower,
        "restaurant": any(kw in raw_lower for kw in ["restaurant", "dining"]),
        "bar": "bar" in raw_lower or "lounge" in raw_lower,
        "spa": "spa" in raw_lower,
        "business_center": "business center" in raw_lower,
        "meeting_rooms": "meeting" in raw_lower or "conference" in raw_lower,
        "concierge": "concierge" in raw_lower,
        "beach_access": any(kw in raw_lower for kw in ["beach", "ocean"]),
        "airport_shuttle": "airport" in raw_lower and "shuttle" in raw_lower,
        "pet_friendly": "pet" in raw_lower,
        "wheelchair_accessible": "wheelchair" in raw_lower,
        "breakfast": "breakfast" in raw_lower,
        "valet_parking": "valet" in raw_lower,
        "24hr_front_desk": "24-hour front desk" in raw_lower,
        "laundry": "laundry" in raw_lower or "dry cleaning" in raw_lower,
        "elevator": "elevator" in raw_lower,
        "smoke_free": "smoke-free" in raw_lower,
    }

    return {
        "amenities": {k: v for k, v in categories.items() if v},
        "total_detected": sum(categories.values()),
    }


def get_all_profiles() -> list[dict]:
    """Get profiles for all SalesOffice hotels."""
    return [get_hotel_profile(hid) for hid in SALESOFFICE_HOTELS]


def get_knowledge_summary() -> dict:
    """Full knowledge base summary for dashboard/API."""
    market = get_market_summary()
    profiles = get_all_profiles()

    return {
        "market": market,
        "our_hotels": profiles,
        "salesoffice_hotel_count": len(SALESOFFICE_HOTELS),
    }
