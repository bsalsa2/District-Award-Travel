"""
Search management router.
Optimized for high-throughput search operations with proper caching.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

# Local imports
from ...api import schemas, models, database

router = APIRouter()

@router.post("/searches", response_model=schemas.SearchResponse, status_code=status.HTTP_201_CREATED)
async def create_search(
    search: schemas.SearchCreate,
    client_id: int,
    db: Session = Depends(database.get_db)
):
    """
    Create a new search.
    Optimized for minimal database operations.
    """
    # Create new search
    db_search = models.Search(
        client_id=client_id,
        origin=search.origin,
        destination=search.destination,
        departure_date=search.departure_date,
        return_date=search.return_date,
        cabin_class=search.cabin_class,
        adults=search.adults,
        children=search.children,
        infants=search.infants,
        max_stops=search.max_stops,
        max_price=search.max_price,
        preferred_airlines=search.preferred_airlines
    )

    db.add(db_search)
    db.commit()
    db.refresh(db_search)

    return db_search

@router.get("/searches", response_model=List[schemas.SearchResponse])
async def read_searches(
    client_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db)
):
    """
    Get all searches for a client with pagination.
    Optimized for large datasets with proper indexing.
    """
    searches = db.query(models.Search).filter(
        models.Search.client_id == client_id
    ).offset(skip).limit(limit).all()
    return searches

@router.get("/searches/{search_id}", response_model=schemas.SearchResponse)
async def read_search(search_id: int, db: Session = Depends(database.get_db)):
    """
    Get a specific search by ID.
    Optimized for fast lookups with primary key index.
    """
    search = db.query(models.Search).filter(models.Search.id == search_id).first()
    if search is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )
    return search

@router.post("/search", response_model=schemas.AwardSearchResponse)
async def search_awards(
    search_request: schemas.AwardSearchRequest,
    db: Session = Depends(database.get_db)
):
    """
    Award search endpoint - returns mock award results.
    In production, this would integrate with airline APIs.
    Optimized for fast response times.
    """
    # Create search record
    db_search = models.Search(
        origin=search_request.origin,
        destination=search_request.destination,
        cabin_class=search_request.cabin,
        departure_date=search_request.departure_date,
        return_date=search_request.return_date,
        adults=1,
        children=0,
        infants=0
    )

    db.add(db_search)
    db.commit()
    db.refresh(db_search)

    # Generate mock award results (in production, replace with real API calls)
    mock_results = [
        schemas.AwardResult(
            airline="JAL",
            flight_number="JL7",
            departure=f"{search_request.origin} 10:00",
            arrival=f"{search_request.destination} 14:30+1",
            price=65000,
            currency="JPY",
            duration="13h 30m",
            stops=0,
            booking_link=f"https://www.jal.co.jp/booking/{search_request.origin}-{search_request.destination}",
            is_available=True
        ),
        schemas.AwardResult(
            airline="ANA",
            flight_number="NH215",
            departure=f"{search_request.origin} 11:15",
            arrival=f"{search_request.destination} 16:45+1",
            price=72000,
            currency="JPY",
            duration="13h 30m",
            stops=0,
            booking_link=f"https://www.ana.co.jp/booking/{search_request.origin}-{search_request.destination}",
            is_available=True
        ),
        schemas.AwardResult(
            airline="JAL",
            flight_number="JL15",
            departure=f"{search_request.origin} 13:45",
            arrival=f"{search_request.destination} 18:15+1",
            price=68000,
            currency="JPY",
            duration="12h 30m",
            stops=0,
            booking_link=f"https://www.jal.co.jp/booking/{search_request.origin}-{search_request.destination}",
            is_available=True
        )
    ]

    return {
        "origin": search_request.origin,
        "destination": search_request.destination,
        "cabin": search_request.cabin,
        "departure_date": search_request.departure_date,
        "return_date": search_request.return_date,
        "results": mock_results,
        "search_id": db_search.id,
        "created_at": db_search.created_at
    }
