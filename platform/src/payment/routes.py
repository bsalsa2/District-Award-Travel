"""
Payment API Routes for District Award Travel
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from platform.src.payment.gateway import PaymentGateway, PaymentRequest, PaymentResponse
from platform.src.auth.middleware import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])
security = HTTPBearer()

gateway = PaymentGateway()

class PaymentCreateRequest(BaseModel):
    """Request model for creating a payment"""
    booking_id: str
    amount: float
    currency: str = "USD"
    payment_method: str
    card_token: Optional[str] = None
    paypal_token: Optional[str] = None
    bank_account: Optional[dict] = None
    metadata: Optional[dict] = None

@router.post("/", response_model=PaymentResponse)
async def create_payment(
    request: PaymentCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new payment request
    """
    try:
        payment_method = request.payment_method.lower()
        payment_request = PaymentRequest(
            user_id=current_user["id"],
            booking_id=request.booking_id,
            amount=request.amount,
            currency=request.currency,
            payment_method=payment_method,
            card_token=request.card_token,
            paypal_token=request.paypal_token,
            bank_account=request.bank_account,
            metadata=request.metadata
        )

        return gateway.create_payment(payment_request)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{payment_id}/process", response_model=PaymentResponse)
async def process_payment(
    payment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Process a payment
    """
    try:
        return gateway.process_payment(payment_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get payment status
    """
    try:
        return gateway.get_payment_status(payment_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: str,
    amount: Optional[float] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Refund a payment
    """
    try:
        return gateway.refund_payment(payment_id, amount)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/webhook")
async def handle_webhook(
    payload: dict,
    signature: str,
    endpoint_secret: str
):
    """
    Handle payment provider webhooks
    """
    try:
        result = gateway.webhook_handler(payload, signature, endpoint_secret)
        return {"status": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
