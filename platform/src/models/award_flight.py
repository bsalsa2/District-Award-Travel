"""
Data models for award flight availability.
Designed for mechanical sympathy with high-throughput processing.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class Airline(str, Enum):
    """Supported airlines for award flights."""
    AA = "AA"  # American Airlines
    DL = "DL"  # Delta Air Lines
    UA = "UA"  # United Airlines
    BA = "BA"  # British Airways
    QF = "QF"  # Qantas
    JL = "JL"  # Japan Airlines
    EK = "EK"  # Emirates
    SQ = "SQ"  # Singapore Airlines

class FlightClass(str, Enum):
    """Award flight cabin classes."""
    ECONOMY = "Economy"
    PREMIUM_ECONOMY = "Premium Economy"
    BUSINESS = "Business"
    FIRST = "First"

class AwardFlight(BaseModel):
    """Model representing an available award flight."""
    airline: Airline = Field(..., description="Airline code")
    flight_number: str = Field(..., description="Flight number")
    origin: str = Field(..., description="Origin airport IATA code")
    destination: str = Field(..., description="Destination airport IATA code")
    departure_date: date = Field(..., description="Departure date")
    return_date: Optional[date] = Field(None, description="Return date (for round trips)")
    cabin_class: FlightClass = Field(..., description="Cabin class")
    award_miles: int = Field(..., description="Miles required for award")
    taxes_fees: float = Field(..., description="Estimated taxes and fees")
    availability: int = Field(..., description="Number of seats available")
    booking_url: str = Field(..., description="Direct booking URL")
    last_updated: date = Field(..., description="Last availability check date")

class AwardSearchRequest(BaseModel):
    """Request model for award flight searches."""
    origin: str = Field(..., min_length=3, max_length=3, description="Origin airport IATA code")
    destination: str = Field(..., min_length=3, max_length=3, description="Destination airport IATA code")
    departure_date: date = Field(..., description="Departure date")
    return_date: Optional[date] = Field(None, description="Return date for round trips")
    cabin_class: FlightClass = Field(default=FlightClass.ECONOMY, description="Cabin class preference")
    airlines: Optional[list[Airline]] = Field(None, description="Filter by specific airlines")
    max_miles: Optional[int] = Field(None, description="Maximum miles to spend")
    limit: Optional[int] = Field(50, description="Maximum number of results to return")
