from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, datetime
from typing import List, Optional
from fastapi.responses import JSONResponse
import logging
from schemas.predictions import (
    PredictionRequest,
    PredictionResponse,
    PredictiveHoldRequest,
    PredictiveHoldResponse,
    BatchPredictionRequest
)
from services.ai_inference import AwardPredictor
from services.predictive_holds import PredictiveHoldService
from config.settings import settings

router = APIRouter(prefix=f"{settings.API_V1_STR}/predictions", tags=["predictions"])
logger = logging.getLogger(__name__)

predictor = AwardPredictor()
hold_service = PredictiveHoldService()

@router.post("/single", response_model=PredictionResponse)
async def get_prediction(
    request: PredictionRequest,
    flexible: bool = Query(False, description="Whether to consider flexible dates")
):
    """Get a single prediction for award availability"""
    try:
        route_key = f"{request.route.origin}_{request.route.destination}_{request.route.cabin_class}"

        departure_date = request.departure_date
        if flexible and request.flexible_dates:
            # For flexible dates, we'd need to check multiple dates
            # For simplicity, we'll just use the first flexible date
            departure_date = request.flexible_dates[0]

        prediction = predictor.predict(
            route_key,
            datetime.combine(departure_date, datetime.min.time()),
            request.passengers
        )

        return PredictionResponse(**prediction)

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch", response_model=List[PredictionResponse])
async def batch_predictions(
    request: BatchPredictionRequest
):
    """Get multiple predictions in a single request"""
    try:
        predictions = await predictor.batch_predict(request.predictions)
        return [PredictionResponse(**p) for p in predictions]
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hold", response_model=PredictiveHoldResponse)
async def create_predictive_hold(
    request: PredictiveHoldRequest
):
    """Create a predictive hold for a future award seat"""
    try:
        hold = await hold_service.create_hold(
            user_id=request.user_id,
            route_key=request.route_key,
            departure_date=request.departure_date,
            hold_duration_minutes=request.hold_duration_minutes,
            metadata=request.metadata
        )

        if not hold:
            raise HTTPException(status_code=429, detail="Maximum predictive holds reached")

        return PredictiveHoldResponse(
            hold_token=hold.hold_token,
            expiry=hold.expiry,
            route_key=hold.route_key,
            departure_date=hold.departure_date,
            status=hold.status,
            metadata=hold.metadata
        )

    except Exception as e:
        logger.error(f"Hold creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hold/{hold_token}", response_model=PredictiveHoldResponse)
async def get_hold_status(hold_token: str):
    """Check the status of a predictive hold"""
    try:
        is_valid = await hold_service.validate_hold(hold_token)
        if not is_valid:
            raise HTTPException(status_code=404, detail="Hold not found or expired")

        # In a real implementation, we would fetch hold details from database
        return PredictiveHoldResponse(
            hold_token=hold_token,
            expiry=datetime.utcnow() + timedelta(minutes=60),  # Simplified
            route_key="JFK_LAX_economy",
            departure_date=date.today(),
            status="active",
            metadata={}
        )
    except Exception as e:
        logger.error(f"Hold status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/hold/{hold_token}")
async def release_hold(hold_token: str):
    """Release a predictive hold"""
    try:
        success = await hold_service.release_hold(hold_token)
        if not success:
            raise HTTPException(status_code=404, detail="Hold not found")

        return {"message": "Hold released successfully"}
    except Exception as e:
        logger.error(f"Hold release error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/routes")
async def get_monitored_routes():
    """Get list of routes being monitored by the predictive engine"""
    # In production, this would query the database
    routes = [
        {"origin": "JFK", "destination": "LAX", "cabin_class": "economy"},
        {"origin": "LAX", "destination": "JFK", "cabin_class": "business"},
        {"origin": "SFO", "destination": "NRT", "cabin_class": "premium_economy"},
        {"origin": "LHR", "destination": "JFK", "cabin_class": "first"}
    ]
    return {"routes": routes, "count": len(routes)}
