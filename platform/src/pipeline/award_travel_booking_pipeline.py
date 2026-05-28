import numpy as np
from typing import Dict
from platform.src.intelligence.award_travel_booking import AwardTravelBooking
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AwardTravelBookingRequest(BaseModel):
    user_id: int
    booking_data: Dict

@app.post("/award_travel_booking")
def create_award_travel_booking(award_travel_booking_request: AwardTravelBookingRequest):
    user_profile = UserProfile(award_travel_booking_request.user_id, "John Doe", "john@example.com", {"New York": 2, "Los Angeles": 1})
    award_travel_booking = AwardTravelBooking(user_profile, award_travel_booking_request.booking_data)
    return {"recommendations": award_travel_booking.get_recommendations()}

@app.get("/award_travel_booking/{user_id}")
def get_award_travel_booking(user_id: int):
    # Retrieve award travel booking from database
    user_profile = UserProfile(user_id, "John Doe", "john@example.com", {"New York": 2, "Los Angeles": 1})
    award_travel_booking = AwardTravelBooking(user_profile, {"New York": 0.5, "Los Angeles": 0.3})
    return {"recommendations": award_travel_booking.get_recommendations()}
