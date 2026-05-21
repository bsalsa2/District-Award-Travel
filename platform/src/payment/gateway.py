"""
Payment Gateway Integration Module
Handles secure payment processing for award bookings with:
- Tokenization for PCI compliance
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Comprehensive observability
"""

import os
import json
import time
import logging
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum
import requests
import numpy as np
from dataclasses import dataclass
from functools import wraps

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('payment_gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PaymentGateway')

class PaymentStatus(Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DECLINED = "declined"

class PaymentMethod(Enum):
    """Supported payment methods"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    WIRE_TRANSFER = "wire_transfer"

@dataclass
class PaymentRequest:
    """Data class for payment requests"""
    amount: float
    currency: str
    booking_id: str
    payment_method: PaymentMethod
    customer_id: str
    metadata: Dict[str, Any]
    token: Optional[str] = None
    email: Optional[str] = None

@dataclass
class PaymentResponse:
    """Data class for payment responses"""
    payment_id: str
    status: PaymentStatus
    amount: float
    currency: str
    transaction_id: Optional[str] = None
    timestamp: str = datetime.utcnow().isoformat()
    error_code: Optional[str] = None
    error_message: Optional[str] = None

class PaymentGatewayError(Exception):
    """Custom exception for payment gateway errors"""
    def __init__(self, message: str, error_code: str = "GATEWAY_ERROR"):
        self.error_code = error_code
        super().__init__(message)

class PaymentGateway:
    """
    Main payment gateway class that integrates with Stripe API
    Implements circuit breaker pattern for fault tolerance
    """

    def __init__(self):
        # Configuration from environment variables
        self.stripe_api_key = os.getenv('STRIPE_SECRET_KEY')
        self.stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.timeout = int(os.getenv('PAYMENT_TIMEOUT', '30'))
        self.max_retries = int(os.getenv('PAYMENT_MAX_RETRIES', '3'))

        # Circuit breaker state
        self._circuit_breaker_state = {
            'state': 'CLOSED',
            'failure_count': 0,
            'last_failure_time': None,
            'reset_timeout': 60  # seconds
        }

        # Validate configuration
        if not self.stripe_api_key:
            raise PaymentGatewayError("Stripe API key not configured")

        # Initialize headers
        self.headers = {
            'Authorization': f'Bearer {self.stripe_api_key}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Stripe-Version': '2023-10-16'
        }

        logger.info("PaymentGateway initialized successfully")

    def _generate_idempotency_key(self, booking_id: str) -> str:
        """Generate idempotency key for request deduplication"""
        return hashlib.sha256(f"{booking_id}-{int(time.time())}".encode()).hexdigest()

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows requests"""
        state = self._circuit_breaker_state['state']

        if state == 'OPEN':
            # Check if reset timeout has passed
            if self._circuit_breaker_state['last_failure_time']:
                elapsed = time.time() - self._circuit_breaker_state['last_failure_time']
                if elapsed > self._circuit_breaker_state['reset_timeout']:
                    self._circuit_breaker_state['state'] = 'HALF-OPEN'
                    self._circuit_breaker_state['failure_count'] = 0
                    logger.info("Circuit breaker transitioned to HALF-OPEN")
                    return True

            logger.warning("Circuit breaker is OPEN - requests blocked")
            return False

        return True

    def _record_failure(self):
        """Record a failure and update circuit breaker state"""
        self._circuit_breaker_state['failure_count'] += 1
        self._circuit_breaker_state['last_failure_time'] = time.time()

        if self._circuit_breaker_state['failure_count'] >= 5:
            self._circuit_breaker_state['state'] = 'OPEN'
            logger.error("Circuit breaker transitioned to OPEN due to failures")

    def _record_success(self):
        """Record a successful operation"""
        if self._circuit_breaker_state['state'] == 'HALF-OPEN':
            self._circuit_breaker_state['state'] = 'CLOSED'
            self._circuit_breaker_state['failure_count'] = 0
            logger.info("Circuit breaker transitioned to CLOSED")

    def _make_request_with_retry(self, method: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and exponential backoff
        """
        if not self._check_circuit_breaker():
            raise PaymentGatewayError("Payment service unavailable due to circuit breaker")

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                url = f"https://api.stripe.com/v1/{endpoint}"

                # Add idempotency key for POST requests
                if method.upper() == 'POST':
                    idempotency_key = self._generate_idempotency_key(data.get('booking_id', str(uuid.uuid4())))
                    headers = {**self.headers, 'Idempotency-Key': idempotency_key}
                else:
                    headers = self.headers

                start_time = time.time()

                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout
                )

                latency = time.time() - start_time

                # Log metrics
                self._log_metrics(
                    endpoint=endpoint,
                    status_code=response.status_code,
                    latency=latency,
                    attempt=attempt + 1
                )

                if response.status_code == 200:
                    self._record_success()
                    return response.json()

                if response.status_code >= 500:
                    last_exception = PaymentGatewayError(
                        f"Stripe API error: {response.text}",
                        f"STRIPE_{response.status_code}"
                    )
                    logger.warning(f"Attempt {attempt + 1} failed with status {response.status_code}")
                    time.sleep(min(2 ** attempt, 10))  # Exponential backoff
                    continue

                # Handle 4xx errors
                error_data = response.json()
                raise PaymentGatewayError(
                    error_data.get('error', {}).get('message', 'Payment processing failed'),
                    error_data.get('error', {}).get('type', 'payment_error')
                )

            except requests.exceptions.RequestException as e:
                last_exception = PaymentGatewayError(
                    f"Network error: {str(e)}",
                    "NETWORK_ERROR"
                )
                logger.warning(f"Attempt {attempt + 1} failed with network error: {str(e)}")
                time.sleep(min(2 ** attempt, 10))
                continue

        self._record_failure()
        raise last_exception or PaymentGatewayError("Max retries exceeded")

    def _log_metrics(self, endpoint: str, status_code: int, latency: float, attempt: int):
        """Log payment metrics for observability"""
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'endpoint': endpoint,
            'status_code': status_code,
            'latency_seconds': round(latency, 4),
            'attempt': attempt,
            'circuit_state': self._circuit_breaker_state['state']
        }

        # In production, this would be sent to a metrics system
        logger.info(f"PAYMENT_METRIC: {json.dumps(metrics)}")

    def create_payment_intent(self, request: PaymentRequest) -> PaymentResponse:
        """
        Create a payment intent for award booking
        """
        logger.info(f"Creating payment intent for booking {request.booking_id}")

        # Prepare Stripe parameters
        params = {
            'amount': int(request.amount * 100),  # Convert to cents
            'currency': request.currency.lower(),
            'automatic_payment_methods[enabled]': 'true',
            'metadata[booking_id]': request.booking_id,
            'metadata[customer_id]': request.customer_id,
            'metadata[payment_method]': request.payment_method.value,
        }

        if request.token:
            params['payment_method'] = request.token
        elif request.email:
            params['receipt_email'] = request.email

        try:
            response = self._make_request_with_retry('POST', 'payment_intents', params)
            payment_id = response['id']

            # Create internal payment record
            self._create_internal_payment_record(
                payment_id=payment_id,
                booking_id=request.booking_id,
                amount=request.amount,
                currency=request.currency,
                status=PaymentStatus.PROCESSING.value
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.PROCESSING,
                amount=request.amount,
                currency=request.currency,
                transaction_id=None
            )

        except PaymentGatewayError as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return PaymentResponse(
                payment_id=str(uuid.uuid4()),
                status=PaymentStatus.FAILED,
                amount=request.amount,
                currency=request.currency,
                error_code=e.error_code,
                error_message=str(e)
            )

    def confirm_payment(self, payment_id: str) -> PaymentResponse:
        """
        Confirm a payment intent
        """
        logger.info(f"Confirming payment {payment_id}")

        try:
            response = self._make_request_with_retry(
                'POST',
                f'payment_intents/{payment_id}/confirm',
                {}
            )

            status = PaymentStatus.COMPLETED if response['status'] == 'succeeded' else PaymentStatus.PROCESSING

            # Update internal payment record
            self._update_internal_payment_record(
                payment_id=payment_id,
                status=status.value,
                transaction_id=response.get('charges', {}).get('data', [{}])[0].get('id')
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=status,
                amount=float(response['amount']) / 100,
                currency=response['currency'].upper(),
                transaction_id=response.get('charges', {}).get('data', [{}])[0].get('id')
            )

        except PaymentGatewayError as e:
            logger.error(f"Failed to confirm payment {payment_id}: {str(e)}")

            # Update internal payment record with failure
            self._update_internal_payment_record(
                payment_id=payment_id,
                status=PaymentStatus.FAILED.value,
                error_code=e.error_code
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
                amount=0,
                currency='USD',
                error_code=e.error_code,
                error_message=str(e)
            )

    def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentResponse:
        """
        Refund a payment
        """
        logger.info(f"Refunding payment {payment_id}")

        params = {}
        if amount:
            params['amount'] = int(amount * 100)

        try:
            response = self._make_request_with_retry(
                'POST',
                f'payment_intents/{payment_id}/refund',
                params
            )

            # Update internal payment record
            self._update_internal_payment_record(
                payment_id=payment_id,
                status=PaymentStatus.REFUNDED.value,
                transaction_id=response.get('id')
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.REFUNDED,
                amount=float(response['amount']) / 100,
                currency=response['currency'].upper(),
                transaction_id=response.get('id')
            )

        except PaymentGatewayError as e:
            logger.error(f"Failed to refund payment {payment_id}: {str(e)}")
            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
                amount=0,
                currency='USD',
                error_code=e.error_code,
                error_message=str(e)
            )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Stripe webhook signature
        """
        if not self.stripe_webhook_secret:
            logger.warning("Webhook secret not configured - skipping signature verification")
            return True

        try:
            # Compute HMAC signature
            computed_signature = hmac.new(
                self.stripe_webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            # Compare signatures in constant time to prevent timing attacks
            return hmac.compare_digest(computed_signature, signature)
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return False

    def process_webhook_event(self, event: Dict[str, Any]) -> PaymentResponse:
        """
        Process Stripe webhook events
        """
        event_type = event.get('type')
        data = event.get('data', {}).get('object', {})

        logger.info(f"Processing webhook event: {event_type}")

        if event_type == 'payment_intent.succeeded':
            payment_id = data.get('id')
            amount = float(data.get('amount')) / 100
            currency = data.get('currency', 'usd').upper()

            # Update internal payment record
            self._update_internal_payment_record(
                payment_id=payment_id,
                status=PaymentStatus.COMPLETED.value,
                transaction_id=data.get('charges', {}).get('data', [{}])[0].get('id')
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.COMPLETED,
                amount=amount,
                currency=currency,
                transaction_id=data.get('charges', {}).get('data', [{}])[0].get('id')
            )

        elif event_type == 'payment_intent.payment_failed':
            payment_id = data.get('id')
            error_code = data.get('last_payment_error', {}).get('code')
            error_message = data.get('last_payment_error', {}).get('message')

            # Update internal payment record
            self._update_internal_payment_record(
                payment_id=payment_id,
                status=PaymentStatus.FAILED.value,
                error_code=error_code
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
                amount=0,
                currency='USD',
                error_code=error_code,
                error_message=error_message
            )

        elif event_type == 'charge.refunded':
            payment_id = data.get('payment_intent')
            amount = float(data.get('amount_refunded')) / 100
            currency = data.get('currency', 'usd').upper()

            # Update internal payment record
            self._update_internal_payment_record(
                payment_id=payment_id,
                status=PaymentStatus.REFUNDED.value,
                transaction_id=data.get('id')
            )

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.REFUNDED,
                amount=amount,
                currency=currency,
                transaction_id=data.get('id')
            )

        return PaymentResponse(
            payment_id=str(uuid.uuid4()),
            status=PaymentStatus.PENDING,
            amount=0,
            currency='USD'
        )

    def _create_internal_payment_record(self, **kwargs):
        """Create internal payment record in database"""
        # In production, this would insert into a database
        logger.info(f"Creating internal payment record: {kwargs}")

    def _update_internal_payment_record(self, **kwargs):
        """Update internal payment record in database"""
        # In production, this would update a database record
        logger.info(f"Updating internal payment record: {kwargs}")

# Global gateway instance
gateway = PaymentGateway()

def payment_gateway_route():
    """FastAPI route handler for payment operations"""
    from fastapi import APIRouter, Request, HTTPException
    from fastapi.responses import JSONResponse

    router = APIRouter()

    @router.post("/payments/create")
    async def create_payment(request: PaymentRequest):
        try:
            response = gateway.create_payment_intent(request)
            return JSONResponse(content=response.__dict__)
        except Exception as e:
            logger.error(f"Payment creation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/payments/confirm/{payment_id}")
    async def confirm_payment(payment_id: str):
        try:
            response = gateway.confirm_payment(payment_id)
            return JSONResponse(content=response.__dict__)
        except Exception as e:
            logger.error(f"Payment confirmation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/payments/refund/{payment_id}")
    async def refund_payment(payment_id: str, request: Request):
        try:
            body = await request.json()
            amount = body.get('amount')
            response = gateway.refund_payment(payment_id, amount)
            return JSONResponse(content=response.__dict__)
        except Exception as e:
            logger.error(f"Payment refund failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/webhooks/stripe")
    async def stripe_webhook(request: Request):
        try:
            payload = await request.body()
            signature = request.headers.get('stripe-signature')

            if not gateway.verify_webhook_signature(payload, signature):
                raise PaymentGatewayError("Invalid webhook signature", "INVALID_SIGNATURE")

            event = json.loads(payload)
            response = gateway.process_webhook_event(event)

            return JSONResponse(content={"status": "received", "payment_id": response.payment_id})
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    return router
