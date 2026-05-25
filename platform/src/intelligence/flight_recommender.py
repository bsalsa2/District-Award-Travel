import numpy as np
from platform.src.pipeline.airline_api import AirlineAPI

class FlightRecommender:
    def __init__(self, airline_api: AirlineAPI):
        self.airline_api = airline_api

    def recommend_flights(self, origin: str, destination: str, departure_date: str) -> List:
        flights = self.airline_api.get_flight_info(origin, destination, departure_date)
        recommended_flights = []
        for flight in flights:
            if flight["availability"] > 0:
                recommended_flights.append(flight)
        return recommended_flights

    def get_flight_scores(self, flights: List) -> List:
        scores = []
        for flight in flights:
            score = self.calculate_flight_score(flight)
            scores.append(score)
        return scores

    def calculate_flight_score(self, flight: Dict) -> float:
        # Calculate a score based on flight duration, price, and availability
        duration = flight["duration"]
        price = flight["price"]
        availability = flight["availability"]
        score = (1 / duration) * (1 / price) * availability
        return score
