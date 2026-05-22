"""
AR Travel Planner - AI Engine for Immersive Award Travel Planning
Uses computer vision, ML, and real-time data to provide AR-based travel planning.
"""

import numpy as np
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
from dataclasses import dataclass
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ARTravelPlanner")

class TravelClass(Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

class TravelType(Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
    CAR_RENTAL = "car_rental"
    PACKAGE = "package"

@dataclass
class TravelPoint:
    """Represents a point in 3D space for AR visualization"""
    x: float
    y: float
    z: float
    label: str
    confidence: float = 1.0

@dataclass
class AwardOpportunity:
    """Represents an award travel opportunity"""
    id: str
    title: str
    description: str
    airline: str
    departure: str
    arrival: str
    departure_date: datetime
    return_date: datetime
    travel_class: TravelClass
    price_in_points: int
    cash_price: float
    availability: int
    duration_days: int
    route_distance: float
    ar_points: List[TravelPoint]
    thumbnail_url: str
    is_featured: bool = False
    tags: List[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "airline": self.airline,
            "departure": self.departure,
            "arrival": self.arrival,
            "departure_date": self.departure_date.isoformat(),
            "return_date": self.return_date.isoformat(),
            "travel_class": self.travel_class.value,
            "price_in_points": self.price_in_points,
            "cash_price": self.cash_price,
            "availability": self.availability,
            "duration_days": self.duration_days,
            "route_distance": self.route_distance,
            "ar_points": [{"x": p.x, "y": p.y, "z": p.z, "label": p.label, "confidence": p.confidence} for p in self.ar_points],
            "thumbnail_url": self.thumbnail_url,
            "is_featured": self.is_featured,
            "tags": self.tags or []
        }

class ARTravelPlanner:
    """
    Core AR Travel Planning Engine with AI valuation models.
    Handles real-time availability, pricing updates, and AR visualization.
    """

    def __init__(self):
        self.opportunities: Dict[str, AwardOpportunity] = {}
        self.user_preferences: Dict[str, any] = {}
        self.valuation_model = self._load_valuation_model()
        self.availability_cache = {}
        self.price_updates = asyncio.Queue()
        self.metrics = {
            "total_opportunities": 0,
            "avg_price": 0,
            "search_count": 0,
            "ar_render_time": 0.0
        }
        logger.info("AR Travel Planner initialized")

    def _load_valuation_model(self) -> Dict:
        """Load or initialize the AI valuation model"""
        # In production, this would load a trained ML model
        # For now, we use a heuristic-based model
        return {
            "base_multiplier": 1.0,
            "seasonality_factors": {
                "peak": 1.5,
                "shoulder": 1.2,
                "low": 0.8
            },
            "class_multipliers": {
                TravelClass.ECONOMY: 1.0,
                TravelClass.PREMIUM_ECONOMY: 1.8,
                TravelClass.BUSINESS: 3.5,
                TravelClass.FIRST: 6.0
            }
        }

    async def update_real_time_pricing(self):
        """Background task to update pricing from external sources"""
        while True:
            update = await self.price_updates.get()
            opportunity_id = update.get("opportunity_id")
            new_price = update.get("new_price")

            if opportunity_id in self.opportunities:
                old_price = self.opportunities[opportunity_id].price_in_points
                self.opportunities[opportunity_id].price_in_points = new_price
                self.opportunities[opportunity_id].cash_price = new_price * 0.01  # Simplified conversion

                logger.info(f"Price updated for {opportunity_id}: {old_price} -> {new_price} points")

                # Update metrics
                self.metrics["avg_price"] = sum(
                    op.price_in_points for op in self.opportunities.values()
                ) / max(1, len(self.opportunities))

            self.price_updates.task_done()

    def calculate_award_value(self, opportunity: AwardOpportunity) -> float:
        """
        Calculate the value score for an award opportunity using AI model.
        Higher score = better value for award points.
        """
        # Base value calculation
        base_value = opportunity.price_in_points

        # Apply seasonality factor
        month = opportunity.departure_date.month
        if month in [12, 1, 2, 7, 8]:
            season = "peak"
        elif month in [3, 4, 5, 9, 10]:
            season = "shoulder"
        else:
            season = "low"

        seasonality_factor = self.valuation_model["seasonality_factors"][season]

        # Apply class multiplier
        class_multiplier = self.valuation_model["class_multipliers"][opportunity.travel_class]

        # Calculate value score (lower points = better value)
        value_score = (base_value * seasonality_factor * class_multiplier) / max(1, opportunity.duration_days)

        # Normalize by distance
        if opportunity.route_distance > 0:
            value_score = value_score / opportunity.route_distance

        return value_score

    def generate_ar_visualization(self, opportunity: AwardOpportunity) -> List[TravelPoint]:
        """
        Generate 3D points for AR visualization based on travel route.
        This creates a visual path the user can follow in AR.
        """
        ar_points = []

        # Departure point
        ar_points.append(TravelPoint(
            x=0, y=0, z=0,
            label=f"🛫 {opportunity.departure}",
            confidence=1.0
        ))

        # Intermediate points along the route
        num_intermediate = min(5, max(1, int(opportunity.route_distance / 500)))
        for i in range(1, num_intermediate + 1):
            x = (i / (num_intermediate + 1)) * 10
            y = np.sin(i * 0.5) * 2
            z = np.cos(i * 0.3) * 1.5

            label = f"✈️ Route {i}/{num_intermediate}"
            ar_points.append(TravelPoint(x=x, y=y, z=z, label=label, confidence=0.95))

        # Arrival point
        ar_points.append(TravelPoint(
            x=10, y=0, z=0,
            label=f"🛬 {opportunity.arrival}",
            confidence=1.0
        ))

        # Add hotel/car rental points if part of package
        if opportunity.travel_type == TravelType.PACKAGE:
            ar_points.append(TravelPoint(
                x=8, y=2, z=1,
                label="🏨 Hotel",
                confidence=0.9
            ))
            ar_points.append(TravelPoint(
                x=9, y=-1, z=0.5,
                label="🚗 Car Rental",
                confidence=0.85
            ))

        return ar_points

    def search_opportunities(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        departure_date: Optional[datetime] = None,
        return_date: Optional[datetime] = None,
        travel_class: Optional[TravelClass] = None,
        max_price: Optional[int] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        limit: int = 20
    ) -> List[AwardOpportunity]:
        """
        Search for award travel opportunities with AI-powered ranking.
        Returns results sorted by best value.
        """
        self.metrics["search_count"] += 1
        start_time = datetime.now()

        candidates = []

        for opp in self.opportunities.values():
            # Apply filters
            if origin and origin.lower() not in [opp.departure.lower(), opp.arrival.lower()]:
                continue
            if destination and destination.lower() not in [opp.departure.lower(), opp.arrival.lower()]:
                continue
            if departure_date and abs((opp.departure_date - departure_date).days) > 7:
                continue  # Within 7 days
            if travel_class and opp.travel_class != travel_class:
                continue
            if max_price and opp.price_in_points > max_price:
                continue
            if min_duration and opp.duration_days < min_duration:
                continue
            if max_duration and opp.duration_days > max_duration:
                continue

            candidates.append(opp)

        # Calculate value scores and sort
        for opp in candidates:
            opp.value_score = self.calculate_award_value(opp)

        # Sort by value score (lower is better) and availability
        candidates.sort(key=lambda x: (x.value_score, -x.availability))

        # Apply limit
        results = candidates[:limit]

        # Update metrics
        if results:
            self.metrics["ar_render_time"] = (datetime.now() - start_time).total_seconds()

        logger.info(f"Search returned {len(results)} results in {self.metrics['ar_render_time']:.3f}s")
        return results

    def get_opportunity_details(self, opportunity_id: str) -> Optional[AwardOpportunity]:
        """Get detailed information about a specific opportunity"""
        return self.opportunities.get(opportunity_id)

    def add_opportunity(self, opportunity: AwardOpportunity):
        """Add a new award opportunity to the system"""
        opportunity.id = opportunity.id or str(uuid.uuid4())
        opportunity.ar_points = self.generate_ar_visualization(opportunity)
        opportunity.value_score = self.calculate_award_value(opportunity)

        self.opportunities[opportunity.id] = opportunity
        self.metrics["total_opportunities"] += 1
        self.metrics["avg_price"] = sum(
            op.price_in_points for op in self.opportunities.values()
        ) / max(1, len(self.opportunities))

        logger.info(f"Added new opportunity: {opportunity.id}")

    def update_user_preferences(self, preferences: Dict):
        """Update user preferences for personalized recommendations"""
        self.user_preferences.update(preferences)
        logger.info(f"Updated user preferences: {preferences}")

    def get_personalized_recommendations(self, user_id: str) -> List[AwardOpportunity]:
        """
        Generate personalized recommendations based on user preferences
        and historical behavior (simulated for now)
        """
        if not self.user_preferences:
            return self.search_opportunities(limit=10)

        # Simple preference-based filtering
        recommendations = []

        for opp in self.opportunities.values():
            # Check if matches preferences
            matches = True

            if "preferred_airlines" in self.user_preferences:
                if opp.airline not in self.user_preferences["preferred_airlines"]:
                    matches = False

            if "preferred_classes" in self.user_preferences:
                if opp.travel_class.value not in self.user_preferences["preferred_classes"]:
                    matches = False

            if matches:
                recommendations.append(opp)

        # Sort by value score
        recommendations.sort(key=lambda x: x.value_score)

        return recommendations[:15]

    def get_ar_session_config(self, opportunity_id: str) -> Dict:
        """
        Generate AR session configuration for WebXR
        """
        opp = self.get_opportunity_details(opportunity_id)
        if not opp:
            return {}

        return {
            "opportunity": opp.to_dict(),
            "ar_points": [p.__dict__ for p in opp.ar_points],
            "initial_camera_position": [0, 1.6, 2],  # Eye level
            "initial_camera_lookat": [5, 0, 0],  # Looking down the route
            "ambient_light": "#404040",
            "directional_light": {
                "color": "#ffffff",
                "intensity": 1.5,
                "position": [10, 20, 10]
            },
            "background": "#000000",
            "interaction_distance": 5.0,
            "max_points_rendered": 50
        }

    def get_system_metrics(self) -> Dict:
        """Get performance metrics for the AR travel planner"""
        return {
            **self.metrics,
            "cache_size": len(self.availability_cache),
            "loaded_opportunities": len(self.opportunities),
            "user_preferences_set": bool(self.user_preferences),
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
ar_planner = ARTravelPlanner()
