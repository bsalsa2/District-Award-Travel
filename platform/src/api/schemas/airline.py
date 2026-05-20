from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class FlightOfferResponse(BaseModel):
    """Schema for flight offer responses"""
    airline: str = Field(..., description="Airline name")
    flight_number: str = Field(..., description="Flight number")
    departure_time: datetime = Field(..., description="Departure time")
    arrival_time: datetime = Field(..., description="Arrival time")
    origin: str = Field(..., description="Origin airport code")
    destination: str = Field(..., description="Destination airport code")
    cabin_class: str = Field(..., description="Cabin class")
    price: float = Field(..., description="Price in currency units")
    currency: str = Field(..., description="Currency code")
    offer_id: str = Field(..., description="Unique offer identifier")
    booking_url: str = Field(..., description="URL to book this offer")
    duration: int = Field(..., description="Flight duration in minutes")
    stops: int = Field(..., description="Number of stops")
    fare_basis: str = Field(..., description="Fare basis code")
    included_bags: int = Field(..., description="Number of included bags")
    timestamp: datetime = Field(..., description="When this offer was retrieved")

    class Config:
        json_schema_extra = {
            "example": {
                "airline": "United",
                "flight_number": "UA123",
                "departure_time": "2024-06-01T10:00:00",
                "arrival_time": "2024-06-01T12:30:00",
                "origin": "JFK",
                "destination": "LAX",
                "cabin_class": "economy",
                "price": 299.99,
                "currency": "USD",
                "offer_id": "offer_12345",
                "booking_url": "https://united.com/book/12345",
                "duration": 150,
                "stops": 0,
                "fare_basis": "Y",
                "included_bags": 1,
                "timestamp": "2024-05-20T15:30:00"
            }
        }

class FlightSearchRequest(BaseModel):
    """Schema for flight search requests"""
    origin: str = Field(..., min_length=3, max_length=3, description="Origin airport IATA code")
    destination: str = Field(..., min_length=3, max_length=3, description="Destination airport IATA code")
    departure_date: date = Field(..., description="Departure date")
    return_date: Optional[date] = Field(None, description="Return date (for round trips)")
    cabin_class: str = Field("economy", description="Cabin class (economy, premium_economy, business, first)")
    adults: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    max_stops: int = Field(1, ge=0, le=3, description="Maximum number of stops")

    class Config:
        json_schema_extra = {
            "example": {
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": "2024-06-01",
                "return_date": "2024-06-08",
                "cabin_class": "economy",
                "adults": 2,
                "max_stops": 1
            }
        }
