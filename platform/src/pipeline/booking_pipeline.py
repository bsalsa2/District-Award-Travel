import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class BookingRequest(BaseModel):
    itinerary: list
    award_type: str

class BookingPipeline:
    def __init__(self):
        self.booking_data = {}

    def book_travel(self, booking_request: BookingRequest):
        # Implement booking logic here
        # For demonstration purposes, return a sample response
        return {
            "booking_id": "BK123",
            "itinerary": booking_request.itinerary,
            "award_type": booking_request.award_type,
            "booking_status": "confirmed"
        }

booking_pipeline = BookingPipeline()

@app.post("/book_travel")
async def book_travel(booking_request: BookingRequest):
    return booking_pipeline.book_travel(booking_request)
