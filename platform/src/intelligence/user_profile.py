import numpy as np
from typing import Dict

class UserProfile:
    def __init__(self, user_id: int, name: str, email: str, travel_history: Dict):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.travel_history = travel_history

    def get_travel_preferences(self):
        # Calculate travel preferences based on travel history
        preferences = {}
        for destination, frequency in self.travel_history.items():
            preferences[destination] = frequency / sum(self.travel_history.values())
        return preferences

    def update_travel_history(self, new_destination: str):
        if new_destination in self.travel_history:
            self.travel_history[new_destination] += 1
        else:
            self.travel_history[new_destination] = 1
