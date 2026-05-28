"""
Payment Gateway API
RESTful interface for payment processing
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import logging
from datetime import datetime
import asyncio

from platform.src.pipeline.payment.payment_processor import payment_processor, PaymentResult
from platform.src.intelligence.models.payment_risk import PaymentRiskModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="District Award Travel Payment Gateway",
    description="Secure payment processing for award travel bookings",
    version="1.0.0",
    docs_url="/payment/docs",
    redoc_url="/payment/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://travel.district.com", "https://*.district.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class PaymentRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in smallest currency unit (e.g., cents)")
    currency: str = Field("usd", description="Currency code (USD, EUR, etc.)")
    payment_method_id: str = Field(..., description="Stripe payment method ID")
    customer_id: Optional[str] = Field(None, description="Existing customer ID")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")
    description: Optional[str] = Field(None, description="Payment description")

class PaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str] = None
    error: Optional[str] = None
    risk_score: Optional[float] = None
    requires_action: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CustomerRequest(BaseModel):
    email: str = Field(..., description="Customer email")
    name: Optional[str] = Field(None, description="Customer name")
    payment_method_id: Optional[str] = Field(None, description="Payment method to attach")

class CustomerResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict] = None

# Dependency
async def get_payment_processor():
    return payment_processor

# Routes
@app.on_event("startup")
async def startup_event():
    """Initialize payment processor on startup"""
    try:
        await payment_processor.initialize()
        logger.info("Payment Gateway started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Payment Gateway: {str(e)}")
        raise

@app.post("/payment/process", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def process_payment(
    request: PaymentRequest,
    processor: PaymentProcessor = Depends(get_payment_processor)
):
    """
    Process a payment
    Returns transaction details and risk assessment
    """
    try:
        result = await processor.process_payment(
            amount=request.amount,
            currency=request.currency,
            payment_method_id=request.payment_method_id,
            customer_id=request.customer_id,
            metadata=request.metadata,
            description=request.description
        )

        return PaymentResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            error=result.error,
            risk_score=result.risk_score,
            requires_action=result.requires_action
        )
    except Exception as e:
        logger.error(f"Payment processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        )

@app.post("/payment/capture/{payment_intent_id}", response_model=PaymentResponse)
async def capture_payment(
    payment_intent_id: str,
    processor: PaymentProcessor = Depends(get_payment_processor)
):
    """Capture an authorized payment"""
    try:
        result = await processor.capture_authorized_payment(payment_intent_id)
        return PaymentResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            error=result.error
        )
    except Exception as e:
        logger.error(f"Capture error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Capture failed"
        )

@app.post("/payment/refund/{payment_intent_id}", response_model=PaymentResponse)
async def refund_payment(
    payment_intent_id: str,
    amount: Optional[int] = None,
    processor: PaymentProcessor = Depends(get_payment_processor)
):
    """Process a refund"""
    try:
        result = await processor.refund_payment(payment_intent_id, amount)
        return PaymentResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            error=result.error
        )
    except Exception as e:
        logger.error(f"Refund error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Refund failed"
        )

@app.post("/payment/customer", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    request: CustomerRequest,
    processor: PaymentProcessor = Depends(get_payment_processor)
):
    """Create a new customer"""
    try:
        customer = await processor.create_customer(
            email=request.email,
            name=request.name,
            payment_method_id=request.payment_method_id
        )
        return CustomerResponse(
            id=customer['id'],
            email=customer['email'],
            name=customer.get('name')
        )
    except Exception as e:
        logger.error(f"Customer creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Customer creation failed"
        )

@app.post("/payment/customer/{customer_id}/payment-method/{payment_method_id}", response_model=bool)
async def attach_payment_method(
    customer_id: str,
    payment_method_id: str,
    processor: PaymentProcessor = Depends(get_payment_processor)
):
    """Attach payment method to customer"""
    try:
        success = await processor.attach_payment_method(customer_id, payment_method_id)
        return success
    except Exception as e:
        logger.error(f"Payment method attachment error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to attach payment method"
        )

@app.get("/payment/health", response_model=HealthResponse)
async def health_check(processor: PaymentProcessor = Depends(get_payment_processor)):
    """Check service health"""
    try:
        health = await processor.health_check()
        return HealthResponse(
            status=health['status'],
            details=health
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            details={"error": str(e)}
        )

@app.get("/payment/risk/assess")
async def assess_risk(
    amount: int,
    currency: str,
    customer_id: Optional[str] = None,
    payment_method: str = "card",
    ip_address: Optional[str] = None
):
    """Assess payment risk (public endpoint for frontend use)"""
    try:
        risk_model = PaymentRiskModel()
        risk_score = risk_model.assess_payment_risk(
            amount=amount,
            currency=currency,
            customer_id=customer_id,
            payment_method_type=payment_method,
            ip_address=ip_address
        )

        return {
            "risk_score": risk_score,
            "category": risk_model.get_risk_category(risk_score),
            "requires_verification": risk_model.requires_additional_verification(risk_score)
        }
    except Exception as e:
        logger.error(f"Risk assessment error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment failed"
        )

# Webhook handler for Stripe events
@app.post("/payment/webhook")
async def handle_webhook(event: Dict):
    """
    Handle Stripe webhook events
    In production, this would verify the webhook signature
    """
    try:
        event_type = event.get('type')
        data = event.get('data', {}).get('object', {})

        logger.info(f"Received webhook: {event_type}")

        # Handle different event types
        if event_type == 'payment_intent.succeeded':
            logger.info(f"Payment succeeded: {data.get('id')}")
            # Update database, send confirmation, etc.
        elif event_type == 'payment_intent.payment_failed':
            logger.warning(f"Payment failed: {data.get('id')}")
        elif event_type == 'charge.refunded':
            logger.info(f"Payment refunded: {data.get('id')}")
        elif event_type == 'customer.created':
            logger.info(f"New customer: {data.get('id')}")

        return {"status": "received"}
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
