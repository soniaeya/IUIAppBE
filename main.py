import pytz
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mongodb import users_collection, hash_password, verify_password

app = FastAPI()


# ---------- Preferences (your existing endpoint) ----------

class Preferences(BaseModel):
    activity: str
    env: str    # "Indoor" / "Outdoor"
    time: datetime  # ISO datetime from frontend


@app.get("/")
def root():
    return {"message": "API is running"}


@app.post("/api/preferences/")
def save_preferences(prefs: Preferences):
    montreal = pytz.timezone("America/Toronto")  # same zone for Montreal
    local_dt = prefs.time.astimezone(montreal)
    time_str = local_dt.strftime("%H:%M")

    print("Activity:", prefs.activity)
    print("Environment:", prefs.env)
    print("Time:", time_str)

    return {
        "status": "ok",
        "activity": prefs.activity,
        "env": prefs.env,
        "formatted": time_str,
    }


# ---------- Auth / Users (MongoDB) ----------

class UserCreate(BaseModel):
    # use str so you don't get 422 from invalid email formats
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None


def user_doc_to_out(doc) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"],
        name=doc.get("name"),
    )


@app.post("/signup", response_model=UserOut)
def signup(user: UserCreate):
    # Check if email already exists
    existing = users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password and insert
    hashed = hash_password(user.password)
    new_user = {
        "email": user.email,
        "password_hash": hashed,
        "name": user.name,
    }

    result = users_collection.insert_one(new_user)
    saved = users_collection.find_one({"_id": result.inserted_id})

    return user_doc_to_out(saved)


@app.post("/login")
def login(data: LoginRequest):
    user = users_collection.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "status": "ok",
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name"),
    }
