"""
FastAPI endpoints for cancellation policy and booking management
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
import logging
import asyncio

from platform.src.policy.cancellation import (
    cancellation_engine,
    CancellationStatus,
    BookingClass,
    FareType
)
from platform.src.pipeline.cancellation_worker import cancellation_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="District Award Travel - Cancellation API",
    description="API for managing award travel booking cancellations and refunds",
    version="1.0.0",
    docs_url="/api/cancellation/docs",
    redoc_url="/api/cancellation/redoc",
    openapi_url="/api/cancellation/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class CancellationRequest(BaseModel):
    booking_id: str = Field(..., description="Unique booking identifier")
    booking_class: str = Field(..., description="Booking class (first, business, premium_economy, economy)")
    fare_type: str = Field(..., description="Fare type (full_fare, discounted, promo, charity)")
    original_amount: str = Field(..., description="Original booking amount in USD")
    departure_date: str = Field(..., description="Departure date in ISO format")
    cancellation_date: Optional[str] = Field(
        default=None,
        description="Cancellation date in ISO format (defaults to now)"
    )

class CancellationValidationRequest(BaseModel):
    booking_class: str = Field(..., description="Booking class")
    fare_type: str = Field(..., description="Fare type")
    original_amount: str = Field(..., description="Original booking amount")
    departure_date: str = Field(..., description="Departure date")
    cancellation_date: Optional[str] = Field(
        default=None,
        description="Optional cancellation date"
    )

class CancellationResult(BaseModel):
    booking_id: Optional[str] = Field(None, description="Booking identifier")
    request_id: str = Field(..., description="Request identifier")
    status: str = Field(..., description="Cancellation status")
    refund_amount: str = Field(..., description="Refund amount in USD")
    penalty_details: Dict[str, Any] = Field(..., description="Penalty breakdown")
    cancellation_date: str = Field(..., description="Cancellation date")
    departure_date: str = Field(..., description="Departure date")
    days_before_departure: int = Field(..., description="Days before departure")
    policy_applied: Dict[str, Any] = Field(..., description="Applied policy details")
    processed_at: Optional[str] = Field(None, description="Processing timestamp")
    success: bool = Field(..., description="Operation success status")
    error: Optional[str] = Field(None, description="Error message if any")

class ValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Whether cancellation is valid")
    can_cancel: bool = Field(..., description="Whether cancellation is allowed")
    restrictions: List[str] = Field(default=[], description="List of restrictions")
    recommendations: List[str] = Field(default=[], description="List of recommendations")

# API Endpoints
@app.post(
    "/api/cancellation/calculate",
    response_model=CancellationResult,
    summary="Calculate cancellation details",
    response_description="Cancellation calculation result"
)
async def calculate_cancellation(request: CancellationRequest):
    """
    Calculate cancellation details including refund amount and penalties
    """
    try:
        # Convert string amounts to Decimal
        original_amount = Decimal(request.original_amount)

        # Parse dates
        departure_date = datetime.fromisoformat(request.departure_date)
        cancellation_date = datetime.fromisoformat(
            request.cancellation_date or datetime.utcnow().isoformat()
        )

        # Get booking class and fare type enums
        try:
            booking_class = BookingClass(request.booking_class.lower())
            fare_type = FareType(request.fare_type.lower())
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid booking class or fare type: {str(e)}"
            )

        # Calculate cancellation
        result = cancellation_engine.calculate_cancellation(
            booking_class=booking_class,
            fare_type=fare_type,
            original_amount=original_amount,
            departure_date=departure_date,
            cancellation_date=cancellation_date
        )

        # Format response
        response = {
            "booking_id": request.booking_id,
            "request_id": f"calc-{datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')}",
            **result
        }

        return response

    except Exception as e:
        logger.error(f"Error calculating cancellation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating cancellation: {str(e)}"
        )

@app.post(
    "/api/cancellation/validate",
    response_model=ValidationResult,
    summary="Validate cancellation eligibility",
    response_description="Validation result"
)
async def validate_cancellation(request: CancellationValidationRequest):
    """
    Validate if a cancellation is allowed under current policy
    """
    try:
        # Convert string amounts to Decimal
        original_amount = Decimal(request.original_amount)

        # Parse dates
        departure_date = datetime.fromisoformat(request.departure_date)
        cancellation_date = datetime.fromisoformat(
            request.cancellation_date or datetime.utcnow().isoformat()
        )

        # Get booking class and fare type enums
        try:
            booking_class = BookingClass(request.booking_class.lower())
            fare_type = FareType(request.fare_type.lower())
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid booking class or fare type: {str(e)}"
            )

        # Validate cancellation
        validation = cancellation_engine.validate_cancellation(
            booking_class=booking_class,
            fare_type=fare_type,
            original_amount=original_amount,
            departure_date=departure_date,
            cancellation_date=cancellation_date
        )

        return validation

    except Exception as e:
        logger.error(f"Error validating cancellation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating cancellation: {str(e)}"
        )

@app.post(
    "/api/cancellation/submit",
    response_model=Dict[str, Any],
    summary="Submit cancellation request for processing",
    response_description="Submission confirmation"
)
async def submit_cancellation(request: CancellationRequest):
    """
    Submit a cancellation request for asynchronous processing
    """
    try:
        # Validate the request first
        validation = await validate_cancellation(CancellationValidationRequest(
            booking_class=request.booking_class,
            fare_type=request.fare_type,
            original_amount=request.original_amount,
            departure_date=request.departure_date,
            cancellation_date=request.cancellation_date
        ))

        if not validation.get("is_valid", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cancellation cannot be processed: {', '.join(validation.get('restrictions', []))}"
            )

        # Submit to worker queue
        request_dict = request.dict()
        request_id = await cancellation_manager.submit_cancellation(request_dict)

        return {
            "request_id": request_id,
            "status": "submitted",
            "message": "Cancellation request submitted for processing",
            "booking_id": request.booking_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting cancellation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting cancellation: {str(e)}"
        )

@app.get(
    "/api/cancellation/status/{request_id}",
    response_model=Dict[str, Any],
    summary="Get cancellation request status",
    response_description="Request status information"
)
async def get_cancellation_status(request_id: str):
    """
    Get status of a cancellation request
    Note: In a real system, this would query a database
    """
    # For demo purposes, return mock status
    return {
        "request_id": request_id,
        "status": "processed",
        "result": {
            "booking_id": "AWARD-2026-001",
            "refund_amount": "937.50",
            "penalty_amount": "312.50",
            "processed_at": datetime.utcnow().isoformat()
        },
        "message": "Cancellation successfully processed"
    }

@app.get(
    "/api/cancellation/policies",
    response_model=Dict[str, Any],
    summary="Get available cancellation policies",
    response_description="List of cancellation policies"
)
async def get_policies():
    """
    Get all available cancellation policies
    """
    policies = {}

    for (booking_class, fare_type), policy in cancellation_engine.policies.items():
        key = f"{booking_class.value}_{fare_type.value}"
        policies[key] = {
            "booking_class": booking_class.value,
            "fare_type": fare_type.value,
            "advance_purchase_days": policy.advance_purchase_days,
            "penalty_percentage": str(policy.penalty_percentage),
            "refund_window_days": policy.refund_window_days,
            "is_non_refundable": policy.is_non_refundable,
            "minimum_penalty": str(policy.minimum_penalty)
        }

    return {
        "policies": policies,
        "total_policies": len(policies),
        "generated_at": datetime.utcnow().isoformat()
    }

# Health check endpoint
@app.get("/api/cancellation/health", include_in_schema=False)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "cancellation_api",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Starting cancellation API...")
    await cancellation_manager.start()
    logger.info("Cancellation API started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Shutting down cancellation API...")
    await cancellation_manager.stop()
    logger.info("Cancellation API shutdown complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
