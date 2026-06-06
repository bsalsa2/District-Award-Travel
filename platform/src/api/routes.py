"""
API routes for District Award Travel Dashboard
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from platform.src.pipeline.booking_pipeline import BookingPipeline
from platform.src.intelligence.valuation_engine import ValuationEngine
from platform.src.db.database import get_db
import sqlite3

router = APIRouter(prefix="/api/v1")

# Pydantic models
class BookingCreate(BaseModel):
    user_id: str
    flight_number: str
    departure_date: str
    return_date: Optional[str] = None
    cabin_class: str
    award_points: int
    status: str = "pending"

class BookingResponse(BaseModel):
    id: int
    user_id: str
    flight_number: str
    departure_date: str
    return_date: Optional[str] = None
    cabin_class: str
    award_points: int
    status: str
    created_at: str
    updated_at: str

class ValuationRequest(BaseModel):
    flight_number: str
    cabin_class: str
    departure_date: str
    return_date: Optional[str] = None

class ValuationResponse(BaseModel):
    flight_number: str
    base_value: float
    award_points: int
    multiplier: float
    valuation_date: str

# Initialize services
booking_pipeline = BookingPipeline()
valuation_engine = ValuationEngine()

@router.get("/bookings", response_model=List[BookingResponse])
async def get_bookings(limit: int = 100, offset: int = 0):
    """Get list of bookings with pagination"""
    try:
        bookings = await booking_pipeline.get_bookings(limit=limit, offset=offset)
        return bookings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: int):
    """Get specific booking by ID"""
    try:
        booking = await booking_pipeline.get_booking(booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return booking
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bookings", response_model=BookingResponse)
async def create_booking(booking: BookingCreate):
    """Create a new booking"""
    try:
        new_booking = await booking_pipeline.create_booking(booking.dict())
        return new_booking
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bookings/{booking_id}", response_model=BookingResponse)
async def update_booking(booking_id: int, booking: BookingCreate):
    """Update an existing booking"""
    try:
        updated_booking = await booking_pipeline.update_booking(booking_id, booking.dict())
        if not updated_booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: int):
    """Delete a booking"""
    try:
        success = await booking_pipeline.delete_booking(booking_id)
        if not success:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {"message": "Booking deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/valuation", response_model=ValuationResponse)
async def get_valuation(request: ValuationRequest):
    """Get award points valuation for a flight"""
    try:
        valuation = valuation_engine.calculate_valuation(
            request.flight_number,
            request.cabin_class,
            request.departure_date,
            request.return_date
        )
        return valuation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/valuation/metrics")
async def get_valuation_metrics():
    """Get current valuation metrics"""
    try:
        metrics = valuation_engine.get_current_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bookings/user/{user_id}", response_model=List[BookingResponse])
async def get_user_bookings(user_id: str, limit: int = 100):
    """Get all bookings for a specific user"""
    try:
        bookings = await booking_pipeline.get_user_bookings(user_id, limit=limit)
        return bookings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
