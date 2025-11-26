# recommender_system.py  (after GYMS = [...] )

from math import radians, sin, cos, asin, sqrt
from typing import List, Optional, Dict, Tuple
from gyms import GYMS
from mongodb import ratings_collection

# -----------------------------
# Feature vocabularies
# -----------------------------

# "type" is your activity: "Boxing", "Muay Thai", "Savate", "Parks", "Relax", "Eat"
ALL_TYPES = sorted({g.get("type") for g in GYMS if g.get("type")})
ALL_ENVS = sorted({g.get("env") for g in GYMS if g.get("env")})
ALL_LEVELS = sorted({lvl for g in GYMS for lvl in g.get("level", [])})

TYPE_INDEX = {t: i for i, t in enumerate(ALL_TYPES)}
ENV_INDEX = {
    e: i + len(ALL_TYPES)
    for i, e in enumerate(ALL_ENVS)
}
LEVEL_INDEX = {
    lvl: i + len(ALL_TYPES) + len(ALL_ENVS)
    for i, lvl in enumerate(ALL_LEVELS)
}

VECTOR_DIM = len(ALL_TYPES) + len(ALL_ENVS) + len(ALL_LEVELS)


# -----------------------------
# Encoding helpers
# -----------------------------

def _encode_gym(gym: dict) -> List[float]:
    """One-hot encode gym (type, env, level) into a vector."""
    vec = [0.0] * VECTOR_DIM

    g_type = gym.get("type")
    if g_type in TYPE_INDEX:
        vec[TYPE_INDEX[g_type]] = 1.0

    g_env = gym.get("env")
    if g_env in ENV_INDEX:
        vec[ENV_INDEX[g_env]] = 1.0

    for lvl in gym.get("level", []):
        if lvl in LEVEL_INDEX:
            vec[LEVEL_INDEX[lvl]] = 1.0

    return vec


def _encode_user(
    activities: Optional[List[str]],
    env: Optional[str],
    intensity: Optional[str],
) -> List[float]:
    """
    Use user's chosen activities (Boxing, Muay Thai, Parks, Relax, Eat),
    env, and intensity as a feature vector.
    """
    vec = [0.0] * VECTOR_DIM

    # activities: list like ["Boxing", "Muay Thai"]
    for act in activities or []:
        if act in TYPE_INDEX:
            vec[TYPE_INDEX[act]] = 1.0

    if env in ENV_INDEX:
        vec[ENV_INDEX[env]] = 1.0

    # optional: push on an approximate level from intensity
    # (if your intensity is "Low"/"Medium"/"High")
    if intensity:
        levels_for_intensity = []
        s = str(intensity).lower()
        if s.startswith("low") or s == "1":
            levels_for_intensity = [1]
        elif s.startswith("med") or s == "2":
            levels_for_intensity = [2]
        elif s.startswith("high") or s == "3":
            levels_for_intensity = [3]

        for lvl in levels_for_intensity:
            if lvl in LEVEL_INDEX:
                vec[LEVEL_INDEX[lvl]] = 1.0

    return vec


def _cosine(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = sum(a * a for a in v1) ** 0.5
    n2 = sum(b * b for b in v2) ** 0.5
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Distance in km between two lat/longs."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * asin(a**0.5)
    return R * c


# precompute gym vectors once
GYM_VECS: Dict[str, List[float]] = {
    g["name"]: _encode_gym(g) for g in GYMS
}


def _load_user_ratings(user_id: Optional[str]) -> Dict[str, float]:
    """
    Returns { gym_name: rating } from Mongo for this user.
    We join by gym_name (must match `name` in GYMS).
    """
    if not user_id:
        return {}

    docs = ratings_collection.find({"user_id": user_id})
    out = {}
    for d in docs:
        name = d.get("gym_name")
        rating = d.get("rating")
        if name and isinstance(rating, (int, float)):
            out[name] = float(rating)
    return out


def _match_intensity(gym: dict, intensity: Optional[str]) -> bool:
    """Filter: does this gym roughly match the user's intensity?"""
    if not intensity:
        return True

    gym_levels = gym.get("level", [])
    if not gym_levels:
        return True  # parks / relax / eat have [] → always ok

    s = str(intensity).lower()

    if s.startswith("low") or s == "1":
        wanted = [1]
    elif s.startswith("med") or s == "2":
        wanted = [2]
    elif s.startswith("high") or s == "3":
        wanted = [3]
    else:
        return True

    return any(lvl in gym_levels for lvl in wanted)


# -----------------------------
# Main API
# -----------------------------

def gyms_for_preferences(
    activities: Optional[List[str]],
    env: Optional[str],
    intensity: Optional[str],
    user_lat: Optional[float] = None,
    user_lon: Optional[float] = None,
    user_id: Optional[str] = None,
    top_k: int = 15,
) -> List[str]:
    """
    Content-based recommendations:
    - filter by user's activities, env, intensity
    - adjust similarity by user's past ratings
    - THEN recommend places that are *closest* to the user
      (primary sort: distance asc, secondary: similarity desc)
    """
    user_vec = _encode_user(activities, env, intensity)
    user_ratings = _load_user_ratings(user_id)

    # only consider positively rated gyms for personalization
    liked_gyms: List[Tuple[str, float]] = [
        (name, r) for name, r in user_ratings.items() if r >= 4.0
    ]

    # results will store (name, similarity_score, distance_km or None)
    results: List[Tuple[str, float, Optional[float]]] = []

    for gym in GYMS:
        # 1) HARD FILTERS based on preferences
        if activities:
            # keep only gyms whose type is one of user's activities
            if gym.get("type") not in activities:
                continue

        if env and gym.get("env") != env:
            continue

        if not _match_intensity(gym, intensity):
            continue

        name = gym["name"]
        g_vec = GYM_VECS[name]

        # 2) base similarity: user preferences vs gym
        base_sim = _cosine(user_vec, g_vec)

        # 3) ratings-based boost: similar to gyms the user liked
        rating_boost = 0.0
        for liked_name, rating in liked_gyms:
            liked_vec = GYM_VECS.get(liked_name)
            if not liked_vec:
                continue

            sim_to_liked = _cosine(g_vec, liked_vec)
            # center rating around 3 (1..5 scale): 1→-2, 3→0, 5→+2
            centered = rating - 3.0
            rating_boost += centered * sim_to_liked

        alpha = 0.1  # small weight for rating influence
        similarity_score = base_sim + alpha * rating_boost

        # 4) distance in km (if we know user location)
        dist_km: Optional[float] = None
        if user_lat is not None and user_lon is not None:
            dist_km = _haversine(user_lat, user_lon,
                                 gym["latitude"], gym["longitude"])

        results.append((name, similarity_score, dist_km))

    # 5) sort:
    #    - if we have distances, primary key = distance asc, secondary = similarity desc
    #    - otherwise, just sort by similarity desc
    if user_lat is not None and user_lon is not None:
        # gyms that somehow have no dist get shoved to the end with a large sentinel distance
        BIG = 1e9
        results.sort(
            key=lambda x: ((x[2] if x[2] is not None else BIG), -x[1])
        )
    else:
        results.sort(key=lambda x: x[1], reverse=True)

    # 6) filter out pure zero similarities (optional)
    filtered = [name for (name, sim, _) in results if sim > 0]

    # fallback: if everything was 0, just return in distance order / similarity order
    if not filtered:
        filtered = [name for (name, _, _) in results]

    return filtered[:top_k]

