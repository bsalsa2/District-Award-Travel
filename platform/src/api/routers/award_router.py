"""
Award search router for District Award Travel API.
Handles award search operations and results.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import database
from ..auth import get_current_active_user

router = APIRouter(
    prefix="/awards",
    tags=["awards"],
    responses={404: {"description": "Not found"}},
)

@router.get("/search", response_model=List[dict])
async def search_awards(
    origin: str = Query(..., min_length=3, max_length=3, description="3-letter airport code"),
    destination: str = Query(..., min_length=3, max_length=3, description="3-letter airport code"),
    cabin: str = Query("Business", description="Cabin class: Economy, Premium Economy, Business, First"),
    current_user: database.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Search for award availability between airports."""
    # Validate airport codes
    valid_airports = ["JFK", "LAX", "SFO", "DFW", "ORD", "BOS", "MIA", "SEA", "NRT", "HND", "LHR", "CDG", "FRA"]
    if origin not in valid_airports or destination not in valid_airports:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid airport code"
        )

    # Generate award data (in production, this would call airline APIs)
    award_results = database.generate_award_data(origin, destination, cabin)

    # Cache results in database
    search_record = database.AwardSearch(
        user_id=current_user.id,
        origin=origin,
        destination=destination,
        cabin_class=cabin,
        results_count=len(award_results)
    )
    db.add(search_record)
    db.commit()
    db.refresh(search_record)

    # Store results
    for result in award_results:
        db_result = database.AwardResult(
            search_id=search_record.id,
            airline=result["airline"],
            airline_code=result["airline_code"],
            route=result["route"],
            origin=result["origin"],
            destination=result["destination"],
            cabin_class=result["cabin_class"],
            miles_required=result["miles_required"],
            cash_value_usd=result["cash_value_usd"],
            cpp=result["cpp"],
            verdict=result["verdict"],
            program_name=result["program_name"],
            alliance=result["alliance"],
            booking_url=result["booking_url"],
            departure_date=result["departure_date"],
            return_date=result["return_date"]
        )
        db.add(db_result)

    db.commit()

    return award_results

@router.get("/programs", response_model=List[dict])
async def list_award_programs(
    db: Session = Depends(database.get_db)
):
    """List all available airline award programs."""
    programs = db.query(database.AwardProgram).filter(
        database.AwardProgram.is_active == True
    ).all()

    return [{
        "id": program.id,
        "airline": program.airline,
        "program_name": program.program_name,
        "alliance": program.alliance,
        "website": program.website,
        "phone": program.phone,
        "is_active": program.is_active
    } for program in programs]
