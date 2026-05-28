import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TravelPreference(BaseModel):
    cabin_class: str
    preferred_airlines: List[str]
    preferred_routes: List[str]
    price_range: Tuple[int, int]
    travel_frequency: int  # trips per year
    preferred_times: List[str]  # ['morning', 'afternoon', 'evening']
    max_points_to_spend: int

class UserBehavior(BaseModel):
    search_history: List[Dict[str, any]]
    booking_history: List[Dict[str, any]]
    click_history: List[Dict[str, any]]
    last_active: str
    session_duration: int  # minutes

class AwardBookingFeatures(BaseModel):
    route: str
    airline: str
    cabin_class: str
    price_in_points: int
    duration_minutes: int
    departure_time: str
    arrival_time: str
    available_seats: int
    days_until_departure: int
    is_weekend: bool
    is_holiday: bool

class MatchingModel:
    def __init__(self):
        # Initialize model weights (in production, these would be trained)
        self.weights = {
            'cabin_class': 0.25,
            'airline': 0.20,
            'route': 0.25,
            'price': 0.15,
            'duration': 0.10,
            'time': 0.05
        }

        # Pre-trained airline preferences (would be learned from data)
        self.airline_preferences = {
            'AA': 0.92, 'DL': 0.88, 'UA': 0.85, 'BA': 0.95,
            'JL': 0.89, 'NH': 0.83, 'EK': 0.93, 'QR': 0.90,
            'LH': 0.87, 'AF': 0.84, 'KL': 0.86, 'SQ': 0.94
        }

        # Pre-trained route preferences (would be learned from data)
        self.route_preferences = {
            'JFK-LAX': 0.91, 'LAX-JFK': 0.91,
            'SFO-NRT': 0.88, 'NRT-SFO': 0.88,
            'LHR-JFK': 0.93, 'JFK-LHR': 0.93,
            'SIN-NRT': 0.87, 'NRT-SIN': 0.87,
            'DXB-JFK': 0.89, 'JFK-DXB': 0.89
        }

    def extract_features(self, booking: AwardBookingFeatures) -> Dict[str, float]:
        """Extract normalized features for matching"""
        features = {}

        # Cabin class (one-hot encoding)
        cabin_weights = {'economy': 0.7, 'premium_economy': 0.8, 'business': 0.9, 'first': 1.0}
        features['cabin_class'] = cabin_weights.get(booking.cabin_class, 0.7)

        # Airline preference
        features['airline'] = self.airline_preferences.get(booking.airline, 0.5)

        # Route preference
        features['route'] = self.route_preferences.get(booking.route, 0.5)

        # Price normalization (lower is better)
        max_points = 200000  # Maximum possible points
        normalized_price = 1.0 - (booking.price_in_points / max_points)
        features['price'] = max(0.0, min(1.0, normalized_price))

        # Duration normalization (shorter is better)
        max_duration = 1800  # 30 hours in minutes
        normalized_duration = 1.0 - (booking.duration_minutes / max_duration)
        features['duration'] = max(0.0, min(1.0, normalized_duration))

        # Time of day preference (morning=0.9, afternoon=0.8, evening=0.7)
        time_weights = {'morning': 0.9, 'afternoon': 0.8, 'evening': 0.7}
        features['time'] = time_weights.get(booking.departure_time.split()[1].lower(), 0.7)

        return features

    def calculate_match_score(self, user_prefs: TravelPreference, booking: AwardBookingFeatures) -> float:
        """Calculate overall match score between user and booking"""
        features = self.extract_features(booking)

        # Weighted sum of features
        score = (
            features['cabin_class'] * self.weights['cabin_class'] +
            features['airline'] * self.weights['airline'] +
            features['route'] * self.weights['route'] +
            features['price'] * self.weights['price'] +
            features['duration'] * self.weights['duration'] +
            features['time'] * self.weights['time']
        )

        # Additional factors
        if booking.available_seats < 2:
            score *= 0.8  # Less attractive if few seats left

        if booking.days_until_departure < 7:
            score *= 1.2  # More attractive if departing soon

        if booking.is_weekend:
            score *= 1.1  # Weekend travel is often preferred

        if booking.is_holiday:
            score *= 1.3  # Holiday travel is high priority

        return round(score, 3)

    def generate_recommendation_reasons(self, score: float, user_prefs: TravelPreference, booking: AwardBookingFeatures) -> List[str]:
        """Generate human-readable reasons for the match"""
        reasons = []
        threshold = 0.7

        if score >= threshold:
            reasons.append("High match score")

        if booking.cabin_class == user_prefs.cabin_class:
            reasons.append(f"Same cabin class: {booking.cabin_class}")

        if booking.airline in user_prefs.preferred_airlines:
            reasons.append(f"Preferred airline: {booking.airline}")

        if booking.route in user_prefs.preferred_routes:
            reasons.append(f"Preferred route: {booking.route}")

        if (user_prefs.price_range[0] <= booking.price_in_points <= user_prefs.price_range[1]):
            reasons.append("Price within your range")

        if booking.duration_minutes <= 600:  # 10 hours
            reasons.append("Reasonable flight duration")

        if booking.available_seats >= 5:
            reasons.append("Good seat availability")

        if score > 0.85:
            reasons.append("Exceptional match!")

        return reasons if reasons else ["Good match based on your preferences"]

class DynamicPreferenceLearner:
    """Learns and adapts to user preferences over time"""
    def __init__(self):
        self.user_profiles = {}  # user_id -> TravelPreference

    def update_preferences(self, user_id: str, new_bookings: List[Dict[str, any]]):
        """Update user preferences based on their booking history"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = TravelPreference(
                cabin_class='economy',
                preferred_airlines=[],
                preferred_routes=[],
                price_range=(0, 100000),
                travel_frequency=2,
                preferred_times=['morning', 'afternoon'],
                max_points_to_spend=50000
            )

        profile = self.user_profiles[user_id]

        # Update based on bookings
        cabin_classes = {}
        airlines = {}
        routes = {}
        prices = []
        durations = []

        for booking in new_bookings:
            # Cabin class
            cabin_classes[booking.get('cabin_class', 'economy')] = cabin_classes.get(booking.get('cabin_class', 'economy'), 0) + 1

            # Airlines
            airline = booking.get('airline', 'Unknown')
            airlines[airline] = airlines.get(airline, 0) + 1

            # Routes
            route = booking.get('route', 'Unknown')
            routes[route] = routes.get(route, 0) + 1

            # Price range
            prices.append(booking.get('price_in_points', 0))

            # Duration
            durations.append(booking.get('duration_minutes', 0))

        # Update most frequent cabin class
        if cabin_classes:
            most_common_cabin = max(cabin_classes.items(), key=lambda x: x[1])[0]
            profile.cabin_class = most_common_cabin

        # Update preferred airlines (top 3)
        if airlines:
            sorted_airlines = sorted(airlines.items(), key=lambda x: x[1], reverse=True)[:3]
            profile.preferred_airlines = [a[0] for a in sorted_airlines]

        # Update preferred routes (top 3)
        if routes:
            sorted_routes = sorted(routes.items(), key=lambda x: x[1], reverse=True)[:3]
            profile.preferred_routes = [r[0] for r in sorted_routes]

        # Update price range (25th to 75th percentile)
        if prices:
            sorted_prices = sorted(prices)
            lower = sorted_prices[int(len(sorted_prices) * 0.25)]
            upper = sorted_prices[int(len(sorted_prices) * 0.75)]
            profile.price_range = (lower, upper)

        # Update travel frequency (average trips per year)
        if new_bookings:
            profile.travel_frequency = len(new_bookings) / 2  # Assuming 2 years of history

        profile.last_updated = datetime.utcnow().isoformat()
        logger.info(f"Updated preferences for user {user_id}")

    def get_adjusted_match_score(self, user_id: str, base_score: float, booking: AwardBookingFeatures) -> float:
        """Adjust base match score based on dynamic user preferences"""
        if user_id not in self.user_profiles:
            return base_score

        profile = self.user_profiles[user_id]

        # Boost score for preferred airlines
        if booking.airline in profile.preferred_airlines:
            base_score = min(1.0, base_score * 1.15)

        # Boost score for preferred routes
        if booking.route in profile.preferred_routes:
            base_score = min(1.0, base_score * 1.20)

        # Penalize if price is outside range
        if not (profile.price_range[0] <= booking.price_in_points <= profile.price_range[1]):
            base_score = max(0.1, base_score * 0.7)

        return round(base_score, 3)

# Singleton instances
matching_model = MatchingModel()
preference_learner = DynamicPreferenceLearner()
