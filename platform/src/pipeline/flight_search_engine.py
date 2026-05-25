from airline_api import AirlineAPI
from typing import List, Dict

class FlightSearchEngine:
    def __init__(self, airline_api: AirlineAPI):
        self.airline_api = airline_api

    def search_flights(self, origin: str, destination: str, departure_date: str) -> List[Dict]:
        flights = self.airline_api.get_flights(origin, destination, departure_date)
        return flights

    def get_flight_details(self, flight_id: str) -> Dict:
        flight_details = self.airline_api.get_flight_details(flight_id)
        return flight_details
