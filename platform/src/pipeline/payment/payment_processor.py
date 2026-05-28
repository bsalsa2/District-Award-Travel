"""
Payment Processor Service
Handles secure payment processing with Stripe integration
Designed for PCI DSS compliance with tokenization
"""

import os
import logging
import stripe
from typing import Dict, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import asyncio
import aiohttp
from platform.src.intelligence.models.payment_risk import PaymentRiskModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PaymentResult:
    success: bool
    transaction_id: Optional[str] = None
    error: Optional[str] = None
    risk_score: Optional[float] = None
    requires_action: bool = False

class PaymentProcessor:
    """
    Core payment processor with Stripe integration
    Implements circuit breaker pattern for resilience
    """

    def __init__(self):
        # Initialize Stripe with API keys from environment
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        stripe.api_version = '2023-10-16'

        # Initialize risk model
        self.risk_model = PaymentRiskModel()

        # Circuit breaker state
        self._circuit_open = False
        self._last_failure = None
        self._failure_count = 0

        # Configuration
        self._retry_attempts = 3
        self._timeout = 10  # seconds

    async def initialize(self):
        """Initialize payment processor"""
        logger.info("Initializing Payment Processor")
        try:
            # Verify Stripe connection
            await self._check_stripe_connection()
            logger.info("Payment Processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Payment Processor: {str(e)}")
            raise

    async def _check_stripe_connection(self):
        """Verify Stripe API connection"""
        try:
            await stripe.PaymentIntent.list(limit=1)
        except stripe.error.StripeError as e:
            logger.error(f"Stripe connection failed: {str(e)}")
            raise

    async def process_payment(
        self,
        amount: int,
        currency: str,
        payment_method_id: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        description: Optional[str] = None
    ) -> PaymentResult:
        """
        Process a payment with risk assessment
        Returns PaymentResult with transaction details
        """
        if self._circuit_open:
            return PaymentResult(
                success=False,
                error="Payment service unavailable. Please try again later."
            )

        # Validate amount (minimum $0.50)
        if amount < 50:
            return PaymentResult(
                success=False,
                error="Amount too small. Minimum is $0.50"
            )

        # Risk assessment
        risk_score = self.risk_model.assess_payment_risk(
            amount=amount,
            currency=currency,
            customer_id=customer_id
        )

        if risk_score > 0.85:  # High risk threshold
            return PaymentResult(
                success=False,
                error="Payment flagged as high risk",
                risk_score=risk_score
            )

        # Prepare metadata
        payment_metadata = {
            'customer_id': customer_id or 'guest',
            'amount': amount,
            'currency': currency,
            'created_at': datetime.utcnow().isoformat(),
            **(metadata or {})
        }

        if description:
            payment_metadata['description'] = description

        # Create payment intent
        for attempt in range(self._retry_attempts):
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency.lower(),
                    payment_method=payment_method_id,
                    customer=customer_id,
                    metadata=payment_metadata,
                    confirm=True,
                    return_url="https://travel.district.com/payment/return",
                    description=description or "District Award Travel Payment"
                )

                # Verify payment status
                if intent.status == 'succeeded':
                    return PaymentResult(
                        success=True,
                        transaction_id=intent.id,
                        risk_score=risk_score
                    )
                elif intent.status == 'requires_action':
                    return PaymentResult(
                        success=True,
                        transaction_id=intent.id,
                        requires_action=True,
                        risk_score=risk_score
                    )
                else:
                    return PaymentResult(
                        success=False,
                        error=f"Payment failed: {intent.status}",
                        risk_score=risk_score
                    )

            except stripe.error.StripeError as e:
                logger.warning(f"Payment attempt {attempt + 1} failed: {str(e)}")
                if attempt == self._retry_attempts - 1:
                    self._handle_failure()
                    return PaymentResult(
                        success=False,
                        error=f"Payment processing failed: {str(e)}",
                        risk_score=risk_score
                    )
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return PaymentResult(
            success=False,
            error="Unexpected error during payment processing"
        )

    async def capture_authorized_payment(self, payment_intent_id: str) -> PaymentResult:
        """Capture an authorized payment"""
        if self._circuit_open:
            return PaymentResult(
                success=False,
                error="Payment service unavailable"
            )

        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
            if intent.status == 'succeeded':
                return PaymentResult(
                    success=True,
                    transaction_id=intent.id
                )
            return PaymentResult(
                success=False,
                error=f"Capture failed: {intent.status}"
            )
        except stripe.error.StripeError as e:
            self._handle_failure()
            return PaymentResult(
                success=False,
                error=f"Capture failed: {str(e)}"
            )

    async def refund_payment(self, payment_intent_id: str, amount: Optional[int] = None) -> PaymentResult:
        """Process a refund"""
        if self._circuit_open:
            return PaymentResult(
                success=False,
                error="Payment service unavailable"
            )

        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount
            )
            return PaymentResult(
                success=True,
                transaction_id=refund.id
            )
        except stripe.error.StripeError as e:
            self._handle_failure()
            return PaymentResult(
                success=False,
                error=f"Refund failed: {str(e)}"
            )

    async def create_customer(self, email: str, name: str = None, payment_method_id: str = None) -> Dict:
        """Create a Stripe customer"""
        if self._circuit_open:
            raise Exception("Payment service unavailable")

        try:
            customer_data = {'email': email}
            if name:
                customer_data['name'] = name

            customer = stripe.Customer.create(**customer_data)

            if payment_method_id:
                stripe.PaymentMethod.attach(
                    payment_method_id,
                    customer=customer.id
                )

            return {
                'id': customer.id,
                'email': customer.email,
                'name': customer.name
            }
        except stripe.error.StripeError as e:
            self._handle_failure()
            raise Exception(f"Customer creation failed: {str(e)}")

    async def attach_payment_method(self, customer_id: str, payment_method_id: str) -> bool:
        """Attach payment method to customer"""
        if self._circuit_open:
            return False

        try:
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            return True
        except stripe.error.StripeError as e:
            self._handle_failure()
            logger.error(f"Failed to attach payment method: {str(e)}")
            return False

    def _handle_failure(self):
        """Handle service failure and update circuit breaker state"""
        self._failure_count += 1
        self._last_failure = datetime.utcnow()

        # Open circuit after 5 failures
        if self._failure_count >= 5:
            self._circuit_open = True
            logger.error("Payment service circuit breaker opened")

    def reset_circuit_breaker(self):
        """Reset circuit breaker state"""
        self._circuit_open = False
        self._failure_count = 0
        self._last_failure = None
        logger.info("Payment service circuit breaker reset")

    async def health_check(self) -> Dict:
        """Check service health"""
        try:
            # Check Stripe connection
            await self._check_stripe_connection()

            # Check circuit breaker
            status = "healthy" if not self._circuit_open else "degraded"

            return {
                'status': status,
                'circuit_open': self._circuit_open,
                'last_failure': self._last_failure.isoformat() if self._last_failure else None,
                'failure_count': self._failure_count
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

# Global instance for dependency injection
payment_processor = PaymentProcessor()
