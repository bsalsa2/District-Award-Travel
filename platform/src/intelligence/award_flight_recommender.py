import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AwardFlight(BaseModel):
    airline: str
    flight_number: str
    departure_airport: str
    departure_date: str
    arrival_airport: str
    arrival_date: str
    estimated_value: float
    booking_link: str

class SearchQuery(BaseModel):
    search: str

@app.post("/api/award-flights")
async def get_award_flights(search_query: SearchQuery):
    # Simulate a database query
    award_flights = [
        AwardFlight(
            airline="American Airlines",
            flight_number="AA123",
            departure_airport="JFK",
            departure_date="2026-06-10",
            arrival_airport="LAX",
            arrival_date="2026-06-10",
            estimated_value=25000.0,
            booking_link="https://example.com/book-now"
        ),
        AwardFlight(
            airline="Delta Air Lines",
            flight_number="DL456",
            departure_airport="LAX",
            departure_date="2026-06-12",
            arrival_airport="JFK",
            arrival_date="2026-06-12",
            estimated_value=30000.0,
            booking_link="https://example.com/book-now"
        ),
    ]

    # Filter award flights based on search query
    filtered_award_flights = [flight for flight in award_flights if search_query.search.lower() in flight.airline.lower() or search_query.search.lower() in flight.flight_number.lower()]

    return filtered_award_flights
