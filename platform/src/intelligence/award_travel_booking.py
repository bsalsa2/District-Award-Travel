import numpy as np
from typing import Dict
from platform.src.intelligence.user_profile import UserProfile

class AwardTravelBooking:
    def __init__(self, user_profile: UserProfile, booking_data: Dict):
        self.user_profile = user_profile
        self.booking_data = booking_data

    def get_recommendations(self):
        # Calculate recommendations based on user profile and booking data
        recommendations = []
        for destination, frequency in self.user_profile.get_travel_preferences().items():
            if destination in self.booking_data:
                recommendations.append((destination, frequency * self.booking_data[destination]))
        return sorted(recommendations, key=lambda x: x[1], reverse=True)

    def book_travel(self, destination: str):
        # Book travel based on user profile and destination
        # Update user travel history
        self.user_profile.update_travel_history(destination)
        return f"Travel booked to {destination}"
