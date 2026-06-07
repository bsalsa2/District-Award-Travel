"""
FastAPI endpoint for award flight availability.
High-performance, low-latency endpoint with caching and rate limiting.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import date, timedelta
from typing import Optional, List
from platform.src.models.award_flight import AwardFlight, AwardSearchRequest, Airline, FlightClass
from platform.src.services.flight_search import FlightSearchService
from platform.src.services.flight_cache import FlightCache
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/award",
    tags=["award-flights"],
    responses={404: {"description": "Not found"}},
)

async def get_flight_search_service(request: Request) -> FlightSearchService:
    """Dependency to get flight search service."""
    redis = request.app.state.redis
    cache = FlightCache(redis)
    service = FlightSearchService(cache)
    await service.initialize()
    return service

@router.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down award availability service")

@router.get(
    "/flights",
    response_model=List[AwardFlight],
    summary="Search for award flight availability",
    response_description="List of available award flights",
    tags=["award-flights"]
)
async def search_award_flights(
    origin: str = Query(..., min_length=3, max_length=3, description="Origin airport IATA code"),
    destination: str = Query(..., min_length=3, max_length=3, description="Destination airport IATA code"),
    departure_date: date = Query(..., description="Departure date"),
    return_date: Optional[date] = Query(None, description="Return date for round trips"),
    cabin_class: FlightClass = Query(default=FlightClass.ECONOMY, description="Cabin class preference"),
    airlines: Optional[List[Airline]] = Query(None, description="Filter by specific airlines"),
    max_miles: Optional[int] = Query(None, description="Maximum miles to spend"),
    limit: Optional[int] = Query(50, description="Maximum number of results to return"),
    service: FlightSearchService = Depends(get_flight_search_service)
):
    """
    Search for award flight availability across multiple airlines.

    Returns award flights sorted by miles required (cheapest first).
    """
    if departure_date < date.today():
        raise HTTPException(status_code=400, detail="Departure date cannot be in the past")

    if return_date and return_date < departure_date:
        raise HTTPException(status_code=400, detail="Return date must be after departure date")

    request = AwardSearchRequest(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        cabin_class=cabin_class,
        airlines=airlines,
        max_miles=max_miles,
        limit=limit
    )

    try:
        flights = await service.search_award_flights(request)
        return JSONResponse(content=jsonable_encoder(flights))
    except Exception as e:
        logger.error(f"Error searching award flights: {e}")
        raise HTTPException(status_code=500, detail="Error searching award flights")

@router.get(
    "/flights/date-range",
    summary="Search award flights across a date range",
    response_description="Dictionary of dates with available flights",
    tags=["award-flights"]
)
async def search_award_flights_date_range(
    origin: str = Query(..., min_length=3, max_length=3, description="Origin airport IATA code"),
    destination: str = Query(..., min_length=3, max_length=3, description="Destination airport IATA code"),
    start_date: date = Query(..., description="Start date of search range"),
    end_date: date = Query(..., description="End date of search range"),
    cabin_class: FlightClass = Query(default=FlightClass.ECONOMY, description="Cabin class preference"),
    airlines: Optional[List[Airline]] = Query(None, description="Filter by specific airlines"),
    max_miles: Optional[int] = Query(None, description="Maximum miles to spend"),
    service: FlightSearchService = Depends(get_flight_search_service)
):
    """
    Search for award flight availability across a date range.

    Returns a dictionary with dates as keys and lists of flights as values.
    """
    if start_date < date.today():
        raise HTTPException(status_code=400, detail="Start date cannot be in the past")

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    date_range = (end_date - start_date).days + 1
    if date_range > 30:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 30 days")

    request = AwardSearchRequest(
        origin=origin,
        destination=destination,
        departure_date=start_date,
        return_date=None,
        cabin_class=cabin_class,
        airlines=airlines,
        max_miles=max_miles,
        limit=100
    )

    try:
        results = await service.search_multiple_dates(request, date_range)
        return JSONResponse(content=jsonable_encoder(results))
    except Exception as e:
        logger.error(f"Error searching award flights date range: {e}")
        raise HTTPException(status_code=500, detail="Error searching award flights")
