from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import AwardFlight, ClientPreference
from platform.src.schemas import AwardFlightSchema, ClientPreferenceSchema
from platform.src.utils import get_award_flights

router = APIRouter()

@router.post("/award_flights", response_model=list[AwardFlightSchema])
async def get_award_flights_endpoint(
    client_preference: ClientPreferenceSchema,
    origin_airport: str,
    destination_airport: str,
    travel_dates: list[str]
):
    try:
        award_flights = get_award_flights(
            client_preference, origin_airport, destination_airport, travel_dates
        )
        return award_flights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
