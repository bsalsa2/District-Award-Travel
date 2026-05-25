from platform.src.pipeline.flight_data_api import FlightDataAPI
from platform.src.intelligence.award_flight_recommender import AwardFlightRecommender

class Pipeline:
    def __init__(self, api_url: str, api_key: str):
        self.flight_data_api = FlightDataAPI(api_url, api_key)
        self.award_flight_recommender = AwardFlightRecommender(self.flight_data_api)

    def run(self, origin: str, destination: str, departure_date: str) -> List[Dict]:
        recommended_flights = self.award_flight_recommender.recommend_flights(origin, destination, departure_date)
        return recommended_flights
