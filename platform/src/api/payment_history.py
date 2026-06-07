"""
FastAPI endpoints for Payment History feature
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging
from datetime import datetime

from platform.src.pipeline.payment_history import payment_service, PaymentHistoryError

# Configure logging
logger = logging.getLogger(__name__)

app = FastAPI(
    title="District Award Travel - Payment History API",
    description="API for viewing and managing payment history",
    version="1.0.0",
    docs_url="/api/payment-history/docs",
    redoc_url="/api/payment-history/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PaymentRecord(BaseModel):
    """Model for recording a payment"""
    user_id: int
    booking_reference: str
    amount: float
    currency: str = "USD"
    payment_method: str
    transaction_id: str
    status: str
    metadata: Optional[Dict] = None

class PaymentUpdate(BaseModel):
    """Model for updating payment status"""
    status: str
    updated_by: Optional[str] = "system"

class PaymentSearch(BaseModel):
    """Model for payment search"""
    query: str

@app.post("/api/payment-history/record", tags=["payments"])
async def record_payment(payment: PaymentRecord):
    """
    Record a new payment

    This endpoint is used by the payment processing system to record successful or failed payments.
    """
    try:
        payment_id, transaction_id = payment_service.record_successful_payment(payment.dict())
        logger.info(f"Recorded payment {transaction_id} for user {payment.user_id}")
        return {
            "success": True,
            "payment_id": payment_id,
            "transaction_id": transaction_id,
            "status": "recorded"
        }
    except PaymentHistoryError as e:
        logger.error(f"Failed to record payment: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error recording payment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/payment-history/user/{user_id}", tags=["payments"])
async def get_user_payments(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get payment history for a user

    Returns paginated list of payments with optional date filtering
    """
    try:
        result = payment_service.get_user_payment_history(user_id, page=page, per_page=per_page)

        # Apply date filtering if provided
        if start_date or end_date:
            filtered_payments = []
            start_dt = datetime.fromisoformat(start_date) if start_date else None
            end_dt = datetime.fromisoformat(end_date) if end_date else None

            for payment in result['payments']:
                payment_date = datetime.fromisoformat(payment['created_at'])
                if (not start_dt or payment_date >= start_dt) and (not end_dt or payment_date <= end_dt):
                    filtered_payments.append(payment)

            result['payments'] = filtered_payments
            result['total_count'] = len(filtered_payments)

        return result
    except PaymentHistoryError as e:
        logger.error(f"Failed to get payment history for user {user_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting payment history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/payment-history/{transaction_id}", tags=["payments"])
async def get_payment_details(transaction_id: str):
    """
    Get details for a specific payment
    """
    try:
        payment = payment_service.get_payment_details(transaction_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payment
    except PaymentHistoryError as e:
        logger.error(f"Failed to get payment details for {transaction_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting payment details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/payment-history/search", tags=["payments"])
async def search_payments(search: PaymentSearch):
    """
    Search payment history

    Searches across transaction IDs, booking references, and user IDs
    """
    try:
        results = payment_service.search_payments(search.query)
        return {
            "query": search.query,
            "results": results,
            "count": len(results)
        }
    except PaymentHistoryError as e:
        logger.error(f"Payment search failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during payment search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/payment-history/user/{user_id}/stats", tags=["payments"])
async def get_payment_stats(user_id: int):
    """
    Get statistics for a user's payment history
    """
    try:
        stats = payment_service.get_payment_statistics(user_id)
        return stats
    except PaymentHistoryError as e:
        logger.error(f"Failed to get payment stats for user {user_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting payment stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/payment-history/refund", tags=["payments"])
async def process_refund(refund_data: Dict):
    """
    Process a refund

    Requires:
    - transaction_id: Original transaction to refund
    - amount: Amount to refund
    - refunded_by: Who is processing the refund
    """
    try:
        transaction_id = refund_data.get('transaction_id')
        amount = refund_data.get('amount')
        refunded_by = refund_data.get('refunded_by', 'system')

        if not transaction_id or not amount:
            raise HTTPException(status_code=400, detail="Missing required fields: transaction_id, amount")

        success = payment_service.record_refund(transaction_id, amount, refunded_by)
        if success:
            return {"success": True, "message": "Refund recorded"}
        else:
            raise HTTPException(status_code=400, detail="Refund processing failed")
    except PaymentHistoryError as e:
        logger.error(f"Refund processing failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error processing refund: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "payment-history"}
