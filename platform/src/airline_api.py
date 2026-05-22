import asyncio
import requests

class AirlineAPI:
    def __init__(self):
        self.api_key = settings.AIRLINE_API_KEY
        self.api_secret = settings.AIRLINE_API_SECRET
        self.base_url = "https://api.airline.com"

    async def connect(self):
        # No connection needed for REST API
        pass

    async def get_award_prices(self):
        response = requests.get(f"{self.base_url}/award-prices", auth=(self.api_key, self.api_secret))
        return response.json()

    async def get_award_availability(self):
        response = requests.get(f"{self.base_url}/award-availability", auth=(self.api_key, self.api_secret))
        return response.json()
