import asyncio
import requests
from typing import Dict

class Pricing:
    def __init__(self):
        self.pricing_api_url = "https://api.example.com/pricing"

    async def get_prices(self, origin: str, destination: str, travel_date: str, travel_class: str):
        # Send request to pricing API
        response = requests.get(self.pricing_api_url, params={
            "origin": origin,
            "destination": destination,
            "travel_date": travel_date,
            "travel_class": travel_class
        })

        # Parse response and return prices
        prices = {}
        for route in response.json()["routes"]:
            prices[(route["origin"], route["destination"])] = route["price"]

        return prices
