"""
Payment Gateway Integration for District Award Travel
Handles PCI-compliant payment processing, tokenization, and fraud detection
"""

import os
import json
import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum
import sqlite3
import requests
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
import numpy as np
from platform.src.intelligence.fraud import FraudDetectionEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PaymentStatus(str, Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DECLINED = "declined"

class PaymentMethod(str, Enum):
    """Supported payment methods"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"

class PaymentRequest(BaseModel):
    """Payment request model"""
    user_id: str = Field(..., description="User ID")
    booking_id: str = Field(..., description="Booking ID")
    amount: float = Field(..., gt=0, description="Payment amount in USD")
    currency: str = Field(default="USD", description="Currency code")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    card_token: Optional[str] = Field(None, description="Tokenized card data")
    paypal_token: Optional[str] = Field(None, description="PayPal token")
    bank_account: Optional[Dict] = Field(None, description="Bank account details")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")

    @validator('card_token')
    def validate_card_token(cls, v, values):
        if values.get('payment_method') in [PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD] and not v:
            raise ValueError('Card token is required for credit/debit card payments')
        return v

class PaymentResponse(BaseModel):
    """Payment response model"""
    payment_id: str
    status: PaymentStatus
    amount: float
    currency: str
    payment_method: PaymentMethod
    transaction_reference: Optional[str] = None
    timestamp: datetime
    fraud_score: Optional[float] = None
    metadata: Dict = {}

class PaymentGateway:
    """
    Main payment gateway class handling all payment operations
    """

    def __init__(self):
        self.fraud_engine = FraudDetectionEngine()
        self.db_path = os.path.join(os.getcwd(), 'platform', 'data', 'payments.db')
        self._init_db()
        self._load_config()

    def _init_db(self) -> None:
        """Initialize payment database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    booking_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    status TEXT NOT NULL,
                    transaction_reference TEXT,
                    card_token TEXT,
                    paypal_token TEXT,
                    bank_account_hash TEXT,
                    metadata TEXT,
                    fraud_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create payment events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (payment_id) REFERENCES payments(id)
                )
            """)

            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_booking ON payments(booking_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")

            conn.commit()

    def _load_config(self) -> None:
        """Load gateway configuration"""
        self.config = {
            "stripe": {
                "api_key": os.getenv("STRIPE_SECRET_KEY", "sk_test_default_key"),
                "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_default_secret"),
                "endpoint": "https://api.stripe.com/v1"
            },
            "paypal": {
                "client_id": os.getenv("PAYPAL_CLIENT_ID", "sb_default_client_id"),
                "secret": os.getenv("PAYPAL_SECRET", "sb_default_secret"),
                "endpoint": "https://api.sandbox.paypal.com"
            },
            "processing_fee": 0.029,  # 2.9% + $0.30
            "fraud_threshold": 0.7
        }

    def _generate_payment_id(self) -> str:
        """Generate unique payment ID"""
        return f"pay_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    def _calculate_fee(self, amount: float) -> float:
        """Calculate processing fee"""
        return amount * self.config["processing_fee"]

    def _hash_bank_account(self, account_details: Dict) -> str:
        """Hash bank account details for security"""
        account_str = f"{account_details.get('routing_number')}_{account_details.get('account_number')}"
        return hashlib.sha256(account_str.encode()).hexdigest()

    def _log_event(self, payment_id: str, status: PaymentStatus, message: str = "") -> None:
        """Log payment event"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_events (payment_id, status, message)
                VALUES (?, ?, ?)
            """, (payment_id, status.value, message))
            conn.commit()

    def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Create a new payment request
        """
        payment_id = self._generate_payment_id()

        # Run fraud detection
        fraud_score = self.fraud_engine.assess_payment(request)

        if fraud_score > self.config["fraud_threshold"]:
            logger.warning(f"High fraud score detected for payment {payment_id}: {fraud_score}")
            self._log_event(payment_id, PaymentStatus.DECLINED, "High fraud score")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Payment declined due to fraud detection (score: {fraud_score:.2f})"
            )

        # Store payment in database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            payment_data = {
                "id": payment_id,
                "user_id": request.user_id,
                "booking_id": request.booking_id,
                "amount": request.amount,
                "currency": request.currency,
                "payment_method": request.payment_method.value,
                "status": PaymentStatus.PENDING.value,
                "card_token": request.card_token,
                "paypal_token": request.paypal_token,
                "bank_account_hash": self._hash_bank_account(request.bank_account) if request.bank_account else None,
                "metadata": json.dumps(request.metadata or {}),
                "fraud_score": fraud_score
            }

            columns = ", ".join(payment_data.keys())
            placeholders = ", ".join(["?"] * len(payment_data))
            cursor.execute(f"""
                INSERT INTO payments ({columns})
                VALUES ({placeholders})
            """, tuple(payment_data.values()))

            conn.commit()

        self._log_event(payment_id, PaymentStatus.PENDING, "Payment created")

        return PaymentResponse(
            payment_id=payment_id,
            status=PaymentStatus.PENDING,
            amount=request.amount,
            currency=request.currency,
            payment_method=request.payment_method,
            timestamp=datetime.utcnow(),
            fraud_score=fraud_score,
            metadata=request.metadata or {}
        )

    def process_payment(self, payment_id: str) -> PaymentResponse:
        """
        Process a payment through the appropriate gateway
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
            payment_data = cursor.fetchone()

            if not payment_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

        # Convert to dict for easier handling
        payment_dict = dict(zip(
            ["id", "user_id", "booking_id", "amount", "currency", "payment_method",
             "status", "transaction_reference", "card_token", "paypal_token",
             "bank_account_hash", "metadata", "fraud_score", "created_at", "updated_at"],
            payment_data
        ))

        payment_method = PaymentMethod(payment_dict["payment_method"])
        status_enum = PaymentStatus(payment_dict["status"])

        if status_enum != PaymentStatus.PENDING:
            return self.get_payment_status(payment_id)

        # Process based on payment method
        try:
            if payment_method in [PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD]:
                response = self._process_card_payment(payment_dict)
            elif payment_method == PaymentMethod.PAYPAL:
                response = self._process_paypal_payment(payment_dict)
            elif payment_method == PaymentMethod.BANK_TRANSFER:
                response = self._process_bank_transfer(payment_dict)
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")

            return response

        except Exception as e:
            logger.error(f"Payment processing failed for {payment_id}: {str(e)}")
            self._log_event(payment_id, PaymentStatus.FAILED, str(e))
            self._update_payment_status(payment_id, PaymentStatus.FAILED)

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment processing failed: {str(e)}"
            )

    def _process_card_payment(self, payment_dict: Dict) -> PaymentResponse:
        """Process credit/debit card payment via Stripe"""
        import stripe
        stripe.api_key = self.config["stripe"]["api_key"]

        try:
            # Create charge
            charge = stripe.Charge.create(
                amount=int(payment_dict["amount"] * 100),  # Convert to cents
                currency=payment_dict["currency"].lower(),
                source=payment_dict["card_token"],
                description=f"District Award Travel - Booking {payment_dict['booking_id']}",
                metadata={
                    "user_id": payment_dict["user_id"],
                    "booking_id": payment_dict["booking_id"],
                    "payment_id": payment_dict["id"]
                }
            )

            # Update payment status
            self._update_payment_status(
                payment_dict["id"],
                PaymentStatus.COMPLETED,
                charge.id
            )

            self._log_event(payment_dict["id"], PaymentStatus.COMPLETED, "Card payment successful")

            return PaymentResponse(
                payment_id=payment_dict["id"],
                status=PaymentStatus.COMPLETED,
                amount=payment_dict["amount"],
                currency=payment_dict["currency"],
                payment_method=PaymentMethod.CREDIT_CARD,
                transaction_reference=charge.id,
                timestamp=datetime.utcnow(),
                fraud_score=payment_dict["fraud_score"],
                metadata=json.loads(payment_dict["metadata"])
            )

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            self._log_event(payment_dict["id"], PaymentStatus.FAILED, str(e))
            raise

    def _process_paypal_payment(self, payment_dict: Dict) -> PaymentResponse:
        """Process PayPal payment"""
        auth_url = f"{self.config['paypal']['endpoint']}/v2/oauth2/token"
        payment_url = f"{self.config['paypal']['endpoint']}/v2/payments/sale"

        # Get access token
        auth_response = requests.post(
            auth_url,
            data="grant_type=client_credentials",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en_US"
            },
            auth=(self.config["paypal"]["client_id"], self.config["paypal"]["secret"])
        )

        if auth_response.status_code != 200:
            raise Exception(f"PayPal authentication failed: {auth_response.text}")

        access_token = auth_response.json().get("access_token")
        if not access_token:
            raise Exception("No access token received from PayPal")

        # Create payment
        payment_data = {
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "transactions": [{
                "amount": {
                    "total": str(payment_dict["amount"]),
                    "currency": payment_dict["currency"]
                },
                "description": f"District Award Travel - Booking {payment_dict['booking_id']}"
            }],
            "redirect_urls": {
                "return_url": "https://district.travel/payment/success",
                "cancel_url": "https://district.travel/payment/cancel"
            }
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(payment_url, json=payment_data, headers=headers)

        if response.status_code != 201:
            raise Exception(f"PayPal payment creation failed: {response.text}")

        payment_response = response.json()
        sale_id = payment_response["id"]

        # Update payment status
        self._update_payment_status(
            payment_dict["id"],
            PaymentStatus.COMPLETED,
            sale_id
        )

        self._log_event(payment_dict["id"], PaymentStatus.COMPLETED, "PayPal payment successful")

        return PaymentResponse(
            payment_id=payment_dict["id"],
            status=PaymentStatus.COMPLETED,
            amount=payment_dict["amount"],
            currency=payment_dict["currency"],
            payment_method=PaymentMethod.PAYPAL,
            transaction_reference=sale_id,
            timestamp=datetime.utcnow(),
            fraud_score=payment_dict["fraud_score"],
            metadata=json.loads(payment_dict["metadata"])
        )

    def _process_bank_transfer(self, payment_dict: Dict) -> PaymentResponse:
        """Process bank transfer payment"""
        # In a real implementation, this would create an ACH transfer
        # For now, we'll simulate it with a pending status

        self._update_payment_status(
            payment_dict["id"],
            PaymentStatus.PROCESSING,
            "bank_transfer_pending"
        )

        self._log_event(payment_dict["id"], PaymentStatus.PROCESSING, "Bank transfer initiated")

        return PaymentResponse(
            payment_id=payment_dict["id"],
            status=PaymentStatus.PROCESSING,
            amount=payment_dict["amount"],
            currency=payment_dict["currency"],
            payment_method=PaymentMethod.BANK_TRANSFER,
            timestamp=datetime.utcnow(),
            fraud_score=payment_dict["fraud_score"],
            metadata=json.loads(payment_dict["metadata"])
        )

    def _update_payment_status(self, payment_id: str, status: PaymentStatus,
                             transaction_reference: Optional[str] = None) -> None:
        """Update payment status in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            update_fields = {
                "status": status.value,
                "updated_at": datetime.utcnow().isoformat()
            }

            if transaction_reference:
                update_fields["transaction_reference"] = transaction_reference

            set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [payment_id]

            cursor.execute(f"""
                UPDATE payments
                SET {set_clause}
                WHERE id = ?
            """, values)

            conn.commit()

    def get_payment_status(self, payment_id: str) -> PaymentResponse:
        """Get payment status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
            payment_data = cursor.fetchone()

            if not payment_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

        payment_dict = dict(zip(
            ["id", "user_id", "booking_id", "amount", "currency", "payment_method",
             "status", "transaction_reference", "card_token", "paypal_token",
             "bank_account_hash", "metadata", "fraud_score", "created_at", "updated_at"],
            payment_data
        ))

        return PaymentResponse(
            payment_id=payment_dict["id"],
            status=PaymentStatus(payment_dict["status"]),
            amount=payment_dict["amount"],
            currency=payment_dict["currency"],
            payment_method=PaymentMethod(payment_dict["payment_method"]),
            transaction_reference=payment_dict["transaction_reference"],
            timestamp=datetime.fromisoformat(payment_dict["updated_at"]),
            fraud_score=payment_dict["fraud_score"],
            metadata=json.loads(payment_dict["metadata"])
        )

    def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentResponse:
        """Refund a completed payment"""
        payment = self.get_payment_status(payment_id)

        if payment.status != PaymentStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only completed payments can be refunded"
            )

        # Calculate refund amount
        refund_amount = amount if amount else payment.amount

        if refund_amount > payment.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refund amount cannot exceed payment amount"
            )

        # Process refund based on payment method
        try:
            if payment.payment_method in [PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD]:
                self._process_card_refund(payment_id, refund_amount)
            elif payment.payment_method == PaymentMethod.PAYPAL:
                self._process_paypal_refund(payment_id, refund_amount)
            else:
                raise ValueError(f"Refund not supported for payment method: {payment.payment_method}")

            # Update payment status
            self._update_payment_status(payment_id, PaymentStatus.REFUNDED)

            self._log_event(payment_id, PaymentStatus.REFUNDED, f"Refund of ${refund_amount} processed")

            return PaymentResponse(
                payment_id=payment_id,
                status=PaymentStatus.REFUNDED,
                amount=refund_amount,
                currency=payment.currency,
                payment_method=payment.payment_method,
                timestamp=datetime.utcnow(),
                metadata={"original_payment": payment_id}
            )

        except Exception as e:
            logger.error(f"Refund failed for {payment_id}: {str(e)}")
            self._log_event(payment_id, PaymentStatus.FAILED, f"Refund failed: {str(e)}")
            raise

    def _process_card_refund(self, payment_id: str, amount: float) -> None:
        """Process card refund via Stripe"""
        import stripe
        stripe.api_key = self.config["stripe"]["api_key"]

        # Get original charge
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT transaction_reference FROM payments WHERE id = ?", (payment_id,))
            transaction_ref = cursor.fetchone()[0]

        if not transaction_ref:
            raise Exception("No transaction reference found for refund")

        # Create refund
        refund = stripe.Refund.create(
            charge=transaction_ref,
            amount=int(amount * 100)  # Convert to cents
        )

        if refund.status != "succeeded":
            raise Exception(f"Refund failed: {refund.failure_reason}")

    def _process_paypal_refund(self, payment_id: str, amount: float) -> None:
        """Process PayPal refund"""
        auth_url = f"{self.config['paypal']['endpoint']}/v2/oauth2/token"
        refund_url = f"{self.config['paypal']['endpoint']}/v2/payments/sale/{payment_id}/refund"

        # Get access token
        auth_response = requests.post(
            auth_url,
            data="grant_type=client_credentials",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en_US"
            },
            auth=(self.config["paypal"]["client_id"], self.config["paypal"]["secret"])
        )

        if auth_response.status_code != 200:
            raise Exception(f"PayPal authentication failed: {auth_response.text}")

        access_token = auth_response.json().get("access_token")
        if not access_token:
            raise Exception("No access token received from PayPal")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        refund_data = {
            "amount": {
                "total": str(amount),
                "currency": "USD"
            }
        }

        response = requests.post(refund_url, json=refund_data, headers=headers)

        if response.status_code != 201:
            raise Exception(f"PayPal refund failed: {response.text}")

    def webhook_handler(self, payload: Dict, signature: str, endpoint_secret: str) -> str:
        """
        Handle webhook events from payment providers
        """
        try:
            # Verify webhook signature
            expected_signature = hmac.new(
                endpoint_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(expected_signature, signature):
                raise ValueError("Invalid webhook signature")

            event_type = payload.get("type")
            event_data = payload.get("data", {}).get("object", {})

            logger.info(f"Received webhook event: {event_type}")

            # Handle different event types
            if event_type == "payment_intent.succeeded":
                payment_id = event_data.get("metadata", {}).get("payment_id")
                if payment_id:
                    self._update_payment_status(payment_id, PaymentStatus.COMPLETED, event_data.get("id"))
                    self._log_event(payment_id, PaymentStatus.COMPLETED, "Webhook: Payment succeeded")

            elif event_type == "payment_intent.payment_failed":
                payment_id = event_data.get("metadata", {}).get("payment_id")
                if payment_id:
                    self._update_payment_status(payment_id, PaymentStatus.FAILED, event_data.get("id"))
                    self._log_event(payment_id, PaymentStatus.FAILED, "Webhook: Payment failed")

            elif event_type == "charge.refunded":
                payment_id = event_data.get("metadata", {}).get("payment_id")
                if payment_id:
                    self._update_payment_status(payment_id, PaymentStatus.REFUNDED, event_data.get("id"))
                    self._log_event(payment_id, PaymentStatus.REFUNDED, "Webhook: Payment refunded")

            return "OK"

        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return "Error", 400
