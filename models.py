from enum import Enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ----------------------------------
# Activity enum
# ----------------------------------
class ActivityEnum(str, Enum):
    boxing = "Boxing"
    muay_thai = "Muay Thai"   # fix spelling
    savate = "Savate"
    parks = "Parks"
    relax = "Relax"
    eat = "Eat"


# ----------------------------------
# Map / Ratings
# ----------------------------------
class MapLocation(BaseModel):
    latitude: float
    longitude: float


class RatingIn(BaseModel):
    user_id: str
    place_id: str
    gym_name: str
    rating: int   # 1–5


# ----------------------------------
# Preferences
# ----------------------------------
class Preferences(BaseModel):
    # ⬇️ now uses the enum for validation
    activities: List[str] = []         # all active toggles
    env: Optional[str] = None                   # "Indoor" / "Outdoor"
    intensity: Optional[str] = None             # e.g. "Low", "Medium", "High"
    time: datetime                              # stored as datetime in Mongo


class PreferencesIn(BaseModel):
    # payload used by POST /api/preferences/ (if you still use it)
    user_id: str
    activities: List[str]
    env: str
    intensity: str
    time: datetime


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
    user_id: str
    activities: List[str]
    env: str
    intensity: str
    time: datetime


# ----------------------------------
# Ratings
# ----------------------------------
class Rating(BaseModel):
    user_id: str
    gym_name: str
    rating: int = Field(ge=1, le=5)
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


class WeatherInfo(BaseModel):
    main: str
    description: Optional[str] = None
    temp_c: Optional[float] = None