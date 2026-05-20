from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import re

class AirlineData(BaseModel):
    """Raw airline data from various sources"""
    airline_code: str = Field(..., min_length=2, max_length=3)
    flight_number: str = Field(..., min_length=1, max_length=6)
    departure_airport: str = Field(..., min_length=3, max_length=3)
    arrival_airport: str = Field(..., min_length=3, max_length=3)
    departure_time: datetime
    arrival_time: datetime
    base_price: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    cabin_class: str = Field(default="Economy", min_length=3, max_length=10)
    seats_available: int = Field(default=0, ge=0)
    flight_date: datetime
    data_source: str = Field(default="airline_api")
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    @validator('airline_code')
    def validate_airline_code(cls, v):
        if not re.match(r'^[A-Z]{2,3}$', v):
            raise ValueError('Invalid airline code format')
        return v

    @validator('flight_number')
    def validate_flight_number(cls, v):
        if not re.match(r'^[A-Z0-9]{1,6}$', v):
            raise ValueError('Invalid flight number format')
        return v

class FareChange(BaseModel):
    """Real-time fare change events"""
    fare_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    airline_code: str = Field(..., min_length=2, max_length=3)
    flight_number: str = Field(..., min_length=1, max_length=6)
    departure_airport: str = Field(..., min_length=3, max_length=3)
    arrival_airport: str = Field(..., min_length=3, max_length=3)
    old_price: float = Field(gt=0)
    new_price: float = Field(gt=0)
    change_percentage: float = Field(default=0.0)
    change_reason: str = Field(default="dynamic_pricing")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = Field(default="fare_aggregator")
    is_award_fare: bool = Field(default=False)

    @validator('change_percentage')
    def calculate_change(cls, v, values):
        if 'old_price' in values and 'new_price' in values:
            return ((values['new_price'] - values['old_price']) / values['old_price']) * 100
        return v

class UserSearch(BaseModel):
    """User search patterns for ML recommendations"""
    search_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    departure_airport: str = Field(..., min_length=3, max_length=3)
    arrival_airport: str = Field(..., min_length=3, max_length=3)
    departure_date: datetime
    return_date: Optional[datetime] = None
    cabin_class: str = Field(default="Economy")
    num_adults: int = Field(default=1, ge=0)
    num_children: int = Field(default=0, ge=0)
    num_infants: int = Field(default=0, ge=0)
    preferred_airlines: Optional[List[str]] = None
    max_price: Optional[float] = None
    search_timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_type: str = Field(default="desktop")

class PricingUpdate(BaseModel):
    """Real-time pricing updates for award tickets"""
    update_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flight_combination_id: str
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    base_price: float
    award_price: float
    currency: str
    cabin_class: str
    seats_available: int
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    model_version: str = Field(default="v1.0")
    update_timestamp: datetime = Field(default_factory=datetime.utcnow)
    change_reason: str = Field(default="ml_prediction")
    is_dynamic: bool = Field(default=True)

    @validator('confidence_score')
    def validate_confidence(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('Confidence score must be between 0 and 1')
        return v

class ModelInput(BaseModel):
    """Input schema for ML model inference"""
    features: List[float] = Field(..., min_items=128, max_items=128)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ModelOutput(BaseModel):
    """Output schema for ML model inference"""
    predicted_price: float
    confidence: float
    feature_importance: Dict[str, float]
    model_version: str
    inference_latency_ms: float
    prediction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class PipelineMetrics(BaseModel):
    """Metrics for pipeline monitoring"""
    events_processed: int = 0
    processing_latency_ms: float = 0.0
    throughput_events_per_sec: float = 0.0
    error_count: int = 0
    last_processed_timestamp: Optional[datetime] = None
    system_load: float = 0.0
    memory_usage_mb: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
