"""Hotel segmentation — zone + tier classification for peer comparison.

Each hotel is assigned a zone (geographic area) and tier (price level).
Signals and benchmarks should compare within the same segment, not globally.

Example: Pullman Airport ($113 avg) should compare against Airport zone peers,
         not against South Beach luxury ($1,100 avg).
"""

# Zone → description + typical ADR range
ZONES = {
    "south_beach": {
        "name": "South Beach",
        "description": "Art Deco District, Ocean Drive, Collins Ave (1st-23rd St)",
        "adr_range": "$150-$500",
    },
    "mid_beach": {
        "name": "Mid-Beach",
        "description": "Quieter luxury stretch, Fontainebleau area (23rd-63rd St)",
        "adr_range": "$200-$600",
    },
    "downtown": {
        "name": "Downtown Miami",
        "description": "Central business district, Bayside, AmericanAirlines Arena",
        "adr_range": "$120-$350",
    },
    "brickell": {
        "name": "Brickell",
        "description": "Financial district, upscale high-rises, south of Miami River",
        "adr_range": "$150-$500",
    },
    "airport": {
        "name": "Airport / Doral",
        "description": "MIA airport area, NW 36th St corridor, Blue Lagoon",
        "adr_range": "$80-$200",
    },
    "sunny_isles": {
        "name": "Sunny Isles / North Beach",
        "description": "North of Miami Beach, resort towers",
        "adr_range": "$150-$400",
    },
}

# Tier → price positioning within zone
TIERS = {
    "budget": {"name": "Budget", "description": "Hostels, basic hotels", "stars": "1-2"},
    "midscale": {"name": "Midscale", "description": "Standard hotels, limited service", "stars": "3"},
    "upscale": {"name": "Upscale", "description": "Full-service, good amenities", "stars": "4"},
    "luxury": {"name": "Luxury", "description": "Premium, high-end, boutique luxury", "stars": "4.5-5"},
}

# Hotel ID → segment mapping for our 23 active hotels
HOTEL_SEGMENTS = {
    # South Beach
    66814:  {"zone": "south_beach", "tier": "midscale",  "name": "Breakwater South Beach"},
    173508: {"zone": "south_beach", "tier": "midscale",  "name": "Cadet Hotel"},
    64390:  {"zone": "south_beach", "tier": "midscale",  "name": "Crystal Beach Suites Hotel"},
    241025: {"zone": "south_beach", "tier": "upscale",   "name": "Dream South Beach"},
    333502: {"zone": "south_beach", "tier": "upscale",   "name": "Eurostars Langford Hotel"},
    117491: {"zone": "south_beach", "tier": "midscale",  "name": "FAIRWIND HOTEL & SUITES"},
    6660:   {"zone": "south_beach", "tier": "budget",    "name": "Freehand Miami"},
    22034:  {"zone": "south_beach", "tier": "luxury",    "name": "Hilton Bentley Miami South Beach"},
    314212: {"zone": "south_beach", "tier": "upscale",   "name": "Hyatt Centric South Beach Miami"},
    383277: {"zone": "south_beach", "tier": "midscale",  "name": "Iberostar Berkeley Shore Hotel"},
    6663:   {"zone": "south_beach", "tier": "midscale",  "name": "Marseilles Hotel"},
    64309:  {"zone": "south_beach", "tier": "midscale",  "name": "Savoy Hotel"},
    848677: {"zone": "south_beach", "tier": "upscale",   "name": "The Gabriel Miami South Beach"},
    31709:  {"zone": "south_beach", "tier": "budget",    "name": "Viajero Miami"},

    # South Beach — boutique/luxury
    88282:  {"zone": "south_beach", "tier": "luxury",    "name": "Sole Miami, A Noble House Resort"},

    # Mid-Beach
    24989:  {"zone": "mid_beach",   "tier": "upscale",   "name": "Hotel Riu Plaza Miami Beach"},

    # Downtown
    24982:  {"zone": "downtown",    "tier": "upscale",   "name": "Hilton Miami Downtown"},
    855865: {"zone": "downtown",    "tier": "upscale",   "name": "The Grayson Hotel Miami Downtown"},

    # Brickell
    852120: {"zone": "brickell",    "tier": "luxury",    "name": "SLS LUX Brickell"},
    853382: {"zone": "brickell",    "tier": "midscale",  "name": "Atwell Suites Miami Brickell"},
    854881: {"zone": "brickell",    "tier": "midscale",  "name": "citizenM Miami Brickell"},

    # Airport
    6805:   {"zone": "airport",     "tier": "upscale",   "name": "Pullman Miami Airport"},
    20702:  {"zone": "airport",     "tier": "upscale",   "name": "Embassy Suites by Hilton MIA"},
}


def get_hotel_segment(hotel_id: int):
    """Get zone + tier for a hotel. Returns None if not mapped."""
    seg = HOTEL_SEGMENTS.get(hotel_id)
    if not seg:
        return None
    zone_info = ZONES.get(seg["zone"], {})
    tier_info = TIERS.get(seg["tier"], {})
    return {
        "hotel_id": hotel_id,
        "hotel_name": seg["name"],
        "zone": seg["zone"],
        "zone_name": zone_info.get("name", ""),
        "zone_adr_range": zone_info.get("adr_range", ""),
        "tier": seg["tier"],
        "tier_name": tier_info.get("name", ""),
        "tier_stars": tier_info.get("stars", ""),
    }


def get_peer_hotels(hotel_id: int, same_zone: bool = True, same_tier: bool = False) -> list[int]:
    """Get peer hotel IDs for comparison.

    Default: same zone, any tier (geographic peers).
    Optional: same zone + same tier (closest peers).
    """
    seg = HOTEL_SEGMENTS.get(hotel_id)
    if not seg:
        return []
    peers = []
    for hid, hseg in HOTEL_SEGMENTS.items():
        if hid == hotel_id:
            continue
        if same_zone and hseg["zone"] != seg["zone"]:
            continue
        if same_tier and hseg["tier"] != seg["tier"]:
            continue
        peers.append(hid)
    return peers


def get_zone_hotels(zone: str) -> list[dict]:
    """Get all hotels in a zone."""
    return [
        {"hotel_id": hid, **seg}
        for hid, seg in HOTEL_SEGMENTS.items()
        if seg["zone"] == zone
    ]
