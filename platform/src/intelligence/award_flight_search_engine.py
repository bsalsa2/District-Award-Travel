import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

class AwardFlightSearchEngine:
    def __init__(self):
        self.flights = [
            {"id": 1, "origin": "JFK", "destination": "LAX", "price": 20000},
            {"id": 2, "origin": "LAX", "destination": "JFK", "price": 25000},
            {"id": 3, "origin": "ORD", "destination": "SFO", "price": 30000},
        ]

    def search_flights(self, origin: str, destination: str) -> List[Dict]:
        return [flight for flight in self.flights if flight["origin"] == origin and flight["destination"] == destination]

@app.get("/search_flights")
async def search_flights(origin: str, destination: str):
    search_engine = AwardFlightSearchEngine()
    flights = search_engine.search_flights(origin, destination)
    return JSONResponse(content={"flights": flights}, media_type="application/json")
