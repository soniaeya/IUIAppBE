from pydantic import BaseModel
from datetime import datetime


# ----------------------------------
# Preferences
# ----------------------------------
class Preferences(BaseModel):
    activity: str               # e.g., "Gym", "Martial arts", "Yoga"
    env: str                    # "Indoor" or "Outdoor"
    time: datetime              # ISO datetime from frontend


# ----------------------------------
# Auth / Users
# ----------------------------------
class UserCreate(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class MapSearch(BaseModel):
    searchQuery: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    preferences: Preferences | None = None   # ⭐ attach preferences here

class UpdatePreferencesRequest(BaseModel):
    user_id: str               # who are we updating?
    preferences: Preferences
