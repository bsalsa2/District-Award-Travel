from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, date
from typing import List, Optional
from ..schemas.airline import FlightOfferResponse, FlightSearchRequest
from ..services.airline_service import AirlineService
from fastapi import status

router = APIRouter(prefix="/api/v1/airlines", tags=["airlines"])

@router.post(
    "/search",
    response_model=List[FlightOfferResponse],
    summary="Search for flight offers",
    response_description="List of available flight offers"
)
async def search_flights(
    request: FlightSearchRequest,
    airline_service: AirlineService = Depends()
):
    """
    Search for flight offers from multiple airlines

    Returns a list of available flight offers matching the search criteria
    """
    try:
        offers = await airline_service.search_flights(
            origin=request.origin,
            destination=request.destination,
            departure_date=request.departure_date,
            return_date=request.return_date,
            cabin_class=request.cabin_class,
            adults=request.adults,
            max_stops=request.max_stops
        )
        return offers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search flights: {str(e)}"
        )

@router.get(
    "/status/{flight_number}",
    summary="Get flight status",
    response_description="Current status of a specific flight"
)
async def get_flight_status(
    flight_number: str,
    airline: str,
    departure_date: str,
    origin: str,
    destination: str,
    airline_service: AirlineService = Depends()
):
    """
    Get current status of a specific flight

    Returns the current status including departure/arrival times and delays
    """
    try:
        status = await airline_service.get_flight_status(
            airline=airline,
            flight_number=flight_number,
            departure_date=datetime.fromisoformat(departure_date),
            origin=origin,
            destination=destination
        )
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight status not available"
            )
        return status
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get flight status: {str(e)}"
        )
