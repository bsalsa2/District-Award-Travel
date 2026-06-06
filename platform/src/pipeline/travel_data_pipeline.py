import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

class TravelDataPipeline:
    def __init__(self):
        self.travel_data = {}

    def fetch_travel_data(self, travel_preferences: Dict):
        # Simulate fetching travel data from external APIs
        # In a real-world scenario, this would involve API calls to external travel services
        travel_data = {
            "flights": [
                {"id": 1, "origin": "New York", "destination": "Los Angeles", "price": 200},
                {"id": 2, "origin": "New York", "destination": "Chicago", "price": 150},
            ],
            "hotels": [
                {"id": 1, "location": "Los Angeles", "price": 100},
                {"id": 2, "location": "Chicago", "price": 80},
            ],
        }

        return travel_data

    def process_travel_data(self, travel_data: Dict):
        # Process travel data to extract relevant information
        processed_data = {
            "flights": [
                {"id": flight["id"], "origin": flight["origin"], "destination": flight["destination"], "price": flight["price"]}
                for flight in travel_data["flights"]
            ],
            "hotels": [
                {"id": hotel["id"], "location": hotel["location"], "price": hotel["price"]}
                for hotel in travel_data["hotels"]
            ],
        }

        return processed_data

@app.get("/travel_data")
async def get_travel_data(travel_preferences: Dict):
    pipeline = TravelDataPipeline()
    travel_data = pipeline.fetch_travel_data(travel_preferences)
    processed_data = pipeline.process_travel_data(travel_data)

    return JSONResponse(content=processed_data, media_type="application/json")
