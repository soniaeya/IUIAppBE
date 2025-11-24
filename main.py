# main.py
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi import Query

from models import (
    Preferences,
    MapLocation,
    UserCreate,
    UserOut,
    LoginRequest,
    MapSearch,
    UpdatePreferencesRequest,
)
from mongodb import users_collection
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
# Extra update models
# -------------------------------------------------
class LocationUpdateRequest(BaseModel):
    user_id: str
    location: MapLocation  # uses your existing MapLocation model


class TimeUpdateRequest(BaseModel):
    user_id: str
    time: datetime


class WeatherUpdateRequest(BaseModel):
    user_id: str
    main: str
    description: Optional[str] = None
    temp_c: Optional[float] = None


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


# -------------------------------------------------
# Preferences: mobile POST (session) + DB PUT (by user_id)
# -------------------------------------------------
@app.post("/api/preferences/")
def save_preferences(prefs: Preferences):
    """
    Called by the mobile app when the user saves preferences
    on the Preferences screen.

    - Updates in-memory current_user
    - Returns what was saved
    """
    current_user.set_preferences(prefs)

    print("Activities:", current_user.activities)
    print("Env:", current_user.env)
    print("Intensity:", current_user.intensity)
    print("Time:", current_user.time)

    return {"status": "ok", "saved": prefs.model_dump()}


@app.put("/user/preferences")
def update_preferences(data: UpdatePreferencesRequest):
    """
    Writes preferences into the user's document in MongoDB.
    """
    user_id = data.user_id
    prefs = data.preferences.model_dump()

    # Convert datetime to ISO for Mongo
    if prefs.get("time"):
        prefs["time"] = prefs["time"].isoformat()

    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"preferences": prefs}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "ok", "preferences": prefs}


# -------------------------------------------------
# Auth
# -------------------------------------------------
@app.post("/signup", response_model=UserOut)
def signup(user: UserCreate):
    """
    Basic signup – stores email + plain password (you can plug hashing later).
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
# Location endpoints
# -------------------------------------------------
@app.post("/map/location")
def save_location(loc: MapLocation):
    """
    Body MUST be: { "latitude": <float>, "longitude": <float> }
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




# -------------------------------------------------
# Time update
# -------------------------------------------------
@app.put("/user/time", response_model=UserOut)
def api_update_time(payload: TimeUpdateRequest):
    """
    Updates only the time of day in the user's preferences.
    """
    user = users_collection.find_one({"_id": ObjectId(payload.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs_doc = user.get("preferences") or {}
    prefs_doc["time"] = payload.time.isoformat()

    users_collection.update_one(
        {"_id": ObjectId(payload.user_id)},
        {"$set": {"preferences": prefs_doc}},
    )

    if current_user.user_id == payload.user_id:
        current_user.time = payload.time

    saved = users_collection.find_one({"_id": ObjectId(payload.user_id)})
    return user_doc_to_out(saved)


# -------------------------------------------------
# Weather update
# -------------------------------------------------
@app.put("/user/weather")
def api_update_weather(payload: WeatherUpdateRequest):
    """
    Stores the latest weather forecast for this user.
    """
    users_collection.update_one(
        {"_id": ObjectId(payload.user_id)},
        {
            "$set": {
                "weather": {
                    "main": payload.main,
                    "description": payload.description,
                    "temp_c": payload.temp_c,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            }
        },
    )

    if current_user.user_id == payload.user_id:
        current_user.set_weather(payload.main, payload.description, payload.temp_c)

    return {"status": "ok", "weather": payload.dict()}


# -------------------------------------------------
# Recommendations
# -------------------------------------------------
@app.get("/recommendations")
def get_recommendations():
    """
    Uses current_user's in-memory preferences + location to
    get a list of matching gym names from recommender_system.gyms_for_preferences.
    """
    if not current_user.activities or not current_user.env or not current_user.intensity:
        raise HTTPException(status_code=400, detail="User preferences not set")

    gym_names = gyms_for_preferences(
        activities=current_user.activities,
        env=current_user.env,
        intensity=current_user.intensity,
        user_lat=current_user.latitude,
        user_lon=current_user.longitude,
    )

    print("Matched locations:", gym_names)

    return {
        "status": "ok",
        "gyms": gym_names,
    }




# -------------------------------------------------
# Location endpoints
# -------------------------------------------------

@app.post("/map/location")
def save_location(loc: MapLocation):
    """
    Body MUST be: { "latitude": <float>, "longitude": <float> }
    Also stores location on the currently logged-in user.
    """
    if not current_user.user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    # Update in-memory session
    current_user.set_location(loc.latitude, loc.longitude)

    # Persist to Mongo
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
