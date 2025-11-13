import pytz
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

class Preferences(BaseModel):
    activity: str
    env: str    # "Indoor" / "Outdoor"
    time: datetime            # "Morning" / "Evening" or specific time

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
        "formatted": time_str
    }

