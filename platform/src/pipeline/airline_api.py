import requests
import json
from typing import List, Dict

class AirlineAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.airline.com"

    def get_flights(self, origin: str, destination: str, departure_date: str) -> List[Dict]:
        url = f"{self.base_url}/flights"
        params = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "api_key": self.api_key
        }
        response = requests.get(url, params=params)
        return response.json()

    def get_availability(self, flight_id: str) -> Dict:
        url = f"{self.base_url}/flights/{flight_id}/availability"
        params = {
            "api_key": self.api_key
        }
        response = requests.get(url, params=params)
        return response.json()
