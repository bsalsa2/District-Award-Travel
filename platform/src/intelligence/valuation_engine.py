"""
Valuation Engine - AI-powered award point valuation system
Uses historical data, market trends, and ML models to calculate optimal award values
"""

import logging
import json
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from platform.src.db.database import (
    cache_valuation, get_cached_valuation,
    db
)
import sqlite3

logger = logging.getLogger(__name__)

class ValuationEngine:
    """AI-powered award point valuation engine"""

    def __init__(self):
        self.model_version = "1.2.0"
        self.cache_ttl = timedelta(hours=24)  # Cache valuations for 24 hours
        self.base_multipliers = {
            'economy': 1.0,
            'premium_economy': 1.5,
            'business': 3.0,
            'first': 5.0
        }
        self.airline_factors = self._load_airline_factors()
        self.seasonal_adjustments = self._load_seasonal_adjustments()
        self.market_trends = self._load_market_trends()

    def _load_airline_factors(self) -> Dict[str, float]:
        """Load airline-specific factors"""
        # In production, this would come from a database or external API
        return {
            'AA': 1.0,    # American Airlines
            'DL': 1.05,   # Delta
            'UA': 0.95,   # United
            'BA': 1.1,    # British Airways
            'LH': 1.08,   # Lufthansa
            'JL': 1.02,   # Japan Airlines
            'QF': 1.03,   # Qantas
            'EK': 1.15,   # Emirates
            'SQ': 1.12,   # Singapore Airlines
            'QR': 1.07    # Qatar Airways
        }

    def _load_seasonal_adjustments(self) -> Dict[str, Dict[str, float]]:
        """Load seasonal adjustment factors"""
        # Month-based adjustments (1-12)
        return {
            1: 1.15,  # January (post-holiday)
            2: 1.10,  # February (Valentine's)
            3: 1.05,  # March (spring break prep)
            4: 1.00,  # April
            5: 1.05,  # May (summer prep)
            6: 1.20,  # June (peak summer)
            7: 1.30,  # July (peak summer)
            8: 1.25,  # August (end of summer)
            9: 1.10,  # September (shoulder season)
            10: 1.05, # October (fall travel)
            11: 1.15, # November (Thanksgiving)
            12: 1.40  # December (holiday season)
        }

    def _load_market_trends(self) -> Dict[str, float]:
        """Load current market trends"""
        # In production, this would be updated dynamically
        return {
            'fuel_cost_index': 1.12,
            'demand_index': 1.08,
            'competition_index': 0.95,
            'award_availability': 1.10
        }

    def _get_base_value(self, flight_number: str) -> float:
        """Get base value for a flight (simplified for demo)"""
        # Extract airline code from flight number
        airline = flight_number[:2] if len(flight_number) >= 2 else 'AA'

        # Base value calculation
        base_value = 500.0  # Default base

        # Apply airline factor
        airline_factor = self.airline_factors.get(airline, 1.0)
        base_value *= airline_factor

        return base_value

    def _get_distance_factor(self, departure_date: str) -> float:
        """Get distance-based factor"""
        # Simplified - in production this would use actual distance
        month = datetime.strptime(departure_date, "%Y-%m-%d").month
        return self.seasonal_adjustments.get(month, 1.0)

    def _get_cabin_multiplier(self, cabin_class: str) -> float:
        """Get cabin class multiplier"""
        return self.base_multipliers.get(cabin_class.lower(), 1.0)

    def _get_market_adjustment(self) -> float:
        """Get combined market adjustment factor"""
        factors = list(self.market_trends.values())
        return np.mean(factors) * 0.9 + 0.1  # Weighted average

    def _calculate_award_points(self, base_value: float, cabin_multiplier: float) -> int:
        """Calculate award points from base value"""
        # Award points are typically 1 point per $X spent
        # For award travel, we adjust based on cabin class
        points_per_dollar = 100  # 1 point per $100
        raw_points = base_value * cabin_multiplier / points_per_dollar

        # Round to nearest 100 for cleaner award points
        return int(round(raw_points / 100) * 100)

    def calculate_valuation(self, flight_number: str, cabin_class: str,
                          departure_date: str, return_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate complete valuation for a flight
        Returns: {
            'flight_number': str,
            'base_value': float,
            'award_points': int,
            'multiplier': float,
            'valuation_date': str
        }
        """
        try:
            # Check cache first
            cache_key = f"{flight_number}_{cabin_class}_{departure_date}"
            cached = await self._get_cached_valuation(flight_number, cabin_class, departure_date)
            if cached:
                return cached

            # Calculate base value
            base_value = self._get_base_value(flight_number)

            # Calculate cabin multiplier
            cabin_multiplier = self._get_cabin_multiplier(cabin_class)

            # Calculate distance factor
            distance_factor = self._get_distance_factor(departure_date)

            # Calculate market adjustment
            market_adjustment = self._get_market_adjustment()

            # Calculate total multiplier
            total_multiplier = cabin_multiplier * distance_factor * market_adjustment

            # Calculate award points
            award_points = self._calculate_award_points(base_value, cabin_multiplier)

            # Build result
            result = {
                'flight_number': flight_number,
                'cabin_class': cabin_class,
                'departure_date': departure_date,
                'return_date': return_date,
                'base_value': round(base_value, 2),
                'award_points': award_points,
                'multiplier': round(total_multiplier, 3),
                'valuation_date': datetime.utcnow().isoformat(),
                'model_version': self.model_version
            }

            # Cache the result
            await self._cache_valuation(result)

            logger.info("Calculated valuation for %s: %d points", flight_number, award_points)
            return result

        except Exception as e:
            logger.error("Failed to calculate valuation: %s", str(e))
            raise ValueError(f"Valuation calculation failed: {str(e)}")

    async def _get_cached_valuation(self, flight_number: str, cabin_class: str, departure_date: str) -> Optional[Dict[str, Any]]:
        """Get cached valuation"""
        try:
            async with db.get_connection() as conn:
                cached = await get_cached_valuation(conn, flight_number, cabin_class, departure_date)
                if cached:
                    # Check if cache is still valid
                    calculated_at = datetime.fromisoformat(cached['calculated_at'])
                    if datetime.utcnow() - calculated_at < self.cache_ttl:
                        return cached
                return None
        except Exception as e:
            logger.error("Failed to get cached valuation: %s", str(e))
            return None

    async def _cache_valuation(self, valuation_data: Dict[str, Any]) -> None:
        """Cache a valuation result"""
        try:
            async with db.get_connection() as conn:
                await cache_valuation(conn, valuation_data)
        except Exception as e:
            logger.error("Failed to cache valuation: %s", str(e))
            # Don't fail the whole operation if caching fails
            pass

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current valuation metrics for dashboard"""
        return {
            'model_version': self.model_version,
            'cache_ttl_hours': self.cache_ttl.total_seconds() / 3600,
            'airline_count': len(self.airline_factors),
            'base_multipliers': self.base_multipliers,
            'market_trends': self.market_trends,
            'last_updated': datetime.utcnow().isoformat()
        }

    def get_historical_trends(self, flight_number: str, days: int = 30) -> Dict[str, Any]:
        """
        Get historical valuation trends for a flight
        Returns: {
            'flight_number': str,
            'days': int,
            'trend_data': List[Dict]
        }
        """
        # In production, this would query historical data
        # For demo, return mock data
        trend_data = []
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            valuation = self.calculate_valuation(
                flight_number,
                'business',
                date
            )
            trend_data.append({
                'date': date,
                'award_points': valuation['award_points'],
                'multiplier': valuation['multiplier']
            })

        return {
            'flight_number': flight_number,
            'days': days,
            'trend_data': trend_data[::-1]  # Return in chronological order
        }
