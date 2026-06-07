import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

# Define a data structure to hold flight information
class Flight:
    def __init__(self, origin: str, destination: str, airline: str, award_price: int):
        self.origin = origin
        self.destination = destination
        self.airline = airline
        self.award_price = award_price

# Define a function to search for award flights
def search_award_flights(origin: str, destination: str) -> List[Flight]:
    # For demonstration purposes, return some sample flights
    flights = [
        Flight("JFK", "LAX", "American Airlines", 25000),
        Flight("JFK", "SFO", "United Airlines", 30000),
        Flight("LAX", "JFK", "Delta Air Lines", 20000),
    ]
    return [flight for flight in flights if flight.origin == origin and flight.destination == destination]

# Define a route to handle award flight booking search requests
@app.get("/award-flight-search")
async def award_flight_search(origin: str, destination: str):
    flights = search_award_flights(origin, destination)
    return JSONResponse(content=[{"origin": flight.origin, "destination": flight.destination, "airline": flight.airline, "award_price": flight.award_price} for flight in flights], media_type="application/json")
