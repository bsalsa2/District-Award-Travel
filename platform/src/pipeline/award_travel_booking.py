import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class AwardTravelBooking(BaseModel):
    id: int
    user_id: int
    travel_date: str
    destination: str
    award_points: int

class AwardTravelBookingManager:
    def __init__(self):
        self.award_travel_bookings = {}

    def create_award_travel_booking(self, booking_id, user_id, travel_date, destination, award_points):
        if booking_id in self.award_travel_bookings:
            raise HTTPException(status_code=400, detail="Award travel booking already exists")
        self.award_travel_bookings[booking_id] = AwardTravelBooking(id=booking_id, user_id=user_id, travel_date=travel_date, destination=destination, award_points=award_points)
        return self.award_travel_bookings[booking_id]

    def get_award_travel_booking(self, booking_id):
        if booking_id not in self.award_travel_bookings:
            raise HTTPException(status_code=404, detail="Award travel booking not found")
        return self.award_travel_bookings[booking_id]

    def update_award_travel_booking(self, booking_id, travel_date, destination, award_points):
        if booking_id not in self.award_travel_bookings:
            raise HTTPException(status_code=404, detail="Award travel booking not found")
        self.award_travel_bookings[booking_id].travel_date = travel_date
        self.award_travel_bookings[booking_id].destination = destination
        self.award_travel_bookings[booking_id].award_points = award_points
        return self.award_travel_bookings[booking_id]

    def delete_award_travel_booking(self, booking_id):
        if booking_id not in self.award_travel_bookings:
            raise HTTPException(status_code=404, detail="Award travel booking not found")
        del self.award_travel_bookings[booking_id]

award_travel_booking_manager = AwardTravelBookingManager()

@app.post("/award_travel_bookings/")
async def create_award_travel_booking(booking_id: int, user_id: int, travel_date: str, destination: str, award_points: int):
    return award_travel_booking_manager.create_award_travel_booking(booking_id, user_id, travel_date, destination, award_points)

@app.get("/award_travel_bookings/{booking_id}")
async def get_award_travel_booking(booking_id: int):
    return award_travel_booking_manager.get_award_travel_booking(booking_id)

@app.put("/award_travel_bookings/{booking_id}")
async def update_award_travel_booking(booking_id: int, travel_date: str, destination: str, award_points: int):
    return award_travel_booking_manager.update_award_travel_booking(booking_id, travel_date, destination, award_points)

@app.delete("/award_travel_bookings/{booking_id}")
async def delete_award_travel_booking(booking_id: int):
    award_travel_booking_manager.delete_award_travel_booking(booking_id)
    return {"message": "Award travel booking deleted successfully"}
