import numpy as np

class AwardRedemptionRecommender:
    def __init__(self, miles_balances, travel_goals, flexible_dates):
        self.miles_balances = miles_balances
        self.travel_goals = travel_goals
        self.flexible_dates = flexible_dates

    def get_recommendations(self):
        # Define a list of possible award redemption options
        award_redemptions = [
            {"program_used": "United MileagePlus", "partner_airline": "Lufthansa", "route": "SFO-FRA", "estimated_miles": 55_000, "estimated_taxes_usd": 100, "value_score": 0.8},
            {"program_used": "American Airlines AAdvantage", "partner_airline": "Qatar Airways", "route": "JFK-DOH", "estimated_miles": 70_000, "estimated_taxes_usd": 200, "value_score": 0.7},
            {"program_used": "Delta SkyMiles", "partner_airline": "Air France", "route": "LAX-CDG", "estimated_miles": 60_000, "estimated_taxes_usd": 150, "value_score": 0.6},
            # Add more award redemption options here...
        ]

        # Apply rule-based logic to filter and rank award redemption options
        filtered_redemptions = []
        for redemption in award_redemptions:
            if self.miles_balances.get(redemption["program_used"], 0) >= redemption["estimated_miles"]:
                if redemption["route"] in self.travel_goals:
                    filtered_redemptions.append(redemption)

        # Sort filtered redemptions by value score
        filtered_redemptions.sort(key=lambda x: x["value_score"], reverse=True)

        # Return top 3 recommendations
        return filtered_redemptions[:3]

    def get_reasoning(self, recommendation):
        return f"Recommended {recommendation['program_used']} award redemption for {recommendation['route']} due to sufficient miles balance and high value score."

def get_recommendations(miles_balances, travel_goals, flexible_dates):
    recommender = AwardRedemptionRecommender(miles_balances, travel_goals, flexible_dates)
    recommendations = recommender.get_recommendations()
    for recommendation in recommendations:
        recommendation["reasoning"] = recommender.get_reasoning(recommendation)
    return recommendations
