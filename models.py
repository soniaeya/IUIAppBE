
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

class MapLocation(BaseModel):
    latitude: float
    longitude: float



from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class Preferences(BaseModel):
    activities: List[str] = []                # all active toggles
    env: Optional[str] = None                 # "Indoor" / "Outdoor"
    intensity: Optional[str] = None           # e.g. "Low", "Medium", "High"
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
    user_id: str               # who are we updating?
    preferences: Preferences
