from platform.src.models import AwardFlight
from platform.src.schemas import AwardFlightSchema
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///award_flights.db")
Session = sessionmaker(bind=engine)

def get_award_flights(
    client_preference: ClientPreferenceSchema,
    origin_airport: str,
    destination_airport: str,
    travel_dates: list[str]
):
    session = Session()
    award_flights = session.query(AwardFlight).filter(
        AwardFlight.origin_airport == origin_airport,
        AwardFlight.destination_airport == destination_airport,
        AwardFlight.travel_date.in_(travel_dates)
    ).all()
    award_flights = [AwardFlightSchema.from_orm(award_flight) for award_flight in award_flights]
    return award_flights
