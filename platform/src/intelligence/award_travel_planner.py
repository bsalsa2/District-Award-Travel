import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

class AwardTravelPlanner:
    def __init__(self):
        self.destinations = []
        self.itineraries = []

    def add_destination(self, destination: Dict):
        self.destinations.append(destination)

    def add_itinerary(self, itinerary: Dict):
        self.itineraries.append(itinerary)

    def get_destinations(self):
        return self.destinations

    def get_itineraries(self):
        return self.itineraries

    def plan_travel(self, origin: str, destination: str, travel_dates: List[str]):
        # Use machine learning model to plan travel
        # For simplicity, we will just return a hardcoded itinerary
        return {
            "origin": origin,
            "destination": destination,
            "travel_dates": travel_dates,
            "flights": [
                {"departure": "JFK", "arrival": "LAX", "departure_time": "10:00 AM", "arrival_time": "1:00 PM"}
            ],
            "hotels": [
                {"name": "Hotel California", "check_in": "2026-05-25", "check_out": "2026-05-26"}
            ]
        }

award_travel_planner = AwardTravelPlanner()

@app.get("/destinations")
async def get_destinations():
    return award_travel_planner.get_destinations()

@app.get("/itineraries")
async def get_itineraries():
    return award_travel_planner.get_itineraries()

@app.post("/plan_travel")
async def plan_travel(origin: str, destination: str, travel_dates: List[str]):
    return award_travel_planner.plan_travel(origin, destination, travel_dates)
