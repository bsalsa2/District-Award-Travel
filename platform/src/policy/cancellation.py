"""
Cancellation Policy Engine for Award Travel Bookings
Handles refund calculations, penalty assessments, and policy enforcement
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging
from decimal import Decimal, ROUND_HALF_UP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CancellationStatus(Enum):
    """Status of a cancellation request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSED = "processed"
    FAILED = "failed"

class BookingClass(Enum):
    """Award booking classes with different cancellation rules"""
    FIRST = "first"
    BUSINESS = "business"
    PREMIUM_ECONOMY = "premium_economy"
    ECONOMY = "economy"

class FareType(Enum):
    """Type of award fare"""
    FULL_FARE = "full_fare"
    DISCOUNTED = "discounted"
    PROMO = "promo"
    CHARITY = "charity"

@dataclass
class CancellationPolicy:
    """Cancellation policy configuration"""
    booking_class: BookingClass
    fare_type: FareType
    advance_purchase_days: int
    penalty_percentage: Decimal
    refund_window_days: int
    is_non_refundable: bool = False
    minimum_penalty: Decimal = Decimal('0.00')

    def calculate_refund(self, original_amount: Decimal, cancellation_date: datetime) -> Decimal:
        """
        Calculate refund amount based on cancellation timing and policy
        Returns refund amount in USD
        """
        if self.is_non_refundable:
            return Decimal('0.00')

        days_before_departure = (self.departure_date - cancellation_date).days

        # Full refund window
        if days_before_departure >= self.refund_window_days:
            return original_amount

        # Partial refund with penalty
        if days_before_departure > 0:
            penalty_amount = original_amount * (self.penalty_percentage / Decimal('100'))
            penalty_amount = max(penalty_amount, self.minimum_penalty)
            refund = original_amount - penalty_amount
            return max(refund, Decimal('0.00'))

        # Cancellation on or after departure
        return Decimal('0.00')

    def get_penalty_details(self, original_amount: Decimal) -> Dict[str, Any]:
        """Get detailed penalty breakdown"""
        penalty_amount = Decimal('0.00')
        refund_amount = Decimal('0.00')

        if not self.is_non_refundable:
            penalty_amount = original_amount * (self.penalty_percentage / Decimal('100'))
            penalty_amount = max(penalty_amount, self.minimum_penalty)
            refund_amount = original_amount - penalty_amount
            refund_amount = max(refund_amount, Decimal('0.00'))

        return {
            "penalty_percentage": str(self.penalty_percentage),
            "penalty_amount": str(penalty_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "refund_amount": str(refund_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "is_non_refundable": self.is_non_refundable,
            "refund_window_days": self.refund_window_days
        }

class CancellationEngine:
    """Main cancellation policy engine"""

    # Default cancellation policies by booking class and fare type
    DEFAULT_POLICIES = {
        (BookingClass.FIRST, FareType.FULL_FARE): CancellationPolicy(
            booking_class=BookingClass.FIRST,
            fare_type=FareType.FULL_FARE,
            advance_purchase_days=365,
            penalty_percentage=Decimal('0'),
            refund_window_days=365,
            is_non_refundable=False
        ),
        (BookingClass.FIRST, FareType.DISCOUNTED): CancellationPolicy(
            booking_class=BookingClass.FIRST,
            fare_type=FareType.DISCOUNTED,
            advance_purchase_days=14,
            penalty_percentage=Decimal('25'),
            refund_window_days=14,
            minimum_penalty=Decimal('150.00')
        ),
        (BookingClass.BUSINESS, FareType.FULL_FARE): CancellationPolicy(
            booking_class=BookingClass.BUSINESS,
            fare_type=FareType.FULL_FARE,
            advance_purchase_days=180,
            penalty_percentage=Decimal('5'),
            refund_window_days=60,
            minimum_penalty=Decimal('75.00')
        ),
        (BookingClass.BUSINESS, FareType.DISCOUNTED): CancellationPolicy(
            booking_class=BookingClass.BUSINESS,
            fare_type=FareType.DISCOUNTED,
            advance_purchase_days=7,
            penalty_percentage=Decimal('50'),
            refund_window_days=7,
            minimum_penalty=Decimal('200.00')
        ),
        (BookingClass.PREMIUM_ECONOMY, FareType.FULL_FARE): CancellationPolicy(
            booking_class=BookingClass.PREMIUM_ECONOMY,
            fare_type=FareType.FULL_FARE,
            advance_purchase_days=90,
            penalty_percentage=Decimal('10'),
            refund_window_days=30,
            minimum_penalty=Decimal('50.00')
        ),
        (BookingClass.PREMIUM_ECONOMY, FareType.DISCOUNTED): CancellationPolicy(
            booking_class=BookingClass.PREMIUM_ECONOMY,
            fare_type=FareType.DISCOUNTED,
            advance_purchase_days=3,
            penalty_percentage=Decimal('75'),
            refund_window_days=3,
            minimum_penalty=Decimal('100.00')
        ),
        (BookingClass.ECONOMY, FareType.FULL_FARE): CancellationPolicy(
            booking_class=BookingClass.ECONOMY,
            fare_type=FareType.FULL_FARE,
            advance_purchase_days=60,
            penalty_percentage=Decimal('20'),
            refund_window_days=14,
            minimum_penalty=Decimal('25.00')
        ),
        (BookingClass.ECONOMY, FareType.DISCOUNTED): CancellationPolicy(
            booking_class=BookingClass.ECONOMY,
            fare_type=FareType.DISCOUNTED,
            advance_purchase_days=1,
            penalty_percentage=Decimal('100'),
            refund_window_days=1,
            is_non_refundable=True
        ),
        (BookingClass.ECONOMY, FareType.PROMO): CancellationPolicy(
            booking_class=BookingClass.ECONOMY,
            fare_type=FareType.PROMO,
            advance_purchase_days=0,
            penalty_percentage=Decimal('100'),
            refund_window_days=0,
            is_non_refundable=True
        ),
        (BookingClass.ECONOMY, FareType.CHARITY): CancellationPolicy(
            booking_class=BookingClass.ECONOMY,
            fare_type=FareType.CHARITY,
            advance_purchase_days=365,
            penalty_percentage=Decimal('0'),
            refund_window_days=365,
            is_non_refundable=False
        )
    }

    def __init__(self):
        self.policies = self.DEFAULT_POLICIES.copy()

    def get_policy(self, booking_class: BookingClass, fare_type: FareType) -> CancellationPolicy:
        """Get cancellation policy for given booking class and fare type"""
        key = (booking_class, fare_type)
        return self.policies.get(key, self.policies[(BookingClass.ECONOMY, FareType.DISCOUNTED)])

    def calculate_cancellation(
        self,
        booking_class: BookingClass,
        fare_type: FareType,
        original_amount: Decimal,
        departure_date: datetime,
        cancellation_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate cancellation details including refund and penalties
        Returns structured cancellation result
        """
        policy = self.get_policy(booking_class, fare_type)

        # Set departure date on policy for calculation
        policy.departure_date = departure_date

        refund_amount = policy.calculate_refund(original_amount, cancellation_date)
        penalty_details = policy.get_penalty_details(original_amount)

        days_before_departure = max(0, (departure_date - cancellation_date).days)

        return {
            "status": CancellationStatus.APPROVED.value,
            "refund_amount": str(refund_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "penalty_details": penalty_details,
            "cancellation_date": cancellation_date.isoformat(),
            "departure_date": departure_date.isoformat(),
            "days_before_departure": days_before_departure,
            "policy_applied": {
                "booking_class": booking_class.value,
                "fare_type": fare_type.value,
                "penalty_percentage": str(policy.penalty_percentage),
                "refund_window_days": policy.refund_window_days
            }
        }

    def validate_cancellation(
        self,
        booking_class: BookingClass,
        fare_type: FareType,
        original_amount: Decimal,
        departure_date: datetime,
        cancellation_date: datetime
    ) -> Dict[str, Any]:
        """
        Validate if cancellation is allowed under current policy
        Returns validation result with any restrictions
        """
        result = self.calculate_cancellation(
            booking_class, fare_type, original_amount, departure_date, cancellation_date
        )

        validation = {
            "is_valid": True,
            "can_cancel": True,
            "restrictions": [],
            "recommendations": []
        }

        if result["refund_amount"] == "0.00":
            validation["can_cancel"] = False
            validation["is_valid"] = False
            validation["restrictions"].append("No refund available under current policy")

        if result["days_before_departure"] <= 0:
            validation["can_cancel"] = False
            validation["is_valid"] = False
            validation["restrictions"].append("Cannot cancel on or after departure date")

        if result["penalty_details"]["is_non_refundable"]:
            validation["can_cancel"] = True
            validation["is_valid"] = True
            validation["restrictions"].append("Non-refundable fare - no monetary refund")

        if result["days_before_departure"] < 24 and not result["penalty_details"]["is_non_refundable"]:
            validation["recommendations"].append(
                "Consider keeping booking due to short cancellation window"
            )

        return validation

# Global engine instance
cancellation_engine = CancellationEngine()
