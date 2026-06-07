from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from platform.src.intelligence.award_flight_booking_system import AwardFlightBookingSystem
from platform.src.intelligence.award_flight_cancellation_system import AwardFlightCancellationSystem
from platform.src.models import AwardFlightBooking, AwardFlightCancellation

app = FastAPI()

def get_award_flight_booking_system():
    return AwardFlightBookingSystem()

def get_award_flight_cancellation_system():
    return AwardFlightCancellationSystem()

@app.post("/cancel-award-flight")
async def cancel_award_flight(
    award_flight_booking_id: int,
    award_flight_cancellation_system: AwardFlightCancellationSystem = Depends(get_award_flight_cancellation_system),
    award_flight_booking_system: AwardFlightBookingSystem = Depends(get_award_flight_booking_system)
):
    award_flight_booking = award_flight_booking_system.get_award_flight_booking(award_flight_booking_id)
    if award_flight_booking:
        award_flight_cancellation = award_flight_cancellation_system.cancel_award_flight(award_flight_booking)
        return JSONResponse(content={"message": "Award flight cancelled successfully"}, status_code=200)
    else:
        return JSONResponse(content={"message": "Award flight booking not found"}, status_code=404)
