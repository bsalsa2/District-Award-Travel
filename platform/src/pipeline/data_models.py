"""
Data models and schemas for the award travel system.
Shared across all components.
"""

from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class TravelClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

class TravelType(str, Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
    CAR_RENTAL = "car_rental"
    PACKAGE = "package"

class UserPreference(BaseModel):
    preferred_airlines: Optional[List[str]] = None
    preferred_classes: Optional[List[TravelClass]] = None
    max_points_budget: Optional[int] = None
    preferred_destinations: Optional[List[str]] = None
    travel_frequency: Optional[str] = None  # "weekly", "monthly", "quarterly"
    preferred_seasons: Optional[List[str]] = None  # "summer", "winter", etc.

class AwardOpportunityBase(BaseModel):
    title: str
    description: str
    airline: str
    departure: str
    arrival: str
    departure_date: datetime
    return_date: Optional[datetime] = None
    travel_class: TravelClass
    travel_type: TravelType
    price_in_points: int
    cash_price: float
    availability: int
    duration_days: int
    route_distance: float
    thumbnail_url: str
    is_featured: bool = False
    tags: Optional[List[str]] = None

class AwardOpportunityCreate(AwardOpportunityBase):
    id: Optional[str] = None

class AwardOpportunityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price_in_points: Optional[int] = None
    cash_price: Optional[float] = None
    availability: Optional[int] = None
    departure_date: Optional[datetime] = None
    return_date: Optional[datetime] = None

class AwardOpportunityResponse(AwardOpportunityBase):
    id: str
    value_score: float
    ar_points: List[Dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True

class ARSessionConfig(BaseModel):
    opportunity: AwardOpportunityResponse
    ar_points: List[Dict]
    initial_camera_position: List[float]
    initial_camera_lookat: List[float]
    ambient_light: str
    directional_light: Dict
    background: str
    interaction_distance: float
    max_points_rendered: int

class SearchRequest(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[datetime] = None
    return_date: Optional[datetime] = None
    travel_class: Optional[TravelClass] = None
    max_price: Optional[int] = None
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None
    limit: int = 20
    sort_by: Optional[str] = "value"  # "value", "price", "duration", "date"

class PriceUpdate(BaseModel):
    opportunity_id: str
    new_price: int
    source: str
    timestamp: datetime = Field(default_factory=datetime.now)

class SystemMetrics(BaseModel):
    total_opportunities: int
    avg_price: float
    search_count: int
    ar_render_time: float
    cache_size: int
    loaded_opportunities: int
    user_preferences_set: bool
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    last_successful_update: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
