"""
Pydantic schemas for request/response validation.
Optimized for performance with proper field types and validation.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
import re

class ClientBase(BaseModel):
    """Base client schema."""
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    frequent_flyer_number: Optional[str] = Field(None, max_length=30)
    loyalty_program: Optional[str] = Field(None, max_length=30)

class ClientCreate(ClientBase):
    """Schema for creating a new client."""
    pass

class ClientResponse(ClientBase):
    """Schema for returning client data."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., max_length=50)
    email: EmailStr

class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=128)

class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str

class UserResponse(UserBase):
    """Schema for returning user data."""
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        orm_mode = True

class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str
    expires_in: int

class SearchBase(BaseModel):
    """Base search schema."""
    origin: str = Field(..., min_length=3, max_length=3, regex=r'^[A-Z]{3}$')
    destination: str = Field(..., min_length=3, max_length=3, regex=r'^[A-Z]{3}$')
    cabin_class: str = Field(..., min_length=1, max_length=10)
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=9)
    infants: int = Field(0, ge=0, le=9)
    max_stops: int = Field(99, ge=0, le=99)

class SearchCreate(SearchBase):
    """Schema for creating a new search."""
    departure_date: datetime
    return_date: Optional[datetime] = None
    max_price: Optional[float] = Field(None, gt=0)
    preferred_airlines: Optional[str] = Field(None, max_length=100)

class SearchResponse(SearchBase):
    """Schema for returning search data."""
    id: int
    client_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class SearchResultBase(BaseModel):
    """Base search result schema."""
    airline: str = Field(..., max_length=50)
    flight_number: Optional[str] = Field(None, max_length=20)
    price: float = Field(..., gt=0)
    currency: str = Field('USD', min_length=3, max_length=3)
    duration_minutes: int
    stops: int = Field(0, ge=0)
    is_available: bool = True

class SearchResultResponse(SearchResultBase):
    """Schema for returning search result data."""
    id: int
    search_id: int
    origin: str
    destination: str
    departure_time: Optional[datetime]
    arrival_time: Optional[datetime]
    booking_link: Optional[str] = Field(None, max_length=500)
    created_at: datetime

    class Config:
        orm_mode = True

class IntakeBase(BaseModel):
    """Base intake schema."""
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    email: EmailStr
    phone: str = Field(..., max_length=20)
    travel_date: Optional[datetime]
    destination: Optional[str] = Field(None, max_length=100)
    budget: Optional[float] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=500)

class IntakeCreate(IntakeBase):
    """Schema for creating a new intake."""
    pass

class IntakeResponse(IntakeBase):
    """Schema for returning intake data."""
    id: int
    client_id: int
    status: str
    created_at: datetime

    class Config:
        orm_mode = True

class AwardSearchRequest(BaseModel):
    """Schema for award search request."""
    origin: str = Field(..., min_length=3, max_length=3, regex=r'^[A-Z]{3}$')
    destination: str = Field(..., min_length=3, max_length=3, regex=r'^[A-Z]{3}$')
    cabin: str = Field(..., min_length=1, max_length=10)
    departure_date: Optional[datetime] = None
    return_date: Optional[datetime] = None

class AwardResult(BaseModel):
    """Schema for individual award result."""
    airline: str
    flight_number: str
    departure: str
    arrival: str
    price: float
    currency: str
    duration: str
    stops: int
    booking_link: str
    is_available: bool

class AwardSearchResponse(BaseModel):
    """Schema for award search response."""
    origin: str
    destination: str
    cabin: str
    departure_date: datetime
    return_date: Optional[datetime]
    results: List[AwardResult]
    search_id: int
    created_at: datetime
