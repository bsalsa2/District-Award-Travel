import requests
import json
from typing import Dict, List

class AirlineAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.airline.com/v1"

    def get_flight_info(self, flight_number: str, departure_date: str) -> Dict:
        url = f"{self.base_url}/flights/{flight_number}/{departure_date}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        return response.json()

    def get_flight_availability(self, flight_number: str, departure_date: str) -> List:
        url = f"{self.base_url}/flights/{flight_number}/{departure_date}/availability"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        return response.json()

    def get_airport_info(self, airport_code: str) -> Dict:
        url = f"{self.base_url}/airports/{airport_code}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        return response.json()
