import numpy as np
from platform.src.pipeline.airline_api import AirlineAPI

class FlightOptimizer:
    def __init__(self, airline_api: AirlineAPI):
        self.airline_api = airline_api

    def optimize_flights(self, origin: str, destination: str, departure_date: str) -> List[Dict]:
        flights = self.airline_api.get_flights(origin, destination, departure_date)
        optimized_flights = []
        for flight in flights:
            availability = self.airline_api.get_availability(flight["id"])
            if availability["available"]:
                optimized_flights.append({
                    "flight_id": flight["id"],
                    "price": flight["price"],
                    "availability": availability["available"]
                })
        return optimized_flights

    def get_best_flight(self, flights: List[Dict]) -> Dict:
        best_flight = min(flights, key=lambda x: x["price"])
        return best_flight
