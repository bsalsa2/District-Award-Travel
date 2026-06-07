import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from typing import Dict

app = FastAPI()

# Define a data structure to store award flight bookings
class AwardFlightBooking:
    def __init__(self, booking_id: int, passenger_name: str, flight_number: str, booking_date: str):
        self.booking_id = booking_id
        self.passenger_name = passenger_name
        self.flight_number = flight_number
        self.booking_date = booking_date

# Initialize a dictionary to store award flight bookings
award_flight_bookings: Dict[int, AwardFlightBooking] = {}

# Define a function to cancel an award flight booking
def cancel_award_flight_booking(booking_id: int):
    if booking_id in award_flight_bookings:
        del award_flight_bookings[booking_id]
        return True
    else:
        return False

# Define a function to process a refund
def process_refund(booking_id: int, refund_amount: float):
    # Simulate a payment gateway refund process
    print(f"Processing refund for booking {booking_id} with amount {refund_amount}")
    return True

# Define a pipeline to cancel an award flight booking and process a refund
def award_flight_booking_cancellation_pipeline(booking_id: int, refund_amount: float):
    if cancel_award_flight_booking(booking_id):
        if process_refund(booking_id, refund_amount):
            return True
    return False

# Define a route to run the pipeline
@app.post("/run_pipeline")
async def run_pipeline_route(booking_id: int, refund_amount: float):
    if award_flight_booking_cancellation_pipeline(booking_id, refund_amount):
        return JSONResponse(content={"message": "Pipeline executed successfully"}, status_code=200)
    else:
        raise HTTPException(status_code=500, detail="Pipeline execution failed")
