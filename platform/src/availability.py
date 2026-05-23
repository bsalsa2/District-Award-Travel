import asyncio
import requests
from typing import Dict

class Availability:
    def __init__(self):
        self.availability_api_url = "https://api.example.com/availability"

    async def get_availability(self, origin: str, destination: str, travel_date: str, travel_class: str):
        # Send request to availability API
        response = requests.get(self.availability_api_url, params={
            "origin": origin,
            "destination": destination,
            "travel_date": travel_date,
            "travel_class": travel_class
        })

        # Parse response and return availability status
        availability_status = {}
        for route in response.json()["routes"]:
            availability_status[(route["origin"], route["destination"])] = route["available"]

        return availability_status
