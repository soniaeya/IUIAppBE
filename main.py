# main.py
from datetime import datetime, timezone
from typing import Optional, Dict

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query
from pymongo.errors import DuplicateKeyError

from gyms import GYMS
from models import (
    Preferences,
    MapLocation,
    UserCreate,
    UserOut,
    LoginRequest,
    MapSearch,
    UpdatePreferencesRequest,
    Rating,
    PreferencesIn,
    RatingIn, LocationUpdateRequest, TimeUpdateRequest, WeatherUpdateRequest, WeatherInfo,
)
from mongodb import users_collection, ratings_collection, weather_collection
from recommender_system import gyms_for_preferences


# -------------------------------------------------
# FastAPI app
# -------------------------------------------------
app = FastAPI()


# -------------------------------------------------
# In-memory "current user" state (for mobile session)
# -------------------------------------------------
class UserState:
    def __init__(self):
        self.user_id: Optional[str] = None
        self.email: Optional[str] = None

        # location
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None

        # preferences
        self.activities: list[str] = []
        self.env: Optional[str] = None
        self.intensity: Optional[str] = None
        self.time: Optional[datetime] = None

        # weather (optional)
        self.weather_main: Optional[str] = None
        self.weather_description: Optional[str] = None
        self.weather_temp_c: Optional[float] = None

    def set_user(self, user_id: str, email: str):
        self.user_id = user_id
        self.email = email

    def set_location(self, lat: float, lon: float):
        self.latitude = lat
        self.longitude = lon

    def set_preferences(self, prefs: Preferences):
        self.activities = prefs.activities
        self.env = prefs.env
        self.intensity = prefs.intensity
        self.time = prefs.time

    def set_weather(self, main: str, description: Optional[str], temp_c: Optional[float]):
        self.weather_main = main
        self.weather_description = description
        self.weather_temp_c = temp_c



current_user = UserState()





# -------------------------------------------------
# Helpers
# -------------------------------------------------
def user_doc_to_out(doc) -> UserOut:
    prefs_doc = doc.get("preferences")
    prefs_obj = Preferences(**prefs_doc) if prefs_doc else None

    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"],
        name=doc.get("name"),
        preferences=prefs_obj,
    )


# -------------------------------------------------
# Root
# -------------------------------------------------
@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/routes")
def list_routes():
    """
    Quick debug endpoint to see registered paths.
    """
    routes_info = []
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if path and methods:
            routes_info.append({"path": path, "methods": list(methods)})
    return routes_info


# -------------------------------------------------
# Preferences: POST create/update + PUT for explicit update
# -------------------------------------------------


# -------------------------------------------------
# Auth
# -------------------------------------------------
@app.post("/signup", response_model=UserOut)
def signup(user: UserCreate):
    """
    Basic signup – stores email + plain password (hash later).
    """
    existing = users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = {
        "email": user.email,
        "password": user.password,
        "name": user.name,
    }

    result = users_collection.insert_one(new_user)
    saved = users_collection.find_one({"_id": result.inserted_id})

    return user_doc_to_out(saved)


@app.post("/login")
def login(data: LoginRequest):
    """
    Simple login – verifies plain password, sets current_user info.
    """
    user = users_collection.find_one({"email": data.email})

    if not user or user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    current_user.set_user(str(user["_id"]), user["email"])

    return {
        "status": "ok",
        "message": "Login successful",
        "user_id": current_user.user_id,
        "email": current_user.email,
    }


# -------------------------------------------------
# Map search echo (optional)
# -------------------------------------------------
@app.put("/map/search")
def map_search(data: MapSearch):
    print("Received search query:", data.searchQuery)
    return {"status": "ok", "query": data.searchQuery}


# -------------------------------------------------
# Location endpoints (session + persistent)
# -------------------------------------------------
@app.post("/map/location")
def save_location(loc: MapLocation):
    """
    Body MUST be: { "latitude": <float>, "longitude": <float> }
    Uses current_user from session.
    """
    if not current_user.user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    # Update in-memory session
    current_user.set_location(loc.latitude, loc.longitude)

    # OPTIONAL: also persist to Mongo
    users_collection.update_one(
        {"_id": ObjectId(current_user.user_id)},
        {
            "$set": {
                "location": {
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                }
            }
        },
    )

    print("User location:", loc.latitude, loc.longitude)

    return {
        "status": "ok",
        "user_location": {
            "latitude": loc.latitude,
            "longitude": loc.longitude,
        },
    }


@app.get("/user/location", response_model=MapLocation)
def api_get_location(user_id: str = Query(...)):
    """
    Returns the stored location for a user.
    Frontend calls:
      GET /user/location?user_id=<mongo_id_string>
    """
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    loc = user.get("location")
    if not loc:
        raise HTTPException(status_code=404, detail="Location not set")

    # loc is {"latitude": ..., "longitude": ...}
    return MapLocation(**loc)


@app.put("/user/location", response_model=UserOut)
def api_update_location(payload: LocationUpdateRequest):
    """
    Writes the location into the user's MongoDB document.
    Body:
    {
      "user_id": "...",
      "location": { "latitude": 45.5, "longitude": -73.56 }
    }
    """
    loc = payload.location

    result = users_collection.update_one(
        {"_id": ObjectId(payload.user_id)},
        {
            "$set": {
                "location": {
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                }
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Also mirror into in-memory current_user
    if current_user.user_id == payload.user_id:
        current_user.set_location(loc.latitude, loc.longitude)

    saved = users_collection.find_one({"_id": ObjectId(payload.user_id)})
    return user_doc_to_out(saved)


@app.post("/api/update_location")
def update_location(data: dict):
    """
    Small helper endpoint; stores last_lat/last_lon.
    """
    user_id = data["user_id"]
    lat = data["lat"]
    lon = data["lon"]

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_lat": lat, "last_lon": lon}},
    )

    return {"status": "ok"}


# -------------------------------------------------
# Time update + read
# -------------------------------------------------
@app.put("/user/time", response_model=UserOut)
def api_update_time(payload: TimeUpdateRequest):
    user = users_collection.find_one({"_id": ObjectId(payload.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs_doc = user.get("preferences") or {}
    prefs_doc["time"] = payload.time  # store datetime

    users_collection.update_one(
        {"_id": ObjectId(payload.user_id)},
        {"$set": {"preferences": prefs_doc}},
    )

    if current_user.user_id == payload.user_id:
        current_user.time = payload.time

    saved = users_collection.find_one({"_id": ObjectId(payload.user_id)})
    return user_doc_to_out(saved)


@app.get("/user/time")
def api_get_time(user_id: str = Query(...)):
    """
    Returns raw `preferences.time` as stored in Mongo (can be datetime or ISO).
    Frontend that wants a canonical ISO string can use /api/preferences/ instead.
    """
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = user.get("preferences") or {}
    return {"time": prefs.get("time")}


@app.put("/user/weather")
def api_update_weather(payload: WeatherUpdateRequest):

    weather_collection.update_one(
        {"user_id": payload.user_id},
        {
            "$set": {
                "user_id": payload.user_id,     # ★ VERY IMPORTANT
                "main": payload.main,
                "description": payload.description,
                "temp_c": payload.temp_c,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True
    )

    return {"status": "ok", "weather": payload.dict()}


@app.get("/user/weather", response_model=WeatherInfo)
def api_get_weather(user_id: str = Query(..., description="Mongo user ID")):
    doc = weather_collection.find_one({"user_id": user_id})

    if not doc:
        raise HTTPException(status_code=404, detail="Weather not found for user")

    return WeatherInfo(
        main=doc.get("main"),
        description=doc.get("description"),
        temp_c=doc.get("temp_c")
    )

# -------------------------------------------------
# Recommendations
# -------------------------------------------------



@app.get("/recommendations")
def recommendations(user_id: str = Query(..., description="Mongo _id of the user as a string")):
    """
    Return a list of gym names recommended for this user.
    - looks up the user by user_id in MongoDB
    - reads user['preferences'] (activities, env, intensity, time)
    - optionally uses user['location'] for distance sorting
    - calls gyms_for_preferences(...)
    """
    # 1) Validate ObjectId
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # 2) Find user
    user = users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3) Ensure preferences exist
    prefs = user.get("preferences")
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences not set for this user")

    activities = prefs.get("activities") or []
    env = prefs.get("env")
    intensity = prefs.get("intensity")

    # 4) Optional: read location if stored
    location = user.get("location") or {}
    user_lat = location.get("latitude")
    user_lon = location.get("longitude")

    open_status: Dict[str, bool] = {gym["name"]: True for gym in GYMS}

    # 5) Call your recommender
    gym_names = gyms_for_preferences(
        activities=activities,
        env=env,
        intensity=intensity,
        user_lat=user_lat,
        user_lon=user_lon,
        user_id=user_id,  # ratings influence this user
        open_status=open_status,
    )

    return {"recommendations": gym_names}


# -------------------------------------------------
# Ratings
# -------------------------------------------------
@app.post("/api/ratings/")
def save_rating(rating: RatingIn):
    """
    Upsert a rating for (user_id, place_id).
    If the user rates the same place again, just update the rating.
    """
    try:
        result = ratings_collection.update_one(
            {"user_id": rating.user_id, "place_id": rating.place_id},  # match on user+place
            {
                "$set": {
                    "user_id": rating.user_id,
                    "place_id": rating.place_id,
                    "gym_name": rating.gym_name,
                    "rating": rating.rating,
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        return {
            "status": "ok",
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    except DuplicateKeyError as e:
        # Fallback in case of duplicate key issues.
        print("DuplicateKeyError in /api/ratings/:", e)
        ratings_collection.update_one(
            {"user_id": rating.user_id, "place_id": rating.place_id},
            {
                "$set": {
                    "gym_name": rating.gym_name,
                    "rating": rating.rating,
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=False,
        )
        return {"status": "ok", "note": "resolved duplicate key"}

    except Exception as e:
        print("Unexpected error in /api/ratings/:", e)
        raise HTTPException(status_code=500, detail="Error saving rating")


@app.get("/api/ratings/")
def get_ratings(user_id: str = Query(..., description="Mongo _id of the user as a string")):
    """
    Return all ratings for a given user as:
    {
      "ratings": {
        "<place_id_1>": 4,
        "<place_id_2>": 5,
        ...
      }
    }
    """
    docs = list(ratings_collection.find({"user_id": user_id}))

    ratings_map = {
        doc["place_id"]: doc.get("rating")
        for doc in docs
        if doc.get("place_id") is not None
    }

    return {"ratings": ratings_map}


# -------------------------------------------------
# Preferences GET (frontend uses this to pre-fill screen)
# -------------------------------------------------
@app.get("/api/preferences/")
def get_preferences(user_id: str = Query(..., description="Mongo _id of the user as a string")):
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = user.get("preferences")
    if not prefs:
        return {"preferences": None}

    # Normalize time to UTC ISO with Z so the frontend interprets it correctly
    t = prefs.get("time")
    if isinstance(t, datetime):
        # Mongo gives a naive datetime that is actually UTC
        t_utc = t.replace(tzinfo=timezone.utc)
        prefs["time"] = t_utc.isoformat().replace("+00:00", "Z")

    return {"preferences": prefs}


@app.post("/api/preferences/")
def save_preferences(prefs: PreferencesIn):
    """
    Save the user's activity preferences into their user document in MongoDB.
    Body:
    {
      "user_id": "...",
      "activities": [...],
      "env": "...",
      "intensity": "...",
      "time": <ISO datetime string>
    }
    """
    # 1) validate user_id is a proper ObjectId
    try:
        user_obj_id = ObjectId(prefs.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # 2) make sure user exists
    user = users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3) build preferences document
    prefs_doc = {
        "activities": prefs.activities,
        "env": prefs.env,
        "intensity": prefs.intensity,
        "time": prefs.time,  # datetime in Mongo
    }

    # 4) save into user document
    users_collection.update_one(
        {"_id": user_obj_id},
        {"$set": {"preferences": prefs_doc}},
    )

    return {"status": "ok", "preferences": prefs_doc}


@app.put("/user/preferences")
def update_preferences(data: UpdatePreferencesRequest): # Directly use UpdatePreferencesRequest
    try:
        user_obj_id = ObjectId(data.user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs_doc = {
        "activities": data.activities,
        "env": data.env,
        "intensity": data.intensity,
        "time": data.time,   # datetime stored in Mongo
    }

    result = users_collection.update_one(
        {"_id": user_obj_id},
        {"$set": {"preferences": prefs_doc}}
    )

    print("Matched:", result.matched_count)
    print("Modified:", result.modified_count)

    return {"status": "ok", "preferences": prefs_doc}