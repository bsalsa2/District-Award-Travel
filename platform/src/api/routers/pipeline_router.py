"""
Booking pipeline router for District Award Travel API.
Handles the award booking pipeline and status tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from .. import database
from ..auth import get_current_active_user

router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
    responses={404: {"description": "Not found"}},
)

class PipelineStatus:
    """Pipeline status constants."""
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    SEARCHING = "SEARCHING"
    BOOKING = "BOOKING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"

@router.get("/", response_model=dict)
async def get_pipeline_status(
    current_user: database.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Get current booking pipeline status."""
    # Get most recent pipeline entry for user
    pipeline_entry = db.query(database.AwardSearch).filter(
        database.AwardSearch.user_id == current_user.id
    ).order_by(database.AwardSearch.created_at.desc()).first()

    if not pipeline_entry:
        return {
            "status": "IDLE",
            "message": "No active pipeline",
            "last_updated": None
        }

    # Calculate completion percentage
    total_results = pipeline_entry.results_count
    completed_bookings = db.query(database.AwardResult).filter(
        database.AwardResult.search_id == pipeline_entry.id,
        database.AwardResult.booking_url.isnot(None)
    ).count()

    completion_percentage = (completed_bookings / total_results * 100) if total_results > 0 else 0

    return {
        "status": PipelineStatus.CONFIRMED if completion_percentage == 100 else PipelineStatus.SEARCHING,
        "pipeline_id": pipeline_entry.id,
        "origin": pipeline_entry.origin,
        "destination": pipeline_entry.destination,
        "cabin_class": pipeline_entry.cabin_class,
        "total_results": total_results,
        "completed_bookings": completed_bookings,
        "completion_percentage": round(completion_percentage, 2),
        "last_updated": pipeline_entry.created_at.isoformat(),
        "results": [{
            "airline": result.airline,
            "route": result.route,
            "miles_required": result.miles_required,
            "cpp": result.cpp,
            "verdict": result.verdict,
            "status": "BOOKED" if result.booking_url else "PENDING",
            "booking_url": result.booking_url
        } for result in pipeline_entry.results[:5]]  # Return top 5 results
    }

@router.post("/book", response_model=dict)
async def book_award(
    award_result_id: int,
    current_user: database.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Book an award ticket (simulated)."""
    award_result = db.query(database.AwardResult).filter(
        database.AwardResult.id == award_result_id,
        database.AwardResult.search.has(user_id=current_user.id)
    ).first()

    if not award_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Award result not found"
        )

    # Simulate booking process
    award_result.booking_url = f"https://book.districtaward.com/confirmation/{award_result_id}"
    award_result.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(award_result)

    return {
        "message": "Award ticket booked successfully",
        "booking_reference": f"DA-{award_result_id:08d}",
        "airline": award_result.airline,
        "route": award_result.route,
        "miles_used": award_result.miles_required,
        "booking_url": award_result.booking_url,
        "status": "CONFIRMED"
    }
