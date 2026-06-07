"""
Award points calculation engine with tiered loyalty program
"""
import numpy as np
from typing import Dict, Tuple, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PointsCalculator:
    """
    Advanced award points calculator with:
    - Tiered loyalty program (bronze, silver, gold, platinum)
    - Distance-based calculations
    - Seasonal multipliers
    - Partner airline bonuses
    """

    def __init__(self):
        # Tier multipliers
        self.tier_multipliers = {
            'bronze': 1.0,
            'silver': 1.2,
            'gold': 1.5,
            'platinum': 2.0
        }

        # Seasonal multipliers (quarterly)
        self.seasonal_multipliers = {
            1: 1.0,  # Q1
            2: 1.1,  # Q2
            3: 1.0,  # Q3
            4: 1.2   # Q4 (holiday season)
        }

        # Partner airline bonuses
        self.partner_bonuses = {
            'AA': 1.1,  # American Airlines
            'DL': 1.15, # Delta
            'UA': 1.05, # United
            'BA': 1.2,  # British Airways
            'EK': 1.3,  # Emirates
            'JL': 1.1   # Japan Airlines
        }

        # Base points per mile (economy)
        self.base_points_per_mile = 0.1

        # Cabin class multipliers
        self.cabin_multipliers = {
            'economy': 1.0,
            'premium_economy': 1.5,
            'business': 2.0,
            'first': 3.0
        }

    def calculate_points(
        self,
        distance_miles: float,
        cabin_class: str,
        airline: str,
        user_tier: str,
        departure_date: Optional[datetime] = None,
        is_partner: bool = False
    ) -> Tuple[int, Dict]:
        """
        Calculate award points for a flight

        Returns:
            Tuple of (total_points, calculation_details)
        """
        # Validate inputs
        if distance_miles <= 0:
            raise ValueError("Distance must be positive")

        if cabin_class not in self.cabin_multipliers:
            raise ValueError(f"Invalid cabin class: {cabin_class}")

        if user_tier not in self.tier_multipliers:
            raise ValueError(f"Invalid user tier: {user_tier}")

        # Calculate base points
        base_points = distance_miles * self.base_points_per_mile
        base_points = int(np.round(base_points))

        # Apply cabin class multiplier
        cabin_multiplier = self.cabin_multipliers[cabin_class]
        cabin_points = int(np.round(base_points * cabin_multiplier))

        # Apply airline partner bonus
        airline_bonus = self.partner_bonuses.get(airline, 1.0)
        airline_points = int(np.round(cabin_points * airline_bonus))

        # Apply tier multiplier
        tier_multiplier = self.tier_multipliers[user_tier]
        tier_points = int(np.round(airline_points * tier_multiplier))

        # Apply seasonal multiplier if date provided
        seasonal_multiplier = 1.0
        if departure_date:
            quarter = (departure_date.month - 1) // 3 + 1
            seasonal_multiplier = self.seasonal_multipliers[quarter]
            seasonal_points = int(np.round(tier_points * seasonal_multiplier))
        else:
            seasonal_points = tier_points

        # Calculate final points
        final_points = seasonal_points

        # Create calculation details
        calculation_details = {
            'base_points': base_points,
            'cabin_class': cabin_class,
            'cabin_multiplier': cabin_multiplier,
            'cabin_points': cabin_points,
            'airline': airline,
            'airline_bonus': airline_bonus,
            'airline_points': airline_points,
            'user_tier': user_tier,
            'tier_multiplier': tier_multiplier,
            'tier_points': tier_points,
            'departure_date': departure_date.isoformat() if departure_date else None,
            'quarter': quarter if departure_date else None,
            'seasonal_multiplier': seasonal_multiplier,
            'seasonal_points': seasonal_points,
            'final_points': final_points,
            'distance_miles': distance_miles,
            'is_partner': is_partner
        }

        logger.info(f"Points calculation: {calculation_details}")
        return final_points, calculation_details

    def estimate_redemption_cost(
        self,
        distance_miles: float,
        cabin_class: str,
        airline: str
    ) -> int:
        """
        Estimate how many points would be needed for redemption
        Uses a simplified redemption formula
        """
        # Base redemption rate
        redemption_rate = 0.05  # 5 points per mile

        # Apply cabin class adjustment
        cabin_adjustment = {
            'economy': 1.0,
            'premium_economy': 1.2,
            'business': 1.8,
            'first': 2.5
        }.get(cabin_class, 1.0)

        # Apply airline multiplier
        airline_multiplier = {
            'AA': 0.9,
            'DL': 1.0,
            'UA': 0.95,
            'BA': 1.1,
            'EK': 1.2,
            'JL': 0.85
        }.get(airline, 1.0)

        estimated_points = int(np.round(
            distance_miles * redemption_rate * cabin_adjustment * airline_multiplier
        ))

        return max(estimated_points, 1000)  # Minimum 1000 points

    def calculate_tier_upgrade_points(
        self,
        current_points: int,
        current_tier: str
    ) -> Tuple[int, str]:
        """
        Calculate how many more points needed for next tier upgrade
        """
        tier_order = ['bronze', 'silver', 'gold', 'platinum']
        current_index = tier_order.index(current_tier)

        if current_index == len(tier_order) - 1:
            return 0, current_tier  # Already at highest tier

        next_tier = tier_order[current_index + 1]

        # Points required for each tier threshold
        tier_thresholds = {
            'bronze': 0,
            'silver': 25000,
            'gold': 75000,
            'platinum': 150000
        }

        points_needed = tier_thresholds[next_tier] - current_points

        return max(points_needed, 0), next_tier

    def get_tier_benefits(self, tier: str) -> Dict:
        """
        Get benefits for each tier level
        """
        benefits = {
            'bronze': {
                'discount': 0.0,
                'priority_boarding': False,
                'lounge_access': False,
                'upgrade_priority': 'low',
                'partner_bonus': 1.0
            },
            'silver': {
                'discount': 0.05,
                'priority_boarding': True,
                'lounge_access': False,
                'upgrade_priority': 'medium',
                'partner_bonus': 1.05
            },
            'gold': {
                'discount': 0.10,
                'priority_boarding': True,
                'lounge_access': True,
                'upgrade_priority': 'high',
                'partner_bonus': 1.1
            },
            'platinum': {
                'discount': 0.15,
                'priority_boarding': True,
                'lounge_access': True,
                'upgrade_priority': 'highest',
                'partner_bonus': 1.2
            }
        }

        return benefits.get(tier, benefits['bronze'])

# Singleton instance
points_calculator = PointsCalculator()
