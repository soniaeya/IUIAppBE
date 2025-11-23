import pytz
from datetime import datetime

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from models import LoginRequest, MapSearch, Preferences, UserCreate, UserOut, UpdatePreferencesRequest, MapLocation
from mongodb import users_collection
from math import radians, sin, cos, asin, sqrt

from recommender_system import gyms_for_preferences

app = FastAPI()


class UserState:
    def __init__(self):
        self.user_id: str | None = None
        self.email: str | None = None

        # location
        self.latitude: float | None = None
        self.longitude: float | None = None

        # preferences
        self.activities: list[str] = []
        self.env: str | None = None
        self.intensity: str | None = None
        self.time: datetime | None = None

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

current_user = UserState()

@app.get("/")
def root():
    return {"message": "API is running"}

@app.post("/api/preferences/")
def save_preferences(prefs: Preferences):
    current_user.set_preferences(prefs)

    print("Activities:", current_user.activities)
    print("Env:", current_user.env)
    print("Intensity:", current_user.intensity)
    print("Time:", current_user.time)

    return {"status": "ok", "saved": prefs.model_dump()}



def user_doc_to_out(doc) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"]
    )


@app.post("/signup", response_model=UserOut)
def signup(user: UserCreate):
    # Check if email already exists
    existing = users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = {
        "email": user.email,
        "password": user.password
    }

    result = users_collection.insert_one(new_user)
    saved = users_collection.find_one({"_id": result.inserted_id})

    return user_doc_to_out(saved)


@app.post("/login")
def login(data: LoginRequest):
    user = users_collection.find_one({"email": data.email})

    if not user or user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    current_user.set_user(str(user["_id"]), user["email"])

    return {
        "status": "ok",
        "message": "Login successful",
        "user_id": current_user.user_id,
        "email": current_user.email
    }


@app.put("/map/search")
def map_search(data: MapSearch):
    print("Received search query:", data.searchQuery)
    return {"status": "ok", "query": data.searchQuery}

@app.put("/user/preferences")
def update_preferences(data: UpdatePreferencesRequest):
    user_id = data.user_id
    prefs = data.preferences.dict()

    # Convert datetime to string if needed
    prefs["time"] = prefs["time"].isoformat()

    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"preferences": prefs}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "ok", "preferences": prefs}

@app.post("/map/location")
def save_location(loc: MapLocation):
    current_user.set_location(loc.latitude, loc.longitude)

    print("User location:", current_user.latitude, current_user.longitude)

    return {
        "status": "ok",
        "user_location": {
            "latitude": current_user.latitude,
            "longitude": current_user.longitude
        }
    }


@app.get("/recommendations")
def get_recommendations():
    # Ensure preferences exist
    if not current_user.activities or not current_user.env or not current_user.intensity:
        raise HTTPException(status_code=400, detail="User preferences not set")

    # (Location may or may not be set → recommender handles both cases)
    user_lat = current_user.latitude
    user_lon = current_user.longitude

    try:
        gym_names = gyms_for_preferences(
            activities=current_user.activities,
            env=current_user.env,
            intensity=current_user.intensity,
            user_lat=user_lat,
            user_lon=user_lon,
        )
        return {"status": "ok", "gyms": gym_names}
    except Exception as e:
        # This prevents ugly tracebacks and makes debugging easier.
        print("Error computing recommendations:", repr(e))
        # If something truly unexpected happens, still return a clean message.
        raise HTTPException(status_code=500, detail="Internal recommender error")
