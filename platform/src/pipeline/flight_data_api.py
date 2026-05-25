import requests
import json
from typing import List, Dict

class FlightDataAPI:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def get_flights(self, origin: str, destination: str, departure_date: str) -> List[Dict]:
        params = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "api_key": self.api_key
        }
        response = requests.get(self.api_url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return []

    def get_flight_details(self, flight_id: str) -> Dict:
        params = {
            "flight_id": flight_id,
            "api_key": self.api_key
        }
        response = requests.get(self.api_url + "/details", params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {}
