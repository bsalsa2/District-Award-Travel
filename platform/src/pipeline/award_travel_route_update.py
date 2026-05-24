import numpy as np
from platform.src.intelligence.user_profile import UserProfile
from typing import Dict, List

class AwardTravelRouteUpdate:
    def __init__(self):
        self.user_profiles = {}

    def update_user_profile(self, user_id: int, flight_id: int, route: str):
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id)
        self.user_profiles[user_id].add_booked_flight(flight_id, route)

    def update_travel_history(self, user_id: int, flight_id: int, route: str, travel_date: str):
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id)
        self.user_profiles[user_id].add_travel_history(flight_id, route, travel_date)

    def get_user_profile(self, user_id: int) -> UserProfile:
        return self.user_profiles.get(user_id)
