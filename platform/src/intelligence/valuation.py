"""
District Award Travel - AI Award Valuation Engine
Core valuation models for calculating cents-per-point (CPP) and award ratings
"""

import json
import os
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CabinClass(Enum):
    """Award cabin classes"""
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

class AwardRating(Enum):
    """Rating for award redemptions"""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    SKIP = "SKIP"

@dataclass
class AwardProgram:
    """Award program data structure"""
    name: str
    carrier: str
    award_rates: Dict[CabinClass, Dict[str, int]]  # {cabin: {route: points}}
    partner_rates: Dict[str, Dict[str, int]]  # {partner: {route: points}}
    fuel_surcharges: Dict[str, float]  # {route: surcharge_factor}
    blackout_dates: List[str]
    close_in_booking_fee: int
    phone_booking_fee: int

@dataclass
class Route:
    """Route information"""
    origin: str
    destination: str
    distance: int  # in miles
    typical_economy_fare: int  # in cents

@dataclass
class AwardOption:
    """Award redemption option"""
    program: str
    cabin: CabinClass
    points_required: int
    taxes_fees: int
    total_cost_cents: int
    cpp: float
    rating: AwardRating
    explanation: str
    route: Route
    departure_date: Optional[str] = None

class AwardValuationEngine:
    """
    Core AI engine for calculating award values and recommendations
    """

    def __init__(self):
        self.programs = self._load_award_programs()
        self.routes = self._load_route_database()
        self._build_indexes()

    def _load_award_programs(self) -> Dict[str, AwardProgram]:
        """Load award program data from JSON"""
        programs_data = {
            "United MileagePlus": {
                "carrier": "United Airlines",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "domestic": 12500,
                        "short-haul": 10000,
                        "long-haul": 25000,
                        "partner": 25000
                    },
                    CabinClass.PREMIUM_ECONOMY: {
                        "domestic": 20000,
                        "international": 35000
                    },
                    CabinClass.BUSINESS: {
                        "domestic": 30000,
                        "transcontinental": 40000,
                        "international": 60000,
                        "partner": 70000
                    },
                    CabinClass.FIRST: {
                        "domestic": 40000,
                        "transcontinental": 50000,
                        "international": 80000
                    }
                },
                "partner_rates": {
                    "ANA": {"international": 70000},
                    "Austrian": {"international": 60000},
                    "Lufthansa": {"international": 60000},
                    "SWISS": {"international": 60000},
                    "Turkish": {"international": 55000}
                },
                "fuel_surcharges": {
                    "United domestic": 0.0,
                    "United Hawaii": 0.15,
                    "United international": 0.25,
                    "ANA": 0.20,
                    "Austrian": 0.22,
                    "Lufthansa": 0.23,
                    "SWISS": 0.24,
                    "Turkish": 0.20
                },
                "blackout_dates": ["2026-12-24", "2026-12-25", "2026-12-31"],
                "close_in_booking_fee": 7500,
                "phone_booking_fee": 2500
            },
            "Delta SkyMiles": {
                "carrier": "Delta Air Lines",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "domestic": 12500,
                        "short-haul": 10000,
                        "long-haul": 25000
                    },
                    CabinClass.PREMIUM_ECONOMY: {
                        "international": 35000
                    },
                    CabinClass.BUSINESS: {
                        "domestic": 30000,
                        "transcontinental": 40000,
                        "international": 60000
                    },
                    CabinClass.FIRST: {
                        "domestic": 40000,
                        "transcontinental": 50000,
                        "international": 80000
                    }
                },
                "partner_rates": {
                    "Air France/KLM": {"international": 55000},
                    "Virgin Atlantic": {"transatlantic": 50000},
                    "Aeromexico": {"international": 50000},
                    "GOL": {"international": 40000}
                },
                "fuel_surcharges": {
                    "Delta domestic": 0.0,
                    "Delta international": 0.20,
                    "Air France/KLM": 0.25,
                    "Virgin Atlantic": 0.30,
                    "Aeromexico": 0.15,
                    "GOL": 0.10
                },
                "blackout_dates": ["2026-12-24", "2026-12-25"],
                "close_in_booking_fee": 10000,
                "phone_booking_fee": 3000
            },
            "American AAdvantage": {
                "carrier": "American Airlines",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "domestic": 12500,
                        "short-haul": 10000,
                        "long-haul": 25000,
                        "partner": 25000
                    },
                    CabinClass.PREMIUM_ECONOMY: {
                        "international": 35000
                    },
                    CabinClass.BUSINESS: {
                        "domestic": 30000,
                        "transcontinental": 40000,
                        "international": 60000,
                        "partner": 70000
                    },
                    CabinClass.FIRST: {
                        "domestic": 40000,
                        "transcontinental": 50000,
                        "international": 80000
                    }
                },
                "partner_rates": {
                    "Qantas": {"international": 70000},
                    "Japan Airlines": {"international": 65000},
                    "Cathay Pacific": {"international": 65000},
                    "Iberia": {"international": 55000},
                    "Finnair": {"international": 55000}
                },
                "fuel_surcharges": {
                    "American domestic": 0.0,
                    "American international": 0.20,
                    "Qantas": 0.25,
                    "Japan Airlines": 0.22,
                    "Cathay Pacific": 0.23,
                    "Iberia": 0.24,
                    "Finnair": 0.21
                },
                "blackout_dates": ["2026-12-24", "2026-12-25"],
                "close_in_booking_fee": 7500,
                "phone_booking_fee": 2500
            },
            "Air Canada Aeroplan": {
                "carrier": "Air Canada",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "domestic": 12500,
                        "short-haul": 10000,
                        "long-haul": 25000,
                        "partner": 25000
                    },
                    CabinClass.PREMIUM_ECONOMY: {
                        "international": 35000
                    },
                    CabinClass.BUSINESS: {
                        "domestic": 30000,
                        "transcontinental": 40000,
                        "international": 55000,
                        "partner": 60000
                    },
                    CabinClass.FIRST: {
                        "international": 70000
                    }
                },
                "partner_rates": {
                    "United": {"international": 60000},
                    "Lufthansa": {"international": 60000},
                    "SWISS": {"international": 60000},
                    "Austrian": {"international": 60000},
                    "Turkish": {"international": 55000}
                },
                "fuel_surcharges": {
                    "Air Canada domestic": 0.0,
                    "Air Canada international": 0.20,
                    "United": 0.20,
                    "Lufthansa": 0.23,
                    "SWISS": 0.24,
                    "Austrian": 0.22,
                    "Turkish": 0.20
                },
                "blackout_dates": ["2026-12-24", "2026-12-25"],
                "close_in_booking_fee": 5000,
                "phone_booking_fee": 3000
            },
            "Virgin Atlantic": {
                "carrier": "Virgin Atlantic",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "transatlantic": 20000,
                        "partner": 25000
                    },
                    CabinClass.PREMIUM: {
                        "transatlantic": 35000
                    },
                    CabinClass.BUSINESS: {
                        "transatlantic": 50000
                    }
                },
                "partner_rates": {
                    "Delta": {"transatlantic": 50000},
                    "Air France": {"transatlantic": 55000},
                    "ANA": {"transpacific": 60000}
                },
                "fuel_surcharges": {
                    "Virgin Atlantic": 0.30,
                    "Delta": 0.20,
                    "Air France": 0.25,
                    "ANA": 0.20
                },
                "blackout_dates": ["2026-12-24", "2026-12-25"],
                "close_in_booking_fee": 10000,
                "phone_booking_fee": 2500
            },
            "ANA Mileage Club": {
                "carrier": "All Nippon Airways",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "short-haul": 20000,
                        "medium-haul": 35000,
                        "long-haul": 55000,
                        "partner": 60000
                    },
                    CabinClass.PREMIUM: {
                        "short-haul": 35000,
                        "medium-haul": 55000,
                        "long-haul": 85000
                    },
                    CabinClass.BUSINESS: {
                        "short-haul": 55000,
                        "medium-haul": 85000,
                        "long-haul": 110000
                    },
                    CabinClass.FIRST: {
                        "long-haul": 160000
                    }
                },
                "partner_rates": {
                    "United": {"transpacific": 80000},
                    "Air Canada": {"transpacific": 80000},
                    "Lufthansa": {"transpacific": 85000}
                },
                "fuel_surcharges": {
                    "ANA": 0.20,
                    "United": 0.20,
                    "Air Canada": 0.20,
                    "Lufthansa": 0.23
                },
                "blackout_dates": ["2026-12-24", "2026-12-25", "2026-12-31"],
                "close_in_booking_fee": 5000,
                "phone_booking_fee": 2500
            },
            "British Airways Executive Club": {
                "carrier": "British Airways",
                "award_rates": {
                    CabinClass.ECONOMY: {
                        "short-haul": 9000,
                        "long-haul": 34000,
                        "partner": 40000
                    },
                    CabinClass.PREMIUM: {
                        "long-haul": 50000
                    },
                    CabinClass.BUSINESS: {
                        "long-haul": 60000
                    },
                    CabinClass.FIRST: {
                        "long-haul": 85000
                    }
                },
                "partner_rates": {
                    "American": {"transatlantic": 40000},
                    "Qantas": {"transpacific": 50000},
                    "Japan Airlines": {"transpacific": 50000}
                },
                "fuel_surcharges": {
                    "British Airways": 0.35,
                    "American": 0.20,
                    "Qantas": 0.25,
                    "Japan Airlines": 0.22
                },
                "blackout_dates": ["2026-12-24", "2026-12-25"],
                "close_in_booking_fee": 5000,
                "phone_booking_fee": 2500
            }
        }

        programs = {}
        for name, data in programs_data.items():
            program = AwardProgram(
                name=name,
                carrier=data["carrier"],
                award_rates={CabinClass(k): v for k, v in data["award_rates"].items()},
                partner_rates=data["partner_rates"],
                fuel_surcharges=data["fuel_surcharges"],
                blackout_dates=data["blackout_dates"],
                close_in_booking_fee=data["close_in_booking_fee"],
                phone_booking_fee=data["phone_booking_fee"]
            )
            programs[name] = program

        return programs

    def _load_route_database(self) -> Dict[str, Route]:
        """Load route distance database"""
        # Simplified route database with key routes
        routes_data = {
            "JFK-LAX": {"distance": 2475, "typical_economy_fare": 35000},
            "JFK-SFO": {"distance": 2586, "typical_economy_fare": 38000},
            "JFK-MIA": {"distance": 1090, "typical_economy_fare": 22000},
            "JFK-LHR": {"distance": 3459, "typical_economy_fare": 65000},
            "JFK-CDG": {"distance": 3625, "typical_economy_fare": 72000},
            "JFK-HND": {"distance": 6757, "typical_economy_fare": 95000},
            "LAX-HND": {"distance": 5478, "typical_economy_fare": 85000},
            "SFO-HND": {"distance": 5149, "typical_economy_fare": 82000},
            "JFK-YYZ": {"distance": 544, "typical_economy_fare": 25000},
            "LAX-SYD": {"distance": 7483, "typical_economy_fare": 110000},
            "JFK-DXB": {"distance": 6840, "typical_economy_fare": 90000},
            "JFK-FRA": {"distance": 3840, "typical_economy_fare": 70000},
            "MIA-LHR": {"distance": 4450, "typical_economy_fare": 75000},
            "DFW-HND": {"distance": 6065, "typical_economy_fare": 92000},
            "ORD-LHR": {"distance": 3959, "typical_economy_fare": 70000},
        }

        routes = {}
        for route_code, data in routes_data.items():
            origin, destination = route_code.split("-")
            route = Route(
                origin=origin,
                destination=destination,
                distance=data["distance"],
                typical_economy_fare=data["typical_economy_fare"]
            )
            routes[route_code] = route
            # Add reverse route
            reverse_code = f"{destination}-{origin}"
            routes[reverse_code] = Route(
                origin=destination,
                destination=origin,
                distance=data["distance"],
                typical_economy_fare=data["typical_economy_fare"]
            )

        return routes

    def _build_indexes(self):
        """Build search indexes for faster lookups"""
        self._cabin_class_map = {
            "economy": CabinClass.ECONOMY,
            "premium_economy": CabinClass.PREMIUM_ECONOMY,
            "business": CabinClass.BUSINESS,
            "first": CabinClass.FIRST
        }

        self._route_index = {}
        for route_code, route in self.routes.items():
            self._route_index[route_code] = route
            self._route_index[route.origin] = route
            self._route_index[route.destination] = route

    def calculate_cpp(
        self,
        program: str,
        miles: int,
        cabin: str,
        route: str,
        taxes: int = 0,
        partner: Optional[str] = None
    ) -> int:
        """
        Calculate cents-per-point (CPP) for an award redemption

        Args:
            program: Award program name
            miles: Miles balance
            cabin: Cabin class (economy, premium_economy, business, first)
            route: Route code (e.g., 'JFK-LAX')
            taxes: Additional taxes/fees in cents
            partner: Partner airline (if applicable)

        Returns:
            Cents-per-point value
        """
        try:
            cabin_class = self._cabin_class_map[cabin.lower()]
            program_obj = self.programs[program]

            # Get base award rate
            if partner:
                if partner not in program_obj.partner_rates:
                    raise ValueError(f"Partner {partner} not available in {program}")

                # Determine route type for partner
                if "transatlantic" in route.lower():
                    rate_key = "transatlantic"
                elif "transpacific" in route.lower():
                    rate_key = "transpacific"
                else:
                    rate_key = "international"

                points_required = program_obj.partner_rates[partner][rate_key]
            else:
                # Determine route type
                route_lower = route.lower()
                if "jfk-lax" in route_lower or "jfk-sfo" in route_lower or "sfo-hnd" in route_lower:
                    rate_key = "long-haul"
                elif "jfk-mia" in route_lower or "jfk-ord" in route_lower:
                    rate_key = "short-haul"
                elif "jfk-lhr" in route_lower or "jfk-cdg" in route_lower:
                    rate_key = "international"
                elif "lax-syd" in route_lower:
                    rate_key = "long-haul"
                else:
                    rate_key = "domestic"

                points_required = program_obj.award_rates[cabin_class][rate_key]

            # Calculate total cost
            route_obj = self._route_index.get(route)
            if not route_obj:
                raise ValueError(f"Route {route} not found in database")

            # Estimate taxes based on program
            fuel_surcharge_factor = program_obj.fuel_surcharges.get(
                f"{program_obj.carrier} {rate_key}" if not partner else partner,
                0.0
            )

            # Base taxes from fuel surcharge
            base_taxes = int(route_obj.typical_economy_fare * fuel_surcharge_factor)

            # Add additional fees
            if miles < 30000:
                base_taxes += program_obj.close_in_booking_fee
            if partner:
                base_taxes += program_obj.phone_booking_fee

            total_taxes = base_taxes + taxes

            # Calculate CPP
            if miles == 0:
                return 0

            cpp = (route_obj.typical_economy_fare + total_taxes) / miles * 100
            return round(cpp, 2)

        except Exception as e:
            logger.error(f"Error calculating CPP: {e}")
            raise

    def rate_award(
        self,
        cpp: float,
        program: str,
        cabin: str,
        route: Optional[str] = None
    ) -> Tuple[AwardRating, str]:
        """
        Rate an award redemption based on CPP value

        Args:
            cpp: Cents-per-point value
            program: Award program name
            cabin: Cabin class
            route: Route code (optional, for context)

        Returns:
            Tuple of (rating, explanation)
        """
        cabin_class = self._cabin_class_map[cabin.lower()]
        program_obj = self.programs[program]

        # Rating thresholds (in cents-per-point)
        thresholds = {
            AwardRating.EXCELLENT: 3.5,
            AwardRating.GOOD: 2.5,
            AwardRating.FAIR: 1.5,
            AwardRating.SKIP: 0.0
        }

        if cpp >= thresholds[AwardRating.EXCELLENT]:
            rating = AwardRating.EXCELLENT
            explanation = f"Excellent value! You're getting {cpp} cents per point, which is outstanding."
        elif cpp >= thresholds[AwardRating.GOOD]:
            rating = AwardRating.GOOD
            explanation = f"Good value at {cpp} cents per point. Consider this redemption."
        elif cpp >= thresholds[AwardRating.FAIR]:
            rating = AwardRating.FAIR
            explanation = f"Fair value at {cpp} cents per point. Only redeem if no better options."
        else:
            rating = AwardRating.SKIP
            explanation = f"Poor value at {cpp} cents per point. Better to save miles or book cash ticket."

        # Add program-specific context
        if program == "British Airways Executive Club" and cabin_class in [CabinClass.ECONOMY, CabinClass.PREMIUM]:
            explanation += " Note: BA charges high fuel surcharges which reduce value."

        if program == "Virgin Atlantic" and cabin_class in [CabinClass.ECONOMY, CabinClass.PREMIUM]:
            explanation += " Note: Virgin Atlantic has high fuel surcharges but good award availability."

        if route:
            route_obj = self._route_index.get(route)
            if route_obj:
                typical_fare = route_obj.typical_economy_fare / 100  # Convert to dollars
                explanation += f" Typical cash fare for this route is ${typical_fare:.0f}."

        return rating, explanation

    def find_best_redemptions(
        self,
        origin: str,
        destination: str,
        cabin: str,
        max_options: int = 5,
        preferred_programs: Optional[List[str]] = None
    ) -> List[AwardOption]:
        """
        Find the best award redemption options for a given route and cabin

        Args:
            origin: Origin airport code
            destination: Destination airport code
            cabin: Cabin class
            max_options: Maximum number of options to return
            preferred_programs: List of preferred programs (optional)

        Returns:
            List of top award options ranked by value
        """
        route_code = f"{origin}-{destination}"
        cabin_class = self._cabin_class_map[cabin.lower()]

        # Generate options for all programs
        options = []

        for program_name, program in self.programs.items():
            # Skip if not in preferred programs (if specified)
            if preferred_programs and program_name not in preferred_programs:
                continue

            try:
                # Check if route is available in program
                rate_key = "domestic"
                if origin.startswith("JFK") and destination in ["LHR", "CDG", "HND"]:
                    rate_key = "international"
                elif origin.startswith("LAX") and destination in ["HND", "SYD"]:
                    rate_key = "long-haul"

                points_required = program.award_rates[cabin_class][rate_key]

                # Calculate taxes
                route_obj = self._route_index.get(route_code)
                if not route_obj:
                    continue

                fuel_surcharge_factor = program.fuel_surcharges.get(
                    f"{program.carrier} {rate_key}",
                    0.0
                )

                base_taxes = int(route_obj.typical_economy_fare * fuel_surcharge_factor)
                total_taxes = base_taxes

                # Calculate CPP with a standard miles balance of 50,000
                miles_balance = 50000
                cpp = self.calculate_cpp(
                    program=program_name,
                    miles=miles_balance,
                    cabin=cabin,
                    route=route_code,
                    taxes=total_taxes
                )

                # Rate the award
                rating, explanation = self.rate_award(
                    cpp=round(cpp, 2),
                    program=program_name,
                    cabin=cabin,
                    route=route_code
                )

                # Create award option
                option = AwardOption(
                    program=program_name,
                    cabin=cabin_class,
                    points_required=points_required,
                    taxes_fees=total_taxes,
                    total_cost_cents=route_obj.typical_economy_fare + total_taxes,
                    cpp=round(cpp, 2),
                    rating=rating,
                    explanation=explanation,
                    route=route_obj
                )

                options.append(option)

            except Exception as e:
                logger.warning(f"Could not generate option for {program_name}: {e}")
                continue

        # Sort by CPP (highest first)
        options.sort(key=lambda x: x.cpp, reverse=True)

        return options[:max_options]

    def compare_programs(
        self,
        miles_balances: Dict[str, int]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare award programs to find best value for each route

        Args:
            miles_balances: Dictionary of {program: miles_balance}

        Returns:
            Dictionary of {route: {program: best_value_info}}
        """
        comparison_results = {}

        # Get all unique routes
        all_routes = set()
        for program, miles in miles_balances.items():
            if program in self.programs:
                for route_code in self._route_index.keys():
                    if "-" in route_code:  # Only real routes
                        all_routes.add(route_code)

        # Compare each route
        for route_code in sorted(all_routes):
            route_obj = self._route_index[route_code]
            route_comparison = {}

            for program_name, miles in miles_balances.items():
                if program_name not in self.programs:
                    continue

                program = self.programs[program_name]

                try:
                    # Try economy cabin first
                    points = program.award_rates[CabinClass.ECONOMY]["domestic"]
                    if "international" in route_code.lower():
                        points = program.award_rates[CabinClass.ECONOMY]["international"]

                    # Calculate CPP
                    cpp = self.calculate_cpp(
                        program=program_name,
                        miles=miles,
                        cabin="economy",
                        route=route_code
                    )

                    rating, explanation = self.rate_award(
                        cpp=round(cpp, 2),
                        program=program_name,
                        cabin="economy",
                        route=route_code
                    )

                    route_comparison[program_name] = {
                        "cpp": round(cpp, 2),
                        "points_required": points,
                        "miles_balance": miles,
                        "miles_remaining": max(0, miles - points),
                        "rating": rating.value,
                        "explanation": explanation,
                        "is_best": False
                    }

                except Exception as e:
                    logger.warning(f"Could not compare {program_name} for {route_code}: {e}")
                    continue

            # Mark the best option
            if route_comparison:
                best_program = max(route_comparison.items(), key=lambda x: x[1]["cpp"])
                route_comparison[best_program[0]]["is_best"] = True

            comparison_results[route_code] = route_comparison

        return comparison_results

# Global instance for the engine
valuation_engine = AwardValuationEngine()
