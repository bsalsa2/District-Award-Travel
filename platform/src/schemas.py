"""
Pydantic schemas for award availability data.
Designed for zero-copy validation and serialization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

class AwardType(str, Enum):
    """Types of award availability."""
    FLIGHT = "flight"
    HOTEL = "hotel"
    CAR = "car"
    CRUISE = "cruise"
    OTHER = "other"

class CabinClass(str, Enum):
    """Cabin classes for flights."""
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

class AwardStatus(str, Enum):
    """Status of award availability."""
    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"
    PENDING = "pending"

class Airline(BaseModel):
    """Airline information."""
    iata_code: str = Field(..., min_length=2, max_length=2, description="IATA airline code")
    icao_code: Optional[str] = Field(None, min_length=3, max_length=3, description="ICAO airline code")
    name: str = Field(..., min_length=2, description="Airline name")
    alliance: Optional[str] = Field(None, description="Airline alliance")

class Airport(BaseModel):
    """Airport information."""
    iata_code: str = Field(..., min_length=3, max_length=3, description="IATA airport code")
    icao_code: Optional[str] = Field(None, min_length=4, max_length=4, description="ICAO airport code")
    name: str = Field(..., min_length=2, description="Airport name")
    city: str = Field(..., min_length=2, description="City name")
    country: str = Field(..., min_length=2, description="Country name")
    timezone: str = Field(..., description="Timezone")

class FlightSegment(BaseModel):
    """Individual flight segment."""
    departure_airport: Airport
    arrival_airport: Airport
    departure_time: datetime
    arrival_time: datetime
    flight_number: str = Field(..., min_length=2, max_length=6)
    operating_airline: Airline
    marketing_airline: Airline
    cabin_class: CabinClass
    aircraft_type: Optional[str] = None
    flight_duration_minutes: int

class AwardAvailability(BaseModel):
    """Core award availability record."""
    id: str = Field(..., description="Unique identifier for the award")
    award_type: AwardType
    status: AwardStatus
    source: str = Field(..., description="Source of the data (e.g., 'AA_API', 'DL_API')")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Flight-specific fields
    flight_segments: Optional[List[FlightSegment]] = None
    departure_date: Optional[datetime] = None
    return_date: Optional[datetime] = None
    origin: Optional[Airport] = None
    destination: Optional[Airport] = None
    passengers: Optional[Dict[str, int]] = None  # {"adult": 1, "child": 0, ...}

    # Hotel-specific fields
    property_id: Optional[str] = None
    check_in_date: Optional[datetime] = None
    check_out_date: Optional[datetime] = None
    nights: Optional[int] = None
    room_type: Optional[str] = None

    # Car-specific fields
    vehicle_id: Optional[str] = None
    pickup_location: Optional[Airport] = None
    dropoff_location: Optional[Airport] = None
    pickup_time: Optional[datetime] = None
    dropoff_time: Optional[datetime] = None

    # Pricing
    currency: str = Field(default="USD", min_length=3, max_length=3)
    points_required: Optional[int] = None
    cash_required: Optional[float] = None
    total_price: Optional[float] = None
    taxes_fees: Optional[float] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    @validator('updated_at')
    def update_timestamp(cls, v, values):
        """Ensure updated_at is always current."""
        return datetime.utcnow()

    class Config:
        """Pydantic config for performance and compatibility."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        from_attributes = True
        arbitrary_types_allowed = True

class AwardSearchRequest(BaseModel):
    """Request schema for award availability searches."""
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[datetime] = None
    return_date: Optional[datetime] = None
    cabin_class: Optional[CabinClass] = None
    award_type: Optional[AwardType] = None
    max_points: Optional[int] = None
    min_points: Optional[int] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

class AwardSearchResponse(BaseModel):
    """Response schema for award availability searches."""
    results: List[AwardAvailability]
    total_count: int
    limit: int
    offset: int
    cached: bool = False
    query_time_ms: float

class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime
    kafka_status: str
    cassandra_status: str
    cache_status: str
    version: str = "1.0.0"
