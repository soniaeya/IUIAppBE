import pytz
from datetime import datetime

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from models import LoginRequest, MapSearch, Preferences, UserCreate, UserOut, UpdatePreferencesRequest
from mongodb import users_collection

app = FastAPI()


@app.get("/")
def root():
    return {"message": "API is running"}

@app.post("/api/preferences/")
def save_preferences(prefs: Preferences):
    print("All activities:", prefs.activities)
    print("Env:", prefs.env)
    print("Intensity:", prefs.intensity)
    print("Time:", prefs.time)

    # here you’d save to MongoDB / SQL, etc.
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
    password = users_collection.find_one({"password": data.password})
    if not user or not password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "status": "ok",
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "email": user["email"]
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
