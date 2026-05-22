import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel

class AwardValuation(BaseModel):
    """Valuation model for award travel redemptions"""
    total_miles: int
    total_points: int
    cash_value: float
    redemption_value: float
    value_per_mile: float
    value_per_point: float
    opportunity_cost: float
    confidence_score: float
    notes: str

class UserPreferences(BaseModel):
    """User preferences for award travel"""
    preferred_airlines: List[str] = []
    preferred_hotel_chains: List[str] = []
    cabin_preference: str = "economy"
    max_connections: int = 2
    max_layover_hours: int = 4
    preferred_departure_times: List[str] = ["morning", "afternoon"]
    preferred_travel_months: List[int] = [1, 2, 3, 4, 5, 9, 10, 11, 12]
    max_price_difference: float = 0.3  # 30% more than cash price
    loyalty_program: str = "all"

class ValuationEngine:
    def __init__(self):
        # Load historical redemption data
        self.historical_redemptions = self._load_historical_data()

        # Valuation parameters
        self.mile_valuation = {
            "AA": 1.5,
            "DL": 1.6,
            "UA": 1.4,
            "BA": 1.8,
            "JL": 1.7,
            "QF": 1.6,
            "EK": 1.9,
            "LH": 1.5
        }

        self.point_valuation = {
            "HILTON": 0.6,
            "HYATT": 0.8,
            "MARRIOTT": 0.7,
            "IHG": 0.5
        }

        self.cabin_multipliers = {
            "economy": 1.0,
            "premium_economy": 1.5,
            "business": 2.5,
            "first": 3.5
        }

        self.seasonal_adjustments = {
            1: 1.1, 2: 1.1, 3: 1.0, 4: 0.9,
            5: 0.9, 6: 0.8, 7: 0.8, 8: 0.8,
            9: 0.9, 10: 1.0, 11: 1.1, 12: 1.2
        }

    def _load_historical_data(self) -> pd.DataFrame:
        """Load historical redemption data for valuation"""
        # In production, this would load from a database
        data = {
            "airline": ["AA", "DL", "UA", "BA", "AA", "DL"],
            "cabin": ["economy", "business", "first", "business", "economy", "premium_economy"],
            "miles_used": [35000, 70000, 120000, 80000, 25000, 50000],
            "cash_price": [450, 1200, 2500, 1500, 350, 800],
            "redemption_date": [
                "2023-01-15", "2023-02-20", "2023-03-10",
                "2023-04-05", "2023-05-12", "2023-06-18"
            ]
        }
        return pd.DataFrame(data)

    def calculate_flight_valuation(
        self,
        flight: Dict,
        user_prefs: UserPreferences,
        current_date: str = None
    ) -> AwardValuation:
        """Calculate valuation for a flight award"""
        if current_date is None:
            current_date = datetime.utcnow().strftime("%Y-%m-%d")

        departure_date = datetime.strptime(flight["departure_time"], "%H:%M")
        month = datetime.strptime(current_date, "%Y-%m-%d").month

        # Base valuation
        base_miles = flight["award_miles"]
        cabin_multiplier = self.cabin_multipliers.get(flight["cabin"], 1.0)

        # Airline-specific valuation
        airline_multiplier = self.mile_valuation.get(flight["airline"], 1.0)

        # Seasonal adjustment
        seasonal_adjustment = self.seasonal_adjustments.get(month, 1.0)

        # Calculate cash value
        cash_value = flight["award_miles"] * 0.01 * airline_multiplier * cabin_multiplier * seasonal_adjustment

        # Calculate redemption value (what it's worth to the user)
        redemption_value = cash_value * 0.8  # Awards are typically worth 80% of cash value

        # Calculate value per mile
        value_per_mile = redemption_value / base_miles

        # Opportunity cost calculation
        opportunity_cost = self._calculate_opportunity_cost(flight, user_prefs)

        # Confidence score based on multiple factors
        confidence_score = self._calculate_confidence_score(flight, user_prefs)

        # Generate notes
        notes = self._generate_valuation_notes(flight, user_prefs, value_per_mile, opportunity_cost)

        return AwardValuation(
            total_miles=base_miles,
            total_points=0,
            cash_value=round(cash_value, 2),
            redemption_value=round(redemption_value, 2),
            value_per_mile=round(value_per_mile, 4),
            value_per_point=0,
            opportunity_cost=round(opportunity_cost, 2),
            confidence_score=round(confidence_score, 2),
            notes=notes
        )

    def calculate_hotel_valuation(
        self,
        hotel: Dict,
        user_prefs: UserPreferences,
        current_date: str = None
    ) -> AwardValuation:
        """Calculate valuation for a hotel award"""
        if current_date is None:
            current_date = datetime.utcnow().strftime("%Y-%m-%d")

        month = datetime.strptime(current_date, "%Y-%m-%d").month

        # Base valuation
        base_points = hotel["award_points"]
        chain_multiplier = self.point_valuation.get(hotel["property_id"].split("-")[0], 0.6)

        # Seasonal adjustment
        seasonal_adjustment = self.seasonal_adjustments.get(month, 1.0)

        # Calculate cash value
        cash_value = base_points * 0.01 * chain_multiplier * seasonal_adjustment

        # Calculate redemption value
        redemption_value = cash_value * 0.85  # Hotels typically retain more value

        # Calculate value per point
        value_per_point = redemption_value / base_points

        # Opportunity cost calculation
        opportunity_cost = self._calculate_hotel_opportunity_cost(hotel, user_prefs)

        # Confidence score
        confidence_score = self._calculate_hotel_confidence_score(hotel, user_prefs)

        # Generate notes
        notes = self._generate_hotel_notes(hotel, user_prefs, value_per_point, opportunity_cost)

        return AwardValuation(
            total_miles=0,
            total_points=base_points,
            cash_value=round(cash_value, 2),
            redemption_value=round(redemption_value, 2),
            value_per_mile=0,
            value_per_point=round(value_per_point, 4),
            opportunity_cost=round(opportunity_cost, 2),
            confidence_score=round(confidence_score, 2),
            notes=notes
        )

    def _calculate_opportunity_cost(self, flight: Dict, user_prefs: UserPreferences) -> float:
        """Calculate the opportunity cost of using miles vs. paying cash"""
        # Get typical cash price for this route
        typical_cash_price = self._get_typical_cash_price(flight["departure"], flight["arrival"])

        if typical_cash_price <= 0:
            return 0

        # Calculate what the miles could be worth if used elsewhere
        miles_value = flight["award_miles"] * 0.01 * 1.5  # Conservative estimate

        # Opportunity cost is the difference
        return max(0, typical_cash_price - miles_value)

    def _calculate_hotel_opportunity_cost(self, hotel: Dict, user_prefs: UserPreferences) -> float:
        """Calculate opportunity cost for hotel awards"""
        # Get typical cash price for this property
        typical_cash_price = self._get_typical_hotel_price(hotel["property_id"])

        if typical_cash_price <= 0:
            return 0

        # Calculate what points could be worth if used elsewhere
        points_value = hotel["award_points"] * 0.01 * 0.8

        return max(0, typical_cash_price - points_value)

    def _calculate_confidence_score(self, flight: Dict, user_prefs: UserPreferences) -> float:
        """Calculate confidence score for flight valuation"""
        score = 0.7  # Base score

        # Airline preference
        if flight["airline"] in user_prefs.preferred_airlines:
            score += 0.15

        # Cabin preference
        if flight["cabin"] == user_prefs.cabin_preference:
            score += 0.1

        # Seasonal preference
        month = datetime.strptime(datetime.utcnow().strftime("%Y-%m-%d"), "%Y-%m-%d").month
        if month in user_prefs.preferred_travel_months:
            score += 0.05

        # Availability factor
        if flight["seats_available"] >= 3:
            score += 0.1

        return min(1.0, max(0.0, score))

    def _calculate_hotel_confidence_score(self, hotel: Dict, user_prefs: UserPreferences) -> float:
        """Calculate confidence score for hotel valuation"""
        score = 0.65  # Base score

        # Chain preference
        chain = hotel["property_id"].split("-")[0]
        if chain in user_prefs.preferred_hotel_chains:
            score += 0.2

        # Room type preference
        if "Deluxe" in hotel["room_type"] and user_prefs.cabin_preference == "business":
            score += 0.1

        # Availability factor
        if hotel["available_rooms"] >= 2:
            score += 0.05

        return min(1.0, max(0.0, score))

    def _get_typical_cash_price(self, origin: str, destination: str) -> float:
        """Get typical cash price for a route (simulated)"""
        # In production, this would query historical data
        routes = {
            ("JFK", "LAX"): 350,
            ("JFK", "LHR"): 800,
            ("LAX", "NRT"): 1200,
            ("ORD", "CDG"): 950,
            ("DFW", "HND"): 1400
        }
        return routes.get((origin, destination), 500)

    def _get_typical_hotel_price(self, property_id: str) -> float:
        """Get typical hotel price (simulated)"""
        prices = {
            "HILTON-123": 250,
            "HYATT-456": 300,
            "MARRIOTT-789": 280,
            "IHG-101": 200
        }
        return prices.get(property_id, 250)

    def _generate_valuation_notes(
        self,
        flight: Dict,
        user_prefs: UserPreferences,
        value_per_mile: float,
        opportunity_cost: float
    ) -> str:
        """Generate detailed notes about the valuation"""
        notes = []

        # Basic info
        notes.append(f"Flight {flight['flight_number']} from {flight['departure']} to {flight['arrival']}")

        # Value assessment
        if value_per_mile > 0.02:
            notes.append("Excellent value per mile")
        elif value_per_mile > 0.015:
            notes.append("Good value per mile")
        elif value_per_mile > 0.01:
            notes.append("Fair value per mile")
        else:
            notes.append("Poor value per mile - consider cash booking")

        # Opportunity cost
        if opportunity_cost > 200:
            notes.append(f"High opportunity cost: ${opportunity_cost:.2f} difference vs cash")
        elif opportunity_cost > 100:
            notes.append(f"Moderate opportunity cost: ${opportunity_cost:.2f} difference vs cash")

        # Airline preference
        if flight["airline"] in user_prefs.preferred_airlines:
            notes.append(f"Preferred airline: {flight['airline']}")

        # Cabin preference
        if flight["cabin"] == user_prefs.cabin_preference:
            notes.append(f"Preferred cabin: {flight['cabin']}")

        return " | ".join(notes)

    def _generate_hotel_notes(
        self,
        hotel: Dict,
        user_prefs: UserPreferences,
        value_per_point: float,
        opportunity_cost: float
    ) -> str:
        """Generate notes for hotel valuation"""
        notes = []

        notes.append(f"{hotel['property_name']} for {hotel['nights']} nights")

        if value_per_point > 0.01:
            notes.append("Excellent value per point")
        elif value_per_point > 0.008:
            notes.append("Good value per point")
        elif value_per_point > 0.005:
            notes.append("Fair value per point")
        else:
            notes.append("Poor value per point - consider cash booking")

        if opportunity_cost > 100:
            notes.append(f"High opportunity cost: ${opportunity_cost:.2f} difference vs cash")

        chain = hotel["property_id"].split("-")[0]
        if chain in user_prefs.preferred_hotel_chains:
            notes.append(f"Preferred chain: {chain}")

        return " | ".join(notes)

    def compare_options(
        self,
        options: List[Dict],
        user_prefs: UserPreferences,
        option_type: str = "flight"
    ) -> List[Dict]:
        """Compare multiple award options and rank them"""
        valuations = []

        for option in options:
            if option_type == "flight":
                valuation = self.calculate_flight_valuation(option, user_prefs)
            else:
                valuation = self.calculate_hotel_valuation(option, user_prefs)

            valuations.append({
                "option": option,
                "valuation": valuation.dict(),
                "rank": 0
            })

        # Sort by redemption value (descending)
        valuations.sort(key=lambda x: x["valuation"]["redemption_value"], reverse=True)

        # Assign ranks
        for i, val in enumerate(valuations):
            val["rank"] = i + 1

        return valuations
