import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Define the award flight booking system model
class AwardFlightBookingSystem(BaseModel):
    user_id: int
    flight_id: int
    points: int

# Define the API endpoint to book an award flight
@app.post("/book_award_flight")
async def book_award_flight(award_flight_booking_system: AwardFlightBookingSystem):
    # Check if the user has enough points to book the flight
    if award_flight_booking_system.points < 10000:
        raise HTTPException(status_code=400, detail="Not enough points to book the flight")
    # Book the flight and deduct the points from the user's account
    return {"message": "Flight booked successfully"}
