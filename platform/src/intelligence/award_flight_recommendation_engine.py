import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict

app = FastAPI()

class AwardFlightRecommendationEngine:
    def __init__(self):
        self.user_behavior_data = {}
        self.loyalty_program_data = {}

    def update_user_behavior(self, user_id: int, behavior_data: Dict):
        self.user_behavior_data[user_id] = behavior_data

    def update_loyalty_program(self, loyalty_program_data: Dict):
        self.loyalty_program_data = loyalty_program_data

    def get_recommendations(self, user_id: int) -> List[Dict]:
        user_behavior = self.user_behavior_data.get(user_id, {})
        loyalty_program = self.loyalty_program_data

        # Calculate personalized recommendations based on user behavior and loyalty program engagement
        recommendations = []
        for flight in loyalty_program.get("flights", []):
            score = self.calculate_score(user_behavior, flight)
            if score > 0:
                recommendations.append({"flight": flight, "score": score})

        return recommendations

    def calculate_score(self, user_behavior: Dict, flight: Dict) -> float:
        # Calculate a score based on user behavior and flight characteristics
        score = 0
        if user_behavior.get("preferred_airlines", []) and flight.get("airline") in user_behavior["preferred_airlines"]:
            score += 1
        if user_behavior.get("preferred_destinations", []) and flight.get("destination") in user_behavior["preferred_destinations"]:
            score += 1
        if user_behavior.get("preferred_travel_dates", []) and flight.get("travel_date") in user_behavior["preferred_travel_dates"]:
            score += 1

        return score

@app.get("/recommendations/{user_id}")
def get_recommendations(user_id: int):
    engine = AwardFlightRecommendationEngine()
    engine.update_user_behavior(user_id, {"preferred_airlines": ["AA", "UA"], "preferred_destinations": ["LAX", "JFK"], "preferred_travel_dates": ["2026-06-01", "2026-06-15"]})
    engine.update_loyalty_program({"flights": [{"airline": "AA", "destination": "LAX", "travel_date": "2026-06-01"}, {"airline": "UA", "destination": "JFK", "travel_date": "2026-06-15"}]})
    recommendations = engine.get_recommendations(user_id)
    return JSONResponse(content=recommendations, media_type="application/json")
