import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class FlightRequest(BaseModel):
    departure: str
    arrival: str
    date: str

class FlightResponse(BaseModel):
    flight_number: str
    departure_time: str
    arrival_time: str
    airline: str

def get_flight_info(flight_request: FlightRequest):
    url = "https://api.flight-scheduler.com/flights"
    params = {
        "departure": flight_request.departure,
        "arrival": flight_request.arrival,
        "date": flight_request.date
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=404, detail="Flights not found")

@app.post("/flights", response_model=FlightResponse)
def get_flights(flight_request: FlightRequest):
    flight_info = get_flight_info(flight_request)
    return flight_info
