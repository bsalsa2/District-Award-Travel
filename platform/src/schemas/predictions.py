from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class PredictionStatus(str, Enum):
    HIGH_AVAILABILITY = "high_availability"
    MEDIUM_AVAILABILITY = "medium_availability"
    LOW_AVAILABILITY = "low_availability"
    CRITICAL_AVAILABILITY = "critical_availability"

class RouteKey(BaseModel):
    origin: str
    destination: str
    cabin_class: str

class PredictionRequest(BaseModel):
    route: RouteKey
    departure_date: date
    return_date: Optional[date] = None
    passengers: int = 1
    currency: str = "USD"
    flexible_dates: Optional[List[date]] = None

class PredictionResponse(BaseModel):
    route_key: str
    departure_date: date
    return_date: Optional[date]
    status: PredictionStatus
    confidence: float
    predicted_availability: int
    historical_average: float
    price_forecast: Dict[str, float]
    factors: List[str]
    expires_at: datetime
    recommended_actions: List[str]

class PredictiveHoldRequest(BaseModel):
    route_key: str
    departure_date: date
    user_id: int
    hold_duration_minutes: int = 1440
    metadata: Optional[Dict[str, Any]] = None

class PredictiveHoldResponse(BaseModel):
    hold_token: str
    expiry: datetime
    route_key: str
    departure_date: date
    status: str
    metadata: Dict[str, Any]

class BatchPredictionRequest(BaseModel):
    predictions: List[PredictionRequest]
    batch_id: str
    priority: int = 0
