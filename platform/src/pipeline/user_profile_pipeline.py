import numpy as np
from typing import Dict
from platform.src.intelligence.user_profile import UserProfile
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserProfileRequest(BaseModel):
    user_id: int
    name: str
    email: str
    travel_history: Dict

@app.post("/user_profile")
def create_user_profile(user_profile_request: UserProfileRequest):
    user_profile = UserProfile(user_profile_request.user_id, user_profile_request.name, user_profile_request.email, user_profile_request.travel_history)
    return {"user_id": user_profile.user_id, "name": user_profile.name, "email": user_profile.email, "travel_history": user_profile.travel_history}

@app.get("/user_profile/{user_id}")
def get_user_profile(user_id: int):
    # Retrieve user profile from database
    user_profile = UserProfile(user_id, "John Doe", "john@example.com", {"New York": 2, "Los Angeles": 1})
    return {"user_id": user_profile.user_id, "name": user_profile.name, "email": user_profile.email, "travel_history": user_profile.travel_history}
