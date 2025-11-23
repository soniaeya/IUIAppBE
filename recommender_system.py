from gyms import GYMS
from math import radians, sin, cos, asin, sqrt

# Map from your text intensity to the numeric "level" stored in gyms
INTENSITY_TO_LEVEL = {
    "Senior-Friendly": 0,   # special case, see logic below
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
}

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return distance in kilometers between two lat/lon points.
    Safe to call only with real numbers.
    """
    from math import radians, sin, cos, asin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # km
    return c * r

def gyms_for_preferences(activities, env, intensity, user_lat=None, user_lon=None):
    """
    Core recommender:
    - filters by env (Indoor / Outdoor)
    - filters by activity type (Boxing, Relax, etc.)
    - filters by intensity level when possible
    - optionally sorts by distance if user_lat / user_lon are set
    Returns a list of gym names.
    """
    target_level = INTENSITY_TO_LEVEL.get(intensity)

    results = []

    for gym in GYMS:
        # 1) Environment filter
        if env and gym.get("env", "").lower() != env.lower():
            continue

        # 2) Activity filter (gym["type"] is like "Boxing", "Relax", etc.)
        if activities and gym.get("type") not in activities:
            continue

        # 3) Intensity filter
        levels = gym.get("level", [])

        # If levels list is non-empty, we can filter by level.
        # Special case: "Senior-Friendly" (0) → don't filter by numeric level,
        # just let env/activity do the work.
        if target_level is not None and target_level > 0 and levels:
            if target_level not in levels:
                continue

        # 4) Distance (optional)
        distance_km = None
        if user_lat is not None and user_lon is not None:
            try:
                distance_km = haversine(
                    float(user_lat),
                    float(user_lon),
                    float(gym["latitude"]),
                    float(gym["longitude"]),
                )
            except (TypeError, ValueError):
                # If any coordinate is invalid, just skip distance
                distance_km = None

        results.append(
            {
                "name": gym["name"],
                "address": gym["address"],
                "distance_km": distance_km,
            }
        )

    # 5) Safe sort by distance only if we actually have distance values
    if user_lat is not None and user_lon is not None:
        results.sort(
            key=lambda g: g["distance_km"]
            if g["distance_km"] is not None
            else float("inf")
        )

    # You only need names for the frontend carousel
    return [g["name"] for g in results]