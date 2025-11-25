
# ----------------------------------
# Preferences
# ----------------------------------
from enum import Enum

class ActivityEnum(str, Enum):
    boxing = "Boxing"
    kickboxing = "Kickboxing"
    bjj = "BJJ"
    muay_thai = "Muay Thai"
    judo = "Judo"
    Wrestling = "Wrestling"



from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel



from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

class MapLocation(BaseModel):
    latitude: float
    longitude: float

class RatingIn(BaseModel):
    user_id: str
    place_id: str
    gym_name: str
    rating: int   # 1–5


class Preferences(BaseModel):
    activities: List[str] = []                # all active toggles
    env: Optional[str] = None                 # "Indoor" / "Outdoor"
    intensity: Optional[str] = None           # e.g. "Low", "Medium", "High"
    time: datetime

class PreferencesIn(BaseModel):
    user_id: str                  # from frontend
    activities: List[str]         # ["Boxing", "Relax", ...]
    env: str                      # "Indoor" / "Outdoor"
    intensity: str                # "Beginner", "Advanced", etc.
    time: datetime                # ISO string → datetime
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

# models.py
from pydantic import BaseModel, Field

class Rating(BaseModel):
    user_id: str                 # Mongo _id of the user as a string
    gym_name: str                # name from GYMS[i]["name"]
    rating: int = Field(ge=1, le=5)  # 1–5 stars, adjust if you want 0–10 etc.
